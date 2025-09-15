"""
ExecutionManager - Comprehensive execution tracking system with status indicators
"""
import asyncio
import subprocess
import threading
import time
import json
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
import logging

logger = logging.getLogger(__name__)

class ExecutionStatus(Enum):
    """Execution status enumeration"""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

class ExecutionResult:
    """Container for execution results"""
    def __init__(self, status: ExecutionStatus, return_code: int = 0, 
                 stdout: str = "", stderr: str = "", duration: float = 0.0,
                 error_message: str = ""):
        self.status = status
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr
        self.duration = duration
        self.error_message = error_message
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'status': self.status.value,
            'return_code': self.return_code,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'duration': self.duration,
            'error_message': self.error_message,
            'timestamp': self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ExecutionResult':
        """Create from dictionary"""
        result = cls(
            status=ExecutionStatus(data['status']),
            return_code=data.get('return_code', 0),
            stdout=data.get('stdout', ''),
            stderr=data.get('stderr', ''),
            duration=data.get('duration', 0.0),
            error_message=data.get('error_message', '')
        )
        if 'timestamp' in data:
            result.timestamp = datetime.fromisoformat(data['timestamp'])
        return result

class ExecutionTask:
    """Represents a single execution task"""
    def __init__(self, file_path: str, task_id: str = None, args: List[str] = None,
                 working_dir: str = None, timeout: float = 30.0):
        self.task_id = task_id or f"task_{int(time.time() * 1000)}"
        self.file_path = file_path
        self.args = args or []
        self.working_dir = working_dir or os.path.dirname(file_path)
        self.timeout = timeout
        self.status = ExecutionStatus.IDLE
        self.result: Optional[ExecutionResult] = None
        self.process: Optional[subprocess.Popen] = None
        self.start_time: Optional[datetime] = None
        self.callbacks: List[Callable] = []
    
    def add_callback(self, callback: Callable):
        """Add status change callback"""
        self.callbacks.append(callback)
    
    def notify_callbacks(self):
        """Notify all callbacks of status change"""
        for callback in self.callbacks:
            try:
                callback(self)
            except Exception as e:
                logger.error(f"Error in callback: {e}")

