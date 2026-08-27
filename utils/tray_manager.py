import colorsys
import threading
import platform
import tkinter as tk

from PIL import Image

from utils.app_logging import get_logger
from utils.i18n import _, register_refresh_callback, unregister_refresh_callback

logger = get_logger(__name__)

# Hue window occupied by the brand gradient on the app icon (cyan -> purple).
_BRAND_HUE_START = 180.0
_BRAND_HUE_END = 270.0
# Where that gradient is re-mapped to for the recording state (orange -> crimson).
_RECORDING_HUE_START = 22.0
_RECORDING_HUE_END = -20.0

# Amber, clearly distinct from both the brand cyan and the recording red.
_PROCESSING_HUE_START = 48.0
_PROCESSING_HUE_END = 28.0
# Greys and near-whites (the ring and the glyph) are left alone, so the icon
# stays recognisably itself rather than becoming a red blob.
_MIN_SATURATION_TO_TINT = 0.25


def make_processing_icon(image):
    """Return an amber 'processing' variant of the application icon.

    Between the red icon going away and the text appearing, a user with the
    window hidden previously had no signal at all that work was still in
    flight.
    """
    return _retint_icon(image, _PROCESSING_HUE_START, _PROCESSING_HUE_END)


def make_recording_icon(image):
    """Return a red 'recording' variant of the application icon.

    Derived from the real icon at runtime rather than shipped as a second
    asset, so it cannot drift out of step if the branding ever changes. Only
    the coloured part of the artwork is re-hued: the dark surround and the
    white glyph keep their values, which is what makes the two icons read as
    the same icon in two states at 16 px.
    """
    return _retint_icon(image, _RECORDING_HUE_START, _RECORDING_HUE_END)


def _retint_icon(image, hue_start, hue_end):
    """Re-hue the coloured part of the icon into a different hue range."""
    source = image.convert("RGBA")
    width, height = source.size
    variant = Image.new("RGBA", (width, height))
    read = source.load()
    write = variant.load()
    hue_span = hue_end - hue_start

    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = read[x, y]
            if alpha == 0:
                write[x, y] = (red, green, blue, alpha)
                continue
            hue, saturation, value = colorsys.rgb_to_hsv(
                red / 255.0, green / 255.0, blue / 255.0)
            if saturation < _MIN_SATURATION_TO_TINT:
                write[x, y] = (red, green, blue, alpha)
                continue
            # Position within the brand gradient, so the new icon keeps a
            # gradient of its own instead of going flat red.
            position = (hue * 360.0 - _BRAND_HUE_START) / (_BRAND_HUE_END - _BRAND_HUE_START)
            position = min(1.0, max(0.0, position))
            new_hue = (hue_start + position * hue_span) % 360.0
            new_red, new_green, new_blue = colorsys.hsv_to_rgb(
                new_hue / 360.0, min(1.0, saturation * 1.05), value)
            write[x, y] = (int(new_red * 255), int(new_green * 255),
                           int(new_blue * 255), alpha)

    return variant

# pystray is imported lazily. Importing it at module scope is unsafe: on Linux
# it raises at import time when no app-indicator library is installed
# (ValueError: Namespace AyatanaAppIndicator3 not available) or when there is
# no DISPLAY at all, which used to stop the whole application from starting.
# The tray is an optional convenience, so a failure here must only disable the
# tray - never the app.
_pystray = None  # None = not attempted yet, False = unavailable


def _load_pystray():
    """Import pystray on demand, returning the module or None if unavailable."""
    global _pystray
    if _pystray is None:
        try:
            import pystray  # noqa: F401 - imported for its side effects too
            _pystray = pystray
            logger.debug("pystray loaded (backend: %s)", getattr(pystray, "Icon", None))
        except Exception as e:
            # ImportError, ValueError (missing GI namespace), Xlib display
            # errors - anything at all. The tray simply becomes unavailable.
            logger.warning("System tray unavailable - could not import pystray: %s", e)
            _pystray = False
    return _pystray or None


