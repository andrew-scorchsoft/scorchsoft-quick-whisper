"""
Unix (macOS/Linux) SystemEventListener fallback implementation.

This module provides a minimal system event listener for macOS and Linux.
Unlike Windows, these platforms don't have a simple API for detecting
screen lock/unlock events. Instead, we rely on the application's
periodic hotkey health checker (already implemented in the main app).

Future enhancements could include:
- macOS: NSDistributedNotificationCenter for screen lock events
- Linux: D-Bus systemd-logind session signals

For now, this is a no-op implementation that gracefully handles
the lack of native event detection.
"""
from .system_events_base import SystemEventListenerBase


class UnixSystemEventListener(SystemEventListenerBase):
    """
    Unix (macOS/Linux) fallback implementation of SystemEventListener.

    This is a minimal implementation that relies on the application's
    periodic hotkey health checker rather than native event detection.

    The main application already has a 30-second health checker that
    verifies hotkeys are working and refreshes them if needed.
    """

    def __init__(self, parent):
        super().__init__(parent)
        # Don't start any listener - rely on health checker
        print("System event listener initialized (Unix fallback - using health checker)")

    def start_listening(self):
        """
        Start listening for system events.

        On Unix platforms, this is a no-op as we rely on the periodic
        health checker instead of native event detection.
        """
        self.is_running = True
        print("System event listener: Unix platforms use periodic health checker")

    def stop_listening(self):
        """Stop the listener (no-op on Unix)."""
        self.is_running = False
