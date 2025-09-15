"""
Configuration Manager for the Modern Taskbar system.

This module provides comprehensive configuration management with:
- Multi-format support (JSON, YAML, TOML, INI)
- Hot-reloading with change notifications
- Environment variable substitution
- Configuration validation and migration
- Backup and recovery mechanisms
- Thread-safe operations
"""

import asyncio
import json
import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Union
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import yaml
import toml
import configparser

from ..core.interfaces import ISettingsManager
from ..core.exceptions import ConfigurationError, ValidationError, FileSystemError
from .schema import ToolbarConfiguration, ConfigurationFormat, ValidationLevel
from .validator import ConfigurationValidator
from .migration import ConfigurationMigrator

logger = logging.getLogger(__name__)


class ConfigurationFileHandler(FileSystemEventHandler):
    """File system event handler for configuration hot-reloading."""
    
    def __init__(self, manager: 'ConfigurationManager'):
        self.manager = manager
        self.last_modified = {}
    
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Check if this is a configuration file we're watching
        if file_path in self.manager._watched_files:
            # Debounce rapid file changes
            now = datetime.now()
            last_mod = self.last_modified.get(file_path, datetime.min)
            
            if (now - last_mod).total_seconds() < 1.0:
                return
            
            self.last_modified[file_path] = now
            
            # Reload configuration asynchronously
            asyncio.create_task(self.manager._reload_configuration(file_path))


