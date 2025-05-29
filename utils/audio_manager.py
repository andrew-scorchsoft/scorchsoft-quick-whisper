import threading
import pyaudio
import wave
from pathlib import Path
from tkinter import messagebox
from audioplayer import AudioPlayer
import os
import sys

class AudioManager:
    def __init__(self, parent):
        self.parent = parent
        self.audio = pyaudio.PyAudio()
        self.recording = False
        self.frames = []
        self.record_thread = None
        self.stream = None
        self.device_index = None
        self.audio_file = None
        
    def get_input_devices(self):
        """Get a list of available input audio devices."""
        devices = {}
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                devices[info['name']] = i
        return devices

    def get_device_index_by_name(self, device_name):
        """Find device index based on selected device name."""
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            if info['name'] == device_name:
                return i
        raise ValueError(f"Device '{device_name}' not found.")
        
    def start_recording(self):
        """Start recording audio from the selected device."""
        print("Getting Device Index")
        try:
            self.device_index = self.get_device_index_by_name(self.parent.selected_device.get())
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
        self.parent.ui_manager.record_button_transcribe.configure(text="Stop and Process", fg_color="red", hover_color="#a83232")
        self.parent.ui_manager.record_button_edit.configure(text="Stop and Process", fg_color="red", hover_color="#a83232")
        self.parent.ui_manager.set_status("Recording...", "red")

        # Play start recording sound
        threading.Thread(target=lambda: self.play_sound("assets/pop.wav")).start()

        # Start recording in a separate thread
        print("Starting Recording")
        self.record_thread = threading.Thread(target=self.record, daemon=True)
        print("Starting Recording thread")
        self.record_thread.start()
        return True

    def record(self):
        """Record audio data from the stream."""
        while self.recording:
            try:
                data = self.stream.read(1024)
                self.frames.append(data)
            except Exception as e:
                print(f"Recording error: {e}")
                messagebox.showerror("Recording error", f"An error occurred while Recording: {e}")
                break

    def stop_recording(self):
        """Stop recording and save the audio file."""
        self.recording = False
        if self.record_thread:
            self.record_thread.join()

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

        print(f"Stopping, about to trigger '{self.parent.current_button_mode}' mode...")

        # Reset buttons to normal state with correct colors - now through ui_manager
        self.parent.ui_manager.record_button_transcribe.configure(
            fg_color="#058705",
            hover_color="#046a38"
        )
        self.parent.ui_manager.record_button_edit.configure(
            fg_color="#058705",
            hover_color="#046a38"
        )

        # Update the buttons with correct shortcuts
        self.parent.hotkey_manager.update_shortcut_displays()

        self.parent.ui_manager.set_status("Processing - Audio File...", "green")

        # Play stop recording sound
        threading.Thread(target=lambda: self.play_sound("assets/pop-down.wav")).start()

        # Ensure tmp folder exists
        tmp_dir = self.parent.tmp_dir
        tmp_dir.mkdir(parents=True, exist_ok=True)

        # Determine filename based on file handling setting
        file_handling = os.getenv("FILE_HANDLING", "overwrite")
        
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

        return self.audio_file
    
    def cancel_recording(self):
        """Cancels the current recording without processing."""
        if self.recording:
            self.recording = False
            if self.record_thread:
                self.record_thread.join()

            if self.stream:
                self.stream.stop_stream()
                self.stream.close()

            # Reset buttons back to original state - now through ui_manager
            self.parent.ui_manager.record_button_transcribe.configure(
                fg_color="#058705", 
                hover_color="#046a38"
            )
            self.parent.ui_manager.record_button_edit.configure(
                fg_color="#058705", 
                hover_color="#046a38"
            )
            
            # Update button text
            self.parent.hotkey_manager.update_shortcut_displays()

            # Reset status
            self.parent.ui_manager.set_status("Idle", "blue")

            # Play failure sound
            threading.Thread(target=lambda: self.play_sound("assets/wrong-short.wav")).start()
            return True
        return False
    
    def retry_last_recording(self):
        """Retry processing the last recorded audio file."""
        file_handling = os.getenv("FILE_HANDLING", "overwrite")
        
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
            threading.Thread(target=lambda: self.play_sound("assets/pop.wav")).start()

            self.audio_file = last_recording
            self.parent.ui_manager.set_status("Retrying transcription...", "orange")
            
            # Re-attempt transcription in a separate thread
            threading.Thread(target=self.parent.transcribe_audio).start()
            return True
        else:
            messagebox.showerror("Retry Failed", "No previous recording found to retry.")
            return False
    
    def play_sound(self, sound_file):
        """Play sound with fallback for Mac compatibility"""
        try:
            player = AudioPlayer(self.resource_path(sound_file))
            player.play(block=True)
        except Exception as e:
            print(f"Warning: Could not play sound: {e}")
            # Silently fail if sound doesn't work on Mac
            pass
            
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
            except:
                pass 