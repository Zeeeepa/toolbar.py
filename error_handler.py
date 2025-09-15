"""
ErrorHandler - Comprehensive error handling and recovery system
"""
import logging
import traceback
import sys
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Union
from enum import Enum
import threading
import queue

class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """Error categories for better classification"""
    SYSTEM = "system"
    USER_INPUT = "user_input"
    FILE_OPERATION = "file_operation"
    EXECUTION = "execution"
    NETWORK = "network"
    CONFIGURATION = "configuration"
    UI = "ui"
    INTEGRATION = "integration"

class ErrorContext:
    """Container for error context information"""
    def __init__(self, operation: str, component: str, user_action: str = None,
                 file_path: str = None, additional_data: Dict = None):
        self.operation = operation
        self.component = component
        self.user_action = user_action
        self.file_path = file_path
        self.additional_data = additional_data or {}
        self.timestamp = datetime.now()
        self.thread_id = threading.get_ident()
        self.process_id = os.getpid()

class ErrorRecord:
    """Detailed error record for logging and analysis"""
    def __init__(self, exception: Exception, context: ErrorContext,
                 severity: ErrorSeverity, category: ErrorCategory):
        self.exception = exception
        self.context = context
        self.severity = severity
        self.category = category
        self.error_id = f"{int(datetime.now().timestamp() * 1000)}_{threading.get_ident()}"
        self.traceback = traceback.format_exc()
        self.resolved = False
        self.resolution_notes = ""
        
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'error_id': self.error_id,
            'exception_type': type(self.exception).__name__,
            'exception_message': str(self.exception),
            'severity': self.severity.value,
            'category': self.category.value,
            'operation': self.context.operation,
            'component': self.context.component,
            'user_action': self.context.user_action,
            'file_path': self.context.file_path,
            'additional_data': self.context.additional_data,
            'timestamp': self.context.timestamp.isoformat(),
            'thread_id': self.context.thread_id,
            'process_id': self.context.process_id,
            'traceback': self.traceback,
            'resolved': self.resolved,
            'resolution_notes': self.resolution_notes
        }

class RecoveryStrategy:
    """Base class for error recovery strategies"""
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    def can_handle(self, error_record: ErrorRecord) -> bool:
        """Check if this strategy can handle the error"""
        raise NotImplementedError
    
    def recover(self, error_record: ErrorRecord) -> bool:
        """Attempt to recover from the error"""
        raise NotImplementedError

class FileOperationRecovery(RecoveryStrategy):
    """Recovery strategy for file operation errors"""
    def __init__(self):
        super().__init__("FileOperationRecovery", "Handles file operation failures")
    
    def can_handle(self, error_record: ErrorRecord) -> bool:
        return error_record.category == ErrorCategory.FILE_OPERATION
    
    def recover(self, error_record: ErrorRecord) -> bool:
        try:
            if isinstance(error_record.exception, FileNotFoundError):
                # Try to locate the file in common locations
                if error_record.context.file_path:
                    return self._try_locate_file(error_record.context.file_path)
            elif isinstance(error_record.exception, PermissionError):
                # Log permission issue and suggest solutions
                logging.warning(f"Permission denied for {error_record.context.file_path}")
                return False
            return False
        except Exception as e:
            logging.error(f"Recovery failed: {e}")
            return False
    
    def _try_locate_file(self, file_path: str) -> bool:
        """Try to locate a missing file"""
        try:
            path = Path(file_path)
            # Check if file exists in parent directories
            for parent in path.parents:
                potential_path = parent / path.name
                if potential_path.exists():
                    logging.info(f"Found file at alternative location: {potential_path}")
                    return True
            return False
        except Exception:
            return False

class ConfigurationRecovery(RecoveryStrategy):
    """Recovery strategy for configuration errors"""
    def __init__(self):
        super().__init__("ConfigurationRecovery", "Handles configuration failures")
    
    def can_handle(self, error_record: ErrorRecord) -> bool:
        return error_record.category == ErrorCategory.CONFIGURATION
    
    def recover(self, error_record: ErrorRecord) -> bool:
        try:
            if "json" in str(error_record.exception).lower():
                # Try to recover corrupted JSON configuration
                return self._recover_json_config(error_record.context.file_path)
            return False
        except Exception:
            return False
    
    def _recover_json_config(self, config_path: str) -> bool:
        """Try to recover corrupted JSON configuration"""
        try:
            if not config_path:
                return False
            
            path = Path(config_path)
            backup_path = path.with_suffix(f"{path.suffix}.backup")
            
            if backup_path.exists():
                # Restore from backup
                path.write_text(backup_path.read_text())
                logging.info(f"Restored configuration from backup: {backup_path}")
                return True
            else:
                # Create minimal valid configuration
                minimal_config = {"version": "1.0", "created": datetime.now().isoformat()}
                path.write_text(json.dumps(minimal_config, indent=2))
                logging.info(f"Created minimal configuration: {path}")
                return True
        except Exception as e:
            logging.error(f"Failed to recover JSON config: {e}")
            return False

