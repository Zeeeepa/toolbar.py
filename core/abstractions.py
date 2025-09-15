"""
Abstract base classes providing common functionality for the Modern Taskbar system.

This module contains abstract base classes that provide default implementations
of common patterns and behaviors. These classes serve as building blocks for
concrete implementations while enforcing architectural contracts.

The abstractions follow the Template Method pattern where appropriate,
allowing subclasses to customize specific behaviors while maintaining
consistent overall structure.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Callable
from datetime import datetime, timedelta
from pathlib import Path
import uuid
import weakref

from .interfaces import (
    IExecutionEngine, IFileManager, ISettingsManager, IUIComponent,
    IPlugin, IEventBus, IHealthCheck, ExecutionResult, ExecutionStatus,
    HealthCheckResult, HealthStatus, Event, PluginContext
)
from .exceptions import ToolbarException, ExecutionError, PluginError


class BaseService(ABC):
    """
    Abstract base class for all services in the system.
    
    Provides common functionality including:
    - Lifecycle management (initialize, start, stop, cleanup)
    - Health checking capabilities
    - Logging integration
    - Configuration management
    - Dependency injection support
    """
    
    def __init__(self, name: str, logger: Optional[logging.Logger] = None):
        self.name = name
        self.logger = logger or logging.getLogger(f"{__name__}.{name}")
        self._initialized = False
        self._started = False
        self._dependencies: Set[str] = set()
        self._health_status = HealthStatus.UNKNOWN
        self._last_health_check: Optional[datetime] = None
        
    async def initialize(self, **kwargs) -> None:
        """
        Initialize the service.
        
        Template method that calls _do_initialize() for custom initialization.
        """
        if self._initialized:
            self.logger.warning(f"Service {self.name} already initialized")
            return
            
        try:
            self.logger.info(f"Initializing service: {self.name}")
            await self._do_initialize(**kwargs)
            self._initialized = True
            self.logger.info(f"Service {self.name} initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize service {self.name}: {e}")
            raise
    
    async def start(self) -> None:
        """
        Start the service.
        
        Template method that calls _do_start() for custom startup logic.
        """
        if not self._initialized:
            raise ToolbarException(f"Service {self.name} not initialized")
            
        if self._started:
            self.logger.warning(f"Service {self.name} already started")
            return
            
        try:
            self.logger.info(f"Starting service: {self.name}")
            await self._do_start()
            self._started = True
            self.logger.info(f"Service {self.name} started successfully")
        except Exception as e:
            self.logger.error(f"Failed to start service {self.name}: {e}")
            raise
    
    async def stop(self) -> None:
        """
        Stop the service gracefully.
        
        Template method that calls _do_stop() for custom shutdown logic.
        """
        if not self._started:
            return
            
        try:
            self.logger.info(f"Stopping service: {self.name}")
            await self._do_stop()
            self._started = False
            self.logger.info(f"Service {self.name} stopped successfully")
        except Exception as e:
            self.logger.error(f"Error stopping service {self.name}: {e}")
            # Don't re-raise to allow graceful shutdown
    
    async def cleanup(self) -> None:
        """
        Clean up service resources.
        
        Template method that calls _do_cleanup() for custom cleanup logic.
        """
        try:
            if self._started:
                await self.stop()
                
            self.logger.info(f"Cleaning up service: {self.name}")
            await self._do_cleanup()
            self._initialized = False
            self.logger.info(f"Service {self.name} cleaned up successfully")
        except Exception as e:
            self.logger.error(f"Error cleaning up service {self.name}: {e}")
    
    async def check_health(self) -> HealthCheckResult:
        """
        Perform health check for this service.
        
        Template method that calls _do_health_check() for custom health logic.
        """
        start_time = datetime.now()
        
        try:
            if not self._initialized:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message="Service not initialized",
                    duration=(datetime.now() - start_time).total_seconds()
                )
            
            result = await self._do_health_check()
            self._health_status = result.status
            self._last_health_check = datetime.now()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Health check failed for {self.name}: {e}")
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Health check error: {str(e)}",
                duration=(datetime.now() - start_time).total_seconds()
            )
    
    # Abstract methods for subclasses to implement
    
    @abstractmethod
    async def _do_initialize(self, **kwargs) -> None:
        """Custom initialization logic."""
        pass
    
    async def _do_start(self) -> None:
        """Custom start logic. Override if needed."""
        pass
    
    async def _do_stop(self) -> None:
        """Custom stop logic. Override if needed."""
        pass
    
    async def _do_cleanup(self) -> None:
        """Custom cleanup logic. Override if needed."""
        pass
    
    async def _do_health_check(self) -> HealthCheckResult:
        """
        Custom health check logic.
        
        Default implementation returns healthy if service is started.
        """
        if self._started:
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message=f"Service {self.name} is running"
            )
        else:
            return HealthCheckResult(
                status=HealthStatus.DEGRADED,
                message=f"Service {self.name} is initialized but not started"
            )
    
    # Properties
    
    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized
    
    @property
    def is_started(self) -> bool:
        """Check if service is started."""
        return self._started
    
    @property
    def health_status(self) -> HealthStatus:
        """Get current health status."""
        return self._health_status
    
    def add_dependency(self, service_name: str) -> None:
        """Add a service dependency."""
        self._dependencies.add(service_name)
    
    def get_dependencies(self) -> Set[str]:
        """Get service dependencies."""
        return self._dependencies.copy()


class BaseExecutionEngine(BaseService, IExecutionEngine):
    """
    Abstract base class for execution engines.
    
    Provides common execution functionality including:
    - Process management
    - Output capture
    - Timeout handling
    - Status tracking
    """
    
    def __init__(self, name: str, supported_extensions: List[str]):
        super().__init__(name)
        self._supported_extensions = supported_extensions
        self._active_processes: Dict[str, asyncio.subprocess.Process] = {}
    
    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return self._supported_extensions.copy()
    
    def can_execute(self, file_path: Path) -> bool:
        """Check if this engine can execute the file."""
        return file_path.suffix.lower() in self._supported_extensions
    
    async def execute_file(
        self,
        file_path: Path,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None
    ) -> ExecutionResult:
        """
        Execute a file with common process management.
        
        Template method that calls _build_command() and _prepare_environment()
        for engine-specific customization.
        """
        if not file_path.exists():
            raise ExecutionError(f"File not found: {file_path}")
        
        if not self.can_execute(file_path):
            raise ExecutionError(f"Cannot execute file type: {file_path.suffix}")
        
        execution_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        try:
            # Build command for execution
            command = await self._build_command(file_path, args or [])
            
            # Prepare environment
            exec_env = await self._prepare_environment(env or {})
            
            # Start process
            self.logger.info(f"Executing: {' '.join(command)}")
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=exec_env,
                cwd=file_path.parent
            )
            
            self._active_processes[execution_id] = process
            
            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise ExecutionError("Execution timed out")
            finally:
                self._active_processes.pop(execution_id, None)
            
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()
            
            # Determine status
            if process.returncode == 0:
                status = ExecutionStatus.SUCCESS
            else:
                status = ExecutionStatus.ERROR
            
            return ExecutionResult(
                status=status,
                exit_code=process.returncode,
                stdout=stdout.decode('utf-8', errors='replace'),
                stderr=stderr.decode('utf-8', errors='replace'),
                duration=duration,
                metadata={
                    'command': command,
                    'file_path': str(file_path),
                    'execution_id': execution_id
                }
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"Execution failed: {e}")
            
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                exit_code=-1,
                stderr=str(e),
                duration=duration,
                metadata={
                    'file_path': str(file_path),
                    'execution_id': execution_id,
                    'error': str(e)
                }
            )
    
    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running execution."""
        process = self._active_processes.get(execution_id)
        if process:
            try:
                process.kill()
                await process.wait()
                return True
            except Exception as e:
                self.logger.error(f"Failed to cancel execution {execution_id}: {e}")
        return False
    
    # Abstract methods for subclasses
    
    @abstractmethod
    async def _build_command(self, file_path: Path, args: List[str]) -> List[str]:
        """Build the command to execute the file."""
        pass
    
    async def _prepare_environment(self, env: Dict[str, str]) -> Dict[str, str]:
        """
        Prepare execution environment.
        
        Default implementation merges with system environment.
        """
        import os
        exec_env = os.environ.copy()
        exec_env.update(env)
        return exec_env
    
    async def _do_initialize(self, **kwargs) -> None:
        """Initialize execution engine."""
        self.logger.info(f"Execution engine {self.name} supports: {self._supported_extensions}")
    
    async def _do_cleanup(self) -> None:
        """Clean up active processes."""
        for execution_id, process in list(self._active_processes.items()):
            try:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
            except Exception as e:
                self.logger.error(f"Error cleaning up process {execution_id}: {e}")
        
        self._active_processes.clear()


