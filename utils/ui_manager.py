import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw
import platform
import ctypes
import time
import math
import sv_ttk

from utils.tooltip import ToolTip
from utils.app_logging import get_logger
from utils.config_manager import get_config, TRANSCRIPTION_MODELS, AI_MODELS
from utils.platform import open_url
from utils.i18n import _, _n
from utils.theme import (
    ThemeColors,
    LightThemeColors,
    theme_colors,
    set_theme_mode,
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

logger = get_logger(__name__)

# Gap after each clickable segment in the status line. Used both when packing
# them and when measuring whether they fit, so the two cannot disagree.
PICKER_PADX = 3


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

class _ThemeMeta(type):
    """Resolves colour names against whichever palette is currently active.

    Colour attributes are deliberately absent from the class body: Python only
    consults ``__getattr__`` when normal lookup fails, so defining them as class
    attributes would freeze them at import time and a theme switch would never
    reach the ~90 ``self.theme.COLOUR`` call sites.
    """

    def __getattr__(cls, name):
        try:
            return getattr(theme_colors(), name)
        except AttributeError:
            raise AttributeError(
                f"{cls.__name__} has no attribute {name!r}"
            ) from None


class ModernTheme(metaclass=_ThemeMeta):
    """Scorchsoft-branded theme with accessible typography.

    Colour attributes are proxied to the active palette (``ThemeColors`` in
    dark mode, ``LightThemeColors`` in light mode), so reading e.g.
    ``theme.TEXT_PRIMARY`` always reflects the current theme. New code should
    use the theme module directly:

        from utils.theme import theme_colors, get_font, get_spacing, get_radius
    """

    def __getattr__(self, name):
        # Instance lookups fall through to the metaclass proxy.
        return getattr(type(self), name)

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
        logger.warning("Could not set dark title bar: %s", e)


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
    
    def index(self, index_or_label):
        """Return an entry index by label or "end" (tk.Menu compatibility)."""
        if index_or_label in ("end", tk.END, "last"):
            return len(self.items) - 1 if self.items else None
        if isinstance(index_or_label, str):
            for i, item in enumerate(self.items):
                if item[1] == index_or_label:
                    return i
            return None
        return index_or_label

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
        
    def tk_popup(self, x, y, align_right=False):
        """Show the popup menu at the specified coordinates.

        With ``align_right`` the given x is treated as the menu's right edge
        rather than its left, which is what a control sitting at the right of
        a row wants - otherwise the menu hangs out past the window.
        """
        logger.debug("tk_popup called, menu=%s, is_open=%s, time_since_close=%.3f",
                     self._menu_name, self._is_open, time.time() - self._close_time)

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
            logger.debug("Skipping menu open - too soon after close (toggle)")
            return

        if self._is_open:
            logger.debug("Menu already open, closing")
            self._close()
            return  # Just close, don't reopen

        logger.debug("Opening popup menu %s", self._menu_name)
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
        
        # Theme-aware colors for the popup menu. self.theme proxies the active
        # palette, so the same names resolve correctly in either mode.
        border_color = self.theme.BORDER
        bg_color = self.theme.BG_SECONDARY
        hover_color = self.theme.BG_HOVER
        text_color = self.theme.TEXT_PRIMARY
        text_muted = self.theme.TEXT_MUTED

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

        if align_right:
            # Now that the width is known, hang the menu leftwards from x. The
            # screen clamping below still has the final say.
            x = x - popup_width
        
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
            logger.warning("Error getting screen dimensions: %s", e)
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
                logger.debug("Popup click, is_open=%s", self._is_open)
                if self.popup and self._is_open:
                    # Get click coordinates relative to screen
                    click_x = e.x_root
                    click_y = e.y_root
                    # Check if click is outside popup bounds
                    inside = (self._popup_x <= click_x <= self._popup_x + self._popup_width and
                              self._popup_y <= click_y <= self._popup_y + self._popup_height)
                    logger.debug("click=(%s,%s), popup=(%s,%s,%s,%s), inside=%s",
                                 click_x, click_y, self._popup_x, self._popup_y,
                                 self._popup_width, self._popup_height, inside)
                    if not inside:
                        logger.debug("Closing popup (click outside)")
                        self._close()
                        return "break"  # Consume the event

            # Use local grab to capture clicks
            try:
                self.popup.grab_set()
                logger.debug("Popup grab_set() succeeded")
            except Exception as e:
                logger.debug("Popup grab_set() failed: %s", e)

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
        logger.debug("Popup _close called, is_open=%s", self._is_open)
        # Clear the pending close timer reference
        self._pending_close_id = None

        if self.popup and self._is_open:
            self._is_open = False
            # Record close time for toggle detection
            self._close_time = time.time()
            logger.debug("Set popup _close_time to %s", self._close_time)

            # Release grab on Linux before destroying
            if platform.system() == "Linux":
                try:
                    self.popup.grab_release()
                    logger.debug("Popup grab_release() succeeded")
                except Exception as e:
                    logger.debug("Popup grab_release() failed: %s", e)

            try:
                self.popup.destroy()
                logger.debug("popup.destroy() succeeded")
            except Exception as e:
                logger.debug("popup.destroy() failed: %s", e)
            self.popup = None

            # On Linux, explicitly restore focus to main window after grab release
            # Without this, text inputs won't receive focus on click
            if platform.system() == "Linux":
                try:
                    root = self.parent.winfo_toplevel()
                    root.focus_force()
                    logger.debug("focus_force() on root succeeded")
                except Exception as e:
                    logger.debug("focus_force() failed: %s", e)

    def destroy(self):
        """Destroy the popup menu and clean up resources."""
        # Cancel any pending close timer
        if self._pending_close_id is not None:
            try:
                self.parent.after_cancel(self._pending_close_id)
            except:
                pass
            self._pending_close_id = None
        
        # Close the popup if open
        self._close()
        
        # Clear item references
        self.items.clear()


class GradientButton(tk.Canvas):
    """Custom button with gradient background (cyan -> blue -> purple like logo)."""

    # Caption colour for the shortcut line. A canvas cannot draw translucent
    # text, so this is a fixed near-white that reads as dimmed over the cyan,
    # purple and red fills alike.
    SUBTEXT_TINT = "#dfe6f2"

    def __init__(self, parent, text="", command=None, width=200, height=50,
                 corner_radius=25, font=None,
                 gradient_start="#06b6d4", gradient_mid="#3b82f6", gradient_end="#8b5cf6",
                 hover_start="#22d3ee", hover_mid="#60a5fa", hover_end="#a78bfa",
                 solid_color=None, solid_hover=None,
                 border_color="#6d9dc5", border_width=1,
                 text_color="#0d0d0d", bg_color="#0d0d0d",
                 subtext="", subtext_font=None, subtext_color=None, **kwargs):

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
        # Secondary line under the label (the keyboard shortcut). Smaller and
        # unbolded, and dimmed a little so it reads as a caption rather than
        # competing with the action itself.
        self.subtext = subtext
        self.subtext_font = subtext_font if subtext_font is not None else get_font('xxs')
        self.subtext_color = subtext_color or self.SUBTEXT_TINT
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
        
        # Draw the label, with the shortcut caption beneath it when there is
        # one. The pair is centred as a block so the button stays optically
        # balanced instead of the label simply shifting up.
        if self.subtext:
            main_size = self._font_pixel_size(self.font, 13)
            sub_size = self._font_pixel_size(self.subtext_font, 10)
            gap = max(2, sub_size // 3)
            block = main_size + gap + sub_size
            top = (self.height - block) // 2
            self.create_text(
                self.width // 2, top + main_size // 2,
                text=self.text, fill=self.text_color,
                font=self.font, anchor="center"
            )
            self.create_text(
                self.width // 2, top + main_size + gap + sub_size // 2,
                text=self.subtext, fill=self.subtext_color,
                font=self.subtext_font, anchor="center"
            )
        else:
            self.create_text(
                self.width // 2, self.height // 2,
                text=self.text, fill=self.text_color,
                font=self.font, anchor="center"
            )

    @staticmethod
    def _font_pixel_size(font, fallback):
        """Approximate line height for a theme font tuple."""
        try:
            size = abs(int(font[1]))
            return size if size else fallback
        except (TypeError, ValueError, IndexError):
            return fallback
    
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
        if 'subtext' in kwargs:
            self.subtext = kwargs.pop('subtext')
            redraw = True
        if 'subtext_color' in kwargs:
            self.subtext_color = kwargs.pop('subtext_color') or self.SUBTEXT_TINT
            redraw = True
        if 'subtext_font' in kwargs:
            self.subtext_font = kwargs.pop('subtext_font')
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
    # Sentinel shown when no input device is available. NOT translated: it is
    # also used as a value comparison in AudioManager.start_recording().
    NO_DEVICES_LABEL = "No audio devices found"

    # Number of blocks in the input level meter. Kept compact so the status
    # row still fits the status text and the model label on a narrow window.
    METER_SEGMENTS = 12

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
        self.device_refresh_link = None
        self.level_meter = None
        self.elapsed_label = None
        self.recording_readout = None
        self.button_rerun = None

        # Live recording readout state (QW-13b)
        self._level_after_id = None      # pending after() id for the poll loop
        self._level_monitoring = False
        self._meter_level = 0.0          # displayed level (0..1, smoothed)
        self._meter_peak = 0.0           # peak-hold marker (0..1)
        self._peak_hold_ticks = 0
        self._limit_state = None         # None | 'warning' | 'critical'
        self._readout_visible = True
        self._level_meter_enabled = True

        # Status pulse state (QW-18a)
        self._pulse_after_id = None
        self._pulse_active = False
        self._pulse_state = True
        self._pulse_color = None

        # Status line state and the processing elapsed counter
        self._status_state = "idle"
        self._status_msgid = None
        self._recording_hint = None
        self._picker_fonts = {}
        self._processing_since = None
        self._processing_base_message = None
        self._processing_after_id = None

        # Device list state (QW-07)
        self._has_audio_devices = False
        self._device_trace_registered = False
        self._suppress_device_trace = False

        # Re-run AI edit affordance (QW-08b)
        self._rerun_disabled = True

        # Status-line picker state (transcription model / AI model / prompt)
        self.status_row = None
        self.status_left = None
        self.status_pickers = None
        self._picker_transcription = None
        self._picker_ai = None
        self._picker_prompt = None
        self._picker_sep_1 = None
        self._picker_sep_2 = None
        self._picker_segments = ()
        self._picker_text = {}
        # (segments dropped, using short names) currently on screen, so a
        # resize that changes nothing does not re-pack the row.
        self._picker_layout = None
        self._prompt_tooltip = None
        self._model_fit_after_id = None
        self._status_min_width = 0
        # Fonts used only for measuring text width, cached per size key.
        self._measure_fonts = {}
        
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

        # Clickable status-line segments (model / prompt pickers). Same size as
        # the caption they replaced, so the row is not made noisier by becoming
        # interactive - the hand cursor and hover colour carry that.
        style.configure("Picker.TLabel",
            font=get_font('xxs'))

    def create_widgets(self):
        """Create UI with Sun Valley theme (ttk widgets)."""
        
        # Get dark mode setting from config
        config = get_config()
        is_dark = config.dark_mode

        # Select the palette before anything is styled or built, so every
        # widget paints in the right colours on its first render rather than
        # being created dark and corrected only when the theme is toggled.
        set_theme_mode(is_dark)

        # Apply title bar styling based on theme
        if is_dark:
            set_dark_title_bar(self.parent)
        else:
            self._set_light_title_bar(self.parent)

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
        
        device_header = ttk.Frame(content)
        device_header.pack(fill=tk.X, pady=(0, 10))

        self.device_label = ttk.Label(device_header, text=_("Input Device"), style="Section.TLabel")
        self.device_label.pack(side=tk.LEFT)

        # Small icon-link to re-scan devices without restarting (QW-07)
        self.device_refresh_link = ttk.Label(
            device_header, text=f"\u21bb  {_('Refresh')}",
            style="Copy.TLabel", cursor="hand2",
            foreground=self.theme.TEXT_SECONDARY
        )
        self.device_refresh_link.pack(side=tk.RIGHT, pady=(4, 0))
        self.device_refresh_link.bind("<Button-1>", lambda e: self.refresh_device_list(notify=True))
        ToolTip(self.device_refresh_link, _("Re-scan for input devices"))

        devices = self._enumerate_devices()
        self._has_audio_devices = bool(devices)

        if not devices:
            # No audio devices found - show warning but continue with UI
            # This allows the app to run for UI testing on systems without audio
            devices = {self.NO_DEVICES_LABEL: -1}
            self._set_device_selection(self.NO_DEVICES_LABEL)
            logger.warning("No input audio devices found. Recording will not work.")
        else:
            saved_device = get_config().selected_input_device
            if saved_device and saved_device in devices:
                self._set_device_selection(saved_device)
            else:
                self._set_device_selection(list(devices.keys())[0])

        # Registered exactly once; refreshes set the variable with the trace
        # suppressed so they never overwrite the saved device setting.
        if not self._device_trace_registered:
            self.parent.selected_device.trace_add("write", self._on_device_change)
            self._device_trace_registered = True

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

        # Separator, history, re-run and copy - with padding to align baselines
        separator_label = ttk.Label(nav_frame, text="|", style="Separator.TLabel", foreground=self.theme.TEXT_MUTED)
        separator_label.pack(side=tk.LEFT, padx=(get_spacing('sm'), nav_btn_pad), pady=(5, 0))

        # Stepping one entry at a time answers "what did I just say"; this
        # answers "what did I dictate about the invoice on Tuesday".
        self.button_history = ttk.Label(
            nav_frame, text=f"  {_('History')}", style="Copy.TLabel", cursor="hand2",
            foreground=self.theme.TEXT_SECONDARY)
        self.button_history.pack(side=tk.LEFT, pady=(8, 0))
        self.button_history.bind("<Button-1>", lambda e: self.parent.show_history())

        separator_label0 = ttk.Label(nav_frame, text="|", style="Separator.TLabel", foreground=self.theme.TEXT_MUTED)
        separator_label0.pack(side=tk.LEFT, padx=(get_spacing('sm'), nav_btn_pad), pady=(5, 0))

        # Re-run the AI edit against the text currently in the box (QW-08b)
        self.button_rerun = ttk.Label(
            nav_frame, text=f"  \u21ba {_('AI Edit')}", style="Copy.TLabel", cursor=""
        )
        self.button_rerun.pack(side=tk.LEFT, pady=(8, 0))
        self.button_rerun.bind("<Button-1>", lambda e: self._rerun_ai_edit())
        # Right-click applies a different prompt for this run only, so trying
        # three tones on one dictation does not change the selected prompt.
        self.button_rerun.bind("<Button-3>", lambda e: self.show_rerun_prompt_menu())

        separator_label2 = ttk.Label(nav_frame, text="|", style="Separator.TLabel", foreground=self.theme.TEXT_MUTED)
        separator_label2.pack(side=tk.LEFT, padx=(get_spacing('sm'), nav_btn_pad), pady=(5, 0))

        # Copy button - more top padding since smaller font (to ai: don't remove the space before "Copy")
        self.button_copy = ttk.Label(nav_frame, text=f"  {_('Copy')}", style="Copy.TLabel", cursor="hand2", foreground=self.theme.TEXT_SECONDARY)
        self.button_copy.pack(side=tk.LEFT, pady=(8, 0))
        self.button_copy.bind("<Button-1>", lambda e: self._copy_transcription())
        
        # Set initial disabled state (muted color)
        self.update_rerun_state()
        self._update_nav_button_appearance()
        
        ToolTip(self.button_first_page, _("Latest entry"))
        ToolTip(self.button_arrow_left, _("Newer"))
        ToolTip(self.button_arrow_right, _("Older"))
        ToolTip(self.button_history, _("Search everything you have dictated"))
        ToolTip(self.button_rerun,
                _("Re-run the AI edit on the text above (right-click for another prompt)"))
        ToolTip(self.button_copy, _("Copy to clipboard"))
        
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
            highlightbackground=self.theme.BORDER,
            highlightcolor=self.theme.BORDER_STRONG,
            padx=12,  # Internal horizontal padding
            pady=10,  # Internal vertical padding
            yscrollcommand=on_scroll_changed
        )
        self.transcription_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.transcription_text.bind("<Button-3>", self._show_text_context_menu)
        
        # Bind events that might change content to update scrollbar visibility
        self.transcription_text.bind("<KeyRelease>", lambda e: self.parent.after(10, self._on_text_changed))
        self.transcription_text.bind("<<Paste>>", lambda e: self.parent.after(10, self._on_text_changed))
        self.transcription_text.bind("<<Cut>>", lambda e: self.parent.after(10, self._on_text_changed))
        self.transcription_text.bind("<Configure>", lambda e: self.parent.after(10, update_scrollbar_visibility))
        
        # Connect scrollbar to text widget
        text_scrollbar.config(command=self.transcription_text.yview)

        # Word count and, where it is known, how long the recording behind this
        # text was. Cheap context that answers "did it get all of that?".
        self.text_stats_label = ttk.Label(
            content, text="", style="Small.TLabel", anchor="e",
            foreground=self.theme.TEXT_MUTED)
        self.text_stats_label.pack(fill=tk.X, pady=(0, get_spacing('sm')))
        self.update_text_stats()
        
        # ─────────────────────────────────────────────────────────────────────
        # STATUS ROW
        # ─────────────────────────────────────────────────────────────────────
        
        status_row = ttk.Frame(content)
        status_row.pack(fill=tk.X, pady=(0, 14))
        self.status_row = status_row
        
        # Grid (not pack) so a long model label gives way to the live readout
        # when the window is narrow, instead of clipping the meter and clock.
        status_row.columnconfigure(0, weight=0)
        status_row.columnconfigure(1, weight=1)

        status_left = ttk.Frame(status_row)
        status_left.grid(row=0, column=0, sticky="w")
        self.status_left = status_left
        
        self.status_dot = ttk.Label(status_left, text="●", font=get_font('status_dot'))
        self.status_dot.pack(side=tk.LEFT, padx=(0, 6))
        
        self.status_label = ttk.Label(status_left, text=_("Idle"), style="Status.TLabel")
        self.status_label.pack(side=tk.LEFT)

        # ── Live recording readout (QW-13b) ──────────────────────────────────
        # Always packed, so starting/stopping a recording never reflows the row.
        # At idle the meter shows an empty trough and the clock shows 0:00 in
        # muted text, which is exactly the "no audio is arriving" signal.
        self._level_meter_enabled = get_config().show_level_meter

        self.recording_readout = ttk.Frame(status_left)
        if self._level_meter_enabled:
            self.recording_readout.pack(side=tk.LEFT, padx=(get_spacing('sm'), 0))

        seg_w, gap, meter_h, meter_w = self._meter_metrics()
        self.level_meter = tk.Canvas(
            self.recording_readout,
            width=meter_w, height=meter_h,
            highlightthickness=0, bd=0, takefocus=0,
            bg=self._surface_color(is_dark)
        )
        self.level_meter.pack(side=tk.LEFT, pady=(2, 0))
        ToolTip(self.level_meter, _("Microphone input level"))

        # Fixed width so the clock ticking from 0:09 to 0:10 cannot shift layout
        self.elapsed_label = ttk.Label(
            status_left, text="0:00", style="Status.TLabel",
            width=5, anchor="w", foreground=self.theme.TEXT_MUTED
        )
        if self._level_meter_enabled:
            self.elapsed_label.pack(side=tk.LEFT, padx=(get_spacing('sm'), 0))

        self._draw_meter()
        self._set_readout_visible(False)

        # ── Model / prompt pickers ───────────────────────────────────────
        # What used to be a read-only caption. The prompt in particular is the
        # main thing that changes between dictations, and it was previously
        # only reachable by cycling blind through a shortcut.
        self.status_pickers = ttk.Frame(status_row)
        self.status_pickers.grid(row=0, column=1, sticky="e", padx=(get_spacing('sm'), 0))

        self._picker_transcription = ttk.Label(
            self.status_pickers, text="", style="Picker.TLabel", cursor="hand2")
        self._picker_sep_1 = ttk.Label(
            self.status_pickers, text="·", style="Small.TLabel",
            foreground=self.theme.TEXT_MUTED)
        self._picker_ai = ttk.Label(
            self.status_pickers, text="", style="Picker.TLabel", cursor="hand2")
        self._picker_sep_2 = ttk.Label(
            self.status_pickers, text="·", style="Small.TLabel",
            foreground=self.theme.TEXT_MUTED)
        self._picker_prompt = ttk.Label(
            self.status_pickers, text="", style="Picker.TLabel", cursor="hand2")

        # Ordered outermost-first: the segments that give way when the window
        # is narrow are the ones at the front of this list.
        self._picker_segments = (
            (self._picker_transcription, self._picker_sep_1),
            (self._picker_ai, self._picker_sep_2),
        )

        for widget in (self._picker_transcription, self._picker_sep_1, self._picker_ai,
                       self._picker_sep_2, self._picker_prompt):
            widget.pack(side=tk.LEFT, padx=(0, PICKER_PADX))

        self._bind_picker(self._picker_transcription, self._show_transcription_model_menu)
        self._bind_picker(self._picker_ai, self._show_ai_model_menu)
        self._bind_picker(self._picker_prompt, self._show_prompt_menu)

        ToolTip(self._picker_transcription, _("Click to change the transcription model"))
        ToolTip(self._picker_ai, _("Click to change the AI copy-editing model"))
        self._prompt_tooltip = ToolTip(self._picker_prompt, self._prompt_tooltip_text())

        self.update_model_label()
        self._reserve_status_width()
        status_row.bind("<Configure>", lambda e: self._schedule_model_label_fit())
        self._schedule_model_label_fit()
        
        # ─────────────────────────────────────────────────────────────────────
        # OPTIONS - Toggle switches (Sun Valley style)
        # ─────────────────────────────────────────────────────────────────────

        # Titling the group says what the two switches apply to, and stops the
        # box reading as an unexplained border.
        self.options_frame = options_frame = ttk.LabelFrame(
            content, text=_("After transcription"), padding=(16, 10))
        options_frame.pack(fill=tk.X, pady=(0, 12))

        # Center container for toggles
        switches_container = ttk.Frame(options_frame)
        switches_container.pack(expand=True)

        # Sun Valley provides "Switch.TCheckbutton" style for toggle switches.
        # "Auto-copy result" rather than "Copy to clipboard": the latter read
        # identically to the Copy link above and to the "Copied to clipboard"
        # toast, so three different things shared one set of words.
        self.auto_copy_switch = ttk.Checkbutton(
            switches_container,
            text=_("Auto-copy result"),
            variable=self.parent.auto_copy,
            style="Switch.TCheckbutton"
        )
        self.auto_copy_switch.pack(side=tk.LEFT, padx=(0, 32))
        ToolTip(self.auto_copy_switch,
                _("Put the finished text on the clipboard automatically"))

        self.auto_paste_switch = ttk.Checkbutton(
            switches_container,
            text=_("Auto-paste result"),
            variable=self.parent.auto_paste,
            style="Switch.TCheckbutton"
        )
        self.auto_paste_switch.pack(side=tk.LEFT)
        ToolTip(self.auto_paste_switch,
                _("Paste the finished text into whichever app you are using"))
        
        # ─────────────────────────────────────────────────────────────────────
        # ACTION BUTTONS (Keep custom gradient buttons)
        # ─────────────────────────────────────────────────────────────────────
        
        buttons_frame = ttk.Frame(content)
        buttons_frame.pack(fill=tk.X, pady=(0, 4))
        
        # Calculate button width (will be adjusted on resize)
        btn_width = 200  # Default, will resize
        
        # Use theme-appropriate background color for buttons
        btn_bg_color = self._surface_color(is_dark)
        
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
            text_color=self.theme.TEXT_ON_ACCENT,
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
            text_color=self.theme.TEXT_ON_ACCENT,
            bg_color=btn_bg_color,
            command=lambda: self.parent.toggle_recording("edit")
        )
        self.record_button_edit.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(btn_gap, 0))
        
        # The shortcuts are the product; the buttons are the training wheels.
        # Printing each shortcut on its button is what teaches the transition -
        # a tooltip only reaches someone who already hovered and waited.
        shortcut_transcribe = self._record_shortcut('record_transcribe')
        shortcut_edit = self._record_shortcut('record_edit')
        self.record_button_transcribe.configure(subtext=shortcut_transcribe)
        self.record_button_edit.configure(subtext=shortcut_edit)

        # Store references for update_button_shortcuts (set to None since we removed the labels)
        self.shortcut_label_left = None
        self.shortcut_label_right = None

        # Add tooltips to buttons
        self._tooltip_transcribe = ToolTip(
            self.record_button_transcribe,
            _("Record and transcribe audio ({shortcut})").format(shortcut=shortcut_transcribe))
        self._tooltip_edit = ToolTip(
            self.record_button_edit,
            _("Record and AI-edit transcription ({shortcut})").format(shortcut=shortcut_edit))
        
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
            logger.debug("Banner image height: %s, total banner_height: %s",
                         banner_img.height, self.banner_height)
            self.banner_photo = ImageTk.PhotoImage(banner_img)
            
            self.banner_label = ttk.Label(self.banner_frame, image=self.banner_photo, cursor="hand2")
            self.banner_label.pack(pady=(4, 6))
            self.banner_label.bind("<Button-1>", lambda e: self.open_scorchsoft())
        except Exception as e:
            logger.warning("Banner load error: %s", e)
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
    
    # ------------------------------------------------------------------
    # Status-line pickers (transcription model / AI model / prompt)
    # ------------------------------------------------------------------

    def _bind_picker(self, label, opener):
        """Make a status-line segment behave like a clickable control."""
        label.bind("<Button-1>", lambda e, fn=opener: fn())
        label.bind("<Enter>", lambda e, w=label: self._set_picker_hover(w, True), add="+")
        label.bind("<Leave>", lambda e, w=label: self._set_picker_hover(w, False), add="+")

    def _picker_font(self, underline):
        """The picker font, cached, with or without an underline."""
        key = 'picker_underline' if underline else 'picker'
        cached = self._picker_fonts.get(key)
        if cached is None:
            family, size = get_font('xxs')[:2]
            cached = tkfont.Font(family=family, size=size, underline=underline)
            self._picker_fonts[key] = cached
        return cached

    def _set_picker_hover(self, label, hovering):
        """Colour and underline a picker segment on hover.

        These segments name the transcription model, the edit model and the
        prompt, and every one of them is a menu - but nothing said so. The
        underline is what says "this is a control", added to the colour shift
        that was already here. It is deliberately a hover-only cue: at rest the
        row stays a quiet caption rather than becoming a line of links.
        """
        if not self._widget_alive(label):
            return
        colour = self.theme.ACCENT_PRIMARY if hovering else self.theme.TEXT_TERTIARY
        try:
            label.configure(foreground=colour, font=self._picker_font(hovering))
        except tk.TclError:
            label.configure(foreground=colour)

    def _refresh_picker_colours(self):
        for label in (self._picker_transcription, self._picker_ai, self._picker_prompt):
            self._set_picker_hover(label, False)

    def _prompt_tooltip_text(self):
        """Tooltip for the prompt segment, naming the cycle shortcut."""
        shortcuts = getattr(self.parent, 'shortcuts', {}) or {}
        back = self._format_accelerator(shortcuts.get('cycle_prompt_back'))
        forward = self._format_accelerator(shortcuts.get('cycle_prompt_forward'))
        if back and forward:
            return _("Click to change the prompt ({back} / {forward} to cycle)").format(
                back=back, forward=forward)
        return _("Click to change the prompt")

    @staticmethod
    def _format_accelerator(combo):
        """Render 'ctrl+alt+j' the way a menu would: 'Ctrl+Alt+J'."""
        if not combo:
            return ""
        pretty = {'ctrl': 'Ctrl', 'control': 'Ctrl', 'alt': 'Alt', 'shift': 'Shift',
                  'cmd': 'Cmd', 'command': 'Cmd', 'super': 'Super', 'win': 'Win'}
        parts = []
        for part in str(combo).split('+'):
            part = part.strip()
            if not part:
                continue
            parts.append(pretty.get(part.lower(), part.upper() if len(part) == 1 else part.title()))
        return "+".join(parts)

    def update_model_label(self):
        # Defensive: this runs while the widgets are being built, before every
        # attribute on the app has necessarily been assigned.
        prompt_name = str(getattr(self.parent, 'current_prompt_name', None) or "Default")
        lang = "Auto" if self.parent.whisper_language == "auto" else self.parent.whisper_language.upper()
        model_type = "GPT" if self.parent.transcription_model_type == "gpt" else "Whisper"

        # Long and short forms per segment; the short form is used once the
        # window is too narrow for everything.
        self._picker_text = {
            self._picker_transcription: (
                f"{self.parent.transcription_model} ({model_type}, {lang})",
                str(self.parent.transcription_model),
            ),
            self._picker_ai: (str(self.parent.ai_model), str(self.parent.ai_model)),
            self._picker_prompt: (prompt_name, prompt_name),
        }
        for label, (long_form, _short) in self._picker_text.items():
            if self._widget_alive(label):
                label.configure(text=long_form)

        if self._widget_alive(self._picker_prompt) and self._prompt_tooltip is not None:
            self._prompt_tooltip.set_text(self._prompt_tooltip_text())

        # The label text has just been overwritten with the long form, so the
        # cached layout must be re-applied rather than skipped as unchanged.
        self._picker_layout = None
        self._refresh_picker_colours()
        self._schedule_model_label_fit()

    def _picker_menu(self, name):
        """A popup menu themed like the main menu bar."""
        return StyledPopupMenu(self.parent, theme=self.theme, menu_name=name)

    def _popup_under(self, menu, widget):
        """Drop a menu just below a status-line segment.

        The segments sit at the right of the row, so the menu is hung from
        their right edge - opening leftwards keeps it over the window instead
        of trailing off the side of it.
        """
        try:
            right_edge = widget.winfo_rootx() + widget.winfo_width()
            y = widget.winfo_rooty() + widget.winfo_height() + 4
            menu.tk_popup(right_edge, y, align_right=True)
        except Exception as e:
            logger.warning("Could not open picker menu: %s", e)

    def _show_prompt_menu(self):
        """Pick the copy-editing prompt straight from the status line."""
        menu = self._picker_menu("prompt_picker")
        current = self.parent.current_prompt_name
        names = self.parent.prompt_names()

        # Hint the cycle shortcuts against the prompts either side of the
        # current one, so the keys are discoverable from the menu itself.
        shortcuts = getattr(self.parent, 'shortcuts', {}) or {}
        accelerators = {}
        if current in names and len(names) > 1:
            position = names.index(current)
            accelerators[names[(position - 1) % len(names)]] = \
                self._format_accelerator(shortcuts.get('cycle_prompt_back'))
            accelerators[names[(position + 1) % len(names)]] = \
                self._format_accelerator(shortcuts.get('cycle_prompt_forward'))

        for name in names:
            menu.add_command(
                label=self._picker_item_label(name, name == current),
                command=lambda n=name: self.parent.select_prompt(n),
                accelerator="" if name == current else accelerators.get(name, ""))

        menu.add_separator()
        menu.add_command(label=_("Manage Prompts..."), command=self.parent.manage_prompts)
        self._popup_under(menu, self._picker_prompt)

    @staticmethod
    def _picker_item_label(name, selected):
        """Mark the active entry so the menu shows what is currently in use."""
        return f"● {name}" if selected else f"     {name}"

    def show_rerun_prompt_menu(self, anchor=None):
        """Offer a one-off prompt to re-run the current text through."""
        if self._rerun_disabled:
            return
        menu = self._picker_menu("rerun_prompt")
        current = self.parent.current_prompt_name
        for name in self.parent.prompt_names():
            menu.add_command(
                label=self._picker_item_label(name, name == current),
                command=lambda n=name: self.parent.rerun_ai_edit(prompt_name=n))
        self._popup_under(menu, anchor or self.button_rerun)

    def _show_transcription_model_menu(self):
        menu = self._picker_menu("transcription_picker")
        current = self.parent.transcription_model
        for model, model_type in TRANSCRIPTION_MODELS.items():
            menu.add_command(
                label=self._picker_item_label(model, model == current),
                command=lambda m=model, t=model_type: self.parent.select_transcription_model(m, t))
        if current not in TRANSCRIPTION_MODELS:
            # A custom model set in the configuration dialog still has to show
            # as the current selection, but is not re-selectable from here.
            menu.add_separator()
            menu.add_command(label=self._picker_item_label(current, True),
                             command=self.parent.open_config)
        menu.add_separator()
        menu.add_command(label=_("More Model Settings..."), command=self.parent.open_config)
        self._popup_under(menu, self._picker_transcription)

    def _show_ai_model_menu(self):
        menu = self._picker_menu("ai_picker")
        current = self.parent.ai_model
        for model in AI_MODELS:
            menu.add_command(label=self._picker_item_label(model, model == current),
                             command=lambda m=model: self.parent.select_ai_model(m))
        if current not in AI_MODELS:
            menu.add_separator()
            menu.add_command(label=self._picker_item_label(current, True),
                             command=self.parent.open_config)
        menu.add_separator()
        menu.add_command(label=_("More Model Settings..."), command=self.parent.open_config)
        self._popup_under(menu, self._picker_ai)

    def _reserve_status_width(self):
        """Reserve room for the longest status message plus the live readout.

        Without this the row reflows when the status text grows ("Idle" ->
        "Recording...") and the meter is briefly clipped out of the row.
        """
        if not self._widget_alive(self.status_row):
            return
        font = self._measuring_font('xs')
        if font is None:
            return
        try:
            # The meter and clock are only on screen while recording, and the
            # statuses shown then are the recording ones - every longer message
            # ("Processing...", "Error during transcription") appears with the
            # readout already hidden. Reserving for both maxima at once cost
            # around 110px that the two can never actually need together, and
            # that space is what the model and prompt pickers live in.
            #
            # The reservation is recomputed when recording starts and stops
            # rather than being sized for the worst case of either: the
            # recording hint is much wider than "Idle", and holding room for it
            # while idle would permanently squeeze the pickers.
            recording_text = max(font.measure(text) for text in (
                _("Recording..."),
                self._cancel_hint_text(),
            ))
            idle_text = max(font.measure(text) for text in (
                _("Idle"),
                _("Processing - Audio File..."),
                _("Processing - Transcript..."),
                _("Processing - AI Editing..."),
                _("Retrying transcription..."),
                _("Error during transcription"),
                _("Clipboard unavailable"),
            ))
            elapsed_width = font.measure("00:00")
        except Exception:
            logger.debug("Could not measure status fonts", exc_info=True)
            return

        _seg_w, _gap, _height, meter_width = self._meter_metrics()
        dot_width = get_font_size('status_dot') + get_spacing('sm')
        readout = (meter_width + elapsed_width + get_spacing('sm') * 2) if self._level_meter_enabled else 0
        if self._status_state == "recording":
            widest = max(recording_text + readout, idle_text)
        else:
            widest = idle_text
        self._status_min_width = dot_width + widest + get_spacing('md')
        self.status_row.columnconfigure(0, minsize=self._status_min_width)

    def _cancel_shortcut(self):
        """Display form of the global cancel shortcut."""
        default = "Cmd+X" if getattr(self.parent, 'is_mac', False) else "Ctrl+Alt+X"
        try:
            return self.parent.hotkey_manager.display_shortcut(
                'cancel_recording', default)
        except Exception:
            return default

    def _cancel_hint_text(self):
        """Recording status naming the way out.

        Cancel previously existed only as an unlabelled global shortcut, so a
        user who started a bad take had no visible way to discard it. The
        global shortcut is named rather than Escape: Escape only reaches us
        while the window has focus, and during dictation it usually does not.
        """
        return _("Recording - {shortcut} to cancel").format(
            shortcut=self._cancel_shortcut())

    def _measuring_font(self, size_key):
        """A cached tkfont for measuring text, or None if fonts are unavailable.

        These are used from resize handlers, so building a fresh Tk font object
        every time would churn named Tcl fonts on every frame of a window drag.
        The cache is cleared whenever the theme or language changes the fonts.
        """
        cached = self._measure_fonts.get(size_key)
        if cached is not None:
            return cached
        try:
            font = tkfont.Font(font=get_font(size_key))
        except Exception:
            logger.debug("Could not build a measuring font for %s", size_key, exc_info=True)
            return None
        self._measure_fonts[size_key] = font
        return font

    def _clear_measuring_fonts(self):
        """Drop the cached fonts after a theme or language change."""
        self._measure_fonts.clear()
        self._picker_fonts.clear()

    def _schedule_model_label_fit(self):
        """Debounced re-fit of the model label (also on resize)."""
        if self._model_fit_after_id is not None:
            self._cancel_after(self._model_fit_after_id)
        self._model_fit_after_id = self._after(60, self._fit_model_label)

    def _fit_model_label(self):
        """Fit the pickers into the status row without squeezing the readout.

        The status row is narrow; the recording level meter and clock are the
        part that must stay readable, so the model information gives way first.
        Segments are dropped whole rather than truncated mid-word - a picker
        showing "gpt-4o-min..." is not something anyone can click with
        confidence. The prompt is never dropped: it is the segment people
        actually change.
        """
        self._model_fit_after_id = None
        if not self._widget_alive(self.status_pickers) or not self._widget_alive(self.status_row):
            return

        row_width = self.status_row.winfo_width()
        if row_width <= 1:
            # Not laid out yet - try again shortly.
            self._model_fit_after_id = self._after(200, self._fit_model_label)
            return

        left_width = self.status_left.winfo_reqwidth() if self._widget_alive(self.status_left) else 0
        left_width = max(left_width, self._status_min_width)
        available = max(row_width - left_width - get_spacing('md'), 40)

        font = self._measuring_font('xxs')
        if font is None:
            return

        def width_of(text):
            # Matches the padx used when the segments are packed.
            return font.measure(text) + PICKER_PADX

        prompt_long, _prompt_short = self._picker_text.get(self._picker_prompt, ("", ""))
        separator_width = width_of("·")

        # Prefer keeping a segment in a shorter form over dropping it, so a
        # moderately narrow window loses "(GPT, Auto)" rather than losing the
        # transcription model entirely. Only when neither form fits is the
        # segment dropped.
        for drop in range(len(self._picker_segments) + 1):
            for use_short in (False, True):
                total = width_of(prompt_long)
                for index, (label, _sep) in enumerate(self._picker_segments):
                    if index < drop:
                        continue
                    long_form, short_form = self._picker_text.get(label, ("", ""))
                    total += width_of(short_form if use_short else long_form) + separator_width
                if total <= available:
                    self._apply_picker_layout(drop, use_short)
                    return

        # Nothing fits: show the prompt on its own.
        self._apply_picker_layout(len(self._picker_segments), True)

    def _apply_picker_layout(self, drop_count, use_short):
        """Show the segments that fit, hiding the rest along with separators.

        Everything is unpacked and re-packed in order, because packing a
        previously hidden segment would otherwise put it at the end of the row.
        """
        layout = (drop_count, use_short)
        if layout == self._picker_layout:
            return
        self._picker_layout = layout

        ordered = []
        for index, (label, separator) in enumerate(self._picker_segments):
            if index >= drop_count:
                long_form, short_form = self._picker_text.get(label, ("", ""))
                if self._widget_alive(label):
                    label.configure(text=short_form if use_short else long_form)
                ordered.extend((label, separator))
        ordered.append(self._picker_prompt)

        for widget in self._all_picker_widgets():
            if self._widget_alive(widget):
                widget.pack_forget()
        for widget in ordered:
            if self._widget_alive(widget):
                widget.pack(side=tk.LEFT, padx=(0, PICKER_PADX))

    def _all_picker_widgets(self):
        widgets = []
        for label, separator in self._picker_segments:
            widgets.extend((label, separator))
        widgets.append(self._picker_prompt)
        return widgets
        
    def _update_nav_button_appearance(self):
        """Update navigation button colors based on disabled state and theme."""
        enabled_color = self.theme.TEXT_SECONDARY
        disabled_color = self.theme.TEXT_MUTED
        copy_color = self.theme.TEXT_SECONDARY

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

        # Re-run AI edit link mirrors the nav arrows' enabled/disabled styling
        if self._widget_alive(self.button_rerun):
            self.button_rerun.configure(
                foreground=disabled_color if self._rerun_disabled else copy_color,
                cursor="" if self._rerun_disabled else "hand2"
            )

        # Device refresh link is always actionable
        if self._widget_alive(self.device_refresh_link):
            self.device_refresh_link.configure(foreground=copy_color)
    
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
            self.transcription_text.insert("1.0", self.parent.history_text(self.parent.history_index))
            # Update scrollbar visibility after content change
            self._after(10, self._update_scrollbar_visibility)
        self.update_rerun_state()
        self.update_text_stats()

    def update_text_stats(self):
        """Refresh the word count / spoken length caption under the transcript."""
        if not self._widget_alive(getattr(self, 'text_stats_label', None)):
            return
        try:
            text = self.transcription_text.get("1.0", "end-1c")
        except Exception:
            return

        words = len(text.split())
        if not words:
            self.text_stats_label.configure(text="")
            return

        parts = [_n("{n} word", "{n} words", words).format(n=words)]

        # Only the entry currently being shown can be labelled with a length -
        # once the text has been edited by hand it no longer describes the
        # recording, so the length is dropped rather than made misleading.
        entry = self.parent.history_entry(self.parent.history_index)
        if entry and entry.get("duration") and entry.get("text") == text:
            parts.append(self._format_duration(entry["duration"]))

        self.text_stats_label.configure(text="  ·  ".join(parts))

    @staticmethod
    def _format_duration(seconds):
        """Render a spoken length as m:ss."""
        total = int(round(float(seconds)))
        return f"{total // 60}:{total % 60:02d}"
            

    # ═════════════════════════════════════════════════════════════════════════
    # SMALL HELPERS
    # ═════════════════════════════════════════════════════════════════════════

    def _widget_alive(self, widget):
        """True if the widget still exists (False during/after shutdown)."""
        if widget is None:
            return False
        try:
            return bool(widget.winfo_exists())
        except Exception:
            return False

    def _after(self, delay, callback):
        """Schedule a callback, returning None if the window has gone away."""
        if not self._widget_alive(self.parent):
            return None
        try:
            return self.parent.after(delay, callback)
        except Exception:
            return None

    def _cancel_after(self, after_id):
        """Cancel a pending after() callback, ignoring an already-fired id."""
        if after_id is None:
            return
        try:
            self.parent.after_cancel(after_id)
        except Exception:
            pass

    def _surface_color(self, is_dark=None):
        """Background colour matching the themed window surface."""
        if is_dark is None:
            is_dark = get_config().dark_mode
        colors = ThemeColors if is_dark else LightThemeColors
        return colors.BG_TERTIARY if is_dark else colors.BG_PRIMARY

    # ═════════════════════════════════════════════════════════════════════════
    # INPUT LEVEL METER + ELAPSED TIMER (QW-13b)
    # ═════════════════════════════════════════════════════════════════════════

    def _meter_metrics(self):
        """Segment width, gap, height and total width for the level meter."""
        unit = max(2, get_spacing('xs'))
        seg_w = unit
        gap = max(1, unit // 2)
        height = get_font_size('status_dot')
        width = self.METER_SEGMENTS * (seg_w + gap) - gap
        return seg_w, gap, height, width

    def _meter_colors(self, is_dark=None):
        """(off, green, amber, red) segment colours for the current theme."""
        if is_dark is None:
            is_dark = get_config().dark_mode
        if is_dark:
            return "#4a4a4a", "#3fb950", "#e3b341", "#f85149"
        return "#a9b0b8", "#177e3a", "#a86800", "#c5202c"

    @staticmethod
    def _level_to_fraction(level):
        """Map a 0..1 input level onto the meter's 0..1 fill fraction.

        AudioManager already applies a dB curve (a -60 dBFS floor), so this
        only adds a mild gamma: enough that quiet speech visibly moves the
        meter, without a second compression that would peg it near full.
        """
        if level <= 0.0:
            return 0.0
        return max(0.0, min(1.0, math.pow(min(level, 1.0), 0.75)))

    def _draw_meter(self):
        """Repaint the segmented meter from the current smoothed level."""
        if not self._widget_alive(self.level_meter):
            return
        seg_w, gap, height, width = self._meter_metrics()
        off, green, amber, red = self._meter_colors()

        # If a narrow window squeezed the canvas, scale the blocks to whatever
        # width we actually have rather than drawing off the right-hand edge.
        actual_width = self.level_meter.winfo_width()
        if 1 < actual_width < width:
            unit = actual_width / float(self.METER_SEGMENTS)
            gap = max(1.0, unit * 0.3)
            seg_w = max(1.0, unit - gap)

        self.level_meter.delete("all")
        lit = self._meter_level * self.METER_SEGMENTS
        peak_index = -1
        if self._meter_peak > 0.0:
            peak_index = min(self.METER_SEGMENTS - 1,
                             int(self._meter_peak * self.METER_SEGMENTS))

        for i in range(self.METER_SEGMENTS):
            position = (i + 0.5) / self.METER_SEGMENTS
            if position < 0.65:
                on_color = green
            elif position < 0.85:
                on_color = amber
            else:
                on_color = red
            # A limit warning tints the whole bar so it reads at a glance
            if self._limit_state == 'critical':
                on_color = red
            elif self._limit_state == 'warning':
                on_color = amber

            if i < lit or i == peak_index:
                color = on_color
            else:
                color = off

            x0 = i * (seg_w + gap)
            self.level_meter.create_rectangle(
                x0, 1, x0 + seg_w, height - 1,
                fill=color, outline=""
            )

    def set_level(self, value):
        """Render a 0.0-1.0 input level (fast attack, slow decay, peak hold)."""
        try:
            level = float(value)
        except (TypeError, ValueError):
            level = 0.0
        level = max(0.0, min(1.0, level))

        target = self._level_to_fraction(level)
        if target >= self._meter_level:
            self._meter_level = target                       # instant attack
        else:
            self._meter_level += (target - self._meter_level) * 0.35  # decay

        if self._meter_level > self._meter_peak:
            self._meter_peak = self._meter_level
            self._peak_hold_ticks = 8                        # ~0.8s hold
        elif self._peak_hold_ticks > 0:
            self._peak_hold_ticks -= 1
        else:
            self._meter_peak = max(self._meter_level, self._meter_peak - 0.03)

        self._draw_meter()

    def set_elapsed(self, seconds):
        """Render elapsed recording time as M:SS, amber/red near the limit."""
        if not self._widget_alive(self.elapsed_label):
            return
        try:
            total = max(0.0, float(seconds))
        except (TypeError, ValueError):
            total = 0.0
        minutes, secs = divmod(int(total), 60)

        state = self._limit_state
        if state is None:
            state = self._limit_state_from_elapsed(total)
            self._limit_state = state

        if state == 'critical':
            color = self.theme.RECORDING_TEXT
        elif state == 'warning':
            color = self.theme.STATUS_PROCESSING
        elif self._level_monitoring:
            color = self.theme.TEXT_TERTIARY
        else:
            color = self.theme.TEXT_MUTED

        self.elapsed_label.configure(text=f"{minutes}:{secs:02d}", foreground=color)
        self._update_recording_hint(state)

    def _update_recording_hint(self, limit_state):
        """Swap the cancel hint for a limit warning as the ceiling approaches.

        The clock turning amber was previously the only sign that recording was
        about to stop by itself, which says nothing to a user who is not
        looking at it or does not know a limit exists.
        """
        if self._status_state != "recording":
            return
        wanted = "limit" if limit_state in ("warning", "critical") else "cancel"
        if wanted == self._recording_hint:
            return
        self._recording_hint = wanted

        if wanted == "limit":
            try:
                max_minutes = int(getattr(get_config(), 'max_recording_minutes', 0) or 0)
            except Exception:
                max_minutes = 0
            text = _("Recording - stops at {minutes}:00").format(minutes=max_minutes)
        else:
            text = self._cancel_hint_text()

        if self._widget_alive(self.status_label):
            self.status_label.configure(text=text)
            self._schedule_model_label_fit()

    def _limit_state_from_elapsed(self, seconds):
        """Derive a limit-warning state from the configured maximum length."""
        if not self._level_monitoring:
            return None
        try:
            max_minutes = int(getattr(get_config(), 'max_recording_minutes', 0) or 0)
        except Exception:
            max_minutes = 0
        if max_minutes <= 0:
            return None
        limit = max_minutes * 60.0
        if seconds >= limit * 0.95:
            return 'critical'
        if seconds >= limit * 0.8:
            return 'warning'
        return None

    def _read_limit_state(self, audio_manager):
        """Read an optional limit-warning flag from the audio manager.

        Agent A may expose this; read defensively so we work without it.
        """
        for name in ('limit_state', 'limit_warning_active', 'limit_warning',
                     'approaching_limit'):
            value = getattr(audio_manager, name, None)
            if callable(value):
                try:
                    value = value()
                except Exception:
                    value = None
            if isinstance(value, str):
                value = value.lower()
                if value in ('warning', 'critical'):
                    return value
                continue
            if value:
                return 'warning'
        return None

    def _set_readout_visible(self, visible):
        """Show or hide the meter and clock.

        The status column has a reserved minimum width, so showing or hiding
        the readout never reflows the row.
        """
        if not self._level_meter_enabled:
            visible = False
        if visible == self._readout_visible:
            return
        self._readout_visible = visible
        for widget in (self.recording_readout, self.elapsed_label):
            if not self._widget_alive(widget):
                continue
            if visible:
                widget.pack(side=tk.LEFT, padx=(get_spacing('sm'), 0))
            else:
                widget.pack_forget()

    def apply_level_meter_setting(self, enabled):
        """Turn the live level readout on or off without a restart."""
        enabled = bool(enabled)
        if enabled == self._level_meter_enabled:
            return
        self._level_meter_enabled = enabled
        if not enabled:
            self.stop_level_monitor()
            self._set_readout_visible(False)
        elif getattr(getattr(self.parent, 'audio_manager', None), 'recording', False):
            # Switched on mid-recording: start showing it straight away.
            self.start_level_monitor()

    def start_level_monitor(self):
        """Begin polling the audio manager for level and elapsed time."""
        if not self._level_meter_enabled or not self._widget_alive(self.level_meter):
            return
        self._cancel_after(self._level_after_id)
        self._level_after_id = None
        self._level_monitoring = True
        self._meter_level = 0.0
        self._meter_peak = 0.0
        self._peak_hold_ticks = 0
        self._limit_state = None
        self._set_readout_visible(True)
        self.set_elapsed(0.0)
        self._draw_meter()
        self._poll_level()

    def stop_level_monitor(self):
        """Stop polling and reset the readout to its idle state."""
        self._level_monitoring = False
        self._cancel_after(self._level_after_id)
        self._level_after_id = None
        self._meter_level = 0.0
        self._meter_peak = 0.0
        self._peak_hold_ticks = 0
        self._limit_state = None
        self._draw_meter()
        self.set_elapsed(0.0)
        self._set_readout_visible(False)

    def _poll_level(self):
        """Poll the audio manager every 100ms (polling, never callbacks)."""
        self._level_after_id = None
        if not self._level_monitoring or not self._widget_alive(self.level_meter):
            return

        level = 0.0
        elapsed = 0.0
        audio_manager = getattr(self.parent, 'audio_manager', None)
        if audio_manager is not None:
            try:
                level = float(getattr(audio_manager, 'current_level', 0.0) or 0.0)
            except (TypeError, ValueError):
                level = 0.0
            getter = getattr(audio_manager, 'get_elapsed_seconds', None)
            if callable(getter):
                try:
                    elapsed = float(getter() or 0.0)
                except Exception:
                    elapsed = 0.0
            self._limit_state = self._read_limit_state(audio_manager)

        self.set_level(level)
        self.set_elapsed(elapsed)

        self._level_after_id = self._after(100, self._poll_level)

    # ═════════════════════════════════════════════════════════════════════════
    # INPUT DEVICES (QW-07)
    # ═════════════════════════════════════════════════════════════════════════

    def _enumerate_devices(self):
        """Return {name: index} of input devices, or {} if enumeration fails."""
        try:
            return self.parent.audio_manager.get_input_devices() or {}
        except Exception:
            logger.error("Failed to enumerate input devices", exc_info=True)
            return {}

    def _set_device_selection(self, name):
        """Set the selected-device variable without persisting it."""
        self._suppress_device_trace = True
        try:
            self.parent.selected_device.set(name)
        finally:
            self._suppress_device_trace = False

    def _on_device_change(self, *args):
        """Persist the device the user picked from the dropdown."""
        if self._suppress_device_trace:
            return
        name = self.parent.selected_device.get()
        if not name or name == self.NO_DEVICES_LABEL:
            return
        try:
            config = get_config()
            config.selected_input_device = name
            config.save_settings()
        except Exception:
            logger.error("Failed to save selected input device", exc_info=True)

    def refresh_device_list(self, notify=False):
        """Re-enumerate input devices and repopulate the combobox.

        Keeps the current selection when the device is still present. Never
        writes to the saved setting: a device that disappeared temporarily
        should still be restored when it comes back.
        """
        if not self._widget_alive(self.device_combo):
            return False

        devices = self._enumerate_devices()
        current = self.parent.selected_device.get()

        if not devices:
            self._has_audio_devices = False
            self.device_combo.configure(
                values=[self.NO_DEVICES_LABEL], state="disabled"
            )
            self._set_device_selection(self.NO_DEVICES_LABEL)
            logger.warning("Device refresh found no input devices")
            if notify:
                self._show_toast(_("No input devices found"),
                                 anchor=self.device_refresh_link)
            return False

        self._has_audio_devices = True
        names = list(devices.keys())
        # Re-enable the combobox if we were previously in the no-device state
        self.device_combo.configure(values=names, state="readonly")

        if current in devices:
            target = current
        else:
            saved = get_config().selected_input_device
            target = saved if saved in devices else names[0]
        if target != current:
            self._set_device_selection(target)

        logger.info("Device refresh found %d input device(s); selection=%s",
                    len(names), self.parent.selected_device.get())
        if notify:
            self._show_toast(
                _n("{n} input device", "{n} input devices", len(names)).format(n=len(names)),
                anchor=self.device_refresh_link
            )
        return True

    # ═════════════════════════════════════════════════════════════════════════
    # RE-RUN AI EDIT (QW-08b)
    # ═════════════════════════════════════════════════════════════════════════

    def _on_text_changed(self):
        """React to manual edits in the transcription box."""
        if callable(getattr(self, '_update_scrollbar_visibility', None)):
            self._update_scrollbar_visibility()
        self.update_rerun_state()
        self.update_text_stats()

    def update_rerun_state(self):
        """Enable the re-run link only when there is text to re-edit."""
        if not self._widget_alive(self.button_rerun):
            return
        has_text = False
        if self._widget_alive(self.transcription_text):
            has_text = bool(self.transcription_text.get("1.0", "end-1c").strip())
        available = hasattr(self.parent, 'rerun_ai_edit')
        self._rerun_disabled = not (has_text and available)
        self._update_nav_button_appearance()

    def _rerun_ai_edit(self):
        """Ask the app to re-run the AI edit on the current text."""
        if self._rerun_disabled:
            return
        handler = getattr(self.parent, 'rerun_ai_edit', None)
        if not callable(handler):
            logger.warning("rerun_ai_edit is not available on the parent")
            return
        try:
            handler()
        except Exception:
            logger.error("Re-run AI edit failed", exc_info=True)

    # Semantic status states. Callers name what is happening rather than a
    # colour, so "in progress" cannot drift back to the success colour: green
    # has to keep meaning finished, or the status line answers nothing at the
    # one moment the user is waiting on it.
    _STATUS_STATES = {
        "idle": ("STATUS_IDLE", "TEXT_TERTIARY"),
        "processing": ("STATUS_PROCESSING", "STATUS_PROCESSING"),
        # Same amber as processing, but a standing condition rather than work
        # in flight, so it must not pulse or run an elapsed counter.
        "warning": ("STATUS_PROCESSING", "STATUS_PROCESSING"),
        "success": ("STATUS_SUCCESS", "STATUS_SUCCESS"),
        "recording": ("STATUS_RECORDING", "RECORDING_TEXT"),
        "error": ("RECORDING_TEXT", "RECORDING_TEXT"),
    }

    # Colour names accepted by older call sites. Amber maps to the non-pulsing
    # warning state: a caller that only knew about colours cannot have meant
    # "work is in progress".
    _LEGACY_STATUS_STATES = {
        "blue": "idle",
        "green": "success",
        "red": "error",
        "orange": "warning",
    }

    # Every fixed status message the app can show, as its untranslated msgid.
    # set_status is handed text that has already been through _(), so it maps
    # that back to the msgid here; a later language change then re-translates
    # from the msgid instead of trying to match the displayed text against
    # English, which never worked when switching between two other languages.
    STATUS_MSGIDS = (
        "Idle",
        "Stopped",
        "Recording...",
        "Processing - Audio File...",
        "Processing - Transcript...",
        "Processing - AI Editing...",
        "Retrying transcription...",
        "No speech detected",
        "Error during transcription",
        "AI edit failed",
        "AI edit returned no text",
        "Clipboard unavailable",
        "System tray unavailable",
        "Success",
        "Error",
    )

    def _remember_status_msgid(self, message):
        """Record which known status this text is, for later re-translation."""
        for msgid in self.STATUS_MSGIDS:
            if message == msgid or message == _(msgid):
                self._status_msgid = msgid
                return
        # A one-off or parameterised message (the completion receipt); it is
        # short-lived, so leaving it untranslated on a language switch is fine.
        self._status_msgid = None

    def set_status(self, message, state="idle", pulsing=None):
        """Update the status line.

        Args:
            message: Text to show.
            state: One of ``idle``, ``processing``, ``success``, ``recording``
                or ``error``. Legacy colour names are still accepted.
            pulsing: Force the dot to pulse. Defaults to pulsing whenever the
                state is ``recording`` or ``processing``.
        """
        state = self._LEGACY_STATUS_STATES.get(state, state)
        dot_attr, text_attr = self._STATUS_STATES.get(
            state, self._STATUS_STATES["idle"]
        )
        dot_color = getattr(self.theme, dot_attr)
        text_color = getattr(self.theme, text_attr)

        # Decide whether the dot should pulse from explicit state, never from
        # the message text - that comparison fails in every non-English locale
        # (QW-18a).
        if pulsing is None:
            pulsing = state in ("recording", "processing")

        previous_state = self._status_state
        self._status_state = state
        self._remember_status_msgid(message)

        if state == "recording":
            # Replace the bare "Recording..." with one that names the way out.
            message = self._cancel_hint_text()
            self._recording_hint = "cancel"
        else:
            self._recording_hint = None

        # Entering or leaving recording changes how much room column 0 needs.
        if (previous_state == "recording") != (state == "recording"):
            self._reserve_status_width()
        # Only recording drives the level meter; processing pulses the dot but
        # the microphone is already closed by then.
        recording = state == "recording"

        if state == "processing":
            self._processing_base_message = message
            if self._processing_since is None:
                self._processing_since = time.time()
                self._schedule_processing_tick()
            message = self._processing_message()
        else:
            self._stop_processing_timer()

        # TTK labels use configure with foreground
        self.status_label.configure(text=message, foreground=text_color)
        self.status_dot.configure(foreground=dot_color)
        # The status text changes width; keep the model label out of the way.
        self._schedule_model_label_fit()

        if pulsing:
            self._start_pulse(dot_color)
        else:
            self._stop_pulse()

        if recording:
            if not self._level_monitoring:
                self.start_level_monitor()
        elif self._level_monitoring:
            self.stop_level_monitor()

    # ── Processing elapsed counter ───────────────────────────────────────────

    def _processing_message(self):
        """The processing status text with its elapsed seconds appended."""
        base = self._processing_base_message or ""
        if self._processing_since is None:
            return base
        seconds = int(time.time() - self._processing_since)
        if seconds < 1:
            return base
        return _("{message} {seconds}s").format(message=base, seconds=seconds)

    def _schedule_processing_tick(self):
        self._processing_after_id = self._after(1000, self._processing_tick)

    def _processing_tick(self):
        self._processing_after_id = None
        if self._processing_since is None or not self._widget_alive(self.status_label):
            return
        self.status_label.configure(text=self._processing_message())
        self._schedule_model_label_fit()
        self._schedule_processing_tick()

    def _stop_processing_timer(self):
        self._processing_since = None
        self._processing_base_message = None
        self._cancel_after(self._processing_after_id)
        self._processing_after_id = None

    def _start_pulse(self, color=None):
        """Start (or keep) the status dot pulsing - never stacks loops."""
        if color is not None:
            self._pulse_color = color
        if self._pulse_active:
            return
        self._pulse_active = True
        self._pulse_state = True
        self._pulse_recording()

    def _stop_pulse(self):
        """Stop the pulse loop and cancel any pending tick."""
        self._pulse_active = False
        self._cancel_after(self._pulse_after_id)
        self._pulse_after_id = None

    def _pulse_recording(self):
        self._pulse_after_id = None
        if not self._pulse_active or not self._widget_alive(self.status_dot):
            return
        self._pulse_state = not self._pulse_state
        lit = self._pulse_color or self.theme.STATUS_RECORDING
        self.status_dot.configure(
            foreground=lit if self._pulse_state else self.theme.TEXT_MUTED
        )
        self._pulse_after_id = self._after(500, self._pulse_recording)

    def _copy_transcription(self):
        """Copy the entire transcription text to clipboard."""
        text = self.transcription_text.get("1.0", "end-1c")
        if text.strip():
            # Route through the app so the copy is verified the same way as
            # every other clipboard write.
            self.parent.copy_to_clipboard(text)

    def show_toast(self, message, duration=1500, anchor=None):
        """Show a toast from any thread, tolerating a torn-down window."""
        def _show():
            try:
                self._show_toast(message, duration=duration, anchor=anchor)
            except Exception as e:
                logger.debug("Could not show toast '%s': %s", message, e)

        try:
            self.parent.after(0, _show)
        except Exception as e:
            logger.debug("Could not schedule toast '%s': %s", message, e)

    def _show_toast(self, message, duration=1500, anchor=None):
        """Show a toast notification that fades away."""
        # Create toast window
        toast = tk.Toplevel(self.parent)
        toast.overrideredirect(True)  # Remove window decorations
        toast.attributes('-topmost', True)
        
        # Style the toast. The outer background shows through as a hairline
        # border, which is what separates the toast from the window in light
        # mode where its fill and the window behind it are both pale.
        toast.configure(bg=self.theme.BORDER)

        # Create rounded frame effect with border
        frame = tk.Frame(toast, bg=self.theme.BG_TERTIARY, padx=16, pady=10)
        frame.pack(padx=1, pady=1)
        
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
        
        # Position below the anchor widget (the Copy link by default). A
        # picker segment dropped because the window is narrow still exists but
        # is unmapped, and its screen position would be stale.
        if anchor is None or not self._widget_alive(anchor) or not anchor.winfo_ismapped():
            anchor = self.button_copy
        if not self._widget_alive(anchor) or not anchor.winfo_ismapped():
            toast.destroy()
            return

        btn_x = anchor.winfo_rootx()
        btn_y = anchor.winfo_rooty()
        btn_height = anchor.winfo_height()

        x = btn_x - toast_width // 2 + anchor.winfo_width() // 2
        y = btn_y + btn_height + 8

        toast.geometry(f"+{x}+{y}")

        # Fade out and destroy after duration. Every step re-checks that the
        # toast (and the app) still exist, so shutdown cannot raise here.
        def fade_out(alpha=1.0):
            if not self._widget_alive(toast):
                return
            if alpha > 0:
                try:
                    toast.attributes('-alpha', alpha)
                except Exception:
                    return
                if self._after(30, lambda: fade_out(alpha - 0.1)) is None:
                    toast.destroy()
            else:
                toast.destroy()

        # Start fade out after duration
        if self._after(duration, fade_out) is None:
            toast.destroy()
    
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
                # The record shortcut only doubles as "stop" in toggle mode;
                # in push-to-talk it is release that stops. Rather than print
                # a key that is right half the time, drop the caption - the
                # status line carries the cancel shortcut while recording.
                subtext="",
                solid_color=None,  # Use gradient mode
                solid_hover=None,
                gradient_start=self.theme.RECORDING_GRADIENT_START,
                gradient_mid=self.theme.RECORDING_GRADIENT_MID,
                gradient_end=self.theme.RECORDING_GRADIENT_END,
                hover_start=self.theme.RECORDING_GRADIENT_HOVER_START,
                hover_mid=self.theme.RECORDING_GRADIENT_HOVER_MID,
                hover_end=self.theme.RECORDING_GRADIENT_HOVER_END,
                border_color=self.theme.RECORDING_BORDER,
                text_color=self.theme.TEXT_ON_ACCENT  # White label on the red fill
            )
            self.record_button_edit.configure(
                text=_("Stop and Process"),
                # The record shortcut only doubles as "stop" in toggle mode;
                # in push-to-talk it is release that stops. Rather than print
                # a key that is right half the time, drop the caption - the
                # status line carries the cancel shortcut while recording.
                subtext="",
                solid_color=None,  # Use gradient mode
                solid_hover=None,
                gradient_start=self.theme.RECORDING_GRADIENT_START,
                gradient_mid=self.theme.RECORDING_GRADIENT_MID,
                gradient_end=self.theme.RECORDING_GRADIENT_END,
                hover_start=self.theme.RECORDING_GRADIENT_HOVER_START,
                hover_mid=self.theme.RECORDING_GRADIENT_HOVER_MID,
                hover_end=self.theme.RECORDING_GRADIENT_HOVER_END,
                border_color=self.theme.RECORDING_BORDER,
                text_color=self.theme.TEXT_ON_ACCENT  # White label on the red fill
            )
        else:
            self.update_button_shortcuts()
    
    def _record_shortcut(self, name):
        """Display form of a record shortcut, with a platform-correct default."""
        if name == 'record_edit':
            default = "Cmd+Alt+J" if self.parent.is_mac else "Ctrl+Alt+J"
        else:
            default = "Cmd+Alt+Shift+J" if self.parent.is_mac else "Ctrl+Alt+Shift+J"
        try:
            return self.parent.hotkey_manager.display_shortcut(name, default)
        except Exception:
            return default

    def update_button_shortcuts(self, transcribe_shortcut=None, edit_shortcut=None):
        # Guard: buttons may not exist yet during initialization
        if not self.record_button_transcribe or not self.record_button_edit:
            return

        edit_shortcut = edit_shortcut or self._record_shortcut('record_edit')
        transcribe_shortcut = transcribe_shortcut or self._record_shortcut('record_transcribe')

        # Reset to original gradient mode with white text
        self.record_button_transcribe.configure(
            text=_("Record + Transcribe"),
            subtext=transcribe_shortcut,
            solid_color=None,
            solid_hover=None,
            gradient_start=self.theme.GRADIENT_START,
            gradient_mid=self.theme.GRADIENT_MID,
            gradient_end=self.theme.GRADIENT_END,
            hover_start=self.theme.GRADIENT_HOVER_START,
            hover_mid=self.theme.GRADIENT_HOVER_MID,
            hover_end=self.theme.GRADIENT_HOVER_END,
            border_color="#6d9dc5",  # Original cyan border
            text_color=self.theme.TEXT_ON_ACCENT
        )
        self.record_button_edit.configure(
            text=_("Record + AI Edit"),
            subtext=edit_shortcut,
            solid_color=None,
            solid_hover=None,
            gradient_start=self.theme.GRADIENT_START,
            gradient_mid=self.theme.GRADIENT_MID,
            gradient_end=self.theme.GRADIENT_END,
            hover_start=self.theme.GRADIENT_HOVER_START,
            hover_mid=self.theme.GRADIENT_HOVER_MID,
            hover_end=self.theme.GRADIENT_HOVER_END,
            border_color="#6d9dc5",  # Original cyan border
            text_color=self.theme.TEXT_ON_ACCENT
        )
        
        # TTK labels use configure with text
        if hasattr(self, 'shortcut_label_left') and self.shortcut_label_left:
            self.shortcut_label_left.configure(text=transcribe_shortcut)
        if hasattr(self, 'shortcut_label_right') and self.shortcut_label_right:
            self.shortcut_label_right.configure(text=edit_shortcut)

        # Keep the tooltips honest after a rebind too.
        for tooltip, template, shortcut in (
            (getattr(self, '_tooltip_transcribe', None),
             _("Record and transcribe audio ({shortcut})"), transcribe_shortcut),
            (getattr(self, '_tooltip_edit', None),
             _("Record and AI-edit transcription ({shortcut})"), edit_shortcut),
        ):
            if tooltip is not None:
                tooltip.set_text(template.format(shortcut=shortcut))

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

        # Update navigation, re-run and copy buttons
        if hasattr(self, 'button_copy'):
            self.button_copy.configure(text=f"  {_('Copy')}")
        if self._widget_alive(getattr(self, 'button_history', None)):
            self.button_history.configure(text=f"  {_('History')}")
        if self._widget_alive(self.button_rerun):
            self.button_rerun.configure(text=f"  \u21ba {_('AI Edit')}")
        if self._widget_alive(self.device_refresh_link):
            self.device_refresh_link.configure(text=f"\u21bb  {_('Refresh')}")

        # Re-translate the status line from the msgid recorded when it was set,
        # so this works for any language pair rather than only from English.
        if self._widget_alive(getattr(self, 'status_label', None)) and self._status_msgid:
            translated = _(self._status_msgid)
            if self._status_state == "processing":
                self._processing_base_message = translated
                translated = self._processing_message()
            self.status_label.configure(text=translated)

        # Update option switches and the group that holds them
        if self._widget_alive(getattr(self, 'options_frame', None)):
            self.options_frame.configure(text=_("After transcription"))
        if hasattr(self, 'auto_copy_switch'):
            self.auto_copy_switch.configure(text=_("Auto-copy result"))
        if hasattr(self, 'auto_paste_switch'):
            self.auto_paste_switch.configure(text=_("Auto-paste result"))

        # Update action buttons (only if not in recording state)
        if hasattr(self, 'record_button_transcribe') and hasattr(self, 'record_button_edit'):
            if not self.parent.audio_manager.recording:
                self.record_button_transcribe.configure(text=_("Record + Transcribe"))
                self.record_button_edit.configure(text=_("Record + AI Edit"))
            else:
                self.record_button_transcribe.configure(text=_("Stop and Process"))
                self.record_button_edit.configure(text=_("Stop and Process"))

        # Translated status text is measured with these, and the strings have
        # just changed underneath them.
        self._clear_measuring_fonts()

        # The picker tooltips name the cycle shortcuts, so they change too.
        if self._widget_alive(self._picker_transcription):
            self.update_model_label()

        # Status widths change with the language - re-reserve and re-fit
        self._reserve_status_width()
        self._schedule_model_label_fit()

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

        # Swap the palette first: _setup_styles and every widget updated below
        # resolve their colours through it.
        set_theme_mode(is_dark)
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
        bg_color = theme_colors().BG_TERTIARY if is_dark else theme_colors().BG_PRIMARY
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
            colors = theme_colors()
            self.transcription_text.configure(
                bg=colors.BG_TERTIARY if is_dark else colors.BG_SECONDARY,
                fg=colors.TEXT_PRIMARY,
                insertbackground=colors.TEXT_PRIMARY,
                highlightbackground=colors.BORDER,
                highlightcolor=colors.BORDER_STRONG,
            )
        
        # Update the level meter surface and repaint it for the new theme
        if self._widget_alive(self.level_meter):
            self.level_meter.configure(bg=self._surface_color(is_dark))
            self._draw_meter()
        if self._widget_alive(self.elapsed_label):
            # Re-apply the elapsed colour for the new palette
            current = str(self.elapsed_label.cget('text')) or "0:00"
            try:
                minutes, secs = current.split(":")
                self.set_elapsed(int(minutes) * 60 + int(secs))
            except (ValueError, TypeError):
                self.set_elapsed(0.0)

        # Styles were rebuilt, so any font they resolved to may have changed.
        self._clear_measuring_fonts()

        # Update navigation button colors for the new theme
        if hasattr(self, 'button_first_page') and self.button_first_page:
            self._update_nav_button_appearance()

        # The picker segments carry an explicit foreground, so they do not
        # follow the ttk style when the theme changes.
        if self._widget_alive(self._picker_prompt):
            self._refresh_picker_colours()
            for separator in (self._picker_sep_1, self._picker_sep_2):
                if self._widget_alive(separator):
                    separator.configure(foreground=self.theme.TEXT_MUTED)

        # Update powered by link color (light blue in dark mode, purple in light mode)
        if hasattr(self, 'powered_by_label') and self.powered_by_label:
            link_color = self.theme.ACCENT_PRIMARY if is_dark else self.theme.GRADIENT_END
            self.powered_by_label.configure(foreground=link_color)

        logger.debug("Theme applied: %s", theme_name)
    
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
            logger.warning("Could not set light title bar: %s", e)