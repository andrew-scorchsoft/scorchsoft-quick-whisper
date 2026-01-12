"""
Theme Colors - Scorchsoft brand color definitions.

All color constants used throughout the application.
"""


class ThemeColors:
    """Scorchsoft-branded color palette."""

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

    # Gradient colors (matching logo: cyan -> purple with glow)
    GRADIENT_START = "#06b6d4"       # Cyan-500 (richer cyan)
    GRADIENT_MID = "#3b82f6"         # Blue-500 (middle transition)
    GRADIENT_END = "#8b5cf6"         # Violet-500 (purple)
    GRADIENT_HOVER_START = "#22d3ee" # Lighter cyan
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

    # Status
    STATUS_IDLE = "#909090"
    STATUS_PROCESSING = "#f59e0b"
    STATUS_RECORDING = "#ef4444"
    STATUS_SUCCESS = "#22c55e"

    # Borders
    BORDER = "#3a3a3a"           # More visible
    BORDER_STRONG = "#505050"    # Pronounced for inputs
