#!/usr/bin/env python3
"""
Enhanced Word Mapper System
Implements proper word mapping workflow:
1. Map all Chinese words
2. Open in Chrome for translation
3. Save mappings
4. Apply to codebase without breaking files
"""

import os
import json
import re
import ast
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class WordMapping:
    """Word mapping with context and metadata"""
    chinese_word: str
    english_translation: str
    context: str = ""
    file_path: str = ""
    line_number: int = 0
    confidence: float = 1.0
    last_updated: float = field(default_factory=time.time)


class ChineseWordExtractor:
    """
    Extract Chinese words from code files for translation mapping
    """
    
    def __init__(self):
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
        self.extracted_words = set()
        self.word_contexts = {}  # word -> list of contexts
        
    def extract_from_python_file(self, file_path: Path) -> Set[str]:
        """Extract Chinese words from Python file using AST"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            words = set()
            
            # Extract from string literals
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    chinese_words = self.chinese_pattern.findall(node.value)
                    for word in chinese_words:
                        words.add(word)
                        self._add_context(word, node.value, str(file_path), node.lineno)
            
            return words
            
        except Exception as e:
            logger.error(f"Failed to extract from Python file {file_path}: {e}")
            return set()
    
    def extract_from_generic_file(self, file_path: Path) -> Set[str]:
        """Extract Chinese words from non-Python files"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            words = set()
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                chinese_words = self.chinese_pattern.findall(line)
                for word in chinese_words:
                    words.add(word)
                    self._add_context(word, line.strip(), str(file_path), line_num)
            
            return words
            
        except Exception as e:
            logger.error(f"Failed to extract from file {file_path}: {e}")
            return set()
    
    def _add_context(self, word: str, context: str, file_path: str, line_num: int):
        """Add context information for a word"""
        if word not in self.word_contexts:
            self.word_contexts[word] = []
        
        self.word_contexts[word].append({
            'context': context,
            'file_path': file_path,
            'line_number': line_num
        })
    
    def extract_from_directory(self, directory: Path, code_extensions: Set[str] = None) -> Dict[str, List[Dict]]:
        """Extract all Chinese words from a directory"""
        if code_extensions is None:
            code_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.hpp'}
        
        directory = Path(directory)
        all_words = {}
        
        for file_path in directory.rglob('*'):
            if file_path.is_file() and file_path.suffix in code_extensions:
                logger.info(f"Extracting words from: {file_path.relative_to(directory)}")
                
                if file_path.suffix == '.py':
                    words = self.extract_from_python_file(file_path)
                else:
                    words = self.extract_from_generic_file(file_path)
                
                for word in words:
                    if word not in all_words:
                        all_words[word] = []
                    
                    # Add contexts for this word from this file
                    if word in self.word_contexts:
                        for context_info in self.word_contexts[word]:
                            if context_info['file_path'] == str(file_path):
                                all_words[word].append(context_info)
        
        logger.info(f"Extracted {len(all_words)} unique Chinese words/phrases")
        return all_words


