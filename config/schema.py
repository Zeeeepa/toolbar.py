"""
Configuration schema definitions using Pydantic models.

This module defines the complete configuration schema for the Modern Taskbar
using Pydantic models for validation, serialization, and type safety.
The schema supports versioning, validation rules, and documentation.
"""

from typing import Any, Dict, List, Optional, Union, Set
from enum import Enum
from pathlib import Path
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, validator, root_validator
import re


class ConfigurationFormat(Enum):
    """Supported configuration file formats."""
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    INI = "ini"


class ValidationLevel(Enum):
    """Configuration validation levels."""
    STRICT = "strict"      # Fail on any validation error
    LENIENT = "lenient"    # Warn on validation errors but continue
    DISABLED = "disabled"  # Skip validation entirely


class MigrationStrategy(Enum):
    """Configuration migration strategies."""
    AUTOMATIC = "automatic"    # Migrate automatically
    PROMPT = "prompt"         # Prompt user for migration
    MANUAL = "manual"         # Require manual migration


class LogLevel(Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ThemeMode(Enum):
    """Theme modes."""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


class EditorType(Enum):
    """Supported editor types."""
    VSCODE = "vscode"
    NOTEPADPP = "notepad++"
    SUBLIME = "sublime"
    ATOM = "atom"
    VIM = "vim"
    NANO = "nano"
    GEDIT = "gedit"
    CUSTOM = "custom"


class AppearanceSettings(BaseModel):
    """Appearance and UI configuration."""
    
    theme_mode: ThemeMode = Field(
        default=ThemeMode.DARK,
        description="Theme mode (light, dark, or auto)"
    )
    
    transparency: int = Field(
        default=95,
        ge=10,
        le=100,
        description="Window transparency percentage (10-100)"
    )
    
    show_tooltips: bool = Field(
        default=True,
        description="Show tooltips on hover"
    )
    
    animation_enabled: bool = Field(
        default=True,
        description="Enable UI animations"
    )
    
    font_family: str = Field(
        default="Segoe UI",
        description="Font family for UI text"
    )
    
    font_size: int = Field(
        default=9,
        ge=8,
        le=16,
        description="Font size for UI text"
    )
    
    icon_size: int = Field(
        default=16,
        ge=12,
        le=32,
        description="Icon size in pixels"
    )
    
    window_width: Optional[int] = Field(
        default=None,
        ge=200,
        le=2000,
        description="Fixed window width (None for auto)"
    )
    
    window_height: Optional[int] = Field(
        default=None,
        ge=50,
        le=200,
        description="Fixed window height (None for auto)"
    )
    
    always_on_top: bool = Field(
        default=True,
        description="Keep window always on top"
    )
    
    custom_css: Optional[str] = Field(
        default=None,
        description="Custom CSS for theming"
    )


class BehaviorSettings(BaseModel):
    """Application behavior configuration."""
    
    auto_start: bool = Field(
        default=False,
        description="Start with Windows/system"
    )
    
    minimize_to_tray: bool = Field(
        default=True,
        description="Minimize to system tray"
    )
    
    confirm_exit: bool = Field(
        default=True,
        description="Confirm before exiting application"
    )
    
    auto_save_interval: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Auto-save interval in seconds"
    )
    
    backup_count: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of configuration backups to keep"
    )
    
    check_updates: bool = Field(
        default=True,
        description="Check for updates automatically"
    )
    
    update_channel: str = Field(
        default="stable",
        regex=r"^(stable|beta|alpha)$",
        description="Update channel (stable, beta, alpha)"
    )
    
    telemetry_enabled: bool = Field(
        default=False,
        description="Enable anonymous telemetry"
    )
    
    crash_reporting: bool = Field(
        default=True,
        description="Enable crash reporting"
    )


