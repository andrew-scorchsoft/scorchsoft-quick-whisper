"""
Theme Spacing - Platform-aware spacing and radius values with HiDPI support.

Provides explicit spacing and border radius values per platform and HiDPI mode
for consistent UI layout across Windows, macOS, and Linux.
"""

import platform


# Spacing values per platform and HiDPI mode
SPACING = {
    # Base spacing (non-HiDPI)
    'base': {
        'xxs': 2,
        'xs': 4,
        'sm': 8,
        'md': 12,
        'lg': 16,
        'xl': 24,
        'xxl': 32,
    },
    # Windows HiDPI
    'windows_hd': {
        'xxs': 3,
        'xs': 5,
        'sm': 10,
        'md': 14,
        'lg': 18,
        'xl': 28,
        'xxl': 36,
    },
    # Linux HiDPI
    'linux_hd': {
        'xxs': 3,
        'xs': 5,
        'sm': 10,
        'md': 14,
        'lg': 18,
        'xl': 28,
        'xxl': 36,
    },
    # macOS HiDPI (OS handles most scaling)
    'darwin_hd': {
        'xxs': 2,
        'xs': 4,
        'sm': 8,
        'md': 12,
        'lg': 16,
        'xl': 24,
        'xxl': 32,
    },
}


# Button height values per platform and HiDPI mode
BUTTON_HEIGHT = {
    # Base button heights (non-HiDPI)
    'base': {
        'sm': 36,
        'md': 50,
        'lg': 60,
        'dialog': 40,
    },
    # Windows HiDPI
    'windows_hd': {
        'sm': 42,
        'md': 90,
        'lg': 70,
        'dialog': 56,
    },
    # Linux HiDPI
    'linux_hd': {
        'sm': 42,
        'md': 80,
        'lg': 70,
        'dialog': 56,
    },
    # macOS HiDPI (OS handles most scaling)
    'darwin_hd': {
        'sm': 36,
        'md': 50,
        'lg': 60,
        'dialog': 40,
    },
}


# Border width values per platform and HiDPI mode
BORDER_WIDTH = {
    # Base border widths (non-HiDPI)
    'base': {
        'sm': 1,
        'md': 1,
        'lg': 2,
    },
    # Windows HiDPI
    'windows_hd': {
        'sm': 1,
        'md': 2,
        'lg': 3,
    },
    # Linux HiDPI
    'linux_hd': {
        'sm': 1,
        'md': 2,
        'lg': 3,
    },
    # macOS HiDPI (OS handles most scaling)
    'darwin_hd': {
        'sm': 1,
        'md': 1,
        'lg': 2,
    },
}


# Border radius values per platform and HiDPI mode
RADIUS = {
    # Base radius (non-HiDPI)
    'base': {
        'xs': 4,
        'sm': 6,
        'md': 8,
        'lg': 12,
        'pill': 9999,
    },
    # Windows HiDPI
    'windows_hd': {
        'xs': 5,
        'sm': 7,
        'md': 10,
        'lg': 14,
        'pill': 9999,
    },
    # Linux HiDPI
    'linux_hd': {
        'xs': 5,
        'sm': 7,
        'md': 10,
        'lg': 14,
        'pill': 9999,
    },
    # macOS HiDPI (OS handles most scaling)
    'darwin_hd': {
        'xs': 4,
        'sm': 6,
        'md': 8,
        'lg': 12,
        'pill': 9999,
    },
}


class SpacingProvider:
    """
    Centralized spacing and radius management with platform-aware HiDPI support.

    Must be initialized after determining HiDPI mode via SpacingProvider.init().
    After initialization, use convenience functions get_spacing() and get_radius().
    """

    _initialized = False
    _is_hidpi = False
    _platform = None
    _map_key = 'base'

    @classmethod
    def init(cls, is_hidpi: bool = False):
        """
        Initialize the spacing provider.

        Args:
            is_hidpi: Whether HiDPI mode is active
        """
        cls._is_hidpi = is_hidpi
        cls._platform = platform.system().lower()

        # Determine which map to use
        if is_hidpi:
            if cls._platform == 'windows':
                cls._map_key = 'windows_hd'
            elif cls._platform == 'darwin':
                cls._map_key = 'darwin_hd'
            else:  # Linux and others
                cls._map_key = 'linux_hd'
        else:
            cls._map_key = 'base'

        cls._initialized = True

    @classmethod
    def get_spacing(cls, size_name: str) -> int:
        """
        Get the spacing value for a given semantic size name.

        Args:
            size_name: One of 'xxs', 'xs', 'sm', 'md', 'lg', 'xl', 'xxl'

        Returns:
            The pixel spacing for the current platform and HiDPI mode
        """
        spacing_map = SPACING.get(cls._map_key, SPACING['base'])
        return spacing_map.get(size_name.lower(), spacing_map['md'])

    @classmethod
    def get_radius(cls, size_name: str) -> int:
        """
        Get the border radius for a given semantic size name.

        Args:
            size_name: One of 'xs', 'sm', 'md', 'lg', 'pill'

        Returns:
            The pixel radius for the current platform and HiDPI mode
        """
        radius_map = RADIUS.get(cls._map_key, RADIUS['base'])
        return radius_map.get(size_name.lower(), radius_map['md'])

    @classmethod
    def get_button_height(cls, size_name: str) -> int:
        """
        Get the button height for a given semantic size name.

        Args:
            size_name: One of 'sm', 'md', 'lg'

        Returns:
            The pixel height for the current platform and HiDPI mode
        """
        height_map = BUTTON_HEIGHT.get(cls._map_key, BUTTON_HEIGHT['base'])
        return height_map.get(size_name.lower(), height_map['md'])

    @classmethod
    def get_border_width(cls, size_name: str) -> int:
        """
        Get the border width for a given semantic size name.

        Args:
            size_name: One of 'sm', 'md', 'lg'

        Returns:
            The pixel border width for the current platform and HiDPI mode
        """
        width_map = BORDER_WIDTH.get(cls._map_key, BORDER_WIDTH['base'])
        return width_map.get(size_name.lower(), width_map['md'])


# Convenience functions for module-level access
def get_spacing(size_name: str) -> int:
    """
    Get the spacing value for a given semantic size name.

    Args:
        size_name: One of 'xxs', 'xs', 'sm', 'md', 'lg', 'xl', 'xxl'

    Returns:
        The pixel spacing for the current platform and HiDPI mode
    """
    return SpacingProvider.get_spacing(size_name)


def get_radius(size_name: str) -> int:
    """
    Get the border radius for a given semantic size name.

    Args:
        size_name: One of 'xs', 'sm', 'md', 'lg', 'pill'

    Returns:
        The pixel radius for the current platform and HiDPI mode
    """
    return SpacingProvider.get_radius(size_name)


def get_button_height(size_name: str) -> int:
    """
    Get the button height for a given semantic size name.

    Args:
        size_name: One of 'sm', 'md', 'lg'

    Returns:
        The pixel height for the current platform and HiDPI mode
    """
    return SpacingProvider.get_button_height(size_name)


def get_border_width(size_name: str) -> int:
    """
    Get the border width for a given semantic size name.

    Args:
        size_name: One of 'sm', 'md', 'lg'

    Returns:
        The pixel border width for the current platform and HiDPI mode
    """
    return SpacingProvider.get_border_width(size_name)
