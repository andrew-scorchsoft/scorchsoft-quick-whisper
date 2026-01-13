"""
Internationalization (i18n) module for Quick Whisper.

Uses Python's standard gettext approach for translations with support for:
- Runtime language switching without app restart
- Auto-detection of OS locale
- Widget refresh bindings for dynamic UI updates
- Plural forms via ngettext

Usage:
    from utils.i18n import _, _n, set_language, get_current_language

    # Simple translation
    label = ttk.Label(parent, text=_("Settings"))

    # Plural translation
    msg = _n("{count} file", "{count} files", count).format(count=count)

    # Register widget for refresh on language change
    from utils.i18n import register_widget
    register_widget(label, 'text', 'settings.title')
"""

import gettext
import locale
import os
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

# Domain name for translations
DOMAIN = "quickwhisper"

# Supported languages with display names
SUPPORTED_LANGUAGES: Dict[str, str] = {
    "en": "English",
    "fr": "Fran\u00e7ais",
    "de": "Deutsch",
    "es": "Espa\u00f1ol",
    "zh_CN": "\u7b80\u4f53\u4e2d\u6587",
    "ar": "\u0627\u0644\u0639\u0631\u0628\u064a\u0629",
}

# Language code mappings for locale detection
LANGUAGE_ALIASES: Dict[str, str] = {
    # English variants
    "en_US": "en",
    "en_GB": "en",
    "en_AU": "en",
    "en_CA": "en",
    # French variants
    "fr_FR": "fr",
    "fr_CA": "fr",
    "fr_BE": "fr",
    "fr_CH": "fr",
    # German variants
    "de_DE": "de",
    "de_AT": "de",
    "de_CH": "de",
    # Spanish variants
    "es_ES": "es",
    "es_MX": "es",
    "es_AR": "es",
    "es_CO": "es",
    # Chinese variants - default to Simplified
    "zh": "zh_CN",
    "zh_Hans": "zh_CN",
    "zh_Hant": "zh_CN",  # Fall back to Simplified if Traditional not available
    "zh_TW": "zh_CN",
    "zh_HK": "zh_CN",
    "zh_SG": "zh_CN",
    # Arabic variants
    "ar_SA": "ar",
    "ar_EG": "ar",
    "ar_AE": "ar",
}

# Current translation state
_current_language: str = "en"
_translations: Optional[gettext.GNUTranslations] = None
_null_translations = gettext.NullTranslations()

# Widget registry for runtime refresh
# Structure: [(widget, property_name, msgid, is_plural, plural_n), ...]
_widget_registry: List[Tuple[Any, str, str, bool, Optional[Callable[[], int]]]] = []

# Callback registry for custom refresh actions
_refresh_callbacks: List[Callable[[], None]] = []


def get_locale_dir() -> Path:
    """
    Get the locale directory path, handling both development and packaged builds.

    Returns the path to the locale directory containing .mo files.
    """
    # Check if running as a PyInstaller bundle
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        base_path = Path(sys._MEIPASS)  # type: ignore
    else:
        # Running from source
        base_path = Path(__file__).parent.parent

    locale_dir = base_path / "locale"

    # Fallback: check if locale dir exists alongside the script
    if not locale_dir.exists():
        alt_locale_dir = Path(__file__).parent.parent / "locale"
        if alt_locale_dir.exists():
            locale_dir = alt_locale_dir

    return locale_dir


def get_available_languages() -> Dict[str, str]:
    """
    Get dictionary of available languages based on compiled .mo files.

    Returns:
        Dict mapping language codes to display names for available translations.
        Always includes English as it's the fallback.
    """
    available = {"en": SUPPORTED_LANGUAGES["en"]}
    locale_dir = get_locale_dir()

    if locale_dir.exists():
        for lang_code in SUPPORTED_LANGUAGES:
            if lang_code == "en":
                continue  # English is always available as fallback
            mo_path = locale_dir / lang_code / "LC_MESSAGES" / f"{DOMAIN}.mo"
            if mo_path.exists():
                available[lang_code] = SUPPORTED_LANGUAGES[lang_code]

    return available


