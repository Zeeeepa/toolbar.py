"""
Configuration and Validation System for the Modern Taskbar.

This module provides a comprehensive configuration management system with:
- Schema-based validation using Pydantic models
- Configuration versioning and automatic migration
- Environment-specific configuration support
- Hot-reloading capabilities with change notifications
- Hierarchical configuration with inheritance
- Secure configuration handling with encryption support

The configuration system supports multiple formats (JSON, YAML, TOML, INI)
and provides a unified interface for accessing and managing all application
settings with full validation and type safety.
"""

from .schema import *
from .manager import ConfigurationManager
from .validator import ConfigurationValidator
from .migration import ConfigurationMigrator

__version__ = "2.0.0"
__author__ = "Modern Taskbar Team"

# Main configuration components
__all__ = [
    # Schema models
    'ToolbarConfiguration',
    'AppearanceSettings',
    'BehaviorSettings', 
    'ExecutionSettings',
    'EditorSettings',
    'PluginSettings',
    'IntegrationSettings',
    'MonitoringSettings',
    
    # Manager and utilities
    'ConfigurationManager',
    'ConfigurationValidator',
    'ConfigurationMigrator',
    
    # Enums and constants
    'ConfigurationFormat',
    'ValidationLevel',
    'MigrationStrategy',
]

