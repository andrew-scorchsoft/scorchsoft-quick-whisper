import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from pathlib import Path
from dotenv import dotenv_values
import customtkinter as ctk

class AdjustModelsDialog:
    def __init__(self, parent):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Adjust AI Models")
        self.dialog.geometry("450x600")
        self.center_dialog()

        # Define Whisper supported languages
        self.languages = {
            "auto": "Auto Detect",
            "af": "Afrikaans",
            "ar": "Arabic",
            "hy": "Armenian",
            "az": "Azerbaijani",
            "be": "Belarusian",
            "bs": "Bosnian",
            "bg": "Bulgarian",
            "ca": "Catalan",
            "zh": "Chinese",
            "hr": "Croatian",
            "cs": "Czech",
            "da": "Danish",
            "nl": "Dutch",
            "en": "English",
            "et": "Estonian",
            "fi": "Finnish",
            "fr": "French",
            "gl": "Galician",
            "de": "German",
            "el": "Greek",
            "he": "Hebrew",
            "hi": "Hindi",
            "hu": "Hungarian",
            "is": "Icelandic",
            "id": "Indonesian",
            "it": "Italian",
            "ja": "Japanese",
            "kn": "Kannada",
            "kk": "Kazakh",
            "ko": "Korean",
            "lv": "Latvian",
            "lt": "Lithuanian",
            "mk": "Macedonian",
            "ms": "Malay",
            "mr": "Marathi",
            "mi": "Maori",
            "ne": "Nepali",
            "no": "Norwegian",
            "fa": "Persian",
            "pl": "Polish",
            "pt": "Portuguese",
            "ro": "Romanian",
            "ru": "Russian",
            "sr": "Serbian",
            "sk": "Slovak",
            "sl": "Slovenian",
            "es": "Spanish",
            "sw": "Swahili",
            "sv": "Swedish",
            "tl": "Tagalog",
            "ta": "Tamil",
            "th": "Thai",
            "tr": "Turkish",
            "uk": "Ukrainian",
            "ur": "Urdu",
            "vi": "Vietnamese",
            "cy": "Welsh"
        }

        self.create_dialog()

    def center_dialog(self):
        # Get the parent window position and dimensions
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()

        # Calculate position for the dialog
        dialog_width = 450  # Width from geometry
        dialog_height = 600  # Updated height
        position_x = parent_x + (parent_width - dialog_width) // 2
        position_y = parent_y + (parent_height - dialog_height) // 2

        # Set the position
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{position_x}+{position_y}")

    def create_dialog(self):
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Language Selection Frame
        language_frame = ttk.LabelFrame(main_frame, text="Whisper Language Settings", padding="5")
        language_frame.pack(fill="x", pady=(0, 10))

        # Language selection
        self.language_var = tk.StringVar(value=self.parent.whisper_language)
        
        # Create list of tuples and sort, but keep "auto" first
        language_values = [(code, name) for code, name in self.languages.items()]
        # Remove auto from the list
        auto_option = next(item for item in language_values if item[0] == "auto")
        language_values.remove(auto_option)
        # Sort the remaining languages
        language_values.sort(key=lambda x: x[1])
        # Add auto back at the beginning
        language_values.insert(0, auto_option)

        # Create Combobox for language selection
        language_label = ttk.Label(language_frame, text="Select Language:")
        language_label.pack(anchor="w", pady=(5, 0))
        
        self.language_combo = ttk.Combobox(language_frame, 
                                         textvariable=self.language_var,
                                         values=[f"{name} ({code})" for code, name in language_values],
                                         state="readonly")
        self.language_combo.pack(fill="x", pady=(0, 5))

        # Set current value
        current_language = self.parent.whisper_language
        current_language_name = self.languages.get(current_language, "Auto Detect")
        self.language_combo.set(f"{current_language_name} ({current_language})")

        # Model Settings Frame
        models_frame = ttk.LabelFrame(main_frame, text="AI Model Settings", padding="5")
        models_frame.pack(fill="x", pady=(0, 10))

        # Transcription Model Entry
        tk.Label(models_frame, text="OpenAI Transcription Model:").pack(anchor="w", pady=(5, 0))
        self.transcription_entry = tk.Entry(models_frame)
        self.transcription_entry.insert(0, self.parent.transcription_model)
        self.transcription_entry.pack(fill="x")
        tk.Label(models_frame, text="e.g., whisper-1", 
                font=("TkDefaultFont", 9), foreground="#4B4B4B").pack(anchor="w")

        # AI Model Entry
        tk.Label(models_frame, text="OpenAI Copyediting Model:").pack(anchor="w", pady=(10, 0))
        self.ai_entry = tk.Entry(models_frame)
        self.ai_entry.insert(0, self.parent.ai_model)
        self.ai_entry.pack(fill="x")
        tk.Label(models_frame, text="e.g., gpt-4o, gpt-4o-mini, o1-mini, o1-preview", 
                font=("TkDefaultFont", 9), foreground="#4B4B4B").pack(anchor="w")

        # Save button - using CTkButton
        save_button = ctk.CTkButton(
            main_frame,
            text="Save Changes",
            corner_radius=20,
            height=35,
            fg_color="#058705",
            hover_color="#046a38",
            font=("Arial", 13, "bold"),
            command=self.save_model_settings
        )
        save_button.pack(pady=10)

        # Link to OpenAI Pricing
        link = tk.Label(main_frame, text="View Available OpenAI Models and Pricing", 
                       fg="blue", cursor="hand2")
        link.pack(pady=(0, 10))
        link.bind("<Button-1>", lambda e: webbrowser.open("https://openai.com/api/pricing/"))

        # Instructional text
        instructional_text = ("How to use language settings:\n\n"
                            "• Auto Detect: Whisper will automatically detect the spoken language\n"
                            "• Specific Language: Select a language to optimize transcription accuracy\n\n"
                            "How to find and set model names:\n\n"
                            "Ensure you input model names exactly as they appear in the OpenAI documentation, "
                            "considering they are case-sensitive. Incorrect model names may cause the application to "
                            "malfunction due to an inability to perform relevant functions. As of this implementation, "
                            "gpt-4o is the more capable model but is more expensive. gpt-4o-mini offers a cost-effective "
                            "alternative (upto 20x cheaper) with less comprehensive world knowledge yet remains suitable "
                            "for copyediting tasks. This information will help you optimise performance and cost. We've "
                            "added the ability to change models to future proof the app and give users more control.")
        
        ttk.Label(
            main_frame, 
            text=instructional_text, 
            wraplength=430, 
            justify="left", 
            font=("TkDefaultFont", 9), 
            foreground="#4B4B4B"
        ).pack(pady=(0, 10))

    def save_model_settings(self):
        env_path = Path("config") / ".env"
        
        # Load existing .env settings into a dictionary
        if env_path.exists():
            env_vars = dotenv_values(env_path)
        else:
            env_vars = {}

        # Get selected language code from combo box
        selected_language = self.language_combo.get()
        language_code = selected_language.split('(')[-1].strip(')')

        # Update values in the dictionary
        env_vars["TRANSCRIPTION_MODEL"] = self.transcription_entry.get()
        env_vars["AI_MODEL"] = self.ai_entry.get()
        env_vars["WHISPER_LANGUAGE"] = language_code

        # Write each environment variable to the .env file
        with open(env_path, 'w') as f:
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")

        # Update parent instance variables
        self.parent.transcription_model = self.transcription_entry.get()
        self.parent.ai_model = self.ai_entry.get()
        self.parent.whisper_language = language_code
        
        # Update the model label
        self.parent.update_model_label()
        
        self.dialog.destroy() 