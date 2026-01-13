"""
Windows-specific SystemEventListener implementation.

This module provides system event detection for Windows using
the WTS (Windows Terminal Services) API to detect screen lock/unlock events.
"""
import threading
import time
import ctypes
from ctypes import wintypes, Structure, POINTER, WINFUNCTYPE

from .system_events_base import SystemEventListenerBase


# Define WNDCLASSW structure (not in wintypes)
class WNDCLASSW(Structure):
    """Windows WNDCLASSW structure for window class registration."""
    _fields_ = [
        ('style', wintypes.UINT),
        ('lpfnWndProc', ctypes.c_void_p),  # Will be set to WNDPROC
        ('cbClsExtra', ctypes.c_int),
        ('cbWndExtra', ctypes.c_int),
        ('hInstance', wintypes.HINSTANCE),
        ('hIcon', wintypes.HICON),
        ('hCursor', wintypes.HANDLE),
        ('hbrBackground', wintypes.HBRUSH),
        ('lpszMenuName', wintypes.LPCWSTR),
        ('lpszClassName', wintypes.LPCWSTR),
    ]


class WindowsSystemEventListener(SystemEventListenerBase):
    """
    Windows implementation of SystemEventListener.

    Uses Windows Terminal Services API (WTSRegisterSessionNotification)
    to detect screen lock/unlock events and trigger hotkey refresh.
    """

    def __init__(self, parent):
        super().__init__(parent)

        # WM_WTSSESSION_CHANGE message value
        self.WM_WTSSESSION_CHANGE = 0x02B1

        # Event constants for Windows session change
        self.WTS_SESSION_LOCK = 0x7    # User locks session
        self.WTS_SESSION_UNLOCK = 0x8   # User unlocks session

        # Other relevant constants
        self.WTS_CONSOLE_CONNECT = 0x1      # Console connect
        self.WTS_CONSOLE_DISCONNECT = 0x2   # Console disconnect
        self.WTS_REMOTE_CONNECT = 0x3       # Remote connect
        self.WTS_REMOTE_DISCONNECT = 0x4    # Remote disconnect
        self.WTS_SESSION_LOGON = 0x5        # Session logon
        self.WTS_SESSION_LOGOFF = 0x6       # Session logoff
        self.WTS_SESSION_REMOTE_CONTROL = 0x9  # Remote control
        
        # Store the WNDPROC callback to prevent garbage collection
        self._wndproc_callback = None

        # Configure ctypes for 64-bit Windows compatibility
        self._configure_ctypes()

        # Start listening automatically on Windows
        self.start_listening()

    def _configure_ctypes(self):
        """Configure ctypes function signatures for 64-bit Windows compatibility."""
        ctypes.windll.user32.DefWindowProcW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        ]
        ctypes.windll.user32.DefWindowProcW.restype = wintypes.LPARAM

    def start_listening(self):
        """Start listening for system events in a background thread."""
        if self.is_running:
            return

        self.is_running = True
        self.thread = threading.Thread(target=self._listen_for_events, daemon=True)
        self.thread.start()
        print("System event listener started (Windows)")

    def stop_listening(self):
        """Stop the listener thread."""
        self.is_running = False
        if self.thread:
            self.thread.join(1.0)  # Wait max 1 second
            self.thread = None

    def _listen_for_events(self):
        """Background thread to listen for Windows events."""
        try:
            # Create a hidden window to receive messages
            wndclass = self._create_window_class()
            hwnd = self._create_message_window(wndclass)

            if not hwnd:
                print("Failed to create message window")
                return

            # Register for session notifications - NOTIFY_FOR_ALL_SESSIONS = 1
            result = ctypes.windll.wtsapi32.WTSRegisterSessionNotification(hwnd, 1)
            if not result:
                print(f"Failed to register for session notifications: {ctypes.GetLastError()}")
                return

            print("Successfully registered for Windows session notifications")

            # Message loop
            msg = wintypes.MSG()
            while self.is_running:
                # GetMessage is blocking, so we use PeekMessage instead
                if ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):  # PM_REMOVE = 1
                    if msg.message == self.WM_WTSSESSION_CHANGE:
                        self._handle_session_change(msg.wParam)

                    # Dispatch message
                    ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                    ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

                # Sleep to reduce CPU usage
                time.sleep(0.1)

            # Cleanup
            ctypes.windll.wtsapi32.WTSUnRegisterSessionNotification(hwnd)
            ctypes.windll.user32.DestroyWindow(hwnd)
            ctypes.windll.user32.UnregisterClassW(wndclass.lpszClassName, wndclass.hInstance)

        except Exception as e:
            print(f"Error in event listener: {e}")

    def _handle_session_change(self, event_type):
        """Handle various session change events."""
        event_names = {
            self.WTS_CONSOLE_CONNECT: "Console Connect",
            self.WTS_CONSOLE_DISCONNECT: "Console Disconnect",
            self.WTS_REMOTE_CONNECT: "Remote Connect",
            self.WTS_REMOTE_DISCONNECT: "Remote Disconnect",
            self.WTS_SESSION_LOGON: "Session Logon",
            self.WTS_SESSION_LOGOFF: "Session Logoff",
            self.WTS_SESSION_LOCK: "Session Lock",
            self.WTS_SESSION_UNLOCK: "Session Unlock",
            self.WTS_SESSION_REMOTE_CONTROL: "Remote Control"
        }

        event_name = event_names.get(event_type, f"Unknown Event ({event_type})")
        print(f"Windows Session Event: {event_name}")

        # Determine if we should refresh hotkeys
        should_refresh = False
        refresh_delay = 1000  # Default delay in ms

        if event_type == self.WTS_SESSION_UNLOCK:
            print("System unlocked - will refresh hotkeys")
            should_refresh = True
            refresh_delay = 1000  # 1 second delay for unlock
        elif event_type == self.WTS_SESSION_LOCK:
            print("System locked - will preemptively refresh hotkeys on unlock")
            should_refresh = True
            refresh_delay = 1500  # 1.5 second delay for lock
        elif event_type in (self.WTS_CONSOLE_CONNECT, self.WTS_REMOTE_CONNECT, self.WTS_SESSION_LOGON):
            print("System connected/logged on - will refresh hotkeys")
            should_refresh = True
            refresh_delay = 2000  # 2 second delay for logon/connect

        # Execute the refresh on the main thread
        if should_refresh:
            self._throttled_refresh(delay_ms=refresh_delay)

    def _create_window_class(self):
        """Create a window class for the message-only window."""
        # WNDPROC signature must use pointer-sized types for 64-bit Windows compatibility
        WNDPROC = ctypes.WINFUNCTYPE(
            wintypes.LPARAM,   # LRESULT (pointer-sized return)
            wintypes.HWND,     # HWND
            wintypes.UINT,     # UINT message
            wintypes.WPARAM,   # WPARAM (pointer-sized)
            wintypes.LPARAM    # LPARAM (pointer-sized)
        )
        # Store callback to prevent garbage collection (critical!)
        self._wndproc_callback = WNDPROC(self._wnd_proc)
        
        # Use our custom WNDCLASSW structure
        wndclass = WNDCLASSW()
        wndclass.style = 0
        # Cast the callback to get its pointer value
        wndclass.lpfnWndProc = ctypes.cast(self._wndproc_callback, ctypes.c_void_p).value
        wndclass.cbClsExtra = 0
        wndclass.cbWndExtra = 0
        wndclass.hInstance = ctypes.windll.kernel32.GetModuleHandleW(None)
        wndclass.hIcon = None
        wndclass.hCursor = None
        wndclass.hbrBackground = None
        wndclass.lpszMenuName = None
        wndclass.lpszClassName = "QuickWhisperMessageWindow"

        result = ctypes.windll.user32.RegisterClassW(ctypes.byref(wndclass))
        if not result:
            error = ctypes.GetLastError()
            # Error 1410 = class already exists (OK, we can reuse it)
            if error == 1410:
                print("Window class already registered (reusing)")
            else:
                print(f"Failed to register window class: error {error}")
                return None

        return wndclass

    def _create_message_window(self, wndclass):
        """Create a message-only window to receive system events."""
        if not wndclass:
            print("Cannot create message window: wndclass is None")
            return None

        # Configure CreateWindowExW
        ctypes.windll.user32.CreateWindowExW.argtypes = [
            wintypes.DWORD,      # dwExStyle
            wintypes.LPCWSTR,    # lpClassName
            wintypes.LPCWSTR,    # lpWindowName
            wintypes.DWORD,      # dwStyle
            ctypes.c_int,        # x
            ctypes.c_int,        # y
            ctypes.c_int,        # nWidth
            ctypes.c_int,        # nHeight
            wintypes.HWND,       # hWndParent (HWND_MESSAGE = -3)
            wintypes.HMENU,      # hMenu
            wintypes.HINSTANCE,  # hInstance
            wintypes.LPVOID,     # lpParam
        ]
        ctypes.windll.user32.CreateWindowExW.restype = wintypes.HWND

        # HWND_MESSAGE = (HWND)-3 for message-only window
        HWND_MESSAGE = wintypes.HWND(-3 & 0xFFFFFFFFFFFFFFFF)  # Handle sign extension
        
        hwnd = ctypes.windll.user32.CreateWindowExW(
            0,                              # dwExStyle
            wndclass.lpszClassName,         # lpClassName
            "QuickWhisperMessageWindow",    # lpWindowName
            0,                              # dwStyle
            0, 0, 0, 0,                     # x, y, width, height
            HWND_MESSAGE,                   # hWndParent = HWND_MESSAGE
            None,                           # hMenu
            wndclass.hInstance,             # hInstance
            None                            # lpParam
        )
        
        if not hwnd:
            error = ctypes.GetLastError()
            print(f"Failed to create message window: error {error}")
            return None
        
        print(f"Message window created successfully: hwnd={hwnd}")
        return hwnd

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        """Window procedure to handle window messages.
        
        This is called directly by Windows for each message sent to our window.
        WM_WTSSESSION_CHANGE messages are sent (not posted) to the window,
        so they must be handled here in the window procedure.
        """
        try:
            if msg == self.WM_WTSSESSION_CHANGE:
                # Handle session change in the window procedure
                # wparam contains the event type (lock, unlock, etc.)
                self._handle_session_change(wparam)
        except Exception as e:
            print(f"Error in window procedure: {e}")
        
        return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)
