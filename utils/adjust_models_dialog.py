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
        # Define transcription models and their types for internal processing
        self.transcription_models = {
            "gpt-4o-transcribe": "gpt",
            "whisper-1": "whisper",
            "other": "unknown"
        }
        
        # Define LLM models for copy-editing (order matters for UI display)
        self.llm_models = [
            "gpt-5",
            "gpt-5-mini",
            "gpt-5-nano",
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4.1-nano",
            "gpt-4o",
            "gpt-4o-mini",
            "other"
        ]

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

        # Create a separate frame for all transcription model components
        transcription_section = ttk.Frame(models_frame)
        transcription_section.pack(fill="x", pady=(5, 15))

        # Transcription Model Selection - renamed label
        tk.Label(transcription_section, text="Transcription Model:").pack(anchor="w")
        
        # Variables for model selection
        self.transcription_model_var = tk.StringVar()
        self.custom_model_var = tk.StringVar()
        
        # Create a container frame for the dropdown
        dropdown_frame = ttk.Frame(transcription_section)
        dropdown_frame.pack(fill="x", pady=(5, 0))
        
        # Function to handle model selection change
        def on_model_change(*args):
            selected = self.transcription_model_var.get()
            if selected == "other":
                self.custom_frame.pack(fill="x", pady=(5, 0))
                self.custom_model_entry.focus()
            else:
                self.custom_frame.pack_forget()
        
        # Set up model dropdown
        self.transcription_model_combo = ttk.Combobox(dropdown_frame, 
                                                     textvariable=self.transcription_model_var,
                                                     values=list(self.transcription_models.keys()),
                                                     state="readonly")
        self.transcription_model_combo.pack(fill="x")
        
        # Create a frame for custom model input to keep it organized
        self.custom_frame = ttk.Frame(transcription_section)
        self.custom_model_label = ttk.Label(self.custom_frame, text="Enter custom transcriptionmodel name:")
        self.custom_model_label.pack(anchor="w")
        self.custom_model_entry = ttk.Entry(self.custom_frame, textvariable=self.custom_model_var)
        self.custom_model_entry.pack(fill="x", pady=(2, 0))
        
        # Set initial values based on current model
        current_model = self.parent.transcription_model
        if current_model in self.transcription_models:
            self.transcription_model_var.set(current_model)
        else:
            self.transcription_model_var.set("other")
            self.custom_model_var.set(current_model)
            self.custom_frame.pack(fill="x", pady=(5, 0))
        
        # Bind the change event
        self.transcription_model_var.trace("w", on_model_change)
        
        # Model type info
        model_type_text = ("Note: GPT models provide higher quality transcription with broad language support.\n"
                           "Whisper is the traditional speech recognition model.")
        ttk.Label(transcription_section, text=model_type_text, 
                 font=("TkDefaultFont", 9), foreground="#4B4B4B").pack(anchor="w", pady=(8, 0))

        # AI Model Entry - after the transcription section with clean separation
        tk.Label(models_frame, text="OpenAI Copyediting Model:").pack(anchor="w", pady=(5, 0))
        
        # Variables for LLM model selection
        self.llm_model_var = tk.StringVar()
        self.custom_llm_var = tk.StringVar()
        
        # Create a container frame for the dropdown
        llm_dropdown_frame = ttk.Frame(models_frame)
        llm_dropdown_frame.pack(fill="x", pady=(5, 0))
        
        # Function to handle model selection change
        def on_llm_change(*args):
            selected = self.llm_model_var.get()
            if selected == "other":
                self.custom_llm_frame.pack(fill="x", pady=(5, 0))
                self.custom_llm_entry.focus()
            else:
                self.custom_llm_frame.pack_forget()
        
        # Set up model dropdown
        self.llm_model_combo = ttk.Combobox(llm_dropdown_frame, 
                                           textvariable=self.llm_model_var,
                                           values=list(self.llm_models),
                                           state="readonly")
        self.llm_model_combo.pack(fill="x")
        
        # Create a frame for custom model input
        self.custom_llm_frame = ttk.Frame(models_frame)
        self.custom_llm_label = ttk.Label(self.custom_llm_frame, text="Enter custom copyediting model name:")
        self.custom_llm_label.pack(anchor="w")
        self.custom_llm_entry = ttk.Entry(self.custom_llm_frame, textvariable=self.custom_llm_var)
        self.custom_llm_entry.pack(fill="x", pady=(2, 0))
        
        # Set initial values based on current model
        current_llm = self.parent.ai_model
        if current_llm in self.llm_models:
            self.llm_model_var.set(current_llm)
        else:
            self.llm_model_var.set("other")
            self.custom_llm_var.set(current_llm)
            self.custom_llm_frame.pack(fill="x", pady=(5, 0))
        
        # Bind the change event
        self.llm_model_var.trace("w", on_llm_change)
        
        # Model info
        llm_info_text = "e.g., gpt-5, gpt-4o, gpt-4o-mini, o1-mini, o1-preview"
        ttk.Label(models_frame, text=llm_info_text, 
                 font=("TkDefaultFont", 9), foreground="#4B4B4B").pack(anchor="w", pady=(5, 0))

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
                            "How to select transcription models:\n\n"
                            "• GPT-4o-transcribe: Highest quality transcription with broad language support\n"
                            "• Whisper-1: Traditional speech recognition model\n"
                            "• Other: Custom model name (advanced usage)\n\n"
                            "For copyediting models, ensure you input model names exactly as they appear "
                            "in the OpenAI documentation. gpt-4o offers the best quality while gpt-4o-mini "
                            "is more cost-effective (up to 20x cheaper) and still suitable for most copyediting tasks.")
        
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

        # Get the selected transcription model
        if self.transcription_model_var.get() == "other":
            transcription_model = self.custom_model_var.get().strip()
            if not transcription_model:
                messagebox.showerror("Error", "Custom model name cannot be empty")
                return
            model_type = "unknown"
        else:
            transcription_model = self.transcription_model_var.get()
            model_type = self.transcription_models[transcription_model]
            
        print(f"Saving model: '{transcription_model}' | Type: '{model_type}'")
            
        # Get the selected LLM model
        if self.llm_model_var.get() == "other":
            llm_model = self.custom_llm_var.get().strip()
            if not llm_model:
                messagebox.showerror("Error", "Custom copyediting model name cannot be empty")
                return
        else:
            llm_model = self.llm_model_var.get()
            
        print(f"Saving LLM model: '{llm_model}'")
            
        # Update values in the dictionary
        env_vars["TRANSCRIPTION_MODEL"] = transcription_model
        env_vars["TRANSCRIPTION_MODEL_TYPE"] = model_type
        env_vars["AI_MODEL"] = llm_model
        env_vars["WHISPER_LANGUAGE"] = language_code

        # Write each environment variable to the .env file
        try:
            print(f"Writing to .env file at {env_path}")
            with open(env_path, 'w') as f:
                for key, value in env_vars.items():
                    if value is None or value.strip() == "":
                        print(f"Warning: Empty value for key {key}, using default")
                        continue
                    f.write(f"{key}={value}\n")
                    print(f"Wrote: {key}={value}")
            print("Successfully updated .env file")
        except Exception as e:
            print(f"Error writing .env file: {e}")
            messagebox.showerror("File Error", f"Could not save settings: {e}")

        # Update parent instance variables
        self.parent.transcription_model = transcription_model
        self.parent.transcription_model_type = model_type
        self.parent.ai_model = llm_model
        self.parent.whisper_language = language_code
        
        # Update the model label
        self.parent.update_model_label()
        
        self.dialog.destroy() 
        self.dialog.destroy() 