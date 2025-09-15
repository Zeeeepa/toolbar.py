"""
Configuration Validator for the Modern Taskbar system.

This module provides comprehensive configuration validation with:
- Schema validation using Pydantic models
- Custom validation rules and constraints
- Cross-field validation and business logic
- Performance validation and resource checks
- Security validation for safe configurations
- Detailed error reporting with suggestions
"""

import re
import logging
from typing import Any, Dict, List, Optional, Union, Tuple
from pathlib import Path
from pydantic import ValidationError as PydanticValidationError

from ..core.exceptions import ValidationError, ConfigurationError
from .schema import ToolbarConfiguration, EditorType, LogLevel, ThemeMode

logger = logging.getLogger(__name__)


class ValidationRule:
    """Base class for custom validation rules."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    def validate(self, config: ToolbarConfiguration) -> List[str]:
        """
        Validate configuration against this rule.
        
        Args:
            config: Configuration to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        raise NotImplementedError


class PathValidationRule(ValidationRule):
    """Validates file and directory paths in configuration."""
    
    def __init__(self):
        super().__init__(
            "path_validation",
            "Validates that configured paths exist and are accessible"
        )
    
    def validate(self, config: ToolbarConfiguration) -> List[str]:
        """Validate path configurations."""
        errors = []
        
        # Validate log file path
        if config.monitoring.log_file:
            log_dir = config.monitoring.log_file.parent
            if not log_dir.exists():
                try:
                    log_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    errors.append(f"Cannot create log directory {log_dir}: {e}")
        
        # Validate plugin directories
        for plugin_dir in config.plugins.plugin_directories:
            if not plugin_dir.exists():
                errors.append(f"Plugin directory does not exist: {plugin_dir}")
            elif not plugin_dir.is_dir():
                errors.append(f"Plugin path is not a directory: {plugin_dir}")
        
        # Validate editor paths
        for editor, path in config.editors.editor_paths.items():
            if not path.exists():
                errors.append(f"Editor executable not found: {editor} -> {path}")
            elif not path.is_file():
                errors.append(f"Editor path is not a file: {editor} -> {path}")
        
        # Validate working directory
        if config.execution.working_directory:
            if not config.execution.working_directory.exists():
                errors.append(f"Working directory does not exist: {config.execution.working_directory}")
            elif not config.execution.working_directory.is_dir():
                errors.append(f"Working directory is not a directory: {config.execution.working_directory}")
        
        return errors


class SecurityValidationRule(ValidationRule):
    """Validates security-related configuration settings."""
    
    def __init__(self):
        super().__init__(
            "security_validation",
            "Validates security settings for safe operation"
        )
    
    def validate(self, config: ToolbarConfiguration) -> List[str]:
        """Validate security configurations."""
        errors = []
        
        # Check for dangerous file types
        dangerous_extensions = ['.exe', '.bat', '.cmd', '.com', '.scr', '.vbs', '.ps1']
        allowed_dangerous = set(config.security.allowed_file_types) & set(dangerous_extensions)
        
        if allowed_dangerous and not config.security.sandbox_execution:
            errors.append(
                f"Dangerous file types allowed without sandboxing: {allowed_dangerous}. "
                "Consider enabling sandbox_execution for security."
            )
        
        # Validate API security
        if config.integrations.api_enabled:
            if not config.integrations.api_key:
                errors.append("API is enabled but no API key is configured")
            elif len(config.integrations.api_key) < 16:
                errors.append("API key should be at least 16 characters long")
        
        # Check webhook URLs
        for webhook_url in config.integrations.webhook_urls:
            if not webhook_url.startswith(('http://', 'https://')):
                errors.append(f"Invalid webhook URL format: {webhook_url}")
            elif webhook_url.startswith('http://') and 'localhost' not in webhook_url:
                errors.append(f"Insecure webhook URL (HTTP): {webhook_url}")
        
        # Validate blocked commands
        if not config.security.blocked_commands:
            errors.append("No blocked commands configured - consider blocking dangerous commands")
        
        return errors


