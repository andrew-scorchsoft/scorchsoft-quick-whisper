"""
Theme Module - Centralized theming with platform-aware HiDPI support.

This module provides:
- ThemeColors: Color constants for the Scorchsoft brand
- FontProvider: Platform-specific font sizing with HiDPI support
- SpacingProvider: Platform-specific spacing and radius with HiDPI support
- WindowSizeProvider: Platform-specific window sizes with HiDPI support

Usage:
    from utils.theme import get_font, get_font_size, get_spacing, get_radius, ThemeColors

    # Initialize (must be called after Tk root is created, before UI setup)
    from utils.theme import init_theme
    init_theme(is_hidpi=True)

    # Get a font tuple for widgets
    font = get_font('md')           # ("Segoe UI", 13) or platform equivalent
    font = get_font('lg', 'bold')   # ("Segoe UI", 14, "bold")

    # Get just the size
    size = get_font_size('md')      # 13 (or HD equivalent)

    # Get spacing values
    padding = get_spacing('md')     # 12 (or HD equivalent)

    # Get radius values
    radius = get_radius('md')       # 8 (or HD equivalent)

    # Get window sizes
    width, height = get_window_size('main')  # (640, 920) or platform/HD equivalent

    # Access colors
    bg = ThemeColors.BG_PRIMARY
"""

from .colors import ThemeColors
from .fonts import (
    FontProvider,
    FONT_SIZES,
    get_font,
    get_font_size,
    get_font_family,
)
from .spacing import (
    SpacingProvider,
    SPACING,
    RADIUS,
    BUTTON_HEIGHT,
    BORDER_WIDTH,
    get_spacing,
    get_radius,
    get_button_height,
    get_border_width,
)
from .windows import (
    WindowSizeProvider,
    WINDOW_SIZES,
    get_window_size,
)


def init_theme(is_hidpi: bool = False):
    """
    Initialize the theme system.

    Must be called after Tk root window is created and before UI setup.

    Args:
        is_hidpi: Whether HiDPI mode is active
    """
    FontProvider.init(is_hidpi=is_hidpi)
    SpacingProvider.init(is_hidpi=is_hidpi)
    WindowSizeProvider.init(is_hidpi=is_hidpi)


__all__ = [
    # Initialization
    'init_theme',
    # Colors
    'ThemeColors',
    # Fonts
    'FontProvider',
    'FONT_SIZES',
    'get_font',
    'get_font_size',
    'get_font_family',
    # Spacing
    'SpacingProvider',
    'SPACING',
    'RADIUS',
    'BUTTON_HEIGHT',
    'BORDER_WIDTH',
    'get_spacing',
    'get_radius',
    'get_button_height',
    'get_border_width',
    # Window sizes
    'WindowSizeProvider',
    'WINDOW_SIZES',
    'get_window_size',
]