def detect_os_locale() -> str:
    """
    Detect the OS locale and map it to a supported language.

    Returns:
        The best matching supported language code, or "en" as fallback.
    """
    try:
        # Try different methods to get the locale
        os_locale = None

        # Method 1: locale.getdefaultlocale (deprecated but still works)
        try:
            os_locale, _ = locale.getdefaultlocale()
        except (ValueError, AttributeError):
            pass

        # Method 2: locale.getlocale
        if not os_locale:
            try:
                os_locale, _ = locale.getlocale()
            except (ValueError, AttributeError):
                pass

        # Method 3: Environment variables
        if not os_locale:
            for var in ('LC_ALL', 'LC_MESSAGES', 'LANG', 'LANGUAGE'):
                os_locale = os.environ.get(var)
                if os_locale:
                    # Clean up encoding suffix
                    os_locale = os_locale.split('.')[0]
                    break

        if not os_locale:
            logger.debug("Could not detect OS locale, defaulting to English")
            return "en"

        logger.debug(f"Detected OS locale: {os_locale}")
        return _match_locale_to_language(os_locale)

    except Exception as e:
        logger.warning(f"Error detecting OS locale: {e}")
        return "en"


def _match_locale_to_language(os_locale: str) -> str:
    """
    Match an OS locale string to a supported language code.

    Implements fallback matching:
    1. Exact match in LANGUAGE_ALIASES
    2. Direct match in SUPPORTED_LANGUAGES
    3. Language-only match (e.g., "fr_CA" -> "fr")
    4. Default to English

    Args:
        os_locale: The OS locale string (e.g., "fr_CA", "de_DE.UTF-8")

    Returns:
        A supported language code.
    """
    # Clean up the locale string
    locale_clean = os_locale.split('.')[0].split('@')[0]

    # Try exact match in aliases
    if locale_clean in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[locale_clean]

    # Try direct match in supported languages
    if locale_clean in SUPPORTED_LANGUAGES:
        return locale_clean

    # Try language-only match (first part before underscore)
    lang_only = locale_clean.split('_')[0]
    if lang_only in SUPPORTED_LANGUAGES:
        return lang_only

    # Check if any alias maps to this language
    if lang_only in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[lang_only]

    logger.debug(f"No match for locale '{os_locale}', defaulting to English")
    return "en"


def get_detected_locale_display() -> str:
    """
    Get a display string for the detected OS locale.

    Returns:
        A string like "German (de_DE)" for UI display.
    """
    detected = detect_os_locale()
    display_name = SUPPORTED_LANGUAGES.get(detected, "English")
    return f"{display_name} ({detected})"


def load_translations(lang_code: str) -> Optional[gettext.GNUTranslations]:
    """
    Load translations for a specific language.

    Args:
        lang_code: The language code (e.g., "fr", "de", "zh_CN")

    Returns:
        A GNUTranslations object, or None if translations couldn't be loaded.
    """
    if lang_code == "en":
        return None  # English uses fallback (original strings)

    locale_dir = get_locale_dir()
    mo_path = locale_dir / lang_code / "LC_MESSAGES" / f"{DOMAIN}.mo"

    if not mo_path.exists():
        logger.warning(f"Translation file not found: {mo_path}")
        return None

    try:
        with open(mo_path, 'rb') as f:
            translations = gettext.GNUTranslations(f)
            logger.info(f"Loaded translations for '{lang_code}'")
            return translations
    except Exception as e:
        logger.error(f"Failed to load translations for '{lang_code}': {e}")
        return None


def set_language(lang_code: str, refresh_ui: bool = True) -> bool:
    """
    Set the current language and optionally refresh all registered widgets.

    Args:
        lang_code: The language code to set (e.g., "fr", "de", "zh_CN")
        refresh_ui: If True, refresh all registered widgets with new translations

    Returns:
        True if the language was set successfully, False otherwise.
    """
    global _current_language, _translations

    # Validate language code
    if lang_code not in SUPPORTED_LANGUAGES and lang_code not in LANGUAGE_ALIASES.values():
        logger.warning(f"Unsupported language code: {lang_code}")
        lang_code = "en"

    # Map aliases to canonical codes
    if lang_code in LANGUAGE_ALIASES:
        lang_code = LANGUAGE_ALIASES[lang_code]

    # Load translations
    if lang_code == "en":
        _translations = None
    else:
        _translations = load_translations(lang_code)
        if _translations is None and lang_code != "en":
            logger.warning(f"Falling back to English for unsupported language: {lang_code}")
            lang_code = "en"

    _current_language = lang_code
    logger.info(f"Language set to: {lang_code}")

    # Refresh registered widgets
    if refresh_ui:
        refresh_all_widgets()

    return True


def get_current_language() -> str:
    """Get the current language code."""
    return _current_language


def get_current_language_display() -> str:
    """Get the display name of the current language."""
    return SUPPORTED_LANGUAGES.get(_current_language, "English")


def _(msgid: str) -> str:
    """
    Translate a string using the current language.

    This is the main translation function. Use it to wrap all user-visible strings.

    Args:
        msgid: The string to translate (in English)

    Returns:
        The translated string, or the original if no translation is available.

    Example:
        label = ttk.Label(parent, text=_("Settings"))
    """
    if _translations is not None:
        return _translations.gettext(msgid)
    return msgid


