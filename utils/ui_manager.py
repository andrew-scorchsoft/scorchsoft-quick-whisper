import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from PIL import Image, ImageTk
import webbrowser
import platform
import ctypes

from utils.tooltip import ToolTip
from utils.config_manager import get_config


# ═══════════════════════════════════════════════════════════════════════════════
# SCORCHSOFT BRAND THEME - Dark with Red Accents
# ═══════════════════════════════════════════════════════════════════════════════

class ModernTheme:
    """Scorchsoft-branded dark theme with proper contrast."""
    
    # Background colors
    BG_PRIMARY = "#0d0d0d"        # Deep black
    BG_SECONDARY = "#171717"      # Card surfaces  
    BG_TERTIARY = "#1f1f1f"       # Input fields
    BG_HOVER = "#2a2a2a"          # Hover states
    BG_MENU = "#141414"           # Menu bar background
    
    # Scorchsoft Brand - Red/Crimson palette
    ACCENT_PRIMARY = "#dc2626"    # Scorchsoft red
    ACCENT_HOVER = "#ef4444"      # Lighter red on hover
    ACCENT_MUTED = "#dc262630"    # Transparent accent
    
    # Secondary - Darker, muted red for second button
    SECONDARY_PRIMARY = "#991b1b"  # Darker crimson
    SECONDARY_HOVER = "#b91c1c"    # Mid crimson
    
    # Text colors - GOOD CONTRAST for accessibility
    TEXT_PRIMARY = "#ffffff"      # Pure white for main text
    TEXT_SECONDARY = "#e5e5e5"    # Very light gray - highly readable
    TEXT_TERTIARY = "#b3b3b3"     # Light gray - readable
    TEXT_MUTED = "#808080"        # Medium gray for less important
    
    # Status colors
    STATUS_IDLE = "#b3b3b3"       # Neutral
    STATUS_PROCESSING = "#fbbf24" # Amber
    STATUS_RECORDING = "#ef4444"  # Red
    STATUS_SUCCESS = "#22c55e"    # Green
    
    # Borders
    BORDER = "#2a2a2a"
    BORDER_SUBTLE = "#1f1f1f"
    BORDER_FOCUS = "#dc2626"
    
    # Font
    FONT_FAMILY = "Segoe UI"
    
    # Sizing
    CORNER_RADIUS = 8
    CORNER_RADIUS_SM = 6


def set_dark_title_bar(window):
    """Set Windows title bar to dark mode."""
    if platform.system() != "Windows":
        return
        
    try:
        window.update()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value), ctypes.sizeof(value)
        )
    except Exception as e:
        print(f"Could not set dark title bar: {e}")


