"""
Platform detection and factory functions for cross-platform support.

This module provides utilities to detect the current operating system
and return the appropriate platform-specific implementations.
"""
import platform


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
