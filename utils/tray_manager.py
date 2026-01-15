import threading
import platform
import os
from PIL import Image
from pystray import Icon as TrayIcon, MenuItem as Item, Menu
import tkinter as tk

class TrayManager:
    def __init__(self, parent):
        self.parent = parent
        self.icon = None
        self.icon_thread = None
        self.is_running = False
        self.is_window_hidden = False
        self.icon_image = None
        
    def setup_tray(self):
        """Set up the system tray icon"""
        try:
            # Load the icon image
            icon_path = self.parent.resource_path("assets/icon-32.png")
            self.icon_image = Image.open(icon_path)
            
            # Create a menu
            # Note: default=True makes left-click on tray icon trigger this action (Windows)
            menu = Menu(
                Item('Show/Hide Window', self._toggle_window, default=True),
                Item('Refresh Hotkeys Now', self._refresh_hotkeys),
                Menu.SEPARATOR,
                Item('Auto-Refresh Hotkeys (Every 30s)', self._toggle_auto_refresh, checked=lambda item: self.parent.auto_hotkey_refresh.get()),
                Menu.SEPARATOR,
                Item('Exit', self._exit_app)
            )
            
            # Create the icon
            self.icon = TrayIcon(
                "QuickWhisper", 
                self.icon_image,
                "Quick Whisper",
                menu
            )
            return True
        except Exception as e:
            print(f"Error setting up system tray icon: {e}")
            return False
        
    def show_tray(self):
        """Show the system tray icon in a separate thread"""
        if self.is_running:
            return True
        
        if not self.setup_tray():
            print("Failed to set up system tray icon")
            return False
            
        self.is_running = True
        
        try:
            # Run in a separate thread to not block the main thread
            # CHANGED: Make this a non-daemon thread so it doesn't terminate prematurely
            self.icon_thread = threading.Thread(target=self._run_tray, daemon=False)
            self.icon_thread.start()
            return True
        except Exception as e:
            print(f"Error starting tray icon thread: {e}")
            self.is_running = False
            return False
        
    def _run_tray(self):
        """Run the system tray icon (called in a thread)"""
        try:
            print("Starting system tray icon")
            self.icon.run()
        except Exception as e:
            print(f"Error running system tray icon: {e}")
        finally:
            self.is_running = False
            
    def stop_tray(self):
        """Stop the system tray icon"""
        if self.icon and self.is_running:
            try:
                # Stop the icon - this signals the icon.run() loop to exit
                self.icon.stop()
            except Exception as e:
                print(f"Error stopping tray icon: {e}")

        # Wait for the icon thread to finish to ensure proper cleanup
        # This is important on Windows to prevent the icon from persisting
        if self.icon_thread and self.icon_thread.is_alive():
            try:
                self.icon_thread.join(timeout=2.0)  # Wait up to 2 seconds
                if self.icon_thread.is_alive():
                    print("Warning: Tray icon thread did not stop in time")
            except Exception as e:
                print(f"Error joining tray icon thread: {e}")

        # Clear references to help garbage collection
        self.icon = None
        self.icon_thread = None
        self.is_running = False
        
    def _toggle_window(self):
        """Toggle the visibility of the main window"""
        # Access from the main thread
        if self.parent.winfo_exists():
            self.parent.after(0, self._do_toggle_window)
    
    def _do_toggle_window(self):
        """Actually perform the window toggle (on main thread)"""
        if self.is_window_hidden:
            # Show window
            self.parent.deiconify()
            self.parent.lift()
            self.parent.focus_force()
            self.is_window_hidden = False
        else:
            # Hide window
            self.parent.withdraw()
            self.is_window_hidden = True
    
    def _refresh_hotkeys(self):
        """Refresh the keyboard shortcuts"""
        if self.parent.winfo_exists():
            self.parent.after(0, self.parent.hotkey_manager.force_hotkey_refresh)
    
    def _exit_app(self):
        """Exit the application"""
        if self.parent.winfo_exists():
            self.parent.after(0, self.parent.on_closing)
    
    def minimize_to_tray(self):
        """Minimize the window to the system tray"""
        # Ensure tray is set up before minimizing
        if not self.is_running:
            success = self.show_tray()
            if not success:
                print("Failed to create system tray icon, not minimizing")
                return
                
        self.parent.withdraw()
        self.is_window_hidden = True
    
    def _toggle_auto_refresh(self):
        """Toggle the auto-refresh hotkeys setting"""
        if self.parent.winfo_exists():
            self.parent.after(0, self._do_toggle_auto_refresh)
    
    def _do_toggle_auto_refresh(self):
        """Actually perform the auto-refresh toggle (on main thread)"""
        current_value = self.parent.auto_hotkey_refresh.get()
        self.parent.auto_hotkey_refresh.set(not current_value)
        self.parent.save_auto_hotkey_refresh()
        new_state = "enabled" if not current_value else "disabled"
        print(f"Auto-refresh hotkeys {new_state} from tray menu") 