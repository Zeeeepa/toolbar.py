"""
Comprehensive exception hierarchy for the Modern Taskbar system.

This module defines a structured exception hierarchy that provides:
- Clear error categorization and classification
- Rich error context and metadata
- Error recovery guidance and suggestions
- Structured logging integration
- Exception chaining and root cause analysis

The exception hierarchy follows the principle of specific exceptions
for specific error conditions, enabling precise error handling and
recovery strategies throughout the system.
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from enum import Enum


class ErrorSeverity(Enum):
    """Enumeration of error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Enumeration of error categories."""
    CONFIGURATION = "configuration"
    EXECUTION = "execution"
    PLUGIN = "plugin"
    UI = "ui"
    INTEGRATION = "integration"
    NETWORK = "network"
    FILESYSTEM = "filesystem"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RESOURCE = "resource"
    TIMEOUT = "timeout"


class ToolbarException(Exception):
    """
    Base exception class for all Modern Taskbar exceptions.
    
    Provides rich error context, categorization, and recovery guidance.
    All custom exceptions in the system should inherit from this class.
    """
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.CONFIGURATION,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
        recoverable: bool = True,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.error_code = error_code or self._generate_error_code()
        self.context = context or {}
        self.suggestions = suggestions or []
        self.recoverable = recoverable
        self.cause = cause
        self.timestamp = datetime.now()
        
        # Chain the cause if provided
        if cause:
            self.__cause__ = cause
    
    def _generate_error_code(self) -> str:
        """Generate a unique error code based on exception type and category."""
        class_name = self.__class__.__name__
        category_code = self.category.value.upper()[:3]
        return f"{category_code}_{class_name.upper()}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging and serialization."""
        return {
            'error_code': self.error_code,
            'message': self.message,
            'category': self.category.value,
            'severity': self.severity.value,
            'context': self.context,
            'suggestions': self.suggestions,
            'recoverable': self.recoverable,
            'timestamp': self.timestamp.isoformat(),
            'exception_type': self.__class__.__name__,
            'cause': str(self.cause) if self.cause else None
        }
    
    def add_context(self, key: str, value: Any) -> 'ToolbarException':
        """Add context information to the exception."""
        self.context[key] = value
        return self
    
    def add_suggestion(self, suggestion: str) -> 'ToolbarException':
        """Add a recovery suggestion to the exception."""
        if suggestion not in self.suggestions:
            self.suggestions.append(suggestion)
        return self
    
    def __str__(self) -> str:
        """String representation with rich context."""
        parts = [f"[{self.error_code}] {self.message}"]
        
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"Context: {context_str}")
        
        if self.suggestions:
            suggestions_str = "; ".join(self.suggestions)
            parts.append(f"Suggestions: {suggestions_str}")
        
        return " | ".join(parts)


class ConfigurationError(ToolbarException):
    """
    Exception raised for configuration-related errors.
    
    This includes invalid configuration values, missing required settings,
    configuration file parsing errors, and validation failures.
    """
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_value: Optional[Any] = None,
        expected_type: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.CONFIGURATION,
            **kwargs
        )
        
        if config_key:
            self.add_context('config_key', config_key)
        if config_value is not None:
            self.add_context('config_value', config_value)
        if expected_type:
            self.add_context('expected_type', expected_type)
        
        # Add common suggestions
        self.add_suggestion("Check configuration file syntax and values")
        self.add_suggestion("Verify all required configuration keys are present")


class ValidationError(ToolbarException):
    """
    Exception raised for data validation errors.
    
    This includes schema validation failures, input validation errors,
    and constraint violations.
    """
    
    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        field_value: Optional[Any] = None,
        validation_rule: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.VALIDATION,
            **kwargs
        )
        
        if field_name:
            self.add_context('field_name', field_name)
        if field_value is not None:
            self.add_context('field_value', field_value)
        if validation_rule:
            self.add_context('validation_rule', validation_rule)
        
        self.add_suggestion("Check input data format and constraints")