class ExecutionSettings(BaseModel):
    """Script execution configuration."""
    
    show_output: bool = Field(
        default=True,
        description="Show execution output in UI"
    )
    
    timeout_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="Default execution timeout in seconds"
    )
    
    max_concurrent: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum concurrent executions"
    )
    
    capture_output: bool = Field(
        default=True,
        description="Capture stdout and stderr"
    )
    
    working_directory: Optional[Path] = Field(
        default=None,
        description="Default working directory for executions"
    )
    
    environment_variables: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional environment variables"
    )
    
    shell_command: Optional[str] = Field(
        default=None,
        description="Custom shell command for script execution"
    )
    
    retry_attempts: int = Field(
        default=0,
        ge=0,
        le=5,
        description="Number of retry attempts on failure"
    )
    
    retry_delay: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Delay between retry attempts in seconds"
    )
    
    kill_on_timeout: bool = Field(
        default=True,
        description="Kill process on timeout"
    )
    
    preserve_output: bool = Field(
        default=True,
        description="Preserve output after execution"
    )


class EditorSettings(BaseModel):
    """Editor integration configuration."""
    
    default_editor: EditorType = Field(
        default=EditorType.VSCODE,
        description="Default editor for opening files"
    )
    
    editor_paths: Dict[str, Path] = Field(
        default_factory=dict,
        description="Custom paths to editor executables"
    )
    
    editor_arguments: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Additional arguments for each editor"
    )
    
    auto_detect_editors: bool = Field(
        default=True,
        description="Automatically detect installed editors"
    )
    
    open_in_new_window: bool = Field(
        default=False,
        description="Open files in new editor window"
    )
    
    jump_to_line: bool = Field(
        default=True,
        description="Support jumping to specific line numbers"
    )
    
    file_associations: Dict[str, EditorType] = Field(
        default_factory=dict,
        description="File extension to editor mappings"
    )


class PluginSettings(BaseModel):
    """Plugin system configuration."""
    
    enabled: bool = Field(
        default=True,
        description="Enable plugin system"
    )
    
    plugin_directories: List[Path] = Field(
        default_factory=lambda: [Path("plugins")],
        description="Directories to search for plugins"
    )
    
    auto_load: bool = Field(
        default=True,
        description="Automatically load plugins on startup"
    )
    
    sandbox_enabled: bool = Field(
        default=True,
        description="Enable plugin sandboxing for security"
    )
    
    allowed_plugins: Optional[List[str]] = Field(
        default=None,
        description="Whitelist of allowed plugins (None for all)"
    )
    
    blocked_plugins: List[str] = Field(
        default_factory=list,
        description="Blacklist of blocked plugins"
    )
    
    plugin_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Plugin initialization timeout in seconds"
    )
    
    max_memory_mb: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Maximum memory usage per plugin in MB"
    )
    
    enable_hot_reload: bool = Field(
        default=False,
        description="Enable hot reloading of plugins during development"
    )


class IntegrationSettings(BaseModel):
    """External integration configuration."""
    
    api_enabled: bool = Field(
        default=False,
        description="Enable REST API server"
    )
    
    api_port: int = Field(
        default=8080,
        ge=1024,
        le=65535,
        description="API server port"
    )
    
    api_host: str = Field(
        default="localhost",
        description="API server host"
    )
    
    api_key: Optional[str] = Field(
        default=None,
        description="API authentication key"
    )
    
    webhook_enabled: bool = Field(
        default=False,
        description="Enable webhook notifications"
    )
    
    webhook_urls: List[str] = Field(
        default_factory=list,
        description="Webhook URLs for notifications"
    )
    
    webhook_events: List[str] = Field(
        default_factory=lambda: ["execution_complete", "error"],
        description="Events to send via webhooks"
    )
    
    external_tools: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Configuration for external tool integrations"
    )
    
    oauth_providers: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="OAuth provider configurations"
    )


