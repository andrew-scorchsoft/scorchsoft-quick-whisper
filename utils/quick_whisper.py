import tkinter as tk
from tkinter import ttk, messagebox, Menu
import threading
import pyaudio
import wave
import os
import sys
import openai
import pyperclip
import json
import pyttsx3
from tkinter import filedialog
import customtkinter as ctk
from PIL import Image, ImageTk 
from openai import OpenAI
from utils.config_manager import get_config
from pathlib import Path
from audioplayer import AudioPlayer
from pynput.keyboard import Controller as KeyboardController, Key  # For auto-paste functionality
import platform
import time

# Platform-specific imports
if platform.system() == 'Windows':
    import ctypes
    from ctypes import wintypes

from utils.tooltip import ToolTip
from utils.manage_prompts_dialog import ManagePromptsDialog
from utils.config_dialog import ConfigDialog
from utils.hotkey_manager import HotkeyManager
from utils.audio_manager import AudioManager
from utils.tts_manager import TTSManager
from utils.ui_manager import UIManager, StyledPopupMenu
from utils.version_update_manager import VersionUpdateManager
from utils.system_event_listener import SystemEventListener
from utils.tray_manager import TrayManager
from utils.theme import init_theme, get_window_size, get_font, get_font_size, get_font_family, get_button_height, get_spacing, get_feature_icons
from utils.platform import open_url
from utils.i18n import _, _n, init_i18n, set_language, get_current_language, register_refresh_callback, SUPPORTED_LANGUAGES


