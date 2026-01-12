"""
Linux-specific HotkeyManager implementation using pynput.

This module provides global hotkey functionality for Linux
using the pynput library. Works best on X11; Wayland has limitations.
"""
import os
from pynput import keyboard
from pynput.keyboard import Key, KeyCode
import threading

from .hotkey_base import HotkeyManagerBase


def is_wayland():
    """Check if running under Wayland."""
    return os.environ.get('XDG_SESSION_TYPE', '').lower() == 'wayland'


def is_x11():
    """Check if running under X11."""
    return os.environ.get('XDG_SESSION_TYPE', '').lower() == 'x11' or \
           os.environ.get('DISPLAY') is not None


class LinuxHotkeyManager(HotkeyManagerBase):
    """
    Linux implementation of HotkeyManager using pynput.

    Uses pynput's keyboard listener to detect global hotkey combinations.
    Works best on X11; Wayland support is limited.
    """

    def __init__(self, parent):
        self.listener = None
        self.pressed_keys = set()
        self._lock = threading.Lock()
        self._registered_hotkeys = {}
        self._wayland_warning_shown = False
        super().__init__(parent)

    def register_hotkeys(self):
        """Register all hotkeys by starting the keyboard listener."""
        try:
            if self._paused:
                return False

            # Check for Wayland and warn user
            if is_wayland() and not self._wayland_warning_shown:
                self._wayland_warning_shown = True
                print("WARNING: Running under Wayland. Global hotkeys may have limited functionality.")
                print("For best hotkey support, consider using X11 or Xwayland.")
                # Schedule warning dialog on main thread
                self.parent.after(1000, self._show_wayland_warning)

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

            print(f"Registered {len(self._registered_hotkeys)} hotkeys successfully (Linux/pynput)")
            return True

        except Exception as e:
            print(f"Error registering hotkeys: {e}")
            # Check for common Linux issues
            if "Xlib" in str(e) or "display" in str(e).lower():
                print("This may be a display server issue. Ensure X11 is running or DISPLAY is set.")
            return False

    def _show_wayland_warning(self):
        """Show a warning dialog about Wayland limitations."""
        try:
            from tkinter import messagebox
            messagebox.showwarning(
                "Wayland Detected",
                "You appear to be running under Wayland.\n\n"
                "Global hotkeys may not work reliably in Wayland.\n"
                "For best results, consider:\n"
                "- Running with XWayland\n"
                "- Using X11 session instead\n\n"
                "The application will still function, but you may need "
                "to use the UI buttons instead of hotkeys."
            )
        except:
            pass

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
            elif part in ('win', 'windows', 'super', 'meta'):
                keys.add('super')
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
                Key.cmd: 'super',
                Key.cmd_l: 'super',
                Key.cmd_r: 'super',
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
                # Handle virtual key codes for special keys on Linux
                # X11 keysyms
                vk_map = {
                    65361: 'left',     # XK_Left
                    65362: 'up',       # XK_Up
                    65363: 'right',    # XK_Right
                    65364: 'down',     # XK_Down
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
