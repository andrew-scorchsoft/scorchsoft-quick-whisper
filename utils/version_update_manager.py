import json
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from urllib.parse import urlparse
import requests
from packaging import version
from packaging.version import InvalidVersion
from utils.config_manager import get_config
from utils.theme import get_font, get_spacing, get_window_size
from utils.platform import open_url
from utils.app_logging import get_logger
from utils.i18n import _

logger = get_logger(__name__)

# The version manifest is a tiny JSON document; refuse anything larger so a
# misbehaving (or hostile) server cannot stream gigabytes into the app.
MAX_MANIFEST_BYTES = 64 * 1024
# (connect, read) timeouts - a server that accepts the connection then stalls
# must not hang the update thread forever.
REQUEST_TIMEOUT = (5, 10)


def _is_safe_download_url(url):
    """Only allow plain http(s) links from the remote manifest.

    ``open_url`` hands the string to the OS handler, so a ``file:``,
    ``javascript:`` or shell-ish URL from a compromised/typo'd manifest must
    never reach it.
    """
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


class VersionUpdateManager:
    def __init__(self, parent):
        self.parent = parent
        self.version_check_url = "https://www.scorchsoft.com/public/blog/quick-whisper-speech-to-copyedited-text/latest-version.json"
        self.auto_update_check = tk.BooleanVar(value=True)
        self.config = get_config()

        # Load settings from config
        self.auto_update_check.set(self.config.auto_update_check)

    def start_check(self, delay=2000):
        """Start the update check with delay to avoid blocking app startup"""
        if self.auto_update_check.get():
            self.parent.after(delay, self._start_check_thread)

    def _start_check_thread(self):
        """Kick off the background check on a daemon thread."""
        # daemon=True: a slow network request must never keep the app alive
        # after the user has closed the window.
        threading.Thread(target=self.check_for_updates, daemon=True,
                         name="QuickWhisperUpdateCheck").start()

    def save_auto_update_setting(self):
        """Save the auto update setting to settings.json."""
        self.config.auto_update_check = self.auto_update_check.get()
        self.config.save_settings()
        logger.info("Auto update check setting saved: %s", self.auto_update_check.get())

    def _on_main_thread(self, func, *args):
        """Run a Tk-touching callback on the main thread."""
        try:
            self.parent.after(0, lambda: func(*args))
        except Exception as e:
            logger.debug("Could not schedule update UI callback: %s", e)

    def _fetch_manifest(self):
        """Fetch and parse the version manifest, with size and time limits."""
        response = requests.get(self.version_check_url,
                                timeout=REQUEST_TIMEOUT, stream=True)
        try:
            if response.status_code != 200:
                return None, response.status_code

            body = b""
            for chunk in response.iter_content(8192):
                body += chunk
                if len(body) > MAX_MANIFEST_BYTES:
                    raise ValueError("version manifest is unexpectedly large")
            return json.loads(body.decode("utf-8", errors="replace")), 200
        finally:
            response.close()

    def check_for_updates(self, manual_check=False):
        """Check for updates from the version check URL.

        Safe to call from a background thread - all UI work is marshalled onto
        the Tk main thread.
        """
        try:
            version_data, status_code = self._fetch_manifest()
            if version_data is None:
                logger.warning("Update check failed: server returned status %s", status_code)
                if manual_check:
                    self._on_main_thread(
                        messagebox.showwarning,
                        _("Update Check Failed"),
                        _("Could not check for updates. Server returned status code: {code}").format(
                            code=status_code)
                    )
                return

            latest_version = version_data.get("latestVersion")
            download_url = version_data.get("downloadUrl")
            notification_message = version_data.get("notificationMessage")

            # Check if there's a newer version available using semantic
            # versioning. A malformed version string from the remote server
            # must not raise out of the update thread.
            newer = False
            if latest_version:
                try:
                    newer = version.parse(str(latest_version)) > version.parse(self.parent.version)
                except (InvalidVersion, TypeError) as e:
                    logger.warning("Ignoring unparseable version from update manifest (%r): %s",
                                   latest_version, e)

            if newer:
                self._on_main_thread(self.show_update_notification,
                                     latest_version, download_url, notification_message)
            elif manual_check:
                self._on_main_thread(
                    messagebox.showinfo,
                    _("Update Check"),
                    _("You are running the latest version ({version}).").format(
                        version=self.parent.version)
                )
        except Exception as e:
            logger.warning("Update check failed: %s", e)
            if manual_check:
                self._on_main_thread(
                    messagebox.showwarning,
                    _("Update Check Failed"),
                    _("Could not check for updates: {error}").format(error=str(e))
                )

    def _position_dialog(self, window, width, height):
        """Centre on the main window when sensible, else on the screen.

        The main window may be minimised, withdrawn to the tray, or left
        off-screen from a previous multi-monitor session, so its coordinates
        cannot be trusted blindly.
        """
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()

        x = y = None
        try:
            if self.parent.state() == "normal" and self.parent.winfo_viewable():
                x = self.parent.winfo_x() + (self.parent.winfo_width() - width) // 2
                y = self.parent.winfo_y() + (self.parent.winfo_height() - height) // 2
        except Exception:
            x = y = None

        if x is None or y is None:
            x = (screen_w - width) // 2
            y = (screen_h - height) // 2

        # Clamp so the dialog is always fully on-screen and reachable.
        x = max(0, min(x, screen_w - width))
        y = max(0, min(y, screen_h - height))
        window.geometry(f"{width}x{height}+{x}+{y}")

    def show_update_notification(self, latest_version, download_url, message):
        """Show a notification about an available update."""
        # Create a notification window
        notification = tk.Toplevel(self.parent)
        notification.withdraw()  # Hide until it is built and positioned
        notification.title(_("Update Available"))

        # Get window dimensions from theme
        notification_width, notification_height = get_window_size('version_notification')
        notification.resizable(False, False)

        pad = get_spacing('lg')
        gap = get_spacing('xs')

        # ttk widgets so the dialog picks up the Sun Valley theme (and follows
        # light/dark mode) instead of rendering as raw grey Tk labels.
        container = ttk.Frame(notification, padding=pad)
        container.pack(fill="both", expand=True)

        heading = ttk.Label(
            container,
            text=_("Update Available"),
            font=get_font('lg', 'bold'),
            anchor="center",
        )
        heading.pack(fill="x", pady=(0, gap))

        if message:
            body = ttk.Label(
                container,
                text=str(message),
                font=get_font('sm'),
                wraplength=notification_width - (pad * 4),
                justify="center",
                anchor="center",
            )
            body.pack(fill="x", pady=(0, gap))

        versions = ttk.Label(
            container,
            text=_("Current version: {current}    Latest version: {latest}").format(
                current=self.parent.version, latest=latest_version),
            font=get_font('xs'),
            anchor="center",
        )
        versions.pack(fill="x", pady=(0, pad))

        # Centred button row, like the app's other dialogs.
        buttons = ttk.Frame(container)
        buttons.pack()

        if _is_safe_download_url(download_url):
            download_button = ttk.Button(
                buttons,
                text=_("Download Update"),
                style="Accent.TButton",
                command=lambda: self.open_download_page(download_url, notification)
            )
            download_button.pack(side="left", padx=(0, gap))
            download_button.focus_set()
        else:
            # Do not offer a button we would refuse to action.
            logger.warning("Update manifest supplied an unusable download URL: %r", download_url)
            ttk.Label(buttons, text=_("See scorchsoft.com for the download."),
                      font=get_font('xs')).pack(side="left", padx=(0, gap))

        close_button = ttk.Button(buttons, text=_("Close"),
                                  command=lambda: self._close_dialog(notification))
        close_button.pack(side="left")
        if not _is_safe_download_url(download_url):
            close_button.focus_set()

        # Grow the dialog if the (translated) content needs more room, so
        # nothing is clipped by the fixed theme size.
        notification.update_idletasks()
        notification_height = max(notification_height, container.winfo_reqheight())
        notification_width = max(notification_width, container.winfo_reqwidth())
        self._position_dialog(notification, notification_width, notification_height)

        # Behave like the app's other dialogs: modal, on top of its parent,
        # closable with the window manager button or Escape.
        notification.transient(self.parent)
        notification.protocol("WM_DELETE_WINDOW", lambda: self._close_dialog(notification))
        notification.bind("<Escape>", lambda e: self._close_dialog(notification))
        notification.deiconify()
        notification.lift()
        try:
            notification.grab_set()
        except tk.TclError as e:
            logger.debug("Could not make update dialog modal: %s", e)

        return notification

    def _close_dialog(self, window):
        """Release the modal grab and destroy the dialog."""
        try:
            window.grab_release()
        except Exception:
            pass
        try:
            window.destroy()
        except Exception:
            pass

    def open_download_page(self, url, notification_window=None):
        """Open the download page in a web browser."""
        if not _is_safe_download_url(url):
            logger.warning("Refusing to open non-http(s) download URL: %r", url)
        else:
            open_url(url)
        if notification_window:
            self._close_dialog(notification_window)
