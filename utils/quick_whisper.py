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
import platform
import time
import gc
from datetime import datetime

# Note: pynput and pyautogui are imported lazily in paste methods to avoid
# X11 connection errors on Linux when display is not available at import time

# Platform-specific imports
if platform.system() == 'Windows':
    import ctypes
    from ctypes import wintypes

from utils.tooltip import ToolTip
from utils.manage_prompts_dialog import ManagePromptsDialog
from utils.history_dialog import HistoryDialog
from utils.config_dialog import ConfigDialog
from utils.hotkey_manager import HotkeyManager
from utils.audio_manager import AudioManager
from utils.tts_manager import TTSManager
from utils.ui_manager import UIManager, StyledPopupMenu
from utils.version_update_manager import VersionUpdateManager
from utils.system_event_listener import SystemEventListener
from utils.tray_manager import TrayManager, tray_supported
from utils.theme import init_theme, get_window_size, get_font, get_font_size, get_font_family, get_button_height, get_spacing, get_feature_icons, theme_colors
from utils.platform import open_url
from utils.app_version import APP_VERSION
from utils.i18n import _, _n, init_i18n, set_language, get_current_language, register_refresh_callback, unregister_refresh_callback, SUPPORTED_LANGUAGES
from utils.dialog_utils import position_dialog, bind_dialog_keys, focus_first
from utils.app_logging import get_logger, setup_logging
from utils.paths import (
    resource_path as _resource_path,
    get_prompts_path,
    get_history_path,
    get_log_dir,
    get_user_data_dir,
    get_default_recording_dir,
    consume_migration_note,
)

logger = get_logger(__name__)


