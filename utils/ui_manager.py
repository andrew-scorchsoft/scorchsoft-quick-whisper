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
# SCORCHSOFT BRAND THEME
# ═══════════════════════════════════════════════════════════════════════════════

class ModernTheme:
    """Scorchsoft-branded dark theme with accessible typography."""
    
    # Background colors
    BG_PRIMARY = "#0d0d0d"
    BG_SECONDARY = "#161616"
    BG_TERTIARY = "#1c1c1c"
    BG_HOVER = "#262626"
    BG_MENU = "#111111"
    
    # Scorchsoft Red - same for both buttons
    ACCENT_PRIMARY = "#dc2626"
    ACCENT_HOVER = "#ef4444"
    
    # Secondary button - SAME red as primary (user preference)
    SECONDARY_PRIMARY = "#dc2626"
    SECONDARY_HOVER = "#ef4444"
    
    # Recording status - lighter/brighter red for visibility
    RECORDING_TEXT = "#f87171"
    
    # Text - high contrast for accessibility
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#e0e0e0"    # Very readable
    TEXT_TERTIARY = "#b0b0b0"     # Still readable
    TEXT_MUTED = "#707070"
    
    # Status
    STATUS_IDLE = "#909090"
    STATUS_PROCESSING = "#f59e0b"
    STATUS_RECORDING = "#ef4444"
    STATUS_SUCCESS = "#22c55e"
    
    # Borders
    BORDER = "#3a3a3a"          # More visible
    BORDER_STRONG = "#505050"   # Pronounced for inputs
    
    # Typography - ACCESSIBLE SIZES
    FONT = "Segoe UI"
    FONT_SIZE_XS = 11       # Only for very minor elements
    FONT_SIZE_SM = 12       # Secondary labels
    FONT_SIZE_MD = 13       # Menu, labels, hints
    FONT_SIZE_LG = 14       # Body text, inputs
    FONT_SIZE_XL = 15       # Primary inputs
    
    # Sizing
    RADIUS = 8
    RADIUS_SM = 6
    RADIUS_PILL = 24        # Pill-shaped buttons


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
        
        # UI references
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
        
        ctk.set_appearance_mode("dark")
        
    def create_widgets(self):
        """Create UI with accessible typography."""
        
        set_dark_title_bar(self.parent)
        self.parent.configure(bg=self.theme.BG_PRIMARY)
        
        # Main container
        self.main_frame = ctk.CTkFrame(
            self.parent, 
            fg_color=self.theme.BG_PRIMARY,
            corner_radius=0
        )
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ─────────────────────────────────────────────────────────────────────
        # CUSTOM MENU BAR - Larger, more readable
        # ─────────────────────────────────────────────────────────────────────
        
        menubar = ctk.CTkFrame(
            self.main_frame,
            fg_color=self.theme.BG_MENU,
            height=36,
            corner_radius=0
        )
        menubar.pack(fill=tk.X, side=tk.TOP)
        menubar.pack_propagate(False)
        
        menu_btn_style = {
            "font": (self.theme.FONT, self.theme.FONT_SIZE_MD),  # 13px - readable
            "text_color": self.theme.TEXT_SECONDARY,
            "fg_color": "transparent",
            "hover_color": self.theme.BG_HOVER,
            "corner_radius": 4,
            "height": 28,
            "anchor": "center"
        }
        
        file_btn = ctk.CTkButton(menubar, text="File", width=55,
                                  command=lambda: self._show_menu("file"), **menu_btn_style)
        file_btn.pack(side=tk.LEFT, padx=(10, 2), pady=4)
        
        settings_btn = ctk.CTkButton(menubar, text="Settings", width=70,
                                      command=lambda: self._show_menu("settings"), **menu_btn_style)
        settings_btn.pack(side=tk.LEFT, padx=2, pady=4)
        
        actions_btn = ctk.CTkButton(menubar, text="Actions", width=65,
                                     command=lambda: self._show_menu("actions"), **menu_btn_style)
        actions_btn.pack(side=tk.LEFT, padx=2, pady=4)
        
        help_btn = ctk.CTkButton(menubar, text="Help", width=55,
                                  command=lambda: self._show_menu("help"), **menu_btn_style)
        help_btn.pack(side=tk.LEFT, padx=2, pady=4)
        
        self._menu_buttons = {
            "file": file_btn, "settings": settings_btn,
            "actions": actions_btn, "help": help_btn
        }
        
        # Content area
        content = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        content.pack(fill=tk.BOTH, expand=True, padx=28, pady=(20, 24))
        
        # ─────────────────────────────────────────────────────────────────────
        # INPUT DEVICE
        # ─────────────────────────────────────────────────────────────────────
        
        device_label = ctk.CTkLabel(
            content,
            text="Input Device",
            font=(self.theme.FONT, self.theme.FONT_SIZE_MD, "bold"),
            text_color=self.theme.TEXT_SECONDARY
        )
        device_label.pack(anchor="w", pady=(0, 10))
        
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
            config.selected_input_device = self.parent.selected_device.get()
            config.save_settings()
        
        self.parent.selected_device.trace_add("write", on_device_change)
        
        # Device dropdown with visible border
        device_menu = ctk.CTkOptionMenu(
            content,
            variable=self.parent.selected_device,
            values=list(devices.keys()),
            fg_color=self.theme.BG_SECONDARY,
            button_color=self.theme.BG_TERTIARY,
            button_hover_color=self.theme.BG_HOVER,
            dropdown_fg_color=self.theme.BG_SECONDARY,
            dropdown_hover_color=self.theme.BG_HOVER,
            dropdown_text_color=self.theme.TEXT_PRIMARY,
            text_color=self.theme.TEXT_PRIMARY,
            font=(self.theme.FONT, self.theme.FONT_SIZE_LG),
            dropdown_font=(self.theme.FONT, self.theme.FONT_SIZE_LG),
            corner_radius=self.theme.RADIUS_SM,
            height=46,
            anchor="w",
            dynamic_resizing=False
        )
        device_menu.pack(fill=tk.X, pady=(0, 24))
        
        # ─────────────────────────────────────────────────────────────────────
        # TRANSCRIPTION
        # ─────────────────────────────────────────────────────────────────────
        
        header_row = ctk.CTkFrame(content, fg_color="transparent")
        header_row.pack(fill=tk.X, pady=(0, 10))
        
        transcription_label = ctk.CTkLabel(
            header_row,
            text="Transcription",
            font=(self.theme.FONT, self.theme.FONT_SIZE_MD, "bold"),
            text_color=self.theme.TEXT_SECONDARY
        )
        transcription_label.pack(side=tk.LEFT)
        
        # Navigation - MINIMAL: no background, no border, just icons
        nav_frame = ctk.CTkFrame(header_row, fg_color="transparent")
        nav_frame.pack(side=tk.RIGHT)
        
        nav_btn_style = {
            "width": 32,
            "height": 32,
            "corner_radius": 6,
            "fg_color": "transparent",           # No background
            "hover_color": self.theme.BG_HOVER,  # Only show on hover
            "text_color": self.theme.TEXT_TERTIARY,
            "text_color_disabled": self.theme.TEXT_MUTED,
            "font": (self.theme.FONT, 14),
            "border_width": 0                    # No border
        }
        
        self.button_first_page = ctk.CTkButton(
            nav_frame, text="⏮", command=self.parent.go_to_first_page,
            state="disabled", **nav_btn_style
        )
        self.button_first_page.pack(side=tk.LEFT, padx=1)
        
        self.button_arrow_left = ctk.CTkButton(
            nav_frame, text="◀", command=self.parent.navigate_left,
            state="disabled", **nav_btn_style
        )
        self.button_arrow_left.pack(side=tk.LEFT, padx=1)
        
        self.button_arrow_right = ctk.CTkButton(
            nav_frame, text="▶", command=self.parent.navigate_right,
            state="disabled", **nav_btn_style
        )
        self.button_arrow_right.pack(side=tk.LEFT, padx=1)
        
        ToolTip(self.button_first_page, "Latest entry")
        ToolTip(self.button_arrow_left, "Newer")
        ToolTip(self.button_arrow_right, "Older")
        
        # Text area - larger font
        # Text area - with pronounced border
        self.transcription_text = ctk.CTkTextbox(
            content,
            height=200,
            fg_color=self.theme.BG_SECONDARY,
            text_color=self.theme.TEXT_PRIMARY,
            font=(self.theme.FONT, self.theme.FONT_SIZE_XL),  # 15px - very readable
            corner_radius=self.theme.RADIUS_SM,
            border_width=1,
            border_color=self.theme.BORDER_STRONG,  # More visible border
            wrap="word"
        )
        self.transcription_text.pack(fill=tk.BOTH, expand=True, pady=(0, 14))
        self.transcription_text.bind("<Button-3>", self._show_text_context_menu)
        
        # ─────────────────────────────────────────────────────────────────────
        # STATUS ROW
        # ─────────────────────────────────────────────────────────────────────
        
        status_row = ctk.CTkFrame(content, fg_color="transparent")
        status_row.pack(fill=tk.X, pady=(0, 14))
        
        status_left = ctk.CTkFrame(status_row, fg_color="transparent")
        status_left.pack(side=tk.LEFT)
        
        self.status_dot = ctk.CTkLabel(
            status_left, text="●", width=18,
            font=(self.theme.FONT, 10),
            text_color=self.theme.STATUS_IDLE
        )
        self.status_dot.pack(side=tk.LEFT, padx=(0, 8))
        
        self.status_label = ctk.CTkLabel(
            status_left, text="Idle",
            font=(self.theme.FONT, self.theme.FONT_SIZE_LG),  # 14px
            text_color=self.theme.TEXT_TERTIARY
        )
        self.status_label.pack(side=tk.LEFT)
        
        # Model info
        self.model_label = ctk.CTkLabel(
            status_row,
            text=f"{self.parent.transcription_model} · {self.parent.ai_model}",
            font=(self.theme.FONT, self.theme.FONT_SIZE_MD),  # 13px
            text_color=self.theme.TEXT_TERTIARY
        )
        self.model_label.pack(side=tk.RIGHT)
        
        # ─────────────────────────────────────────────────────────────────────
        # OPTIONS
        # ─────────────────────────────────────────────────────────────────────
        
        options_row = ctk.CTkFrame(content, fg_color="transparent")
        options_row.pack(fill=tk.X, pady=(0, 18))
        
        cb_style = {
            "font": (self.theme.FONT, self.theme.FONT_SIZE_MD),  # 13px
            "text_color": self.theme.TEXT_SECONDARY,
            "fg_color": self.theme.ACCENT_PRIMARY,
            "hover_color": self.theme.ACCENT_HOVER,
            "border_color": self.theme.TEXT_MUTED,
            "checkmark_color": self.theme.TEXT_PRIMARY,
            "corner_radius": 4,
            "border_width": 2,
            "checkbox_width": 20,
            "checkbox_height": 20
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
        buttons_frame.pack(fill=tk.X, pady=(0, 8))
        buttons_frame.columnconfigure(0, weight=1)
        buttons_frame.columnconfigure(1, weight=1)
        
        self.record_button_transcribe = ctk.CTkButton(
            buttons_frame,
            text="Record + Transcript",
            corner_radius=self.theme.RADIUS_PILL,  # Pill shape
            height=50,
            fg_color=self.theme.ACCENT_PRIMARY,
            hover_color=self.theme.ACCENT_HOVER,
            text_color=self.theme.TEXT_PRIMARY,
            font=(self.theme.FONT, self.theme.FONT_SIZE_LG, "bold"),
            command=lambda: self.parent.toggle_recording("transcribe")
        )
        self.record_button_transcribe.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        
        self.record_button_edit = ctk.CTkButton(
            buttons_frame,
            text="Record + AI Edit",
            corner_radius=self.theme.RADIUS_PILL,  # Pill shape
            height=50,
            fg_color=self.theme.ACCENT_PRIMARY,  # Same red as other button
            hover_color=self.theme.ACCENT_HOVER,
            text_color=self.theme.TEXT_PRIMARY,
            font=(self.theme.FONT, self.theme.FONT_SIZE_LG, "bold"),
            command=lambda: self.parent.toggle_recording("edit")
        )
        self.record_button_edit.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        
        # Shortcut hints - compact, close to buttons
        hints_frame = ctk.CTkFrame(content, fg_color="transparent")
        hints_frame.pack(fill=tk.X, pady=(2, 12))  # Reduced top padding
        hints_frame.columnconfigure(0, weight=1)
        hints_frame.columnconfigure(1, weight=1)
        
        shortcut_transcribe = "Cmd+Alt+Shift+J" if self.parent.is_mac else "Ctrl+Alt+Shift+J"
        shortcut_edit = "Cmd+Alt+J" if self.parent.is_mac else "Ctrl+Alt+J"
        
        self.shortcut_label_left = ctk.CTkLabel(
            hints_frame, text=shortcut_transcribe,
            font=(self.theme.FONT, self.theme.FONT_SIZE_SM),  # Slightly smaller
            text_color=self.theme.TEXT_TERTIARY
        )
        self.shortcut_label_left.grid(row=0, column=0)
        
        self.shortcut_label_right = ctk.CTkLabel(
            hints_frame, text=shortcut_edit,
            font=(self.theme.FONT, self.theme.FONT_SIZE_SM),
            text_color=self.theme.TEXT_TERTIARY
        )
        self.shortcut_label_right.grid(row=0, column=1)
        
        # Add tooltips to buttons with shortcuts (reinforces keyboard usage)
        ToolTip(self.record_button_transcribe, f"Record and transcribe audio ({shortcut_transcribe})")
        ToolTip(self.record_button_edit, f"Record and AI-edit transcription ({shortcut_edit})")
        
        # ─────────────────────────────────────────────────────────────────────
        # BANNER
        # ─────────────────────────────────────────────────────────────────────
        
        self.banner_frame = ctk.CTkFrame(content, fg_color="transparent")
        self.banner_frame.pack(fill=tk.X)
        
        self.banner_height = 0  # Will store actual banner height for toggle
        
        try:
            banner_path = self.parent.resource_path("assets/banner-00-560.png")
            banner_img = Image.open(banner_path)
            # Only the banner image + minimal padding (powered_by link replaces hide link)
            self.banner_height = banner_img.height + 10
            print(f"Banner image height: {banner_img.height}, total banner_height: {self.banner_height}")
            self.banner_photo = ImageTk.PhotoImage(banner_img)
            
            self.banner_label = tk.Label(
                self.banner_frame, image=self.banner_photo,
                cursor="hand2", bg=self.theme.BG_PRIMARY
            )
            self.banner_label.pack(pady=(4, 6))
            self.banner_label.bind("<Button-1>", lambda e: self.open_scorchsoft())
        except Exception as e:
            print(f"Banner load error: {e}")
            self.banner_height = 260  # Fallback (247 + 10)
        
        self.hide_banner_link = ctk.CTkLabel(
            self.banner_frame, text="Hide Banner",
            font=(self.theme.FONT, self.theme.FONT_SIZE_SM),
            text_color=self.theme.TEXT_MUTED, cursor="hand2"
        )
        self.hide_banner_link.pack(pady=(0, 4))
        self.hide_banner_link.bind("<Button-1>", lambda e: self.parent.toggle_banner())
        self.hide_banner_link.bind("<Enter>", lambda e: self.hide_banner_link.configure(text_color=self.theme.ACCENT_PRIMARY))
        self.hide_banner_link.bind("<Leave>", lambda e: self.hide_banner_link.configure(text_color=self.theme.TEXT_MUTED))
        
        # Powered by label - red and underlined, visible when banner hidden
        self.powered_by_label = ctk.CTkLabel(
            self.banner_frame, text="Powered by Scorchsoft.com",
            font=(self.theme.FONT, self.theme.FONT_SIZE_SM, "underline"),
            text_color=self.theme.ACCENT_PRIMARY, cursor="hand2"
        )
        self.powered_by_label.bind("<Button-1>", lambda e: self.open_scorchsoft())
        self.powered_by_label.bind("<Enter>", lambda e: self.powered_by_label.configure(text_color=self.theme.ACCENT_HOVER))
        self.powered_by_label.bind("<Leave>", lambda e: self.powered_by_label.configure(text_color=self.theme.ACCENT_PRIMARY))
        
        return self.main_frame
    
    def _show_menu(self, menu_name):
        """Show menu dropdown."""
        menu_map = {
            "file": getattr(self.parent, 'file_menu', None),
            "settings": getattr(self.parent, 'settings_menu', None),
            "actions": getattr(self.parent, 'actions_menu', None),
            "help": getattr(self.parent, 'help_menu', None)
        }
        menu = menu_map.get(menu_name)
        btn = self._menu_buttons.get(menu_name)
        if menu and btn:
            menu.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())
        
    def open_scorchsoft(self, event=None):
        webbrowser.open('https://www.scorchsoft.com/contact-scorchsoft')
        
    def toggle_banner(self):
        current_height = self.parent.winfo_height()
        # Delta = banner image + small padding (powered_by link replaces hide link, similar size)
        delta = self.banner_height if hasattr(self, 'banner_height') and self.banner_height > 0 else 260
        new_height = current_height + delta if not self.banner_visible else current_height - delta

        if self.banner_visible:
            if self.banner_label:
                self.banner_label.pack_forget()
            self.hide_banner_link.pack_forget()
            self.powered_by_label.pack(pady=(8, 12))
            try:
                self.parent.help_menu.entryconfig("Hide Banner", label="Show Banner")
            except:
                pass
        else:
            if self.banner_label:
                self.banner_label.pack(pady=(4, 6))
            self.powered_by_label.pack_forget()
            self.hide_banner_link.pack(pady=(0, 4))
            try:
                self.parent.help_menu.entryconfig("Show Banner", label="Hide Banner")
            except:
                pass

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
            "blue": (self.theme.STATUS_IDLE, self.theme.TEXT_TERTIARY, "normal"),
            "green": (self.theme.STATUS_SUCCESS, self.theme.STATUS_SUCCESS, "normal"),
            "red": (self.theme.RECORDING_TEXT, self.theme.RECORDING_TEXT, "bold"),  # Lighter red, bold
            "orange": (self.theme.STATUS_PROCESSING, self.theme.STATUS_PROCESSING, "normal")
        }
        dot_color, text_color, weight = color_map.get(color, (self.theme.STATUS_IDLE, self.theme.TEXT_TERTIARY, "normal"))
        self.status_label.configure(
            text=message, 
            text_color=text_color,
            font=(self.theme.FONT, self.theme.FONT_SIZE_LG, weight)
        )
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
            font=(self.theme.FONT, self.theme.FONT_SIZE_MD),
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
        # Guard: buttons may not exist yet during initialization
        if not self.record_button_transcribe or not self.record_button_edit:
            return
            
        if hasattr(self.parent, 'hotkey_manager') and hasattr(self.parent.hotkey_manager, 'shortcuts'):
            edit_shortcut = edit_shortcut or self.parent.hotkey_manager.shortcuts.get('record_edit', 'Ctrl+Alt+J')
            transcribe_shortcut = transcribe_shortcut or self.parent.hotkey_manager.shortcuts.get('record_transcribe', 'Ctrl+Alt+Shift+J')
        else:
            edit_shortcut = edit_shortcut or ("Cmd+Alt+J" if self.parent.is_mac else "Ctrl+Alt+J")
            transcribe_shortcut = transcribe_shortcut or ("Cmd+Alt+Shift+J" if self.parent.is_mac else "Ctrl+Alt+Shift+J")
        
        self.record_button_transcribe.configure(
            text="Record + Transcript",
            fg_color=self.theme.ACCENT_PRIMARY,
            hover_color=self.theme.ACCENT_HOVER,
            corner_radius=self.theme.RADIUS_PILL
        )
        self.record_button_edit.configure(
            text="Record + AI Edit",
            fg_color=self.theme.ACCENT_PRIMARY,  # Same red
            hover_color=self.theme.ACCENT_HOVER,
            corner_radius=self.theme.RADIUS_PILL
        )
        
        if hasattr(self, 'shortcut_label_left') and self.shortcut_label_left:
            self.shortcut_label_left.configure(text=transcribe_shortcut)
        if hasattr(self, 'shortcut_label_right') and self.shortcut_label_right:
            self.shortcut_label_right.configure(text=edit_shortcut)
