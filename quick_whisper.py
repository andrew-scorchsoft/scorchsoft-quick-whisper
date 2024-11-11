import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, Menu
import threading
import pyaudio
import wave
import os
import sys
import json
import platform
import webbrowser
import openai
import pyperclip
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from pydub import AudioSegment
from audioplayer import AudioPlayer
import keyboard  # For auto-paste functionality
from pystray import Icon as icon, MenuItem as item, Menu as menu


# Load environment variables from config/.env
def load_env_file():
    env_path = Path("config") / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)

class QuickWhisper(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Simple Speech to Text")
        self.geometry("600x400")
        self.version = "1.0.0"
        self.resizable(False, False)

        load_env_file()
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

        

        self.recording = False
        self.frames = []

        keyboard.add_hotkey('win+j', self.toggle_recording)

        self.create_menu()
        self.create_widgets()

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
            self.client = OpenAI(api_key=self.api_key)
            messagebox.showinfo("API Key Updated", "The OpenAI API Key has been updated successfully.")

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
        ttk.Label(main_frame, text="Select Input Device:").grid(row=0, column=0, sticky=tk.W, pady=(0,10))
        devices = self.get_input_devices()
        if not devices:
            messagebox.showerror("No Input Devices", "No input audio devices found.")
            self.destroy()
            return
        self.selected_device.set(list(devices.keys())[0])  # Default selection
        device_menu = ttk.OptionMenu(main_frame, self.selected_device, self.selected_device.get(), *devices.keys())
        device_menu.grid(row=0, column=1, sticky=tk.W, pady=(0,10))

        # Record Button
        self.record_button = ttk.Button(main_frame, text="Start Recording", command=self.toggle_recording)
        self.record_button.grid(row=1, column=0, columnspan=2, pady=(0,10), sticky="ew")

        # Auto-Copy Checkbox
        auto_copy_cb = ttk.Checkbutton(main_frame, text="Auto-Copy to Clipboard on Transcription", variable=self.auto_copy)
        auto_copy_cb.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(0,10))

        # Auto-Paste Checkbox
        auto_paste_cb = ttk.Checkbutton(main_frame, text="Auto-Paste Clipboard on Transcription", variable=self.auto_paste)
        auto_paste_cb.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(0,10))

        # Transcription Text Area
        ttk.Label(main_frame, text="Transcription:").grid(row=4, column=0, sticky=tk.W)
        self.transcription_text = tk.Text(main_frame, height=10, width=70)
        self.transcription_text.grid(row=5, column=0, columnspan=2, pady=(0,10))

        # Optional GPT Processing
        self.process_with_gpt = tk.BooleanVar()
        gpt_cb = ttk.Checkbutton(main_frame, text="Auto Copy-edit with gpt-4o", variable=self.process_with_gpt)
        gpt_cb.grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=(0,10))

        # Status Label
        self.status_label = ttk.Label(main_frame, text="Status: Idle", foreground="blue")
        self.status_label.grid(row=7, column=0, columnspan=2, sticky=tk.W)

        # Configure grid
        for i in range(2):
            main_frame.columnconfigure(i, weight=1)

    def create_menu(self):
        self.menubar = Menu(self)
        self.config(menu=self.menubar)

        # File or settings menu
        settings_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Change API Key", command=self.change_api_key)



        # Help menu
        help_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Terms of Use and Licence", command=self.show_terms_of_use)
        help_menu.add_command(label="Version", command=self.show_version)

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
                break

    def stop_recording(self):
        self.recording = False
        self.record_thread.join()

        self.stream.stop_stream()
        self.stream.close()

        self.record_button.config(text="Start Recording")
        self.status_label.config(text="Status: Processing...", foreground="green")

        # Play stop recording sound
        threading.Thread(target=lambda:  self.play_sound("assets/pop.wav")).start()

        # Save the recorded data to a temporary WAV file
        self.audio_file = "temp_recording.wav"
        wf = wave.open(self.audio_file, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(16000)
        wf.writeframes(b''.join(self.frames))
        wf.close()

        # Start transcription in a separate thread
        threading.Thread(target=self.transcribe_audio).start()

    def transcribe_audio(self):
        file_path = self.audio_file

        try:
            with open(str(file_path), "rb") as audio_file:
                # Use OpenAI's transcription API as intended
                transcription = self.client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-1",
                    response_format="verbose_json"
                )

            # Retrieve the transcription text correctly
            transcription_text = transcription.get("text", "") if isinstance(transcription, dict) else transcription.text
            auto_apply_ai = self.process_with_gpt.get()

            # Process transcription with or without GPT as per the checkbox setting
            if auto_apply_ai:
                print("Applying AI to transcription")
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
            print(f"Transcription error: An error occurred during transcription: {str(e)}")
            self.status_label.config(text="Status: Error during transcription", foreground="red")
        finally:
            self.status_label.config(text="Status: Idle", foreground="blue")
            if os.path.exists(file_path):
                os.remove(file_path)


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
            You are an expert copy editor. When provided with text, you provide a cleaned-up copy-edited version of that text. If a style is specified, please adopt that style.

            #Copy Editing Styles:
            1) General Business 
            2) Books/Articles
            3) Emails

            #Copy Editing Rules

            Please apply the following rules to the reply or any modified text:
            - Reply using UK spelling and grammar conventions, not US conventions (very important!). 
            - Please provide responses that emulate the described writing style: clear, engaging, informative, and conversational, using anecdotes and examples to illustrate points, with a friendly and approachable tone. 
            - Make use of proper grammar, spelling, and punctuation. 
            - Avoid using filter words or unnecessary words in replies. You don't have to re-write sentences or phrases where the copy is already clear, concise and effective.
            - Use simple, short and concise words that are easy to understand by the average non-technical reader. Avoid long, elaborate words where a shorter word can be used instead.
            - Be direct with language and avoid split infinitives. Always use active voice rather than passive voice. For example, if there is an actor in the sentence then begins with the actor of the sentence before the subject on most occasions.
            - Do not use wordy introduction sentences start with "in the", such as opening with "in a fast-paced business world", "in today's competitive landscape" or phrases of a similar style to that. Do not use the phrases "AI is a powerful tool", "imagine having", "the world of", “world of”, "comes in" or phrases of a similar style to that. 
            - Maintain consistent tense: Ensure that the verb tense is consistent throughout the text.
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
            - Adjust the emotional tone and persuasive elements to match the intended impact on the reader, whether it’s to inform, persuade, entertain, or inspire.
            - Ensure that terminology and naming conventions are consistent throughout the document. For example, if a term is introduced with a specific definition, use that term consistently without introducing synonyms that might confuse the reader.
            - Tailor the complexity and tone of the language to the target audience's knowledge level and expectations. For instance, content for a general audience should avoid jargon, whereas content for specialists can include more technical language.
            - Avoid Nominalisations: Convert nouns derived from verbs (nominalisations) back into their verb forms to make sentences more direct. For example, use "decide" instead of "make a decision".
            - Replace passive voice constructions with active voice wherever possible. For example, change "The report was written by the team" to "The team wrote the report".
            - Direct Statement of Purpose: State the main purpose or action of a sentence directly and early. Avoid burying the main verb or action deep in the sentence.
            - Limit Sentence Complexity: Break down overly complex or compound sentences into simpler, shorter sentences to maintain clarity and readability.

            #Other Considerations
            - Ensure consistent use of formatting elements like bullet points, headers, and fonts. 
            - Tailor your language and content to the intended audience and purpose of the document. For instance, the tone and complexity of language in an internal email may differ from that in a public-facing article.
            - Inclusivity and Sensitivity: Be mindful of inclusive language, avoiding terms that might be considered outdated or offensive. This also includes being aware of gender-neutral language, especially in a business context.
            - Fact-Checking and Accuracy: Especially for non-fiction books and articles, ensure that all factual statements are accurate and sourced appropriately. This includes checking dates, names, statistics, and quotations.
            - Optimizing for Different Media: If the content is intended for online use, consider principles of SEO (Search Engine Optimization) and readability on digital platforms, like shorter paragraphs and the use of subheadings.
            - Legal Compliance: Be aware of any legal implications of the content, especially regarding copyright, libel, and compliance with industry-specific regulations.
            -Clarity in Complex Information: When dealing with complex or technical subjects, ensure clarity and accessibility for the lay reader without oversimplifying the content.

            #Approach to take:
            - If the person you speak with opens the conversation with nothing but text and no instruction, please apply the standard Copy Editing Rules above to all text.
            - If someone says "please copyright in the [something] style/format" then please acknowledge concisely and ask them to provide the text to copy edit.
            """

            user_prompt = "Here is the transcription \r\n<transcription>\r\n" + text + "\r\n</transcription>\r\n"

            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=4000
            )
            gpt_text = response.choices[0].message.content
            return gpt_text
        except Exception as e:
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
        license_path = self.resource_path("LICENSE.md")

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
