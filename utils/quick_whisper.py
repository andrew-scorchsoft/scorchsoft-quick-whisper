import tkinter as tk
from tkinter import ttk, messagebox, Menu
import threading
import pyaudio
import wave
import os
import sys
import openai
import pyperclip
import webbrowser
import json
import pyttsx3
from tkinter import filedialog
import customtkinter as ctk
from PIL import Image, ImageTk 
from openai import OpenAI
from dotenv import load_dotenv, dotenv_values, set_key
from pathlib import Path
from audioplayer import AudioPlayer
import keyboard  # For auto-paste functionality
from pystray import Icon as icon, MenuItem as item, Menu as menu
import platform
import time

from utils.tooltip import ToolTip
from utils.adjust_models_dialog import AdjustModelsDialog
from utils.manage_prompts_dialog import ManagePromptsDialog
from utils.hotkey_manager import HotkeyManager
from utils.audio_manager import AudioManager
from utils.tts_manager import TTSManager
from utils.ui_manager import UIManager


class QuickWhisper(tk.Tk):
    def __init__(self):
        super().__init__()

        self.version = "1.9.0"

        self.is_mac = platform.system() == 'Darwin'

        self.title(f"Quick Whisper by Scorchsoft.com (Speech to Copy Edited Text) - v{self.version}")

        # Initialize prompts
        self.prompts = self.load_prompts()  # Assuming you have a method to load prompts

        icon_path = self.resource_path("assets/icon-32.png")
        self.iconphoto(False, tk.PhotoImage(file=icon_path))
        self.iconbitmap(self.resource_path("assets/icon.ico"))

        # Set window size
        window_width = 600
        window_height = 700
        
        # Get screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Calculate center position
        center_x = int((screen_width - window_width) / 2)
        center_y = int((screen_height - window_height) / 2)
        
        # Set window geometry
        self.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
        self.resizable(False, False)
        self.banner_visible = True
        # Initial model settings
        self.transcription_model = "gpt-4o-transcribe"
        self.transcription_model_type = "gpt"  # Can be "gpt" or "whisper"
        self.ai_model = "gpt-4o"
        self.whisper_language = "auto"
        self.last_trancription = "NO LATEST TRANSCRIPTION"
        self.last_edit = "NO LATEST EDIT"

        self.load_env_file()
        self.api_key = self.get_api_key()
        if not self.api_key:
            messagebox.showerror("API Key Missing", "Please set your OpenAI API Key in config/.env or input it now.")
            self.destroy()
            return

        openai.api_key = self.api_key
        self.client = OpenAI(api_key=self.api_key)
        self.selected_device = tk.StringVar()
        self.auto_copy = tk.BooleanVar(value=True)
        self.auto_paste = tk.BooleanVar(value=True)
        self.history = []  # Stores up to 50 items of transcription or edited text
        self.history_index = -1  # -1 indicates no history selected yet
        self.max_history_length = 10000
        self.current_button_mode = "transcribe" # "transcribe" or "edit"
        self.tmp_dir = Path.cwd() / "tmp"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        # Define helper method for environment variables before initializing managers
        self._env_get = lambda key, default=None: os.getenv(key, default)
        # Initialize the managers
        self.hotkey_manager = HotkeyManager(self)
        self.audio_manager = AudioManager(self)
        self.tts_manager = TTSManager(self)
        self.ui_manager = UIManager(self)
        
        # Register hotkeys
        self.hotkey_manager.register_hotkeys()

        self.create_menu()
        
        # Create UI widgets
        self.ui_manager.create_widgets()

        # Hide the banner on load if HIDE_BANNER is set to true in .env
        if self.hide_banner_on_load:
            self.toggle_banner()

        self.set_default_prompt()
        
        # Load selected prompt from .env if it exists
        env_prompt = os.getenv("SELECTED_PROMPT")
        if env_prompt:
            if env_prompt == "Default":
                self.current_prompt_name = env_prompt
            elif env_prompt in self.prompts:
                self.current_prompt_name = env_prompt
            else:
                messagebox.showwarning("Prompt Not Found", 
                    f"Selected prompt '{env_prompt}' not found. Using default prompt.")
                self.current_prompt_name = "Default"

        # After loading the prompt from env, update the model label
        self.update_model_label()

        # Add binding for window state changes
        self.bind('<Unmap>', self._handle_minimize)
        self.bind('<Map>', self._handle_restore)
        self.was_minimized = False

    # Load environment variables from config/.env
    def load_env_file(self):

        env_path = Path("config") / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)

        # Check the HIDE_BANNER setting and set initial visibility
        self.hide_banner_on_load = os.getenv("HIDE_BANNER", "false").lower() == "true"

        # Overwrite transcription model if set
        transcription_model = os.getenv("TRANSCRIPTION_MODEL")
        if transcription_model and transcription_model.strip():
            self.transcription_model = transcription_model
            print(f"Loaded transcription model from env: '{transcription_model}'")
        else:
            print(f"Using default transcription model: '{self.transcription_model}'")

        # Overwrite transcription model type if set
        transcription_model_type = os.getenv("TRANSCRIPTION_MODEL_TYPE")
        if transcription_model_type and transcription_model_type.strip():
            self.transcription_model_type = transcription_model_type
            print(f"Loaded model type from env: '{transcription_model_type}'")
        elif "gpt" in self.transcription_model.lower():
            self.transcription_model_type = "gpt"
            print(f"Determined model type from name: '{self.transcription_model_type}'")
        else:
            self.transcription_model_type = "whisper"
            print(f"Set default model type: '{self.transcription_model_type}'")

        # Overwrite AI model if set
        ai_model = os.getenv("AI_MODEL")
        if ai_model:
            self.ai_model = ai_model

        # Load whisper language setting
        whisper_language = os.getenv("WHISPER_LANGUAGE")
        if whisper_language:
            self.whisper_language = whisper_language

        # Load keyboard shortcuts with defaults
        self.shortcuts = {
            'record_edit': os.getenv('SHORTCUT_RECORD_EDIT', 'win+j' if not self.is_mac else 'command+j'),
            'record_transcribe': os.getenv('SHORTCUT_RECORD_TRANSCRIBE', 'win+ctrl+j' if not self.is_mac else 'command+ctrl+j'),
            'cancel_recording': os.getenv('SHORTCUT_CANCEL_RECORDING', 'win+x' if not self.is_mac else 'command+x'),
            'cycle_prompt_back': os.getenv('SHORTCUT_CYCLE_PROMPT_BACK', 'alt+left' if not self.is_mac else 'command+['),
            'cycle_prompt_forward': os.getenv('SHORTCUT_CYCLE_PROMPT_FORWARD', 'alt+right' if not self.is_mac else 'command+]')
        }
        
        # Schedule UI update and hotkey registration after main window is initialized
        def after_init():
            # Update UI with loaded shortcuts
            self.update_shortcut_displays()
            # Register the loaded shortcuts
            self.force_hotkey_refresh()

        # Delay slightly to ensure UI is ready
        self.after(100, after_init)

    def get_api_key(self):
        """Get the OpenAI API key, prompting if not found."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:  # Prompt for the key if it's not set
            api_key = self.openai_key_dialog()  # Call custom dialog
            if api_key:
                self.save_api_key(api_key)
            else:
                messagebox.showwarning("API Key Missing", "OpenAI API key is required to continue.")
                self.destroy()  # Exit if no key is provided
        return api_key
    
    def change_api_key(self):
        """Open the dialog to change the OpenAI API key."""
        new_key = self.openai_key_dialog()
        if new_key:
            self.save_api_key(new_key)
            self.api_key = new_key
            messagebox.showinfo("API Key Updated", "The OpenAI API Key has been updated successfully.")
        else:
            messagebox.showinfo("Update Cancelled", "The OpenAI API Key was not changed.")


    def openai_key_dialog(self):
        """Custom dialog for entering a new OpenAI API key with guidance link."""
        dialog = tk.Toplevel(self)
        dialog.title("Enter New OpenAI API Key")
        dialog_width = 400
        dialog_height = 200
        
        # Calculate center position relative to parent
        position_x = self.winfo_x() + (self.winfo_width() - dialog_width) // 2
        position_y = self.winfo_y() + (self.winfo_height() - dialog_height) // 2
        
        dialog.geometry(f"{dialog_width}x{dialog_height}+{position_x}+{position_y}")
        dialog.resizable(False, False)

        # Label for instructions
        instruction_label = ttk.Label(dialog, text="Please enter your new OpenAI API Key below:")
        instruction_label.pack(pady=(10, 5))

        # Entry field for the API key
        api_key_entry = ttk.Entry(dialog, show='*', width=50)
        api_key_entry.pack(pady=(5, 10))

        # Link to guidance
        link_label = tk.Label(dialog, text="How to obtain an OpenAI API key", fg="blue", cursor="hand2", font=("Arial", 9))
        link_label.pack()
        link_label.bind("<Button-1>", lambda e: webbrowser.open("https://scorchsoft.com/howto-get-openai-api-key"))

        # Variable to store the API key input
        entered_key = None

        # Save action to capture API key input
        def save_and_close():
            nonlocal entered_key  # Use nonlocal to modify the outer variable
            entered_key = api_key_entry.get().strip()
            if entered_key:
                dialog.destroy()  # Close dialog after saving input
            else:
                messagebox.showwarning("Input Required", "Please enter a valid API key.")

        # Buttons for saving and cancelling
        save_button = ttk.Button(dialog, text="Save", command=save_and_close)
        save_button.pack(pady=(10, 5))
        cancel_button = ttk.Button(dialog, text="Cancel", command=dialog.destroy)
        cancel_button.pack(pady=(0, 10))

        # Set focus to the entry field and make dialog modal
        api_key_entry.focus()
        dialog.transient(self)
        dialog.grab_set()
        self.wait_window(dialog)

        # Return the entered key or None if cancelled
        return entered_key if entered_key else None


    def save_api_key(self, api_key):
        """Save the API key to config/.env without overwriting existing variables."""
        config_dir = Path("config")
        config_dir.mkdir(parents=True, exist_ok=True)
        env_path = config_dir / ".env"

        # Read existing settings to preserve them
        env_vars = {}
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if line.strip():
                        key, val = line.strip().split('=', 1)
                        env_vars[key] = val

        # Update or add the OPENAI_API_KEY
        env_vars["OPENAI_API_KEY"] = api_key
        env_vars["HIDE_BANNER"] = self.hide_banner_on_load

        # Write back all variables
        with open(env_path, 'w') as f:
            for key, val in env_vars.items():
                f.write(f"{key}={val}\n")

    def create_menu(self):
        self.menubar = Menu(self)
        self.config(menu=self.menubar)

        # File menu
        file_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Save Session History", command=self.save_session_history)

        # Settings menu
        settings_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Change API Key", command=self.change_api_key)
        settings_menu.add_command(label="Adjust AI Models", command=self.adjust_models)
        settings_menu.add_command(label="Manage Prompts", command=self.manage_prompts)
        settings_menu.add_separator()
        settings_menu.add_command(label="Check Keyboard Shortcuts", command=self.check_keyboard_shortcuts)

        # Actions Menu (combining Play and Copy menus)
        actions_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Actions", menu=actions_menu)
        
        # Recording actions group
        actions_menu.add_command(
            label="Record & Edit", 
            command=lambda: self.toggle_recording("edit"),
            accelerator=self.shortcuts['record_edit']
        )
        actions_menu.add_command(
            label="Record & Transcribe", 
            command=lambda: self.toggle_recording("transcribe"),
            accelerator=self.shortcuts['record_transcribe']
        )
        actions_menu.add_command(
            label="Cancel Recording", 
            command=self.cancel_recording,
            accelerator=self.shortcuts['cancel_recording']
        )
        actions_menu.add_separator()
        
        # Retry and copy actions group
        actions_menu.add_command(
            label="Retry Last Recording", 
            command=self.retry_last_recording
        )
        actions_menu.add_separator()
        
        # Copy actions group
        actions_menu.add_command(
            label="Copy Last Transcript", 
            command=self.copy_last_transcription
        )
        actions_menu.add_command(
            label="Copy Last Edit", 
            command=self.copy_last_edit
        )
        actions_menu.add_separator()
        
        # Prompt navigation group
        actions_menu.add_command(
            label="Previous Prompt", 
            command=self.cycle_prompt_backward,
            accelerator=self.shortcuts['cycle_prompt_back']
        )
        actions_menu.add_command(
            label="Next Prompt", 
            command=self.cycle_prompt_forward,
            accelerator=self.shortcuts['cycle_prompt_forward']
        )

        # Help menu
        self.help_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Help", menu=self.help_menu)
    
        self.help_menu.add_command(label="Hide Banner", command=self.toggle_banner)
        self.help_menu.add_command(label="Terms of Use and Licence", command=self.show_terms_of_use)
        self.help_menu.add_command(label="Version", command=self.show_version)

    def check_keyboard_shortcuts(self):
        """Test keyboard shortcuts and show status."""
        self.hotkey_manager.check_keyboard_shortcuts()

    def toggle_recording(self, mode="transcribe"):
        if not self.audio_manager.recording:
            # Set globally so the app knows when recording stops whether 
            # transcript or edit mode was selected
            self.current_button_mode = mode
            print(f"\nAbout to start recording. mode = {mode}")
            self.start_recording()
        else:
            print(f"About to stop recording. mode = {self.current_button_mode}")
            self.stop_recording()

    def start_recording(self):
        """Start audio recording."""
        if self.audio_manager.start_recording():
            # Recording started successfully
            self.hotkey_manager.update_shortcut_displays()

    def stop_recording(self):
        """Stop recording and process audio."""
        audio_file = self.audio_manager.stop_recording()
        if audio_file:
            # Start transcription in a separate thread
            threading.Thread(target=self.transcribe_audio).start()
            
    def cancel_recording(self):
        """Cancel the current recording without processing."""
        self.audio_manager.cancel_recording()
        self.hotkey_manager.update_shortcut_displays()
    
    def retry_last_recording(self):
        """Retry processing the last recording."""
        self.audio_manager.retry_last_recording()

    def transcribe_audio(self):
        file_path = self.audio_manager.audio_file

        try:
            self.ui_manager.set_status("Processing - Transcript...", "green")

            with open(str(file_path), "rb") as audio_file:

                print(f"Transcription Mode: '{self.transcription_model}' | Type: '{self.transcription_model_type}'")
                
                # Different API call based on model type
                if not self.transcription_model or not self.transcription_model.strip():
                    messagebox.showerror("Configuration Error", 
                                        "Transcription model name is empty. Please check your settings.")
                    raise ValueError("Empty transcription model name")
                
                if self.transcription_model_type == "gpt":
                    # GPT-4o speech-to-text API
                    print(f"Using GPT API with model: {self.transcription_model}")
                    try:
                        transcription = self.client.audio.transcriptions.create(
                            file=audio_file,
                            model=self.transcription_model,
                            language=None if self.whisper_language == "auto" else self.whisper_language,
                            response_format="text"
                        )
                        transcription_text = transcription
                    except Exception as e:
                        print(f"Error with GPT transcription: {e}")
                        raise
                else:
                    # Traditional Whisper API
                    print(f"Using Whisper API with model: {self.transcription_model}")
                    try:
                        transcription = self.client.audio.transcriptions.create(
                            file=audio_file,
                            model=self.transcription_model,
                            language=None if self.whisper_language == "auto" else self.whisper_language,
                            response_format="verbose_json"
                        )
                        # Retrieve the transcription text correctly
                        transcription_text = transcription.get("text", "") if isinstance(transcription, dict) else transcription.text
                    except Exception as e:
                        print(f"Error with Whisper transcription: {e}")
                        raise

            self.add_to_history(transcription_text)
            self.last_trancription = transcription_text

            # Process transcription with or without GPT as per the checkbox setting
            if self.current_button_mode == "edit":
                print("AI Editing Transcription")

                # set input box to transcription text first, just incase there is a failure
                self.ui_manager.transcription_text.delete("1.0", tk.END)
                self.ui_manager.transcription_text.insert("1.0", transcription_text)

                # Then GPT edit that transcribed text and insert
                self.ui_manager.set_status("Processing - AI Editing...", "green")

                # AI Edit the transcript
                edited_text = self.process_with_gpt_model(transcription_text)
                self.add_to_history(edited_text)
                self.last_edit = edited_text
                play_text = edited_text

                self.ui_manager.transcription_text.delete("1.0", tk.END)
                self.ui_manager.transcription_text.insert("1.0", play_text)
            else:
                print("Outputting Raw Transcription Only")
                self.ui_manager.transcription_text.delete("1.0", tk.END)
                self.ui_manager.transcription_text.insert("1.0", transcription_text)
                play_text = transcription_text


            if self.auto_copy.get():
                self.auto_copy_text(play_text)

            if self.auto_paste.get():
                self.auto_paste_text(play_text)

            print("Transcription Complete: The audio has been transcribed and the text has been placed in the input area.")
            # Play stop recording sound
            threading.Thread(target=lambda: self.play_sound("assets/double-pop-down.wav")).start()

        except Exception as e:
            # Play failure sound
            threading.Thread(target=lambda: self.play_sound("assets/wrong-short.wav")).start()

            print(f"Transcription error: An error occurred during transcription: {str(e)}")
            self.ui_manager.set_status("Error during transcription", "red")

            messagebox.showerror("Transcription Error", f"An error occurred while Transcribing: {e}")

        finally:
            self.ui_manager.set_status("Idle", "blue")

    def copy_last_transcription(self):
        try:
            # Copy text to clipboard
            pyperclip.copy(self.last_trancription)

        except Exception as e:
            messagebox.showerror("Auto-Copy Error", f"Failed to copy the transcription to clipboard: {e}")
    
    def copy_last_edit(self):
        try:
            # Copy text to clipboard
            pyperclip.copy(self.last_edit)

        except Exception as e:
            messagebox.showerror("Auto-Copy Error", f"Failed to copy the last edit to clipboard: {e}")
        
    def auto_copy_text(self, text):
        try:
            # Copy text to clipboard
            pyperclip.copy(text)

        except Exception as e:
            messagebox.showerror("Auto-Copy Error", f"Failed to auto-copy the transcription: {e}")

    def auto_paste_text(self, text):
        try:
            # Use OS-specific keyboard shortcuts
            if self.is_mac:
                keyboard.press_and_release('command+v')
            else:
                keyboard.press_and_release('ctrl+v')
        except Exception as e:
            messagebox.showerror("Auto-Paste Error", f"Failed to auto-paste the transcription: {e}")


    def process_with_gpt_model(self, text):
        try:
            # Replace the hardcoded system prompt with the selected one
            system_prompt = self.get_system_prompt()
            
            user_prompt = "Here is the transcription \r\n<transcription>\r\n" + text + "\r\n</transcription>\r\n"

            print(f"About to process with AI Model {self.ai_model}")
            response = self.client.chat.completions.create(
                model=self.ai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=8000
            )
            gpt_text = response.choices[0].message.content
            return gpt_text
        except Exception as e:
            # Play failure sound
            threading.Thread(target=lambda: self.play_sound("assets/wrong-short.wav")).start()
            messagebox.showerror("GPT Processing Error", f"An error occurred while processing with GPT: {e}")
            return None
        

    def resource_path(self, relative_path):
        """Get the absolute path to the resource, works for both development and PyInstaller environments."""
        try:
            base_path = sys._MEIPASS
        except AttributeError:
            base_path = os.path.dirname(os.path.abspath(sys.argv[0]))

        # Handle icon files differently for Mac
        if self.is_mac and relative_path.endswith('.ico'):
            # Use .png version instead of .ico for Mac
            relative_path = relative_path.replace('.ico', '.png')

        abs_path = os.path.join(base_path, relative_path)
        return abs_path

    def on_closing(self):
        """Clean up resources before closing."""
        # Clean up TTS
        self.tts_manager.cleanup()
        
        # Clean up hotkeys
        for hotkey in self.hotkey_manager.hotkeys:
            try:
                keyboard.remove_hotkey(hotkey)
            except:
                pass
        self.hotkey_manager.hotkeys.clear()
        
        # Clean up audio
        self.audio_manager.cleanup()
        
        self.destroy()

    def play_sound(self, sound_file):
        """Play sound using audio manager."""
        self.audio_manager.play_sound(sound_file)

    def show_terms_of_use(self):
        # Create a new window to display the terms of use
        instruction_window = tk.Toplevel(self)
        instruction_window.title("Terms of Use")
        
        # Set size and center the window
        window_width = 800
        window_height = 700
        position_x = self.winfo_x() + (self.winfo_width() - window_width) // 2
        position_y = self.winfo_y() + (self.winfo_height() - window_height) // 2
        instruction_window.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")

        # Get the path to the LICENSE.md file using the resource_path method
        license_path = self.resource_path("assets/LICENSE.md")

        # Attempt to read the content of the LICENSE.md file
        try:
            with open(license_path, "r", encoding="utf-8") as file:
                license_content = file.read()
        except FileNotFoundError:
            license_content = "License file not found. Please ensure the LICENSE.md file exists in the application directory."
        except PermissionError:
            license_content = "Permission denied. Please ensure the script has read access to LICENSE.md."
        except UnicodeDecodeError as e:
            license_content = f"Error reading license file due to encoding issue: {e}"
        except Exception as e:
            license_content = f"An unexpected error occurred while reading the license file: {e}"

        # Create a frame to contain the text widget and scrollbar
        frame = ttk.Frame(instruction_window)
        frame.pack(fill=tk.BOTH, expand=True)

        # Add a scrolling text widget to display the license content
        text_widget = tk.Text(frame, wrap=tk.WORD)
        text_widget.insert(tk.END, license_content)
        text_widget.config(state=tk.DISABLED)  # Make the text read-only
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add a vertical scrollbar
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text_widget.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure the scrollbar to work with the text widget
        text_widget.config(yscrollcommand=scrollbar.set)

        # Add a button to close the window
        ttk.Button(instruction_window, text="Close", command=instruction_window.destroy).pack(pady=(10, 0))

    def show_version(self):
        instruction_window = tk.Toplevel(self)
        instruction_window.title("App Version")
        instruction_window.geometry("300x150")
        
        # Center the window
        window_width = 300
        window_height = 150
        position_x = self.winfo_x() + (self.winfo_width() - window_width) // 2
        position_y = self.winfo_y() + (self.winfo_height() - window_height) // 2
        instruction_window.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")
        
        instructions = f"""Version {self.version}\n\n App by Scorchsoft.com"""
        
        tk.Label(instruction_window, text=instructions, justify=tk.LEFT, wraplength=280).pack(padx=10, pady=10)
        
        # Add a button to close the window
        ttk.Button(instruction_window, text="Close", command=instruction_window.destroy).pack(pady=(10, 0))

    def add_to_history(self, text):
        # Append new text to the end of the list
        self.history.append(text)

        # Enforce max history length by removing the oldest element if necessary
        if len(self.history) > self.max_history_length:
            self.history.pop(0)  # Removes the oldest (first) item in the array

        # Update the index to the last entry (most recent)
        self.history_index = len(self.history) - 1
        self.ui_manager.update_transcription_text()
        self.ui_manager.update_navigation_buttons()
        
    def navigate_right(self):
        self.history_index -= 1
        self.ui_manager.update_transcription_text()
        self.ui_manager.update_navigation_buttons()

    def navigate_left(self):
        self.history_index += 1
        self.ui_manager.update_transcription_text()
        self.ui_manager.update_navigation_buttons()

    def go_to_first_page(self):
        self.history_index = len(self.history) - 1  # Set to most recent
        self.ui_manager.update_transcription_text()
        self.ui_manager.update_navigation_buttons()
    
    def save_session_history(self):
        if not self.history:
            messagebox.showinfo("No History", "There is no history to save.")
            return

        # Open a file save dialog
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")],
            title="Save Session History"
        )

        if not file_path:
            # User cancelled the save dialog
            return

        try:
            # Serialize history to JSON and save to file
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=4, ensure_ascii=False)

            messagebox.showinfo("Success", f"Session history saved successfully to {file_path}")
        except Exception as e:
            # Handle errors during the save process
            messagebox.showerror("Save Error", f"An error occurred while saving: {e}")

    def update_model_label(self):
        """Update the model label to include the prompt name and language setting."""
        self.ui_manager.update_model_label()

    def toggle_banner(self):
        """Toggle the visibility of the banner image."""
        self.ui_manager.toggle_banner()

    def load_prompts(self):
        """Load custom prompts from JSON file."""
        prompts_file = Path("config") / "prompts.json"
        if prompts_file.exists():
            try:
                with open(prompts_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading prompts: {e}")
        return {}

    def save_prompts(self, prompts):
        """Save custom prompts to JSON file."""
        prompts_file = Path("config") / "prompts.json"
        try:
            # Ensure config directory exists
            prompts_file.parent.mkdir(parents=True, exist_ok=True)
            with open(prompts_file, 'w', encoding='utf-8') as f:
                json.dump(prompts, f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save prompts: {e}")

    def save_prompt_to_env(self, prompt_name):
        """Save selected prompt to .env file."""
        config_dir = Path("config")
        config_dir.mkdir(parents=True, exist_ok=True)
        env_path = config_dir / ".env"

        # Read existing settings
        env_vars = {}
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            key, val = line.strip().split('=', 1)
                            env_vars[key] = val
                        except ValueError:
                            continue  # Skip malformed lines

        # Update or add the SELECTED_PROMPT
        env_vars["SELECTED_PROMPT"] = prompt_name

        # Write back all variables
        with open(env_path, 'w') as f:
            for key, val in env_vars.items():
                f.write(f"{key}={val}\n")

    def get_system_prompt(self):
        """Get the current system prompt based on selection."""
        if self.current_prompt_name == "Default":
            return self.default_system_prompt
        return self.prompts.get(self.current_prompt_name, self.default_system_prompt)
    
    
    def set_default_prompt(self):
        """Initialize default prompt and prompts dictionary."""
        try:
            default_prompt_path = self.resource_path("assets/DefaultPrompt.md")
            with open(default_prompt_path, 'r', encoding='utf-8') as f:
                self.default_system_prompt = f.read()
        except Exception as e:
            print(f"Error loading default prompt: {e}")
            # Fallback to a basic prompt if file can't be loaded
            self.default_system_prompt = "You are an expert Copy Editor. When provided with text, provide a cleaned-up copy-edited version of that text in response."
            
        self.prompts = self.load_prompts()
        self.current_prompt_name = "Default"

    def _handle_minimize(self, event):
        """Track when window is minimized"""
        self.was_minimized = True

    def _handle_restore(self, event):
        """Handle window restore from minimized state"""
        if self.was_minimized:
            self.was_minimized = False
            print("Window restored from minimized state - refreshing hotkeys")
            self.hotkey_manager.force_hotkey_refresh()

    def manage_prompts(self):
        ManagePromptsDialog(self)

    def adjust_models(self):
        AdjustModelsDialog(self)

    def show_prompt_notification(self, message):
        """Show a temporary notification message in the status label and speak the prompt name."""
        # Create a clean version of the message for speech
        speech_message = message.replace("Prompt: ", "")
        
        # Use text-to-speech for Windows
        if platform.system() == 'Windows':
            self.tts_manager.speak_text(speech_message)

    def cycle_prompt_forward(self):
        """Cycle to the next prompt in the list."""
        # Create list of prompt names including "Default"
        prompt_names = ["Default"] + list(self.prompts.keys())
        
        # Find current index
        try:
            current_index = prompt_names.index(self.current_prompt_name)
        except ValueError:
            current_index = 0  # Default to the first prompt if not found
        
        # Calculate next index (cycle back to start if at end)
        next_index = (current_index + 1) % len(prompt_names)
        
        # Update current prompt
        self.current_prompt_name = prompt_names[next_index]
        self.save_prompt_to_env(self.current_prompt_name)
        
        # Update UI
        self.update_model_label()
        
        # Show notification and trigger text-to-speech
        self.show_prompt_notification(f"Prompt: {self.current_prompt_name}")

    def cycle_prompt_backward(self):
        """Cycle to the previous prompt in the list."""
        # Create list of prompt names including "Default"
        prompt_names = ["Default"] + list(self.prompts.keys())
        
        # Find current index
        try:
            current_index = prompt_names.index(self.current_prompt_name)
        except ValueError:
            current_index = 0  # Default to the first prompt if not found
        
        # Calculate previous index (cycle to end if at start)
        prev_index = (current_index - 1) % len(prompt_names)
        
        # Update current prompt
        self.current_prompt_name = prompt_names[prev_index]
        self.save_prompt_to_env(self.current_prompt_name)
        
        # Update UI
        self.update_model_label()
        
        # Show notification and trigger text-to-speech
        self.show_prompt_notification(f"Prompt: {self.current_prompt_name}")
