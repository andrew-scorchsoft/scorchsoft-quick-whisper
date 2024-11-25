import tkinter as tk
from tkinter import ttk, messagebox
import json
from pathlib import Path
import customtkinter as ctk

class ManagePromptsDialog:
    def __init__(self, parent):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Prompt Management")
        self.dialog.geometry("800x650")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog on the screen
        self.center_dialog()
        
        # Add a variable to track the currently selected prompt
        self.current_selected_prompt = None
        
        self.create_dialog()
        self.parent.after(100, self.update_content)

    def center_dialog(self):
        # Get the parent window position and dimensions
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()

        # Calculate position for the dialog
        dialog_width = 800  # Width from geometry
        dialog_height = 650  # Height from geometry
        position_x = parent_x + (parent_width - dialog_width) // 2
        position_y = parent_y + (parent_height - dialog_height) // 2

        # Set the position
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{position_x}+{position_y}")

    def create_dialog(self):
        # Main container frame with padding
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Create left panel (prompt selection)
        self.create_left_panel(main_frame)
        
        # Create right panel (prompt content)
        self.create_right_panel(main_frame)

        # Create bottom frame for main action button
        self.create_bottom_frame()

    def create_left_panel(self, main_frame):
        left_panel = ttk.Frame(main_frame, width=200)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)

        select_frame = ttk.LabelFrame(left_panel, text="Prompt Selection", padding="5")
        select_frame.pack(fill=tk.BOTH, expand=True)

        # Listbox for prompts with scrollbar
        self.prompt_list = tk.Listbox(select_frame, height=8, selectmode=tk.BROWSE)
        prompt_scrollbar = ttk.Scrollbar(select_frame, orient=tk.VERTICAL, command=self.prompt_list.yview)
        self.prompt_list.config(yscrollcommand=prompt_scrollbar.set)
        
        self.prompt_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5)
        prompt_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        # Populate listbox
        all_prompts = ["Default"] + list(self.parent.prompts.keys())
        for prompt in all_prompts:
            self.prompt_list.insert(tk.END, prompt)
            if prompt == self.parent.current_prompt_name:
                self.prompt_list.selection_set(all_prompts.index(prompt))

        # Button frame
        button_frame = ttk.Frame(left_panel)
        button_frame.pack(fill=tk.X, pady=5)

        # Action buttons
        self.new_button = ttk.Button(button_frame, text="New Prompt", command=self.create_new_prompt)
        self.delete_button = ttk.Button(button_frame, text="Delete", command=self.delete_current_prompt)
        
        self.new_button.pack(side=tk.LEFT, padx=2)
        self.delete_button.pack(side=tk.LEFT, padx=2)

        # Bind selection event
        self.prompt_list.bind('<<ListboxSelect>>', self.on_prompt_select)

    def on_prompt_select(self, event):
        """Handle prompt selection and update the current selection."""
        selected_indices = self.prompt_list.curselection()
        if selected_indices:
            self.current_selected_prompt = self.prompt_list.get(selected_indices[0])
            self.update_content()

    def create_right_panel(self, main_frame):
        self.right_panel = ttk.Frame(main_frame)
        self.right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        content_frame = ttk.LabelFrame(self.right_panel, text="Prompt Content", padding="5")
        content_frame.pack(fill=tk.BOTH, expand=True)

        self.edit_status_label = ttk.Label(content_frame, foreground="red")
        self.edit_status_label.pack(anchor=tk.W, padx=5, pady=(5,0))

        self.content_text = tk.Text(content_frame, wrap=tk.WORD)
        content_scrollbar = ttk.Scrollbar(content_frame, orient=tk.VERTICAL, command=self.content_text.yview)
        self.content_text.config(yscrollcommand=content_scrollbar.set)
        
        self.content_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5)
        content_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        self.save_changes_button = ttk.Button(self.right_panel, text="Save Changes", 
                                            command=self.save_content_changes, state='disabled')
        self.save_changes_button.pack(pady=(5, 0), anchor=tk.E)

    def create_bottom_frame(self):
        bottom_frame = ttk.Frame(self.dialog)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10, padx=10)

        save_button = ctk.CTkButton(
            bottom_frame,
            text="Save Selection and Exit",
            corner_radius=20,
            height=35,
            fg_color="#058705",
            hover_color="#046a38",
            font=("Arial", 13, "bold"),
            command=self.save_and_exit
        )
        save_button.pack(side=tk.BOTTOM, fill=tk.X)

    def update_content(self):
        """Update the content area with the selected prompt."""
        if not self.current_selected_prompt:
            selected_indices = self.prompt_list.curselection()
            if selected_indices:
                self.current_selected_prompt = self.prompt_list.get(selected_indices[0])
            else:
                return

        # Enable content_text before any operations
        self.content_text.config(state='normal')
        self.content_text.delete('1.0', tk.END)
        
        if self.current_selected_prompt == "Default":
            self.content_text.insert('1.0', self.parent.default_system_prompt)
            self.content_text.config(state='disabled')
            self.save_changes_button.config(state='disabled')
            self.delete_button.config(state='disabled')
            self.edit_status_label.config(
                text="(Default prompt cannot be edited)",
                foreground="red"
            )
        else:
            self.content_text.insert('1.0', self.parent.prompts[self.current_selected_prompt])
            self.content_text.config(state='normal')
            self.save_changes_button.config(state='normal')
            self.delete_button.config(state='normal')
            self.edit_status_label.config(
                text=f"{self.current_selected_prompt}",
                foreground="blue"
            )

    def save_content_changes(self):
        """Save changes to the current prompt content."""
        if not self.current_selected_prompt or self.current_selected_prompt == "Default":
            return
        
        new_content = self.content_text.get("1.0", tk.END).strip()
        if not new_content:
            messagebox.showerror("Error", "Prompt content cannot be empty")
            return

        self.parent.prompts[self.current_selected_prompt] = new_content
        self.parent.save_prompts(self.parent.prompts)
        messagebox.showinfo("Success", "Prompt changes saved successfully")

    def create_new_prompt(self):
        """Open dialog for creating a new prompt."""
        prompt_dialog = tk.Toplevel(self.dialog)
        prompt_dialog.title("Create New Prompt")
        prompt_dialog.geometry("600x400")
        prompt_dialog.transient(self.dialog)
        prompt_dialog.grab_set()
        
        # Center the new prompt dialog
        dialog_width = 600
        dialog_height = 400
        position_x = self.dialog.winfo_x() + (self.dialog.winfo_width() - dialog_width) // 2
        position_y = self.dialog.winfo_y() + (self.dialog.winfo_height() - dialog_height) // 2
        prompt_dialog.geometry(f"{dialog_width}x{dialog_height}+{position_x}+{position_y}")
        
        # Name entry
        name_frame = ttk.Frame(prompt_dialog, padding="10")
        name_frame.pack(fill=tk.X)
        ttk.Label(name_frame, text="Prompt Name:").pack(side=tk.LEFT)
        name_entry = ttk.Entry(name_frame)
        name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # System prompt
        prompt_frame = ttk.LabelFrame(prompt_dialog, text="System Prompt", padding="10")
        prompt_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        new_prompt_text = tk.Text(prompt_frame, wrap=tk.WORD, height=15)
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
            self.parent.prompts[new_name] = new_content
            self.parent.save_prompts(self.parent.prompts)

            # Update listbox and select the new prompt
            self.prompt_list.delete(0, tk.END)
            all_prompts = ["Default"] + list(self.parent.prompts.keys())
            for p in all_prompts:
                self.prompt_list.insert(tk.END, p)
            
            # Find and select the new prompt
            new_prompt_index = all_prompts.index(new_name)
            self.prompt_list.selection_clear(0, tk.END)
            self.prompt_list.selection_set(new_prompt_index)
            self.prompt_list.see(new_prompt_index)
            self.update_content()

            prompt_dialog.destroy()

        # Buttons
        button_frame = ttk.Frame(prompt_dialog)
        button_frame.pack(fill=tk.X, pady=10, padx=10)
        ttk.Button(button_frame, text="Save", 
                  command=save_new_prompt).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", 
                  command=prompt_dialog.destroy).pack(side=tk.RIGHT)

    def delete_current_prompt(self):
        """Delete the currently selected prompt."""
        selected_indices = self.prompt_list.curselection()
        if not selected_indices:
            return
        
        prompt_name = self.prompt_list.get(selected_indices[0])
        if prompt_name == "Default":
            return
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{prompt_name}'?"):
            if prompt_name == self.parent.current_prompt_name:
                self.parent.current_prompt_name = "Default"
                self.parent.save_prompt_to_env(self.parent.current_prompt_name)
                self.parent.update_model_label()

            del self.parent.prompts[prompt_name]
            self.parent.save_prompts(self.parent.prompts)
            
            # Update listbox
            self.prompt_list.delete(0, tk.END)
            for p in ["Default"] + list(self.parent.prompts.keys()):
                self.prompt_list.insert(tk.END, p)
            
            # Set current_selected_prompt to "Default" before selecting it in the listbox
            self.current_selected_prompt = "Default"
            self.prompt_list.selection_set(0)
            self.update_content()

    def save_and_exit(self):
        """Save the selected prompt and close the dialog."""
        if not self.current_selected_prompt:
            messagebox.showwarning("No Selection", "Please select a prompt before saving")
            return
        
        prompt_name = self.current_selected_prompt
        
        # First save any content changes if it's not the default prompt
        if prompt_name != "Default":
            new_content = self.content_text.get("1.0", tk.END).strip()
            if new_content:
                self.parent.prompts[prompt_name] = new_content
                self.parent.save_prompts(self.parent.prompts)
        
        # Then save the selection
        self.parent.save_prompt_to_env(prompt_name)
        self.parent.current_prompt_name = prompt_name
        self.parent.update_model_label()
        self.dialog.destroy()
        messagebox.showinfo("Success", f"Now using prompt: {prompt_name}")