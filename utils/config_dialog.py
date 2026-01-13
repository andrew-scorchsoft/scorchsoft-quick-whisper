import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
from pathlib import Path
import os
import platform
import time
from utils.config_manager import get_config
from utils.theme import get_font, get_font_size, get_font_family, get_window_size, get_button_height, get_spacing
from utils.platform import open_url
from utils.i18n import (
    _, _n, set_language, get_current_language, detect_os_locale,
    get_detected_locale_display, get_available_languages, SUPPORTED_LANGUAGES
)

# Theme colors for dark mode (used in AI Models section)
THEME_TEXT_MUTED = "#909090"
THEME_ACCENT = "#22d3ee"
THEME_ACCENT_HOVER = "#67e8f9"

class ConfigDialog:
    def __init__(self, parent):
        _t0 = time.perf_counter()
        print(f"[CONFIG DIALOG] __init__ started")

        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.withdraw()  # Hide window until UI is built
        self.dialog.title(_("Configuration Settings"))
        print(f"[CONFIG DIALOG] Toplevel created: {(time.perf_counter() - _t0)*1000:.1f}ms")

        # Get window dimensions from theme
        window_width, window_height = get_window_size('config_dialog')
        self.dialog.geometry(f"{window_width}x{window_height}")

        # Center the window
        position_x = parent.winfo_x() + (parent.winfo_width() - window_width) // 2
        position_y = parent.winfo_y() + (parent.winfo_height() - window_height) // 2
        self.dialog.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")

        self.dialog.transient(parent)

        # Handle window close (X button) to ensure hotkeys are resumed
        self.dialog.protocol("WM_DELETE_WINDOW", self._close_dialog)
        print(f"[CONFIG DIALOG] Window configured: {(time.perf_counter() - _t0)*1000:.1f}ms")

        # Variables for settings
        self.recording_location_var = tk.StringVar()
        self.custom_location_var = tk.StringVar()
        self.file_handling_var = tk.StringVar()
        self.hidpi_mode_var = tk.StringVar()

        # Language settings variables
        self.language_mode_var = tk.StringVar()
        self.language_var = tk.StringVar()

        # AI Models settings variables
        self.whisper_language_var = tk.StringVar()
        self.transcription_model_var = tk.StringVar()
        self.custom_transcription_model_var = tk.StringVar()
        self.llm_model_var = tk.StringVar()
        self.custom_llm_model_var = tk.StringVar()

        # Track original HiDPI setting for restart prompt
        self.original_hidpi_mode = None
        print(f"[CONFIG DIALOG] Variables initialized: {(time.perf_counter() - _t0)*1000:.1f}ms")

        # Define Whisper supported languages
        self.languages = {
            "auto": "Auto Detect",
            "af": "Afrikaans",
            "ar": "Arabic",
            "hy": "Armenian",
            "az": "Azerbaijani",
            "be": "Belarusian",
            "bs": "Bosnian",
            "bg": "Bulgarian",
            "ca": "Catalan",
            "zh": "Chinese",
            "hr": "Croatian",
            "cs": "Czech",
            "da": "Danish",
            "nl": "Dutch",
            "en": "English",
            "et": "Estonian",
            "fi": "Finnish",
            "fr": "French",
            "gl": "Galician",
            "de": "German",
            "el": "Greek",
            "he": "Hebrew",
            "hi": "Hindi",
            "hu": "Hungarian",
            "is": "Icelandic",
            "id": "Indonesian",
            "it": "Italian",
            "ja": "Japanese",
            "kn": "Kannada",
            "kk": "Kazakh",
            "ko": "Korean",
            "lv": "Latvian",
            "lt": "Lithuanian",
            "mk": "Macedonian",
            "ms": "Malay",
            "mr": "Marathi",
            "mi": "Maori",
            "ne": "Nepali",
            "no": "Norwegian",
            "fa": "Persian",
            "pl": "Polish",
            "pt": "Portuguese",
            "ro": "Romanian",
            "ru": "Russian",
            "sr": "Serbian",
            "sk": "Slovak",
            "sl": "Slovenian",
            "es": "Spanish",
            "sw": "Swahili",
            "sv": "Swedish",
            "tl": "Tagalog",
            "ta": "Tamil",
            "th": "Thai",
            "tr": "Turkish",
            "uk": "Ukrainian",
            "ur": "Urdu",
            "vi": "Vietnamese",
            "cy": "Welsh"
        }

        # Define transcription models and their types
        self.transcription_models = {
            "gpt-4o-transcribe": "gpt",
            "whisper-1": "whisper",
            "other": "unknown"
        }

        # Define LLM models for copy-editing
        self.llm_models = [
            "gpt-5",
            "gpt-5-mini",
            "gpt-5-nano",
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4.1-nano",
            "gpt-4o",
            "gpt-4o-mini",
            "other"
        ]
        print(f"[CONFIG DIALOG] Static data defined: {(time.perf_counter() - _t0)*1000:.1f}ms")

        # Load current settings
        self.load_current_settings()
        print(f"[CONFIG DIALOG] Settings loaded: {(time.perf_counter() - _t0)*1000:.1f}ms")
        
        # Current selected category
        self.current_category = "Recording"

        self.create_dialog()
        print(f"[CONFIG DIALOG] create_dialog() done: {(time.perf_counter() - _t0)*1000:.1f}ms")

        # Force Tkinter to process all widget geometry before showing
        # This prevents the black flash by ensuring widgets are rendered
        self.dialog.update_idletasks()
        print(f"[CONFIG DIALOG] update_idletasks() done: {(time.perf_counter() - _t0)*1000:.1f}ms")

        # Show window now that UI is fully built (prevents black flash)
        self.dialog.deiconify()
        print(f"[CONFIG DIALOG] deiconify() done: {(time.perf_counter() - _t0)*1000:.1f}ms")

        # Make dialog modal after UI is built (faster perceived load)
        self.dialog.wait_visibility()  # Wait for dialog to be visible before grabbing (Linux fix)
        print(f"[CONFIG DIALOG] wait_visibility() done: {(time.perf_counter() - _t0)*1000:.1f}ms")
        self.dialog.grab_set()
        print(f"[CONFIG DIALOG] grab_set() done: {(time.perf_counter() - _t0)*1000:.1f}ms")

        # Defer hotkey pause to after dialog is fully painted
        # Using after(50) + update() ensures widgets are rendered before the blocking pause
        if hasattr(self.parent, 'hotkey_manager'):
            def pause_hotkeys():
                self.dialog.update()  # Force full repaint before blocking pause
                self.parent.hotkey_manager.pause()
            self.dialog.after(50, pause_hotkeys)
        print(f"[CONFIG DIALOG] __init__ complete: {(time.perf_counter() - _t0)*1000:.1f}ms")

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

        # Language settings
        self.language_mode_var.set(self.config.language_mode)
        self.language_var.set(self.config.language)

        # AI Models settings
        self.whisper_language_var.set(self.config.whisper_language)

        # Transcription model - determine if it's a known model or custom
        current_trans_model = self.config.transcription_model
        if current_trans_model in self.transcription_models:
            self.transcription_model_var.set(current_trans_model)
        else:
            self.transcription_model_var.set("other")
            self.custom_transcription_model_var.set(current_trans_model)

        # LLM model - determine if it's a known model or custom
        current_llm = self.config.ai_model
        if current_llm in self.llm_models:
            self.llm_model_var.set(current_llm)
        else:
            self.llm_model_var.set("other")
            self.custom_llm_model_var.set(current_llm)
        
    def create_dialog(self):
        """Create the main dialog layout."""
        _t0 = time.perf_counter()

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
        print(f"[CONFIG DIALOG]   - styles configured: {(time.perf_counter() - _t0)*1000:.1f}ms")

        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Create top frame for navigation and content
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.BOTH, expand=True)
        print(f"[CONFIG DIALOG]   - frames created: {(time.perf_counter() - _t0)*1000:.1f}ms")

        # Create bottom frame for buttons
        self.create_bottom_buttons(main_frame)
        print(f"[CONFIG DIALOG]   - bottom buttons created: {(time.perf_counter() - _t0)*1000:.1f}ms")

        # Create left navigation and right content areas in the top frame
        self.create_navigation_panel(top_frame)
        print(f"[CONFIG DIALOG]   - navigation panel created: {(time.perf_counter() - _t0)*1000:.1f}ms")
        self.create_content_panel(top_frame)
        print(f"[CONFIG DIALOG]   - content panel created: {(time.perf_counter() - _t0)*1000:.1f}ms")

        # Initially show recording settings
        self.show_recording_settings()
        print(f"[CONFIG DIALOG]   - recording settings shown: {(time.perf_counter() - _t0)*1000:.1f}ms")
        
    def create_navigation_panel(self, parent):
        """Create the left navigation panel."""
        self.nav_frame = ttk.LabelFrame(parent, text=_("Settings Categories"), padding="10", style='Dialog.TLabelframe')
        self.nav_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Navigation buttons
        self.nav_buttons = {}

        self.nav_buttons["Recording"] = ttk.Button(
            self.nav_frame,
            text=_("Recording"),
            command=lambda: self.switch_category("Recording"),
            width=15,
            style='Nav.TButton',
            cursor='hand2'
        )
        self.nav_buttons["Recording"].pack(fill=tk.X, pady=2)

        self.nav_buttons["Display"] = ttk.Button(
            self.nav_frame,
            text=_("Display"),
            command=lambda: self.switch_category("Display"),
            width=15,
            style='Nav.TButton',
            cursor='hand2'
        )
        self.nav_buttons["Display"].pack(fill=tk.X, pady=2)

        self.nav_buttons["Language"] = ttk.Button(
            self.nav_frame,
            text=_("Language"),
            command=lambda: self.switch_category("Language"),
            width=15,
            style='Nav.TButton',
            cursor='hand2'
        )
        self.nav_buttons["Language"].pack(fill=tk.X, pady=2)

        self.nav_buttons["AI Models"] = ttk.Button(
            self.nav_frame,
            text=_("AI Models"),
            command=lambda: self.switch_category("AI Models"),
            width=15,
            style='Nav.TButton',
            cursor='hand2'
        )
        self.nav_buttons["AI Models"].pack(fill=tk.X, pady=2)

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
            text=_("Cancel"),
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
            text=_("Save Changes"),
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
        elif category == "Language":
            self.show_language_settings()
        elif category == "AI Models":
            self.show_ai_models_settings()
            
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
            text=_("Recording Settings"),
            font=get_font('lg', 'bold')
        )
        title_label.pack(anchor="w", pady=(0, 20))

        # Recording Location Section
        location_frame = ttk.LabelFrame(
            self.content_frame,
            text=_("Recording Location"),
            padding="15",
            style='Dialog.TLabelframe'
        )
        location_frame.pack(fill="x", pady=(0, 20))

        ttk.Label(
            location_frame,
            text=_("Choose where to save audio recording files:"),
            style='Dialog.TLabel'
        ).pack(anchor="w", pady=(0, 10))

        # Radio buttons for location options
        ttk.Radiobutton(
            location_frame,
            text=_("Alongside application (recommended)"),
            variable=self.recording_location_var,
            value="alongside",
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)

        # Get the appropriate AppData path based on OS
        if platform.system() == "Windows":
            appdata_text = _("In AppData folder")
        elif platform.system() == "Darwin":  # macOS
            appdata_text = _("In Application Support folder")
        else:  # Linux
            appdata_text = _("In home config folder")

        ttk.Radiobutton(
            location_frame,
            text=appdata_text,
            variable=self.recording_location_var,
            value="appdata",
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)

        ttk.Radiobutton(
            location_frame,
            text=_("Custom folder:"),
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
            text=_("Browse..."),
            command=self.browse_custom_folder,
            state="disabled" if self.recording_location_var.get() != "custom" else "normal",
            style='Dialog.TButton',
            cursor='hand2'
        )
        self.browse_button.pack(side=tk.RIGHT)

        # File Handling Section
        handling_frame = ttk.LabelFrame(
            self.content_frame,
            text=_("File Handling"),
            padding="15",
            style='Dialog.TLabelframe'
        )
        handling_frame.pack(fill="x", pady=(0, 20))

        ttk.Label(
            handling_frame,
            text=_("Choose how to handle recording files:"),
            style='Dialog.TLabel'
        ).pack(anchor="w", pady=(0, 10))

        ttk.Radiobutton(
            handling_frame,
            text=_("Overwrite the same file each time (saves disk space)"),
            variable=self.file_handling_var,
            value="overwrite",
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)

        ttk.Radiobutton(
            handling_frame,
            text=_("Save each recording with date/time in filename"),
            variable=self.file_handling_var,
            value="timestamp",
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)

        # Warning for timestamp option
        warning_frame = ttk.Frame(handling_frame)
        warning_frame.pack(fill="x", pady=(5, 0), padx=(20, 0))

        ttk.Label(
            warning_frame,
            text=_("Warning: This can consume significant disk space over time"),
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
            text=_("Display Settings"),
            font=get_font('lg', 'bold')
        )
        title_label.pack(anchor="w", pady=(0, 20))

        # HiDPI Scaling Section
        hidpi_frame = ttk.LabelFrame(
            self.content_frame,
            text=_("HiDPI Scaling"),
            padding="15",
            style='Dialog.TLabelframe'
        )
        hidpi_frame.pack(fill="x", pady=(0, 20))

        ttk.Label(
            hidpi_frame,
            text=_("Choose how HiDPI (high resolution) scaling is applied:"),
            style='Dialog.TLabel'
        ).pack(anchor="w", pady=(0, 10))

        # Radio buttons for HiDPI options
        ttk.Radiobutton(
            hidpi_frame,
            text=_("Auto-detect (recommended)"),
            variable=self.hidpi_mode_var,
            value="auto",
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)

        auto_description = ttk.Label(
            hidpi_frame,
            text=_("Automatically detect and apply appropriate scaling based on your display"),
            font=get_font('xxs'),
            foreground="#888888"
        )
        auto_description.pack(anchor="w", padx=(20, 0), pady=(0, 8))

        ttk.Radiobutton(
            hidpi_frame,
            text=_("Force enabled"),
            variable=self.hidpi_mode_var,
            value="enabled",
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)

        enabled_description = ttk.Label(
            hidpi_frame,
            text=_("Always apply HiDPI scaling (use if auto-detection doesn't work correctly)"),
            font=get_font('xxs'),
            foreground="#888888"
        )
        enabled_description.pack(anchor="w", padx=(20, 0), pady=(0, 8))

        ttk.Radiobutton(
            hidpi_frame,
            text=_("Disabled"),
            variable=self.hidpi_mode_var,
            value="disabled",
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)

        disabled_description = ttk.Label(
            hidpi_frame,
            text=_("Never apply HiDPI scaling (use standard scaling)"),
            font=get_font('xxs'),
            foreground="#888888"
        )
        disabled_description.pack(anchor="w", padx=(20, 0), pady=(0, 8))

        # Note about restart requirement
        note_frame = ttk.Frame(hidpi_frame)
        note_frame.pack(fill="x", pady=(10, 0))

        ttk.Label(
            note_frame,
            text=_("Note: Changes to HiDPI scaling require a restart to take effect."),
            font=get_font('xs'),
            foreground="#CC6600"
        ).pack(anchor="w")

    def show_language_settings(self):
        """Show the language settings panel."""
        # Main title
        title_label = ttk.Label(
            self.content_frame,
            text=_("Language Settings"),
            font=get_font('lg', 'bold')
        )
        title_label.pack(anchor="w", pady=(0, 20))

        # Application Language Section
        language_frame = ttk.LabelFrame(
            self.content_frame,
            text=_("Application Language"),
            padding="15",
            style='Dialog.TLabelframe'
        )
        language_frame.pack(fill="x", pady=(0, 20))

        ttk.Label(
            language_frame,
            text=_("Choose how the application language is determined:"),
            style='Dialog.TLabel'
        ).pack(anchor="w", pady=(0, 10))

        # Radio buttons for language mode
        ttk.Radiobutton(
            language_frame,
            text=_("Auto-detect from system"),
            variable=self.language_mode_var,
            value="auto",
            command=self._on_language_mode_change,
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)

        auto_description = ttk.Label(
            language_frame,
            text=_("Automatically detect language from your operating system settings"),
            font=get_font('xxs'),
            foreground="#888888"
        )
        auto_description.pack(anchor="w", padx=(20, 0), pady=(0, 8))

        # Show detected language when auto is selected
        self.detected_lang_frame = ttk.Frame(language_frame)
        self.detected_lang_frame.pack(fill="x", padx=(20, 0), pady=(0, 8))

        detected_label = ttk.Label(
            self.detected_lang_frame,
            text=_("Detected:"),
            font=get_font('xxs'),
            foreground="#22d3ee"
        )
        detected_label.pack(side=tk.LEFT)

        self.detected_lang_value = ttk.Label(
            self.detected_lang_frame,
            text=get_detected_locale_display(),
            font=get_font('xxs'),
            foreground="#22d3ee"
        )
        self.detected_lang_value.pack(side=tk.LEFT, padx=(5, 0))

        ttk.Radiobutton(
            language_frame,
            text=_("Manual selection"),
            variable=self.language_mode_var,
            value="manual",
            command=self._on_language_mode_change,
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)

        # Manual language selection frame
        self.manual_lang_frame = ttk.Frame(language_frame)
        self.manual_lang_frame.pack(fill="x", padx=(20, 0), pady=(5, 0))

        ttk.Label(
            self.manual_lang_frame,
            text=_("Select Language:"),
            style='Dialog.TLabel'
        ).pack(anchor="w", pady=(0, 5))

        # Get available languages from compiled translations
        available = get_available_languages()

        # Language dropdown
        self.language_combo = ttk.Combobox(
            self.manual_lang_frame,
            values=[f"{name} ({code})" for code, name in available.items()],
            state="readonly",
            font=get_font('sm')
        )
        self.language_combo.pack(fill="x", pady=(0, 5))

        # Set current language value
        current_lang = self.language_var.get()
        if current_lang in available:
            self.language_combo.set(f"{available[current_lang]} ({current_lang})")
        elif current_lang in SUPPORTED_LANGUAGES:
            self.language_combo.set(f"{SUPPORTED_LANGUAGES[current_lang]} ({current_lang})")
        else:
            self.language_combo.set(f"English (en)")

        # Bind language change to update preview
        self.language_combo.bind("<<ComboboxSelected>>", self._on_manual_language_change)

        # Note about immediate update
        note_frame = ttk.Frame(language_frame)
        note_frame.pack(fill="x", pady=(10, 0))

        ttk.Label(
            note_frame,
            text=_("Note: Changing the language will update the interface immediately."),
            font=get_font('xs'),
            foreground="#CC6600"
        ).pack(anchor="w")

        # Update visibility based on current mode
        self._on_language_mode_change()

    def _on_language_mode_change(self):
        """Handle changes to the language mode selection."""
        is_auto = self.language_mode_var.get() == "auto"

        # Show/hide detected language info
        if is_auto:
            self.detected_lang_frame.pack(fill="x", padx=(20, 0), pady=(0, 8))
            self.manual_lang_frame.pack_forget()
        else:
            self.detected_lang_frame.pack_forget()
            self.manual_lang_frame.pack(fill="x", padx=(20, 0), pady=(5, 0))

    def _on_manual_language_change(self, event=None):
        """Handle manual language selection change."""
        selected = self.language_combo.get()
        # Extract language code from "Display Name (code)" format
        if "(" in selected and ")" in selected:
            lang_code = selected.split("(")[-1].strip(")")
            self.language_var.set(lang_code)

    def show_ai_models_settings(self):
        """Show the AI models settings panel."""
        # Main title
        title_label = ttk.Label(
            self.content_frame,
            text=_("AI Model Settings"),
            font=get_font('lg', 'bold')
        )
        title_label.pack(anchor="w", pady=(0, 20))

        # Language Selection Frame
        language_frame = ttk.LabelFrame(
            self.content_frame,
            text=_("Whisper Language Settings"),
            padding="15",
            style='Dialog.TLabelframe'
        )
        language_frame.pack(fill="x", pady=(0, 15))

        # Language selection label
        ttk.Label(
            language_frame,
            text=_("Select Language:"),
            style='Dialog.TLabel'
        ).pack(anchor="w", pady=(0, 5))

        # Prepare sorted language list with Auto Detect first
        language_values = [(code, name) for code, name in self.languages.items()]
        auto_option = next(item for item in language_values if item[0] == "auto")
        language_values.remove(auto_option)
        language_values.sort(key=lambda x: x[1])
        language_values.insert(0, auto_option)

        # Language combobox
        self.language_combo = ttk.Combobox(
            language_frame,
            values=[f"{name} ({code})" for code, name in language_values],
            state="readonly",
            font=get_font('sm')
        )
        self.language_combo.pack(fill="x", pady=(0, 5))

        # Set current language value
        current_lang = self.whisper_language_var.get()
        current_lang_name = self.languages.get(current_lang, "Auto Detect")
        self.language_combo.set(f"{current_lang_name} ({current_lang})")

        # Model Settings Frame
        models_frame = ttk.LabelFrame(
            self.content_frame,
            text=_("AI Model Settings"),
            padding="15",
            style='Dialog.TLabelframe'
        )
        models_frame.pack(fill="x", pady=(0, 15))

        # --- Transcription Model Section ---
        transcription_section = ttk.Frame(models_frame)
        transcription_section.pack(fill="x", pady=(0, 15))

        ttk.Label(
            transcription_section,
            text=_("Transcription Model:"),
            style='Dialog.TLabel'
        ).pack(anchor="w")

        # Transcription model dropdown
        dropdown_frame = ttk.Frame(transcription_section)
        dropdown_frame.pack(fill="x", pady=(5, 0))

        self.transcription_model_combo = ttk.Combobox(
            dropdown_frame,
            textvariable=self.transcription_model_var,
            values=list(self.transcription_models.keys()),
            state="readonly",
            font=get_font('sm')
        )
        self.transcription_model_combo.pack(fill="x")

        # Custom transcription model input frame
        self.custom_trans_frame = ttk.Frame(transcription_section)
        ttk.Label(
            self.custom_trans_frame,
            text=_("Enter custom transcription model name:"),
            style='Dialog.TLabel'
        ).pack(anchor="w")
        self.custom_trans_entry = ttk.Entry(
            self.custom_trans_frame,
            textvariable=self.custom_transcription_model_var,
            font=get_font('sm')
        )
        self.custom_trans_entry.pack(fill="x", pady=(2, 0))

        # Show custom frame if "other" selected
        if self.transcription_model_var.get() == "other":
            self.custom_trans_frame.pack(fill="x", pady=(5, 0))

        # Bind transcription model change
        self.transcription_model_var.trace_add("write", self._on_transcription_model_change)

        # Model type info
        ttk.Label(
            transcription_section,
            text="Note: GPT models provide higher quality transcription with broad language support.\nWhisper is the traditional speech recognition model.",
            font=get_font('xxs'),
            foreground=THEME_TEXT_MUTED
        ).pack(anchor="w", pady=(8, 0))

        # --- LLM Model Section ---
        ttk.Label(
            models_frame,
            text=_("OpenAI Copyediting Model:"),
            style='Dialog.TLabel'
        ).pack(anchor="w", pady=(5, 0))

        llm_dropdown_frame = ttk.Frame(models_frame)
        llm_dropdown_frame.pack(fill="x", pady=(5, 0))

        self.llm_model_combo = ttk.Combobox(
            llm_dropdown_frame,
            textvariable=self.llm_model_var,
            values=self.llm_models,
            state="readonly",
            font=get_font('sm')
        )
        self.llm_model_combo.pack(fill="x")

        # Custom LLM model input frame
        self.custom_llm_frame = ttk.Frame(models_frame)
        ttk.Label(
            self.custom_llm_frame,
            text=_("Enter custom copyediting model name:"),
            style='Dialog.TLabel'
        ).pack(anchor="w")
        self.custom_llm_entry = ttk.Entry(
            self.custom_llm_frame,
            textvariable=self.custom_llm_model_var,
            font=get_font('sm')
        )
        self.custom_llm_entry.pack(fill="x", pady=(2, 0))

        # Show custom frame if "other" selected
        if self.llm_model_var.get() == "other":
            self.custom_llm_frame.pack(fill="x", pady=(5, 0))

        # Bind LLM model change
        self.llm_model_var.trace_add("write", self._on_llm_model_change)

        # Model info
        ttk.Label(
            models_frame,
            text="e.g., gpt-5, gpt-4o, gpt-4o-mini, o1-mini, o1-preview",
            font=get_font('xxs'),
            foreground=THEME_TEXT_MUTED
        ).pack(anchor="w", pady=(5, 0))

        # Link to OpenAI Pricing
        link = tk.Label(
            self.content_frame,
            text=_("View Available OpenAI Models and Pricing"),
            fg=THEME_ACCENT,
            cursor="hand2",
            font=get_font('copy_link', 'underline')
        )
        link.pack(anchor="w", pady=(10, 0))
        link.bind("<Button-1>", lambda e: open_url("https://openai.com/api/pricing/"))
        link.bind("<Enter>", lambda e: link.config(fg=THEME_ACCENT_HOVER))
        link.bind("<Leave>", lambda e: link.config(fg=THEME_ACCENT))

    def _on_transcription_model_change(self, *args):
        """Handle transcription model dropdown change."""
        if hasattr(self, 'custom_trans_frame'):
            if self.transcription_model_var.get() == "other":
                self.custom_trans_frame.pack(fill="x", pady=(5, 0))
                if hasattr(self, 'custom_trans_entry'):
                    self.custom_trans_entry.focus()
            else:
                self.custom_trans_frame.pack_forget()

    def _on_llm_model_change(self, *args):
        """Handle LLM model dropdown change."""
        if hasattr(self, 'custom_llm_frame'):
            if self.llm_model_var.get() == "other":
                self.custom_llm_frame.pack(fill="x", pady=(5, 0))
                if hasattr(self, 'custom_llm_entry'):
                    self.custom_llm_entry.focus()
            else:
                self.custom_llm_frame.pack_forget()

    def on_custom_location_selected(self):
        """Handle when custom location radio button is selected."""
        # If no custom path is set and custom is selected, open browse dialog
        if not self.custom_location_var.get().strip():
            self.browse_custom_folder()
            
    def browse_custom_folder(self):
        """Open a folder selection dialog."""
        folder_path = filedialog.askdirectory(
            title=_("Select Recording Folder"),
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
                messagebox.showerror(_("Error"), _("Please select a custom folder path"))
                return

            if not os.path.exists(custom_path):
                create_folder = messagebox.askyesno(
                    _("Folder Does Not Exist"),
                    _("The folder '{path}' does not exist. Would you like to create it?").format(path=custom_path)
                )
                if create_folder:
                    try:
                        os.makedirs(custom_path, exist_ok=True)
                    except Exception as e:
                        messagebox.showerror(_("Error"), _("Could not create folder: {error}").format(error=e))
                        return
                else:
                    return

        # Check if HiDPI setting changed (requires restart)
        hidpi_changed = self.hidpi_mode_var.get() != self.original_hidpi_mode

        # Validate AI Models settings
        # Get selected whisper language code from combo box (if AI Models category was visited)
        if hasattr(self, 'language_combo') and self.current_category == "AI Models":
            selected_language = self.language_combo.get()
            whisper_language_code = selected_language.split('(')[-1].strip(')')
        else:
            whisper_language_code = self.whisper_language_var.get()

        # Get the selected transcription model
        if self.transcription_model_var.get() == "other":
            transcription_model = self.custom_transcription_model_var.get().strip()
            if not transcription_model:
                messagebox.showerror(_("Error"), _("Custom transcription model name cannot be empty."))
                return
            model_type = "unknown"
        else:
            transcription_model = self.transcription_model_var.get()
            model_type = self.transcription_models.get(transcription_model, "unknown")

        # Get the selected LLM model
        if self.llm_model_var.get() == "other":
            llm_model = self.custom_llm_model_var.get().strip()
            if not llm_model:
                messagebox.showerror(_("Error"), _("Custom copyediting model name cannot be empty."))
                return
        else:
            llm_model = self.llm_model_var.get()

        # Update configuration values
        try:
            self.config.recording_location = self.recording_location_var.get()
            self.config.custom_recording_path = self.custom_location_var.get()
            self.config.file_handling = self.file_handling_var.get()
            self.config.hidpi_mode = self.hidpi_mode_var.get()

            # Save language settings
            self.config.language_mode = self.language_mode_var.get()
            self.config.language = self.language_var.get()

            # Save AI Models settings
            self.config.whisper_language = whisper_language_code
            self.config.transcription_model = transcription_model
            self.config.transcription_model_type = model_type
            self.config.ai_model = llm_model

            # Save to file
            self.config.save_settings()

            # Update parent's recording directory
            self.parent.update_recording_directory()

            # Update parent's AI model instance variables
            self.parent.whisper_language = whisper_language_code
            self.parent.transcription_model = transcription_model
            self.parent.transcription_model_type = model_type
            self.parent.ai_model = llm_model

            # Update the model label in the UI
            self.parent.update_model_label()

            # Apply language change immediately
            new_lang_mode = self.language_mode_var.get()
            new_lang = self.language_var.get()
            # Resolve language based on mode
            if new_lang_mode == "auto":
                resolved_lang = detect_os_locale()
            else:
                resolved_lang = new_lang
            set_language(resolved_lang)

            # If HiDPI changed, prompt for restart
            if hidpi_changed:
                restart_now = messagebox.askyesno(
                    _("Restart Required"),
                    _("The HiDPI scaling setting has been changed. This requires a restart to take effect.") + "\n\n" +
                    _("Would you like to restart the application now?"),
                    icon='question'
                )
                if restart_now:
                    self._close_dialog()
                    self.parent.restart_application()
                    return
                else:
                    messagebox.showinfo(
                        _("Settings Saved"),
                        _("Configuration settings saved successfully!") + "\n\n" +
                        _("The HiDPI scaling change will take effect after you restart the application.")
                    )
                    self._close_dialog()
                    return

            messagebox.showinfo(_("Success"), _("Configuration settings saved and applied successfully!"))
            self._close_dialog()

        except Exception as e:
            messagebox.showerror(_("Error"), _("Could not save settings: {error}").format(error=e)) 

    def _close_dialog(self):
        try:
            self.dialog.destroy()
        finally:
            if hasattr(self.parent, 'hotkey_manager'):
                self.parent.hotkey_manager.resume()