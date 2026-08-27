"""
Theme Colors - Scorchsoft brand color definitions.

Two palettes are defined with identical attribute names: ``ThemeColors`` (dark)
and ``LightThemeColors``. Widgets should resolve colours through
``theme_colors()`` rather than importing a palette directly, so that a theme
switch reaches every colour without per-widget ``if is_dark`` branches.

    from utils.theme import theme_colors
    label.configure(foreground=theme_colors().TEXT_PRIMARY)

Brand colours (the cyan-to-purple action gradient and the red recording
gradient) are deliberately identical in both palettes - they carry white text
on a saturated fill and read correctly against either ground.
"""


class ThemeColors:
    """Scorchsoft-branded dark palette (the default)."""

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

    # Gradient colors (matching logo: cyan -> purple with glow).
    # GRADIENT_START is cyan-600 rather than cyan-500 so the white button label
    # keeps usable contrast over the lightest end of the fill.
    GRADIENT_START = "#0891b2"       # Cyan-600
    GRADIENT_MID = "#3b82f6"         # Blue-500 (middle transition)
    GRADIENT_END = "#8b5cf6"         # Violet-500 (purple)
    GRADIENT_HOVER_START = "#06b6d4" # Lighter cyan
    GRADIENT_HOVER_MID = "#60a5fa"   # Lighter blue
    GRADIENT_HOVER_END = "#a78bfa"   # Lighter purple

    # Recording status - lighter/brighter red for visibility
    RECORDING_TEXT = "#f87171"

    # Recording button gradient (red tones)
    RECORDING_GRADIENT_START = "#dc2626"       # Red-600
    RECORDING_GRADIENT_MID = "#b91c1c"         # Red-700
    RECORDING_GRADIENT_END = "#7f1d1d"         # Red-900
    RECORDING_GRADIENT_HOVER_START = "#ef4444" # Red-500 (lighter)
    RECORDING_GRADIENT_HOVER_MID = "#dc2626"   # Red-600
    RECORDING_GRADIENT_HOVER_END = "#991b1b"   # Red-800
    RECORDING_BORDER = "#7f1d1d"               # Dark red border (Red-900)

    # Text - high contrast for accessibility
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#e0e0e0"    # Very readable
    TEXT_TERTIARY = "#b0b0b0"     # Still readable
    TEXT_MUTED = "#707070"

    # Label colour for text sitting on a saturated brand fill (the gradient
    # buttons). Those fills are identical in both themes, so this must NOT
    # follow the theme the way TEXT_PRIMARY does.
    TEXT_ON_ACCENT = "#ffffff"

    # Status
    STATUS_IDLE = "#909090"
    STATUS_PROCESSING = "#f59e0b"
    STATUS_RECORDING = "#ef4444"
    STATUS_SUCCESS = "#22c55e"

    # Borders
    BORDER = "#3a3a3a"           # More visible
    BORDER_STRONG = "#505050"    # Pronounced for inputs


class LightThemeColors:
    """Light palette.

    Text and status colours are chosen to clear WCAG AA (4.5:1) against
    ``BG_PRIMARY``/``BG_SECONDARY``; the dark palette's values sit between
    1.9:1 and 2.8:1 on a light ground, which is why they cannot simply be
    reused.
    """

    # Background colors
    BG_PRIMARY = "#fafafa"
    BG_SECONDARY = "#ffffff"
    BG_TERTIARY = "#f0f0f0"
    BG_HOVER = "#e8e8e8"
    BG_MENU = "#ffffff"

    # Scorchsoft Red - reserved for recording/stop states
    SCORCHSOFT_RED = "#dc2626"
    SCORCHSOFT_RED_HOVER = "#b91c1c"

    # Action accents - darkened so they stay legible as text/borders on white
    ACCENT_PRIMARY = "#0e7490"    # Cyan-700
    ACCENT_HOVER = "#0891b2"      # Cyan-600

    # Brand gradients are shared with the dark palette
    GRADIENT_START = ThemeColors.GRADIENT_START
    GRADIENT_MID = ThemeColors.GRADIENT_MID
    GRADIENT_END = ThemeColors.GRADIENT_END
    GRADIENT_HOVER_START = ThemeColors.GRADIENT_HOVER_START
    GRADIENT_HOVER_MID = ThemeColors.GRADIENT_HOVER_MID
    GRADIENT_HOVER_END = ThemeColors.GRADIENT_HOVER_END

    # Recording status text on a light ground
    RECORDING_TEXT = "#b91c1c"

    RECORDING_GRADIENT_START = ThemeColors.RECORDING_GRADIENT_START
    RECORDING_GRADIENT_MID = ThemeColors.RECORDING_GRADIENT_MID
    RECORDING_GRADIENT_END = ThemeColors.RECORDING_GRADIENT_END
    RECORDING_GRADIENT_HOVER_START = ThemeColors.RECORDING_GRADIENT_HOVER_START
    RECORDING_GRADIENT_HOVER_MID = ThemeColors.RECORDING_GRADIENT_HOVER_MID
    RECORDING_GRADIENT_HOVER_END = ThemeColors.RECORDING_GRADIENT_HOVER_END
    RECORDING_BORDER = "#b91c1c"

    # Text
    TEXT_PRIMARY = "#1a1a1a"
    TEXT_SECONDARY = "#3d3d3d"
    TEXT_TERTIARY = "#595959"     # 7.0:1 on BG_PRIMARY
    TEXT_MUTED = "#6e6e6e"        # 4.9:1 on BG_PRIMARY

    # Shared with the dark palette: the brand fills underneath are the same.
    TEXT_ON_ACCENT = ThemeColors.TEXT_ON_ACCENT

    # Status
    STATUS_IDLE = "#6e6e6e"
    STATUS_PROCESSING = "#b45309"  # Amber-700
    STATUS_RECORDING = "#dc2626"
    STATUS_SUCCESS = "#15803d"     # Green-700

    # Borders
    BORDER = "#d0d0d0"
    BORDER_STRONG = "#a0a0a0"


# Active palette state. Dark is the historical default, so an app that never
# calls set_theme_mode() behaves exactly as before.
_dark_mode = True


def set_theme_mode(is_dark: bool):
    """Select the palette returned by :func:`theme_colors`."""
    global _dark_mode
    _dark_mode = bool(is_dark)


def is_dark_mode() -> bool:
    """Whether the dark palette is currently active."""
    return _dark_mode


def theme_colors():
    """Return the palette class for the active theme."""
    return ThemeColors if _dark_mode else LightThemeColors
