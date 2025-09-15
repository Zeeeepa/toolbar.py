"""
Retry mechanisms and resilience patterns for the Modern Taskbar system.

This module provides comprehensive retry functionality with:
- Exponential backoff with jitter
- Configurable retry policies and conditions
- Circuit breaker integration
- Retry statistics and monitoring
- Async and sync retry decorators
- Custom retry strategies for different scenarios
"""

import asyncio
import functools
import logging
import random
import time
from typing import Any, Callable, Dict, List, Optional, Type, Union, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import threading

from .exceptions import ToolbarException, TimeoutError, NetworkError, IntegrationError

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategy types."""
    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIBONACCI_BACKOFF = "fibonacci_backoff"
    CUSTOM = "custom"


class StopCondition(Enum):
    """Conditions for stopping retries."""
    MAX_ATTEMPTS = "max_attempts"
    MAX_DURATION = "max_duration"
    SUCCESS = "success"
    FATAL_ERROR = "fatal_error"


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    jitter: bool = True
    jitter_range: float = 0.1
    backoff_multiplier: float = 2.0
    max_duration: Optional[float] = None
    
    # Exception handling
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        NetworkError,
        IntegrationError,
    )
    fatal_exceptions: Tuple[Type[Exception], ...] = (
        KeyboardInterrupt,
        SystemExit,
        MemoryError,
    )
    
    # Callbacks
    on_retry: Optional[Callable[[int, Exception, float], None]] = None
    on_success: Optional[Callable[[int, float], None]] = None
    on_failure: Optional[Callable[[Exception, int, float], None]] = None
    
    # Custom strategy function
    custom_delay_func: Optional[Callable[[int, float], float]] = None


@dataclass
class RetryAttempt:
    """Information about a retry attempt."""
    
    attempt_number: int
    start_time: datetime
    end_time: Optional[datetime] = None
    exception: Optional[Exception] = None
    delay_before: float = 0.0
    success: bool = False
    
    @property
    def duration(self) -> float:
        """Get attempt duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


@dataclass
class RetryResult:
    """Result of a retry operation."""
    
    success: bool
    result: Any = None
    exception: Optional[Exception] = None
    attempts: List[RetryAttempt] = field(default_factory=list)
    total_duration: float = 0.0
    stop_reason: StopCondition = StopCondition.SUCCESS
    
    @property
    def attempt_count(self) -> int:
        """Get total number of attempts."""
        return len(self.attempts)
    
    @property
    def last_attempt(self) -> Optional[RetryAttempt]:
        """Get the last retry attempt."""
        return self.attempts[-1] if self.attempts else None


