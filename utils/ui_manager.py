import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw
import platform
import ctypes
import time
import sv_ttk
import pyperclip

from utils.tooltip import ToolTip
from utils.config_manager import get_config
from utils.platform import open_url
from utils.i18n import _, _n
from utils.theme import (
    ThemeColors,
    get_font,
    get_font_size,
    get_font_family,
    get_spacing,
    get_radius,
    get_button_height,
    get_border_width,
    get_switch_size,
    get_text_area_height,
)


def get_system_font():
    """Get the appropriate system font for the current platform."""
    system = platform.system()
    if system == 'Windows':
        return "Segoe UI"
    elif system == 'Darwin':  # macOS
        return "SF Pro Text"
    else:  # Linux
        # Try common Linux fonts in order of preference
        import tkinter.font as tkfont
        try:
            # Need a temporary root window to query fonts
            temp_root = tk._default_root
            if temp_root is None:
                # Fonts can't be queried yet, use a safe default
                return "TkDefaultFont"
            available_fonts = tkfont.families()
            linux_fonts = [
                "Ubuntu",
                "Noto Sans",
                "DejaVu Sans",
                "Liberation Sans",
                "FreeSans",
                "Sans",
            ]
            for font in linux_fonts:
                if font in available_fonts:
                    return font
        except Exception:
            pass
        return "TkDefaultFont"  # Ultimate fallback


# ═══════════════════════════════════════════════════════════════════════════════
# SCORCHSOFT BRAND THEME
# ═══════════════════════════════════════════════════════════════════════════════

class ModernTheme:
    """Scorchsoft-branded dark theme with accessible typography.

    This class provides backward compatibility by delegating to ThemeColors
    and the new theme system. New code should use the theme module directly:

        from utils.theme import ThemeColors, get_font, get_spacing, get_radius
    """

    # Background colors - delegate to ThemeColors
    BG_PRIMARY = ThemeColors.BG_PRIMARY
    BG_SECONDARY = ThemeColors.BG_SECONDARY
    BG_TERTIARY = ThemeColors.BG_TERTIARY
    BG_HOVER = ThemeColors.BG_HOVER
    BG_MENU = ThemeColors.BG_MENU

    # Scorchsoft Red - reserved for recording/stop states
    SCORCHSOFT_RED = ThemeColors.SCORCHSOFT_RED
    SCORCHSOFT_RED_HOVER = ThemeColors.SCORCHSOFT_RED_HOVER

    # Action buttons - gradient inspired by logo (cyan to purple)
    ACCENT_PRIMARY = ThemeColors.ACCENT_PRIMARY
    ACCENT_HOVER = ThemeColors.ACCENT_HOVER

    # Gradient colors (matching logo: cyan -> purple with glow)
    GRADIENT_START = ThemeColors.GRADIENT_START
    GRADIENT_MID = ThemeColors.GRADIENT_MID
    GRADIENT_END = ThemeColors.GRADIENT_END
    GRADIENT_HOVER_START = ThemeColors.GRADIENT_HOVER_START
    GRADIENT_HOVER_MID = ThemeColors.GRADIENT_HOVER_MID
    GRADIENT_HOVER_END = ThemeColors.GRADIENT_HOVER_END

    # Recording status - lighter/brighter red for visibility
    RECORDING_TEXT = ThemeColors.RECORDING_TEXT

    # Recording button gradient (red tones)
    RECORDING_GRADIENT_START = ThemeColors.RECORDING_GRADIENT_START
    RECORDING_GRADIENT_MID = ThemeColors.RECORDING_GRADIENT_MID
    RECORDING_GRADIENT_END = ThemeColors.RECORDING_GRADIENT_END
    RECORDING_GRADIENT_HOVER_START = ThemeColors.RECORDING_GRADIENT_HOVER_START
    RECORDING_GRADIENT_HOVER_MID = ThemeColors.RECORDING_GRADIENT_HOVER_MID
    RECORDING_GRADIENT_HOVER_END = ThemeColors.RECORDING_GRADIENT_HOVER_END
    RECORDING_BORDER = ThemeColors.RECORDING_BORDER

    # Text - high contrast for accessibility
    TEXT_PRIMARY = ThemeColors.TEXT_PRIMARY
    TEXT_SECONDARY = ThemeColors.TEXT_SECONDARY
    TEXT_TERTIARY = ThemeColors.TEXT_TERTIARY
    TEXT_MUTED = ThemeColors.TEXT_MUTED

    # Status
    STATUS_IDLE = ThemeColors.STATUS_IDLE
    STATUS_PROCESSING = ThemeColors.STATUS_PROCESSING
    STATUS_RECORDING = ThemeColors.STATUS_RECORDING
    STATUS_SUCCESS = ThemeColors.STATUS_SUCCESS

    # Borders
    BORDER = ThemeColors.BORDER
    BORDER_STRONG = ThemeColors.BORDER_STRONG

    # Typography - ACCESSIBLE SIZES (cross-platform font)
    # These are base sizes; the theme system handles HiDPI scaling
    FONT = None  # Set dynamically after Tk init via init_font()
    FONT_SIZE_XXS = 9       # Only for very very minor elements
    FONT_SIZE_XS = 11       # Only for very minor elements
    FONT_SIZE_SM = 12       # Secondary labels
    FONT_SIZE_MD = 13       # Menu, labels, hints
    FONT_SIZE_LG = 14       # Body text, inputs
    FONT_SIZE_XL = 15       # Primary inputs

    # Sizing - use get_radius() from theme for HiDPI-aware values
    RADIUS = 8
    RADIUS_SM = 6
    RADIUS_PILL = 25        # Pill-shaped buttons

    @classmethod
    def init_font(cls):
        """Initialize the font after Tk is available."""
        if cls.FONT is None:
            cls.FONT = get_font_family()


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


