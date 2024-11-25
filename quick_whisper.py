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
from tkinter import filedialog
import customtkinter as ctk
from PIL import Image, ImageTk 
from openai import OpenAI
from dotenv import load_dotenv, dotenv_values, set_key
from pathlib import Path
from audioplayer import AudioPlayer
import keyboard  # For auto-paste functionality
from pystray import Icon as icon, MenuItem as item, Menu as menu

from utils.tooltip import ToolTip


class QuickWhisper(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Quick Whisper by Scorchsoft.com (Speech to Copy Edited Text) ")

        # Initialize prompts
        self.prompts = self.load_prompts()  # Assuming you have a method to load prompts

        icon_path = self.resource_path("assets/icon-32.png")
        self.iconphoto(False, tk.PhotoImage(file=icon_path))
        self.iconbitmap(self.resource_path("assets/icon.ico"))

        self.geometry("600x700")
        self.version = "1.5.0"
        self.resizable(False, False)
        self.banner_visible = True

        # Initial model settings
        self.transcription_model = "whisper-1"
        self.ai_model = "gpt-4o"

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

        self.audio = pyaudio.PyAudio()
        self.selected_device = tk.StringVar()
        self.auto_copy = tk.BooleanVar(value=True)
        self.auto_paste = tk.BooleanVar(value=True)
        self.history = []  # Stores up to 50 items of transcription or edited text
        self.history_index = -1  # -1 indicates no history selected yet
        self.max_history_length = 10000
        self.current_button_mode = "transcribe" # "transcribe" or "edit"
        self.tmp_dir = Path.cwd() / "tmp"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.record_thread = None
        self.recording = False
        self.frames = []

        keyboard.add_hotkey('win+j', lambda: self.toggle_recording("edit"))
        keyboard.add_hotkey('win+ctrl+j', lambda: self.toggle_recording("transcribe"))
        keyboard.add_hotkey('win+x', self.cancel_recording)

        self.create_menu()
        self.create_widgets()

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

    # Load environment variables from config/.env
    def load_env_file(self):

        env_path = Path("config") / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)

        # Check the HIDE_BANNER setting and set initial visibility
        self.hide_banner_on_load = os.getenv("HIDE_BANNER", "false").lower() == "true"

        # Overwrite transcription model if set
        transcription_model = os.getenv("TRANSCRIPTION_MODEL")
        if transcription_model:
            self.transcription_model = transcription_model

        # Overwrite AI model if set
        ai_model = os.getenv("AI_MODEL")
        if ai_model:
            self.ai_model = ai_model

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
        dialog.geometry("400x200")
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

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        row = 0;

        # Input Device Selection
        ttk.Label(main_frame, text="Input Device (mic):").grid(row=row, column=0, sticky="ew", pady=(0,10))
        devices = self.get_input_devices()
        if not devices:
            messagebox.showerror("No Input Devices", "No input audio devices found.")
            self.destroy()
            return
        self.selected_device.set(list(devices.keys())[0])  # Default selection

        device_menu = ttk.OptionMenu(main_frame, self.selected_device, self.selected_device.get(), *devices.keys())
        #device_menu.config(width=20)  # Set a fixed width for consistency
        device_menu.grid(row=row, column=1, sticky="ew", pady=(0,10))

        row +=1

        # Assuming you've converted the SVG files to PNG with the same names
        self.icon_first_page = tk.PhotoImage(file=self.resource_path("assets/first-page.png"))
        self.icon_arrow_left = tk.PhotoImage(file=self.resource_path("assets/arrow-left.png"))
        self.icon_arrow_right = tk.PhotoImage(file=self.resource_path("assets/arrow-right.png"))

        # Create a dedicated frame for the transcription section
        self.transcription_frame = ttk.Frame(main_frame)
        self.transcription_frame.grid(row=row, column=0, columnspan=2, pady=(0, 0), padx=0, sticky="ew")

        # Add the Transcription label to the transcription frame
        ttk.Label(self.transcription_frame, text="Transcription:").grid(row=0, column=0, sticky="w", pady=(0, 0), padx=(0, 0))

        # Create navigation buttons and place them next to the label within the transcription frame
        self.button_first_page = tk.Button(self.transcription_frame, image=self.icon_first_page, command=self.go_to_first_page, state=tk.DISABLED, borderwidth=0)
        self.button_arrow_left = tk.Button(self.transcription_frame, image=self.icon_arrow_left, command=self.navigate_left, state=tk.DISABLED, borderwidth=0)
        self.button_arrow_right = tk.Button(self.transcription_frame, image=self.icon_arrow_right, command=self.navigate_right, state=tk.DISABLED, borderwidth=0)

        # Add tooltips to navigation buttons
        ToolTip(self.button_first_page, "Go to the latest entry")
        ToolTip(self.button_arrow_left, "Navigate to the more recent entry")
        ToolTip(self.button_arrow_right, "Navigate to the older entry")

        # Grid placement for navigation buttons in the transcription frame
        self.button_first_page.grid(row=0, column=1, sticky="e", padx=(0, 0))
        self.button_arrow_left.grid(row=0, column=2, sticky="e", padx=(0, 0))
        self.button_arrow_right.grid(row=0, column=3, sticky="e", padx=(0, 0))

        # Configure the columns within the transcription frame for proper alignment
        self.transcription_frame.columnconfigure(0, weight=1)  # Allow text area to expand
        self.transcription_frame.columnconfigure(1, minsize=30)  # Set a minimum size for each button column
        self.transcription_frame.columnconfigure(2, minsize=30)
        self.transcription_frame.columnconfigure(3, minsize=30)
        
        row +=1

        # Transcription Text Area
        self.transcription_text = tk.Text(main_frame, height=10, width=70, wrap="word")
        self.transcription_text.grid(row=row, column=0, columnspan=2, pady=(0,5))

        row +=1

        # Model Label
        self.model_label = ttk.Label(main_frame, text=f"{self.transcription_model}, {self.ai_model}", foreground="grey")
        self.model_label.grid(row=row, column=0, columnspan=2, sticky=tk.E, pady=(0,20))

        # Status Label
        self.status_label = ttk.Label(main_frame, text=f"Status: Idle", foreground="blue")
        self.status_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0,20))

        row +=1

        # Auto-Copy Checkbox
        auto_copy_cb = ttk.Checkbutton(main_frame, text="Copy to clipboard when done", variable=self.auto_copy)
        auto_copy_cb.grid(row=row, column=0, columnspan=1, sticky=tk.W, pady=(0,20))

        # Auto-Paste Checkbox
        auto_paste_cb = ttk.Checkbutton(main_frame, text="Paste from clipboard when done", variable=self.auto_paste)
        auto_paste_cb.grid(row=row, column=1, columnspan=1, sticky=tk.W, pady=(0,20))

        row +=1

        button_width =50

        ctk.set_appearance_mode("light")  # Options: "light" or "dark"
        ctk.set_default_color_theme("green")  # Options: "blue", "dark-blue", "green"

        # Record Transcript Only Button with green background and padding on the right
        self.record_button_transcribe = ctk.CTkButton(
            main_frame, 
            text="Record + Transcript (Win+Ctrl+J)", 
            corner_radius=20, 
            height=35,
            width=button_width,
            fg_color="#058705",
            font=("Arial", 13, "bold"),
            command=lambda: self.toggle_recording("transcribe")
        )
        self.record_button_transcribe.grid(row=row, column=0, columnspan=1, pady=(0,10), padx=(0, 5), sticky="ew")

        self.record_button_edit = ctk.CTkButton(
            main_frame, 
            text="Record + AI Edit (Win+J)", 
            corner_radius=20,
            height=35,
            width=button_width,
            fg_color="#058705",
            font=("Arial", 13, "bold"),
            command=lambda: self.toggle_recording("edit")
        )
        self.record_button_edit.grid(row=row, column=1, columnspan=1, pady=(0,10), padx=(5, 0), sticky="ew")

        row +=1

        # Load and display the banner image
        banner_image_path = self.resource_path("assets/banner-00-560.png")
        banner_image = Image.open(banner_image_path)
        self.banner_photo = ImageTk.PhotoImage(banner_image)  # Store to prevent garbage collection

        # Display the image in a label with clickability
        self.banner_label = tk.Label(main_frame, image=self.banner_photo, cursor="hand2")
        self.banner_label.grid(column=0, row=row, columnspan=2, pady=(10, 0), sticky="ew")
        self.banner_label.bind("<Button-1>", lambda e: self.open_scorchsoft())  # Bind the click event

        row +=1

        self.hide_banner_link = tk.Label(
            main_frame, 
            text="Hide Banner", 
            fg="blue", 
            cursor="hand2", 
            font=("Arial", 10, "underline")
        )
        self.hide_banner_link.grid(row=row, column=0, columnspan=2, pady=(5, 0), sticky="ew")
        self.hide_banner_link.bind("<Button-1>", lambda e: self.toggle_banner())


        # Add a "Powered by Scorchsoft.com" link to replace the banner when hidden
        self.powered_by_label = tk.Label(
            main_frame,
            text="Powered by Scorchsoft.com",
            fg="black",
            cursor="hand2",
            font=("Arial", 8, "underline")
        )
        self.powered_by_label.grid(column=0, row=row, columnspan=2, pady=(5, 0), sticky="ew")
        self.powered_by_label.bind("<Button-1>", lambda e: self.open_scorchsoft())  # Bind click to open website
        self.powered_by_label.grid_remove()  # Hide the label initially

        # Configure grid
        main_frame.columnconfigure(0, weight=1, minsize=280)  # Set minsize to ensure equal width
        main_frame.columnconfigure(1, weight=1, minsize=280)


    def open_scorchsoft(self, event=None):
        webbrowser.open('https://www.scorchsoft.com/contact-scorchsoft')

    def create_menu(self):
        self.menubar = Menu(self)
        self.config(menu=self.menubar)

        # File menu
        file_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Save Session History", command=self.save_session_history)


        # File or settings menu
        settings_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Change API Key", command=self.change_api_key)
        settings_menu.add_command(label="Adjust AI Models", command=self.adjust_models)
        settings_menu.add_command(label="Manage Prompts", command=self.manage_prompts)

        # Play Menu
        play_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Play", menu=play_menu)
        play_menu.add_command(label="Retry Last Recording", command=self.retry_last_recording)
        play_menu.add_command(label="Cancel Recording (Win+X)", command=self.cancel_recording)

        #Copy Menu
        copy_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Copy", menu=copy_menu)
        copy_menu.add_command(label="Last Transcript", command=self.copy_last_transcription)
        copy_menu.add_command(label="Last Edit", command=self.copy_last_edit)

    
        # Help menu
        self.help_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Help", menu=self.help_menu)
        self.help_menu.add_command(label="Hide Banner", command=self.toggle_banner)
        self.help_menu.add_command(label="Terms of Use and Licence", command=self.show_terms_of_use)
        self.help_menu.add_command(label="Version", command=self.show_version)


    def toggle_banner(self):
        """Toggle the visibility of the banner image and adjust the window height."""
        current_height = self.winfo_height()
        new_height = current_height + 260 if not self.banner_visible else current_height - 260

        if self.banner_visible:
            self.banner_label.grid_remove()  # Hide the banner
            self.hide_banner_link.grid_remove()
            self.powered_by_label.grid()
            self.help_menu.entryconfig("Hide Banner", label="Show Banner")  # Update menu text
        else:
            self.banner_label.grid()  # Show the banner
            self.help_menu.entryconfig("Show Banner", label="Hide Banner")  # Update menu text
            self.powered_by_label.grid_remove() 

        # Set the new height and keep the current width
        self.geometry(f"{self.winfo_width()}x{new_height}")
        
        self.banner_visible = not self.banner_visible  # Toggle the visibility flag


    def navigate_right(self):
        self.history_index -= 1
        self.update_transcription_text()
        self.update_navigation_buttons()

    def navigate_left(self):
        self.history_index += 1
        self.update_transcription_text()
        self.update_navigation_buttons()

    def go_to_first_page(self):
    
        self.history_index = len(self.history) - 1  # Set to most recent
        self.update_transcription_text()
        self.update_navigation_buttons()


    def adjust_models(self):
        # Create pop-up window for adjusting models
        model_dialog = tk.Toplevel(self)
        model_dialog.title("Adjust AI Models")
        model_dialog.geometry("450x420")

        # Transcription Model Entry
        tk.Label(model_dialog, text="OpenAI Transcription Model:").pack(anchor="w", padx=10, pady=(10, 0))
        transcription_entry = tk.Entry(model_dialog)
        transcription_entry.insert(0, self.transcription_model)  # Default to current model
        transcription_entry.pack(fill="x", padx=10)
        tk.Label(model_dialog, text="e.g., whisper-1", font=("TkDefaultFont", 9), foreground="#4B4B4B").pack(anchor="w", padx=10)

        # AI Model Entry
        tk.Label(model_dialog, text="OpenAI Copyediting Model:").pack(anchor="w", padx=10, pady=(10, 0))
        ai_entry = tk.Entry(model_dialog)
        ai_entry.insert(0, self.ai_model)  # Default to current model
        ai_entry.pack(fill="x", padx=10)
        tk.Label(model_dialog, text="e.g., gpt-4o, gpt-4o-mini, o1-mini, o1-preview", font=("TkDefaultFont", 9), foreground="#4B4B4B").pack(anchor="w", padx=10)

        # Save button
        save_button = ttk.Button(model_dialog, text="Save", command=lambda: self.save_model_settings(transcription_entry.get(), ai_entry.get(), model_dialog))
        save_button.pack(pady=10)

        # Link to OpenAI Pricing
        link = tk.Label(model_dialog, text="View Available OpenAI Models and Pricing", fg="blue", cursor="hand2")
        link.pack(pady=(10, 0))
        link.bind("<Button-1>", lambda e: webbrowser.open("https://openai.com/api/pricing/"))

        # Instructional text
        instructional_text = ("How to find and set model names:\n\nEnsure you input model names exactly as they appear in the OpenAI documentation, "
                            "considering they are case-sensitive. Incorrect model names may cause the application to "
                            "malfunction due to an inability to perform relevant functions. As of this implementation, "
                            "gpt-4o is the more capable model but is more expensive. gpt-4o-mini offers a cost-effective "
                            "alternative (upto 20x cheaper) with less comprehensive world knowledge yet remains suitable for copyediting tasks. "
                            "This information will help you optimise performance and cost. We've added the ability to change models to future proof "
                            " the app and give users more control.")
        tk.Label(model_dialog, text=instructional_text, wraplength=430, justify="left", font=("TkDefaultFont", 9), foreground="#4B4B4B").pack(pady=(10, 0), padx=10)
        

    def save_model_settings(self, transcription_model, ai_model, model_dialog):
        env_path = Path("config") / ".env"
        
        # Load existing .env settings into a dictionary
        if env_path.exists():
            env_vars = dotenv_values(env_path)
        else:
            env_vars = {}

        # Update model values in the dictionary
        env_vars["TRANSCRIPTION_MODEL"] = transcription_model
        env_vars["AI_MODEL"] = ai_model

        # Write each environment variable to the .env file, overwriting existing values
        with open(env_path, "w") as f:
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")

        # Update instance variables
        self.transcription_model = transcription_model
        self.ai_model = ai_model
        model_dialog.destroy()




    def get_input_devices(self):
        devices = {}
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                devices[info['name']] = i
        return devices
    
    # Find device index based on selected device name
    def get_device_index_by_name(self, device_name):
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            if info['name'] == device_name:
                return i
        raise ValueError(f"Device '{device_name}' not found.")

    def toggle_recording(self,mode="transcribe"):

        if not self.recording:
            # Set globally so the app knows when recording stops whether 
            # transcript or edit mode was selected
            self.current_button_mode = mode
            print(f"\nAbout to start recording. mode = {mode}")
            self.start_recording()
        else:
            print(f"About to stop recording. mode = {self.current_button_mode}")
            self.stop_recording()

    def start_recording(self, mode="edit"):

        print("Getting Device Index")
        try:
            self.device_index = self.get_device_index_by_name(self.selected_device.get())
        except ValueError as e:
            messagebox.showerror("Device Error", str(e))
            return

        print("Starting Stream")
        self.stream = self.audio.open(format=pyaudio.paInt16,
                                      channels=1,
                                      rate=16000,
                                      input=True,
                                      frames_per_buffer=1024,
                                      input_device_index=self.device_index)

        self.frames = []
        self.recording = True

        self.record_button_transcribe.configure(text="Stop and Process", fg_color="red", hover_color="#a83232")
        self.record_button_edit.configure(text="Stop and Process", fg_color="red", hover_color="#a83232")

        print("Update status label")
        self.status_label.config(text="Status: Recording...", foreground="red")

        # Play start recording sound
        threading.Thread(target=lambda: self.play_sound("assets/pop.wav")).start()

        # Start recording in a separate thread
        print("Starting Recording")
        self.record_thread = threading.Thread(target=self.record, daemon=True)
        print("Starting Recording thread")
        self.record_thread.start()

    def record(self):
        while self.recording:
            try:
                data = self.stream.read(1024)
                self.frames.append(data)
            except Exception as e:
                print(f"Recording error: {e}")
                messagebox.showerror("Recording error", f"An error occurred while Recording: {e}")
                break


    # Inside your class definition, replace stop_recording with the following:
    def stop_recording(self):

        self.recording = False
        self.record_thread.join()

        self.stream.stop_stream()
        self.stream.close()

        print(f"Stopping, about to trigger '{self.current_button_mode}' mode...")


        self.record_button_transcribe.configure(text="Record + Transcript (Win+Ctrl+J)", fg_color="#058705", hover_color="#046a38")
        self.record_button_edit.configure(text="Record + AI Edit (Win+J)", fg_color="#058705", hover_color="#046a38")


        self.status_label.config(text="Status: Processing - Audio File...", foreground="green")


        # Play stop recording sound
        threading.Thread(target=lambda: self.play_sound("assets/pop-down.wav")).start()

        # Ensure tmp folder exists
        
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

        # Save the recorded data to the tmp folder as temp_recording.wav
        self.audio_file = self.tmp_dir / "temp_recording.wav"
        print(f"Saving Recording to {self.audio_file}")

        with wave.open(str(self.audio_file), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(16000)
            wf.writeframes(b''.join(self.frames))

        # Start transcription in a separate thread
        threading.Thread(target=self.transcribe_audio).start()

    def retry_last_recording(self):

        last_recording = self.tmp_dir / "temp_recording.wav"

        if last_recording.exists():

            # Play start recording sound
            threading.Thread(target=lambda: self.play_sound("assets/pop.wav")).start()

            self.audio_file = last_recording
            self.status_label.config(text="Status: Retrying transcription...", foreground="orange")
            
            # Re-attempt transcription in a separate thread
            threading.Thread(target=self.transcribe_audio).start()
        else:
            messagebox.showerror("Retry Failed", "No previous recording found to retry in tmp folder.")



    def transcribe_audio(self):
        file_path = self.audio_file

        try:

            self.status_label.config(text="Status: Processing - Transcript...", foreground="green")

            with open(str(file_path), "rb") as audio_file:
                # Use OpenAI's transcription API as intended

                print(f"About to transcrible model {self.transcription_model}")
                transcription = self.client.audio.transcriptions.create(
                    file=audio_file,
                    model=self.transcription_model,
                    response_format="verbose_json"
                )

            # Retrieve the transcription text correctly
            transcription_text = transcription.get("text", "") if isinstance(transcription, dict) else transcription.text
            self.add_to_history(transcription_text)
            self.last_trancription = transcription_text

            # Process transcription with or without GPT as per the checkbox setting
            if self.current_button_mode == "edit":
                print("AI Editing Transcription")

                # set input box to transcription text first, just incase there is a failure
                self.transcription_text.delete("1.0", tk.END)
                self.transcription_text.insert("1.0", transcription_text)

                # Then GPT edit that transcribed text and insert
                self.status_label.config(text="Status: Processing - AI Editing...", foreground="green")

                # AI Edit the transcript
                edited_text = self.process_with_gpt_model(transcription_text)
                self.add_to_history(edited_text)
                self.last_edit = edited_text
                play_text = edited_text

                self.transcription_text.delete("1.0", tk.END)
                self.transcription_text.insert("1.0", play_text)
            else:
                print("Outputting Raw Transcription Only")
                self.transcription_text.delete("1.0", tk.END)
                self.transcription_text.insert("1.0", transcription_text)
                play_text = transcription_text


            if self.auto_copy.get():
                self.auto_copy_text(play_text)

            if self.auto_paste.get():
                self.auto_paste_text(play_text)

            print("Transcription Complete: The audio has been transcribed and the text has been placed in the input area.")
            # Play stop recording sound
            threading.Thread(target=lambda:  self.play_sound("assets/double-pop-down.wav")).start()

        except Exception as e:
            # Play failure sound
            threading.Thread(target=lambda:  self.play_sound("assets/wrong-short.wav")).start()

            print(f"Transcription error: An error occurred during transcription: {str(e)}")
            self.status_label.config(text="Status: Error during transcription", foreground="red")

            messagebox.showerror("Transcription Error", f"An error occurred while Transcribing: {e}")

        finally:
            self.status_label.config(text="Status: Idle", foreground="blue")
            # No longer remove temp file
            # if os.path.exists(file_path):
            #    os.remove(file_path)



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
            # no needt to copy twice
            #pyperclip.copy(text)
            
            # Simulate Ctrl+V to paste from clipboard
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
            # When running in a PyInstaller bundle, use the '_MEIPASS' directory
            base_path = sys._MEIPASS
        except AttributeError:
            # When running normally (not bundled), use the directory where the main script is located
            base_path = os.path.dirname(os.path.abspath(sys.argv[0]))

        # Resolve the absolute path
        abs_path = os.path.join(base_path, relative_path)

        # Debugging: Print the absolute path to check if it's correct
        print(f"Resolved path for {relative_path}: {abs_path}")

        return abs_path

    def on_closing(self):
        if self.recording:
            self.stop_recording()
        self.audio.terminate()
        self.destroy()

    def play_sound(self, sound_file):
        player = AudioPlayer(self.resource_path(sound_file))
        player.play(block=True) 

    def show_terms_of_use(self):
        # Get the path to the LICENSE.md file using the resource_path method
        license_path = self.resource_path("assets/LICENSE.md")

        # Attempt to read the content of the LICENSE.md file
        try:
            # Open the file with 'r' (read mode) and specify 'utf-8' encoding
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

        # Create a new window to display the terms of use
        instruction_window = tk.Toplevel(self)
        instruction_window.title("Terms of Use")
        instruction_window.geometry("800x700")  # Width x Height

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
        instruction_window.geometry("300x150")  # Width x Height

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
        self.update_transcription_text()
        self.update_navigation_buttons()
        
    def update_transcription_text(self):
        # Display the current history entry in the transcription text box
        if 0 <= self.history_index < len(self.history):
            self.transcription_text.delete("1.0", tk.END)
            self.transcription_text.insert("1.0", self.history[self.history_index])

    def update_navigation_buttons(self):
        # Disable 'first page' and 'left' buttons if we're on the latest (last) entry
        if self.history_index >= len(self.history) - 1:
            self.button_first_page.config(state=tk.DISABLED)
            self.button_arrow_left.config(state=tk.DISABLED)
        else:
            self.button_first_page.config(state=tk.NORMAL)
            self.button_arrow_left.config(state=tk.NORMAL)

        # Disable 'right' button if we're on the oldest (first) entry
        if self.history_index <= 0:
            self.button_arrow_right.config(state=tk.DISABLED)
        else:
            self.button_arrow_right.config(state=tk.NORMAL)
    
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

    def cancel_recording(self):
        """Cancels the current recording without processing."""
        if self.recording:
            self.recording = False
            if self.record_thread:
                self.record_thread.join()

            self.stream.stop_stream()
            self.stream.close()

            # Reset buttons back to original state
            self.record_button_transcribe.configure(
                text="Record + Transcript (Win+Ctrl+J)", 
                fg_color="#058705", 
                hover_color="#046a38"
            )
            self.record_button_edit.configure(
                text="Record + AI Edit (Win+J)", 
                fg_color="#058705", 
                hover_color="#046a38"
            )

            # Reset status
            self.status_label.config(text="Status: Idle", foreground="blue")

            # Play failure sound
            threading.Thread(target=lambda: self.play_sound("assets/wrong-short.wav")).start()

    def manage_prompts(self):
        """Open dialog for managing prompts."""
        dialog = tk.Toplevel(self)
        dialog.title("Prompt Management")
        dialog.geometry("800x650")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        # Main container frame with padding
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left panel for prompt selection
        left_panel = ttk.Frame(main_frame, width=200)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)  # Maintain width

        # Prompt selection section
        select_frame = ttk.LabelFrame(left_panel, text="Prompt Selection", padding="5")
        select_frame.pack(fill=tk.BOTH, expand=True)

        # Load existing custom prompts
        self.prompts = self.load_prompts()
        
        # Combine default and custom prompts
        all_prompts = ["Default"] + list(self.prompts.keys())
        selected_prompt = tk.StringVar(value=self.current_prompt_name)

        # Listbox for prompts with scrollbar
        prompt_list = tk.Listbox(select_frame, height=8, selectmode=tk.BROWSE)  # Changed to BROWSE mode
        prompt_scrollbar = ttk.Scrollbar(select_frame, orient=tk.VERTICAL, command=prompt_list.yview)
        prompt_list.config(yscrollcommand=prompt_scrollbar.set)
        
        prompt_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5)
        prompt_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        # Populate listbox
        for prompt in all_prompts:
            prompt_list.insert(tk.END, prompt)
            if prompt == self.current_prompt_name:
                prompt_list.selection_set(all_prompts.index(prompt))

        # Button frame under listbox
        button_frame = ttk.Frame(left_panel)
        button_frame.pack(fill=tk.X, pady=5)

        # Right panel for prompt content
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Content area with label frame
        content_frame = ttk.LabelFrame(right_panel, text="Prompt Content", padding="5")
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Status label for edit state
        edit_status_label = ttk.Label(content_frame, foreground="red")
        edit_status_label.pack(anchor=tk.W, padx=5, pady=(5,0))

        # Content area
        content_text = tk.Text(content_frame, wrap=tk.WORD)
        content_scrollbar = ttk.Scrollbar(content_frame, orient=tk.VERTICAL, command=content_text.yview)
        content_text.config(yscrollcommand=content_scrollbar.set)
        
        content_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5)
        content_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        # Save changes button (initially hidden)
        save_changes_button = ttk.Button(right_panel, text="Save Changes", state='disabled')
        save_changes_button.pack(pady=(5, 0), anchor=tk.E)

        def update_content(event=None):
            selected_indices = prompt_list.curselection()
            if not selected_indices:
                return
            
            prompt_name = prompt_list.get(selected_indices[0])
            
            # Enable content_text before any operations
            content_text.config(state='normal')
            content_text.delete('1.0', tk.END)
            
            if prompt_name == "Default":
                content_text.insert('1.0', self.default_system_prompt)
                content_text.config(state='disabled')
                save_changes_button.config(state='disabled')
                delete_button.config(state='disabled')
                edit_status_label.config(text="(Default prompt cannot be edited)")
            else:
                content_text.insert('1.0', self.prompts[prompt_name])
                content_text.config(state='normal')
                save_changes_button.config(state='normal')
                delete_button.config(state='normal')
                edit_status_label.config(text="")  # Clear the status text

        def save_content_changes():
            selected_indices = prompt_list.curselection()
            if not selected_indices:
                return
            
            prompt_name = prompt_list.get(selected_indices[0])
            if prompt_name == "Default":
                return
            
            new_content = content_text.get("1.0", tk.END).strip()
            if not new_content:
                messagebox.showerror("Error", "Prompt content cannot be empty")
                return

            self.prompts[prompt_name] = new_content
            self.save_prompts(self.prompts)
            messagebox.showinfo("Success", "Prompt changes saved successfully")

        save_changes_button.config(command=save_content_changes)

        # Bind single click selection and ensure content_text is ready
        def on_prompt_select(event):
            self.after(10, update_content)  # Small delay to ensure widget is ready
        
        prompt_list.bind('<<ListboxSelect>>', on_prompt_select)

        def create_new_prompt():
            prompt_dialog = tk.Toplevel(dialog)
            prompt_dialog.title("Create New Prompt")
            prompt_dialog.geometry("600x400")  # Reduced height
            prompt_dialog.transient(dialog)
            prompt_dialog.grab_set()
            
            # Name entry
            name_frame = ttk.Frame(prompt_dialog, padding="10")
            name_frame.pack(fill=tk.X)
            ttk.Label(name_frame, text="Prompt Name:").pack(side=tk.LEFT)
            name_entry = ttk.Entry(name_frame)
            name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

            # System prompt
            prompt_frame = ttk.LabelFrame(prompt_dialog, text="System Prompt", padding="10")
            prompt_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            
            new_prompt_text = tk.Text(prompt_frame, wrap=tk.WORD, height=15)  # Set fixed height
            new_prompt_text.pack(fill=tk.BOTH, expand=True)

            def save_new_prompt():
                new_name = name_entry.get().strip()
                if not new_name:
                    messagebox.showerror("Error", "Please enter a prompt name")
                    return
                if len(new_name) > 25:
                    messagebox.showerror("Error", "Prompt name must be 25 characters or less")
                    return
                
                new_content = new_prompt_text.get("1.0", tk.END).strip()
                if not new_content:
                    messagebox.showerror("Error", "Please enter a system prompt")
                    return

                # Save prompt
                self.prompts[new_name] = new_content
                self.save_prompts(self.prompts)

                # Update listbox and select the new prompt
                prompt_list.delete(0, tk.END)
                all_prompts = ["Default"] + list(self.prompts.keys())
                for p in all_prompts:
                    prompt_list.insert(tk.END, p)
                
                # Find and select the new prompt
                new_prompt_index = all_prompts.index(new_name)
                prompt_list.selection_clear(0, tk.END)
                prompt_list.selection_set(new_prompt_index)
                prompt_list.see(new_prompt_index)
                update_content()  # Update content area with new prompt

                prompt_dialog.destroy()

            # Buttons
            button_frame = ttk.Frame(prompt_dialog)
            button_frame.pack(fill=tk.X, pady=10, padx=10)
            ttk.Button(button_frame, text="Save", 
                      command=save_new_prompt).pack(side=tk.RIGHT, padx=5)
            ttk.Button(button_frame, text="Cancel", 
                      command=prompt_dialog.destroy).pack(side=tk.RIGHT)

        def delete_current_prompt():
            selected_indices = prompt_list.curselection()
            if not selected_indices:
                return
            
            prompt_name = prompt_list.get(selected_indices[0])
            if prompt_name == "Default":
                return
            
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{prompt_name}'?"):
                if prompt_name == self.current_prompt_name:
                    self.current_prompt_name = "Default"
                    self.save_prompt_to_env(self.current_prompt_name)
                    self.update_model_label()

                del self.prompts[prompt_name]
                self.save_prompts(self.prompts)
                
                # Update listbox
                prompt_list.delete(0, tk.END)
                for p in ["Default"] + list(self.prompts.keys()):
                    prompt_list.insert(tk.END, p)
                
                # Select default
                prompt_list.selection_set(0)
                update_content()

        # Action buttons
        new_button = ttk.Button(button_frame, text="New Prompt", command=create_new_prompt)
        delete_button = ttk.Button(button_frame, text="Delete", command=delete_current_prompt)
        
        new_button.pack(side=tk.LEFT, padx=2)
        delete_button.pack(side=tk.LEFT, padx=2)

        # Bottom frame for the main action button
        bottom_frame = ttk.Frame(dialog)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10, padx=10)

        def save_and_exit():
            selected_indices = prompt_list.curselection()
            if not selected_indices:
                return
            
            prompt_name = prompt_list.get(selected_indices[0])
            
            # First save any content changes if it's not the default prompt
            if prompt_name != "Default":
                new_content = content_text.get("1.0", tk.END).strip()
                if new_content:
                    self.prompts[prompt_name] = new_content
                    self.save_prompts(self.prompts)
            
            # Then save the selection
            self.save_prompt_to_env(prompt_name)
            self.current_prompt_name = prompt_name
            self.update_model_label()
            dialog.destroy()
            messagebox.showinfo("Success", f"Now using prompt: {prompt_name}")

        # Create a custom button similar to the main app's style
        save_button = ctk.CTkButton(
            bottom_frame,
            text="Save Selection and Exit",
            corner_radius=20,
            height=35,
            fg_color="#058705",
            hover_color="#046a38",
            font=("Arial", 13, "bold"),
            command=save_and_exit
        )
        save_button.pack(side=tk.BOTTOM, fill=tk.X)

        # Initial content update
        update_content()

    def create_prompt_ui(self, dialog, prompt_name=None, prompt_list=None, content_text=None):
        """Create or edit prompt UI."""
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Name entry
        name_frame = ttk.Frame(main_frame)
        name_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(name_frame, text="Prompt Name:").pack(side=tk.LEFT)
        name_entry = ttk.Entry(name_frame)
        name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # System prompt
        ttk.Label(main_frame, text="System Prompt:").pack(anchor=tk.W)
        prompt_text = tk.Text(main_frame, wrap=tk.WORD)
        prompt_text.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

        # If editing, populate fields
        if prompt_name:
            name_entry.insert(0, prompt_name)
            name_entry.config(state='disabled')  # Can't change name when editing
            prompt_text.insert('1.0', self.prompts[prompt_name])

        def save_prompt():
            new_name = name_entry.get().strip()
            if not new_name:
                messagebox.showerror("Error", "Please enter a prompt name")
                return
            if len(new_name) > 25:
                messagebox.showerror("Error", "Prompt name must be 25 characters or less")
                return
            
            new_content = prompt_text.get("1.0", tk.END).strip()
            if not new_content:
                messagebox.showerror("Error", "Please enter a system prompt")
                return

            # Save prompt
            self.prompts[new_name] = new_content
            self.save_prompts(self.prompts)

            # Update listbox and content
            if prompt_list:
                prompt_list.delete(0, tk.END)
                for p in ["Default"] + list(self.prompts.keys()):
                    prompt_list.insert(tk.END, p)
                    if p == new_name:
                        prompt_list.selection_set(["Default"] + list(self.prompts.keys()).index(p))

            if content_text:
                content_text.config(state='normal')
                content_text.delete('1.0', tk.END)
                content_text.insert('1.0', new_content)

            dialog.destroy()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(button_frame, text="Save", 
                  command=save_prompt).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", 
                  command=dialog.destroy).pack(side=tk.RIGHT)

    def update_model_label(self):
        """Update the model label to include the prompt name."""
        self.model_label.config(text=f"{self.transcription_model}, {self.ai_model}, {self.current_prompt_name}")

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

if __name__ == "__main__":
    app = QuickWhisper()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
