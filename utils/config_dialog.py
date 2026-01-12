import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
from pathlib import Path
import os
import platform
from utils.config_manager import get_config
from utils.theme import get_font, get_font_size, get_font_family, get_window_size, get_button_height, get_spacing

class ConfigDialog:
    def __init__(self, parent):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Configuration Settings")

        # Get window dimensions from theme
        window_width, window_height = get_window_size('config_dialog')
        self.dialog.geometry(f"{window_width}x{window_height}")

        # Center the window
        position_x = parent.winfo_x() + (parent.winfo_width() - window_width) // 2
        position_y = parent.winfo_y() + (parent.winfo_height() - window_height) // 2
        self.dialog.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")
        
        self.dialog.transient(parent)
        self.dialog.wait_visibility()  # Wait for dialog to be visible before grabbing (Linux fix)
        self.dialog.grab_set()
        # Pause hotkeys while config is active
        if hasattr(self.parent, 'hotkey_manager'):
            self.parent.hotkey_manager.pause()
        
        # Handle window close (X button) to ensure hotkeys are resumed
        self.dialog.protocol("WM_DELETE_WINDOW", self._close_dialog)
        
        # Variables for settings
        self.recording_location_var = tk.StringVar()
        self.custom_location_var = tk.StringVar()
        self.file_handling_var = tk.StringVar()
        self.hidpi_mode_var = tk.StringVar()

        # Track original HiDPI setting for restart prompt
        self.original_hidpi_mode = None

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

        # HiDPI mode (default: auto)
        self.hidpi_mode_var.set(self.config.hidpi_mode)
        self.original_hidpi_mode = self.config.hidpi_mode
        
    def create_dialog(self):
        """Create the main dialog layout."""
        # Check current theme for appropriate colors
        is_dark = self.config.dark_mode

        # Configure styles for consistent fonts
        style = ttk.Style()
        style.configure('Dialog.TButton', font=get_font('sm'))
        style.configure('Dialog.TLabel', font=get_font('sm'))
        style.configure('Dialog.TLabelframe.Label', font=get_font('sm', 'bold'))
        style.configure('Dialog.TRadiobutton', font=get_font('sm'))

        # Navigation button styles - unselected (normal)
        style.configure('Nav.TButton', font=get_font('sm'))

        # Navigation button styles - selected (bold with accent background)
        style.configure('NavSelected.TButton', font=get_font('sm', 'bold'))

        # Map colors for selected state based on theme
        if is_dark:
            # Dark mode: lighter background for selected
            style.map('NavSelected.TButton',
                background=[('!disabled', '#3d3d3d'), ('active', '#4a4a4a')],
                foreground=[('!disabled', '#ffffff')]
            )
        else:
            # Light mode: slightly darker/accent background for selected
            style.map('NavSelected.TButton',
                background=[('!disabled', '#e0e0e0'), ('active', '#d0d0d0')],
                foreground=[('!disabled', '#000000')]
            )

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
        self.nav_frame = ttk.LabelFrame(parent, text="Settings Categories", padding="10", style='Dialog.TLabelframe')
        self.nav_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Navigation buttons
        self.nav_buttons = {}

        self.nav_buttons["Recording"] = ttk.Button(
            self.nav_frame,
            text="Recording",
            command=lambda: self.switch_category("Recording"),
            width=15,
            style='Nav.TButton',
            cursor='hand2'
        )
        self.nav_buttons["Recording"].pack(fill=tk.X, pady=2)

        self.nav_buttons["Display"] = ttk.Button(
            self.nav_frame,
            text="Display",
            command=lambda: self.switch_category("Display"),
            width=15,
            style='Nav.TButton',
            cursor='hand2'
        )
        self.nav_buttons["Display"].pack(fill=tk.X, pady=2)

        # Highlight current selection
        self.update_navigation_highlight()
        
    def create_content_panel(self, parent):
        """Create the right content panel."""
        self.content_frame = ttk.Frame(parent)
        self.content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
    def create_bottom_buttons(self, parent):
        """Create the bottom button panel."""
        button_frame = ttk.Frame(parent)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(get_spacing('lg'), 0))

        # Use half the button height for corner_radius to create pill shape
        button_height = get_button_height('dialog')
        corner_radius = button_height // 2

        # Cancel and Save buttons (Cancel on left, Save on right)
        cancel_button = ctk.CTkButton(
            button_frame,
            text="Cancel",
            corner_radius=corner_radius,
            height=button_height,
            width=180,
            fg_color="#666666",
            hover_color="#444444",
            font=ctk.CTkFont(family=get_font_family(), size=get_font_size('dialog_button'), weight='bold'),
            cursor="hand2",
            command=self._close_dialog
        )
        cancel_button.pack(side=tk.LEFT, padx=(0, get_spacing('sm')))

        save_button = ctk.CTkButton(
            button_frame,
            text="Save Changes",
            corner_radius=corner_radius,
            height=button_height,
            width=200,
            fg_color="#058705",
            hover_color="#046a38",
            font=ctk.CTkFont(family=get_font_family(), size=get_font_size('dialog_button'), weight='bold'),
            cursor="hand2",
            command=self.save_settings
        )
        save_button.pack(side=tk.RIGHT, padx=(get_spacing('sm'), 0))
        
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
        elif category == "Display":
            self.show_display_settings()
            
    def update_navigation_highlight(self):
        """Update the visual highlight for the current navigation selection."""
        for category, button in self.nav_buttons.items():
            if category == self.current_category:
                # Selected: bold text with accent background
                button.configure(style='NavSelected.TButton')
            else:
                # Unselected: normal style
                button.configure(style='Nav.TButton')
                
    def show_recording_settings(self):
        """Show the recording settings panel."""
        # Main title
        title_label = ttk.Label(
            self.content_frame,
            text="Recording Settings",
            font=get_font('lg', 'bold')
        )
        title_label.pack(anchor="w", pady=(0, 20))

        # Recording Location Section
        location_frame = ttk.LabelFrame(
            self.content_frame,
            text="Recording Location",
            padding="15",
            style='Dialog.TLabelframe'
        )
        location_frame.pack(fill="x", pady=(0, 20))

        ttk.Label(
            location_frame,
            text="Choose where to save audio recording files:",
            style='Dialog.TLabel'
        ).pack(anchor="w", pady=(0, 10))

        # Radio buttons for location options
        ttk.Radiobutton(
            location_frame,
            text="Alongside application (recommended)",
            variable=self.recording_location_var,
            value="alongside",
            style='Dialog.TRadiobutton'
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
            value="appdata",
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)

        ttk.Radiobutton(
            location_frame,
            text="Custom folder:",
            variable=self.recording_location_var,
            value="custom",
            command=self.on_custom_location_selected,
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)
        
        # Custom folder selection frame
        self.custom_folder_frame = ttk.Frame(location_frame)
        self.custom_folder_frame.pack(fill="x", pady=(5, 0), padx=(20, 0))

        self.custom_path_entry = ttk.Entry(
            self.custom_folder_frame,
            textvariable=self.custom_location_var,
            state="readonly" if self.recording_location_var.get() != "custom" else "normal",
            font=get_font('sm')
        )
        self.custom_path_entry.pack(side=tk.LEFT, fill="x", expand=True, padx=(0, 5))

        self.browse_button = ttk.Button(
            self.custom_folder_frame,
            text="Browse...",
            command=self.browse_custom_folder,
            state="disabled" if self.recording_location_var.get() != "custom" else "normal",
            style='Dialog.TButton',
            cursor='hand2'
        )
        self.browse_button.pack(side=tk.RIGHT)
        
        # File Handling Section
        handling_frame = ttk.LabelFrame(
            self.content_frame,
            text="File Handling",
            padding="15",
            style='Dialog.TLabelframe'
        )
        handling_frame.pack(fill="x", pady=(0, 20))

        ttk.Label(
            handling_frame,
            text="Choose how to handle recording files:",
            style='Dialog.TLabel'
        ).pack(anchor="w", pady=(0, 10))

        ttk.Radiobutton(
            handling_frame,
            text="Overwrite the same file each time (saves disk space)",
            variable=self.file_handling_var,
            value="overwrite",
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)

        ttk.Radiobutton(
            handling_frame,
            text="Save each recording with date/time in filename",
            variable=self.file_handling_var,
            value="timestamp",
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)
        
        # Warning for timestamp option
        warning_frame = ttk.Frame(handling_frame)
        warning_frame.pack(fill="x", pady=(5, 0), padx=(20, 0))
        
        ttk.Label(
            warning_frame,
            text="⚠️ Warning: This can consume significant disk space over time",
            font=get_font('xxs'),
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

    def show_display_settings(self):
        """Show the display settings panel."""
        # Main title
        title_label = ttk.Label(
            self.content_frame,
            text="Display Settings",
            font=get_font('lg', 'bold')
        )
        title_label.pack(anchor="w", pady=(0, 20))

        # HiDPI Scaling Section
        hidpi_frame = ttk.LabelFrame(
            self.content_frame,
            text="HiDPI Scaling",
            padding="15",
            style='Dialog.TLabelframe'
        )
        hidpi_frame.pack(fill="x", pady=(0, 20))

        ttk.Label(
            hidpi_frame,
            text="Choose how HiDPI (high resolution) scaling is applied:",
            style='Dialog.TLabel'
        ).pack(anchor="w", pady=(0, 10))

        # Radio buttons for HiDPI options
        ttk.Radiobutton(
            hidpi_frame,
            text="Auto-detect (recommended)",
            variable=self.hidpi_mode_var,
            value="auto",
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)

        auto_description = ttk.Label(
            hidpi_frame,
            text="Automatically detect and apply appropriate scaling based on your display",
            font=get_font('xxs'),
            foreground="#888888"
        )
        auto_description.pack(anchor="w", padx=(20, 0), pady=(0, 8))

        ttk.Radiobutton(
            hidpi_frame,
            text="Force enabled",
            variable=self.hidpi_mode_var,
            value="enabled",
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)

        enabled_description = ttk.Label(
            hidpi_frame,
            text="Always apply HiDPI scaling (use if auto-detection doesn't work correctly)",
            font=get_font('xxs'),
            foreground="#888888"
        )
        enabled_description.pack(anchor="w", padx=(20, 0), pady=(0, 8))

        ttk.Radiobutton(
            hidpi_frame,
            text="Disabled",
            variable=self.hidpi_mode_var,
            value="disabled",
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)

        disabled_description = ttk.Label(
            hidpi_frame,
            text="Never apply HiDPI scaling (use standard scaling)",
            font=get_font('xxs'),
            foreground="#888888"
        )
        disabled_description.pack(anchor="w", padx=(20, 0), pady=(0, 8))

        # Note about restart requirement
        note_frame = ttk.Frame(hidpi_frame)
        note_frame.pack(fill="x", pady=(10, 0))

        ttk.Label(
            note_frame,
            text="Note: Changes to HiDPI scaling require a restart to take effect.",
            font=get_font('xs'),
            foreground="#CC6600"
        ).pack(anchor="w")

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

        # Check if HiDPI setting changed (requires restart)
        hidpi_changed = self.hidpi_mode_var.get() != self.original_hidpi_mode

        # Update configuration values
        try:
            self.config.recording_location = self.recording_location_var.get()
            self.config.custom_recording_path = self.custom_location_var.get()
            self.config.file_handling = self.file_handling_var.get()
            self.config.hidpi_mode = self.hidpi_mode_var.get()

            # Save to file
            self.config.save_settings()

            # Update parent's recording directory
            self.parent.update_recording_directory()

            # If HiDPI changed, prompt for restart
            if hidpi_changed:
                restart_now = messagebox.askyesno(
                    "Restart Required",
                    "The HiDPI scaling setting has been changed. "
                    "This requires a restart to take effect.\n\n"
                    "Would you like to restart the application now?",
                    icon='question'
                )
                if restart_now:
                    self._close_dialog()
                    self.parent.restart_application()
                    return
                else:
                    messagebox.showinfo(
                        "Settings Saved",
                        "Configuration settings saved successfully!\n\n"
                        "The HiDPI scaling change will take effect after you restart the application."
                    )
                    self._close_dialog()
                    return

            messagebox.showinfo("Success", "Configuration settings saved and applied successfully!")
            self._close_dialog()

        except Exception as e:
            messagebox.showerror("Error", f"Could not save settings: {e}") 

    def _close_dialog(self):
        try:
            self.dialog.destroy()
        finally:
            if hasattr(self.parent, 'hotkey_manager'):
                self.parent.hotkey_manager.resume()