class UIManager:
    def __init__(self, parent):
        self.parent = parent
        self.banner_visible = True
        self.theme = ModernTheme()
        
        # Store UI element references
        self.transcription_text = None
        self.status_label = None
        self.status_dot = None
        self.model_label = None
        self.record_button_transcribe = None
        self.record_button_edit = None
        self.banner_label = None
        self.hide_banner_link = None
        self.powered_by_label = None
        self.banner_photo = None
        self.button_first_page = None
        self.button_arrow_left = None
        self.button_arrow_right = None
        self.main_frame = None
        self.banner_frame = None
        self.shortcut_label_left = None
        self.shortcut_label_right = None
        self.custom_menubar = None
        
        ctk.set_appearance_mode("dark")
        
    def create_widgets(self):
        """Create all UI widgets with Scorchsoft branding."""
        
        set_dark_title_bar(self.parent)
        self.parent.configure(bg=self.theme.BG_PRIMARY)
        
        # Hide the default tkinter menu bar - we'll create a custom one
        # Note: The parent still has the menu for functionality, but we overlay it
        
        # Main container
        self.main_frame = ctk.CTkFrame(
            self.parent, 
            fg_color=self.theme.BG_PRIMARY,
            corner_radius=0
        )
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ─────────────────────────────────────────────────────────────────────
        # CUSTOM DARK MENU BAR
        # ─────────────────────────────────────────────────────────────────────
        
        self.custom_menubar = ctk.CTkFrame(
            self.main_frame,
            fg_color=self.theme.BG_MENU,
            height=32,
            corner_radius=0
        )
        self.custom_menubar.pack(fill=tk.X, side=tk.TOP)
        self.custom_menubar.pack_propagate(False)
        
        menu_btn_style = {
            "font": (self.theme.FONT_FAMILY, 11),
            "text_color": self.theme.TEXT_SECONDARY,
            "fg_color": "transparent",
            "hover_color": self.theme.BG_HOVER,
            "corner_radius": 4,
            "height": 26,
            "anchor": "center"
        }
        
        # Menu buttons that trigger the actual menus
        file_btn = ctk.CTkButton(self.custom_menubar, text="File", width=50,
                                  command=lambda: self._show_menu("file"), **menu_btn_style)
        file_btn.pack(side=tk.LEFT, padx=(8, 0), pady=3)
        
        settings_btn = ctk.CTkButton(self.custom_menubar, text="Settings", width=65,
                                      command=lambda: self._show_menu("settings"), **menu_btn_style)
        settings_btn.pack(side=tk.LEFT, padx=0, pady=3)
        
        actions_btn = ctk.CTkButton(self.custom_menubar, text="Actions", width=60,
                                     command=lambda: self._show_menu("actions"), **menu_btn_style)
        actions_btn.pack(side=tk.LEFT, padx=0, pady=3)
        
        help_btn = ctk.CTkButton(self.custom_menubar, text="Help", width=50,
                                  command=lambda: self._show_menu("help"), **menu_btn_style)
        help_btn.pack(side=tk.LEFT, padx=0, pady=3)
        
        # Store button references for menu positioning
        self._menu_buttons = {
            "file": file_btn,
            "settings": settings_btn,
            "actions": actions_btn,
            "help": help_btn
        }
        
        # Content with generous margins
        content = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        content.pack(fill=tk.BOTH, expand=True, padx=28, pady=(16, 24))
        
        # ─────────────────────────────────────────────────────────────────────
        # INPUT DEVICE SECTION
        # ─────────────────────────────────────────────────────────────────────
        
        device_label = ctk.CTkLabel(
            content,
            text="Input Device",
            font=(self.theme.FONT_FAMILY, 12, "bold"),
            text_color=self.theme.TEXT_SECONDARY
        )
        device_label.pack(anchor="w", pady=(0, 8))
        
        devices = self.parent.audio_manager.get_input_devices()
        if not devices:
            tk.messagebox.showerror("No Input Devices", "No input audio devices found.")
            self.parent.destroy()
            return
        
        config = get_config()
        saved_device = config.selected_input_device
        if saved_device and saved_device in devices:
            self.parent.selected_device.set(saved_device)
        else:
            self.parent.selected_device.set(list(devices.keys())[0])
        
        def on_device_change(*args):
            new_device = self.parent.selected_device.get()
            config.selected_input_device = new_device
            config.save_settings()
        
        self.parent.selected_device.trace_add("write", on_device_change)
        
        device_menu = ctk.CTkOptionMenu(
            content,
            variable=self.parent.selected_device,
            values=list(devices.keys()),
            fg_color=self.theme.BG_SECONDARY,
            button_color=self.theme.BG_SECONDARY,
            button_hover_color=self.theme.BG_HOVER,
            dropdown_fg_color=self.theme.BG_SECONDARY,
            dropdown_hover_color=self.theme.BG_HOVER,
            dropdown_text_color=self.theme.TEXT_PRIMARY,
            text_color=self.theme.TEXT_PRIMARY,
            font=(self.theme.FONT_FAMILY, 13),
            dropdown_font=(self.theme.FONT_FAMILY, 13),
            corner_radius=self.theme.CORNER_RADIUS_SM,
            height=44,
            anchor="w",
            dynamic_resizing=False
        )
        device_menu.pack(fill=tk.X, pady=(0, 20))
        
        # ─────────────────────────────────────────────────────────────────────
        # TRANSCRIPTION SECTION
        # ─────────────────────────────────────────────────────────────────────
        
        header_row = ctk.CTkFrame(content, fg_color="transparent")
        header_row.pack(fill=tk.X, pady=(0, 8))
        
        transcription_label = ctk.CTkLabel(
            header_row,
            text="Transcription",
            font=(self.theme.FONT_FAMILY, 12, "bold"),
            text_color=self.theme.TEXT_SECONDARY
        )
        transcription_label.pack(side=tk.LEFT)
        
        # Navigation buttons - NOW VISIBLE with proper contrast
        nav_frame = ctk.CTkFrame(header_row, fg_color="transparent")
        nav_frame.pack(side=tk.RIGHT)
        
        nav_btn_style = {
            "width": 30,
            "height": 30,
            "corner_radius": 6,
            "fg_color": self.theme.BG_TERTIARY,  # Visible background
            "hover_color": self.theme.BG_HOVER,
            "text_color": self.theme.TEXT_SECONDARY,  # Bright text
            "text_color_disabled": self.theme.TEXT_MUTED,
            "font": (self.theme.FONT_FAMILY, 12),
            "border_width": 1,
            "border_color": self.theme.BORDER
        }
        
        self.button_first_page = ctk.CTkButton(
            nav_frame, text="⏮", command=self.parent.go_to_first_page,
            state="disabled", **nav_btn_style
        )
        self.button_first_page.pack(side=tk.LEFT, padx=2)
        
        self.button_arrow_left = ctk.CTkButton(
            nav_frame, text="◀", command=self.parent.navigate_left,
            state="disabled", **nav_btn_style
        )
        self.button_arrow_left.pack(side=tk.LEFT, padx=2)
        
        self.button_arrow_right = ctk.CTkButton(
            nav_frame, text="▶", command=self.parent.navigate_right,
            state="disabled", **nav_btn_style
        )
        self.button_arrow_right.pack(side=tk.LEFT, padx=2)
        
        ToolTip(self.button_first_page, "Latest entry")
        ToolTip(self.button_arrow_left, "Newer")
        ToolTip(self.button_arrow_right, "Older")
        
        # Text area
        self.transcription_text = ctk.CTkTextbox(
            content,
            height=200,
            fg_color=self.theme.BG_SECONDARY,
            text_color=self.theme.TEXT_PRIMARY,
            font=(self.theme.FONT_FAMILY, 14),
            corner_radius=self.theme.CORNER_RADIUS_SM,
            border_width=1,
            border_color=self.theme.BORDER,
            wrap="word"
        )
        self.transcription_text.pack(fill=tk.BOTH, expand=True, pady=(0, 12))
        self.transcription_text.bind("<Button-3>", self._show_text_context_menu)
        
        # ─────────────────────────────────────────────────────────────────────
        # STATUS BAR - LARGER FONT
        # ─────────────────────────────────────────────────────────────────────
        
        status_row = ctk.CTkFrame(content, fg_color="transparent")
        status_row.pack(fill=tk.X, pady=(0, 12))
        
        status_left = ctk.CTkFrame(status_row, fg_color="transparent")
        status_left.pack(side=tk.LEFT)
        
        self.status_dot = ctk.CTkLabel(
            status_left, text="●", width=16,
            font=(self.theme.FONT_FAMILY, 10),
            text_color=self.theme.STATUS_IDLE
        )
        self.status_dot.pack(side=tk.LEFT, padx=(0, 6))
        
        self.status_label = ctk.CTkLabel(
            status_left, text="Idle",
            font=(self.theme.FONT_FAMILY, 13),  # Larger
            text_color=self.theme.TEXT_TERTIARY
        )
        self.status_label.pack(side=tk.LEFT)
        
        # Model info - LARGER AND BRIGHTER
        self.model_label = ctk.CTkLabel(
            status_row,
            text=f"{self.parent.transcription_model} · {self.parent.ai_model}",
            font=(self.theme.FONT_FAMILY, 12),  # Larger
            text_color=self.theme.TEXT_TERTIARY  # Brighter
        )
        self.model_label.pack(side=tk.RIGHT)
        
        # ─────────────────────────────────────────────────────────────────────
        # OPTIONS
        # ─────────────────────────────────────────────────────────────────────
        
        options_row = ctk.CTkFrame(content, fg_color="transparent")
        options_row.pack(fill=tk.X, pady=(0, 16))
        
        cb_style = {
            "font": (self.theme.FONT_FAMILY, 12),
            "text_color": self.theme.TEXT_SECONDARY,
            "fg_color": self.theme.ACCENT_PRIMARY,
            "hover_color": self.theme.ACCENT_HOVER,
            "border_color": self.theme.TEXT_MUTED,
            "checkmark_color": self.theme.TEXT_PRIMARY,
            "corner_radius": 4,
            "border_width": 2,
            "checkbox_width": 18,
            "checkbox_height": 18
        }
        
        auto_copy_cb = ctk.CTkCheckBox(
            options_row, text="Copy to clipboard",
            variable=self.parent.auto_copy, **cb_style
        )
        auto_copy_cb.pack(side=tk.LEFT)
        
        auto_paste_cb = ctk.CTkCheckBox(
            options_row, text="Auto-paste",
            variable=self.parent.auto_paste, **cb_style
        )
        auto_paste_cb.pack(side=tk.RIGHT)
        
        # ─────────────────────────────────────────────────────────────────────
        # ACTION BUTTONS
        # ─────────────────────────────────────────────────────────────────────
        
        buttons_frame = ctk.CTkFrame(content, fg_color="transparent")
        buttons_frame.pack(fill=tk.X, pady=(0, 6))
        buttons_frame.columnconfigure(0, weight=1)
        buttons_frame.columnconfigure(1, weight=1)
        
        self.record_button_transcribe = ctk.CTkButton(
            buttons_frame,
            text="Record + Transcript",
            corner_radius=self.theme.CORNER_RADIUS,
            height=48,
            fg_color=self.theme.ACCENT_PRIMARY,
            hover_color=self.theme.ACCENT_HOVER,
            text_color=self.theme.TEXT_PRIMARY,
            font=(self.theme.FONT_FAMILY, 13, "bold"),
            command=lambda: self.parent.toggle_recording("transcribe")
        )
        self.record_button_transcribe.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        
        self.record_button_edit = ctk.CTkButton(
            buttons_frame,
            text="Record + AI Edit",
            corner_radius=self.theme.CORNER_RADIUS,
            height=48,
            fg_color=self.theme.SECONDARY_PRIMARY,
            hover_color=self.theme.SECONDARY_HOVER,
            text_color=self.theme.TEXT_PRIMARY,
            font=(self.theme.FONT_FAMILY, 13, "bold"),
            command=lambda: self.parent.toggle_recording("edit")
        )
        self.record_button_edit.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        
        # Shortcut hints - LARGER FONT
        hints_frame = ctk.CTkFrame(content, fg_color="transparent")
        hints_frame.pack(fill=tk.X, pady=(4, 12))
        hints_frame.columnconfigure(0, weight=1)
        hints_frame.columnconfigure(1, weight=1)
        
        shortcut_transcribe = "Cmd+Alt+Shift+J" if self.parent.is_mac else "Ctrl+Alt+Shift+J"
        shortcut_edit = "Cmd+Alt+J" if self.parent.is_mac else "Ctrl+Alt+J"
        
        self.shortcut_label_left = ctk.CTkLabel(
            hints_frame, text=shortcut_transcribe,
            font=(self.theme.FONT_FAMILY, 12),  # Larger
            text_color=self.theme.TEXT_TERTIARY  # Brighter
        )
        self.shortcut_label_left.grid(row=0, column=0)
        
        self.shortcut_label_right = ctk.CTkLabel(
            hints_frame, text=shortcut_edit,
            font=(self.theme.FONT_FAMILY, 12),  # Larger
            text_color=self.theme.TEXT_TERTIARY  # Brighter
        )
        self.shortcut_label_right.grid(row=0, column=1)
        
        # ─────────────────────────────────────────────────────────────────────
        # BANNER SECTION
        # ─────────────────────────────────────────────────────────────────────
        
        self.banner_frame = ctk.CTkFrame(content, fg_color="transparent")
        self.banner_frame.pack(fill=tk.X)
        
        try:
            banner_path = self.parent.resource_path("assets/banner-00-560.png")
            banner_img = Image.open(banner_path)
            self.banner_photo = ImageTk.PhotoImage(banner_img)
            
            self.banner_label = tk.Label(
                self.banner_frame, image=self.banner_photo,
                cursor="hand2", bg=self.theme.BG_PRIMARY
            )
            self.banner_label.pack(pady=(0, 8))
            self.banner_label.bind("<Button-1>", lambda e: self.open_scorchsoft())
        except Exception as e:
            print(f"Banner load error: {e}")
        
        self.hide_banner_link = ctk.CTkLabel(
            self.banner_frame, text="Hide Banner",
            font=(self.theme.FONT_FAMILY, 11),
            text_color=self.theme.TEXT_MUTED, cursor="hand2"
        )
        self.hide_banner_link.pack()
        self.hide_banner_link.bind("<Button-1>", lambda e: self.parent.toggle_banner())
        self.hide_banner_link.bind("<Enter>", lambda e: self.hide_banner_link.configure(text_color=self.theme.ACCENT_PRIMARY))
        self.hide_banner_link.bind("<Leave>", lambda e: self.hide_banner_link.configure(text_color=self.theme.TEXT_MUTED))
        
        self.powered_by_label = ctk.CTkLabel(
            self.banner_frame, text="Powered by Scorchsoft.com",
            font=(self.theme.FONT_FAMILY, 11),
            text_color=self.theme.TEXT_MUTED, cursor="hand2"
        )
        self.powered_by_label.bind("<Button-1>", lambda e: self.open_scorchsoft())
        self.powered_by_label.bind("<Enter>", lambda e: self.powered_by_label.configure(text_color=self.theme.ACCENT_PRIMARY))
        self.powered_by_label.bind("<Leave>", lambda e: self.powered_by_label.configure(text_color=self.theme.TEXT_MUTED))
        
        return self.main_frame
    
    def _show_menu(self, menu_name):
        """Show the corresponding menu at the button location."""
        menu_map = {
            "file": getattr(self.parent, 'file_menu', None),
            "settings": getattr(self.parent, 'settings_menu', None),
            "actions": getattr(self.parent, 'actions_menu', None),
            "help": getattr(self.parent, 'help_menu', None)
        }
        
        menu = menu_map.get(menu_name)
        btn = self._menu_buttons.get(menu_name)
        
        if menu and btn:
            x = btn.winfo_rootx()
            y = btn.winfo_rooty() + btn.winfo_height()
            menu.tk_popup(x, y)
        
    def open_scorchsoft(self, event=None):
        webbrowser.open('https://www.scorchsoft.com/contact-scorchsoft')
        
    def toggle_banner(self):
        current_height = self.parent.winfo_height()
        delta = 260
        new_height = current_height + delta if not self.banner_visible else current_height - delta

        if self.banner_visible:
            if self.banner_label:
                self.banner_label.pack_forget()
            self.hide_banner_link.pack_forget()
            self.powered_by_label.pack(pady=(8, 0))
            self.parent.help_menu.entryconfig("Hide Banner", label="Show Banner")
        else:
            if self.banner_label:
                self.banner_label.pack(pady=(0, 8))
            self.powered_by_label.pack_forget()
            self.hide_banner_link.pack()
            self.parent.help_menu.entryconfig("Show Banner", label="Hide Banner")

        self.parent.geometry(f"{self.parent.winfo_width()}x{new_height}")
        self.banner_visible = not self.banner_visible
    
    def update_model_label(self):
        lang = "Auto" if self.parent.whisper_language == "auto" else self.parent.whisper_language.upper()
        model_type = "GPT" if self.parent.transcription_model_type == "gpt" else "Whisper"
        self.model_label.configure(
            text=f"{self.parent.transcription_model} ({model_type}, {lang}) · {self.parent.ai_model} · {self.parent.current_prompt_name}"
        )
        
    def update_navigation_buttons(self):
        if self.parent.history_index >= len(self.parent.history) - 1:
            self.button_first_page.configure(state="disabled")
            self.button_arrow_left.configure(state="disabled")
        else:
            self.button_first_page.configure(state="normal")
            self.button_arrow_left.configure(state="normal")

        if self.parent.history_index <= 0:
            self.button_arrow_right.configure(state="disabled")
        else:
            self.button_arrow_right.configure(state="normal")
            
    def update_transcription_text(self):
        if 0 <= self.parent.history_index < len(self.parent.history):
            self.transcription_text.delete("1.0", tk.END)
            self.transcription_text.insert("1.0", self.parent.history[self.parent.history_index])
            
    def set_status(self, message, color="blue"):
        color_map = {
            "blue": (self.theme.STATUS_IDLE, self.theme.TEXT_TERTIARY),
            "green": (self.theme.STATUS_SUCCESS, self.theme.STATUS_SUCCESS),
            "red": (self.theme.STATUS_RECORDING, self.theme.STATUS_RECORDING),
            "orange": (self.theme.STATUS_PROCESSING, self.theme.STATUS_PROCESSING)
        }
        dot_color, text_color = color_map.get(color, (self.theme.STATUS_IDLE, self.theme.TEXT_TERTIARY))
        
        self.status_label.configure(text=message, text_color=text_color)
        self.status_dot.configure(text_color=dot_color)
        
        if "Recording" in message:
            self._pulse_recording()
    
    def _pulse_recording(self):
        if not hasattr(self, '_pulse_state'):
            self._pulse_state = True
        
        if "Recording" in self.status_label.cget("text"):
            self._pulse_state = not self._pulse_state
            self.status_dot.configure(
                text_color=self.theme.STATUS_RECORDING if self._pulse_state else self.theme.TEXT_MUTED
            )
            self.parent.after(500, self._pulse_recording)

    def _show_text_context_menu(self, event):
        menu = tk.Menu(
            self.parent, tearoff=0,
            bg=self.theme.BG_MENU, fg=self.theme.TEXT_PRIMARY,
            activebackground=self.theme.BG_HOVER, 
            activeforeground=self.theme.TEXT_PRIMARY,
            bd=0, relief="flat"
        )
        menu.add_command(label="Cut", command=lambda: self.transcription_text.event_generate('<<Cut>>'))
        menu.add_command(label="Copy", command=lambda: self.transcription_text.event_generate('<<Copy>>'))
        menu.add_command(label="Paste", command=lambda: self.transcription_text.event_generate('<<Paste>>'))
        menu.add_separator()
        menu.add_command(label="Select All", command=lambda: self.transcription_text.tag_add("sel", "1.0", "end-1c"))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def update_button_states(self, recording=False, mode=None):
        if recording:
            self.record_button_transcribe.configure(
                text="Stop Recording",
                fg_color=self.theme.STATUS_RECORDING if mode == "transcribe" else self.theme.BG_TERTIARY,
                hover_color=self.theme.STATUS_RECORDING
            )
            self.record_button_edit.configure(
                text="Stop Recording",
                fg_color=self.theme.STATUS_RECORDING if mode == "edit" else self.theme.BG_TERTIARY,
                hover_color=self.theme.STATUS_RECORDING
            )
        else:
            self.update_button_shortcuts()
    
    def update_button_shortcuts(self, transcribe_shortcut=None, edit_shortcut=None):
        if hasattr(self.parent, 'hotkey_manager') and hasattr(self.parent.hotkey_manager, 'shortcuts'):
            edit_shortcut = edit_shortcut or self.parent.hotkey_manager.shortcuts.get('record_edit', 'Ctrl+Alt+J')
            transcribe_shortcut = transcribe_shortcut or self.parent.hotkey_manager.shortcuts.get('record_transcribe', 'Ctrl+Alt+Shift+J')
        else:
            edit_shortcut = edit_shortcut or ("Cmd+Alt+J" if self.parent.is_mac else "Ctrl+Alt+J")
            transcribe_shortcut = transcribe_shortcut or ("Cmd+Alt+Shift+J" if self.parent.is_mac else "Ctrl+Alt+Shift+J")
        
        self.record_button_transcribe.configure(
            text="Record + Transcript",
            fg_color=self.theme.ACCENT_PRIMARY,
            hover_color=self.theme.ACCENT_HOVER
        )
        self.record_button_edit.configure(
            text="Record + AI Edit",
            fg_color=self.theme.SECONDARY_PRIMARY,
            hover_color=self.theme.SECONDARY_HOVER
        )
        
        if hasattr(self, 'shortcut_label_left') and self.shortcut_label_left:
            self.shortcut_label_left.configure(text=transcribe_shortcut)
        if hasattr(self, 'shortcut_label_right') and self.shortcut_label_right:
            self.shortcut_label_right.configure(text=edit_shortcut)
