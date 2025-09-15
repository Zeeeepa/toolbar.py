"""
Enhanced service classes for the Modern Taskbar application
"""
import os
import subprocess
import platform
import shutil
import configparser
from pathlib import Path
from datetime import datetime
from collections import defaultdict, deque
from enum import Enum
import uuid
import logging

logger = logging.getLogger(__name__)

# Editor Types
class EditorType(Enum):
    VSCODE = "code"
    NOTEPADPP = "notepad++"
    SUBLIME = "subl"
    ATOM = "atom"
    VIM = "vim"
    NANO = "nano"
    GEDIT = "gedit"

# Execution Status Enum
class ExecutionStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"

class SettingsManager:
    """Comprehensive settings management"""
    def __init__(self, config_file="taskbar_settings.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.default_settings = {
            'appearance': {
                'transparency': '95',
                'theme': 'violet',
                'show_tooltips': 'true',
                'animation_enabled': 'true'
            },
            'behavior': {
                'auto_start': 'false',
                'stay_on_top': 'true',
                'minimize_to_tray': 'false',
                'confirm_exit': 'true'
            },
            'execution': {
                'show_output': 'true',
                'timeout_seconds': '300',
                'max_concurrent': '5',
                'auto_close_success': 'false'
            },
            'editors': {
                'default_editor': 'vscode',
                'editor_args': ''
            },
            'monitoring': {
                'track_performance': 'true',
                'history_limit': '1000',
                'show_notifications': 'true'
            }
        }
        self.load_settings()
    
    def load_settings(self):
        """Load settings from file"""
        try:
            if os.path.exists(self.config_file):
                self.config.read(self.config_file)
            else:
                self._create_default_config()
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            self._create_default_config()
    
    def _create_default_config(self):
        """Create default configuration"""
        for section, settings in self.default_settings.items():
            self.config[section] = settings
        self.save_settings()
    
    def save_settings(self):
        """Save settings to file"""
        try:
            with open(self.config_file, 'w') as f:
                self.config.write(f)
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
    
    def get(self, section, key, fallback=None):
        """Get a setting value"""
        try:
            return self.config.get(section, key, fallback=fallback)
        except:
            return fallback
    
    def getint(self, section, key, fallback=0):
        """Get an integer setting value"""
        try:
            return self.config.getint(section, key, fallback=fallback)
        except:
            return fallback
    
    def getboolean(self, section, key, fallback=False):
        """Get a boolean setting value"""
        try:
            return self.config.getboolean(section, key, fallback=fallback)
        except:
            return fallback
    
    def set(self, section, key, value):
        """Set a setting value"""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = str(value)
    
    def get_all_settings(self):
        """Get all settings as a dictionary"""
        settings = {}
        for section in self.config.sections():
            settings[section] = dict(self.config[section])
        return settings

