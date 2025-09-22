from __future__ import annotations

import abc
from typing import Dict, List, Optional


class BaseTranslator(abc.ABC):
    """Abstract translator interface."""

    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback

    @abc.abstractmethod
    def translate_words(self, words: List[str], src_lang: str, tgt_lang: str) -> Dict[str, str]:
        """Translate a list of words from src_lang to tgt_lang.
        Returns a mapping original -> translated. Implementations must be deterministic for the same inputs.
        """
        raise NotImplementedError


class ChromeTranslatorAdapter(BaseTranslator):
    """Adapter that wraps the existing ChromeTranslator for compatibility with the BaseTranslator interface.
    If selenium is unavailable, raises ImportError so callers can fallback to other engines.
    """

    def __init__(self, progress_callback=None, headless: bool = True):
        super().__init__(progress_callback)
        # Lazy import to avoid mandatory selenium dependency
        from translate.chrome_translate import ChromeTranslator
        self._impl = ChromeTranslator(progress_callback=progress_callback)
        self._impl.headless_mode = headless

    def translate_words(self, words: List[str], src_lang: str, tgt_lang: str) -> Dict[str, str]:
        if not words:
            return {}
        # Chrome translator doesn't use languages directly; it relies on UI detection/whitelists.
        result = self._impl.translate_words(words)
        # Ensure mapping shape
        out: Dict[str, str] = {}
        for w in words:
            out[w] = result.get(w, w)
        return out


def get_translator(engine: str, progress_callback=None):
    engine = (engine or "zai").lower()
    if engine == "chrome":
        return ChromeTranslatorAdapter(progress_callback=progress_callback, headless=True)
    elif engine == "zai":
        from translate.zai_translator import ZAITranslator
        return ZAITranslator(progress_callback=progress_callback)
    else:
        raise ValueError(f"Unknown translation engine: {engine}")