class PerformanceValidationRule(ValidationRule):
    """Validates performance-related configuration settings."""
    
    def __init__(self):
        super().__init__(
            "performance_validation",
            "Validates performance settings for optimal operation"
        )
    
    def validate(self, config: ToolbarConfiguration) -> List[str]:
        """Validate performance configurations."""
        errors = []
        warnings = []
        
        # Check execution limits
        if config.execution.max_concurrent > 10:
            warnings.append(
                f"High concurrent execution limit ({config.execution.max_concurrent}) "
                "may impact system performance"
            )
        
        if config.execution.timeout_seconds > 1800:  # 30 minutes
            warnings.append(
                f"Very long execution timeout ({config.execution.timeout_seconds}s) "
                "may cause resource issues"
            )
        
        # Check plugin limits
        if config.plugins.max_memory_mb > 500:
            warnings.append(
                f"High plugin memory limit ({config.plugins.max_memory_mb}MB) "
                "may impact system performance"
            )
        
        # Check monitoring intervals
        if config.monitoring.metrics_interval < 10:
            errors.append("Metrics interval too low - minimum 10 seconds recommended")
        
        if config.monitoring.health_check_interval < 5:
            errors.append("Health check interval too low - minimum 5 seconds recommended")
        
        # Check log file size
        if config.monitoring.log_max_size_mb > 100:
            warnings.append(
                f"Large log file size limit ({config.monitoring.log_max_size_mb}MB) "
                "may consume significant disk space"
            )
        
        # Check backup count
        if config.behavior.backup_count > 20:
            warnings.append(
                f"High backup count ({config.behavior.backup_count}) "
                "may consume significant disk space"
            )
        
        # Return errors (warnings are logged but not returned as errors)
        for warning in warnings:
            logger.warning(f"Performance validation warning: {warning}")
        
        return errors


class BusinessLogicValidationRule(ValidationRule):
    """Validates business logic and cross-field constraints."""
    
    def __init__(self):
        super().__init__(
            "business_logic_validation",
            "Validates business logic and cross-field constraints"
        )
    
    def validate(self, config: ToolbarConfiguration) -> List[str]:
        """Validate business logic constraints."""
        errors = []
        
        # Validate retry configuration
        if config.execution.retry_attempts > 0:
            if config.execution.retry_delay <= 0:
                errors.append("Retry delay must be positive when retry attempts > 0")
            
            if config.execution.retry_attempts * config.execution.retry_delay > config.execution.timeout_seconds:
                errors.append(
                    "Total retry time exceeds execution timeout - "
                    "reduce retry attempts or increase timeout"
                )
        
        # Validate plugin configuration
        if config.plugins.enabled:
            if not config.plugins.plugin_directories:
                errors.append("Plugin system enabled but no plugin directories configured")
            
            if config.plugins.plugin_timeout > config.execution.timeout_seconds:
                errors.append("Plugin timeout should not exceed execution timeout")
        
        # Validate monitoring configuration
        if config.monitoring.metrics_enabled:
            if config.monitoring.metrics_interval > config.monitoring.health_check_interval * 10:
                errors.append(
                    "Metrics interval is much larger than health check interval - "
                    "consider adjusting for better monitoring"
                )
        
        # Validate API configuration
        if config.integrations.api_enabled:
            if config.integrations.api_port == 80 or config.integrations.api_port == 443:
                errors.append("API port conflicts with standard HTTP/HTTPS ports")
        
        # Validate editor configuration
        if config.editors.default_editor == EditorType.CUSTOM:
            if not config.editors.editor_paths.get('custom'):
                errors.append("Custom editor selected but no custom editor path configured")
        
        # Validate appearance settings
        if config.appearance.transparency < 50:
            errors.append("Very low transparency may make the application hard to see")
        
        if config.appearance.font_size < 8:
            errors.append("Font size too small - may be hard to read")
        
        return errors


