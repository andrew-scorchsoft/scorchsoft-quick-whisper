import threading
import platform
import time
import ctypes
from ctypes import wintypes

# Define WNDCLASSW structure manually if not available
if not hasattr(wintypes, 'WNDCLASSW'):
    class WNDCLASSW(ctypes.Structure):
        _fields_ = [('style', ctypes.c_uint),
                    ('lpfnWndProc', ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)),
                    ('cbClsExtra', ctypes.c_int),
                    ('cbWndExtra', ctypes.c_int),
                    ('hInstance', ctypes.c_void_p),
                    ('hIcon', ctypes.c_void_p),
                    ('hCursor', ctypes.c_void_p),
                    ('hbrBackground', ctypes.c_void_p),
                    ('lpszMenuName', ctypes.c_wchar_p),
                    ('lpszClassName', ctypes.c_wchar_p)]
else:
    WNDCLASSW = wintypes.WNDCLASSW

class SystemEventListener:
    def __init__(self, parent):
        self.parent = parent
        self.is_running = False
        self.thread = None
        self.last_refresh_time = 0
        
        # Only initialize on Windows
        if platform.system() == 'Windows':
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
            
            # Register for session change notifications
            self.start_listening()
    
    def start_listening(self):
        """Start listening for system events in a background thread"""
        if self.is_running:
            return
            
        self.is_running = True
        self.thread = threading.Thread(target=self._listen_for_events, daemon=True)
        self.thread.start()
        print("System event listener started")
    
    def stop_listening(self):
        """Stop the listener thread"""
        self.is_running = False
        if self.thread:
            self.thread.join(1.0)  # Wait max 1 second
            self.thread = None
    
    def _listen_for_events(self):
        """Background thread to listen for Windows events"""
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
        """Handle various session change events"""
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
            # Prevent too frequent refreshes (throttle to 3 seconds)
            current_time = int(time.time())
            if current_time - self.last_refresh_time >= 3:
                self.last_refresh_time = current_time
                self.parent.after(refresh_delay, self._refresh_hotkeys)
            else:
                print("Skipping refresh - too soon since last refresh")
    
    def _refresh_hotkeys(self):
        """Execute hotkey refresh on the main thread"""
        print("System event triggered hotkey refresh")
        if hasattr(self.parent, 'hotkey_manager'):
            self.parent.hotkey_manager.force_hotkey_refresh()
        else:
            print("Error: Cannot refresh hotkeys - hotkey_manager not found")
    
    def _create_window_class(self):
        """Create a window class for the message-only window"""
        wndclass = WNDCLASSW()
        wndclass.style = 0
        wndclass.lpfnWndProc = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_int, ctypes.c_uint, ctypes.c_int, ctypes.c_int
        )(self._wnd_proc)
        wndclass.cbClsExtra = 0
        wndclass.cbWndExtra = 0
        wndclass.hInstance = ctypes.windll.kernel32.GetModuleHandleW(None)
        wndclass.hIcon = 0
        wndclass.hCursor = 0
        wndclass.hbrBackground = 0
        wndclass.lpszMenuName = 0
        wndclass.lpszClassName = "QuickWhisperMessageWindow"
        
        if not ctypes.windll.user32.RegisterClassW(ctypes.byref(wndclass)):
            print(f"Failed to register window class: {ctypes.GetLastError()}")
            return None
            
        return wndclass
        
    def _create_message_window(self, wndclass):
        """Create a message-only window to receive system events"""
        if not wndclass:
            return None
            
        # HWND_MESSAGE = -3
        return ctypes.windll.user32.CreateWindowExW(
            0, wndclass.lpszClassName, "QuickWhisperMessageWindow",
            0, 0, 0, 0, 0, -3, 0, wndclass.hInstance, 0
        )
    
    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        """Window procedure to handle window messages"""
        # We handle WM_WTSSESSION_CHANGE in _listen_for_events now
        return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)