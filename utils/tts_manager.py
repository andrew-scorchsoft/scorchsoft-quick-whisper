"""
TTSManager - Cross-platform text-to-speech for prompt name announcements.

This module provides text-to-speech functionality using pyttsx3,
which supports multiple platforms:
- Windows: SAPI5
- macOS: NSSpeechSynthesizer (nsss)
- Linux: espeak (must be installed separately)
"""
import threading
import platform
import shutil

# Only import pyttsx3 when needed to avoid import errors if TTS dependencies missing
_pyttsx3 = None


def _get_pyttsx3():
    """Lazy import pyttsx3 to handle missing dependencies gracefully."""
    global _pyttsx3
    if _pyttsx3 is None:
        try:
            import pyttsx3
            _pyttsx3 = pyttsx3
        except ImportError as e:
            print(f"pyttsx3 import error: {e}")
            _pyttsx3 = False
    return _pyttsx3 if _pyttsx3 else None


def _check_linux_tts_available():
    """Check if espeak is available on Linux."""
    if platform.system() == 'Linux':
        if not shutil.which('espeak') and not shutil.which('espeak-ng'):
            return False
    return True


class TTSManager:
    """
    Cross-platform text-to-speech manager for announcing prompt names.

    Uses pyttsx3 which automatically selects the appropriate driver:
    - Windows: SAPI5
    - macOS: NSSpeechSynthesizer
    - Linux: espeak (requires installation: sudo apt install espeak)
    """

    def __init__(self, parent):
        self.parent = parent
        self.tts_engine = None
        self.tts_lock = threading.Lock()
        self.current_speech_thread = None
        self.speech_should_stop = threading.Event()
        self._tts_available = True
        self._warned_about_missing_tts = False
        self.init_tts_engine()

    def init_tts_engine(self):
        """Initialize or reinitialize the TTS engine."""
        try:
            # Check Linux espeak availability first
            if platform.system() == 'Linux' and not _check_linux_tts_available():
                if not self._warned_about_missing_tts:
                    self._warned_about_missing_tts = True
                    print("TTS Warning: espeak not found on Linux.")
                    print("To enable TTS, install espeak: sudo apt install espeak")
                    # Schedule warning dialog on main thread
                    self.parent.after(2000, self._show_espeak_warning)
                self._tts_available = False
                return

            # Clean up existing engine if it exists
            if self.tts_engine:
                try:
                    self.tts_engine.stop()
                except Exception:
                    pass  # Ignore errors when stopping old engine

            pyttsx3 = _get_pyttsx3()
            if not pyttsx3:
                print("TTS Warning: pyttsx3 not available")
                self._tts_available = False
                return

            self.tts_engine = pyttsx3.init()

            # Platform-specific rate settings
            system = platform.system()
            if system == 'Windows':
                self.tts_engine.setProperty('rate', 175)
            elif system == 'Darwin':
                # macOS NSSpeechSynthesizer
                self.tts_engine.setProperty('rate', 180)
            else:
                # Linux espeak tends to be faster
                self.tts_engine.setProperty('rate', 160)

            self._tts_available = True
            print(f"TTS engine initialized successfully on {system}")

        except Exception as e:
            print(f"TTS initialization error: {e}")
            self.tts_engine = None
            self._tts_available = False

    def _show_espeak_warning(self):
        """Show a warning dialog about missing espeak on Linux."""
        try:
            from tkinter import messagebox
            messagebox.showinfo(
                "TTS Not Available",
                "Text-to-speech (prompt announcements) requires espeak.\n\n"
                "To enable TTS, install espeak:\n"
                "  sudo apt install espeak\n\n"
                "The application will function normally without TTS."
            )
        except Exception:
            pass  # Ignore dialog errors

    def speak_text(self, text):
        """Speak the given text using the TTS engine."""
        # Check if TTS is available
        if not self._tts_available:
            return

        # Signal any existing speech to stop
        self.speech_should_stop.set()

        # If there's a current speech thread, wait briefly for it to stop
        if self.current_speech_thread and self.current_speech_thread.is_alive():
            self.current_speech_thread.join(0.1)  # Wait max 100ms

        # Reset the stop flag
        self.speech_should_stop.clear()

        # Create and start new speech thread
        self.current_speech_thread = threading.Thread(
            target=self._speak_thread,
            args=(text,),
            daemon=True
        )
        self.current_speech_thread.start()

    def _speak_thread(self, text):
        """Thread function that actually performs the speech."""
        with self.tts_lock:
            try:
                # Reinitialize engine if needed
                if not self.tts_engine:
                    self.init_tts_engine()

                if self.tts_engine and not self.speech_should_stop.is_set():
                    try:
                        self.tts_engine.stop()
                    except Exception:
                        self.init_tts_engine()

                    if self.tts_engine:
                        self.tts_engine.say(text)

                        # Break runAndWait into smaller chunks to check for interruption
                        while not self.speech_should_stop.is_set():
                            try:
                                self.tts_engine.startLoop(False)
                                # Run a short iteration
                                if not self.tts_engine.iterate():
                                    break
                                self.tts_engine.endLoop()
                            except Exception:
                                break  # Exit loop on any TTS iteration error

                        # If we were interrupted, stop the engine
                        if self.speech_should_stop.is_set():
                            try:
                                self.tts_engine.stop()
                            except Exception:
                                pass  # Ignore errors when stopping

            except Exception as e:
                print(f"TTS error: {e}")
                self.init_tts_engine()

    def cleanup(self):
        """Clean up resources before closing."""
        # Signal any speech to stop
        self.speech_should_stop.set()

        # Wait briefly for speech to stop
        if self.current_speech_thread and self.current_speech_thread.is_alive():
            self.current_speech_thread.join(0.2)

        # Clean up TTS engine
        if self.tts_engine:
            with self.tts_lock:
                try:
                    self.tts_engine.stop()
                    self.tts_engine = None
                except Exception:
                    pass  # Ignore errors during cleanup