class StyledPopupMenu:
    """A modern styled popup menu using ttk widgets for Sun Valley theme compatibility."""

    def __init__(self, parent, theme=None, menu_name=None):
        self.parent = parent
        self.theme = theme or ModernTheme()
        self.popup = None
        self.items = []  # List of menu items: (type, label, command, variable, accelerator)
        self._is_open = False
        self._pending_close_id = None  # Track pending close timer
        self._menu_name = menu_name  # Identify this menu for toggle behavior
        self._close_time = 0  # Track when menu was last closed for toggle detection
        self._parent_click_binding = None  # Track binding for cleanup
        
    def add_command(self, label, command=None, accelerator=None):
        """Add a command item to the menu."""
        self.items.append(('command', label, command, None, accelerator))
        
    def add_checkbutton(self, label, variable=None, command=None):
        """Add a checkbutton item to the menu."""
        self.items.append(('checkbutton', label, command, variable, None))
        
    def add_separator(self):
        """Add a separator line to the menu."""
        self.items.append(('separator', None, None, None, None))
    
    def entryconfig(self, index_or_label, **kwargs):
        """Configure a menu entry by index or label (for compatibility)."""
        # Find the item by label if string is passed
        target_index = None
        if isinstance(index_or_label, str):
            for i, item in enumerate(self.items):
                if item[1] == index_or_label:
                    target_index = i
                    break
        else:
            target_index = index_or_label
        
        if target_index is not None and 0 <= target_index < len(self.items):
            item_type, label, command, variable, accelerator = self.items[target_index]
            # Update label if provided
            if 'label' in kwargs:
                self.items[target_index] = (item_type, kwargs['label'], command, variable, accelerator)
        
    def tk_popup(self, x, y):
        """Show the popup menu at the specified coordinates."""
        print(f"[POPUP DEBUG] tk_popup called, menu={self._menu_name}, is_open={self._is_open}, time_since_close={time.time() - self._close_time:.3f}")

        # Cancel any pending close timer from previous popup
        if self._pending_close_id is not None:
            try:
                self.parent.after_cancel(self._pending_close_id)
            except:
                pass
            self._pending_close_id = None

        # Toggle behavior: if menu was just closed (within 300ms), don't reopen
        # This handles the case where user clicks the same menu button to close it
        if time.time() - self._close_time < 0.3:
            print("[POPUP DEBUG] Skipping open - too soon after close (toggle)")
            return

        if self._is_open:
            print("[POPUP DEBUG] Already open, closing")
            self._close()
            return  # Just close, don't reopen

        print("[POPUP DEBUG] Opening popup")
        self._is_open = True
        
        # Create popup window
        self.popup = tk.Toplevel(self.parent)
        self.popup.withdraw()  # Hide initially to prevent flicker
        self.popup.overrideredirect(True)  # Remove window decorations
        self.popup.attributes('-topmost', True)
        
        # Check current theme setting
        config = get_config()
        is_dark = config.dark_mode
        
        # Set title bar based on theme
        if is_dark:
            set_dark_title_bar(self.popup)
        
        # Theme-aware colors for the popup menu
        if is_dark:
            border_color = self.theme.BORDER
            bg_color = self.theme.BG_SECONDARY
            hover_color = self.theme.BG_HOVER
            text_color = self.theme.TEXT_PRIMARY
            text_muted = self.theme.TEXT_MUTED
        else:
            border_color = "#d0d0d0"
            bg_color = "#ffffff"
            hover_color = "#f0f0f0"
            text_color = "#1c1c1c"
            text_muted = "#666666"
        
        # Store colors for use in menu item creation
        self._current_bg = bg_color
        self._current_hover = hover_color
        self._current_text = text_color
        self._current_text_muted = text_muted
        
        # Main frame with border
        outer_frame = tk.Frame(
            self.popup,
            bg=border_color,
            padx=1,
            pady=1
        )
        outer_frame.pack(fill=tk.BOTH, expand=True)
        
        # Inner content frame
        inner_frame = tk.Frame(
            outer_frame,
            bg=bg_color,
            padx=4,
            pady=6
        )
        inner_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create menu items
        for item_type, label, command, variable, accelerator in self.items:
            if item_type == 'separator':
                sep = tk.Frame(inner_frame, height=1, bg=border_color)
                sep.pack(fill=tk.X, pady=6, padx=8)
            elif item_type == 'command':
                self._create_command_item(inner_frame, label, command, accelerator)
            elif item_type == 'checkbutton':
                self._create_checkbutton_item(inner_frame, label, command, variable)
        
        # Update geometry and show
        self.popup.update_idletasks()
        
        popup_width = self.popup.winfo_reqwidth()
        popup_height = self.popup.winfo_reqheight()
        
        # Get the virtual screen bounds (spans all monitors)
        # winfo_vrootx/y give the offset of the virtual root
        # For multi-monitor, we need to be careful about bounds checking
        try:
            # On Windows, we can get multi-monitor info via ctypes
            if platform.system() == "Windows":
                # Get virtual screen dimensions (all monitors combined)
                user32 = ctypes.windll.user32
                # SM_XVIRTUALSCREEN = 76, SM_YVIRTUALSCREEN = 77
                # SM_CXVIRTUALSCREEN = 78, SM_CYVIRTUALSCREEN = 79
                virtual_left = user32.GetSystemMetrics(76)
                virtual_top = user32.GetSystemMetrics(77)
                virtual_width = user32.GetSystemMetrics(78)
                virtual_height = user32.GetSystemMetrics(79)
                
                # Adjust position if menu would go off virtual screen edges
                if x + popup_width > virtual_left + virtual_width:
                    x = virtual_left + virtual_width - popup_width - 5
                if y + popup_height > virtual_top + virtual_height:
                    y = virtual_top + virtual_height - popup_height - 5
                if x < virtual_left:
                    x = virtual_left + 5
                if y < virtual_top:
                    y = virtual_top + 5
            else:
                # For non-Windows, use basic screen dimensions
                screen_width = self.popup.winfo_screenwidth()
                screen_height = self.popup.winfo_screenheight()
                if x + popup_width > screen_width:
                    x = screen_width - popup_width - 5
                if y + popup_height > screen_height:
                    y = screen_height - popup_height - 5
        except Exception as e:
            print(f"Error getting screen dimensions: {e}")
            # Fallback: don't adjust position
        
        self.popup.geometry(f"+{x}+{y}")
        self.popup.deiconify()  # Show the popup

        # Store popup geometry for click-outside detection
        self._popup_x = x
        self._popup_y = y
        self._popup_width = popup_width
        self._popup_height = popup_height

        # Close on escape
        self.popup.bind('<Escape>', lambda e: self._close())

        # On Linux, FocusOut is unreliable for overrideredirect windows
        # Use grab to capture all clicks and check if they're outside
        if platform.system() == "Linux":
            # With grab_set(), clicks outside the popup are still sent to the popup
            # but with screen coordinates we can detect if they're outside bounds
            def on_any_click(e):
                print(f"[POPUP DEBUG] on_any_click called, is_open={self._is_open}, popup={self.popup}")
                if self.popup and self._is_open:
                    # Get click coordinates relative to screen
                    click_x = e.x_root
                    click_y = e.y_root
                    # Check if click is outside popup bounds
                    inside = (self._popup_x <= click_x <= self._popup_x + self._popup_width and
                              self._popup_y <= click_y <= self._popup_y + self._popup_height)
                    print(f"[POPUP DEBUG] click=({click_x},{click_y}), popup=({self._popup_x},{self._popup_y},{self._popup_width},{self._popup_height}), inside={inside}")
                    if not inside:
                        print("[POPUP DEBUG] Closing popup (click outside)")
                        self._close()
                        return "break"  # Consume the event

            # Use local grab to capture clicks
            try:
                self.popup.grab_set()
                print("[POPUP DEBUG] grab_set() succeeded")
            except Exception as e:
                print(f"[POPUP DEBUG] grab_set() failed: {e}")

            # Bind click handler to popup - this catches all clicks due to grab
            self.popup.bind('<Button-1>', on_any_click)
        else:
            # Windows/macOS: FocusOut works reliably
            def schedule_close(e):
                self._pending_close_id = self.parent.after(100, self._close)
            self.popup.bind('<FocusOut>', schedule_close)
            self.popup.focus_set()
        
    def _create_command_item(self, parent, label, command, accelerator=None):
        """Create a command menu item."""
        bg = self._current_bg
        hover = self._current_hover
        text = self._current_text
        text_muted = self._current_text_muted
        
        item_frame = tk.Frame(parent, bg=bg, cursor='hand2')
        item_frame.pack(fill=tk.X, pady=1)
        
        # Label
        lbl = tk.Label(
            item_frame,
            text=f"    {label}",
            font=get_font('md'),
            fg=text,
            bg=bg,
            anchor='w',
            padx=12,
            pady=6
        )
        lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Accelerator (keyboard shortcut) if provided
        if accelerator:
            accel_lbl = tk.Label(
                item_frame,
                text=accelerator,
                font=get_font('xs'),
                fg=text_muted,
                bg=bg,
                anchor='e',
                padx=12
            )
            accel_lbl.pack(side=tk.RIGHT)
        
        def on_enter(e):
            item_frame.configure(bg=hover)
            lbl.configure(bg=hover)
            if accelerator:
                accel_lbl.configure(bg=hover)
        
        def on_leave(e):
            item_frame.configure(bg=bg)
            lbl.configure(bg=bg)
            if accelerator:
                accel_lbl.configure(bg=bg)
        
        def on_click(e):
            self._close()
            if command:
                self.parent.after(10, command)
        
        for widget in [item_frame, lbl] + ([accel_lbl] if accelerator else []):
            widget.bind('<Enter>', on_enter)
            widget.bind('<Leave>', on_leave)
            widget.bind('<Button-1>', on_click)
    
    def _create_checkbutton_item(self, parent, label, command, variable):
        """Create a checkbutton menu item."""
        bg = self._current_bg
        hover = self._current_hover
        text = self._current_text
        text_muted = self._current_text_muted
        
        item_frame = tk.Frame(parent, bg=bg, cursor='hand2')
        item_frame.pack(fill=tk.X, pady=1)
        
        # Checkmark indicator
        is_checked = variable.get() if variable else False
        check_text = "✓" if is_checked else "   "
        check_lbl = tk.Label(
            item_frame,
            text=check_text,
            font=get_font('md'),
            fg=self.theme.ACCENT_PRIMARY if is_checked else text_muted,
            bg=bg,
            width=3,
            anchor='center'
        )
        check_lbl.pack(side=tk.LEFT, padx=(8, 0))

        # Label
        lbl = tk.Label(
            item_frame,
            text=label,
            font=get_font('md'),
            fg=text,
            bg=bg,
            anchor='w',
            padx=4,
            pady=6
        )
        lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
        
        def on_enter(e):
            item_frame.configure(bg=hover)
            check_lbl.configure(bg=hover)
            lbl.configure(bg=hover)
        
        def on_leave(e):
            item_frame.configure(bg=bg)
            check_lbl.configure(bg=bg)
            lbl.configure(bg=bg)
        
        def on_click(e):
            # Toggle the variable
            if variable:
                new_val = not variable.get()
                variable.set(new_val)
                # Update checkmark
                check_lbl.configure(
                    text="✓" if new_val else "   ",
                    fg=self.theme.ACCENT_PRIMARY if new_val else self.theme.TEXT_MUTED
                )
            self._close()
            if command:
                self.parent.after(10, command)
        
        for widget in [item_frame, check_lbl, lbl]:
            widget.bind('<Enter>', on_enter)
            widget.bind('<Leave>', on_leave)
            widget.bind('<Button-1>', on_click)
    
    def _close(self):
        """Close the popup menu."""
        print(f"[POPUP DEBUG] _close called, is_open={self._is_open}, popup={self.popup}")
        # Clear the pending close timer reference
        self._pending_close_id = None

        if self.popup and self._is_open:
            self._is_open = False
            # Record close time for toggle detection
            self._close_time = time.time()
            print(f"[POPUP DEBUG] Set _close_time to {self._close_time}")

            # Release grab on Linux before destroying
            if platform.system() == "Linux":
                try:
                    self.popup.grab_release()
                    print("[POPUP DEBUG] grab_release() succeeded")
                except Exception as e:
                    print(f"[POPUP DEBUG] grab_release() failed: {e}")

            try:
                self.popup.destroy()
                print("[POPUP DEBUG] popup.destroy() succeeded")
            except Exception as e:
                print(f"[POPUP DEBUG] popup.destroy() failed: {e}")
            self.popup = None

            # On Linux, explicitly restore focus to main window after grab release
            # Without this, text inputs won't receive focus on click
            if platform.system() == "Linux":
                try:
                    root = self.parent.winfo_toplevel()
                    root.focus_force()
                    print("[POPUP DEBUG] focus_force() on root succeeded")
                except Exception as e:
                    print(f"[POPUP DEBUG] focus_force() failed: {e}")


