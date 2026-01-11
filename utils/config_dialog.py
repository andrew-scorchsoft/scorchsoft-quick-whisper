import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
from pathlib import Path
import os
import platform
from utils.config_manager import get_config

class ConfigDialog:
    def __init__(self, parent):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Configuration Settings")
        self.dialog.geometry("700x500")
        
        # Center the window
        window_width = 700
        window_height = 500
        position_x = parent.winfo_x() + (parent.winfo_width() - window_width) // 2
        position_y = parent.winfo_y() + (parent.winfo_height() - window_height) // 2
        self.dialog.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")
        
        self.dialog.transient(parent)
        self.dialog.grab_set()
        # Pause hotkeys while config is active
        if hasattr(self.parent, 'hotkey_manager'):
            self.parent.hotkey_manager.pause()
        
        # Variables for settings
        self.recording_location_var = tk.StringVar()
        self.custom_location_var = tk.StringVar()
        self.file_handling_var = tk.StringVar()
        
        # Load current settings
        self.load_current_settings()
        
        # Current selected category
        self.current_category = "Recording"
        
        self.create_dialog()
        
    def load_current_settings(self):
        """Load current configuration settings from settings.json."""
        self.config = get_config()
            
        # Recording location (default: alongside)
        self.recording_location_var.set(self.config.recording_location)
        
        # Custom location path
        self.custom_location_var.set(self.config.custom_recording_path)
        
        # File handling (default: overwrite)
        self.file_handling_var.set(self.config.file_handling)
        
    def create_dialog(self):
        """Create the main dialog layout."""
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create top frame for navigation and content
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create bottom frame for buttons
        self.create_bottom_buttons(main_frame)
        
        # Create left navigation and right content areas in the top frame
        self.create_navigation_panel(top_frame)
        self.create_content_panel(top_frame)
        
        # Initially show recording settings
        self.show_recording_settings()
        
    def create_navigation_panel(self, parent):
        """Create the left navigation panel."""
        self.nav_frame = ttk.LabelFrame(parent, text="Settings Categories", padding="10")
        self.nav_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # Navigation buttons
        self.nav_buttons = {}
        
        self.nav_buttons["Recording"] = ttk.Button(
            self.nav_frame,
            text="Recording",
            command=lambda: self.switch_category("Recording"),
            width=15
        )
        self.nav_buttons["Recording"].pack(fill=tk.X, pady=2)
        
        # Future categories can be added here
        # self.nav_buttons["Other"] = ttk.Button(
        #     self.nav_frame,
        #     text="Other Settings",
        #     command=lambda: self.switch_category("Other"),
        #     width=15
        # )
        # self.nav_buttons["Other"].pack(fill=tk.X, pady=2)
        
        # Highlight current selection
        self.update_navigation_highlight()
        
    def create_content_panel(self, parent):
        """Create the right content panel."""
        self.content_frame = ttk.Frame(parent)
        self.content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
    def create_bottom_buttons(self, parent):
        """Create the bottom button panel."""
        button_frame = ttk.Frame(parent)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        
        # Cancel and Save buttons (Cancel on left, Save on right)
        cancel_button = ctk.CTkButton(
            button_frame,
            text="Cancel",
            corner_radius=20,
            height=35,
            width=150,
            fg_color="#666666",
            hover_color="#444444",
            font=("Arial", 13, "bold"),
            command=self._close_dialog
        )
        cancel_button.pack(side=tk.LEFT, padx=(0, 5))
        
        save_button = ctk.CTkButton(
            button_frame,
            text="Save Changes",
            corner_radius=20,
            height=35,
            width=150,
            fg_color="#058705",
            hover_color="#046a38",
            font=("Arial", 13, "bold"),
            command=self.save_settings
        )
        save_button.pack(side=tk.RIGHT, padx=(5, 0))
        
    def switch_category(self, category):
        """Switch to a different settings category."""
        self.current_category = category
        self.update_navigation_highlight()
        
        # Clear current content
        for widget in self.content_frame.winfo_children():
            widget.destroy()
            
        # Show appropriate settings
        if category == "Recording":
            self.show_recording_settings()
        # Add other categories here as needed
            
    def update_navigation_highlight(self):
        """Update the visual highlight for the current navigation selection."""
        for category, button in self.nav_buttons.items():
            if category == self.current_category:
                # Highlight the current selection by making it look pressed
                button.state(['pressed'])
            else:
                # Normal state for other buttons
                button.state(['!pressed'])
                
    def show_recording_settings(self):
        """Show the recording settings panel."""
        # Main title
        title_label = ttk.Label(
            self.content_frame,
            text="Recording Settings",
            font=("Arial", 14, "bold")
        )
        title_label.pack(anchor="w", pady=(0, 20))
        
        # Recording Location Section
        location_frame = ttk.LabelFrame(
            self.content_frame,
            text="Recording Location",
            padding="15"
        )
        location_frame.pack(fill="x", pady=(0, 20))
        
        ttk.Label(
            location_frame,
            text="Choose where to save audio recording files:",
            font=("Arial", 10)
        ).pack(anchor="w", pady=(0, 10))
        
        # Radio buttons for location options
        ttk.Radiobutton(
            location_frame,
            text="Alongside application (recommended)",
            variable=self.recording_location_var,
            value="alongside"
        ).pack(anchor="w", pady=2)
        
        # Get the appropriate AppData path based on OS
        if platform.system() == "Windows":
            appdata_text = "In AppData folder"
        elif platform.system() == "Darwin":  # macOS
            appdata_text = "In Application Support folder"
        else:  # Linux
            appdata_text = "In home config folder"
            
        ttk.Radiobutton(
            location_frame,
            text=appdata_text,
            variable=self.recording_location_var,
            value="appdata"
        ).pack(anchor="w", pady=2)
        
        ttk.Radiobutton(
            location_frame,
            text="Custom folder:",
            variable=self.recording_location_var,
            value="custom",
            command=self.on_custom_location_selected
        ).pack(anchor="w", pady=2)
        
        # Custom folder selection frame
        self.custom_folder_frame = ttk.Frame(location_frame)
        self.custom_folder_frame.pack(fill="x", pady=(5, 0), padx=(20, 0))
        
        self.custom_path_entry = ttk.Entry(
            self.custom_folder_frame,
            textvariable=self.custom_location_var,
            state="readonly" if self.recording_location_var.get() != "custom" else "normal"
        )
        self.custom_path_entry.pack(side=tk.LEFT, fill="x", expand=True, padx=(0, 5))
        
        self.browse_button = ttk.Button(
            self.custom_folder_frame,
            text="Browse...",
            command=self.browse_custom_folder,
            state="disabled" if self.recording_location_var.get() != "custom" else "normal"
        )
        self.browse_button.pack(side=tk.RIGHT)
        
        # File Handling Section
        handling_frame = ttk.LabelFrame(
            self.content_frame,
            text="File Handling",
            padding="15"
        )
        handling_frame.pack(fill="x", pady=(0, 20))
        
        ttk.Label(
            handling_frame,
            text="Choose how to handle recording files:",
            font=("Arial", 10)
        ).pack(anchor="w", pady=(0, 10))
        
        ttk.Radiobutton(
            handling_frame,
            text="Overwrite the same file each time (saves disk space)",
            variable=self.file_handling_var,
            value="overwrite"
        ).pack(anchor="w", pady=2)
        
        ttk.Radiobutton(
            handling_frame,
            text="Save each recording with date/time in filename",
            variable=self.file_handling_var,
            value="timestamp"
        ).pack(anchor="w", pady=2)
        
        # Warning for timestamp option
        warning_frame = ttk.Frame(handling_frame)
        warning_frame.pack(fill="x", pady=(5, 0), padx=(20, 0))
        
        ttk.Label(
            warning_frame,
            text="⚠️ Warning: This can consume significant disk space over time",
            font=("Arial", 9),
            foreground="#CC6600"
        ).pack(anchor="w")
        
        # Bind radio button changes to update UI state
        self.recording_location_var.trace("w", self.on_location_change)
        
    def on_location_change(self, *args):
        """Handle changes to the recording location selection."""
        is_custom = self.recording_location_var.get() == "custom"
        
        # Enable/disable custom path controls
        self.custom_path_entry.configure(state="normal" if is_custom else "readonly")
        self.browse_button.configure(state="normal" if is_custom else "disabled")
        
    def on_custom_location_selected(self):
        """Handle when custom location radio button is selected."""
        # If no custom path is set and custom is selected, open browse dialog
        if not self.custom_location_var.get().strip():
            self.browse_custom_folder()
            
    def browse_custom_folder(self):
        """Open a folder selection dialog."""
        folder_path = filedialog.askdirectory(
            title="Select Recording Folder",
            initialdir=self.custom_location_var.get() or os.path.expanduser("~")
        )
        
        if folder_path:
            self.custom_location_var.set(folder_path)
            
    def save_settings(self):
        """Save the configuration settings to settings.json."""
        # Validate custom path if selected
        if self.recording_location_var.get() == "custom":
            custom_path = self.custom_location_var.get().strip()
            if not custom_path:
                messagebox.showerror("Error", "Please select a custom folder path.")
                return
                
            if not os.path.exists(custom_path):
                create_folder = messagebox.askyesno(
                    "Folder Does Not Exist",
                    f"The folder '{custom_path}' does not exist. Would you like to create it?"
                )
                if create_folder:
                    try:
                        os.makedirs(custom_path, exist_ok=True)
                    except Exception as e:
                        messagebox.showerror("Error", f"Could not create folder: {e}")
                        return
                else:
                    return
        
        # Update configuration values
        try:
            self.config.recording_location = self.recording_location_var.get()
            self.config.custom_recording_path = self.custom_location_var.get()
            self.config.file_handling = self.file_handling_var.get()
            
            # Save to file
            self.config.save_settings()
                        
            messagebox.showinfo("Success", "Configuration settings saved and applied successfully!")
            
            # Update parent's recording directory
            self.parent.update_recording_directory()
            
            self._close_dialog()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not save settings: {e}") 

    def _close_dialog(self):
        try:
            self.dialog.destroy()
        finally:
            if hasattr(self.parent, 'hotkey_manager'):
                self.parent.hotkey_manager.resume()