class TranslationMappingManager:
    """
    Manage translation mappings with persistence and Chrome integration
    """
    
    def __init__(self, cache_file: Path):
        self.cache_file = Path(cache_file)
        self.mappings: Dict[str, WordMapping] = {}
        self.load_mappings()
        
        # Initialize with comprehensive dictionary
        self._initialize_comprehensive_mappings()
    
    def _initialize_comprehensive_mappings(self):
        """Initialize with comprehensive translation mappings"""
        comprehensive_dict = {
            # Complete phrases and sentences
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
            "版本": "version",
            "依赖": "dependency",
            "包": "package",
            "构建": "build",
            "编译": "compile",
            "解释": "interpret",
            "虚拟": "virtual",
            "容器": "container",
            "云": "cloud",
            "计算": "computing",
            "前端": "frontend",
            "后端": "backend",
            "移动": "mobile",
            "网页": "web",
            "桌面": "desktop",
            "应用": "application",
            "模块": "module",
            "组件": "component",
            "库": "library",
            "框架": "framework",
            "平台": "platform",
            "引擎": "engine",
            "驱动": "driver",
            "插件": "plugin",
            "扩展": "extension",
            "主题": "theme",
            "样式": "style",
            "布局": "layout",
            "界面": "interface",
            "控件": "widget",
            "按钮": "button",
            "菜单": "menu",
            "对话框": "dialog",
            "窗口": "window",
            "面板": "panel",
            "标签": "tab",
            "列表": "list",
            "表格": "table",
            "图表": "chart",
            "图像": "image",
            "视频": "video",
            "音频": "audio",
            "媒体": "media",
            "资源": "resource",
            "资产": "asset",
            "内容": "content",
            "信息": "information",
            "消息": "message",
            "通知": "notification",
            "警告": "warning",
            "错误": "error",
            "提示": "tip",
            "帮助": "help",
            "支持": "support",
            "反馈": "feedback",
            "建议": "suggestion",
            "改进": "improvement",
            "更新": "update",
            "升级": "upgrade",
            "安装": "install",
            "卸载": "uninstall",
            "激活": "activate",
            "禁用": "disable",
            "启用": "enable",
            "开启": "enable",
            "关闭": "close",
            "打开": "open",
            "保存": "save",
            "加载": "load",
            "导入": "import",
            "导出": "export",
            "上传": "upload",
            "下载": "download",
            "同步": "sync",
            "刷新": "refresh",
            "重置": "reset",
            "清除": "clear",
            "删除": "delete",
            "添加": "add",
            "创建": "create",
            "新建": "new",
            "编辑": "edit",
            "修改": "modify",
            "更改": "change",
            "替换": "replace",
            "查找": "find",
            "搜索": "search",
            "过滤": "filter",
            "排序": "sort",
            "分组": "group",
            "分类": "category",
            "标记": "mark",
            "标签": "label",
            "注释": "comment",
            "备注": "note",
            "说明": "description",
            "详情": "details",
            "摘要": "summary",
            "概述": "overview",
            "介绍": "introduction",
            "指南": "guide",
            "教程": "tutorial",
            "示例": "example",
            "演示": "demo",
            "样本": "sample",
            "模板": "template",
            "原型": "prototype",
            "草稿": "draft",
            "版本": "version",
            "发布": "release",
            "构建": "build",
            "编译": "compile",
            "打包": "package",
            "部署": "deploy",
            "发布": "publish",
            "分享": "share",
            "协作": "collaborate",
            "团队": "team",
            "成员": "member",
            "角色": "role",
            "权限": "permission",
            "访问": "access",
            "控制": "control",
            "管理": "management",
            "监督": "supervision",
            "检查": "check",
            "验证": "verify",
            "确认": "confirm",
            "批准": "approve",
            "拒绝": "reject",
            "取消": "cancel",
            "完成": "complete",
            "成功": "success",
            "失败": "failure",
            "进行中": "in progress",
            "等待": "waiting",
            "暂停": "pause",
            "继续": "continue",
            "开始": "start",
            "结束": "end",
            "停止": "stop",
            "重启": "restart"
        }
        
        for chinese, english in comprehensive_dict.items():
            if chinese not in self.mappings:
                self.mappings[chinese] = WordMapping(
                    chinese_word=chinese,
                    english_translation=english,
                    confidence=1.0
                )
    
    def load_mappings(self):
        """Load mappings from cache file"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for item in data:
                    mapping = WordMapping(
                        chinese_word=item['chinese_word'],
                        english_translation=item['english_translation'],
                        context=item.get('context', ''),
                        file_path=item.get('file_path', ''),
                        line_number=item.get('line_number', 0),
                        confidence=item.get('confidence', 1.0),
                        last_updated=item.get('last_updated', time.time())
                    )
                    self.mappings[mapping.chinese_word] = mapping
                
                logger.info(f"Loaded {len(self.mappings)} translation mappings")
                
            except Exception as e:
                logger.error(f"Failed to load mappings: {e}")
    
    def save_mappings(self):
        """Save mappings to cache file"""
        try:
            data = []
            for mapping in self.mappings.values():
                data.append({
                    'chinese_word': mapping.chinese_word,
                    'english_translation': mapping.english_translation,
                    'context': mapping.context,
                    'file_path': mapping.file_path,
                    'line_number': mapping.line_number,
                    'confidence': mapping.confidence,
                    'last_updated': mapping.last_updated
                })
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Saved {len(self.mappings)} translation mappings")
            
        except Exception as e:
            logger.error(f"Failed to save mappings: {e}")
    
    def add_mapping(self, chinese_word: str, english_translation: str, context: str = "", 
                   file_path: str = "", line_number: int = 0, confidence: float = 1.0):
        """Add or update a translation mapping"""
        self.mappings[chinese_word] = WordMapping(
            chinese_word=chinese_word,
            english_translation=english_translation,
            context=context,
            file_path=file_path,
            line_number=line_number,
            confidence=confidence,
            last_updated=time.time()
        )
    
    def get_translation(self, chinese_word: str) -> Optional[str]:
        """Get translation for a Chinese word"""
        if chinese_word in self.mappings:
            return self.mappings[chinese_word].english_translation
        return None
    
    def get_unmapped_words(self, all_words: Dict[str, List[Dict]]) -> Set[str]:
        """Get list of words that don't have mappings yet"""
        unmapped = set()
        for word in all_words.keys():
            if word not in self.mappings:
                unmapped.add(word)
        return unmapped
    
    def export_for_chrome_translation(self, words: Set[str], output_file: Path):
        """Export unmapped words for Chrome translation"""
        # Create a simple HTML file that can be opened in Chrome
        html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Chinese Words for Translation</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .word { margin: 10px 0; padding: 10px; border: 1px solid #ddd; }
        .chinese { font-size: 18px; font-weight: bold; }
        .translation { margin-top: 5px; }
        input { width: 300px; padding: 5px; }
    </style>
    <script>
        function exportTranslations() {
            const words = [];
            const inputs = document.querySelectorAll('input[data-chinese]');
            inputs.forEach(input => {
                if (input.value.trim()) {
                    words.push({
                        chinese: input.dataset.chinese,
                        english: input.value.trim()
                    });
                }
            });
            
            const json = JSON.stringify(words, null, 2);
            const blob = new Blob([json], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'word_mappings.json';
            a.click();
            URL.revokeObjectURL(url);
        }
    </script>
</head>
<body>
    <h1>Chinese Words Translation Mapping</h1>
    <p>Translate each Chinese word/phrase to English and click Export when done.</p>
    <button onclick="exportTranslations()">Export Translations</button>
    <hr>
"""
        
        for word in sorted(words):
            html_content += f"""
    <div class="word">
        <div class="chinese">{word}</div>
        <div class="translation">
            English: <input type="text" data-chinese="{word}" placeholder="Enter English translation">
        </div>
    </div>
"""
        
        html_content += """
    <hr>
    <button onclick="exportTranslations()">Export Translations</button>
</body>
</html>
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"Exported {len(words)} words for Chrome translation to {output_file}")
    
    def import_chrome_translations(self, json_file: Path):
        """Import translations from Chrome-exported JSON"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                translations = json.load(f)
            
            imported = 0
            for item in translations:
                if 'chinese' in item and 'english' in item:
                    chinese = item['chinese']
                    english = item['english']
                    
                    if chinese and english:
                        self.add_mapping(chinese, english, confidence=0.8)  # Lower confidence for manual translation
                        imported += 1
            
            self.save_mappings()
            logger.info(f"Imported {imported} translations from Chrome")
            return imported
            
        except Exception as e:
            logger.error(f"Failed to import Chrome translations: {e}")
            return 0


class WordMappingWorkflow:
    """
    Complete word mapping workflow implementation
    """
    
    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        self.extractor = ChineseWordExtractor()
        self.mapping_manager = TranslationMappingManager(self.cache_dir / "word_mappings.json")
        
    def run_complete_workflow(self, input_dir: Path, output_dir: Path = None):
        """
        Run the complete word mapping workflow:
        1. Extract all Chinese words
        2. Identify unmapped words
        3. Export for Chrome translation
        4. Apply mappings to create translated files
        """
        input_dir = Path(input_dir)
        if output_dir:
            output_dir = Path(output_dir)
        else:
            output_dir = input_dir.parent / f"{input_dir.name}_translated"
        
        logger.info("Starting complete word mapping workflow...")
        
        # Step 1: Extract all Chinese words
        logger.info("Step 1: Extracting Chinese words from codebase...")
        all_words = self.extractor.extract_from_directory(input_dir)
        
        # Step 2: Identify unmapped words
        logger.info("Step 2: Identifying unmapped words...")
        unmapped_words = self.mapping_manager.get_unmapped_words(all_words)
        
        if unmapped_words:
            logger.info(f"Found {len(unmapped_words)} unmapped words")
            
            # Step 3: Export for Chrome translation
            chrome_file = self.cache_dir / "chrome_translation.html"
            self.mapping_manager.export_for_chrome_translation(unmapped_words, chrome_file)
            
            logger.info(f"Chrome translation file created: {chrome_file}")
            logger.info("Please open the HTML file in Chrome, translate the words, and export the JSON file.")
            logger.info("Then run import_chrome_translations() with the exported JSON file.")
            
            return {
                'status': 'needs_translation',
                'chrome_file': chrome_file,
                'unmapped_count': len(unmapped_words),
                'total_words': len(all_words)
            }
        
        else:
            logger.info("All words are already mapped. Proceeding with translation...")
            
            # Step 4: Apply mappings to create translated files
            return self.apply_mappings_to_directory(input_dir, output_dir, all_words)
    
    def apply_mappings_to_directory(self, input_dir: Path, output_dir: Path, word_contexts: Dict[str, List[Dict]]):
        """Apply translation mappings to create translated files"""
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Applying translations: {input_dir} → {output_dir}")
        
        processed = 0
        success = 0
        
        # Get all code files
        code_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.hpp'}
        
        for file_path in input_dir.rglob('*'):
            if file_path.is_file() and file_path.suffix in code_extensions:
                try:
                    # Read original content
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Apply translations
                    translated_content = self._apply_translations_to_content(content)
                    
                    # Calculate output path
                    rel_path = file_path.relative_to(input_dir)
                    output_file = output_dir / rel_path
                    
                    # Create output directory
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Write translated content
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(translated_content)
                    
                    success += 1
                    logger.info(f"Translated: {rel_path}")
                    
                except Exception as e:
                    logger.error(f"Failed to translate {file_path}: {e}")
                
                processed += 1
        
        logger.info(f"Translation complete: {success}/{processed} files translated")
        
        return {
            'status': 'completed',
            'processed': processed,
            'success': success,
            'output_dir': output_dir
        }
    
    def _apply_translations_to_content(self, content: str) -> str:
        """Apply translation mappings to file content"""
        # Sort mappings by length (longest first) to avoid partial matches
        mappings = sorted(self.mapping_manager.mappings.items(), key=lambda x: len(x[0]), reverse=True)
        
        translated_content = content
        
        for chinese_word, mapping in mappings:
            if chinese_word in translated_content:
                # Use word boundary matching to avoid partial replacements
                # But be careful with Chinese characters which don't have word boundaries
                
                # For Chinese text, we need to be more careful about replacement
                # Replace whole matches, not partial ones
                
                # Simple approach: direct replacement (could be improved with regex)
                translated_content = translated_content.replace(chinese_word, mapping.english_translation)
        
        return translated_content
    
    def import_chrome_translations(self, json_file: Path):
        """Import translations and continue workflow"""
        imported_count = self.mapping_manager.import_chrome_translations(json_file)
        logger.info(f"Successfully imported {imported_count} translations")
        return imported_count


def main():
    """Main function for testing the word mapping workflow"""
    # Example usage
    cache_dir = Path("./word_mapping_cache")
    workflow = WordMappingWorkflow(cache_dir)
    
    # Test with current directory
    current_dir = Path(".")
    result = workflow.run_complete_workflow(current_dir)
    
    print(f"Workflow result: {result}")


if __name__ == "__main__":
    main()