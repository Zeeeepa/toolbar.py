from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from translate.config import Config, DEFAULT_CONFIG


def read_text_any(path: Path) -> Tuple[str, str] | Tuple[None, None]:
    encodings = ["utf-8", "utf-16", "latin1", "cp1252", "ascii"]
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read(), enc
        except UnicodeDecodeError:
            continue
        except Exception:
            continue
    return None, None


def write_atomic(path: Path, content: str, encoding: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding=encoding) as f:
        f.write(content)
    os.replace(tmp, path)


def apply_mapping_to_text(content: str, mapping: List[Tuple[str, str]]) -> Tuple[str, int]:
    # mapping is sorted by key length desc
    total = 0
    out = content
    for k, v in mapping:
        if not k or not v or k == v:
            continue
        if k in out:
            count = out.count(k)
            out = out.replace(k, v)
            total += count
    return out, total


class TranslationApplierMT:
    def __init__(self, config: Config | None = None, progress_callback=None):
        self.config = config or DEFAULT_CONFIG
        self.progress_callback = progress_callback

    def _iter_files(self, root: Path) -> Iterable[Path]:
        for p in root.rglob("*"):
            if p.is_file() and not self.config.is_binary(p) and not self.config.in_blacklist(p):
                yield p

    def apply(self, input_dir: Path, output_dir: Path, mapping: Dict[str, str], workers: int | None = None, dry_run: bool = False) -> Tuple[bool, str, Dict[str, int]]:
        if not output_dir.exists():
            return False, f"Output directory does not exist: {output_dir}", {}

        # filter actual translations and sort
        pairs = [(k, v) for k, v in mapping.items() if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip() and k != v]
        pairs.sort(key=lambda kv: len(kv[0]), reverse=True)

        all_files = list(self._iter_files(output_dir))
        total_files = len(all_files)
        total_replacements = 0
        files_updated = 0
        per_file_counts: Dict[str, int] = {}

        def process_file(path: Path) -> Tuple[str, int, bool]:
            text_enc = read_text_any(path)
            if not text_enc[0]:
                return str(path), 0, False
            content, enc = text_enc  # type: ignore
            new_content, replaced = apply_mapping_to_text(content, pairs)
            if replaced > 0 and not dry_run:
                write_atomic(path, new_content, enc)
            return str(path), replaced, replaced > 0

        max_workers = workers or self.config.workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(process_file, p): p for p in all_files}
            done = 0
            for fut in concurrent.futures.as_completed(futures):
                path_str, replaced, updated = fut.result()
                per_file_counts[path_str] = replaced
                total_replacements += replaced
                if updated:
                    files_updated += 1
                done += 1
                if self.progress_callback:
                    self.progress_callback(done, total_files, f"Applying translations... {done}/{total_files}")

        msg = (
            f"Processed {total_files} files. Updated {files_updated} files with {total_replacements} total replacements."
        )
        return True, msg, per_file_counts

