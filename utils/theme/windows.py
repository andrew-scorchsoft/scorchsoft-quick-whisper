"""
Theme Window Sizes - Platform-aware window dimensions with HiDPI support.

Provides explicit window sizes per platform and HiDPI mode for consistent
window sizing across Windows, macOS, and Linux.
"""

import platform


# Transcription text area height (in lines/rows) per mode
# This controls the minimum height of the text widget
TEXT_AREA_HEIGHT = {
    'base': 2,        # Non-HiDPI: 10 lines
    'hidpi': 2,        # HiDPI: 8 lines (font is larger, so fewer lines needed)
}


# Window size definitions per platform and HiDPI mode
# Format: (width, height)
WINDOW_SIZES = {
    # Base sizes (non-HiDPI)
    'base': {
        'main': (640, 920),
        'api_key_dialog': (420, 220),
        'about_dialog': (800, 800),
        'tos_dialog': (300, 150),
        'terms_of_use': (580, 800),
        'manage_prompts': (800, 650),
        'edit_prompt_dialog': (600, 600),
        'config_dialog': (700, 500),
        'hotkey_dialog': (500, 400),
        'adjust_models': (450, 620),
        'version_notification': (400, 200),
    },
    # Windows HiDPI - explicit values
    'windows_hd': {
        'main': (1000, 1200),
        'api_key_dialog': (480, 250),
        'about_dialog': (1100, 1050),
        'tos_dialog': (340, 170),
        'terms_of_use': (720, 1080),
        'manage_prompts': (1500, 1050),
        'edit_prompt_dialog': (700, 720),
        'config_dialog': (1050, 750),
        'hotkey_dialog': (550, 440),
        'adjust_models': (540, 880),
        'version_notification': (440, 220),
    },
    # Linux HiDPI - explicit values (matched to windows_hd for consistent HiDPI experience)
    'linux_hd': {
        'main': (1000, 1150),
        'api_key_dialog': (480, 250),
        'about_dialog': (1100, 1000),
        'tos_dialog': (340, 170),
        'terms_of_use': (720, 1080),
        'manage_prompts': (1500, 1050),
        'edit_prompt_dialog': (700, 720),
        'config_dialog': (1050, 750),
        'hotkey_dialog': (550, 440),
        'adjust_models': (540, 880),
        'version_notification': (440, 220),
    },
    # macOS HiDPI - OS handles most scaling
    'darwin_hd': {
        'main': (640, 920),
        'api_key_dialog': (420, 220),
        'about_dialog': (800, 700),
        'tos_dialog': (300, 150),
        'terms_of_use': (580, 800),
        'manage_prompts': (800, 650),
        'edit_prompt_dialog': (600, 600),
        'config_dialog': (700, 500),
        'hotkey_dialog': (500, 400),
        'adjust_models': (450, 620),
        'version_notification': (400, 200),
    },
}


class WindowSizeProvider:
    """
    Centralized window size management with platform-aware HiDPI support.

    Must be initialized after determining HiDPI mode via WindowSizeProvider.init().
    After initialization, use convenience function get_window_size().
    """

    _initialized = False
    _is_hidpi = False
    _platform = None
    _map_key = 'base'

    @classmethod
    def init(cls, is_hidpi: bool = False):
        """
        Initialize the window size provider.

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
    def get_size(cls, window_name: str) -> tuple:
        """
        Get the window size for a given window name.

        Args:
            window_name: One of 'main', 'api_key_dialog', 'about_dialog',
                        'tos_dialog', 'terms_of_use', 'manage_prompts',
                        'edit_prompt_dialog', 'config_dialog', 'hotkey_dialog',
                        'adjust_models', 'version_notification'

        Returns:
            Tuple of (width, height) for the current platform and HiDPI mode
        """
        size_map = WINDOW_SIZES.get(cls._map_key, WINDOW_SIZES['base'])
        return size_map.get(window_name.lower(), size_map.get('main', (640, 920)))

    @classmethod
    def get_text_area_height(cls) -> int:
        """
        Get the transcription text area height in lines.

        Returns:
            Number of lines for the text area height
        """
        if cls._is_hidpi:
            return TEXT_AREA_HEIGHT.get('hidpi', 8)
        return TEXT_AREA_HEIGHT.get('base', 10)


# Convenience functions for module-level access
def get_window_size(window_name: str) -> tuple:
    """
    Get the window size for a given window name.

    Args:
        window_name: One of 'main', 'api_key_dialog', 'about_dialog',
                    'tos_dialog', 'terms_of_use', 'manage_prompts',
                    'edit_prompt_dialog', 'config_dialog', 'hotkey_dialog',
                    'adjust_models', 'version_notification'

    Returns:
        Tuple of (width, height) for the current platform and HiDPI mode
    """
    return WindowSizeProvider.get_size(window_name)


def get_text_area_height() -> int:
    """
    Get the transcription text area height in lines.

    Returns:
        Number of lines for the text area height
    """
    return WindowSizeProvider.get_text_area_height()