class BasePlugin(IPlugin):
    """
    Abstract base class for plugins.
    
    Provides common plugin functionality including:
    - Lifecycle management
    - Dependency tracking
    - Capability advertisement
    - Context management
    """
    
    def __init__(self, name: str, version: str):
        self._name = name
        self._version = version
        self._dependencies: List[str] = []
        self._capabilities: List[str] = []
        self._context: Optional[PluginContext] = None
        self._initialized = False
        self.logger = logging.getLogger(f"plugin.{name}")
    
    def get_name(self) -> str:
        """Get plugin name."""
        return self._name
    
    def get_version(self) -> str:
        """Get plugin version."""
        return self._version
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return self._dependencies.copy()
    
    def get_capabilities(self) -> List[str]:
        """Get plugin capabilities."""
        return self._capabilities.copy()
    
    async def initialize(self, context: PluginContext) -> None:
        """
        Initialize the plugin.
        
        Template method that calls _do_initialize() for custom logic.
        """
        if self._initialized:
            raise PluginError(f"Plugin {self._name} already initialized")
        
        self._context = context
        
        try:
            self.logger.info(f"Initializing plugin: {self._name}")
            await self._do_initialize(context)
            self._initialized = True
            self.logger.info(f"Plugin {self._name} initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize plugin {self._name}: {e}")
            raise PluginError(f"Plugin initialization failed: {e}")
    
    async def shutdown(self) -> None:
        """
        Shutdown the plugin.
        
        Template method that calls _do_shutdown() for custom logic.
        """
        if not self._initialized:
            return
        
        try:
            self.logger.info(f"Shutting down plugin: {self._name}")
            await self._do_shutdown()
            self._initialized = False
            self.logger.info(f"Plugin {self._name} shutdown successfully")
        except Exception as e:
            self.logger.error(f"Error shutting down plugin {self._name}: {e}")
    
    # Abstract methods for subclasses
    
    @abstractmethod
    async def _do_initialize(self, context: PluginContext) -> None:
        """Custom initialization logic."""
        pass
    
    async def _do_shutdown(self) -> None:
        """Custom shutdown logic. Override if needed."""
        pass
    
    # Helper methods for subclasses
    
    def add_dependency(self, dependency: str) -> None:
        """Add a dependency."""
        if dependency not in self._dependencies:
            self._dependencies.append(dependency)
    
    def add_capability(self, capability: str) -> None:
        """Add a capability."""
        if capability not in self._capabilities:
            self._capabilities.append(capability)
    
    @property
    def context(self) -> Optional[PluginContext]:
        """Get plugin context."""
        return self._context
    
    @property
    def is_initialized(self) -> bool:
        """Check if plugin is initialized."""
        return self._initialized


