# gui.py
"""
Minimal GUI for the translation system.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from tkinter import StringVar, BooleanVar
from pathlib import Path
from typing import Callable
import time


class TranslationGUI:
    """Minimal GUI for the translation system."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Codebase Translator")
        self.root.geometry("800x600")

        # Variables
        self.folder_path = StringVar()
        self.remove_docstrings = BooleanVar(value=True)
        self.remove_comments = BooleanVar(value=True)
        self.translate_code_files = BooleanVar(value=True)
        self.translate_documents = BooleanVar(value=False)
        self.headless_mode = BooleanVar(value=False)

        # Progress tracking
        self.progress_var = tk.DoubleVar()
        self.status_var = StringVar(value="Ready")

        # Create GUI elements
        self._create_widgets()

    def _create_widgets(self):
        """Create all GUI widgets."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Folder selection
        folder_frame = ttk.Frame(main_frame)
        folder_frame.pack(fill=tk.X, pady=5)

        ttk.Label(folder_frame, text="Select Folder:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(folder_frame, textvariable=self.folder_path, width=50).pack(
            side=tk.LEFT, padx=5, fill=tk.X, expand=True
        )
        ttk.Button(folder_frame, text="Browse", command=self._browse_folder).pack(
            side=tk.LEFT, padx=5
        )

        # Options frame
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10")
        options_frame.pack(fill=tk.X, pady=10)

        # First row of options
        row1 = ttk.Frame(options_frame)
        row1.pack(fill=tk.X, pady=2)

        ttk.Checkbutton(
            row1, text="Remove Docstrings", variable=self.remove_docstrings
        ).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(
            row1, text="Remove Comments", variable=self.remove_comments
        ).pack(side=tk.LEFT, padx=5)

        # Second row of options
        row2 = ttk.Frame(options_frame)
        row2.pack(fill=tk.X, pady=2)

        ttk.Checkbutton(
            row2, text="Translate Code Files", variable=self.translate_code_files
        ).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(
            row2, text="Translate Documents", variable=self.translate_documents
        ).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(row2, text="Headless Mode", variable=self.headless_mode).pack(
            side=tk.LEFT, padx=5
        )

        # Progress bar
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=10)

        ttk.Label(progress_frame, text="Progress:").pack(side=tk.LEFT, padx=5)
        ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100).pack(
            side=tk.LEFT, padx=5, fill=tk.X, expand=True
        )
        ttk.Label(progress_frame, textvariable=self.status_var).pack(
            side=tk.LEFT, padx=5
        )

        # Log area
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(
            button_frame, text="Start Translation", command=self._start_translation
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Log", command=self._clear_log).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(button_frame, text="Exit", command=self.root.quit).pack(
            side=tk.RIGHT, padx=5
        )

    def _browse_folder(self):
        """Browse for a folder."""
        folder = filedialog.askdirectory()
        if folder:
            self.folder_path.set(folder)
            self.log(f"Selected folder: {folder}")

    def _start_translation(self):
        """Start the translation process."""
        folder = self.folder_path.get()
        if not folder:
            messagebox.showerror("Error", "Please select a folder first")
            return

        if not Path(folder).exists():
            messagebox.showerror("Error", "Selected folder does not exist")
            return

        # Get options
        options = {
            "remove_docstrings": self.remove_docstrings.get(),
            "remove_comments": self.remove_comments.get(),
            "translate_code_files": self.translate_code_files.get(),
            "translate_documents": self.translate_documents.get(),
            "headless_mode": self.headless_mode.get(),
        }

        self.log(f"Starting translation with options: {options}")

        # This would be replaced with actual translation logic
        # For now, just simulate progress
        self._simulate_translation()

    def _simulate_translation(self):
        """Simulate translation progress for demonstration."""

        def update_progress():
            for i in range(101):
                self.progress_var.set(i)
                self.status_var.set(f"Processing... {i}%")
                self.root.update()
                self.root.after(50)  # 50ms delay

            self.status_var.set("Translation completed!")
            self.log("Translation completed successfully!")
            messagebox.showinfo("Success", "Translation completed!")

        # Run in a separate thread to avoid blocking the GUI
        self.root.after(100, update_progress)

    def _clear_log(self):
        """Clear the log text."""
        self.log_text.delete(1.0, tk.END)

    def log(self, message: str):
        """Add a message to the log."""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)  # Scroll to end

    def set_progress_callback(self, callback: Callable[[int, int, str], None]):
        """Set a callback function to handle progress updates."""
        self.progress_callback = callback

    def get_options(self) -> dict:
        """Get the current options as a dictionary."""
        return {
            "folder_path": self.folder_path.get(),
            "remove_docstrings": self.remove_docstrings.get(),
            "remove_comments": self.remove_comments.get(),
            "translate_code_files": self.translate_code_files.get(),
            "translate_documents": self.translate_documents.get(),
            "headless_mode": self.headless_mode.get(),
        }


# Example usage
if __name__ == "__main__":
    import time

    root = tk.Tk()
    app = TranslationGUI(root)
    root.mainloop()
