"""Shared conventions for dialog windows.

Every dialog in the app used to position itself with its own copy of
``parent.winfo_x() + (parent.winfo_width() - width) // 2`` and bind (or, more
often, not bind) its own keys. That left dialogs opening off-screen whenever
the main window was minimised, near a screen edge, or left on a monitor that is
no longer attached, and left Escape working in one dialog out of nine.

These helpers are the single implementation of both.
"""

import tkinter as tk

from utils.app_logging import get_logger

logger = get_logger(__name__)


def position_dialog(window, width, height, parent=None):
    """Centre a dialog on its parent when sensible, else on the screen.

    The parent may be minimised, withdrawn to the tray, unrealized, or left
    off-screen by a previous multi-monitor session, so its coordinates cannot
    be trusted blindly. The result is always clamped fully on-screen.
    """
    if parent is None:
        parent = window.master

    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()

    x = y = None
    try:
        if (parent is not None
                and parent.winfo_exists()
                and parent.winfo_viewable()
                and parent.winfo_width() > 1):
            x = parent.winfo_x() + (parent.winfo_width() - width) // 2
            y = parent.winfo_y() + (parent.winfo_height() - height) // 2
    except Exception:
        x = y = None

    if x is None or y is None:
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2

    # Clamp so the dialog is always fully on-screen and reachable.
    x = max(0, min(x, max(0, screen_w - width)))
    y = max(0, min(y, max(0, screen_h - height)))
    window.geometry(f"{width}x{height}+{x}+{y}")


def _focus_is_multiline(window):
    """Whether the focused widget is a Text box that owns the Return key."""
    try:
        widget = window.focus_get()
    except Exception:
        return False
    return isinstance(widget, tk.Text)


def bind_dialog_keys(window, on_cancel=None, on_accept=None):
    """Give a dialog the keyboard behaviour people already expect.

    Escape cancels, Return activates the primary action. Return is ignored
    while a multi-line Text has focus, so typing a prompt body cannot submit
    the dialog out from under the user.
    """
    if on_cancel is not None:
        def _cancel(_event=None):
            on_cancel()
            return "break"
        window.bind("<Escape>", _cancel)

    if on_accept is not None:
        def _accept(_event=None):
            if _focus_is_multiline(window):
                return None
            on_accept()
            return "break"
        window.bind("<Return>", _accept)
        window.bind("<KP_Enter>", _accept)


def focus_first(widget):
    """Put the caret in a dialog's first field once it is mapped.

    Several dialogs opened with focus nowhere, so Tab did nothing at all until
    the user clicked into the window first.
    """
    if widget is None:
        return
    try:
        widget.after(50, widget.focus_set)
    except Exception:
        logger.debug("Could not focus the first dialog field", exc_info=True)
