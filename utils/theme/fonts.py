"""
Theme Fonts - Platform-aware font management with HiDPI support.

Provides explicit font sizes per platform and HiDPI mode for consistent
rendering across Windows, macOS, and Linux.
"""

import platform


# Font size definitions per platform and HiDPI mode
# Keys: 'base' (non-HiDPI), 'windows_hd', 'linux_hd', 'darwin_hd'
FONT_SIZES = {
    # Base sizes (non-HiDPI) - current values preserved
    'base': {
        'xxs': 10,
        'xs': 11,
        'sm': 12,
        'md': 13,
        'lg': 14,
        'xl': 15,
        # Semantic sizes for specific UI elements
        'menu_button': 10,
        'nav_arrow': 24,
        'separator': 16,
        'copy_link': 10,
        'status_dot': 14,
        'dialog_button': 12,
    },
    # Windows HiDPI - explicit values
    'windows_hd': {
        'xxs': 13,
        'xs': 14,
        'sm': 15,
        'md': 16,
        'lg': 17,
        'xl': 18,
        'menu_button': 13,
        'nav_arrow': 26,
        'separator': 18,
        'copy_link': 14,
        'status_dot': 15,
        'dialog_button': 14,
    },
    # Linux HiDPI - explicit values (may differ from Windows)
    'linux_hd': {
        'xxs': 10,
        'xs': 12,
        'sm': 13,
        'md': 14,
        'lg': 15,
        'xl': 16,
        'menu_button': 11,
        'nav_arrow': 26,
        'separator': 18,
        'copy_link': 11,
        'status_dot': 15,
        'dialog_button': 28,
    },
    # macOS HiDPI - OS handles most scaling, may need minor tweaks
    'darwin_hd': {
        'xxs': 9,
        'xs': 11,
        'sm': 12,
        'md': 13,
        'lg': 14,
        'xl': 15,
        'menu_button': 13,
        'nav_arrow': 24,
        'separator': 16,
        'copy_link': 10,
        'status_dot': 14,
        'dialog_button': 12,
    },
}


def _get_system_font():
    """Get the appropriate system font for the current platform."""
    system = platform.system()
    if system == 'Windows':
        return "Segoe UI"
    elif system == 'Darwin':  # macOS
        return "SF Pro Text"
    else:  # Linux
        # Try common Linux fonts in order of preference
        import tkinter.font as tkfont
        import tkinter as tk
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


class FontProvider:
    """
    Centralized font management with platform-aware HiDPI support.

    Must be initialized after Tk root window is created via FontProvider.init().
    After initialization, use convenience functions get_font() and get_font_size().
    """

    _initialized = False
    _font_family = None
    _is_hidpi = False
    _platform = None
    _size_map_key = 'base'

    @classmethod
    def init(cls, is_hidpi: bool = False):
        """
        Initialize the font provider after Tk root is available.

        Args:
            is_hidpi: Whether HiDPI mode is active
        """
        cls._font_family = _get_system_font()
        cls._is_hidpi = is_hidpi
        cls._platform = platform.system().lower()

        # Determine which size map to use
        if is_hidpi:
            if cls._platform == 'windows':
                cls._size_map_key = 'windows_hd'
            elif cls._platform == 'darwin':
                cls._size_map_key = 'darwin_hd'
            else:  # Linux and others
                cls._size_map_key = 'linux_hd'
        else:
            cls._size_map_key = 'base'

        cls._initialized = True

    @classmethod
    def get_family(cls) -> str:
        """Get the current font family name."""
        if not cls._initialized:
            # Return a safe default if not initialized
            return _get_system_font()
        return cls._font_family

    @classmethod
    def get_size(cls, size_name: str) -> int:
        """
        Get the font size for a given semantic size name.

        Args:
            size_name: One of 'xxs', 'xs', 'sm', 'md', 'lg', 'xl',
                      'nav_arrow', 'separator', 'copy_link', 'status_dot'

        Returns:
            The pixel size for the current platform and HiDPI mode
        """
        size_map = FONT_SIZES.get(cls._size_map_key, FONT_SIZES['base'])
        return size_map.get(size_name.lower(), size_map['md'])

    @classmethod
    def get_font(cls, size_name: str, weight: str = 'normal') -> tuple:
        """
        Get a complete font tuple for use with Tkinter widgets.

        Args:
            size_name: One of 'xxs', 'xs', 'sm', 'md', 'lg', 'xl',
                      'nav_arrow', 'separator', 'copy_link', 'status_dot'
            weight: 'normal', 'bold', 'italic', or 'underline'

        Returns:
            A tuple of (font_family, size) or (font_family, size, weight)
        """
        family = cls.get_family()
        size = cls.get_size(size_name)

        if weight == 'normal':
            return (family, size)
        else:
            return (family, size, weight)

    @classmethod
    def is_hidpi(cls) -> bool:
        """Check if HiDPI mode is active."""
        return cls._is_hidpi

    @classmethod
    def get_platform(cls) -> str:
        """Get the current platform identifier."""
        return cls._platform or platform.system().lower()


