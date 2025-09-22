#!/usr/bin/env python3
"""
Codebase scanner for extracting foreign words (Chinese) from source files.
"""

import os
import re
import ast
import logging
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Default blacklist of directories to skip
DEFAULT_BLACKLIST = [
    "multi-language",
    "docs",
    ".git",
    "build",
    ".github",
    ".vscode",
    "__pycache__",
    "venv",
    "node_modules",
    ".idea",
    ".vs",
    ".pytest_cache",
    ".mypy_cache",
    "__snapshots__",
    ".next",
    ".nuxt",
    "dist",
]


class ChineseExtractor:
    """Extracts Chinese text from source files with enhanced detection."""

    # Extended Chinese character ranges
    CHINESE_PATTERNS = [
        r"[\u4e00-\u9fff]+",  # CJK Unified Ideographs
        r"[\u3400-\u4dbf]+",  # CJK Extension A
        r"[\u20000-\u2a6df]+",  # CJK Extension B
        r"[\u2a700-\u2b73f]+",  # CJK Extension C
        r"[\u2b740-\u2b81f]+",  # CJK Extension D
        r"[\u2b820-\u2ceaf]+",  # CJK Extension E
        r"[\uf900-\ufaff]+",  # CJK Compatibility Ideographs
        r"[\u2f800-\u2fa1f]+",  # CJK Compatibility Ideographs Supplement
    ]

    @staticmethod
    def contains_chinese(text: str) -> bool:
        """Check if text contains Chinese characters."""
        if not text:
            return False

        for pattern in ChineseExtractor.CHINESE_PATTERNS:
            if re.search(pattern, text):
                return True
        return False

    @staticmethod
    def extract_from_file_content(
        file_path: str, gui_callback=None
    ) -> Tuple[List[str], List[str]]:
        """Extract both identifiers and strings from a file."""
        identifiers = []
        strings = []

        try:
            # Try multiple encodings
            content = None
            encodings = [
                "utf-8",
                "utf-8-sig",
                "gbk",
                "gb2312",
                "big5",
                "latin1",
                "cp1252",
            ]

            for encoding in encodings:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        content = f.read()
                    if gui_callback:
                        gui_callback(f"✓ Read {file_path} with {encoding} encoding")
                    break
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    if gui_callback:
                        gui_callback(
                            f"✗ Error reading {file_path} with {encoding}: {e}"
                        )
                    continue

            if not content:
                if gui_callback:
                    gui_callback(f"✗ Could not read {file_path} with any encoding")
                return identifiers, strings

            # Check if file has any Chinese at all
            has_chinese = ChineseExtractor.contains_chinese(content)
            if gui_callback:
                gui_callback(
                    f"📄 {os.path.basename(file_path)}: Contains Chinese = {has_chinese}"
                )

            if not has_chinese:
                return identifiers, strings

            # Extract comments first (before AST parsing)
            comment_strings = ChineseExtractor._extract_comments(content, gui_callback)
            strings.extend(comment_strings)

            # Extract string literals and identifiers using AST
            try:
                tree = ast.parse(content)
                ast_identifiers, ast_strings = ChineseExtractor._extract_from_ast(
                    tree, gui_callback
                )
                identifiers.extend(ast_identifiers)
                strings.extend(ast_strings)

            except SyntaxError as e:
                if gui_callback:
                    gui_callback(
                        f"⚠ AST parsing failed for {file_path}, using regex fallback: {e}"
                    )
                # Regex fallback
                regex_identifiers, regex_strings = ChineseExtractor._extract_with_regex(
                    content, gui_callback
                )
                identifiers.extend(regex_identifiers)
                strings.extend(regex_strings)

            # Debug output
            if identifiers or strings:
                if gui_callback:
                    gui_callback(
                        f"📊 {os.path.basename(file_path)}: Found {len(identifiers)} identifiers, {len(strings)} strings"
                    )
                    if identifiers:
                        gui_callback(f" Identifiers sample: {identifiers[:3]}")
                    if strings:
                        gui_callback(f" Strings sample: {strings[:3]}")

        except Exception as e:
            if gui_callback:
                gui_callback(f"✗ Error processing {file_path}: {e}")
            logger.error(f"Error extracting from {file_path}: {e}")

        return identifiers, strings

    @staticmethod
    def _extract_comments(content: str, gui_callback=None) -> List[str]:
        """Extract Chinese from comments."""
        comment_strings = []

        for line_num, line in enumerate(content.splitlines(), 1):
            # Find comments
            comment_match = re.search(r"#(.*)$", line)
            if comment_match:
                comment = comment_match.group(1).strip()
                if comment and ChineseExtractor.contains_chinese(comment):
                    # Split complex comments
                    split_comments = ChineseExtractor._split_complex_string(comment)
                    if split_comments:
                        comment_strings.extend(split_comments)
                        if gui_callback:
                            gui_callback(
                                f" 📝 Line {line_num} comment: {split_comments}"
                            )

        return comment_strings

    @staticmethod
    def _extract_from_ast(tree, gui_callback=None) -> Tuple[List[str], List[str]]:
        """Extract using AST parsing."""
        identifiers = []
        strings = []

        for node in ast.walk(tree):
            # Extract identifiers
            if isinstance(node, ast.Name):
                if ChineseExtractor.contains_chinese(node.id):
                    identifiers.append(node.id)
            elif isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                if ChineseExtractor.contains_chinese(node.name):
                    identifiers.append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if ChineseExtractor.contains_chinese(alias.name):
                        identifiers.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and ChineseExtractor.contains_chinese(node.module):
                    for part in node.module.split("."):
                        if ChineseExtractor.contains_chinese(part):
                            identifiers.append(part)
                for alias in node.names:
                    if ChineseExtractor.contains_chinese(alias.name):
                        identifiers.append(alias.name)

            # Extract string literals
            string_value = None
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                string_value = node.value
            elif hasattr(ast, "Str") and isinstance(node, ast.Str):  # Python < 3.8
                string_value = node.s

            if string_value and ChineseExtractor.contains_chinese(string_value):
                split_strings = ChineseExtractor._split_complex_string(string_value)
                if split_strings:
                    strings.extend(split_strings)

        return identifiers, strings

    @staticmethod
    def _extract_with_regex(
        content: str, gui_callback=None
    ) -> Tuple[List[str], List[str]]:
        """Regex-based extraction fallback."""
        identifiers = []
        strings = []

        # Extract string literals
        string_patterns = [
            r'"([^"]*)"',  # Double quotes
            r"'([^']*)'",  # Single quotes
            r'"""([^"]*)"""',  # Triple double quotes
            r"'''([^']*)'''",  # Triple single quotes
        ]

        for pattern in string_patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            for match in matches:
                if match and ChineseExtractor.contains_chinese(match):
                    split_strings = ChineseExtractor._split_complex_string(match)
                    strings.extend(split_strings)

        # Extract potential identifiers (simple approach)
        identifier_pattern = (
            r"\b([a-zA-Z_][a-zA-Z0-9_]*[\u4e00-\u9fff]+[a-zA-Z0-9_]*)\b"
        )
        identifier_matches = re.findall(identifier_pattern, content)
        for match in identifier_matches:
            if ChineseExtractor.contains_chinese(match):
                identifiers.append(match)

        return identifiers, strings

    @staticmethod
    def _split_complex_string(text: str) -> List[str]:
        """Split complex strings into translatable parts."""
        if not text or not ChineseExtractor.contains_chinese(text):
            return []

        # Clean the text
        text = text.strip()
        if text.startswith("[Local Message]"):
            text = text.replace("[Local Message]", "").strip()

        # Split by delimiters
        delimiters = [
            "，",
            "。",
            "）",
            "（",
            "(",
            ")",
            "<",
            ">",
            "[",
            "]",
            "【",
            "】",
            "？",
            "：",
            ":",
            ",",
            "#",
            "\n",
            ";",
            "`",
            " ",
            "- ",
            "---",
            "！",
            "!",
            "、",
            "…",
            "～",
        ]

        parts = [text]
        for delimiter in delimiters:
            new_parts = []
            for part in parts:
                if delimiter in part:
                    split_parts = [p.strip() for p in part.split(delimiter)]
                    for p in split_parts:
                        if p and ChineseExtractor.contains_chinese(p):
                            new_parts.append(p)
                else:
                    if ChineseExtractor.contains_chinese(part):
                        new_parts.append(part)
            parts = new_parts

        # Filter out problematic parts
        filtered_parts = []
        for part in parts:
            part = part.strip()
            # Skip if too short, contains URLs, or problematic characters
            if (
                len(part) < 2
                or any(
                    url in part.lower()
                    for url in [".com", ".org", ".net", "http", "www.", "https"]
                )
                or part.count('"') > 0
                or part.count("'") > 0
                or part.startswith("//")
                or part.startswith("/*")
            ):
                continue
            filtered_parts.append(part)

        return filtered_parts