class BaseUIComponent(IUIComponent):
    """
    Abstract base class for UI components.
    
    Provides common UI functionality including:
    - State management
    - Event handling
    - Lifecycle management
    - Parent-child relationships
    """
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"ui.{name}")
        self._parent: Optional[Any] = None
        self._children: List['BaseUIComponent'] = []
        self._state: Dict[str, Any] = {}
        self._initialized = False
        self._event_handlers: Dict[str, List[Callable]] = {}
    
    def initialize(self, parent: Any, **kwargs) -> None:
        """
        Initialize the UI component.
        
        Template method that calls _do_initialize() for custom logic.
        """
        if self._initialized:
            self.logger.warning(f"Component {self.name} already initialized")
            return
        
        self._parent = parent
        
        try:
            self.logger.debug(f"Initializing UI component: {self.name}")
            self._do_initialize(parent, **kwargs)
            self._initialized = True
            self.logger.debug(f"UI component {self.name} initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize UI component {self.name}: {e}")
            raise
    
    def update_state(self, state: Dict[str, Any]) -> None:
        """
        Update component state.
        
        Template method that calls _on_state_changed() for custom logic.
        """
        old_state = self._state.copy()
        self._state.update(state)
        
        try:
            self._on_state_changed(old_state, self._state)
        except Exception as e:
            self.logger.error(f"Error updating state for {self.name}: {e}")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current component state."""
        return self._state.copy()
    
    def cleanup(self) -> None:
        """
        Clean up component resources.
        
        Template method that calls _do_cleanup() for custom logic.
        """
        try:
            # Clean up children first
            for child in self._children:
                child.cleanup()
            
            self.logger.debug(f"Cleaning up UI component: {self.name}")
            self._do_cleanup()
            self._initialized = False
            self.logger.debug(f"UI component {self.name} cleaned up")
        except Exception as e:
            self.logger.error(f"Error cleaning up UI component {self.name}: {e}")
    
    # Abstract methods for subclasses
    
    @abstractmethod
    def _do_initialize(self, parent: Any, **kwargs) -> None:
        """Custom initialization logic."""
        pass
    
    def _on_state_changed(self, old_state: Dict[str, Any], new_state: Dict[str, Any]) -> None:
        """Handle state changes. Override if needed."""
        pass
    
    def _do_cleanup(self) -> None:
        """Custom cleanup logic. Override if needed."""
        pass
    
    # Helper methods for subclasses
    
    def add_child(self, child: 'BaseUIComponent') -> None:
        """Add a child component."""
        if child not in self._children:
            self._children.append(child)
    
    def remove_child(self, child: 'BaseUIComponent') -> None:
        """Remove a child component."""
        if child in self._children:
            self._children.remove(child)
            child.cleanup()
    
    def bind_event(self, event_name: str, handler: Callable) -> None:
        """Bind an event handler."""
        if event_name not in self._event_handlers:
            self._event_handlers[event_name] = []
        self._event_handlers[event_name].append(handler)
    
    def emit_event(self, event_name: str, *args, **kwargs) -> None:
        """Emit an event to all handlers."""
        handlers = self._event_handlers.get(event_name, [])
        for handler in handlers:
            try:
                handler(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"Error in event handler for {event_name}: {e}")
    
    @property
    def parent(self) -> Optional[Any]:
        """Get parent component."""
        return self._parent
    
    @property
    def children(self) -> List['BaseUIComponent']:
        """Get child components."""
        return self._children.copy()
    
    @property
    def is_initialized(self) -> bool:
        """Check if component is initialized."""
        return self._initialized

