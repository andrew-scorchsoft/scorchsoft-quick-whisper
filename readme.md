# Scorchsoft QuickWhisper

You can find more information about Quick Whisper here:
[Scorchsoft Quick Whisper - Free Speech-to-Copy-Edited-Text AI App for Desktop](https://www.scorchsoft.com/blog/speech-to-copyedited-text-app/)

QuickWhisper is a user-friendly, voice-to-text transcription app that leverages OpenAI's Whisper model for accurate audio transcription. With QuickWhisper, users can start recording their voice, automatically transcribe it to text, copy it to the clipboard, and optionally paste it into other applications. Additionally, the transcription text can be processed through GPT-4 for a polished, copy-edited output.

## Features

- **Simple Recording & Transcription**: Quickly record audio and transcribe it to text with a single click or a hotkey (`Ctrl+Alt+J` for edit, `Ctrl+Alt+Shift+J` for transcription).
- **Auto Copy & Paste**: Automatically copy transcriptions to the clipboard and paste them into other applications if desired.
- **Optional GPT-4 Editing**: Enhance your transcriptions using GPT-4 for a polished, copy-edited text output.
- **Customizable Settings**: Enable or disable auto-copy and auto-paste, choose from available input devices, and toggle GPT-4 editing.

## Installation

1. Clone the repository or download the code to your local machine.

2. Ensure you have Python 3.x installed. Install the required dependencies with the following command:
    `pip install pystray pyaudio openai pyperclip python-dotenv pydub audioplayer keyboard customtkinter pyttsx3 packaging`


3. Place your OpenAI API key in a `.env` file located in the `config` folder or enter it directly in the app.

    **Example** `.env` file in `config/.env`:
    ```plaintext
    OPENAI_API_KEY=your_openai_api_key_here
    ```

    This is optional, if you don't define your key then the app will ask for it on first run

## Usage

1. Run the application:

    ```bash
    python quick_whisper.py
    ```

2. Select an input device, then press one of the recording buttons or use the hotkeys:
   - `Ctrl+Alt+J` for Record + AI Edit
   - `Ctrl+Alt+Shift+J` for Record + Transcript
   - `Win+X` to Cancel Recording

3. After recording, the app will transcribe the audio and display the text in the transcription area. The text can be automatically copied to the clipboard or pasted into other applications, depending on the settings.

4. Enable "Auto Copy-edit with GPT-4" for advanced text processing, allowing GPT-4 to edit the transcription for improved readability and structure.

## Configuration

QuickWhisper includes a configuration system that allows you to customize recording behavior. Access it via **Settings > Config**.

### Recording Location

Choose where audio recording files are saved:

- **Alongside application (recommended)**: Saves recordings in a `tmp` folder next to the application
- **In AppData folder**: Uses the OS-appropriate application data directory:
  - Windows: `%APPDATA%\QuickWhisper\recordings`
  - macOS: `~/Library/Application Support/QuickWhisper/recordings`
  - Linux: `~/.config/QuickWhisper/recordings`
- **Custom folder**: Specify any folder of your choice

### File Handling

Control how recording files are managed:

- **Overwrite the same file each time (default)**: Saves disk space by reusing the same filename
- **Save each recording with date/time in filename**: Creates unique files like `recording_20240101_143052.wav`
  - ⚠️ **Warning**: This option can consume significant disk space over time

All configuration settings are saved to the `config/.env` file and will persist between application restarts.

## Screenshot

![QuickWhisper Interface](assets/quick-whisper-v1-5-0.png)


## License

This project is licensed under the terms specified in the LICENSE.md file.

## Making an installer

Windows:
`python -m PyInstaller --onefile --windowed --add-data "assets;assets" --icon="assets/icon.ico" --hidden-import pystray._win32 --hidden-import PIL._tkinter_finder quick_whisper.py`

Windows with terminal:
`python -m PyInstaller --onefile --add-data "assets;assets" --icon="assets/icon.ico" --hidden-import pystray._win32 --hidden-import PIL._tkinter_finder quick_whisper.py`

Mac:
`pyinstaller --onefile --add-data "assets:assets" --hidden-import pystray._darwin --hidden-import PIL._tkinter_finder quick_whisper.py`

# About Scorchsoft

We can deliver your innovative, technically complex project, using the latest web and mobile application development technologies.
Scorchsoft develops online portals, applications, web and mobile apps, and AI projects. With over fourteen years experience working with hundreds of small, medium, and large enterprises, in a diverse range of sectors, we'd love to discover how we can apply our expertise to your project.

[Scorchsoft App Developers](https://www.scorchsoft.com/blog/speech-to-copyedited-text-app/)

## Mac-Specific Setup

For Mac users:
1. Install portaudio first:
   ```bash
   brew install portaudio
   ```

2. You may need to grant accessibility permissions to the app for keyboard shortcuts:
   - Go to System Preferences > Security & Privacy > Privacy > Accessibility
   - Add QuickWhisper to the list of allowed apps

3. The app uses Command (⌘) instead of Windows key for shortcuts:
   - ⌘+Alt+J: Record + AI Edit
   - ⌘+Alt+Shift+J: Record + Transcript
   - ⌘+X: Cancel Recording
