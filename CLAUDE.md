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
pyinstaller quick_whisper.spec
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
- Handles OpenAI API calls for transcription (`client.audio.transcriptions.create`) and AI editing (`client.responses.create` for GPT-5, `client.chat.completions.create` for others)
- Manages prompts (Default from `assets/DefaultPrompt.md`, custom from `config/prompts.json`)

### Manager Classes (in `utils/`)
| Manager | Purpose |
|---------|---------|
| `AudioManager` | PyAudio recording, WAV file handling, sound playback |
| `HotkeyManager` | Global hotkeys via `pynput`, delegates to platform-specific implementations |
| `UIManager` | All Tkinter widgets, Sun Valley theme (sv_ttk), custom `GradientButton` component |
| `ConfigManager` | JSON-based settings (`config/settings.json`) and encrypted credentials (`config/credentials.json`) |
| `TTSManager` | Text-to-speech for prompt name announcements |
| `TrayManager` | System tray icon via `pystray` |
| `VersionUpdateManager` | GitHub release checking |
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
- `Win+X` - Cancel recording
- `Alt+Left/Right` - Cycle through prompts

**macOS:**
- `Cmd+Alt+J` - Record + AI Edit
- `Cmd+Alt+Shift+J` - Record + Transcribe only
- `Cmd+X` - Cancel recording
- `Cmd+[/]` - Cycle through prompts

### Theming (`utils/theme/`)
Centralized theming module with platform-aware HiDPI support. Uses Sun Valley ttk theme (`sv_ttk`) with custom styling.

**Module Structure:**
| File | Purpose |
|------|---------|
| `colors.py` | `ThemeColors` class with Scorchsoft brand colors |
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
    ThemeColors,                        # Color constants
)

# Examples
font = get_font('md', 'bold')           # ("Segoe UI", 14, "bold") on Windows HiDPI
padding = get_spacing('md')             # 14 on HiDPI, 12 on base
width, height = get_window_size('main') # Platform/HiDPI-aware dimensions
```

**Initialization:** Call `init_theme(is_hidpi=True/False)` after Tk root is created, before UI setup.

**Font size keys:** `xxs`, `xs`, `sm`, `md`, `lg`, `xl`, plus semantic names like `nav_arrow`, `copy_link`, `menu_button`

**Legacy:** `ModernTheme` class in `ui_manager.py` delegates to `ThemeColors` for backward compatibility.

## Key Technical Notes

- **Thread safety**: All keyboard callbacks are marshaled to main Tkinter thread via `self.parent.after(0, ...)` to prevent UI glitches
- **Hotkey reliability**: Hotkeys can become unregistered after Windows lock/unlock - the app has health checking and auto-refresh (every 30s when enabled)
- **Transcription models**: Two types supported - `gpt` (gpt-4o-transcribe) and `whisper` (whisper-1) with different API parameters
- **Recording storage**: Configurable location - alongside app, AppData/config folder, or custom path
- **Linux/Wayland**: Global hotkeys have limited support under Wayland; X11 recommended for best results
- **HiDPI**: Platform-specific scaling via `utils/theme/` module; explicit pixel values per platform (Windows, Linux, macOS) for fonts, spacing, and window sizes
