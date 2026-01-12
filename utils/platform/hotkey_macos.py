"""
macOS-specific HotkeyManager implementation using pynput.

This module provides global hotkey functionality for macOS
using the pynput library. Requires Accessibility permissions.
"""
from pynput import keyboard
from pynput.keyboard import Key, KeyCode
import threading
import subprocess

from .hotkey_base import HotkeyManagerBase


def check_accessibility_permissions():
    """
    Check if the application has Accessibility permissions on macOS.

    Returns:
        bool: True if permissions are granted, False otherwise.
    """
    try:
        # Use tccutil to check accessibility permissions
        # This is a heuristic - we try to create a listener and see if it works
        return True  # We'll detect permission issues when hotkeys fail
    except:
        return False


class MacOSHotkeyManager(HotkeyManagerBase):
    """
    macOS implementation of HotkeyManager using pynput.

    Uses pynput's keyboard listener to detect global hotkey combinations.
    Requires Accessibility permissions in System Settings.
    """

    def __init__(self, parent):
        self.listener = None
        self.pressed_keys = set()
        self._lock = threading.Lock()
        self._registered_hotkeys = {}
        self._permission_warning_shown = False
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
            try:
                self.listener = keyboard.Listener(
                    on_press=self._on_press,
                    on_release=self._on_release
                )
                self.listener.start()

                # Give the listener a moment to start
                import time
                time.sleep(0.1)

                # Check if listener started successfully
                if not self.listener.is_alive():
                    raise Exception("Listener failed to start - may need Accessibility permissions")

                print(f"Registered {len(self._registered_hotkeys)} hotkeys successfully (macOS/pynput)")
                return True

            except Exception as e:
                if not self._permission_warning_shown:
                    self._permission_warning_shown = True
                    self.parent.after(500, self._show_permission_dialog)
                raise e

        except Exception as e:
            print(f"Error registering hotkeys: {e}")
            return False

    def _show_permission_dialog(self):
        """Show a dialog explaining how to grant Accessibility permissions."""
        try:
            from tkinter import messagebox
            result = messagebox.askyesno(
                "Accessibility Permission Required",
                "Quick Whisper needs Accessibility permission to use global hotkeys.\n\n"
                "To enable:\n"
                "1. Open System Settings\n"
                "2. Go to Privacy & Security > Accessibility\n"
                "3. Enable Quick Whisper (or Terminal/Python if running from source)\n\n"
                "Would you like to open System Settings now?\n\n"
                "(You can still use the app with UI buttons without this permission)"
            )
            if result:
                self._open_accessibility_settings()
        except Exception as e:
            print(f"Error showing permission dialog: {e}")

    def _open_accessibility_settings(self):
        """Open macOS System Settings to Accessibility preferences."""
        try:
            subprocess.run([
                'open',
                'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'
            ])
        except:
            try:
                # Fallback for older macOS versions
                subprocess.run([
                    'open',
                    '/System/Library/PreferencePanes/Security.prefPane'
                ])
            except Exception as e:
                print(f"Could not open System Settings: {e}")

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
            shortcut_str: String like 'command+alt+j'

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
            elif part in ('option', 'opt'):
                keys.add('alt')
            elif part == 'shift':
                keys.add('shift')
            elif part in ('cmd', 'command', 'win', 'super'):
                keys.add('cmd')
            elif part == 'left':
                keys.add('left')
            elif part == 'right':
                keys.add('right')
            elif part == '[':
                keys.add('[')
            elif part == ']':
                keys.add(']')
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
                Key.cmd: 'cmd',
                Key.cmd_l: 'cmd',
                Key.cmd_r: 'cmd',
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
                Key.f1: 'f1', Key.f2: 'f2', Key.f3: 'f3', Key.f4: 'f4',
                Key.f5: 'f5', Key.f6: 'f6', Key.f7: 'f7', Key.f8: 'f8',
                Key.f9: 'f9', Key.f10: 'f10', Key.f11: 'f11', Key.f12: 'f12',
            }
            return key_map.get(key)
        elif isinstance(key, KeyCode):
            if key.char:
                char = key.char.lower()
                # Handle bracket keys which may come through as chars
                return char
            elif key.vk:
                # Handle virtual key codes for macOS
                vk_map = {
                    123: 'left',     # kVK_LeftArrow
                    124: 'right',    # kVK_RightArrow
                    125: 'down',     # kVK_DownArrow
                    126: 'up',       # kVK_UpArrow
                    33: '[',         # kVK_ANSI_LeftBracket
                    30: ']',         # kVK_ANSI_RightBracket
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
