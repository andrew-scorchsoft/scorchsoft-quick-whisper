# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Quick Whisper is a desktop speech-to-copy-edited-text application by Scorchsoft. It records audio, transcribes it using OpenAI's Whisper/GPT-4o models, optionally runs AI copy-editing via GPT, and auto-pastes the result. Built with Python/Tkinter for Windows (primary), macOS, and Linux.

## Development Commands

```bash
# Setup virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Linux: use --system-site-packages for GTK/GStreamer bindings
python3 -m venv venv --system-site-packages

# Install dependencies
pip install -r requirements.txt

# Run the application
python quick_whisper.py

# Build standalone executable (PyInstaller)
python tools/build.py              # windowed release build
python tools/build.py --console    # console-enabled diagnostic build
```

### Platform Prerequisites

**Linux** (before creating venv):
```bash
sudo apt install portaudio19-dev python3-tk python3-gi gir1.2-gstreamer-1.0 gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 gstreamer1.0-plugins-base espeak
```

**macOS**:
```bash
brew install portaudio
# Grant accessibility permissions: System Preferences > Security & Privacy > Privacy > Accessibility
```

## Architecture

### Entry Point
- `quick_whisper.py` - Minimal launcher that instantiates `QuickWhisper` from `utils/quick_whisper.py`

### Core Application (`utils/quick_whisper.py`)
- `QuickWhisper` class extends `tk.Tk` - main application window
- Initializes all managers and coordinates between them
- Handles OpenAI API calls for transcription (`client.audio.transcriptions.create`) and AI editing (`client.responses.create` for GPT-5/GPT-5.6, `client.chat.completions.create` for others)
- Manages prompts (Default from `assets/DefaultPrompt.md`, custom from `config/prompts.json`)

### Manager Classes (in `utils/`)
| Manager | Purpose |
|---------|---------|
| `AudioManager` | PyAudio recording, WAV file handling, sound playback |
| `HotkeyManager` | Global hotkeys via `pynput`, delegates to platform-specific implementations |
| `UIManager` | All Tkinter widgets, Sun Valley theme (sv_ttk), custom `GradientButton` component |
| `ConfigManager` | JSON-based settings (`config/settings.json`) and encrypted credentials (`config/credentials.json`) |
| `TTSManager` | Text-to-speech for prompt name announcements |
| `TrayManager` | System tray icon via `pystray`, including the red recording-state variant generated from the app icon |
| `VersionUpdateManager` | GitHub release checking |
| `paths` | Central path resolution (config, prompts, logs, recordings) - anchored to the app, never the working directory |
| `app_logging` | Rotating log file + console logging; `get_logger(__name__)` in every module |
| `SystemEventListener` | Session lock/unlock detection for hotkey refresh |

### Platform-Specific Module (`utils/platform/`)
Cross-platform support via factory pattern in `__init__.py`:
- `hotkey_base.py` - Abstract base class for hotkey managers
- `hotkey_windows.py`, `hotkey_macos.py`, `hotkey_linux.py` - Platform implementations using `pynput`
- `system_events_base.py` - Abstract base for system event listeners
- `system_events_windows.py`, `system_events_unix.py` - Platform-specific event handling

Factory functions: `get_hotkey_manager_class()`, `get_system_event_listener_class()`

### Configuration
- `config/settings.json` - UI preferences, model settings, keyboard shortcuts, recording options
- `config/credentials.json` - Encrypted OpenAI API key (uses `cryptography` Fernet)
- Auto-migrates from legacy `.env` format

### Default Keyboard Shortcuts
**Windows/Linux:**
- `Ctrl+Alt+J` - Record + AI Edit
- `Ctrl+Alt+Shift+J` - Record + Transcribe only
- `Ctrl+Alt+X` - Cancel recording
- `Ctrl+Alt+R` - Retry last recording
- `Alt+Left/Right` - Cycle through prompts
- `Escape` - Cancel recording (when the window has focus)

**macOS:**
- `Cmd+Alt+J` - Record + AI Edit
- `Cmd+Alt+Shift+J` - Record + Transcribe only
- `Cmd+X` - Cancel recording
- `Cmd+Alt+R` - Retry last recording
- `Cmd+[/]` - Cycle through prompts
- `Escape` - Cancel recording (when the window has focus)