class CodebaseMapper:
    """Maps and enumerates all foreign words in the codebase."""

    def __init__(self, root_path: str, blacklist: List[str] = None):
        self.root_path = Path(root_path)
        self.blacklist = blacklist or DEFAULT_BLACKLIST
        self.extractor = ChineseExtractor()
        self.all_words: Set[str] = set()
        self.file_word_map: Dict[str, List[str]] = {}

    def scan_codebase(self, gui_callback=None) -> Dict[str, List[str]]:
        """Scan the entire codebase for Chinese words."""
        if gui_callback:
            gui_callback(f"🔍 Scanning codebase: {self.root_path}")

        for file_path in self._get_python_files():
            if gui_callback:
                gui_callback(f"📄 Processing: {file_path}")

            identifiers, strings = self.extractor.extract_from_file_content(
                file_path, gui_callback
            )

            # Combine and add to global set
            file_words = identifiers + strings
            if file_words:
                self.file_word_map[str(file_path)] = file_words
                self.all_words.update(file_words)

        if gui_callback:
            gui_callback(f"✅ Found {len(self.all_words)} unique Chinese words")

        return self.file_word_map

    def _get_python_files(self) -> List[Path]:
        """Get all Python files in the codebase, excluding blacklisted directories."""
        python_files = []

        for root, dirs, files in os.walk(self.root_path):
            # Skip blacklisted directories
            dirs[:] = [d for d in dirs if d not in self.blacklist]

            for file in files:
                if file.endswith(".py"):
                    python_files.append(Path(root) / file)

        return python_files

    def get_unique_words(self) -> List[str]:
        """Get all unique Chinese words found in the codebase."""
        return sorted(list(self.all_words))

    def get_word_counts(self) -> Dict[str, int]:
        """Get frequency count of each Chinese word."""
        word_counts = {}
        for words in self.file_word_map.values():
            for word in words:
                word_counts[word] = word_counts.get(word, 0) + 1
        return word_counts


def main():
    """Main function to run the codebase scanner."""
    parser = argparse.ArgumentParser(description="Scan codebase for Chinese text.")
    parser.add_argument("path", help="Path to the codebase to scan")
    parser.add_argument(
        "--blacklist",
        nargs="*",
        default=None,
        help="Space-separated list of directories to blacklist (default: use built-in blacklist)",
    )
    args = parser.parse_args()

    # Use custom blacklist if provided, otherwise use default
    blacklist = args.blacklist if args.blacklist else None

    mapper = CodebaseMapper(args.path, blacklist)
    word_map = mapper.scan_codebase()
    unique_words = mapper.get_unique_words()
    word_counts = mapper.get_word_counts()

    print(f"Found {len(unique_words)} unique Chinese words")
    print("Top 10 most common:")
    for word, count in sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[
        :10
    ]:
        print(f"  {word}: {count}")


if __name__ == "__main__":
    main()
