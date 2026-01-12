"""
Base class for platform-specific SystemEventListener implementations.

This module provides the abstract base class for detecting system events
like screen lock/unlock that require hotkey refresh.
"""
import threading
import time
from abc import ABC, abstractmethod


class SystemEventListenerBase(ABC):
    """
    Abstract base class for system event listeners.

    Detects system events (like screen lock/unlock) that may require
    hotkey refresh to maintain functionality.
    """

    def __init__(self, parent):
        self.parent = parent
        self.is_running = False
        self.thread = None
        self.last_refresh_time = 0

    @abstractmethod
    def start_listening(self):
        """Start listening for system events in a background thread."""
        pass

    @abstractmethod
    def stop_listening(self):
        """Stop the listener thread."""
        pass

    def _refresh_hotkeys(self):
        """Execute hotkey refresh on the main thread."""
        print("System event triggered hotkey refresh")
        if hasattr(self.parent, 'hotkey_manager'):
            self.parent.hotkey_manager.force_hotkey_refresh()
        else:
            print("Error: Cannot refresh hotkeys - hotkey_manager not found")

    def _throttled_refresh(self, delay_ms=1000, min_interval_sec=3):
        """
        Schedule a throttled hotkey refresh.

        Args:
            delay_ms: Delay before refresh in milliseconds
            min_interval_sec: Minimum seconds between refreshes
        """
        current_time = int(time.time())
        if current_time - self.last_refresh_time >= min_interval_sec:
            self.last_refresh_time = current_time
            self.parent.after(delay_ms, self._refresh_hotkeys)
        else:
            print("Skipping refresh - too soon since last refresh")