class MonitoringSettings(BaseModel):
    """Monitoring and logging configuration."""
    
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level"
    )
    
    log_file: Optional[Path] = Field(
        default=Path("logs/toolbar.log"),
        description="Log file path"
    )
    
    log_rotation: bool = Field(
        default=True,
        description="Enable log file rotation"
    )
    
    log_max_size_mb: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum log file size in MB"
    )
    
    log_backup_count: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of log backup files to keep"
    )
    
    metrics_enabled: bool = Field(
        default=True,
        description="Enable metrics collection"
    )
    
    metrics_interval: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Metrics collection interval in seconds"
    )
    
    health_check_interval: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Health check interval in seconds"
    )
    
    performance_monitoring: bool = Field(
        default=True,
        description="Enable performance monitoring"
    )
    
    memory_threshold_mb: int = Field(
        default=500,
        ge=100,
        le=2000,
        description="Memory usage threshold for alerts in MB"
    )
    
    cpu_threshold_percent: int = Field(
        default=80,
        ge=50,
        le=100,
        description="CPU usage threshold for alerts in percent"
    )


class SecuritySettings(BaseModel):
    """Security configuration."""
    
    encrypt_config: bool = Field(
        default=False,
        description="Encrypt configuration files"
    )
    
    config_password: Optional[str] = Field(
        default=None,
        description="Password for configuration encryption"
    )
    
    require_admin: bool = Field(
        default=False,
        description="Require administrator privileges"
    )
    
    allowed_file_types: List[str] = Field(
        default_factory=lambda: [".py", ".js", ".ts", ".bat", ".sh", ".ps1"],
        description="Allowed file types for execution"
    )
    
    blocked_commands: List[str] = Field(
        default_factory=list,
        description="Blocked commands/executables"
    )
    
    sandbox_execution: bool = Field(
        default=False,
        description="Execute scripts in sandbox environment"
    )
    
    network_access: bool = Field(
        default=True,
        description="Allow network access for scripts"
    )
    
    file_system_access: bool = Field(
        default=True,
        description="Allow file system access for scripts"
    )


