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

# Install dependencies
pip install -r requirements.txt

# Run the application
python quick_whisper.py

# Build standalone executable (PyInstaller)
pyinstaller quick_whisper.spec
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
| `HotkeyManager` | Global keyboard shortcuts via `keyboard` library, handles registration/refresh/verification |
| `UIManager` | All Tkinter widgets, Sun Valley theme (sv_ttk), custom `GradientButton` component |
| `ConfigManager` | JSON-based settings (`config/settings.json`) and encrypted credentials (`config/credentials.json`) |
| `TTSManager` | Text-to-speech for prompt name announcements (Windows only) |
| `TrayManager` | System tray icon via `pystray` |
| `VersionUpdateManager` | GitHub release checking |
| `SystemEventListener` | Windows session lock/unlock detection for hotkey refresh |

### Configuration
- `config/settings.json` - UI preferences, model settings, keyboard shortcuts, recording options
- `config/credentials.json` - Encrypted OpenAI API key (uses `cryptography` Fernet)
- Auto-migrates from legacy `.env` format

### Default Keyboard Shortcuts (Windows)
- `Ctrl+Alt+J` - Record + AI Edit
- `Ctrl+Alt+Shift+J` - Record + Transcribe only
- `Win+X` - Cancel recording
- `Alt+Left/Right` - Cycle through prompts

### Theming
Uses Sun Valley ttk theme (`sv_ttk`) with custom `ModernTheme` class defining Scorchsoft brand colors. Supports dark/light mode toggle.

## Key Technical Notes

- Hotkeys can become unregistered after Windows lock/unlock - the app has health checking and auto-refresh (every 30s when enabled)
- Transcription supports two model types: `gpt` (gpt-4o-transcribe) and `whisper` (whisper-1) with different API parameters
- All keyboard callbacks are marshaled to main Tkinter thread via `self.parent.after(0, ...)` to prevent UI glitches
- Recording files go to configurable location: alongside app, AppData, or custom path