class RetryManager:
    """
    Manages retry operations with comprehensive statistics and monitoring.
    
    Provides retry functionality with configurable policies, statistics
    tracking, and integration with circuit breakers and monitoring systems.
    """
    
    def __init__(self):
        self._statistics: Dict[str, Dict[str, Any]] = {}
        self._active_retries: Dict[str, RetryResult] = {}
        self._lock = threading.RLock()
        
        # Fibonacci sequence cache for fibonacci backoff
        self._fibonacci_cache = [1, 1]
    
    async def retry_async(
        self,
        func: Callable,
        *args,
        policy: Optional[RetryPolicy] = None,
        operation_name: Optional[str] = None,
        **kwargs
    ) -> RetryResult:
        """
        Retry an async function with the specified policy.
        
        Args:
            func: Async function to retry
            *args: Function arguments
            policy: Retry policy (uses default if None)
            operation_name: Name for statistics tracking
            **kwargs: Function keyword arguments
            
        Returns:
            RetryResult with operation outcome
        """
        policy = policy or RetryPolicy()
        operation_name = operation_name or func.__name__
        
        result = RetryResult()
        start_time = datetime.now()
        
        # Track active retry
        retry_id = f"{operation_name}_{id(result)}"
        with self._lock:
            self._active_retries[retry_id] = result
        
        try:
            for attempt_num in range(1, policy.max_attempts + 1):
                attempt = RetryAttempt(
                    attempt_number=attempt_num,
                    start_time=datetime.now()
                )
                
                try:
                    # Execute the function
                    if asyncio.iscoroutinefunction(func):
                        attempt_result = await func(*args, **kwargs)
                    else:
                        attempt_result = func(*args, **kwargs)
                    
                    # Success!
                    attempt.end_time = datetime.now()
                    attempt.success = True
                    result.attempts.append(attempt)
                    result.success = True
                    result.result = attempt_result
                    result.stop_reason = StopCondition.SUCCESS
                    
                    # Call success callback
                    if policy.on_success:
                        try:
                            policy.on_success(attempt_num, attempt.duration)
                        except Exception as e:
                            logger.warning(f"Error in retry success callback: {e}")
                    
                    break
                    
                except Exception as e:
                    attempt.end_time = datetime.now()
                    attempt.exception = e
                    result.attempts.append(attempt)
                    
                    # Check if this is a fatal exception
                    if isinstance(e, policy.fatal_exceptions):
                        logger.error(f"Fatal exception in {operation_name}: {e}")
                        result.exception = e
                        result.stop_reason = StopCondition.FATAL_ERROR
                        break
                    
                    # Check if this is a retryable exception
                    if not isinstance(e, policy.retryable_exceptions):
                        logger.error(f"Non-retryable exception in {operation_name}: {e}")
                        result.exception = e
                        result.stop_reason = StopCondition.FATAL_ERROR
                        break
                    
                    # Check max duration
                    elapsed = (datetime.now() - start_time).total_seconds()
                    if policy.max_duration and elapsed >= policy.max_duration:
                        logger.warning(f"Max duration exceeded for {operation_name}")
                        result.exception = e
                        result.stop_reason = StopCondition.MAX_DURATION
                        break
                    
                    # Calculate delay for next attempt
                    if attempt_num < policy.max_attempts:
                        delay = self._calculate_delay(attempt_num, policy)
                        attempt.delay_before = delay
                        
                        logger.info(
                            f"Retry {attempt_num}/{policy.max_attempts} for {operation_name} "
                            f"after {delay:.2f}s delay. Error: {e}"
                        )
                        
                        # Call retry callback
                        if policy.on_retry:
                            try:
                                policy.on_retry(attempt_num, e, delay)
                            except Exception as callback_error:
                                logger.warning(f"Error in retry callback: {callback_error}")
                        
                        # Wait before next attempt
                        await asyncio.sleep(delay)
                    else:
                        # Max attempts reached
                        logger.error(f"Max attempts reached for {operation_name}: {e}")
                        result.exception = e
                        result.stop_reason = StopCondition.MAX_ATTEMPTS
            
            # Calculate total duration
            result.total_duration = (datetime.now() - start_time).total_seconds()
            
            # Call failure callback if operation failed
            if not result.success and policy.on_failure:
                try:
                    policy.on_failure(result.exception, result.attempt_count, result.total_duration)
                except Exception as e:
                    logger.warning(f"Error in retry failure callback: {e}")
            
            # Update statistics
            self._update_statistics(operation_name, result)
            
            return result
            
        finally:
            # Remove from active retries
            with self._lock:
                self._active_retries.pop(retry_id, None)
    
    def retry_sync(
        self,
        func: Callable,
        *args,
        policy: Optional[RetryPolicy] = None,
        operation_name: Optional[str] = None,
        **kwargs
    ) -> RetryResult:
        """
        Retry a synchronous function with the specified policy.
        
        Args:
            func: Function to retry
            *args: Function arguments
            policy: Retry policy (uses default if None)
            operation_name: Name for statistics tracking
            **kwargs: Function keyword arguments
            
        Returns:
            RetryResult with operation outcome
        """
        policy = policy or RetryPolicy()
        operation_name = operation_name or func.__name__
        
        result = RetryResult()
        start_time = datetime.now()
        
        # Track active retry
        retry_id = f"{operation_name}_{id(result)}"
        with self._lock:
            self._active_retries[retry_id] = result
        
        try:
            for attempt_num in range(1, policy.max_attempts + 1):
                attempt = RetryAttempt(
                    attempt_number=attempt_num,
                    start_time=datetime.now()
                )
                
                try:
                    # Execute the function
                    attempt_result = func(*args, **kwargs)
                    
                    # Success!
                    attempt.end_time = datetime.now()
                    attempt.success = True
                    result.attempts.append(attempt)
                    result.success = True
                    result.result = attempt_result
                    result.stop_reason = StopCondition.SUCCESS
                    
                    # Call success callback
                    if policy.on_success:
                        try:
                            policy.on_success(attempt_num, attempt.duration)
                        except Exception as e:
                            logger.warning(f"Error in retry success callback: {e}")
                    
                    break
                    
                except Exception as e:
                    attempt.end_time = datetime.now()
                    attempt.exception = e
                    result.attempts.append(attempt)
                    
                    # Check if this is a fatal exception
                    if isinstance(e, policy.fatal_exceptions):
                        logger.error(f"Fatal exception in {operation_name}: {e}")
                        result.exception = e
                        result.stop_reason = StopCondition.FATAL_ERROR
                        break
                    
                    # Check if this is a retryable exception
                    if not isinstance(e, policy.retryable_exceptions):
                        logger.error(f"Non-retryable exception in {operation_name}: {e}")
                        result.exception = e
                        result.stop_reason = StopCondition.FATAL_ERROR
                        break
                    
                    # Check max duration
                    elapsed = (datetime.now() - start_time).total_seconds()
                    if policy.max_duration and elapsed >= policy.max_duration:
                        logger.warning(f"Max duration exceeded for {operation_name}")
                        result.exception = e
                        result.stop_reason = StopCondition.MAX_DURATION
                        break
                    
                    # Calculate delay for next attempt
                    if attempt_num < policy.max_attempts:
                        delay = self._calculate_delay(attempt_num, policy)
                        attempt.delay_before = delay
                        
                        logger.info(
                            f"Retry {attempt_num}/{policy.max_attempts} for {operation_name} "
                            f"after {delay:.2f}s delay. Error: {e}"
                        )
                        
                        # Call retry callback
                        if policy.on_retry:
                            try:
                                policy.on_retry(attempt_num, e, delay)
                            except Exception as callback_error:
                                logger.warning(f"Error in retry callback: {callback_error}")
                        
                        # Wait before next attempt
                        time.sleep(delay)
                    else:
                        # Max attempts reached
                        logger.error(f"Max attempts reached for {operation_name}: {e}")
                        result.exception = e
                        result.stop_reason = StopCondition.MAX_ATTEMPTS
            
            # Calculate total duration
            result.total_duration = (datetime.now() - start_time).total_seconds()
            
            # Call failure callback if operation failed
            if not result.success and policy.on_failure:
                try:
                    policy.on_failure(result.exception, result.attempt_count, result.total_duration)
                except Exception as e:
                    logger.warning(f"Error in retry failure callback: {e}")
            
            # Update statistics
            self._update_statistics(operation_name, result)
            
            return result
            
        finally:
            # Remove from active retries
            with self._lock:
                self._active_retries.pop(retry_id, None)
    
    def get_statistics(self, operation_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get retry statistics.
        
        Args:
            operation_name: Specific operation name (None for all)
            
        Returns:
            Statistics dictionary
        """
        with self._lock:
            if operation_name:
                return self._statistics.get(operation_name, {})
            else:
                return self._statistics.copy()
    
    def get_active_retries(self) -> Dict[str, RetryResult]:
        """
        Get currently active retry operations.
        
        Returns:
            Dictionary of active retry operations
        """
        with self._lock:
            return self._active_retries.copy()
    
    def reset_statistics(self, operation_name: Optional[str] = None) -> None:
        """
        Reset retry statistics.
        
        Args:
            operation_name: Specific operation name (None for all)
        """
        with self._lock:
            if operation_name:
                self._statistics.pop(operation_name, None)
            else:
                self._statistics.clear()
    
    # Private methods
    
    def _calculate_delay(self, attempt_num: int, policy: RetryPolicy) -> float:
        """Calculate delay before next retry attempt."""
        if policy.strategy == RetryStrategy.FIXED_DELAY:
            delay = policy.base_delay
            
        elif policy.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = policy.base_delay * (policy.backoff_multiplier ** (attempt_num - 1))
            
        elif policy.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = policy.base_delay * attempt_num
            
        elif policy.strategy == RetryStrategy.FIBONACCI_BACKOFF:
            delay = policy.base_delay * self._get_fibonacci(attempt_num)
            
        elif policy.strategy == RetryStrategy.CUSTOM and policy.custom_delay_func:
            delay = policy.custom_delay_func(attempt_num, policy.base_delay)
            
        else:
            # Default to exponential backoff
            delay = policy.base_delay * (policy.backoff_multiplier ** (attempt_num - 1))
        
        # Apply max delay limit
        delay = min(delay, policy.max_delay)
        
        # Apply jitter if enabled
        if policy.jitter:
            jitter_amount = delay * policy.jitter_range
            delay += random.uniform(-jitter_amount, jitter_amount)
            delay = max(0, delay)  # Ensure non-negative
        
        return delay
    
    def _get_fibonacci(self, n: int) -> int:
        """Get nth Fibonacci number (cached)."""
        while len(self._fibonacci_cache) <= n:
            next_fib = self._fibonacci_cache[-1] + self._fibonacci_cache[-2]
            self._fibonacci_cache.append(next_fib)
        
        return self._fibonacci_cache[n - 1] if n > 0 else 1
    
    def _update_statistics(self, operation_name: str, result: RetryResult) -> None:
        """Update retry statistics for an operation."""
        with self._lock:
            if operation_name not in self._statistics:
                self._statistics[operation_name] = {
                    'total_operations': 0,
                    'successful_operations': 0,
                    'failed_operations': 0,
                    'total_attempts': 0,
                    'total_duration': 0.0,
                    'avg_attempts': 0.0,
                    'avg_duration': 0.0,
                    'success_rate': 0.0,
                    'last_operation': None,
                    'stop_reasons': {}
                }
            
            stats = self._statistics[operation_name]
            
            # Update counters
            stats['total_operations'] += 1
            stats['total_attempts'] += result.attempt_count
            stats['total_duration'] += result.total_duration
            
            if result.success:
                stats['successful_operations'] += 1
            else:
                stats['failed_operations'] += 1
            
            # Update stop reason counts
            stop_reason = result.stop_reason.value
            stats['stop_reasons'][stop_reason] = stats['stop_reasons'].get(stop_reason, 0) + 1
            
            # Calculate averages
            stats['avg_attempts'] = stats['total_attempts'] / stats['total_operations']
            stats['avg_duration'] = stats['total_duration'] / stats['total_operations']
            stats['success_rate'] = (stats['successful_operations'] / stats['total_operations']) * 100
            
            # Update last operation info
            stats['last_operation'] = {
                'timestamp': datetime.now().isoformat(),
                'success': result.success,
                'attempts': result.attempt_count,
                'duration': result.total_duration,
                'stop_reason': stop_reason
            }


# Global retry manager instance
_retry_manager = RetryManager()


# Decorator functions

def retry_async(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        ConnectionError, TimeoutError, NetworkError, IntegrationError
    ),
    **policy_kwargs
):
    """
    Decorator for async functions with retry capability.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay between retries
        strategy: Retry strategy to use
        retryable_exceptions: Exceptions that should trigger retries
        **policy_kwargs: Additional retry policy parameters
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            policy = RetryPolicy(
                max_attempts=max_attempts,
                base_delay=base_delay,
                strategy=strategy,
                retryable_exceptions=retryable_exceptions,
                **policy_kwargs
            )
            
            result = await _retry_manager.retry_async(
                func, *args, policy=policy, operation_name=func.__name__, **kwargs
            )
            
            if result.success:
                return result.result
            else:
                raise result.exception or Exception("Retry failed")
        
        return wrapper
    return decorator


def retry_sync(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        ConnectionError, TimeoutError, NetworkError, IntegrationError
    ),
    **policy_kwargs
):
    """
    Decorator for synchronous functions with retry capability.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay between retries
        strategy: Retry strategy to use
        retryable_exceptions: Exceptions that should trigger retries
        **policy_kwargs: Additional retry policy parameters
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            policy = RetryPolicy(
                max_attempts=max_attempts,
                base_delay=base_delay,
                strategy=strategy,
                retryable_exceptions=retryable_exceptions,
                **policy_kwargs
            )
            
            result = _retry_manager.retry_sync(
                func, *args, policy=policy, operation_name=func.__name__, **kwargs
            )
            
            if result.success:
                return result.result
            else:
                raise result.exception or Exception("Retry failed")
        
        return wrapper
    return decorator


# Utility functions

def get_retry_statistics(operation_name: Optional[str] = None) -> Dict[str, Any]:
    """Get retry statistics from the global retry manager."""
    return _retry_manager.get_statistics(operation_name)


def reset_retry_statistics(operation_name: Optional[str] = None) -> None:
    """Reset retry statistics in the global retry manager."""
    _retry_manager.reset_statistics(operation_name)


def get_active_retries() -> Dict[str, RetryResult]:
    """Get currently active retry operations."""
    return _retry_manager.get_active_retries()