class QuickWhisper(tk.Tk):

    # Ceiling on any single OpenAI call. Without one a hung request pins the
    # status line on "Processing..." forever with nothing the user can do; the
    # value is generous enough for a full-length recording to upload.
    API_TIMEOUT_SECONDS = 180.0

    def __init__(self):
        # Logging first: the packaged build has no console, so anything logged
        # before this point would be lost entirely.
        setup_logging()
        self._install_exception_logging()

        super().__init__()

        # Hide window during initialization to prevent partial rendering flash
        self.withdraw()

        self.version = APP_VERSION

        self.is_mac = platform.system() == 'Darwin'

        # Apply HiDPI scaling for better display on high-resolution monitors
        self._apply_hidpi_scaling()

        # Initialize theme system with HiDPI awareness
        is_hidpi = getattr(self, 'hidpi_scale_factor', 1.0) > 1.0
        init_theme(is_hidpi=is_hidpi)

        # The title bar is wayfinding - it is what the taskbar, alt-tab and the
        # window list show, and they truncate. The product name alone is what
        # identifies it there; the strapline and version live in Help > About.
        self.title(self._window_title())

        # Initialize prompts
        self.prompts = self.load_prompts()  # Assuming you have a method to load prompts
        # The widgets are built before set_default_prompt() runs, and the status
        # line names the selected prompt, so it has to exist by then.
        self.current_prompt_name = "Default"

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
        self.transcription_model = "gpt-transcribe"
        self.transcription_model_type = "gpt"  # Can be "gpt" or "whisper"
        self.ai_model = "gpt-5.6-luna"
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
            # get_api_key() has already explained and torn the window down;
            # a second dialog here just made the user dismiss the same news
            # twice on their way out.
            return

        openai.api_key = self.api_key
        self.client = OpenAI(api_key=self.api_key, timeout=self.API_TIMEOUT_SECONDS)
        self.selected_device = tk.StringVar()
        self.auto_copy = tk.BooleanVar(value=True)
        self.auto_paste = tk.BooleanVar(value=True)
        # Transcription/edit history. Kept to config.history_limit entries and
        # (optionally) persisted between sessions.
        self.history = []
        self.history_index = -1  # -1 indicates no history selected yet
        self.max_history_length = self.config_manager.history_limit
        self.persist_history = self.config_manager.persist_history
        self._history_path = get_history_path()
        self.load_history()
        self.current_button_mode = "transcribe" # "transcribe" or "edit"
        self._rerun_in_progress = False
        # True from the moment a recording stops until its transcription (and
        # any AI edit) finishes, so a second record request can be answered
        # instead of silently racing the one in flight.
        self._processing = False
        # Bumped whenever processing is abandoned, so a late result from a
        # thread the user already gave up on is discarded rather than pasted.
        self._processing_generation = 0
        # Guards the completion receipt against clobbering a newer status.
        self._receipt_token = 0
        # Serialises the read/write/restore sequence around auto-paste so two
        # transcriptions finishing close together cannot interleave.
        self._clipboard_lock = threading.Lock()
        # What to put back after an auto-paste, what we put on the clipboard to
        # get there, and a counter so only the most recent paste owns the
        # restore. All three are guarded by _clipboard_lock.
        self._clipboard_snapshot = None
        self._last_pasted_text = None
        self._clipboard_generation = 0
        
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

        # Setup periodic memory diagnostics (logs every 60s to console)
        self._setup_memory_diagnostics()
        
        # Register hotkeys. The result is kept rather than discarded: on
        # Wayland, on macOS without Accessibility permission, or behind a failed
        # Windows hook, registration fails and the app would otherwise look
        # perfectly healthy while every shortcut silently did nothing. The
        # status bar does not exist yet, so the notice waits until it does.
        self._initial_hotkeys_ok = self.hotkey_manager.register_hotkeys()

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
                messagebox.showwarning(
                    _("Prompt Not Found"),
                    _("Selected prompt '{name}' not found. Using default prompt.").format(name=saved_prompt))
                self.current_prompt_name = "Default"

        # After loading the prompt from env, update the model label
        self.update_model_label()

        # Now that the status bar exists, say so if the shortcuts never came up.
        if not self._initial_hotkeys_ok:
            logger.warning("Global hotkeys did not register at startup")
            self.hotkey_manager.report_hotkeys_unavailable()
        elif getattr(self, '_show_ready_hint', False):
            # First run: point at the shortcut rather than saying "Idle" to
            # someone who has just this second finished setting the app up.
            shortcut = self.hotkey_manager.display_shortcut(
                'record_edit', "Ctrl+Alt+J")
            self._set_status(
                _("Ready - press {shortcut} to dictate").format(shortcut=shortcut),
                "success")
            self.after(8000, lambda: self._set_status(_("Idle"), "idle"))

        # Add binding for window state changes
        self.bind('<Unmap>', self._handle_minimize)
        self.bind('<Map>', self._handle_restore)
        self.was_minimized = False

        # Escape is what everyone reaches for to abandon something. Bound on
        # the main window (not globally) so it only applies when Quick Whisper
        # has focus, and it does nothing at all when not recording.
        self.bind('<Escape>', self._handle_escape)

        # Ensure default bindings for common edit actions in Text and Entry widgets
        self._install_text_bindings()
        
        # Initialize system tray
        self.setup_system_tray()

        # Check for updates in a separate thread
        self.version_manager.start_check()

        # Show window now that all widgets are created (prevents partial rendering flash)
        self.update_idletasks()  # Process all pending layout calculations
        self.deiconify()

        # Restore the history view (text area + navigation button states) now
        # that the widgets exist.
        if self.history:
            self.history_index = len(self.history) - 1
            try:
                self.ui_manager.update_transcription_text()
                self.ui_manager.update_navigation_buttons()
            except Exception as e:
                logger.warning("Could not restore history view: %s", e)

        # Tell the user once if their configuration was migrated out of the
        # working directory (see utils/paths.py).
        self._announce_config_migration()

        # Schedule UI update for shortcuts after everything is initialized
        def after_init():
            if hasattr(self, 'hotkey_manager') and self.hotkey_manager:
                self.hotkey_manager.update_shortcut_displays()
            self._register_retry_shortcut()

        # Delay to ensure UI is fully ready
        self.after(200, after_init)

    def _install_exception_logging(self):
        """Route unhandled exceptions to the log file.

        In a windowed (no console) build an unhandled exception simply
        disappears, which makes bug reports impossible to act on. Both the
        interpreter hook and Tk's own callback hook are redirected here.
        """
        previous_hook = sys.excepthook

        def _log_unhandled(exc_type, exc_value, exc_tb):
            if issubclass(exc_type, KeyboardInterrupt):
                previous_hook(exc_type, exc_value, exc_tb)
                return
            logger.error("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
            try:
                previous_hook(exc_type, exc_value, exc_tb)
            except Exception:
                pass

        sys.excepthook = _log_unhandled

        # Tk swallows callback errors into its own reporter; send those to the
        # log too so hotkey/menu callbacks leave a trace.
        def _report_callback_exception(exc_type, exc_value, exc_tb):
            logger.error("Unhandled exception in Tk callback",
                         exc_info=(exc_type, exc_value, exc_tb))

        self.report_callback_exception = _report_callback_exception

    def _announce_config_migration(self):
        """Log and (once) show any legacy configuration migration note."""
        note = consume_migration_note()
        if not note:
            return
        logger.info(note)

        def _show():
            messagebox.showinfo(
                _("Settings Location Updated"),
                _("Your Quick Whisper settings were moved so they are found no "
                  "matter which folder the app is launched from.\n\n"
                  "New location:\n{location}").format(location=get_prompts_path().parent)
            )

        # Non-blocking: let the window finish appearing first.
        self.after(1200, _show)

    def open_log_folder(self):
        """Open the folder containing the application log files."""
        log_dir = get_log_dir()
        logger.info("Opening log folder: %s", log_dir)
        try:
            system = platform.system()
            if system == 'Windows':
                os.startfile(str(log_dir))  # noqa: S606 - platform API
            elif system == 'Darwin':
                import subprocess
                subprocess.Popen(['open', str(log_dir)])
            else:
                # Linux: xdg-open handles file managers; fall back to a file URL
                # so WSL and unusual desktops still get somewhere useful.
                import subprocess
                try:
                    subprocess.Popen(['xdg-open', str(log_dir)])
                except (FileNotFoundError, OSError):
                    if not open_url(log_dir.as_uri()):
                        raise RuntimeError("no handler available")
        except Exception as e:
            logger.warning("Could not open log folder %s: %s", log_dir, e)
            messagebox.showinfo(
                _("Log Folder"),
                _("Could not open the log folder automatically.\n\nIt is here:\n{path}").format(path=log_dir)
            )

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

        logger.info(f"HiDPI mode setting: {hidpi_mode}")

        # Skip scaling if disabled
        if hidpi_mode == "disabled":
            logger.info("HiDPI scaling disabled by user setting")
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

                logger.info(f"Windows screen info: {screen_width}x{screen_height}, current Tk scaling: {current_scaling:.2f}")

                # For both "auto" and "enabled" modes, set DPI awareness for sharp rendering
                try:
                    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
                    logger.info("Set per-monitor DPI awareness")
                except (AttributeError, OSError):
                    try:
                        ctypes.windll.user32.SetProcessDPIAware()
                        logger.info("Set system DPI awareness (fallback)")
                    except (AttributeError, OSError):
                        logger.error("Could not set DPI awareness")

                # Get actual system DPI
                try:
                    dpi = ctypes.windll.user32.GetDpiForSystem()
                except (AttributeError, OSError):
                    hdc = ctypes.windll.user32.GetDC(0)
                    dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
                    ctypes.windll.user32.ReleaseDC(0, hdc)

                logger.info(f"Windows detected DPI: {dpi}")

                if hidpi_mode == "enabled":
                    # User explicitly enabled HiDPI - always apply scaling
                    scale_factor = dpi / 96.0
                    scale_factor = max(1.0, min(scale_factor, 2.5))  # Clamp between 1.0 and 2.5

                    self.tk.call('tk', 'scaling', scale_factor)
                    self.hidpi_scale_factor = scale_factor
                    logger.info(f"Windows HiDPI enabled: DPI={dpi}, applied {scale_factor:.2f}x scaling")
                else:
                    # Auto mode: Detect if HiDPI is needed based on resolution and DPI
                    scale_factor = None
                    
                    # Strategy 1: Detect high-resolution displays by pixel count
                    if screen_width >= 3840 or screen_height >= 2160:
                        # 4K display - use 2x scaling
                        scale_factor = 2.0
                        logger.info(f"Detected 4K+ display ({screen_width}x{screen_height}), using 2x scaling")
                    elif screen_width >= 2560 or screen_height >= 1440:
                        # QHD/2K display - use 1.5x scaling
                        scale_factor = 1.5
                        logger.info(f"Detected QHD+ display ({screen_width}x{screen_height}), using 1.5x scaling")
                    elif screen_width >= 1920 and dpi > 96:
                        # Full HD with high DPI (Windows scaling applied) - use DPI-based scaling
                        scale_factor = dpi / 96.0
                        scale_factor = max(1.25, min(scale_factor, 2.5))  # At least 1.25x, cap at 2.5x
                        logger.info(f"Detected Full HD with high DPI ({dpi}), using {scale_factor:.2f}x scaling")
                    
                    # Strategy 2: Fall back to DPI-based detection for any high DPI display
                    if scale_factor is None and dpi > 96 * 1.1:  # 10% threshold above 96
                        scale_factor = dpi / 96.0
                        scale_factor = min(scale_factor, 2.5)  # Cap at 2.5x
                        logger.info(f"Using DPI-based scaling: {scale_factor:.2f}x")
                    
                    # Apply scaling if we determined one
                    if scale_factor and scale_factor > 1.0:
                        self.tk.call('tk', 'scaling', scale_factor)
                        self.hidpi_scale_factor = scale_factor
                        logger.info(f"Windows auto mode: HiDPI scaling applied: {scale_factor:.2f}x")
                    else:
                        logger.info("Windows auto mode: No HiDPI scaling needed")

            except Exception as e:
                logger.error(f"Could not apply HiDPI scaling on Windows: {e}")

        elif system == 'Linux':
            # Linux: Multiple strategies for HiDPI detection
            # WSL and some X11 setups don't report DPI correctly
            try:
                scale_factor = None
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()
                screen_dpi = self.winfo_fpixels('1i')
                current_scaling = float(self.tk.call('tk', 'scaling'))

                logger.info(f"Screen info: {screen_width}x{screen_height}, reported DPI: {screen_dpi:.0f}, current Tk scaling: {current_scaling:.2f}")

                # If user forced HiDPI mode, use aggressive scaling
                if hidpi_mode == "enabled":
                    # User wants HiDPI - determine appropriate scale based on resolution
                    if screen_width >= 3840 or screen_height >= 2160:
                        scale_factor = 2.0
                    elif screen_width >= 2560 or screen_height >= 1440:
                        scale_factor = 1.75
                    else:
                        scale_factor = 1.5  # Default forced scaling
                    logger.info(f"HiDPI forced enabled, using {scale_factor}x scaling")
                else:
                    # Auto-detect mode
                    # Strategy 1: Check environment variables (set by desktop environments)
                    env_scale = os.environ.get('GDK_SCALE') or os.environ.get('QT_SCALE_FACTOR')
                    if env_scale:
                        try:
                            scale_factor = float(env_scale)
                            logger.info(f"Using environment scale factor: {scale_factor}")
                        except ValueError:
                            pass

                    # Strategy 2: Detect high-resolution displays by pixel count
                    # Common HiDPI resolutions: 2560x1440 (QHD), 3840x2160 (4K), 2880x1800 (Retina)
                    if scale_factor is None:
                        if screen_width >= 3840 or screen_height >= 2160:
                            # 4K display - use 2x scaling
                            scale_factor = 2.0
                            logger.info(f"Detected 4K+ display ({screen_width}x{screen_height}), using 2x scaling")
                        elif screen_width >= 2560 or screen_height >= 1440:
                            # QHD/2K display - use 1.5x scaling
                            scale_factor = 1.5
                            logger.info(f"Detected QHD+ display ({screen_width}x{screen_height}), using 1.5x scaling")
                        elif screen_width >= 1920 and screen_dpi > 96:
                            # Full HD with high DPI - modest scaling
                            scale_factor = 1.25
                            logger.info("Detected Full HD with high DPI, using 1.25x scaling")

                    # Strategy 3: Fall back to DPI-based calculation
                    if scale_factor is None and screen_dpi > 96 * 1.1:
                        scale_factor = screen_dpi / 96.0
                        scale_factor = min(scale_factor, 2.5)  # Cap at 2.5x
                        logger.info(f"Using DPI-based scaling: {scale_factor:.2f}x")

                # Apply scaling if we determined one
                if scale_factor and scale_factor > 1.0:
                    self.tk.call('tk', 'scaling', scale_factor)
                    self.hidpi_scale_factor = scale_factor
                    logger.info(f"HiDPI scaling applied: {scale_factor:.2f}x")
                elif current_scaling < 1.0:
                    # Ensure minimum scaling of 1.0
                    self.tk.call('tk', 'scaling', 1.0)
                    logger.info(f"Applied minimum Tk scaling: 1.0 (was {current_scaling:.2f})")

            except Exception as e:
                logger.error(f"Could not apply HiDPI scaling on Linux: {e}")

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
        logger.info(f"Loaded transcription model: '{self.transcription_model}'")
        
        self.transcription_model_type = self.config_manager.transcription_model_type
        # Determine model type from name if not set
        if not self.transcription_model_type or self.transcription_model_type == "unknown":
            if "gpt" in self.transcription_model.lower():
                self.transcription_model_type = "gpt"
            else:
                self.transcription_model_type = "whisper"
        logger.info(f"Loaded model type: '{self.transcription_model_type}'")

        self.ai_model = self.config_manager.ai_model
        logger.info(f"Loaded AI model: '{self.ai_model}'")

        self.whisper_language = self.config_manager.whisper_language
        logger.info(f"Loaded whisper language: '{self.whisper_language}'")

        # Load keyboard shortcuts from config
        self.shortcuts = {
            'record_edit': self.config_manager.get_shortcut('record_edit'),
            'record_transcribe': self.config_manager.get_shortcut('record_transcribe'),
            'cancel_recording': self.config_manager.get_shortcut('cancel_recording'),
            'cycle_prompt_back': self.config_manager.get_shortcut('cycle_prompt_back'),
            'cycle_prompt_forward': self.config_manager.get_shortcut('cycle_prompt_forward'),
            'retry_last': self.config_manager.get_shortcut('retry_last') or self.default_retry_shortcut()
        }

    def default_retry_shortcut(self):
        """Default 'retry last recording' shortcut for this platform.

        Deliberately clear of the five existing shortcuts (record edit/
        transcribe, cancel, and the two prompt-cycle keys).
        """
        return "command+alt+r" if self.is_mac else "ctrl+alt+r"

    def _register_retry_shortcut(self):
        """Make the retry shortcut visible and usable.

        The global hotkey tables live in utils/platform/hotkey_*.py, which only
        know about the original five shortcuts. Rather than silently dropping
        the new one we (a) publish it into the hotkey manager's shortcut map so
        it appears in - and can be re-bound from - the Keyboard Shortcut Mapping
        dialog, and (b) bind it locally on the main window so it works whenever
        Quick Whisper has focus, even if the global hook does not know it.
        """
        combo = self.shortcuts.get('retry_last') or self.default_retry_shortcut()
        try:
            manager = getattr(self, 'hotkey_manager', None)
            inner = getattr(manager, 'hotkey_manager', manager)
            shortcuts = getattr(inner, 'shortcuts', None)
            if isinstance(shortcuts, dict):
                shortcuts.setdefault('retry_last', combo)
        except Exception as e:
            logger.debug("Could not publish retry shortcut to hotkey manager: %s", e)

        # Local (window-focused) binding as a graceful fallback.
        binding = self._tk_binding_for_shortcut(combo)
        if not binding:
            logger.info("No local Tk binding available for retry shortcut '%s'", combo)
            return
        try:
            self.bind_all(binding, lambda e: self.retry_last_recording())
            logger.info("Retry shortcut bound locally as %s (%s)", combo, binding)
        except Exception as e:
            logger.warning("Could not bind retry shortcut '%s': %s", combo, e)

    @staticmethod
    def _tk_binding_for_shortcut(combo):
        """Translate a 'ctrl+alt+r' style shortcut into a Tk binding string.

        Returns None when the combination cannot be represented (in which case
        the local fallback is simply skipped).
        """
        if not combo:
            return None
        modifier_map = {
            'ctrl': 'Control', 'control': 'Control',
            'alt': 'Alt', 'shift': 'Shift',
            'win': 'Super', 'super': 'Super', 'command': 'Command', 'cmd': 'Command',
        }
        parts = [p.strip().lower() for p in combo.split('+') if p.strip()]
        modifiers, keys = [], []
        for part in parts:
            if part in modifier_map:
                modifiers.append(modifier_map[part])
            else:
                keys.append(part)
        if len(keys) != 1 or len(keys[0]) != 1:
            return None
        return "<" + "-".join(modifiers + [keys[0]]) + ">"

    def get_api_key(self):
        """Get the OpenAI API key, prompting if not found."""
        api_key = self.config_manager.openai_api_key
        if not api_key:  # Prompt for the key if it's not set
            # Ensure the main window is visible and on top before showing the dialog
            try:
                self.deiconify()
                self.lift()
                self.attributes("-topmost", True)
            except Exception:
                pass

            api_key = self.openai_key_dialog(first_run=True)

            # Release the topmost flag after showing the dialog
            try:
                self.attributes("-topmost", False)
            except Exception:
                pass
            if api_key:
                self.save_api_key(api_key)
                # The whole of onboarding, in one line: name the shortcut that
                # does the thing the app exists for.
                self._show_ready_hint = True
            else:
                messagebox.showwarning(
                    _("API Key Needed"),
                    _("Quick Whisper can't transcribe without an OpenAI API key.\n\n"
                      "You can add one later from Settings > Change API Key."))
                self.destroy()  # Exit if no key is provided
        return api_key
    
    def change_api_key(self):
        """Open the dialog to change the OpenAI API key."""
        new_key = self.openai_key_dialog()
        if new_key:
            self.save_api_key(new_key)
            self.api_key = new_key
            # Rebuild the client so the new key takes effect immediately
            # instead of only after a restart.
            openai.api_key = new_key
            self.client = OpenAI(api_key=new_key, timeout=self.API_TIMEOUT_SECONDS)
            self._toast(_("API key updated"))


    def openai_key_dialog(self, first_run=False):
        """Ask for an OpenAI API key.

        On first run this is the whole of the app's onboarding, so it is framed
        as a welcome and says where the key is kept; opened from the menu later
        it is simply a change-key dialog.
        """
        from utils.ui_manager import set_dark_title_bar
        import sv_ttk

        colors = theme_colors()
        THEME_ACCENT = colors.ACCENT_PRIMARY
        THEME_ACCENT_HOVER = colors.ACCENT_HOVER

        dialog = tk.Toplevel(self)
        dialog.title(_("Welcome to Quick Whisper") if first_run
                     else _("Change OpenAI API Key"))

        # Typing a key must not fire the global record shortcut underneath the
        # dialog - alarming at the best of times, more so while pasting a secret.
        hotkeys_paused = False
        try:
            if hasattr(self, 'hotkey_manager'):
                self.hotkey_manager.pause()
                hotkeys_paused = True
        except Exception as e:
            logger.debug("Could not pause hotkeys for the API key dialog: %s", e)

        # Get window dimensions from theme
        dialog_width, dialog_height = get_window_size('api_key_dialog')

        # On first run this dialog opens before the main window is laid out,
        # so centring on the parent would place it against a 1x1 window.
        position_dialog(dialog, dialog_width, dialog_height, self)
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
        if first_run:
            heading = ttk.Label(
                content_frame,
                text=_("Welcome to Quick Whisper"),
                font=get_font('lg', 'bold')
            )
            heading.pack(pady=(0, 6))
            instruction_text = _(
                "Quick Whisper needs an OpenAI API key to turn your speech into "
                "text. It is stored encrypted on this computer.")
        else:
            instruction_text = _("Enter your OpenAI API key below:")

        instruction_label = ttk.Label(
            content_frame,
            text=instruction_text,
            font=font_xs,
            wraplength=380,
            justify=tk.CENTER,
        )
        instruction_label.pack(pady=(5, 12))

        # Entry field for the API key, with a reveal toggle - a mistyped
        # character in a masked 50-character secret is otherwise unfindable.
        entry_row = ttk.Frame(content_frame)
        entry_row.pack(fill=tk.X, pady=(0, 12))
        # Narrow enough that the reveal toggle beside it is not squeezed out;
        # it still fills the row because it expands.
        api_key_entry = ttk.Entry(entry_row, show='*', width=30, font=font_xs)
        api_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        # Provide standard context menu and key bindings
        self._attach_entry_context_menu(api_key_entry)

        show_key = tk.BooleanVar(value=False)

        def toggle_reveal():
            api_key_entry.configure(show='' if show_key.get() else '*')

        reveal = ttk.Checkbutton(entry_row, text=_("Show"), variable=show_key,
                                 command=toggle_reveal, cursor="hand2")
        reveal.pack(side=tk.LEFT, padx=(8, 0))

        # Link to guidance - styled for dark mode visibility
        # Get background color to match theme
        bg_color = colors.BG_TERTIARY if self.dark_mode.get() else colors.BG_PRIMARY
        link_label = tk.Label(
            content_frame,
            text=_("How to obtain an OpenAI API key"),
            fg=THEME_ACCENT,
            bg=bg_color,
            cursor="hand2",
            font=font_link
        )
        link_label.pack(pady=(0, 15))
        link_label.bind("<Button-1>", lambda e: open_url("https://scorchsoft.com/howto-get-openai-api-key"))
        link_label.bind("<Enter>", lambda e: link_label.config(fg=THEME_ACCENT_HOVER))
        link_label.bind("<Leave>", lambda e: link_label.config(fg=THEME_ACCENT))

        # Status line used while the key is being checked against the API.
        status_label = ttk.Label(content_frame, text="", font=font_xs)
        status_label.pack(pady=(0, 8))

        # Variable to store the API key input
        entered_key = None

        def finish(key):
            """Accept the key and close the dialog."""
            nonlocal entered_key
            entered_key = key
            if dialog.winfo_exists():
                dialog.destroy()

        def on_validation_result(key, ok, detail):
            """Handle the outcome of the background validation (main thread)."""
            if not dialog.winfo_exists():
                return
            status_label.configure(text="")
            save_button.configure(state=tk.NORMAL)

            if ok:
                finish(key)
                self._toast(_("API key verified"))
                return

            # Let the user save anyway - they may be offline or behind a proxy.
            if messagebox.askyesno(
                _("Could Not Verify API Key"),
                _("The API key could not be verified:\n\n{error}\n\n"
                  "This can also happen when you are offline or behind a proxy.\n\n"
                  "Save this key anyway?").format(error=detail),
                parent=dialog
            ):
                finish(key)

        # Save action to capture API key input
        def save_and_close():
            key = api_key_entry.get().strip()
            if not key:
                messagebox.showwarning(_("Input Required"),
                                       _("Please enter a valid API key."), parent=dialog)
                return

            # Cheap local sanity check first - an obviously wrong string should
            # fail instantly rather than after a network round trip.
            problem = self._api_key_format_problem(key)
            if problem:
                if messagebox.askyesno(
                    _("Key Does Not Look Right"),
                    _("{problem}\n\nSave it anyway?").format(problem=problem),
                    parent=dialog
                ):
                    finish(key)
                return

            status_label.configure(text=_("Checking key with OpenAI..."))
            save_button.configure(state=tk.DISABLED)

            def worker():
                ok, detail = self._validate_api_key(key)
                # Back to the main thread for anything touching widgets.
                self.after(0, lambda: on_validation_result(key, ok, detail))

            threading.Thread(target=worker, daemon=True, name="api-key-check").start()

        # Buttons frame for horizontal layout
        buttons_frame = ttk.Frame(content_frame)
        buttons_frame.pack(pady=(0, 5))

        # Get button font from theme
        font_button = get_font('sm')

        # Secondary on the left, primary on the right - the same order as the
        # Configuration dialog, which this one used to contradict.
        cancel_button = ttk.Button(buttons_frame, text=_("Cancel"), command=dialog.destroy, width=12, cursor="hand2")
        cancel_button.pack(side=tk.LEFT, padx=(0, 8))
        cancel_button.configure(style='Dialog.TButton')

        save_button = ttk.Button(buttons_frame, text=_("Save"), command=save_and_close, width=12, cursor="hand2")
        save_button.pack(side=tk.LEFT)
        save_button.configure(style='Dialog.TButton')

        # Configure button style with theme font
        style = ttk.Style()
        style.configure('Dialog.TButton', font=font_button)

        # Enter saves, Escape cancels.
        bind_dialog_keys(dialog, on_cancel=dialog.destroy, on_accept=save_and_close)

        # Set focus to the entry field and make dialog modal
        api_key_entry.focus()
        dialog.transient(self)
        dialog.wait_visibility()  # Wait for dialog to be visible before grabbing (Linux fix)
        dialog.grab_set()
        try:
            self.wait_window(dialog)
        finally:
            if hotkeys_paused:
                try:
                    self.hotkey_manager.resume()
                except Exception as e:
                    logger.debug("Could not resume hotkeys after the API key dialog: %s", e)

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
            logger.error(f"Error installing text bindings: {e}")

    def _attach_entry_context_menu(self, entry_widget):
        try:
            entry_widget.bind("<Button-3>", self._show_entry_context_menu)
            entry_widget.bind("<Control-a>", lambda e: (e.widget.selection_range(0, 'end'), "break"))
            entry_widget.bind("<Control-A>", lambda e: (e.widget.selection_range(0, 'end'), "break"))
        except Exception as e:
            logger.error(f"Error attaching entry context menu: {e}")

    def _show_text_context_menu(self, event):
        widget = event.widget
        menu = Menu(self, tearoff=0)
        try:
            menu.add_command(label=_("Cut"), command=lambda: widget.event_generate('<<Cut>>'))
            menu.add_command(label=_("Copy"), command=lambda: widget.event_generate('<<Copy>>'))
            menu.add_command(label=_("Paste"), command=lambda: widget.event_generate('<<Paste>>'))
            menu.add_separator()
            menu.add_command(label=_("Select All"), command=lambda: widget.tag_add("sel", "1.0", "end-1c"))
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_entry_context_menu(self, event):
        widget = event.widget
        menu = Menu(self, tearoff=0)
        try:
            menu.add_command(label=_("Cut"), command=lambda: widget.event_generate('<<Cut>>'))
            menu.add_command(label=_("Copy"), command=lambda: widget.event_generate('<<Copy>>'))
            menu.add_command(label=_("Paste"), command=lambda: widget.event_generate('<<Paste>>'))
            menu.add_separator()
            menu.add_command(label=_("Select All"), command=lambda: widget.selection_range(0, 'end'))
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()


    @staticmethod
    def _api_key_format_problem(api_key):
        """Return a human-readable problem with the key's shape, or None.

        Purely local: catches the common paste mistakes (whitespace, a
        truncated key, the wrong string entirely) without a network call.
        """
        if not api_key:
            return _("The key is empty.")
        if any(c.isspace() for c in api_key):
            return _("The key contains spaces or line breaks, which OpenAI keys never do.")
        if not api_key.startswith("sk-"):
            return _("OpenAI API keys start with 'sk-'.")
        if len(api_key) < 20:
            return _("The key looks too short to be complete.")
        return None

    def _validate_api_key(self, api_key):
        """Check a key against the API with one cheap call.

        Runs on a background thread - it must not touch any widget.

        Returns:
            Tuple of (ok, detail) where detail describes the failure.
        """
        try:
            client = OpenAI(api_key=api_key, timeout=15.0)
            client.models.list()
            logger.info("API key validated successfully")
            return True, ""
        except Exception as e:
            logger.warning("API key validation failed: %s", e)
            detail = str(e).strip() or e.__class__.__name__
            # Keep the dialog readable - API errors can be very long.
            if len(detail) > 300:
                detail = detail[:300] + "..."
            return False, detail

    def save_api_key(self, api_key):
        """Save the API key to credentials.json."""
        self.config_manager.openai_api_key = api_key
        self.config_manager.save_credentials()
        logger.info("OpenAI API key saved")

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
        self.file_menu.add_command(label=_("Browse History..."), command=self.show_history)
        self.file_menu.add_command(label=_("Save Session History"), command=self.save_session_history)
        self.file_menu.add_separator()
        # Only offer "Minimize to Tray" when there is actually a tray to
        # minimise into (the popup menu has no disabled state, so the entry is
        # left out rather than shown greyed).
        if self._tray_is_available():
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
        self.settings_menu.add_checkbutton(label=_("Auto-Refresh Hotkeys"),
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
            label=_("Record + AI Edit"),
            command=lambda: self.toggle_recording("edit"),
            accelerator=self.shortcuts['record_edit']
        )
        self.actions_menu.add_command(
            label=_("Record + Transcribe"),
            command=lambda: self.toggle_recording("transcribe"),
            accelerator=self.shortcuts['record_transcribe']
        )
        self.actions_menu.add_command(
            label=_("Cancel Recording"),
            command=self.cancel_recording,
            accelerator=self.shortcuts['cancel_recording']
        )
        self.actions_menu.add_separator()

        # Retry and re-run actions group
        self.actions_menu.add_command(
            label=_("Retry Last Recording"),
            command=self.retry_last_recording,
            accelerator=self.shortcuts.get('retry_last', '')
        )
        self.actions_menu.add_command(
            label=_("Retry Last Recording as Transcript"),
            command=lambda: self.retry_last_recording("transcribe")
        )
        self.actions_menu.add_command(
            label=_("Retry Last Recording as AI Edit"),
            command=lambda: self.retry_last_recording("edit")
        )
        self.actions_menu.add_separator()
        self.actions_menu.add_command(
            label=_("Re-run AI Edit on Current Text"),
            command=self.rerun_ai_edit
        )
        self.actions_menu.add_command(
            label=_("Re-run AI Edit With Prompt..."),
            command=lambda: self.ui_manager.show_rerun_prompt_menu()
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
        self.help_menu.add_separator()
        self.help_menu.add_command(label=_("Open Log Folder"), command=self.open_log_folder)

    def check_keyboard_shortcuts(self):
        """Test keyboard shortcuts and show status."""
        self.hotkey_manager.check_keyboard_shortcuts()

    def _reject_if_processing(self):
        """Answer a record request that arrives mid-transcription.

        Starting a second recording while one is still being transcribed races
        the in-flight job over current_button_mode and the status line. Say so
        and point at the way out rather than starting silently.
        """
        if not self._processing:
            return False
        logger.info("Record request ignored - still processing the previous recording")
        try:
            self.ui_manager.show_toast(_("Still processing - press Esc to abandon"))
        except Exception as e:
            logger.debug("Could not show the still-processing toast: %s", e)
        return True

    def toggle_recording(self, mode="transcribe"):
        if not self.audio_manager.recording:
            if self._reject_if_processing():
                return
            # Set globally so the app knows when recording stops whether
            # transcript or edit mode was selected
            self.current_button_mode = mode
            logger.info("About to start recording. mode = %s", mode)

            # Recording must NEVER be gated on the state of the global hotkeys.
            # Wayland, X11-less Linux, macOS without Accessibility permission
            # and a failed Windows hook all leave the hotkeys unregistered -
            # and a user clicking the button in the window has already said
            # what they want. Repair the hotkeys opportunistically in the
            # background instead (fire and forget).
            try:
                if not self.hotkey_manager.verify_hotkeys():
                    logger.warning("Hotkeys not functioning correctly; refreshing in the background")
                    self.hotkey_manager.force_hotkey_refresh()
            except Exception as e:
                logger.warning("Hotkey health check failed: %s", e)

            self.start_recording()
        else:
            logger.info("About to stop recording. mode = %s", self.current_button_mode)
            self.stop_recording()

    def start_push_to_talk(self, mode="transcribe"):
        """Begin recording because a record shortcut is being held down.

        Push-to-talk deliberately does nothing when a recording is already
        running: the user may have started one from the buttons, and cutting
        it short because a shortcut was touched would lose their words.
        """
        if self.audio_manager.recording:
            logger.debug("Push-to-talk press ignored - already recording")
            return
        if self._reject_if_processing():
            return
        self.current_button_mode = mode
        logger.info("Push-to-talk recording started (mode=%s)", mode)
        self.start_recording()

    def finish_push_to_talk(self):
        """Stop and process because the held record shortcut was released."""
        if not self.audio_manager.recording:
            logger.debug("Push-to-talk release ignored - not recording")
            return
        logger.info("Push-to-talk recording finished")
        self.stop_recording()

    def start_recording(self):
        """Start audio recording."""
        # audio_manager.start_recording() handles all UI updates including button states
        self.audio_manager.start_recording()

    def stop_recording(self):
        """Stop recording and process audio."""
        audio_file = self.audio_manager.stop_recording()
        if audio_file:
            self._processing = True
            # Start transcription in a separate thread (daemon so a hung
            # request can never keep the application alive after close)
            threading.Thread(target=self.transcribe_audio, daemon=True,
                             name="transcribe").start()
            
    def cancel_recording(self):
        """Cancel the current recording without processing."""
        self.audio_manager.cancel_recording()
        self.hotkey_manager.update_shortcut_displays()

    def _handle_escape(self, _event=None):
        """Cancel an in-progress recording, or abandon a stuck transcription."""
        if self.audio_manager.recording:
            logger.info("Recording cancelled with Escape")
            self.cancel_recording()
            return "break"
        if self._processing:
            logger.info("Processing abandoned with Escape")
            self.abandon_processing()
            return "break"
        return None

    def _toast(self, message):
        """Confirm something routine without a dialog to dismiss.

        Every modal steals focus from whatever the user is dictating into, so
        for a tool whose whole job is pasting into other apps an unnecessary
        one breaks the flow it exists to serve.
        """
        try:
            self.ui_manager.show_toast(message)
        except Exception as e:
            logger.debug("Could not show the '%s' toast: %s", message, e)

    @staticmethod
    def _friendly_api_error(error):
        """Explain an API failure, keeping the raw text as a detail line.

        Raw SDK exceptions are written for developers - a wall of JSON and a
        stack of URLs - and tell the user nothing about what to do next.
        """
        detail = str(error).strip() or error.__class__.__name__
        lowered = detail.lower()
        name = error.__class__.__name__.lower()

        if 'timeout' in lowered or 'timed out' in lowered or 'timeout' in name:
            reason = _("The request took too long and was given up on. This is "
                       "usually a slow or dropped connection.")
        elif 'rate limit' in lowered or '429' in lowered or 'ratelimit' in name:
            reason = _("Your OpenAI account is being rate limited. Wait a moment "
                       "and try again.")
        elif ('authentication' in lowered or 'api key' in lowered
                or 'unauthorized' in lowered or '401' in lowered):
            reason = _("Your OpenAI API key was rejected. Check it under "
                       "Settings > Change API Key.")
        elif ('quota' in lowered or 'insufficient_quota' in lowered
                or 'billing' in lowered):
            reason = _("Your OpenAI account has no available credit.")
        elif ('connection' in lowered or 'network' in lowered
              or 'getaddrinfo' in lowered or 'connection' in name):
            reason = _("Could not reach OpenAI. Check your internet connection.")
        else:
            reason = _("Something went wrong talking to OpenAI.")

        # Long API errors push the useful sentence off the dialog.
        if len(detail) > 300:
            detail = detail[:300] + "..."
        return _("{reason}\n\nDetails: {detail}").format(reason=reason, detail=detail)

    def _is_abandoned(self, generation):
        """Whether the run that started at ``generation`` has been given up on."""
        return generation != self._processing_generation

    def abandon_processing(self):
        """Give up on the transcription in flight and free the UI.

        The request itself cannot be cancelled once the SDK has it, so the
        generation counter is bumped instead: the thread runs to completion but
        its result is discarded rather than pasted somewhere unexpected minutes
        later.
        """
        if not self._processing:
            return
        self._processing_generation += 1
        self._processing = False
        self._set_status(_("Stopped"), "idle")
        try:
            self.ui_manager.show_toast(_("Stopped waiting for the result"))
        except Exception as e:
            logger.debug("Could not show the abandon toast: %s", e)
    
    def retry_last_recording(self, mode=None):
        """Retry processing the last recording.

        Args:
            mode: "edit", "transcribe", or None to reuse whichever mode the
                  recording was originally made with.
        """
        logger.info("Retry last recording requested (mode=%s)", mode or "last used")
        try:
            return self.audio_manager.retry_last_recording(mode)
        except TypeError:
            # Older AudioManager without mode support - still honour the request
            # by setting the mode ourselves before retrying.
            if mode in ("edit", "transcribe"):
                self.current_button_mode = mode
            return self.audio_manager.retry_last_recording()

    def rerun_ai_edit(self, prompt_name=None):
        """Re-run the AI edit over the text currently in the transcript box.

        Lets the user apply a different prompt to something they have already
        dictated without having to dictate it again. ``prompt_name`` applies a
        prompt for this run only, leaving the selected prompt alone - trying
        three tones on one dictation should not change what the next recording
        will use.
        """
        if self._rerun_in_progress:
            logger.info("Re-run AI edit ignored - one is already running")
            messagebox.showinfo(_("Already Running"),
                                _("An AI edit is already in progress. Please wait for it to finish."))
            return

        try:
            source_text = self.ui_manager.transcription_text.get("1.0", "end-1c").strip()
        except Exception as e:
            logger.error("Could not read the transcript box: %s", e, exc_info=True)
            return

        if not source_text:
            messagebox.showinfo(_("Nothing to Edit"),
                                _("There is no text to re-run the AI edit on."))
            return

        if prompt_name is not None and prompt_name not in self.prompt_names():
            logger.warning("Cannot re-run with unknown prompt '%s'", prompt_name)
            messagebox.showwarning(
                _("Prompt Not Found"),
                _("The prompt '{name}' no longer exists.").format(name=prompt_name))
            return

        effective_prompt = prompt_name or self.current_prompt_name
        self._rerun_in_progress = True
        self._set_status(_("Processing - AI Editing..."), "processing")
        logger.info("Re-running AI edit on %d characters using prompt '%s'",
                    len(source_text), effective_prompt)

        threading.Thread(target=self._rerun_ai_edit_worker,
                         args=(source_text, effective_prompt),
                         daemon=True, name="rerun-ai-edit").start()

    def _rerun_ai_edit_worker(self, source_text, prompt_name=None):
        """Background half of :meth:`rerun_ai_edit`."""
        try:
            edited_text = self.process_with_gpt_model(source_text, prompt_name=prompt_name)
            if edited_text is None:
                # process_with_gpt_model has already told the user what failed.
                self._ui_status(_("AI edit failed"), "error")
                return

            edited_text = edited_text.rstrip()
            if not edited_text:
                logger.warning("AI edit returned empty text; leaving the original in place")
                self._ui_status(_("AI edit returned no text"), "error")
                return

            self.last_edit = edited_text
            used_prompt = prompt_name or getattr(self, 'current_prompt_name', None)
            self.after(0, lambda: self.add_to_history(
                edited_text, mode=self.HISTORY_MODE_EDIT, prompt=used_prompt))

            # Same auto-copy/auto-paste behaviour as a normal recording.
            if self.auto_copy.get():
                self.auto_copy_text(edited_text)
            if self.auto_paste.get():
                self.auto_paste_text(edited_text)

            self._ui_status(_("Idle"), "idle")
            logger.info("Re-run AI edit complete (%d characters)", len(edited_text))
        except Exception as e:
            logger.error("Re-run AI edit failed: %s", e, exc_info=True)
            self._ui_status(_("AI edit failed"), "error")
            self._show_error_async(_("AI Edit Error"),
                                   _("An error occurred while re-running the AI edit: {error}").format(error=e))
        finally:
            self._rerun_in_progress = False

    def _set_status(self, message, state="idle", pulsing=None):
        """Set the status text on the main thread.

        ``state`` names what is happening (``idle``, ``processing``,
        ``success``, ``recording``, ``error``) rather than a colour, so the
        palette stays the status line's own business.
        """
        try:
            self.ui_manager.set_status(message, state, pulsing=pulsing)
        except TypeError:
            # UIManager without the explicit pulsing argument.
            self.ui_manager.set_status(message, state)
        except Exception as e:
            logger.debug("Could not set status '%s': %s", message, e)

    def _ui_status(self, message, state="idle", pulsing=None):
        """Set the status text from any thread."""
        try:
            self.after(0, lambda: self._set_status(message, state, pulsing))
        except Exception as e:
            logger.debug("Could not set status '%s': %s", message, e)

    RECEIPT_DURATION_MS = 4000

    def _show_completion_receipt(self, text, spoken_seconds=None):
        """Confirm what was just delivered, then fall back to Idle.

        Success previously snapped straight to "Idle" with only a sound to mark
        it, which left "did that actually paste?" unanswered at exactly the
        moment the user is looking away at their target app.
        """
        chars = len(text or "")
        duration = None
        if spoken_seconds:
            try:
                total = int(round(float(spoken_seconds)))
                duration = f"{total // 60}:{total % 60:02d}"
            except (TypeError, ValueError):
                duration = None

        if duration:
            message = _("Done - {chars} chars - {duration} spoken").format(
                chars=chars, duration=duration)
        else:
            message = _("Done - {chars} chars").format(chars=chars)

        self._receipt_token += 1
        token = self._receipt_token
        self._ui_status(message, "success")

        def revert():
            # Only clear our own receipt: anything that happened since (a new
            # recording, an error) owns the status line now.
            if token != self._receipt_token:
                return
            self._set_status(_("Idle"), "idle")

        try:
            self.after(self.RECEIPT_DURATION_MS, revert)
        except Exception as e:
            logger.debug("Could not schedule the completion receipt reset: %s", e)

    def _show_error_async(self, title, message):
        """Show an error dialog from any thread without blocking the caller."""
        try:
            self.after(0, lambda: messagebox.showerror(title, message))
        except Exception:
            logger.error("%s: %s", title, message)

    def _play_sound_async(self, sound_file):
        """Queue a sound without blocking, tolerating a shut-down sound pool."""
        try:
            player = getattr(self.audio_manager, '_play_async', None)
            if callable(player):
                player(sound_file)
            else:
                self.audio_manager._sound_pool.submit(self.play_sound, sound_file)
        except Exception as e:
            logger.debug("Could not play %s: %s", sound_file, e)

    @staticmethod
    def _extract_transcription_text(transcription):
        """Pull the text out of whatever shape the transcription API returned.

        ``response_format="text"`` yields a plain string, ``verbose_json`` a
        model object (older SDKs returned a dict), so all three are handled.
        """
        if transcription is None:
            return ""
        if isinstance(transcription, str):
            return transcription
        if isinstance(transcription, dict):
            return transcription.get("text", "") or ""
        text = getattr(transcription, "text", None)
        if text:
            return text
        # Last resort for SDK objects that only expose a dict dump.
        for dumper in ("model_dump", "to_dict"):
            fn = getattr(transcription, dumper, None)
            if callable(fn):
                try:
                    return fn().get("text", "") or ""
                except Exception:
                    pass
        return str(transcription)

    def transcribe_audio(self):
        file_path = self.audio_manager.audio_file
        succeeded = False
        # Snapshot the generation so an abandoned run can tell it is no longer
        # the one the user is waiting for.
        generation = self._processing_generation

        try:
            self._ui_status(_("Processing - Transcript..."), "processing")

            if not self.transcription_model or not self.transcription_model.strip():
                self._show_error_async(
                    _("Configuration Error"),
                    _("Transcription model name is empty. Please check your settings.")
                )
                raise ValueError("Empty transcription model name")

            if not file_path or not os.path.exists(str(file_path)):
                self._show_error_async(
                    _("Transcription Error"),
                    _("The recording could not be found. Please try recording again.")
                )
                raise FileNotFoundError(f"Recording not found: {file_path}")

            with open(str(file_path), "rb") as audio_file:

                logger.info("Transcription mode: '%s' | type: '%s'",
                            self.transcription_model, self.transcription_model_type)

                if self.transcription_model_type == "gpt":
                    # GPT speech-to-text API (returns plain text)
                    response_format = "text"
                else:
                    # Traditional Whisper API
                    response_format = "verbose_json"

                try:
                    transcription = self.client.audio.transcriptions.create(
                        file=audio_file,
                        model=self.transcription_model,
                        language=None if self.whisper_language == "auto" else self.whisper_language,
                        response_format=response_format
                    )
                except Exception as e:
                    logger.error("Error calling the transcription API (%s): %s",
                                 self.transcription_model, e, exc_info=True)
                    raise

                transcription_text = self._extract_transcription_text(transcription)

            # Remove any trailing newlines/spaces to avoid moving the caret to a new line on paste
            transcription_text = (transcription_text or "").rstrip()

            if self._is_abandoned(generation):
                logger.info("Discarding transcription - the user stopped waiting for it")
                return

            if not transcription_text:
                logger.warning("Transcription returned no text")
                # A modal here punished a mistyped hotkey with a dialog to
                # dismiss; the red status plus a toast says the same thing at a
                # glance and costs the user nothing.
                self._ui_status(_("No speech detected"), "error")
                self._toast(_("No speech detected"))
                return

            self.last_transcription = transcription_text
            # add_to_history touches widgets, so it must run on the main thread.
            spoken_seconds = getattr(self.audio_manager, 'last_recording_duration', None)
            self.after(0, lambda t=transcription_text, d=spoken_seconds: self.add_to_history(
                t, mode=self.HISTORY_MODE_TRANSCRIPT, duration=d))

            # Process transcription with or without GPT as per the checkbox setting
            if self.current_button_mode == "edit":
                logger.info("AI editing transcription")
                self._ui_status(_("Processing - AI Editing..."), "processing")

                edited_text = self.process_with_gpt_model(transcription_text)
                if edited_text is None or not edited_text.strip():
                    # The edit failed (the user has already been told why) - keep
                    # the raw transcript rather than pasting nothing.
                    logger.warning("AI edit produced no text; falling back to the raw transcript")
                    play_text = transcription_text
                else:
                    play_text = edited_text.rstrip()
                    self.last_edit = play_text
                    prompt_name = self.current_prompt_name
                    self.after(0, lambda t=play_text, p=prompt_name, d=spoken_seconds:
                               self.add_to_history(t, mode=self.HISTORY_MODE_EDIT,
                                                   prompt=p, duration=d))
            else:
                logger.info("Outputting raw transcription only")
                play_text = transcription_text

            if self.auto_copy.get():
                self.auto_copy_text(play_text)

            if self.auto_paste.get():
                self.auto_paste_text(play_text)

            logger.info("Transcription complete (%d characters)", len(play_text))
            succeeded = True
            self._play_sound_async("assets/double-pop-down.wav")

        except Exception as e:
            if self._is_abandoned(generation):
                logger.info("Transcription failed after being abandoned: %s", e)
                return

            # Play failure sound
            self._play_sound_async("assets/wrong-short.wav")

            logger.error("An error occurred during transcription: %s", e, exc_info=True)
            self._ui_status(_("Error during transcription"), "error")

            # Provide a clearer hint for known unsupported/renamed models
            known_models = ("gpt-transcribe", "gpt-4o-transcribe", "gpt-4o-mini-transcribe", "whisper-1")
            if (self.transcription_model or "").strip() not in known_models:
                self._show_error_async(
                    _("Transcription Error"),
                    _("The selected transcription model may be unsupported. Try 'gpt-transcribe' or 'whisper-1'.\n\n"
                      "If you entered a custom model, please verify the exact model name supported by the API.")
                )
            else:
                self._show_error_async(
                    _("Transcription Error"),
                    self._friendly_api_error(e)
                )

        finally:
            # An abandoned run has already handed the status line over to
            # whatever the user did next; it must not clear the flag either,
            # since a newer recording may own it by now.
            if not self._is_abandoned(generation):
                self._processing = False
                # Only replace the processing status when things went well -
                # otherwise the error the user needs to see would be wiped out
                # immediately.
                if succeeded:
                    self.after(0, lambda t=play_text, d=spoken_seconds:
                               self._show_completion_receipt(t, d))

    def copy_last_transcription(self):
        self.copy_to_clipboard(self.last_transcription)

    def copy_last_edit(self):
        self.copy_to_clipboard(self.last_edit)

    def copy_to_clipboard(self, text):
        """Copy text on the user's explicit request (so it is never restored)."""
        with self._clipboard_lock:
            self._abandon_clipboard_restore()
            if self._write_clipboard(text):
                self.ui_manager.show_toast(_("Copied to clipboard"))
                return
        messagebox.showerror(
            _("Copy Failed"),
            _("The text could not be copied to the clipboard."))
        
    def auto_copy_text(self, text):
        with self._clipboard_lock:
            self._abandon_clipboard_restore()
            if self._write_clipboard(text):
                return
        logger.error("Failed to auto-copy the transcription to the clipboard")
        self._show_error_async(
            _("Auto-Copy Error"),
            _("The transcription could not be copied to the clipboard. It is still "
              "shown above and can be copied manually."))

    # Sentinel meaning "the clipboard could not be read", which is different
    # from "the clipboard was empty" - only the latter is safe to restore.
    _CLIPBOARD_UNREADABLE = object()

    def _abandon_clipboard_restore(self):
        """Cancel any pending restore. Must be called holding the lock.

        Used when the user deliberately puts something on the clipboard: they
        have said they want it there, so a restore scheduled moments earlier
        must not snatch it back.
        """
        self._clipboard_generation += 1
        self._clipboard_snapshot = None
        self._last_pasted_text = None

    def _read_clipboard(self):
        """Return the clipboard text, or _CLIPBOARD_UNREADABLE if it cannot be read."""
        try:
            return pyperclip.paste()
        except Exception as e:
            logger.warning("Could not read the clipboard: %s", e)
            return self._CLIPBOARD_UNREADABLE

    def _write_clipboard(self, text, verify=True):
        """Put text on the clipboard, confirming it actually landed.

        pyperclip can fail silently when no clipboard backend is available
        (a headless Linux box with no xclip/xsel, for instance). Pasting in
        that state would send Ctrl+V with somebody else's content still on the
        clipboard, so the write is read back before it is trusted.
        """
        try:
            pyperclip.copy(text)
        except Exception as e:
            logger.error("Could not write to the clipboard: %s", e, exc_info=True)
            return False
        if not verify:
            return True
        try:
            return pyperclip.paste() == text
        except Exception as e:
            # The write did not raise; treat an unreadable clipboard as success
            # rather than blocking the paste on a read-only failure.
            logger.debug("Could not verify the clipboard write: %s", e)
            return True

    def _take_clipboard_snapshot(self):
        """Remember what to put back once the pending paste has landed.

        Must be called holding ``_clipboard_lock``. If a restore from an
        earlier paste is still outstanding and the clipboard still holds what
        that paste put there, the *older* snapshot is carried forward -
        otherwise two transcriptions finishing inside the restore window would
        "restore" the first one's dictated text and leave it on the clipboard.
        """
        current = self._read_clipboard()
        pending = self._clipboard_snapshot
        if (pending is not None
                and self._last_pasted_text is not None
                and current == self._last_pasted_text):
            logger.debug("Carrying the earlier clipboard snapshot through a second paste")
            return pending
        return current

    def _schedule_clipboard_restore(self, pasted_text):
        """Put the previous clipboard contents back a moment after pasting.

        Dictated text is often the most sensitive thing the app touches, so it
        is not left sitting on the clipboard once it has been delivered. The
        restore is skipped when the user has copied something else in the
        meantime - their newer copy always wins - and when a newer paste has
        taken over, since that paste owns the restore now.
        """
        with self._clipboard_lock:
            snapshot = self._clipboard_snapshot
            generation = self._clipboard_generation

        if snapshot is self._CLIPBOARD_UNREADABLE:
            # Never guess: clearing a clipboard we could not read risks
            # destroying something the user still wants.
            logger.info("Skipping clipboard restore - the previous contents could not be read")
            return

        delay_seconds = self.config_manager.clipboard_restore_delay_ms / 1000.0

        def _restore():
            time.sleep(delay_seconds)
            with self._clipboard_lock:
                if generation != self._clipboard_generation:
                    logger.debug("A newer paste owns the clipboard restore; standing down")
                    return
                current = self._read_clipboard()
                if current is self._CLIPBOARD_UNREADABLE:
                    return
                if current != pasted_text:
                    logger.debug("Clipboard changed since pasting; leaving it alone")
                    return
                if self._write_clipboard(snapshot, verify=False):
                    logger.info("Previous clipboard contents restored after auto-paste")
                self._clipboard_snapshot = None
                self._last_pasted_text = None

        threading.Thread(target=_restore, daemon=True, name="clipboard-restore").start()

    def _is_foreground_window(self):
        """Whether Quick Whisper itself currently holds the keyboard focus."""
        try:
            if platform.system() == 'Windows':
                import ctypes
                foreground = ctypes.windll.user32.GetForegroundWindow()
                # winfo_id() is the child HWND; walk up to the toplevel.
                own = ctypes.windll.user32.GetAncestor(self.winfo_id(), 2)  # GA_ROOT
                return bool(foreground) and foreground == own
            # Elsewhere, Tk knowing which of our widgets has focus is the
            # signal: focus_get() returns None when another app is in front.
            return self.focus_displayof() is not None
        except Exception as e:
            logger.debug("Could not determine the foreground window: %s", e)
            return False

    def auto_paste_text(self, text):
        """Auto-paste text by putting it on the clipboard and sending Ctrl+V.

        Every paste method here simulates the paste shortcut, so the text has
        to be on the clipboard first - sending the keystroke on its own would
        paste whatever the user happened to have copied earlier.
        """
        try:
            # A paste is aimed at whatever holds the OS focus. When the user
            # started the recording from the buttons in this window - the
            # discoverable path for anyone new - that is Quick Whisper itself,
            # so the keystroke would land in our own transcript box and read as
            # "auto-paste is broken". Put the text on the clipboard and say
            # where to put it instead.
            if self._is_foreground_window():
                logger.info("Skipping auto-paste - Quick Whisper has focus")
                if not self._write_clipboard(text):
                    logger.error("Could not place the text on the clipboard")
                    self._ui_status(_("Clipboard unavailable"), "error")
                    return
                try:
                    self.ui_manager.show_toast(
                        _("Copied - click into your app and press paste"))
                except Exception as e:
                    logger.debug("Could not show the focus-guard toast: %s", e)
                return

            # The text has to be on the clipboard for Ctrl+V to mean anything.
            # When auto-copy is on it is already there and the user wants it to
            # stay; otherwise it is placed there just long enough to paste.
            keep_on_clipboard = bool(self.auto_copy.get())
            restore_after = not keep_on_clipboard and self.config_manager.restore_clipboard

            with self._clipboard_lock:
                if restore_after:
                    self._clipboard_snapshot = self._take_clipboard_snapshot()
                    self._last_pasted_text = text
                    self._clipboard_generation += 1
                if not self._write_clipboard(text):
                    logger.error("Aborting auto-paste - the text is not on the clipboard")
                    # Kept short: the status column reserves room for the
                    # longest message it can ever show, and that reservation
                    # comes out of the space the model/prompt pickers use.
                    self._ui_status(_("Clipboard unavailable"), "error")
                    self._show_error_async(
                        _("Auto-Paste Error"),
                        _("The text could not be placed on the clipboard, so it was not "
                          "pasted. It is still shown above and can be copied manually."))
                    return

            # Small delay before starting to ensure any previous key events are processed
            time.sleep(0.05)

            # Get configured paste method
            paste_method = self.config_manager.paste_method

            # Determine effective method based on config and platform
            if paste_method == "auto":
                # Auto mode: use SendInput on Windows (most reliable), pynput elsewhere
                if platform.system() == 'Windows':
                    paste_method = "sendinput"
                else:
                    paste_method = "pynput"

            # Dispatch to the appropriate paste method
            if paste_method == "sendinput" and platform.system() == 'Windows':
                self._paste_sendinput()
            elif paste_method == "win32api" and platform.system() == 'Windows':
                self._paste_win32api()
            elif paste_method == "pyautogui":
                self._paste_pyautogui()
            elif paste_method == "pynput_legacy":
                self._paste_pynput_legacy()
            else:
                # Default to pynput with delays (also handles non-Windows with sendinput selected)
                self._paste_pynput()

            # Small delay after to ensure paste completes before any other operations
            time.sleep(0.05)

            if restore_after:
                self._schedule_clipboard_restore(text)
        except Exception as e:
            logger.error("Auto-paste error: %s", e, exc_info=True)
            self._show_error_async(_("Auto-Paste Error"),
                                   _("Failed to auto-paste the transcription: {error}").format(error=e))

    def _paste_sendinput(self):
        """Paste using Windows SendInput API - most reliable on Windows."""
        # Virtual key codes
        VK_CONTROL = 0x11
        VK_V = 0x56

        # Input type for keyboard
        INPUT_KEYBOARD = 1
        KEYEVENTF_KEYUP = 0x0002

        # Define the INPUT structure for SendInput
        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
            ]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", wintypes.DWORD),
                ("ki", KEYBDINPUT),
                ("padding", ctypes.c_ubyte * 8)  # Padding to match union size
            ]

        def make_key_input(vk, flags=0):
            """Create an INPUT structure for a key event."""
            inp = INPUT()
            inp.type = INPUT_KEYBOARD
            inp.ki.wVk = vk
            inp.ki.wScan = 0
            inp.ki.dwFlags = flags
            inp.ki.time = 0
            inp.ki.dwExtraInfo = None
            return inp

        # Create the sequence: Ctrl down, V down, V up, Ctrl up
        inputs = (INPUT * 4)()
        inputs[0] = make_key_input(VK_CONTROL)                  # Ctrl down
        inputs[1] = make_key_input(VK_V)                        # V down
        inputs[2] = make_key_input(VK_V, KEYEVENTF_KEYUP)       # V up
        inputs[3] = make_key_input(VK_CONTROL, KEYEVENTF_KEYUP) # Ctrl up

        # Send all inputs at once - this is atomic from Windows' perspective
        ctypes.windll.user32.SendInput(4, ctypes.byref(inputs), ctypes.sizeof(INPUT))

    def _paste_pynput(self):
        """Paste using pynput KeyboardController with timing delays."""
        # Lazy import to avoid X11 connection errors at module load time
        from pynput.keyboard import Controller as KeyboardController, Key
        keyboard_controller = KeyboardController()

        # Add delays between key events to give the OS time to register
        # the modifier key before the character key is pressed.
        if self.is_mac:
            keyboard_controller.press(Key.cmd)
            time.sleep(0.02)  # Give OS time to register Cmd
            keyboard_controller.press('v')
            time.sleep(0.02)  # Brief hold
            keyboard_controller.release('v')
            time.sleep(0.02)  # Brief pause before releasing modifier
            keyboard_controller.release(Key.cmd)
        else:
            keyboard_controller.press(Key.ctrl)
            time.sleep(0.02)  # Give OS time to register Ctrl
            keyboard_controller.press('v')
            time.sleep(0.02)  # Brief hold
            keyboard_controller.release('v')
            time.sleep(0.02)  # Brief pause before releasing modifier
            keyboard_controller.release(Key.ctrl)

    def _paste_pynput_legacy(self):
        """Paste using pynput KeyboardController - original method without delays.

        This is the original implementation before timing fixes were added.
        Some users may find this works better on their systems.
        """
        # Lazy import to avoid X11 connection errors at module load time
        from pynput.keyboard import Controller as KeyboardController, Key
        keyboard_controller = KeyboardController()

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

    def _paste_pyautogui(self):
        """Paste using pyautogui library - alternative cross-platform method."""
        # Lazy import to avoid X11 connection errors at module load time
        import pyautogui
        pyautogui.PAUSE = 0.02  # Small pause between actions
        pyautogui.FAILSAFE = False  # Disable failsafe

        # pyautogui.hotkey handles the key timing automatically
        if self.is_mac:
            pyautogui.hotkey('command', 'v')
        else:
            pyautogui.hotkey('ctrl', 'v')

    def _paste_win32api(self):
        """Paste using win32api keybd_event - older Windows API method.

        Some applications respond better to keybd_event than SendInput.
        This uses the pywin32 package.
        """
        import win32api
        import win32con

        # Virtual key codes
        VK_CONTROL = win32con.VK_CONTROL
        VK_V = 0x56

        # Press Ctrl
        win32api.keybd_event(VK_CONTROL, 0, 0, 0)
        time.sleep(0.02)

        # Press V
        win32api.keybd_event(VK_V, 0, 0, 0)
        time.sleep(0.02)

        # Release V
        win32api.keybd_event(VK_V, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.02)

        # Release Ctrl
        win32api.keybd_event(VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)

    def process_with_gpt_model(self, text, prompt_name=None):
        try:
            # Replace the hardcoded system prompt with the selected one
            system_prompt = self.get_system_prompt(prompt_name)
            
            user_prompt = "Here is the transcription \r\n<transcription>\r\n" + text + "\r\n</transcription>\r\n"


            logger.info(f"About to process with AI Model {self.ai_model}")

            if "gpt-5" in self.ai_model:
                # GPT-5.6 (Sol/Terra/Luna) dropped the "minimal" effort level in favour of
                # none/low/medium/high/xhigh/max - use "low" for fast copy-editing.
                reasoning_effort = "low" if "gpt-5.6" in self.ai_model else "minimal"
                response = self.client.responses.create(
                    model=self.ai_model,
                    instructions=system_prompt,
                    text={"verbosity": "low"},
                    reasoning={"effort": reasoning_effort},
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
            self._play_sound_async("assets/wrong-short.wav")
            logger.error("An error occurred while processing with the AI model: %s", e, exc_info=True)
            self._show_error_async(
                _("AI Processing Error"),
                self._friendly_api_error(e))
            return None
        

    def resource_path(self, relative_path):
        """Absolute path to a bundled resource.

        Delegates to utils.paths.resource_path (which handles the PyInstaller
        _MEIPASS case) so resources no longer depend on the working directory.
        """
        # Handle icon files differently for Mac
        if self.is_mac and relative_path.endswith('.ico'):
            # Use .png version instead of .ico for Mac
            relative_path = relative_path.replace('.ico', '.png')

        return str(_resource_path(relative_path))

    def on_closing(self):
        """Clean up resources before closing."""
        logger.info("Shutting down")

        # Unregister the language change callback first to prevent errors during cleanup
        try:
            unregister_refresh_callback(self._on_language_change)
        except Exception as e:
            logger.debug("Could not unregister language callback: %s", e)

        # Save window position and history for next launch
        self._save_window_position()
        try:
            self.save_history()
        except Exception as e:
            logger.warning("Could not save history on close: %s", e)

        # Each manager is cleaned up independently: one that failed to
        # initialise (or to shut down) must not stop the others being closed.
        cleanup_steps = (
            ("tray_manager", "stop_tray"),
            ("system_event_listener", "stop_listening"),
            ("tts_manager", "cleanup"),
            ("hotkey_manager", "unregister_hotkeys"),
            ("audio_manager", "cleanup"),
        )
        for attr, method in cleanup_steps:
            manager = getattr(self, attr, None)
            fn = getattr(manager, method, None) if manager is not None else None
            if not callable(fn):
                logger.debug("Skipping %s.%s - not available", attr, method)
                continue
            try:
                fn()
            except Exception as e:
                logger.warning("Error during %s.%s: %s", attr, method, e)

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
                    logger.info(f"Restoring window position to ({saved_x}, {saved_y})")
                    return saved_x, saved_y
                else:
                    logger.info(
                        "Saved window position (%s, %s) is off virtual screen "
                        "(bounds: %s,%s to %s,%s), using default",
                        saved_x, saved_y, virtual_left, virtual_top,
                        virtual_left + virtual_width, virtual_top + virtual_height)
        except Exception as e:
            logger.error(f"Error loading saved window position: {e}")

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
                except Exception as e:
                    logger.debug("Could not read virtual root dimensions: %s", e)
                # Fallback to standard screen dimensions
                return 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()
                
        except Exception as e:
            logger.error(f"Error getting virtual screen bounds: {e}")
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
            logger.error(f"Error saving window position: {e}")

    def play_sound(self, sound_file):
        """Play sound using audio manager."""
        self.audio_manager.play_sound(sound_file)

    def show_terms_of_use(self):
        # Create a new window to display the terms of use
        instruction_window = tk.Toplevel(self)
        instruction_window.title(_("Terms of Use"))
        instruction_window.transient(self)

        # Get window dimensions from theme
        window_width, window_height = get_window_size('about_dialog')
        position_dialog(instruction_window, window_width, window_height, self)
        bind_dialog_keys(instruction_window, on_cancel=instruction_window.destroy)

        # Get the path to the LICENSE.md file using the resource_path method
        license_path = self.resource_path("assets/LICENSE.md")

        # Attempt to read the content of the LICENSE.md file
        try:
            with open(license_path, "r", encoding="utf-8") as file:
                license_content = file.read()
        except FileNotFoundError:
            logger.warning("License file not found at %s", license_path)
            license_content = _("License file not found. Please ensure the LICENSE.md file exists in the application directory.")
        except PermissionError:
            logger.warning("Permission denied reading %s", license_path)
            license_content = _("Permission denied. Please ensure the script has read access to LICENSE.md.")
        except UnicodeDecodeError as e:
            license_content = _("Error reading license file due to encoding issue: {error}").format(error=e)
        except Exception as e:
            logger.error("Error reading license file %s: %s", license_path, e, exc_info=True)
            license_content = _("An unexpected error occurred while reading the license file: {error}").format(error=e)

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
        ttk.Button(instruction_window, text=_("Close"), command=instruction_window.destroy).pack(pady=(10, 0))

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
        dialog.title(_("About Quick Whisper"))

        # Get window dimensions from theme
        window_width, window_height = get_window_size('about_dialog')
        position_dialog(dialog, window_width, window_height, self)
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
            text=_("Quick Whisper"),
            font=get_font('xl', 'bold'),
            fg=text_primary,
            bg=bg_primary
        )
        title_label.pack(anchor="w", pady=(0, 4))

        # Subtitle/tagline
        tagline_label = tk.Label(
            content,
            text=_("AI-Powered Speech-to-Copy-Edited-Text"),
            font=get_font('md'),
            fg=theme.ACCENT_PRIMARY,
            bg=bg_primary
        )
        tagline_label.pack(anchor="w", pady=(0, 16))

        # Version
        version_label = tk.Label(
            content,
            text=_("Version {version}").format(version=self.version),
            font=get_font('xs'),
            fg=text_muted,
            bg=bg_primary
        )
        version_label.pack(anchor="w", pady=(0, 20))
        
        # Description text frame
        desc_frame = tk.Frame(content, bg=bg_secondary, padx=16, pady=16)
        desc_frame.pack(fill=tk.X, pady=(0, 20))
        
        description = _(
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
            text=_("Key Features"),
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
        
        usage_text = _(
            "How to use: Press {edit_shortcut} to record and AI-edit, or "
            "{transcribe_shortcut} for raw transcription. The app will automatically "
            "copy and paste the result into your active application."
        ).format(edit_shortcut=self.shortcuts.get('record_edit', 'Ctrl+Alt+J'),
                 transcribe_shortcut=self.shortcuts.get('record_transcribe', 'Ctrl+Alt+Shift+J'))
        
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
            text=_("Learn More on Our Website"),
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
            text=_("Close"),
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
            text=_("Developed by Scorchsoft.com | App & AI Developers"),
            font=get_font('xs', 'underline'),
            fg=link_color,
            bg=bg_primary,
            cursor="hand2"
        )
        credit_label.pack(anchor="center", pady=(0, 0))
        credit_label.bind("<Button-1>", lambda e: open_url("https://www.scorchsoft.com/"))
        credit_label.bind("<Enter>", lambda e: credit_label.config(fg=link_hover))
        credit_label.bind("<Leave>", lambda e: credit_label.config(fg=link_color))

    # Modes recorded against a history entry, kept as stable identifiers so a
    # saved history stays readable whatever language the app is running in.
    HISTORY_MODE_TRANSCRIPT = "transcript"
    HISTORY_MODE_EDIT = "edit"

    def add_to_history(self, text, mode=None, prompt=None, duration=None):
        """Append an entry to the history, trimming and persisting it.

        Entries carry when they were made, whether they are a raw transcript
        or an AI edit, and which prompt produced them. Without that the
        history is an unlabelled stack of text in which the transcript and its
        edit look identical.
        """
        if text is None:
            return

        entry = {
            "text": text,
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "mode": mode or self.HISTORY_MODE_TRANSCRIPT,
            "prompt": prompt,
            "duration": round(float(duration), 1) if duration else None,
        }

        # Repeating the same text (e.g. a re-run that produced an identical
        # edit) would just add a duplicate page to flick through.
        if self.history and self.history_text(len(self.history) - 1) == text:
            self.history_index = len(self.history) - 1
        else:
            self.history.append(entry)

            # Enforce max history length by removing the oldest entries.
            limit = max(1, int(self.max_history_length or 1))
            if len(self.history) > limit:
                del self.history[:len(self.history) - limit]

            # Update the index to the last entry (most recent)
            self.history_index = len(self.history) - 1

        self.ui_manager.update_transcription_text()
        self.ui_manager.update_navigation_buttons()
        self.save_history()

    @staticmethod
    def _normalise_history_entry(item):
        """Coerce a stored item into an entry dict, or None if unusable.

        Histories written before entries had metadata are plain strings; they
        are kept, just without a timestamp or a mode.
        """
        if isinstance(item, str):
            return {"text": item, "timestamp": None, "mode": None,
                    "prompt": None, "duration": None}
        if isinstance(item, dict):
            text = item.get("text")
            if not isinstance(text, str):
                return None
            return {
                "text": text,
                "timestamp": item.get("timestamp"),
                "mode": item.get("mode"),
                "prompt": item.get("prompt"),
                "duration": item.get("duration"),
            }
        return None

    def history_entry(self, index):
        """The entry dict at `index`, or None when out of range."""
        if 0 <= index < len(self.history):
            return self.history[index]
        return None

    def history_text(self, index):
        """The text at `index`, or an empty string when out of range."""
        entry = self.history_entry(index)
        return entry["text"] if entry else ""

    def _clamp_history_index(self):
        """Keep the history index inside the bounds of the history list."""
        if not self.history:
            self.history_index = -1
            return
        self.history_index = max(0, min(self.history_index, len(self.history) - 1))

    def navigate_right(self):
        self.history_index -= 1
        self._clamp_history_index()
        self.ui_manager.update_transcription_text()
        self.ui_manager.update_navigation_buttons()

    def navigate_left(self):
        self.history_index += 1
        self._clamp_history_index()
        self.ui_manager.update_transcription_text()
        self.ui_manager.update_navigation_buttons()

    def go_to_first_page(self):
        self.history_index = len(self.history) - 1  # Set to most recent
        self._clamp_history_index()
        self.ui_manager.update_transcription_text()
        self.ui_manager.update_navigation_buttons()

    def show_history(self):
        """Open the searchable history browser."""
        if not self.history:
            messagebox.showinfo(_("No History"),
                                _("There is nothing in your history yet."))
            return
        try:
            HistoryDialog(self)
        except Exception as e:
            # The dialog pauses the global hotkeys while it is open; if it
            # failed to finish opening, they have to come back.
            logger.error("Could not open the history browser: %s", e, exc_info=True)
            try:
                self.hotkey_manager.resume()
            except Exception:
                pass
            messagebox.showerror(
                _("History Unavailable"),
                _("The history browser could not be opened: {error}").format(error=e))

    def load_history_entry(self, index):
        """Show a history entry in the main window (from the browser)."""
        if not (0 <= index < len(self.history)):
            return
        self.history_index = index
        self.ui_manager.update_transcription_text()
        self.ui_manager.update_navigation_buttons()

    def load_history(self):
        """Restore the transcription history saved by a previous session.

        A corrupt or unreadable file must never stop the app starting, so any
        problem simply results in an empty history.
        """
        self.history = []
        self.history_index = -1

        if not self.persist_history:
            logger.info("History persistence disabled; starting with an empty history")
            return

        path = self._history_path
        if not path.exists():
            logger.info("No saved history at %s", path)
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logger.warning("Could not read history file %s (%s); starting empty", path, e)
            return

        # Accept both the plain list format and a wrapped {"entries": [...]}.
        if isinstance(data, dict):
            data = data.get("entries", [])
        if not isinstance(data, list):
            logger.warning("History file %s has an unexpected format; starting empty", path)
            return

        entries = [e for e in (self._normalise_history_entry(item) for item in data) if e]
        limit = max(1, int(self.max_history_length or 1))
        self.history = entries[-limit:]
        self.history_index = len(self.history) - 1
        logger.info("Restored %d history entries from %s", len(self.history), path)

    def save_history(self):
        """Persist the history, writing atomically so it can never be truncated."""
        if not self.persist_history:
            return

        path = self._history_path
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        payload = {"version": 2, "entries": self.history}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except Exception as e:
            logger.warning("Could not save history to %s: %s", path, e)
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass

    def save_session_history(self):
        if not self.history:
            messagebox.showinfo(_("No History"), _("There is no history to save."))
            return

        # Open a file save dialog
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")],
            title=_("Save Session History")
        )

        if not file_path:
            # User cancelled the save dialog
            return

        try:
            # Serialize history to JSON and save to file
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump({"version": 2, "entries": self.history}, f,
                          indent=4, ensure_ascii=False)

            logger.info("Session history saved to %s", file_path)
            self._toast(_("History saved"))
        except Exception as e:
            # Handle errors during the save process
            logger.error("Error saving session history to %s: %s", file_path, e, exc_info=True)
            messagebox.showerror(_("Save Error"),
                                 _("An error occurred while saving: {error}").format(error=e))

    def update_model_label(self):
        """Update the model label to include the prompt name and language setting."""
        self.ui_manager.update_model_label()

    def toggle_banner(self):
        """Toggle the visibility of the banner image."""
        self.ui_manager.toggle_banner()

    def load_prompts(self):
        """Load custom prompts from JSON file.

        Resolved through utils.paths so the prompts are found regardless of the
        directory the application was launched from.
        """
        prompts_file = get_prompts_path()
        if prompts_file.exists():
            try:
                with open(prompts_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                if not isinstance(loaded, dict):
                    logger.warning("Prompts file %s is not a JSON object; ignoring", prompts_file)
                    return {}
                logger.info("Loaded %d custom prompt(s) from %s", len(loaded), prompts_file)
                return loaded
            except Exception as e:
                logger.error("Error loading prompts from %s: %s", prompts_file, e, exc_info=True)
        else:
            logger.info("No custom prompts file at %s", prompts_file)
        return {}

    def save_prompts(self, prompts):
        """Save custom prompts to JSON file."""
        prompts_file = get_prompts_path()
        try:
            # Ensure config directory exists
            prompts_file.parent.mkdir(parents=True, exist_ok=True)
            with open(prompts_file, 'w', encoding='utf-8') as f:
                json.dump(prompts, f, indent=4)
            logger.info("Saved %d prompt(s) to %s", len(prompts), prompts_file)
        except Exception as e:
            logger.error("Failed to save prompts to %s: %s", prompts_file, e, exc_info=True)
            messagebox.showerror(_("Error"), _("Failed to save prompts: {error}").format(error=e))

    def save_prompt_to_config(self, prompt_name):
        """Save selected prompt to settings.json."""
        self.config_manager.selected_prompt = prompt_name
        self.config_manager.save_settings()

    def get_system_prompt(self, prompt_name=None):
        """The system prompt text for `prompt_name`, or for the current selection."""
        name = prompt_name or self.current_prompt_name
        if name == "Default":
            return self.default_system_prompt
        return self.prompts.get(name, self.default_system_prompt)
    
    
    def set_default_prompt(self):
        """Initialize default prompt and prompts dictionary."""
        try:
            default_prompt_path = self.resource_path("assets/DefaultPrompt.md")
            with open(default_prompt_path, 'r', encoding='utf-8') as f:
                self.default_system_prompt = f.read()
        except Exception as e:
            logger.error(f"Error loading default prompt: {e}")
            # Fallback to a basic prompt if file can't be loaded
            self.default_system_prompt = "You are an expert Copy Editor. When provided with text, provide a cleaned-up copy-edited version of that text in response."
            
        self.prompts = self.load_prompts()
        self.current_prompt_name = "Default"

    def _handle_minimize(self, event):
        """Track when window is minimized.
        
        When minimized, hotkeys are more likely to fail because Windows
        may release keyboard hooks for minimized applications.
        """
        if not self.was_minimized:
            self.was_minimized = True
            self._minimize_timestamp = time.time()
            logger.warning("Window minimized - hotkeys may become unresponsive")

    def _handle_restore(self, event):
        """Handle window restore from minimized state.
        
        Always refreshes hotkeys when restoring from minimized state,
        and resets the activity tracking to avoid false stale detection.
        """
        if self.was_minimized:
            self.was_minimized = False
            minimize_duration = time.time() - getattr(self, '_minimize_timestamp', time.time())
            logger.info(f"Window restored after {minimize_duration:.0f}s minimized - refreshing hotkeys")
            
            # Reset the activity timestamp on the hotkey manager
            # This prevents false "stale listener" detection right after restore
            if hasattr(self.hotkey_manager, '_last_key_event_time'):
                self.hotkey_manager._last_key_event_time = time.time()
            
            # Always refresh hotkeys on restore - this is the most reliable fix
            self.hotkey_manager.force_hotkey_refresh()

    def manage_prompts(self):
        ManagePromptsDialog(self)

    def open_config(self):
        """Open the configuration dialog."""
        ConfigDialog(self)

    def show_prompt_notification(self, message):
        """Tell the user which prompt is now selected.

        Speech used to be the only feedback here, and only on Windows, which
        left Mac and Linux users cycling prompts completely blind. An on-screen
        toast works everywhere, and is also the right answer for anyone running
        with their sound muted.
        """
        try:
            self.ui_manager.show_toast(
                message, anchor=getattr(self.ui_manager, '_picker_prompt', None))
        except Exception as e:
            logger.debug("Could not show the prompt notification: %s", e)

        # Speech is still useful when the window is not visible at all.
        if platform.system() == 'Windows':
            speech_message = message.split(": ", 1)[-1]
            self.tts_manager.speak_text(speech_message)

    def select_prompt(self, prompt_name):
        """Switch to a named prompt (from the status-line picker)."""
        if prompt_name not in self.prompt_names():
            logger.warning("Prompt '%s' no longer exists; keeping '%s'",
                           prompt_name, self.current_prompt_name)
            messagebox.showwarning(
                _("Prompt Not Found"),
                _("The prompt '{name}' no longer exists.").format(name=prompt_name))
            return
        if prompt_name == self.current_prompt_name:
            return
        self.current_prompt_name = prompt_name
        self.save_prompt_to_config(prompt_name)
        self.update_model_label()
        logger.info("Prompt changed to '%s'", prompt_name)
        self.show_prompt_notification(_("Prompt: {name}").format(name=prompt_name))

    def select_transcription_model(self, model, model_type):
        """Switch transcription model (from the status-line picker)."""
        if model == self.transcription_model:
            return
        self.transcription_model = model
        self.transcription_model_type = model_type
        self.config_manager.transcription_model = model
        self.config_manager.transcription_model_type = model_type
        self.config_manager.save_settings()
        self.update_model_label()
        logger.info("Transcription model changed to '%s' (%s)", model, model_type)
        self.ui_manager.show_toast(_("Transcription: {model}").format(model=model),
                                   anchor=self.ui_manager._picker_transcription)

    def select_ai_model(self, model):
        """Switch the copy-editing model (from the status-line picker)."""
        if model == self.ai_model:
            return
        self.ai_model = model
        self.config_manager.ai_model = model
        self.config_manager.save_settings()
        self.update_model_label()
        logger.info("AI model changed to '%s'", model)
        self.ui_manager.show_toast(_("AI edit: {model}").format(model=model),
                                   anchor=self.ui_manager._picker_ai)

    def prompt_names(self):
        """Every selectable prompt name, with the built-in default first."""
        return ["Default"] + [name for name in self.prompts.keys() if name != "Default"]

    def _cycle_prompt(self, step):
        """Move `step` places through the prompt list, wrapping around."""
        names = self.prompt_names()
        if len(names) < 2:
            logger.debug("Prompt cycling ignored - only one prompt is available")
            return
        try:
            current_index = names.index(self.current_prompt_name)
        except ValueError:
            current_index = 0
        self.select_prompt(names[(current_index + step) % len(names)])

    def cycle_prompt_forward(self):
        """Cycle to the next prompt in the list."""
        self._cycle_prompt(1)

    def cycle_prompt_backward(self):
        """Cycle to the previous prompt in the list."""
        self._cycle_prompt(-1)

    def cycle_prompt_notification(self, prompt_name):
        """Show a temporary notification about the prompt change."""
        self.show_prompt_notification(_("Prompt: {name}").format(name=prompt_name))

    def setup_hotkey_health_checker(self):
        """Set up periodic health checks and refreshes for hotkeys.
        
        Health checks run every 5 seconds for diagnostic visibility.
        Refreshes happen every 2 minutes when minimized (or on health failures).
        
        The health check tracks:
        - Total key events received
        - Total modifier key events (Ctrl, Alt, Shift, Win)
        - Total hotkey triggers
        - Time since last modifier event
        """
        # Health check interval (frequent, for diagnostics)
        self.hotkey_check_interval = 5000  # 5 seconds
        # Refresh interval (less frequent, to actually fix issues)
        self.hotkey_refresh_interval = 120000  # 2 minutes
        # Track time since last refresh
        self._last_hotkey_refresh = time.time()
        # Track consecutive health check failures
        self._hotkey_check_failures = 0
        self._max_consecutive_failures = 3
        
        def check_hotkey_health():
            # Determine state
            is_minimized = getattr(self, 'was_minimized', False) or self.winfo_viewable() == 0
            
            # Only run if auto hotkey refresh is enabled
            if self.auto_hotkey_refresh.get():
                # ALWAYS run diagnostic health check for visibility
                health_ok = self.hotkey_manager.verify_hotkeys()
                
                # Check if it's time for a refresh (every 30 seconds when minimized)
                time_since_refresh = time.time() - self._last_hotkey_refresh
                should_refresh = False
                refresh_reason = ""
                
                if is_minimized and time_since_refresh >= (self.hotkey_refresh_interval / 1000):
                    should_refresh = True
                    refresh_reason = f"minimized, {time_since_refresh:.0f}s since last refresh"
                elif not health_ok:
                    self._hotkey_check_failures += 1
                    if self._hotkey_check_failures >= self._max_consecutive_failures:
                        should_refresh = True
                        refresh_reason = f"{self._hotkey_check_failures} consecutive failures"
                else:
                    self._hotkey_check_failures = 0
                
                if should_refresh:
                    logger.info(f"[REFRESH] Reason: {refresh_reason}")
                    self.hotkey_manager.force_hotkey_refresh()
                    self._last_hotkey_refresh = time.time()
                    self._hotkey_check_failures = 0
            else:
                logger.warning("Hotkey health check skipped - auto refresh disabled")
                
            # Schedule next check (always 5 seconds)
            self.after(self.hotkey_check_interval, check_hotkey_health)
        
        # Start the periodic check
        self.after(self.hotkey_check_interval, check_hotkey_health)

    def _setup_memory_diagnostics(self):
        """Set up periodic memory and resource diagnostics logged to console.

        Prints a summary every 60 seconds so that if a user experiences growing
        memory usage, the console output will show which counters are climbing.
        """
        self._mem_diag_start = time.time()
        self._last_mem_mb = 0

        def _get_process_memory_mb():
            """Get current process RSS in MB, cross-platform."""
            try:
                import psutil
                return psutil.Process().memory_info().rss / (1024 * 1024)
            except ImportError:
                pass
            # Windows fallback without psutil
            if platform.system() == 'Windows':
                try:
                    import ctypes
                    from ctypes import wintypes
                    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                        _fields_ = [("cb", wintypes.DWORD),
                                    ("PageFaultCount", wintypes.DWORD),
                                    ("PeakWorkingSetSize", ctypes.c_size_t),
                                    ("WorkingSetSize", ctypes.c_size_t),
                                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                                    ("PagefileUsage", ctypes.c_size_t),
                                    ("PeakPagefileUsage", ctypes.c_size_t)]
                    pmc = PROCESS_MEMORY_COUNTERS()
                    pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                    kernel32 = ctypes.windll.kernel32
                    psapi = ctypes.windll.psapi
                    handle = kernel32.GetCurrentProcess()
                    if psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
                        return pmc.WorkingSetSize / (1024 * 1024)
                except Exception:
                    pass
            # Unix fallback
            try:
                import resource
                usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                # macOS returns bytes, Linux returns KB
                if platform.system() == 'Darwin':
                    return usage / (1024 * 1024)
                return usage / 1024
            except ImportError:
                return -1

        def _log_diagnostics():
            try:
                uptime = time.time() - self._mem_diag_start
                uptime_min = uptime / 60

                mem_mb = _get_process_memory_mb()
                threads = threading.active_count()

                # Audio diagnostics
                from utils.audio_manager import get_audio_diagnostics
                audio = get_audio_diagnostics()

                # Thread details
                thread_names = [t.name for t in threading.enumerate()]

                # GC stats
                gc_counts = gc.get_count()
                gc_objects = len(gc.get_objects())

                # Track memory delta
                delta = mem_mb - self._last_mem_mb if self._last_mem_mb > 0 else 0
                self._last_mem_mb = mem_mb
                delta_str = f"  delta={delta:+.1f}MB" if delta != 0 else ""

                logger.debug("[MEMORY DIAG] uptime=%.1fmin  RSS=%.1fMB%s  threads=%s",
                             uptime_min, mem_mb, delta_str, threads)
                logger.debug("[MEMORY DIAG] gc_objects=%s  gc_counts=%s", gc_objects, gc_counts)
                logger.debug("[MEMORY DIAG] audio: sounds=%s  streams_opened=%s  "
                             "streams_closed=%s  frames_peak=%s  recordings=%s/%s",
                             audio['sounds_played'], audio['streams_opened'],
                             audio['streams_closed'], audio['frames_peak'],
                             audio['recordings_started'], audio['recordings_stopped'])
                logger.debug("[MEMORY DIAG] threads: %s", thread_names)

            except Exception as e:
                logger.error(f"[MEMORY DIAG] Error collecting diagnostics: {e}")

            # Schedule next run
            self.after(60000, _log_diagnostics)

        # First run after 10 seconds (baseline)
        self.after(10000, _log_diagnostics)

    def apply_advanced_settings(self):
        """Adopt Advanced settings that the running app keeps its own copy of.

        Everything else is read from the config on demand, so only the cached
        history values and the level meter need doing by hand here.
        """
        previous_persist = self.persist_history
        self.max_history_length = self.config_manager.history_limit
        self.persist_history = self.config_manager.persist_history

        # Trim straight away rather than waiting for the next transcription.
        limit = max(1, int(self.max_history_length or 1))
        if len(self.history) > limit:
            del self.history[:len(self.history) - limit]
            self._clamp_history_index()
            self.ui_manager.update_transcription_text()
            self.ui_manager.update_navigation_buttons()

        if self.persist_history:
            self.save_history()
        elif previous_persist:
            self._offer_to_delete_saved_history()

        self.ui_manager.apply_level_meter_setting(self.config_manager.show_level_meter)

    def _offer_to_delete_saved_history(self):
        """Ask whether the already-saved history should be deleted too.

        Turning persistence off only stops new entries being written, so the
        file already on disk would otherwise sit there indefinitely - which is
        not what someone switching it off for privacy reasons expects. Deleting
        it silently is not right either: it is the user's data, so they decide.
        """
        try:
            if not self._history_path.exists():
                return
        except Exception as e:
            logger.warning("Could not check for the history file: %s", e)
            return

        delete_it = messagebox.askyesno(
            _("Delete Saved History?"),
            _("History will no longer be saved between sessions.\n\n"
              "Would you like to delete the history already stored on disk?\n\n"
              "Your current session's history stays in the window either way."),
            icon='question')
        if not delete_it:
            logger.info("History persistence disabled; the saved file was kept")
            return

        try:
            self._history_path.unlink()
            logger.info("History persistence disabled; removed %s", self._history_path)
        except Exception as e:
            logger.warning("Could not remove the history file %s: %s", self._history_path, e)
            messagebox.showwarning(
                _("Could Not Delete History"),
                _("The saved history file could not be deleted:\n{path}\n\nDetails: {error}"
                  ).format(path=self._history_path, error=e))

    def save_auto_hotkey_refresh(self):
        """Save the auto hotkey refresh setting to settings.json."""
        self.config_manager.auto_hotkey_refresh = self.auto_hotkey_refresh.get()
        self.config_manager.save_settings()
        logger.info(f"Auto hotkey refresh setting saved: {self.auto_hotkey_refresh.get()}")

    def toggle_dark_mode(self):
        """Toggle between dark and light mode and save the setting."""
        is_dark = self.dark_mode.get()
        self.config_manager.dark_mode = is_dark
        self.config_manager.save_settings()
        self.ui_manager.apply_theme(is_dark)
        logger.info(f"Dark mode setting saved: {is_dark}")

    def _window_title(self, recording=False):
        """The window/taskbar title, optionally marked as recording."""
        if recording:
            return _("Quick Whisper - Recording...")
        return _("Quick Whisper")

    def set_title_recording(self, recording):
        """Mirror the recording state into the title bar.

        The tray icon already turns red; this is the same signal for anyone
        who finds the app by its taskbar entry instead.
        """
        try:
            self.title(self._window_title(recording))
        except Exception as e:
            logger.debug("Could not update the window title: %s", e)

    def _rebuild_menus(self):
        """Destroy and recreate the popup menus from current state."""
        for name in ('file_menu', 'settings_menu', 'actions_menu', 'help_menu'):
            menu = getattr(self, name, None)
            if menu is not None:
                try:
                    menu.destroy()
                except Exception:
                    logger.debug("Could not destroy %s", name, exc_info=True)
        self.create_menu()

    def refresh_menu_accelerators(self):
        """Re-read the shortcuts and rebuild the menus that display them.

        The hotkey manager calls this after a rebind. It used to be missing
        entirely - the call was guarded by callable(), so rebinding a shortcut
        silently left every menu showing the old key.
        """
        try:
            for name in self.shortcuts:
                saved = self.config_manager.get_shortcut(name)
                if saved:
                    self.shortcuts[name] = saved
            self._rebuild_menus()
            logger.debug("Menu accelerators refreshed")
        except Exception:
            logger.error("Could not refresh the menu accelerators", exc_info=True)

    def _on_language_change(self):
        """Handle runtime language change by rebuilding menus and refreshing UI."""
        # Update window title
        self.title(self._window_title())

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

        logger.info(f"Language changed to: {lang_code}")

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
        """Initialize and show the system tray icon.

        A missing tray (common on minimal Linux desktops) must not greet the
        user with a modal before they have even seen the window: it is logged
        and shown in the status line instead, and the close button falls back
        to closing the application.
        """
        # Ask the manager whether a tray backend exists before trying to use
        # one - show_tray() has side effects, so it is not a good predicate.
        if not self._tray_is_available():
            logger.warning("System tray unavailable on this system; "
                           "closing the window will exit the application")
            self.tray_available = False
            self.protocol("WM_DELETE_WINDOW", self.on_closing)
            self._set_status(_("System tray unavailable"), "warning")
            # Leave the message up briefly, then return to the normal status.
            self.after(6000, lambda: self._set_status(_("Idle"), "idle"))
            return

        success = self.tray_manager.show_tray()
        self.tray_available = bool(success)

        if not success:
            # Backend exists but the icon could not be created - same
            # non-blocking treatment.
            logger.warning("Could not create the system tray icon; "
                           "closing the window will exit the application")
            self.protocol("WM_DELETE_WINDOW", self.on_closing)
            self._set_status(_("System tray unavailable"), "warning")
            self.after(6000, lambda: self._set_status(_("Idle"), "idle"))
        else:
            # Set up close button behavior based on user preference
            self.update_close_behavior()

    def _tray_is_available(self):
        """True when a system tray backend can be used on this machine."""
        manager = getattr(self, 'tray_manager', None)
        if manager is not None:
            try:
                return bool(manager.available)
            except Exception as e:
                logger.debug("Could not query tray availability: %s", e)
        try:
            return bool(tray_supported())
        except Exception as e:
            logger.debug("Could not determine tray support: %s", e)
            return False

    def update_close_behavior(self):
        """Update window close behavior based on user preference"""
        if self.config_manager.close_to_tray:
            # Minimize to tray when X is clicked
            self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        else:
            # Close the application when X is clicked
            self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def minimize_to_tray(self):
        """Minimize the application to system tray instead of closing"""
        self.tray_manager.minimize_to_tray()

    def update_recording_directory(self):
        """Update the recording directory based on configuration settings."""
        # Load recording location setting from config
        recording_location = self.config_manager.recording_location
        
        if recording_location == "appdata":
            # Per-user data directory (utils.paths knows the OS conventions).
            self.tmp_dir = get_user_data_dir()
        elif recording_location == "custom":
            custom_path = self.config_manager.custom_recording_path
            if custom_path and os.path.exists(custom_path):
                self.tmp_dir = Path(custom_path)
            else:
                # Fallback to alongside if custom path is invalid
                logger.warning("Custom recording path '%s' does not exist. Falling back to 'alongside'.",
                               custom_path)
                self.tmp_dir = get_default_recording_dir()
        else:  # Default: alongside the application (not the working directory)
            self.tmp_dir = get_default_recording_dir()

        # Ensure the directory exists
        try:
            self.tmp_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error("Could not create recording directory %s: %s", self.tmp_dir, e, exc_info=True)
            self.tmp_dir = get_default_recording_dir()
            self.tmp_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Recording directory set to: %s", self.tmp_dir)
