import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from pathlib import Path
from dotenv import dotenv_values

class AdjustModelsDialog:
    def __init__(self, parent):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Adjust AI Models")
        self.dialog.geometry("450x420")
        self.create_dialog()

    def create_dialog(self):
        # Transcription Model Entry
        tk.Label(self.dialog, text="OpenAI Transcription Model:").pack(anchor="w", padx=10, pady=(10, 0))
        self.transcription_entry = tk.Entry(self.dialog)
        self.transcription_entry.insert(0, self.parent.transcription_model)
        self.transcription_entry.pack(fill="x", padx=10)
        tk.Label(self.dialog, text="e.g., whisper-1", font=("TkDefaultFont", 9), foreground="#4B4B4B").pack(anchor="w", padx=10)

        # AI Model Entry
        tk.Label(self.dialog, text="OpenAI Copyediting Model:").pack(anchor="w", padx=10, pady=(10, 0))
        self.ai_entry = tk.Entry(self.dialog)
        self.ai_entry.insert(0, self.parent.ai_model)
        self.ai_entry.pack(fill="x", padx=10)
        tk.Label(self.dialog, text="e.g., gpt-4o, gpt-4o-mini, o1-mini, o1-preview", 
                font=("TkDefaultFont", 9), foreground="#4B4B4B").pack(anchor="w", padx=10)

        # Save button
        save_button = ttk.Button(self.dialog, text="Save", command=self.save_model_settings)
        save_button.pack(pady=10)

        # Link to OpenAI Pricing
        link = tk.Label(self.dialog, text="View Available OpenAI Models and Pricing", fg="blue", cursor="hand2")
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
        tk.Label(self.dialog, text=instructional_text, wraplength=430, justify="left", 
                font=("TkDefaultFont", 9), foreground="#4B4B4B").pack(pady=(10, 0), padx=10)

    def save_model_settings(self):
        env_path = Path("config") / ".env"
        
        # Load existing .env settings into a dictionary
        if env_path.exists():
            env_vars = dotenv_values(env_path)
        else:
            env_vars = {}

        # Update model values in the dictionary
        env_vars["TRANSCRIPTION_MODEL"] = self.transcription_entry.get()
        env_vars["AI_MODEL"] = self.ai_entry.get()

        # Write each environment variable to the .env file
        with open(env_path, 'w') as f:
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")

        # Update parent instance variables
        self.parent.transcription_model = self.transcription_entry.get()
        self.parent.ai_model = self.ai_entry.get()
        
        # Add this line to update the model label
        self.parent.update_model_label()
        
        self.dialog.destroy() 