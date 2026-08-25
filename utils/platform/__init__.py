"""
Platform detection and factory functions for cross-platform support.

This module provides utilities to detect the current operating system
and return the appropriate platform-specific implementations.
"""
import platform
import subprocess
import webbrowser

from utils.app_logging import get_logger

logger = get_logger(__name__)


def get_platform():
    """
    Return normalized platform name.

    Returns:
        str: 'windows', 'macos', or 'linux'
    """
    system = platform.system()
    if system == 'Windows':
        return 'windows'
    elif system == 'Darwin':
        return 'macos'
    else:
        return 'linux'


CURRENT_PLATFORM = get_platform()
IS_WINDOWS = CURRENT_PLATFORM == 'windows'
IS_MACOS = CURRENT_PLATFORM == 'macos'
IS_LINUX = CURRENT_PLATFORM == 'linux'


def _detect_wsl():
    """Detect if running inside Windows Subsystem for Linux."""
    if not IS_LINUX:
        return False
    try:
        with open('/proc/version', 'r') as f:
            version_info = f.read().lower()
            return 'microsoft' in version_info or 'wsl' in version_info
    except (FileNotFoundError, PermissionError):
        return False


IS_WSL = _detect_wsl()


class _NoOpHotkeyManager:
    """Fallback hotkey manager when pynput is not available (e.g., Linux without X11)."""

    def __init__(self, parent):
        from utils.config_manager import get_config
        self.parent = parent
        self._paused = False
        self.config = get_config()
        self.shortcuts = {
            'record_edit': 'ctrl+alt+j',
            'record_transcribe': 'ctrl+alt+shift+j',
            'cancel_recording': 'ctrl+alt+x',
            'cycle_prompt_back': 'alt+left',
            'cycle_prompt_forward': 'alt+right'
        }

    def register_hotkeys(self):
        logger.info("Hotkeys not available (no X11 display)")
        return False

    def unregister_hotkeys(self):
        pass

    def verify_hotkeys(self):
        return False

    def force_hotkey_refresh(self, callback=None):
        if callback:
            callback(False)
        return False

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def load_shortcuts_from_config(self):
        """Mirror the configured shortcuts so the UI can still display them."""
        try:
            for name in list(self.shortcuts):
                configured = self.config.get_shortcut(name)
                if configured:
                    self.shortcuts[name] = configured
        except Exception:
            pass

    def update_shortcut_displays(self):
        pass

    # The real managers expose these; without them this class is a trap for the
    # next caller that reaches for one on the no-hotkey path.
    def _get_default_shortcuts(self):
        return dict(self.shortcuts)

    def format_shortcut(self, keys):
        modifier_order = ['ctrl', 'alt', 'shift', 'win', 'command']
        modifiers = [k for k in keys if k in modifier_order]
        regular = [k for k in keys if k not in modifier_order]
        return "+".join(sorted(modifiers, key=modifier_order.index) + sorted(regular))

    def save_shortcut_to_config(self, shortcut_name, key_combination):
        combo = key_combination if isinstance(key_combination, str) else self.format_shortcut(key_combination)
        try:
            self.config.set_shortcut(shortcut_name, combo)
            self.config.save_settings()
        except Exception:
            logger.warning("Could not save shortcut %s with no hotkey backend", shortcut_name)
        self.shortcuts[shortcut_name] = combo

    def reset_shortcuts_to_default(self, shortcuts_window=None):
        self.shortcuts = self._get_default_shortcuts()

    def check_keyboard_shortcuts(self):
        from tkinter import messagebox
        from utils.i18n import _
        messagebox.showinfo(_("Hotkeys Unavailable"),
            _("Global hotkeys are not available.\n\n"
              "On Linux, this requires an X11 display.\n"
              "You can still use the application via the UI buttons."))


def get_hotkey_manager_class():
    """
    Factory function to get the appropriate HotkeyManager class for current OS.

    Returns:
        class: Platform-specific HotkeyManager class
    """
    if IS_WINDOWS:
        from .hotkey_windows import WindowsHotkeyManager
        return WindowsHotkeyManager
    elif IS_MACOS:
        from .hotkey_macos import MacOSHotkeyManager
        return MacOSHotkeyManager
    else:
        try:
            from .hotkey_linux import LinuxHotkeyManager
            return LinuxHotkeyManager
        except ImportError as e:
            # pynput requires X11 on Linux - if not available, use no-op fallback
            logger.warning("Warning: Hotkeys disabled - pynput not available: %s", e)
            return _NoOpHotkeyManager


def get_system_event_listener_class():
    """
    Factory function to get the appropriate SystemEventListener class for current OS.

    Returns:
        class: Platform-specific SystemEventListener class
    """
    if IS_WINDOWS:
        from .system_events_windows import WindowsSystemEventListener
        return WindowsSystemEventListener
    else:
        # macOS and Linux use the same fallback implementation
        from .system_events_unix import UnixSystemEventListener
        return UnixSystemEventListener


def open_url(url):
    """
    Open a URL in the system's default browser.

    Handles WSL specially by using Windows browser via cmd.exe interop.

    Args:
        url: The URL to open

    Returns:
        bool: True if successful, False otherwise
    """
    if IS_WSL:
        try:
            # Use cmd.exe to open URL in Windows default browser
            # The /c flag runs the command and terminates
            subprocess.run(
                ['cmd.exe', '/c', 'start', '', url],
                check=True,
                capture_output=True
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.error("Failed to open URL via WSL interop: %s", e)
            return False
    else:
        try:
            webbrowser.open(url)
            return True
        except Exception as e:
            logger.error("Failed to open URL: %s", e)
            return False
