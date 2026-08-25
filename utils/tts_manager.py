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

from utils.app_logging import get_logger
from utils.i18n import _

logger = get_logger(__name__)

# Only import pyttsx3 when needed to avoid import errors if TTS dependencies missing
_pyttsx3 = None


def _get_pyttsx3():
    """Lazy import pyttsx3 to handle missing dependencies gracefully."""
    global _pyttsx3
    if _pyttsx3 is None:
        try:
            import pyttsx3
            _pyttsx3 = pyttsx3
        except Exception as e:
            logger.warning("pyttsx3 not available: %s", e)
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
        self._unavailable_reason = None
        self._closing = False
        self.init_tts_engine()

    def init_tts_engine(self):
        """Initialize or reinitialize the TTS engine."""
        try:
            # Check Linux espeak availability first
            if platform.system() == 'Linux' and not _check_linux_tts_available():
                # Log only. Prompt-name speech is a minor convenience, so a
                # missing espeak must never interrupt startup with a modal
                # dialog - the user is told (once) only if they actually use
                # a feature that needs speech.
                logger.info("TTS unavailable: espeak/espeak-ng not found on Linux "
                            "(install with: sudo apt install espeak)")
                self._unavailable_reason = _(
                    "Text-to-speech (prompt announcements) requires espeak. "
                    "Install it with: sudo apt install espeak"
                )
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
                logger.info("TTS unavailable: pyttsx3 could not be imported")
                self._unavailable_reason = _(
                    "Text-to-speech is unavailable because its speech engine "
                    "could not be loaded."
                )
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
            self._unavailable_reason = None
            logger.info("TTS engine initialized successfully on %s", system)

        except Exception as e:
            logger.warning("TTS initialization failed: %s", e)
            self.tts_engine = None
            self._tts_available = False
            self._unavailable_reason = _(
                "Text-to-speech could not be started on this system."
            )

    @property
    def is_available(self):
        """True when speech can actually be produced."""
        return bool(self._tts_available)

    @property
    def unavailable_reason(self):
        """A translated explanation of why TTS is off, or None."""
        return self._unavailable_reason

    def _notice_unavailable(self):
        """Tell the user once, without blocking, that speech is unavailable.

        This is only reached when the user triggers something that would have
        spoken, so it never fires during startup.
        """
        if self._warned_about_missing_tts:
            return
        self._warned_about_missing_tts = True

        reason = self._unavailable_reason or _("Text-to-speech is unavailable.")
        logger.info("TTS requested but unavailable: %s", reason)

        # Surface it in the status line if the UI is up - never a modal dialog.
        try:
            ui = getattr(self.parent, 'ui_manager', None)
            if ui is not None and hasattr(ui, 'set_status'):
                self.parent.after(0, lambda: ui.set_status(reason, "orange"))
        except Exception:
            pass  # A status update must never break speech handling

    def speak_text(self, text):
        """Speak the given text using the TTS engine."""
        # Never start new speech once the app is shutting down - a speech
        # thread that outlives the app can keep the process alive on some
        # drivers.
        if self._closing:
            return

        # Check if TTS is available
        if not self._tts_available:
            self._notice_unavailable()
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
                logger.warning("TTS playback error: %s", e)
                self.init_tts_engine()

    def cleanup(self):
        """Clean up resources before closing."""
        self._closing = True

        # Signal any speech to stop
        self.speech_should_stop.set()

        # Wait briefly for speech to stop
        if self.current_speech_thread and self.current_speech_thread.is_alive():
            self.current_speech_thread.join(0.2)

        # Clean up TTS engine. Use a bounded wait for the lock: if a speech
        # thread is wedged inside the driver we must still be able to close.
        if self.tts_engine:
            acquired = self.tts_lock.acquire(timeout=1.0)
            try:
                try:
                    self.tts_engine.stop()
                except Exception:
                    pass  # Ignore errors during cleanup
                self.tts_engine = None
            finally:
                if acquired:
                    self.tts_lock.release()