class ConfigurationValidator:
    """
    Comprehensive configuration validator with multiple validation rules.
    
    Provides schema validation, custom rule validation, and detailed
    error reporting with suggestions for fixing issues.
    """
    
    def __init__(self):
        self.rules: List[ValidationRule] = [
            PathValidationRule(),
            SecurityValidationRule(),
            PerformanceValidationRule(),
            BusinessLogicValidationRule(),
        ]
        
        # Validation statistics
        self.validation_count = 0
        self.error_count = 0
        self.warning_count = 0
    
    def validate_configuration(self, config: ToolbarConfiguration) -> List[str]:
        """
        Validate a complete configuration object.
        
        Args:
            config: Configuration to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        self.validation_count += 1
        all_errors = []
        
        try:
            # Run all validation rules
            for rule in self.rules:
                try:
                    errors = rule.validate(config)
                    if errors:
                        all_errors.extend([f"[{rule.name}] {error}" for error in errors])
                except Exception as e:
                    logger.error(f"Error in validation rule {rule.name}: {e}")
                    all_errors.append(f"[{rule.name}] Validation rule failed: {e}")
            
            # Update statistics
            if all_errors:
                self.error_count += 1
            
            return all_errors
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            self.error_count += 1
            return [f"Validation system error: {e}"]
    
    def validate_raw_data(self, data: Dict[str, Any]) -> List[str]:
        """
        Validate raw configuration data before creating objects.
        
        Args:
            data: Raw configuration dictionary
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        try:
            # Try to create configuration object for validation
            if 'version' in data and data['version'] < '2.0.0':
                config = ToolbarConfiguration.from_legacy_format(data)
            else:
                config = ToolbarConfiguration(**data)
            
            # Validate the created configuration
            return self.validate_configuration(config)
            
        except PydanticValidationError as e:
            # Extract Pydantic validation errors
            for error in e.errors():
                field_path = '.'.join(str(loc) for loc in error['loc'])
                error_msg = error['msg']
                errors.append(f"Field '{field_path}': {error_msg}")
            
            self.error_count += 1
            return errors
            
        except Exception as e:
            logger.error(f"Raw data validation failed: {e}")
            self.error_count += 1
            return [f"Data validation error: {e}"]
    
    def validate_partial_update(
        self,
        config: ToolbarConfiguration,
        updates: Dict[str, Any]
    ) -> List[str]:
        """
        Validate a partial configuration update.
        
        Args:
            config: Current configuration
            updates: Proposed updates
            
        Returns:
            List of validation errors (empty if valid)
        """
        try:
            # Create a copy of the configuration
            config_dict = config.dict()
            
            # Apply updates
            self._apply_nested_updates(config_dict, updates)
            
            # Validate the updated configuration
            return self.validate_raw_data(config_dict)
            
        except Exception as e:
            logger.error(f"Partial update validation failed: {e}")
            return [f"Update validation error: {e}"]
    
    def get_validation_suggestions(self, errors: List[str]) -> List[str]:
        """
        Get suggestions for fixing validation errors.
        
        Args:
            errors: List of validation errors
            
        Returns:
            List of suggestions
        """
        suggestions = []
        
        for error in errors:
            if "does not exist" in error.lower():
                suggestions.append("Check file and directory paths in configuration")
            elif "api key" in error.lower():
                suggestions.append("Generate a strong API key for secure access")
            elif "timeout" in error.lower():
                suggestions.append("Adjust timeout values for better performance")
            elif "memory" in error.lower():
                suggestions.append("Review memory limits to prevent resource issues")
            elif "plugin" in error.lower():
                suggestions.append("Check plugin configuration and directories")
            elif "editor" in error.lower():
                suggestions.append("Verify editor paths and installation")
            elif "security" in error.lower():
                suggestions.append("Review security settings for safe operation")
            elif "performance" in error.lower():
                suggestions.append("Optimize performance settings for your system")
        
        # Add general suggestions
        if errors:
            suggestions.extend([
                "Check the configuration documentation for valid values",
                "Use the configuration schema for reference",
                "Consider using default values for problematic settings"
            ])
        
        return list(set(suggestions))  # Remove duplicates
    
    def add_custom_rule(self, rule: ValidationRule) -> None:
        """
        Add a custom validation rule.
        
        Args:
            rule: Custom validation rule to add
        """
        self.rules.append(rule)
        logger.info(f"Added custom validation rule: {rule.name}")
    
    def remove_rule(self, rule_name: str) -> bool:
        """
        Remove a validation rule by name.
        
        Args:
            rule_name: Name of the rule to remove
            
        Returns:
            True if rule was removed
        """
        for i, rule in enumerate(self.rules):
            if rule.name == rule_name:
                del self.rules[i]
                logger.info(f"Removed validation rule: {rule_name}")
                return True
        return False
    
    def get_validation_statistics(self) -> Dict[str, int]:
        """
        Get validation statistics.
        
        Returns:
            Dictionary with validation statistics
        """
        return {
            'total_validations': self.validation_count,
            'total_errors': self.error_count,
            'total_warnings': self.warning_count,
            'success_rate': (
                (self.validation_count - self.error_count) / max(self.validation_count, 1)
            ) * 100
        }
    
    def reset_statistics(self) -> None:
        """Reset validation statistics."""
        self.validation_count = 0
        self.error_count = 0
        self.warning_count = 0
    
    # Private methods
    
    def _apply_nested_updates(self, target: Dict[str, Any], updates: Dict[str, Any]) -> None:
        """Apply nested updates to a dictionary."""
        for key, value in updates.items():
            if '.' in key:
                # Handle nested keys like 'appearance.transparency'
                parts = key.split('.')
                current = target
                
                # Navigate to parent
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                
                # Set final value
                current[parts[-1]] = value
            else:
                # Direct key
                if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                    # Merge dictionaries
                    self._apply_nested_updates(target[key], value)
                else:
                    # Replace value
                    target[key] = value

