import tkinter as tk
from tkinter import ttk, messagebox
import threading
import requests
from pathlib import Path
from packaging import version
from utils.config_manager import get_config
from utils.theme import get_window_size
from utils.platform import open_url

class VersionUpdateManager:
    def __init__(self, parent):
        self.parent = parent
        self.version_check_url = "https://www.scorchsoft.com/public/blog/quick-whisper-speech-to-copyedited-text/latest-version.json"
        self.auto_update_check = tk.BooleanVar(value=True)
        self.config = get_config()
        
        # Load settings from config
        self.auto_update_check.set(self.config.auto_update_check)
        
    def start_check(self, delay=2000):
        """Start the update check with delay to avoid blocking app startup"""
        if self.auto_update_check.get():
            self.parent.after(delay, lambda: threading.Thread(target=self.check_for_updates).start())
    
    def save_auto_update_setting(self):
        """Save the auto update setting to settings.json."""
        self.config.auto_update_check = self.auto_update_check.get()
        self.config.save_settings()
        print(f"Auto update check setting saved: {self.auto_update_check.get()}")

    def check_for_updates(self, manual_check=False):
        """Check for updates from the version check URL."""
        try:
            response = requests.get(self.version_check_url, timeout=5)
            if response.status_code == 200:
                version_data = response.json()
                latest_version = version_data.get("latestVersion")
                download_url = version_data.get("downloadUrl")
                notification_message = version_data.get("notificationMessage")
                
                # Check if there's a newer version available using semantic versioning
                if latest_version and version.parse(latest_version) > version.parse(self.parent.version):
                    self.show_update_notification(latest_version, download_url, notification_message)
                elif manual_check:
                    messagebox.showinfo("Update Check", f"You are running the latest version ({self.parent.version}).")
            else:
                if manual_check:
                    messagebox.showwarning("Update Check Failed", 
                                        f"Could not check for updates. Server returned status code: {response.status_code}")
        except Exception as e:
            if manual_check:
                messagebox.showwarning("Update Check Failed", f"Could not check for updates: {str(e)}")
            print(f"Update check failed: {str(e)}")

    def show_update_notification(self, latest_version, download_url, message):
        """Show a notification about an available update."""
        # Create a notification window
        notification = tk.Toplevel(self.parent)
        notification.title("Update Available")

        # Get window dimensions from theme
        notification_width, notification_height = get_window_size('version_notification')
        position_x = self.parent.winfo_x() + (self.parent.winfo_width() - notification_width) // 2
        position_y = self.parent.winfo_y() + (self.parent.winfo_height() - notification_height) // 2
        notification.geometry(f"{notification_width}x{notification_height}+{position_x}+{position_y}")
        notification.resizable(False, False)

        # Add notification content (scale wraplength with dialog width)
        wrap_width = notification_width - 20
        tk.Label(notification, text=f"{message}", wraplength=wrap_width, justify="center", pady=10).pack()
        tk.Label(notification, text=f"Current version: {self.parent.version}", pady=5).pack()
        tk.Label(notification, text=f"Latest version: {latest_version}", pady=5).pack()
        
        # Add download button
        download_button = ttk.Button(
            notification, 
            text="Download Update", 
            command=lambda: self.open_download_page(download_url, notification)
        )
        download_button.pack(pady=10)
        
        # Add close button
        close_button = ttk.Button(notification, text="Close", command=notification.destroy)
        close_button.pack(pady=5)

    def open_download_page(self, url, notification_window=None):
        """Open the download page in a web browser."""
        open_url(url)
        if notification_window:
            notification_window.destroy() 