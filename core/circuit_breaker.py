"""
Circuit Breaker pattern implementation for the Modern Taskbar system.

This module provides circuit breaker functionality for fault tolerance with:
- Automatic failure detection and recovery
- Configurable failure thresholds and timeouts
- Half-open state for gradual recovery testing
- Integration with retry mechanisms
- Comprehensive monitoring and statistics
- Thread-safe operations for concurrent access
"""

import asyncio
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Type, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field

from .exceptions import ToolbarException, IntegrationError, NetworkError

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation, requests pass through
    OPEN = "open"           # Circuit is open, requests fail immediately
    HALF_OPEN = "half_open" # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    
    # Failure detection
    failure_threshold: int = 5
    failure_rate_threshold: float = 0.5  # 50% failure rate
    minimum_requests: int = 10
    
    # Timing
    timeout_duration: float = 60.0  # Seconds to stay open
    half_open_max_calls: int = 3    # Max calls in half-open state
    
    # Exception handling
    failure_exceptions: tuple = (
        ConnectionError,
        TimeoutError,
        NetworkError,
        IntegrationError,
    )
    
    # Monitoring
    rolling_window_size: int = 100  # Number of recent calls to track
    
    # Callbacks
    on_state_change: Optional[Callable[[CircuitState, CircuitState], None]] = None
    on_failure: Optional[Callable[[Exception], None]] = None
    on_success: Optional[Callable[[], None]] = None


@dataclass
class CallResult:
    """Result of a circuit breaker call."""
    
    timestamp: datetime
    success: bool
    duration: float
    exception: Optional[Exception] = None


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""
    
    state: CircuitState
    failure_count: int = 0
    success_count: int = 0
    total_calls: int = 0
    failure_rate: float = 0.0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_changed_time: datetime = field(default_factory=datetime.now)
    time_in_current_state: float = 0.0
    recent_calls: List[CallResult] = field(default_factory=list)
    
    def update_metrics(self) -> None:
        """Update calculated metrics."""
        if self.total_calls > 0:
            self.failure_rate = self.failure_count / self.total_calls
        else:
            self.failure_rate = 0.0
        
        self.time_in_current_state = (datetime.now() - self.state_changed_time).total_seconds()