### Recording Modes
`behavior.recording_mode` selects how the record shortcuts behave:
- `toggle` (default) - press to start, press again to stop
- `push_to_talk` - hold the shortcut, release to stop and process

Push-to-talk is implemented in `HotkeyManagerBase._dispatch_record` /
`_note_key_released`; every platform listener calls `_note_key_released` from
its own key-release handler. The buttons in the main window always toggle,
whichever mode is selected.

### Settings Dialog (`utils/config_dialog.py`)

Six categories, listed in `ConfigDialog.CATEGORIES`: Recording, Output &
Clipboard, AI Models, Appearance, History & Storage, System. Panels are
composed from `_section_*` methods, so moving a setting between categories is
moving one line. `_panel(title)` returns a scrollable body to fill.

Settings that also appear on a menu (dark mode, auto-refresh hotkeys, update
checks) share the menu's own variable and handler, so both places are one
switch. All tk variables are created and loaded up front; only widgets are
built lazily, and anything reading a widget must go through `_alive()` -
`hasattr` stays true after a panel is destroyed.

### Status Line States (`UIManager.set_status`)

Callers name a semantic state - `idle`, `processing`, `warning`, `success`,
`recording`, `error` - rather than a colour, so "in progress" cannot drift
back to the success green. Processing pulses amber and counts its seconds;
`warning` is the same amber without the pulse. Legacy colour names still map
through `_LEGACY_STATUS_STATES`. Any fixed status string must be listed in
`STATUS_MSGIDS` so a language change can re-translate it from its msgid.

### Dialog Conventions (`utils/dialog_utils.py`)

- `position_dialog(window, w, h, parent)` - centres on the parent when it can
  be trusted, else on screen, always clamped fully on-screen.
- `bind_dialog_keys(window, on_cancel, on_accept)` - Escape cancels, Return
  activates the primary action (ignored while a `tk.Text` has focus).
- `focus_first(widget)` - put the caret in the first field.

Routine confirmations use `ui_manager.show_toast()`, not a modal: every modal
steals focus from the app the user is dictating into.

### Clipboard Handling
Auto-paste simulates the paste shortcut, so the text has to be on the clipboard
first and the write is verified before the keystroke is sent. When "Copy to
clipboard" is off, the previous clipboard contents are restored shortly
afterwards (`behavior.restore_clipboard`), and never when the user has copied
something else in the meantime.

### History
`self.history` is a list of entry dicts (`text`, `timestamp`, `mode`, `prompt`,
`duration`), persisted as `{"version": 2, "entries": [...]}`. Plain-string
histories written by older versions still load. `utils/history_dialog.py`
provides the searchable browser.

### Theming (`utils/theme/`)
Centralized theming module with platform-aware HiDPI support. Uses Sun Valley ttk theme (`sv_ttk`) with custom styling.

**Module Structure:**
| File | Purpose |
|------|---------|
| `colors.py` | `ThemeColors` (dark) and `LightThemeColors`, plus the `theme_colors()` accessor |
| `fonts.py` | `FontProvider` with platform-specific font sizes (base + HiDPI per platform) |
| `spacing.py` | `SpacingProvider` for spacing, radius, button heights, border widths |
| `windows.py` | `WindowSizeProvider` for dialog dimensions per platform/HiDPI mode |

**Usage:**
```python
from utils.theme import (
    get_font, get_font_size,           # Font tuples and sizes
    get_spacing, get_radius,            # Padding and corner radius
    get_button_height, get_border_width, # Button dimensions
    get_window_size,                    # Dialog sizes
    theme_colors,                       # Active palette (dark or light)
    set_theme_mode,                     # Select the palette
)

# Examples
font = get_font('md', 'bold')           # ("Segoe UI", 14, "bold") on Windows HiDPI
padding = get_spacing('md')             # 14 on HiDPI, 12 on base
width, height = get_window_size('main') # Platform/HiDPI-aware dimensions
fg = theme_colors().TEXT_PRIMARY        # Resolves per active theme
```

**Palettes:** `ThemeColors` (dark) and `LightThemeColors` define the same
attribute names. Read colours through `theme_colors()` rather than importing a
palette, so a theme switch reaches every widget. Both light and dark values
clear WCAG AA (4.5:1) against their backgrounds. `TEXT_ON_ACCENT` and the
`BUTTON_*` tokens are deliberately theme-independent: they sit on saturated
fills that are identical in both themes.

