"""
Dependency Injection Container for the Modern Taskbar system.

This module provides a comprehensive dependency injection container that manages:
- Service registration and resolution
- Lifecycle management (singleton, transient, scoped)
- Dependency graph resolution and circular dependency detection
- Automatic constructor injection
- Factory pattern support
- Configuration-based service registration

The container follows the Inversion of Control (IoC) principle and supports
both constructor injection and property injection patterns.
"""

import asyncio
import inspect
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar, Callable, Union, get_type_hints
from enum import Enum
from dataclasses import dataclass
from collections import defaultdict, deque
import weakref
import threading

from .interfaces import IHealthCheck
from .exceptions import ToolbarException, ConfigurationError

T = TypeVar('T')

logger = logging.getLogger(__name__)


class ServiceLifetime(Enum):
    """Service lifetime management options."""
    SINGLETON = "singleton"      # Single instance for the entire application
    TRANSIENT = "transient"      # New instance every time
    SCOPED = "scoped"           # Single instance per scope (e.g., per request)


@dataclass
class ServiceDescriptor:
    """Describes how a service should be registered and created."""
    service_type: Type
    implementation_type: Optional[Type] = None
    factory: Optional[Callable] = None
    instance: Optional[Any] = None
    lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT
    dependencies: Optional[List[str]] = None
    configuration: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    health_check: Optional[Callable] = None


class ServiceScope:
    """Represents a service scope for scoped lifetime management."""
    
    def __init__(self, container: 'Container'):
        self.container = container
        self._scoped_instances: Dict[Type, Any] = {}
        self._disposed = False
    
    def get_scoped_instance(self, service_type: Type) -> Optional[Any]:
        """Get a scoped instance if it exists."""
        return self._scoped_instances.get(service_type)
    
    def set_scoped_instance(self, service_type: Type, instance: Any) -> None:
        """Set a scoped instance."""
        if not self._disposed:
            self._scoped_instances[service_type] = instance
    
    async def dispose(self) -> None:
        """Dispose of all scoped instances."""
        if self._disposed:
            return
        
        self._disposed = True
        
        # Dispose instances in reverse order of creation
        for instance in reversed(list(self._scoped_instances.values())):
            try:
                if hasattr(instance, 'dispose'):
                    if asyncio.iscoroutinefunction(instance.dispose):
                        await instance.dispose()
                    else:
                        instance.dispose()
                elif hasattr(instance, 'cleanup'):
                    if asyncio.iscoroutinefunction(instance.cleanup):
                        await instance.cleanup()
                    else:
                        instance.cleanup()
            except Exception as e:
                logger.error(f"Error disposing scoped instance {type(instance)}: {e}")
        
        self._scoped_instances.clear()


