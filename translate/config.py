from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Set


DEFAULT_CACHE_DIR = Path("docs")
DEFAULT_OUT_DIR = Path("translate/out")
DEFAULT_STATE_DIR = Path("translate/state")


@dataclass
class Config:
    # Languages
    source_lang: str = field(default_factory=lambda: os.getenv("TRANSLATE_SRC", "Chinese"))
    target_lang: str = field(default_factory=lambda: os.getenv("TRANSLATE_TGT", "English"))

    # Directories
    cache_dir: Path = field(default_factory=lambda: Path(os.getenv("TRANSLATE_CACHE_DIR", str(DEFAULT_CACHE_DIR))))
    out_dir: Path = field(default_factory=lambda: Path(os.getenv("TRANSLATE_OUT_DIR", str(DEFAULT_OUT_DIR))))
    state_dir: Path = field(default_factory=lambda: Path(os.getenv("TRANSLATE_STATE_DIR", str(DEFAULT_STATE_DIR))))

    # Engine selection
    engine: str = field(default_factory=lambda: os.getenv("TRANSLATE_ENGINE", "zai"))  # zai | chrome

    # Batching and concurrency
    max_chars_per_batch: int = int(os.getenv("TRANSLATE_MAX_CHARS_PER_BATCH", "3800"))
    max_items_per_batch: int = int(os.getenv("TRANSLATE_MAX_ITEMS_PER_BATCH", "32"))
    concurrency: int = int(os.getenv("TRANSLATE_CONCURRENCY", "10"))

    # Apply/IO
    workers: int = int(os.getenv("TRANSLATE_APPLY_WORKERS", "10"))

    # File scanning
    blacklist: Set[str] = field(default_factory=lambda: {
        ".git", "__pycache__", "build", "dist", "venv", ".idea", ".vs",
        "node_modules", ".pytest_cache", ".mypy_cache", "__snapshots__",
        ".next", ".nuxt"
    })

    binary_extensions: Set[str] = field(default_factory=lambda: {
        ".woff", ".woff2", ".ttf", ".eot", ".otf", ".exe", ".dll",
        ".so", ".dylib", ".bin", ".zip", ".tar", ".gz", ".rar", ".7z",
        ".mp3", ".mp4", ".wav", ".avi", ".mov", ".pdf", ".wasm", ".idx",
        ".pack", ".rev"
    })

    # Safety
    placeholder_patterns: tuple[str, ...] = (
        r"\{[^}]+\}",  # {name}
        r"%s|%\([^)]+\)s",  # %s or %(name)s
        r"\$\{[^}]+\}",  # ${name}
    )

    def ensure_dirs(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    @property
    def cache_file(self) -> Path:
        # docs/translate_<lang>.json
        return self.cache_dir / f"translate_{self.target_lang.lower()}.json"

    @property
    def mapping_file(self) -> Path:
        return self.out_dir / "mapping.jsonl"

    @property
    def wordlist_file(self) -> Path:
        return self.cache_dir / f"translated_words_{self.target_lang.lower()}.txt"

    @property
    def summary_file(self) -> Path:
        return self.out_dir / "summary.json"

    @property
    def validation_report_file(self) -> Path:
        return self.out_dir / "validation_report.json"

    def is_binary(self, path: Path) -> bool:
        return path.suffix.lower() in self.binary_extensions

    def in_blacklist(self, path: Path) -> bool:
        # If any blacklist part is in the parents
        return any(b in str(path) for b in self.blacklist)


DEFAULT_CONFIG = Config()
DEFAULT_CONFIG.ensure_dirs()