class ExecutionError(ToolbarException):
    """
    Exception raised for script execution errors.
    
    This includes process execution failures, timeout errors,
    and runtime exceptions during script execution.
    """
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        exit_code: Optional[int] = None,
        command: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.EXECUTION,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        
        if file_path:
            self.add_context('file_path', file_path)
        if exit_code is not None:
            self.add_context('exit_code', exit_code)
        if command:
            self.add_context('command', ' '.join(command))
        
        self.add_suggestion("Check script syntax and dependencies")
        self.add_suggestion("Verify file permissions and accessibility")


class PluginError(ToolbarException):
    """
    Exception raised for plugin-related errors.
    
    This includes plugin loading failures, dependency resolution errors,
    and plugin lifecycle management issues.
    """
    
    def __init__(
        self,
        message: str,
        plugin_name: Optional[str] = None,
        plugin_version: Optional[str] = None,
        missing_dependencies: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.PLUGIN,
            **kwargs
        )
        
        if plugin_name:
            self.add_context('plugin_name', plugin_name)
        if plugin_version:
            self.add_context('plugin_version', plugin_version)
        if missing_dependencies:
            self.add_context('missing_dependencies', missing_dependencies)
        
        self.add_suggestion("Check plugin compatibility and dependencies")
        self.add_suggestion("Verify plugin installation and configuration")


class IntegrationError(ToolbarException):
    """
    Exception raised for external integration errors.
    
    This includes API communication failures, authentication errors,
    and external service unavailability.
    """
    
    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None,
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.INTEGRATION,
            **kwargs
        )
        
        if service_name:
            self.add_context('service_name', service_name)
        if endpoint:
            self.add_context('endpoint', endpoint)
        if status_code:
            self.add_context('status_code', status_code)
        
        self.add_suggestion("Check network connectivity and service availability")
        self.add_suggestion("Verify authentication credentials and permissions")


class UIError(ToolbarException):
    """
    Exception raised for UI-related errors.
    
    This includes widget creation failures, event handling errors,
    and UI state management issues.
    """
    
    def __init__(
        self,
        message: str,
        component_name: Optional[str] = None,
        widget_type: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.UI,
            **kwargs
        )
        
        if component_name:
            self.add_context('component_name', component_name)
        if widget_type:
            self.add_context('widget_type', widget_type)
        
        self.add_suggestion("Check UI component initialization and dependencies")


class NetworkError(ToolbarException):
    """
    Exception raised for network-related errors.
    
    This includes connection failures, timeout errors,
    and network configuration issues.
    """
    
    def __init__(
        self,
        message: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
        timeout: Optional[float] = None,
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.NETWORK,
            **kwargs
        )
        
        if host:
            self.add_context('host', host)
        if port:
            self.add_context('port', port)
        if timeout:
            self.add_context('timeout', timeout)
        
        self.add_suggestion("Check network connectivity and firewall settings")
        self.add_suggestion("Verify host and port configuration")


class FileSystemError(ToolbarException):
    """
    Exception raised for file system errors.
    
    This includes file access errors, permission issues,
    and disk space problems.
    """
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.FILESYSTEM,
            **kwargs
        )
        
        if file_path:
            self.add_context('file_path', file_path)
        if operation:
            self.add_context('operation', operation)
        
        self.add_suggestion("Check file permissions and accessibility")
        self.add_suggestion("Verify disk space and file system integrity")


