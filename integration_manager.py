"""
IntegrationManager - Advanced integration capabilities for external systems
"""
import json
import os
import subprocess
import threading
import time
import requests
import socket
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Union
from enum import Enum
import logging
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

class IntegrationType(Enum):
    """Types of integrations supported"""
    REST_API = "rest_api"
    WEBHOOK = "webhook"
    DATABASE = "database"
    FILE_SYSTEM = "file_system"
    COMMAND_LINE = "command_line"
    SOCKET = "socket"
    MESSAGE_QUEUE = "message_queue"
    CUSTOM = "custom"

class IntegrationStatus(Enum):
    """Integration connection status"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    TIMEOUT = "timeout"

class IntegrationConfig:
    """Configuration for an integration"""
    def __init__(self, name: str, integration_type: IntegrationType, 
                 config: Dict, enabled: bool = True):
        self.name = name
        self.integration_type = integration_type
        self.config = config
        self.enabled = enabled
        self.created_at = datetime.now()
        self.last_used = None
        self.status = IntegrationStatus.DISCONNECTED
        self.error_count = 0
        self.success_count = 0

class IntegrationResult:
    """Result of an integration operation"""
    def __init__(self, success: bool, data: Any = None, error: str = None,
                 response_time: float = 0.0, status_code: int = None):
        self.success = success
        self.data = data
        self.error = error
        self.response_time = response_time
        self.status_code = status_code
        self.timestamp = datetime.now()

class BaseIntegration:
    """Base class for all integrations"""
    def __init__(self, config: IntegrationConfig):
        self.config = config
        self.connection = None
        self.last_health_check = None
        
    def connect(self) -> bool:
        """Establish connection to the integration"""
        raise NotImplementedError
    
    def disconnect(self):
        """Close connection to the integration"""
        raise NotImplementedError
    
    def health_check(self) -> bool:
        """Check if the integration is healthy"""
        raise NotImplementedError
    
    def execute(self, operation: str, params: Dict = None) -> IntegrationResult:
        """Execute an operation on the integration"""
        raise NotImplementedError

class RestApiIntegration(BaseIntegration):
    """REST API integration"""
    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self.session = requests.Session()
        self.base_url = config.config.get('base_url', '')
        self.headers = config.config.get('headers', {})
        self.timeout = config.config.get('timeout', 30)
        
        # Setup authentication
        auth_config = config.config.get('auth', {})
        if auth_config.get('type') == 'bearer':
            self.headers['Authorization'] = f"Bearer {auth_config.get('token')}"
        elif auth_config.get('type') == 'basic':
            self.session.auth = (auth_config.get('username'), auth_config.get('password'))
        elif auth_config.get('type') == 'api_key':
            key_name = auth_config.get('key_name', 'X-API-Key')
            self.headers[key_name] = auth_config.get('api_key')
    
    def connect(self) -> bool:
        try:
            self.config.status = IntegrationStatus.CONNECTING
            response = self.session.get(f"{self.base_url}/health", 
                                      headers=self.headers, timeout=self.timeout)
            if response.status_code == 200:
                self.config.status = IntegrationStatus.CONNECTED
                return True
            else:
                self.config.status = IntegrationStatus.ERROR
                return False
        except Exception as e:
            logger.error(f"Failed to connect to REST API {self.config.name}: {e}")
            self.config.status = IntegrationStatus.ERROR
            return False
    
    def disconnect(self):
        try:
            self.session.close()
            self.config.status = IntegrationStatus.DISCONNECTED
        except Exception as e:
            logger.error(f"Error disconnecting from REST API {self.config.name}: {e}")
    
    def health_check(self) -> bool:
        try:
            response = self.session.get(f"{self.base_url}/health", 
                                      headers=self.headers, timeout=5)
            self.last_health_check = datetime.now()
            return response.status_code == 200
        except Exception:
            return False
    
    def execute(self, operation: str, params: Dict = None) -> IntegrationResult:
        start_time = time.time()
        try:
            method = params.get('method', 'GET').upper()
            endpoint = params.get('endpoint', '')
            data = params.get('data')
            
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            
            if method == 'GET':
                response = self.session.get(url, headers=self.headers, 
                                          params=data, timeout=self.timeout)
            elif method == 'POST':
                response = self.session.post(url, headers=self.headers, 
                                           json=data, timeout=self.timeout)
            elif method == 'PUT':
                response = self.session.put(url, headers=self.headers, 
                                          json=data, timeout=self.timeout)
            elif method == 'DELETE':
                response = self.session.delete(url, headers=self.headers, 
                                             timeout=self.timeout)
            else:
                return IntegrationResult(False, error=f"Unsupported method: {method}")
            
            response_time = time.time() - start_time
            
            if response.status_code < 400:
                self.config.success_count += 1
                try:
                    data = response.json()
                except:
                    data = response.text
                return IntegrationResult(True, data=data, 
                                       response_time=response_time,
                                       status_code=response.status_code)
            else:
                self.config.error_count += 1
                return IntegrationResult(False, error=f"HTTP {response.status_code}: {response.text}",
                                       response_time=response_time,
                                       status_code=response.status_code)
                
        except Exception as e:
            response_time = time.time() - start_time
            self.config.error_count += 1
            return IntegrationResult(False, error=str(e), response_time=response_time)

class WebhookIntegration(BaseIntegration):
    """Webhook integration for receiving HTTP callbacks"""
    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self.server = None
        self.port = config.config.get('port', 8080)
        self.path = config.config.get('path', '/webhook')
        self.callbacks = []
        
    def connect(self) -> bool:
        try:
            from http.server import HTTPServer, BaseHTTPRequestHandler
            
            class WebhookHandler(BaseHTTPRequestHandler):
                def __init__(self, integration, *args, **kwargs):
                    self.integration = integration
                    super().__init__(*args, **kwargs)
                
                def do_POST(self):
                    if self.path == self.integration.path:
                        content_length = int(self.headers['Content-Length'])
                        post_data = self.rfile.read(content_length)
                        
                        try:
                            data = json.loads(post_data.decode('utf-8'))
                        except:
                            data = post_data.decode('utf-8')
                        
                        # Notify callbacks
                        for callback in self.integration.callbacks:
                            try:
                                callback(data)
                            except Exception as e:
                                logger.error(f"Webhook callback error: {e}")
                        
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(b'OK')
                    else:
                        self.send_response(404)
                        self.end_headers()
            
            handler = lambda *args, **kwargs: WebhookHandler(self, *args, **kwargs)
            self.server = HTTPServer(('localhost', self.port), handler)
            
            # Start server in background thread
            server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            server_thread.start()
            
            self.config.status = IntegrationStatus.CONNECTED
            return True
            
        except Exception as e:
            logger.error(f"Failed to start webhook server: {e}")
            self.config.status = IntegrationStatus.ERROR
            return False
    
    def disconnect(self):
        try:
            if self.server:
                self.server.shutdown()
                self.server = None
            self.config.status = IntegrationStatus.DISCONNECTED
        except Exception as e:
            logger.error(f"Error stopping webhook server: {e}")
    
    def health_check(self) -> bool:
        try:
            # Check if port is still bound
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', self.port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def add_callback(self, callback: Callable):
        """Add callback for webhook events"""
        self.callbacks.append(callback)
    
    def execute(self, operation: str, params: Dict = None) -> IntegrationResult:
        # Webhooks are passive, so execution means checking status
        if operation == 'status':
            return IntegrationResult(True, data={
                'port': self.port,
                'path': self.path,
                'callbacks': len(self.callbacks),
                'status': self.config.status.value
            })
        return IntegrationResult(False, error="Unsupported operation for webhook")

class CommandLineIntegration(BaseIntegration):
    """Command line integration for executing system commands"""
    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self.working_dir = config.config.get('working_dir', os.getcwd())
        self.environment = config.config.get('environment', {})
        self.timeout = config.config.get('timeout', 30)
        
    def connect(self) -> bool:
        # Test connection by running a simple command
        try:
            result = subprocess.run(['echo', 'test'], capture_output=True, 
                                  text=True, timeout=5, cwd=self.working_dir)
            self.config.status = IntegrationStatus.CONNECTED
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Command line integration test failed: {e}")
            self.config.status = IntegrationStatus.ERROR
            return False
    
    def disconnect(self):
        self.config.status = IntegrationStatus.DISCONNECTED
    
    def health_check(self) -> bool:
        return self.connect()  # Same as connection test
    
    def execute(self, operation: str, params: Dict = None) -> IntegrationResult:
        start_time = time.time()
        try:
            command = params.get('command', operation)
            args = params.get('args', [])
            shell = params.get('shell', False)
            
            if isinstance(command, str) and not shell:
                command = command.split()
            
            if args:
                if isinstance(command, list):
                    command.extend(args)
                else:
                    command += ' ' + ' '.join(args)
            
            env = os.environ.copy()
            env.update(self.environment)
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.working_dir,
                env=env,
                shell=shell
            )
            
            response_time = time.time() - start_time
            
            if result.returncode == 0:
                self.config.success_count += 1
                return IntegrationResult(True, data={
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'return_code': result.returncode
                }, response_time=response_time)
            else:
                self.config.error_count += 1
                return IntegrationResult(False, error=result.stderr or result.stdout,
                                       response_time=response_time)
                
        except subprocess.TimeoutExpired:
            response_time = time.time() - start_time
            self.config.error_count += 1
            return IntegrationResult(False, error="Command timed out", 
                                   response_time=response_time)
        except Exception as e:
            response_time = time.time() - start_time
            self.config.error_count += 1
            return IntegrationResult(False, error=str(e), response_time=response_time)

class FileSystemIntegration(BaseIntegration):
    """File system integration for file operations"""
    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self.base_path = Path(config.config.get('base_path', '.'))
        self.allowed_extensions = config.config.get('allowed_extensions', [])
        self.max_file_size = config.config.get('max_file_size', 10 * 1024 * 1024)  # 10MB
        
    def connect(self) -> bool:
        try:
            if self.base_path.exists() and self.base_path.is_dir():
                self.config.status = IntegrationStatus.CONNECTED
                return True
            else:
                self.config.status = IntegrationStatus.ERROR
                return False
        except Exception as e:
            logger.error(f"File system integration failed: {e}")
            self.config.status = IntegrationStatus.ERROR
            return False
    
    def disconnect(self):
        self.config.status = IntegrationStatus.DISCONNECTED
    
    def health_check(self) -> bool:
        return self.base_path.exists() and self.base_path.is_dir()
    
    def execute(self, operation: str, params: Dict = None) -> IntegrationResult:
        start_time = time.time()
        try:
            if operation == 'read':
                return self._read_file(params)
            elif operation == 'write':
                return self._write_file(params)
            elif operation == 'list':
                return self._list_files(params)
            elif operation == 'delete':
                return self._delete_file(params)
            elif operation == 'exists':
                return self._file_exists(params)
            else:
                return IntegrationResult(False, error=f"Unsupported operation: {operation}")
                
        except Exception as e:
            response_time = time.time() - start_time
            self.config.error_count += 1
            return IntegrationResult(False, error=str(e), response_time=response_time)
    
    def _read_file(self, params: Dict) -> IntegrationResult:
        start_time = time.time()
        file_path = self.base_path / params.get('path', '')
        
        if not self._is_allowed_path(file_path):
            return IntegrationResult(False, error="Path not allowed")
        
        if not file_path.exists():
            return IntegrationResult(False, error="File not found")
        
        if file_path.stat().st_size > self.max_file_size:
            return IntegrationResult(False, error="File too large")
        
        try:
            content = file_path.read_text(encoding='utf-8')
            response_time = time.time() - start_time
            self.config.success_count += 1
            return IntegrationResult(True, data=content, response_time=response_time)
        except UnicodeDecodeError:
            # Try binary read
            content = file_path.read_bytes()
            response_time = time.time() - start_time
            self.config.success_count += 1
            return IntegrationResult(True, data=content, response_time=response_time)
    
    def _write_file(self, params: Dict) -> IntegrationResult:
        start_time = time.time()
        file_path = self.base_path / params.get('path', '')
        content = params.get('content', '')
        
        if not self._is_allowed_path(file_path):
            return IntegrationResult(False, error="Path not allowed")
        
        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        if isinstance(content, str):
            file_path.write_text(content, encoding='utf-8')
        else:
            file_path.write_bytes(content)
        
        response_time = time.time() - start_time
        self.config.success_count += 1
        return IntegrationResult(True, data=f"Written {len(content)} bytes", 
                               response_time=response_time)
    
    def _list_files(self, params: Dict) -> IntegrationResult:
        start_time = time.time()
        dir_path = self.base_path / params.get('path', '')
        pattern = params.get('pattern', '*')
        
        if not self._is_allowed_path(dir_path):
            return IntegrationResult(False, error="Path not allowed")
        
        if not dir_path.exists() or not dir_path.is_dir():
            return IntegrationResult(False, error="Directory not found")
        
        files = []
        for file_path in dir_path.glob(pattern):
            files.append({
                'name': file_path.name,
                'path': str(file_path.relative_to(self.base_path)),
                'size': file_path.stat().st_size if file_path.is_file() else 0,
                'is_dir': file_path.is_dir(),
                'modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            })
        
        response_time = time.time() - start_time
        self.config.success_count += 1
        return IntegrationResult(True, data=files, response_time=response_time)
    
    def _delete_file(self, params: Dict) -> IntegrationResult:
        start_time = time.time()
        file_path = self.base_path / params.get('path', '')
        
        if not self._is_allowed_path(file_path):
            return IntegrationResult(False, error="Path not allowed")
        
        if not file_path.exists():
            return IntegrationResult(False, error="File not found")
        
        if file_path.is_dir():
            file_path.rmdir()
        else:
            file_path.unlink()
        
        response_time = time.time() - start_time
        self.config.success_count += 1
        return IntegrationResult(True, data="File deleted", response_time=response_time)
    
    def _file_exists(self, params: Dict) -> IntegrationResult:
        start_time = time.time()
        file_path = self.base_path / params.get('path', '')
        
        exists = file_path.exists()
        response_time = time.time() - start_time
        self.config.success_count += 1
        return IntegrationResult(True, data=exists, response_time=response_time)
    
    def _is_allowed_path(self, path: Path) -> bool:
        """Check if path is allowed (within base path and has allowed extension)"""
        try:
            # Check if path is within base path
            path.resolve().relative_to(self.base_path.resolve())
            
            # Check extension if specified
            if self.allowed_extensions and path.suffix.lower() not in self.allowed_extensions:
                return False
            
            return True
        except ValueError:
            return False

class IntegrationManager:
    """Manages all integrations and their lifecycle"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.config_file = self.data_dir / "integrations.json"
        self.integrations: Dict[str, BaseIntegration] = {}
        self.integration_configs: Dict[str, IntegrationConfig] = {}
        
        # Integration type mapping
        self.integration_classes = {
            IntegrationType.REST_API: RestApiIntegration,
            IntegrationType.WEBHOOK: WebhookIntegration,
            IntegrationType.COMMAND_LINE: CommandLineIntegration,
            IntegrationType.FILE_SYSTEM: FileSystemIntegration,
        }
        
        # Health check thread
        self.health_check_interval = 60  # seconds
        self.health_check_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self.health_check_running = True
        
        # Load configurations
        self._load_configurations()
        
        # Start health checking
        self.health_check_thread.start()
    
    def add_integration(self, name: str, integration_type: IntegrationType, 
                       config: Dict, enabled: bool = True) -> bool:
        """Add a new integration"""
        try:
            integration_config = IntegrationConfig(name, integration_type, config, enabled)
            self.integration_configs[name] = integration_config
            
            if enabled:
                self._create_integration(integration_config)
            
            self._save_configurations()
            return True
            
        except Exception as e:
            logger.error(f"Failed to add integration {name}: {e}")
            return False
    
    def remove_integration(self, name: str) -> bool:
        """Remove an integration"""
        try:
            if name in self.integrations:
                self.integrations[name].disconnect()
                del self.integrations[name]
            
            if name in self.integration_configs:
                del self.integration_configs[name]
            
            self._save_configurations()
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove integration {name}: {e}")
            return False
    
    def enable_integration(self, name: str) -> bool:
        """Enable an integration"""
        try:
            if name not in self.integration_configs:
                return False
            
            config = self.integration_configs[name]
            config.enabled = True
            
            if name not in self.integrations:
                self._create_integration(config)
            
            self._save_configurations()
            return True
            
        except Exception as e:
            logger.error(f"Failed to enable integration {name}: {e}")
            return False
    
    def disable_integration(self, name: str) -> bool:
        """Disable an integration"""
        try:
            if name in self.integrations:
                self.integrations[name].disconnect()
                del self.integrations[name]
            
            if name in self.integration_configs:
                self.integration_configs[name].enabled = False
            
            self._save_configurations()
            return True
            
        except Exception as e:
            logger.error(f"Failed to disable integration {name}: {e}")
            return False
    
    def execute_integration(self, name: str, operation: str, 
                          params: Dict = None) -> Optional[IntegrationResult]:
        """Execute an operation on an integration"""
        try:
            if name not in self.integrations:
                return IntegrationResult(False, error=f"Integration {name} not found or disabled")
            
            integration = self.integrations[name]
            result = integration.execute(operation, params or {})
            
            # Update last used timestamp
            integration.config.last_used = datetime.now()
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to execute operation {operation} on {name}: {e}")
            return IntegrationResult(False, error=str(e))
    
    def get_integration_status(self, name: str) -> Optional[Dict]:
        """Get status information for an integration"""
        try:
            if name not in self.integration_configs:
                return None
            
            config = self.integration_configs[name]
            integration = self.integrations.get(name)
            
            return {
                'name': config.name,
                'type': config.integration_type.value,
                'enabled': config.enabled,
                'status': config.status.value,
                'created_at': config.created_at.isoformat(),
                'last_used': config.last_used.isoformat() if config.last_used else None,
                'error_count': config.error_count,
                'success_count': config.success_count,
                'connected': integration is not None and config.status == IntegrationStatus.CONNECTED,
                'last_health_check': integration.last_health_check.isoformat() if integration and integration.last_health_check else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get status for integration {name}: {e}")
            return None
    
    def get_all_integrations(self) -> List[Dict]:
        """Get status for all integrations"""
        return [self.get_integration_status(name) for name in self.integration_configs.keys()]
    
    def test_integration(self, name: str) -> bool:
        """Test an integration connection"""
        try:
            if name not in self.integrations:
                return False
            
            return self.integrations[name].health_check()
            
        except Exception as e:
            logger.error(f"Failed to test integration {name}: {e}")
            return False
    
    def _create_integration(self, config: IntegrationConfig):
        """Create an integration instance"""
        try:
            integration_class = self.integration_classes.get(config.integration_type)
            if not integration_class:
                logger.error(f"Unsupported integration type: {config.integration_type}")
                return
            
            integration = integration_class(config)
            if integration.connect():
                self.integrations[config.name] = integration
                logger.info(f"Successfully created integration: {config.name}")
            else:
                logger.error(f"Failed to connect integration: {config.name}")
                
        except Exception as e:
            logger.error(f"Failed to create integration {config.name}: {e}")
    
    def _health_check_loop(self):
        """Background health check loop"""
        while self.health_check_running:
            try:
                for name, integration in list(self.integrations.items()):
                    try:
                        if integration.health_check():
                            integration.config.status = IntegrationStatus.CONNECTED
                        else:
                            integration.config.status = IntegrationStatus.ERROR
                            logger.warning(f"Health check failed for integration: {name}")
                    except Exception as e:
                        logger.error(f"Health check error for {name}: {e}")
                        integration.config.status = IntegrationStatus.ERROR
                
                time.sleep(self.health_check_interval)
                
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                time.sleep(self.health_check_interval)
    
    def _load_configurations(self):
        """Load integration configurations from file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for item in data:
                    config = IntegrationConfig(
                        name=item['name'],
                        integration_type=IntegrationType(item['type']),
                        config=item['config'],
                        enabled=item.get('enabled', True)
                    )
                    config.created_at = datetime.fromisoformat(item.get('created_at', datetime.now().isoformat()))
                    config.error_count = item.get('error_count', 0)
                    config.success_count = item.get('success_count', 0)
                    
                    self.integration_configs[config.name] = config
                    
                    if config.enabled:
                        self._create_integration(config)
                
                logger.info(f"Loaded {len(self.integration_configs)} integration configurations")
                
        except Exception as e:
            logger.error(f"Failed to load integration configurations: {e}")
    
    def _save_configurations(self):
        """Save integration configurations to file"""
        try:
            data = []
            for config in self.integration_configs.values():
                data.append({
                    'name': config.name,
                    'type': config.integration_type.value,
                    'config': config.config,
                    'enabled': config.enabled,
                    'created_at': config.created_at.isoformat(),
                    'error_count': config.error_count,
                    'success_count': config.success_count
                })
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Failed to save integration configurations: {e}")
    
    def shutdown(self):
        """Shutdown the integration manager"""
        try:
            self.health_check_running = False
            
            for integration in self.integrations.values():
                try:
                    integration.disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting integration: {e}")
            
            self.integrations.clear()
            logger.info("Integration manager shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during integration manager shutdown: {e}")
    
    def export_integration_report(self, file_path: str) -> bool:
        """Export integration status report"""
        try:
            report = {
                'generated_at': datetime.now().isoformat(),
                'total_integrations': len(self.integration_configs),
                'active_integrations': len(self.integrations),
                'integrations': self.get_all_integrations()
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Integration report exported to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export integration report: {e}")
            return False
