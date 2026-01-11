import tkinter as tk


class ToolTip():
    """Minimal, refined tooltip."""
    
    BG_COLOR = "#27272a"
    TEXT_COLOR = "#fafafa"
    
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None

        widget.bind("<Enter>", self.show_tooltip)
        widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.text:
            return
        
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        self.tooltip_window.attributes("-topmost", True)
        self.tooltip_window.configure(bg=self.BG_COLOR)

        label = tk.Label(
            self.tooltip_window, 
            text=self.text, 
            background=self.BG_COLOR,
            foreground=self.TEXT_COLOR,
            font=("Segoe UI", 9),
            padx=8, pady=4
        )
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