class ErrorHandler:
    """Comprehensive error handling and recovery system"""
    
    def __init__(self, data_dir: str = "data", log_dir: str = "logs"):
        self.data_dir = Path(data_dir)
        self.log_dir = Path(log_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.log_dir.mkdir(exist_ok=True)
        
        # Error storage
        self.error_log_file = self.log_dir / "error_log.json"
        self.error_records: List[ErrorRecord] = []
        self.max_error_records = 1000
        
        # Recovery strategies
        self.recovery_strategies: List[RecoveryStrategy] = [
            FileOperationRecovery(),
            ConfigurationRecovery()
        ]
        
        # Error callbacks
        self.error_callbacks: Dict[ErrorCategory, List[Callable]] = {}
        
        # Async error processing
        self.error_queue = queue.Queue()
        self.processing_thread = threading.Thread(target=self._process_errors, daemon=True)
        self.processing_thread.start()
        
        # Load existing error records
        self._load_error_records()
        
        # Setup logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup comprehensive logging"""
        try:
            # Create formatters
            detailed_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
            
            simple_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            
            # File handlers
            error_file_handler = logging.FileHandler(self.log_dir / "errors.log")
            error_file_handler.setLevel(logging.ERROR)
            error_file_handler.setFormatter(detailed_formatter)
            
            debug_file_handler = logging.FileHandler(self.log_dir / "debug.log")
            debug_file_handler.setLevel(logging.DEBUG)
            debug_file_handler.setFormatter(detailed_formatter)
            
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(simple_formatter)
            
            # Configure root logger
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.DEBUG)
            root_logger.addHandler(error_file_handler)
            root_logger.addHandler(debug_file_handler)
            root_logger.addHandler(console_handler)
            
        except Exception as e:
            print(f"Failed to setup logging: {e}")
    
    def handle_error(self, exception: Exception, context: ErrorContext,
                    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                    category: ErrorCategory = ErrorCategory.SYSTEM,
                    attempt_recovery: bool = True) -> Optional[ErrorRecord]:
        """Handle an error with comprehensive logging and recovery"""
        try:
            # Create error record
            error_record = ErrorRecord(exception, context, severity, category)
            
            # Log the error
            self._log_error(error_record)
            
            # Add to queue for async processing
            self.error_queue.put((error_record, attempt_recovery))
            
            return error_record
            
        except Exception as e:
            # Fallback logging if error handling fails
            logging.critical(f"Error handler failed: {e}")
            logging.critical(f"Original error: {exception}")
            return None
    
    def _log_error(self, error_record: ErrorRecord):
        """Log error with appropriate level"""
        message = f"[{error_record.error_id}] {error_record.context.operation} failed: {error_record.exception}"
        
        if error_record.severity == ErrorSeverity.CRITICAL:
            logging.critical(message)
        elif error_record.severity == ErrorSeverity.HIGH:
            logging.error(message)
        elif error_record.severity == ErrorSeverity.MEDIUM:
            logging.warning(message)
        else:
            logging.info(message)
        
        # Log additional context
        if error_record.context.additional_data:
            logging.debug(f"[{error_record.error_id}] Context: {error_record.context.additional_data}")
    
    def _process_errors(self):
        """Process errors asynchronously"""
        while True:
            try:
                error_record, attempt_recovery = self.error_queue.get(timeout=1.0)
                
                # Store error record
                self.error_records.append(error_record)
                self._save_error_records()
                
                # Attempt recovery if requested
                if attempt_recovery:
                    self._attempt_recovery(error_record)
                
                # Notify callbacks
                self._notify_error_callbacks(error_record)
                
                self.error_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"Error processing failed: {e}")
    
    def _attempt_recovery(self, error_record: ErrorRecord):
        """Attempt to recover from error using available strategies"""
        try:
            for strategy in self.recovery_strategies:
                if strategy.can_handle(error_record):
                    logging.info(f"Attempting recovery with {strategy.name}")
                    if strategy.recover(error_record):
                        error_record.resolved = True
                        error_record.resolution_notes = f"Recovered using {strategy.name}"
                        logging.info(f"Successfully recovered from error {error_record.error_id}")
                        return True
            
            logging.warning(f"No recovery strategy available for error {error_record.error_id}")
            return False
            
        except Exception as e:
            logging.error(f"Recovery attempt failed: {e}")
            return False
    
    def _notify_error_callbacks(self, error_record: ErrorRecord):
        """Notify registered error callbacks"""
        try:
            callbacks = self.error_callbacks.get(error_record.category, [])
            for callback in callbacks:
                try:
                    callback(error_record)
                except Exception as e:
                    logging.error(f"Error callback failed: {e}")
        except Exception as e:
            logging.error(f"Failed to notify error callbacks: {e}")
    
    def add_error_callback(self, category: ErrorCategory, callback: Callable):
        """Add error callback for specific category"""
        if category not in self.error_callbacks:
            self.error_callbacks[category] = []
        self.error_callbacks[category].append(callback)
    
    def add_recovery_strategy(self, strategy: RecoveryStrategy):
        """Add custom recovery strategy"""
        self.recovery_strategies.append(strategy)
    
    def _load_error_records(self):
        """Load error records from file"""
        try:
            if self.error_log_file.exists():
                with open(self.error_log_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Note: We don't reconstruct full ErrorRecord objects from JSON
                    # as they contain exception objects that can't be serialized
                    logging.info(f"Loaded {len(data)} error records from log")
        except Exception as e:
            logging.error(f"Failed to load error records: {e}")
    
    def _save_error_records(self):
        """Save error records to file"""
        try:
            # Keep only recent records
            if len(self.error_records) > self.max_error_records:
                self.error_records = self.error_records[-self.max_error_records:]
            
            # Convert to serializable format
            serializable_records = [record.to_dict() for record in self.error_records[-100:]]
            
            with open(self.error_log_file, 'w', encoding='utf-8') as f:
                json.dump(serializable_records, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logging.error(f"Failed to save error records: {e}")
    
    def get_error_statistics(self) -> Dict:
        """Get error statistics"""
        try:
            if not self.error_records:
                return {
                    'total_errors': 0,
                    'by_severity': {},
                    'by_category': {},
                    'recovery_rate': 0.0,
                    'recent_errors': 0
                }
            
            total = len(self.error_records)
            resolved = sum(1 for record in self.error_records if record.resolved)
            
            # Count by severity
            by_severity = {}
            for severity in ErrorSeverity:
                count = sum(1 for record in self.error_records if record.severity == severity)
                by_severity[severity.value] = count
            
            # Count by category
            by_category = {}
            for category in ErrorCategory:
                count = sum(1 for record in self.error_records if record.category == category)
                by_category[category.value] = count
            
            # Recent errors (last hour)
            recent_threshold = datetime.now().timestamp() - 3600
            recent_errors = sum(1 for record in self.error_records 
                              if record.context.timestamp.timestamp() > recent_threshold)
            
            return {
                'total_errors': total,
                'by_severity': by_severity,
                'by_category': by_category,
                'recovery_rate': (resolved / total) * 100 if total > 0 else 0.0,
                'recent_errors': recent_errors
            }
            
        except Exception as e:
            logging.error(f"Failed to get error statistics: {e}")
            return {}
    
    def get_recent_errors(self, limit: int = 50) -> List[Dict]:
        """Get recent error records"""
        try:
            recent_records = self.error_records[-limit:] if self.error_records else []
            return [record.to_dict() for record in reversed(recent_records)]
        except Exception as e:
            logging.error(f"Failed to get recent errors: {e}")
            return []
    
    def clear_resolved_errors(self):
        """Clear resolved error records"""
        try:
            original_count = len(self.error_records)
            self.error_records = [record for record in self.error_records if not record.resolved]
            cleared_count = original_count - len(self.error_records)
            logging.info(f"Cleared {cleared_count} resolved error records")
            self._save_error_records()
        except Exception as e:
            logging.error(f"Failed to clear resolved errors: {e}")
    
    def export_error_report(self, file_path: str) -> bool:
        """Export comprehensive error report"""
        try:
            report = {
                'generated_at': datetime.now().isoformat(),
                'statistics': self.get_error_statistics(),
                'recent_errors': self.get_recent_errors(100),
                'recovery_strategies': [
                    {'name': strategy.name, 'description': strategy.description}
                    for strategy in self.recovery_strategies
                ]
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logging.info(f"Error report exported to {file_path}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to export error report: {e}")
            return False

# Decorator for automatic error handling
def handle_errors(severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 category: ErrorCategory = ErrorCategory.SYSTEM,
                 operation: str = None):
    """Decorator for automatic error handling"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Get error handler instance (assumes it's available globally)
                error_handler = getattr(wrapper, '_error_handler', None)
                if error_handler:
                    context = ErrorContext(
                        operation=operation or func.__name__,
                        component=func.__module__,
                        additional_data={'args': str(args), 'kwargs': str(kwargs)}
                    )
                    error_handler.handle_error(e, context, severity, category)
                raise
        return wrapper
    return decorator
