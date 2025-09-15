"""
Core interfaces and contracts for the Modern Taskbar system.

This module defines the fundamental interfaces that establish contracts
between different components of the system. These interfaces enable
dependency injection, testing, and plugin development by providing
clear boundaries and expectations.

All interfaces follow the Interface Segregation Principle (ISP) to
ensure that implementing classes are not forced to depend on methods
they don't use.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Callable, AsyncIterator
from enum import Enum
from datetime import datetime
from pathlib import Path
import asyncio


class ExecutionStatus(Enum):
    """Enumeration of possible execution states."""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class HealthStatus(Enum):
    """Enumeration of health check states."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class IExecutionEngine(ABC):
    """
    Interface for script execution engines.
    
    Defines the contract for executing various types of scripts and files
    with proper status tracking, output capture, and error handling.
    """
    
    @abstractmethod
    async def execute_file(
        self, 
        file_path: Path, 
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None
    ) -> 'ExecutionResult':
        """
        Execute a file asynchronously.
        
        Args:
            file_path: Path to the file to execute
            args: Optional command line arguments
            env: Optional environment variables
            timeout: Optional timeout in seconds
            
        Returns:
            ExecutionResult containing status, output, and metadata
            
        Raises:
            ExecutionError: If execution fails
            TimeoutError: If execution times out
        """
        pass
    
    @abstractmethod
    def can_execute(self, file_path: Path) -> bool:
        """
        Check if this engine can execute the given file.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if this engine can handle the file type
        """
        pass
    
    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """
        Get list of file extensions this engine supports.
        
        Returns:
            List of supported file extensions (e.g., ['.py', '.js'])
        """
        pass


class IFileManager(ABC):
    """
    Interface for file management operations.
    
    Provides abstraction for file system operations, editor integration,
    and file metadata management.
    """
    
    @abstractmethod
    async def get_file_properties(self, file_path: Path) -> Dict[str, Any]:
        """
        Get comprehensive file properties.
        
        Args:
            file_path: Path to analyze
            
        Returns:
            Dictionary containing file metadata
        """
        pass
    
    @abstractmethod
    async def open_in_editor(
        self, 
        file_path: Path, 
        editor: Optional[str] = None,
        line_number: Optional[int] = None
    ) -> bool:
        """
        Open file in specified editor.
        
        Args:
            file_path: File to open
            editor: Editor to use (None for default)
            line_number: Optional line to jump to
            
        Returns:
            True if successfully opened
        """
        pass
    
    @abstractmethod
    def get_available_editors(self) -> List[Dict[str, str]]:
        """
        Get list of available editors on the system.
        
        Returns:
            List of editor information dictionaries
        """
        pass


class ISettingsManager(ABC):
    """
    Interface for configuration and settings management.
    
    Provides abstraction for configuration storage, validation,
    and change notification.
    """
    
    @abstractmethod
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        pass
    
    @abstractmethod
    def set(self, section: str, key: str, value: Any) -> None:
        """Set configuration value."""
        pass
    
    @abstractmethod
    def validate_config(self) -> List[str]:
        """
        Validate current configuration.
        
        Returns:
            List of validation errors (empty if valid)
        """
        pass
    
    @abstractmethod
    def register_change_callback(
        self, 
        section: str, 
        callback: Callable[[str, str, Any], None]
    ) -> None:
        """Register callback for configuration changes."""
        pass