# Convenience functions for module-level access
def get_font(size_name: str, weight: str = 'normal') -> tuple:
    """
    Get a font tuple for the given semantic size.

    Args:
        size_name: One of 'xxs', 'xs', 'sm', 'md', 'lg', 'xl',
                  'nav_arrow', 'separator', 'copy_link', 'status_dot'
        weight: 'normal', 'bold', 'italic', or 'underline'

    Returns:
        A tuple of (font_family, size) or (font_family, size, weight)
    """
    return FontProvider.get_font(size_name, weight)


def get_font_size(size_name: str) -> int:
    """
    Get just the numeric size for a semantic size name.

    Args:
        size_name: One of 'xxs', 'xs', 'sm', 'md', 'lg', 'xl',
                  'nav_arrow', 'separator', 'copy_link', 'status_dot'

    Returns:
        The pixel size for the current platform and HiDPI mode
    """
    return FontProvider.get_size(size_name)


def get_font_family() -> str:
    """Get the current font family name."""
    return FontProvider.get_family()


def get_emoji_font() -> str:
    """
    Get a font family that supports emoji rendering on the current platform.

    Returns:
        Font family name that supports emojis, or None if not available
    """
    system = platform.system()
    if system == 'Windows':
        return "Segoe UI Emoji"
    elif system == 'Darwin':  # macOS
        return "Apple Color Emoji"
    else:  # Linux
        import tkinter.font as tkfont
        import tkinter as tk
        try:
            temp_root = tk._default_root
            if temp_root is None:
                return None
            available_fonts = tkfont.families()
            # Try common emoji fonts on Linux
            emoji_fonts = [
                "Noto Color Emoji",
                "Noto Emoji",
                "Symbola",
                "Twemoji",
                "EmojiOne",
            ]
            for font in emoji_fonts:
                if font in available_fonts:
                    return font
        except Exception:
            pass
        return None


# Platform-aware feature icons (fallback text for systems without emoji support)
def get_feature_icons() -> list:
    """
    Get feature icons that work on the current platform.

    Returns:
        List of tuples (icon, description) for the About dialog features
    """
    system = platform.system()

    # Check if we have emoji support on Linux
    emoji_available = True
    if system == 'Linux':
        emoji_font = get_emoji_font()
        emoji_available = emoji_font is not None

    if emoji_available and system != 'Linux':
        # Windows and macOS - use emojis
        return [
            ("🎤", "Automatic Speech-to-Text Conversion"),
            ("✨", "Built-in AI Copy Editing"),
            ("📋", "Auto-Copy and Auto-Paste Functionality"),
            ("⌨️", "Hotkey-Activated Recording"),
            ("🔧", "Customizable AI Models and Prompts")
        ]
    else:
        # Linux or no emoji support - use Unicode symbols that render reliably
        return [
            ("●", "Automatic Speech-to-Text Conversion"),
            ("●", "Built-in AI Copy Editing"),
            ("●", "Auto-Copy and Auto-Paste Functionality"),
            ("●", "Hotkey-Activated Recording"),
            ("●", "Customizable AI Models and Prompts")
        ]