class EnhancedFileManager:
    """Enhanced file management operations"""
    def __init__(self):
        self.supported_editors = self._detect_available_editors()
        self.default_editor = self._get_default_editor()
    
    def _detect_available_editors(self):
        """Detect available editors on the system"""
        editors = {}
        editor_commands = {
            EditorType.VSCODE: ['code', 'code.exe'],
            EditorType.NOTEPADPP: ['notepad++', 'notepad++.exe'],
            EditorType.SUBLIME: ['subl', 'sublime_text.exe'],
            EditorType.ATOM: ['atom', 'atom.exe'],
            EditorType.VIM: ['vim', 'vim.exe'],
            EditorType.NANO: ['nano'],
            EditorType.GEDIT: ['gedit']
        }
        
        for editor_type, commands in editor_commands.items():
            for cmd in commands:
                if shutil.which(cmd):
                    editors[editor_type] = cmd
                    break
        
        return editors
    
    def _get_default_editor(self):
        """Get the default editor"""
        priority_order = [EditorType.VSCODE, EditorType.NOTEPADPP, EditorType.SUBLIME, EditorType.ATOM]
        for editor in priority_order:
            if editor in self.supported_editors:
                return editor
        return list(self.supported_editors.keys())[0] if self.supported_editors else None
    
    def open_in_editor(self, file_path, editor_type=None):
        """Open file in specified editor"""
        if not editor_type:
            editor_type = self.default_editor
        
        if editor_type not in self.supported_editors:
            raise ValueError(f"Editor {editor_type} not available")
        
        command = self.supported_editors[editor_type]
        subprocess.Popen([command, file_path])
    
    def open_folder(self, folder_path):
        """Open folder in system file manager"""
        try:
            if platform.system() == "Windows":
                os.startfile(folder_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", folder_path])
            else:  # Linux
                subprocess.Popen(["xdg-open", folder_path])
        except Exception as e:
            logger.error(f"Error opening folder: {e}")
            raise
    
    def open_terminal(self, folder_path):
        """Open terminal in specified folder"""
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["cmd", "/c", "start", "cmd", "/k", f"cd /d {folder_path}"])
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", "-a", "Terminal", folder_path])
            else:  # Linux
                subprocess.Popen(["gnome-terminal", "--working-directory", folder_path])
        except Exception as e:
            logger.error(f"Error opening terminal: {e}")
            raise
    
    def rename_file(self, old_path, new_name):
        """Rename a file safely"""
        try:
            old_path = Path(old_path)
            new_path = old_path.parent / new_name
            
            if new_path.exists():
                raise FileExistsError(f"File {new_name} already exists")
            
            old_path.rename(new_path)
            return str(new_path)
        except Exception as e:
            logger.error(f"Error renaming file: {e}")
            raise
    
    def get_file_properties(self, file_path):
        """Get detailed file properties"""
        try:
            path = Path(file_path)
            stat = path.stat()
            
            return {
                'name': path.name,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'created': datetime.fromtimestamp(stat.st_ctime),
                'is_executable': os.access(file_path, os.X_OK),
                'extension': path.suffix,
                'parent': str(path.parent)
            }
        except Exception as e:
            logger.error(f"Error getting file properties: {e}")
            return None

class ExecutionStatusManager:
    """Manages execution status tracking and monitoring"""
    def __init__(self):
        self.execution_history = deque(maxlen=1000)
        self.active_executions = {}
        self.status_callbacks = defaultdict(list)
        self.performance_stats = defaultdict(list)
    
    def start_execution(self, script_id, script_path, command):
        """Start tracking an execution"""
        execution_data = {
            'id': str(uuid.uuid4()),
            'script_id': script_id,
            'script_path': script_path,
            'command': command,
            'start_time': datetime.now(),
            'status': ExecutionStatus.RUNNING,
            'process': None,
            'output': [],
            'error_output': []
        }
        self.active_executions[execution_data['id']] = execution_data
        self._notify_status_change(script_id, ExecutionStatus.RUNNING, execution_data)
        return execution_data['id']
    
    def update_execution_status(self, execution_id, status, output=None, error=None):
        """Update execution status"""
        if execution_id in self.active_executions:
            execution_data = self.active_executions[execution_id]
            execution_data['status'] = status
            
            if output:
                execution_data['output'].append(output)
            if error:
                execution_data['error_output'].append(error)
            
            if status in [ExecutionStatus.SUCCESS, ExecutionStatus.ERROR, ExecutionStatus.CANCELLED]:
                execution_data['end_time'] = datetime.now()
                execution_data['duration'] = (execution_data['end_time'] - execution_data['start_time']).total_seconds()
                self.execution_history.append(execution_data.copy())
                self._update_performance_stats(execution_data)
                del self.active_executions[execution_id]
            
            self._notify_status_change(execution_data['script_id'], status, execution_data)
    
    def _notify_status_change(self, script_id, status, execution_data):
        """Notify registered callbacks of status changes"""
        for callback in self.status_callbacks[script_id]:
            try:
                callback(status, execution_data)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")
    
    def _update_performance_stats(self, execution_data):
        """Update performance statistics"""
        script_path = execution_data['script_path']
        duration = execution_data.get('duration', 0)
        self.performance_stats[script_path].append({
            'duration': duration,
            'timestamp': execution_data['end_time'],
            'status': execution_data['status']
        })
    
    def register_status_callback(self, script_id, callback):
        """Register a callback for status changes"""
        self.status_callbacks[script_id].append(callback)
    
    def get_execution_history(self, script_path=None, limit=50):
        """Get execution history"""
        history = list(self.execution_history)
        if script_path:
            history = [h for h in history if h['script_path'] == script_path]
        return history[-limit:]
    
    def get_performance_stats(self, script_path):
        """Get performance statistics for a script"""
        stats = self.performance_stats.get(script_path, [])
        if not stats:
            return None
        
        durations = [s['duration'] for s in stats]
        success_count = len([s for s in stats if s['status'] == ExecutionStatus.SUCCESS])
        
        return {
            'total_executions': len(stats),
            'success_rate': success_count / len(stats) * 100,
            'avg_duration': sum(durations) / len(durations),
            'min_duration': min(durations),
            'max_duration': max(durations),
            'last_execution': stats[-1]['timestamp']
        }

