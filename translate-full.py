import os
import shutil
import json
import re
import logging
import asyncio
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from tkinter import StringVar
from dataclasses import dataclass, field
from typing import Dict, List, Set
import aiofiles
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
from concurrent.futures import ThreadPoolExecutor
import traceback
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("translation_app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class Config:
    input_dir: Path
    cache_dir: Path
    output_dir: Path
    workers: int = 10
    blacklist: Set[str] = field(
        default_factory=lambda: {
            ".git",
            "__pycache__",
            "build",
            "dist",
            "venv",
            ".idea",
            ".vs",
            "node_modules",
            ".pytest_cache",
            ".mypy_cache",
            "__snapshots__",
            ".next",
            ".nuxt",
        }
    )

    # Code-related extensions
    code_extensions: Set[str] = field(
        default_factory=lambda: {
            ".py",
            ".js",
            ".ts",
            ".java",
            ".cpp",
            ".c",
            ".h",
            ".hpp",
            ".cs",
            ".php",
            ".rb",
            ".go",
            ".rs",
            ".swift",
            ".kt",
            ".scala",
            ".m",
            ".sql",
            ".r",
            ".sh",
            ".bash",
            ".ps1",
            ".html",
            ".css",
            ".scss",
            ".sass",
            ".less",
            ".ejs",
            ".vue",
            ".jsx",
            ".tsx",
            ".json",
            ".wasm",
            ".module",
            ".map",
            ".nsh",
            ".LICENSE",
        }
    )

    # Document extensions
    document_extensions: Set[str] = field(
        default_factory=lambda: {
            ".txt",
            ".md",
            ".rtf",
            ".odt",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".pdf",
            ".epub",
            ".mobi",
            ".csv",
            ".ods",
            ".odp",
            ".sample",
        }
    )

    # Asset extensions
    asset_extensions: Set[str] = field(
        default_factory=lambda: {
            ".png",
            ".svg",
            ".ico",
            ".icns",
            ".woff",
            ".woff2",
            ".plist",
            ".idx",
            ".pack",
            ".rev",
        }
    )

    # Binary extensions (to skip)
    binary_extensions: Set[str] = field(
        default_factory=lambda: {
            ".woff",
            ".woff2",
            ".ttf",
            ".eot",
            ".otf",
            ".exe",
            ".dll",
            ".so",
            ".dylib",
            ".bin",
            ".zip",
            ".tar",
            ".gz",
            ".rar",
            ".7z",
            ".mp3",
            ".mp4",
            ".wav",
            ".avi",
            ".mov",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".pdf",
            ".wasm",
            ".idx",
            ".pack",
            ".rev",
        }
    )

    # Default to code extensions
    extensions_to_scan: Set[str] = field(default_factory=lambda: set())

    def get_extensions_by_type(self, scan_type: str) -> Set[str]:
        if scan_type == "code":
            return self.code_extensions
        elif scan_type == "documents":
            return self.document_extensions
        else:  # "all"
            return (
                self.code_extensions | self.document_extensions | self.asset_extensions
            )

    @classmethod
    def get_default_binary_extensions(cls) -> Set[str]:
        """Get binary extensions without creating a Config instance"""
        return {
            ".woff",
            ".woff2",
            ".ttf",
            ".eot",
            ".otf",
            ".exe",
            ".dll",
            ".so",
            ".dylib",
            ".bin",
            ".zip",
            ".tar",
            ".gz",
            ".rar",
            ".7z",
            ".mp3",
            ".mp4",
            ".wav",
            ".avi",
            ".mov",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".pdf",
            ".wasm",
            ".idx",
            ".pack",
            ".rev",
        }


class ForeignWordCache:
    def __init__(self, cache_dir: Path, cache_filename="ForeignWordMap.json"):
        self.cache_dir = cache_dir
        self.cache_file = cache_dir / cache_filename
        self.cache: Set[str] = set()
        self.modified = False

    async def initialize(self):
        """Initialize cache from existing file and deduplicate"""
        await self._load_cache()
        await self.deduplicate()
        logging.info(f"Loaded {len(self.cache)} foreign words from cache")

    async def _load_cache(self):
        """Load foreign words from existing cache file"""
        try:
            if self.cache_file.exists():
                async with aiofiles.open(self.cache_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                    self.cache = set(json.loads(content))
                logging.info(f"Successfully loaded cache from {self.cache_file}")
            else:
                logging.warning(f"Cache file not found at {self.cache_file}")
                self.cache = set()
        except Exception as e:
            logging.error(f"Error loading cache: {str(e)}")
            self.cache = set()

    async def deduplicate(self):
        """Remove duplicate words from cache"""
        original_size = len(self.cache)
        self.cache = set(self.cache)
        new_size = len(self.cache)

        if original_size != new_size:
            self.modified = True
            logging.info(
                f"Removed {original_size - new_size} duplicate words from cache"
            )
            await self.save()

    async def save(self):
        """Save cache to file if modified"""
        if not self.modified:
            return

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(self.cache_file, "w", encoding="utf-8") as f:
                await f.write(
                    json.dumps(list(self.cache), ensure_ascii=False, indent=2)
                )
            self.modified = False
            logging.info(f"Saved {len(self.cache)} foreign words to cache")
        except Exception as e:
            logging.error(f"Error saving cache: {str(e)}")

    def contains(self, word: str) -> bool:
        """Check if word is in cache"""
        return word in self.cache

    async def add(self, words: Set[str]):
        """Add new foreign words to cache"""
        new_words = words - self.cache
        if new_words:
            self.cache.update(new_words)
            self.modified = True
            logging.info(f"Added {len(new_words)} new foreign words to cache")
            await self.save()


class ForeignWordScanner:
    def __init__(self, config: Config, cache: ForeignWordCache, progress_callback=None):
        self.config = config
        self.cache = cache
        self.progress_callback = progress_callback
        self.executor = ThreadPoolExecutor(max_workers=config.workers)

    def is_binary_file(self, file_path: Path) -> bool:
        """Check if a file is likely to be binary based on extension and content"""
        if file_path.suffix.lower() in Config.get_default_binary_extensions():
            logging.debug(f"Skipping known binary file type: {file_path.suffix}")
            return True

        try:
            chunk_size = 1024
            with open(file_path, "rb") as f:
                chunk = f.read(chunk_size)
            text_characters = bytearray(
                {7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7F}
            )
            return bool(chunk.translate(None, text_characters))
        except Exception as e:
            logging.debug(f"Error checking if file is binary {file_path}: {str(e)}")
            return True

    def _scan_file(self, file_path: Path):
        """Scan a single file for foreign words"""
        try:
            if self.is_binary_file(file_path):
                logging.debug(f"Skipping binary file: {file_path}")
                return

            encodings = ["utf-8", "utf-16", "latin1", "cp1252", "ascii"]
            content = None

            for encoding in encodings:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    logging.debug(f"Failed to read with encoding {encoding}: {str(e)}")
                    continue

            if content is None:
                logging.warning(
                    f"Could not decode file {file_path} with any supported encoding"
                )
                return

            foreign_words = self._extract_foreign_words(content)
            new_words = {
                word for word in foreign_words if not self.cache.contains(word)
            }

            if new_words:
                asyncio.run(self.cache.add(new_words))

        except Exception as e:
            logging.error(f"Error scanning file {file_path}: {str(e)}")
            traceback.print_exc()

    def _extract_foreign_words(self, content: str) -> Set[str]:
        """Extract foreign words from content"""
        # Extract non-ASCII characters (including emojis)
        foreign_words = set()

        # Extract words with non-ASCII characters
        main_pattern = re.findall(r"\b[^\x00-\x7F]+\b", content)
        additional_pattern = re.findall(r"[^\x00-\x7F]+", content)

        # Extract emojis
        emoji_pattern = re.findall(
            r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251\U0001F900-\U0001F9FF]",
            content,
        )

        # Combine all patterns
        foreign_words = set(main_pattern + additional_pattern + emoji_pattern)
        return foreign_words

    async def scan_project(self, progress_callback=None):
        """Scan the project for foreign words"""
        logging.info(f"Starting project scan from {self.config.input_dir}")

        self._found_words = set()
        self._found_words_lock = threading.Lock()

        try:
            files_to_scan = [
                file_path
                for file_path in self.config.input_dir.rglob("*")
                if (
                    file_path.is_file()
                    and file_path.suffix.lower() in self.config.extensions_to_scan
                    and not any(p in file_path.parts for p in self.config.blacklist)
                )
            ]

            total_files = len(files_to_scan)
            logging.info(f"Found {total_files} files to scan")

            if progress_callback:
                progress_callback(0, total_files, "Scanning files...")

            loop = asyncio.get_event_loop()
            batch_size = 10
            for i in range(0, len(files_to_scan), batch_size):
                batch = files_to_scan[i : i + batch_size]
                tasks = []
                for file_path in batch:
                    tasks.append(
                        loop.run_in_executor(self.executor, self._scan_file, file_path)
                    )

                await asyncio.gather(*tasks)

                if progress_callback:
                    current = min(i + batch_size, total_files)
                    progress_callback(
                        current,
                        total_files,
                        f"Scanning files... {current}/{total_files}",
                    )

            if hasattr(self, "_found_words") and self._found_words:
                new_words = {w for w in self._found_words if not self.cache.contains(w)}
                if new_words:
                    await self.cache.add(new_words)
                    logging.info(f"Added {len(new_words)} words to cache")

            logging.info(f"Completed scanning {total_files} files")

            return {
                "total_files": total_files,
                "files_with_foreign_words": getattr(
                    self, "files_with_foreign_words", 0
                ),
                "new_words_found": len(getattr(self, "_found_words", set())),
                "total_cache_size": len(self.cache.cache),
            }

        except Exception as e:
            logging.error(f"Error during scan: {str(e)}")
            traceback.print_exc()
            raise
        finally:
            await self.cache.save()
            logging.info("Project scan completed")


class GoogleTranslateAPI:
    """Simple Google Translate API fallback"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )
        self.base_url = "https://translate.googleapis.com/translate_a/single"

    def translate_text(
        self, text: str, source_lang: str = "auto", target_lang: str = "en"
    ) -> str:
        """Translate text using Google Translate API"""
        try:
            params = {
                "client": "gtx",
                "sl": source_lang,
                "tl": target_lang,
                "dt": "t",
                "q": text,
            }

            response = self.session.get(self.base_url, params=params)
            response.raise_for_status()

            data = response.json()
            if data and len(data) > 0 and len(data[0]) > 0:
                return data[0][0][0]
            return text
        except Exception as e:
            logging.warning(f"Google Translate API failed for '{text}': {str(e)}")
            return text

    def translate_batch(
        self, texts: List[str], source_lang: str = "auto", target_lang: str = "en"
    ) -> Dict[str, str]:
        """Translate multiple texts"""
        results = {}
        for text in texts:
            if text and text.strip():
                translated = self.translate_text(text, source_lang, target_lang)
                results[text] = translated
                time.sleep(0.1)  # Avoid rate limiting
            else:
                results[text] = text
        return results


class ChromeTranslator:
    def __init__(self, progress_callback=None):
        self.driver = None
        self.translations = {}
        self.progress_callback = progress_callback
        self.temp_file = None
        self.translation_failed = False
        self.fallback_translator = GoogleTranslateAPI()
        self.root = None

    def setup_driver(self, headless=False):
        """Setup Chrome driver with enhanced translation options"""
        chrome_options = Options()

        if headless:
            chrome_options.add_argument("--headless=new")

        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-images")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--lang=en-US")

        # Enhanced translation settings
        prefs = {
            "translate": {"enabled": True},
            "translate.enabled": True,
            "translate_whitelists": {
                "zh": "en",
                "zh-CN": "en",
                "zh-TW": "en",
                "ja": "en",
                "ko": "en",
                "ar": "en",
                "ru": "en",
                "fr": "en",
                "de": "en",
                "es": "en",
                "it": "en",
                "pt": "en",
                "hi": "en",
                "th": "en",
                "vi": "en",
            },
            "translate_accepted_languages": ["en"],
            "translate_site_blacklist": [],
            "profile.default_content_setting_values": {"notifications": 2},
        }
        chrome_options.add_experimental_option("prefs", prefs)

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(120)
            logging.info("Chrome driver setup successful")
            return True
        except WebDriverException as e:
            logging.error(f"Failed to setup Chrome driver: {str(e)}")
            return False

    def create_translation_html(self, words: List[str]) -> Path:
        """Create an HTML page optimized for translation extraction"""
        self.temp_file = Path("temp_translation.html")

        html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="google" content="translate">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Translation Test Page</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }
        .word-container { 
            margin: 8px 0; 
            padding: 12px; 
            background: white; 
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .word-text { 
            font-size: 18px; 
            font-weight: 500; 
            color: #333;
            user-select: text;
        }
        .status { 
            position: fixed; 
            top: 20px; 
            right: 20px; 
            background: #4CAF50; 
            color: white; 
            padding: 10px 20px; 
            border-radius: 4px; 
        }
        h1 { text-align: center; color: #2c3e50; }
        .instructions { text-align: center; color: #666; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="status" id="status">Ready for translation</div>
    <h1>需要翻译的文本 - Text to be translated</h1>
    <div class="instructions">
        Chrome will automatically detect and translate the foreign text below to English.
        Please wait for the translation to complete.
    </div>
    
    <div id="wordList">"""

        # Add each word with a unique identifier
        for i, word in enumerate(words):
            html_content += f'''
        <div class="word-container">
            <div class="word-text" id="word_{i}" data-original="{word}" data-index="{i}">{word}</div>
        </div>'''

        html_content += f"""
    </div>
    
    <script>
        // Enhanced translation detection and extraction
        let originalWords = {json.dumps(words)};
        let translationResults = {{}};
        let checkCount = 0;
        let maxChecks = 60; // Check for 60 seconds
        
        function updateStatus(message) {{
            document.getElementById('status').textContent = message;
        }}
        
        function isTranslated(original, current) {{
            if (!original || !current) return false;
            if (original === current) return false;
            
            // Check if translation contains mostly ASCII characters (likely English)
            let asciiCount = 0;
            for (let char of current) {{
                if (char.charCodeAt(0) < 128) asciiCount++;
            }}
            return asciiCount / current.length > 0.7;
        }}
        
        function extractTranslations() {{
            let translatedCount = 0;
            let results = {{}};
            
            originalWords.forEach((word, index) => {{
                let element = document.getElementById(`word_${{index}}`);
                if (element) {{
                    let currentText = element.textContent.trim();
                    if (isTranslated(word, currentText)) {{
                        results[word] = currentText;
                        translatedCount++;
                    }}
                }}
            }});
            
            return {{ results, translatedCount }};
        }}
        
        function checkTranslationProgress() {{
            checkCount++;
            let {{ results, translatedCount }} = extractTranslations();
            
            updateStatus(`Checking... ${{translatedCount}}/${{originalWords.length}} translated (Check ${{checkCount}}/${{maxChecks}})`);
            
            // Save current results
            translationResults = results;
            
            // Store in window for external access
            window.translationData = {{
                results: results,
                translatedCount: translatedCount,
                totalWords: originalWords.length,
                isComplete: translatedCount >= originalWords.length * 0.8 || checkCount >= maxChecks
            }};
            
            if (checkCount >= maxChecks) {{
                updateStatus(`Translation check complete - ${{translatedCount}}/${{originalWords.length}} words translated`);
                return;
            }}
            
            // Continue checking
            setTimeout(checkTranslationProgress, 2000);
        }}
        
        // Start checking after page loads
        setTimeout(() => {{
            updateStatus('Starting translation detection...');
            checkTranslationProgress();
        }}, 3000);
        
        // Initial setup
        window.translationData = {{
            results: {{}},
            translatedCount: 0,
            totalWords: originalWords.length,
            isComplete: false
        }};
    </script>
</body>
</html>"""

        with open(self.temp_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        logging.info(f"Created translation HTML with {len(words)} words")
        return self.temp_file

    def wait_for_translation(self, timeout=120):
        """Wait for Chrome to translate the words and extract results"""
        start_time = time.time()
        best_results = {}

        while time.time() - start_time < timeout:
            try:
                # Get translation data from JavaScript
                translation_data = self.driver.execute_script(
                    "return window.translationData;"
                )

                if translation_data:
                    results = translation_data.get("results", {})
                    translated_count = translation_data.get("translatedCount", 0)
                    total_words = translation_data.get("totalWords", 0)
                    is_complete = translation_data.get("isComplete", False)

                    # Keep track of best results so far
                    if len(results) > len(best_results):
                        best_results = results.copy()

                    elapsed = int(time.time() - start_time)
                    if self.progress_callback:
                        progress = min(90, 40 + (elapsed / timeout * 40))
                        self.progress_callback(
                            int(progress),
                            100,
                            f"Translating... {translated_count}/{total_words} words ({elapsed}s)",
                        )

                    logging.info(
                        f"Translation progress: {translated_count}/{total_words} words ({elapsed}s)"
                    )

                    # Check if we have enough translations or timeout
                    if is_complete or translated_count >= total_words * 0.8:
                        logging.info(
                            f"Translation completed with {translated_count}/{total_words} words"
                        )
                        return results

                time.sleep(2)

            except Exception as e:
                logging.warning(f"Error checking translation progress: {str(e)}")
                time.sleep(2)

        logging.warning(
            f"Translation timeout after {timeout}s, using best results: {len(best_results)} translations"
        )
        return best_results

    def method_chrome_translation(self, words: List[str]) -> bool:
        """Enhanced Chrome translation method"""
        if not self.setup_driver(headless=False):
            return False

        try:
            # Create and load HTML page
            html_file = self.create_translation_html(words)
            file_url = f"file://{html_file.absolute()}"

            logging.info(f"Loading translation page: {file_url}")
            self.driver.get(file_url)

            # Wait for page to load
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.ID, "wordList"))
            )

            # Wait a bit for Chrome to detect the language
            time.sleep(5)

            # Try to trigger translation by right-clicking and looking for translate option
            try:
                body = self.driver.find_element(By.TAG_NAME, "body")
                self.driver.execute_script("arguments[0].click();", body)
                time.sleep(2)
            except:
                pass

            # Wait for translation and extract results
            self.translations = self.wait_for_translation()

            if self.translations:
                logging.info(
                    f"Successfully extracted {len(self.translations)} translations from Chrome"
                )
                return True
            else:
                logging.warning("No translations extracted from Chrome")
                return False

        except Exception as e:
            logging.error(f"Chrome translation failed: {str(e)}")
            traceback.print_exc()
            return False
        finally:
            self.cleanup()

    def method_fallback_api_translation(self, words: List[str]) -> bool:
        """Fallback API translation method"""
        logging.info("Using fallback Google Translate API")

        try:
            batch_size = 50
            all_translations = {}

            for i in range(0, len(words), batch_size):
                batch = words[i : i + batch_size]
                logging.info(
                    f"Translating batch {i // batch_size + 1}/{(len(words) - 1) // batch_size + 1}"
                )

                batch_translations = self.fallback_translator.translate_batch(batch)
                all_translations.update(batch_translations)

                if self.progress_callback:
                    progress = 50 + (i / len(words)) * 40
                    self.progress_callback(
                        int(progress),
                        100,
                        f"Using fallback API... {i + len(batch)}/{len(words)}",
                    )

                time.sleep(1)  # Rate limiting

            self.translations = all_translations
            return True

        except Exception as e:
            logging.error(f"Fallback API translation failed: {str(e)}")
            return False

    def translate_words(self, words: List[str]) -> Dict[str, str]:
        """Main translation method with improved error handling"""
        if not words:
            return {}

        self.translations = {}

        if self.progress_callback:
            self.progress_callback(0, 100, "Starting translation process...")

        # Try Chrome translation first
        try:
            logging.info("Attempting Chrome translation...")
            if self.method_chrome_translation(words):
                valid_translations = {}
                for original, translated in self.translations.items():
                    if original != translated and translated.strip():
                        valid_translations[original] = translated

                if len(valid_translations) > 0:
                    logging.info(
                        f"Chrome translation successful: {len(valid_translations)}/{len(words)} words"
                    )
                    # Fill in missing translations with original words
                    final_translations = {word: word for word in words}
                    final_translations.update(valid_translations)
                    return final_translations
        except Exception as e:
            logging.error(f"Chrome translation failed: {str(e)}")

        # Fallback to API translation
        try:
            logging.info("Attempting fallback API translation...")
            if self.method_fallback_api_translation(words):
                if self.progress_callback:
                    self.progress_callback(
                        100, 100, "Fallback API translation completed"
                    )
                return self.translations
        except Exception as e:
            logging.error(f"Fallback API translation failed: {str(e)}")

        # Final fallback: return original words
        logging.warning("All translation methods failed, returning original words")
        return {word: word for word in words}

    def cleanup(self):
        """Clean up resources"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
        except:
            pass

        try:
            if self.temp_file and self.temp_file.exists():
                self.temp_file.unlink()
                self.temp_file = None
        except:
            pass


class JSONNormalizer:
    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback

    def process_file(self, file_path: Path) -> bool:
        """Normalize JSON file format"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()

            if content.startswith("[") and content.endswith("]"):
                content = content[1:-1].strip()

            if "\n" in content:
                lines = content.split("\n")
            else:
                lines = content.split(",")

            normalized_lines = []
            for line in lines:
                line = line.strip()
                if not line or line in ["[", "]"]:
                    continue

                if line.endswith(","):
                    line = line[:-1].strip()

                if (line.startswith('"') and line.endswith('"')) or (
                    line.startswith('"') and line.endswith('"')
                ):
                    text = line[1:-1]
                else:
                    text = line

                text = self.fix_quotes_in_text(text)
                text = text.replace('"', '\\"')
                normalized_lines.append(text)

            json_array = "[\n"
            for i, line in enumerate(normalized_lines):
                if i < len(normalized_lines) - 1:
                    json_array += f' "{line}",\n'
                else:
                    json_array += f' "{line}"\n'
            json_array += "]"

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(json_array)

            with open(file_path, "r", encoding="utf-8") as f:
                json.loads(f.read())

            return True

        except Exception as e:
            logging.error(f"Error normalizing JSON: {str(e)}")
            return False

    def fix_quotes_in_text(self, text: str) -> str:
        """Fix common quote issues in text"""
        text = text.replace('list of "are"', "list of 'are'")
        text = text.replace(
            'suitable instruction found"', "suitable instruction found'"
        )
        text = re.sub(r'(\w+) "(\w+)" (\w+)', r"\1 '\2' \3", text)
        text = re.sub(r'"([^"]+)"', r"'\1'", text)
        text = text.replace("''", "'")
        text = text.replace('""', "'")

        if text.endswith('"') and not text.endswith(',"'):
            text = text[:-1] + ',"'

        return text