class ToolbarConfiguration(BaseModel):
    """Main configuration model for the Modern Taskbar."""
    
    version: str = Field(
        default="2.0.0",
        description="Configuration schema version"
    )
    
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Configuration creation timestamp"
    )
    
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="Configuration last update timestamp"
    )
    
    # Configuration sections
    appearance: AppearanceSettings = Field(
        default_factory=AppearanceSettings,
        description="Appearance and UI settings"
    )
    
    behavior: BehaviorSettings = Field(
        default_factory=BehaviorSettings,
        description="Application behavior settings"
    )
    
    execution: ExecutionSettings = Field(
        default_factory=ExecutionSettings,
        description="Script execution settings"
    )
    
    editors: EditorSettings = Field(
        default_factory=EditorSettings,
        description="Editor integration settings"
    )
    
    plugins: PluginSettings = Field(
        default_factory=PluginSettings,
        description="Plugin system settings"
    )
    
    integrations: IntegrationSettings = Field(
        default_factory=IntegrationSettings,
        description="External integration settings"
    )
    
    monitoring: MonitoringSettings = Field(
        default_factory=MonitoringSettings,
        description="Monitoring and logging settings"
    )
    
    security: SecuritySettings = Field(
        default_factory=SecuritySettings,
        description="Security settings"
    )
    
    # Legacy support
    scripts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Legacy script configurations"
    )
    
    trays: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Legacy tray configurations"
    )
    
    # Custom settings
    custom: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom user-defined settings"
    )
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        validate_assignment = True
        extra = "forbid"
        schema_extra = {
            "example": {
                "version": "2.0.0",
                "appearance": {
                    "theme_mode": "dark",
                    "transparency": 95,
                    "show_tooltips": True
                },
                "behavior": {
                    "auto_start": False,
                    "confirm_exit": True
                },
                "execution": {
                    "timeout_seconds": 300,
                    "max_concurrent": 5
                }
            }
        }
    
    @validator('version')
    def validate_version(cls, v):
        """Validate version format."""
        if not re.match(r'^\d+\.\d+\.\d+$', v):
            raise ValueError('Version must be in format X.Y.Z')
        return v
    
    @root_validator
    def validate_configuration(cls, values):
        """Perform cross-field validation."""
        # Update timestamp on any change
        values['updated_at'] = datetime.now()
        
        # Validate plugin settings
        plugins = values.get('plugins')
        if plugins and plugins.enabled:
            if plugins.max_memory_mb < 10:
                raise ValueError('Plugin max memory must be at least 10MB')
        
        # Validate execution settings
        execution = values.get('execution')
        if execution:
            if execution.retry_attempts > 0 and execution.retry_delay <= 0:
                raise ValueError('Retry delay must be positive when retry attempts > 0')
        
        # Validate monitoring settings
        monitoring = values.get('monitoring')
        if monitoring:
            if monitoring.metrics_enabled and monitoring.metrics_interval < 10:
                raise ValueError('Metrics interval must be at least 10 seconds')
        
        return values
    
    def get_nested_value(self, path: str, default: Any = None) -> Any:
        """
        Get a nested configuration value using dot notation.
        
        Args:
            path: Dot-separated path (e.g., 'appearance.transparency')
            default: Default value if path not found
            
        Returns:
            Configuration value or default
        """
        try:
            value = self
            for part in path.split('.'):
                value = getattr(value, part)
            return value
        except (AttributeError, KeyError):
            return default
    
    def set_nested_value(self, path: str, value: Any) -> None:
        """
        Set a nested configuration value using dot notation.
        
        Args:
            path: Dot-separated path (e.g., 'appearance.transparency')
            value: Value to set
        """
        parts = path.split('.')
        obj = self
        
        # Navigate to parent object
        for part in parts[:-1]:
            obj = getattr(obj, part)
        
        # Set the final value
        setattr(obj, parts[-1], value)
        
        # Update timestamp
        self.updated_at = datetime.now()
    
    def to_legacy_format(self) -> Dict[str, Any]:
        """
        Convert to legacy configuration format for backward compatibility.
        
        Returns:
            Dictionary in legacy format
        """
        return {
            'transparency': self.appearance.transparency,
            'scripts': self.scripts,
            'trays': self.trays,
            'show_tooltips': self.appearance.show_tooltips,
            'auto_start': self.behavior.auto_start,
            'confirm_exit': self.behavior.confirm_exit,
            'timeout_seconds': self.execution.timeout_seconds,
            'max_concurrent': self.execution.max_concurrent,
            'default_editor': self.editors.default_editor.value,
        }
    
    @classmethod
    def from_legacy_format(cls, data: Dict[str, Any]) -> 'ToolbarConfiguration':
        """
        Create configuration from legacy format.
        
        Args:
            data: Legacy configuration dictionary
            
        Returns:
            ToolbarConfiguration instance
        """
        config = cls()
        
        # Map legacy fields to new structure
        if 'transparency' in data:
            config.appearance.transparency = data['transparency']
        
        if 'scripts' in data:
            config.scripts = data['scripts']
        
        if 'trays' in data:
            config.trays = data['trays']
        
        if 'show_tooltips' in data:
            config.appearance.show_tooltips = data['show_tooltips']
        
        if 'auto_start' in data:
            config.behavior.auto_start = data['auto_start']
        
        if 'confirm_exit' in data:
            config.behavior.confirm_exit = data['confirm_exit']
        
        if 'timeout_seconds' in data:
            config.execution.timeout_seconds = data['timeout_seconds']
        
        if 'max_concurrent' in data:
            config.execution.max_concurrent = data['max_concurrent']
        
        if 'default_editor' in data:
            try:
                config.editors.default_editor = EditorType(data['default_editor'])
            except ValueError:
                pass  # Keep default if invalid
        
        return config

