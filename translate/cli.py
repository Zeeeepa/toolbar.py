from __future__ import annotations

import argparse
import json
import logging
import shutil
from pathlib import Path
from typing import Dict, List

from translate.config import Config, DEFAULT_CONFIG
from translate.mapper import CodebaseMapper, ChineseExtractor
from translate.translators.base import get_translator
from translate.applier_mt import TranslationApplierMT


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("translate.cli")


def get_cache(target_lang: str):
    # Lazy import to avoid selenium/chrome issues on simple commands
    from translate.chrome_translate import TranslationCache  # local import
    return TranslationCache(target_lang)


def save_mapping_jsonl(mapping_path: Path, words: List[str]) -> None:
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    with open(mapping_path, "w", encoding="utf-8") as f:
        for w in words:
            rec = {"text": w}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_mapping_jsonl(mapping_path: Path) -> List[str]:
    words: List[str] = []
    if mapping_path.exists():
        with open(mapping_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    t = obj.get("text")
                    if isinstance(t, str):
                        words.append(t)
                except Exception:
                    continue
    return words


def export_wordlist(config: Config, mapping_words: List[str], cache) -> None:
    # Merge cache values for found words
    merged: Dict[str, str] = {}
    for w in mapping_words:
        v = cache.get_cached_translation(w)
        if v:
            merged[w] = v
    # Format and save
    lines = []
    for k, v in merged.items():
        if v and v.strip() and k != v:
            lines.append((k, v))
    # sort: by len desc then lexicographically
    lines.sort(key=lambda kv: (-len(kv[0]), kv[0]))
    config.cache_dir.mkdir(parents=True, exist_ok=True)
    with open(config.wordlist_file, "w", encoding="utf-8") as f:
        for k, v in lines:
            f.write(f"{k} -> {v}\n")
    logger.info(f"Exported formatted word list: {config.wordlist_file}")


def validate_translations(config: Config, mapping_words: List[str], cache) -> int:
    # Build a simple validation report
    report = {
        "total_words": len(mapping_words),
        "checked": 0,
        "issues": [],
    }

    def contains_chinese(s: str) -> bool:
        return ChineseExtractor.contains_chinese(s)

    for w in mapping_words:
        t = cache.get_cached_translation(w)
        if not t:
            continue
        report["checked"] += 1
        # Check emptiness
        if not t.strip():
            report["issues"].append({"word": w, "issue": "empty_translation"})
            continue
        # Check that Chinese is reduced (sanity)
        if contains_chinese(t) and not contains_chinese(w):
            report["issues"].append({"word": w, "issue": "target_contains_chinese"})
        # Placeholder preservation (basic): if source had placeholders, target should too
        had_brace = "{" in w and "}" in w
        if had_brace and ("{" not in t or "}" not in t):
            report["issues"].append({"word": w, "issue": "brace_placeholder_lost"})

    config.out_dir.mkdir(parents=True, exist_ok=True)
    with open(config.validation_report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info(f"Validation report written to: {config.validation_report_file}")

    return 1 if report["issues"] else 0


def cmd_map(args: argparse.Namespace, config: Config) -> int:
    mapper = CodebaseMapper(args.project)
    mapper.scan_codebase()
    words = mapper.get_unique_words()
    words.sort(key=lambda s: (len(s), s))
    save_mapping_jsonl(config.mapping_file, words)
    logger.info(f"Mapped {len(words)} unique words -> {config.mapping_file}")
    return 0


def cmd_translate(args: argparse.Namespace, config: Config) -> int:
    words = load_mapping_jsonl(config.mapping_file)
    if not words:
        logger.warning("No mapping words found; run 'map' first")
        return 1

    cache = get_cache(config.target_lang)
    untranslated = [w for w in words if not cache.get_cached_translation(w)]
    logger.info(f"{len(untranslated)} words to translate (from {len(words)} total)")

    if not untranslated:
        return 0

    translator = get_translator(config.engine)
    translated_map = translator.translate_words(untranslated, config.source_lang, config.target_lang)
    cache.add_translations(translated_map)

    # Export formatted list
    export_wordlist(config, words, cache)
    return 0


def cmd_export(args: argparse.Namespace, config: Config) -> int:
    words = load_mapping_jsonl(config.mapping_file)
    cache = get_cache(config.target_lang)
    export_wordlist(config, words, cache)
    return 0


def cmd_validate(args: argparse.Namespace, config: Config) -> int:
    words = load_mapping_jsonl(config.mapping_file)
    cache = get_cache(config.target_lang)
    code = validate_translations(config, words, cache)
    return code


def cmd_apply(args: argparse.Namespace, config: Config) -> int:
    project_path = Path(args.project).resolve()
    output_path = Path(args.out).resolve() if args.out else project_path.parent / f"{project_path.name}_translated"

    if output_path.exists():
        if output_path.is_file():
            output_path.unlink()
        else:
            shutil.rmtree(output_path)
    shutil.copytree(project_path, output_path)

    cache = get_cache(config.target_lang)
    mapping = cache.cache  # dict

    applier = TranslationApplierMT(config)
    ok, msg, _details = applier.apply(project_path, output_path, mapping, workers=config.workers, dry_run=False)
    if ok:
        logger.info(msg)
        return 0
    else:
        logger.error(msg)
        return 1


def cmd_status(args: argparse.Namespace, config: Config) -> int:
    words = load_mapping_jsonl(config.mapping_file)
    cache = get_cache(config.target_lang)
    total = len(words)
    translated = sum(1 for w in words if cache.get_cached_translation(w))
    logger.info(f"Status: {translated}/{total} mapped words have cached translations")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="translate", description="Codebase translation CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    p.add_argument("--engine", default=DEFAULT_CONFIG.engine, help="Engine: zai|chrome (default: zai)")
    p.add_argument("--workers", type=int, default=DEFAULT_CONFIG.workers, help="Workers for apply")
    p.add_argument("--language", default=DEFAULT_CONFIG.target_lang, help="Target language (default: English)")

    m = sub.add_parser("map", help="Scan project and map unique CN words")
    m.add_argument("project", help="Path to project")
    m.set_defaults(func=cmd_map)

    t = sub.add_parser("translate", help="Translate unmapped words and update cache")
    t.add_argument("project", help="Path to project (used for context paths only)")
    t.set_defaults(func=cmd_translate)

    e = sub.add_parser("export", help="Export formatted word list from cache")
    e.add_argument("project", help="Path to project (used for locating mapping.jsonl)")
    e.set_defaults(func=cmd_export)

    v = sub.add_parser("validate", help="Run validation gates on cached translations")
    v.add_argument("project", help="Path to project")
    v.set_defaults(func=cmd_validate)

    a = sub.add_parser("apply", help="Apply translations to a copied project directory")
    a.add_argument("project", help="Path to project")
    a.add_argument("--out", help="Output directory (default: <project>_translated)")
    a.set_defaults(func=cmd_apply)

    s = sub.add_parser("status", help="Show cache/mapping status")
    s.add_argument("project", help="Path to project")
    s.set_defaults(func=cmd_status)

    return p


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    cfg = Config()
    cfg.engine = args.engine
    cfg.workers = int(args.workers)
    cfg.target_lang = args.language
    cfg.ensure_dirs()

    return args.func(args, cfg)


if __name__ == "__main__":
    raise SystemExit(main())