class TranslationMappingManager:
    """Enhanced class to handle translation mappings with better save/load functionality"""

    def __init__(self, cache_dir: Path, project_name: str):
        self.cache_dir = cache_dir
        self.project_name = project_name
        self.translation_file = cache_dir / f"{project_name}_TranslationMap.json"
        self.backup_file = cache_dir / f"{project_name}_TranslationMap_backup.json"
        self.mappings = {}

    def save_translations(self, translations: Dict[str, str]) -> bool:
        """Save translation mappings with backup"""
        try:
            # Ensure cache directory exists
            self.cache_dir.mkdir(parents=True, exist_ok=True)

            # Create backup if file exists
            if self.translation_file.exists():
                shutil.copy2(self.translation_file, self.backup_file)
                logging.info(f"Created backup: {self.backup_file}")

            # Filter out empty or invalid translations
            valid_translations = {}
            for original, translated in translations.items():
                if (
                    original
                    and translated
                    and isinstance(original, str)
                    and isinstance(translated, str)
                ):
                    valid_translations[original] = translated

            # Save translations
            with open(self.translation_file, "w", encoding="utf-8") as f:
                json.dump(valid_translations, f, ensure_ascii=False, indent=2)

            self.mappings = valid_translations
            logging.info(
                f"Saved {len(valid_translations)} translations to {self.translation_file}"
            )

            # Verify file was written correctly
            if (
                self.translation_file.exists()
                and self.translation_file.stat().st_size > 0
            ):
                return True
            else:
                logging.error("Translation file was not created or is empty")
                return False

        except Exception as e:
            logging.error(f"Error saving translations: {str(e)}")
            traceback.print_exc()
            return False

    def load_translations(self) -> Dict[str, str]:
        """Load translation mappings"""
        try:
            if self.translation_file.exists():
                with open(self.translation_file, "r", encoding="utf-8") as f:
                    self.mappings = json.load(f)
                logging.info(
                    f"Loaded {len(self.mappings)} translations from {self.translation_file}"
                )
                return self.mappings
            else:
                logging.info("No existing translation file found")
                return {}
        except Exception as e:
            logging.error(f"Error loading translations: {str(e)}")
            # Try backup
            try:
                if self.backup_file.exists():
                    with open(self.backup_file, "r", encoding="utf-8") as f:
                        self.mappings = json.load(f)
                    logging.info(
                        f"Loaded {len(self.mappings)} translations from backup"
                    )
                    return self.mappings
            except Exception as backup_e:
                logging.error(f"Error loading backup: {str(backup_e)}")
            return {}