class IUIComponent(ABC):
    """
    Interface for UI components.
    
    Defines the contract for UI components with lifecycle management,
    event handling, and state management.
    """
    
    @abstractmethod
    def initialize(self, parent: Any, **kwargs) -> None:
        """Initialize the UI component."""
        pass
    
    @abstractmethod
    def update_state(self, state: Dict[str, Any]) -> None:
        """Update component state."""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Clean up resources when component is destroyed."""
        pass
    
    @abstractmethod
    def get_state(self) -> Dict[str, Any]:
        """Get current component state."""
        pass


class IPlugin(ABC):
    """
    Interface for plugins.
    
    Defines the contract for plugin development with lifecycle management,
    dependency declaration, and capability advertisement.
    """
    
    @abstractmethod
    def get_name(self) -> str:
        """Get plugin name."""
        pass
    
    @abstractmethod
    def get_version(self) -> str:
        """Get plugin version."""
        pass
    
    @abstractmethod
    def get_dependencies(self) -> List[str]:
        """Get list of required dependencies."""
        pass
    
    @abstractmethod
    async def initialize(self, context: 'PluginContext') -> None:
        """Initialize the plugin."""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the plugin gracefully."""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Get list of capabilities this plugin provides."""
        pass


class IEventBus(ABC):
    """
    Interface for event bus system.
    
    Provides publish-subscribe messaging with typed events,
    priority handling, and async support.
    """
    
    @abstractmethod
    async def publish(self, event: 'Event') -> None:
        """Publish an event."""
        pass
    
    @abstractmethod
    def subscribe(
        self, 
        event_type: str, 
        handler: Callable[['Event'], None],
        priority: int = 0
    ) -> str:
        """
        Subscribe to events of a specific type.
        
        Returns:
            Subscription ID for unsubscribing
        """
        pass
    
    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from events."""
        pass


class IHealthCheck(ABC):
    """
    Interface for health check providers.
    
    Enables components to report their health status and
    provide diagnostic information.
    """
    
    @abstractmethod
    async def check_health(self) -> 'HealthCheckResult':
        """
        Perform health check.
        
        Returns:
            HealthCheckResult with status and details
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get health check name."""
        pass


class IRepository(ABC):
    """
    Interface for data repositories.
    
    Provides abstraction for data persistence with async support
    and transaction management.
    """
    
    @abstractmethod
    async def save(self, entity: Any) -> Any:
        """Save entity to repository."""
        pass
    
    @abstractmethod
    async def find_by_id(self, entity_id: str) -> Optional[Any]:
        """Find entity by ID."""
        pass
    
    @abstractmethod
    async def find_all(self) -> List[Any]:
        """Find all entities."""
        pass
    
    @abstractmethod
    async def delete(self, entity_id: str) -> bool:
        """Delete entity by ID."""
        pass


class IServiceDiscovery(ABC):
    """
    Interface for service discovery.
    
    Enables dynamic service registration and discovery
    for plugin architecture and external integrations.
    """
    
    @abstractmethod
    async def register_service(
        self, 
        name: str, 
        instance: Any, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Register a service instance."""
        pass
    
    @abstractmethod
    async def discover_service(self, name: str) -> Optional[Any]:
        """Discover a service by name."""
        pass
    
    @abstractmethod
    async def discover_services(self, capability: str) -> List[Any]:
        """Discover services by capability."""
        pass


# Data transfer objects and value objects

class ExecutionResult:
    """Result of script execution."""
    
    def __init__(
        self,
        status: ExecutionStatus,
        exit_code: int = 0,
        stdout: str = "",
        stderr: str = "",
        duration: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.status = status
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.duration = duration
        self.metadata = metadata or {}
        self.timestamp = datetime.now()


class HealthCheckResult:
    """Result of health check."""
    
    def __init__(
        self,
        status: HealthStatus,
        message: str = "",
        details: Optional[Dict[str, Any]] = None,
        duration: float = 0.0
    ):
        self.status = status
        self.message = message
        self.details = details or {}
        self.duration = duration
        self.timestamp = datetime.now()


class Event:
    """Base event class for event bus."""
    
    def __init__(
        self,
        event_type: str,
        data: Dict[str, Any],
        source: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        self.event_type = event_type
        self.data = data
        self.source = source
        self.correlation_id = correlation_id
        self.timestamp = datetime.now()


class PluginContext:
    """Context provided to plugins during initialization."""
    
    def __init__(
        self,
        container: 'Container',
        event_bus: IEventBus,
        settings: ISettingsManager,
        logger: Any
    ):
        self.container = container
        self.event_bus = event_bus
        self.settings = settings
        self.logger = logger