**Initialization:** Call `init_theme(is_hidpi=True/False)` after Tk root is created, before UI setup.

**Font size keys:** `xxs`, `xs`, `sm`, `md`, `lg`, `xl`, plus semantic names like `nav_arrow`, `copy_link`, `menu_button`

**Legacy:** `ModernTheme` in `ui_manager.py` proxies colour lookups to the
active palette via a metaclass, so existing `self.theme.COLOUR` call sites are
theme-aware without change. Colour attributes must NOT be defined on the class
- Python would resolve them before `__getattr__` and freeze them at import.

## Key Technical Notes

- **Thread safety**: All keyboard callbacks are marshaled to main Tkinter thread via `self.parent.after(0, ...)` to prevent UI glitches
- **Hotkey reliability**: Hotkeys can become unregistered after Windows lock/unlock - the app health-checks every 5s and refreshes after repeated failures, or every 2 minutes while minimised. Initial registration failure is surfaced in the status bar.
- **Transcription models**: Two types supported - `gpt` (default `gpt-transcribe`, also `gpt-4o-transcribe`/`gpt-4o-mini-transcribe`) and `whisper` (whisper-1) with different API parameters
- **Copy-editing model**: Defaults to `gpt-5.6-luna` via the Responses API with `reasoning.effort="low"`; older `gpt-5*` models use `effort="minimal"`, non-GPT-5 models use Chat Completions
- **Recording storage**: Configurable location - alongside app, AppData/config folder, or custom path
- **Linux/Wayland**: Global hotkeys have limited support under Wayland; X11 recommended for best results
- **HiDPI**: Platform-specific scaling via `utils/theme/` module; explicit pixel values per platform (Windows, Linux, macOS) for fonts, spacing, and window sizes

### Internationalization (`utils/i18n.py`)

The app uses Python's standard `gettext` module for translations.

**Module Structure:**
- `utils/i18n.py` - Core i18n module with translation functions and language management
- `locale/` - Translation files organized by language code (e.g., `locale/fr/LC_MESSAGES/quickwhisper.po`)
- `tools/i18n_tools.py` - Script for extracting strings and managing translations
- `tools/compile_mo.py` - Pure Python .po to .mo compiler (no external dependencies)

**Supported Languages:**
- `en` - English (default)
- `fr` - French
- `de` - German
- `es` - Spanish
- `zh_CN` - Chinese (Simplified)
- `ar` - Arabic
- `ja` - Japanese
- `ko` - Korean
- `ru` - Russian
- `pt` - Portuguese

`utils.i18n.SUPPORTED_LANGUAGES` is the single source of truth; `tools/i18n_tools.py`
derives its language list from it.

**Usage:**
```python
from utils.i18n import _, _n, set_language, get_current_language

# Simple translation
label = _("Save Changes")

# Plural form (not currently used extensively)
msg = _n("1 file", "{n} files", count).format(n=count)

# Change language at runtime (triggers UI refresh)
set_language("fr")
```

**Key Functions:**
| Function | Purpose |
|----------|---------|
| `_(text)` | Translate a string |
| `_n(singular, plural, n)` | Translate with plural forms |
| `init_i18n(mode, lang)` | Initialize i18n at startup |
| `set_language(lang_code, refresh_ui=True)` | Change language and refresh UI |
| `register_refresh_callback(fn)` | Register callback for language changes |
| `get_available_languages()` | Get languages with compiled .mo files |

**Adding New Strings:**
1. Wrap UI strings with `_()` in Python code (`_n()` for plurals - `compile_mo.py`
   emits proper plural catalogues, and its output is verified to match GNU
   `msgfmt`)
2. Run `python3 tools/i18n_tools.py extract` to update `.pot` template
3. Run `python3 tools/i18n_tools.py update` to merge into existing `.po` files
4. Translate the new strings in each `.po` file
5. Run `python3 tools/compile_mo.py` to compile `.mo` files

Entries `msgmerge` marks `#, fuzzy` are guesses from a similar string and are
frequently wrong. `compile_mo.py` excludes them (matching gettext's own
`msgfmt`), so they fall back to English until a translator confirms them.

**Runtime Language Switching:**
Language changes take effect immediately without restart. The i18n module uses a callback registry to notify UI components when the language changes - menus are rebuilt and the UIManager's `refresh_translations()` method updates widget text.
