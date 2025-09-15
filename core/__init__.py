"""
Core architecture module for the Modern Taskbar Enhanced Edition.

This module provides the foundational architecture components including:
- Abstract base classes and interfaces
- Dependency injection container
- Service registry and lifecycle management
- Plugin architecture framework
- Event system foundation

The core module establishes the architectural patterns and contracts
that all other modules must follow to ensure consistency, testability,
and maintainability across the entire system.
"""

from .interfaces import *
from .abstractions import *
from .container import Container
from .registry import ServiceRegistry
from .exceptions import *

__version__ = "2.0.0"
__author__ = "Modern Taskbar Team"

# Core architectural components
__all__ = [
    # Interfaces
    'IExecutionEngine',
    'IFileManager', 
    'ISettingsManager',
    'IUIComponent',
    'IPlugin',
    'IEventBus',
    'IHealthCheck',
    
    # Abstract base classes
    'BaseService',
    'BasePlugin',
    'BaseUIComponent',
    'BaseExecutionEngine',
    
    # Container and registry
    'Container',
    'ServiceRegistry',
    
    # Exceptions
    'ToolbarException',
    'ConfigurationError',
    'ExecutionError',
    'PluginError',
    'IntegrationError',
]