def _n(singular: str, plural: str, n: int) -> str:
    """
    Translate a string with plural forms.

    Use this for strings that vary based on count. The translated string will
    use the appropriate plural form for the current language.

    Args:
        singular: The singular form (in English)
        plural: The plural form (in English)
        n: The count to determine which form to use

    Returns:
        The translated string in the appropriate plural form.

    Example:
        msg = _n("{count} file selected", "{count} files selected", count).format(count=count)
    """
    if _translations is not None:
        return _translations.ngettext(singular, plural, n)
    return singular if n == 1 else plural


# Aliases for convenience
gettext_func = _
ngettext_func = _n


def register_widget(widget: Any, property_name: str, msgid: str,
                   is_plural: bool = False, plural_n_func: Optional[Callable[[], int]] = None) -> None:
    """
    Register a widget for automatic text refresh on language change.

    Args:
        widget: The Tkinter widget to register
        property_name: The property to update (e.g., 'text', 'label')
        msgid: The message ID (original English string) to translate
        is_plural: If True, use ngettext for translation
        plural_n_func: A callable that returns the count for plural forms

    Example:
        label = ttk.Label(parent, text=_("Settings"))
        register_widget(label, 'text', "Settings")
    """
    _widget_registry.append((widget, property_name, msgid, is_plural, plural_n_func))


def unregister_widget(widget: Any) -> None:
    """
    Unregister a widget from automatic refresh.

    Call this when a widget is destroyed to prevent memory leaks.

    Args:
        widget: The widget to unregister
    """
    global _widget_registry
    _widget_registry = [
        entry for entry in _widget_registry
        if entry[0] is not widget
    ]


def register_refresh_callback(callback: Callable[[], None]) -> None:
    """
    Register a callback to be called when the language changes.

    Use this for complex UI elements that need custom refresh logic,
    such as menus or dynamically generated content.

    Args:
        callback: A function to call on language change
    """
    if callback not in _refresh_callbacks:
        _refresh_callbacks.append(callback)


def unregister_refresh_callback(callback: Callable[[], None]) -> None:
    """
    Unregister a refresh callback.

    Args:
        callback: The callback to remove
    """
    if callback in _refresh_callbacks:
        _refresh_callbacks.remove(callback)


def refresh_all_widgets() -> None:
    """
    Refresh all registered widgets with current translations.

    This is called automatically when the language changes, but can also
    be called manually if needed.
    """
    # Refresh registered widgets
    dead_widgets = []
    for widget, prop_name, msgid, is_plural, plural_n_func in _widget_registry:
        try:
            # Check if widget still exists
            if not widget.winfo_exists():
                dead_widgets.append((widget, prop_name, msgid, is_plural, plural_n_func))
                continue

            # Get translated text
            if is_plural and plural_n_func is not None:
                n = plural_n_func()
                # For plural, msgid should be a tuple (singular, plural)
                if isinstance(msgid, tuple):
                    text = _n(msgid[0], msgid[1], n)
                else:
                    text = _(msgid)
            else:
                text = _(msgid)

            # Update widget property
            widget.configure(**{prop_name: text})

        except Exception as e:
            logger.debug(f"Failed to refresh widget: {e}")
            dead_widgets.append((widget, prop_name, msgid, is_plural, plural_n_func))

    # Clean up dead widgets
    for entry in dead_widgets:
        if entry in _widget_registry:
            _widget_registry.remove(entry)

    # Call refresh callbacks
    for callback in _refresh_callbacks[:]:  # Copy to avoid modification during iteration
        try:
            callback()
        except Exception as e:
            logger.error(f"Refresh callback failed: {e}")


def clear_widget_registry() -> None:
    """
    Clear all widget registrations.

    Call this when rebuilding the UI or on application shutdown.
    """
    global _widget_registry, _refresh_callbacks
    _widget_registry.clear()
    _refresh_callbacks.clear()


def init_i18n(config_language_mode: str = "auto",
              config_language: Optional[str] = None) -> str:
    """
    Initialize the i18n system based on configuration.

    Args:
        config_language_mode: Either "auto" or "manual"
        config_language: The language code if mode is "manual"

    Returns:
        The language code that was set.
    """
    if config_language_mode == "auto":
        lang = detect_os_locale()
    elif config_language:
        lang = config_language
    else:
        lang = "en"

    set_language(lang, refresh_ui=False)
    return lang


# Initialize with English by default
_current_language = "en"
_translations = None