class CircuitBreaker:
    """
    Circuit breaker implementation for fault tolerance.
    
    Provides automatic failure detection and recovery with configurable
    thresholds and monitoring capabilities.
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        # State management
        self._state = CircuitState.CLOSED
        self._stats = CircuitBreakerStats(state=self._state)
        self._lock = threading.RLock()
        
        # Timing
        self._last_failure_time: Optional[datetime] = None
        self._state_changed_time = datetime.now()
        self._half_open_calls = 0
        
        logger.info(f"Circuit breaker '{name}' initialized in CLOSED state")
    
    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute an async function through the circuit breaker.
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            IntegrationError: If circuit is open
            Original exception: If function fails
        """
        # Check if call is allowed
        if not self._is_call_allowed():
            raise IntegrationError(
                f"Circuit breaker '{self.name}' is OPEN",
                service_name=self.name
            )
        
        start_time = datetime.now()
        
        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Record success
            duration = (datetime.now() - start_time).total_seconds()
            self._record_success(duration)
            
            return result
            
        except Exception as e:
            # Record failure
            duration = (datetime.now() - start_time).total_seconds()
            self._record_failure(e, duration)
            raise
    
    def call_sync(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a synchronous function through the circuit breaker.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            IntegrationError: If circuit is open
            Original exception: If function fails
        """
        # Check if call is allowed
        if not self._is_call_allowed():
            raise IntegrationError(
                f"Circuit breaker '{self.name}' is OPEN",
                service_name=self.name
            )
        
        start_time = datetime.now()
        
        try:
            # Execute the function
            result = func(*args, **kwargs)
            
            # Record success
            duration = (datetime.now() - start_time).total_seconds()
            self._record_success(duration)
            
            return result
            
        except Exception as e:
            # Record failure
            duration = (datetime.now() - start_time).total_seconds()
            self._record_failure(e, duration)
            raise
    
    def get_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        with self._lock:
            return self._state
    
    def get_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics."""
        with self._lock:
            stats_copy = CircuitBreakerStats(
                state=self._stats.state,
                failure_count=self._stats.failure_count,
                success_count=self._stats.success_count,
                total_calls=self._stats.total_calls,
                failure_rate=self._stats.failure_rate,
                last_failure_time=self._stats.last_failure_time,
                last_success_time=self._stats.last_success_time,
                state_changed_time=self._stats.state_changed_time,
                recent_calls=self._stats.recent_calls.copy()
            )
            stats_copy.update_metrics()
            return stats_copy
    
    def reset(self) -> None:
        """Reset circuit breaker to CLOSED state."""
        with self._lock:
            old_state = self._state
            self._state = CircuitState.CLOSED
            self._stats = CircuitBreakerStats(state=self._state)
            self._last_failure_time = None
            self._state_changed_time = datetime.now()
            self._half_open_calls = 0
            
            logger.info(f"Circuit breaker '{self.name}' reset to CLOSED state")
            
            # Notify state change
            if old_state != self._state and self.config.on_state_change:
                try:
                    self.config.on_state_change(old_state, self._state)
                except Exception as e:
                    logger.error(f"Error in state change callback: {e}")
    
    def force_open(self) -> None:
        """Force circuit breaker to OPEN state."""
        with self._lock:
            old_state = self._state
            self._state = CircuitState.OPEN
            self._stats.state = self._state
            self._state_changed_time = datetime.now()
            
            logger.warning(f"Circuit breaker '{self.name}' forced to OPEN state")
            
            # Notify state change
            if old_state != self._state and self.config.on_state_change:
                try:
                    self.config.on_state_change(old_state, self._state)
                except Exception as e:
                    logger.error(f"Error in state change callback: {e}")
    
    def is_healthy(self) -> bool:
        """Check if circuit breaker is in a healthy state."""
        with self._lock:
            return self._state == CircuitState.CLOSED
    
    # Private methods
    
    def _is_call_allowed(self) -> bool:
        """Check if a call is allowed through the circuit breaker."""
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            
            elif self._state == CircuitState.OPEN:
                # Check if timeout has elapsed
                if self._last_failure_time:
                    elapsed = (datetime.now() - self._last_failure_time).total_seconds()
                    if elapsed >= self.config.timeout_duration:
                        # Transition to half-open
                        self._transition_to_half_open()
                        return True
                
                return False
            
            elif self._state == CircuitState.HALF_OPEN:
                # Allow limited calls in half-open state
                return self._half_open_calls < self.config.half_open_max_calls
            
            return False
    
    def _record_success(self, duration: float) -> None:
        """Record a successful call."""
        with self._lock:
            now = datetime.now()
            
            # Update statistics
            self._stats.success_count += 1
            self._stats.total_calls += 1
            self._stats.last_success_time = now
            
            # Add to recent calls
            call_result = CallResult(
                timestamp=now,
                success=True,
                duration=duration
            )
            self._add_recent_call(call_result)
            
            # Handle state transitions
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                
                # Check if we should close the circuit
                if self._half_open_calls >= self.config.half_open_max_calls:
                    self._transition_to_closed()
            
            # Update metrics
            self._stats.update_metrics()
            
            # Call success callback
            if self.config.on_success:
                try:
                    self.config.on_success()
                except Exception as e:
                    logger.error(f"Error in success callback: {e}")
    
    def _record_failure(self, exception: Exception, duration: float) -> None:
        """Record a failed call."""
        with self._lock:
            now = datetime.now()
            
            # Check if this exception should be counted as a failure
            if not isinstance(exception, self.config.failure_exceptions):
                # Don't count this as a circuit breaker failure
                return
            
            # Update statistics
            self._stats.failure_count += 1
            self._stats.total_calls += 1
            self._stats.last_failure_time = now
            self._last_failure_time = now
            
            # Add to recent calls
            call_result = CallResult(
                timestamp=now,
                success=False,
                duration=duration,
                exception=exception
            )
            self._add_recent_call(call_result)
            
            # Handle state transitions
            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open state opens the circuit
                self._transition_to_open()
            elif self._state == CircuitState.CLOSED:
                # Check if we should open the circuit
                if self._should_open_circuit():
                    self._transition_to_open()
            
            # Update metrics
            self._stats.update_metrics()
            
            # Call failure callback
            if self.config.on_failure:
                try:
                    self.config.on_failure(exception)
                except Exception as e:
                    logger.error(f"Error in failure callback: {e}")
    
    def _should_open_circuit(self) -> bool:
        """Check if circuit should be opened based on failure criteria."""
        # Check minimum requests threshold
        if self._stats.total_calls < self.config.minimum_requests:
            return False
        
        # Check failure count threshold
        if self._stats.failure_count >= self.config.failure_threshold:
            return True
        
        # Check failure rate threshold
        if self._stats.failure_rate >= self.config.failure_rate_threshold:
            return True
        
        return False
    
    def _transition_to_open(self) -> None:
        """Transition circuit breaker to OPEN state."""
        old_state = self._state
        self._state = CircuitState.OPEN
        self._stats.state = self._state
        self._state_changed_time = datetime.now()
        self._half_open_calls = 0
        
        logger.warning(
            f"Circuit breaker '{self.name}' transitioned to OPEN state. "
            f"Failure rate: {self._stats.failure_rate:.2%}, "
            f"Failure count: {self._stats.failure_count}"
        )
        
        # Notify state change
        if old_state != self._state and self.config.on_state_change:
            try:
                self.config.on_state_change(old_state, self._state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")
    
    def _transition_to_half_open(self) -> None:
        """Transition circuit breaker to HALF_OPEN state."""
        old_state = self._state
        self._state = CircuitState.HALF_OPEN
        self._stats.state = self._state
        self._state_changed_time = datetime.now()
        self._half_open_calls = 0
        
        logger.info(f"Circuit breaker '{self.name}' transitioned to HALF_OPEN state")
        
        # Notify state change
        if old_state != self._state and self.config.on_state_change:
            try:
                self.config.on_state_change(old_state, self._state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")
    
    def _transition_to_closed(self) -> None:
        """Transition circuit breaker to CLOSED state."""
        old_state = self._state
        self._state = CircuitState.CLOSED
        self._stats.state = self._state
        self._state_changed_time = datetime.now()
        self._half_open_calls = 0
        
        # Reset failure counts for fresh start
        self._stats.failure_count = 0
        self._stats.success_count = 0
        self._stats.total_calls = 0
        
        logger.info(f"Circuit breaker '{self.name}' transitioned to CLOSED state")
        
        # Notify state change
        if old_state != self._state and self.config.on_state_change:
            try:
                self.config.on_state_change(old_state, self._state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")
    
    def _add_recent_call(self, call_result: CallResult) -> None:
        """Add a call result to the recent calls list."""
        self._stats.recent_calls.append(call_result)
        
        # Keep only the most recent calls
        if len(self._stats.recent_calls) > self.config.rolling_window_size:
            self._stats.recent_calls = self._stats.recent_calls[-self.config.rolling_window_size:]


class CircuitBreakerManager:
    """
    Manages multiple circuit breakers with centralized monitoring.
    
    Provides a registry of circuit breakers with health monitoring
    and statistics aggregation across all managed circuits.
    """
    
    def __init__(self):
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.RLock()
    
    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """
        Get existing circuit breaker or create a new one.
        
        Args:
            name: Circuit breaker name
            config: Configuration (uses default if None)
            
        Returns:
            CircuitBreaker instance
        """
        with self._lock:
            if name not in self._circuit_breakers:
                self._circuit_breakers[name] = CircuitBreaker(name, config)
                logger.info(f"Created new circuit breaker: {name}")
            
            return self._circuit_breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """
        Get circuit breaker by name.
        
        Args:
            name: Circuit breaker name
            
        Returns:
            CircuitBreaker instance or None if not found
        """
        with self._lock:
            return self._circuit_breakers.get(name)
    
    def remove(self, name: str) -> bool:
        """
        Remove circuit breaker by name.
        
        Args:
            name: Circuit breaker name
            
        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if name in self._circuit_breakers:
                del self._circuit_breakers[name]
                logger.info(f"Removed circuit breaker: {name}")
                return True
            return False
    
    def get_all_stats(self) -> Dict[str, CircuitBreakerStats]:
        """
        Get statistics for all circuit breakers.
        
        Returns:
            Dictionary mapping names to statistics
        """
        with self._lock:
            return {
                name: cb.get_stats()
                for name, cb in self._circuit_breakers.items()
            }
    
    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get health summary for all circuit breakers.
        
        Returns:
            Health summary dictionary
        """
        with self._lock:
            total_circuits = len(self._circuit_breakers)
            healthy_circuits = sum(1 for cb in self._circuit_breakers.values() if cb.is_healthy())
            
            return {
                'total_circuits': total_circuits,
                'healthy_circuits': healthy_circuits,
                'unhealthy_circuits': total_circuits - healthy_circuits,
                'health_percentage': (healthy_circuits / max(total_circuits, 1)) * 100,
                'circuit_states': {
                    name: cb.get_state().value
                    for name, cb in self._circuit_breakers.items()
                }
            }
    
    def reset_all(self) -> None:
        """Reset all circuit breakers to CLOSED state."""
        with self._lock:
            for cb in self._circuit_breakers.values():
                cb.reset()
            logger.info("Reset all circuit breakers")
    
    def get_circuit_names(self) -> List[str]:
        """Get list of all circuit breaker names."""
        with self._lock:
            return list(self._circuit_breakers.keys())


# Global circuit breaker manager
_circuit_manager = CircuitBreakerManager()


# Decorator functions

def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    timeout_duration: float = 60.0,
    failure_exceptions: tuple = (ConnectionError, TimeoutError, NetworkError, IntegrationError),
    **config_kwargs
):
    """
    Decorator to add circuit breaker protection to a function.
    
    Args:
        name: Circuit breaker name
        failure_threshold: Number of failures before opening
        timeout_duration: Seconds to stay open
        failure_exceptions: Exceptions that count as failures
        **config_kwargs: Additional configuration parameters
        
    Returns:
        Decorated function
    """
    def decorator(func):
        # Create circuit breaker configuration
        config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            timeout_duration=timeout_duration,
            failure_exceptions=failure_exceptions,
            **config_kwargs
        )
        
        # Get or create circuit breaker
        cb = _circuit_manager.get_or_create(name, config)
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await cb.call_async(func, *args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                return cb.call_sync(func, *args, **kwargs)
            return sync_wrapper
    
    return decorator


# Utility functions

def get_circuit_breaker(name: str) -> Optional[CircuitBreaker]:
    """Get circuit breaker by name from global manager."""
    return _circuit_manager.get(name)


def get_all_circuit_stats() -> Dict[str, CircuitBreakerStats]:
    """Get statistics for all circuit breakers."""
    return _circuit_manager.get_all_stats()


def get_circuit_health_summary() -> Dict[str, Any]:
    """Get health summary for all circuit breakers."""
    return _circuit_manager.get_health_summary()


def reset_all_circuits() -> None:
    """Reset all circuit breakers to CLOSED state."""
    _circuit_manager.reset_all()

