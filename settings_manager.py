"""
SettingsManager - Advanced settings system with transparency controls and preferences
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Tuple
import logging

logger = logging.getLogger(__name__)

class SettingsManager:
    """Manages application settings with persistence and validation"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.settings_file = self.data_dir / "settings.json"
        self.settings = self._load_settings()
        
        # Settings change callbacks
        self.change_callbacks: Dict[str, List[Callable]] = {}
        
        # Default settings schema
        self.default_settings = {
            'ui': {
                'transparency': 0.95,  # 0.0 to 1.0
                'always_on_top': True,
                'auto_hide': False,
                'auto_hide_delay': 3.0,  # seconds
                'theme': 'violet',
                'font_size': 10,
                'show_tooltips': True,
                'animation_speed': 'normal',  # slow, normal, fast
                'compact_mode': False
            },
            'execution': {
                'default_timeout': 30.0,  # seconds
                'max_concurrent_tasks': 5,
                'auto_save_output': True,
                'show_console_output': True,
                'capture_screenshots': False,
                'log_level': 'INFO',  # DEBUG, INFO, WARNING, ERROR
                'confirm_dangerous_operations': True
            },
            'editor': {
                'default_editor': 'vscode',
                'auto_detect_editors': True,
                'open_in_new_window': False,
                'remember_last_position': True,
                'syntax_highlighting': True
            },
            'file_management': {
                'show_hidden_files': False,
                'auto_backup': True,
                'backup_count': 5,
                'confirm_delete': True,
                'use_trash': True,
                'watch_file_changes': True
            },
            'notifications': {
                'show_execution_complete': True,
                'show_execution_errors': True,
                'sound_enabled': False,
                'popup_duration': 3.0,  # seconds
                'system_notifications': True
            },
            'security': {
                'require_confirmation_for_exe': True,
                'scan_for_malware': False,
                'restrict_file_types': [],
                'allowed_directories': [],
                'log_all_executions': True
            },
            'advanced': {
                'debug_mode': False,
                'performance_monitoring': False,
                'memory_limit_mb': 512,
                'cache_size_mb': 100,
                'auto_update_check': True,
                'telemetry_enabled': False
            }
        }
        
        # Merge defaults with loaded settings
        self._merge_defaults()
    
    def _load_settings(self) -> Dict:
        """Load settings from file"""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                logger.info("Settings loaded successfully")
                return settings
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
        
        return {}
    
    def _save_settings(self):
        """Save settings to file"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            logger.debug("Settings saved successfully")
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
    
    def _merge_defaults(self):
        """Merge default settings with loaded settings"""
        def merge_dict(default: Dict, current: Dict) -> Dict:
            """Recursively merge dictionaries"""
            result = default.copy()
            for key, value in current.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = merge_dict(result[key], value)
                else:
                    result[key] = value
            return result
        
        self.settings = merge_dict(self.default_settings, self.settings)
        self._save_settings()
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Get setting value using dot notation (e.g., 'ui.transparency')"""
        try:
            keys = key_path.split('.')
            value = self.settings
            
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default
            
            return value
        except Exception as e:
            logger.error(f"Error getting setting {key_path}: {e}")
            return default
    
    def set(self, key_path: str, value: Any, save: bool = True) -> bool:
        """Set setting value using dot notation"""
        try:
            keys = key_path.split('.')
            current = self.settings
            
            # Navigate to parent dictionary
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            
            # Set the value
            old_value = current.get(keys[-1])
            current[keys[-1]] = value
            
            if save:
                self._save_settings()
            
            # Notify callbacks
            self._notify_change(key_path, old_value, value)
            
            logger.debug(f"Setting {key_path} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting {key_path}: {e}")
            return False
    
    def get_category(self, category: str) -> Dict:
        """Get all settings for a category"""
        return self.settings.get(category, {})
    
    def set_category(self, category: str, settings: Dict, save: bool = True) -> bool:
        """Set all settings for a category"""
        try:
            old_settings = self.settings.get(category, {})
            self.settings[category] = settings
            
            if save:
                self._save_settings()
            
            # Notify callbacks for each changed setting
            for key, value in settings.items():
                key_path = f"{category}.{key}"
                old_value = old_settings.get(key)
                if old_value != value:
                    self._notify_change(key_path, old_value, value)
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting category {category}: {e}")
            return False
    
    def reset_to_defaults(self, category: str = None) -> bool:
        """Reset settings to defaults"""
        try:
            if category:
                if category in self.default_settings:
                    self.settings[category] = self.default_settings[category].copy()
                    logger.info(f"Reset {category} settings to defaults")
                else:
                    return False
            else:
                self.settings = self.default_settings.copy()
                logger.info("Reset all settings to defaults")
            
            self._save_settings()
            return True
            
        except Exception as e:
            logger.error(f"Error resetting settings: {e}")
            return False
    
    def add_change_callback(self, key_path: str, callback: Callable):
        """Add callback for setting changes"""
        if key_path not in self.change_callbacks:
            self.change_callbacks[key_path] = []
        self.change_callbacks[key_path].append(callback)
    
    def remove_change_callback(self, key_path: str, callback: Callable):
        """Remove callback for setting changes"""
        if key_path in self.change_callbacks:
            try:
                self.change_callbacks[key_path].remove(callback)
                if not self.change_callbacks[key_path]:
                    del self.change_callbacks[key_path]
            except ValueError:
                pass
    
    def _notify_change(self, key_path: str, old_value: Any, new_value: Any):
        """Notify callbacks of setting changes"""
        # Notify specific key callbacks
        if key_path in self.change_callbacks:
            for callback in self.change_callbacks[key_path]:
                try:
                    callback(key_path, old_value, new_value)
                except Exception as e:
                    logger.error(f"Error in settings callback: {e}")
        
        # Notify wildcard callbacks
        for callback_key in self.change_callbacks:
            if callback_key.endswith('.*') and key_path.startswith(callback_key[:-2]):
                for callback in self.change_callbacks[callback_key]:
                    try:
                        callback(key_path, old_value, new_value)
                    except Exception as e:
                        logger.error(f"Error in settings callback: {e}")
    
    def validate_setting(self, key_path: str, value: Any) -> Tuple[bool, str]:
        """Validate setting value"""
        try:
            # UI validation
            if key_path == 'ui.transparency':
                if not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0:
                    return False, "Transparency must be between 0.0 and 1.0"
            
            elif key_path == 'ui.font_size':
                if not isinstance(value, int) or not 8 <= value <= 24:
                    return False, "Font size must be between 8 and 24"
            
            elif key_path == 'ui.animation_speed':
                if value not in ['slow', 'normal', 'fast']:
                    return False, "Animation speed must be 'slow', 'normal', or 'fast'"
            
            # Execution validation
            elif key_path == 'execution.default_timeout':
                if not isinstance(value, (int, float)) or value <= 0:
                    return False, "Timeout must be a positive number"
            
            elif key_path == 'execution.max_concurrent_tasks':
                if not isinstance(value, int) or not 1 <= value <= 20:
                    return False, "Max concurrent tasks must be between 1 and 20"
            
            elif key_path == 'execution.log_level':
                if value not in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
                    return False, "Log level must be DEBUG, INFO, WARNING, or ERROR"
            
            # Advanced validation
            elif key_path == 'advanced.memory_limit_mb':
                if not isinstance(value, int) or not 64 <= value <= 4096:
                    return False, "Memory limit must be between 64 and 4096 MB"
            
            elif key_path == 'advanced.cache_size_mb':
                if not isinstance(value, int) or not 10 <= value <= 1024:
                    return False, "Cache size must be between 10 and 1024 MB"
            
            return True, ""
            
        except Exception as e:
            return False, f"Validation error: {e}"
    
    def export_settings(self, file_path: str) -> bool:
        """Export settings to file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            logger.info(f"Settings exported to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error exporting settings: {e}")
            return False
    
    def import_settings(self, file_path: str, merge: bool = True) -> bool:
        """Import settings from file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported_settings = json.load(f)
            
            if merge:
                # Merge with existing settings
                def merge_dict(current: Dict, imported: Dict) -> Dict:
                    result = current.copy()
                    for key, value in imported.items():
                        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                            result[key] = merge_dict(result[key], value)
                        else:
                            result[key] = value
                    return result
                
                self.settings = merge_dict(self.settings, imported_settings)
            else:
                # Replace all settings
                self.settings = imported_settings
            
            self._save_settings()
            logger.info(f"Settings imported from {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error importing settings: {e}")
            return False
    
    def get_setting_info(self, key_path: str) -> Optional[Dict]:
        """Get information about a setting"""
        setting_info = {
            'ui.transparency': {
                'type': 'float',
                'range': [0.0, 1.0],
                'description': 'Window transparency level',
                'default': 0.95
            },
            'ui.always_on_top': {
                'type': 'bool',
                'description': 'Keep window always on top',
                'default': True
            },
            'ui.font_size': {
                'type': 'int',
                'range': [8, 24],
                'description': 'UI font size',
                'default': 10
            },
            'execution.default_timeout': {
                'type': 'float',
                'range': [1.0, 300.0],
                'description': 'Default execution timeout in seconds',
                'default': 30.0
            },
            'execution.max_concurrent_tasks': {
                'type': 'int',
                'range': [1, 20],
                'description': 'Maximum number of concurrent tasks',
                'default': 5
            }
        }
        
        return setting_info.get(key_path)
    
    def get_all_settings(self) -> Dict:
        """Get all settings"""
        return self.settings.copy()
    
    def get_settings_summary(self) -> Dict:
        """Get summary of current settings"""
        return {
            'ui_transparency': self.get('ui.transparency'),
            'always_on_top': self.get('ui.always_on_top'),
            'default_editor': self.get('editor.default_editor'),
            'execution_timeout': self.get('execution.default_timeout'),
            'debug_mode': self.get('advanced.debug_mode'),
            'total_categories': len(self.settings),
            'settings_file': str(self.settings_file)
        }
    
    def backup_settings(self, backup_dir: str = None) -> str:
        """Create backup of current settings"""
        try:
            if not backup_dir:
                backup_dir = self.data_dir / "backups"
            
            backup_dir = Path(backup_dir)
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"settings_backup_{timestamp}.json"
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Settings backed up to {backup_file}")
            return str(backup_file)
            
        except Exception as e:
            logger.error(f"Error backing up settings: {e}")
            return ""
    
    def restore_settings(self, backup_file: str) -> bool:
        """Restore settings from backup"""
        return self.import_settings(backup_file, merge=False)
