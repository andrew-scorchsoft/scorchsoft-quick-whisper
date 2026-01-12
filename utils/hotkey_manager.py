"""
HotkeyManager - Cross-platform global hotkey management.

This module provides a unified interface for managing global keyboard
hotkeys across Windows, macOS, and Linux using pynput.

The actual implementation is delegated to platform-specific classes
in the utils.platform module.
"""
from utils.platform import get_hotkey_manager_class


# Get the appropriate class for the current platform
_HotkeyManagerClass = get_hotkey_manager_class()


class HotkeyManager(_HotkeyManagerClass):
    """
    Cross-platform HotkeyManager.

    Inherits from the appropriate platform-specific implementation
    (WindowsHotkeyManager, MacOSHotkeyManager, or LinuxHotkeyManager).

    Provides the following interface:
        - register_hotkeys(): Register all hotkeys with the system
        - unregister_hotkeys(): Remove all hotkeys
        - verify_hotkeys(): Check if hotkeys are working
        - force_hotkey_refresh(callback): Refresh all hotkeys
        - pause() / resume(): Temporarily disable/enable hotkeys
        - save_shortcut_to_config(name, keys): Save a shortcut
        - check_keyboard_shortcuts(): Open the shortcuts dialog

    Default shortcuts (Windows/Linux):
        - Ctrl+Alt+J: Record + AI Edit
        - Ctrl+Alt+Shift+J: Record + Transcribe only
        - Ctrl+Alt+X: Cancel recording
        - Alt+Left: Cycle prompt backward
        - Alt+Right: Cycle prompt forward

    Default shortcuts (macOS):
        - Command+Alt+J: Record + AI Edit
        - Command+Alt+Shift+J: Record + Transcribe only
        - Command+X: Cancel recording
        - Command+[: Cycle prompt backward
        - Command+]: Cycle prompt forward
    """
    pass
