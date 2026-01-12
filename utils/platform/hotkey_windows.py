"""
Windows-specific HotkeyManager implementation using pynput.

This module provides global hotkey functionality for Windows
using the pynput library.
"""
from pynput import keyboard
from pynput.keyboard import Key, KeyCode
import threading

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
                self.listener = None

            with self._lock:
                self.pressed_keys.clear()
                self._registered_hotkeys.clear()

            print("Hotkeys unregistered")
        except Exception as e:
            print(f"Error unregistering hotkeys: {e}")

    def verify_hotkeys(self):
        """Verify that the keyboard listener is running."""
        try:
            if self._paused:
                return True

            if not self._registered_hotkeys:
                print("No hotkeys registered")
                return False

            if not self.listener or not self.listener.is_alive():
                print("Keyboard listener not alive")
                return False

            print("Hotkey verification passed - listener is active")
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
                    37: 'left',    # VK_LEFT
                    38: 'up',      # VK_UP
                    39: 'right',   # VK_RIGHT
                    40: 'down',    # VK_DOWN
                    219: '[',      # VK_OEM_4 (left bracket)
                    221: ']',      # VK_OEM_6 (right bracket)
                }
                return vk_map.get(key.vk)
        return None

    def _on_press(self, key):
        """Handle key press events."""
        try:
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
