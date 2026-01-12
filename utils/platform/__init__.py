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
        from .hotkey_linux import LinuxHotkeyManager
        return LinuxHotkeyManager


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
