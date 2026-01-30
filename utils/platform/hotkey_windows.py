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
    
    MODIFIER_KEYS = frozenset({'ctrl', 'alt', 'shift', 'win'})
    
    # Maximum time a key can be "pressed" before we assume the release was missed
    KEY_EXPIRY_SECONDS = 30.0
    
    # Keys pressed more than this many seconds ago are ignored when matching hotkeys
    # This filters out stale/phantom keys that weren't properly released
    KEY_RELEVANCE_SECONDS = 3.0

    def __init__(self, parent):
        self.listener = None
        self.listener_thread = None
        self.pressed_keys = set()
        self._key_press_times = {}  # Track when each key was pressed
        self._lock = threading.Lock()
        self._registered_hotkeys = {}
        # Track keyboard activity to detect stale listeners
        self._last_key_event_time = time.time()
        self._last_modifier_event_time = time.time()  # Track modifier keys separately
        self._listener_start_time = 0
        # Threshold for considering listener stale (seconds)
        self._stale_threshold = 120  # 2 minutes
        # Track statistics for diagnostics
        self._total_key_events = 0
        self._total_modifier_events = 0
        self._hotkey_triggers = 0
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
            
            # Wait for the listener to fully initialize its Windows hook
            # pynput's start() is async - the hook isn't ready immediately
            try:
                # Use wait() with timeout if available, otherwise small delay
                if hasattr(self.listener, 'wait'):
                    self.listener.wait()
                else:
                    time.sleep(0.1)  # Give the hook time to initialize
            except Exception:
                time.sleep(0.1)
            
            # Track when listener was started and reset activity timestamps
            self._listener_start_time = time.time()
            self._last_key_event_time = time.time()
            self._last_modifier_event_time = time.time()
            
            # Clear pressed_keys AFTER new listener is ready
            # This prevents stale keys from previous listener affecting new one
            with self._lock:
                self.pressed_keys.clear()
                self._key_press_times.clear()

            print(f"Registered {len(self._registered_hotkeys)} hotkeys successfully (Windows/pynput)")
            return True

        except Exception as e:
            print(f"Error registering hotkeys: {e}")
            return False

    def unregister_hotkeys(self):
        """Stop the keyboard listener and clear hotkeys."""
        try:
            if self.listener:
                old_listener = self.listener
                self.listener = None
                old_listener.stop()
                # Wait longer for listener thread to fully terminate to prevent
                # leaked Windows keyboard hooks (a known source of memory leaks)
                try:
                    old_listener.join(timeout=5.0)
                    if old_listener.is_alive():
                        print("[MEMORY] WARNING: pynput listener thread did not terminate within 5s - potential leak")
                except Exception:
                    pass

            with self._lock:
                self.pressed_keys.clear()
                self._key_press_times.clear()
                self._registered_hotkeys.clear()

            print("Hotkeys unregistered")
        except Exception as e:
            print(f"Error unregistering hotkeys: {e}")

    def verify_hotkeys(self):
        """Verify that the keyboard listener is running and responsive.
        
        This method performs diagnostic checks and returns detailed status.
        
        IMPORTANT: This check can return True even when hotkeys don't work!
        The listener can receive regular key events while failing to receive
        modifier key combinations. Use this for diagnostics, not as a gate
        for whether to refresh hotkeys.
        
        Checks performed:
        1. Is the listener thread alive?
        2. Has the listener received any key events recently?
        3. Has the listener received modifier key events recently?
        4. Statistics on key events and hotkey triggers
        """
        try:
            if self._paused:
                return True

            if not self._registered_hotkeys:
                print("HEALTH CHECK: FAIL - No hotkeys registered")
                return False

            if not self.listener or not self.listener.is_alive():
                print("HEALTH CHECK: FAIL - Keyboard listener thread not alive")
                return False

            current_time = time.time()
            time_since_last_event = current_time - self._last_key_event_time
            time_since_last_modifier = current_time - self._last_modifier_event_time
            time_since_start = current_time - self._listener_start_time
            
            # Build diagnostic message
            status_parts = []
            is_healthy = True
            
            # Check for completely dead listener (no events at all)
            if time_since_start > self._stale_threshold and time_since_last_event > self._stale_threshold:
                status_parts.append(f"NO EVENTS for {time_since_last_event:.0f}s")
                is_healthy = False
            else:
                status_parts.append(f"last_event={time_since_last_event:.0f}s")
            
            # Check for modifier key events - this is the key diagnostic
            # If we're receiving regular events but no modifier events, hotkeys likely broken
            if time_since_start > 30:  # Only check after listener has been running a bit
                if time_since_last_modifier > 60 and time_since_last_event < 30:
                    # Receiving regular keys but no modifier keys for a while - suspicious
                    status_parts.append(f"NO MODIFIERS for {time_since_last_modifier:.0f}s (SUSPICIOUS)")
                    is_healthy = False
                else:
                    status_parts.append(f"last_modifier={time_since_last_modifier:.0f}s")
            
            # Add statistics
            status_parts.append(f"keys={self._total_key_events}")
            status_parts.append(f"mods={self._total_modifier_events}")
            status_parts.append(f"triggers={self._hotkey_triggers}")
            
            status_str = ", ".join(status_parts)
            
            if is_healthy:
                print(f"HEALTH CHECK: OK - {status_str}")
            else:
                print(f"HEALTH CHECK: SUSPICIOUS - {status_str}")
            
            return is_healthy

        except Exception as e:
            print(f"HEALTH CHECK: ERROR - {e}")
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
        """Convert a pynput key to a normalized name string.
        
        IMPORTANT: For letter and number keys, we ALWAYS use virtual key codes (vk)
        instead of key.char. This is because when Ctrl+Alt is held on Windows,
        it's often interpreted as AltGr (used for typing special characters in 
        some keyboard layouts). This causes key.char to return the AltGr character
        (e.g., '!' for AltGr+J on some layouts) instead of the actual key pressed.
        
        Virtual key codes represent the physical key, not the character produced,
        so they're immune to keyboard layout transformations.
        """
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
            # ALWAYS check virtual key codes FIRST for letters and numbers.
            # This prevents keyboard layout transformations (Ctrl+Alt → AltGr)
            # from polluting our pressed_keys set with wrong characters.
            if key.vk:
                # Letters (A-Z): vk codes 65-90 → always use these for hotkey detection
                if 65 <= key.vk <= 90:
                    return chr(key.vk).lower()  # 65 → 'a', 66 → 'b', etc.
                
                # Numbers (0-9): vk codes 48-57 → always use these for hotkey detection
                if 48 <= key.vk <= 57:
                    return chr(key.vk)  # 48 → '0', 49 → '1', etc.
                
                # Handle other virtual key codes for special keys
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
                }
                result = vk_map.get(key.vk)
                if result:
                    return result
            
            # Fall back to key.char ONLY for keys not handled above (symbols, etc.)
            # This is safe because we've already handled letters/numbers via vk codes
            if key.char and len(key.char) == 1 and 32 <= ord(key.char) <= 126:
                return key.char.lower()
            
        return None

    def _on_press(self, key):
        """Handle key press events."""
        try:
            current_time = time.time()
            
            # Update activity timestamp - this proves the listener is working
            self._last_key_event_time = current_time
            self._total_key_events += 1
            
            key_name = self._key_to_name(key)
            if key_name:
                # Track modifier key events separately - these are critical for hotkeys
                if key_name in self.MODIFIER_KEYS:
                    self._last_modifier_event_time = current_time
                    self._total_modifier_events += 1
                
                with self._lock:
                    # Clean up expired keys before adding new one
                    self._cleanup_expired_keys(current_time)
                    
                    self.pressed_keys.add(key_name)
                    self._key_press_times[key_name] = current_time
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
                    self._key_press_times.pop(key_name, None)
                    
                    # When a modifier key is released, clear any non-modifier keys
                    # This prevents stray characters from accumulating due to:
                    # - Missed release events
                    # - Keys that leaked in during modifier combinations
                    if key_name in self.MODIFIER_KEYS:
                        # Check if any modifiers are still held
                        remaining_modifiers = self.pressed_keys & self.MODIFIER_KEYS
                        if not remaining_modifiers:
                            # All modifiers released - clear any lingering non-modifier keys
                            non_modifiers = self.pressed_keys - self.MODIFIER_KEYS
                            if non_modifiers:
                                current_time = time.time()
                                ages = [round(current_time - self._key_press_times.get(k, current_time), 1) for k in non_modifiers]
                                print(f"[HOTKEY] Clearing {len(non_modifiers)} stray key(s) on modifier release: {non_modifiers} ages={ages}s")
                                self.pressed_keys.clear()
                                self._key_press_times.clear()
        except Exception as e:
            print(f"Error in key release handler: {e}")

    def _cleanup_expired_keys(self, current_time):
        """Remove keys that have been 'pressed' for too long (missed release events).
        
        Must be called while holding self._lock.
        """
        expired_keys = []
        expired_ages = []
        for key_name, press_time in self._key_press_times.items():
            age = current_time - press_time
            if age > self.KEY_EXPIRY_SECONDS:
                expired_keys.append(key_name)
                expired_ages.append(round(age, 1))
        
        if expired_keys:
            print(f"[HOTKEY] Expiring {len(expired_keys)} stale key(s): {expired_keys} ages={expired_ages}s")
            for key_name in expired_keys:
                self.pressed_keys.discard(key_name)
                self._key_press_times.pop(key_name, None)

    def _check_hotkeys(self):
        """Check if currently pressed keys match any registered hotkey."""
        current_time = time.time()
        
        # Defensive: filter out any invalid keys (non-printable chars that may have leaked in)
        valid_keys = {k for k in self.pressed_keys if len(k) == 1 and ord(k) >= 32 or len(k) > 1}
        
        # Defensive: if pressed_keys has grown unreasonably large, it's corrupted - clear it
        if len(self.pressed_keys) > 8:
            print(f"[HOTKEY WARNING] pressed_keys too large ({len(self.pressed_keys)}), clearing: {self.pressed_keys}")
            self.pressed_keys.clear()
            self._key_press_times.clear()
            return
        
        # Filter out stale keys - only consider keys pressed within KEY_RELEVANCE_SECONDS
        # This prevents phantom/stale keys from blocking hotkey detection
        recent_keys = set()
        stale_keys = set()
        for k in valid_keys:
            age = current_time - self._key_press_times.get(k, current_time)
            if age <= self.KEY_RELEVANCE_SECONDS:
                recent_keys.add(k)
            else:
                stale_keys.add(k)
        
        # Log if we filtered out stale keys
        if stale_keys:
            stale_ages = [round(current_time - self._key_press_times.get(k, current_time), 2) for k in stale_keys]
            print(f"[HOTKEY] Ignoring {len(stale_keys)} stale key(s): {stale_keys} ages={stale_ages}s")
        
        current_keys = frozenset(recent_keys)
        
        # Debug: log when we have multiple modifiers pressed (potential hotkey attempt)
        modifier_count = sum(1 for k in current_keys if k in self.MODIFIER_KEYS)
        if modifier_count >= 2 and len(current_keys) >= 3:
            # User is pressing multiple modifiers + a key - log this for debugging
            matched = current_keys in self._registered_hotkeys
            if not matched:
                print(f"[HOTKEY DEBUG] Keys pressed: {current_keys} - no match")

        for hotkey_keys, callback in self._registered_hotkeys.items():
            if hotkey_keys == current_keys:
                # Execute callback
                try:
                    self._hotkey_triggers += 1
                    ages = [round(current_time - self._key_press_times.get(k, current_time), 2) for k in current_keys]
                    print(f"[HOTKEY] Triggered: {current_keys} pressed_ago={ages}")
                    callback()
                except Exception as e:
                    print(f"Error executing hotkey callback: {e}")
                break
