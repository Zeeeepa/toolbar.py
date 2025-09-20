# chrome_translate.py
"""
Chrome-based translation system with proper Chinese detection
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import WebDriverException, StaleElementReferenceException, TimeoutException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Warning: selenium not installed. Install with: pip install selenium")

# Configuration
CACHE_FOLDER = "./docs"
TARGET_LANG = "English"


class TranslationCache:
    """Manages translation cache."""
    
    def __init__(self, language: str):
        self.language = language.lower()
        self.cache_dir = Path(CACHE_FOLDER)
        self.cache_file = self.cache_dir / f"translate_{self.language}.json"
        self.cache: Dict[str, str] = {}
        self._ensure_cache_dir()
        self._load_cache()
    
    def _ensure_cache_dir(self):
        """Ensure cache directory exists."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_cache(self):
        """Load existing translation cache."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                # Filter valid translations only
                self.cache = {k: v for k, v in self.cache.items() 
                             if v is not None and k.strip() and v.strip()}
                logger.info(f"Loaded {len(self.cache)} cached translations")
            except Exception as e:
                logger.error(f"Error loading cache: {e}")
                self.cache = {}
        else:
            logger.info("No existing cache found, starting fresh")
            self.cache = {}
    
    def save_cache(self):
        """Save translation cache to file."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=4, ensure_ascii=False)
            logger.info(f"Saved {len(self.cache)} translations to cache")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
    
    def get_cached_translation(self, text: str) -> Optional[str]:
        """Get cached translation if available."""
        return self.cache.get(text.strip())
    
    def add_translations(self, translations: Dict[str, str]):
        """Add new translations to cache."""
        valid_translations = {k: v for k, v in translations.items() 
                              if k and v and k.strip() and v.strip() and k != v}
        if valid_translations:
            self.cache.update(valid_translations)
            self.save_cache()
            logger.info(f"Added {len(valid_translations)} new translations to cache")
    
    def get_untranslated_words(self, words: List[str]) -> List[str]:
        """Return list of words that need translation."""
        untranslated = []
        for word in words:
            if word.strip() and (word not in self.cache or self.cache[word] is None):
                untranslated.append(word)
        return untranslated