class TimeoutError(ToolbarException):
    """
    Exception raised for timeout-related errors.
    
    This includes operation timeouts, network timeouts,
    and execution timeouts.
    """
    
    def __init__(
        self,
        message: str,
        timeout_duration: Optional[float] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        
        if timeout_duration:
            self.add_context('timeout_duration', timeout_duration)
        if operation:
            self.add_context('operation', operation)
        
        self.add_suggestion("Increase timeout duration if appropriate")
        self.add_suggestion("Check system performance and resource availability")


class ResourceError(ToolbarException):
    """
    Exception raised for resource-related errors.
    
    This includes memory exhaustion, CPU overload,
    and resource allocation failures.
    """
    
    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        current_usage: Optional[str] = None,
        limit: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.RESOURCE,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        
        if resource_type:
            self.add_context('resource_type', resource_type)
        if current_usage:
            self.add_context('current_usage', current_usage)
        if limit:
            self.add_context('limit', limit)
        
        self.add_suggestion("Check system resource usage and availability")
        self.add_suggestion("Consider increasing resource limits or optimizing usage")


class AuthenticationError(ToolbarException):
    """
    Exception raised for authentication errors.
    
    This includes invalid credentials, expired tokens,
    and authentication service failures.
    """
    
    def __init__(
        self,
        message: str,
        auth_method: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        
        if auth_method:
            self.add_context('auth_method', auth_method)
        
        self.add_suggestion("Verify authentication credentials")
        self.add_suggestion("Check if authentication tokens need renewal")


class AuthorizationError(ToolbarException):
    """
    Exception raised for authorization errors.
    
    This includes insufficient permissions, access denied,
    and role-based access control failures.
    """
    
    def __init__(
        self,
        message: str,
        required_permission: Optional[str] = None,
        user_role: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.AUTHORIZATION,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        
        if required_permission:
            self.add_context('required_permission', required_permission)
        if user_role:
            self.add_context('user_role', user_role)
        
        self.add_suggestion("Check user permissions and role assignments")
        self.add_suggestion("Contact administrator for access rights")


# Exception utilities

def create_exception_from_dict(data: Dict[str, Any]) -> ToolbarException:
    """
    Create an exception instance from a dictionary representation.
    
    Useful for deserializing exceptions from logs or network messages.
    """
    exception_type = data.get('exception_type', 'ToolbarException')
    message = data.get('message', 'Unknown error')
    
    # Map exception types to classes
    exception_classes = {
        'ToolbarException': ToolbarException,
        'ConfigurationError': ConfigurationError,
        'ValidationError': ValidationError,
        'ExecutionError': ExecutionError,
        'PluginError': PluginError,
        'IntegrationError': IntegrationError,
        'UIError': UIError,
        'NetworkError': NetworkError,
        'FileSystemError': FileSystemError,
        'TimeoutError': TimeoutError,
        'ResourceError': ResourceError,
        'AuthenticationError': AuthenticationError,
        'AuthorizationError': AuthorizationError,
    }
    
    exception_class = exception_classes.get(exception_type, ToolbarException)
    
    # Create exception with basic parameters
    exception = exception_class(
        message=message,
        category=ErrorCategory(data.get('category', 'configuration')),
        severity=ErrorSeverity(data.get('severity', 'medium')),
        error_code=data.get('error_code'),
        context=data.get('context', {}),
        suggestions=data.get('suggestions', []),
        recoverable=data.get('recoverable', True)
    )
    
    return exception


def format_exception_for_user(exception: ToolbarException) -> str:
    """
    Format an exception for user-friendly display.
    
    Provides a clean, actionable error message without technical details.
    """
    message = exception.message
    
    if exception.suggestions:
        suggestions = "\n".join(f"• {suggestion}" for suggestion in exception.suggestions[:3])
        message += f"\n\nSuggestions:\n{suggestions}"
    
    return message


def is_recoverable_error(exception: Exception) -> bool:
    """
    Check if an error is recoverable.
    
    Returns True if the error can potentially be recovered from
    through retry or user action.
    """
    if isinstance(exception, ToolbarException):
        return exception.recoverable
    
    # Default heuristics for standard exceptions
    recoverable_types = (
        ConnectionError,
        TimeoutError,
        FileNotFoundError,
        PermissionError,
    )
    
    return isinstance(exception, recoverable_types)