class Container:
    """
    Dependency injection container with advanced features.
    
    Provides service registration, resolution, and lifecycle management
    with support for complex dependency graphs and multiple lifetime patterns.
    """
    
    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._named_services: Dict[str, ServiceDescriptor] = {}
        self._singletons: Dict[Type, Any] = {}
        self._building: set = set()  # Track services being built to detect circular dependencies
        self._lock = threading.RLock()
        self._current_scope: Optional[ServiceScope] = None
        self._health_checks: Dict[str, IHealthCheck] = {}
        
        # Register the container itself
        self.register_instance(Container, self)
    
    def register_singleton(
        self, 
        service_type: Type[T], 
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[[], T]] = None,
        instance: Optional[T] = None,
        **kwargs
    ) -> 'Container':
        """
        Register a service with singleton lifetime.
        
        Args:
            service_type: The service interface or base type
            implementation_type: The concrete implementation type
            factory: Factory function to create the service
            instance: Pre-created instance to use
            **kwargs: Additional configuration
            
        Returns:
            Self for method chaining
        """
        return self._register_service(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            instance=instance,
            lifetime=ServiceLifetime.SINGLETON,
            **kwargs
        )
    
    def register_transient(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[[], T]] = None,
        **kwargs
    ) -> 'Container':
        """
        Register a service with transient lifetime.
        
        Args:
            service_type: The service interface or base type
            implementation_type: The concrete implementation type
            factory: Factory function to create the service
            **kwargs: Additional configuration
            
        Returns:
            Self for method chaining
        """
        return self._register_service(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            lifetime=ServiceLifetime.TRANSIENT,
            **kwargs
        )
    
    def register_scoped(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[[], T]] = None,
        **kwargs
    ) -> 'Container':
        """
        Register a service with scoped lifetime.
        
        Args:
            service_type: The service interface or base type
            implementation_type: The concrete implementation type
            factory: Factory function to create the service
            **kwargs: Additional configuration
            
        Returns:
            Self for method chaining
        """
        return self._register_service(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            lifetime=ServiceLifetime.SCOPED,
            **kwargs
        )
    
    def register_instance(self, service_type: Type[T], instance: T) -> 'Container':
        """
        Register a pre-created instance.
        
        Args:
            service_type: The service type
            instance: The instance to register
            
        Returns:
            Self for method chaining
        """
        with self._lock:
            self._services[service_type] = ServiceDescriptor(
                service_type=service_type,
                instance=instance,
                lifetime=ServiceLifetime.SINGLETON
            )
            self._singletons[service_type] = instance
        
        logger.debug(f"Registered instance for {service_type.__name__}")
        return self
    
    def register_named(
        self,
        name: str,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[[], T]] = None,
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
        **kwargs
    ) -> 'Container':
        """
        Register a named service.
        
        Args:
            name: Service name
            service_type: The service interface or base type
            implementation_type: The concrete implementation type
            factory: Factory function to create the service
            lifetime: Service lifetime
            **kwargs: Additional configuration
            
        Returns:
            Self for method chaining
        """
        with self._lock:
            descriptor = ServiceDescriptor(
                service_type=service_type,
                implementation_type=implementation_type,
                factory=factory,
                lifetime=lifetime,
                **kwargs
            )
            self._named_services[name] = descriptor
        
        logger.debug(f"Registered named service '{name}' for {service_type.__name__}")
        return self
    
    def resolve(self, service_type: Type[T]) -> T:
        """
        Resolve a service instance.
        
        Args:
            service_type: The service type to resolve
            
        Returns:
            Service instance
            
        Raises:
            ConfigurationError: If service is not registered or cannot be created
        """
        with self._lock:
            return self._resolve_service(service_type)
    
    def resolve_named(self, name: str) -> Any:
        """
        Resolve a named service instance.
        
        Args:
            name: Service name
            
        Returns:
            Service instance
            
        Raises:
            ConfigurationError: If named service is not registered
        """
        with self._lock:
            if name not in self._named_services:
                raise ConfigurationError(f"Named service '{name}' not registered")
            
            descriptor = self._named_services[name]
            return self._create_instance(descriptor)
    
    def resolve_all(self, service_type: Type[T]) -> List[T]:
        """
        Resolve all instances of a service type.
        
        Args:
            service_type: The service type to resolve
            
        Returns:
            List of service instances
        """
        instances = []
        
        # Resolve main registration
        try:
            instance = self.resolve(service_type)
            instances.append(instance)
        except ConfigurationError:
            pass
        
        # Resolve named registrations
        for name, descriptor in self._named_services.items():
            if descriptor.service_type == service_type:
                try:
                    instance = self.resolve_named(name)
                    instances.append(instance)
                except Exception as e:
                    logger.warning(f"Failed to resolve named service '{name}': {e}")
        
        return instances
    
    def is_registered(self, service_type: Type) -> bool:
        """
        Check if a service type is registered.
        
        Args:
            service_type: The service type to check
            
        Returns:
            True if registered
        """
        return service_type in self._services
    
    def create_scope(self) -> ServiceScope:
        """
        Create a new service scope.
        
        Returns:
            New service scope
        """
        return ServiceScope(self)
    
    def set_current_scope(self, scope: Optional[ServiceScope]) -> None:
        """
        Set the current service scope.
        
        Args:
            scope: The scope to set as current
        """
        self._current_scope = scope
    
    def get_current_scope(self) -> Optional[ServiceScope]:
        """
        Get the current service scope.
        
        Returns:
            Current scope or None
        """
        return self._current_scope
    
    async def validate_configuration(self) -> List[str]:
        """
        Validate the container configuration.
        
        Returns:
            List of validation errors
        """
        errors = []
        
        # Check for circular dependencies
        try:
            self._check_circular_dependencies()
        except ConfigurationError as e:
            errors.append(str(e))
        
        # Validate each service can be created
        for service_type, descriptor in self._services.items():
            try:
                # Try to resolve dependencies without creating instance
                self._get_constructor_dependencies(
                    descriptor.implementation_type or service_type
                )
            except Exception as e:
                errors.append(f"Service {service_type.__name__}: {e}")
        
        return errors
    
    async def dispose(self) -> None:
        """Dispose of the container and all managed instances."""
        logger.info("Disposing container")
        
        # Dispose current scope
        if self._current_scope:
            await self._current_scope.dispose()
        
        # Dispose singletons in reverse order
        for instance in reversed(list(self._singletons.values())):
            try:
                if hasattr(instance, 'dispose'):
                    if asyncio.iscoroutinefunction(instance.dispose):
                        await instance.dispose()
                    else:
                        instance.dispose()
                elif hasattr(instance, 'cleanup'):
                    if asyncio.iscoroutinefunction(instance.cleanup):
                        await instance.cleanup()
                    else:
                        instance.cleanup()
            except Exception as e:
                logger.error(f"Error disposing singleton {type(instance)}: {e}")
        
        # Clear all registrations
        self._services.clear()
        self._named_services.clear()
        self._singletons.clear()
        self._health_checks.clear()
    
    # Private methods
    
    def _register_service(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable] = None,
        instance: Optional[T] = None,
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
        dependencies: Optional[List[str]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        health_check: Optional[Callable] = None
    ) -> 'Container':
        """Internal method to register a service."""
        with self._lock:
            # Validate registration
            if instance is not None and lifetime != ServiceLifetime.SINGLETON:
                raise ConfigurationError(
                    "Instance registration requires singleton lifetime"
                )
            
            if factory is None and implementation_type is None and instance is None:
                implementation_type = service_type
            
            descriptor = ServiceDescriptor(
                service_type=service_type,
                implementation_type=implementation_type,
                factory=factory,
                instance=instance,
                lifetime=lifetime,
                dependencies=dependencies,
                configuration=configuration,
                tags=tags,
                health_check=health_check
            )
            
            self._services[service_type] = descriptor
            
            # Store singleton instance if provided
            if instance is not None:
                self._singletons[service_type] = instance
        
        logger.debug(f"Registered {lifetime.value} service {service_type.__name__}")
        return self
    
    def _resolve_service(self, service_type: Type[T]) -> T:
        """Internal method to resolve a service."""
        if service_type not in self._services:
            raise ConfigurationError(f"Service {service_type.__name__} not registered")
        
        # Check for circular dependency
        if service_type in self._building:
            cycle = " -> ".join(cls.__name__ for cls in self._building)
            raise ConfigurationError(f"Circular dependency detected: {cycle} -> {service_type.__name__}")
        
        descriptor = self._services[service_type]
        
        # Handle different lifetimes
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            if service_type in self._singletons:
                return self._singletons[service_type]
            
            # Create singleton instance
            self._building.add(service_type)
            try:
                instance = self._create_instance(descriptor)
                self._singletons[service_type] = instance
                return instance
            finally:
                self._building.discard(service_type)
        
        elif descriptor.lifetime == ServiceLifetime.SCOPED:
            if self._current_scope:
                instance = self._current_scope.get_scoped_instance(service_type)
                if instance is not None:
                    return instance
                
                # Create scoped instance
                self._building.add(service_type)
                try:
                    instance = self._create_instance(descriptor)
                    self._current_scope.set_scoped_instance(service_type, instance)
                    return instance
                finally:
                    self._building.discard(service_type)
            else:
                # No scope, treat as transient
                self._building.add(service_type)
                try:
                    return self._create_instance(descriptor)
                finally:
                    self._building.discard(service_type)
        
        else:  # TRANSIENT
            self._building.add(service_type)
            try:
                return self._create_instance(descriptor)
            finally:
                self._building.discard(service_type)
    
    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Create an instance from a service descriptor."""
        # Use existing instance if available
        if descriptor.instance is not None:
            return descriptor.instance
        
        # Use factory if available
        if descriptor.factory is not None:
            return descriptor.factory()
        
        # Create using constructor injection
        implementation_type = descriptor.implementation_type or descriptor.service_type
        
        # Get constructor dependencies
        dependencies = self._get_constructor_dependencies(implementation_type)
        
        # Resolve dependencies
        resolved_deps = {}
        for param_name, param_type in dependencies.items():
            try:
                resolved_deps[param_name] = self._resolve_service(param_type)
            except ConfigurationError as e:
                raise ConfigurationError(
                    f"Cannot resolve dependency '{param_name}' of type {param_type.__name__} "
                    f"for service {implementation_type.__name__}: {e}"
                )
        
        # Create instance
        try:
            instance = implementation_type(**resolved_deps)
            logger.debug(f"Created instance of {implementation_type.__name__}")
            return instance
        except Exception as e:
            raise ConfigurationError(
                f"Failed to create instance of {implementation_type.__name__}: {e}"
            )
    
    def _get_constructor_dependencies(self, implementation_type: Type) -> Dict[str, Type]:
        """Get constructor dependencies for a type."""
        try:
            # Get constructor signature
            signature = inspect.signature(implementation_type.__init__)
            type_hints = get_type_hints(implementation_type.__init__)
            
            dependencies = {}
            for param_name, param in signature.parameters.items():
                if param_name == 'self':
                    continue
                
                # Get type annotation
                param_type = type_hints.get(param_name)
                if param_type is None:
                    if param.default is inspect.Parameter.empty:
                        raise ConfigurationError(
                            f"Parameter '{param_name}' in {implementation_type.__name__} "
                            "has no type annotation and no default value"
                        )
                    continue
                
                dependencies[param_name] = param_type
            
            return dependencies
            
        except Exception as e:
            raise ConfigurationError(
                f"Failed to analyze constructor of {implementation_type.__name__}: {e}"
            )
    
    def _check_circular_dependencies(self) -> None:
        """Check for circular dependencies in the service graph."""
        visited = set()
        visiting = set()
        
        def visit(service_type: Type) -> None:
            if service_type in visiting:
                raise ConfigurationError(f"Circular dependency detected involving {service_type.__name__}")
            
            if service_type in visited:
                return
            
            visiting.add(service_type)
            
            # Get dependencies
            if service_type in self._services:
                descriptor = self._services[service_type]
                implementation_type = descriptor.implementation_type or service_type
                
                try:
                    dependencies = self._get_constructor_dependencies(implementation_type)
                    for dep_type in dependencies.values():
                        if dep_type in self._services:
                            visit(dep_type)
                except Exception:
                    # Skip if we can't analyze dependencies
                    pass
            
            visiting.remove(service_type)
            visited.add(service_type)
        
        # Visit all registered services
        for service_type in self._services:
            visit(service_type)

