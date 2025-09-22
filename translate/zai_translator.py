from __future__ import annotations

import asyncio
import json
import math
import random
import re
from typing import Dict, List

from translate.zai_client import AsyncZAIClient, ChatCompletionResponse
from translate.config import DEFAULT_CONFIG, Config


def chunk_by_chars(items: List[str], max_chars: int, max_items: int) -> List[List[str]]:
    batches: List[List[str]] = []
    current: List[str] = []
    char_count = 0
    for t in items:
        l = len(t)
        # oversize: its own batch
        if l >= max_chars:
            if current:
                batches.append(current)
                current = []
                char_count = 0
            batches.append([t])
            continue
        if current and (char_count + l > max_chars or len(current) >= max_items):
            batches.append(current)
            current = [t]
            char_count = l
        else:
            current.append(t)
            char_count += l
    if current:
        batches.append(current)
    return batches


def protect_placeholders(s: str) -> str:
    # Replace braces-based placeholders with markers to avoid translation engine mangling them
    s = re.sub(r"\{([^}]+)\}", r"⟦ph:{\1}⟧", s)
    s = re.sub(r"%\(([^)]+)\)s", r"⟦ph:%(\1)s⟧", s)
    s = s.replace("%s", "⟦ph:%s⟧")
    s = re.sub(r"\$\{([^}]+)\}", r"⟦ph:${\1}⟧", s)
    return s


def unprotect_placeholders(s: str) -> str:
    s = re.sub(r"⟦ph:\{([^}]+)\}⟧", r"{\1}", s)
    s = re.sub(r"⟦ph:%\(([^)]+)\)s⟧", r"%(\1)s", s)
    s = s.replace("⟦ph:%s⟧", "%s")
    s = re.sub(r"⟦ph:\$\{([^}]+)\}⟧", r"${\1}", s)
    return s


class ZAITranslator:
    def __init__(self, progress_callback=None, config: Config | None = None):
        self.progress_callback = progress_callback
        self.config = config or DEFAULT_CONFIG

    async def _translate_batch(self, client: AsyncZAIClient, batch: List[str]) -> Dict[str, str]:
        # JSON-based mapping prompt where values are '#'
        payload = {protect_placeholders(t): "#" for t in batch}
        json_str = json.dumps(payload, ensure_ascii=False)
        prompt = (
            f"Replace each json value `#` with translated results in {self.config.target_lang}. "
            f"Keep JSON format only. Do not include explanations.\n\n{json_str}"
        )
        try:
            resp: ChatCompletionResponse = await client.simple_chat_async(prompt, model="glm-4.5v", max_tokens=3800)
            out = resp.content.strip()
            # Try to parse as JSON first
            try:
                parsed = json.loads(out)
            except json.JSONDecodeError:
                # Fallback: attempt to extract object text
                m = re.search(r"\{[\s\S]*\}", out)
                if not m:
                    return {t: t for t in batch}  # identity
                try:
                    parsed = json.loads(m.group(0))
                except Exception:
                    return {t: t for t in batch}
            result: Dict[str, str] = {}
            for orig in batch:
                p = protect_placeholders(orig)
                v = parsed.get(p)
                if isinstance(v, str) and v and v != "#":
                    v2 = unprotect_placeholders(v).strip()
                    result[orig] = v2
                else:
                    result[orig] = orig
            return result
        except Exception:
            # On any error, return identity mapping for the batch
            return {t: t for t in batch}

    async def translate_words_async(self, words: List[str], src_lang: str, tgt_lang: str) -> Dict[str, str]:
        words = [w for w in words if isinstance(w, str) and w.strip()]
        if not words:
            return {}
        # Shuffle a copy to avoid pathological clustering
        items = list(dict.fromkeys(words))  # de-dup preserving order
        random.shuffle(items)
        batches = chunk_by_chars(items, self.config.max_chars_per_batch, self.config.max_items_per_batch)
        sem = asyncio.Semaphore(self.config.concurrency)
        results: Dict[str, str] = {}

        async def worker(batch: List[str]):
            async with sem:
                client = AsyncZAIClient()
                try:
                    return await self._translate_batch(client, batch)
                finally:
                    await client.close()

        tasks = [asyncio.create_task(worker(b)) for b in batches]
        completed = 0
        for coro in asyncio.as_completed(tasks):
            out = await coro
            results.update(out)
            completed += 1
            if self.progress_callback:
                self.progress_callback(completed, len(batches), f"Translated batches: {completed}/{len(batches)}")
        # Ensure full mapping for original words list
        final: Dict[str, str] = {}
        for w in words:
            t = results.get(w, w)
            final[w] = t
        return final

    def translate_words(self, words: List[str], src_lang: str, tgt_lang: str) -> Dict[str, str]:
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                import concurrent.futures

                def run_it():
                    new_loop = asyncio.new_event_loop()
                    try:
                        asyncio.set_event_loop(new_loop)
                        return new_loop.run_until_complete(self.translate_words_async(words, src_lang, tgt_lang))
                    finally:
                        new_loop.close()

                with concurrent.futures.ThreadPoolExecutor() as ex:
                    fut = ex.submit(run_it)
                    return fut.result()
        except RuntimeError:
            pass
        return asyncio.run(self.translate_words_async(words, src_lang, tgt_lang))