class ExecutionManager:
    """Manages script execution with status tracking and history"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.history_file = self.data_dir / "execution_history.json"
        self.active_tasks: Dict[str, ExecutionTask] = {}
        self.execution_history: List[Dict] = []
        self.max_history_size = 1000
        
        # File type handlers
        self.file_handlers = {
            '.py': self._execute_python,
            '.bat': self._execute_batch,
            '.cmd': self._execute_batch,
            '.ps1': self._execute_powershell,
            '.js': self._execute_javascript,
            '.exe': self._execute_executable,
            '.msi': self._execute_executable,
        }
        
        # Load execution history
        self._load_history()
        
        # Status change callbacks
        self.status_callbacks: List[Callable] = []
    
    def add_status_callback(self, callback: Callable):
        """Add global status change callback"""
        self.status_callbacks.append(callback)
    
    def _notify_status_change(self, task: ExecutionTask):
        """Notify all status callbacks"""
        for callback in self.status_callbacks:
            try:
                callback(task)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")
    
    def _load_history(self):
        """Load execution history from file"""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.execution_history = json.load(f)
                logger.info(f"Loaded {len(self.execution_history)} execution history entries")
        except Exception as e:
            logger.error(f"Error loading execution history: {e}")
            self.execution_history = []
    
    def _save_history(self):
        """Save execution history to file"""
        try:
            # Keep only the most recent entries
            if len(self.execution_history) > self.max_history_size:
                self.execution_history = self.execution_history[-self.max_history_size:]
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.execution_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving execution history: {e}")
    
    def get_file_type_handler(self, file_path: str) -> Optional[Callable]:
        """Get appropriate handler for file type"""
        ext = Path(file_path).suffix.lower()
        return self.file_handlers.get(ext)
    
    def execute_file(self, file_path: str, args: List[str] = None, 
                    working_dir: str = None, timeout: float = 30.0,
                    callback: Callable = None) -> str:
        """Execute a file and return task ID"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        handler = self.get_file_type_handler(file_path)
        if not handler:
            raise ValueError(f"Unsupported file type: {Path(file_path).suffix}")
        
        # Create execution task
        task = ExecutionTask(file_path, args=args, working_dir=working_dir, timeout=timeout)
        if callback:
            task.add_callback(callback)
        
        self.active_tasks[task.task_id] = task
        
        # Start execution in background thread
        thread = threading.Thread(target=self._execute_task, args=(task, handler))
        thread.daemon = True
        thread.start()
        
        return task.task_id
    
    def _execute_task(self, task: ExecutionTask, handler: Callable):
        """Execute task in background thread"""
        try:
            task.status = ExecutionStatus.RUNNING
            task.start_time = datetime.now()
            task.notify_callbacks()
            self._notify_status_change(task)
            
            # Execute using appropriate handler
            result = handler(task)
            task.result = result
            task.status = result.status
            
        except Exception as e:
            logger.error(f"Error executing task {task.task_id}: {e}")
            task.result = ExecutionResult(
                status=ExecutionStatus.ERROR,
                error_message=str(e)
            )
            task.status = ExecutionStatus.ERROR
        
        finally:
            # Calculate duration
            if task.start_time and task.result:
                task.result.duration = (datetime.now() - task.start_time).total_seconds()
            
            # Add to history
            self._add_to_history(task)
            
            # Notify callbacks
            task.notify_callbacks()
            self._notify_status_change(task)
            
            # Clean up
            if task.task_id in self.active_tasks:
                del self.active_tasks[task.task_id]
    
    def _execute_python(self, task: ExecutionTask) -> ExecutionResult:
        """Execute Python script"""
        cmd = ['python', task.file_path] + task.args
        return self._run_subprocess(cmd, task)
    
    def _execute_batch(self, task: ExecutionTask) -> ExecutionResult:
        """Execute batch/cmd script"""
        cmd = [task.file_path] + task.args
        return self._run_subprocess(cmd, task, shell=True)
    
    def _execute_powershell(self, task: ExecutionTask) -> ExecutionResult:
        """Execute PowerShell script"""
        cmd = ['powershell', '-ExecutionPolicy', 'Bypass', '-File', task.file_path] + task.args
        return self._run_subprocess(cmd, task)
    
    def _execute_javascript(self, task: ExecutionTask) -> ExecutionResult:
        """Execute JavaScript file"""
        cmd = ['node', task.file_path] + task.args
        return self._run_subprocess(cmd, task)
    
    def _execute_executable(self, task: ExecutionTask) -> ExecutionResult:
        """Execute executable file"""
        cmd = [task.file_path] + task.args
        return self._run_subprocess(cmd, task)
    
    def _run_subprocess(self, cmd: List[str], task: ExecutionTask, shell: bool = False) -> ExecutionResult:
        """Run subprocess with timeout and capture output"""
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=task.working_dir,
                shell=shell,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            task.process = process
            
            try:
                stdout, stderr = process.communicate(timeout=task.timeout)
                return_code = process.returncode
                
                if return_code == 0:
                    status = ExecutionStatus.SUCCESS
                else:
                    status = ExecutionStatus.ERROR
                
                return ExecutionResult(
                    status=status,
                    return_code=return_code,
                    stdout=stdout,
                    stderr=stderr
                )
                
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                return ExecutionResult(
                    status=ExecutionStatus.TIMEOUT,
                    return_code=-1,
                    stdout=stdout,
                    stderr=stderr,
                    error_message=f"Process timed out after {task.timeout} seconds"
                )
                
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error_message=str(e)
            )
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel running task"""
        if task_id not in self.active_tasks:
            return False
        
        task = self.active_tasks[task_id]
        if task.process and task.process.poll() is None:
            try:
                task.process.terminate()
                task.status = ExecutionStatus.CANCELLED
                task.notify_callbacks()
                self._notify_status_change(task)
                return True
            except Exception as e:
                logger.error(f"Error cancelling task {task_id}: {e}")
        
        return False
    
    def get_task_status(self, task_id: str) -> Optional[ExecutionStatus]:
        """Get current status of task"""
        if task_id in self.active_tasks:
            return self.active_tasks[task_id].status
        return None
    
    def get_task(self, task_id: str) -> Optional[ExecutionTask]:
        """Get task by ID"""
        return self.active_tasks.get(task_id)
    
    def get_active_tasks(self) -> List[ExecutionTask]:
        """Get all active tasks"""
        return list(self.active_tasks.values())
    
    def _add_to_history(self, task: ExecutionTask):
        """Add completed task to history"""
        if task.result:
            history_entry = {
                'task_id': task.task_id,
                'file_path': task.file_path,
                'args': task.args,
                'working_dir': task.working_dir,
                'result': task.result.to_dict()
            }
            self.execution_history.append(history_entry)
            self._save_history()
    
    def get_execution_history(self, file_path: str = None, limit: int = 50) -> List[Dict]:
        """Get execution history, optionally filtered by file path"""
        history = self.execution_history
        
        if file_path:
            history = [entry for entry in history if entry['file_path'] == file_path]
        
        # Return most recent entries first
        return list(reversed(history[-limit:]))
    
    def get_file_last_status(self, file_path: str) -> Optional[ExecutionStatus]:
        """Get last execution status for a file"""
        file_history = self.get_execution_history(file_path, limit=1)
        if file_history:
            return ExecutionStatus(file_history[0]['result']['status'])
        return None
    
    def clear_history(self):
        """Clear execution history"""
        self.execution_history = []
        self._save_history()
    
    def get_statistics(self) -> Dict:
        """Get execution statistics"""
        if not self.execution_history:
            return {
                'total_executions': 0,
                'success_rate': 0.0,
                'average_duration': 0.0,
                'most_executed_files': []
            }
        
        total = len(self.execution_history)
        successful = sum(1 for entry in self.execution_history 
                        if entry['result']['status'] == 'success')
        
        durations = [entry['result']['duration'] for entry in self.execution_history 
                    if entry['result']['duration'] > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        
        # Count file executions
        file_counts = {}
        for entry in self.execution_history:
            file_path = entry['file_path']
            file_counts[file_path] = file_counts.get(file_path, 0) + 1
        
        most_executed = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            'total_executions': total,
            'success_rate': (successful / total) * 100 if total > 0 else 0.0,
            'average_duration': avg_duration,
            'most_executed_files': most_executed
        }
