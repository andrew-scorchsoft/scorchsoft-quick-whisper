import threading
from concurrent.futures import ThreadPoolExecutor
import math
import pyaudio
import wave
from array import array
from pathlib import Path
from tkinter import messagebox
from audioplayer import AudioPlayer
import os
import sys
import time
from datetime import datetime
from utils.config_manager import get_config
from utils.app_logging import get_logger
from utils.i18n import _

logger = get_logger(__name__)

# ``audioop`` is the cheap way to get an RMS out of a PCM buffer, but it was
# removed from the standard library in Python 3.13. Fall back to a small
# pure-stdlib implementation so the app runs on both.
try:  # pragma: no cover - depends on interpreter version
    import audioop  # type: ignore
except Exception:  # pragma: no cover
    audioop = None

# Recording format constants (16 kHz mono 16-bit PCM = 32 KB/sec).
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
SAMPLE_WIDTH = 2

# Level meter scaling. Raw linear RMS barely moves for speech, so the level is
# mapped onto a dB scale: METER_FLOOR_DB -> 0.0, full scale -> 1.0.
METER_FLOOR_DB = -60.0

# A recording whose loudest buffer never gets above this normalised level is
# treated as "nothing was said". Kept deliberately low (roughly -55 dBFS) so
# genuinely quiet speech still counts as signal.
SILENCE_PEAK_THRESHOLD = 0.08

# How long before the recording limit the user starts being warned.
LIMIT_WARNING_SECONDS = 30.0

# If the main loop cannot be reached to perform the auto-stop, keep trying for
# this long before ending capture anyway.
LIMIT_STOP_GRACE_SECONDS = 120.0

# Memory diagnostic counters for audio subsystem
_audio_diag = {
    'sounds_played': 0,
    'streams_opened': 0,
    'streams_closed': 0,
    'frames_peak': 0,
    'recordings_started': 0,
    'recordings_stopped': 0,
    'recordings_discarded': 0,
    'recordings_pruned': 0,
}

def get_audio_diagnostics():
    """Return a copy of audio diagnostic counters."""
    return dict(_audio_diag)


def _buffer_rms(data):
    """Return the RMS (0-32768) of a mono 16-bit PCM buffer.

    Uses ``audioop`` where available and falls back to ``array`` arithmetic on
    interpreters that no longer ship it (Python 3.13+).
    """
    if not data:
        return 0.0
    if audioop is not None:
        try:
            return float(audioop.rms(data, SAMPLE_WIDTH))
        except Exception:
            return 0.0
    try:
        samples = array('h')
        # array.frombytes needs a whole number of items.
        usable = len(data) - (len(data) % SAMPLE_WIDTH)
        samples.frombytes(data[:usable])
        if sys.byteorder == 'big':
            samples.byteswap()
        if not samples:
            return 0.0
        total = 0
        for s in samples:
            total += s * s
        return math.sqrt(total / len(samples))
    except Exception:
        return 0.0


