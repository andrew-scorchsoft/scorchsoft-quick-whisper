import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from PIL import Image, ImageTk
import webbrowser

from utils.tooltip import ToolTip

class UIManager:
    def __init__(self, parent):
        self.parent = parent
        self.banner_visible = True
        
        # Store UI element references
        self.transcription_text = None
        self.status_label = None
        self.model_label = None
        self.record_button_transcribe = None
        self.record_button_edit = None
        self.banner_label = None
        self.hide_banner_link = None
        self.powered_by_label = None
        self.banner_photo = None
        self.button_first_page = None
        self.button_arrow_left = None
        self.button_arrow_right = None
        
        # Icons
        self.icon_first_page = None
        self.icon_arrow_left = None
        self.icon_arrow_right = None
        
    def create_widgets(self):
        """Create all UI widgets for the application."""
        main_frame = ttk.Frame(self.parent, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        row = 0
        
        # Input Device Selection
        ttk.Label(main_frame, text="Input Device (mic):").grid(row=row, column=0, sticky="ew", pady=(0,10))
        devices = self.parent.audio_manager.get_input_devices()
        if not devices:
            tk.messagebox.showerror("No Input Devices", "No input audio devices found.")
            self.parent.destroy()
            return
        self.parent.selected_device.set(list(devices.keys())[0])  # Default selection

        device_menu = ttk.OptionMenu(main_frame, self.parent.selected_device, self.parent.selected_device.get(), *devices.keys())
        device_menu.grid(row=row, column=1, sticky="ew", pady=(0,10))

        row += 1

        # Load navigation icons
        self.icon_first_page = tk.PhotoImage(file=self.parent.resource_path("assets/first-page.png"))
        self.icon_arrow_left = tk.PhotoImage(file=self.parent.resource_path("assets/arrow-left.png"))
        self.icon_arrow_right = tk.PhotoImage(file=self.parent.resource_path("assets/arrow-right.png"))

        # Create a dedicated frame for the transcription section
        self.transcription_frame = ttk.Frame(main_frame)
        self.transcription_frame.grid(row=row, column=0, columnspan=2, pady=(0, 0), padx=0, sticky="ew")

        # Add the Transcription label to the transcription frame
        ttk.Label(self.transcription_frame, text="Transcription:").grid(row=0, column=0, sticky="w", pady=(0, 0), padx=(0, 0))

        # Create navigation buttons and place them next to the label within the transcription frame
        self.button_first_page = tk.Button(
            self.transcription_frame, 
            image=self.icon_first_page, 
            command=self.parent.go_to_first_page, 
            state=tk.DISABLED, 
            borderwidth=0
        )
        self.button_arrow_left = tk.Button(
            self.transcription_frame, 
            image=self.icon_arrow_left, 
            command=self.parent.navigate_left, 
            state=tk.DISABLED, 
            borderwidth=0
        )
        self.button_arrow_right = tk.Button(
            self.transcription_frame, 
            image=self.icon_arrow_right, 
            command=self.parent.navigate_right, 
            state=tk.DISABLED, 
            borderwidth=0
        )

        # Add tooltips to navigation buttons
        ToolTip(self.button_first_page, "Go to the latest entry")
        ToolTip(self.button_arrow_left, "Navigate to the more recent entry")
        ToolTip(self.button_arrow_right, "Navigate to the older entry")

        # Grid placement for navigation buttons in the transcription frame
        self.button_first_page.grid(row=0, column=1, sticky="e", padx=(0, 0))
        self.button_arrow_left.grid(row=0, column=2, sticky="e", padx=(0, 0))
        self.button_arrow_right.grid(row=0, column=3, sticky="e", padx=(0, 0))

        # Configure the columns within the transcription frame for proper alignment
        self.transcription_frame.columnconfigure(0, weight=1)  # Allow text area to expand
        self.transcription_frame.columnconfigure(1, minsize=30)  # Set a minimum size for each button column
        self.transcription_frame.columnconfigure(2, minsize=30)
        self.transcription_frame.columnconfigure(3, minsize=30)
        
        row += 1

        # Transcription Text Area
        self.transcription_text = tk.Text(main_frame, height=10, width=70, wrap="word")
        self.transcription_text.grid(row=row, column=0, columnspan=2, pady=(0,5))

        row += 1

        # Model Label
        self.model_label = ttk.Label(
            main_frame, 
            text=f"{self.parent.transcription_model}, {self.parent.ai_model}", 
            foreground="grey"
        )
        self.model_label.grid(row=row, column=0, columnspan=2, sticky=tk.E, pady=(0,20))

        # Status Label
        self.status_label = ttk.Label(main_frame, text=f"Status: Idle", foreground="blue")
        self.status_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0,20))

        row += 1

        # Auto-Copy Checkbox
        auto_copy_cb = ttk.Checkbutton(
            main_frame, 
            text="Copy to clipboard when done", 
            variable=self.parent.auto_copy
        )
        auto_copy_cb.grid(row=row, column=0, columnspan=1, sticky=tk.W, pady=(0,20))

        # Auto-Paste Checkbox
        auto_paste_cb = ttk.Checkbutton(
            main_frame, 
            text="Paste from clipboard when done", 
            variable=self.parent.auto_paste
        )
        auto_paste_cb.grid(row=row, column=1, columnspan=1, sticky=tk.W, pady=(0,20))

        row += 1

        button_width = 50

        ctk.set_appearance_mode("light")  # Options: "light" or "dark"
        ctk.set_default_color_theme("green")  # Options: "blue", "dark-blue", "green"

        # Update button text to show proper OS-specific shortcuts
        shortcut_text = "Cmd+Alt+J" if self.parent.is_mac else "Win+Alt+J"
        ctrl_shortcut_text = "Cmd+Ctrl+J" if self.parent.is_mac else "Win+Ctrl+J"

        # Record Transcript Only Button
        self.record_button_transcribe = ctk.CTkButton(
            main_frame, 
            text=f"Record + Transcript ({ctrl_shortcut_text})", 
            corner_radius=20, 
            height=35,
            width=button_width,
            fg_color="#058705",
            font=("Arial", 13, "bold"),
            command=lambda: self.parent.toggle_recording("transcribe")
        )
        self.record_button_transcribe.grid(row=row, column=0, columnspan=1, pady=(0,10), padx=(0, 5), sticky="ew")

        # Record + AI Edit Button
        self.record_button_edit = ctk.CTkButton(
            main_frame, 
            text=f"Record + AI Edit ({shortcut_text})", 
            corner_radius=20,
            height=35,
            width=button_width,
            fg_color="#058705",
            font=("Arial", 13, "bold"),
            command=lambda: self.parent.toggle_recording("edit")
        )
        self.record_button_edit.grid(row=row, column=1, columnspan=1, pady=(0,10), padx=(5, 0), sticky="ew")

        row += 1

        # Load and display the banner image
        banner_image_path = self.parent.resource_path("assets/banner-00-560.png")
        banner_image = Image.open(banner_image_path)
        self.banner_photo = ImageTk.PhotoImage(banner_image)  # Store to prevent garbage collection

        # Display the image in a label with clickability
        self.banner_label = tk.Label(main_frame, image=self.banner_photo, cursor="hand2")
        self.banner_label.grid(column=0, row=row, columnspan=2, pady=(10, 0), sticky="ew")
        self.banner_label.bind("<Button-1>", lambda e: self.open_scorchsoft())  # Bind the click event

        row += 1

        self.hide_banner_link = tk.Label(
            main_frame, 
            text="Hide Banner", 
            fg="blue", 
            cursor="hand2", 
            font=("Arial", 10, "underline")
        )
        self.hide_banner_link.grid(row=row, column=0, columnspan=2, pady=(5, 0), sticky="ew")
        self.hide_banner_link.bind("<Button-1>", lambda e: self.parent.toggle_banner())

        # Add a "Powered by Scorchsoft.com" link to replace the banner when hidden
        self.powered_by_label = tk.Label(
            main_frame,
            text="Powered by Scorchsoft.com",
            fg="black",
            cursor="hand2",
            font=("Arial", 8, "underline")
        )
        self.powered_by_label.grid(column=0, row=row, columnspan=2, pady=(5, 0), sticky="ew")
        self.powered_by_label.bind("<Button-1>", lambda e: self.open_scorchsoft())  # Bind click to open website
        self.powered_by_label.grid_remove()  # Hide the label initially

        # Configure grid
        main_frame.columnconfigure(0, weight=1, minsize=280)  # Set minsize to ensure equal width
        main_frame.columnconfigure(1, weight=1, minsize=280)
        
        return main_frame
        
    def open_scorchsoft(self, event=None):
        """Open the Scorchsoft website."""
        webbrowser.open('https://www.scorchsoft.com/contact-scorchsoft')
        
    def toggle_banner(self):
        """Toggle the visibility of the banner image and adjust the window height."""
        current_height = self.parent.winfo_height()
        new_height = current_height + 260 if not self.banner_visible else current_height - 260

        if self.banner_visible:
            self.banner_label.grid_remove()  # Hide the banner
            self.hide_banner_link.grid_remove()
            self.powered_by_label.grid()
            self.parent.help_menu.entryconfig("Hide Banner", label="Show Banner")  # Update menu text
        else:
            self.banner_label.grid()  # Show the banner
            self.parent.help_menu.entryconfig("Show Banner", label="Hide Banner")  # Update menu text
            self.powered_by_label.grid_remove() 

        # Set the new height and keep the current width
        self.parent.geometry(f"{self.parent.winfo_width()}x{new_height}")
        
        self.banner_visible = not self.banner_visible  # Toggle the visibility flag
    
    def update_model_label(self):
        """Update the model label to include the prompt name and language setting."""
        language_display = "Auto Detect" if self.parent.whisper_language == "auto" else self.parent.whisper_language.upper()
        model_type_display = "GPT" if self.parent.transcription_model_type == "gpt" else "Whisper"
        self.model_label.config(
            text=f"{self.parent.transcription_model} ({model_type_display}, {language_display}), {self.parent.ai_model}, {self.parent.current_prompt_name}"
        )
        
    def update_navigation_buttons(self):
        """Update the state of the navigation buttons based on history position."""
        if self.parent.history_index >= len(self.parent.history) - 1:
            self.button_first_page.config(state=tk.DISABLED)
            self.button_arrow_left.config(state=tk.DISABLED)
        else:
            self.button_first_page.config(state=tk.NORMAL)
            self.button_arrow_left.config(state=tk.NORMAL)

        # Disable 'right' button if we're on the oldest (first) entry
        if self.parent.history_index <= 0:
            self.button_arrow_right.config(state=tk.DISABLED)
        else:
            self.button_arrow_right.config(state=tk.NORMAL)
            
    def update_transcription_text(self):
        """Update the transcription text area with the current history item."""
        if 0 <= self.parent.history_index < len(self.parent.history):
            self.transcription_text.delete("1.0", tk.END)
            self.transcription_text.insert("1.0", self.parent.history[self.parent.history_index])
            
    def set_status(self, message, color="blue"):
        """Update the status label with a message and color."""
        self.status_label.config(text=f"Status: {message}", foreground=color) 