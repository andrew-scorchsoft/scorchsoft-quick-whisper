import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, Menu

class ToolTip():
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None

        # Bind the hover events to show/hide tooltip
        widget.bind("<Enter>", self.show_tooltip)
        widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        # Create tooltip window
        if self.tooltip_window or not self.text:
            return
        
        # Position the tooltip window just below the widget
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        # Create a new top-level window for the tooltip
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)  # Remove window decorations
        self.tooltip_window.wm_geometry(f"+{x}+{y}")   # Position the tooltip

        # Add a label with the tooltip text
        label = tk.Label(self.tooltip_window, text=self.text, background="white", relief="solid", borderwidth=1, font=("Arial", 10))
        label.pack(ipadx=5, ipady=2)

    def hide_tooltip(self, event=None):
        # Destroy the tooltip window if it exists
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None