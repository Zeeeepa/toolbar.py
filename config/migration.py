"""
Configuration Migration System for the Modern Toolbar.

This module provides automatic configuration migration between versions with:
- Version detection and migration path planning
- Backward compatibility preservation
- Data transformation and schema updates
- Rollback capabilities for failed migrations
- Migration validation and verification
- Detailed migration logging and reporting
"""

import logging
from typing import Any, Dict, List, Optional, Callable, Tuple
from datetime import datetime
from pathlib import Path
import json
import shutil
from packaging import version

from ..core.exceptions import ConfigurationError, ValidationError

logger = logging.getLogger(__name__)


class MigrationStep:
    """Represents a single migration step between versions."""
    
    def __init__(
        self,
        from_version: str,
        to_version: str,
        description: str,
        migration_func: Callable[[Dict[str, Any]], Dict[str, Any]],
        rollback_func: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    ):
        self.from_version = from_version
        self.to_version = to_version
        self.description = description
        self.migration_func = migration_func
        self.rollback_func = rollback_func
    
    def apply(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply the migration step."""
        try:
            logger.info(f"Applying migration: {self.from_version} -> {self.to_version}")
            logger.info(f"Migration description: {self.description}")
            
            result = self.migration_func(data)
            
            # Ensure version is updated
            result['version'] = self.to_version
            result['migrated_at'] = datetime.now().isoformat()
            
            return result
            
        except Exception as e:
            logger.error(f"Migration step failed: {e}")
            raise ConfigurationError(f"Migration {self.from_version} -> {self.to_version} failed: {e}")
    
    def rollback(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Rollback the migration step."""
        if not self.rollback_func:
            raise ConfigurationError(f"No rollback available for migration {self.from_version} -> {self.to_version}")
        
        try:
            logger.info(f"Rolling back migration: {self.to_version} -> {self.from_version}")
            
            result = self.rollback_func(data)
            result['version'] = self.from_version
            
            return result
            
        except Exception as e:
            logger.error(f"Migration rollback failed: {e}")
            raise ConfigurationError(f"Rollback {self.to_version} -> {self.from_version} failed: {e}")


class ConfigurationMigrator:
    """
    Handles configuration migration between different versions.
    
    Provides automatic migration with rollback capabilities and
    comprehensive validation of migration results.
    """
    
    def __init__(self):
        self.migration_steps: List[MigrationStep] = []
        self.current_version = "2.0.0"
        
        # Register built-in migration steps
        self._register_builtin_migrations()
    
    def needs_migration(self, data: Dict[str, Any]) -> bool:
        """
        Check if configuration data needs migration.
        
        Args:
            data: Configuration data to check
            
        Returns:
            True if migration is needed
        """
        config_version = data.get('version', '1.0.0')
        
        try:
            return version.parse(config_version) < version.parse(self.current_version)
        except Exception as e:
            logger.warning(f"Invalid version format '{config_version}': {e}")
            return True  # Assume migration needed for invalid versions
    
    async def migrate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate configuration data to the current version.
        
        Args:
            data: Configuration data to migrate
            
        Returns:
            Migrated configuration data
            
        Raises:
            ConfigurationError: If migration fails
        """
        config_version = data.get('version', '1.0.0')
        
        if not self.needs_migration(data):
            logger.info(f"Configuration version {config_version} is current, no migration needed")
            return data
        
        logger.info(f"Starting migration from version {config_version} to {self.current_version}")
        
        # Create backup before migration
        backup_data = data.copy()
        
        try:
            # Find migration path
            migration_path = self._find_migration_path(config_version, self.current_version)
            
            if not migration_path:
                raise ConfigurationError(
                    f"No migration path found from {config_version} to {self.current_version}"
                )
            
            # Apply migration steps
            current_data = data
            applied_steps = []
            
            for step in migration_path:
                try:
                    current_data = step.apply(current_data)
                    applied_steps.append(step)
                    logger.info(f"Successfully applied migration step: {step.from_version} -> {step.to_version}")
                    
                except Exception as e:
                    logger.error(f"Migration step failed: {e}")
                    
                    # Attempt rollback of applied steps
                    await self._rollback_steps(current_data, applied_steps)
                    
                    raise ConfigurationError(f"Migration failed at step {step.from_version} -> {step.to_version}: {e}")
            
            # Validate migrated configuration
            validation_errors = self._validate_migrated_data(current_data)
            if validation_errors:
                logger.error(f"Migration validation failed: {validation_errors}")
                
                # Attempt rollback
                await self._rollback_steps(current_data, applied_steps)
                
                raise ValidationError(f"Migrated configuration is invalid: {validation_errors}")
            
            logger.info(f"Migration completed successfully: {config_version} -> {self.current_version}")
            
            # Add migration metadata
            current_data['migration_history'] = current_data.get('migration_history', [])
            current_data['migration_history'].append({
                'from_version': config_version,
                'to_version': self.current_version,
                'migrated_at': datetime.now().isoformat(),
                'steps_applied': len(applied_steps)
            })
            
            return current_data
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
    
    def register_migration_step(self, step: MigrationStep) -> None:
        """
        Register a custom migration step.
        
        Args:
            step: Migration step to register
        """
        self.migration_steps.append(step)
        logger.info(f"Registered migration step: {step.from_version} -> {step.to_version}")
    
    def get_migration_history(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get migration history from configuration data.
        
        Args:
            data: Configuration data
            
        Returns:
            List of migration history entries
        """
        return data.get('migration_history', [])
    
    def get_available_versions(self) -> List[str]:
        """
        Get list of available versions in migration chain.
        
        Returns:
            List of version strings
        """
        versions = set()
        for step in self.migration_steps:
            versions.add(step.from_version)
            versions.add(step.to_version)
        
        return sorted(versions, key=lambda v: version.parse(v))
    
    # Private methods
    
    def _register_builtin_migrations(self) -> None:
        """Register built-in migration steps."""
        
        # Migration from 1.0.0 to 1.1.0
        self.register_migration_step(MigrationStep(
            from_version="1.0.0",
            to_version="1.1.0",
            description="Add execution settings and editor configuration",
            migration_func=self._migrate_1_0_to_1_1,
            rollback_func=self._rollback_1_1_to_1_0
        ))
        
        # Migration from 1.1.0 to 2.0.0
        self.register_migration_step(MigrationStep(
            from_version="1.1.0",
            to_version="2.0.0",
            description="Restructure configuration with new schema and add advanced features",
            migration_func=self._migrate_1_1_to_2_0,
            rollback_func=self._rollback_2_0_to_1_1
        ))
        
        # Direct migration from 1.0.0 to 2.0.0 for efficiency
        self.register_migration_step(MigrationStep(
            from_version="1.0.0",
            to_version="2.0.0",
            description="Direct migration to new schema with all features",
            migration_func=self._migrate_1_0_to_2_0,
            rollback_func=self._rollback_2_0_to_1_0
        ))
    
    def _migrate_1_0_to_1_1(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate from version 1.0.0 to 1.1.0."""
        migrated = data.copy()
        
        # Add execution settings
        if 'execution' not in migrated:
            migrated['execution'] = {
                'timeout_seconds': migrated.get('timeout_seconds', 300),
                'max_concurrent': migrated.get('max_concurrent', 5),
                'show_output': True,
                'capture_output': True
            }
        
        # Add editor settings
        if 'editors' not in migrated:
            migrated['editors'] = {
                'default_editor': migrated.get('default_editor', 'vscode'),
                'auto_detect_editors': True,
                'editor_paths': {},
                'editor_arguments': {}
            }
        
        # Remove old top-level settings
        for old_key in ['timeout_seconds', 'max_concurrent', 'default_editor']:
            migrated.pop(old_key, None)
        
        return migrated
    
    def _rollback_1_1_to_1_0(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Rollback from version 1.1.0 to 1.0.0."""
        rolled_back = data.copy()
        
        # Extract settings back to top level
        if 'execution' in rolled_back:
            execution = rolled_back.pop('execution')
            rolled_back['timeout_seconds'] = execution.get('timeout_seconds', 300)
            rolled_back['max_concurrent'] = execution.get('max_concurrent', 5)
        
        if 'editors' in rolled_back:
            editors = rolled_back.pop('editors')
            rolled_back['default_editor'] = editors.get('default_editor', 'vscode')
        
        return rolled_back
    
    def _migrate_1_1_to_2_0(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate from version 1.1.0 to 2.0.0."""
        migrated = {
            'version': '2.0.0',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # Migrate appearance settings
        migrated['appearance'] = {
            'theme_mode': 'dark',
            'transparency': data.get('transparency', 95),
            'show_tooltips': data.get('show_tooltips', True),
            'animation_enabled': data.get('animation_enabled', True),
            'font_family': 'Segoe UI',
            'font_size': 9,
            'icon_size': 16,
            'always_on_top': data.get('always_on_top', True)
        }
        
        # Migrate behavior settings
        migrated['behavior'] = {
            'auto_start': data.get('auto_start', False),
            'minimize_to_tray': True,
            'confirm_exit': data.get('confirm_exit', True),
            'auto_save_interval': 30,
            'backup_count': 5,
            'check_updates': True,
            'update_channel': 'stable'
        }
        
        # Migrate execution settings
        execution_data = data.get('execution', {})
        migrated['execution'] = {
            'show_output': execution_data.get('show_output', True),
            'timeout_seconds': execution_data.get('timeout_seconds', 300),
            'max_concurrent': execution_data.get('max_concurrent', 5),
            'capture_output': execution_data.get('capture_output', True),
            'retry_attempts': 0,
            'retry_delay': 1.0,
            'kill_on_timeout': True,
            'preserve_output': True,
            'environment_variables': {}
        }
        
        # Migrate editor settings
        editors_data = data.get('editors', {})
        migrated['editors'] = {
            'default_editor': editors_data.get('default_editor', 'vscode'),
            'editor_paths': editors_data.get('editor_paths', {}),
            'editor_arguments': editors_data.get('editor_arguments', {}),
            'auto_detect_editors': editors_data.get('auto_detect_editors', True),
            'open_in_new_window': False,
            'jump_to_line': True,
            'file_associations': {}
        }
        
        # Add new sections with defaults
        migrated['plugins'] = {
            'enabled': True,
            'plugin_directories': ['plugins'],
            'auto_load': True,
            'sandbox_enabled': True,
            'plugin_timeout': 30,
            'max_memory_mb': 100,
            'enable_hot_reload': False,
            'allowed_plugins': None,
            'blocked_plugins': []
        }
        
        migrated['integrations'] = {
            'api_enabled': False,
            'api_port': 8080,
            'api_host': 'localhost',
            'webhook_enabled': False,
            'webhook_urls': [],
            'webhook_events': ['execution_complete', 'error'],
            'external_tools': {},
            'oauth_providers': {}
        }
        
        migrated['monitoring'] = {
            'log_level': 'INFO',
            'log_file': 'logs/toolbar.log',
            'log_rotation': True,
            'log_max_size_mb': 10,
            'log_backup_count': 5,
            'metrics_enabled': True,
            'metrics_interval': 60,
            'health_check_interval': 30,
            'performance_monitoring': True,
            'memory_threshold_mb': 500,
            'cpu_threshold_percent': 80
        }
        
        migrated['security'] = {
            'encrypt_config': False,
            'require_admin': False,
            'allowed_file_types': ['.py', '.js', '.ts', '.bat', '.sh', '.ps1'],
            'blocked_commands': [],
            'sandbox_execution': False,
            'network_access': True,
            'file_system_access': True
        }
        
        # Preserve legacy data
        migrated['scripts'] = data.get('scripts', [])
        migrated['trays'] = data.get('trays', [])
        migrated['custom'] = data.get('custom', {})
        
        return migrated
    
    def _rollback_2_0_to_1_1(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Rollback from version 2.0.0 to 1.1.0."""
        rolled_back = {
            'version': '1.1.0',
            'scripts': data.get('scripts', []),
            'trays': data.get('trays', [])
        }
        
        # Extract appearance settings
        appearance = data.get('appearance', {})
        rolled_back['transparency'] = appearance.get('transparency', 95)
        rolled_back['show_tooltips'] = appearance.get('show_tooltips', True)
        rolled_back['animation_enabled'] = appearance.get('animation_enabled', True)
        rolled_back['always_on_top'] = appearance.get('always_on_top', True)
        
        # Extract behavior settings
        behavior = data.get('behavior', {})
        rolled_back['auto_start'] = behavior.get('auto_start', False)
        rolled_back['confirm_exit'] = behavior.get('confirm_exit', True)
        
        # Extract execution settings
        execution = data.get('execution', {})
        rolled_back['execution'] = {
            'show_output': execution.get('show_output', True),
            'timeout_seconds': execution.get('timeout_seconds', 300),
            'max_concurrent': execution.get('max_concurrent', 5),
            'capture_output': execution.get('capture_output', True)
        }
        
        # Extract editor settings
        editors = data.get('editors', {})
        rolled_back['editors'] = {
            'default_editor': editors.get('default_editor', 'vscode'),
            'auto_detect_editors': editors.get('auto_detect_editors', True),
            'editor_paths': editors.get('editor_paths', {}),
            'editor_arguments': editors.get('editor_arguments', {})
        }
        
        return rolled_back
    
    def _migrate_1_0_to_2_0(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Direct migration from version 1.0.0 to 2.0.0."""
        # First migrate to 1.1.0
        intermediate = self._migrate_1_0_to_1_1(data)
        
        # Then migrate to 2.0.0
        return self._migrate_1_1_to_2_0(intermediate)
    
    def _rollback_2_0_to_1_0(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Direct rollback from version 2.0.0 to 1.0.0."""
        # First rollback to 1.1.0
        intermediate = self._rollback_2_0_to_1_1(data)
        
        # Then rollback to 1.0.0
        return self._rollback_1_1_to_1_0(intermediate)
    
    def _find_migration_path(self, from_version: str, to_version: str) -> Optional[List[MigrationStep]]:
        """
        Find the optimal migration path between versions.
        
        Args:
            from_version: Starting version
            to_version: Target version
            
        Returns:
            List of migration steps or None if no path found
        """
        # Try direct migration first
        for step in self.migration_steps:
            if step.from_version == from_version and step.to_version == to_version:
                return [step]
        
        # Use breadth-first search to find shortest path
        from collections import deque
        
        queue = deque([(from_version, [])])
        visited = {from_version}
        
        while queue:
            current_version, path = queue.popleft()
            
            if current_version == to_version:
                return path
            
            # Find all possible next steps
            for step in self.migration_steps:
                if step.from_version == current_version and step.to_version not in visited:
                    visited.add(step.to_version)
                    queue.append((step.to_version, path + [step]))
        
        return None  # No path found
    
    async def _rollback_steps(self, data: Dict[str, Any], applied_steps: List[MigrationStep]) -> None:
        """Rollback applied migration steps in reverse order."""
        for step in reversed(applied_steps):
            try:
                if step.rollback_func:
                    data = step.rollback(data)
                    logger.info(f"Rolled back migration step: {step.to_version} -> {step.from_version}")
                else:
                    logger.warning(f"No rollback available for step: {step.from_version} -> {step.to_version}")
            except Exception as e:
                logger.error(f"Rollback failed for step {step.to_version} -> {step.from_version}: {e}")
    
    def _validate_migrated_data(self, data: Dict[str, Any]) -> List[str]:
        """
        Validate migrated configuration data.
        
        Args:
            data: Migrated configuration data
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Basic structure validation
        required_fields = ['version', 'appearance', 'behavior', 'execution', 'editors']
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        # Version validation
        if 'version' in data:
            try:
                parsed_version = version.parse(data['version'])
                current_parsed = version.parse(self.current_version)
                
                if parsed_version > current_parsed:
                    errors.append(f"Migrated version {data['version']} is newer than current {self.current_version}")
            except Exception as e:
                errors.append(f"Invalid version format: {data['version']}")
        
        # Type validation for critical fields
        if 'appearance' in data and not isinstance(data['appearance'], dict):
            errors.append("Appearance section must be a dictionary")
        
        if 'scripts' in data and not isinstance(data['scripts'], list):
            errors.append("Scripts section must be a list")
        
        if 'trays' in data and not isinstance(data['trays'], list):
            errors.append("Trays section must be a list")
        
        return errors

