"""
Base class for platform-specific HotkeyManager implementations.

This module provides the abstract base class and shared functionality
for managing global keyboard hotkeys across different platforms.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from abc import ABC, abstractmethod
from pathlib import Path
import threading
import time

from utils.config_manager import get_config
from utils.i18n import _
from utils.theme import get_font, get_font_size, get_font_family, get_window_size, get_button_height, get_spacing, theme_colors
from . import CURRENT_PLATFORM

from utils.dialog_utils import position_dialog, bind_dialog_keys, focus_first
from utils.app_logging import get_logger

logger = get_logger(__name__)


# Tk reports key presses as keysyms, while pynput reports its own key names.
# The two vocabularies disagree (Tk "return" vs pynput "enter", Tk "Prior" vs
# pynput "pageup"), so a shortcut captured in the dialog could be stored in a
# form the listener would never match - the shortcut simply never fired. Both
# sides now normalise through this one table.
KEYSYM_TO_CANONICAL = {
    'return': 'enter', 'kp_enter': 'enter',
    'prior': 'pageup', 'next': 'pagedown',
    'bracketleft': '[', 'bracketright': ']',
    'minus': '-', 'equal': '=', 'comma': ',', 'period': '.',
    'slash': '/', 'backslash': '\\', 'semicolon': ';', 'apostrophe': "'",
    'grave': '`', 'space': 'space', 'tab': 'tab', 'escape': 'escape',
    'backspace': 'backspace', 'delete': 'delete', 'insert': 'insert',
    'home': 'home', 'end': 'end',
    'left': 'left', 'right': 'right', 'up': 'up', 'down': 'down',
}

# Shifted digits arrive as their punctuation keysym ("exclam" for Shift+1), which
# the old capture handler dropped entirely - leaving a bare modifier shortcut.
SHIFTED_DIGIT_KEYSYMS = {
    'exclam': '1', 'at': '2', 'numbersign': '3', 'dollar': '4', 'percent': '5',
    'asciicircum': '6', 'ampersand': '7', 'asterisk': '8', 'parenleft': '9',
    'parenright': '0',
}

MODIFIER_NAMES = ('ctrl', 'alt', 'shift', 'win', 'command')

# How long the calling (main) thread will wait for a listener to die before
# handing the rest of the wait to a background thread.
LISTENER_JOIN_TIMEOUT = 0.25
LISTENER_BACKGROUND_TIMEOUT = 10.0


def stop_listener_without_blocking(listener, platform_label):
    """Stop a pynput listener without freezing the Tk main thread.

    On X11 the listener does not notice stop() until it next receives an X
    event, so joining it with a 5 second timeout ran the full 5 seconds on an
    idle keyboard - every time. Since unregister_hotkeys() is always called
    from the main thread, that froze the window whenever the user opened
    Settings or Manage Prompts, refreshed hotkeys, restored from minimised, or
    closed the app.

    The thread does terminate, just later, so wait briefly here and let a
    short-lived daemon thread do the rest and report a genuine leak.
    """
    if listener is None:
        return
    try:
        listener.stop()
    except Exception as e:
        logger.debug("Error stopping %s listener: %s", platform_label, e)

    try:
        listener.join(timeout=LISTENER_JOIN_TIMEOUT)
    except Exception:
        return

    if not listener.is_alive():
        return

    def _finish_join():
        try:
            listener.join(timeout=LISTENER_BACKGROUND_TIMEOUT)
            if listener.is_alive():
                logger.warning(
                    "[MEMORY] %s listener thread still alive after %.0fs - potential leak",
                    platform_label, LISTENER_BACKGROUND_TIMEOUT)
            else:
                logger.debug("%s listener thread terminated in background", platform_label)
        except Exception as e:
            logger.debug("Background join of %s listener failed: %s", platform_label, e)

    threading.Thread(target=_finish_join, daemon=True,
                     name=f"HotkeyListenerJoin-{platform_label}").start()


def canonical_key_name(keysym, is_mac=False):
    """Normalise a Tk keysym to the name the pynput listener will produce.

    Returns None when the keysym is not a usable shortcut key.
    """
    key = (keysym or '').lower()
    if not key:
        return None
    if key in KEYSYM_TO_CANONICAL:
        return KEYSYM_TO_CANONICAL[key]
    if key in SHIFTED_DIGIT_KEYSYMS:
        return SHIFTED_DIGIT_KEYSYMS[key]
    if len(key) == 1:
        return key
    if key.startswith('f') and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        return key
    return None


class HotkeyManagerBase(ABC):
    """
    Abstract base class for platform-specific hotkey managers.

    Subclasses must implement the abstract methods for registering,
    unregistering, and verifying hotkeys using platform-specific APIs.
    """

    def __init__(self, parent):
        self.parent = parent
        self._paused = False
        # Four independent callers can trigger a refresh (the 5s health check,
        # the tray thread, the system-event listener and toggle_recording), and
        # the old code unregistered immediately then re-registered 100ms later.
        # Overlapping refreshes caused duplicate re-registration and a spurious
        # failure dialog. One in flight at a time, cancellable on pause.
        self._refresh_in_flight = False
        self._pending_refresh_id = None
        # The failure dialog is shown once, not once per refresh attempt.
        self._refresh_failure_reported = False
        self.config = get_config()
        self.is_mac = CURRENT_PLATFORM == 'macos'

        # Push-to-talk state. ``_held_combo`` is the key combination currently
        # being held down to record; releasing any of its keys ends the take.
        self._held_combo = None
        self._hold_lock = threading.Lock()

        # Default shortcuts (platform-specific)
        self.shortcuts = self._get_default_shortcuts()

        # Load shortcuts from config (may override defaults)
        self.load_shortcuts_from_config()

    def _get_default_shortcuts(self):
        """Get default shortcuts for the current platform."""
        if self.is_mac:
            return {
                'record_edit': 'command+alt+j',
                'record_transcribe': 'command+alt+shift+j',
                'cancel_recording': 'command+x',
                'cycle_prompt_back': 'command+[',
                'cycle_prompt_forward': 'command+]',
                'retry_last': 'command+alt+r'
            }
        else:
            # Windows and Linux use the same defaults
            return {
                'record_edit': 'ctrl+alt+j',
                'record_transcribe': 'ctrl+alt+shift+j',
                'cancel_recording': 'ctrl+alt+x',
                'cycle_prompt_back': 'alt+left',
                'cycle_prompt_forward': 'alt+right',
                'retry_last': 'ctrl+alt+r'
            }

    def load_shortcuts_from_config(self):
        """Load keyboard shortcuts from config file."""
        # Iterate the defaults rather than a second hand-maintained list, so
        # adding a shortcut in one place is enough.
        defaults = self._get_default_shortcuts()
        self.shortcuts = {
            name: (self.config.get_shortcut(name) or default)
            for name, default in defaults.items()
        }

    # ------------------------------------------------------------------
    # Hotkey map + push-to-talk
    # ------------------------------------------------------------------

    def build_hotkey_map(self):
        """Return ``{frozenset(keys): callback}`` for the platform listener.

        All three platforms drive the same six actions from the same shortcut
        names, so the mapping is built once here. Recording is routed through
        :meth:`_dispatch_record` so it can behave as a toggle or as
        push-to-talk without the platform listeners needing to know.
        """
        actions = {
            'record_edit': lambda combo: self._dispatch_record("edit", combo),
            'record_transcribe': lambda combo: self._dispatch_record("transcribe", combo),
            'cancel_recording': lambda combo: self._on_main_thread(self.parent.cancel_recording),
            'cycle_prompt_back': lambda combo: self._on_main_thread(self.parent.cycle_prompt_backward),
            'cycle_prompt_forward': lambda combo: self._on_main_thread(self.parent.cycle_prompt_forward),
            'retry_last': lambda combo: self._on_main_thread(self.parent.retry_last_recording),
        }

        mapping = {}
        for name, action in actions.items():
            combo = self._normalize_shortcut(self.shortcuts.get(name, '') or '')
            # An unset shortcut normalises to an empty frozenset, which would
            # otherwise match "no keys pressed".
            if not combo:
                continue
            # Bind the combination now so the callback knows which keys have to
            # be released to end a push-to-talk recording.
            mapping[combo] = (lambda a=action, c=combo: a(c))
        return mapping

    def _on_main_thread(self, func, *args):
        """Run a callback on the Tk main loop, tolerating a closing window."""
        try:
            self.parent.after(0, lambda: func(*args))
        except Exception as e:
            logger.debug("Could not marshal hotkey callback to the main thread: %s", e)

    def recording_mode(self):
        """Return "toggle" or "push_to_talk" from the current configuration."""
        try:
            return self.config.recording_mode
        except Exception:
            return "toggle"

    def _dispatch_record(self, mode, combo):
        """Handle a record hotkey press for either recording mode."""
        if self.recording_mode() != "push_to_talk":
            self._on_main_thread(self.parent.toggle_recording, mode)
            return

        # Only claim the hold if this press will actually start a recording.
        # start_push_to_talk deliberately refuses when a recording is already
        # running (the user may have started it from the buttons) or while the
        # previous one is still processing - but the hold was being claimed
        # before it got a say, so releasing the key then stopped a recording
        # this press never started.
        if self._press_would_be_refused():
            logger.debug("Push-to-talk press ignored - the app is busy")
            return

        with self._hold_lock:
            if self._held_combo is not None:
                # Key auto-repeat while the combination is held. Already
                # recording, so there is nothing to do.
                return
            self._held_combo = combo

        logger.info("Push-to-talk started (mode=%s)", mode)
        self._on_main_thread(self.parent.start_push_to_talk, mode)

    def _press_would_be_refused(self):
        """Whether the app would ignore a new push-to-talk press right now.

        Read from the listener thread, so it only touches thread-safe state:
        ``recording`` is backed by an Event and ``_processing`` by a bool.
        """
        try:
            if self.parent.audio_manager.recording:
                return True
            return bool(getattr(self.parent, '_processing', False))
        except Exception:
            return False

    def _note_key_released(self, key_name):
        """Tell the base class a key came up, so push-to-talk can end.

        Called by every platform listener from its own release handler.
        Releasing any key of the held combination ends the recording, which
        matches how people actually let go of a chord.
        """
        if not key_name:
            return
        # This runs for every key the user releases anywhere in the OS, so the
        # overwhelmingly common "not holding anything" case is answered without
        # taking a lock. Reading the attribute is atomic; the lock below still
        # settles any race over who clears it.
        if self._held_combo is None:
            return
        with self._hold_lock:
            combo = self._held_combo
            if combo is None or key_name not in combo:
                return
            self._held_combo = None

        logger.info("Push-to-talk released")
        self._on_main_thread(self.parent.finish_push_to_talk)

    def _clear_hold_state(self):
        """Forget any in-flight push-to-talk hold (used around refreshes)."""
        with self._hold_lock:
            self._held_combo = None

    @abstractmethod
    def register_hotkeys(self):
        """
        Register all hotkeys with the system.

        Returns:
            bool: True if registration succeeded, False otherwise.
        """
        pass

    @abstractmethod
    def unregister_hotkeys(self):
        """Unregister all hotkeys from the system."""
        pass

    @abstractmethod
    def verify_hotkeys(self):
        """
        Verify that hotkeys are currently working.

        Returns:
            bool: True if hotkeys are working, False otherwise.
        """
        pass

    def force_hotkey_refresh(self, callback=None):
        """
        Force a complete refresh of all hotkeys.

        Args:
            callback: Optional callback function(success: bool) called after refresh.

        Returns:
            bool: True if refresh started successfully.
        """
        logger.info("Forcing hotkey refresh")
        try:
            if self._paused:
                logger.warning("Hotkeys are paused; skipping refresh")
                if callback:
                    callback(True)
                return True

            if self._refresh_in_flight:
                logger.debug("Hotkey refresh already in flight; skipping")
                if callback:
                    callback(True)
                return True

            self._refresh_in_flight = True

            # Unregister all hotkeys
            self.unregister_hotkeys()

            # Schedule re-registration
            def _after_refresh():
                self._pending_refresh_id = None
                try:
                    # The user may have opened a modal (which pauses hotkeys) in
                    # the window between unregister and here. That is not a
                    # failure - resume() will re-register.
                    if self._paused:
                        logger.debug("Hotkeys paused during refresh; deferring to resume()")
                        if callback:
                            callback(True)
                        return

                    success = self.register_hotkeys()
                    if success:
                        logger.info("Hotkey refresh completed successfully")
                        self._refresh_failure_reported = False
                        if callback:
                            callback(True)
                    else:
                        logger.error("Failed to register hotkeys")
                        if callback:
                            callback(False)
                        self._report_refresh_failure()
                finally:
                    self._refresh_in_flight = False

            self._pending_refresh_id = self.parent.after(100, _after_refresh)
            return True

        except Exception as e:
            self._refresh_in_flight = False
            logger.error("Error during hotkey refresh: %s", e)
            if callback:
                callback(False)
            self._report_refresh_failure()
            return False

    def report_hotkeys_unavailable(self):
        """Tell the user hotkeys are down - once, not once per retry.

        The health checker retries every few seconds, so a modal here used to
        stack dialogs from inside its own nested event loop and trap the user.
        """
        if self._refresh_failure_reported:
            return
        self._refresh_failure_reported = True
        try:
            self.parent.ui_manager.set_status(
                _("Global shortcuts unavailable - buttons still work"), "warning")
        except Exception:
            logger.warning("Could not surface hotkey failure in the status bar")

    # Kept under the old private name for existing internal callers.
    _report_refresh_failure = report_hotkeys_unavailable

    def pause(self):
        """Temporarily disable all hotkeys."""
        try:
            logger.info("Pausing hotkeys...")
            self._paused = True
            # A hold that survives the pause would wait for a release event
            # that can no longer arrive.
            self._clear_hold_state()
            # Drop any refresh scheduled before the pause, so it cannot
            # re-register behind a modal that deliberately disabled hotkeys.
            if self._pending_refresh_id is not None:
                try:
                    self.parent.after_cancel(self._pending_refresh_id)
                except Exception:
                    pass
                self._pending_refresh_id = None
                self._refresh_in_flight = False
            self.unregister_hotkeys()
            logger.info("Hotkeys paused")
        except Exception as e:
            logger.error("Error while pausing hotkeys: %s", e)

    def resume(self):
        """Re-enable hotkeys after a pause."""
        try:
            if not self._paused:
                return
            logger.info("Resuming hotkeys...")
            self._paused = False
            self.register_hotkeys()
            logger.info("Hotkeys resumed")
        except Exception as e:
            logger.error("Error while resuming hotkeys: %s", e)

    def save_shortcut_to_config(self, shortcut_name, key_combination):
        """Save a keyboard shortcut to settings.json."""
        formatted_combination = self.format_shortcut(
            key_combination.split('+') if isinstance(key_combination, str) else key_combination
        )

        self.config.set_shortcut(shortcut_name, formatted_combination)
        self.config.save_settings()
        self.shortcuts[shortcut_name] = formatted_combination
        self.update_shortcut_displays()

    def update_shortcut_displays(self):
        """Update all UI elements that display keyboard shortcuts."""
        # Pass the display form: shortcuts are stored lowercase for matching,
        # and these end up printed on the buttons.
        transcribe = self.display_shortcut('record_transcribe')
        edit = self.display_shortcut('record_edit')

        if hasattr(self.parent.ui_manager, 'update_button_shortcuts'):
            self.parent.ui_manager.update_button_shortcuts(
                transcribe_shortcut=transcribe,
                edit_shortcut=edit
            )
        else:
            self.parent.ui_manager.record_button_edit.configure(
                text=_("Record + AI Edit ({shortcut})").format(shortcut=edit)
            )
            self.parent.ui_manager.record_button_transcribe.configure(
                text=_("Record + Transcribe ({shortcut})").format(shortcut=transcribe)
            )

        # The menu label used to be located by searching for the English string
        # "Cancel Recording", which never matched in a translated UI. The menus
        # own their own labels and accelerators, so just ask them to refresh.
        try:
            refresh = getattr(self.parent, 'refresh_menu_accelerators', None)
            if callable(refresh):
                refresh()
        except Exception:
            logger.debug("Could not refresh menu accelerators", exc_info=True)

    def format_shortcut(self, keys):
        """Format a set of keys into a shortcut string with consistent ordering."""
        modifier_order = ['ctrl', 'alt', 'shift', 'win', 'command']
        modifiers = [k for k in keys if k in modifier_order]
        regular_keys = [k for k in keys if k not in modifier_order]
        sorted_modifiers = sorted(modifiers, key=lambda x: modifier_order.index(x))
        return "+".join(sorted_modifiers + sorted(regular_keys))

    # How each stored key name is written when shown to a user. Anything not
    # listed is title-cased, which covers the letter and arrow keys.
    _KEY_DISPLAY_NAMES = {
        'ctrl': 'Ctrl',
        'alt': 'Alt',
        'shift': 'Shift',
        'win': 'Win',
        'command': 'Cmd',
        'left': 'Left',
        'right': 'Right',
        'up': 'Up',
        'down': 'Down',
        'space': 'Space',
        'esc': 'Esc',
        'escape': 'Esc',
        'tab': 'Tab',
        'enter': 'Enter',
        'return': 'Enter',
    }

    def display_shortcut(self, shortcut_name, default=""):
        """A shortcut written the way a user expects to read it.

        Shortcuts are stored lowercase ("ctrl+alt+x") because that is what the
        key listeners match on. Anywhere one is shown - button labels, the
        status line, tooltips - it needs to be capitalised instead.
        """
        combo = ""
        try:
            combo = self.shortcuts.get(shortcut_name, "") or ""
        except Exception:
            logger.debug("Could not read the %s shortcut", shortcut_name)
        if not combo:
            return default
        return "+".join(
            self._KEY_DISPLAY_NAMES.get(part.lower(), part.title())
            for part in combo.split("+") if part
        )

    def reset_shortcuts_to_default(self, shortcuts_window=None):
        """Reset all keyboard shortcuts to their default values."""
        if not shortcuts_window:
            shortcuts_window = self.parent

        confirm = tk.messagebox.askyesno(
            "Reset Shortcuts",
            "Are you sure you want to reset all keyboard shortcuts to their default values?",
            parent=shortcuts_window
        )

        if confirm:
            try:
                default_shortcuts = self._get_default_shortcuts()
                self.shortcuts = default_shortcuts.copy()

                for name, shortcut in default_shortcuts.items():
                    self.config.set_shortcut(name, shortcut)
                self.config.save_settings()

                if shortcuts_window != self.parent:
                    self._update_shortcut_dialog_labels(shortcuts_window)

                def on_refresh_complete(success):
                    self.update_shortcut_displays()
                    if success:
                        tk.messagebox.showinfo(
                            "Success",
                            "Shortcuts have been reset to defaults",
                            parent=shortcuts_window
                        )
                    else:
                        tk.messagebox.showerror(
                            "Error",
                            "Failed to register default shortcuts. Try closing and reopening the application.",
                            parent=shortcuts_window
                        )

                self.force_hotkey_refresh(callback=on_refresh_complete)

            except Exception as e:
                tk.messagebox.showerror(
                    "Error",
                    f"Failed to reset shortcuts: {e}",
                    parent=shortcuts_window
                )

    def _update_shortcut_dialog_labels(self, shortcuts_window):
        """Update shortcut labels in the dialog window."""
        for child in shortcuts_window.winfo_children():
            if isinstance(child, ttk.Frame):
                for frame_child in child.winfo_children():
                    if isinstance(frame_child, ttk.Frame):
                        for shortcut_frame in frame_child.winfo_children():
                            if isinstance(shortcut_frame, ttk.Frame):
                                labels = [w for w in shortcut_frame.winfo_children()
                                         if isinstance(w, ttk.Label)]
                                if len(labels) >= 2:
                                    name_label = labels[0]
                                    shortcut_label = labels[1]
                                    shortcut_name = name_label.cget('text').replace(':', '').lower().replace(' ', '_')
                                    if shortcut_name in self.shortcuts:
                                        shortcut_label.config(text=self.shortcuts[shortcut_name])

    def check_keyboard_shortcuts(self):
        """Open the keyboard shortcuts dialog for viewing and editing."""
        shortcut_window = tk.Toplevel(self.parent)
        shortcut_window.title(_("Keyboard Shortcuts"))

        # Every other modal pauses hotkeys; this one did not, so pressing the
        # current Ctrl+Alt+J while assigning a new shortcut both captured the
        # keystroke and started a recording.
        self.pause()

        def _on_dialog_close():
            try:
                self.resume()
            finally:
                shortcut_window.destroy()

        shortcut_window.protocol("WM_DELETE_WINDOW", _on_dialog_close)
        bind_dialog_keys(shortcut_window, on_cancel=_on_dialog_close)

        # Get window dimensions from theme
        window_width, window_height = get_window_size('hotkey_dialog')
        position_dialog(shortcut_window, window_width, window_height, self.parent)

        # Configure styles for consistent fonts
        style = ttk.Style()
        style.configure('HotkeyDialog.TLabel', font=get_font('sm'))
        style.configure('HotkeyDialog.TButton', font=get_font('sm'))

        main_frame = ttk.Frame(shortcut_window, padding=get_spacing('xl'))
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(
            main_frame,
            text="Keyboard Shortcuts",
            font=get_font('lg', 'bold')
        )
        title_label.pack(pady=(0, get_spacing('lg')))

        shortcuts_frame = ttk.Frame(main_frame)
        shortcuts_frame.pack(fill=tk.BOTH, expand=True)

        for name, shortcut in self.shortcuts.items():
            frame = ttk.Frame(shortcuts_frame)
            frame.pack(fill=tk.X, pady=get_spacing('xs'))

            name_label = ttk.Label(
                frame,
                text=name.replace('_', ' ').title() + ":",
                style='HotkeyDialog.TLabel'
            )
            name_label.pack(side=tk.LEFT, padx=(0, get_spacing('sm')))

            shortcut_label = ttk.Label(
                frame,
                text=shortcut,
                style='HotkeyDialog.TLabel'
            )
            shortcut_label.pack(side=tk.LEFT, padx=(0, get_spacing('sm')))

            edit_button = ttk.Button(
                frame,
                text="Edit",
                style='HotkeyDialog.TButton'
            )
            edit_button.pack(side=tk.RIGHT)
            edit_button.configure(
                command=lambda n=name, b=edit_button, l=shortcut_label:
                    self._start_shortcut_edit(n, b, l, shortcut_window)
            )

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=get_spacing('xl'))

        # Use half the button height for corner_radius to create pill shape
        button_height = get_button_height('dialog')
        corner_radius = button_height // 2

        refresh_button = ctk.CTkButton(
            button_frame,
            text="Refresh Shortcuts",
            corner_radius=corner_radius,
            height=button_height,
            width=220,
            fg_color=theme_colors().BUTTON_PRIMARY,
            hover_color=theme_colors().BUTTON_PRIMARY_HOVER,
            font=ctk.CTkFont(family=get_font_family(), size=get_font_size('dialog_button'), weight='bold'),
            cursor="hand2",
            command=self.force_hotkey_refresh
        )
        refresh_button.pack(side=tk.LEFT, padx=get_spacing('sm'))

        reset_button = ctk.CTkButton(
            button_frame,
            text="Reset to Defaults",
            corner_radius=corner_radius,
            height=button_height,
            width=220,
            fg_color=theme_colors().BUTTON_SECONDARY,
            hover_color=theme_colors().BUTTON_SECONDARY_HOVER,
            font=ctk.CTkFont(family=get_font_family(), size=get_font_size('dialog_button'), weight='bold'),
            cursor="hand2",
            command=lambda: self.reset_shortcuts_to_default(shortcuts_window=shortcut_window)
        )
        reset_button.pack(side=tk.LEFT, padx=get_spacing('sm'))

        # Platform-specific note
        if CURRENT_PLATFORM == 'macos':
            note_text = ("Note: On macOS, you may need to grant Accessibility\n"
                        "permissions for global hotkeys to work.")
        elif CURRENT_PLATFORM == 'linux':
            note_text = ("Note: On Linux with Wayland, global hotkeys may\n"
                        "have limited functionality. X11 is recommended.")
        else:
            note_text = ("Note: If shortcuts stop working after unlocking Windows,\n"
                        "use this dialog to refresh them. If refresh doesn't work,\n"
                        "try closing and reopening the application.")

        ttk.Label(
            main_frame,
            text=note_text,
            justify=tk.CENTER,
            font=get_font('xxs'),
            foreground=theme_colors().BUTTON_SECONDARY
        ).pack(pady=get_spacing('sm'))

        # Close button using CTkButton for consistency
        close_button = ctk.CTkButton(
            main_frame,
            text="Close",
            corner_radius=corner_radius,
            height=button_height,
            width=120,
            fg_color="#555555",
            hover_color=theme_colors().BUTTON_SECONDARY_HOVER,
            font=ctk.CTkFont(family=get_font_family(), size=get_font_size('dialog_button'), weight='bold'),
            cursor="hand2",
            command=_on_dialog_close
        )
        close_button.pack(pady=(get_spacing('sm'), 0))

    def _start_shortcut_edit(self, shortcut_name, button, label, shortcut_window):
        """Handle shortcut editing when user clicks Edit button."""
        if not button or not button.winfo_exists():
            return

        button.config(text="Press new shortcut...")

        pressed_keys = set()
        currently_pressed = set()

        def on_key_press(event):
            key = event.keysym.lower()

            if key == 'escape':
                # Escape cancels rather than being captured as a shortcut.
                pressed_keys.clear()
                currently_pressed.clear()
                button.config(text=_("Edit"))
                _end_capture()
                return "break"

            modifier_map = {
                'control_l': 'ctrl', 'control_r': 'ctrl',
                'alt_l': 'alt', 'alt_r': 'alt',
                'shift_l': 'shift', 'shift_r': 'shift',
                'super_l': 'win' if not self.is_mac else 'command',
                'super_r': 'win' if not self.is_mac else 'command',
                'win_l': 'win', 'win_r': 'win',
                'meta_l': 'command', 'meta_r': 'command'
            }

            if key in modifier_map:
                currently_pressed.add(modifier_map[key])
            else:
                # Normalise through the shared table so what we store is what
                # the pynput listener will actually produce.
                canonical = canonical_key_name(key, self.is_mac)
                if canonical:
                    currently_pressed.add(canonical)
                else:
                    logger.debug("Ignoring unmapped keysym during capture: %s", key)

            pressed_keys.clear()
            pressed_keys.update(currently_pressed)

            # Check modifier state from event
            if event.state & 0x4:
                pressed_keys.add('ctrl')
            if event.state & 0x1:
                pressed_keys.add('shift')
            if event.state & 0x20000:
                pressed_keys.add('alt')
            if event.state & 0x40000:
                pressed_keys.add('win' if not self.is_mac else 'command')

            current_combo = "+".join(sorted(pressed_keys))
            button.config(text=f"Press: {current_combo}")
            return "break"

        def on_key_release(event):
            nonlocal currently_pressed
            key = event.keysym.lower()

            if key in currently_pressed:
                currently_pressed.remove(key)

            modifier_map = {
                'control_l': 'ctrl', 'control_r': 'ctrl',
                'alt_l': 'alt', 'alt_r': 'alt',
                'shift_l': 'shift', 'shift_r': 'shift',
                'super_l': 'win' if not self.is_mac else 'command',
                'super_r': 'win' if not self.is_mac else 'command',
                'win_l': 'win', 'win_r': 'win',
                'meta_l': 'command', 'meta_r': 'command'
            }
            if key in modifier_map:
                mod_key = modifier_map[key]
                if mod_key in currently_pressed:
                    currently_pressed.remove(mod_key)

            if not currently_pressed and pressed_keys:
                try:
                    new_shortcut = self.format_shortcut(pressed_keys)

                    # A modifier alone is not a shortcut. The old check only
                    # asked whether *any* key was a modifier, so tapping Ctrl by
                    # itself saved "ctrl" as a global hotkey - after which every
                    # Ctrl press anywhere toggled recording.
                    modifiers = [k for k in pressed_keys if k in MODIFIER_NAMES]
                    regular = [k for k in pressed_keys if k not in MODIFIER_NAMES]

                    if not modifiers:
                        messagebox.showerror(_("Invalid Shortcut"),
                            _("Please include at least one modifier key (Ctrl, Alt, Shift, Win/Cmd)."))
                        button.config(text=_("Edit"))
                        return

                    if len(regular) != 1:
                        messagebox.showerror(_("Invalid Shortcut"),
                            _("Please press one modifier key plus exactly one other key."))
                        button.config(text=_("Edit"))
                        return

                    for name, shortcut in self.shortcuts.items():
                        if shortcut == new_shortcut and name != shortcut_name:
                            messagebox.showerror("Error",
                                f"This shortcut is already assigned to '{name}'")
                            button.config(text="Edit")
                            return

                    self.save_shortcut_to_config(shortcut_name, new_shortcut)

                    def on_refresh_complete(success):
                        if success:
                            label.config(text=new_shortcut)
                            button.config(text="Edit")
                        else:
                            messagebox.showerror("Error",
                                "Failed to register new shortcut. Please try a different combination.")
                            button.config(text="Edit")

                    self.force_hotkey_refresh(callback=on_refresh_complete)

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update shortcut: {e}")
                    button.config(text="Edit")

                finally:
                    pressed_keys.clear()
                    currently_pressed.clear()
                    _end_capture()

        def _end_capture():
            """Detach the capture bindings once we are done with them.

            Previously nothing unbound them, so after editing one shortcut any
            later chord typed in the dialog silently reassigned the same one.
            """
            try:
                shortcut_window.unbind('<KeyPress>')
                shortcut_window.unbind('<KeyRelease>')
            except Exception:
                pass

        self._end_shortcut_capture = _end_capture

        shortcut_window.unbind('<KeyPress>')
        shortcut_window.unbind('<KeyRelease>')
        shortcut_window.bind('<KeyPress>', on_key_press)
        shortcut_window.bind('<KeyRelease>', on_key_release)
