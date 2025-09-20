# main.py
"""
Main entry point for the codebase translator.
"""

import sys
import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional

# Import our modules
from mapper import CodebaseMapper
from chrome_translate import ChromeTranslator, TranslationCache
from error_healer import ErrorHealer
from remove_comments import remove_comments_from_directory
from gui import TranslationGUI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("codebase_translator.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Configuration
CACHE_FOLDER = "./docs"
OUTPUT_FILE = "translation_map.json"


class CodebaseTranslator:
    """Main class to orchestrate the translation process."""
    
    def __init__(self):
        self.mapper = None
        self.translator = None
        self.cache = None
        self.healer = ErrorHealer(max_retries=3, retry_delay=1.0)
        self.gui = None
        self.translation_map: Dict[str, str] = {}
    
    def setup(self, folder_path: str, options: dict):
        """Setup the translator with folder path and options."""
        self.mapper = CodebaseMapper(folder_path)
        self.translator = ChromeTranslator(progress_callback=self._progress_callback)
        self.cache = TranslationCache(TARGET_LANG)
        
        # Set headless mode
        self.translator.headless_mode = options.get('headless_mode', False)
    
    def _progress_callback(self, current: int, total: int, message: str):
        """Handle progress updates from the translator."""
        if self.gui:
            self.gui.progress_var.set(current)
            self.gui.status_var.set(message)
            self.gui.log(message)
        else:
            print(f"Progress: {current}/{total} - {message}")
    
    def scan_codebase(self) -> List[str]:
        """Scan the codebase for Chinese words."""
        if not self.mapper:
            raise ValueError("Mapper not initialized")
        
        # Use error healer to safely execute the scan
        gui_callback = self.gui.log if self.gui else None
        word_map = self.healer.safe_execute(
            self.mapper.scan_codebase,
            gui_callback,
            context="Scanning codebase for Chinese words"
        )
        
        if word_map is None:
            logger.error("Failed to scan codebase")
            return []
        
        unique_words = self.mapper.get_unique_words()
        logger.info(f"Found {len(unique_words)} unique Chinese words")
        return unique_words
    
    def translate_words(self, words: List[str]) -> Dict[str, str]:
        """Translate a list of Chinese words."""
        if not self.translator:
            raise ValueError("Translator not initialized")
        
        # Check cache first
        untranslated_words = self.cache.get_untranslated_words(words)
        logger.info(f"Found {len(untranslated_words)} words to translate")
        
        if not untranslated_words:
            logger.info("All words are already in cache")
            return {word: self.cache.get_cached_translation(word) for word in words}
        
        # Translate the words
        translations = self.healer.safe_execute(
            self.translator.translate_words,
            untranslated_words,
            context="Translating Chinese words"
        )
        
        if translations is None:
            logger.error("Translation failed")
            return {}
        
        # Add to cache
        self.cache.add_translations(translations)
        
        # Combine with cached translations
        all_translations = {}
        for word in words:
            cached = self.cache.get_cached_translation(word)
            if cached:
                all_translations[word] = cached
            elif word in translations:
                all_translations[word] = translations[word]
            else:
                all_translations[word] = word  # Fallback
        
        return all_translations
    
    def remove_comments_and_docstrings(self, options: dict) -> bool:
        """Remove comments and docstrings from the codebase."""
        if not self.mapper:
            raise ValueError("Mapper not initialized")
        
        folder_path = self.mapper.root_path
        
        # Determine output directory
        output_dir = None
        if options.get('create_backup', True):
            output_dir = folder_path.parent / f"{folder_path.name}_cleaned"
        
        # Remove comments
        results = self.healer.safe_execute(
            remove_comments_from_directory,
            folder_path,
            output_dir,
            options.get('remove_docstrings', True),
            options.get('remove_comments', True),
            True,  # Recursive
            context="Removing comments and docstrings"
        )
        
        if results is None:
            logger.error("Failed to remove comments")
            return False
        
        success_count = sum(1 for r in results if r)
        total_count = len(results)
        logger.info(f"Successfully processed {success_count}/{total_count} files")
        return success_count == total_count
    
    def save_translation_map(self, translations: Dict[str, str], output_file: str = OUTPUT_FILE):
        """Save the translation map to a JSON file."""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(translations, f, ensure_ascii=False, indent=2)
            logger.info(f"Translation map saved to {output_file}")
        except Exception as e:
            logger.error(f"Failed to save translation map: {e}")
    
    def run_with_gui(self):
        """Run the translator with the GUI."""
        root = tk.Tk()
        self.gui = TranslationGUI(root)
        
        # Set up the actual translation function
        def start_translation():
            # Get options
            options = self.gui.get_options()
            folder_path = options['folder_path']
            
            if not folder_path:
                messagebox.showerror("Error", "Please select a folder first")
                return
            
            # Setup
            self.setup(folder_path, options)
            
            # Scan codebase
            self.gui.log("Scanning codebase for Chinese words...")
            words = self.scan_codebase()
            
            if not words:
                self.gui.log("No Chinese words found in the codebase")
                return
            
            self.gui.log(f"Found {len(words)} unique Chinese words")
            
            # Translate words
            self.gui.log("Starting translation...")
            translations = self.translate_words(words)
            
            # Save translation map
            self.save_translation_map(translations)
            
            # Remove comments if requested
            if options.get('remove_comments') or options.get('remove_docstrings'):
                self.gui.log("Removing comments and docstrings...")
                self.remove_comments_and_docstrings(options)
            
            self.gui.log("Translation process completed!")
            messagebox.showinfo("Success", "Translation process completed!")
        
        # Override the GUI's start method
        self.gui._start_translation = start_translation
        
        root.mainloop()
    
    def run_cli(self, folder_path: str, options: dict):
        """Run the translator in command-line mode."""
        # Setup
        self.setup(folder_path, options)
        
        # Scan codebase
        print("Scanning codebase for Chinese words...")
        words = self.scan_codebase()
        
        if not words:
            print("No Chinese words found in the codebase")
            return
        
        print(f"Found {len(words)} unique Chinese words")
        
        # Translate words
        print("Starting translation...")
        translations = self.translate_words(words)
        
        # Save translation map
        self.save_translation_map(translations)
        
        # Remove comments if requested
        if options.get('remove_comments') or options.get('remove_docstrings'):
            print("Removing comments and docstrings...")
            self.remove_comments_and_docstrings(options)
        
        print("Translation process completed!")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Codebase Translator")
    parser.add_argument("folder", nargs="?", help="Folder to translate (optional, will use GUI if not provided)")
    parser.add_argument("--no-docstrings", action="store_true", help="Don't remove docstrings")
    parser.add_argument("--no-comments", action="store_true", help="Don't remove comments")
    parser.add_argument("--no-code", action="store_true", help="Don't translate code files")
    parser.add_argument("--documents", action="store_true", help="Translate documents")
    parser.add_argument("--headless", action="store_true", help="Run Chrome in headless mode")
    parser.add_argument("--no-backup", action="store_true", help="Don't create backup when removing comments")
    
    args = parser.parse_args()
    
    translator = CodebaseTranslator()
    
    if args.folder:
        # Command-line mode
        options = {
            'remove_docstrings': not args.no_docstrings,
            'remove_comments': not args.no_comments,
            'translate_code_files': not args.no_code,
            'translate_documents': args.documents,
            'headless_mode': args.headless,
            'create_backup': not args.no_backup
        }
        translator.run_cli(args.folder, options)
    else:
        # GUI mode
        translator.run_with_gui()


if __name__ == "__main__":
    main()