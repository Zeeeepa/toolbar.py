"""
Service Registry for the Modern Taskbar system.

This module provides a centralized service registry that manages:
- Service discovery and registration
- Service metadata and capabilities
- Health monitoring and status tracking
- Service lifecycle coordination
- Dynamic service loading and unloading

The registry acts as a central hub for all services in the system,
enabling loose coupling and dynamic service management.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Set, Callable, Type
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
import weakref
import threading

from .interfaces import IHealthCheck, HealthStatus, HealthCheckResult
from .exceptions import ToolbarException, ConfigurationError
from .container import Container

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service status enumeration."""
    REGISTERED = "registered"
    INITIALIZING = "initializing"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ServiceMetadata:
    """Metadata for a registered service."""
    name: str
    service_type: Type
    instance: Any
    status: ServiceStatus = ServiceStatus.REGISTERED
    capabilities: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    tags: Set[str] = field(default_factory=set)
    version: Optional[str] = None
    description: Optional[str] = None
    health_check: Optional[IHealthCheck] = None
    last_health_check: Optional[datetime] = None
    health_status: HealthStatus = HealthStatus.UNKNOWN
    registration_time: datetime = field(default_factory=datetime.now)
    start_time: Optional[datetime] = None
    stop_time: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None
    configuration: Dict[str, Any] = field(default_factory=dict)


