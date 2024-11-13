import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, Menu
import threading
import pyaudio
import wave
import os
import sys
import openai
import pyperclip
import webbrowser
from PIL import Image, ImageTk 
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from audioplayer import AudioPlayer
import keyboard  # For auto-paste functionality
from pystray import Icon as icon, MenuItem as item, Menu as menu




class QuickWhisper(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Quick Whisper (Speech to text) by Scorchsoft.com")

        icon_path = self.resource_path("assets/icon-32.png")
        self.iconphoto(False, tk.PhotoImage(file=icon_path))
        self.iconbitmap(self.resource_path("assets/icon.ico"))

        self.geometry("600x690")
        self.version = "1.0.2"
        self.resizable(False, False)
        self.banner_visible = True

        # Initial model settings
        self.transcription_model = "whisper-1"
        self.ai_model = "gpt-4o"

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
        self.process_with_gpt = tk.BooleanVar(value=True)


        self.tmp_dir = Path.cwd() / "tmp"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        

        self.recording = False
        self.frames = []

        keyboard.add_hotkey('win+j', self.toggle_recording)

        self.create_menu()
        self.create_widgets()

        # Hide the banner on load if HIDE_BANNER is set to true in .env
        if self.hide_banner_on_load:
            self.toggle_banner()

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
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            # Prompt the user for API key
            api_key = simpledialog.askstring("OpenAI API Key", "Enter your OpenAI API Key:", show='*', parent=self)
            if api_key:
                self.save_api_key(api_key)
            else:
                return None
        return api_key
    
    def change_api_key(self):
        new_key = simpledialog.askstring("API Key", "Enter new OpenAI API Key:", parent=self)
        if new_key:
            self.save_api_key(new_key)
            self.api_key = new_key
            openai.api_key = self.api_key
            self.client = OpenAI(api_key=self.api_key)
            messagebox.showinfo("API Key Updated", "The OpenAI API Key has been updated successfully.\nYou may need to restart the app for it to take effect ")

    def save_api_key(self, api_key):
        """Save the API key to config/.env"""
        config_dir = Path("config")
        config_dir.mkdir(parents=True, exist_ok=True)
        env_path = config_dir / ".env"
        with open(env_path, 'w') as f:
            f.write(f"OPENAI_API_KEY={api_key}\n")
        load_dotenv(dotenv_path=env_path)

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Input Device Selection
        ttk.Label(main_frame, text="Input Device (mic):").grid(row=0, column=0, sticky=tk.W, pady=(0,10))
        devices = self.get_input_devices()
        if not devices:
            messagebox.showerror("No Input Devices", "No input audio devices found.")
            self.destroy()
            return
        self.selected_device.set(list(devices.keys())[0])  # Default selection
        device_menu = ttk.OptionMenu(main_frame, self.selected_device, self.selected_device.get(), *devices.keys())
        device_menu.grid(row=0, column=1, sticky=tk.W, pady=(0,10))

        # Record Button
        self.record_button = ttk.Button(main_frame, text="Start Recording (Win+J)", command=self.toggle_recording)
        self.record_button.grid(row=1, column=0, columnspan=2, pady=(0,10), sticky="ew")

        # Transcription Text Area
        ttk.Label(main_frame, text="Transcription:").grid(row=2, column=0, sticky=tk.W)
        self.transcription_text = tk.Text(main_frame, height=10, width=70)
        self.transcription_text.grid(row=3, column=0, columnspan=2, pady=(0,10))

        # Model Label
        self.model_label = ttk.Label(main_frame, text=f"{self.transcription_model}, {self.ai_model}", foreground="grey")
        self.model_label.grid(row=4, column=0, columnspan=2, sticky=tk.E, pady=(0,10))

        # Optional GPT Processing
        gpt_cb = ttk.Checkbutton(main_frame, text="Auto Copy-Edit With GPT-4o", variable=self.process_with_gpt)
        gpt_cb.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(0,10))

        # Auto-Copy Checkbox
        auto_copy_cb = ttk.Checkbutton(main_frame, text="Auto-Copy to Clipboard on Completion", variable=self.auto_copy)
        auto_copy_cb.grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=(0,10))

        # Auto-Paste Checkbox
        auto_paste_cb = ttk.Checkbutton(main_frame, text="Auto-Paste Clipboard on Completion", variable=self.auto_paste)
        auto_paste_cb.grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=(0,10))

        # Status Label
        self.status_label = ttk.Label(main_frame, text=f"Status: Idle", foreground="blue")
        self.status_label.grid(row=7, column=0, columnspan=2, sticky=tk.W)


        # Load and display the banner image
        banner_image_path = self.resource_path("assets/banner-00-560.png")
        banner_image = Image.open(banner_image_path)

        # Hardcode the banner width to 600 and adjust the height proportionally
        #banner_image = banner_image.resize((600, int(banner_image.height * (600 / 261))), Image.LANCZOS)
        self.banner_photo = ImageTk.PhotoImage(banner_image)  # Store to prevent garbage collection

        # Display the image in a label with clickability
        self.banner_label = tk.Label(main_frame, image=self.banner_photo, cursor="hand2")
        self.banner_label.grid(column=0, row=8, columnspan=2, pady=(10, 0), sticky="ew")
        self.banner_label.bind("<Button-1>", lambda e: self.open_scorchsoft())  # Bind the click event




        # Configure grid
        for i in range(2):
            main_frame.columnconfigure(i, weight=1)

    def open_scorchsoft(self, event=None):
        webbrowser.open('https://www.scorchsoft.com')

    def create_menu(self):
        self.menubar = Menu(self)
        self.config(menu=self.menubar)

        # File or settings menu
        settings_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Change API Key", command=self.change_api_key)

        # Play Menu
        play_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Play", menu=play_menu)
        play_menu.add_command(label="Retry Last Recording", command=self.retry_last_recording)

        # Help menu
        self.help_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Help", menu=self.help_menu)
        self.help_menu.add_command(label="Hide Banner", command=self.toggle_banner)
        self.help_menu.add_command(label="Terms of Use and Licence", command=self.show_terms_of_use)
        self.help_menu.add_command(label="Version", command=self.show_version)


    def toggle_banner(self):
        """Toggle the visibility of the banner image and adjust the window height."""
        current_height = self.winfo_height()
        new_height = current_height + 257 if not self.banner_visible else current_height - 257

        if self.banner_visible:
            self.banner_label.grid_remove()  # Hide the banner
            self.help_menu.entryconfig("Hide Banner", label="Show Banner")  # Update menu text
        else:
            self.banner_label.grid()  # Show the banner
            self.help_menu.entryconfig("Show Banner", label="Hide Banner")  # Update menu text

        # Set the new height and keep the current width
        self.geometry(f"{self.winfo_width()}x{new_height}")
        
        self.banner_visible = not self.banner_visible  # Toggle the visibility flag


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

    def toggle_recording(self):
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        try:
            self.device_index = self.get_device_index_by_name(self.selected_device.get())
        except ValueError as e:
            messagebox.showerror("Device Error", str(e))
            return

        self.stream = self.audio.open(format=pyaudio.paInt16,
                                      channels=1,
                                      rate=16000,
                                      input=True,
                                      frames_per_buffer=1024,
                                      input_device_index=self.device_index)

        self.frames = []
        self.recording = True
        self.record_button.config(text="Stop Recording")
        self.status_label.config(text="Status: Recording...", foreground="red")

        # Play start recording sound
        threading.Thread(target=lambda: self.play_sound("assets/pop.wav")).start()

        # Start recording in a separate thread
        self.record_thread = threading.Thread(target=self.record)
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

        self.record_button.config(text="Start Recording (Win+J)")
        self.status_label.config(text="Status: Processing...", foreground="green")

        # Play stop recording sound
        threading.Thread(target=lambda: self.play_sound("assets/pop.wav")).start()

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
            auto_apply_ai = self.process_with_gpt.get()

            # Process transcription with or without GPT as per the checkbox setting
            if auto_apply_ai:
                print("Applying AI to transcription")

                # set input box to transcription text first, just incase there is a failure
                self.transcription_text.delete("1.0", tk.END)
                self.transcription_text.insert("1.0", transcription_text)

                # Then GPT edit that transcribed text and insert
                play_text = self.process_with_gpt_model(transcription_text)
                self.transcription_text.delete("1.0", tk.END)
                self.transcription_text.insert("1.0", play_text)
            else:
                print("Outputting raw transcription")
                self.transcription_text.delete("1.0", tk.END)
                self.transcription_text.insert("1.0", transcription_text)
                play_text = transcription_text


            if self.auto_copy.get():
                self.auto_copy_text(play_text)

            if self.auto_paste.get():
                self.auto_paste_text(play_text)

            print("Transcription Complete: The audio has been transcribed and the text has been placed in the input area.")
            # Play stop recording sound
            threading.Thread(target=lambda:  self.play_sound("assets/pop.wav")).start()

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
            system_prompt = """

            # Your Purpose 
            
            You are an expert Copy Editor. 
            
            When provided with text, you provide a cleaned-up copy-edited version of that text in response. 

            Sometimes the text you are provided with will provide instructions for the output format, style or tone. If you detect such instructions then please apply them to the copy edited text, and do not write out the instructions in the returned copy-edited text. For example, if the text starts "this is for an email", or similar, then the format and structure of the copy editing should match that of an email.

            # Copy Editing Rules

            Please apply the following rules to the reply or any modified text (only deviate if asked otherwise):

            - Reply using UK spelling and grammar conventions, not US conventions (very important!). 
            - Please provide responses that are clear, engaging, informative, and conversational, using anecdotes and examples to illustrate points, with a friendly and approachable tone. 
            - Make use of proper grammar, spelling, and punctuation. 
            - Avoid using filter words or unnecessary words in replies. You don't have to re-write sentences or phrases where the copy is already clear, concise and effective.
            - Use simple, short and concise words that are easy to understand by the average non-technical reader. Avoid long, elaborate words where a shorter word can be used instead.
            - Be direct with language and avoid split infinitives. Always use active voice rather than passive voice. For example, if there is an actor in the sentence then begins with the actor of the sentence before the subject on most occasions.
            - Do not use wordy introduction sentences start with "in the", such as opening with "in a fast-paced business world", "in today's competitive landscape" or phrases of a similar style to that. Do not use the phrases "AI is a powerful tool", "imagine having", "the world of", “world of”, "comes in" or phrases of a similar style to that. 
            - Maintain consistent tense: Ensure that the verb tense is consistent throughout the text.
            - Maintain meaning: Ensure your copy edited version doesn't lose the original nuance or meaning.
            - Proper capitalization: Check and correct the capitalization of proper nouns, product names, and brand names.
            - Use compound adjectives with hyphens: When two words are used together as an adjective before a noun, add a hyphen between them.
            - Be specific and avoid repetition: If a phrase or word is used multiple times or is not clear, revise it to provide more specific information or use a synonym.
            - Use strong and concise language: Avoid weak, vague, or lengthy phrases and opt for more impactful and concise wording.
            - Punctuation for titles and references: When referencing chapter titles, books, or other works, follow the appropriate punctuation rules, such as avoiding quotation marks around chapter titles.
            - Improve clarity and coherence: Revise sentences or phrases to make the overall meaning clearer and more coherent, ensuring the text flows well.
            - Use parallel structure: Keep the same grammatical structure throughout when making a list or using coordinating conjunctions in a sentence.
            - Check and correct spelling: Ensure that all words are spelt correctly (based on UK spelling and grammar conventions) and, if applicable, follow the preferred spelling or regional variation.
            - Ensure subject-verb agreement: Check that the subject of a sentence agrees with the verb in terms of plurality.
            - Vary sentence length and structure: Aim for a balanced mix of short, medium, and long sentences in your writing. This helps create a more engaging and comfortable reading experience.
            - Use concrete and sensory language: Use words and phrases that convey specific, vivid imagery or appeal to the reader's senses. This can make your writing more evocative, memorable, and persuasive.
            - Avoid cliches and overused expressions: Replace cliches with more original, striking phrases to keep the reader's interest.
            - Use appropriate tone and level of formality for the desired context.
            - Use transitions effectively: Connect ideas and paragraphs by using transitional words, phrases, or sentences. This helps guide the reader through your argument and creates a more coherent text.
            - Be cautious with jargon and technical terms: If you need to use specialized vocabulary, make sure to explain it clearly or provide context for your reader, especially if they're likely to be unfamiliar with the terminology.
            - Avoid overuse of qualifiers and intensifiers: Words like "very- Avoid overuse of qualifiers and intensifiers: Words like "very," "quite," "rather," and "really" can weaken your writing if they're overused. Focus on strong, descriptive language instead.
            - Avoid overly flamboyant language and words. Concise and muted language is more appropriate.
            - Use subject-verb-object in most scenarios.
            - use active voice rather than passive voice.
            - Eliminate Redundancies: Remove redundant words, phrases, or sentences to tighten the prose without losing meaning or emphasis.
            - Adjust the emotional tone and persuasive elements to match the intended impact on the reader, whether it’s to inform, be friendly, persuade, entertain, or inspire. 
            - Ensure that terminology and naming conventions are consistent throughout the document. For example, if a term is introduced with a specific definition, use that term consistently without introducing synonyms that might confuse the reader.
            - Tailor the complexity and tone of the language to the target audience's knowledge level and expectations. For instance, content for a general audience should avoid jargon, whereas content for specialists can include more technical language.
            - Avoid Nominalisations: Convert nouns derived from verbs (nominalisations) back into their verb forms to make sentences more direct. For example, use "decide" instead of "make a decision".
            - Replace passive voice constructions with active voice wherever possible if it doesn't deminish meaning or impact to do so. For example, change "The report was written by the team" to "The team wrote the report".
            - Direct Statement of Purpose: State the main purpose or action of a sentence directly and early. Avoid burying the main verb or action deep in the sentence.
            - Limit Sentence Complexity: Break down overly complex or compound sentences into simpler, shorter sentences to maintain clarity and readability. Again, apply this rule where shortening doesn't impact sentence meaning or impact of the sentence.

            # Other Considerations

            - Ensure consistent use of formatting elements like bullet points, headers, and fonts. 
            - Reply as plain text without markdown tags that would look out of place if viewed without a markdown viewer.
            - Tailor your language and content to the intended audience and purpose of the document. For instance, the tone and complexity of language in an internal email may differ from that in a public-facing article.
            - Inclusivity and Sensitivity: Be mindful of inclusive language, avoiding terms that might be considered outdated or offensive. This also includes being aware of gender-neutral language, especially in a business context.
            - Optimizing for Different Media if defined: For example, if you are told that the content is intended for online use, consider principles of SEO (Search Engine Optimization) and readability on digital platforms, like shorter paragraphs and the use of subheadings.
            - Clarity in Complex Information: When dealing with complex or technical subjects, ensure clarity and accessibility for the lay reader without oversimplifying the content.
            - Soften directness in coversational language: If you detect that the nature of the content being copy edited is likely for an instant message or email, then please make sure to use friendly language, it's ok to soften the directness a little in this case to ensure the edited copy doesn't come across as rude or angry. You may also choose to retain more colloquial terms used in the transcript for emails, chat replies or other message-based content than if you think the content is to be used in other formats.

            # CRITICALLY IMPORTANT:
            - When you give your reply, give just the copy edited text. For example don't reply with "hey this is your text:" followed by the text (or anything similar to preceed), it should just be the edited text.
            - I repeat, only reply with the copy edited text.
            """

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
            threading.Thread(target=lambda:  self.play_sound("assets/wrong-short.wav")).start()
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

if __name__ == "__main__":
    app = QuickWhisper()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
