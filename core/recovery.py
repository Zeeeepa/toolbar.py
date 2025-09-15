"""
Recovery and graceful degradation mechanisms for the Modern Taskbar system.

This module provides comprehensive recovery strategies with:
- Graceful degradation for missing dependencies
- Automatic service recovery and restart mechanisms
- Fallback strategies for failed operations
- Health-based recovery decisions
- Recovery orchestration and coordination
- Comprehensive recovery monitoring and reporting
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Callable, Set, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import threading

from .interfaces import IHealthCheck, HealthStatus, HealthCheckResult
from .exceptions import ToolbarException, ConfigurationError, IntegrationError
from .registry import ServiceRegistry

logger = logging.getLogger(__name__)


class RecoveryStrategy(Enum):
    """Recovery strategy types."""
    RESTART = "restart"
    FALLBACK = "fallback"
    DEGRADE = "degrade"
    ISOLATE = "isolate"
    ESCALATE = "escalate"


class RecoveryPriority(Enum):
    """Recovery priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RecoveryAction:
    """Represents a recovery action to be taken."""
    
    strategy: RecoveryStrategy
    target: str  # Service name or component identifier
    priority: RecoveryPriority
    description: str
    action_func: Callable[[], Any]
    rollback_func: Optional[Callable[[], Any]] = None
    max_attempts: int = 3
    timeout: float = 30.0
    dependencies: List[str] = field(default_factory=list)
    
    # Execution tracking
    attempts: int = 0
    last_attempt: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_error: Optional[str] = None


@dataclass
class RecoveryPlan:
    """A plan containing multiple recovery actions."""
    
    name: str
    description: str
    actions: List[RecoveryAction] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    # Execution tracking
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    success: bool = False
    error_message: Optional[str] = None


class FallbackProvider:
    """
    Provides fallback implementations for failed services.
    
    Maintains a registry of fallback implementations that can be used
    when primary services fail or are unavailable.
    """
    
    def __init__(self):
        self._fallbacks: Dict[str, Dict[str, Any]] = {}
        self._active_fallbacks: Set[str] = set()
        self._lock = threading.RLock()
    
    def register_fallback(
        self,
        service_name: str,
        fallback_impl: Any,
        capabilities: Optional[List[str]] = None,
        priority: int = 0
    ) -> None:
        """
        Register a fallback implementation for a service.
        
        Args:
            service_name: Name of the service
            fallback_impl: Fallback implementation
            capabilities: List of capabilities provided
            priority: Priority (higher = preferred)
        """
        with self._lock:
            if service_name not in self._fallbacks:
                self._fallbacks[service_name] = {}
            
            fallback_id = f"{service_name}_fallback_{len(self._fallbacks[service_name])}"
            
            self._fallbacks[service_name][fallback_id] = {
                'implementation': fallback_impl,
                'capabilities': capabilities or [],
                'priority': priority,
                'registered_at': datetime.now(),
                'usage_count': 0,
                'last_used': None
            }
            
            logger.info(f"Registered fallback for service '{service_name}': {fallback_id}")
    
    def get_fallback(self, service_name: str, required_capabilities: Optional[List[str]] = None) -> Optional[Any]:
        """
        Get the best fallback implementation for a service.
        
        Args:
            service_name: Name of the service
            required_capabilities: Required capabilities
            
        Returns:
            Fallback implementation or None
        """
        with self._lock:
            if service_name not in self._fallbacks:
                return None
            
            # Find compatible fallbacks
            compatible_fallbacks = []
            
            for fallback_id, fallback_info in self._fallbacks[service_name].items():
                if required_capabilities:
                    # Check if fallback provides required capabilities
                    fallback_caps = set(fallback_info['capabilities'])
                    required_caps = set(required_capabilities)
                    
                    if not required_caps.issubset(fallback_caps):
                        continue
                
                compatible_fallbacks.append((fallback_id, fallback_info))
            
            if not compatible_fallbacks:
                return None
            
            # Sort by priority (highest first)
            compatible_fallbacks.sort(key=lambda x: x[1]['priority'], reverse=True)
            
            # Use the highest priority fallback
            fallback_id, fallback_info = compatible_fallbacks[0]
            
            # Update usage statistics
            fallback_info['usage_count'] += 1
            fallback_info['last_used'] = datetime.now()
            
            # Track active fallback
            self._active_fallbacks.add(f"{service_name}:{fallback_id}")
            
            logger.info(f"Using fallback for service '{service_name}': {fallback_id}")
            
            return fallback_info['implementation']
    
    def release_fallback(self, service_name: str) -> None:
        """
        Release active fallback for a service.
        
        Args:
            service_name: Name of the service
        """
        with self._lock:
            # Remove all active fallbacks for this service
            to_remove = [fb for fb in self._active_fallbacks if fb.startswith(f"{service_name}:")]
            for fb in to_remove:
                self._active_fallbacks.discard(fb)
            
            logger.info(f"Released fallbacks for service '{service_name}'")
    
    def get_active_fallbacks(self) -> List[str]:
        """Get list of currently active fallbacks."""
        with self._lock:
            return list(self._active_fallbacks)
    
    def get_fallback_stats(self) -> Dict[str, Any]:
        """Get fallback usage statistics."""
        with self._lock:
            stats = {
                'total_fallbacks': sum(len(fallbacks) for fallbacks in self._fallbacks.values()),
                'active_fallbacks': len(self._active_fallbacks),
                'services_with_fallbacks': len(self._fallbacks),
                'fallback_details': {}
            }
            
            for service_name, fallbacks in self._fallbacks.items():
                stats['fallback_details'][service_name] = {
                    'count': len(fallbacks),
                    'total_usage': sum(fb['usage_count'] for fb in fallbacks.values()),
                    'last_used': max(
                        (fb['last_used'] for fb in fallbacks.values() if fb['last_used']),
                        default=None
                    )
                }
            
            return stats