def _rms_to_level(rms):
    """Map an RMS value onto a 0.0-1.0 meter level using a dB scale."""
    if rms <= 0:
        return 0.0
    db = 20.0 * math.log10(min(rms, 32767.0) / 32768.0)
    if db <= METER_FLOOR_DB:
        return 0.0
    level = (db - METER_FLOOR_DB) / (0.0 - METER_FLOOR_DB)
    return max(0.0, min(1.0, level))


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

        # Recording feedback state, written by the record thread and polled by
        # the UI (never the other way around - no Tk from this thread).
        self.current_level = 0.0
        self.peak_level = 0.0
        self.limit_warning_active = False
        self._record_start_time = None
        self._limit_reached = False

        # Guards start/stop/cancel against re-entrancy (double hotkey presses,
        # the auto-stop firing while the user is already stopping, and so on).
        self._transition_lock = threading.RLock()
        self._stopping = False
        self._shutdown = False
        self._retention_ran = False

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

    # ------------------------------------------------------------------
    # Recording feedback (polled by UIManager)
    # ------------------------------------------------------------------

    def get_elapsed_seconds(self):
        """Seconds since recording started; 0.0 when not recording."""
        start = self._record_start_time
        if start is None:
            return 0.0
        return max(0.0, time.monotonic() - start)

    def _reset_level_state(self):
        """Zero the meter/timer state. Safe to call from any thread."""
        self.current_level = 0.0
        self.peak_level = 0.0
        self.limit_warning_active = False
        self._limit_reached = False
        self._record_start_time = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _play_async(self, sound_file):
        """Queue a sound on the pool, tolerating a shut-down pool."""
        if self._shutdown:
            return
        try:
            self._sound_pool.submit(self.play_sound, sound_file)
        except RuntimeError:
            # Pool already shut down (app closing) - not worth a sound.
            logger.debug("Sound pool closed; skipping %s", sound_file)
        except Exception as e:
            logger.warning("Could not queue sound %s: %s", sound_file, e)

    def _ui(self, method, *args, **kwargs):
        """Call a UIManager method defensively (main thread only)."""
        try:
            ui = getattr(self.parent, 'ui_manager', None)
            fn = getattr(ui, method, None)
            if callable(fn):
                fn(*args, **kwargs)
        except Exception as e:
            logger.debug("UI call %s failed: %s", method, e)

    def _show_error(self, title, message):
        """Show an error box without blocking the caller."""
        try:
            self.parent.after(0, lambda: messagebox.showerror(title, message))
        except Exception:
            logger.error("%s: %s", title, message)

    def _show_info(self, title, message):
        """Show an informational box without blocking the caller."""
        try:
            self.parent.after(0, lambda: messagebox.showinfo(title, message))
        except Exception:
            logger.info("%s: %s", title, message)

    def get_input_devices(self):
        """Get a list of available input audio devices.

        A device can vanish between the count and the per-index query (USB
        headset unplugged mid-enumeration), so each lookup is guarded.
        """
        devices = {}
        try:
            count = self.audio.get_device_count()
        except Exception as e:
            logger.error("Could not enumerate audio devices: %s", e, exc_info=True)
            return devices

        for i in range(count):
            try:
                info = self.audio.get_device_info_by_index(i)
            except Exception as e:
                logger.debug("Skipping audio device %s: %s", i, e)
                continue
            try:
                if info['maxInputChannels'] > 0:
                    devices[info['name']] = i
            except (KeyError, TypeError):
                continue
        return devices

    def get_device_index_by_name(self, device_name):
        """Find device index based on selected device name (input devices only)."""
        try:
            count = self.audio.get_device_count()
        except Exception as e:
            logger.error("Could not enumerate audio devices: %s", e, exc_info=True)
            raise ValueError(_("Input device '{name}' not found.").format(name=device_name))

        for i in range(count):
            try:
                info = self.audio.get_device_info_by_index(i)
            except Exception as e:
                logger.debug("Skipping audio device %s: %s", i, e)
                continue
            try:
                # Must match name AND be an input device (maxInputChannels > 0)
                if info['name'] == device_name and info['maxInputChannels'] > 0:
                    return i
            except (KeyError, TypeError):
                continue
        raise ValueError(_("Input device '{name}' not found.").format(name=device_name))

    # ------------------------------------------------------------------
    # Recording lifecycle
    # ------------------------------------------------------------------

    def start_recording(self):
        """Start recording audio from the selected device."""
        with self._transition_lock:
            if self.recording:
                logger.debug("start_recording ignored - already recording")
                return False

            selected_name = self.parent.selected_device.get()

            # Check if we have valid audio devices
            if selected_name == "No audio devices found" or not selected_name:
                messagebox.showerror(_("No Audio Device"),
                    _("No audio input device available. Please connect a microphone and restart the application."))
                return False

            logger.debug("Getting device index for: '%s'", selected_name)
            try:
                self.device_index = self.get_device_index_by_name(selected_name)
                # Log the actual device info for verification
                device_info = self.audio.get_device_info_by_index(self.device_index)
                logger.info("Recording from device index %s: '%s' (input channels: %s)",
                            self.device_index, device_info['name'], device_info['maxInputChannels'])
            except ValueError as e:
                messagebox.showerror(_("Device Error"), str(e))
                self._ui('refresh_device_list')
                return False
            except Exception as e:
                logger.error("Could not resolve input device: %s", e, exc_info=True)
                messagebox.showerror(_("Device Error"), str(e))
                self._ui('refresh_device_list')
                return False

            logger.debug("Opening audio stream")
            try:
                self.stream = self.audio.open(format=pyaudio.paInt16,
                                              channels=1,
                                              rate=SAMPLE_RATE,
                                              input=True,
                                              frames_per_buffer=CHUNK_SIZE,
                                              input_device_index=self.device_index)
            except Exception as e:
                # Device busy, unplugged since startup, or otherwise unusable.
                logger.error("Could not open audio input stream: %s", e, exc_info=True)
                self.stream = None
                self.recording = False
                self._reset_level_state()
                self._ui('update_button_states', recording=False)
                self._ui('set_status', _("Idle"), "blue")
                self._ui('refresh_device_list')
                messagebox.showerror(
                    _("Microphone Unavailable"),
                    _("Could not start recording from '{device}'.\n\n"
                      "The microphone may be in use by another application, or it may "
                      "have been unplugged. Close any app that might be using it, or "
                      "pick a different input device, then try again.\n\nDetails: {error}"
                      ).format(device=selected_name, error=e))
                self._play_async("assets/wrong-short.wav")
                return False

            self.frames = []
            # A previous file must never survive into a new take - a retry
            # after a cancelled recording would otherwise re-send it.
            self.audio_file = None
            self._reset_level_state()
            self._stopping = False
            self._record_start_time = time.monotonic()
            self.recording = True

            # Update UI in parent - now through ui_manager
            self._ui('update_button_states', recording=True)
            self._ui('set_status', _("Recording..."), "red")
            self._ui('start_level_monitor')

            _audio_diag['recordings_started'] += 1
            _audio_diag['streams_opened'] += 1

            # Play start recording sound
            self._play_async("assets/pop.wav")

            # Start recording in a separate thread
            self.record_thread = threading.Thread(target=self.record, daemon=True)
            self.record_thread.start()
            logger.info("Recording started")
            return True

    def record(self):
        """Record audio data from the stream, tracking level and elapsed time."""
        max_minutes = 0
        try:
            max_minutes = int(self.config.max_recording_minutes or 0)
        except Exception:
            max_minutes = 0
        max_seconds = max_minutes * 60 if max_minutes > 0 else 0
        warn_at = max_seconds - LIMIT_WARNING_SECONDS if max_seconds else 0
        if max_seconds and warn_at < max_seconds * 0.5:
            # Very short limits: warn from halfway instead of a fixed 30s.
            warn_at = max_seconds * 0.5

        while self._recording_event.is_set():
            try:
                # Take a local reference: another thread may clear self.stream.
                stream = self.stream
                if stream is None or not stream.is_active():
                    break
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                self.frames.append(data)

                # Cheap per-buffer level for the meter.
                level = _rms_to_level(_buffer_rms(data))
                self.current_level = level
                if level > self.peak_level:
                    self.peak_level = level

                if max_seconds:
                    elapsed = self.get_elapsed_seconds()
                    if not self.limit_warning_active and elapsed >= warn_at:
                        self.limit_warning_active = True
                        logger.warning(
                            "Approaching the %s minute recording limit (%.0fs elapsed)",
                            max_minutes, elapsed)
                    if elapsed >= max_seconds and not self._limit_reached:
                        logger.warning(
                            "Recording limit of %s minutes reached - stopping and "
                            "processing what has been captured", max_minutes)
                        # Hand back to the main thread; never touch Tk here.
                        try:
                            self.parent.after(0, self._stop_due_to_limit)
                            self._limit_reached = True
                            break
                        except Exception as e:
                            # Could not reach the main loop. Keep capturing and
                            # try again shortly rather than stranding the take,
                            # but do not run away with memory either.
                            logger.error("Could not schedule limit stop: %s", e, exc_info=True)
                            if elapsed >= max_seconds + LIMIT_STOP_GRACE_SECONDS:
                                logger.error("Giving up on the main loop; ending capture")
                                self.recording = False
                                break
            except OSError as e:
                # Stream was closed - this is expected when stopping
                if not self._recording_event.is_set():
                    break
                logger.warning("Recording OSError: %s", e)
                break
            except Exception as e:
                logger.error("Recording error: %s", e, exc_info=True)
                # Only show error dialog if we're still supposed to be recording
                if self._recording_event.is_set():
                    self._show_error(_("Recording Error"),
                                     _("An error occurred while recording: {error}").format(error=e))
                break

        self.current_level = 0.0

    def _stop_due_to_limit(self):
        """Main-thread callback: stop at the size limit but keep the audio."""
        if not self.recording:
            return
        try:
            max_minutes = int(self.config.max_recording_minutes or 0)
        except Exception:
            max_minutes = 0
        self._show_info(
            _("Recording Limit Reached"),
            _("Recording stopped automatically after {minutes} minutes to stay "
              "within the upload size limit. What you have said so far is being "
              "processed now.").format(minutes=max_minutes))
        # Route through the app so transcription is kicked off exactly as it
        # would be for a manual stop.
        try:
            stop = getattr(self.parent, 'stop_recording', None)
            if callable(stop):
                stop()
                return
        except Exception as e:
            logger.error("Parent stop_recording failed: %s", e, exc_info=True)
        self.stop_recording()

    def _teardown_stream(self, context="stop"):
        """Join the record thread and close the stream. Returns True if closed."""
        if self.record_thread:
            self.record_thread.join(timeout=2.0)
            if self.record_thread.is_alive():
                logger.warning("Record thread did not stop in time during %s", context)
        self.record_thread = None

        closed = False
        stream = self.stream
        self.stream = None
        if stream is not None:
            try:
                stream.stop_stream()
            except Exception as e:
                logger.debug("Error stopping stream during %s: %s", context, e)
            try:
                stream.close()
                closed = True
            except Exception as e:
                logger.warning("Error closing stream during %s: %s", context, e)
        return closed

    def stop_recording(self):
        """Stop recording and save the audio file.

        Returns the path of the saved file, or ``None`` when the recording
        should not be transcribed (too short, silent, or unsaveable).
        """
        with self._transition_lock:
            if self._stopping:
                logger.debug("stop_recording ignored - already stopping")
                return None
            if not self.recording and not self.frames:
                logger.debug("stop_recording called while not recording")
                return None
            self._stopping = True

        try:
            self.recording = False

            elapsed = self.get_elapsed_seconds()
            peak = self.peak_level

            if self._teardown_stream("stop"):
                _audio_diag['streams_closed'] += 1

            logger.info("Stopping recording (mode='%s', %.1fs, peak level %.3f)",
                        getattr(self.parent, 'current_button_mode', '?'), elapsed, peak)

            # Reset buttons to normal state - now through ui_manager
            self._ui('update_button_states', recording=False)
            self._ui('stop_level_monitor')

            _audio_diag['recordings_stopped'] += 1

            frames = self.frames
            self.frames = []
            _audio_diag['frames_peak'] = max(_audio_diag['frames_peak'], len(frames))

            total_bytes = sum(len(f) for f in frames)
            duration = total_bytes / float(SAMPLE_RATE * SAMPLE_WIDTH) if total_bytes else 0.0

            discard_reason = self._discard_reason(duration, peak, elapsed)
            if discard_reason:
                _audio_diag['recordings_discarded'] += 1
                logger.info("Discarding recording: %s (%.2fs, peak %.3f)",
                            discard_reason, duration, peak)
                self.audio_file = None
                self._reset_level_state()
                self._ui('set_status', _("Idle"), "blue")
                self._play_async("assets/wrong-short.wav")
                self._show_info(_("Nothing to Transcribe"), discard_reason)
                return None

            self._ui('set_status', _("Processing - Audio File..."), "green")

            # Play stop recording sound
            self._play_async("assets/pop-down.wav")

            saved = self._write_wave(frames)
            self._reset_level_state()
            if saved is not None:
                self._schedule_retention_cleanup(keep=saved)
            return saved
        finally:
            self._stopping = False

    def _discard_reason(self, duration, peak, elapsed=0.0):
        """Return a user-facing reason to skip transcription, else None.

        ``duration`` is what was actually captured and ``elapsed`` is wall
        clock. They usually match, but a driver that drops buffers can make
        the captured audio shorter - so the length test uses whichever is
        longer, and only a genuinely brief press is rejected.
        """
        if duration <= 0:
            return _("No audio was captured, so there is nothing to transcribe.")

        try:
            min_seconds = float(self.config.min_recording_seconds)
        except Exception:
            min_seconds = 0.4
        if min_seconds > 0 and max(duration, elapsed) < min_seconds:
            return _("That recording was too short ({duration:.1f}s) to transcribe. "
                     "Hold the shortcut a little longer and speak before releasing it."
                     ).format(duration=duration)

        try:
            discard_silent = bool(self.config.discard_silent_recordings)
        except Exception:
            discard_silent = True
        if discard_silent and peak < SILENCE_PEAK_THRESHOLD:
            return _("No speech was detected in that recording, so it was not sent for "
                     "transcription. Check that the right microphone is selected and "
                     "that it is not muted.")
        return None

    def _write_wave(self, frames):
        """Write the captured frames to disk. Returns the path or None."""
        try:
            # Ensure tmp folder exists
            tmp_dir = Path(self.parent.tmp_dir)
            tmp_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error("Could not create recording directory: %s", e, exc_info=True)
            self._ui('set_status', _("Idle"), "blue")
            self._show_error(_("Save Failed"),
                             _("Could not create the recording folder:\n{error}").format(error=e))
            self._play_async("assets/wrong-short.wav")
            return None

        # Determine filename based on file handling setting
        if self.config.file_handling == "timestamp":
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{timestamp}.wav"
        else:
            # Default: overwrite the same file
            filename = "temp_recording.wav"

        target = tmp_dir / filename
        logger.info("Saving recording to %s", target)
        try:
            with wave.open(str(target), 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(b''.join(frames))
        except Exception as e:
            # Full disk, read-only folder, path no longer valid, ...
            logger.error("Could not write recording to %s: %s", target, e, exc_info=True)
            self.audio_file = None
            self._ui('set_status', _("Idle"), "blue")
            self._show_error(
                _("Save Failed"),
                _("The recording could not be saved to:\n{path}\n\n"
                  "Check that the location exists and has free space.\n\nDetails: {error}"
                  ).format(path=target, error=e))
            self._play_async("assets/wrong-short.wav")
            return None

        self.audio_file = target
        return target

    def cancel_recording(self):
        """Cancels the current recording without processing."""
        with self._transition_lock:
            if not self.recording:
                logger.debug("cancel_recording ignored - not recording")
                return False
            # Clear the flag first so the record thread stops on its next
            # buffer (~64 ms) even if this call arrives moments after start.
            self.recording = False
            self._stopping = True

        try:
            if self._teardown_stream("cancel"):
                _audio_diag['streams_closed'] += 1

            # Reset buttons back to original state - now through ui_manager
            self._ui('update_button_states', recording=False)
            self._ui('stop_level_monitor')

            # Release recorded frames on cancel and make sure a later retry
            # cannot pick up a file from this abandoned take.
            self.frames = []
            self.audio_file = None
            self._reset_level_state()

            # Reset status
            self._ui('set_status', _("Idle"), "blue")

            # Play failure sound
            self._play_async("assets/wrong-short.wav")
            logger.info("Recording cancelled")
            return True
        finally:
            self._stopping = False

    def retry_last_recording(self, mode=None):
        """Retry processing the last recorded audio file.

        Args:
            mode: "edit", "transcribe", or None to reuse the last mode used.
        """
        if self.recording:
            messagebox.showinfo(_("Retry Unavailable"),
                                _("Stop the current recording before retrying the previous one."))
            return False

        file_handling = self.config.file_handling

        if file_handling == "timestamp":
            # Find the most recent recording file
            try:
                recording_files = list(Path(self.parent.tmp_dir).glob("recording_*.wav"))
                if recording_files:
                    # Sort by modification time and get the most recent
                    last_recording = max(recording_files, key=lambda f: f.stat().st_mtime)
                else:
                    messagebox.showerror(_("Retry Failed"), _("No previous recordings found."))
                    return False
            except Exception as e:
                logger.error("Error finding previous recordings: %s", e, exc_info=True)
                messagebox.showerror(_("Retry Failed"),
                                     _("Error finding previous recordings: {error}").format(error=e))
                return False
        else:
            # Default: look for temp_recording.wav
            last_recording = Path(self.parent.tmp_dir) / "temp_recording.wav"

        if last_recording.exists():
            if mode in ("edit", "transcribe"):
                self.parent.current_button_mode = mode
            logger.info("Retrying '%s' on %s",
                        getattr(self.parent, 'current_button_mode', '?'), last_recording)

            # Play start recording sound
            self._play_async("assets/pop.wav")

            self.audio_file = last_recording
            self._ui('set_status', _("Retrying transcription..."), "orange")

            # Re-attempt transcription in a separate thread
            threading.Thread(target=self.parent.transcribe_audio, daemon=True).start()
            return True
        else:
            logger.warning("Retry requested but %s does not exist", last_recording)
            messagebox.showerror(_("Retry Failed"), _("No previous recording found to retry."))
            return False

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------

    def _schedule_retention_cleanup(self, keep=None):
        """Prune old recordings on a background thread (once per session)."""
        if self._retention_ran or self._shutdown:
            return
        self._retention_ran = True
        try:
            threading.Thread(target=self.prune_old_recordings,
                             kwargs={'keep': keep},
                             name="recording-retention",
                             daemon=True).start()
        except Exception as e:
            logger.debug("Could not start retention thread: %s", e)

    def prune_old_recordings(self, keep=None, directory=None):
        """Delete ``recording_*.wav`` files older than the retention window.

        Only ever touches files matching the app's own recording naming
        pattern. ``recording_retention_days`` of 0 means keep forever.
        """
        try:
            days = int(self.config.recording_retention_days)
        except Exception:
            days = 14
        if days <= 0:
            logger.debug("Recording retention disabled; keeping everything")
            return 0

        try:
            tmp_dir = Path(directory) if directory else Path(self.parent.tmp_dir)
        except Exception as e:
            logger.debug("No recording directory to prune: %s", e)
            return 0
        if not tmp_dir.is_dir():
            return 0

        cutoff = time.time() - (days * 86400)
        keep_resolved = None
        if keep is not None:
            try:
                keep_resolved = Path(keep).resolve()
            except Exception:
                keep_resolved = None

        removed = 0
        for path in tmp_dir.glob("recording_*.wav"):
            try:
                if not path.is_file():
                    continue
                if keep_resolved is not None and path.resolve() == keep_resolved:
                    continue
                if path.stat().st_mtime >= cutoff:
                    continue
                path.unlink()
                removed += 1
                logger.info("Deleted old recording %s", path.name)
            except OSError as e:
                # In use, permission denied, removed by someone else - skip it.
                logger.debug("Could not delete %s: %s", path, e)
            except Exception as e:
                logger.debug("Skipping %s during retention sweep: %s", path, e)

        if removed:
            _audio_diag['recordings_pruned'] += removed
            logger.info("Retention sweep removed %s recording(s) older than %s day(s) from %s",
                        removed, days, tmp_dir)
        else:
            logger.debug("Retention sweep removed nothing from %s", tmp_dir)
        return removed

    # ------------------------------------------------------------------
    # Sound / resources
    # ------------------------------------------------------------------

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
            logger.warning("Could not play sound %s: %s", sound_file, e)
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
        self._shutdown = True
        try:
            if self.recording:
                # Closing mid-recording: drop the take rather than kicking off
                # a transcription the user will never see.
                self.cancel_recording()
        except Exception as e:
            logger.error("Error stopping recording during cleanup: %s", e, exc_info=True)
        try:
            self.audio.terminate()
        except Exception as e:
            logger.error("Error during audio termination: %s", e, exc_info=True)
        # Shutdown the sound thread pool
        try:
            self._sound_pool.shutdown(wait=False)
        except Exception:
            pass
        # Release any held frame data
        self.frames = []
        self._reset_level_state()