class AdvancedExecutionEngine:
    """Advanced execution engine with support for multiple file types and modes"""
    def __init__(self, status_manager, settings_manager):
        self.status_manager = status_manager
        self.settings_manager = settings_manager
        self.supported_extensions = {
            '.py': self._execute_python,
            '.js': self._execute_javascript,
            '.ts': self._execute_typescript,
            '.bat': self._execute_batch,
            '.cmd': self._execute_batch,
            '.ps1': self._execute_powershell,
            '.sh': self._execute_shell,
            '.rb': self._execute_ruby,
            '.php': self._execute_php,
            '.go': self._execute_go,
            '.rs': self._execute_rust,
            '.java': self._execute_java,
            '.cpp': self._execute_cpp,
            '.c': self._execute_c,
            '.exe': self._execute_executable,
            '.msi': self._execute_installer
        }
    
    def execute_file(self, file_path, args=None, elevated=False, background=True):
        """Execute a file with advanced options"""
        try:
            path = Path(file_path)
            extension = path.suffix.lower()
            
            if extension not in self.supported_extensions:
                return self._execute_generic(file_path, args, elevated, background)
            
            return self.supported_extensions[extension](file_path, args, elevated, background)
        
        except Exception as e:
            logger.error(f"Error executing file {file_path}: {e}")
            raise
    
    def _execute_python(self, file_path, args=None, elevated=False, background=True):
        """Execute Python files"""
        cmd = ['python', file_path]
        if args:
            cmd.extend(args)
        return self._run_command(cmd, elevated, background)
    
    def _execute_javascript(self, file_path, args=None, elevated=False, background=True):
        """Execute JavaScript files"""
        cmd = ['node', file_path]
        if args:
            cmd.extend(args)
        return self._run_command(cmd, elevated, background)
    
    def _execute_typescript(self, file_path, args=None, elevated=False, background=True):
        """Execute TypeScript files"""
        cmd = ['ts-node', file_path]
        if args:
            cmd.extend(args)
        return self._run_command(cmd, elevated, background)
    
    def _execute_batch(self, file_path, args=None, elevated=False, background=True):
        """Execute batch files"""
        cmd = [file_path]
        if args:
            cmd.extend(args)
        return self._run_command(cmd, elevated, background, shell=True)
    
    def _execute_powershell(self, file_path, args=None, elevated=False, background=True):
        """Execute PowerShell files"""
        cmd = ['powershell', '-ExecutionPolicy', 'Bypass', '-File', file_path]
        if args:
            cmd.extend(args)
        return self._run_command(cmd, elevated, background)
    
    def _execute_shell(self, file_path, args=None, elevated=False, background=True):
        """Execute shell scripts"""
        cmd = ['bash', file_path]
        if args:
            cmd.extend(args)
        return self._run_command(cmd, elevated, background)
    
    def _execute_ruby(self, file_path, args=None, elevated=False, background=True):
        """Execute Ruby files"""
        cmd = ['ruby', file_path]
        if args:
            cmd.extend(args)
        return self._run_command(cmd, elevated, background)
    
    def _execute_php(self, file_path, args=None, elevated=False, background=True):
        """Execute PHP files"""
        cmd = ['php', file_path]
        if args:
            cmd.extend(args)
        return self._run_command(cmd, elevated, background)
    
    def _execute_go(self, file_path, args=None, elevated=False, background=True):
        """Execute Go files"""
        cmd = ['go', 'run', file_path]
        if args:
            cmd.extend(args)
        return self._run_command(cmd, elevated, background)
    
    def _execute_rust(self, file_path, args=None, elevated=False, background=True):
        """Execute Rust files"""
        # Compile and run Rust files
        path = Path(file_path)
        exe_path = path.with_suffix('.exe' if platform.system() == 'Windows' else '')
        
        # Compile first
        compile_cmd = ['rustc', file_path, '-o', str(exe_path)]
        compile_process = subprocess.run(compile_cmd, capture_output=True, text=True)
        
        if compile_process.returncode != 0:
            raise RuntimeError(f"Rust compilation failed: {compile_process.stderr}")
        
        # Run the compiled executable
        cmd = [str(exe_path)]
        if args:
            cmd.extend(args)
        return self._run_command(cmd, elevated, background)
    
    def _execute_java(self, file_path, args=None, elevated=False, background=True):
        """Execute Java files"""
        path = Path(file_path)
        class_name = path.stem
        
        # Compile first
        compile_cmd = ['javac', file_path]
        compile_process = subprocess.run(compile_cmd, capture_output=True, text=True)
        
        if compile_process.returncode != 0:
            raise RuntimeError(f"Java compilation failed: {compile_process.stderr}")
        
        # Run the compiled class
        cmd = ['java', '-cp', str(path.parent), class_name]
        if args:
            cmd.extend(args)
        return self._run_command(cmd, elevated, background)
    
    def _execute_cpp(self, file_path, args=None, elevated=False, background=True):
        """Execute C++ files"""
        path = Path(file_path)
        exe_path = path.with_suffix('.exe' if platform.system() == 'Windows' else '')
        
        # Compile first
        compile_cmd = ['g++', file_path, '-o', str(exe_path)]
        compile_process = subprocess.run(compile_cmd, capture_output=True, text=True)
        
        if compile_process.returncode != 0:
            raise RuntimeError(f"C++ compilation failed: {compile_process.stderr}")
        
        # Run the compiled executable
        cmd = [str(exe_path)]
        if args:
            cmd.extend(args)
        return self._run_command(cmd, elevated, background)
    
    def _execute_c(self, file_path, args=None, elevated=False, background=True):
        """Execute C files"""
        path = Path(file_path)
        exe_path = path.with_suffix('.exe' if platform.system() == 'Windows' else '')
        
        # Compile first
        compile_cmd = ['gcc', file_path, '-o', str(exe_path)]
        compile_process = subprocess.run(compile_cmd, capture_output=True, text=True)
        
        if compile_process.returncode != 0:
            raise RuntimeError(f"C compilation failed: {compile_process.stderr}")
        
        # Run the compiled executable
        cmd = [str(exe_path)]
        if args:
            cmd.extend(args)
        return self._run_command(cmd, elevated, background)
    
    def _execute_executable(self, file_path, args=None, elevated=False, background=True):
        """Execute executable files"""
        cmd = [file_path]
        if args:
            cmd.extend(args)
        return self._run_command(cmd, elevated, background)
    
    def _execute_installer(self, file_path, args=None, elevated=False, background=True):
        """Execute installer files"""
        cmd = [file_path]
        if args:
            cmd.extend(args)
        return self._run_command(cmd, elevated=True, background=background)  # Installers usually need elevation
    
    def _execute_generic(self, file_path, args=None, elevated=False, background=True):
        """Execute generic files using system default"""
        if platform.system() == "Windows":
            cmd = ['start', '', file_path]
            if args:
                cmd.extend(args)
            return self._run_command(cmd, elevated, background, shell=True)
        else:
            cmd = ['xdg-open', file_path]
            return self._run_command(cmd, elevated, background)
    
    def _run_command(self, cmd, elevated=False, background=True, shell=False):
        """Run a command with optional elevation and background execution"""
        try:
            if elevated and platform.system() == "Windows":
                # Use runas for elevation on Windows
                cmd = ['runas', '/user:Administrator'] + cmd
            
            if background:
                process = subprocess.Popen(
                    cmd,
                    shell=shell,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                return process
            else:
                result = subprocess.run(
                    cmd,
                    shell=shell,
                    capture_output=True,
                    text=True,
                    timeout=self.settings_manager.getint('execution', 'timeout_seconds', 300)
                )
                return result
        
        except Exception as e:
            logger.error(f"Error running command {cmd}: {e}")
            raise