class GradientButton(tk.Canvas):
    """Custom button with gradient background (cyan -> blue -> purple like logo)."""

    def __init__(self, parent, text="", command=None, width=200, height=50,
                 corner_radius=25, font=None,
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
        # Use provided font or default to theme font
        self.font = font if font is not None else get_font('md', 'bold')
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
        self._resize_pending = None  # For debouncing resize events
        self._initial_render_done = False  # Skip initial render, wait for correct size

        # Don't create gradient images here - wait for Configure event with actual size
        # This prevents the "flash" where buttons render small then resize

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

        # Guard against zero or negative dimensions (window resized too small)
        inner_w = sw - border * 2
        inner_h = sh - border * 2
        if inner_w < 1 or inner_h < 1 or sw < 1 or sh < 1:
            # Return a minimal transparent image
            return ImageTk.PhotoImage(Image.new('RGBA', (max(1, w), max(1, h)), (0, 0, 0, 0)))

        img = Image.new('RGBA', (sw, sh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Draw border first (if border_width > 0)
        if self.border_width > 0:
            border_rgb = self._hex_to_rgb(self.border_color)
            draw.rounded_rectangle([(0, 0), (sw-1, sh-1)], radius=sr, fill=(*border_rgb, 255))
        
        # Create gradient for inner area
        inner_img = Image.new('RGBA', (inner_w, inner_h), (0, 0, 0, 0))
        inner_r = max(0, sr - border)

        start_rgb = self._hex_to_rgb(color_start)
        mid_rgb = self._hex_to_rgb(color_mid)
        end_rgb = self._hex_to_rgb(color_end)

        # Pre-calculate horizontal gradient colors (much faster than per-pixel)
        h_colors = []
        for x in range(inner_w):
            ratio = x / (inner_w - 1) if inner_w > 1 else 0
            if ratio < 0.5:
                local_ratio = ratio * 2
                h_colors.append(self._interpolate_color(start_rgb, mid_rgb, local_ratio))
            else:
                local_ratio = (ratio - 0.5) * 2
                h_colors.append(self._interpolate_color(mid_rgb, end_rgb, local_ratio))

        # Pre-calculate vertical highlight multipliers
        v_highlights = [1.0 + 0.12 * (1 - y / inner_h) for y in range(inner_h)]

        # Build pixel data in one pass (much faster than putpixel)
        pixels = []
        for y in range(inner_h):
            highlight = v_highlights[y]
            for x in range(inner_w):
                base_rgb = h_colors[x]
                r_val = min(255, int(base_rgb[0] * highlight))
                g_val = min(255, int(base_rgb[1] * highlight))
                b_val = min(255, int(base_rgb[2] * highlight))
                pixels.append((r_val, g_val, b_val, 255))

        inner_img.putdata(pixels)
        
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
        """Handle resize with debouncing to prevent expensive operations during drag."""
        if event.width != self.width or event.height != self.height:
            self.width = event.width
            self.height = event.height

            # First render: create images immediately at correct size (no debounce)
            # This prevents the "flash" where buttons appear small then resize
            if not self._initial_render_done:
                self._initial_render_done = True
                self._create_gradient_images()
                self._draw()
                return

            # Cancel any pending resize operation
            if self._resize_pending is not None:
                self.after_cancel(self._resize_pending)

            # Debounce: only regenerate images after resize stops (100ms delay)
            self._resize_pending = self.after(100, self._do_resize)

            # Immediately redraw with existing images (scaled/stretched) for responsiveness
            self._draw()

    def _do_resize(self):
        """Actually regenerate gradient images after resize stops."""
        self._resize_pending = None
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
        if 'border_color' in kwargs:
            self.border_color = kwargs.pop('border_color')
            regenerate_gradients = True
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
        # Initialize font before using theme (needs Tk to be available)
        ModernTheme.init_font()
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
            font=get_font('md', 'bold'))

        # Custom style for muted text
        style.configure("Muted.TLabel",
            font=get_font('sm'))

        # Smaller muted text for model info
        style.configure("Small.TLabel",
            font=get_font('xxs'))

        # Custom style for status text
        style.configure("Status.TLabel",
            font=get_font('xs'))

        # Nav button style
        style.configure("Nav.TButton",
            font=get_font('lg'),
            padding=(4, 4))

        # Menu bar button style
        style.configure("Menu.TButton",
            font=get_font('menu_button'),
            padding=(8, 4))

        # Switch toggle style (for Options checkbuttons)
        style.configure("Switch.TCheckbutton",
            font=get_font('sm'))

        # LabelFrame style (for Options frame title)
        style.configure("TLabelframe.Label",
            font=get_font('sm'))

        # Navigation arrow buttons (Latest, Newer, Older)
        style.configure("Nav.TLabel",
            font=get_font('nav_arrow'))

        # Separator between nav arrows and copy
        style.configure("Separator.TLabel",
            font=get_font('separator'))

        # Copy link button
        style.configure("Copy.TLabel",
            font=get_font('copy_link'))

    def create_widgets(self):
        """Create UI with Sun Valley theme (ttk widgets)."""
        
        # Get dark mode setting from config
        config = get_config()
        is_dark = config.dark_mode
        
        # Apply title bar styling based on theme
        if is_dark:
            set_dark_title_bar(self.parent)
        
        # Apply Sun Valley theme based on setting
        sv_ttk.set_theme("dark" if is_dark else "light")
        
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

        # Use Menu.TButton style for scaled fonts
        self.file_btn = ttk.Button(menubar, text=_("File"), width=8, style="Menu.TButton",
                              command=lambda: self._show_menu("file"))
        self.file_btn.pack(side=tk.LEFT, padx=(8, 2), pady=6)

        self.settings_btn = ttk.Button(menubar, text=_("Settings"), width=10, style="Menu.TButton",
                                  command=lambda: self._show_menu("settings"))
        self.settings_btn.pack(side=tk.LEFT, padx=2, pady=6)

        self.actions_btn = ttk.Button(menubar, text=_("Actions"), width=9, style="Menu.TButton",
                                 command=lambda: self._show_menu("actions"))
        self.actions_btn.pack(side=tk.LEFT, padx=2, pady=6)

        self.help_btn = ttk.Button(menubar, text=_("Help"), width=8, style="Menu.TButton",
                              command=lambda: self._show_menu("help"))
        self.help_btn.pack(side=tk.LEFT, padx=2, pady=6)

        self._menu_buttons = {
            "file": self.file_btn, "settings": self.settings_btn,
            "actions": self.actions_btn, "help": self.help_btn
        }
        
        # Content area with padding (minimal bottom padding)
        content = ttk.Frame(self.main_frame, padding=(28, 20, 28, 0))
        content.pack(fill=tk.BOTH, expand=True)
        
        # ─────────────────────────────────────────────────────────────────────
        # INPUT DEVICE
        # ─────────────────────────────────────────────────────────────────────
        
        self.device_label = ttk.Label(content, text=_("Input Device"), style="Section.TLabel")
        self.device_label.pack(anchor="w", pady=(0, 10))

        devices = self.parent.audio_manager.get_input_devices()
        self._has_audio_devices = bool(devices)

        if not devices:
            # No audio devices found - show warning but continue with UI
            # This allows the app to run for UI testing on systems without audio
            devices = {"No audio devices found": -1}
            self.parent.selected_device.set("No audio devices found")
            print("Warning: No input audio devices found. Recording will not work.")
        else:
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
            state="readonly" if self._has_audio_devices else "disabled",
            font=get_font('md')
        )
        self.device_combo.pack(fill=tk.X, pady=(0, 24), ipady=6)

        # Set dropdown list font to match
        self.parent.option_add('*TCombobox*Listbox.font', get_font('md'))
        
        # ─────────────────────────────────────────────────────────────────────
        # TRANSCRIPTION
        # ─────────────────────────────────────────────────────────────────────
        
        header_row = ttk.Frame(content)
        header_row.pack(fill=tk.X, pady=(0, 10))
        
        self.transcription_label = ttk.Label(header_row, text=_("Transcription"), style="Section.TLabel")
        self.transcription_label.pack(side=tk.LEFT)
        
        # Navigation buttons - minimal icon-only style
        # Use ttk widgets throughout to inherit correct theme background
        nav_frame = ttk.Frame(header_row)
        nav_frame.pack(side=tk.RIGHT)

        self._nav_button_disabled = {"first": True, "left": True, "right": True}

        nav_btn_pad = get_spacing('xs')

        self.button_first_page = ttk.Label(nav_frame, text="«", style="Nav.TLabel", cursor="hand2")
        self.button_first_page.pack(side=tk.LEFT, padx=nav_btn_pad)
        self.button_first_page.bind("<Button-1>", lambda e: None if self._nav_button_disabled["first"] else self.parent.go_to_first_page())

        self.button_arrow_left = ttk.Label(nav_frame, text="‹", style="Nav.TLabel", cursor="hand2")
        self.button_arrow_left.pack(side=tk.LEFT, padx=nav_btn_pad)
        self.button_arrow_left.bind("<Button-1>", lambda e: None if self._nav_button_disabled["left"] else self.parent.navigate_left())

        self.button_arrow_right = ttk.Label(nav_frame, text="›", style="Nav.TLabel", cursor="hand2")
        self.button_arrow_right.pack(side=tk.LEFT, padx=nav_btn_pad)
        self.button_arrow_right.bind("<Button-1>", lambda e: None if self._nav_button_disabled["right"] else self.parent.navigate_right())

        # Separator and copy - with padding to align baselines with arrows
        separator_label = ttk.Label(nav_frame, text="|", style="Separator.TLabel", foreground=self.theme.TEXT_MUTED)
        separator_label.pack(side=tk.LEFT, padx=(get_spacing('sm'), nav_btn_pad), pady=(5, 0))

        # Copy button - more top padding since smaller font (to ai: don't remove the space before "Copy")
        self.button_copy = ttk.Label(nav_frame, text=f"  {_('Copy')}", style="Copy.TLabel", cursor="hand2", foreground=self.theme.TEXT_SECONDARY)
        self.button_copy.pack(side=tk.LEFT, pady=(8, 0))
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
            height=get_text_area_height(),
            font=get_font('sm'),
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
        
        self.status_dot = ttk.Label(status_left, text="●", font=get_font('status_dot'))
        self.status_dot.pack(side=tk.LEFT, padx=(0, 6))
        
        self.status_label = ttk.Label(status_left, text=_("Idle"), style="Status.TLabel")
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

        options_frame = ttk.LabelFrame(content, text="", padding=(16, 10))
        options_frame.pack(fill=tk.X, pady=(0, 12))

        # Center container for toggles
        switches_container = ttk.Frame(options_frame)
        switches_container.pack(expand=True)

        # Sun Valley provides "Switch.TCheckbutton" style for toggle switches
        self.auto_copy_switch = ttk.Checkbutton(
            switches_container,
            text=_("Copy to clipboard"),
            variable=self.parent.auto_copy,
            style="Switch.TCheckbutton"
        )
        self.auto_copy_switch.pack(side=tk.LEFT, padx=(0, 32))

        self.auto_paste_switch = ttk.Checkbutton(
            switches_container,
            text=_("Auto-paste"),
            variable=self.parent.auto_paste,
            style="Switch.TCheckbutton"
        )
        self.auto_paste_switch.pack(side=tk.LEFT)
        
        # ─────────────────────────────────────────────────────────────────────
        # ACTION BUTTONS (Keep custom gradient buttons)
        # ─────────────────────────────────────────────────────────────────────
        
        buttons_frame = ttk.Frame(content)
        buttons_frame.pack(fill=tk.X, pady=(0, 4))
        
        # Calculate button width (will be adjusted on resize)
        btn_width = 200  # Default, will resize
        
        # Use theme-appropriate background color for buttons
        btn_bg_color = "#1c1c1c" if is_dark else "#fafafa"
        
        self.record_button_transcribe = GradientButton(
            buttons_frame,
            text=_("Record + Transcribe"),
            width=btn_width,
            height=get_button_height('md'),
            corner_radius=get_radius('pill'),
            border_width=get_border_width('md'),
            font=get_font('md', 'bold'),
            gradient_start=self.theme.GRADIENT_START,
            gradient_mid=self.theme.GRADIENT_MID,
            gradient_end=self.theme.GRADIENT_END,
            hover_start=self.theme.GRADIENT_HOVER_START,
            hover_mid=self.theme.GRADIENT_HOVER_MID,
            hover_end=self.theme.GRADIENT_HOVER_END,
            text_color=self.theme.TEXT_PRIMARY,
            bg_color=btn_bg_color,
            command=lambda: self.parent.toggle_recording("transcribe")
        )
        btn_gap = get_spacing('sm')
        self.record_button_transcribe.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, btn_gap))

        self.record_button_edit = GradientButton(
            buttons_frame,
            text=_("Record + AI Edit"),
            width=btn_width,
            height=get_button_height('md'),
            corner_radius=get_radius('pill'),
            border_width=get_border_width('md'),
            font=get_font('md', 'bold'),
            gradient_start=self.theme.GRADIENT_START,
            gradient_mid=self.theme.GRADIENT_MID,
            gradient_end=self.theme.GRADIENT_END,
            hover_start=self.theme.GRADIENT_HOVER_START,
            hover_mid=self.theme.GRADIENT_HOVER_MID,
            hover_end=self.theme.GRADIENT_HOVER_END,
            text_color=self.theme.TEXT_PRIMARY,
            bg_color=btn_bg_color,
            command=lambda: self.parent.toggle_recording("edit")
        )
        self.record_button_edit.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(btn_gap, 0))
        
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
            self.banner_frame, text=_("Hide Banner"),
            style="Muted.TLabel", cursor="hand2"
        )
        self.hide_banner_link.pack(pady=(4, 12))
        self.hide_banner_link.bind("<Button-1>", lambda e: self.parent.toggle_banner())

        # Powered by label - light blue in dark mode, purple in light mode
        link_color = self.theme.ACCENT_PRIMARY if is_dark else self.theme.GRADIENT_END
        self.powered_by_label = ttk.Label(
            self.banner_frame, text=_("Developed by Scorchsoft.com | App & AI Developers"),
            cursor="hand2", foreground=link_color,
            font=get_font('xxs', 'underline')
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
        open_url('https://www.scorchsoft.com/')
        
    def toggle_banner(self):
        # Check if window still exists before accessing winfo
        try:
            if not self.parent.winfo_exists():
                return
        except:
            return

        current_width = self.parent.winfo_width()
        current_height = self.parent.winfo_height()

        # If window hasn't been properly rendered yet, just toggle visibility without geometry change
        # This happens when toggle_banner is called during initialization
        window_not_ready = current_width < 100 or current_height < 100

        banner_delta = self.banner_height if hasattr(self, 'banner_height') and self.banner_height > 0 else 260
        link_height = 35  # Space needed for footer link (same for both states)

        if self.banner_visible:
            # Hiding banner - reduce height but keep space for "Powered by"
            new_height = current_height - (banner_delta - link_height)
            if self.banner_label:
                self.banner_label.pack_forget()
            self.hide_banner_link.pack_forget()
            # Use theme spacing for consistent padding - even spacing above and below
            self.powered_by_label.pack(pady=get_spacing('xl'))
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

        # Only adjust geometry if window is properly sized and new dimensions are valid
        if not window_not_ready and new_height > 100 and current_width > 100:
            self.parent.geometry(f"{current_width}x{new_height}")

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
        """Update navigation button colors based on disabled state and theme."""
        # Get current theme setting
        config = get_config()
        is_dark = config.dark_mode
        
        # Use appropriate colors for current theme
        if is_dark:
            enabled_color = self.theme.TEXT_SECONDARY  # Light gray on dark background
            disabled_color = self.theme.TEXT_MUTED     # Darker gray (muted)
            copy_color = self.theme.TEXT_SECONDARY     # Light gray for clickable Copy
        else:
            enabled_color = "#333333"   # Dark gray on light background (clickable)
            disabled_color = "#b0b0b0"  # Lighter gray (muted/disabled)
            copy_color = "#333333"      # Dark gray for clickable Copy
        
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
        
        # Update Copy button color for current theme
        if hasattr(self, 'button_copy') and self.button_copy:
            self.button_copy.configure(foreground=copy_color)
    
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
            font=get_font('md'),
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
            font=get_font('md'),
            bd=0, relief="flat"
        )
        menu.add_command(label=_("Cut"), command=lambda: self.transcription_text.event_generate('<<Cut>>'))
        menu.add_command(label=_("Copy"), command=lambda: self.transcription_text.event_generate('<<Copy>>'))
        menu.add_command(label=_("Paste"), command=lambda: self.transcription_text.event_generate('<<Paste>>'))
        menu.add_separator()
        menu.add_command(label=_("Select All"), command=lambda: self.transcription_text.tag_add("sel", "1.0", "end-1c"))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def update_button_states(self, recording=False, mode=None):
        if recording:
            # BOTH buttons turn red gradient and show "Stop and Process"
            self.record_button_transcribe.configure(
                text=_("Stop and Process"),
                solid_color=None,  # Use gradient mode
                solid_hover=None,
                gradient_start=self.theme.RECORDING_GRADIENT_START,
                gradient_mid=self.theme.RECORDING_GRADIENT_MID,
                gradient_end=self.theme.RECORDING_GRADIENT_END,
                hover_start=self.theme.RECORDING_GRADIENT_HOVER_START,
                hover_mid=self.theme.RECORDING_GRADIENT_HOVER_MID,
                hover_end=self.theme.RECORDING_GRADIENT_HOVER_END,
                border_color=self.theme.RECORDING_BORDER,
                text_color=self.theme.TEXT_PRIMARY  # White text on red
            )
            self.record_button_edit.configure(
                text=_("Stop and Process"),
                solid_color=None,  # Use gradient mode
                solid_hover=None,
                gradient_start=self.theme.RECORDING_GRADIENT_START,
                gradient_mid=self.theme.RECORDING_GRADIENT_MID,
                gradient_end=self.theme.RECORDING_GRADIENT_END,
                hover_start=self.theme.RECORDING_GRADIENT_HOVER_START,
                hover_mid=self.theme.RECORDING_GRADIENT_HOVER_MID,
                hover_end=self.theme.RECORDING_GRADIENT_HOVER_END,
                border_color=self.theme.RECORDING_BORDER,
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
            text=_("Record + Transcribe"),
            solid_color=None,
            solid_hover=None,
            gradient_start=self.theme.GRADIENT_START,
            gradient_mid=self.theme.GRADIENT_MID,
            gradient_end=self.theme.GRADIENT_END,
            hover_start=self.theme.GRADIENT_HOVER_START,
            hover_mid=self.theme.GRADIENT_HOVER_MID,
            hover_end=self.theme.GRADIENT_HOVER_END,
            border_color="#6d9dc5",  # Original cyan border
            text_color=self.theme.TEXT_PRIMARY
        )
        self.record_button_edit.configure(
            text=_("Record + AI Edit"),
            solid_color=None,
            solid_hover=None,
            gradient_start=self.theme.GRADIENT_START,
            gradient_mid=self.theme.GRADIENT_MID,
            gradient_end=self.theme.GRADIENT_END,
            hover_start=self.theme.GRADIENT_HOVER_START,
            hover_mid=self.theme.GRADIENT_HOVER_MID,
            hover_end=self.theme.GRADIENT_HOVER_END,
            border_color="#6d9dc5",  # Original cyan border
            text_color=self.theme.TEXT_PRIMARY
        )
        
        # TTK labels use configure with text
        if hasattr(self, 'shortcut_label_left') and self.shortcut_label_left:
            self.shortcut_label_left.configure(text=transcribe_shortcut)
        if hasattr(self, 'shortcut_label_right') and self.shortcut_label_right:
            self.shortcut_label_right.configure(text=edit_shortcut)

    def refresh_translations(self):
        """Refresh all UI labels with current translations.

        Called when the application language is changed at runtime.
        """
        # Update menu bar buttons
        if hasattr(self, 'file_btn'):
            self.file_btn.configure(text=_("File"))
        if hasattr(self, 'settings_btn'):
            self.settings_btn.configure(text=_("Settings"))
        if hasattr(self, 'actions_btn'):
            self.actions_btn.configure(text=_("Actions"))
        if hasattr(self, 'help_btn'):
            self.help_btn.configure(text=_("Help"))

        # Update section labels
        if hasattr(self, 'device_label'):
            self.device_label.configure(text=_("Input Device"))
        if hasattr(self, 'transcription_label'):
            self.transcription_label.configure(text=_("Transcription"))

        # Update navigation and copy button
        if hasattr(self, 'button_copy'):
            self.button_copy.configure(text=f"  {_('Copy')}")

        # Update status label (only if showing "Idle")
        if hasattr(self, 'status_label'):
            current_text = str(self.status_label.cget('text'))
            # Only update if it's a translatable status
            status_translations = {
                "Idle": _("Idle"),
                "Recording...": _("Recording..."),
                "Success": _("Success"),
                "Error": _("Error"),
            }
            for orig, trans in status_translations.items():
                if current_text == orig or current_text == trans:
                    self.status_label.configure(text=trans)
                    break

        # Update option switches
        if hasattr(self, 'auto_copy_switch'):
            self.auto_copy_switch.configure(text=_("Copy to clipboard"))
        if hasattr(self, 'auto_paste_switch'):
            self.auto_paste_switch.configure(text=_("Auto-paste"))

        # Update action buttons (only if not in recording state)
        if hasattr(self, 'record_button_transcribe') and hasattr(self, 'record_button_edit'):
            if not self.parent.audio_manager.recording:
                self.record_button_transcribe.configure(text=_("Record + Transcribe"))
                self.record_button_edit.configure(text=_("Record + AI Edit"))
            else:
                self.record_button_transcribe.configure(text=_("Stop and Process"))
                self.record_button_edit.configure(text=_("Stop and Process"))

        # Update banner labels
        if hasattr(self, 'hide_banner_link'):
            self.hide_banner_link.configure(text=_("Hide Banner"))
        if hasattr(self, 'powered_by_label'):
            self.powered_by_label.configure(text=_("Developed by Scorchsoft.com | App & AI Developers"))

    def apply_theme(self, is_dark: bool):
        """Apply the Sun Valley theme (dark or light mode).
        
        Args:
            is_dark: True for dark mode, False for light mode
        """
        theme_name = "dark" if is_dark else "light"
        sv_ttk.set_theme(theme_name)

        # Reapply custom ttk styles after theme change
        # (sv_ttk.set_theme resets style configurations)
        self._setup_styles()

        # Update title bar styling on Windows
        if is_dark:
            set_dark_title_bar(self.parent)
        else:
            # For light mode, we need to set the title bar to light
            self._set_light_title_bar(self.parent)
        
        # Update gradient buttons background color to match theme
        bg_color = "#1c1c1c" if is_dark else "#fafafa"
        if self.record_button_transcribe:
            self.record_button_transcribe.configure(bg=bg_color)
            self.record_button_transcribe.bg_color = bg_color
            self.record_button_transcribe._draw()
        if self.record_button_edit:
            self.record_button_edit.configure(bg=bg_color)
            self.record_button_edit.bg_color = bg_color
            self.record_button_edit._draw()
        
        # Update text widget colors based on theme
        if self.transcription_text:
            if is_dark:
                self.transcription_text.configure(
                    bg="#1c1c1c",
                    fg="#ffffff",
                    insertbackground="#ffffff",
                    highlightbackground="#404040",
                    highlightcolor="#505050"
                )
            else:
                self.transcription_text.configure(
                    bg="#ffffff",
                    fg="#1c1c1c",
                    insertbackground="#1c1c1c",
                    highlightbackground="#d0d0d0",
                    highlightcolor="#a0a0a0"
                )
        
        # Update navigation button colors for the new theme
        if hasattr(self, 'button_first_page') and self.button_first_page:
            self._update_nav_button_appearance()

        # Update powered by link color (light blue in dark mode, purple in light mode)
        if hasattr(self, 'powered_by_label') and self.powered_by_label:
            link_color = self.theme.ACCENT_PRIMARY if is_dark else self.theme.GRADIENT_END
            self.powered_by_label.configure(foreground=link_color)

        print(f"Theme applied: {theme_name}")
    
    def _set_light_title_bar(self, window):
        """Set Windows title bar to light mode."""
        if platform.system() != "Windows":
            return
        try:
            window.update()
            hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            value = ctypes.c_int(0)  # 0 for light mode
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(value), ctypes.sizeof(value)
            )
        except Exception as e:
            print(f"Could not set light title bar: {e}")