class RecoveryOrchestrator:
    """
    Orchestrates recovery operations across the system.
    
    Coordinates recovery actions, manages dependencies, and provides
    comprehensive recovery monitoring and reporting.
    """
    
    def __init__(self, service_registry: Optional[ServiceRegistry] = None):
        self.service_registry = service_registry
        self.fallback_provider = FallbackProvider()
        
        # Recovery state
        self._recovery_plans: Dict[str, RecoveryPlan] = {}
        self._active_recoveries: Dict[str, RecoveryPlan] = {}
        self._recovery_history: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        
        # Configuration
        self.max_concurrent_recoveries = 3
        self.recovery_timeout = 300.0  # 5 minutes
        self.health_check_interval = 30.0
        
        # Monitoring
        self._recovery_stats = {
            'total_recoveries': 0,
            'successful_recoveries': 0,
            'failed_recoveries': 0,
            'average_recovery_time': 0.0,
            'last_recovery': None
        }
    
    def register_recovery_plan(self, plan: RecoveryPlan) -> None:
        """
        Register a recovery plan.
        
        Args:
            plan: Recovery plan to register
        """
        with self._lock:
            self._recovery_plans[plan.name] = plan
            logger.info(f"Registered recovery plan: {plan.name}")
    
    def create_recovery_action(
        self,
        strategy: RecoveryStrategy,
        target: str,
        description: str,
        action_func: Callable,
        priority: RecoveryPriority = RecoveryPriority.MEDIUM,
        **kwargs
    ) -> RecoveryAction:
        """
        Create a recovery action.
        
        Args:
            strategy: Recovery strategy
            target: Target service or component
            description: Action description
            action_func: Function to execute
            priority: Action priority
            **kwargs: Additional action parameters
            
        Returns:
            RecoveryAction instance
        """
        return RecoveryAction(
            strategy=strategy,
            target=target,
            priority=priority,
            description=description,
            action_func=action_func,
            **kwargs
        )
    
    async def execute_recovery_plan(self, plan_name: str) -> bool:
        """
        Execute a recovery plan.
        
        Args:
            plan_name: Name of the recovery plan
            
        Returns:
            True if recovery was successful
        """
        with self._lock:
            if plan_name not in self._recovery_plans:
                logger.error(f"Recovery plan not found: {plan_name}")
                return False
            
            plan = self._recovery_plans[plan_name]
            
            # Check if already running
            if plan_name in self._active_recoveries:
                logger.warning(f"Recovery plan already active: {plan_name}")
                return False
            
            # Check concurrent recovery limit
            if len(self._active_recoveries) >= self.max_concurrent_recoveries:
                logger.warning(f"Maximum concurrent recoveries reached, queuing: {plan_name}")
                return False
            
            # Mark as active
            self._active_recoveries[plan_name] = plan
            plan.started_at = datetime.now()
        
        logger.info(f"Starting recovery plan: {plan_name}")
        
        try:
            # Execute recovery actions
            success = await self._execute_recovery_actions(plan)
            
            # Update plan status
            plan.completed_at = datetime.now()
            plan.success = success
            
            # Update statistics
            self._update_recovery_stats(plan)
            
            # Add to history
            self._add_to_history(plan)
            
            if success:
                logger.info(f"Recovery plan completed successfully: {plan_name}")
            else:
                logger.error(f"Recovery plan failed: {plan_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Recovery plan execution failed: {plan_name}: {e}")
            plan.completed_at = datetime.now()
            plan.success = False
            plan.error_message = str(e)
            
            self._update_recovery_stats(plan)
            self._add_to_history(plan)
            
            return False
            
        finally:
            # Remove from active recoveries
            with self._lock:
                self._active_recoveries.pop(plan_name, None)
    
    async def auto_recover_service(self, service_name: str) -> bool:
        """
        Automatically recover a failed service.
        
        Args:
            service_name: Name of the service to recover
            
        Returns:
            True if recovery was successful
        """
        logger.info(f"Starting auto-recovery for service: {service_name}")
        
        # Create recovery plan
        plan = RecoveryPlan(
            name=f"auto_recovery_{service_name}",
            description=f"Automatic recovery for service {service_name}"
        )
        
        # Add restart action
        restart_action = self.create_recovery_action(
            strategy=RecoveryStrategy.RESTART,
            target=service_name,
            description=f"Restart service {service_name}",
            action_func=lambda: self._restart_service(service_name),
            priority=RecoveryPriority.HIGH
        )
        plan.actions.append(restart_action)
        
        # Add fallback action if restart fails
        fallback_action = self.create_recovery_action(
            strategy=RecoveryStrategy.FALLBACK,
            target=service_name,
            description=f"Use fallback for service {service_name}",
            action_func=lambda: self._activate_fallback(service_name),
            priority=RecoveryPriority.MEDIUM
        )
        plan.actions.append(fallback_action)
        
        # Register and execute plan
        self.register_recovery_plan(plan)
        return await self.execute_recovery_plan(plan.name)
    
    async def degrade_gracefully(self, service_name: str, capabilities: List[str]) -> bool:
        """
        Gracefully degrade a service by disabling non-essential capabilities.
        
        Args:
            service_name: Name of the service
            capabilities: Capabilities to disable
            
        Returns:
            True if degradation was successful
        """
        logger.info(f"Gracefully degrading service: {service_name}")
        
        try:
            if self.service_registry:
                service = self.service_registry.get_service(service_name)
                if service and hasattr(service, 'disable_capabilities'):
                    await service.disable_capabilities(capabilities)
                    logger.info(f"Disabled capabilities for {service_name}: {capabilities}")
                    return True
            
            logger.warning(f"Cannot degrade service {service_name}: not found or not supported")
            return False
            
        except Exception as e:
            logger.error(f"Failed to degrade service {service_name}: {e}")
            return False
    
    def get_recovery_stats(self) -> Dict[str, Any]:
        """Get recovery statistics."""
        with self._lock:
            return {
                **self._recovery_stats,
                'active_recoveries': len(self._active_recoveries),
                'registered_plans': len(self._recovery_plans),
                'fallback_stats': self.fallback_provider.get_fallback_stats()
            }
    
    def get_recovery_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recovery history."""
        with self._lock:
            return self._recovery_history[-limit:]
    
    def get_active_recoveries(self) -> Dict[str, Dict[str, Any]]:
        """Get currently active recovery operations."""
        with self._lock:
            return {
                name: {
                    'plan_name': plan.name,
                    'description': plan.description,
                    'started_at': plan.started_at.isoformat() if plan.started_at else None,
                    'actions_count': len(plan.actions),
                    'duration': (datetime.now() - plan.started_at).total_seconds() if plan.started_at else 0
                }
                for name, plan in self._active_recoveries.items()
            }
    
    # Private methods
    
    async def _execute_recovery_actions(self, plan: RecoveryPlan) -> bool:
        """Execute all actions in a recovery plan."""
        # Sort actions by priority (critical first)
        priority_order = {
            RecoveryPriority.CRITICAL: 0,
            RecoveryPriority.HIGH: 1,
            RecoveryPriority.MEDIUM: 2,
            RecoveryPriority.LOW: 3
        }
        
        sorted_actions = sorted(plan.actions, key=lambda a: priority_order[a.priority])
        
        for action in sorted_actions:
            success = await self._execute_recovery_action(action)
            
            if not success:
                logger.error(f"Recovery action failed: {action.description}")
                
                # For critical actions, fail the entire plan
                if action.priority == RecoveryPriority.CRITICAL:
                    return False
                
                # For other actions, continue with remaining actions
                continue
        
        return True
    
    async def _execute_recovery_action(self, action: RecoveryAction) -> bool:
        """Execute a single recovery action."""
        logger.info(f"Executing recovery action: {action.description}")
        
        action.attempts += 1
        action.last_attempt = datetime.now()
        
        try:
            # Execute the action with timeout
            if asyncio.iscoroutinefunction(action.action_func):
                await asyncio.wait_for(action.action_func(), timeout=action.timeout)
            else:
                # Run sync function in executor
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, action.action_func)
            
            action.last_success = datetime.now()
            logger.info(f"Recovery action succeeded: {action.description}")
            return True
            
        except asyncio.TimeoutError:
            error_msg = f"Recovery action timed out: {action.description}"
            logger.error(error_msg)
            action.last_error = error_msg
            
        except Exception as e:
            error_msg = f"Recovery action failed: {action.description}: {e}"
            logger.error(error_msg)
            action.last_error = str(e)
        
        # Retry if attempts remaining
        if action.attempts < action.max_attempts:
            logger.info(f"Retrying recovery action: {action.description} (attempt {action.attempts + 1}/{action.max_attempts})")
            await asyncio.sleep(1.0)  # Brief delay before retry
            return await self._execute_recovery_action(action)
        
        return False
    
    async def _restart_service(self, service_name: str) -> None:
        """Restart a service."""
        if not self.service_registry:
            raise IntegrationError("Service registry not available")
        
        logger.info(f"Restarting service: {service_name}")
        
        # Stop the service
        await self.service_registry.stop_service(service_name)
        
        # Wait a moment
        await asyncio.sleep(1.0)
        
        # Start the service
        success = await self.service_registry.start_service(service_name)
        
        if not success:
            raise IntegrationError(f"Failed to restart service: {service_name}")
    
    def _activate_fallback(self, service_name: str) -> None:
        """Activate fallback for a service."""
        logger.info(f"Activating fallback for service: {service_name}")
        
        fallback = self.fallback_provider.get_fallback(service_name)
        
        if not fallback:
            raise IntegrationError(f"No fallback available for service: {service_name}")
        
        # Register fallback as temporary service
        if self.service_registry:
            self.service_registry.register_service(
                name=f"{service_name}_fallback",
                instance=fallback,
                tags={'fallback', 'temporary'}
            )
    
    def _update_recovery_stats(self, plan: RecoveryPlan) -> None:
        """Update recovery statistics."""
        with self._lock:
            self._recovery_stats['total_recoveries'] += 1
            
            if plan.success:
                self._recovery_stats['successful_recoveries'] += 1
            else:
                self._recovery_stats['failed_recoveries'] += 1
            
            # Update average recovery time
            if plan.started_at and plan.completed_at:
                duration = (plan.completed_at - plan.started_at).total_seconds()
                total_time = (
                    self._recovery_stats['average_recovery_time'] * 
                    (self._recovery_stats['total_recoveries'] - 1) + duration
                )
                self._recovery_stats['average_recovery_time'] = total_time / self._recovery_stats['total_recoveries']
            
            self._recovery_stats['last_recovery'] = datetime.now().isoformat()
    
    def _add_to_history(self, plan: RecoveryPlan) -> None:
        """Add recovery plan to history."""
        with self._lock:
            history_entry = {
                'plan_name': plan.name,
                'description': plan.description,
                'started_at': plan.started_at.isoformat() if plan.started_at else None,
                'completed_at': plan.completed_at.isoformat() if plan.completed_at else None,
                'success': plan.success,
                'error_message': plan.error_message,
                'actions_count': len(plan.actions),
                'duration': (
                    (plan.completed_at - plan.started_at).total_seconds()
                    if plan.started_at and plan.completed_at else 0
                )
            }
            
            self._recovery_history.append(history_entry)
            
            # Keep only recent history (last 1000 entries)
            if len(self._recovery_history) > 1000:
                self._recovery_history = self._recovery_history[-1000:]


# Global recovery orchestrator instance
_recovery_orchestrator: Optional[RecoveryOrchestrator] = None


def get_recovery_orchestrator() -> RecoveryOrchestrator:
    """Get the global recovery orchestrator instance."""
    global _recovery_orchestrator
    if _recovery_orchestrator is None:
        _recovery_orchestrator = RecoveryOrchestrator()
    return _recovery_orchestrator


def register_fallback(
    service_name: str,
    fallback_impl: Any,
    capabilities: Optional[List[str]] = None,
    priority: int = 0
) -> None:
    """Register a fallback implementation for a service."""
    orchestrator = get_recovery_orchestrator()
    orchestrator.fallback_provider.register_fallback(
        service_name, fallback_impl, capabilities, priority
    )


async def auto_recover_service(service_name: str) -> bool:
    """Automatically recover a failed service."""
    orchestrator = get_recovery_orchestrator()
    return await orchestrator.auto_recover_service(service_name)


def get_recovery_stats() -> Dict[str, Any]:
    """Get recovery statistics."""
    orchestrator = get_recovery_orchestrator()
    return orchestrator.get_recovery_stats()

