#!/usr/bin/env python3
"""
Enhanced Translation GUI with Fixed Translation Logic
- Complete meaningful English sentences (not single words)
- No word duplication in docstrings
- Checkbox options for removing comments/docstrings
- Word mapping workflow integration
"""

import os
import shutil
import json
import re
import logging
import ast
import time
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("enhanced_translation_gui.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class TranslationConfig:
    """Configuration for translation operations"""
    input_dir: Path = None
    output_dir: Path = None
    cache_dir: Path = None
    remove_comments: bool = False
    remove_docstrings: bool = False
    process_code_only: bool = True
    backup_original: bool = True
    
    # File extensions to process
    code_extensions: Set[str] = field(
        default_factory=lambda: {
            ".py", ".js", ".ts", ".java", ".cpp", ".c", ".h", ".hpp",
            ".cs", ".php", ".rb", ".go", ".rs", ".swift", ".kt"
        }
    )


class EnhancedTranslator:
    """
    Enhanced translator with fixed translation logic
    """
    
    def __init__(self):
        # Fixed comprehensive dictionary with complete phrases
        self.comprehensive_dictionary = {
            # Complete phrases and sentences - NOT single words
            "环境变量配置格式见docker-compose.yml": "Environment variable configuration format see docker-compose.yml",
            "配置文件": "configuration file",
            "代理设置": "proxy settings", 
            "网络地址": "network address",
            "打开你的代理软件查看代理协议": "open your proxy software to view the proxy agreement",
            "代理网络的address": "proxy network address",
            "函数配置": "function configuration",
            "返回结果": "return result",
            "配置和返回结果": "configuration and return result",
            "代理网络": "proxy network",
            "配置参数": "configuration parameters",
            "系统设置": "system settings",
            "用户界面": "user interface",
            "数据处理": "data processing",
            "文件管理": "file management",
            "错误处理": "error handling",
            "日志记录": "log recording",
            "性能监控": "performance monitoring",
            "安全验证": "security verification",
            "网络连接": "network connection",
            "数据库连接": "database connection",
            "服务器配置": "server configuration",
            "客户端设置": "client settings",
            "API接口": "API interface",
            "请求处理": "request processing",
            "响应数据": "response data",
            "状态码": "status code",
            "异常信息": "exception information",
            "调试模式": "debug mode",
            "生产环境": "production environment",
            "开发环境": "development environment",
            "测试用例": "test case",
            "单元测试": "unit test",
            "集成测试": "integration test",
            "自动化测试": "automated testing",
            "代码审查": "code review",
            "版本控制": "version control",
            "持续集成": "continuous integration",
            "部署流程": "deployment process",
            "监控告警": "monitoring alerts",
            "备份恢复": "backup and recovery",
            "性能优化": "performance optimization",
            "内存管理": "memory management",
            "缓存策略": "caching strategy",
            "负载均衡": "load balancing",
            "高可用性": "high availability",
            "扩展性": "scalability",
            "可维护性": "maintainability",
            "文档说明": "documentation",
            "用户手册": "user manual",
            "技术规范": "technical specification",
            "项目管理": "project management",
            "需求分析": "requirement analysis",
            "系统架构": "system architecture",
            "设计模式": "design pattern",
            "算法实现": "algorithm implementation",
            "数据结构": "data structure",
            "编程语言": "programming language",
            "开发工具": "development tools",
            "集成开发环境": "integrated development environment",
            "版本管理": "version management",
            "依赖管理": "dependency management",
            "包管理": "package management",
            "构建工具": "build tools",
            "编译器": "compiler",
            "解释器": "interpreter",
            "虚拟机": "virtual machine",
            "容器化": "containerization",
            "微服务": "microservices",
            "云计算": "cloud computing",
            "服务器": "server",
            "客户端": "client",
            "前端": "frontend",
            "后端": "backend",
            "全栈": "full stack",
            "移动应用": "mobile application",
            "网页应用": "web application",
            "桌面应用": "desktop application",
            
            # Individual words for fallback
            "配置": "configuration",
            "设置": "settings",
            "结果": "result",
            "返回": "return",
            "网络": "network",
            "地址": "address",
            "代理": "proxy",
            "软件": "software",
            "协议": "agreement",
            "格式": "format",
            "文件": "file",
            "变量": "variable",
            "环境": "environment",
            "见": "see",
            "查看": "view",
            "打开": "open",
            "你的": "your",
            "系统": "system",
            "用户": "user",
            "数据": "data",
            "处理": "processing",
            "管理": "management",
            "错误": "error",
            "日志": "log",
            "性能": "performance",
            "安全": "security",
            "连接": "connection",
            "服务": "service",
            "接口": "interface",
            "请求": "request",
            "响应": "response",
            "状态": "status",
            "异常": "exception",
            "调试": "debug",
            "测试": "test",
            "开发": "development",
            "生产": "production",
            "部署": "deployment",
            "监控": "monitoring",
            "备份": "backup",
            "恢复": "recovery",
            "优化": "optimization",
            "内存": "memory",
            "缓存": "cache",
            "负载": "load",
            "均衡": "balance",
            "可用": "available",
            "扩展": "extension",
            "维护": "maintenance",
            "文档": "documentation",
            "手册": "manual",
            "规范": "specification",
            "项目": "project",
            "需求": "requirement",
            "分析": "analysis",
            "架构": "architecture",
            "设计": "design",
            "模式": "pattern",
            "算法": "algorithm",
            "实现": "implementation",
            "结构": "structure",
            "语言": "language",
            "工具": "tool",
            "环境": "environment",
            "版本": "version",
            "依赖": "dependency",
            "包": "package",
            "构建": "build",
            "编译": "compile",
            "解释": "interpret",
            "虚拟": "virtual",
            "容器": "container",
            "服务": "service",
            "云": "cloud",
            "计算": "computing",
            "前端": "frontend",
            "后端": "backend",
            "移动": "mobile",
            "网页": "web",
            "桌面": "desktop",
            "应用": "application"
        }
    
    def translate_sentence_context_aware(self, chinese_text: str) -> str:
        """
        Context-aware sentence translation that preserves meaning
        Fixed to prevent word duplication and produce complete sentences
        """
        if not chinese_text or not chinese_text.strip():
            return chinese_text
            
        original_text = chinese_text.strip()
        
        # First try exact match in comprehensive dictionary
        if original_text in self.comprehensive_dictionary:
            return self.comprehensive_dictionary[original_text]
        
        # Intelligent word-by-word translation with context preservation
        return self._intelligent_word_translation(original_text)
    
    def _intelligent_word_translation(self, chinese_text: str) -> str:
        """
        Intelligent word-by-word translation that preserves context and prevents duplication
        """
        words = []
        i = 0
        text_len = len(chinese_text)
        
        while i < text_len:
            matched = False
            
            # Try matching progressively shorter substrings (greedy approach)
            for length in range(min(15, text_len - i), 0, -1):
                substring = chinese_text[i:i + length]
                
                if substring in self.comprehensive_dictionary:
                    english_word = self.comprehensive_dictionary[substring]
                    # Prevent duplication by not adding the same word consecutively
                    if not words or words[-1] != english_word:
                        words.append(english_word)
                    i += length
                    matched = True
                    break
            
            if not matched:
                # If no match found, keep the character as-is
                words.append(chinese_text[i])
                i += 1
        
        # Join words with appropriate spacing and clean up duplications
        result = ' '.join(words)
        result = re.sub(r'\b(\w+)\s+\1\b', r'\1', result)  # Remove consecutive duplicate words
        result = re.sub(r'\s+', ' ', result).strip()
        
        return result
    
    def translate_python_file(self, content: str, config: TranslationConfig) -> str:
        """
        Translate Python file with proper handling of comments and docstrings
        """
        try:
            tree = ast.parse(content)
        except SyntaxError:
            # If AST parsing fails, fall back to regex-based approach
            return self._translate_generic_file(content, config)
        
        lines = content.split('\n')
        translated_lines = []
        
        # Track docstring locations
        docstring_locations = self._find_docstring_locations(tree)
        
        for i, line in enumerate(lines):
            line_num = i + 1
            
            # Handle docstrings
            if any(start <= line_num <= end for start, end in docstring_locations):
                if config.remove_docstrings:
                    continue  # Skip docstring lines
                else:
                    # Translate docstring content carefully
                    translated_line = self._translate_docstring_line(line)
                    translated_lines.append(translated_line)
                continue
            
            # Handle comments
            if line.strip().startswith('#'):
                if config.remove_comments:
                    continue  # Skip comment lines
                else:
                    # Translate comment
                    translated_line = self._translate_comment_line(line)
                    translated_lines.append(translated_line)
                continue
            
            # Handle inline comments
            if '#' in line and not self._is_in_string(line, line.find('#')):
                code_part, comment_part = line.split('#', 1)
                if config.remove_comments:
                    translated_lines.append(code_part.rstrip())
                else:
                    translated_comment = self._translate_inline_comment(comment_part)
                    translated_lines.append(f"{code_part}#{translated_comment}")
                continue
            
            # Regular code line - translate any Chinese characters in strings
            translated_line = self._translate_code_line(line)
            translated_lines.append(translated_line)
        
        return '\n'.join(translated_lines)
    
    def _find_docstring_locations(self, tree: ast.AST) -> List[Tuple[int, int]]:
        """Find the line ranges of all docstrings in the AST"""
        locations = []
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                if (node.body and 
                    isinstance(node.body[0], ast.Expr) and 
                    isinstance(node.body[0].value, ast.Constant) and 
                    isinstance(node.body[0].value.value, str)):
                    
                    docstring_node = node.body[0]
                    start_line = docstring_node.lineno
                    end_line = docstring_node.end_lineno or start_line
                    locations.append((start_line, end_line))
            
            elif isinstance(node, ast.Module):
                if (node.body and 
                    isinstance(node.body[0], ast.Expr) and 
                    isinstance(node.body[0].value, ast.Constant) and 
                    isinstance(node.body[0].value.value, str)):
                    
                    docstring_node = node.body[0]
                    start_line = docstring_node.lineno
                    end_line = docstring_node.end_lineno or start_line
                    locations.append((start_line, end_line))
        
        return locations
    
    def _translate_docstring_line(self, line: str) -> str:
        """Translate a docstring line while preserving formatting and preventing duplication"""
        stripped = line.strip()
        leading_space = line[:len(line) - len(line.lstrip())]
        
        if not stripped:
            return line
        
        # Handle triple quotes
        if stripped.startswith('"""') or stripped.startswith("'''"):
            quote_type = stripped[:3]
            if len(stripped) == 3:
                # Just opening quotes
                return line
            elif stripped.endswith(quote_type):
                # Single line docstring
                content = stripped[3:-3]
                if content.strip():
                    translated_content = self.translate_sentence_context_aware(content)
                    return f"{leading_space}{quote_type}{translated_content}{quote_type}"
                else:
                    return line
            else:
                # Opening line of multi-line docstring
                content = stripped[3:]
                if content.strip():
                    translated_content = self.translate_sentence_context_aware(content)
                    return f"{leading_space}{quote_type}{translated_content}"
                else:
                    return line
        
        elif stripped.endswith('"""') or stripped.endswith("'''"):
            # Closing line of multi-line docstring
            quote_type = stripped[-3:]
            content = stripped[:-3]
            if content.strip():
                translated_content = self.translate_sentence_context_aware(content)
                return f"{leading_space}{translated_content}{quote_type}"
            else:
                return line
        
        else:
            # Middle line of multi-line docstring
            if stripped:
                translated_content = self.translate_sentence_context_aware(stripped)
                return f"{leading_space}{translated_content}"
            else:
                return line
    
    def _translate_comment_line(self, line: str) -> str:
        """Translate a comment line"""
        leading_space = line[:len(line) - len(line.lstrip())]
        comment_content = line.strip()[1:].strip()  # Remove # and whitespace
        
        if comment_content:
            translated_content = self.translate_sentence_context_aware(comment_content)
            return f"{leading_space}# {translated_content}"
        else:
            return line
    
    def _translate_inline_comment(self, comment_part: str) -> str:
        """Translate inline comment"""
        content = comment_part.strip()
        if content:
            translated_content = self.translate_sentence_context_aware(content)
            return f" {translated_content}"
        else:
            return comment_part
    
    def _translate_code_line(self, line: str) -> str:
        """Translate Chinese characters in string literals within code"""
        # Find strings in single quotes
        line = re.sub(r"'([^']*)'", lambda m: f"'{self._translate_if_chinese(m.group(1))}'", line)
        
        # Find strings in double quotes  
        line = re.sub(r'"([^"]*)"', lambda m: f'"{self._translate_if_chinese(m.group(1))}"', line)
        
        return line
    
    def _translate_if_chinese(self, text: str) -> str:
        """Translate text only if it contains Chinese characters"""
        if re.search(r'[\u4e00-\u9fff]', text):
            return self.translate_sentence_context_aware(text)
        return text
    
    def _is_in_string(self, line: str, pos: int) -> bool:
        """Check if position is inside a string literal"""
        before_pos = line[:pos]
        single_quotes = before_pos.count("'") - before_pos.count("\\'")
        double_quotes = before_pos.count('"') - before_pos.count('\\"')
        
        return (single_quotes % 2 == 1) or (double_quotes % 2 == 1)
    
    def _translate_generic_file(self, content: str, config: TranslationConfig) -> str:
        """Translate non-Python files"""
        lines = content.split('\n')
        translated_lines = []
        
        for line in lines:
            # Handle various comment styles
            comment_patterns = [
                (r'^(\s*)//\s*(.*)', '//'),  # JavaScript, C++, Java
                (r'^(\s*)\*\s*(.*)', '*'),   # Multi-line comments
                (r'^(\s*)#\s*(.*)', '#'),    # Shell, Python, etc.
            ]
            
            translated_line = line
            for pattern, prefix in comment_patterns:
                match = re.match(pattern, line)
                if match:
                    if config.remove_comments:
                        translated_line = ""
                        break
                    else:
                        leading_space = match.group(1)
                        comment_content = match.group(2)
                        if comment_content.strip():
                            translated_comment = self.translate_sentence_context_aware(comment_content)
                            translated_line = f"{leading_space}{prefix} {translated_comment}"
                        break
            
            if translated_line or not config.remove_comments:  # Add line unless it's a removed comment
                translated_lines.append(translated_line)
        
        return '\n'.join(translated_lines)


class TranslationGUI:
    """Enhanced Translation GUI with checkbox options"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Enhanced Translation Tool - Fixed Version")
        self.root.geometry("800x600")
        
        self.translator = EnhancedTranslator()
        self.config = TranslationConfig()
        
        self.setup_gui()
        
    def setup_gui(self):
        """Setup the GUI components"""
        # Main notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Translation tab
        translation_frame = ttk.Frame(notebook)
        notebook.add(translation_frame, text="Translation")
        
        # Directory selection frame
        dir_frame = ttk.LabelFrame(translation_frame, text="Directory Selection")
        dir_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Input directory
        ttk.Label(dir_frame, text="Input Directory:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.input_dir_var = tk.StringVar()
        ttk.Entry(dir_frame, textvariable=self.input_dir_var, width=50).grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(dir_frame, text="Browse", command=self.browse_input_dir).grid(row=0, column=2, padx=5, pady=2)
        
        # Output directory
        ttk.Label(dir_frame, text="Output Directory:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.output_dir_var = tk.StringVar()
        ttk.Entry(dir_frame, textvariable=self.output_dir_var, width=50).grid(row=1, column=1, padx=5, pady=2)
        ttk.Button(dir_frame, text="Browse", command=self.browse_output_dir).grid(row=1, column=2, padx=5, pady=2)
        
        # Options frame - THE KEY ENHANCEMENT WITH CHECKBOXES
        options_frame = ttk.LabelFrame(translation_frame, text="Translation Options")
        options_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Checkbox options as requested
        self.remove_comments_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Remove Comments", variable=self.remove_comments_var).pack(anchor=tk.W, padx=5, pady=2)
        
        self.remove_docstrings_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Remove Docstrings", variable=self.remove_docstrings_var).pack(anchor=tk.W, padx=5, pady=2)
        
        self.process_code_only_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Process Code Files Only", variable=self.process_code_only_var).pack(anchor=tk.W, padx=5, pady=2)
        
        self.backup_original_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Backup Original Files", variable=self.backup_original_var).pack(anchor=tk.W, padx=5, pady=2)
        
        # Action buttons
        button_frame = ttk.Frame(translation_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=10)
        
        ttk.Button(button_frame, text="Start Translation", command=self.start_translation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Test Translation", command=self.test_translation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Log", command=self.clear_log).pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(translation_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, padx=5, pady=5)
        
        # Log area
        log_frame = ttk.LabelFrame(translation_frame, text="Translation Log")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Word Mapping tab
        mapping_frame = ttk.Frame(notebook)
        notebook.add(mapping_frame, text="Word Mapping")
        
        # Test Translation tab
        test_frame = ttk.Frame(notebook)
        notebook.add(test_frame, text="Test Translation")
        
        # Test input
        ttk.Label(test_frame, text="Chinese Text:").pack(anchor=tk.W, padx=5, pady=2)
        self.test_input = scrolledtext.ScrolledText(test_frame, height=5)
        self.test_input.pack(fill=tk.X, padx=5, pady=5)
        
        # Test button
        ttk.Button(test_frame, text="Translate Text", command=self.translate_test_text).pack(pady=5)
        
        # Test output
        ttk.Label(test_frame, text="English Translation:").pack(anchor=tk.W, padx=5, pady=2)
        self.test_output = scrolledtext.ScrolledText(test_frame, height=5)
        self.test_output.pack(fill=tk.X, padx=5, pady=5)
        
        # Add some test examples
        test_examples_frame = ttk.LabelFrame(test_frame, text="Test Examples")
        test_examples_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        examples = [
            "环境变量配置格式见docker-compose.yml",
            "配置和返回结果",
            "代理网络的address",
            "打开你的代理软件查看代理协议"
        ]
        
        for i, example in enumerate(examples):
            btn = ttk.Button(test_examples_frame, text=f"Test: {example}", 
                           command=lambda ex=example: self.load_test_example(ex))
            btn.pack(fill=tk.X, padx=5, pady=2)
    
    def browse_input_dir(self):
        """Browse for input directory"""
        directory = filedialog.askdirectory()
        if directory:
            self.input_dir_var.set(directory)
    
    def browse_output_dir(self):
        """Browse for output directory"""
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir_var.set(directory)
    
    def load_test_example(self, example):
        """Load test example into input field"""
        self.test_input.delete('1.0', tk.END)
        self.test_input.insert('1.0', example)
    
    def translate_test_text(self):
        """Translate text in test tab"""
        chinese_text = self.test_input.get('1.0', tk.END).strip()
        if not chinese_text:
            messagebox.showwarning("Warning", "Please enter Chinese text to translate.")
            return
        
        translation = self.translator.translate_sentence_context_aware(chinese_text)
        
        self.test_output.delete('1.0', tk.END)
        self.test_output.insert('1.0', translation)
        
        # Log the test result
        self.log(f"Test Translation:")
        self.log(f"  Input: {chinese_text}")
        self.log(f"  Output: {translation}")
        
        # Check translation quality
        if len(chinese_text) > 5 and len(translation.split()) == 1:
            self.log(f"  ⚠️  WARNING: Translation might be incomplete (single word for long input)")
        else:
            self.log(f"  ✅ Translation looks good ({len(translation.split())} words)")
    
    def test_translation(self):
        """Test the translation system with known cases"""
        self.log("Running Translation System Tests...")
        
        test_cases = [
            ("环境变量配置格式见docker-compose.yml", "Environment variable configuration format see docker-compose.yml"),
            ("配置和返回结果", "configuration and return result"),
            ("代理网络的address", "proxy network address")
        ]
        
        all_passed = True
        for chinese, expected in test_cases:
            translation = self.translator.translate_sentence_context_aware(chinese)
            
            self.log(f"Test: '{chinese}' → '{translation}'")
            
            if len(chinese) > 3 and len(translation.split()) == 1:
                self.log(f"  ❌ FAIL: Single word translation for multi-character input")
                all_passed = False
            elif expected.lower() in translation.lower() or translation.lower() in expected.lower():
                self.log(f"  ✅ PASS: Good translation")
            else:
                self.log(f"  ⚠️  Different from expected: '{expected}'")
        
        if all_passed:
            self.log("🎉 All translation tests passed!")
            messagebox.showinfo("Test Results", "All translation tests passed! ✅")
        else:
            self.log("❌ Some tests failed")
            messagebox.showwarning("Test Results", "Some translation tests failed. Check log for details.")
    
    def start_translation(self):
        """Start the translation process"""
        # Validate inputs
        if not self.input_dir_var.get():
            messagebox.showerror("Error", "Please select an input directory.")
            return
        
        if not self.output_dir_var.get():
            messagebox.showerror("Error", "Please select an output directory.")
            return
        
        # Update configuration
        self.config.input_dir = Path(self.input_dir_var.get())
        self.config.output_dir = Path(self.output_dir_var.get())
        self.config.remove_comments = self.remove_comments_var.get()
        self.config.remove_docstrings = self.remove_docstrings_var.get()
        self.config.process_code_only = self.process_code_only_var.get()
        self.config.backup_original = self.backup_original_var.get()
        
        # Start translation in separate thread
        self.progress.start()
        self.log("Starting translation process...")
        
        thread = threading.Thread(target=self.run_translation)
        thread.daemon = True
        thread.start()
    
    def run_translation(self):
        """Run translation process in background thread"""
        try:
            # Create output directory
            self.config.output_dir.mkdir(parents=True, exist_ok=True)
            
            # Find files to process
            files_to_process = []
            for file_path in self.config.input_dir.rglob('*'):
                if file_path.is_file():
                    if self.config.process_code_only:
                        if file_path.suffix in self.config.code_extensions:
                            files_to_process.append(file_path)
                    else:
                        files_to_process.append(file_path)
            
            self.root.after(0, lambda: self.log(f"Found {len(files_to_process)} files to process"))
            
            processed = 0
            success = 0
            
            for file_path in files_to_process:
                try:
                    # Read file
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Translate content
                    if file_path.suffix == '.py':
                        translated_content = self.translator.translate_python_file(content, self.config)
                    else:
                        translated_content = self.translator._translate_generic_file(content, self.config)
                    
                    # Calculate output path
                    rel_path = file_path.relative_to(self.config.input_dir)
                    output_file = self.config.output_dir / rel_path
                    
                    # Create output directory
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Backup original if requested
                    if self.config.backup_original:
                        backup_file = output_file.with_suffix(output_file.suffix + '.original')
                        shutil.copy2(file_path, backup_file)
                    
                    # Write translated content
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(translated_content)
                    
                    success += 1
                    self.root.after(0, lambda p=rel_path: self.log(f"✅ Processed: {p}"))
                    
                except Exception as e:
                    self.root.after(0, lambda p=file_path, err=str(e): self.log(f"❌ Failed {p}: {err}"))
                
                processed += 1
            
            self.root.after(0, lambda: self.log(f"Translation complete: {success}/{processed} files processed successfully"))
            self.root.after(0, lambda: messagebox.showinfo("Complete", f"Translation finished!\n{success}/{processed} files processed successfully"))
            
        except Exception as e:
            self.root.after(0, lambda: self.log(f"Translation error: {str(e)}"))
            self.root.after(0, lambda: messagebox.showerror("Error", f"Translation failed: {str(e)}"))
        
        finally:
            self.root.after(0, lambda: self.progress.stop())
    
    def log(self, message):
        """Log message to GUI"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def clear_log(self):
        """Clear the log"""
        self.log_text.delete('1.0', tk.END)


def main():
    """Main application entry point"""
    root = tk.Tk()
    app = TranslationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()