class QuickWhisper(tk.Tk):
    def __init__(self):
        super().__init__()

        # Hide window during initialization to prevent partial rendering flash
        self.withdraw()

        self.version = "2.0"

        self.is_mac = platform.system() == 'Darwin'

        # Apply HiDPI scaling for better display on high-resolution monitors
        self._apply_hidpi_scaling()

        # Initialize theme system with HiDPI awareness
        is_hidpi = getattr(self, 'hidpi_scale_factor', 1.0) > 1.0
        init_theme(is_hidpi=is_hidpi)

        self.title(f"{_('Quick Whisper by Scorchsoft.com (Speech to Copy Edited Text)')} - v{self.version}")

        # Initialize prompts
        self.prompts = self.load_prompts()  # Assuming you have a method to load prompts

        icon_path = self.resource_path("assets/icon-32.png")
        self.iconphoto(False, tk.PhotoImage(file=icon_path))
        if platform.system() == "Windows":
            self.iconbitmap(self.resource_path("assets/icon.ico"))

        # Set window size (sized to fit all content including full banner)
        # Use platform-specific window sizes from theme
        window_width, window_height = get_window_size('main')

        # Get screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # Ensure window fits on screen (with some margin)
        if window_height > screen_height - 100:
            window_height = screen_height - 100
        if window_width > screen_width - 100:
            window_width = screen_width - 100

        # Try to use saved window position from config
        # This helps with multi-monitor setups where centering puts window between monitors
        position_x, position_y = self._get_valid_window_position(
            window_width, window_height, screen_width, screen_height
        )

        # Set window geometry
        self.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")
        # Allow window resizing on all platforms
        self.resizable(True, True)
        # Set minimum size to prevent window becoming too small
        self.minsize(500, 300)
        self.banner_visible = True
        # Initial model settings
        self.transcription_model = "gpt-4o-transcribe"
        self.transcription_model_type = "gpt"  # Can be "gpt" or "whisper"
        self.ai_model = "gpt-5-mini"
        self.whisper_language = "auto"
        self.last_transcription = "NO LATEST TRANSCRIPTION"
        self.last_edit = "NO LATEST EDIT"

        # Initialize auto hotkey refresh setting (default to True)
        self.auto_hotkey_refresh = tk.BooleanVar(value=True)

        # Initialize dark mode setting (default to True)
        self.dark_mode = tk.BooleanVar(value=True)

        # Initialize HiDPI setting (False = auto-detect, True = force enabled)
        self.hidpi_enabled = tk.BooleanVar(value=False)

        self.load_config()

        # Initialize internationalization (i18n)
        # Must be done after config is loaded but before any UI strings are created
        init_i18n(
            config_language_mode=self.config_manager.language_mode,
            config_language=self.config_manager.language
        )
        # Register callback to rebuild menus when language changes
        register_refresh_callback(self._on_language_change)

        self.api_key = self.get_api_key()
        if not self.api_key:
            messagebox.showerror(_("API Key Missing"), _("Please set your OpenAI API Key in config/credentials.json or input it now."))
            self.destroy()
            return

        openai.api_key = self.api_key
        self.client = OpenAI(api_key=self.api_key)
        self.selected_device = tk.StringVar()
        self.auto_copy = tk.BooleanVar(value=True)
        self.auto_paste = tk.BooleanVar(value=True)
        self.history = []  # Stores up to 50 items of transcription or edited text
        self.history_index = -1  # -1 indicates no history selected yet
        self.max_history_length = 10000
        self.current_button_mode = "transcribe" # "transcribe" or "edit"
        
        # Initialize recording directory based on settings
        self.update_recording_directory()
        
        # Define helper method for environment variables before initializing managers
        self._env_get = lambda key, default=None: os.getenv(key, default)
        # Initialize the managers
        self.hotkey_manager = HotkeyManager(self)
        self.audio_manager = AudioManager(self)
        self.tts_manager = TTSManager(self)
        self.ui_manager = UIManager(self)
        self.version_manager = VersionUpdateManager(self)
        self.system_event_listener = SystemEventListener(self)
        self.tray_manager = TrayManager(self)
        
        # Setup hotkey health checker
        self.setup_hotkey_health_checker()
        
        # Register hotkeys
        self.hotkey_manager.register_hotkeys()

        self.create_menu()
        
        # Create UI widgets
        self.ui_manager.create_widgets()

        # Hide the banner on load if hide_banner is set to true in settings
        if self.hide_banner_on_load:
            self.toggle_banner()

        self.set_default_prompt()
        
        # Load selected prompt from config if it exists
        saved_prompt = self.config_manager.selected_prompt
        if saved_prompt:
            if saved_prompt == "Default":
                self.current_prompt_name = saved_prompt
            elif saved_prompt in self.prompts:
                self.current_prompt_name = saved_prompt
            else:
                messagebox.showwarning("Prompt Not Found", 
                    f"Selected prompt '{saved_prompt}' not found. Using default prompt.")
                self.current_prompt_name = "Default"

        # After loading the prompt from env, update the model label
        self.update_model_label()

        # Add binding for window state changes
        self.bind('<Unmap>', self._handle_minimize)
        self.bind('<Map>', self._handle_restore)
        self.was_minimized = False

        # Ensure default bindings for common edit actions in Text and Entry widgets
        self._install_text_bindings()
        
        # Initialize system tray
        self.setup_system_tray()

        # Check for updates in a separate thread
        self.version_manager.start_check()

        # Show window now that all widgets are created (prevents partial rendering flash)
        self.update_idletasks()  # Process all pending layout calculations
        self.deiconify()

        # Schedule UI update for shortcuts after everything is initialized
        def after_init():
            if hasattr(self, 'hotkey_manager') and self.hotkey_manager:
                self.hotkey_manager.update_shortcut_displays()

        # Delay to ensure UI is fully ready
        self.after(200, after_init)

    def _apply_hidpi_scaling(self):
        """Apply HiDPI scaling for better display on high-resolution monitors.

        This method handles DPI awareness differently per platform:
        - Windows: Sets DPI awareness for sharper rendering
        - Linux: Calculates and applies Tk scaling based on screen DPI/resolution
        - macOS: Usually handled automatically by the OS

        Respects the hidpi_mode setting from config:
        - "auto": Auto-detect based on screen resolution/DPI
        - "enabled": Force HiDPI scaling on
        - "disabled": Skip HiDPI scaling

        Sets self.hidpi_scale_factor which dialogs can use to scale their dimensions.
        """
        system = platform.system()

        # Initialize scale factor to 1.0 (no scaling)
        self.hidpi_scale_factor = 1.0

        # Load HiDPI setting from config (before load_config is called)
        try:
            config = get_config()
            hidpi_mode = config.hidpi_mode
        except Exception:
            hidpi_mode = "auto"

        print(f"HiDPI mode setting: {hidpi_mode}")

        # Skip scaling if disabled
        if hidpi_mode == "disabled":
            print("HiDPI scaling disabled by user setting")
            return

        if system == 'Windows':
            # Windows HiDPI handling:
            # - "disabled": Return early (handled above) - Windows default scaling preserved
            # - "auto": Auto-detect based on screen resolution and DPI
            # - "enabled": User explicitly wants HiDPI - set DPI awareness and apply Tk scaling
            try:
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()
                current_scaling = float(self.tk.call('tk', 'scaling'))

                print(f"Windows screen info: {screen_width}x{screen_height}, current Tk scaling: {current_scaling:.2f}")

                # For both "auto" and "enabled" modes, set DPI awareness for sharp rendering
                try:
                    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
                    print("Set per-monitor DPI awareness")
                except (AttributeError, OSError):
                    try:
                        ctypes.windll.user32.SetProcessDPIAware()
                        print("Set system DPI awareness (fallback)")
                    except (AttributeError, OSError):
                        print("Could not set DPI awareness")

                # Get actual system DPI
                try:
                    dpi = ctypes.windll.user32.GetDpiForSystem()
                except (AttributeError, OSError):
                    hdc = ctypes.windll.user32.GetDC(0)
                    dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
                    ctypes.windll.user32.ReleaseDC(0, hdc)

                print(f"Windows detected DPI: {dpi}")

                if hidpi_mode == "enabled":
                    # User explicitly enabled HiDPI - always apply scaling
                    scale_factor = dpi / 96.0
                    scale_factor = max(1.0, min(scale_factor, 2.5))  # Clamp between 1.0 and 2.5

                    self.tk.call('tk', 'scaling', scale_factor)
                    self.hidpi_scale_factor = scale_factor
                    print(f"Windows HiDPI enabled: DPI={dpi}, applied {scale_factor:.2f}x scaling")
                else:
                    # Auto mode: Detect if HiDPI is needed based on resolution and DPI
                    scale_factor = None
                    
                    # Strategy 1: Detect high-resolution displays by pixel count
                    if screen_width >= 3840 or screen_height >= 2160:
                        # 4K display - use 2x scaling
                        scale_factor = 2.0
                        print(f"Detected 4K+ display ({screen_width}x{screen_height}), using 2x scaling")
                    elif screen_width >= 2560 or screen_height >= 1440:
                        # QHD/2K display - use 1.5x scaling
                        scale_factor = 1.5
                        print(f"Detected QHD+ display ({screen_width}x{screen_height}), using 1.5x scaling")
                    elif screen_width >= 1920 and dpi > 96:
                        # Full HD with high DPI (Windows scaling applied) - use DPI-based scaling
                        scale_factor = dpi / 96.0
                        scale_factor = max(1.25, min(scale_factor, 2.5))  # At least 1.25x, cap at 2.5x
                        print(f"Detected Full HD with high DPI ({dpi}), using {scale_factor:.2f}x scaling")
                    
                    # Strategy 2: Fall back to DPI-based detection for any high DPI display
                    if scale_factor is None and dpi > 96 * 1.1:  # 10% threshold above 96
                        scale_factor = dpi / 96.0
                        scale_factor = min(scale_factor, 2.5)  # Cap at 2.5x
                        print(f"Using DPI-based scaling: {scale_factor:.2f}x")
                    
                    # Apply scaling if we determined one
                    if scale_factor and scale_factor > 1.0:
                        self.tk.call('tk', 'scaling', scale_factor)
                        self.hidpi_scale_factor = scale_factor
                        print(f"Windows auto mode: HiDPI scaling applied: {scale_factor:.2f}x")
                    else:
                        print("Windows auto mode: No HiDPI scaling needed")

            except Exception as e:
                print(f"Could not apply HiDPI scaling on Windows: {e}")

        elif system == 'Linux':
            # Linux: Multiple strategies for HiDPI detection
            # WSL and some X11 setups don't report DPI correctly
            try:
                scale_factor = None
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()
                screen_dpi = self.winfo_fpixels('1i')
                current_scaling = float(self.tk.call('tk', 'scaling'))

                print(f"Screen info: {screen_width}x{screen_height}, reported DPI: {screen_dpi:.0f}, current Tk scaling: {current_scaling:.2f}")

                # If user forced HiDPI mode, use aggressive scaling
                if hidpi_mode == "enabled":
                    # User wants HiDPI - determine appropriate scale based on resolution
                    if screen_width >= 3840 or screen_height >= 2160:
                        scale_factor = 2.0
                    elif screen_width >= 2560 or screen_height >= 1440:
                        scale_factor = 1.75
                    else:
                        scale_factor = 1.5  # Default forced scaling
                    print(f"HiDPI forced enabled, using {scale_factor}x scaling")
                else:
                    # Auto-detect mode
                    # Strategy 1: Check environment variables (set by desktop environments)
                    env_scale = os.environ.get('GDK_SCALE') or os.environ.get('QT_SCALE_FACTOR')
                    if env_scale:
                        try:
                            scale_factor = float(env_scale)
                            print(f"Using environment scale factor: {scale_factor}")
                        except ValueError:
                            pass

                    # Strategy 2: Detect high-resolution displays by pixel count
                    # Common HiDPI resolutions: 2560x1440 (QHD), 3840x2160 (4K), 2880x1800 (Retina)
                    if scale_factor is None:
                        if screen_width >= 3840 or screen_height >= 2160:
                            # 4K display - use 2x scaling
                            scale_factor = 2.0
                            print(f"Detected 4K+ display ({screen_width}x{screen_height}), using 2x scaling")
                        elif screen_width >= 2560 or screen_height >= 1440:
                            # QHD/2K display - use 1.5x scaling
                            scale_factor = 1.5
                            print(f"Detected QHD+ display ({screen_width}x{screen_height}), using 1.5x scaling")
                        elif screen_width >= 1920 and screen_dpi > 96:
                            # Full HD with high DPI - modest scaling
                            scale_factor = 1.25
                            print(f"Detected Full HD with high DPI, using 1.25x scaling")

                    # Strategy 3: Fall back to DPI-based calculation
                    if scale_factor is None and screen_dpi > 96 * 1.1:
                        scale_factor = screen_dpi / 96.0
                        scale_factor = min(scale_factor, 2.5)  # Cap at 2.5x
                        print(f"Using DPI-based scaling: {scale_factor:.2f}x")

                # Apply scaling if we determined one
                if scale_factor and scale_factor > 1.0:
                    self.tk.call('tk', 'scaling', scale_factor)
                    self.hidpi_scale_factor = scale_factor
                    print(f"HiDPI scaling applied: {scale_factor:.2f}x")
                elif current_scaling < 1.0:
                    # Ensure minimum scaling of 1.0
                    self.tk.call('tk', 'scaling', 1.0)
                    print(f"Applied minimum Tk scaling: 1.0 (was {current_scaling:.2f})")

            except Exception as e:
                print(f"Could not apply HiDPI scaling on Linux: {e}")

        # macOS generally handles Retina displays automatically
        # No special handling needed

    # Load configuration from JSON files
    def load_config(self):
        """Load configuration from settings.json and credentials.json files."""
        self.config_manager = get_config()

        # Load UI settings
        self.hide_banner_on_load = self.config_manager.hide_banner

        # Load auto hotkey refresh setting
        self.auto_hotkey_refresh.set(self.config_manager.auto_hotkey_refresh)
        
        # Load dark mode setting (default to True if not present)
        self.dark_mode.set(self.config_manager.dark_mode)

        # Load HiDPI setting (enabled = force HiDPI, auto = auto-detect)
        hidpi_mode = self.config_manager.hidpi_mode
        self.hidpi_enabled.set(hidpi_mode == "enabled")

        # Load model settings
        self.transcription_model = self.config_manager.transcription_model
        print(f"Loaded transcription model: '{self.transcription_model}'")
        
        self.transcription_model_type = self.config_manager.transcription_model_type
        # Determine model type from name if not set
        if not self.transcription_model_type or self.transcription_model_type == "unknown":
            if "gpt" in self.transcription_model.lower():
                self.transcription_model_type = "gpt"
            else:
                self.transcription_model_type = "whisper"
        print(f"Loaded model type: '{self.transcription_model_type}'")

        self.ai_model = self.config_manager.ai_model
        print(f"Loaded AI model: '{self.ai_model}'")

        self.whisper_language = self.config_manager.whisper_language
        print(f"Loaded whisper language: '{self.whisper_language}'")

        # Load keyboard shortcuts from config
        self.shortcuts = {
            'record_edit': self.config_manager.get_shortcut('record_edit'),
            'record_transcribe': self.config_manager.get_shortcut('record_transcribe'),
            'cancel_recording': self.config_manager.get_shortcut('cancel_recording'),
            'cycle_prompt_back': self.config_manager.get_shortcut('cycle_prompt_back'),
            'cycle_prompt_forward': self.config_manager.get_shortcut('cycle_prompt_forward')
        }

    def get_api_key(self):
        """Get the OpenAI API key, prompting if not found."""
        api_key = self.config_manager.openai_api_key
        if not api_key:  # Prompt for the key if it's not set
            api_key = self.openai_key_dialog()  # Call custom dialog
            if api_key:
                self.save_api_key(api_key)
            else:
                messagebox.showwarning("API Key Missing", "OpenAI API key is required to continue.")
                self.destroy()  # Exit if no key is provided
        return api_key
    
    def change_api_key(self):
        """Open the dialog to change the OpenAI API key."""
        new_key = self.openai_key_dialog()
        if new_key:
            self.save_api_key(new_key)
            self.api_key = new_key
            messagebox.showinfo("API Key Updated", "The OpenAI API Key has been updated successfully.")


    def openai_key_dialog(self):
        """Custom dialog for entering a new OpenAI API key with guidance link."""
        from utils.ui_manager import set_dark_title_bar
        import sv_ttk

        # Theme colors
        THEME_ACCENT = "#22d3ee"
        THEME_ACCENT_HOVER = "#67e8f9"

        dialog = tk.Toplevel(self)
        dialog.title("Enter New OpenAI API Key")

        # Get window dimensions from theme
        dialog_width, dialog_height = get_window_size('api_key_dialog')

        # Calculate center position relative to parent
        position_x = self.winfo_x() + (self.winfo_width() - dialog_width) // 2
        position_y = self.winfo_y() + (self.winfo_height() - dialog_height) // 2

        dialog.geometry(f"{dialog_width}x{dialog_height}+{position_x}+{position_y}")
        dialog.resizable(False, False)

        # Apply Sun Valley theme and dark title bar
        sv_ttk.set_theme("dark" if self.dark_mode.get() else "light")
        if self.dark_mode.get():
            set_dark_title_bar(dialog)

        # Get fonts from theme
        font_xs = get_font('xs')
        font_link = get_font('copy_link', 'underline')

        # Main content frame with padding
        content_frame = ttk.Frame(dialog, padding=(20, 15))
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Label for instructions
        instruction_label = ttk.Label(
            content_frame,
            text="Please enter your new OpenAI API Key below:",
            font=font_xs
        )
        instruction_label.pack(pady=(5, 12))

        # Entry field for the API key
        api_key_entry = ttk.Entry(content_frame, show='*', width=50, font=font_xs)
        api_key_entry.pack(pady=(0, 12), ipady=4)
        # Provide standard context menu and key bindings
        self._attach_entry_context_menu(api_key_entry)

        # Link to guidance - styled for dark mode visibility
        # Get background color to match theme
        bg_color = "#1c1c1c" if self.dark_mode.get() else "#fafafa"
        link_label = tk.Label(
            content_frame,
            text="How to obtain an OpenAI API key",
            fg=THEME_ACCENT,
            bg=bg_color,
            cursor="hand2",
            font=font_link
        )
        link_label.pack(pady=(0, 15))
        link_label.bind("<Button-1>", lambda e: open_url("https://scorchsoft.com/howto-get-openai-api-key"))
        link_label.bind("<Enter>", lambda e: link_label.config(fg=THEME_ACCENT_HOVER))
        link_label.bind("<Leave>", lambda e: link_label.config(fg=THEME_ACCENT))

        # Variable to store the API key input
        entered_key = None

        # Save action to capture API key input
        def save_and_close():
            nonlocal entered_key  # Use nonlocal to modify the outer variable
            entered_key = api_key_entry.get().strip()
            if entered_key:
                dialog.destroy()  # Close dialog after saving input
            else:
                messagebox.showwarning("Input Required", "Please enter a valid API key.")

        # Buttons frame for horizontal layout
        buttons_frame = ttk.Frame(content_frame)
        buttons_frame.pack(pady=(0, 5))

        # Get button font from theme
        font_button = get_font('sm')

        save_button = ttk.Button(buttons_frame, text="Save", command=save_and_close, width=12, cursor="hand2")
        save_button.pack(side=tk.LEFT, padx=(0, 8))
        save_button.configure(style='Dialog.TButton')

        cancel_button = ttk.Button(buttons_frame, text="Cancel", command=dialog.destroy, width=12, cursor="hand2")
        cancel_button.pack(side=tk.LEFT)
        cancel_button.configure(style='Dialog.TButton')

        # Configure button style with theme font
        style = ttk.Style()
        style.configure('Dialog.TButton', font=font_button)

        # Set focus to the entry field and make dialog modal
        api_key_entry.focus()
        dialog.transient(self)
        dialog.wait_visibility()  # Wait for dialog to be visible before grabbing (Linux fix)
        dialog.grab_set()
        self.wait_window(dialog)

        # Return the entered key or None if cancelled
        return entered_key if entered_key else None

    def _install_text_bindings(self):
        """Install standard copy/paste/cut/select-all bindings and context menus."""
        try:
            # Apply to all future Text widgets
            self.bind_class("Text", "<Control-a>", lambda e: (e.widget.tag_add("sel", "1.0", "end-1c"), "break"))
            self.bind_class("Text", "<Control-A>", lambda e: (e.widget.tag_add("sel", "1.0", "end-1c"), "break"))
            self.bind_class("Text", "<Control-c>", lambda e: (e.widget.event_generate("<<Copy>>"), "break"))
            self.bind_class("Text", "<Control-C>", lambda e: (e.widget.event_generate("<<Copy>>"), "break"))
            self.bind_class("Text", "<Control-v>", lambda e: (e.widget.event_generate("<<Paste>>"), "break"))
            self.bind_class("Text", "<Control-V>", lambda e: (e.widget.event_generate("<<Paste>>"), "break"))
            self.bind_class("Text", "<Control-x>", lambda e: (e.widget.event_generate("<<Cut>>"), "break"))
            self.bind_class("Text", "<Control-X>", lambda e: (e.widget.event_generate("<<Cut>>"), "break"))
            # Right-click menu
            self.bind_class("Text", "<Button-3>", self._show_text_context_menu)

            # Apply to all future Entry widgets
            self.bind_class("TEntry", "<Control-a>", lambda e: (e.widget.selection_range(0, 'end'), "break"))
            self.bind_class("TEntry", "<Control-A>", lambda e: (e.widget.selection_range(0, 'end'), "break"))
            self.bind_class("TEntry", "<Control-c>", lambda e: (e.widget.event_generate("<<Copy>>"), "break"))
            self.bind_class("TEntry", "<Control-C>", lambda e: (e.widget.event_generate("<<Copy>>"), "break"))
            self.bind_class("TEntry", "<Control-v>", lambda e: (e.widget.event_generate("<<Paste>>"), "break"))
            self.bind_class("TEntry", "<Control-V>", lambda e: (e.widget.event_generate("<<Paste>>"), "break"))
            self.bind_class("TEntry", "<Control-x>", lambda e: (e.widget.event_generate("<<Cut>>"), "break"))
            self.bind_class("TEntry", "<Control-X>", lambda e: (e.widget.event_generate("<<Cut>>"), "break"))
            self.bind_class("TEntry", "<Button-3>", self._show_entry_context_menu)
        except Exception as e:
            print(f"Error installing text bindings: {e}")

    def _attach_entry_context_menu(self, entry_widget):
        try:
            entry_widget.bind("<Button-3>", self._show_entry_context_menu)
            entry_widget.bind("<Control-a>", lambda e: (e.widget.selection_range(0, 'end'), "break"))
            entry_widget.bind("<Control-A>", lambda e: (e.widget.selection_range(0, 'end'), "break"))
        except Exception as e:
            print(f"Error attaching entry context menu: {e}")

    def _show_text_context_menu(self, event):
        widget = event.widget
        menu = Menu(self, tearoff=0)
        try:
            menu.add_command(label="Cut", command=lambda: widget.event_generate('<<Cut>>'))
            menu.add_command(label="Copy", command=lambda: widget.event_generate('<<Copy>>'))
            menu.add_command(label="Paste", command=lambda: widget.event_generate('<<Paste>>'))
            menu.add_separator()
            menu.add_command(label="Select All", command=lambda: widget.tag_add("sel", "1.0", "end-1c"))
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_entry_context_menu(self, event):
        widget = event.widget
        menu = Menu(self, tearoff=0)
        try:
            menu.add_command(label="Cut", command=lambda: widget.event_generate('<<Cut>>'))
            menu.add_command(label="Copy", command=lambda: widget.event_generate('<<Copy>>'))
            menu.add_command(label="Paste", command=lambda: widget.event_generate('<<Paste>>'))
            menu.add_separator()
            menu.add_command(label="Select All", command=lambda: widget.selection_range(0, 'end'))
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()


    def save_api_key(self, api_key):
        """Save the API key to credentials.json."""
        self.config_manager.openai_api_key = api_key
        self.config_manager.save_credentials()

    def create_menu(self):
        """Create application menus with translated labels."""
        # Dark menu styling with readable font
        menu_style = {
            'bg': '#111111',
            'fg': '#ffffff',
            'activebackground': '#262626',
            'activeforeground': '#ffffff',
            'relief': 'flat',
            'bd': 0,
            'font': ('Segoe UI', 11)  # Readable menu items
        }

        # Create a hidden menubar (we use a custom dark one in UI)
        self.menubar = Menu(self, **menu_style)
        # Don't set the menu - we'll use custom menu bar
        # self.config(menu=self.menubar)

        # File menu - use styled popup menu for modern look
        self.file_menu = StyledPopupMenu(self)
        self.file_menu.add_command(label=_("Save Session History"), command=self.save_session_history)
        self.file_menu.add_separator()
        self.file_menu.add_command(label=_("Minimize to Tray"), command=self.minimize_to_tray)
        self.file_menu.add_command(label=_("Exit"), command=self.on_closing)

        # Settings menu - use styled popup menu for modern look
        self.settings_menu = StyledPopupMenu(self)
        self.settings_menu.add_command(label=_("Change API Key"), command=self.change_api_key)
        self.settings_menu.add_command(label=_("Manage Prompts"), command=self.manage_prompts)
        self.settings_menu.add_command(label=_("Configuration"), command=self.open_config)
        self.settings_menu.add_separator()
        self.settings_menu.add_checkbutton(label=_("Automatically Check for Updates"),
                                    variable=self.version_manager.auto_update_check,
                                    command=self.version_manager.save_auto_update_setting)
        self.settings_menu.add_checkbutton(label=_("Auto-Refresh Hotkeys (Every 30s)"),
                                    variable=self.auto_hotkey_refresh,
                                    command=self.save_auto_hotkey_refresh)
        self.settings_menu.add_checkbutton(label=_("Dark Mode"),
                                    variable=self.dark_mode,
                                    command=self.toggle_dark_mode)
        self.settings_menu.add_separator()
        self.settings_menu.add_command(label=_("Keyboard Shortcut Mapping"), command=self.check_keyboard_shortcuts)
        self.settings_menu.add_command(label=_("Refresh Hotkeys"), command=self.hotkey_manager.force_hotkey_refresh)

        # Actions Menu - use styled popup menu for modern look
        self.actions_menu = StyledPopupMenu(self)

        # Recording actions group
        self.actions_menu.add_command(
            label=_("Record & Edit"),
            command=lambda: self.toggle_recording("edit"),
            accelerator=self.shortcuts['record_edit']
        )
        self.actions_menu.add_command(
            label=_("Record & Transcribe"),
            command=lambda: self.toggle_recording("transcribe"),
            accelerator=self.shortcuts['record_transcribe']
        )
        self.actions_menu.add_command(
            label=_("Cancel Recording"),
            command=self.cancel_recording,
            accelerator=self.shortcuts['cancel_recording']
        )
        self.actions_menu.add_separator()

        # Retry and copy actions group
        self.actions_menu.add_command(
            label=_("Retry Last Recording"),
            command=self.retry_last_recording
        )
        self.actions_menu.add_separator()

        # Copy actions group
        self.actions_menu.add_command(
            label=_("Copy Last Transcript"),
            command=self.copy_last_transcription
        )
        self.actions_menu.add_command(
            label=_("Copy Last Edit"),
            command=self.copy_last_edit
        )
        self.actions_menu.add_separator()

        # Prompt navigation group
        self.actions_menu.add_command(
            label=_("Previous Prompt"),
            command=self.cycle_prompt_backward,
            accelerator=self.shortcuts['cycle_prompt_back']
        )
        self.actions_menu.add_command(
            label=_("Next Prompt"),
            command=self.cycle_prompt_forward,
            accelerator=self.shortcuts['cycle_prompt_forward']
        )

        # Help menu - use styled popup menu for modern look
        self.help_menu = StyledPopupMenu(self)

        self.help_menu.add_command(label=_("About Quick Whisper"), command=self.show_about)
        self.help_menu.add_separator()
        self.help_menu.add_command(label=_("Check for Updates"), command=lambda: self.version_manager.check_for_updates(True))
        self.help_menu.add_command(label=_("Hide Banner") if self.banner_visible else _("Show Banner"), command=self.toggle_banner)
        self.help_menu.add_command(label=_("Terms of Use and Licence"), command=self.show_terms_of_use)

    def check_keyboard_shortcuts(self):
        """Test keyboard shortcuts and show status."""
        self.hotkey_manager.check_keyboard_shortcuts()

    def toggle_recording(self, mode="transcribe"):
        if not self.audio_manager.recording:
            # Set globally so the app knows when recording stops whether 
            # transcript or edit mode was selected
            self.current_button_mode = mode
            print(f"\nAbout to start recording. mode = {mode}")
            
            # Quick verification of hotkey state before recording
            # This helps ensure we can actually stop the recording with hotkeys
            if not self.hotkey_manager.verify_hotkeys():
                print("WARNING: Hotkeys not functioning correctly. Refreshing before recording...")
                self.hotkey_manager.force_hotkey_refresh(callback=lambda success: 
                                                        self.start_recording() if success else None)
            else:
                self.start_recording()
        else:
            print(f"About to stop recording. mode = {self.current_button_mode}")
            self.stop_recording()

    def start_recording(self):
        """Start audio recording."""
        # audio_manager.start_recording() handles all UI updates including button states
        self.audio_manager.start_recording()

    def stop_recording(self):
        """Stop recording and process audio."""
        audio_file = self.audio_manager.stop_recording()
        if audio_file:
            # Start transcription in a separate thread
            threading.Thread(target=self.transcribe_audio).start()
            
    def cancel_recording(self):
        """Cancel the current recording without processing."""
        self.audio_manager.cancel_recording()
        self.hotkey_manager.update_shortcut_displays()
    
    def retry_last_recording(self):
        """Retry processing the last recording."""
        self.audio_manager.retry_last_recording()

    def transcribe_audio(self):
        file_path = self.audio_manager.audio_file

        try:
            self.ui_manager.set_status("Processing - Transcript...", "green")

            with open(str(file_path), "rb") as audio_file:

                print(f"Transcription Mode: '{self.transcription_model}' | Type: '{self.transcription_model_type}'")
                
                # Different API call based on model type
                if not self.transcription_model or not self.transcription_model.strip():
                    messagebox.showerror("Configuration Error", 
                                        "Transcription model name is empty. Please check your settings.")
                    raise ValueError("Empty transcription model name")
                
                if self.transcription_model_type == "gpt":
                    # GPT-4o speech-to-text API
                    print(f"Using GPT API with model: {self.transcription_model}")
                    try:
                        transcription = self.client.audio.transcriptions.create(
                            file=audio_file,
                            model=self.transcription_model,
                            language=None if self.whisper_language == "auto" else self.whisper_language,
                            response_format="text"
                        )
                        transcription_text = transcription
                    except Exception as e:
                        print(f"Error with GPT transcription: {e}")
                        raise
                else:
                    # Traditional Whisper API
                    print(f"Using Whisper API with model: {self.transcription_model}")
                    try:
                        transcription = self.client.audio.transcriptions.create(
                            file=audio_file,
                            model=self.transcription_model,
                            language=None if self.whisper_language == "auto" else self.whisper_language,
                            response_format="verbose_json"
                        )
                        # Retrieve the transcription text correctly
                        transcription_text = transcription.get("text", "") if isinstance(transcription, dict) else transcription.text
                    except Exception as e:
                        print(f"Error with Whisper transcription: {e}")
                        raise

            # Remove any trailing newlines/spaces to avoid moving the caret to a new line on paste
            transcription_text = (transcription_text or "").rstrip()

            self.add_to_history(transcription_text)
            self.last_transcription = transcription_text

            # Process transcription with or without GPT as per the checkbox setting
            if self.current_button_mode == "edit":
                print("AI Editing Transcription")

                # Helper to update UI safely from this thread
                def update_transcription_ui(text):
                    self.ui_manager.transcription_text.delete("1.0", tk.END)
                    self.ui_manager.transcription_text.insert("1.0", text)

                # set input box to transcription text first, just incase there is a failure
                # Schedule UI update on main thread (Tkinter is not thread-safe)
                self.after(0, lambda: update_transcription_ui(transcription_text))

                # Then GPT edit that transcribed text and insert
                self.ui_manager.set_status("Processing - AI Editing...", "green")

                # AI Edit the transcript
                edited_text = self.process_with_gpt_model(transcription_text)
                edited_text = (edited_text or "").rstrip()
                self.add_to_history(edited_text)
                self.last_edit = edited_text
                play_text = edited_text

                # Schedule UI update on main thread (Tkinter is not thread-safe)
                self.after(0, lambda: update_transcription_ui(play_text))
            else:
                print("Outputting Raw Transcription Only")
                # Schedule UI update on main thread (Tkinter is not thread-safe)
                def update_transcription_ui(text):
                    self.ui_manager.transcription_text.delete("1.0", tk.END)
                    self.ui_manager.transcription_text.insert("1.0", text)
                self.after(0, lambda: update_transcription_ui(transcription_text))
                play_text = transcription_text


            if self.auto_copy.get():
                self.auto_copy_text(play_text)

            if self.auto_paste.get():
                self.auto_paste_text(play_text)

            print("Transcription Complete: The audio has been transcribed and the text has been placed in the input area.")
            # Play stop recording sound
            threading.Thread(target=lambda: self.play_sound("assets/double-pop-down.wav")).start()

        except Exception as e:
            # Play failure sound
            threading.Thread(target=lambda: self.play_sound("assets/wrong-short.wav")).start()

            print(f"Transcription error: An error occurred during transcription: {str(e)}")
            self.ui_manager.set_status("Error during transcription", "red")

            # Provide a clearer hint for known unsupported/renamed models
            err_text = str(e)
            if "mini" in (self.transcription_model or "").lower():
                messagebox.showerror(
                    "Transcription Error",
                    "The selected transcription model may be unsupported. Try 'gpt-4o-transcribe' or 'whisper-1'.\n\n"
                    "If you entered a custom model, please verify the exact model name supported by the API."
                )
            else:
                messagebox.showerror("Transcription Error", f"An error occurred while Transcribing: {e}")

        finally:
            self.ui_manager.set_status("Idle", "blue")

    def copy_last_transcription(self):
        try:
            # Copy text to clipboard
            pyperclip.copy(self.last_transcription)

        except Exception as e:
            messagebox.showerror("Auto-Copy Error", f"Failed to copy the transcription to clipboard: {e}")
    
    def copy_last_edit(self):
        try:
            # Copy text to clipboard
            pyperclip.copy(self.last_edit)

        except Exception as e:
            messagebox.showerror("Auto-Copy Error", f"Failed to copy the last edit to clipboard: {e}")
        
    def auto_copy_text(self, text):
        try:
            # Copy text to clipboard
            pyperclip.copy(text)

        except Exception as e:
            messagebox.showerror("Auto-Copy Error", f"Failed to auto-copy the transcription: {e}")

    def auto_paste_text(self, text):
        try:
            # Use pynput keyboard controller for cross-platform paste
            keyboard_controller = KeyboardController()

            # Use OS-specific keyboard shortcuts
            if self.is_mac:
                keyboard_controller.press(Key.cmd)
                keyboard_controller.press('v')
                keyboard_controller.release('v')
                keyboard_controller.release(Key.cmd)
            else:
                keyboard_controller.press(Key.ctrl)
                keyboard_controller.press('v')
                keyboard_controller.release('v')
                keyboard_controller.release(Key.ctrl)
        except Exception as e:
            messagebox.showerror("Auto-Paste Error", f"Failed to auto-paste the transcription: {e}")


    def process_with_gpt_model(self, text):
        try:
            # Replace the hardcoded system prompt with the selected one
            system_prompt = self.get_system_prompt()
            
            user_prompt = "Here is the transcription \r\n<transcription>\r\n" + text + "\r\n</transcription>\r\n"


            print(f"About to process with AI Model {self.ai_model}")

            if "gpt-5" in self.ai_model:
                response = self.client.responses.create(
                    model=self.ai_model,
                    instructions=system_prompt,
                    text={"verbosity": "low"},  
                    reasoning={"effort": "minimal"},
                    input=user_prompt,
                    max_output_tokens=8000
                )
                gpt_text = response.output_text
            else:
                response = self.client.chat.completions.create(
                    model=self.ai_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=8000
                )
                gpt_text = response.choices[0].message.content

            
            
            
            return gpt_text
        

        except Exception as e:
            # Play failure sound
            threading.Thread(target=lambda: self.play_sound("assets/wrong-short.wav")).start()
            messagebox.showerror("GPT Processing Error", f"An error occurred while processing with GPT: {e}")
            return None
        

    def resource_path(self, relative_path):
        """Get the absolute path to the resource, works for both development and PyInstaller environments."""
        try:
            base_path = sys._MEIPASS
        except AttributeError:
            base_path = os.path.dirname(os.path.abspath(sys.argv[0]))

        # Handle icon files differently for Mac
        if self.is_mac and relative_path.endswith('.ico'):
            # Use .png version instead of .ico for Mac
            relative_path = relative_path.replace('.ico', '.png')

        abs_path = os.path.join(base_path, relative_path)
        return abs_path

    def on_closing(self):
        """Clean up resources before closing."""
        # Save window position for next launch
        self._save_window_position()

        # Stop the system tray icon
        if hasattr(self, 'tray_manager'):
            self.tray_manager.stop_tray()

        # Stop the system event listener
        if hasattr(self, 'system_event_listener'):
            self.system_event_listener.stop_listening()

        # Clean up TTS
        self.tts_manager.cleanup()

        # Clean up hotkeys
        self.hotkey_manager.unregister_hotkeys()

        # Clean up audio
        self.audio_manager.cleanup()

        self.destroy()

    def _get_valid_window_position(self, window_width, window_height, screen_width, screen_height):
        """
        Get a valid window position, using saved position if available and valid.
        Falls back to centering on the primary monitor area if saved position is off-screen.
        
        Properly handles multi-monitor setups on all platforms.
        """
        from utils.config_manager import get_config

        # Get virtual screen bounds (spans all monitors)
        virtual_left, virtual_top, virtual_width, virtual_height = self._get_virtual_screen_bounds()
        
        try:
            config = get_config()
            saved_x = config.window_x
            saved_y = config.window_y

            if saved_x is not None and saved_y is not None:
                # Validate the saved position is still on the virtual screen
                # Allow the window to be partially off-screen but at least 100px must be visible
                min_visible = 100

                # Check if at least part of the window would be visible on any monitor
                # Using virtual screen bounds for multi-monitor support
                if (saved_x > virtual_left - window_width + min_visible and
                    saved_x < virtual_left + virtual_width - min_visible and
                    saved_y > virtual_top - window_height + min_visible and
                    saved_y < virtual_top + virtual_height - min_visible):
                    print(f"Restoring window position to ({saved_x}, {saved_y})")
                    return saved_x, saved_y
                else:
                    print(f"Saved window position ({saved_x}, {saved_y}) is off virtual screen "
                          f"(bounds: {virtual_left},{virtual_top} to {virtual_left + virtual_width},{virtual_top + virtual_height}), "
                          f"using default")
        except Exception as e:
            print(f"Error loading saved window position: {e}")

        # Fall back to centering - but on multi-monitor setups, try to stay on the left/primary monitor
        # If screen is very wide (suggesting multi-monitor), center on left half
        if screen_width > 3000:  # Likely multi-monitor
            # Center on the left portion of the screen (assuming ~1920px primary monitor)
            center_x = int((min(1920, screen_width // 2) - window_width) / 2)
        else:
            center_x = int((screen_width - window_width) / 2)

        center_y = int((screen_height - window_height) / 2)
        return center_x, center_y
    
    def _get_virtual_screen_bounds(self):
        """
        Get the bounds of the virtual screen (spanning all monitors).
        
        Returns:
            Tuple of (left, top, width, height) representing the virtual screen bounds.
            On single-monitor setups, this will be (0, 0, screen_width, screen_height).
        """
        try:
            if platform.system() == "Windows":
                # Use Windows API to get virtual screen dimensions
                user32 = ctypes.windll.user32
                # SM_XVIRTUALSCREEN = 76 (left edge of virtual screen)
                # SM_YVIRTUALSCREEN = 77 (top edge of virtual screen)
                # SM_CXVIRTUALSCREEN = 78 (width of virtual screen)
                # SM_CYVIRTUALSCREEN = 79 (height of virtual screen)
                virtual_left = user32.GetSystemMetrics(76)
                virtual_top = user32.GetSystemMetrics(77)
                virtual_width = user32.GetSystemMetrics(78)
                virtual_height = user32.GetSystemMetrics(79)
                return virtual_left, virtual_top, virtual_width, virtual_height
            
            elif platform.system() == "Darwin":
                # On macOS, try to use AppKit if available
                try:
                    from AppKit import NSScreen
                    screens = NSScreen.screens()
                    if screens:
                        # Calculate the bounding box of all screens
                        min_x = min(screen.frame().origin.x for screen in screens)
                        min_y = min(screen.frame().origin.y for screen in screens)
                        max_x = max(screen.frame().origin.x + screen.frame().size.width for screen in screens)
                        max_y = max(screen.frame().origin.y + screen.frame().size.height for screen in screens)
                        return int(min_x), int(min_y), int(max_x - min_x), int(max_y - min_y)
                except ImportError:
                    pass
                # Fallback: macOS tkinter usually returns virtual screen dimensions
                return 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()
            
            else:  # Linux and others
                # On Linux with X11, winfo_vrootwidth/height should give virtual screen size
                # Try to get the virtual root dimensions
                try:
                    vroot_width = self.winfo_vrootwidth()
                    vroot_height = self.winfo_vrootheight()
                    if vroot_width > 0 and vroot_height > 0:
                        return 0, 0, vroot_width, vroot_height
                except:
                    pass
                # Fallback to standard screen dimensions
                return 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()
                
        except Exception as e:
            print(f"Error getting virtual screen bounds: {e}")
            # Fallback to basic screen dimensions
            return 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()

    def _save_window_position(self):
        """Save the current window position to config for next launch."""
        try:
            if hasattr(self, 'config_manager'):
                # Get current window position
                x = self.winfo_x()
                y = self.winfo_y()

                # Only save if position seems valid (not minimized/hidden)
                if x > -10000 and y > -10000:
                    self.config_manager.window_x = x
                    self.config_manager.window_y = y
                    self.config_manager.save_settings()
        except Exception as e:
            print(f"Error saving window position: {e}")

    def play_sound(self, sound_file):
        """Play sound using audio manager."""
        self.audio_manager.play_sound(sound_file)

    def show_terms_of_use(self):
        # Create a new window to display the terms of use
        instruction_window = tk.Toplevel(self)
        instruction_window.title("Terms of Use")

        # Get window dimensions from theme
        window_width, window_height = get_window_size('about_dialog')
        position_x = self.winfo_x() + (self.winfo_width() - window_width) // 2
        position_y = self.winfo_y() + (self.winfo_height() - window_height) // 2
        instruction_window.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")

        # Get the path to the LICENSE.md file using the resource_path method
        license_path = self.resource_path("assets/LICENSE.md")

        # Attempt to read the content of the LICENSE.md file
        try:
            with open(license_path, "r", encoding="utf-8") as file:
                license_content = file.read()
        except FileNotFoundError:
            license_content = "License file not found. Please ensure the LICENSE.md file exists in the application directory."
        except PermissionError:
            license_content = "Permission denied. Please ensure the script has read access to LICENSE.md."
        except UnicodeDecodeError as e:
            license_content = f"Error reading license file due to encoding issue: {e}"
        except Exception as e:
            license_content = f"An unexpected error occurred while reading the license file: {e}"

        # Create a frame to contain the text widget and scrollbar
        frame = ttk.Frame(instruction_window)
        frame.pack(fill=tk.BOTH, expand=True)

        # Add a scrolling text widget to display the license content
        text_widget = tk.Text(frame, wrap=tk.WORD)
        text_widget.insert(tk.END, license_content)
        text_widget.config(state=tk.DISABLED)  # Make the text read-only
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add a vertical scrollbar
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text_widget.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure the scrollbar to work with the text widget
        text_widget.config(yscrollcommand=scrollbar.set)

        # Add a button to close the window
        ttk.Button(instruction_window, text="Close", command=instruction_window.destroy).pack(pady=(10, 0))

    def show_version(self):
        instruction_window = tk.Toplevel(self)
        instruction_window.title("App Version")

        # Get window dimensions from theme
        window_width, window_height = get_window_size('tos_dialog')
        position_x = self.winfo_x() + (self.winfo_width() - window_width) // 2
        position_y = self.winfo_y() + (self.winfo_height() - window_height) // 2
        instruction_window.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")
        
        instructions = f"""Version {self.version}\n\n App by Scorchsoft.com"""
        
        tk.Label(instruction_window, text=instructions, justify=tk.LEFT, wraplength=280).pack(padx=10, pady=10)
        
        # Add a button to close the window
        ttk.Button(instruction_window, text="Close", command=instruction_window.destroy).pack(pady=(10, 0))

    def show_about(self):
        """Show the About Quick Whisper dialog with information about the app."""
        from utils.ui_manager import set_dark_title_bar, ModernTheme
        
        theme = ModernTheme()
        
        # Check current theme setting
        is_dark = self.config_manager.dark_mode
        
        # Theme-aware colors
        if is_dark:
            bg_primary = theme.BG_PRIMARY
            bg_secondary = theme.BG_SECONDARY
            bg_tertiary = theme.BG_TERTIARY
            bg_hover = theme.BG_HOVER
            text_primary = theme.TEXT_PRIMARY
            text_secondary = theme.TEXT_SECONDARY
            text_tertiary = theme.TEXT_TERTIARY
            text_muted = theme.TEXT_MUTED
        else:
            bg_primary = "#fafafa"
            bg_secondary = "#f0f0f0"
            bg_tertiary = "#e8e8e8"
            bg_hover = "#e0e0e0"
            text_primary = "#1c1c1c"
            text_secondary = "#333333"
            text_tertiary = "#555555"
            text_muted = "#777777"
        
        dialog = tk.Toplevel(self)
        dialog.title("About Quick Whisper")

        # Get window dimensions from theme
        window_width, window_height = get_window_size('about_dialog')
        position_x = self.winfo_x() + (self.winfo_width() - window_width) // 2
        position_y = self.winfo_y() + (self.winfo_height() - window_height) // 2
        dialog.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")
        dialog.resizable(True, True)
        dialog.minsize(500, 400)

        # Calculate initial wraplength for text labels based on window width and padding
        # content padding: 32*2, desc_frame padding: 16*2
        text_wraplength = window_width - 32*2 - 16*2 - 10  # extra margin for safety

        # Store labels that need dynamic wraplength updates
        wrapping_labels = []
        
        # Apply title bar based on theme
        if is_dark:
            set_dark_title_bar(dialog)
        
        # Make dialog modal
        dialog.transient(self)
        dialog.wait_visibility()  # Wait for dialog to be visible before grabbing (Linux fix)
        dialog.grab_set()

        # Main container with theme-aware background
        main_frame = tk.Frame(dialog, bg=bg_primary)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Content area with padding
        content = tk.Frame(main_frame, bg=bg_primary, padx=32, pady=24)
        content.pack(fill=tk.BOTH, expand=True)
        
        # App icon/logo area with gradient accent line
        accent_line = tk.Frame(content, height=3, bg=theme.GRADIENT_START)
        accent_line.pack(fill=tk.X, pady=(0, 20))
        
        # Title
        title_label = tk.Label(
            content,
            text="Quick Whisper",
            font=get_font('xl', 'bold'),
            fg=text_primary,
            bg=bg_primary
        )
        title_label.pack(anchor="w", pady=(0, 4))

        # Subtitle/tagline
        tagline_label = tk.Label(
            content,
            text="AI-Powered Speech-to-Copy-Edited-Text",
            font=get_font('md'),
            fg=theme.ACCENT_PRIMARY,
            bg=bg_primary
        )
        tagline_label.pack(anchor="w", pady=(0, 16))

        # Version
        version_label = tk.Label(
            content,
            text=f"Version {self.version}",
            font=get_font('xs'),
            fg=text_muted,
            bg=bg_primary
        )
        version_label.pack(anchor="w", pady=(0, 20))
        
        # Description text frame
        desc_frame = tk.Frame(content, bg=bg_secondary, padx=16, pady=16)
        desc_frame.pack(fill=tk.X, pady=(0, 20))
        
        description = (
            "Quick Whisper is a free and open-source speech-to-copy-edited-text "
            "software tool that uses AI to convert spoken audio into a copy-edited "
            "transcript, automatically pasting it into your active application.\n\n"
            "Designed to enhance productivity, it significantly accelerates workflows, "
            "allowing quicker responses to emails or messages—speaking is generally "
            "two to three times faster than typing."
        )
        
        desc_label = tk.Label(
            desc_frame,
            text=description,
            font=get_font('sm'),
            fg=text_secondary,
            bg=bg_secondary,
            wraplength=text_wraplength,
            justify=tk.LEFT
        )
        desc_label.pack(anchor="w", fill=tk.X)
        wrapping_labels.append(desc_label)

        # Features section
        features_label = tk.Label(
            content,
            text="Key Features",
            font=get_font('md', 'bold'),
            fg=text_primary,
            bg=bg_primary
        )
        features_label.pack(anchor="w", pady=(0, 10))
        
        features = get_feature_icons()
        
        for icon, feature in features:
            feature_frame = tk.Frame(content, bg=bg_primary)
            feature_frame.pack(fill=tk.X, pady=2)

            tk.Label(
                feature_frame,
                text=icon,
                font=get_font('sm'),
                fg=text_primary,
                bg=bg_primary
            ).pack(side=tk.LEFT, padx=(0, 10))

            tk.Label(
                feature_frame,
                text=feature,
                font=get_font('sm'),
                fg=text_secondary,
                bg=bg_primary,
                anchor="w"
            ).pack(side=tk.LEFT, fill=tk.X)
        
        # Spacer
        tk.Frame(content, height=12, bg=bg_primary).pack()
        
        # How to use section
        usage_frame = tk.Frame(content, bg=bg_tertiary, padx=16, pady=12)
        usage_frame.pack(fill=tk.X, pady=(0, 16))
        
        usage_text = (
            "How to use: Press Ctrl+Alt+J to record and AI-edit, or Ctrl+Alt+Shift+J "
            "for raw transcription. The app will automatically copy and paste "
            "the result into your active application."
        )
        
        usage_label = tk.Label(
            usage_frame,
            text=usage_text,
            font=get_font('xs'),
            fg=text_tertiary,
            bg=bg_tertiary,
            wraplength=text_wraplength,
            justify=tk.LEFT
        )
        usage_label.pack(anchor="w", fill=tk.X)
        wrapping_labels.append(usage_label)

        # Dynamic text wrapping on resize
        def on_dialog_resize(event):
            # Only respond to dialog width changes
            if event.widget == dialog:
                new_wraplength = event.width - 32*2 - 16*2 - 10
                if new_wraplength > 100:  # Sanity check
                    for label in wrapping_labels:
                        label.configure(wraplength=new_wraplength)

        dialog.bind('<Configure>', on_dialog_resize)

        # Bottom buttons frame
        button_frame = tk.Frame(content, bg=bg_primary)
        button_frame.pack(fill=tk.X, pady=(10, 20))
        
        # Learn More button (styled link to blog)
        def open_blog():
            open_url("https://www.scorchsoft.com/blog/speech-to-copyedited-text-app/")
        
        # Use half the button height for corner_radius to create pill shape
        button_height = get_button_height('dialog')
        corner_radius = button_height // 2

        learn_more_btn = ctk.CTkButton(
            button_frame,
            text="Learn More on Our Website",
            corner_radius=corner_radius,
            height=button_height,
            width=320,
            fg_color=theme.GRADIENT_START,
            hover_color=theme.GRADIENT_HOVER_START,
            text_color="#ffffff" if not is_dark else theme.BG_PRIMARY,
            font=ctk.CTkFont(family=get_font_family(), size=get_font_size('dialog_button'), weight='bold'),
            cursor="hand2",
            command=open_blog
        )
        learn_more_btn.pack(side=tk.LEFT, padx=(0, get_spacing('lg')))

        # Close button
        close_btn = ctk.CTkButton(
            button_frame,
            text="Close",
            corner_radius=corner_radius,
            height=button_height,
            width=140,
            fg_color=bg_tertiary,
            hover_color=bg_hover,
            text_color=text_primary,
            font=ctk.CTkFont(family=get_font_family(), size=get_font_size('dialog_button')),
            cursor="hand2",
            command=dialog.destroy
        )
        close_btn.pack(side=tk.RIGHT)
        
        # Developer credit at bottom - light blue in dark mode, purple in light mode
        link_color = theme.ACCENT_PRIMARY if is_dark else theme.GRADIENT_END
        link_hover = theme.GRADIENT_HOVER_START if is_dark else theme.GRADIENT_HOVER_END
        credit_label = tk.Label(
            content,
            text="Developed by Scorchsoft.com | App & AI Developers",
            font=get_font('xs', 'underline'),
            fg=link_color,
            bg=bg_primary,
            cursor="hand2"
        )
        credit_label.pack(anchor="center", pady=(0, 0))
        credit_label.bind("<Button-1>", lambda e: open_url("https://www.scorchsoft.com/"))
        credit_label.bind("<Enter>", lambda e: credit_label.config(fg=link_hover))
        credit_label.bind("<Leave>", lambda e: credit_label.config(fg=link_color))

    def add_to_history(self, text):
        # Append new text to the end of the list
        self.history.append(text)

        # Enforce max history length by removing the oldest element if necessary
        if len(self.history) > self.max_history_length:
            self.history.pop(0)  # Removes the oldest (first) item in the array

        # Update the index to the last entry (most recent)
        self.history_index = len(self.history) - 1
        self.ui_manager.update_transcription_text()
        self.ui_manager.update_navigation_buttons()
        
    def navigate_right(self):
        self.history_index -= 1
        self.ui_manager.update_transcription_text()
        self.ui_manager.update_navigation_buttons()

    def navigate_left(self):
        self.history_index += 1
        self.ui_manager.update_transcription_text()
        self.ui_manager.update_navigation_buttons()

    def go_to_first_page(self):
        self.history_index = len(self.history) - 1  # Set to most recent
        self.ui_manager.update_transcription_text()
        self.ui_manager.update_navigation_buttons()
    
    def save_session_history(self):
        if not self.history:
            messagebox.showinfo("No History", "There is no history to save.")
            return

        # Open a file save dialog
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")],
            title="Save Session History"
        )

        if not file_path:
            # User cancelled the save dialog
            return

        try:
            # Serialize history to JSON and save to file
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=4, ensure_ascii=False)

            messagebox.showinfo("Success", f"Session history saved successfully to {file_path}")
        except Exception as e:
            # Handle errors during the save process
            messagebox.showerror("Save Error", f"An error occurred while saving: {e}")

    def update_model_label(self):
        """Update the model label to include the prompt name and language setting."""
        self.ui_manager.update_model_label()

    def toggle_banner(self):
        """Toggle the visibility of the banner image."""
        self.ui_manager.toggle_banner()

    def load_prompts(self):
        """Load custom prompts from JSON file."""
        prompts_file = Path("config") / "prompts.json"
        if prompts_file.exists():
            try:
                with open(prompts_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading prompts: {e}")
        return {}

    def save_prompts(self, prompts):
        """Save custom prompts to JSON file."""
        prompts_file = Path("config") / "prompts.json"
        try:
            # Ensure config directory exists
            prompts_file.parent.mkdir(parents=True, exist_ok=True)
            with open(prompts_file, 'w', encoding='utf-8') as f:
                json.dump(prompts, f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save prompts: {e}")

    def save_prompt_to_config(self, prompt_name):
        """Save selected prompt to settings.json."""
        self.config_manager.selected_prompt = prompt_name
        self.config_manager.save_settings()

    def get_system_prompt(self):
        """Get the current system prompt based on selection."""
        if self.current_prompt_name == "Default":
            return self.default_system_prompt
        return self.prompts.get(self.current_prompt_name, self.default_system_prompt)
    
    
    def set_default_prompt(self):
        """Initialize default prompt and prompts dictionary."""
        try:
            default_prompt_path = self.resource_path("assets/DefaultPrompt.md")
            with open(default_prompt_path, 'r', encoding='utf-8') as f:
                self.default_system_prompt = f.read()
        except Exception as e:
            print(f"Error loading default prompt: {e}")
            # Fallback to a basic prompt if file can't be loaded
            self.default_system_prompt = "You are an expert Copy Editor. When provided with text, provide a cleaned-up copy-edited version of that text in response."
            
        self.prompts = self.load_prompts()
        self.current_prompt_name = "Default"

    def _handle_minimize(self, event):
        """Track when window is minimized"""
        self.was_minimized = True

    def _handle_restore(self, event):
        """Handle window restore from minimized state"""
        if self.was_minimized:
            self.was_minimized = False
            print("Window restored from minimized state - refreshing hotkeys")
            self.hotkey_manager.force_hotkey_refresh()

    def manage_prompts(self):
        ManagePromptsDialog(self)

    def open_config(self):
        """Open the configuration dialog."""
        ConfigDialog(self)

    def show_prompt_notification(self, message):
        """Show a temporary notification message in the status label and speak the prompt name."""
        # Create a clean version of the message for speech
        speech_message = message.replace("Prompt: ", "")
        
        # Use text-to-speech for Windows
        if platform.system() == 'Windows':
            self.tts_manager.speak_text(speech_message)

    def cycle_prompt_forward(self):
        """Cycle to the next prompt in the list."""
        # Create list of prompt names including "Default"
        prompt_names = ["Default"] + list(self.prompts.keys())
        
        # Find current index
        try:
            current_index = prompt_names.index(self.current_prompt_name)
        except ValueError:
            current_index = 0  # Default to the first prompt if not found
        
        # Calculate next index (cycle back to start if at end)
        next_index = (current_index + 1) % len(prompt_names)
        
        # Update current prompt
        self.current_prompt_name = prompt_names[next_index]
        self.save_prompt_to_config(self.current_prompt_name)
        
        # Update UI
        self.update_model_label()
        
        # Show notification and trigger text-to-speech
        self.show_prompt_notification(f"Prompt: {self.current_prompt_name}")

    def cycle_prompt_backward(self):
        """Cycle to the previous prompt in the list."""
        # Create list of prompt names including "Default"
        prompt_names = ["Default"] + list(self.prompts.keys())
        
        # Find current index
        try:
            current_index = prompt_names.index(self.current_prompt_name)
        except ValueError:
            current_index = 0  # Default to the first prompt if not found
        
        # Calculate previous index (cycle to end if at start)
        prev_index = (current_index - 1) % len(prompt_names)
        
        # Update current prompt
        self.current_prompt_name = prompt_names[prev_index]
        self.save_prompt_to_config(self.current_prompt_name)
        
        # Update UI
        self.update_model_label()
        
        # Show notification and trigger text-to-speech
        self.show_prompt_notification(f"Prompt: {self.current_prompt_name}")

    def cycle_prompt_notification(self, prompt_name):
        """Show a temporary notification about the prompt change."""
        self.show_prompt_notification(f"Prompt: {prompt_name}")

    def setup_hotkey_health_checker(self):
        """Set up a periodic check of hotkey health"""
        # Check hotkeys every 30 seconds
        self.hotkey_check_interval = 30000  # 30 seconds in milliseconds
        
        def check_hotkey_health():
            # Only run the check if auto hotkey refresh is enabled
            if self.auto_hotkey_refresh.get():
                # Check if any hotkeys are registered
                if not self.hotkey_manager.verify_hotkeys():
                    print("Hotkey health check failed - refreshing hotkeys")
                    self.hotkey_manager.force_hotkey_refresh()
                else:
                    print("Hotkey health check passed")
            else:
                print("Hotkey health check skipped - auto refresh disabled")
                
            # Always schedule next check, even if disabled (in case user enables it later)
            self.after(self.hotkey_check_interval, check_hotkey_health)
        
        # Start the periodic check
        self.after(self.hotkey_check_interval, check_hotkey_health)

    def save_auto_hotkey_refresh(self):
        """Save the auto hotkey refresh setting to settings.json."""
        self.config_manager.auto_hotkey_refresh = self.auto_hotkey_refresh.get()
        self.config_manager.save_settings()
        print(f"Auto hotkey refresh setting saved: {self.auto_hotkey_refresh.get()}")

    def toggle_dark_mode(self):
        """Toggle between dark and light mode and save the setting."""
        is_dark = self.dark_mode.get()
        self.config_manager.dark_mode = is_dark
        self.config_manager.save_settings()
        self.ui_manager.apply_theme(is_dark)
        print(f"Dark mode setting saved: {is_dark}")

    def _on_language_change(self):
        """Handle runtime language change by rebuilding menus and refreshing UI."""
        # Update window title
        self.title(f"{_('Quick Whisper by Scorchsoft.com (Speech to Copy Edited Text)')} - v{self.version}")

        # Rebuild menus with new translations
        # Destroy old menus first
        if hasattr(self, 'file_menu'):
            self.file_menu.destroy()
        if hasattr(self, 'settings_menu'):
            self.settings_menu.destroy()
        if hasattr(self, 'actions_menu'):
            self.actions_menu.destroy()
        if hasattr(self, 'help_menu'):
            self.help_menu.destroy()

        # Recreate menus
        self.create_menu()

        # Update menu button labels in UI manager
        if hasattr(self, 'ui_manager'):
            self.ui_manager.refresh_translations()

    def change_language(self, lang_code: str):
        """Change the application language and refresh the UI.

        Args:
            lang_code: The language code to switch to (e.g., 'fr', 'de', 'zh_CN')
        """
        set_language(lang_code, refresh_ui=True)

        # Save to config
        self.config_manager.language = lang_code
        self.config_manager.save_settings()

        print(f"Language changed to: {lang_code}")

    def restart_application(self):
        """Restart the application to apply settings that require a restart."""
        import subprocess

        # Clean up resources
        self.on_closing()

        # Get the command to restart
        python = sys.executable
        script = sys.argv[0]

        # Restart the application
        subprocess.Popen([python, script])

    def setup_system_tray(self):
        """Initialize and show the system tray icon"""
        # Start the tray icon
        success = self.tray_manager.show_tray()
        
        if not success:
            # If we can't create a tray icon, don't change window closing behavior
            messagebox.showwarning(
                _("System Tray Unavailable"),
                _("Could not create system tray icon. Closing the window will exit the application.")
            )
            # Use normal window closing behavior
            self.protocol("WM_DELETE_WINDOW", self.on_closing)
        else:
            # Set up close button behavior to minimize to tray instead of exit
            self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

    def minimize_to_tray(self):
        """Minimize the application to system tray instead of closing"""
        self.tray_manager.minimize_to_tray()

    def update_recording_directory(self):
        """Update the recording directory based on configuration settings."""
        # Load recording location setting from config
        recording_location = self.config_manager.recording_location
        
        if recording_location == "appdata":
            # Use OS-appropriate app data directory
            if platform.system() == "Windows":
                appdata_dir = Path(os.getenv("APPDATA", os.path.expanduser("~"))) / "QuickWhisper"
            elif platform.system() == "Darwin":  # macOS
                appdata_dir = Path.home() / "Library" / "Application Support" / "QuickWhisper"
            else:  # Linux and other Unix-like systems
                appdata_dir = Path.home() / ".config" / "QuickWhisper"
            self.tmp_dir = appdata_dir
        elif recording_location == "custom":
            custom_path = self.config_manager.custom_recording_path
            if custom_path and os.path.exists(custom_path):
                self.tmp_dir = Path(custom_path)
            else:
                # Fallback to alongside if custom path is invalid
                print(f"Warning: Custom recording path '{custom_path}' does not exist. Falling back to 'alongside' option.")
                self.tmp_dir = Path.cwd() / "tmp"
        else:  # Default: alongside
            self.tmp_dir = Path.cwd() / "tmp"
        
        # Ensure the directory exists
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        print(f"Recording directory set to: {self.tmp_dir}")