def tray_supported():
    """True when a system tray backend could be loaded on this machine."""
    return _load_pystray() is not None


class TrayManager:
    def __init__(self, parent):
        self.parent = parent
        self.icon = None
        self.icon_thread = None
        self.is_running = False
        self.is_window_hidden = False
        self.icon_image = None
        self.recording_icon_image = None
        self.processing_icon_image = None
        self._is_recording = False
        self._state = "idle"
        self._lock = threading.RLock()
        self._shutting_down = False
        self._language_callback_registered = False

    @property
    def available(self):
        """True when the tray backend is importable on this platform."""
        return tray_supported()

    def _menu_items(self, pystray):
        """Build the (translated) tray menu.

        Item labels are callables so pystray re-evaluates them - together with
        ``icon.update_menu()`` this lets the menu follow a runtime language
        change instead of being frozen in the language used at startup.
        """
        Item = pystray.MenuItem
        Menu = pystray.Menu
        # Note: default=True makes left-click on tray icon trigger this action (Windows)
        return Menu(
            Item(lambda item: _('Show/Hide Window'), self._toggle_window, default=True),
            Menu.SEPARATOR,
            Item(lambda item: _('Settings...'), self._open_settings),
            Item(lambda item: _('History...'), self._open_history),
            Menu.SEPARATOR,
            Item(lambda item: _('Refresh Hotkeys Now'), self._refresh_hotkeys),
            Item(lambda item: _('Auto-Refresh Hotkeys'),
                 self._toggle_auto_refresh,
                 checked=lambda item: self._auto_refresh_enabled()),
            Menu.SEPARATOR,
            Item(lambda item: _('Exit'), self._exit_app)
        )

    def _tooltip_text(self):
        """Tray tooltip, which doubles as the state indicator on hover."""
        if self._state == "recording":
            return _("Quick Whisper - Recording...")
        if self._state == "processing":
            return _("Quick Whisper - Processing...")
        return "Quick Whisper"

    def set_recording(self, recording):
        """Show or clear the recording state."""
        self.set_state("recording" if recording else "idle")

    def set_processing(self, processing):
        """Show or clear the processing state.

        Ignored while recording, so a stop that has not been processed yet
        cannot make the icon flicker backwards.
        """
        if processing:
            if self._state != "recording":
                self.set_state("processing")
        elif self._state == "processing":
            self.set_state("idle")

    def set_state(self, state):
        """Switch the tray icon between idle, recording and processing.

        The tray is the only feedback available while the window is minimised
        or hidden, which is how the app is used most of the time. Safe to call
        from any thread and when there is no tray at all.
        """
        with self._lock:
            if state == self._state:
                return
            self._state = state
            self._is_recording = (state == "recording")
            icon_ref = self.icon
            if not icon_ref or not self.is_running:
                return
            image = {
                "recording": self.recording_icon_image,
                "processing": self.processing_icon_image,
            }.get(state) or self.icon_image

        try:
            # pystray redraws the tray on assignment; title updates the tooltip.
            icon_ref.icon = image
            icon_ref.title = self._tooltip_text()
        except Exception as e:
            logger.debug("Could not update the tray icon state: %s", e)

    def _auto_refresh_enabled(self):
        """Read the auto-refresh flag defensively (called from the tray thread)."""
        try:
            return bool(self.parent.auto_hotkey_refresh.get())
        except Exception:
            return False

    def setup_tray(self):
        """Set up the system tray icon"""
        pystray = _load_pystray()
        if pystray is None:
            return False

        try:
            # Load the icon image
            icon_path = self.parent.resource_path("assets/icon-32.png")
            self.icon_image = Image.open(icon_path)

            # Build the state variants once, up front - swapping icons has
            # to be instant, and a failure here must not disable the tray.
            try:
                self.recording_icon_image = make_recording_icon(self.icon_image)
            except Exception as e:
                logger.warning("Could not build the recording tray icon: %s", e)
                self.recording_icon_image = None
            try:
                self.processing_icon_image = make_processing_icon(self.icon_image)
            except Exception as e:
                logger.warning("Could not build the processing tray icon: %s", e)
                self.processing_icon_image = None

            # Create the icon
            self.icon = pystray.Icon(
                "QuickWhisper",
                self.icon_image,
                self._tooltip_text(),
                self._menu_items(pystray)
            )
            return True
        except Exception as e:
            logger.error("Error setting up system tray icon: %s", e, exc_info=True)
            self.icon = None
            return False

    def show_tray(self):
        """Show the system tray icon in a separate thread"""
        with self._lock:
            if self.is_running:
                return True

            if not self.setup_tray():
                logger.warning("Failed to set up system tray icon; tray disabled")
                return False

            # Mark as running before the thread starts so a second caller
            # cannot race in and create a second icon.
            self.is_running = True
            self._shutting_down = False

            try:
                # Run in a separate thread to not block the main thread
                # Use daemon=True so the thread won't prevent the app from exiting
                self.icon_thread = threading.Thread(
                    target=self._run_tray, args=(self.icon,), daemon=True,
                    name="QuickWhisperTray")
                self.icon_thread.start()
            except Exception as e:
                logger.error("Error starting tray icon thread: %s", e, exc_info=True)
                self.is_running = False
                self.icon = None
                self.icon_thread = None
                return False

        self._register_language_callback()
        return True

    def _register_language_callback(self):
        """Rebuild the tray menu when the UI language changes."""
        if self._language_callback_registered:
            return
        try:
            register_refresh_callback(self._on_language_change)
            self._language_callback_registered = True
        except Exception as e:
            logger.warning("Could not register tray language refresh: %s", e)

    def _unregister_language_callback(self):
        if not self._language_callback_registered:
            return
        try:
            unregister_refresh_callback(self._on_language_change)
        except Exception:
            pass
        self._language_callback_registered = False

    def _on_language_change(self):
        """Refresh the tray menu labels after a language change."""
        icon_ref = self.icon
        if not icon_ref or not self.is_running:
            return
        try:
            icon_ref.update_menu()
            logger.debug("Tray menu refreshed for language change")
        except Exception as e:
            logger.warning("Could not refresh tray menu after language change: %s", e)

    def _run_tray(self, icon):
        """Run the system tray icon (called in a thread)"""
        try:
            logger.info("Starting system tray icon")
            icon.run()
        except Exception as e:
            if self._shutting_down:
                # pystray's teardown reaches out to the notification service; on
                # a box with no notification daemon that raises a GLib
                # ServiceUnknown out of icon.run() during shutdown. Nothing is
                # wrong and there is nothing to restore.
                logger.debug("Tray backend error during shutdown (ignored): %s", e)
                return
            logger.error("Error running system tray icon: %s", e, exc_info=True)
            # The backend failed after we said the tray was up. If the window
            # is hidden the user would have no way to get it back, so restore
            # it rather than leaving them stranded.
            self.is_running = False
            if self.is_window_hidden:
                self._call_on_main(self._restore_window)
        finally:
            self.is_running = False

    def stop_tray(self):
        """Stop the system tray icon"""
        with self._lock:
            self._shutting_down = True
            icon_ref = self.icon  # Keep a local reference
            thread_ref = self.icon_thread
            was_running = self.is_running

            # Mark as not running first to prevent re-entry
            self.is_running = False
            self.icon = None
            self.icon_thread = None

        self._unregister_language_callback()

        if icon_ref and was_running:
            try:
                logger.info("Stopping tray icon...")

                # On Windows, set visibility to False before stopping
                # This is the key step that removes the icon from the tray
                if platform.system() == "Windows":
                    try:
                        icon_ref.visible = False
                    except Exception as e:
                        logger.warning("Error setting icon visibility: %s", e)

                # Stop the icon - this signals the icon.run() loop to exit
                icon_ref.stop()

            except Exception as e:
                logger.error("Error stopping tray icon: %s", e, exc_info=True)

        # Wait briefly for the icon thread to finish
        # Since it's a daemon thread, it will be killed when the main thread exits anyway
        if thread_ref and thread_ref.is_alive() and thread_ref is not threading.current_thread():
            try:
                thread_ref.join(timeout=1.0)  # Wait up to 1 second
                if thread_ref.is_alive():
                    logger.warning("Tray thread still running, will be terminated on exit")
            except Exception as e:
                logger.warning("Error joining tray icon thread: %s", e)

        logger.info("Tray icon stopped")

    def _call_on_main(self, func):
        """Marshal a call onto the Tk main thread, tolerating a dead window."""
        try:
            self.parent.after(0, func)
            return True
        except Exception as e:
            # Window already destroyed, or Tk is shutting down.
            logger.debug("Could not schedule tray callback on main thread: %s", e)
            return False

    def _toggle_window(self):
        """Toggle the visibility of the main window"""
        # Called from the tray thread - never touch widgets directly here.
        self._call_on_main(self._do_toggle_window)

    def _restore_window(self):
        """Bring the main window back (main thread)."""
        try:
            self.parent.deiconify()
            self.parent.lift()
            self.parent.focus_force()
        except tk.TclError as e:
            logger.debug("Could not restore window: %s", e)
        self.is_window_hidden = False

    def _do_toggle_window(self):
        """Actually perform the window toggle (on main thread)"""
        if self.is_window_hidden:
            self._restore_window()
        else:
            self._hide_window()

    def _hide_window(self):
        """Hide the main window (main thread), without trapping the user."""
        try:
            if self.is_running:
                # There is a tray icon to bring it back with.
                self.parent.withdraw()
                self.is_window_hidden = True
            else:
                # No tray icon: withdraw() would leave the window unreachable,
                # so iconify instead - the window manager can still restore it.
                logger.info("Tray not running; minimising to taskbar instead of hiding")
                self.parent.iconify()
                self.is_window_hidden = False
        except tk.TclError as e:
            logger.debug("Could not hide window: %s", e)

    def _refresh_hotkeys(self):
        """Refresh the keyboard shortcuts"""
        # Resolve the manager inside the callback: the parent may already be
        # tearing down when the tray fires this.
        self._call_on_main(lambda: self.parent.hotkey_manager.force_hotkey_refresh())

    def _open_settings(self):
        """Open the settings dialog from the tray.

        Both this and History bring the window up first: a modal dialog with
        no visible parent behind it is disorienting, and the user is going
        back to the window afterwards anyway.
        """
        def show():
            self.parent.deiconify()
            self.parent.lift()
            self.parent.open_config()
        self._call_on_main(show)

    def _open_history(self):
        """Open the history browser from the tray."""
        def show():
            self.parent.deiconify()
            self.parent.lift()
            self.parent.show_history()
        self._call_on_main(show)

    def _exit_app(self):
        """Exit the application"""
        self._call_on_main(lambda: self.parent.on_closing())

    def minimize_to_tray(self):
        """Minimize the window to the system tray"""
        # Ensure tray is set up before minimizing
        if not self.is_running:
            if not self.show_tray():
                # Degrade gracefully: minimise normally rather than either
                # doing nothing or hiding a window the user cannot get back.
                logger.warning("System tray unavailable; minimising to taskbar instead")
                self._hide_window()
                return

        self._hide_window()

    def _toggle_auto_refresh(self):
        """Toggle the auto-refresh hotkeys setting"""
        self._call_on_main(self._do_toggle_auto_refresh)

    def _do_toggle_auto_refresh(self):
        """Actually perform the auto-refresh toggle (on main thread)"""
        try:
            current_value = self.parent.auto_hotkey_refresh.get()
            self.parent.auto_hotkey_refresh.set(not current_value)
            self.parent.save_auto_hotkey_refresh()
        except Exception as e:
            logger.error("Could not toggle auto-refresh from tray: %s", e, exc_info=True)
            return
        new_state = "enabled" if not current_value else "disabled"
        logger.info("Auto-refresh hotkeys %s from tray menu", new_state)
