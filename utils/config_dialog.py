import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
from pathlib import Path
import os
import platform
import time
from utils.config_manager import get_config, TRANSCRIPTION_MODELS, AI_MODELS
from utils.theme import get_font, get_font_size, get_font_family, get_window_size, get_button_height, get_spacing, theme_colors
from utils.platform import open_url
from utils.i18n import (
    _, _n, set_language, get_current_language, detect_os_locale,
    get_detected_locale_display, get_available_languages, SUPPORTED_LANGUAGES
)
from utils.dialog_utils import position_dialog, bind_dialog_keys, focus_first
from utils.app_logging import get_logger

logger = get_logger(__name__)

# Theme colors for dark mode (used in AI Models section)
THEME_TEXT_MUTED = "#909090"
THEME_ACCENT = "#22d3ee"
THEME_ACCENT_HOVER = "#67e8f9"

class ScrollableSettingsFrame(ttk.Frame):
    """A settings panel that scrolls when its content is taller than the dialog.

    Widgets go into ``.body``. The scrollbar only appears when it is actually
    needed, so a short panel looks exactly like a plain frame.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self._canvas = tk.Canvas(self, highlightthickness=0, bd=0, takefocus=0)
        self._scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._on_scroll)

        self.body = ttk.Frame(self._canvas)
        self._window = self._canvas.create_window((0, 0), window=self.body, anchor="nw")

        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._scrollbar_visible = False

        # Match the canvas background to the theme so it does not show up as a
        # white rectangle behind the settings in dark mode.
        try:
            self._canvas.configure(bg=ttk.Style().lookup('TFrame', 'background') or '#1c1c1c')
        except Exception:
            pass

        self.body.bind("<Configure>", self._on_body_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        # Bind the wheel while the pointer is over the panel only, so it does
        # not steal scrolling from the rest of the dialog.
        self._canvas.bind("<Enter>", self._bind_wheel)
        self._canvas.bind("<Leave>", self._unbind_wheel)
        # Switching settings category destroys this panel, and <Leave> does not
        # necessarily fire first. An application-wide wheel binding left
        # pointing at a destroyed canvas would raise on every scroll anywhere
        # in the app, so it is torn down explicitly.
        self.bind("<Destroy>", self._on_destroy)

    def _on_scroll(self, first, last):
        self._scrollbar.set(first, last)
        needed = not (float(first) <= 0.0 and float(last) >= 1.0)
        if needed and not self._scrollbar_visible:
            self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self._scrollbar_visible = True
        elif not needed and self._scrollbar_visible:
            self._scrollbar.pack_forget()
            self._scrollbar_visible = False

    def _on_body_configure(self, _event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        # Keep the inner frame as wide as the canvas so text wraps sensibly.
        self._canvas.itemconfigure(self._window, width=event.width)

    def _bind_wheel(self, _event=None):
        self._canvas.bind_all("<MouseWheel>", self._on_wheel)
        # X11 reports the wheel as buttons 4 and 5 rather than <MouseWheel>.
        self._canvas.bind_all("<Button-4>", self._on_wheel)
        self._canvas.bind_all("<Button-5>", self._on_wheel)

    def _unbind_wheel(self, _event=None):
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            try:
                self._canvas.unbind_all(sequence)
            except Exception:
                pass

    def _on_destroy(self, event=None):
        # <Destroy> also fires for child widgets; only act on our own.
        if event is not None and event.widget is not self:
            return
        self._unbind_wheel()

    def _on_wheel(self, event):
        if not self._scrollbar_visible:
            return
        if getattr(event, 'num', None) == 4:
            delta = -1
        elif getattr(event, 'num', None) == 5:
            delta = 1
        else:
            # Windows reports multiples of 120; macOS reports small integers.
            delta = -1 if event.delta > 0 else 1
        try:
            self._canvas.yview_scroll(delta, "units")
        except tk.TclError:
            # The panel went away without <Leave> or <Destroy> reaching us.
            self._unbind_wheel()


class ConfigDialog:
    def __init__(self, parent):
        _t0 = time.perf_counter()
        logger.info("[CONFIG DIALOG] __init__ started")

        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.withdraw()  # Hide window until UI is built
        self.dialog.title(_("Configuration Settings"))
        logger.info("[CONFIG DIALOG] Toplevel created: %sms", (time.perf_counter() - _t0)*1000)

        # Get window dimensions from theme
        window_width, window_height = get_window_size('config_dialog')
        position_dialog(self.dialog, window_width, window_height, parent)

        self.dialog.transient(parent)

        # Handle window close (X button) to ensure hotkeys are resumed
        self.dialog.protocol("WM_DELETE_WINDOW", self._close_dialog)
        logger.info("[CONFIG DIALOG] Window configured: %sms", (time.perf_counter() - _t0)*1000)

        # Variables for settings
        self.recording_location_var = tk.StringVar()
        self.custom_location_var = tk.StringVar()
        self.file_handling_var = tk.StringVar()
        self.paste_method_var = tk.StringVar()
        self.hidpi_mode_var = tk.StringVar()
        self.close_to_tray_var = tk.BooleanVar()

        # Language settings variables
        self.language_mode_var = tk.StringVar()
        self.language_var = tk.StringVar()

        # AI Models settings variables
        self.whisper_language_var = tk.StringVar()
        self.transcription_model_var = tk.StringVar()
        self.custom_transcription_model_var = tk.StringVar()
        self.llm_model_var = tk.StringVar()
        self.custom_llm_model_var = tk.StringVar()

        # Advanced settings variables
        self.recording_mode_var = tk.StringVar()
        self.max_minutes_var = tk.StringVar()
        self.min_seconds_var = tk.StringVar()
        self.discard_silent_var = tk.BooleanVar()
        self.retention_days_var = tk.StringVar()
        self.persist_history_var = tk.BooleanVar()
        self.history_limit_var = tk.StringVar()
        self.show_level_meter_var = tk.BooleanVar()
        self.play_sounds_var = tk.BooleanVar()
        self.restore_clipboard_var = tk.BooleanVar()

        # Track original HiDPI setting for restart prompt
        self.original_hidpi_mode = None
        logger.info("[CONFIG DIALOG] Variables initialized: %sms", (time.perf_counter() - _t0)*1000)

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
        # Shared with the status-line pickers; "other" is the dialog's own
        # affordance for typing a custom model name.
        self.transcription_models = dict(TRANSCRIPTION_MODELS)
        self.transcription_models["other"] = "unknown"

        # Define LLM models for copy-editing
        self.llm_models = list(AI_MODELS) + ["other"]
        logger.info("[CONFIG DIALOG] Static data defined: %sms", (time.perf_counter() - _t0)*1000)

        # Load current settings
        self.load_current_settings()
        logger.info("[CONFIG DIALOG] Settings loaded: %sms", (time.perf_counter() - _t0)*1000)
        
        # Current selected category
        self.current_category = "Recording"

        self.create_dialog()
        logger.info("[CONFIG DIALOG] create_dialog() done: %sms", (time.perf_counter() - _t0)*1000)

        # Baseline for the unsaved-changes check, taken once the settings are
        # in their variables and before the user can touch anything.
        self._baseline = self._settings_snapshot()
        bind_dialog_keys(self.dialog,
                         on_cancel=self._close_dialog,
                         on_accept=self.save_settings)

        # Force Tkinter to process all widget geometry before showing
        # This prevents the black flash by ensuring widgets are rendered
        self.dialog.update_idletasks()
        logger.info("[CONFIG DIALOG] update_idletasks() done: %sms", (time.perf_counter() - _t0)*1000)

        # Show window now that UI is fully built (prevents black flash)
        self.dialog.deiconify()
        logger.info("[CONFIG DIALOG] deiconify() done: %sms", (time.perf_counter() - _t0)*1000)

        # Make dialog modal after UI is built (faster perceived load)
        self.dialog.wait_visibility()  # Wait for dialog to be visible before grabbing (Linux fix)
        logger.info("[CONFIG DIALOG] wait_visibility() done: %sms", (time.perf_counter() - _t0)*1000)
        self.dialog.grab_set()
        logger.info("[CONFIG DIALOG] grab_set() done: %sms", (time.perf_counter() - _t0)*1000)

        # Defer hotkey pause to after dialog is fully painted
        # Using after(50) + update() ensures widgets are rendered before the blocking pause
        if hasattr(self.parent, 'hotkey_manager'):
            def pause_hotkeys():
                self.dialog.update()  # Force full repaint before blocking pause
                self.parent.hotkey_manager.pause()
            self.dialog.after(50, pause_hotkeys)
        logger.info("[CONFIG DIALOG] __init__ complete: %sms", (time.perf_counter() - _t0)*1000)

    def load_current_settings(self):
        """Load current configuration settings from settings.json."""
        self.config = get_config()

        # Recording location (default: alongside)
        self.recording_location_var.set(self.config.recording_location)

        # Custom location path
        self.custom_location_var.set(self.config.custom_recording_path)

        # File handling (default: overwrite)
        self.file_handling_var.set(self.config.file_handling)

        # Paste method (default: auto)
        self.paste_method_var.set(self.config.paste_method)

        # HiDPI mode (default: auto)
        self.hidpi_mode_var.set(self.config.hidpi_mode)
        self.original_hidpi_mode = self.config.hidpi_mode

        # Close to tray (default: False - close app on X)
        self.close_to_tray_var.set(self.config.close_to_tray)

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

        # Advanced settings
        self.recording_mode_var.set(self.config.recording_mode)
        self.max_minutes_var.set(str(self.config.max_recording_minutes))
        self.min_seconds_var.set(f"{self.config.min_recording_seconds:g}")
        self.discard_silent_var.set(self.config.discard_silent_recordings)
        self.retention_days_var.set(str(self.config.recording_retention_days))
        self.persist_history_var.set(self.config.persist_history)
        self.history_limit_var.set(str(self.config.history_limit))
        self.show_level_meter_var.set(self.config.show_level_meter)
        self.play_sounds_var.set(self.config.play_sounds)
        self.restore_clipboard_var.set(self.config.restore_clipboard)
        
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
        logger.info("[CONFIG DIALOG]   - styles configured: %sms", (time.perf_counter() - _t0)*1000)

        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Create top frame for navigation and content
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.BOTH, expand=True)
        logger.info("[CONFIG DIALOG]   - frames created: %sms", (time.perf_counter() - _t0)*1000)

        # Create bottom frame for buttons
        self.create_bottom_buttons(main_frame)
        logger.info("[CONFIG DIALOG]   - bottom buttons created: %sms", (time.perf_counter() - _t0)*1000)

        # Create left navigation and right content areas in the top frame
        self.create_navigation_panel(top_frame)
        logger.info("[CONFIG DIALOG]   - navigation panel created: %sms", (time.perf_counter() - _t0)*1000)
        self.create_content_panel(top_frame)
        logger.info("[CONFIG DIALOG]   - content panel created: %sms", (time.perf_counter() - _t0)*1000)

        # Initially show recording settings
        self.show_recording_settings()
        logger.info("[CONFIG DIALOG]   - recording settings shown: %sms", (time.perf_counter() - _t0)*1000)
        
    # Category key -> (translated label, panel builder attribute name).
    # Keeping this in one table means a new settings tab is one entry, not a
    # hand-copied button plus a branch in switch_category.
    #
    # Grouped by what a setting does, not by how advanced it is. "Advanced"
    # had become a nine-item drawer holding the recording mode - the most
    # behaviour-changing choice in the app - while "Display" and "Behavior"
    # held one setting each. It no longer exists; everything in it had a
    # natural home.
    CATEGORIES = (
        ("Recording", lambda: _("Recording"), "show_recording_settings"),
        ("Output", lambda: _("Output & Clipboard"), "show_output_settings"),
        ("AI Models", lambda: _("AI Models"), "show_ai_models_settings"),
        ("Appearance", lambda: _("Appearance"), "show_display_settings"),
        ("History", lambda: _("History & Storage"), "show_history_settings"),
        ("System", lambda: _("System"), "show_behavior_settings"),
    )

    def create_navigation_panel(self, parent):
        """Create the left navigation panel."""
        self.nav_frame = ttk.LabelFrame(parent, text=_("Settings Categories"), padding="10", style='Dialog.TLabelframe')
        self.nav_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Navigation buttons
        self.nav_buttons = {}

        for key, label, _builder in self.CATEGORIES:
            button = ttk.Button(
                self.nav_frame,
                text=label(),
                command=lambda k=key: self.switch_category(k),
                width=15,
                style='Nav.TButton',
                cursor='hand2'
            )
            button.pack(fill=tk.X, pady=2)
            self.nav_buttons[key] = button

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
            fg_color=theme_colors().BUTTON_SECONDARY,
            hover_color=theme_colors().BUTTON_SECONDARY_HOVER,
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
            fg_color=theme_colors().BUTTON_PRIMARY,
            hover_color=theme_colors().BUTTON_PRIMARY_HOVER,
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
        for key, _label, builder in self.CATEGORIES:
            if key == category:
                getattr(self, builder)()
                break
            
    def update_navigation_highlight(self):
        """Update the visual highlight for the current navigation selection."""
        for category, button in self.nav_buttons.items():
            if category == self.current_category:
                # Selected: bold text with accent background
                button.configure(style='NavSelected.TButton')
            else:
                # Unselected: normal style
                button.configure(style='Nav.TButton')
                
    def _panel(self, title):
        """Start a settings panel: a title plus a scrollable body to fill.

        Panels are scrollable as a matter of course now that settings are
        grouped by what they do rather than by how advanced they are - a
        category can hold more than fits at base scaling.
        """
        ttk.Label(
            self.content_frame,
            text=title,
            font=get_font('lg', 'bold')
        ).pack(anchor="w", pady=(0, 16))
        scroll = ScrollableSettingsFrame(self.content_frame)
        scroll.pack(fill=tk.BOTH, expand=True)
        return scroll.body

    def show_recording_settings(self):
        """Everything about capturing audio: how to trigger it, and its limits."""
        body = self._panel(_("Recording"))
        self._section_recording_mode(body)
        self._section_recording_limits(body)
        self._section_recording_feedback(body)

    def _section_recording_location(self, parent):
        """Where recording files are written."""
        # Recording Location Section
        location_frame = ttk.LabelFrame(
            parent,
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

    def _section_file_handling(self, parent):
        """Overwrite one file, or keep every take."""
        # File Handling Section
        handling_frame = ttk.LabelFrame(
            parent,
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

    def show_output_settings(self):
        """What happens to the transcription once it exists."""
        body = self._panel(_("Output & Clipboard"))
        self._section_clipboard(body)
        self._section_paste_method(body)

    # Auto-paste methods, described by what they do rather than by the library
    # that implements them. The technical name is kept in brackets because it
    # is what users quote in bug reports.
    #   (value, label, windows_only)
    PASTE_METHODS = (
        ("auto", lambda: _("Automatic (recommended)"), False),
        ("sendinput", lambda: _("Most reliable on Windows (SendInput)"), True),
        ("win32api", lambda: _("For older Windows apps (win32api)"), True),
        ("pynput", lambda: _("For slow apps, with delays (pynput)"), False),
        ("pynput_legacy", lambda: _("Fastest, no delays (pynput legacy)"), False),
        ("pyautogui", lambda: _("If nothing else works (pyautogui)"), False),
    )

    def _section_paste_method(self, parent):
        """How the paste keystroke is simulated."""
        paste_frame = self._advanced_section(parent, _("Auto-Paste Method"))

        # The troubleshooting line is why anyone opens this section, so it
        # leads rather than trailing the list.
        self._hint_label(
            paste_frame,
            _("Only change this if auto-paste misbehaves - for example if it types "
              "'v' instead of pasting."))

        ttk.Label(
            paste_frame,
            text=_("How the paste keystroke is sent:"),
            style='Dialog.TLabel'
        ).pack(anchor="w", pady=(10, 6))

        is_windows = platform.system() == "Windows"
        for value, label, windows_only in self.PASTE_METHODS:
            if windows_only and not is_windows:
                continue
            ttk.Radiobutton(
                paste_frame,
                text=label(),
                variable=self.paste_method_var,
                value=value,
                style='Dialog.TRadiobutton'
            ).pack(anchor="w", pady=2)

    def show_display_settings(self):
        """How the app looks: theme, scaling and interface language."""
        body = self._panel(_("Appearance"))
        self._section_theme(body)
        self._section_hidpi(body)
        self._section_app_language(body)

    def _section_hidpi(self, parent):
        """Scaling for high-resolution displays."""
        # HiDPI Scaling Section
        hidpi_frame = ttk.LabelFrame(
            parent,
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

    def show_behavior_settings(self):
        """How the app behaves as a running program."""
        body = self._panel(_("System"))
        self._section_close_behavior(body)
        self._section_background(body)

    def _section_close_behavior(self, parent):
        """What the X button does."""
        # Window Close Behavior Section
        close_frame = ttk.LabelFrame(
            parent,
            text=_("Window Close Behavior"),
            padding="15",
            style='Dialog.TLabelframe'
        )
        close_frame.pack(fill="x", pady=(0, 20))

        ttk.Label(
            close_frame,
            text=_("Choose what happens when you click the X button:"),
            style='Dialog.TLabel'
        ).pack(anchor="w", pady=(0, 10))

        # Radio buttons for close behavior
        ttk.Radiobutton(
            close_frame,
            text=_("Close the application"),
            variable=self.close_to_tray_var,
            value=False,
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)

        close_description = ttk.Label(
            close_frame,
            text=_("Clicking X will close Quick Whisper completely"),
            font=get_font('xxs'),
            foreground="#888888"
        )
        close_description.pack(anchor="w", padx=(20, 0), pady=(0, 8))

        ttk.Radiobutton(
            close_frame,
            text=_("Minimize to system tray"),
            variable=self.close_to_tray_var,
            value=True,
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)

        tray_description = ttk.Label(
            close_frame,
            text=_("Clicking X will hide the window to the system tray (use tray icon to restore)"),
            font=get_font('xxs'),
            foreground="#888888"
        )
        tray_description.pack(anchor="w", padx=(20, 0), pady=(0, 8))

    # ------------------------------------------------------------------
    # Advanced settings
    # ------------------------------------------------------------------

    def _advanced_section(self, parent, title):
        """A titled group inside the Advanced panel."""
        frame = ttk.LabelFrame(parent, text=title, padding="15", style='Dialog.TLabelframe')
        frame.pack(fill="x", pady=(0, 14))
        return frame

    @staticmethod
    def _hint_label(parent, text, indent=0):
        """Explanatory small print that wraps to whatever width it is given.

        A fixed wraplength cannot work here: the settings dialog is 700px wide
        at base scaling and 1050px on HiDPI, so any constant is either clipped
        on one and wasteful on the other.
        """
        label = ttk.Label(
            parent, text=text, font=get_font('xxs'), foreground="#888888",
            justify="left", wraplength=360)
        # fill="x" makes the label exactly as wide as the space it has, so its
        # own width is the wrap width - no guessing at the parent's padding.
        label.pack(anchor="w", fill="x", padx=(indent, 0), pady=(0, 10))

        def _rewrap(event):
            width = event.width - 4
            if width > 80 and abs(width - int(label.cget('wraplength'))) > 8:
                label.configure(wraplength=width)

        label.bind("<Configure>", _rewrap, add="+")
        return label

    def _advanced_field(self, parent, label, variable, hint, width=8):
        """A short labelled entry with an explanatory line beneath it."""
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 2))
        ttk.Label(row, text=label, style='Dialog.TLabel').pack(side=tk.LEFT)
        entry = ttk.Entry(row, textvariable=variable, width=width, font=get_font('sm'))
        entry.pack(side=tk.LEFT, padx=(10, 0))
        self._hint_label(parent, hint)
        return entry

    def _advanced_check(self, parent, label, variable, hint, command=None):
        """A checkbox with an explanatory line beneath it.

        ``command`` is for settings that are also on a menu and apply the
        moment they change: passing the menu's own handler keeps the two in
        step rather than making them two sources of truth.
        """
        ttk.Checkbutton(
            parent, text=label, variable=variable, style='Switch.TCheckbutton',
            command=command
        ).pack(anchor="w", pady=(0, 2))
        self._hint_label(parent, hint, indent=6)

    def _section_theme(self, parent):
        """Light or dark.

        Shares the main window's BooleanVar, so the menu item and this
        checkbox are the same switch rather than two sources of truth.
        """
        frame = self._advanced_section(parent, _("Theme"))
        self._advanced_check(
            frame, _("Dark mode"), self.parent.dark_mode,
            _("Applies immediately. Also available from the Settings menu."),
            command=self.parent.toggle_dark_mode)

    def _section_background(self, parent):
        """Options that govern the app running in the background."""
        frame = self._advanced_section(parent, _("Background Behaviour"))
        self._advanced_check(
            frame, _("Keep global shortcuts working automatically"),
            self.parent.auto_hotkey_refresh,
            _("Re-registers the global shortcuts periodically. Windows can drop them "
              "after locking and unlocking the screen, and this puts them back "
              "without you noticing."),
            command=self.parent.save_auto_hotkey_refresh)
        self._advanced_check(
            frame, _("Check for updates on startup"),
            self.parent.version_manager.auto_update_check,
            _("Looks for a newer release of Quick Whisper when the app starts."),
            command=self.parent.version_manager.save_auto_update_setting)

    def _section_recording_mode(self, parent):
        """Toggle vs push-to-talk.

        This lived in "Advanced" - the single most behaviour-changing choice
        in the app, filed where settings go to die.
        """
        mode_frame = self._advanced_section(parent, _("Recording Shortcut Behaviour"))
        ttk.Label(
            mode_frame,
            text=_("Choose how the record shortcuts behave:"),
            style='Dialog.TLabel'
        ).pack(anchor="w", pady=(0, 10))

        # Radio labels cannot wrap, so they stay short and the line beneath
        # carries the detail.
        ttk.Radiobutton(
            mode_frame, text=_("Toggle"),
            variable=self.recording_mode_var, value="toggle",
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)
        self._hint_label(
            mode_frame,
            _("Press the shortcut once to start recording and again to stop. The "
              "current behaviour, and the better one for longer dictation where you "
              "do not want to hold keys down."),
            indent=20)

        ttk.Radiobutton(
            mode_frame, text=_("Push to talk"),
            variable=self.recording_mode_var, value="push_to_talk",
            style='Dialog.TRadiobutton'
        ).pack(anchor="w", pady=2)
        self._hint_label(
            mode_frame,
            _("Hold the shortcut down and release it to send. Best for short "
              "dictation. Recording stops as soon as you let go of any key in the "
              "shortcut. The buttons in this window always toggle, whichever mode "
              "is selected."),
            indent=20)

    def _section_recording_limits(self, parent):
        """How long a take may run, and when one is not worth sending."""
        limits_frame = self._advanced_section(parent, _("Recording Limits"))
        self._advanced_field(
            limits_frame, _("Maximum length (minutes):"), self.max_minutes_var,
            _("Recording stops automatically at this length so the audio stays within "
              "the upload size limit. Whatever was said is still transcribed. "
              "Use 0 for no limit."))
        self._advanced_field(
            limits_frame, _("Minimum length (seconds):"), self.min_seconds_var,
            _("Recordings shorter than this are discarded rather than sent for "
              "transcription, which stops an accidental tap of the shortcut costing "
              "an API call. Use 0 to keep every recording."))
        self._advanced_check(
            limits_frame, _("Discard silent recordings"), self.discard_silent_var,
            _("Skip uploading a recording when no speech was detected in it. Turn this "
              "off if quiet dictation is being discarded by mistake."))

    def _section_recording_feedback(self, parent):
        """What the app shows and plays while recording."""
        feedback_frame = self._advanced_section(parent, _("While Recording"))
        self._advanced_check(
            feedback_frame, _("Show the input level meter while recording"),
            self.show_level_meter_var,
            _("Displays a live microphone level and timer next to the status, so you "
              "can see that your voice is being picked up."))
        self._advanced_check(
            feedback_frame, _("Play sound effects"), self.play_sounds_var,
            _("Short sounds mark the start and end of a recording and confirm when a "
              "transcription is ready. Turn this off to work silently."))

    def _section_retention(self, parent):
        """Automatic clean-up of saved audio."""
        files_frame = self._advanced_section(parent, _("Stored Recordings"))
        self._advanced_field(
            files_frame, _("Delete recordings after (days):"), self.retention_days_var,
            _("Audio files older than this are deleted automatically. Only applies when "
              "recordings are saved with a date and time in the filename. "
              "Use 0 to keep them forever."))

    def _section_history(self, parent):
        """How much dictation history is kept, and for how long."""
        history_frame = self._advanced_section(parent, _("Transcription History"))
        self._advanced_check(
            history_frame, _("Remember history between sessions"), self.persist_history_var,
            _("Keep your transcriptions on disk so they are still there next time the "
              "app starts. Turn this off if you would rather nothing was written down."))
        self._advanced_field(
            history_frame, _("Entries to keep:"), self.history_limit_var,
            _("How many transcriptions are kept in the history before the oldest are "
              "dropped."))

    def _section_clipboard(self, parent):
        """What happens to the result once it is ready."""
        frame = self._advanced_section(parent, _("After Transcription"))
        self._advanced_check(
            frame, _("Auto-copy result"), self.parent.auto_copy,
            _("Put the finished text on the clipboard automatically. The same switch "
              "appears under the transcript in the main window."))
        self._advanced_check(
            frame, _("Auto-paste result"), self.parent.auto_paste,
            _("Paste the finished text straight into whichever app you were using."))
        self._advanced_check(
            frame, _("Restore the previous clipboard after auto-paste"),
            self.restore_clipboard_var,
            _("When auto-copy is switched off, the transcription is put on "
              "the clipboard only long enough to paste it, then whatever you had "
              "copied before is put back."))

    def show_history_settings(self):
        """Where dictation and its audio are kept."""
        body = self._panel(_("History & Storage"))
        self._section_history(body)
        self._section_recording_location(body)
        self._section_file_handling(body)
        self._section_retention(body)

    def _section_app_language(self, parent):
        """The language the interface is shown in."""
        # Application Language Section
        language_frame = ttk.LabelFrame(
            parent,
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

    def _section_speech_language(self, parent):
        """Which language the speech is in.

        This used to sit in a panel titled "Language" next to the interface
        language, where the two unrelated meanings were easy to confuse. It
        belongs with the transcription model that consumes it.
        """
        # AI Language Settings Section (for transcription)
        ai_language_frame = ttk.LabelFrame(
            parent,
            text=_("Speech Language"),
            padding="15",
            style='Dialog.TLabelframe'
        )
        ai_language_frame.pack(fill="x", pady=(0, 20))

        ttk.Label(
            ai_language_frame,
            text=_("Select the language for AI transcription:"),
            style='Dialog.TLabel'
        ).pack(anchor="w", pady=(0, 5))

        # Prepare sorted language list with Auto Detect first
        language_values = [(code, name) for code, name in self.languages.items()]
        auto_option = next(item for item in language_values if item[0] == "auto")
        language_values.remove(auto_option)
        language_values.sort(key=lambda x: x[1])
        language_values.insert(0, auto_option)

        # AI Language combobox
        self.ai_language_combo = ttk.Combobox(
            ai_language_frame,
            values=[f"{name} ({code})" for code, name in language_values],
            state="readonly",
            font=get_font('sm')
        )
        self.ai_language_combo.pack(fill="x", pady=(0, 5))

        # Set current language value
        current_ai_lang = self.whisper_language_var.get()
        current_ai_lang_name = self.languages.get(current_ai_lang, "Auto Detect")
        self.ai_language_combo.set(f"{current_ai_lang_name} ({current_ai_lang})")
        # Keep the variable authoritative: it is what save reads, and it
        # survives the panel being destroyed when the category changes.
        self.ai_language_combo.bind(
            "<<ComboboxSelected>>", lambda _e: self._sync_speech_language())

        ttk.Label(
            ai_language_frame,
            text=_("Specifying the language improves transcription accuracy and speed."),
            font=get_font('xxs'),
            foreground="#888888"
        ).pack(anchor="w")

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
        """The models used to transcribe and to copy-edit, and the spoken language."""
        body = self._panel(_("AI Models"))
        self._section_models(body)
        self._section_speech_language(body)

    def _section_models(self, parent):
        """Transcription and copy-editing model choices."""
        # Model Settings Frame
        models_frame = ttk.LabelFrame(
            parent,
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
            text="e.g., gpt-5.6-luna, gpt-5.6-terra, gpt-5.6-sol, gpt-5, gpt-4.1, gpt-4o-mini",
            font=get_font('xxs'),
            foreground=THEME_TEXT_MUTED
        ).pack(anchor="w", pady=(5, 0))

        # Link to OpenAI Pricing
        link = tk.Label(
            parent,
            text=_("View Available OpenAI Models and Pricing"),
            fg=theme_colors().ACCENT_PRIMARY,
            bg=theme_colors().BG_PRIMARY,
            cursor="hand2",
            font=get_font('copy_link', 'underline')
        )
        link.pack(anchor="w", pady=(10, 0))
        link.bind("<Button-1>", lambda e: open_url("https://openai.com/api/pricing/"))
        link.bind("<Enter>", lambda e: link.config(fg=theme_colors().ACCENT_HOVER))
        link.bind("<Leave>", lambda e: link.config(fg=theme_colors().ACCENT_PRIMARY))

    def _on_transcription_model_change(self, *args):
        """Handle transcription model dropdown change."""
        if self._alive(getattr(self, 'custom_trans_frame', None)):
            if self.transcription_model_var.get() == "other":
                self.custom_trans_frame.pack(fill="x", pady=(5, 0))
                if self._alive(getattr(self, 'custom_trans_entry', None)):
                    self.custom_trans_entry.focus()
            else:
                self.custom_trans_frame.pack_forget()

    def _on_llm_model_change(self, *args):
        """Handle LLM model dropdown change."""
        if self._alive(getattr(self, 'custom_llm_frame', None)):
            if self.llm_model_var.get() == "other":
                self.custom_llm_frame.pack(fill="x", pady=(5, 0))
                if self._alive(getattr(self, 'custom_llm_entry', None)):
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
        # Get selected AI language code from combo box (if Language category was visited)
        if self._alive(getattr(self, 'ai_language_combo', None)):
            self._sync_speech_language()
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

        # Validate the Advanced numbers before anything is written, so a typo
        # cannot leave half the settings saved.
        advanced = self._validated_advanced_settings()
        if advanced is None:
            return

        # Update configuration values
        try:
            self.config.recording_location = self.recording_location_var.get()
            self.config.custom_recording_path = self.custom_location_var.get()
            self.config.file_handling = self.file_handling_var.get()
            self.config.paste_method = self.paste_method_var.get()
            self.config.hidpi_mode = self.hidpi_mode_var.get()
            self.config.close_to_tray = self.close_to_tray_var.get()

            # Save language settings
            self.config.language_mode = self.language_mode_var.get()
            self.config.language = self.language_var.get()

            # Save AI Models settings
            self.config.whisper_language = whisper_language_code
            self.config.transcription_model = transcription_model
            self.config.transcription_model_type = model_type
            self.config.ai_model = llm_model

            # Save Advanced settings
            self.config.recording_mode = advanced['recording_mode']
            self.config.max_recording_minutes = advanced['max_minutes']
            self.config.min_recording_seconds = advanced['min_seconds']
            self.config.discard_silent_recordings = advanced['discard_silent']
            self.config.recording_retention_days = advanced['retention_days']
            self.config.persist_history = advanced['persist_history']
            self.config.history_limit = advanced['history_limit']
            self.config.show_level_meter = advanced['show_level_meter']
            self.config.play_sounds = advanced['play_sounds']
            self.config.restore_clipboard = advanced['restore_clipboard']

            # Save to file
            self.config.save_settings()

            # Apply the advanced settings that the running app caches
            self.parent.apply_advanced_settings()

            # Update parent's recording directory
            self.parent.update_recording_directory()

            # Update parent's AI model instance variables
            self.parent.whisper_language = whisper_language_code
            self.parent.transcription_model = transcription_model
            self.parent.transcription_model_type = model_type
            self.parent.ai_model = llm_model

            # Update the model label in the UI
            self.parent.update_model_label()

            # Apply close-to-tray setting immediately
            self.parent.update_close_behavior()

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
                    self._close_dialog(check_unsaved=False)
                    self.parent.restart_application()
                    return
                else:
                    # Kept as a dialog: this one carries a consequence the user
                    # has to act on later, unlike a plain "saved" confirmation.
                    messagebox.showinfo(
                        _("Settings Saved"),
                        _("Configuration settings saved successfully!") + "\n\n" +
                        _("The HiDPI scaling change will take effect after you restart the application.")
                    )
                    self._close_dialog(check_unsaved=False)
                    return

            # A toast rather than a modal: a successful save needs
            # acknowledging, not dismissing.
            self._close_dialog(check_unsaved=False)
            self._notify_parent(_("Settings saved"))

        except Exception as e:
            messagebox.showerror(_("Error"), _("Could not save settings: {error}").format(error=e)) 

    def _validated_advanced_settings(self):
        """Parse the Advanced fields, or show an error and return None.

        The panel is only built once the user visits it, so anything they have
        not looked at falls back to the value already in the configuration
        rather than to a blank string.
        """
        def number(variable, label, current, minimum, maximum, as_float=False):
            raw = (variable.get() or "").strip()
            if not raw:
                return current
            try:
                value = float(raw) if as_float else int(raw)
            except ValueError:
                messagebox.showerror(
                    _("Invalid Value"),
                    _("'{value}' is not a valid number for {field}.").format(
                        value=raw, field=label))
                return None
            if value < minimum or value > maximum:
                messagebox.showerror(
                    _("Invalid Value"),
                    _("{field} must be between {minimum} and {maximum}.").format(
                        field=label, minimum=minimum, maximum=maximum))
                return None
            return value

        max_minutes = number(self.max_minutes_var, _("Maximum length (minutes)"),
                             self.config.max_recording_minutes, 0, 600)
        if max_minutes is None:
            return None

        min_seconds = number(self.min_seconds_var, _("Minimum length (seconds)"),
                             self.config.min_recording_seconds, 0, 60, as_float=True)
        if min_seconds is None:
            return None

        retention_days = number(self.retention_days_var, _("Delete recordings after (days)"),
                                self.config.recording_retention_days, 0, 3650)
        if retention_days is None:
            return None

        history_limit = number(self.history_limit_var, _("Entries to keep"),
                               self.config.history_limit, 1, 10000)
        if history_limit is None:
            return None

        mode = self.recording_mode_var.get() or self.config.recording_mode
        return {
            'recording_mode': mode if mode in ("toggle", "push_to_talk") else "toggle",
            'max_minutes': int(max_minutes),
            'min_seconds': float(min_seconds),
            'discard_silent': bool(self.discard_silent_var.get()),
            'retention_days': int(retention_days),
            'persist_history': bool(self.persist_history_var.get()),
            'history_limit': int(history_limit),
            'show_level_meter': bool(self.show_level_meter_var.get()),
            'play_sounds': bool(self.play_sounds_var.get()),
            'restore_clipboard': bool(self.restore_clipboard_var.get()),
        }

    def _sync_speech_language(self):
        """Copy the speech-language combobox selection into its variable."""
        try:
            selected = self.ai_language_combo.get()
            self.whisper_language_var.set(selected.split('(')[-1].strip(')'))
        except Exception:
            logger.debug("Could not read the speech language selection", exc_info=True)

    @staticmethod
    def _alive(widget):
        """Whether a widget reference still points at a live widget.

        Switching category destroys the current panel but leaves the
        attributes pointing at its widgets, so hasattr() alone reports a
        destroyed combobox as present and reading it raises TclError.
        """
        try:
            return widget is not None and bool(widget.winfo_exists())
        except Exception:
            return False

    def _notify_parent(self, message):
        """Show a toast on the main window (the dialog is on its way out)."""
        try:
            self.parent.ui_manager.show_toast(message)
        except Exception as e:
            logger.debug("Could not show the '%s' toast: %s", message, e)

    def _settings_snapshot(self):
        """Current value of every settings variable on this dialog.

        Collected by introspection rather than a hand-written list, so a
        setting added later is covered by the unsaved-changes check without
        anyone having to remember to add it here.
        """
        snapshot = {}
        for name, value in vars(self).items():
            if isinstance(value, (tk.StringVar, tk.BooleanVar,
                                  tk.IntVar, tk.DoubleVar)):
                try:
                    snapshot[name] = value.get()
                except Exception:
                    continue
        return snapshot

    def _has_unsaved_changes(self):
        baseline = getattr(self, '_baseline', None)
        if not baseline:
            return False
        current = self._settings_snapshot()
        return any(current.get(k) != v for k, v in baseline.items())

    def _close_dialog(self, check_unsaved=True):
        """Close the dialog, asking first if edits would be thrown away.

        Cancel and the X button used to discard everything silently.
        """
        if check_unsaved and self._has_unsaved_changes():
            keep_open = not messagebox.askyesno(
                _("Discard Changes?"),
                _("You have unsaved changes. Discard them?"),
                parent=self.dialog, default='no')
            if keep_open:
                return
        try:
            self.dialog.destroy()
        finally:
            if hasattr(self.parent, 'hotkey_manager'):
                self.parent.hotkey_manager.resume()