class ServiceRegistry:
    """
    Centralized service registry with advanced management capabilities.
    
    Provides service discovery, health monitoring, lifecycle management,
    and dependency tracking for all services in the system.
    """
    
    def __init__(self, container: Optional[Container] = None):
        self.container = container or Container()
        self._services: Dict[str, ServiceMetadata] = {}
        self._services_by_type: Dict[Type, List[ServiceMetadata]] = defaultdict(list)
        self._services_by_capability: Dict[str, List[ServiceMetadata]] = defaultdict(list)
        self._services_by_tag: Dict[str, List[ServiceMetadata]] = defaultdict(list)
        self._status_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self._health_check_interval = 30  # seconds
        self._health_check_task: Optional[asyncio.Task] = None
        self._lock = threading.RLock()
        self._shutdown_event = asyncio.Event()
        
        # Statistics
        self._stats = {
            'total_registrations': 0,
            'successful_starts': 0,
            'failed_starts': 0,
            'total_health_checks': 0,
            'failed_health_checks': 0
        }
    
    async def initialize(self) -> None:
        """Initialize the service registry."""
        logger.info("Initializing service registry")
        
        # Start health check monitoring
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        logger.info("Service registry initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the service registry and all managed services."""
        logger.info("Shutting down service registry")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # Stop all services in reverse dependency order
        await self._stop_all_services()
        
        # Clear registry
        with self._lock:
            self._services.clear()
            self._services_by_type.clear()
            self._services_by_capability.clear()
            self._services_by_tag.clear()
            self._status_callbacks.clear()
        
        logger.info("Service registry shutdown complete")
    
    def register_service(
        self,
        name: str,
        instance: Any,
        service_type: Optional[Type] = None,
        capabilities: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
        tags: Optional[Set[str]] = None,
        version: Optional[str] = None,
        description: Optional[str] = None,
        health_check: Optional[IHealthCheck] = None,
        configuration: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register a service with the registry.
        
        Args:
            name: Unique service name
            instance: Service instance
            service_type: Service type (inferred if not provided)
            capabilities: List of capabilities the service provides
            dependencies: List of service dependencies
            tags: Set of tags for categorization
            version: Service version
            description: Service description
            health_check: Health check implementation
            configuration: Service configuration
            
        Raises:
            ConfigurationError: If service name already exists
        """
        with self._lock:
            if name in self._services:
                raise ConfigurationError(f"Service '{name}' already registered")
            
            # Infer service type if not provided
            if service_type is None:
                service_type = type(instance)
            
            # Create metadata
            metadata = ServiceMetadata(
                name=name,
                service_type=service_type,
                instance=instance,
                capabilities=capabilities or [],
                dependencies=dependencies or [],
                tags=tags or set(),
                version=version,
                description=description,
                health_check=health_check,
                configuration=configuration or {}
            )
            
            # Store in various indexes
            self._services[name] = metadata
            self._services_by_type[service_type].append(metadata)
            
            for capability in metadata.capabilities:
                self._services_by_capability[capability].append(metadata)
            
            for tag in metadata.tags:
                self._services_by_tag[tag].append(metadata)
            
            # Update statistics
            self._stats['total_registrations'] += 1
            
            logger.info(f"Registered service '{name}' of type {service_type.__name__}")
            
            # Notify status callbacks
            self._notify_status_change(name, ServiceStatus.REGISTERED)
    
    def unregister_service(self, name: str) -> bool:
        """
        Unregister a service from the registry.
        
        Args:
            name: Service name to unregister
            
        Returns:
            True if service was unregistered, False if not found
        """
        with self._lock:
            if name not in self._services:
                return False
            
            metadata = self._services[name]
            
            # Stop service if running
            if metadata.status == ServiceStatus.RUNNING:
                asyncio.create_task(self.stop_service(name))
            
            # Remove from indexes
            del self._services[name]
            
            self._services_by_type[metadata.service_type].remove(metadata)
            if not self._services_by_type[metadata.service_type]:
                del self._services_by_type[metadata.service_type]
            
            for capability in metadata.capabilities:
                self._services_by_capability[capability].remove(metadata)
                if not self._services_by_capability[capability]:
                    del self._services_by_capability[capability]
            
            for tag in metadata.tags:
                self._services_by_tag[tag].remove(metadata)
                if not self._services_by_tag[tag]:
                    del self._services_by_tag[tag]
            
            logger.info(f"Unregistered service '{name}'")
            return True
    
    def get_service(self, name: str) -> Optional[Any]:
        """
        Get a service instance by name.
        
        Args:
            name: Service name
            
        Returns:
            Service instance or None if not found
        """
        with self._lock:
            metadata = self._services.get(name)
            return metadata.instance if metadata else None
    
    def get_service_metadata(self, name: str) -> Optional[ServiceMetadata]:
        """
        Get service metadata by name.
        
        Args:
            name: Service name
            
        Returns:
            Service metadata or None if not found
        """
        with self._lock:
            return self._services.get(name)
    
    def find_services_by_type(self, service_type: Type) -> List[Any]:
        """
        Find all services of a specific type.
        
        Args:
            service_type: Type to search for
            
        Returns:
            List of service instances
        """
        with self._lock:
            metadata_list = self._services_by_type.get(service_type, [])
            return [metadata.instance for metadata in metadata_list]
    
    def find_services_by_capability(self, capability: str) -> List[Any]:
        """
        Find all services that provide a specific capability.
        
        Args:
            capability: Capability to search for
            
        Returns:
            List of service instances
        """
        with self._lock:
            metadata_list = self._services_by_capability.get(capability, [])
            return [metadata.instance for metadata in metadata_list]
    
    def find_services_by_tag(self, tag: str) -> List[Any]:
        """
        Find all services with a specific tag.
        
        Args:
            tag: Tag to search for
            
        Returns:
            List of service instances
        """
        with self._lock:
            metadata_list = self._services_by_tag.get(tag, [])
            return [metadata.instance for metadata in metadata_list]
    
    def get_all_services(self) -> Dict[str, Any]:
        """
        Get all registered services.
        
        Returns:
            Dictionary mapping service names to instances
        """
        with self._lock:
            return {name: metadata.instance for name, metadata in self._services.items()}
    
    def get_service_names(self) -> List[str]:
        """
        Get all registered service names.
        
        Returns:
            List of service names
        """
        with self._lock:
            return list(self._services.keys())
    
    def is_service_registered(self, name: str) -> bool:
        """
        Check if a service is registered.
        
        Args:
            name: Service name
            
        Returns:
            True if registered
        """
        with self._lock:
            return name in self._services
    
    async def start_service(self, name: str) -> bool:
        """
        Start a registered service.
        
        Args:
            name: Service name
            
        Returns:
            True if started successfully
        """
        with self._lock:
            if name not in self._services:
                logger.error(f"Service '{name}' not registered")
                return False
            
            metadata = self._services[name]
            
            if metadata.status == ServiceStatus.RUNNING:
                logger.warning(f"Service '{name}' already running")
                return True
            
            # Check dependencies
            for dep_name in metadata.dependencies:
                if not self.is_service_running(dep_name):
                    logger.error(f"Dependency '{dep_name}' not running for service '{name}'")
                    return False
        
        try:
            # Update status
            self._update_service_status(name, ServiceStatus.INITIALIZING)
            
            # Start the service
            instance = metadata.instance
            if hasattr(instance, 'start'):
                if asyncio.iscoroutinefunction(instance.start):
                    await instance.start()
                else:
                    instance.start()
            elif hasattr(instance, 'initialize'):
                if asyncio.iscoroutinefunction(instance.initialize):
                    await instance.initialize()
                else:
                    instance.initialize()
            
            # Update status and timing
            with self._lock:
                metadata.status = ServiceStatus.RUNNING
                metadata.start_time = datetime.now()
                self._stats['successful_starts'] += 1
            
            logger.info(f"Started service '{name}'")
            self._notify_status_change(name, ServiceStatus.RUNNING)
            return True
            
        except Exception as e:
            logger.error(f"Failed to start service '{name}': {e}")
            
            with self._lock:
                metadata.status = ServiceStatus.ERROR
                metadata.error_count += 1
                metadata.last_error = str(e)
                self._stats['failed_starts'] += 1
            
            self._notify_status_change(name, ServiceStatus.ERROR)
            return False
    
    async def stop_service(self, name: str) -> bool:
        """
        Stop a running service.
        
        Args:
            name: Service name
            
        Returns:
            True if stopped successfully
        """
        with self._lock:
            if name not in self._services:
                logger.error(f"Service '{name}' not registered")
                return False
            
            metadata = self._services[name]
            
            if metadata.status != ServiceStatus.RUNNING:
                logger.warning(f"Service '{name}' not running")
                return True
        
        try:
            # Update status
            self._update_service_status(name, ServiceStatus.STOPPING)
            
            # Stop the service
            instance = metadata.instance
            if hasattr(instance, 'stop'):
                if asyncio.iscoroutinefunction(instance.stop):
                    await instance.stop()
                else:
                    instance.stop()
            elif hasattr(instance, 'cleanup'):
                if asyncio.iscoroutinefunction(instance.cleanup):
                    await instance.cleanup()
                else:
                    instance.cleanup()
            
            # Update status and timing
            with self._lock:
                metadata.status = ServiceStatus.STOPPED
                metadata.stop_time = datetime.now()
            
            logger.info(f"Stopped service '{name}'")
            self._notify_status_change(name, ServiceStatus.STOPPED)
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop service '{name}': {e}")
            
            with self._lock:
                metadata.status = ServiceStatus.ERROR
                metadata.error_count += 1
                metadata.last_error = str(e)
            
            self._notify_status_change(name, ServiceStatus.ERROR)
            return False
    
    async def restart_service(self, name: str) -> bool:
        """
        Restart a service.
        
        Args:
            name: Service name
            
        Returns:
            True if restarted successfully
        """
        logger.info(f"Restarting service '{name}'")
        
        # Stop first
        await self.stop_service(name)
        
        # Wait a moment
        await asyncio.sleep(0.1)
        
        # Start again
        return await self.start_service(name)
    
    def is_service_running(self, name: str) -> bool:
        """
        Check if a service is running.
        
        Args:
            name: Service name
            
        Returns:
            True if running
        """
        with self._lock:
            metadata = self._services.get(name)
            return metadata.status == ServiceStatus.RUNNING if metadata else False
    
    def get_service_status(self, name: str) -> Optional[ServiceStatus]:
        """
        Get service status.
        
        Args:
            name: Service name
            
        Returns:
            Service status or None if not found
        """
        with self._lock:
            metadata = self._services.get(name)
            return metadata.status if metadata else None
    
    def register_status_callback(self, service_name: str, callback: Callable[[str, ServiceStatus], None]) -> None:
        """
        Register a callback for service status changes.
        
        Args:
            service_name: Service name to monitor
            callback: Callback function
        """
        with self._lock:
            self._status_callbacks[service_name].append(callback)
    
    def unregister_status_callback(self, service_name: str, callback: Callable) -> None:
        """
        Unregister a status callback.
        
        Args:
            service_name: Service name
            callback: Callback function to remove
        """
        with self._lock:
            if service_name in self._status_callbacks:
                try:
                    self._status_callbacks[service_name].remove(callback)
                except ValueError:
                    pass
    
    async def check_service_health(self, name: str) -> Optional[HealthCheckResult]:
        """
        Check health of a specific service.
        
        Args:
            name: Service name
            
        Returns:
            Health check result or None if service not found
        """
        with self._lock:
            metadata = self._services.get(name)
            if not metadata:
                return None
        
        try:
            if metadata.health_check:
                result = await metadata.health_check.check_health()
            elif hasattr(metadata.instance, 'check_health'):
                if asyncio.iscoroutinefunction(metadata.instance.check_health):
                    result = await metadata.instance.check_health()
                else:
                    result = metadata.instance.check_health()
            else:
                # Default health check based on status
                if metadata.status == ServiceStatus.RUNNING:
                    result = HealthCheckResult(
                        status=HealthStatus.HEALTHY,
                        message=f"Service '{name}' is running"
                    )
                else:
                    result = HealthCheckResult(
                        status=HealthStatus.UNHEALTHY,
                        message=f"Service '{name}' is not running (status: {metadata.status.value})"
                    )
            
            # Update metadata
            with self._lock:
                metadata.last_health_check = datetime.now()
                metadata.health_status = result.status
                self._stats['total_health_checks'] += 1
                
                if result.status == HealthStatus.UNHEALTHY:
                    self._stats['failed_health_checks'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Health check failed for service '{name}': {e}")
            
            with self._lock:
                metadata.health_status = HealthStatus.UNHEALTHY
                metadata.error_count += 1
                metadata.last_error = str(e)
                self._stats['failed_health_checks'] += 1
            
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Health check error: {str(e)}"
            )
    
    async def check_all_health(self) -> Dict[str, HealthCheckResult]:
        """
        Check health of all services.
        
        Returns:
            Dictionary mapping service names to health results
        """
        results = {}
        
        # Get all service names
        with self._lock:
            service_names = list(self._services.keys())
        
        # Check health for each service
        for name in service_names:
            result = await self.check_service_health(name)
            if result:
                results[name] = result
        
        return results
    
    def get_registry_statistics(self) -> Dict[str, Any]:
        """
        Get registry statistics.
        
        Returns:
            Dictionary containing various statistics
        """
        with self._lock:
            stats = self._stats.copy()
            
            # Add current counts
            stats.update({
                'total_services': len(self._services),
                'running_services': sum(1 for m in self._services.values() if m.status == ServiceStatus.RUNNING),
                'stopped_services': sum(1 for m in self._services.values() if m.status == ServiceStatus.STOPPED),
                'error_services': sum(1 for m in self._services.values() if m.status == ServiceStatus.ERROR),
                'healthy_services': sum(1 for m in self._services.values() if m.health_status == HealthStatus.HEALTHY),
                'unhealthy_services': sum(1 for m in self._services.values() if m.health_status == HealthStatus.UNHEALTHY),
                'total_capabilities': len(self._services_by_capability),
                'total_tags': len(self._services_by_tag)
            })
            
            return stats
    
    # Private methods
    
    def _update_service_status(self, name: str, status: ServiceStatus) -> None:
        """Update service status and notify callbacks."""
        with self._lock:
            if name in self._services:
                self._services[name].status = status
        
        self._notify_status_change(name, status)
    
    def _notify_status_change(self, service_name: str, status: ServiceStatus) -> None:
        """Notify all registered callbacks of status change."""
        callbacks = self._status_callbacks.get(service_name, [])
        for callback in callbacks:
            try:
                callback(service_name, status)
            except Exception as e:
                logger.error(f"Error in status callback for service '{service_name}': {e}")
    
    async def _health_check_loop(self) -> None:
        """Background task for periodic health checks."""
        logger.info("Starting health check monitoring")
        
        while not self._shutdown_event.is_set():
            try:
                # Wait for next check interval
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self._health_check_interval
                )
                break  # Shutdown requested
            except asyncio.TimeoutError:
                pass  # Continue with health check
            
            # Perform health checks
            try:
                await self.check_all_health()
            except Exception as e:
                logger.error(f"Error during health check cycle: {e}")
        
        logger.info("Health check monitoring stopped")
    
    async def _stop_all_services(self) -> None:
        """Stop all services in reverse dependency order."""
        # Build dependency graph
        dependency_graph = {}
        with self._lock:
            for name, metadata in self._services.items():
                dependency_graph[name] = metadata.dependencies.copy()
        
        # Topological sort to determine stop order
        stop_order = self._topological_sort_reverse(dependency_graph)
        
        # Stop services in order
        for name in stop_order:
            if self.is_service_running(name):
                await self.stop_service(name)
    
    def _topological_sort_reverse(self, dependency_graph: Dict[str, List[str]]) -> List[str]:
        """Perform reverse topological sort for shutdown order."""
        # Create reverse dependency graph
        reverse_graph = defaultdict(list)
        in_degree = defaultdict(int)
        
        for service, deps in dependency_graph.items():
            in_degree[service] = len(deps)
            for dep in deps:
                reverse_graph[dep].append(service)
        
        # Kahn's algorithm for topological sort
        queue = [service for service, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            service = queue.pop(0)
            result.append(service)
            
            for dependent in reverse_graph[service]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        # Return in reverse order for shutdown
        return list(reversed(result))

