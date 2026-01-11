import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw
import webbrowser
import platform
import ctypes
import sv_ttk
import pyperclip

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
    
    # Scorchsoft Red - reserved for recording/stop states
    SCORCHSOFT_RED = "#dc2626"
    SCORCHSOFT_RED_HOVER = "#ef4444"
    
    # Action buttons - gradient inspired by logo (cyan to purple)
    ACCENT_PRIMARY = "#22d3ee"
    ACCENT_HOVER = "#67e8f9"
    
    # Gradient colors (matching logo: cyan → purple with glow)
    GRADIENT_START = "#06b6d4"   # Cyan-500 (richer cyan)
    GRADIENT_MID = "#3b82f6"     # Blue-500 (middle transition)
    GRADIENT_END = "#8b5cf6"     # Violet-500 (purple)
    GRADIENT_HOVER_START = "#22d3ee"  # Lighter cyan
    GRADIENT_HOVER_MID = "#60a5fa"    # Lighter blue
    GRADIENT_HOVER_END = "#a78bfa"    # Lighter purple
    
    # Recording status - lighter/brighter red for visibility
    RECORDING_TEXT = "#f87171"
    
    # Recording button gradient (red tones)
    RECORDING_GRADIENT_START = "#dc2626"   # Red-600
    RECORDING_GRADIENT_MID = "#b91c1c"     # Red-700
    RECORDING_GRADIENT_END = "#7f1d1d"     # Red-900
    RECORDING_GRADIENT_HOVER_START = "#ef4444"  # Red-500 (lighter)
    RECORDING_GRADIENT_HOVER_MID = "#dc2626"    # Red-600
    RECORDING_GRADIENT_HOVER_END = "#991b1b"    # Red-800
    
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
    RADIUS_PILL = 25        # Pill-shaped buttons (half of 50px height for perfect semicircle)


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


