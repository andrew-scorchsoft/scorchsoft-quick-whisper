import threading
from concurrent.futures import ThreadPoolExecutor
import pyaudio
import wave
from pathlib import Path
from tkinter import messagebox
from audioplayer import AudioPlayer
import os
import sys
import time
from utils.config_manager import get_config

# Memory diagnostic counters for audio subsystem
_audio_diag = {
    'sounds_played': 0,
    'streams_opened': 0,
    'streams_closed': 0,
    'frames_peak': 0,
    'recordings_started': 0,
    'recordings_stopped': 0,
}

def get_audio_diagnostics():
    """Return a copy of audio diagnostic counters."""
    return dict(_audio_diag)


class AudioManager:
    def __init__(self, parent):
        self.parent = parent
        self.audio = pyaudio.PyAudio()
        self._recording_event = threading.Event()  # Thread-safe recording flag
        self.frames = []
        self.record_thread = None
        self.stream = None
        self.device_index = None
        self.audio_file = None
        self.config = get_config()
        # Thread pool for sound playback to avoid spawning unbounded threads
        self._sound_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="sound")

    @property
    def recording(self):
        """Thread-safe check if recording is in progress."""
        return self._recording_event.is_set()

    @recording.setter
    def recording(self, value):
        """Thread-safe set recording state."""
        if value:
            self._recording_event.set()
        else:
            self._recording_event.clear()
        
    def get_input_devices(self):
        """Get a list of available input audio devices."""
        devices = {}
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                devices[info['name']] = i
        return devices

    def get_device_index_by_name(self, device_name):
        """Find device index based on selected device name (input devices only)."""
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            # Must match name AND be an input device (maxInputChannels > 0)
            if info['name'] == device_name and info['maxInputChannels'] > 0:
                return i
        raise ValueError(f"Input device '{device_name}' not found.")
        
    def start_recording(self):
        """Start recording audio from the selected device."""
        selected_name = self.parent.selected_device.get()

        # Check if we have valid audio devices
        if selected_name == "No audio devices found" or not selected_name:
            messagebox.showerror("No Audio Device",
                "No audio input device available. Please connect a microphone and restart the application.")
            return False

        print(f"Getting Device Index for: '{selected_name}'")
        try:
            self.device_index = self.get_device_index_by_name(selected_name)
            # Log the actual device info for verification
            device_info = self.audio.get_device_info_by_index(self.device_index)
            print(f"Recording from device index {self.device_index}: '{device_info['name']}' (Input channels: {device_info['maxInputChannels']})")
        except ValueError as e:
            messagebox.showerror("Device Error", str(e))
            return False

        print("Starting Stream")
        self.stream = self.audio.open(format=pyaudio.paInt16,
                                      channels=1,
                                      rate=16000,
                                      input=True,
                                      frames_per_buffer=1024,
                                      input_device_index=self.device_index)

        self.frames = []
        self.recording = True

        # Update UI in parent - now through ui_manager
        self.parent.ui_manager.update_button_states(recording=True)
        self.parent.ui_manager.set_status("Recording...", "red")

        _audio_diag['recordings_started'] += 1
        _audio_diag['streams_opened'] += 1

        # Play start recording sound
        self._sound_pool.submit(self.play_sound, "assets/pop.wav")

        # Start recording in a separate thread
        print("Starting Recording")
        self.record_thread = threading.Thread(target=self.record, daemon=True)
        print("Starting Recording thread")
        self.record_thread.start()
        return True

    def record(self):
        """Record audio data from the stream."""
        while self._recording_event.is_set():
            try:
                # Use a smaller timeout to allow checking the stop flag more frequently
                if self.stream and self.stream.is_active():
                    data = self.stream.read(1024, exception_on_overflow=False)
                    self.frames.append(data)
                else:
                    break
            except OSError as e:
                # Stream was closed - this is expected when stopping
                if not self._recording_event.is_set():
                    break
                print(f"Recording OSError: {e}")
                break
            except Exception as e:
                print(f"Recording error: {e}")
                # Only show error dialog if we're still supposed to be recording
                if self._recording_event.is_set():
                    self.parent.after(0, lambda: messagebox.showerror("Recording error", f"An error occurred while Recording: {e}"))
                break

    def stop_recording(self):
        """Stop recording and save the audio file."""
        self.recording = False

        # Wait for record thread to finish with timeout
        if self.record_thread:
            self.record_thread.join(timeout=2.0)
            if self.record_thread.is_alive():
                print("Warning: Record thread did not stop in time")

        # Safely close the stream
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                print(f"Error closing stream: {e}")
            finally:
                self.stream = None

        print(f"Stopping, about to trigger '{self.parent.current_button_mode}' mode...")

        # Reset buttons to normal state - now through ui_manager
        self.parent.ui_manager.update_button_states(recording=False)

        _audio_diag['recordings_stopped'] += 1
        _audio_diag['streams_closed'] += 1
        self.parent.ui_manager.set_status("Processing - Audio File...", "green")

        # Play stop recording sound
        self._sound_pool.submit(self.play_sound, "assets/pop-down.wav")

        # Ensure tmp folder exists
        tmp_dir = self.parent.tmp_dir
        tmp_dir.mkdir(parents=True, exist_ok=True)

        # Determine filename based on file handling setting
        file_handling = self.config.file_handling
        
        if file_handling == "timestamp":
            # Create timestamped filename
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{timestamp}.wav"
        else:
            # Default: overwrite the same file
            filename = "temp_recording.wav"
        
        self.audio_file = tmp_dir / filename
        print(f"Saving Recording to {self.audio_file}")

        with wave.open(str(self.audio_file), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(16000)
            wf.writeframes(b''.join(self.frames))

        # Track peak frame count then release memory
        _audio_diag['frames_peak'] = max(_audio_diag['frames_peak'], len(self.frames))
        self.frames = []

        return self.audio_file
    
    def cancel_recording(self):
        """Cancels the current recording without processing."""
        if self.recording:
            self.recording = False

            # Wait for record thread to finish with timeout
            if self.record_thread:
                self.record_thread.join(timeout=2.0)
                if self.record_thread.is_alive():
                    print("Warning: Record thread did not stop in time during cancel")

            # Safely close the stream
            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except Exception as e:
                    print(f"Error closing stream during cancel: {e}")
                finally:
                    self.stream = None

            # Reset buttons back to original state - now through ui_manager
            self.parent.ui_manager.update_button_states(recording=False)

            _audio_diag['streams_closed'] += 1

            # Release recorded frames on cancel
            self.frames = []

            # Reset status
            self.parent.ui_manager.set_status("Idle", "blue")

            # Play failure sound
            self._sound_pool.submit(self.play_sound, "assets/wrong-short.wav")
            return True
        return False
    
    def retry_last_recording(self):
        """Retry processing the last recorded audio file."""
        file_handling = self.config.file_handling
        
        if file_handling == "timestamp":
            # Find the most recent recording file
            try:
                recording_files = list(self.parent.tmp_dir.glob("recording_*.wav"))
                if recording_files:
                    # Sort by modification time and get the most recent
                    last_recording = max(recording_files, key=lambda f: f.stat().st_mtime)
                else:
                    messagebox.showerror("Retry Failed", "No previous recordings found.")
                    return False
            except Exception as e:
                messagebox.showerror("Retry Failed", f"Error finding previous recordings: {e}")
                return False
        else:
            # Default: look for temp_recording.wav
            last_recording = self.parent.tmp_dir / "temp_recording.wav"

        if last_recording.exists():
            # Play start recording sound
            self._sound_pool.submit(self.play_sound, "assets/pop.wav")

            self.audio_file = last_recording
            self.parent.ui_manager.set_status("Retrying transcription...", "orange")

            # Re-attempt transcription in a separate thread
            threading.Thread(target=self.parent.transcribe_audio, daemon=True).start()
            return True
        else:
            messagebox.showerror("Retry Failed", "No previous recording found to retry.")
            return False
    
    def play_sound(self, sound_file):
        """Play sound with fallback for Mac compatibility.

        Explicitly closes the AudioPlayer after playback to prevent
        resource leaks (COM handles on Windows, file descriptors on other platforms).
        """
        player = None
        try:
            player = AudioPlayer(self.resource_path(sound_file))
            player.play(block=True)
            _audio_diag['sounds_played'] += 1
        except Exception as e:
            print(f"Warning: Could not play sound: {e}")
        finally:
            # Explicitly release the player to free OS-level resources
            if player is not None:
                try:
                    player.close()
                except Exception:
                    pass
                del player
            
    def resource_path(self, relative_path):
        """Get the absolute path to the resource, works for both development and PyInstaller environments."""
        try:
            base_path = sys._MEIPASS
        except AttributeError:
            base_path = os.path.dirname(os.path.abspath(sys.argv[0]))

        # Handle icon files differently for Mac
        is_mac = self.parent.is_mac
        if is_mac and relative_path.endswith('.ico'):
            # Use .png version instead of .ico for Mac
            relative_path = relative_path.replace('.ico', '.png')

        abs_path = os.path.join(base_path, relative_path)
        return abs_path
    
    def cleanup(self):
        """Clean up resources when closing."""
        try:
            if self.recording:
                self.stop_recording()
            self.audio.terminate()
        except Exception as e:
            print(f"Error during audio cleanup: {e}")
            # Continue with termination even if stop_recording fails
            try:
                self.audio.terminate()
            except Exception as e2:
                print(f"Error during audio termination: {e2}")
        # Shutdown the sound thread pool
        try:
            self._sound_pool.shutdown(wait=False)
        except Exception:
            pass
        # Release any held frame data
        self.frames = []