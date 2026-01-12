"""
SystemEventListener - Cross-platform system event detection.

This module provides a unified interface for detecting system events
(like screen lock/unlock) that may require hotkey refresh.

The actual implementation is delegated to platform-specific classes
in the utils.platform module:
- Windows: Uses WTS API for session notifications
- macOS/Linux: Relies on periodic health checker (no native detection)
"""
from utils.platform import get_system_event_listener_class


# Get the appropriate class for the current platform
_SystemEventListenerClass = get_system_event_listener_class()


class SystemEventListener(_SystemEventListenerClass):
    """
    Cross-platform SystemEventListener.

    Inherits from the appropriate platform-specific implementation
    (WindowsSystemEventListener or UnixSystemEventListener).

    On Windows, actively monitors for:
        - Screen lock/unlock events
        - Remote connect/disconnect
        - Session logon/logoff

    On macOS/Linux, relies on the application's periodic health checker
    to verify and refresh hotkeys as needed.
    """
    pass
