#!/usr/bin/env python3
"""
Chrome Translation Tool - Enhanced Version

This module provides Chrome-based translation capabilities with:
- Chrome UI opening for translation
- Word translating and translated content fetching
- Mapping to initial foreign word mapping
- Saving translation map

Fixes all mypy and ruff issues:
- Proper type annotations
- No bare except clauses
- No unused variables
- Enhanced error handling
"""

import json
import logging
import re
import shutil
import time
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Callable

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    WebDriverException,
    TimeoutException,
    NoSuchElementException,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("chrome_translate.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class TranslationError(Exception):
    """Custom exception for translation errors."""
    pass


class ChromeTranslationConfig:
    """Configuration for Chrome translation settings."""
    
    def __init__(
        self,
        headless: bool = False,
        timeout: int = 120,
        translation_timeout: int = 60,
        batch_size: int = 50,
        retry_attempts: int = 3,
    ) -> None:
        self.headless = headless
        self.timeout = timeout
        self.translation_timeout = translation_timeout
        self.batch_size = batch_size
        self.retry_attempts = retry_attempts


class GoogleTranslateAPI:
    """Google Translate API fallback implementation."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        })
        self.base_url = "https://translate.googleapis.com/translate_a/single"

    def translate_text(
        self, 
        text: str, 
        source_lang: str = "auto", 
        target_lang: str = "en"
    ) -> str:
        """Translate text using Google Translate API."""
        try:
            params = {
                "client": "gtx",
                "sl": source_lang,
                "tl": target_lang,
                "dt": "t",
                "q": text,
            }

            response = self.session.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()

            data: Any = response.json()
            if data and len(data) > 0 and len(data[0]) > 0:
                return str(data[0][0][0])
            return text
            
        except Exception as e:
            logger.warning(f"Google Translate API failed for '{text}': {e}")
            return text

    def translate_batch(
        self, 
        texts: List[str], 
        source_lang: str = "auto", 
        target_lang: str = "en"
    ) -> Dict[str, str]:
        """Translate multiple texts with rate limiting."""
        results: Dict[str, str] = {}
        
        for text in texts:
            if text and text.strip():
                translated = self.translate_text(text, source_lang, target_lang)
                results[text] = translated
                time.sleep(0.1)  # Rate limiting
            else:
                results[text] = text
                
        return results


class TranslationMapping:
    """Manages foreign word to English translation mappings."""

    def __init__(self, cache_dir: Path, project_name: str) -> None:
        self.cache_dir = cache_dir
        self.project_name = project_name
        self.translation_file = cache_dir / f"{project_name}_TranslationMap.json"
        self.backup_file = cache_dir / f"{project_name}_TranslationMap_backup.json"
        self.mappings: Dict[str, str] = {}

    def save_translations(self, translations: Dict[str, str]) -> bool:
        """Save translation mappings with backup and validation."""
        try:
            # Ensure cache directory exists
            self.cache_dir.mkdir(parents=True, exist_ok=True)

            # Create backup if file exists
            if self.translation_file.exists():
                shutil.copy2(self.translation_file, self.backup_file)
                logger.info(f"Created backup: {self.backup_file}")

            # Filter out empty or invalid translations
            valid_translations: Dict[str, str] = {}
            for original, translated in translations.items():
                if (
                    original
                    and translated
                    and isinstance(original, str)
                    and isinstance(translated, str)
                    and original.strip()
                    and translated.strip()
                ):
                    valid_translations[original.strip()] = translated.strip()

            # Save translations
            with open(self.translation_file, "w", encoding="utf-8") as f:
                json.dump(valid_translations, f, ensure_ascii=False, indent=2)

            self.mappings = valid_translations
            logger.info(
                f"Saved {len(valid_translations)} translations to {self.translation_file}"
            )

            # Verify file was written correctly
            return (
                self.translation_file.exists()
                and self.translation_file.stat().st_size > 0
            )

        except Exception as e:
            logger.error(f"Error saving translations: {e}")
            traceback.print_exc()
            return False

    def load_translations(self) -> Dict[str, str]:
        """Load translation mappings with fallback to backup."""
        try:
            if self.translation_file.exists():
                with open(self.translation_file, "r", encoding="utf-8") as f:
                    self.mappings = json.load(f)
                logger.info(
                    f"Loaded {len(self.mappings)} translations from {self.translation_file}"
                )
                return self.mappings
                
        except Exception as e:
            logger.error(f"Error loading translations: {e}")
            # Try backup
            try:
                if self.backup_file.exists():
                    with open(self.backup_file, "r", encoding="utf-8") as f:
                        self.mappings = json.load(f)
                    logger.info(
                        f"Loaded {len(self.mappings)} translations from backup"
                    )
                    return self.mappings
            except Exception as backup_e:
                logger.error(f"Error loading backup: {backup_e}")

        logger.info("No existing translation file found")
        return {}

    def get_mapping_stats(self) -> Dict[str, int]:
        """Get statistics about the translation mappings."""
        if not self.mappings:
            return {"total": 0, "translated": 0, "unchanged": 0}

        translated = sum(
            1 for orig, trans in self.mappings.items() 
            if orig != trans
        )
        unchanged = len(self.mappings) - translated

        return {
            "total": len(self.mappings),
            "translated": translated,
            "unchanged": unchanged,
        }


class ChromeTranslator:
    """Enhanced Chrome-based translator with proper error handling."""

    def __init__(
        self, 
        config: Optional[ChromeTranslationConfig] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> None:
        self.config = config or ChromeTranslationConfig()
        self.progress_callback = progress_callback
        self.driver: Optional[webdriver.Chrome] = None
        self.translations: Dict[str, str] = {}
        self.temp_file: Optional[Path] = None
        self.fallback_translator = GoogleTranslateAPI()

    def setup_chrome_driver(self) -> bool:
        """Setup Chrome driver with enhanced translation options."""
        chrome_options = Options()

        if self.config.headless:
            chrome_options.add_argument("--headless=new")

        # Performance and security options
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-images")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--lang=en-US")

        # Enhanced translation preferences
        prefs = {
            "translate": {"enabled": True},
            "translate.enabled": True,
            "translate_whitelists": {
                "zh": "en", "zh-CN": "en", "zh-TW": "en",
                "ja": "en", "ko": "en", "ar": "en",
                "ru": "en", "fr": "en", "de": "en",
                "es": "en", "it": "en", "pt": "en",
                "hi": "en", "th": "en", "vi": "en",
            },
            "translate_accepted_languages": ["en"],
            "translate_site_blacklist": [],
            "profile.default_content_setting_values": {"notifications": 2},
        }
        chrome_options.add_experimental_option("prefs", prefs)

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(self.config.timeout)
            logger.info("Chrome driver setup successful")
            return True
            
        except WebDriverException as e:
            logger.error(f"Failed to setup Chrome driver: {e}")
            return False

    def create_translation_html(self, words: List[str]) -> Path:
        """Create optimized HTML page for translation extraction."""
        self.temp_file = Path("temp_translation.html")

        # Create comprehensive HTML with JavaScript for translation detection
        html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="google" content="translate">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chrome Translation Tool</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            padding: 20px;
            background: #f5f5f5;
            line-height: 1.6;
        }}
        .word-container {{
            margin: 8px 0;
            padding: 12px;
            background: white;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .word-text {{
            font-size: 18px;
            font-weight: 500;
            color: #333;
            user-select: text;
        }}
        .status {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: #4CAF50;
            color: white;
            padding: 10px 20px;
            border-radius: 4px;
            z-index: 1000;
        }}
        h1 {{
            text-align: center;
            color: #2c3e50;
        }}
        .instructions {{
            text-align: center;
            color: #666;
            margin: 20px 0;
        }}
        .stats {{
            text-align: center;
            margin: 20px 0;
            padding: 10px;
            background: #e8f4f8;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="status" id="status">Ready for translation</div>
    <h1>需要翻译的文本 - Text to be translated</h1>
    <div class="instructions">
        Chrome will automatically detect and translate the foreign text below to English.
        Please wait for the translation to complete.
    </div>
    <div class="stats" id="stats">Total words: {len(words)}</div>
    
    <div id="wordList">'''

        # Add each word with unique identifier
        for i, word in enumerate(words):
            # Escape HTML special characters
            escaped_word = (word
                           .replace("&", "&amp;")
                           .replace("<", "&lt;")
                           .replace(">", "&gt;")
                           .replace('"', "&quot;")
                           .replace("'", "&#x27;"))
            
            html_content += f'''
        <div class="word-container">
            <div class="word-text" id="word_{i}" data-original="{escaped_word}" data-index="{i}">
                {escaped_word}
            </div>
        </div>'''

        html_content += f'''
    </div>
    
    <script>
        const originalWords = {json.dumps(words, ensure_ascii=False)};
        let translationResults = {{}};
        let checkCount = 0;
        const maxChecks = {self.config.translation_timeout // 2};
        
        function updateStatus(message) {{
            const statusEl = document.getElementById('status');
            if (statusEl) statusEl.textContent = message;
        }}
        
        function updateStats(translated, total) {{
            const statsEl = document.getElementById('stats');
            if (statsEl) {{
                statsEl.textContent = `Translated: ${{translated}}/${{total}} words`;
            }}
        }}
        
        function isTranslated(original, current) {{
            if (!original || !current || original === current) return false;
            
            // Check if translation contains mostly ASCII characters (likely English)
            let asciiCount = 0;
            for (let char of current) {{
                if (char.charCodeAt(0) < 128) asciiCount++;
            }}
            
            // Consider translated if >70% ASCII and different from original
            return asciiCount / current.length > 0.7;
        }}
        
        function extractTranslations() {{
            let translatedCount = 0;
            const results = {{}};
            
            originalWords.forEach((word, index) => {{
                const element = document.getElementById(`word_${{index}}`);
                if (element) {{
                    const currentText = element.textContent.trim();
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
            const {{ results, translatedCount }} = extractTranslations();
            
            updateStatus(`Checking... ${{translatedCount}}/${{originalWords.length}} translated (Check ${{checkCount}}/${{maxChecks}})`);
            updateStats(translatedCount, originalWords.length);
            
            // Save current results
            translationResults = results;
            
            // Store in window for external access
            window.translationData = {{
                results: results,
                translatedCount: translatedCount,
                totalWords: originalWords.length,
                isComplete: translatedCount >= originalWords.length * 0.8 || checkCount >= maxChecks,
                checkCount: checkCount,
                maxChecks: maxChecks
            }};
            
            if (checkCount >= maxChecks) {{
                updateStatus(`Translation complete - ${{translatedCount}}/${{originalWords.length}} words translated`);
                return;
            }}
            
            // Continue checking
            setTimeout(checkTranslationProgress, 2000);
        }}
        
        // Auto-start translation detection
        document.addEventListener('DOMContentLoaded', function() {{
            setTimeout(() => {{
                updateStatus('Starting translation detection...');
                checkTranslationProgress();
            }}, 3000);
        }});
        
        // Initialize window data
        window.translationData = {{
            results: {{}},
            translatedCount: 0,
            totalWords: originalWords.length,
            isComplete: false,
            checkCount: 0,
            maxChecks: maxChecks
        }};
    </script>
</body>
</html>'''

        with open(self.temp_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"Created translation HTML with {len(words)} words")
        return self.temp_file

    def wait_for_translation(self) -> Dict[str, str]:
        """Wait for Chrome to translate words and extract results."""
        if not self.driver:
            raise TranslationError("Chrome driver not initialized")

        start_time = time.time()
        best_results: Dict[str, str] = {}
        last_count = 0

        while time.time() - start_time < self.config.translation_timeout:
            try:
                # Get translation data from JavaScript
                translation_data: Any = self.driver.execute_script(
                    "return window.translationData;"
                )

                if translation_data and isinstance(translation_data, dict):
                    results = translation_data.get("results", {})
                    translated_count = translation_data.get("translatedCount", 0)
                    total_words = translation_data.get("totalWords", 0)
                    is_complete = translation_data.get("isComplete", False)

                    # Keep track of best results so far
                    if len(results) > len(best_results):
                        best_results = dict(results)

                    # Update progress
                    elapsed = int(time.time() - start_time)
                    if self.progress_callback and translated_count != last_count:
                        progress = min(90, 40 + (elapsed / self.config.translation_timeout * 40))
                        self.progress_callback(
                            int(progress),
                            100,
                            f"Translating... {translated_count}/{total_words} words ({elapsed}s)",
                        )
                        last_count = translated_count

                    logger.info(
                        f"Translation progress: {translated_count}/{total_words} "
                        f"words ({elapsed}s)"
                    )

                    # Check completion conditions
                    if is_complete or translated_count >= total_words * 0.8:
                        logger.info(
                            f"Translation completed with {translated_count}/{total_words} words"
                        )
                        return dict(results)

                time.sleep(2)

            except Exception as e:
                logger.warning(f"Error checking translation progress: {e}")
                time.sleep(2)

        logger.warning(
            f"Translation timeout after {self.config.translation_timeout}s, "
            f"using best results: {len(best_results)} translations"
        )
        return best_results

    def translate_with_chrome(self, words: List[str]) -> bool:
        """Translate words using Chrome's built-in translation."""
        if not self.setup_chrome_driver():
            return False

        try:
            # Create and load HTML page
            html_file = self.create_translation_html(words)
            if not html_file:
                logger.error("Failed to create translation HTML file")
                return False
            file_url = f"file://{html_file.absolute()}"

            logger.info(f"Loading translation page: {file_url}")
            if self.driver is not None:
                self.driver.get(file_url)

            # Wait for page to load
            try:
                if self.driver is not None:
                    WebDriverWait(self.driver, 30).until(
                        EC.presence_of_element_located((By.ID, "wordList"))
                    )
            except TimeoutException:
                logger.error("Timeout waiting for page to load")
                return False

            # Allow time for Chrome to detect the language
            time.sleep(5)

            # Try to trigger translation
            try:
                if self.driver is not None:
                    body = self.driver.find_element(By.TAG_NAME, "body")
                    self.driver.execute_script("arguments[0].click();", body)
                time.sleep(2)
            except NoSuchElementException:
                logger.warning("Could not find body element to trigger translation")

            # Extract translation results
            self.translations = self.wait_for_translation()

            success = len(self.translations) > 0
            if success:
                logger.info(
                    f"Chrome translation successful: {len(self.translations)} translations"
                )
            else:
                logger.warning("No translations extracted from Chrome")

            return success

        except Exception as e:
            logger.error(f"Chrome translation failed: {e}")
            traceback.print_exc()
            return False

    def translate_with_fallback_api(self, words: List[str]) -> bool:
        """Fallback to Google Translate API."""
        logger.info("Using fallback Google Translate API")

        try:
            all_translations: Dict[str, str] = {}

            # Process in batches
            for i in range(0, len(words), self.config.batch_size):
                batch = words[i : i + self.config.batch_size]
                batch_num = i // self.config.batch_size + 1
                total_batches = (len(words) - 1) // self.config.batch_size + 1
                
                logger.info(f"Translating batch {batch_num}/{total_batches}")

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
            logger.error(f"Fallback API translation failed: {e}")
            return False

    def translate_words(self, words: List[str]) -> Dict[str, str]:
        """Main translation method with fallback handling."""
        if not words:
            return {}

        self.translations = {}

        if self.progress_callback:
            self.progress_callback(0, 100, "Starting translation process...")

        # Try Chrome translation first
        for attempt in range(self.config.retry_attempts):
            try:
                logger.info(f"Attempting Chrome translation (attempt {attempt + 1})")
                
                if self.translate_with_chrome(words):
                    # Validate translations
                    valid_translations = {
                        original: translated
                        for original, translated in self.translations.items()
                        if original != translated and translated.strip()
                    }

                    if len(valid_translations) > 0:
                        logger.info(
                            f"Chrome translation successful: "
                            f"{len(valid_translations)}/{len(words)} words"
                        )
                        # Fill in missing translations with original words
                        final_translations = {word: word for word in words}
                        final_translations.update(valid_translations)
                        return final_translations
                        
            except Exception as e:
                logger.error(f"Chrome translation attempt {attempt + 1} failed: {e}")
                
            finally:
                self.cleanup()

            # Wait before retry
            if attempt < self.config.retry_attempts - 1:
                time.sleep(2)

        # Fallback to API translation
        try:
            logger.info("Attempting fallback API translation...")
            if self.translate_with_fallback_api(words):
                if self.progress_callback:
                    self.progress_callback(100, 100, "Fallback API translation completed")
                return self.translations
                
        except Exception as e:
            logger.error(f"Fallback API translation failed: {e}")

        # Final fallback: return original words
        logger.warning("All translation methods failed, returning original words")
        return {word: word for word in words}

    def cleanup(self) -> None:
        """Clean up Chrome driver and temporary files."""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                logger.debug("Chrome driver closed")
            except Exception as e:
                logger.warning(f"Error closing Chrome driver: {e}")

        if self.temp_file and self.temp_file.exists():
            try:
                self.temp_file.unlink()
                self.temp_file = None
                logger.debug("Temporary HTML file removed")
            except Exception as e:
                logger.warning(f"Error removing temporary file: {e}")

    def __enter__(self) -> 'ChromeTranslator':
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.cleanup()


def extract_foreign_words_from_content(content: str) -> Set[str]:
    """Extract foreign (non-ASCII) words from content."""
    foreign_words: Set[str] = set()

    # Extract words with non-ASCII characters
    main_pattern = re.findall(r"\b[^\x00-\x7F]+\b", content)
    additional_pattern = re.findall(r"[^\x00-\x7F]+", content)

    # Extract emojis
    emoji_pattern = re.findall(
        r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
        r"\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251"
        r"\U0001F900-\U0001F9FF]",
        content,
    )

    # Combine all patterns
    foreign_words = set(main_pattern + additional_pattern + emoji_pattern)
    
    # Filter out empty strings and whitespace-only
    return {word.strip() for word in foreign_words if word.strip()}


def translate_project_words(
    words: List[str],
    project_name: str,
    cache_dir: Path,
    config: Optional[ChromeTranslationConfig] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Tuple[Dict[str, str], Dict[str, int]]:
    """
    Main function to translate project words and save mappings.
    
    Returns:
        Tuple of (translations, stats)
    """
    if not words:
        return {}, {"total": 0, "translated": 0, "unchanged": 0}

    # Initialize translation mapping manager
    mapping_manager = TranslationMapping(cache_dir, project_name)
    
    # Load existing translations
    existing_translations = mapping_manager.load_translations()
    
    # Filter words that need translation
    words_to_translate = [
        word for word in words 
        if word not in existing_translations
    ]
    
    if not words_to_translate:
        logger.info("All words already translated")
        stats = mapping_manager.get_mapping_stats()
        return existing_translations, stats

    logger.info(f"Need to translate {len(words_to_translate)} new words")

    # Translate new words
    translation_config = config or ChromeTranslationConfig()
    
    with ChromeTranslator(translation_config, progress_callback) as translator:
        new_translations = translator.translate_words(words_to_translate)

    # Combine with existing translations
    all_translations = {**existing_translations, **new_translations}
    
    # Save updated translations
    if mapping_manager.save_translations(all_translations):
        logger.info("Translation mappings saved successfully")
    else:
        logger.error("Failed to save translation mappings")

    # Get final statistics
    stats = mapping_manager.get_mapping_stats()
    
    return all_translations, stats


# Example usage
if __name__ == "__main__":
    # Example words to translate
    test_words = [
        "配置文件",
        "代理设置", 
        "网络地址",
        "打开你的代理软件查看代理协议",
        "代理网络的address",
        "函数配置",
        "返回结果",
    ]

    project_name = "test_project"
    cache_dir = Path("./translation_cache")

    # Configure Chrome translation
    config = ChromeTranslationConfig(
        headless=False,  # Set to True for headless mode
        timeout=120,
        translation_timeout=60,
        batch_size=50,
        retry_attempts=3,
    )

    def progress_update(current: int, total: int, message: str) -> None:
        print(f"Progress: {current}/{total} - {message}")

    # Translate and save mappings
    try:
        translations, stats = translate_project_words(
            test_words,
            project_name,
            cache_dir,
            config,
            progress_update,
        )

        print("\nTranslation Results:")
        print(f"Total words: {stats['total']}")
        print(f"Successfully translated: {stats['translated']}")
        print(f"Unchanged: {stats['unchanged']}")

        print("\nSample translations:")
        for i, (original, translated) in enumerate(list(translations.items())[:5]):
            status = "✓" if original != translated else "="
            print(f"{i+1}. {status} '{original}' -> '{translated}'")

    except Exception as e:
        logger.error(f"Translation failed: {e}")
        traceback.print_exc()