class ChromeTranslator:
    """Chrome-based translator using web UI."""
    
    def __init__(self, progress_callback=None):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium is required for ChromeTranslator")
            
        self.driver = None
        self.translations = {}
        self.progress_callback = progress_callback
        self.temp_file = None
        self.translation_failed = False
        self.root = None
        self.translation_complete = False
        self.headless_mode = False
        self.retry_count = 0
        self.max_retries = 3
        self.translated_count = 0
        self.total_count = 0
        self.debug_mode = True
    
    def setup_driver(self, method_name="", headless=False, root=None):
        """Setup Chrome driver with enhanced error handling."""
        self.root = root
        self.headless_mode = headless
        chrome_options = Options()
        
        if headless:
            chrome_options.add_argument("--headless=new")
        
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--lang=en-US")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-images")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-translate-ranker-enforcement")
        
        # Force Chrome to detect Chinese content
        chrome_options.add_argument("--accept-language=en-US,en;q=0.9")
        chrome_options.add_argument("--disable-notifications")
        
        # Enhanced translation preferences
        prefs = {
            "translate": {"enabled": True},
            "translate.enabled": True,
            "translate_whitelists": {
                "zh": "en", "zh-CN": "en", "zh-TW": "en",
                "ja": "en", "ko": "en", "ar": "en", "ru": "en",
                "fr": "en", "de": "en", "es": "en", "it": "en",
                "pt": "en", "ru": "en"
            },
            "translate_accepted_languages": ["en"],
            "translate_site_blacklist": [],
            "profile.default_content_setting_values": {"notifications": 2},
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Translation features
        chrome_options.add_argument("--enable-features=Translate")
        chrome_options.add_argument("--translate-script-url=https://translate.googleapis.com/translate_a/element.js")
        chrome_options.add_argument("--disable-translate-new-ux")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(60)
            logger.info(f"Chrome driver setup successful for method: {method_name}")
            return True
        except WebDriverException as e:
            logger.error(f"Failed to setup Chrome driver for method {method_name}: {str(e)}")
            return False
    
    def create_translation_html(self, words: List[str]) -> Path:
        """Create an HTML page optimized for translation extraction."""
        self.temp_file = Path("temp_translation_page.html")
        self.total_count = len(words)
        self.translated_count = 0
        
        # Group words by length to optimize translation
        word_groups = {}
        for word in words:
            length = len(word)
            if length not in word_groups:
                word_groups[length] = []
            word_groups[length].append(word)
        
        # Sort groups by length (longest first)
        sorted_groups = sorted(word_groups.items(), key=lambda x: x[0], reverse=True)
        
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN" translate="yes">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Language" content="zh-CN">
    <meta name="google" content="translate">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>需要翻译的文本内容</title>
    <style>
        body {{
            font-family: 'Microsoft YaHei', SimHei, sans-serif;
            padding: 20px;
            line-height: 1.6;
            background-color: #f9f9f9;
        }}
        .word-container {{
            margin: 10px 0;
            padding: 12px;
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
        .word-text {{
            font-size: 16px;
            font-weight: 500;
            color: #333;
            position: relative;
            padding-left: 30px;
        }}
        .word-number {{
            position: absolute;
            left: 0;
            top: 0;
            color: #666;
            font-size: 12px;
            font-weight: normal;
        }}
        .translated-word {{
            color: #2196F3;
            font-weight: bold;
        }}
        h1 {{
            color: #2c3e50;
            margin-bottom: 20px;
            text-align: center;
        }}
        .instruction {{
            text-align: center;
            color: #7f8c8d;
            margin-bottom: 20px;
        }}
        .translation-status {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: #4CAF50;
            color: white;
            padding: 10px 20px;
            border-radius: 4px;
            display: none;
        }}
        #translateButton {{
            display: block;
            margin: 20px auto;
            padding: 10px 20px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }}
        #translateButton:hover {{
            background-color: #45a049;
        }}
        .progress-container {{
            position: fixed;
            top: 20px;
            left: 20px;
            background: #2196F3;
            color: white;
            padding: 10px 15px;
            border-radius: 4px;
            font-size: 14px;
            z-index: 1000;
        }}
        .word-list {{
            column-count: 2;
            column-gap: 20px;
        }}
        .word-item {{
            break-inside: avoid;
            margin-bottom: 10px;
        }}
        .continue-button {{
            display: none;
            margin: 20px auto;
            padding: 10px 20px;
            background-color: #2196F3;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }}
        .continue-button:hover {{
            background-color: #0b7dda;
        }}
        .force-translate-button {{
            display: none;
            margin: 20px auto;
            padding: 10px 20px;
            background-color: #ff9800;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }}
        .force-translate-button:hover {{
            background-color: #e68a00;
        }}
        .debug-panel {{
            position: fixed;
            bottom: 10px;
            right: 10px;
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 10px;
            border-radius: 4px;
            font-size: 12px;
            max-width: 300px;
            max-height: 200px;
            overflow-y: auto;
            display: none;
        }}
        .debug-panel h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
        }}
        .debug-item {{
            margin: 2px 0;
            padding: 2px;
            border-bottom: 1px solid rgba(255,255,255,0.2);
            font-family: monospace;
            font-size: 11px;
        }}
    </style>
</head>
<body translate="yes">
    <div class="progress-container" id="progressContainer">0/{self.total_count}</div>
    <div class="translation-status" id="translationStatus">准备翻译...</div>
    <h1>需要翻译的文本内容</h1>
    <p class="instruction">以下是从项目中提取的需要翻译的词汇，Chrome将自动翻译为英语</p>
    <button id="translateButton">开始翻译 - Start Translate</button>
    <button id="continueButton" class="continue-button">继续翻译已翻译的数字 - Continue Translating Already Translated Number</button>
    <button id="forceTranslateButton" class="force-translate-button">强制翻译 - Force Translation</button>
    <div class="word-list" id="wordList">
"""
        
        # Add words with data attributes and numbering
        for i, word in enumerate(words, 1):
            html_content += f"""        <div class="word-item">
            <div class="word-text" data-original="{word}" data-number="{i}">
                <span class="word-number">{i}.</span> {word}
            </div>
        </div>
"""
        
        html_content += """    </div>
    <p class="instruction">翻译完成</p>
    <div class="debug-panel" id="debugPanel">
        <h3>调试信息 - Debug Information</h3>
        <div id="debugContent"></div>
    </div>

    <script>
        // Force Chrome to detect language and show translation
        document.documentElement.lang = 'zh-CN';
        document.documentElement.setAttribute('translate', 'yes');
        
        // Initialize translation
        let translatedCount = 0;
        let totalCount = document.querySelectorAll('.word-text').length;
        let translationComplete = false;
        let translationStarted = false;
        let translationResults = {};
        let debugMessages = [];
        let checkInterval = null;
        let startTime = null;
        let maxWaitTime = 120000; // 2 minutes
        
        // Debug logging function
        function debugLog(message) {
            debugMessages.push(message);
            console.log(message);
            const debugContent = document.getElementById('debugContent');
            if (debugContent) {
                debugContent.innerHTML = debugMessages.slice(-10).join('<br>');
            }
        }
        
        // Update progress
        function updateProgress() {
            document.getElementById('progressContainer').textContent = `${translatedCount}/${totalCount}`;
            
            if (translatedCount >= totalCount && totalCount > 0) {
                translationComplete = true;
                document.getElementById('translationStatus').textContent = '翻译完成！';
                document.getElementById('translationStatus').style.display = 'block';
                document.getElementById('translateButton').style.display = 'none';
                document.getElementById('continueButton').style.display = 'block';
                document.getElementById('forceTranslateButton').style.display = 'block';
                
                // Signal parent window that translation is complete
                window.postMessage({
                    type: 'translationComplete',
                    count: translatedCount,
                    total: totalCount
                }, '*');
                
                debugLog('Translation marked as complete');
            }
        }
        
        // Enhanced translation detection
        function detectTranslation(element) {
            const original = element.getAttribute('data-original');
            const current = element.textContent.trim();
            
            if (!original || !current || original === current) {
                return null;
            }
            
            // Check if text contains English characters
            const hasEnglish = /[a-zA-Z]/.test(current);
            
            // Check if text has changed significantly
            const isDifferent = current !== original;
            
            // Check if text contains any non-ASCII characters (indicating it might still be in original language)
            const hasNonASCII = /[^\\x00-\\x7F]/.test(current);
            
            // Check ASCII ratio
            let asciiCount = 0;
            for (let i = 0; i < current.length; i++) {
                if (current.charCodeAt(i) < 128) asciiCount++;
            }
            const asciiRatio = asciiCount / current.length;
            
            debugLog(`Detection for "${original}": hasEnglish=${hasEnglish}, isDifferent=${isDifferent}, hasNonASCII=${hasNonASCII}, asciiRatio=${asciiRatio.toFixed(2)}`);
            
            // Consider it translated if it has English characters and is different from original
            if (hasEnglish && isDifferent) {
                return current;
            }
            
            // Also consider it translated if ASCII ratio is high enough and text is different
            if (asciiRatio > 0.6 && isDifferent) {
                return current;
            }
            
            // For very short words, be more lenient
            if (original.length <= 3 && isDifferent && asciiRatio > 0.3) {
                return current;
            }
            
            return null;
        }
        
        // Monitor all elements for translation changes
        function monitorTranslations() {
            const elements = document.querySelectorAll('.word-text');
            let newTranslations = 0;
            
            elements.forEach((element, index) => {
                const original = element.getAttribute('data-original');
                const translatedText = detectTranslation(element);
                
                if (translatedText && !element.classList.contains('translated')) {
                    element.classList.add('translated');
                    element.setAttribute('data-translated', translatedText);
                    translationResults[original] = translatedText;
                    newTranslations++;
                    debugLog(`Translation detected: "${original}" -> "${translatedText}"`);
                }
            });
            
            if (newTranslations > 0) {
                translatedCount += newTranslations;
                updateProgress();
            }
        }
        
        // Check if Chrome has shown translation UI
        function checkForTranslationUI() {
            const translateElement = document.querySelector('goog-gt');
            if (translateElement) {
                debugLog('Google Translate UI detected');
                return true;
            }
            return false;
        }
        
        // Start translation
        document.getElementById('translateButton').addEventListener('click', function() {
            if (translationStarted) return;
            translationStarted = true;
            startTime = Date.now();
            
            debugLog('Starting translation process...');
            
            // Mark all words for translation
            document.querySelectorAll('.word-text').forEach(el => {
                el.setAttribute('translate', 'yes');
            });
            
            // Hide the button
            this.style.display = 'none';
            
            // Try to trigger Chrome's translation
            try {
                // Right-click to trigger context menu
                const event = new MouseEvent('contextmenu', {
                    bubbles: true
                });
                document.dispatchEvent(event);
                
                // Look for translate option in context menu
                setTimeout(() => {
                    const contextMenu = document.querySelector('.goog-menu');
                    if (contextMenu) {
                        debugLog('Found Google context menu');
                        // Try to click translate option
                        const translateOptions = contextMenu.querySelectorAll('.goog-menuitem');
                        translateOptions.forEach(option => {
                            if (option.textContent.includes('Translate')) {
                                debugLog('Clicking translate option');
                                option.click();
                            }
                        });
                    }
                }, 1000);
            } catch (e) {
                debugLog('Error triggering context menu: ' + e.message);
            }
            
            // Start monitoring
            checkInterval = setInterval(monitorTranslations, 2000);
            debugLog('Started monitoring translations');
        });
        
        // Force translation
        document.getElementById('forceTranslateButton').addEventListener('click', function() {
            debugLog('Force translating all words...');
            
            // Reset all translations
            document.querySelectorAll('.word-text').forEach(el => {
                el.classList.remove('translated');
                el.removeAttribute('data-translated');
                el.setAttribute('translate', 'yes');
            });
            
            // Clear existing results
            translationResults = {};
            translatedCount = 0;
            
            // Try to force Chrome to retranslate
            try {
                // Create a new paragraph with Chinese text to trigger translation
                const tempDiv = document.createElement('div');
                tempDiv.style.cssText = 'position: absolute; left: -9999px; top: -9999px;';
                tempDiv.textContent = '这是一个测试文本用于触发翻译功能';
                document.body.appendChild(tempDiv);
                
                // Select and trigger translation
                const range = document.createRange();
                range.selectNodeContents(tempDiv);
                const selection = window.getSelection();
                selection.removeAllRanges();
                selection.addRange(range);
                
                // Trigger translation
                setTimeout(() => {
                    tempDiv.remove();
                    monitorTranslations();
                }, 1000);
                
            } catch (e) {
                debugLog('Error forcing translation: ' + e.message);
            }
        });
        
        // Continue translating already translated words
        document.getElementById('continueButton').addEventListener('click', function() {
            debugLog('Continuing translation process...');
            
            // Reset translated count to recheck all words
            translatedCount = 0;
            translationComplete = false;
            
            // Clear translated class to force re-translation
            document.querySelectorAll('.word-text').forEach(el => {
                el.classList.remove('translated');
                el.removeAttribute('data-translated');
                el.setAttribute('translate', 'yes');
            });
            
            // Hide continue button
            this.style.display = 'none';
            document.getElementById('translateButton').style.display = 'block';
            document.getElementById('forceTranslateButton').style.display = 'none';
            
            // Start monitoring again
            if (checkInterval) {
                clearInterval(checkInterval);
            }
            checkInterval = setInterval(monitorTranslations, 2000);
        });
        
        // Global function to get translations (called by Selenium)
        window.getTranslationResults = function() {
            debugLog('getTranslationResults called, collecting all translations...');
            
            // Final collection - get all translated text
            const finalResults = {};
            const elements = document.querySelectorAll('.word-text');
            
            elements.forEach((element, index) => {
                const original = element.getAttribute('data-original');
                const translated = element.getAttribute('data-translated');
                const current = element.textContent.trim();
                
                // Use stored translation if available
                if (translated) {
                    finalResults[original] = translated;
                } else if (current !== original) {
                    // Try to detect translation on the fly
                    const detected = detectTranslation(element);
                    if (detected) {
                        finalResults[original] = detected;
                    }
                }
            });
            
            const resultCount = Object.keys(finalResults).length;
            debugLog(`Final collection: ${resultCount} translations found`);
            
            return {
                translations: finalResults,
                count: resultCount,
                total: totalCount,
                success: resultCount > 0
            };
        };
        
        // Global function to get detailed translation status
        window.getTranslationStatus = function() {
            return {
                translated: translatedCount,
                total: totalCount,
                complete: translationComplete,
                elapsedTime: startTime ? Date.now() - startTime : 0
            };
        };
        
        // Initialize
        updateProgress();
        debugLog('Page loaded, ready for translation');
        
        // Show debug panel if debug mode is enabled
        if ({self.debug_mode}) {
            document.getElementById('debugPanel').style.display = 'block';
        }
    </script>
</body>
</html>"""
        
        try:
            with open(self.temp_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info(f"Created translation page with {len(words)} words")
            return self.temp_file
        except Exception as e:
            logger.error(f"Failed to create translation page: {str(e)}")
            raise
    
    def scroll_to_bottom(self, delay=0.5):
        """Scroll to the bottom of the page to trigger translation of all elements."""
        if not self.driver:
            return
            
        try:
            # Get the total height of the page
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            viewport_height = self.driver.execute_script("return window.innerHeight")
            
            # Calculate how many page downs we need
            scroll_steps = max(1, int(total_height / viewport_height))
            
            logger.info(f"Scrolling through {scroll_steps} pages to trigger translation")
            
            # Scroll down in steps
            for i in range(scroll_steps):
                # Scroll by one viewport
                self.driver.execute_script("window.scrollBy(0, window.innerHeight);")
                
                # Wait a bit for translation to happen
                time.sleep(delay)
                
                # Log progress
                if self.progress_callback and i % 5 == 0:
                    progress = min(90, 30 + (i / scroll_steps) * 50)
                    self.progress_callback(int(progress), 100, f"Scrolling to trigger translation: {i+1}/{scroll_steps}")
            
            # Scroll back to top
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(delay)
            
            logger.info("Scrolling completed")
            
        except Exception as e:
            logger.error(f"Error during scrolling: {str(e)}")
    
    def extract_translations(self, words: List[str]):
        """Extract translations using multiple methods with enhanced detection."""
        self.translations = {}
        successful_translations = 0
        
        try:
            # Wait a bit more for Chrome translation to settle
            logger.info("Waiting for Chrome translation to settle...")
            time.sleep(5)
            
            # Try multiple approaches to extract translations
            approaches = [
                ("Direct DOM Text", self._extract_by_dom_text),
                ("Data Attributes", self._extract_by_data_attributes),
                ("JavaScript Function", self._extract_by_javascript_function),
                ("Inner HTML", self._extract_by_inner_html),
                ("Computed Styles", self._extract_by_computed_styles),
            ]
            
            for approach_name, approach_func in approaches:
                try:
                    logger.info(f"Trying extraction method: {approach_name}")
                    approach_translations = approach_func()
                    
                    if approach_translations:
                        # Validate and merge translations
                        for original, translated in approach_translations.items():
                            if original and translated and original != translated:
                                # Only add if we don't already have a translation for this word
                                if original not in self.translations:
                                    self.translations[original] = translated
                                    successful_translations += 1
                                    if successful_translations <= 10:  # Log first 10
                                        logger.info(f"Translated: '{original}' -> '{translated}' (method: {approach_name})")
                        
                        if self.translations:
                            logger.info(f"Found {len(self.translations)} translations using {approach_name}")
                            break  # Exit if we found translations
                except Exception as e:
                    logger.warning(f"Error with extraction method {approach_name}: {str(e)}")
            
            # If no translations were found, use fallback
            if not self.translations:
                logger.warning("All extraction methods failed, using fallback")
                self.translations = {word: word for word in words}
            
            logger.info(f"Translation extraction completed: {successful_translations}/{len(words)} words translated")
            
        except Exception as e:
            logger.error(f"Error extracting translations: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _extract_by_dom_text(self) -> Dict[str, str]:
        """Extract translations by comparing DOM text content."""
        translations = {}
        try:
            word_elements = self.driver.find_elements(By.CSS_SELECTOR, ".word-text")
            logger.info(f"Found {len(word_elements)} word elements")
            
            for element in word_elements:
                try:
                    original = element.get_attribute("data-original")
                    current = element.text.strip()
                    
                    if original and current and original != current:
                        # Check if it looks like English
                        if self._is_likely_english(current):
                            translations[original] = current
                            logger.debug(f"DOM Text: '{original}' -> '{current}'")
                except StaleElementReferenceException:
                    continue
            except Exception as e:
                logger.warning(f"Error in DOM text extraction: {str(e)}")
        
        return translations
    
    def _extract_by_data_attributes(self) -> Dict[str, str]:
        """Extract translations using data attributes."""
        translations = {}
        try:
            word_elements = self.driver.find_elements(By.CSS_SELECTOR, ".word-text")
            
            for element in word_elements:
                try:
                    original = element.get_attribute("data-original")
                    translated = element.get_attribute("data-translated")
                    
                    if original and translated and original != translated:
                        translations[original] = translated
                        logger.debug(f"Data Attribute: '{original}' -> '{translated}'")
                except StaleElementReferenceException:
                    continue
        except Exception as e:
            logger.warning(f"Error in data attribute extraction: {str(e)}")
        
        return translations
    
    def _extract_by_javascript_function(self) -> Dict[str, str]:
        """Extract translations using JavaScript function."""
        translations = {}
        try:
            # Call JavaScript function to get translations
            result = self.driver.execute_script("return window.getTranslationResults ? window.getTranslationResults() : {};")
            
            if result and isinstance(result, dict):
                translations = result.get("translations", {})
                logger.info(f"JavaScript Function returned {len(translations)} translations")
        except Exception as e:
            logger.warning(f"Error in JavaScript function extraction: {str(e)}")
        
        return translations
    
    def _extract_by_inner_html(self) -> Dict[str, str]:
        """Extract translations by parsing inner HTML."""
        translations = {}
        try:
            word_elements = self.driver.find_elements(By.CSS_SELECTOR, ".word-text")
            
            for element in word_elements:
                try:
                    original = element.get_attribute("data-original")
                    inner_html = element.get_attribute("innerHTML")
                    
                    if not inner_html:
                        continue
                    
                    # Parse HTML to extract text
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(inner_html, "html.parser")
                    parsed_text = soup.get_text().strip()
                    
                    if original and parsed_text and original != parsed_text:
                        if self._is_likely_english(parsed_text):
                            translations[original] = parsed_text
                            logger.debug(f"Inner HTML: '{original}' -> '{parsed_text}'")
                except StaleElementReferenceException:
                    continue
        except Exception as e:
            logger.warning(f"Error in inner HTML extraction: {str(e)}")
        
        return translations
    
    def _extract_by_computed_styles(self) -> Dict[str, str]:
        """Extract translations by checking computed styles."""
        translations = {}
        try:
            word_elements = self.driver.find_elements(By.CSS_SELECTOR, ".word-text")
            
            for element in word_elements:
                try:
                    original = element.get_attribute("data-original")
                    current = element.text.strip()
                    
                    if original and current and original != current:
                        # Check if element has been translated by Chrome
                        style = element.get_attribute("style") or ""
                        if "font-family" in style or "direction" in style:
                            if self._is_likely_english(current):
                                translations[original] = current
                                logger.debug(f"Computed Style: '{original}' -> '{current}'")
                except StaleElementReferenceException:
                    continue
        except Exception as e:
            logger.warning(f"Error in computed styles extraction: {str(e)}")
        
        return translations
    
    def _is_likely_english(self, text: str) -> bool:
        """Check if text is likely English."""
        if not text or len(text) < 2:
            return False
        
        # Check ASCII ratio
        ascii_chars = sum(1 for c in text if ord(c) < 128)
        ascii_ratio = ascii_chars / len(text)
        
        # Must have mostly ASCII characters
        if ascii_ratio < 0.6:
            return False
        
        # Check for common English words
        common_words = {
            'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have',
            'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you',
            'do', 'at', 'this', 'but', 'his', 'by', 'from',
            'they', 'we', 'say', 'her', 'she', 'or', 'an',
            'will', 'my', 'one', 'all', 'would', 'there', 'their',
            'what', 'so', 'up', 'out', 'if', 'about', 'who',
            'get', 'which', 'go', 'me', 'when', 'make', 'can',
            'like', 'time', 'no', 'just', 'him', 'know', 'take',
            'people', 'into', 'year', 'your', 'good', 'some',
            'could', 'them', 'see', 'other', 'than', 'then',
            'now', 'look', 'only', 'come', 'its', 'over', 'think',
            'also', 'back', 'after', 'use', 'two', 'how',
            'our', 'work', 'first', 'well', 'way', 'even',
            'new', 'want', 'because', 'any', 'these', 'give',
            'day', 'most', 'us'
        }
        
        words = text.lower().split()
        common_word_count = sum(1 for word in words if word in common_words)
        
        # If we have at least one common English word and high ASCII ratio, consider it English
        return common_word_count > 0 or ascii_ratio > 0.8
    
    def method_1_visible_chrome_translation(self, words: List[str]) -> bool:
        """Enhanced Chrome translation with better error handling and retry logic."""
        if not self.setup_driver("Visible Chrome Translation", headless=self.headless_mode, root=self.root):
            return False
        
        try:
            self.create_translation_page(words)
            file_url = f"file://{self.temp_file.absolute()}"
            self.driver.get(file_url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Wait for user to click translate button
            logger.info("Waiting for user to click 'Start Translate' button...")
            time.sleep(5)
            
            # Try to click translate button automatically
            try:
                translate_button = self.driver.find_element(By.ID, "translateButton")
                translate_button.click()
                logger.info("Clicked 'Start Translate' button")
            except:
                logger.info("Could not find or click 'Start Translate' button")
            
            # Scroll through the page to trigger translation
            self.scroll_to_bottom(delay=0.5)
            
            # Wait for translation to complete with improved monitoring
            logger.info("Waiting for Chrome translation to complete...")
            
            # Maximum wait time
            max_wait_time = 180  # 3 minutes
            start_time = time.time()
            last_translated_count = 0
            stable_count = 0
            
            while time.time() - start_time < max_wait_time:
                try:
                    # Get current translation status
                    status = self.driver.execute_script("return window.getTranslationStatus ? window.getTranslationStatus() : null;")
                    
                    if status:
                        current_count = status.get("translated", 0)
                        total = status.get("total", len(words))
                        is_complete = status.get("complete", False)
                        elapsed = int(status.get("elapsedTime", 0) / 1000)
                        
                        if current_count > last_translated_count:
                            last_translated_count = current_count
                            stable_count = 0
                        else:
                            stable_count += 1
                        
                        # Update progress
                        if self.progress_callback:
                            progress = 30 + (current_count / total) * 50  # 30-80% range
                            self.progress_callback(int(progress), 100, f"Chrome translating: {current_count}/{total} words ({elapsed}s)")
                        
                        # If translation count is stable for 10 seconds, consider it complete
                        if stable_count >= 10 and current_count > 0:
                            logger.info(f"Translation appears complete: {current_count} words")
                            break
                        
                        # If we have a good number of translations, continue for a bit more
                        if current_count >= total * 0.8:  # 80% or more translated
                            logger.info(f"Good translation progress: {current_count}/{total} (80%+ threshold reached)")
                            if stable_count >= 5:  # Less strict for high translation rates
                                break
                    
                    time.sleep(2)  # Check every 2 seconds
                
                except Exception as e:
                    logger.warning(f"Error checking translation status: {str(e)}")
                    time.sleep(2)
            
            # Extract translations using multiple methods
            self.extract_translations(words)
            return True
        
        except Exception as e:
            logger.error(f"Visible Chrome translation failed: {str(e)}")
            import traceback
            traceback.print_exc()
            self.retry_count += 1
            
            if self.retry_count < self.max_retries:
                logger.info(f"Retrying ({self.retry_count}/{self.max_retries})...")
                time.sleep(2)  # Wait before retry
                return self.method_1_visible_chrome_translation(words)
            
            return False
        finally:
            self.cleanup()
            self.retry_count = 0  # Reset retry count
    
    def translate_words(self, words: List[str]) -> Dict[str, str]:
        """Main translation method - Chrome only."""
        if not words:
            return {}
        
        self.translations = {}
        total_words = len(words)
        
        if self.progress_callback:
            self.progress_callback(0, 100, "Starting translation process...")
        
        # Try Chrome translation
        try:
            if self.progress_callback:
                self.progress_callback(20, 100, "Trying Chrome Translation...")
            
            if self.method_1_visible_chrome_translation(words):
                if self.progress_callback:
                    successful_count = len([t for t in self.translations.values() 
                                          if t != words[list(self.translations.keys()).index(t)]])
                    self.progress_callback(100, 100, f"Chrome Translation successful! Translated {successful_count}/{len(words)} words")
                return self.translations
            else:
                if self.progress_callback:
                    self.progress_callback(25, 100, "Chrome Translation failed")
        
        except Exception as e:
            logger.error(f"Chrome Translation failed with error: {str(e)}")
            if self.progress_callback:
                self.progress_callback(25, 100, f"Chrome Translation failed with error: {str(e)}")
        
        # All methods failed
        logger.error("All translation methods failed")
        if self.progress_callback:
            self.progress_callback(100, 100, "All translation methods failed - using fallback")
        
        # Final fallback: keep original words
        return {word: word for word in words}
    
    def cleanup(self):
        """Clean up resources with error handling."""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
        except Exception as e:
            logger.error(f"Error quitting driver: {str(e)}")
            self.driver = None
        
        try:
            if self.temp_file and self.temp_file.exists():
                self.temp_file.unlink()
                self.temp_file = None
        except Exception as e:
            logger.error(f"Error deleting temp file: {str(e)}")
            self.temp_file = None


# Example usage
if __name__ == "__main__":
    # Example words to translate
    chinese_words = [
        "你好", "世界", "计算机", "编程", "语言", "翻译", "软件", "开发",
        "人工智能", "机器学习", "深度学习", "数据科学", "算法", "数据结构"
    ]
    
    # Initialize translator with progress callback
    def progress_callback(current, total, message=""):
        print(f"Progress: {current}/{total} - {message}")
    
    translator = ChromeTranslator(progress_callback=progress_callback)
    
    # Translate words
    translations = translator.translate_words(chinese_words)
    
    # Print results
    print("\nTranslation Results:")
    for original, translated in translations.items():
        print(f"{original} -> {translated}")
    
    # Save translation map to file
    output_file = Path("translation_map.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(translations, f, ensure_ascii=False, indent=2)
    
    print(f"\nTranslation map saved to: {output_file}")