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
from utils.config_manager import get_config
from pathlib import Path
from audioplayer import AudioPlayer
import keyboard  # For auto-paste functionality
import platform
import time
import ctypes
from ctypes import wintypes

from utils.tooltip import ToolTip
from utils.adjust_models_dialog import AdjustModelsDialog
from utils.manage_prompts_dialog import ManagePromptsDialog
from utils.config_dialog import ConfigDialog
from utils.hotkey_manager import HotkeyManager
from utils.audio_manager import AudioManager
from utils.tts_manager import TTSManager
from utils.ui_manager import UIManager
from utils.version_update_manager import VersionUpdateManager
from utils.system_event_listener import SystemEventListener
from utils.tray_manager import TrayManager


class QuickWhisper(tk.Tk):
    def __init__(self):
        super().__init__()

        self.version = "1.9.3"
        
        self.is_mac = platform.system() == 'Darwin'

        self.title(f"Quick Whisper by Scorchsoft.com (Speech to Copy Edited Text) - v{self.version}")

        # Initialize prompts
        self.prompts = self.load_prompts()  # Assuming you have a method to load prompts

        icon_path = self.resource_path("assets/icon-32.png")
        self.iconphoto(False, tk.PhotoImage(file=icon_path))
        self.iconbitmap(self.resource_path("assets/icon.ico"))

        # Set window size (slightly wider for modern UI)
        window_width = 640
        window_height = 720
        
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
        self.ai_model = "gpt-5-mini"
        self.whisper_language = "auto"
        self.last_trancription = "NO LATEST TRANSCRIPTION"
        self.last_edit = "NO LATEST EDIT"

        # Initialize auto hotkey refresh setting (default to True)
        self.auto_hotkey_refresh = tk.BooleanVar(value=True)

        self.load_config()
        self.api_key = self.get_api_key()
        if not self.api_key:
            messagebox.showerror("API Key Missing", "Please set your OpenAI API Key in config/credentials.json or input it now.")
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
        
        # Initialize recording directory based on settings
        self.update_recording_directory()
        
        # Define helper method for environment variables before initializing managers
        self._env_get = lambda key, default=None: os.getenv(key, default)
        # Initialize the managers
        self.hotkey_manager = HotkeyManager(self)
        self.audio_manager = AudioManager(self)
        self.tts_manager = TTSManager(self)
        self.ui_manager = UIManager(self)
        self.version_manager = VersionUpdateManager(self)
        self.system_event_listener = SystemEventListener(self)
        self.tray_manager = TrayManager(self)
        
        # Setup hotkey health checker
        self.setup_hotkey_health_checker()
        
        # Register hotkeys
        self.hotkey_manager.register_hotkeys()

        self.create_menu()
        
        # Create UI widgets
        self.ui_manager.create_widgets()

        # Hide the banner on load if hide_banner is set to true in settings
        if self.hide_banner_on_load:
            self.toggle_banner()

        self.set_default_prompt()
        
        # Load selected prompt from config if it exists
        saved_prompt = self.config_manager.selected_prompt
        if saved_prompt:
            if saved_prompt == "Default":
                self.current_prompt_name = saved_prompt
            elif saved_prompt in self.prompts:
                self.current_prompt_name = saved_prompt
            else:
                messagebox.showwarning("Prompt Not Found", 
                    f"Selected prompt '{saved_prompt}' not found. Using default prompt.")
                self.current_prompt_name = "Default"

        # After loading the prompt from env, update the model label
        self.update_model_label()

        # Add binding for window state changes
        self.bind('<Unmap>', self._handle_minimize)
        self.bind('<Map>', self._handle_restore)
        self.was_minimized = False

        # Ensure default bindings for common edit actions in Text and Entry widgets
        self._install_text_bindings()
        
        # Initialize system tray
        self.setup_system_tray()
        
        # Check for updates in a separate thread
        self.version_manager.start_check()

    # Load configuration from JSON files
    def load_config(self):
        """Load configuration from settings.json and credentials.json files."""
        self.config_manager = get_config()

        # Load UI settings
        self.hide_banner_on_load = self.config_manager.hide_banner

        # Load auto hotkey refresh setting
        self.auto_hotkey_refresh.set(self.config_manager.auto_hotkey_refresh)

        # Load model settings
        self.transcription_model = self.config_manager.transcription_model
        print(f"Loaded transcription model: '{self.transcription_model}'")
        
        self.transcription_model_type = self.config_manager.transcription_model_type
        # Determine model type from name if not set
        if not self.transcription_model_type or self.transcription_model_type == "unknown":
            if "gpt" in self.transcription_model.lower():
                self.transcription_model_type = "gpt"
            else:
                self.transcription_model_type = "whisper"
        print(f"Loaded model type: '{self.transcription_model_type}'")

        self.ai_model = self.config_manager.ai_model
        print(f"Loaded AI model: '{self.ai_model}'")

        self.whisper_language = self.config_manager.whisper_language
        print(f"Loaded whisper language: '{self.whisper_language}'")

        # Load keyboard shortcuts from config
        self.shortcuts = {
            'record_edit': self.config_manager.get_shortcut('record_edit'),
            'record_transcribe': self.config_manager.get_shortcut('record_transcribe'),
            'cancel_recording': self.config_manager.get_shortcut('cancel_recording'),
            'cycle_prompt_back': self.config_manager.get_shortcut('cycle_prompt_back'),
            'cycle_prompt_forward': self.config_manager.get_shortcut('cycle_prompt_forward')
        }
        
        # Schedule UI update and hotkey registration after main window is initialized
        def after_init():
            # Update UI with loaded shortcuts
            self.hotkey_manager.update_shortcut_displays()
            # Register the loaded shortcuts
            self.hotkey_manager.force_hotkey_refresh()

        # Delay slightly to ensure UI is ready
        self.after(100, after_init)

    def get_api_key(self):
        """Get the OpenAI API key, prompting if not found."""
        api_key = self.config_manager.openai_api_key
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
        # Provide standard context menu and key bindings
        self._attach_entry_context_menu(api_key_entry)

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

    def _install_text_bindings(self):
        """Install standard copy/paste/cut/select-all bindings and context menus."""
        try:
            # Apply to all future Text widgets
            self.bind_class("Text", "<Control-a>", lambda e: (e.widget.tag_add("sel", "1.0", "end-1c"), "break"))
            self.bind_class("Text", "<Control-A>", lambda e: (e.widget.tag_add("sel", "1.0", "end-1c"), "break"))
            self.bind_class("Text", "<Control-c>", lambda e: (e.widget.event_generate("<<Copy>>"), "break"))
            self.bind_class("Text", "<Control-C>", lambda e: (e.widget.event_generate("<<Copy>>"), "break"))
            self.bind_class("Text", "<Control-v>", lambda e: (e.widget.event_generate("<<Paste>>"), "break"))
            self.bind_class("Text", "<Control-V>", lambda e: (e.widget.event_generate("<<Paste>>"), "break"))
            self.bind_class("Text", "<Control-x>", lambda e: (e.widget.event_generate("<<Cut>>"), "break"))
            self.bind_class("Text", "<Control-X>", lambda e: (e.widget.event_generate("<<Cut>>"), "break"))
            # Right-click menu
            self.bind_class("Text", "<Button-3>", self._show_text_context_menu)

            # Apply to all future Entry widgets
            self.bind_class("TEntry", "<Control-a>", lambda e: (e.widget.selection_range(0, 'end'), "break"))
            self.bind_class("TEntry", "<Control-A>", lambda e: (e.widget.selection_range(0, 'end'), "break"))
            self.bind_class("TEntry", "<Control-c>", lambda e: (e.widget.event_generate("<<Copy>>"), "break"))
            self.bind_class("TEntry", "<Control-C>", lambda e: (e.widget.event_generate("<<Copy>>"), "break"))
            self.bind_class("TEntry", "<Control-v>", lambda e: (e.widget.event_generate("<<Paste>>"), "break"))
            self.bind_class("TEntry", "<Control-V>", lambda e: (e.widget.event_generate("<<Paste>>"), "break"))
            self.bind_class("TEntry", "<Control-x>", lambda e: (e.widget.event_generate("<<Cut>>"), "break"))
            self.bind_class("TEntry", "<Control-X>", lambda e: (e.widget.event_generate("<<Cut>>"), "break"))
            self.bind_class("TEntry", "<Button-3>", self._show_entry_context_menu)
        except Exception as e:
            print(f"Error installing text bindings: {e}")

    def _attach_entry_context_menu(self, entry_widget):
        try:
            entry_widget.bind("<Button-3>", self._show_entry_context_menu)
            entry_widget.bind("<Control-a>", lambda e: (e.widget.selection_range(0, 'end'), "break"))
            entry_widget.bind("<Control-A>", lambda e: (e.widget.selection_range(0, 'end'), "break"))
        except Exception as e:
            print(f"Error attaching entry context menu: {e}")

    def _show_text_context_menu(self, event):
        widget = event.widget
        menu = Menu(self, tearoff=0)
        try:
            menu.add_command(label="Cut", command=lambda: widget.event_generate('<<Cut>>'))
            menu.add_command(label="Copy", command=lambda: widget.event_generate('<<Copy>>'))
            menu.add_command(label="Paste", command=lambda: widget.event_generate('<<Paste>>'))
            menu.add_separator()
            menu.add_command(label="Select All", command=lambda: widget.tag_add("sel", "1.0", "end-1c"))
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_entry_context_menu(self, event):
        widget = event.widget
        menu = Menu(self, tearoff=0)
        try:
            menu.add_command(label="Cut", command=lambda: widget.event_generate('<<Cut>>'))
            menu.add_command(label="Copy", command=lambda: widget.event_generate('<<Copy>>'))
            menu.add_command(label="Paste", command=lambda: widget.event_generate('<<Paste>>'))
            menu.add_separator()
            menu.add_command(label="Select All", command=lambda: widget.selection_range(0, 'end'))
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()


    def save_api_key(self, api_key):
        """Save the API key to credentials.json."""
        self.config_manager.openai_api_key = api_key
        self.config_manager.save_credentials()

    def create_menu(self):
        self.menubar = Menu(self)
        self.config(menu=self.menubar)

        # File menu
        file_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Save Session History", command=self.save_session_history)
        file_menu.add_separator()
        file_menu.add_command(label="Minimize to Tray", command=self.minimize_to_tray)
        file_menu.add_command(label="Exit", command=self.on_closing)

        # Settings menu
        settings_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Change API Key", command=self.change_api_key)
        settings_menu.add_command(label="Adjust AI Models", command=self.adjust_models)
        settings_menu.add_command(label="Manage Prompts", command=self.manage_prompts)
        settings_menu.add_command(label="Config", command=self.open_config)
        settings_menu.add_separator()
        settings_menu.add_checkbutton(label="Automatically Check for Updates", 
                                    variable=self.version_manager.auto_update_check, 
                                    command=self.version_manager.save_auto_update_setting)
        settings_menu.add_checkbutton(label="Auto-Refresh Hotkeys (Every 30s)", 
                                    variable=self.auto_hotkey_refresh, 
                                    command=self.save_auto_hotkey_refresh)
        settings_menu.add_separator()
        settings_menu.add_command(label="Check Keyboard Shortcuts", command=self.check_keyboard_shortcuts)
        settings_menu.add_command(label="Refresh Hotkeys", command=self.hotkey_manager.force_hotkey_refresh)

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
        
        self.help_menu.add_command(label="Check for Updates", command=lambda: self.version_manager.check_for_updates(True))
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
            
            # Quick verification of hotkey state before recording
            # This helps ensure we can actually stop the recording with hotkeys
            if not self.hotkey_manager.verify_hotkeys():
                print("WARNING: Hotkeys not functioning correctly. Refreshing before recording...")
                self.hotkey_manager.force_hotkey_refresh(callback=lambda success: 
                                                        self.start_recording() if success else None)
            else:
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

            # Remove any trailing newlines/spaces to avoid moving the caret to a new line on paste
            transcription_text = (transcription_text or "").rstrip()

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
                edited_text = (edited_text or "").rstrip()
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

            # Provide a clearer hint for known unsupported/renamed models
            err_text = str(e)
            if "mini" in (self.transcription_model or "").lower():
                messagebox.showerror(
                    "Transcription Error",
                    "The selected transcription model may be unsupported. Try 'gpt-4o-transcribe' or 'whisper-1'.\n\n"
                    "If you entered a custom model, please verify the exact model name supported by the API."
                )
            else:
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

            if "gpt-5" in self.ai_model:
                response = self.client.responses.create(
                    model=self.ai_model,
                    instructions=system_prompt,
                    text={"verbosity": "low"},  
                    reasoning={"effort": "minimal"},
                    input=user_prompt,
                    max_output_tokens=8000
                )
                gpt_text = response.output_text
            else:
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
        # Stop the system tray icon
        if hasattr(self, 'tray_manager'):
            self.tray_manager.stop_tray()
            
        # Stop the system event listener
        if hasattr(self, 'system_event_listener'):
            self.system_event_listener.stop_listening()
            
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

    def save_prompt_to_config(self, prompt_name):
        """Save selected prompt to settings.json."""
        self.config_manager.selected_prompt = prompt_name
        self.config_manager.save_settings()

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

    def open_config(self):
        """Open the configuration dialog."""
        ConfigDialog(self)

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
        self.save_prompt_to_config(self.current_prompt_name)
        
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
        self.save_prompt_to_config(self.current_prompt_name)
        
        # Update UI
        self.update_model_label()
        
        # Show notification and trigger text-to-speech
        self.show_prompt_notification(f"Prompt: {self.current_prompt_name}")

    def cycle_prompt_notification(self, prompt_name):
        """Show a temporary notification about the prompt change."""
        self.show_prompt_notification(f"Prompt: {prompt_name}")

    def setup_hotkey_health_checker(self):
        """Set up a periodic check of hotkey health"""
        # Check hotkeys every 30 seconds
        self.hotkey_check_interval = 30000  # 30 seconds in milliseconds
        
        def check_hotkey_health():
            # Only run the check if auto hotkey refresh is enabled
            if self.auto_hotkey_refresh.get():
                # Check if any hotkeys are registered
                if not self.hotkey_manager.verify_hotkeys():
                    print("Hotkey health check failed - refreshing hotkeys")
                    self.hotkey_manager.force_hotkey_refresh()
                else:
                    print("Hotkey health check passed")
            else:
                print("Hotkey health check skipped - auto refresh disabled")
                
            # Always schedule next check, even if disabled (in case user enables it later)
            self.after(self.hotkey_check_interval, check_hotkey_health)
        
        # Start the periodic check
        self.after(self.hotkey_check_interval, check_hotkey_health)

    def save_auto_hotkey_refresh(self):
        """Save the auto hotkey refresh setting to settings.json."""
        self.config_manager.auto_hotkey_refresh = self.auto_hotkey_refresh.get()
        self.config_manager.save_settings()
        print(f"Auto hotkey refresh setting saved: {self.auto_hotkey_refresh.get()}")

    def setup_system_tray(self):
        """Initialize and show the system tray icon"""
        # Start the tray icon
        success = self.tray_manager.show_tray()
        
        if not success:
            # If we can't create a tray icon, don't change window closing behavior
            messagebox.showwarning(
                "System Tray Unavailable", 
                "Could not create system tray icon. Closing the window will exit the application."
            )
            # Use normal window closing behavior
            self.protocol("WM_DELETE_WINDOW", self.on_closing)
        else:
            # Set up close button behavior to minimize to tray instead of exit
            self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

    def minimize_to_tray(self):
        """Minimize the application to system tray instead of closing"""
        self.tray_manager.minimize_to_tray()

    def update_recording_directory(self):
        """Update the recording directory based on configuration settings."""
        # Load recording location setting from config
        recording_location = self.config_manager.recording_location
        
        if recording_location == "appdata":
            # Use OS-appropriate app data directory
            if platform.system() == "Windows":
                appdata_dir = Path(os.getenv("APPDATA", os.path.expanduser("~"))) / "QuickWhisper"
            elif platform.system() == "Darwin":  # macOS
                appdata_dir = Path.home() / "Library" / "Application Support" / "QuickWhisper"
            else:  # Linux and other Unix-like systems
                appdata_dir = Path.home() / ".config" / "QuickWhisper"
            self.tmp_dir = appdata_dir
        elif recording_location == "custom":
            custom_path = self.config_manager.custom_recording_path
            if custom_path and os.path.exists(custom_path):
                self.tmp_dir = Path(custom_path)
            else:
                # Fallback to alongside if custom path is invalid
                print(f"Warning: Custom recording path '{custom_path}' does not exist. Falling back to 'alongside' option.")
                self.tmp_dir = Path.cwd() / "tmp"
        else:  # Default: alongside
            self.tmp_dir = Path.cwd() / "tmp"
        
        # Ensure the directory exists
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        print(f"Recording directory set to: {self.tmp_dir}")
