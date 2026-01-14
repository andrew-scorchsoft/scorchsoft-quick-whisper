"""
Platform detection and factory functions for cross-platform support.

This module provides utilities to detect the current operating system
and return the appropriate platform-specific implementations.
"""
import platform
import subprocess
import webbrowser


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
        self.parent = parent
        self._paused = False
        self.shortcuts = {
            'record_edit': 'ctrl+alt+j',
            'record_transcribe': 'ctrl+alt+shift+j',
            'cancel_recording': 'ctrl+alt+x',
            'cycle_prompt_back': 'alt+left',
            'cycle_prompt_forward': 'alt+right'
        }

    def register_hotkeys(self):
        print("Hotkeys not available (no X11 display)")
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
        pass

    def update_shortcut_displays(self):
        pass

    def check_keyboard_shortcuts(self):
        from tkinter import messagebox
        messagebox.showinfo("Hotkeys Unavailable",
            "Global hotkeys are not available.\n\n"
            "On Linux, this requires an X11 display.\n"
            "You can still use the application via the UI buttons.")


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
            print(f"Warning: Hotkeys disabled - pynput not available: {e}")
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
            print(f"Failed to open URL via WSL interop: {e}")
            return False
    else:
        try:
            webbrowser.open(url)
            return True
        except Exception as e:
            print(f"Failed to open URL: {e}")
            return False