class TranslationApplier:
    def __init__(self, progress_callback=None):
        self.translation_mapping = {}
        self.normalizer = JSONNormalizer(progress_callback)
        self.progress_callback = progress_callback
        self.config = None

    def set_config(self, config: Config):
        """Set the configuration for accessing binary extensions"""
        self.config = config

    def load_translation_mapping_from_dict(
        self, translation_dict: Dict[str, str]
    ) -> bool:
        """Load translation mapping from a dictionary with validation"""
        try:
            # Filter and validate translations
            valid_mappings = {}
            for foreign, english in translation_dict.items():
                if (
                    foreign
                    and english
                    and isinstance(foreign, str)
                    and isinstance(english, str)
                    and foreign.strip()
                    and english.strip()
                ):
                    valid_mappings[foreign] = english

            self.translation_mapping = valid_mappings
            logging.info(
                f"Loaded {len(self.translation_mapping)} valid translation mappings"
            )

            # Log some examples
            count = 0
            for foreign, english in self.translation_mapping.items():
                if count < 10:  # Show more examples
                    logging.info(f"Mapping {count + 1}: '{foreign}' -> '{english}'")
                    count += 1
                else:
                    break

            return len(self.translation_mapping) > 0
        except Exception as e:
            logging.error(
                f"Error loading translation mapping from dictionary: {str(e)}"
            )
            return False

    def normalize_json_files(self, directory: Path):
        """Normalize JSON files in the directory"""
        json_files = list(directory.rglob("*.json"))
        total_files = len(json_files)

        if total_files == 0:
            return

        logging.info(f"Found {total_files} JSON files to normalize")

        for i, json_file in enumerate(json_files):
            try:
                self.normalizer.process_file(json_file)
                logging.debug(f"Normalized JSON file: {json_file}")

                if self.progress_callback:
                    self.progress_callback(
                        i + 1,
                        total_files,
                        f"Normalizing JSON files... {i + 1}/{total_files}",
                    )

            except Exception as e:
                logging.error(f"Error normalizing JSON file {json_file}: {str(e)}")

    def apply_translations(self, input_dir: Path, output_dir: Path):
        """Apply translations to all files in the directory with improved error handling"""
        if not self.translation_mapping:
            logging.error("Translation mapping is empty or not loaded")
            return False, "Translation mapping not loaded"

        try:
            # Sort translations by length (longest first) for better replacement
            sorted_translation_mapping = sorted(
                self.translation_mapping.items(),
                key=lambda item: len(item[0]),
                reverse=True,
            )

            logging.info(f"Applying {len(sorted_translation_mapping)} translations")

            if not output_dir.exists():
                logging.error(f"Output directory does not exist: {output_dir}")
                return False, "Output directory does not exist"

            # First check if there are any actual translations to apply
            actual_translations = {
                k: v
                for k, v in self.translation_mapping.items()
                if k != v and k.strip() and v.strip()
            }
            if not actual_translations:
                logging.warning(
                    "No actual translations found - all words map to themselves"
                )
                return (
                    True,
                    "No translations were needed - all words were already in the target language",
                )

            logging.info(
                f"Found {len(actual_translations)} actual translations to apply"
            )

            # Normalize JSON files first
            self.normalize_json_files(output_dir)

            # Get all files to process
            all_files = []
            for file_path in output_dir.rglob("*"):
                if file_path.is_file():
                    # Use the config's binary_extensions if available, otherwise use default
                    binary_extensions = (
                        self.config.binary_extensions
                        if self.config
                        else Config.get_default_binary_extensions()
                    )
                    if file_path.suffix.lower() not in binary_extensions:
                        all_files.append(file_path)

            total_files = len(all_files)
            processed_files = 0
            files_with_translations = 0
            total_replacements = 0

            logging.info(f"Found {total_files} files to process in output directory")

            for file_path in all_files:
                try:
                    # Try multiple encodings
                    encodings = ["utf-8", "utf-16", "latin1", "cp1252", "ascii"]
                    content = None
                    encoding_used = None

                    for encoding in encodings:
                        try:
                            with open(file_path, "r", encoding=encoding) as f:
                                content = f.read()
                            encoding_used = encoding
                            break
                        except UnicodeDecodeError:
                            continue

                    if content is None:
                        logging.warning(f"Could not decode file: {file_path}")
                        processed_files += 1
                        continue

                    file_modified = False
                    original_content = content
                    replacements_in_file = 0

                    # Apply translations - only process actual translations
                    for foreign_word, translation in sorted_translation_mapping:
                        if (
                            foreign_word != translation
                            and foreign_word.strip()
                            and translation.strip()
                            and foreign_word in content
                        ):
                            # Count occurrences before replacement
                            occurrences = content.count(foreign_word)
                            if occurrences > 0:
                                content = content.replace(foreign_word, translation)
                                file_modified = True
                                replacements_in_file += occurrences
                                total_replacements += occurrences
                                logging.debug(
                                    f"Replaced '{foreign_word}' -> '{translation}' "
                                    f"({occurrences} times) in {file_path.name}"
                                )

                    # Save file if modified
                    if file_modified:
                        with open(file_path, "w", encoding=encoding_used) as f:
                            f.write(content)
                        files_with_translations += 1
                        logging.info(
                            f"Updated file with {replacements_in_file} replacements: {file_path.name}"
                        )

                    processed_files += 1

                    if self.progress_callback:
                        progress = (processed_files / total_files) * 100
                        self.progress_callback(
                            processed_files,
                            total_files,
                            f"Applying translations... {processed_files}/{total_files} "
                            f"({total_replacements} replacements so far)",
                        )

                except Exception as e:
                    logging.error(f"Error processing file {file_path}: {str(e)}")
                    processed_files += 1

            if total_replacements == 0:
                success_message = (
                    f"Processed {processed_files} files but found no foreign words to replace. "
                    f"This could mean: 1) The words were already translated, "
                    f"2) The translation service returned the same words, or "
                    f"3) The foreign words don't exist in the code files."
                )
                logging.warning(success_message)
                return True, success_message
            else:
                success_message = (
                    f"Successfully processed {processed_files} files. "
                    f"{files_with_translations} files were updated with {total_replacements} total replacements."
                )
                logging.info(success_message)
                return True, success_message

        except Exception as e:
            logging.error(f"Error applying translations: {str(e)}")
            traceback.print_exc()
            return False, str(e)


class ProjectTranslatorGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Enhanced Project Translator")
        self.root.geometry("950x750")

        self.project_dir = StringVar()
        self.output_dir = StringVar()
        self.scan_type = StringVar(value="all")
        self.file_extension = StringVar(value=".py")

        self.config = None
        self.cache = None
        self.scanner = None
        self.translator = None
        self.applier = None
        self.mapping_manager = None

        self.create_widgets()

    def create_widgets(self):
        # Project Selection Frame
        project_frame = ttk.LabelFrame(self.root, text="Project Selection", padding=10)
        project_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(project_frame, text="Project Directory:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        ttk.Entry(project_frame, textvariable=self.project_dir, width=50).grid(
            row=0, column=1, padx=5, pady=5
        )
        ttk.Button(project_frame, text="Browse", command=self.browse_project).grid(
            row=0, column=2, padx=5, pady=5
        )

        ttk.Label(project_frame, text="Output Directory:").grid(
            row=1, column=0, sticky=tk.W, pady=5
        )
        ttk.Entry(project_frame, textvariable=self.output_dir, width=50).grid(
            row=1, column=1, padx=5, pady=5
        )
        ttk.Button(project_frame, text="Browse", command=self.browse_output).grid(
            row=1, column=2, padx=5, pady=5
        )

        # Options Frame
        options_frame = ttk.LabelFrame(self.root, text="Scanning Options", padding=10)
        options_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(options_frame, text="Scan Type:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        ttk.Radiobutton(
            options_frame, text="All Files", value="all", variable=self.scan_type
        ).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Radiobutton(
            options_frame, text="Code Files", value="code", variable=self.scan_type
        ).grid(row=0, column=2, sticky=tk.W, padx=5)
        ttk.Radiobutton(
            options_frame, text="Documents", value="documents", variable=self.scan_type
        ).grid(row=0, column=3, sticky=tk.W, padx=5)
        ttk.Radiobutton(
            options_frame,
            text="Specific Type",
            value="specific",
            variable=self.scan_type,
        ).grid(row=0, column=4, sticky=tk.W, padx=5)

        self.extension_frame = ttk.Frame(options_frame)
        self.extension_frame.grid(row=1, column=0, columnspan=5, sticky=tk.W, pady=5)
        self.extension_label = ttk.Label(self.extension_frame, text="File Extension:")
        self.extension_entry = ttk.Entry(
            self.extension_frame, textvariable=self.file_extension, width=10
        )

        # Progress Frame
        self.progress_frame = ttk.LabelFrame(self.root, text="Progress", padding=10)
        self.progress_frame.pack(fill=tk.X, padx=10, pady=5)

        self.progress_bar = ttk.Progressbar(self.progress_frame, mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=5)

        self.status_label = ttk.Label(
            self.progress_frame, text="Ready to start", font=("Arial", 10, "bold")
        )
        self.status_label.pack(anchor=tk.W, pady=5)

        # Control Buttons Frame
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        self.translate_button = ttk.Button(
            control_frame,
            text="Start Translation Process",
            command=self.start_translation,
        )
        self.translate_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(
            control_frame, text="Stop", command=self.stop_translation, state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # Log Frame
        log_frame = ttk.LabelFrame(self.root, text="Process Log", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, height=18, width=90
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Bind events
        self.scan_type.trace("w", self.update_extension_input)

        # Initialize state
        self.translation_active = False

    def browse_project(self):
        directory = filedialog.askdirectory(title="Select Project Directory")
        if directory:
            self.project_dir.set(directory)
            project_name = os.path.basename(directory)
            default_output = os.path.join(
                os.path.dirname(directory), f"{project_name}_translated"
            )
            self.output_dir.set(default_output)
            self.log_message(f"Project selected: {directory}")
            self.log_message(f"Default output directory set: {default_output}")

    def browse_output(self):
        directory = filedialog.askdirectory(title="Select Output Directory")
        if directory:
            self.output_dir.set(directory)
            self.log_message(f"Output directory selected: {directory}")

    def update_extension_input(self, *args):
        if self.scan_type.get() == "specific":
            self.extension_label.pack(side=tk.LEFT, padx=5)
            self.extension_entry.pack(side=tk.LEFT, padx=5)
        else:
            self.extension_label.pack_forget()
            self.extension_entry.pack_forget()

    def log_message(self, message):
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, formatted_message)
        self.log_text.see(tk.END)
        self.root.update()
        logger.info(message)

    def update_progress(self, current, total, message=""):
        if not self.translation_active:
            return

        try:
            current = int(current)
            total = int(total)
        except (ValueError, TypeError):
            current = 0
            total = 100

        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar["value"] = percentage
            status_text = f"Progress: {current}/{total} ({percentage}%)"
            if message:
                status_text += f" - {message}"
            self.status_label.config(text=status_text)
        else:
            self.progress_bar["value"] = 0
            if message:
                self.status_label.config(text=message)
            else:
                self.status_label.config(text="Processing...")
        self.root.update()

    def validate_project(self, project_path: Path) -> bool:
        """Enhanced project validation"""
        try:
            if not project_path.exists():
                raise FileNotFoundError(
                    f"Project directory does not exist: {project_path}"
                )

            if not project_path.is_dir():
                raise NotADirectoryError(f"Path is not a directory: {project_path}")

            # Check if directory has any files
            has_files = any(project_path.rglob("*"))
            if not has_files:
                self.log_message("Warning: Project directory appears to be empty")

                # Check for git repository
                git_dir = project_path / ".git"
                if git_dir.exists():
                    result = messagebox.askyesno(
                        "Empty Repository",
                        "The project directory is empty but appears to be a git repository.\n\n"
                        "This might be normal for a new repository. Continue anyway?",
                    )
                    if not result:
                        return False
                else:
                    result = messagebox.askyesno(
                        "Empty Directory",
                        "The project directory is empty.\n\nContinue anyway?",
                    )
                    if not result:
                        return False

            return True

        except Exception as e:
            self.log_message(f"Error validating project: {str(e)}")
            messagebox.showerror(
                "Validation Error", f"Error validating project:\n{str(e)}"
            )
            return False

    def stop_translation(self):
        """Stop the translation process"""
        self.translation_active = False
        self.log_message("Translation process stopped by user")
        self.translate_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_label.config(text="Process stopped")

    def start_translation(self):
        if not self.project_dir.get() or not self.output_dir.get():
            messagebox.showerror(
                "Error", "Please select both project and output directories"
            )
            return

        self.translate_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.translation_active = True
        self.progress_bar["value"] = 0
        self.status_label.config(text="Starting translation process...")
        self.log_text.delete(1.0, tk.END)

        # Start translation in a separate thread
        threading.Thread(target=self.translate_project, daemon=True).start()

    def translate_project(self):
        """Main translation process with enhanced error handling"""
        try:
            if not self.translation_active:
                return

            project_path = Path(self.project_dir.get())
            output_path = Path(self.output_dir.get())

            # Step 0: Validate project
            self.log_message("Step 0: Validating project...")
            if not self.validate_project(project_path):
                return

            # Initialize configuration
            cache_dir = output_path / "translation_cache"
            project_name = project_path.name

            self.config = Config(
                input_dir=project_path,
                cache_dir=cache_dir,
                output_dir=output_path,
            )

            # Set up extensions to scan
            scan_type = self.scan_type.get()
            if scan_type == "specific":
                extension = self.file_extension.get()
                if not extension.startswith("."):
                    extension = "." + extension
                self.config.extensions_to_scan = {extension}
            else:
                self.config.extensions_to_scan = self.config.get_extensions_by_type(
                    scan_type
                )

            self.log_message(
                f"Scanning for extensions: {', '.join(sorted(self.config.extensions_to_scan))}"
            )

            if not self.translation_active:
                return

            # Step 1: Copy project
            self.update_progress(5, 100, "Step 1: Copying project...")
            self.log_message("Step 1: Copying project to output directory...")

            if output_path.exists():
                if output_path.is_file():
                    output_path.unlink()
                elif output_path != project_path:  # Don't delete if same directory
                    shutil.rmtree(output_path)

            if output_path != project_path:
                shutil.copytree(project_path, output_path)
                self.log_message(f"Project copied to: {output_path}")
            else:
                self.log_message("Working in-place (same input/output directory)")

            cache_dir.mkdir(parents=True, exist_ok=True)

            if not self.translation_active:
                return

            # Step 2: Initialize translation mapping manager
            self.mapping_manager = TranslationMappingManager(cache_dir, project_name)

            # Step 3: Scan for foreign words
            self.update_progress(10, 100, "Step 2: Initializing word cache...")
            self.log_message("Step 2: Scanning for foreign words...")

            self.cache = ForeignWordCache(
                cache_dir, f"{project_name}_ForeignWordMap.json"
            )
            asyncio.run(self.cache.initialize())

            self.scanner = ForeignWordScanner(
                self.config, self.cache, self.update_progress
            )

            if not self.translation_active:
                return

            scan_results = asyncio.run(self.scanner.scan_project(self.update_progress))

            self.log_message(
                f"Scan completed: {scan_results['new_words_found']} new foreign words found"
            )
            self.log_message(f"Total foreign words in cache: {len(self.cache.cache)}")

            if not self.translation_active:
                return

            # Step 4: Translate words
            foreign_words = list(self.cache.cache)

            if not foreign_words:
                self.log_message("No foreign words found - translation complete!")
                self.update_progress(100, 100, "No translation needed")
                messagebox.showinfo(
                    "Complete", "No foreign words were found in the project"
                )
                return

            self.update_progress(30, 100, "Step 3: Starting translation...")
            self.log_message(
                f"Step 3: Translating {len(foreign_words)} foreign words..."
            )

            # Show some examples of words to be translated
            self.log_message("Sample words to translate:")
            for i, word in enumerate(foreign_words[:10]):
                self.log_message(f"  {i + 1}. '{word}'")
            if len(foreign_words) > 10:
                self.log_message(f"  ... and {len(foreign_words) - 10} more words")

            self.translator = ChromeTranslator(self.update_progress)
            translations = self.translator.translate_words(foreign_words)

            if not self.translation_active:
                return

            # Analyze translation results
            successful_translations = {
                word: translation
                for word, translation in translations.items()
                if word != translation and translation.strip()
            }

            self.log_message(
                f"Translation completed: {len(successful_translations)}/{len(translations)} words were successfully translated"
            )

            # Show some translation examples
            if successful_translations:
                self.log_message("Sample successful translations:")
                count = 0
                for original, translated in successful_translations.items():
                    if count < 10:
                        self.log_message(f"  '{original}' -> '{translated}'")
                        count += 1
                    else:
                        break
            else:
                self.log_message("WARNING: No successful translations found!")
                self.log_message("This could mean:")
                self.log_message("1. All words were already in English")
                self.log_message("2. Translation service couldn't translate the words")
                self.log_message("3. Translation service returned the same words")

                # Show some examples of what was "translated"
                self.log_message("\nSample translation attempts:")
                count = 0
                for original, translated in list(translations.items())[:10]:
                    self.log_message(
                        f"  '{original}' -> '{translated}' {'(SAME)' if original == translated else '(DIFFERENT)'}"
                    )
                    count += 1

            # Step 5: Save translation mappings
            self.update_progress(70, 100, "Step 4: Saving translation mappings...")
            self.log_message("Step 4: Saving translation mappings...")

            if self.mapping_manager.save_translations(translations):
                self.log_message("Translation mappings saved successfully")
            else:
                self.log_message("Warning: Failed to save translation mappings")

            if not self.translation_active:
                return

            # Step 6: Apply translations to files
            self.update_progress(80, 100, "Step 5: Applying translations to files...")
            self.log_message("Step 5: Applying translations to project files...")

            self.applier = TranslationApplier(self.update_progress)
            self.applier.set_config(self.config)

            if not self.applier.load_translation_mapping_from_dict(translations):
                raise Exception("Failed to load translation mapping")

            success, message = self.applier.apply_translations(
                project_path, output_path
            )

            if not self.translation_active:
                return

            # Step 7: Complete
            if success:
                self.update_progress(100, 100, "Translation completed successfully!")
                self.log_message("Translation process completed successfully!")
                self.log_message(message)

                summary_message = (
                    f"Translation Summary:\n"
                    f"• Total words processed: {len(foreign_words)}\n"
                    f"• Successfully translated: {len(successful_translations)}\n"
                    f"• {message}"
                )

                messagebox.showinfo("Success", summary_message)
            else:
                self.update_progress(0, 100, f"Translation failed: {message}")
                messagebox.showerror("Error", f"Translation failed: {message}")

        except Exception as e:
            if self.translation_active:
                self.update_progress(0, 100, f"Error: {str(e)}")
                logger.error(f"Translation failed: {str(e)}")
                logger.error(traceback.format_exc())
                messagebox.showerror("Error", f"Translation failed: {str(e)}")
                self.log_message(f"Error: {str(e)}")
                self.log_message("Full error details logged to translation_app.log")

        finally:
            self.translation_active = False
            self.translate_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ProjectTranslatorGUI()
    app.run()
