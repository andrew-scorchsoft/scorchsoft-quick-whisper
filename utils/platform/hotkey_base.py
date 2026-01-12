"""
Base class for platform-specific HotkeyManager implementations.

This module provides the abstract base class and shared functionality
for managing global keyboard hotkeys across different platforms.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from abc import ABC, abstractmethod
from pathlib import Path
import threading
import time

from utils.config_manager import get_config
from utils.theme import get_font, get_window_size
from . import CURRENT_PLATFORM


class HotkeyManagerBase(ABC):
    """
    Abstract base class for platform-specific hotkey managers.

    Subclasses must implement the abstract methods for registering,
    unregistering, and verifying hotkeys using platform-specific APIs.
    """

    def __init__(self, parent):
        self.parent = parent
        self._paused = False
        self.config = get_config()
        self.is_mac = CURRENT_PLATFORM == 'macos'

        # Default shortcuts (platform-specific)
        self.shortcuts = self._get_default_shortcuts()

        # Load shortcuts from config (may override defaults)
        self.load_shortcuts_from_config()

    def _get_default_shortcuts(self):
        """Get default shortcuts for the current platform."""
        if self.is_mac:
            return {
                'record_edit': 'command+alt+j',
                'record_transcribe': 'command+alt+shift+j',
                'cancel_recording': 'command+x',
                'cycle_prompt_back': 'command+[',
                'cycle_prompt_forward': 'command+]'
            }
        else:
            # Windows and Linux use the same defaults
            return {
                'record_edit': 'ctrl+alt+j',
                'record_transcribe': 'ctrl+alt+shift+j',
                'cancel_recording': 'ctrl+alt+x',
                'cycle_prompt_back': 'alt+left',
                'cycle_prompt_forward': 'alt+right'
            }

    def load_shortcuts_from_config(self):
        """Load keyboard shortcuts from config file."""
        defaults = self._get_default_shortcuts()
        self.shortcuts = {
            'record_edit': self.config.get_shortcut('record_edit') or defaults['record_edit'],
            'record_transcribe': self.config.get_shortcut('record_transcribe') or defaults['record_transcribe'],
            'cancel_recording': self.config.get_shortcut('cancel_recording') or defaults['cancel_recording'],
            'cycle_prompt_back': self.config.get_shortcut('cycle_prompt_back') or defaults['cycle_prompt_back'],
            'cycle_prompt_forward': self.config.get_shortcut('cycle_prompt_forward') or defaults['cycle_prompt_forward']
        }

    @abstractmethod
    def register_hotkeys(self):
        """
        Register all hotkeys with the system.

        Returns:
            bool: True if registration succeeded, False otherwise.
        """
        pass

    @abstractmethod
    def unregister_hotkeys(self):
        """Unregister all hotkeys from the system."""
        pass

    @abstractmethod
    def verify_hotkeys(self):
        """
        Verify that hotkeys are currently working.

        Returns:
            bool: True if hotkeys are working, False otherwise.
        """
        pass

    def force_hotkey_refresh(self, callback=None):
        """
        Force a complete refresh of all hotkeys.

        Args:
            callback: Optional callback function(success: bool) called after refresh.

        Returns:
            bool: True if refresh started successfully.
        """
        print("Forcing hotkey refresh")
        try:
            if self._paused:
                print("Hotkeys are paused; skipping refresh")
                if callback:
                    callback(True)
                return True

            # Unregister all hotkeys
            self.unregister_hotkeys()

            # Schedule re-registration
            def _after_refresh():
                success = self.register_hotkeys()
                if success:
                    print("Hotkey refresh completed successfully")
                    if callback:
                        callback(True)
                else:
                    print("Failed to register hotkeys")
                    if callback:
                        callback(False)
                    messagebox.showerror("Hotkey Error",
                        "Failed to re-register hotkeys. Try closing and reopening the application.")

            self.parent.after(100, _after_refresh)
            return True

        except Exception as e:
            print(f"Error during hotkey refresh: {e}")
            if callback:
                callback(False)
            messagebox.showerror("Hotkey Error",
                "Failed to refresh hotkeys. Try closing and reopening the application.")
            return False

    def pause(self):
        """Temporarily disable all hotkeys."""
        try:
            print("Pausing hotkeys...")
            self._paused = True
            self.unregister_hotkeys()
            print("Hotkeys paused")
        except Exception as e:
            print(f"Error while pausing hotkeys: {e}")

    def resume(self):
        """Re-enable hotkeys after a pause."""
        try:
            if not self._paused:
                return
            print("Resuming hotkeys...")
            self._paused = False
            self.register_hotkeys()
            print("Hotkeys resumed")
        except Exception as e:
            print(f"Error while resuming hotkeys: {e}")

    def save_shortcut_to_config(self, shortcut_name, key_combination):
        """Save a keyboard shortcut to settings.json."""
        formatted_combination = self.format_shortcut(
            key_combination.split('+') if isinstance(key_combination, str) else key_combination
        )

        self.config.set_shortcut(shortcut_name, formatted_combination)
        self.config.save_settings()
        self.shortcuts[shortcut_name] = formatted_combination
        self.update_shortcut_displays()

    def update_shortcut_displays(self):
        """Update all UI elements that display keyboard shortcuts."""
        if hasattr(self.parent.ui_manager, 'update_button_shortcuts'):
            self.parent.ui_manager.update_button_shortcuts(
                transcribe_shortcut=self.shortcuts['record_transcribe'],
                edit_shortcut=self.shortcuts['record_edit']
            )
        else:
            self.parent.ui_manager.record_button_edit.configure(
                text=f"Record + AI Edit ({self.shortcuts['record_edit']})"
            )
            self.parent.ui_manager.record_button_transcribe.configure(
                text=f"Record + Transcript ({self.shortcuts['record_transcribe']})"
            )

        try:
            for menu in self.parent.menubar.winfo_children():
                if "Cancel Recording" in menu.entrycget(0, 'label'):
                    menu.entryconfigure(0,
                        label=f"Cancel Recording ({self.shortcuts['cancel_recording']})"
                    )
        except:
            pass

    def format_shortcut(self, keys):
        """Format a set of keys into a shortcut string with consistent ordering."""
        modifier_order = ['ctrl', 'alt', 'shift', 'win', 'command']
        modifiers = [k for k in keys if k in modifier_order]
        regular_keys = [k for k in keys if k not in modifier_order]
        sorted_modifiers = sorted(modifiers, key=lambda x: modifier_order.index(x))
        return "+".join(sorted_modifiers + sorted(regular_keys))

    def reset_shortcuts_to_default(self, shortcuts_window=None):
        """Reset all keyboard shortcuts to their default values."""
        if not shortcuts_window:
            shortcuts_window = self.parent

        confirm = tk.messagebox.askyesno(
            "Reset Shortcuts",
            "Are you sure you want to reset all keyboard shortcuts to their default values?",
            parent=shortcuts_window
        )

        if confirm:
            try:
                default_shortcuts = self._get_default_shortcuts()
                self.shortcuts = default_shortcuts.copy()

                for name, shortcut in default_shortcuts.items():
                    self.config.set_shortcut(name, shortcut)
                self.config.save_settings()

                if shortcuts_window != self.parent:
                    self._update_shortcut_dialog_labels(shortcuts_window)

                def on_refresh_complete(success):
                    self.update_shortcut_displays()
                    if success:
                        tk.messagebox.showinfo(
                            "Success",
                            "Shortcuts have been reset to defaults",
                            parent=shortcuts_window
                        )
                    else:
                        tk.messagebox.showerror(
                            "Error",
                            "Failed to register default shortcuts. Try closing and reopening the application.",
                            parent=shortcuts_window
                        )

                self.force_hotkey_refresh(callback=on_refresh_complete)

            except Exception as e:
                tk.messagebox.showerror(
                    "Error",
                    f"Failed to reset shortcuts: {e}",
                    parent=shortcuts_window
                )

    def _update_shortcut_dialog_labels(self, shortcuts_window):
        """Update shortcut labels in the dialog window."""
        for child in shortcuts_window.winfo_children():
            if isinstance(child, ttk.Frame):
                for frame_child in child.winfo_children():
                    if isinstance(frame_child, ttk.Frame):
                        for shortcut_frame in frame_child.winfo_children():
                            if isinstance(shortcut_frame, ttk.Frame):
                                labels = [w for w in shortcut_frame.winfo_children()
                                         if isinstance(w, ttk.Label)]
                                if len(labels) >= 2:
                                    name_label = labels[0]
                                    shortcut_label = labels[1]
                                    shortcut_name = name_label.cget('text').replace(':', '').lower().replace(' ', '_')
                                    if shortcut_name in self.shortcuts:
                                        shortcut_label.config(text=self.shortcuts[shortcut_name])

    def check_keyboard_shortcuts(self):
        """Open the keyboard shortcuts dialog for viewing and editing."""
        shortcut_window = tk.Toplevel(self.parent)
        shortcut_window.title("Keyboard Shortcuts")

        # Get window dimensions from theme
        window_width, window_height = get_window_size('hotkey_dialog')
        position_x = self.parent.winfo_x() + (self.parent.winfo_width() - window_width) // 2
        position_y = self.parent.winfo_y() + (self.parent.winfo_height() - window_height) // 2
        shortcut_window.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")

        main_frame = ttk.Frame(shortcut_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(
            main_frame,
            text="Keyboard Shortcuts",
            font=get_font('sm', 'bold')
        )
        title_label.pack(pady=(0, 10))

        shortcuts_frame = ttk.Frame(main_frame)
        shortcuts_frame.pack(fill=tk.BOTH, expand=True)

        for name, shortcut in self.shortcuts.items():
            frame = ttk.Frame(shortcuts_frame)
            frame.pack(fill=tk.X, pady=5)

            name_label = ttk.Label(frame, text=name.replace('_', ' ').title() + ":")
            name_label.pack(side=tk.LEFT, padx=(0, 10))

            shortcut_label = ttk.Label(frame, text=shortcut)
            shortcut_label.pack(side=tk.LEFT, padx=(0, 10))

            edit_button = ttk.Button(frame, text="Edit")
            edit_button.pack(side=tk.RIGHT)
            edit_button.configure(
                command=lambda n=name, b=edit_button, l=shortcut_label:
                    self._start_shortcut_edit(n, b, l, shortcut_window)
            )

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        refresh_button = ctk.CTkButton(
            button_frame,
            text="Refresh Shortcuts",
            corner_radius=20,
            height=35,
            width=200,
            fg_color="#058705",
            hover_color="#046a38",
            font=get_font('md', 'bold'),
            command=self.force_hotkey_refresh
        )
        refresh_button.pack(side=tk.LEFT, padx=5)

        reset_button = ctk.CTkButton(
            button_frame,
            text="Reset to Defaults",
            corner_radius=20,
            height=35,
            width=200,
            fg_color="#666666",
            hover_color="#444444",
            font=get_font('md', 'bold'),
            command=lambda: self.reset_shortcuts_to_default(shortcuts_window=shortcut_window)
        )
        reset_button.pack(side=tk.LEFT, padx=5)

        # Platform-specific note
        if CURRENT_PLATFORM == 'macos':
            note_text = ("Note: On macOS, you may need to grant Accessibility\n"
                        "permissions for global hotkeys to work.")
        elif CURRENT_PLATFORM == 'linux':
            note_text = ("Note: On Linux with Wayland, global hotkeys may\n"
                        "have limited functionality. X11 is recommended.")
        else:
            note_text = ("Note: If shortcuts stop working after unlocking Windows,\n"
                        "use this dialog to refresh them. If refresh doesn't work,\n"
                        "try closing and reopening the application.")

        ttk.Label(
            main_frame,
            text=note_text,
            justify=tk.CENTER,
            font=get_font('xxs'),
            foreground="#666666"
        ).pack(pady=10)

        close_button = ttk.Button(
            main_frame,
            text="Close",
            command=shortcut_window.destroy
        )
        close_button.pack(pady=(10, 0))

    def _start_shortcut_edit(self, shortcut_name, button, label, shortcut_window):
        """Handle shortcut editing when user clicks Edit button."""
        if not button or not button.winfo_exists():
            return

        button.config(text="Press new shortcut...")

        pressed_keys = set()
        currently_pressed = set()

        def on_key_press(event):
            key = event.keysym.lower()

            modifier_map = {
                'control_l': 'ctrl', 'control_r': 'ctrl',
                'alt_l': 'alt', 'alt_r': 'alt',
                'shift_l': 'shift', 'shift_r': 'shift',
                'super_l': 'win' if not self.is_mac else 'command',
                'super_r': 'win' if not self.is_mac else 'command',
                'win_l': 'win', 'win_r': 'win',
                'meta_l': 'command', 'meta_r': 'command'
            }

            if key in modifier_map:
                currently_pressed.add(modifier_map[key])
            else:
                valid_keys = ('left', 'right', 'up', 'down', 'space', 'tab', 'return',
                             'backspace', 'delete', 'escape', 'home', 'end', 'pageup',
                             'pagedown', 'insert', 'bracketleft', 'bracketright',
                             'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9',
                             'f10', 'f11', 'f12')
                if len(key) == 1 or key in valid_keys:
                    # Map bracket keys
                    if key == 'bracketleft':
                        key = '['
                    elif key == 'bracketright':
                        key = ']'
                    currently_pressed.add(key)

            pressed_keys.clear()
            pressed_keys.update(currently_pressed)

            # Check modifier state from event
            if event.state & 0x4:
                pressed_keys.add('ctrl')
            if event.state & 0x1:
                pressed_keys.add('shift')
            if event.state & 0x20000:
                pressed_keys.add('alt')
            if event.state & 0x40000:
                pressed_keys.add('win' if not self.is_mac else 'command')

            current_combo = "+".join(sorted(pressed_keys))
            button.config(text=f"Press: {current_combo}")
            return "break"

        def on_key_release(event):
            nonlocal currently_pressed
            key = event.keysym.lower()

            if key in currently_pressed:
                currently_pressed.remove(key)

            modifier_map = {
                'control_l': 'ctrl', 'control_r': 'ctrl',
                'alt_l': 'alt', 'alt_r': 'alt',
                'shift_l': 'shift', 'shift_r': 'shift',
                'super_l': 'win' if not self.is_mac else 'command',
                'super_r': 'win' if not self.is_mac else 'command',
                'win_l': 'win', 'win_r': 'win',
                'meta_l': 'command', 'meta_r': 'command'
            }
            if key in modifier_map:
                mod_key = modifier_map[key]
                if mod_key in currently_pressed:
                    currently_pressed.remove(mod_key)

            if not currently_pressed and pressed_keys:
                try:
                    new_shortcut = self.format_shortcut(pressed_keys)

                    has_modifier = any(mod in pressed_keys for mod in ('ctrl', 'alt', 'shift', 'win', 'command'))
                    if not has_modifier:
                        messagebox.showerror("Error",
                            "Please include at least one modifier key (Ctrl, Alt, Shift, Win/Cmd)")
                        button.config(text="Edit")
                        return

                    for name, shortcut in self.shortcuts.items():
                        if shortcut == new_shortcut and name != shortcut_name:
                            messagebox.showerror("Error",
                                f"This shortcut is already assigned to '{name}'")
                            button.config(text="Edit")
                            return

                    self.save_shortcut_to_config(shortcut_name, new_shortcut)

                    def on_refresh_complete(success):
                        if success:
                            label.config(text=new_shortcut)
                            button.config(text="Edit")
                        else:
                            messagebox.showerror("Error",
                                "Failed to register new shortcut. Please try a different combination.")
                            button.config(text="Edit")

                    self.force_hotkey_refresh(callback=on_refresh_complete)

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update shortcut: {e}")
                    button.config(text="Edit")

                finally:
                    pressed_keys.clear()
                    currently_pressed.clear()

        shortcut_window.unbind('<KeyPress>')
        shortcut_window.unbind('<KeyRelease>')
        shortcut_window.bind('<KeyPress>', on_key_press)
        shortcut_window.bind('<KeyRelease>', on_key_release)
