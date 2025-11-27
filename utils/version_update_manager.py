import tkinter as tk
from tkinter import ttk, messagebox
import threading
import requests
import webbrowser
from pathlib import Path
import os
from packaging import version

class VersionUpdateManager:
    def __init__(self, parent):
        self.parent = parent
        self.version_check_url = "https://www.scorchsoft.com/public/blog/quick-whisper-speech-to-copyedited-text/latest-version.json"
        self.auto_update_check = tk.BooleanVar(value=True)
        
        # Load settings from env file
        auto_update = os.getenv("AUTO_UPDATE_CHECK", "true").lower()
        self.auto_update_check.set(auto_update == "true")
        
    def start_check(self, delay=2000):
        """Start the update check with delay to avoid blocking app startup"""
        if self.auto_update_check.get():
            self.parent.after(delay, lambda: threading.Thread(target=self.check_for_updates).start())
    
    def save_auto_update_setting(self):
        """Save the auto update setting to the .env file."""
        config_dir = Path("config")
        config_dir.mkdir(parents=True, exist_ok=True)
        env_path = config_dir / ".env"

        # Read existing settings
        env_vars = {}
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            key, val = line.strip().split('=', 1)
                            env_vars[key] = val
                        except ValueError:
                            continue  # Skip malformed lines

        # Update or add the AUTO_UPDATE_CHECK setting
        env_vars["AUTO_UPDATE_CHECK"] = str(self.auto_update_check.get()).lower()

        # Write back all variables
        with open(env_path, 'w') as f:
            for key, val in env_vars.items():
                f.write(f"{key}={val}\n")

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
                    messagebox.showinfo(self.parent.get_text("Update Check"), self.parent.get_text("You are running the latest version ({})").format(self.parent.version))
            else:
                if manual_check:
                    messagebox.showwarning(self.parent.get_text("Update Check Failed"), 
                                        self.parent.get_text("Could not check for updates. Server returned status code: {}").format(response.status_code))
        except Exception as e:
            if manual_check:
                messagebox.showwarning(self.parent.get_text("Update Check Failed"), self.parent.get_text("Could not check for updates: {}").format(str(e)))
            print(f"Update check failed: {str(e)}")

    def show_update_notification(self, latest_version, download_url, message):
        """Show a notification about an available update."""
        # Create a notification window
        notification = tk.Toplevel(self.parent)
        notification.title(self.parent.get_text("Update Available"))
        
        # Set size and position
        notification_width = 400
        notification_height = 200
        position_x = self.parent.winfo_x() + (self.parent.winfo_width() - notification_width) // 2
        position_y = self.parent.winfo_y() + (self.parent.winfo_height() - notification_height) // 2
        notification.geometry(f"{notification_width}x{notification_height}+{position_x}+{position_y}")
        notification.resizable(False, False)
        
        # Add notification content
        tk.Label(notification, text=f"{message}", wraplength=380, justify="center", pady=10).pack()
        tk.Label(notification, text=self.parent.get_text("Current version: {}").format(self.parent.version), pady=5).pack()
        tk.Label(notification, text=self.parent.get_text("Latest version: {}").format(latest_version), pady=5).pack()
        
        # Add download button
        download_button = ttk.Button(
            notification, 
            text=self.parent.get_text("Download Update"), 
            command=lambda: self.open_download_page(download_url, notification)
        )
        download_button.pack(pady=10)
        
        # Add close button
        close_button = ttk.Button(notification, text=self.parent.get_text("Close"), command=notification.destroy)
        close_button.pack(pady=5)

    def open_download_page(self, url, notification_window=None):
        """Open the download page in a web browser."""
        webbrowser.open(url)
        if notification_window:
            notification_window.destroy() 