"""
Windows-specific HotkeyManager implementation using pynput.

This module provides global hotkey functionality for Windows
using the pynput library.
"""
from pynput import keyboard
from pynput.keyboard import Key, KeyCode
import threading
import time

from .hotkey_base import HotkeyManagerBase


class WindowsHotkeyManager(HotkeyManagerBase):
    """
    Windows implementation of HotkeyManager using pynput.

    Uses pynput's keyboard listener to detect global hotkey combinations.
    """

    def __init__(self, parent):
        self.listener = None
        self.listener_thread = None
        self.pressed_keys = set()
        self._lock = threading.Lock()
        self._registered_hotkeys = {}
        # Track keyboard activity to detect stale listeners
        self._last_key_event_time = time.time()
        self._listener_start_time = 0
        # Threshold for considering listener stale (seconds)
        # If no key events for this long, assume listener might be dead
        self._stale_threshold = 120  # 2 minutes
        super().__init__(parent)

    def register_hotkeys(self):
        """Register all hotkeys by starting the keyboard listener."""
        try:
            if self._paused:
                return False

            # Stop existing listener if any
            self.unregister_hotkeys()

            # Build hotkey mappings
            self._registered_hotkeys = {
                self._normalize_shortcut(self.shortcuts['record_edit']):
                    lambda: self.parent.after(0, lambda: self.parent.toggle_recording("edit")),
                self._normalize_shortcut(self.shortcuts['record_transcribe']):
                    lambda: self.parent.after(0, lambda: self.parent.toggle_recording("transcribe")),
                self._normalize_shortcut(self.shortcuts['cancel_recording']):
                    lambda: self.parent.after(0, self.parent.cancel_recording),
                self._normalize_shortcut(self.shortcuts['cycle_prompt_back']):
                    lambda: self.parent.after(0, self.parent.cycle_prompt_backward),
                self._normalize_shortcut(self.shortcuts['cycle_prompt_forward']):
                    lambda: self.parent.after(0, self.parent.cycle_prompt_forward),
            }

            # Start new listener
            self.listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release
            )
            self.listener.start()
            
            # Track when listener was started and reset activity timestamp
            self._listener_start_time = time.time()
            self._last_key_event_time = time.time()

            print(f"Registered {len(self._registered_hotkeys)} hotkeys successfully (Windows/pynput)")
            return True

        except Exception as e:
            print(f"Error registering hotkeys: {e}")
            return False

    def unregister_hotkeys(self):
        """Stop the keyboard listener and clear hotkeys."""
        try:
            if self.listener:
                self.listener.stop()
                # Wait for listener thread to fully terminate to prevent duplicates
                try:
                    self.listener.join(timeout=1.0)
                except Exception:
                    pass  # Ignore join errors
                self.listener = None

            with self._lock:
                self.pressed_keys.clear()
                self._registered_hotkeys.clear()

            print("Hotkeys unregistered")
        except Exception as e:
            print(f"Error unregistering hotkeys: {e}")

    def verify_hotkeys(self):
        """Verify that the keyboard listener is running and responsive.
        
        This method performs several checks:
        1. Is the listener thread alive?
        2. Has the listener received any key events recently?
        3. Is the listener in a potentially stale state?
        
        A listener can become "stale" when Windows releases or invalidates
        the low-level keyboard hook, which can happen when:
        - The app is minimized for extended periods
        - Windows does power management/sleep cycles
        - UAC dialogs or other system events occur
        """
        try:
            if self._paused:
                return True

            if not self._registered_hotkeys:
                print("No hotkeys registered")
                return False

            if not self.listener or not self.listener.is_alive():
                print("Keyboard listener not alive")
                return False

            # Check if listener might be stale
            # The listener thread can be "alive" but the Windows hook might be dead
            current_time = time.time()
            time_since_last_event = current_time - self._last_key_event_time
            time_since_start = current_time - self._listener_start_time
            
            # Only consider staleness if listener has been running long enough
            # to have reasonably received some keyboard activity
            if time_since_start > self._stale_threshold:
                if time_since_last_event > self._stale_threshold:
                    print(f"Keyboard listener may be stale - no key events for {time_since_last_event:.0f}s")
                    # Don't immediately fail - let the health checker handle refresh
                    # This allows for cases where user genuinely hasn't typed
                    # But flag it as potentially unhealthy
                    return False

            print(f"Hotkey verification passed - listener active (last event {time_since_last_event:.0f}s ago)")
            return True

        except Exception as e:
            print(f"Error verifying hotkeys: {e}")
            return False

    def _normalize_shortcut(self, shortcut_str):
        """
        Convert a shortcut string to a frozenset of normalized key names.

        Args:
            shortcut_str: String like 'ctrl+alt+j'

        Returns:
            frozenset: Normalized key names for comparison
        """
        keys = set()
        for part in shortcut_str.lower().split('+'):
            part = part.strip()
            # Normalize key names
            if part in ('ctrl', 'control'):
                keys.add('ctrl')
            elif part == 'alt':
                keys.add('alt')
            elif part == 'shift':
                keys.add('shift')
            elif part in ('win', 'windows', 'super', 'cmd', 'command'):
                keys.add('win')
            elif part == 'left':
                keys.add('left')
            elif part == 'right':
                keys.add('right')
            else:
                keys.add(part)
        return frozenset(keys)

    def _key_to_name(self, key):
        """Convert a pynput key to a normalized name string."""
        if isinstance(key, Key):
            key_map = {
                Key.ctrl: 'ctrl',
                Key.ctrl_l: 'ctrl',
                Key.ctrl_r: 'ctrl',
                Key.alt: 'alt',
                Key.alt_l: 'alt',
                Key.alt_r: 'alt',
                Key.alt_gr: 'alt',
                Key.shift: 'shift',
                Key.shift_l: 'shift',
                Key.shift_r: 'shift',
                Key.cmd: 'win',
                Key.cmd_l: 'win',
                Key.cmd_r: 'win',
                Key.left: 'left',
                Key.right: 'right',
                Key.up: 'up',
                Key.down: 'down',
                Key.space: 'space',
                Key.enter: 'enter',
                Key.backspace: 'backspace',
                Key.delete: 'delete',
                Key.esc: 'escape',
                Key.home: 'home',
                Key.end: 'end',
                Key.page_up: 'pageup',
                Key.page_down: 'pagedown',
                Key.insert: 'insert',
                Key.f1: 'f1', Key.f2: 'f2', Key.f3: 'f3', Key.f4: 'f4',
                Key.f5: 'f5', Key.f6: 'f6', Key.f7: 'f7', Key.f8: 'f8',
                Key.f9: 'f9', Key.f10: 'f10', Key.f11: 'f11', Key.f12: 'f12',
            }
            return key_map.get(key)
        elif isinstance(key, KeyCode):
            if key.char:
                return key.char.lower()
            elif key.vk:
                # Handle virtual key codes for special keys
                # Windows virtual key codes
                vk_map = {
                    # Modifier keys
                    16: 'shift',   # VK_SHIFT
                    17: 'ctrl',    # VK_CONTROL
                    18: 'alt',     # VK_MENU (Alt)
                    160: 'shift',  # VK_LSHIFT
                    161: 'shift',  # VK_RSHIFT
                    162: 'ctrl',   # VK_LCONTROL
                    163: 'ctrl',   # VK_RCONTROL
                    164: 'alt',    # VK_LMENU (Left Alt)
                    165: 'alt',    # VK_RMENU (Right Alt)
                    91: 'win',     # VK_LWIN (Left Windows key)
                    92: 'win',     # VK_RWIN (Right Windows key)
                    # Arrow keys
                    37: 'left',    # VK_LEFT
                    38: 'up',      # VK_UP
                    39: 'right',   # VK_RIGHT
                    40: 'down',    # VK_DOWN
                    # Special keys
                    8: 'backspace',   # VK_BACK
                    9: 'tab',         # VK_TAB
                    13: 'enter',      # VK_RETURN
                    27: 'escape',     # VK_ESCAPE
                    32: 'space',      # VK_SPACE
                    33: 'pageup',     # VK_PRIOR
                    34: 'pagedown',   # VK_NEXT
                    35: 'end',        # VK_END
                    36: 'home',       # VK_HOME
                    45: 'insert',     # VK_INSERT
                    46: 'delete',     # VK_DELETE
                    # Bracket/punctuation keys
                    219: '[',      # VK_OEM_4 (left bracket)
                    221: ']',      # VK_OEM_6 (right bracket)
                    # Function keys
                    112: 'f1', 113: 'f2', 114: 'f3', 115: 'f4',
                    116: 'f5', 117: 'f6', 118: 'f7', 119: 'f8',
                    120: 'f9', 121: 'f10', 122: 'f11', 123: 'f12',
                    # Letters (A-Z) as fallback if key.char not set
                    65: 'a', 66: 'b', 67: 'c', 68: 'd', 69: 'e',
                    70: 'f', 71: 'g', 72: 'h', 73: 'i', 74: 'j',
                    75: 'k', 76: 'l', 77: 'm', 78: 'n', 79: 'o',
                    80: 'p', 81: 'q', 82: 'r', 83: 's', 84: 't',
                    85: 'u', 86: 'v', 87: 'w', 88: 'x', 89: 'y', 90: 'z',
                    # Numbers (0-9) as fallback
                    48: '0', 49: '1', 50: '2', 51: '3', 52: '4',
                    53: '5', 54: '6', 55: '7', 56: '8', 57: '9',
                }
                return vk_map.get(key.vk)
        return None

    def _on_press(self, key):
        """Handle key press events."""
        try:
            # Update activity timestamp - this proves the listener is working
            self._last_key_event_time = time.time()
            
            key_name = self._key_to_name(key)
            if key_name:
                with self._lock:
                    self.pressed_keys.add(key_name)
                    self._check_hotkeys()
        except Exception as e:
            print(f"Error in key press handler: {e}")

    def _on_release(self, key):
        """Handle key release events."""
        try:
            # Update activity timestamp - this proves the listener is working
            self._last_key_event_time = time.time()
            
            key_name = self._key_to_name(key)
            if key_name:
                with self._lock:
                    self.pressed_keys.discard(key_name)
        except Exception as e:
            print(f"Error in key release handler: {e}")

    def _check_hotkeys(self):
        """Check if currently pressed keys match any registered hotkey."""
        current_keys = frozenset(self.pressed_keys)

        for hotkey_keys, callback in self._registered_hotkeys.items():
            if hotkey_keys == current_keys:
                # Execute callback
                try:
                    callback()
                except Exception as e:
                    print(f"Error executing hotkey callback: {e}")
                break