class GradientButton(tk.Canvas):
    """Custom button with gradient background (cyan → blue → purple like logo)."""
    
    def __init__(self, parent, text="", command=None, width=200, height=50, 
                 corner_radius=25, font=("Segoe UI", 13, "bold"),
                 gradient_start="#06b6d4", gradient_mid="#3b82f6", gradient_end="#8b5cf6",
                 hover_start="#22d3ee", hover_mid="#60a5fa", hover_end="#a78bfa",
                 solid_color=None, solid_hover=None,
                 border_color="#6d9dc5", border_width=1,
                 text_color="#0d0d0d", bg_color="#0d0d0d", **kwargs):
        
        super().__init__(parent, width=width, height=height, 
                        bg=bg_color, highlightthickness=0, cursor="hand2", **kwargs)
        
        self.text = text
        self.command = command
        self.width = width
        self.height = height
        self.corner_radius = corner_radius
        self.font = font
        self.text_color = text_color
        self.bg_color = bg_color
        self.border_color = border_color
        self.border_width = border_width
        
        # Gradient colors (3-stop for smoother transition)
        self.gradient_start = gradient_start
        self.gradient_mid = gradient_mid
        self.gradient_end = gradient_end
        self.hover_start = hover_start
        self.hover_mid = hover_mid
        self.hover_end = hover_end
        
        # Solid color mode (for recording state)
        self.solid_color = solid_color
        self.solid_hover = solid_hover
        
        self._is_hovered = False
        self._gradient_image = None
        self._hover_gradient_image = None
        
        # Create gradient images
        self._create_gradient_images()
        self._draw()
        
        # Bind events
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Configure>", self._on_resize)
    
    def _hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _interpolate_color(self, color1, color2, ratio):
        """Interpolate between two RGB colors."""
        return tuple(int(color1[i] + (color2[i] - color1[i]) * ratio) for i in range(3))
    
    def _create_gradient_images(self):
        """Create gradient images for normal and hover states."""
        w, h = self.width, self.height
        r = min(self.corner_radius, h // 2)
        
        # Normal gradient (3-stop)
        self._gradient_image = self._create_rounded_gradient(
            w, h, r, self.gradient_start, self.gradient_mid, self.gradient_end
        )
        
        # Hover gradient (3-stop, brighter)
        self._hover_gradient_image = self._create_rounded_gradient(
            w, h, r, self.hover_start, self.hover_mid, self.hover_end
        )
    
    def _create_rounded_gradient(self, w, h, r, color_start, color_mid, color_end):
        """Create a 3-stop horizontal gradient with border, highlight and rounded corners."""
        # Use higher resolution for anti-aliasing, then downscale
        scale = 2
        sw, sh = w * scale, h * scale
        sr = r * scale
        border = self.border_width * scale
        
        img = Image.new('RGBA', (sw, sh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Draw border first (if border_width > 0)
        if self.border_width > 0:
            border_rgb = self._hex_to_rgb(self.border_color)
            draw.rounded_rectangle([(0, 0), (sw-1, sh-1)], radius=sr, fill=(*border_rgb, 255))
        
        # Create gradient for inner area
        inner_img = Image.new('RGBA', (sw - border*2, sh - border*2), (0, 0, 0, 0))
        inner_w, inner_h = inner_img.size
        inner_r = max(0, sr - border)
        
        start_rgb = self._hex_to_rgb(color_start)
        mid_rgb = self._hex_to_rgb(color_mid)
        end_rgb = self._hex_to_rgb(color_end)
        
        # Draw 3-stop gradient
        for x in range(inner_w):
            ratio = x / (inner_w - 1) if inner_w > 1 else 0
            
            # 3-stop gradient: start → mid (0-0.5), mid → end (0.5-1)
            if ratio < 0.5:
                local_ratio = ratio * 2
                base_rgb = self._interpolate_color(start_rgb, mid_rgb, local_ratio)
            else:
                local_ratio = (ratio - 0.5) * 2
                base_rgb = self._interpolate_color(mid_rgb, end_rgb, local_ratio)
            
            for y in range(inner_h):
                # Add subtle vertical highlight (brighter at top)
                highlight = 1.0 + 0.12 * (1 - y / inner_h)  # 12% brighter at top
                
                r_val = min(255, int(base_rgb[0] * highlight))
                g_val = min(255, int(base_rgb[1] * highlight))
                b_val = min(255, int(base_rgb[2] * highlight))
                
                inner_img.putpixel((x, y), (r_val, g_val, b_val, 255))
        
        # Create rounded mask for inner gradient
        inner_mask = Image.new('L', (inner_w, inner_h), 0)
        inner_draw = ImageDraw.Draw(inner_mask)
        inner_draw.rounded_rectangle([(0, 0), (inner_w-1, inner_h-1)], radius=inner_r, fill=255)
        inner_img.putalpha(inner_mask)
        
        # Paste inner gradient onto main image
        img.paste(inner_img, (border, border), inner_img)
        
        # Create outer mask
        mask = Image.new('L', (sw, sh), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([(0, 0), (sw-1, sh-1)], radius=sr, fill=255)
        img.putalpha(mask)
        
        # Downscale with anti-aliasing
        img = img.resize((w, h), Image.LANCZOS)
        
        return ImageTk.PhotoImage(img)
    
    def _create_solid_image(self, color):
        """Create a solid color image with border and rounded corners."""
        w, h = self.width, self.height
        r = min(self.corner_radius, h // 2)
        border = self.border_width
        
        img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Draw border if present
        if border > 0:
            border_rgb = self._hex_to_rgb(self.border_color)
            draw.rounded_rectangle([(0, 0), (w-1, h-1)], radius=r, fill=(*border_rgb, 255))
            # Draw inner solid
            inner_r = max(0, r - border)
            rgb = self._hex_to_rgb(color)
            draw.rounded_rectangle([(border, border), (w-1-border, h-1-border)], 
                                   radius=inner_r, fill=(*rgb, 255))
        else:
            rgb = self._hex_to_rgb(color)
            draw.rounded_rectangle([(0, 0), (w-1, h-1)], radius=r, fill=(*rgb, 255))
        
        return ImageTk.PhotoImage(img)
    
    def _draw(self):
        """Draw the button."""
        self.delete("all")
        
        # Choose image based on state
        if self.solid_color:
            # Solid color mode (recording state)
            if self._is_hovered and self.solid_hover:
                img = self._create_solid_image(self.solid_hover)
            else:
                img = self._create_solid_image(self.solid_color)
            self._current_image = img  # Keep reference
            self.create_image(0, 0, anchor="nw", image=img)
        else:
            # Gradient mode
            img = self._hover_gradient_image if self._is_hovered else self._gradient_image
            self.create_image(0, 0, anchor="nw", image=img)
        
        # Draw text
        self.create_text(
            self.width // 2, self.height // 2,
            text=self.text, fill=self.text_color,
            font=self.font, anchor="center"
        )
    
    def _on_enter(self, event):
        self._is_hovered = True
        self._draw()
    
    def _on_leave(self, event):
        self._is_hovered = False
        self._draw()
    
    def _on_click(self, event):
        if self.command:
            self.command()
    
    def _on_resize(self, event):
        if event.width != self.width or event.height != self.height:
            self.width = event.width
            self.height = event.height
            self._create_gradient_images()
            self._draw()
    
    def configure(self, **kwargs):
        """Configure button properties."""
        redraw = False
        regenerate_gradients = False
        
        if 'text' in kwargs:
            self.text = kwargs.pop('text')
            redraw = True
        if 'text_color' in kwargs:
            self.text_color = kwargs.pop('text_color')
            redraw = True
        if 'font' in kwargs:
            self.font = kwargs.pop('font')
            redraw = True
        if 'solid_color' in kwargs:
            self.solid_color = kwargs.pop('solid_color')
            redraw = True
        if 'solid_hover' in kwargs:
            self.solid_hover = kwargs.pop('solid_hover')
            redraw = True
        if 'gradient_start' in kwargs:
            self.gradient_start = kwargs.pop('gradient_start')
            regenerate_gradients = True
        if 'gradient_mid' in kwargs:
            self.gradient_mid = kwargs.pop('gradient_mid')
            regenerate_gradients = True
        if 'gradient_end' in kwargs:
            self.gradient_end = kwargs.pop('gradient_end')
            regenerate_gradients = True
        if 'hover_start' in kwargs:
            self.hover_start = kwargs.pop('hover_start')
            regenerate_gradients = True
        if 'hover_mid' in kwargs:
            self.hover_mid = kwargs.pop('hover_mid')
            regenerate_gradients = True
        if 'hover_end' in kwargs:
            self.hover_end = kwargs.pop('hover_end')
            regenerate_gradients = True
        if 'command' in kwargs:
            self.command = kwargs.pop('command')
        
        if regenerate_gradients:
            self._create_gradient_images()
            redraw = True
        
        # Handle CTk-style parameters (ignore them gracefully)
        for key in ['fg_color', 'hover_color', 'corner_radius']:
            kwargs.pop(key, None)
            
        if kwargs:
            super().configure(**kwargs)
        
        if redraw:
            self._draw()
    
    # Alias for CTk compatibility
    config = configure


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
        self.device_combo = None
        
    def _setup_styles(self):
        """Configure ttk styles for Sun Valley theme customization."""
        style = ttk.Style()
        
        # Custom style for section labels
        style.configure("Section.TLabel",
            font=(self.theme.FONT, self.theme.FONT_SIZE_MD, "bold"))
        
        # Custom style for muted text
        style.configure("Muted.TLabel",
            font=(self.theme.FONT, self.theme.FONT_SIZE_SM))
        
        # Smaller muted text for model info
        style.configure("Small.TLabel",
            font=(self.theme.FONT, self.theme.FONT_SIZE_XS))
        
        # Custom style for status text  
        style.configure("Status.TLabel",
            font=(self.theme.FONT, self.theme.FONT_SIZE_LG))
        
        # Nav button style
        style.configure("Nav.TButton",
            font=(self.theme.FONT, 14),
            padding=(4, 4))
        
    def create_widgets(self):
        """Create UI with Sun Valley theme (ttk widgets)."""
        
        set_dark_title_bar(self.parent)
        
        # Apply Sun Valley dark theme FIRST
        sv_ttk.set_theme("dark")
        
        # Setup custom styles
        self._setup_styles()
        
        # Main container - use ttk.Frame
        self.main_frame = ttk.Frame(self.parent)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ─────────────────────────────────────────────────────────────────────
        # MENU BAR - Using ttk buttons for Sun Valley styling
        # ─────────────────────────────────────────────────────────────────────
        
        menubar = ttk.Frame(self.main_frame)
        menubar.pack(fill=tk.X, side=tk.TOP, pady=(0, 0))
        
        file_btn = ttk.Button(menubar, text="File", width=8,
                              command=lambda: self._show_menu("file"))
        file_btn.pack(side=tk.LEFT, padx=(8, 2), pady=6)
        
        settings_btn = ttk.Button(menubar, text="Settings", width=10,
                                  command=lambda: self._show_menu("settings"))
        settings_btn.pack(side=tk.LEFT, padx=2, pady=6)
        
        actions_btn = ttk.Button(menubar, text="Actions", width=9,
                                 command=lambda: self._show_menu("actions"))
        actions_btn.pack(side=tk.LEFT, padx=2, pady=6)
        
        help_btn = ttk.Button(menubar, text="Help", width=8,
                              command=lambda: self._show_menu("help"))
        help_btn.pack(side=tk.LEFT, padx=2, pady=6)
        
        self._menu_buttons = {
            "file": file_btn, "settings": settings_btn,
            "actions": actions_btn, "help": help_btn
        }
        
        # Content area with padding (minimal bottom padding)
        content = ttk.Frame(self.main_frame, padding=(28, 20, 28, 0))
        content.pack(fill=tk.BOTH, expand=True)
        
        # ─────────────────────────────────────────────────────────────────────
        # INPUT DEVICE
        # ─────────────────────────────────────────────────────────────────────
        
        device_label = ttk.Label(content, text="Input Device", style="Section.TLabel")
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
        
        # Device dropdown - ttk.Combobox with Sun Valley styling
        self.device_combo = ttk.Combobox(
            content,
            textvariable=self.parent.selected_device,
            values=list(devices.keys()),
            state="readonly",
            font=(self.theme.FONT, self.theme.FONT_SIZE_MD)  # Slightly smaller
        )
        self.device_combo.pack(fill=tk.X, pady=(0, 24), ipady=6)
        
        # Set dropdown list font to match
        self.parent.option_add('*TCombobox*Listbox.font', (self.theme.FONT, self.theme.FONT_SIZE_MD))
        
        # ─────────────────────────────────────────────────────────────────────
        # TRANSCRIPTION
        # ─────────────────────────────────────────────────────────────────────
        
        header_row = ttk.Frame(content)
        header_row.pack(fill=tk.X, pady=(0, 10))
        
        transcription_label = ttk.Label(header_row, text="Transcription", style="Section.TLabel")
        transcription_label.pack(side=tk.LEFT)
        
        # Navigation buttons - minimal icon-only style
        nav_frame = ttk.Frame(header_row)
        nav_frame.pack(side=tk.RIGHT)
        
        # Use labels styled as clickable icons (no button border) - larger for visibility
        nav_style = {"font": (self.theme.FONT, 20), "cursor": "hand2"}
        
        self._nav_button_disabled = {"first": True, "left": True, "right": True}
        
        self.button_first_page = ttk.Label(nav_frame, text="«", **nav_style)
        self.button_first_page.pack(side=tk.LEFT, padx=4)
        self.button_first_page.bind("<Button-1>", lambda e: None if self._nav_button_disabled["first"] else self.parent.go_to_first_page())
        
        self.button_arrow_left = ttk.Label(nav_frame, text="‹", **nav_style)
        self.button_arrow_left.pack(side=tk.LEFT, padx=4)
        self.button_arrow_left.bind("<Button-1>", lambda e: None if self._nav_button_disabled["left"] else self.parent.navigate_left())
        
        self.button_arrow_right = ttk.Label(nav_frame, text="›", **nav_style)
        self.button_arrow_right.pack(side=tk.LEFT, padx=4)
        self.button_arrow_right.bind("<Button-1>", lambda e: None if self._nav_button_disabled["right"] else self.parent.navigate_right())
        
        # Separator between navigation and copy
        separator_label = ttk.Label(nav_frame, text="│", font=(self.theme.FONT, 12), foreground=self.theme.TEXT_MUTED)
        separator_label.pack(side=tk.LEFT, padx=(8, 4))
        
        # Copy button - same size as navigation buttons
        self.button_copy = ttk.Label(nav_frame, text="⧉", **nav_style)
        self.button_copy.pack(side=tk.LEFT, padx=4)
        self.button_copy.bind("<Button-1>", lambda e: self._copy_transcription())
        
        # Set initial disabled state (muted color)
        self._update_nav_button_appearance()
        
        ToolTip(self.button_first_page, "Latest entry")
        ToolTip(self.button_arrow_left, "Newer")
        ToolTip(self.button_arrow_right, "Older")
        ToolTip(self.button_copy, "Copy to clipboard")
        
        # Text area - tk.Text with border, padding, and rounded appearance
        text_frame = ttk.Frame(content)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 14))
        
        # Create scrollbar (Sun Valley styled) - initially hidden
        text_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        self._text_scrollbar = text_scrollbar
        self._text_scrollbar_visible = False
        
        # Auto-show/hide scrollbar based on content
        def update_scrollbar_visibility():
            """Check if scrollbar is needed and show/hide accordingly."""
            first, last = self.transcription_text.yview()
            needs_scrollbar = first > 0.0 or last < 1.0
            if needs_scrollbar and not self._text_scrollbar_visible:
                text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                self._text_scrollbar_visible = True
            elif not needs_scrollbar and self._text_scrollbar_visible:
                text_scrollbar.pack_forget()
                self._text_scrollbar_visible = False
        
        def on_scroll_changed(first, last):
            text_scrollbar.set(first, last)
            update_scrollbar_visibility()
        
        self._update_scrollbar_visibility = update_scrollbar_visibility
        
        self.transcription_text = tk.Text(
            text_frame,
            height=10,
            font=(self.theme.FONT, self.theme.FONT_SIZE_MD),
            wrap="word",
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#404040",
            highlightcolor="#505050",
            padx=12,  # Internal horizontal padding
            pady=10,  # Internal vertical padding
            yscrollcommand=on_scroll_changed
        )
        self.transcription_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.transcription_text.bind("<Button-3>", self._show_text_context_menu)
        
        # Bind events that might change content to update scrollbar visibility
        self.transcription_text.bind("<KeyRelease>", lambda e: self.parent.after(10, update_scrollbar_visibility))
        self.transcription_text.bind("<<Paste>>", lambda e: self.parent.after(10, update_scrollbar_visibility))
        self.transcription_text.bind("<<Cut>>", lambda e: self.parent.after(10, update_scrollbar_visibility))
        self.transcription_text.bind("<Configure>", lambda e: self.parent.after(10, update_scrollbar_visibility))
        
        # Connect scrollbar to text widget
        text_scrollbar.config(command=self.transcription_text.yview)
        
        # ─────────────────────────────────────────────────────────────────────
        # STATUS ROW
        # ─────────────────────────────────────────────────────────────────────
        
        status_row = ttk.Frame(content)
        status_row.pack(fill=tk.X, pady=(0, 14))
        
        status_left = ttk.Frame(status_row)
        status_left.pack(side=tk.LEFT)
        
        self.status_dot = ttk.Label(status_left, text="●", font=(self.theme.FONT, 14))
        self.status_dot.pack(side=tk.LEFT, padx=(0, 6))
        
        self.status_label = ttk.Label(status_left, text="Idle", style="Status.TLabel")
        self.status_label.pack(side=tk.LEFT)
        
        # Model info - smaller font
        self.model_label = ttk.Label(
            status_row,
            text=f"{self.parent.transcription_model} · {self.parent.ai_model}",
            style="Small.TLabel"
        )
        self.model_label.pack(side=tk.RIGHT)
        
        # ─────────────────────────────────────────────────────────────────────
        # OPTIONS - Toggle switches (Sun Valley style)
        # ─────────────────────────────────────────────────────────────────────
        
        options_frame = ttk.LabelFrame(content, text="Options", padding=(16, 10))
        options_frame.pack(fill=tk.X, pady=(0, 12))
        
        # Center container for toggles
        switches_container = ttk.Frame(options_frame)
        switches_container.pack(expand=True)
        
        # Sun Valley provides "Switch.TCheckbutton" style for toggle switches
        auto_copy_switch = ttk.Checkbutton(
            switches_container,
            text="Copy to clipboard",
            variable=self.parent.auto_copy,
            style="Switch.TCheckbutton"
        )
        auto_copy_switch.pack(side=tk.LEFT, padx=(0, 32))
        
        auto_paste_switch = ttk.Checkbutton(
            switches_container,
            text="Auto-paste",
            variable=self.parent.auto_paste,
            style="Switch.TCheckbutton"
        )
        auto_paste_switch.pack(side=tk.LEFT)
        
        # ─────────────────────────────────────────────────────────────────────
        # ACTION BUTTONS (Keep custom gradient buttons)
        # ─────────────────────────────────────────────────────────────────────
        
        buttons_frame = ttk.Frame(content)
        buttons_frame.pack(fill=tk.X, pady=(0, 4))
        
        # Calculate button width (will be adjusted on resize)
        btn_width = 200  # Default, will resize
        
        self.record_button_transcribe = GradientButton(
            buttons_frame,
            text="Record + Transcript",
            width=btn_width,
            height=50,
            corner_radius=self.theme.RADIUS_PILL,
            font=(self.theme.FONT, self.theme.FONT_SIZE_MD, "bold"),
            gradient_start=self.theme.GRADIENT_START,
            gradient_mid=self.theme.GRADIENT_MID,
            gradient_end=self.theme.GRADIENT_END,
            hover_start=self.theme.GRADIENT_HOVER_START,
            hover_mid=self.theme.GRADIENT_HOVER_MID,
            hover_end=self.theme.GRADIENT_HOVER_END,
            text_color=self.theme.TEXT_PRIMARY,
            bg_color="#1c1c1c",  # Match Sun Valley dark theme background
            command=lambda: self.parent.toggle_recording("transcribe")
        )
        self.record_button_transcribe.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        
        self.record_button_edit = GradientButton(
            buttons_frame,
            text="Record + AI Edit",
            width=btn_width,
            height=50,
            corner_radius=self.theme.RADIUS_PILL,
            font=(self.theme.FONT, self.theme.FONT_SIZE_MD, "bold"),
            gradient_start=self.theme.GRADIENT_START,
            gradient_mid=self.theme.GRADIENT_MID,
            gradient_end=self.theme.GRADIENT_END,
            hover_start=self.theme.GRADIENT_HOVER_START,
            hover_mid=self.theme.GRADIENT_HOVER_MID,
            hover_end=self.theme.GRADIENT_HOVER_END,
            text_color=self.theme.TEXT_PRIMARY,
            bg_color="#1c1c1c",  # Match Sun Valley dark theme background
            command=lambda: self.parent.toggle_recording("edit")
        )
        self.record_button_edit.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        
        # Shortcut tooltips only (no visible labels - tooltips show on hover)
        shortcut_transcribe = "Cmd+Alt+Shift+J" if self.parent.is_mac else "Ctrl+Alt+Shift+J"
        shortcut_edit = "Cmd+Alt+J" if self.parent.is_mac else "Ctrl+Alt+J"
        
        # Store references for update_button_shortcuts (set to None since we removed the labels)
        self.shortcut_label_left = None
        self.shortcut_label_right = None
        
        # Add tooltips to buttons
        ToolTip(self.record_button_transcribe, f"Record and transcribe audio ({shortcut_transcribe})")
        ToolTip(self.record_button_edit, f"Record and AI-edit transcription ({shortcut_edit})")
        
        # ─────────────────────────────────────────────────────────────────────
        # BANNER
        # ─────────────────────────────────────────────────────────────────────
        
        self.banner_frame = ttk.Frame(content)
        self.banner_frame.pack(fill=tk.X)
        
        self.banner_height = 0
        
        try:
            banner_path = self.parent.resource_path("assets/banner-00-560.png")
            banner_img = Image.open(banner_path)
            self.banner_height = banner_img.height + 10
            print(f"Banner image height: {banner_img.height}, total banner_height: {self.banner_height}")
            self.banner_photo = ImageTk.PhotoImage(banner_img)
            
            self.banner_label = ttk.Label(self.banner_frame, image=self.banner_photo, cursor="hand2")
            self.banner_label.pack(pady=(4, 6))
            self.banner_label.bind("<Button-1>", lambda e: self.open_scorchsoft())
        except Exception as e:
            print(f"Banner load error: {e}")
            self.banner_height = 260
        
        self.hide_banner_link = ttk.Label(
            self.banner_frame, text="Hide Banner",
            style="Muted.TLabel", cursor="hand2"
        )
        self.hide_banner_link.pack(pady=(4, 12))
        self.hide_banner_link.bind("<Button-1>", lambda e: self.parent.toggle_banner())
        
        # Powered by label
        self.powered_by_label = ttk.Label(
            self.banner_frame, text="Powered by Scorchsoft.com",
            cursor="hand2", foreground=self.theme.SCORCHSOFT_RED
        )
        self.powered_by_label.bind("<Button-1>", lambda e: self.open_scorchsoft())
        
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
        banner_delta = self.banner_height if hasattr(self, 'banner_height') and self.banner_height > 0 else 260
        link_height = 35  # Space needed for footer link (same for both states)
        
        if self.banner_visible:
            # Hiding banner - reduce height but keep space for "Powered by"
            new_height = current_height - (banner_delta - link_height)
            if self.banner_label:
                self.banner_label.pack_forget()
            self.hide_banner_link.pack_forget()
            self.powered_by_label.pack(pady=(8, 12))
            try:
                self.parent.help_menu.entryconfig("Hide Banner", label="Show Banner")
            except:
                pass
        else:
            # Showing banner - add back the height difference
            new_height = current_height + (banner_delta - link_height)
            if self.banner_label:
                self.banner_label.pack(pady=(4, 6))
            self.powered_by_label.pack_forget()
            self.hide_banner_link.pack(pady=(4, 12))  # More padding for visibility
            try:
                self.parent.help_menu.entryconfig("Show Banner", label="Hide Banner")
            except:
                pass

        self.parent.geometry(f"{self.parent.winfo_width()}x{new_height}")
        self.banner_visible = not self.banner_visible
        
        # Save the banner visibility setting to config
        self.parent.config_manager.hide_banner = not self.banner_visible
        self.parent.config_manager.save_settings()
    
    def update_model_label(self):
        lang = "Auto" if self.parent.whisper_language == "auto" else self.parent.whisper_language.upper()
        model_type = "GPT" if self.parent.transcription_model_type == "gpt" else "Whisper"
        self.model_label.configure(
            text=f"{self.parent.transcription_model} ({model_type}, {lang}) · {self.parent.ai_model} · {self.parent.current_prompt_name}"
        )
        
    def _update_nav_button_appearance(self):
        """Update navigation button colors based on disabled state."""
        enabled_color = self.theme.TEXT_SECONDARY
        disabled_color = self.theme.TEXT_MUTED
        
        self.button_first_page.configure(
            foreground=disabled_color if self._nav_button_disabled["first"] else enabled_color,
            cursor="" if self._nav_button_disabled["first"] else "hand2"
        )
        self.button_arrow_left.configure(
            foreground=disabled_color if self._nav_button_disabled["left"] else enabled_color,
            cursor="" if self._nav_button_disabled["left"] else "hand2"
        )
        self.button_arrow_right.configure(
            foreground=disabled_color if self._nav_button_disabled["right"] else enabled_color,
            cursor="" if self._nav_button_disabled["right"] else "hand2"
        )
    
    def update_navigation_buttons(self):
        # Update disabled states
        if self.parent.history_index >= len(self.parent.history) - 1:
            self._nav_button_disabled["first"] = True
            self._nav_button_disabled["left"] = True
        else:
            self._nav_button_disabled["first"] = False
            self._nav_button_disabled["left"] = False

        if self.parent.history_index <= 0:
            self._nav_button_disabled["right"] = True
        else:
            self._nav_button_disabled["right"] = False
        
        self._update_nav_button_appearance()
            
    def update_transcription_text(self):
        if 0 <= self.parent.history_index < len(self.parent.history):
            self.transcription_text.delete("1.0", tk.END)
            self.transcription_text.insert("1.0", self.parent.history[self.parent.history_index])
            # Update scrollbar visibility after content change
            self.parent.after(10, self._update_scrollbar_visibility)
            
    def set_status(self, message, color="blue"):
        color_map = {
            "blue": (self.theme.STATUS_IDLE, self.theme.TEXT_TERTIARY),
            "green": (self.theme.STATUS_SUCCESS, self.theme.STATUS_SUCCESS),
            "red": (self.theme.RECORDING_TEXT, self.theme.RECORDING_TEXT),
            "orange": (self.theme.STATUS_PROCESSING, self.theme.STATUS_PROCESSING)
        }
        dot_color, text_color = color_map.get(color, (self.theme.STATUS_IDLE, self.theme.TEXT_TERTIARY))
        
        # TTK labels use configure with foreground
        self.status_label.configure(text=message, foreground=text_color)
        self.status_dot.configure(foreground=dot_color)
        
        if "Recording" in message:
            self._pulse_recording()
    
    def _pulse_recording(self):
        if not hasattr(self, '_pulse_state'):
            self._pulse_state = True
        if "Recording" in str(self.status_label.cget("text")):
            self._pulse_state = not self._pulse_state
            self.status_dot.configure(
                foreground=self.theme.STATUS_RECORDING if self._pulse_state else self.theme.TEXT_MUTED
            )
            self.parent.after(500, self._pulse_recording)

    def _copy_transcription(self):
        """Copy the entire transcription text to clipboard."""
        text = self.transcription_text.get("1.0", "end-1c")
        if text.strip():
            pyperclip.copy(text)
            self._show_toast("Copied to clipboard")
    
    def _show_toast(self, message, duration=1500):
        """Show a toast notification that fades away."""
        # Create toast window
        toast = tk.Toplevel(self.parent)
        toast.overrideredirect(True)  # Remove window decorations
        toast.attributes('-topmost', True)
        
        # Style the toast
        toast.configure(bg=self.theme.BG_TERTIARY)
        
        # Create rounded frame effect with border
        frame = tk.Frame(toast, bg=self.theme.BG_TERTIARY, padx=16, pady=10)
        frame.pack()
        
        # Toast label
        label = tk.Label(
            frame,
            text=message,
            font=(self.theme.FONT, self.theme.FONT_SIZE_MD),
            fg=self.theme.TEXT_PRIMARY,
            bg=self.theme.BG_TERTIARY
        )
        label.pack()
        
        # Position toast near the copy button
        toast.update_idletasks()
        toast_width = toast.winfo_reqwidth()
        toast_height = toast.winfo_reqheight()
        
        # Get copy button position
        btn_x = self.button_copy.winfo_rootx()
        btn_y = self.button_copy.winfo_rooty()
        btn_height = self.button_copy.winfo_height()
        
        # Position below the copy button
        x = btn_x - toast_width // 2 + self.button_copy.winfo_width() // 2
        y = btn_y + btn_height + 8
        
        toast.geometry(f"+{x}+{y}")
        
        # Fade out and destroy after duration
        def fade_out(alpha=1.0):
            if alpha > 0:
                toast.attributes('-alpha', alpha)
                self.parent.after(30, lambda: fade_out(alpha - 0.1))
            else:
                toast.destroy()
        
        # Start fade out after duration
        self.parent.after(duration, fade_out)
    
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
            # BOTH buttons turn red gradient and show "Stop and Process"
            self.record_button_transcribe.configure(
                text="Stop and Process",
                solid_color=None,  # Use gradient mode
                solid_hover=None,
                gradient_start=self.theme.RECORDING_GRADIENT_START,
                gradient_mid=self.theme.RECORDING_GRADIENT_MID,
                gradient_end=self.theme.RECORDING_GRADIENT_END,
                hover_start=self.theme.RECORDING_GRADIENT_HOVER_START,
                hover_mid=self.theme.RECORDING_GRADIENT_HOVER_MID,
                hover_end=self.theme.RECORDING_GRADIENT_HOVER_END,
                text_color=self.theme.TEXT_PRIMARY  # White text on red
            )
            self.record_button_edit.configure(
                text="Stop and Process",
                solid_color=None,  # Use gradient mode
                solid_hover=None,
                gradient_start=self.theme.RECORDING_GRADIENT_START,
                gradient_mid=self.theme.RECORDING_GRADIENT_MID,
                gradient_end=self.theme.RECORDING_GRADIENT_END,
                hover_start=self.theme.RECORDING_GRADIENT_HOVER_START,
                hover_mid=self.theme.RECORDING_GRADIENT_HOVER_MID,
                hover_end=self.theme.RECORDING_GRADIENT_HOVER_END,
                text_color=self.theme.TEXT_PRIMARY  # White text on red
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
        
        # Reset to original gradient mode with white text
        self.record_button_transcribe.configure(
            text="Record + Transcript",
            solid_color=None,
            solid_hover=None,
            gradient_start=self.theme.GRADIENT_START,
            gradient_mid=self.theme.GRADIENT_MID,
            gradient_end=self.theme.GRADIENT_END,
            hover_start=self.theme.GRADIENT_HOVER_START,
            hover_mid=self.theme.GRADIENT_HOVER_MID,
            hover_end=self.theme.GRADIENT_HOVER_END,
            text_color=self.theme.TEXT_PRIMARY
        )
        self.record_button_edit.configure(
            text="Record + AI Edit",
            solid_color=None,
            solid_hover=None,
            gradient_start=self.theme.GRADIENT_START,
            gradient_mid=self.theme.GRADIENT_MID,
            gradient_end=self.theme.GRADIENT_END,
            hover_start=self.theme.GRADIENT_HOVER_START,
            hover_mid=self.theme.GRADIENT_HOVER_MID,
            hover_end=self.theme.GRADIENT_HOVER_END,
            text_color=self.theme.TEXT_PRIMARY
        )
        
        # TTK labels use configure with text
        if hasattr(self, 'shortcut_label_left') and self.shortcut_label_left:
            self.shortcut_label_left.configure(text=transcribe_shortcut)
        if hasattr(self, 'shortcut_label_right') and self.shortcut_label_right:
            self.shortcut_label_right.configure(text=edit_shortcut)
