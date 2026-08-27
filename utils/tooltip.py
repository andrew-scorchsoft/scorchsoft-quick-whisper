import tkinter as tk

from utils.app_logging import get_logger
from utils.theme import get_font, theme_colors

logger = get_logger(__name__)


class ToolTip():
    """Minimal tooltip that follows the active theme.

    Colours are read when the tooltip is shown rather than captured at import
    time, so a tooltip opened after a theme switch matches the new palette.
    """

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None

        # add="+" so an existing <Enter>/<Leave> binding on the widget (hover
        # styling, for example) is not silently replaced by the tooltip.
        widget.bind("<Enter>", self.show_tooltip, add="+")
        widget.bind("<Leave>", self.hide_tooltip, add="+")
        # Keyboard users reach these controls by Tab, never by hover, so the
        # tooltip has to follow focus as well to stay readable to them.
        widget.bind("<FocusIn>", self.show_tooltip, add="+")
        widget.bind("<FocusOut>", self.hide_tooltip, add="+")
        # A click usually opens something on top of us; get out of the way.
        widget.bind("<ButtonPress>", self.hide_tooltip, add="+")
        # Never outlive the widget we are attached to.
        widget.bind("<Destroy>", self._on_widget_destroyed, add="+")

    def set_text(self, text):
        """Change the tooltip text, refreshing it if it is currently showing."""
        self.text = text
        if self.tooltip_window:
            self.hide_tooltip()

    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.text:
            return

        try:
            if not self.widget.winfo_exists():
                return

            x = self.widget.winfo_rootx() + 10
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4

            colors = theme_colors()

            self.tooltip_window = tk.Toplevel(self.widget)
            self.tooltip_window.wm_overrideredirect(True)
            self.tooltip_window.wm_geometry(f"+{x}+{y}")
            self.tooltip_window.attributes("-topmost", True)
            # The border is what keeps the chip readable in light mode, where
            # its fill is close to the window behind it.
            self.tooltip_window.configure(
                bg=colors.BORDER,
                highlightthickness=0,
            )

            label = tk.Label(
                self.tooltip_window,
                text=self.text,
                background=colors.BG_TERTIARY,
                foreground=colors.TEXT_PRIMARY,
                font=get_font('xxs'),
                padx=8, pady=4
            )
            # 1px of the Toplevel's background shows through as the border.
            label.pack(padx=1, pady=1)
        except tk.TclError as e:
            # The widget (or the whole app) went away mid-hover.
            logger.debug("Could not show tooltip: %s", e)
            self.hide_tooltip()

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            try:
                self.tooltip_window.destroy()
            except tk.TclError:
                pass  # Already gone, e.g. during app shutdown
            self.tooltip_window = None

    def _on_widget_destroyed(self, event=None):
        """Tear the tooltip down with its widget.

        Without this a tooltip left on screen when its widget is destroyed
        (a rebuilt toolbar, a language change) becomes an orphan Toplevel
        that nothing can close.
        """
        # <Destroy> also fires for child widgets; only act on our own.
        if event is not None and event.widget is not self.widget:
            return
        self.hide_tooltip()
