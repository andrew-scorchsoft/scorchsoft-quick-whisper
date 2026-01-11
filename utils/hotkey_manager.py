import keyboard
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from pathlib import Path
import platform
import threading
import time
from utils.config_manager import get_config


class HotkeyManager:
    def __init__(self, parent):
        self.parent = parent
        self.hotkeys = []
        self.is_mac = platform.system() == 'Darwin'
        self._paused = False
        self.config = get_config()
        
        # Default shortcuts
        self.shortcuts = {
            'record_edit': 'ctrl+alt+j' if not self.is_mac else 'command+alt+j',
            'record_transcribe': 'ctrl+alt+shift+j' if not self.is_mac else 'command+alt+shift+j',
            'cancel_recording': 'ctrl+alt+x' if not self.is_mac else 'command+x',
            'cycle_prompt_back': 'alt+left' if not self.is_mac else 'command+[',
            'cycle_prompt_forward': 'alt+right' if not self.is_mac else 'command+]'
        }
        
        # Load shortcuts from config
        self.load_shortcuts_from_config()
        
        # A dict to track keys we've intercepted to avoid suppressing modifier keys alone
        self.key_state = {}
    
    def load_shortcuts_from_config(self):
        """Load keyboard shortcuts from config file"""
        # Overwrite defaults with any config-defined shortcuts
        self.shortcuts = {
            'record_edit': self.config.get_shortcut('record_edit') or ('ctrl+alt+j' if not self.is_mac else 'command+alt+j'),
            'record_transcribe': self.config.get_shortcut('record_transcribe') or ('ctrl+alt+shift+j' if not self.is_mac else 'command+alt+shift+j'),
            'cancel_recording': self.config.get_shortcut('cancel_recording') or ('ctrl+alt+x' if not self.is_mac else 'command+x'),
            'cycle_prompt_back': self.config.get_shortcut('cycle_prompt_back') or ('alt+left' if not self.is_mac else 'command+['),
            'cycle_prompt_forward': self.config.get_shortcut('cycle_prompt_forward') or ('alt+right' if not self.is_mac else 'command+]')
        }
    
    def register_hotkeys(self):
        """Register all hotkeys and store them for monitoring."""
        try:
            if self._paused:
                return False
            # Clear existing hotkeys first
            for hotkey in self.hotkeys:
                try:
                    keyboard.remove_hotkey(hotkey)
                except:
                    pass
            self.hotkeys.clear()

            # Register hotkeys for combinations, but don't suppress yet
            # We'll do manual suppression in the key event handlers
            # This is to avoid suppressing the windows key when used alone
            
            # Set up individual key handlers
            keyboard.on_press(self.on_key_press)
            keyboard.on_release(self.on_key_release)
            
            # Register hotkeys - these will set up detection but won't suppress
            # IMPORTANT: Use self.parent.after(0, ...) to schedule callbacks on the main Tkinter thread
            # The keyboard library fires callbacks from its own thread, which causes UI glitches
            # (like black button flashes) if we don't marshal the call to the main thread
            self.hotkeys.append(keyboard.add_hotkey(self.shortcuts['record_edit'], 
                                                  lambda: self.parent.after(0, lambda: self.parent.toggle_recording("edit")), 
                                                  suppress=False))
            self.hotkeys.append(keyboard.add_hotkey(self.shortcuts['record_transcribe'], 
                                                  lambda: self.parent.after(0, lambda: self.parent.toggle_recording("transcribe")), 
                                                  suppress=False))
            self.hotkeys.append(keyboard.add_hotkey(self.shortcuts['cancel_recording'], 
                                                  lambda: self.parent.after(0, self.parent.cancel_recording), 
                                                  suppress=False))
            self.hotkeys.append(keyboard.add_hotkey(self.shortcuts['cycle_prompt_back'], 
                                                  lambda: self.parent.after(0, self.parent.cycle_prompt_backward), 
                                                  suppress=False))
            self.hotkeys.append(keyboard.add_hotkey(self.shortcuts['cycle_prompt_forward'], 
                                                  lambda: self.parent.after(0, self.parent.cycle_prompt_forward), 
                                                  suppress=False))
            
            print(f"Registered {len(self.hotkeys)} hotkeys successfully")
            return True
        except Exception as e:
            print(f"Error registering hotkeys: {e}")
            return False
    
    def on_key_press(self, event):
        """Handle key press events and selectively suppress"""
        try:
            key_name = event.name if hasattr(event, 'name') else ''
            scan_code = event.scan_code if hasattr(event, 'scan_code') else None
            
            # Track key state
            self.key_state[scan_code] = {
                'name': key_name,
                'time': time.time()
            }
            
            # For Ctrl+Alt+J combination (record_edit)
            if key_name.lower() == 'j' and keyboard.is_pressed('ctrl') and keyboard.is_pressed('alt') and not keyboard.is_pressed('shift'):
                return False  # Suppress the j key
            
            # For Ctrl+Alt+Shift+J combination (record_transcribe)
            elif key_name.lower() == 'j' and keyboard.is_pressed('ctrl') and keyboard.is_pressed('alt') and keyboard.is_pressed('shift'):
                return False  # Suppress the j key
            
            # Avoid suppressing other system and navigation shortcuts
            
            # For all other keys, don't suppress
            return True
            
        except Exception as e:
            print(f"Error in key press handler: {e}")
            return True  # Don't suppress on error
    
    def on_key_release(self, event):
        """Handle key release events"""
        try:
            scan_code = event.scan_code if hasattr(event, 'scan_code') else None
            
            # Clean up key state
            if scan_code in self.key_state:
                del self.key_state[scan_code]
            
            # Never suppress key releases
            return True
            
        except Exception as e:
            print(f"Error in key release handler: {e}")
            return True  # Don't suppress on error
    
    def force_hotkey_refresh(self, callback=None):
        """Force a complete refresh of all hotkeys."""
        print("Forcing hotkey refresh")
        print(f"Current hotkeys before refresh: {len(self.hotkeys)}")
        try:
            if self._paused:
                print("Hotkeys are paused; skipping refresh")
                if callback:
                    callback(True)
                return True
            # Kill all keyboard hooks
            print("Unhooking all keyboard hooks...")
            keyboard.unhook_all()
            print("Successfully unhooked all keyboard hooks")
            
            # Clear our tracking
            print("Clearing hotkey tracking list...")
            self.hotkeys.clear()
            self.key_state.clear()
            print("Hotkey tracking list cleared")
            
            # Try to reset the keyboard module's internal state
            try:
                print("Resetting keyboard module internal state...")
                keyboard._recording = False
                keyboard._pressed_events.clear()
                keyboard._physically_pressed_keys.clear()
                keyboard._logically_pressed_keys.clear()
                print("Keyboard module internal state reset complete")
            except Exception as inner_e:
                print(f"Warning: Error while resetting keyboard state: {inner_e}")
            
            # Schedule the complete refresh
            def _after_refresh():
                success = self.register_hotkeys()
                if success and self.hotkeys:
                    print(f"Hotkey refresh completed successfully with {len(self.hotkeys)} hotkeys")
                    if callback:
                        callback(True)
                else:
                    print("Failed to register hotkeys")
                    if callback:
                        callback(False)
                    messagebox.showerror("Hotkey Error", 
                        "Failed to re-register hotkeys. Try closing and reopening the application.")
            
            print("Scheduling complete refresh...")
            self.parent.after(100, _after_refresh)
            return True
            
        except Exception as e:
            print(f"Error during hotkey refresh: {e}")
            print(f"Error type: {type(e)}")
            print(f"Error details: {str(e)}")
            if callback:
                callback(False)
            messagebox.showerror("Hotkey Error", 
                "Failed to refresh hotkeys. Try closing and reopening the application.")
            return False
    
    def verify_hotkeys(self):
        """Verify that hotkeys are working correctly."""
        try:
            if self._paused:
                print("Hotkeys are paused")
                return True
            # First check if we have any hotkeys registered
            if len(self.hotkeys) == 0:
                print("No hotkeys registered")
                return False
            
            # Check the OS-level hook state
            try:
                # For Windows platform, check if the keyboard hooks are still registered
                if platform.system() == 'Windows':
                    # Check if the keyboard module's hooks are still active
                    if not hasattr(keyboard, '_hooks') or not keyboard._hooks:
                        print("Keyboard hooks not active - all hooks are missing")
                        return False
                    
                    # Check if we still have our hotkey handlers in _hotkeys
                    if not hasattr(keyboard, '_hotkeys') or not keyboard._hotkeys:
                        print("No hotkeys registered in keyboard module")
                        return False
                    
                    # Try to check if specific shortcuts are registered
                    # Look for any of our shortcut combinations in the hotkeys dictionary
                    hotkey_keys = keyboard._hotkeys.keys()
                    our_shortcut_found = False
                    
                    for shortcut in self.shortcuts.values():
                        # Normalize the shortcut format to match how keyboard module formats it
                        # Convert "win+j" to something like "windows+j"
                        normalized = shortcut.replace('win+', 'windows+').replace('command+', 'command+')
                        
                        # Check if any keys in _hotkeys correspond to our shortcuts
                        for hk_key in hotkey_keys:
                            # Simple substring check since we don't know exact format
                            if any(part in hk_key for part in normalized.split('+')):
                                our_shortcut_found = True
                                break
                        
                        if our_shortcut_found:
                            break
                    
                    if not our_shortcut_found:
                        print("None of our specific shortcuts found in keyboard bindings")
                        return False
                    
                    # Check keyboard listener thread state if we can safely access it
                    try:
                        if hasattr(keyboard, '_listener') and keyboard._listener and hasattr(keyboard._listener, '_thread'):
                            thread = keyboard._listener._thread
                            if not thread or not thread.is_alive():
                                print("Keyboard listener thread not alive")
                                return False
                    except Exception as thread_e:
                        print(f"Error checking keyboard thread: {thread_e}")
                        # Continue even if this check fails
            
            except Exception as e:
                print(f"Error in OS-specific hotkey checks: {e}")
                return False
            
            # All checks passed
            print("Hotkey verification passed - hotkeys are working correctly")
            return True
        except Exception as e:
            print(f"Error verifying hotkeys: {e}")
            return False
    
    def save_shortcut_to_config(self, shortcut_name, key_combination):
        """Save a keyboard shortcut to settings.json."""
        # Format the key combination consistently before saving
        formatted_combination = self.format_shortcut(key_combination.split('+') if isinstance(key_combination, str) else key_combination)
        
        # Update config and save
        self.config.set_shortcut(shortcut_name, formatted_combination)
        self.config.save_settings()

        # Update runtime shortcut with formatted combination
        self.shortcuts[shortcut_name] = formatted_combination
        
        # Update UI elements displaying shortcuts
        self.update_shortcut_displays()
    
    def update_shortcut_displays(self):
        """Update all UI elements that display keyboard shortcuts"""
        # Use the UI manager's method to update buttons with proper formatting
        if hasattr(self.parent.ui_manager, 'update_button_shortcuts'):
            self.parent.ui_manager.update_button_shortcuts(
                transcribe_shortcut=self.shortcuts['record_transcribe'],
                edit_shortcut=self.shortcuts['record_edit']
            )
        else:
            # Fallback for older UI manager versions
            self.parent.ui_manager.record_button_edit.configure(
                text=f"Record + AI Edit ({self.shortcuts['record_edit']})"
            )
            self.parent.ui_manager.record_button_transcribe.configure(
                text=f"Record + Transcript ({self.shortcuts['record_transcribe']})"
            )
        
        # Update menu items if they exist
        try:
            # Find the Play menu
            for menu in self.parent.menubar.winfo_children():
                if menu.entrycget(0, 'label') == "Cancel Recording (Win+X)" or "Cancel Recording" in menu.entrycget(0, 'label'):
                    menu.entryconfigure(0, 
                        label=f"Cancel Recording ({self.shortcuts['cancel_recording']})"
                    )
        except:
            pass
    
    def format_shortcut(self, keys):
        """Format a set of keys into a shortcut string with consistent ordering."""
        # Define modifier order
        modifier_order = ['ctrl', 'alt', 'shift', 'win', 'command']
        
        # Split into modifiers and regular keys
        modifiers = [k for k in keys if k in modifier_order]
        regular_keys = [k for k in keys if k not in modifier_order]
        
        # Sort modifiers according to our preferred order
        sorted_modifiers = sorted(modifiers, key=lambda x: modifier_order.index(x))
        
        # Combine modifiers and regular keys (regular keys in alphabetical order)
        return "+".join(sorted_modifiers + sorted(regular_keys))
    
    def reset_shortcuts_to_default(self, shortcuts_window=None):
        """Reset all keyboard shortcuts to their default values."""
        if not shortcuts_window:
            shortcuts_window = self.parent  # Fallback to main window if shortcuts window not found
        
        # Create custom confirmation dialog
        confirm = tk.messagebox.askyesno(
            "Reset Shortcuts",
            "Are you sure you want to reset all keyboard shortcuts to their default values?",
            parent=shortcuts_window
        )
        
        if confirm:
            try:
                # Reset shortcuts in memory to defaults
                default_shortcuts = {
                    'record_edit': 'ctrl+alt+j' if not self.is_mac else 'command+alt+j',
                    'record_transcribe': 'ctrl+alt+shift+j' if not self.is_mac else 'command+alt+shift+j',
                    'cancel_recording': 'win+x' if not self.is_mac else 'command+x',
                    'cycle_prompt_back': 'alt+left' if not self.is_mac else 'command+[',
                    'cycle_prompt_forward': 'alt+right' if not self.is_mac else 'command+]'
                }
                
                self.shortcuts = default_shortcuts.copy()
                
                # Update config with default shortcuts and save
                for name, shortcut in default_shortcuts.items():
                    self.config.set_shortcut(name, shortcut)
                self.config.save_settings()
                
                # Update all shortcut labels in the dialog
                if shortcuts_window != self.parent:
                    for child in shortcuts_window.winfo_children():
                        if isinstance(child, ttk.Frame):  # Main frame
                            for frame_child in child.winfo_children():
                                if isinstance(frame_child, ttk.Frame):  # Shortcuts frame
                                    for shortcut_frame in frame_child.winfo_children():
                                        if isinstance(shortcut_frame, ttk.Frame):  # Individual shortcut frames
                                            # Get the name label (first child)
                                            name_label = [w for w in shortcut_frame.winfo_children() 
                                                        if isinstance(w, ttk.Label)][0]
                                            # Get the shortcut name from the label
                                            shortcut_name = name_label.cget('text').replace(':', '').lower().replace(' ', '_')
                                            
                                            if shortcut_name in self.shortcuts:
                                                # Get the shortcut label (second child)
                                                shortcut_label = [w for w in shortcut_frame.winfo_children() 
                                                                if isinstance(w, ttk.Label)][1]
                                                # Update the label
                                                shortcut_label.config(text=self.shortcuts[shortcut_name])
                
                # Refresh the hotkeys
                def on_refresh_complete(success):
                    if success:
                        # Update main window UI
                        self.update_shortcut_displays()
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

    def pause(self):
        """Temporarily disable all hotkeys and keyboard hooks."""
        try:
            print("Pausing hotkeys...")
            self._paused = True
            keyboard.unhook_all()
            for hotkey in self.hotkeys:
                try:
                    keyboard.remove_hotkey(hotkey)
                except Exception:
                    pass
            self.hotkeys.clear()
            self.key_state.clear()
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
    
    def check_keyboard_shortcuts(self):
        """Test keyboard shortcuts and show status."""
        shortcut_window = tk.Toplevel(self.parent)
        shortcut_window.title("Keyboard Shortcuts")
        shortcut_window.geometry("500x400")
        
        # Center the window
        window_width = 500
        window_height = 400
        position_x = self.parent.winfo_x() + (self.parent.winfo_width() - window_width) // 2
        position_y = self.parent.winfo_y() + (self.parent.winfo_height() - window_height) // 2
        shortcut_window.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")

        main_frame = ttk.Frame(shortcut_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Add title
        title_label = ttk.Label(
            main_frame, 
            text="Keyboard Shortcuts", 
            font=("Arial", 12, "bold")
        )
        title_label.pack(pady=(0, 10))

        # Create frame for shortcuts
        shortcuts_frame = ttk.Frame(main_frame)
        shortcuts_frame.pack(fill=tk.BOTH, expand=True)

        # Function to handle shortcut editing
        def start_shortcut_edit(shortcut_name, button, label):
            # Add check for valid button
            if not button or not button.winfo_exists():
                print("Warning: Button no longer exists")
                return
            
            button.config(text="Press new shortcut...")
            
            # Track pressed keys and modifiers
            pressed_keys = set()
            currently_pressed = set()  # Track keys that are currently held down
            last_state = 0  # Track the last event state
            
            def on_key_press(event):
                nonlocal last_state
                last_state = event.state
                
                # Convert key to lowercase
                key = event.keysym.lower()
                
                # Debug print
                print(f"Key press - key: {key}")
                print(f"State bits: {format(event.state, '016b')}")
                print(f"State value: {event.state}")
                print(f"Currently pressed keys before: {currently_pressed}")
                
                # Map left/right modifier variants to their base form
                modifier_map = {
                    'control_l': 'ctrl', 'control_r': 'ctrl',
                    'alt_l': 'alt', 'alt_r': 'alt',
                    'shift_l': 'shift', 'shift_r': 'shift',
                    'super_l': 'win', 'super_r': 'win',
                    'win_l': 'win', 'win_r': 'win'
                }
                
                # Add to currently pressed keys
                if key in modifier_map:
                    mod_key = modifier_map[key]
                    currently_pressed.add(mod_key)
                else:
                    # Only add non-modifier keys if they're actual keys (not just state changes)
                    if len(key) == 1 or key in ('left', 'right', 'up', 'down', 'space', 'tab', 'return', 
                                               'backspace', 'delete', 'escape', 'home', 'end', 'pageup', 
                                               'pagedown', 'insert', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6',
                                               'f7', 'f8', 'f9', 'f10', 'f11', 'f12'):
                        currently_pressed.add(key)
                
                # Update pressed_keys with all current keys
                pressed_keys.clear()
                pressed_keys.update(currently_pressed)
                
                # Add modifiers based on state
                if event.state & 0x4:
                    pressed_keys.add('ctrl')
                if event.state & 0x1:
                    pressed_keys.add('shift')
                if event.state & 0x20000:
                    pressed_keys.add('alt')
                if event.state & 0x40000 or 'win' in currently_pressed:
                    pressed_keys.add('win')
                
                print(f"Currently pressed keys after: {pressed_keys}")
                
                # Update button text to show current combination
                current_combo = "+".join(sorted(pressed_keys))
                button.config(text=f"Press: {current_combo}")
                
                return "break"
            
            def on_key_release(event):
                nonlocal currently_pressed
                key = event.keysym.lower()
                
                print(f"Key release - key: {key}")
                print(f"Currently pressed before release: {currently_pressed}")
                
                # Remove released key from currently pressed set
                if key in currently_pressed:
                    currently_pressed.remove(key)
                
                # Handle modifier key releases
                modifier_map = {
                    'control_l': 'ctrl', 'control_r': 'ctrl',
                    'alt_l': 'alt', 'alt_r': 'alt',
                    'shift_l': 'shift', 'shift_r': 'shift',
                    'super_l': 'win', 'super_r': 'win',
                    'win_l': 'win', 'win_r': 'win'
                }
                if key in modifier_map:
                    mod_key = modifier_map[key]
                    if mod_key in currently_pressed:
                        currently_pressed.remove(mod_key)
                
                print(f"Currently pressed after release: {currently_pressed}")
                
                # Only process the shortcut when all keys are released
                if not currently_pressed and pressed_keys:
                    try:
                        # Create the shortcut string with consistent ordering
                        new_shortcut = self.format_shortcut(pressed_keys)
                        
                        # Check if there's at least one modifier
                        has_modifier = any(mod in pressed_keys for mod in ('ctrl', 'alt', 'shift', 'win', 'command'))
                        
                        # Validate the shortcut
                        if not has_modifier:
                            messagebox.showerror("Error", 
                                "Please include at least one modifier key (Ctrl, Alt, Shift, or Win)")
                            button.config(text="Edit")
                            return
                        
                        # Check if this shortcut is already in use
                        for name, shortcut in self.shortcuts.items():
                            if shortcut == new_shortcut and name != shortcut_name:
                                messagebox.showerror("Error", 
                                    f"This shortcut is already assigned to '{name}'")
                                button.config(text="Edit")
                                return
                        
                        # Save to config and update runtime
                        self.save_shortcut_to_config(shortcut_name, new_shortcut)
                        
                        # Refresh hotkeys with callback
                        def on_refresh_complete(success):
                            if success:
                                # Update UI
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
                        # Clear the sets
                        pressed_keys.clear()
                        currently_pressed.clear()
            
            # Remove any existing bindings first
            shortcut_window.unbind('<KeyPress>')
            shortcut_window.unbind('<KeyRelease>')
            
            # Bind both key press and release events
            shortcut_window.bind('<KeyPress>', on_key_press)
            shortcut_window.bind('<KeyRelease>', on_key_release)

        # Add each shortcut with its edit button
        row = 0
        for name, shortcut in self.shortcuts.items():
            # Create frame for this shortcut
            frame = ttk.Frame(shortcuts_frame)
            frame.pack(fill=tk.X, pady=5)
            
            # Add shortcut name
            name_label = ttk.Label(frame, text=name.replace('_', ' ').title() + ":")
            name_label.pack(side=tk.LEFT, padx=(0, 10))
            
            # Add current shortcut
            shortcut_label = ttk.Label(frame, text=shortcut)
            shortcut_label.pack(side=tk.LEFT, padx=(0, 10))
            
            # Add edit button
            edit_button = ttk.Button(
                frame, 
                text="Edit"
            )
            edit_button.pack(side=tk.RIGHT)
            
            # Configure button command after creation to avoid stale references
            edit_button.configure(command=lambda n=name, b=edit_button, l=shortcut_label: 
                                 start_shortcut_edit(n, b, l))
            
            row += 1

        # Create a frame for the buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        # Add refresh button
        refresh_button = ctk.CTkButton(
            button_frame,
            text="Refresh Shortcuts",
            corner_radius=20,
            height=35,
            width=200,  # Set explicit width
            fg_color="#058705",
            hover_color="#046a38",
            font=("Arial", 13, "bold"),
            command=self.force_hotkey_refresh
        )
        refresh_button.pack(side=tk.LEFT, padx=5)

        # Add reset to defaults button
        reset_button = ctk.CTkButton(
            button_frame,
            text="Reset to Defaults",
            corner_radius=20,
            height=35,
            width=200,  # Set explicit width
            fg_color="#666666",  # Grey color
            hover_color="#444444",
            font=("Arial", 13, "bold"),
            command=lambda: self.reset_shortcuts_to_default(shortcuts_window=shortcut_window)
        )
        reset_button.pack(side=tk.LEFT, padx=5)

        # Add note about Windows lock
        note_text = ("Note: If shortcuts stop working after unlocking Windows,\n"
                    "use this dialog to refresh them. If refresh doesn't work,\n"
                    "try closing and reopening the application.")
        
        ttk.Label(
            main_frame, 
            text=note_text,
            justify=tk.CENTER,
            font=("Arial", 9),
            foreground="#666666"
        ).pack(pady=10)

        # Close button
        close_button = ttk.Button(
            main_frame,
            text="Close",
            command=shortcut_window.destroy
        )
        close_button.pack(pady=(10, 0)) 