class ConfigurationManager(ISettingsManager):
    """
    Comprehensive configuration manager with advanced features.
    
    Provides configuration loading, validation, hot-reloading, and
    change notification capabilities with support for multiple formats.
    """
    
    def __init__(
        self,
        config_path: Optional[Path] = None,
        format: ConfigurationFormat = ConfigurationFormat.JSON,
        validation_level: ValidationLevel = ValidationLevel.STRICT,
        enable_hot_reload: bool = True,
        backup_count: int = 5
    ):
        self.config_path = config_path or Path("config/toolbar.json")
        self.format = format
        self.validation_level = validation_level
        self.enable_hot_reload = enable_hot_reload
        self.backup_count = backup_count
        
        # Internal state
        self._config: Optional[ToolbarConfiguration] = None
        self._validator = ConfigurationValidator()
        self._migrator = ConfigurationMigrator()
        self._lock = threading.RLock()
        self._change_callbacks: Dict[str, List[Callable]] = {}
        self._watched_files: set = set()
        self._file_observer: Optional[Observer] = None
        self._initialized = False
        
        # Environment variable prefix
        self.env_prefix = "TOOLBAR_"
        
        # Supported file formats
        self._format_handlers = {
            ConfigurationFormat.JSON: self._load_json,
            ConfigurationFormat.YAML: self._load_yaml,
            ConfigurationFormat.TOML: self._load_toml,
            ConfigurationFormat.INI: self._load_ini,
        }
        
        self._format_writers = {
            ConfigurationFormat.JSON: self._save_json,
            ConfigurationFormat.YAML: self._save_yaml,
            ConfigurationFormat.TOML: self._save_toml,
            ConfigurationFormat.INI: self._save_ini,
        }
    
    async def initialize(self) -> None:
        """Initialize the configuration manager."""
        if self._initialized:
            return
        
        logger.info(f"Initializing configuration manager with file: {self.config_path}")
        
        try:
            # Create config directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Load configuration
            await self.load_configuration()
            
            # Setup hot-reloading if enabled
            if self.enable_hot_reload:
                await self._setup_hot_reload()
            
            self._initialized = True
            logger.info("Configuration manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize configuration manager: {e}")
            raise ConfigurationError(f"Configuration initialization failed: {e}")
    
    async def shutdown(self) -> None:
        """Shutdown the configuration manager."""
        if not self._initialized:
            return
        
        logger.info("Shutting down configuration manager")
        
        # Stop file watching
        if self._file_observer:
            self._file_observer.stop()
            self._file_observer.join()
        
        # Save current configuration
        if self._config:
            await self.save_configuration()
        
        self._initialized = False
        logger.info("Configuration manager shutdown complete")
    
    async def load_configuration(self) -> ToolbarConfiguration:
        """
        Load configuration from file.
        
        Returns:
            Loaded configuration
            
        Raises:
            ConfigurationError: If loading fails
        """
        with self._lock:
            try:
                if not self.config_path.exists():
                    logger.info("Configuration file not found, creating default")
                    self._config = ToolbarConfiguration()
                    await self.save_configuration()
                    return self._config
                
                # Determine format from file extension if not explicitly set
                format_to_use = self._detect_format()
                
                # Load configuration data
                handler = self._format_handlers.get(format_to_use)
                if not handler:
                    raise ConfigurationError(f"Unsupported format: {format_to_use}")
                
                data = handler(self.config_path)
                
                # Apply environment variable substitution
                data = self._substitute_environment_variables(data)
                
                # Check if migration is needed
                if self._migrator.needs_migration(data):
                    logger.info("Configuration migration required")
                    data = await self._migrator.migrate(data)
                    
                    # Save migrated configuration
                    await self._save_raw_data(data)
                
                # Validate and create configuration object
                if self.validation_level != ValidationLevel.DISABLED:
                    validation_errors = self._validator.validate_raw_data(data)
                    
                    if validation_errors:
                        if self.validation_level == ValidationLevel.STRICT:
                            raise ValidationError(
                                f"Configuration validation failed: {validation_errors}"
                            )
                        else:
                            logger.warning(f"Configuration validation warnings: {validation_errors}")
                
                # Create configuration object
                if 'version' in data and data['version'] < '2.0.0':
                    # Legacy format
                    self._config = ToolbarConfiguration.from_legacy_format(data)
                else:
                    # New format
                    self._config = ToolbarConfiguration(**data)
                
                logger.info(f"Configuration loaded successfully from {self.config_path}")
                return self._config
                
            except Exception as e:
                logger.error(f"Failed to load configuration: {e}")
                
                # Try to load from backup
                backup_config = await self._load_from_backup()
                if backup_config:
                    self._config = backup_config
                    return backup_config
                
                # Fall back to default configuration
                logger.warning("Using default configuration due to load failure")
                self._config = ToolbarConfiguration()
                return self._config
    
    async def save_configuration(self) -> None:
        """
        Save current configuration to file.
        
        Raises:
            ConfigurationError: If saving fails
        """
        if not self._config:
            raise ConfigurationError("No configuration to save")
        
        with self._lock:
            try:
                # Create backup before saving
                await self._create_backup()
                
                # Validate configuration before saving
                if self.validation_level != ValidationLevel.DISABLED:
                    validation_errors = self._validator.validate_configuration(self._config)
                    
                    if validation_errors:
                        if self.validation_level == ValidationLevel.STRICT:
                            raise ValidationError(
                                f"Configuration validation failed: {validation_errors}"
                            )
                        else:
                            logger.warning(f"Configuration validation warnings: {validation_errors}")
                
                # Convert to dictionary
                data = self._config.dict()
                
                # Save using appropriate format handler
                writer = self._format_writers.get(self.format)
                if not writer:
                    raise ConfigurationError(f"Unsupported format: {self.format}")
                
                writer(self.config_path, data)
                
                logger.info(f"Configuration saved successfully to {self.config_path}")
                
            except Exception as e:
                logger.error(f"Failed to save configuration: {e}")
                raise ConfigurationError(f"Configuration save failed: {e}")
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Args:
            section: Configuration section (ignored for compatibility)
            key: Configuration key (supports dot notation)
            default: Default value if not found
            
        Returns:
            Configuration value
        """
        if not self._config:
            return default
        
        # Support both section.key and direct key access
        if section and section != key:
            full_key = f"{section}.{key}"
        else:
            full_key = key
        
        return self._config.get_nested_value(full_key, default)
    
    def set(self, section: str, key: str, value: Any) -> None:
        """
        Set configuration value using dot notation.
        
        Args:
            section: Configuration section (ignored for compatibility)
            key: Configuration key (supports dot notation)
            value: Value to set
        """
        if not self._config:
            self._config = ToolbarConfiguration()
        
        # Support both section.key and direct key access
        if section and section != key:
            full_key = f"{section}.{key}"
        else:
            full_key = key
        
        old_value = self._config.get_nested_value(full_key)
        
        try:
            self._config.set_nested_value(full_key, value)
            
            # Notify change callbacks
            self._notify_change_callbacks(section, key, value, old_value)
            
            # Auto-save if enabled
            if self._config.behavior.auto_save_interval > 0:
                asyncio.create_task(self._auto_save())
                
        except Exception as e:
            logger.error(f"Failed to set configuration value {full_key}: {e}")
            raise ConfigurationError(f"Failed to set configuration: {e}")
    
    def get_configuration(self) -> Optional[ToolbarConfiguration]:
        """
        Get the complete configuration object.
        
        Returns:
            Configuration object or None if not loaded
        """
        return self._config
    
    def validate_config(self) -> List[str]:
        """
        Validate current configuration.
        
        Returns:
            List of validation errors (empty if valid)
        """
        if not self._config:
            return ["No configuration loaded"]
        
        return self._validator.validate_configuration(self._config)
    
    def register_change_callback(
        self,
        section: str,
        callback: Callable[[str, str, Any], None]
    ) -> None:
        """
        Register callback for configuration changes.
        
        Args:
            section: Configuration section to monitor
            callback: Callback function (section, key, new_value)
        """
        with self._lock:
            if section not in self._change_callbacks:
                self._change_callbacks[section] = []
            self._change_callbacks[section].append(callback)
    
    def unregister_change_callback(
        self,
        section: str,
        callback: Callable[[str, str, Any], None]
    ) -> None:
        """
        Unregister change callback.
        
        Args:
            section: Configuration section
            callback: Callback function to remove
        """
        with self._lock:
            if section in self._change_callbacks:
                try:
                    self._change_callbacks[section].remove(callback)
                except ValueError:
                    pass
    
    async def reload_configuration(self) -> None:
        """Reload configuration from file."""
        logger.info("Reloading configuration")
        await self.load_configuration()
        
        # Notify all callbacks of reload
        for section, callbacks in self._change_callbacks.items():
            for callback in callbacks:
                try:
                    callback(section, "*", "reload")
                except Exception as e:
                    logger.error(f"Error in change callback: {e}")
    
    def get_backup_files(self) -> List[Path]:
        """
        Get list of available backup files.
        
        Returns:
            List of backup file paths
        """
        backup_dir = self.config_path.parent / "backups"
        if not backup_dir.exists():
            return []
        
        pattern = f"{self.config_path.stem}_backup_*{self.config_path.suffix}"
        return sorted(backup_dir.glob(pattern), reverse=True)
    
    async def restore_from_backup(self, backup_path: Path) -> bool:
        """
        Restore configuration from backup.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            True if restored successfully
        """
        try:
            if not backup_path.exists():
                raise FileSystemError(f"Backup file not found: {backup_path}")
            
            # Load backup
            format_to_use = self._detect_format(backup_path)
            handler = self._format_handlers.get(format_to_use)
            if not handler:
                raise ConfigurationError(f"Unsupported backup format: {format_to_use}")
            
            data = handler(backup_path)
            
            # Validate backup
            if self.validation_level != ValidationLevel.DISABLED:
                validation_errors = self._validator.validate_raw_data(data)
                if validation_errors and self.validation_level == ValidationLevel.STRICT:
                    raise ValidationError(f"Backup validation failed: {validation_errors}")
            
            # Create configuration from backup
            if 'version' in data and data['version'] < '2.0.0':
                self._config = ToolbarConfiguration.from_legacy_format(data)
            else:
                self._config = ToolbarConfiguration(**data)
            
            # Save as current configuration
            await self.save_configuration()
            
            logger.info(f"Configuration restored from backup: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore from backup {backup_path}: {e}")
            return False
    
    # Private methods
    
    def _detect_format(self, file_path: Optional[Path] = None) -> ConfigurationFormat:
        """Detect configuration format from file extension."""
        path = file_path or self.config_path
        suffix = path.suffix.lower()
        
        format_map = {
            '.json': ConfigurationFormat.JSON,
            '.yaml': ConfigurationFormat.YAML,
            '.yml': ConfigurationFormat.YAML,
            '.toml': ConfigurationFormat.TOML,
            '.ini': ConfigurationFormat.INI,
        }
        
        return format_map.get(suffix, self.format)
    
    def _load_json(self, file_path: Path) -> Dict[str, Any]:
        """Load JSON configuration file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in {file_path}: {e}")
        except Exception as e:
            raise FileSystemError(f"Failed to read {file_path}: {e}")
    
    def _load_yaml(self, file_path: Path) -> Dict[str, Any]:
        """Load YAML configuration file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in {file_path}: {e}")
        except Exception as e:
            raise FileSystemError(f"Failed to read {file_path}: {e}")
    
    def _load_toml(self, file_path: Path) -> Dict[str, Any]:
        """Load TOML configuration file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return toml.load(f)
        except toml.TomlDecodeError as e:
            raise ConfigurationError(f"Invalid TOML in {file_path}: {e}")
        except Exception as e:
            raise FileSystemError(f"Failed to read {file_path}: {e}")
    
    def _load_ini(self, file_path: Path) -> Dict[str, Any]:
        """Load INI configuration file."""
        try:
            parser = configparser.ConfigParser()
            parser.read(file_path, encoding='utf-8')
            
            # Convert to nested dictionary
            result = {}
            for section_name in parser.sections():
                result[section_name] = dict(parser[section_name])
            
            return result
        except configparser.Error as e:
            raise ConfigurationError(f"Invalid INI in {file_path}: {e}")
        except Exception as e:
            raise FileSystemError(f"Failed to read {file_path}: {e}")
    
    def _save_json(self, file_path: Path, data: Dict[str, Any]) -> None:
        """Save JSON configuration file."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str, ensure_ascii=False)
        except Exception as e:
            raise FileSystemError(f"Failed to write {file_path}: {e}")
    
    def _save_yaml(self, file_path: Path, data: Dict[str, Any]) -> None:
        """Save YAML configuration file."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            raise FileSystemError(f"Failed to write {file_path}: {e}")
    
    def _save_toml(self, file_path: Path, data: Dict[str, Any]) -> None:
        """Save TOML configuration file."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                toml.dump(data, f)
        except Exception as e:
            raise FileSystemError(f"Failed to write {file_path}: {e}")
    
    def _save_ini(self, file_path: Path, data: Dict[str, Any]) -> None:
        """Save INI configuration file."""
        try:
            parser = configparser.ConfigParser()
            
            # Convert nested dictionary to INI format
            for section_name, section_data in data.items():
                if isinstance(section_data, dict):
                    parser[section_name] = {k: str(v) for k, v in section_data.items()}
            
            with open(file_path, 'w', encoding='utf-8') as f:
                parser.write(f)
        except Exception as e:
            raise FileSystemError(f"Failed to write {file_path}: {e}")
    
    async def _save_raw_data(self, data: Dict[str, Any]) -> None:
        """Save raw data using current format."""
        writer = self._format_writers.get(self.format)
        if writer:
            writer(self.config_path, data)
    
    def _substitute_environment_variables(self, data: Any) -> Any:
        """Recursively substitute environment variables in configuration data."""
        if isinstance(data, dict):
            return {k: self._substitute_environment_variables(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._substitute_environment_variables(item) for item in data]
        elif isinstance(data, str):
            # Replace ${VAR} and $VAR patterns
            import re
            
            def replace_var(match):
                var_name = match.group(1) or match.group(2)
                # Try with prefix first, then without
                value = os.getenv(f"{self.env_prefix}{var_name}")
                if value is None:
                    value = os.getenv(var_name)
                return value if value is not None else match.group(0)
            
            # Match ${VAR} or $VAR patterns
            pattern = r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)'
            return re.sub(pattern, replace_var, data)
        else:
            return data
    
    async def _setup_hot_reload(self) -> None:
        """Setup file system watching for hot-reload."""
        try:
            self._file_observer = Observer()
            handler = ConfigurationFileHandler(self)
            
            # Watch the configuration file directory
            watch_dir = self.config_path.parent
            self._file_observer.schedule(handler, str(watch_dir), recursive=False)
            
            # Track watched files
            self._watched_files.add(self.config_path)
            
            self._file_observer.start()
            logger.info(f"Hot-reload enabled for {self.config_path}")
            
        except Exception as e:
            logger.warning(f"Failed to setup hot-reload: {e}")
    
    async def _reload_configuration(self, file_path: Path) -> None:
        """Reload configuration from file (called by file watcher)."""
        try:
            if file_path == self.config_path:
                logger.info("Configuration file changed, reloading...")
                await self.load_configuration()
                
                # Notify all callbacks
                for section, callbacks in self._change_callbacks.items():
                    for callback in callbacks:
                        try:
                            callback(section, "*", "file_changed")
                        except Exception as e:
                            logger.error(f"Error in change callback: {e}")
                            
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
    
    async def _create_backup(self) -> None:
        """Create backup of current configuration."""
        try:
            if not self.config_path.exists():
                return
            
            backup_dir = self.config_path.parent / "backups"
            backup_dir.mkdir(exist_ok=True)
            
            # Create backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{self.config_path.stem}_backup_{timestamp}{self.config_path.suffix}"
            backup_path = backup_dir / backup_name
            
            # Copy current config to backup
            shutil.copy2(self.config_path, backup_path)
            
            # Clean up old backups
            await self._cleanup_old_backups(backup_dir)
            
            logger.debug(f"Configuration backup created: {backup_path}")
            
        except Exception as e:
            logger.warning(f"Failed to create configuration backup: {e}")
    
    async def _cleanup_old_backups(self, backup_dir: Path) -> None:
        """Clean up old backup files."""
        try:
            pattern = f"{self.config_path.stem}_backup_*{self.config_path.suffix}"
            backups = sorted(backup_dir.glob(pattern), reverse=True)
            
            # Keep only the specified number of backups
            for backup in backups[self.backup_count:]:
                backup.unlink()
                logger.debug(f"Removed old backup: {backup}")
                
        except Exception as e:
            logger.warning(f"Failed to cleanup old backups: {e}")
    
    async def _load_from_backup(self) -> Optional[ToolbarConfiguration]:
        """Try to load configuration from the most recent backup."""
        try:
            backups = self.get_backup_files()
            if not backups:
                return None
            
            logger.info(f"Attempting to load from backup: {backups[0]}")
            
            # Load from most recent backup
            format_to_use = self._detect_format(backups[0])
            handler = self._format_handlers.get(format_to_use)
            if not handler:
                return None
            
            data = handler(backups[0])
            
            # Create configuration object
            if 'version' in data and data['version'] < '2.0.0':
                return ToolbarConfiguration.from_legacy_format(data)
            else:
                return ToolbarConfiguration(**data)
                
        except Exception as e:
            logger.error(f"Failed to load from backup: {e}")
            return None
    
    def _notify_change_callbacks(self, section: str, key: str, new_value: Any, old_value: Any = None) -> None:
        """Notify registered callbacks of configuration changes."""
        callbacks = self._change_callbacks.get(section, [])
        for callback in callbacks:
            try:
                callback(section, key, new_value)
            except Exception as e:
                logger.error(f"Error in change callback for {section}.{key}: {e}")
    
    async def _auto_save(self) -> None:
        """Auto-save configuration after a delay."""
        if not self._config or self._config.behavior.auto_save_interval <= 0:
            return
        
        # Wait for the auto-save interval
        await asyncio.sleep(self._config.behavior.auto_save_interval)
        
        try:
            await self.save_configuration()
        except Exception as e:
            logger.error(f"Auto-save failed: {e}")

