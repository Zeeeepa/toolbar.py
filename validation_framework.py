"""
ValidationFramework - Comprehensive validation and testing system
"""
import json
import os
import time
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Union, Tuple
from enum import Enum
import logging
import traceback
import inspect

logger = logging.getLogger(__name__)

class ValidationLevel(Enum):
    """Validation levels"""
    BASIC = "basic"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"
    STRESS = "stress"

class ValidationResult(Enum):
    """Validation result status"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIP = "skip"
    ERROR = "error"

class TestCategory(Enum):
    """Test categories"""
    UNIT = "unit"
    INTEGRATION = "integration"
    FUNCTIONAL = "functional"
    PERFORMANCE = "performance"
    SECURITY = "security"
    COMPATIBILITY = "compatibility"
    USABILITY = "usability"

class ValidationTest:
    """Individual validation test"""
    def __init__(self, name: str, description: str, category: TestCategory,
                 test_function: Callable, level: ValidationLevel = ValidationLevel.STANDARD,
                 timeout: float = 30.0, dependencies: List[str] = None):
        self.name = name
        self.description = description
        self.category = category
        self.test_function = test_function
        self.level = level
        self.timeout = timeout
        self.dependencies = dependencies or []
        self.result: Optional[ValidationResult] = None
        self.error_message: Optional[str] = None
        self.execution_time: float = 0.0
        self.output: str = ""
        self.timestamp: Optional[datetime] = None

class ValidationSuite:
    """Collection of validation tests"""
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.tests: List[ValidationTest] = []
        self.setup_function: Optional[Callable] = None
        self.teardown_function: Optional[Callable] = None
        
    def add_test(self, test: ValidationTest):
        """Add a test to the suite"""
        self.tests.append(test)
    
    def set_setup(self, setup_function: Callable):
        """Set setup function for the suite"""
        self.setup_function = setup_function
    
    def set_teardown(self, teardown_function: Callable):
        """Set teardown function for the suite"""
        self.teardown_function = teardown_function

class ValidationReport:
    """Comprehensive validation report"""
    def __init__(self, suite_name: str):
        self.suite_name = suite_name
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.warning_tests = 0
        self.skipped_tests = 0
        self.error_tests = 0
        self.test_results: List[Dict] = []
        self.system_info: Dict = {}
        self.performance_metrics: Dict = {}
        
    def add_test_result(self, test: ValidationTest):
        """Add test result to report"""
        self.test_results.append({
            'name': test.name,
            'description': test.description,
            'category': test.category.value,
            'level': test.level.value,
            'result': test.result.value if test.result else 'unknown',
            'execution_time': test.execution_time,
            'error_message': test.error_message,
            'output': test.output,
            'timestamp': test.timestamp.isoformat() if test.timestamp else None
        })
        
        # Update counters
        if test.result == ValidationResult.PASS:
            self.passed_tests += 1
        elif test.result == ValidationResult.FAIL:
            self.failed_tests += 1
        elif test.result == ValidationResult.WARNING:
            self.warning_tests += 1
        elif test.result == ValidationResult.SKIP:
            self.skipped_tests += 1
        elif test.result == ValidationResult.ERROR:
            self.error_tests += 1
    
    def finalize(self):
        """Finalize the report"""
        self.end_time = datetime.now()
        self.total_tests = len(self.test_results)
    
    def get_success_rate(self) -> float:
        """Get success rate percentage"""
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100
    
    def to_dict(self) -> Dict:
        """Convert report to dictionary"""
        return {
            'suite_name': self.suite_name,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': (self.end_time - self.start_time).total_seconds() if self.end_time else 0,
            'total_tests': self.total_tests,
            'passed_tests': self.passed_tests,
            'failed_tests': self.failed_tests,
            'warning_tests': self.warning_tests,
            'skipped_tests': self.skipped_tests,
            'error_tests': self.error_tests,
            'success_rate': self.get_success_rate(),
            'test_results': self.test_results,
            'system_info': self.system_info,
            'performance_metrics': self.performance_metrics
        }

class ValidationFramework:
    """Comprehensive validation and testing framework"""
    
    def __init__(self, data_dir: str = "data", report_dir: str = "reports"):
        self.data_dir = Path(data_dir)
        self.report_dir = Path(report_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.report_dir.mkdir(exist_ok=True)
        
        self.suites: Dict[str, ValidationSuite] = {}
        self.global_setup: Optional[Callable] = None
        self.global_teardown: Optional[Callable] = None
        
        # Execution context
        self.current_context: Dict = {}
        self.shared_resources: Dict = {}
        
        # Performance monitoring
        self.performance_data: Dict = {}
        
        # Register built-in test suites
        self._register_builtin_suites()
    
    def register_suite(self, suite: ValidationSuite):
        """Register a validation suite"""
        self.suites[suite.name] = suite
        logger.info(f"Registered validation suite: {suite.name}")
    
    def set_global_setup(self, setup_function: Callable):
        """Set global setup function"""
        self.global_setup = setup_function
    
    def set_global_teardown(self, teardown_function: Callable):
        """Set global teardown function"""
        self.global_teardown = teardown_function
    
    def run_suite(self, suite_name: str, level: ValidationLevel = ValidationLevel.STANDARD,
                  categories: List[TestCategory] = None) -> ValidationReport:
        """Run a validation suite"""
        if suite_name not in self.suites:
            raise ValueError(f"Suite '{suite_name}' not found")
        
        suite = self.suites[suite_name]
        report = ValidationReport(suite_name)
        
        try:
            # Collect system information
            report.system_info = self._collect_system_info()
            
            # Global setup
            if self.global_setup:
                self._execute_function(self.global_setup, "Global Setup")
            
            # Suite setup
            if suite.setup_function:
                self._execute_function(suite.setup_function, f"Suite Setup ({suite_name})")
            
            # Filter tests by level and categories
            tests_to_run = self._filter_tests(suite.tests, level, categories)
            
            # Sort tests by dependencies
            sorted_tests = self._sort_tests_by_dependencies(tests_to_run)
            
            # Execute tests
            for test in sorted_tests:
                self._execute_test(test, report)
            
        except Exception as e:
            logger.error(f"Error running suite {suite_name}: {e}")
        
        finally:
            try:
                # Suite teardown
                if suite.teardown_function:
                    self._execute_function(suite.teardown_function, f"Suite Teardown ({suite_name})")
                
                # Global teardown
                if self.global_teardown:
                    self._execute_function(self.global_teardown, "Global Teardown")
            except Exception as e:
                logger.error(f"Error in teardown: {e}")
            
            # Finalize report
            report.finalize()
        
        return report
    
    def run_all_suites(self, level: ValidationLevel = ValidationLevel.STANDARD,
                      categories: List[TestCategory] = None) -> Dict[str, ValidationReport]:
        """Run all validation suites"""
        reports = {}
        
        for suite_name in self.suites.keys():
            try:
                report = self.run_suite(suite_name, level, categories)
                reports[suite_name] = report
            except Exception as e:
                logger.error(f"Failed to run suite {suite_name}: {e}")
        
        return reports
    
    def _execute_test(self, test: ValidationTest, report: ValidationReport):
        """Execute a single test"""
        test.timestamp = datetime.now()
        start_time = time.time()
        
        try:
            logger.info(f"Running test: {test.name}")
            
            # Check dependencies
            if not self._check_dependencies(test, report):
                test.result = ValidationResult.SKIP
                test.error_message = "Dependencies not met"
                report.add_test_result(test)
                return
            
            # Execute test with timeout
            if test.timeout > 0:
                result = self._execute_with_timeout(test.test_function, test.timeout)
            else:
                result = test.test_function()
            
            # Process result
            if isinstance(result, bool):
                test.result = ValidationResult.PASS if result else ValidationResult.FAIL
            elif isinstance(result, ValidationResult):
                test.result = result
            elif isinstance(result, tuple) and len(result) == 2:
                test.result, test.output = result
            else:
                test.result = ValidationResult.PASS
                test.output = str(result) if result is not None else ""
            
        except TimeoutError:
            test.result = ValidationResult.ERROR
            test.error_message = f"Test timed out after {test.timeout} seconds"
        except Exception as e:
            test.result = ValidationResult.ERROR
            test.error_message = str(e)
            logger.error(f"Test {test.name} failed with error: {e}")
            logger.debug(traceback.format_exc())
        
        finally:
            test.execution_time = time.time() - start_time
            report.add_test_result(test)
    
    def _execute_with_timeout(self, function: Callable, timeout: float) -> Any:
        """Execute function with timeout"""
        result = [None]
        exception = [None]
        
        def target():
            try:
                result[0] = function()
            except Exception as e:
                exception[0] = e
        
        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout)
        
        if thread.is_alive():
            raise TimeoutError(f"Function timed out after {timeout} seconds")
        
        if exception[0]:
            raise exception[0]
        
        return result[0]
    
    def _execute_function(self, function: Callable, name: str):
        """Execute a setup/teardown function"""
        try:
            logger.info(f"Executing: {name}")
            function()
        except Exception as e:
            logger.error(f"Error in {name}: {e}")
            raise
    
    def _filter_tests(self, tests: List[ValidationTest], level: ValidationLevel,
                     categories: List[TestCategory] = None) -> List[ValidationTest]:
        """Filter tests by level and categories"""
        filtered_tests = []
        
        level_order = {
            ValidationLevel.BASIC: 1,
            ValidationLevel.STANDARD: 2,
            ValidationLevel.COMPREHENSIVE: 3,
            ValidationLevel.STRESS: 4
        }
        
        for test in tests:
            # Check level
            if level_order[test.level] > level_order[level]:
                continue
            
            # Check categories
            if categories and test.category not in categories:
                continue
            
            filtered_tests.append(test)
        
        return filtered_tests
    
    def _sort_tests_by_dependencies(self, tests: List[ValidationTest]) -> List[ValidationTest]:
        """Sort tests by dependencies using topological sort"""
        # Simple dependency resolution - can be enhanced
        sorted_tests = []
        remaining_tests = tests.copy()
        
        while remaining_tests:
            # Find tests with no unmet dependencies
            ready_tests = []
            for test in remaining_tests:
                dependencies_met = all(
                    any(completed_test.name == dep for completed_test in sorted_tests)
                    for dep in test.dependencies
                )
                if dependencies_met:
                    ready_tests.append(test)
            
            if not ready_tests:
                # Circular dependency or missing dependency
                logger.warning("Circular or missing dependencies detected, adding remaining tests")
                ready_tests = remaining_tests
            
            # Add ready tests to sorted list
            for test in ready_tests:
                sorted_tests.append(test)
                remaining_tests.remove(test)
        
        return sorted_tests
    
    def _check_dependencies(self, test: ValidationTest, report: ValidationReport) -> bool:
        """Check if test dependencies are met"""
        for dep in test.dependencies:
            # Check if dependency test passed
            dep_result = None
            for result in report.test_results:
                if result['name'] == dep:
                    dep_result = result
                    break
            
            if not dep_result or dep_result['result'] != 'pass':
                return False
        
        return True
    
    def _collect_system_info(self) -> Dict:
        """Collect system information"""
        try:
            import platform
            import psutil
            
            return {
                'platform': platform.platform(),
                'python_version': platform.python_version(),
                'cpu_count': psutil.cpu_count(),
                'memory_total': psutil.virtual_memory().total,
                'memory_available': psutil.virtual_memory().available,
                'disk_usage': psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:').percent,
                'timestamp': datetime.now().isoformat()
            }
        except ImportError:
            return {
                'platform': 'unknown',
                'python_version': 'unknown',
                'timestamp': datetime.now().isoformat()
            }
    
    def _register_builtin_suites(self):
        """Register built-in validation suites"""
        # Basic functionality suite
        basic_suite = ValidationSuite("basic_functionality", "Basic functionality tests")
        
        # Import tests
        basic_suite.add_test(ValidationTest(
            "import_test",
            "Test that all modules can be imported",
            TestCategory.UNIT,
            self._test_imports,
            ValidationLevel.BASIC
        ))
        
        # Configuration tests
        basic_suite.add_test(ValidationTest(
            "config_test",
            "Test configuration loading and validation",
            TestCategory.FUNCTIONAL,
            self._test_configuration,
            ValidationLevel.BASIC
        ))
        
        # File system tests
        basic_suite.add_test(ValidationTest(
            "filesystem_test",
            "Test file system operations",
            TestCategory.FUNCTIONAL,
            self._test_filesystem,
            ValidationLevel.STANDARD
        ))
        
        self.register_suite(basic_suite)
        
        # Performance suite
        performance_suite = ValidationSuite("performance", "Performance and stress tests")
        
        performance_suite.add_test(ValidationTest(
            "memory_usage_test",
            "Test memory usage under normal conditions",
            TestCategory.PERFORMANCE,
            self._test_memory_usage,
            ValidationLevel.STANDARD
        ))
        
        performance_suite.add_test(ValidationTest(
            "execution_speed_test",
            "Test execution speed of core operations",
            TestCategory.PERFORMANCE,
            self._test_execution_speed,
            ValidationLevel.COMPREHENSIVE
        ))
        
        self.register_suite(performance_suite)
    
    def _test_imports(self) -> ValidationResult:
        """Test module imports"""
        try:
            # Test core modules
            import execution_manager
            import file_manager
            import settings_manager
            import error_handler
            import integration_manager
            
            return ValidationResult.PASS
        except ImportError as e:
            return ValidationResult.FAIL, f"Import failed: {e}"
    
    def _test_configuration(self) -> ValidationResult:
        """Test configuration system"""
        try:
            from settings_manager import SettingsManager
            
            # Create temporary settings manager
            settings = SettingsManager("test_data")
            
            # Test basic operations
            settings.set("test.value", "test_data")
            value = settings.get("test.value")
            
            if value != "test_data":
                return ValidationResult.FAIL, "Configuration value mismatch"
            
            return ValidationResult.PASS
        except Exception as e:
            return ValidationResult.FAIL, f"Configuration test failed: {e}"
    
    def _test_filesystem(self) -> ValidationResult:
        """Test file system operations"""
        try:
            from file_manager import FileManager
            
            # Create temporary file manager
            file_mgr = FileManager("test_data")
            
            # Test basic operations
            test_file = Path("test_data/test_file.txt")
            test_file.parent.mkdir(exist_ok=True)
            test_file.write_text("test content")
            
            # Test file operations
            info = file_mgr.get_file_info(str(test_file))
            if not info:
                return ValidationResult.FAIL, "Failed to get file info"
            
            # Cleanup
            test_file.unlink()
            
            return ValidationResult.PASS
        except Exception as e:
            return ValidationResult.FAIL, f"Filesystem test failed: {e}"
    
    def _test_memory_usage(self) -> ValidationResult:
        """Test memory usage"""
        try:
            import psutil
            import gc
            
            # Get initial memory usage
            process = psutil.Process()
            initial_memory = process.memory_info().rss
            
            # Perform memory-intensive operations
            data = []
            for i in range(1000):
                data.append(f"test_data_{i}" * 100)
            
            # Check memory usage
            current_memory = process.memory_info().rss
            memory_increase = current_memory - initial_memory
            
            # Cleanup
            del data
            gc.collect()
            
            # Check if memory usage is reasonable (less than 50MB increase)
            if memory_increase > 50 * 1024 * 1024:
                return ValidationResult.WARNING, f"High memory usage: {memory_increase / 1024 / 1024:.2f} MB"
            
            return ValidationResult.PASS
        except ImportError:
            return ValidationResult.SKIP, "psutil not available"
        except Exception as e:
            return ValidationResult.FAIL, f"Memory test failed: {e}"
    
    def _test_execution_speed(self) -> ValidationResult:
        """Test execution speed"""
        try:
            from execution_manager import ExecutionManager
            
            # Create execution manager
            exec_mgr = ExecutionManager("test_data")
            
            # Measure execution time for basic operations
            start_time = time.time()
            
            # Perform operations
            for i in range(100):
                exec_mgr.get_file_type_handler("test.py")
            
            execution_time = time.time() - start_time
            
            # Check if execution time is reasonable (less than 1 second)
            if execution_time > 1.0:
                return ValidationResult.WARNING, f"Slow execution: {execution_time:.2f} seconds"
            
            return ValidationResult.PASS, f"Execution time: {execution_time:.3f} seconds"
        except Exception as e:
            return ValidationResult.FAIL, f"Speed test failed: {e}"
    
    def export_report(self, report: ValidationReport, file_path: str, format: str = "json") -> bool:
        """Export validation report"""
        try:
            if format.lower() == "json":
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
            elif format.lower() == "html":
                self._export_html_report(report, file_path)
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            logger.info(f"Validation report exported to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export report: {e}")
            return False
    
    def _export_html_report(self, report: ValidationReport, file_path: str):
        """Export HTML validation report"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Validation Report - {report.suite_name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .summary {{ margin: 20px 0; }}
                .test-result {{ margin: 10px 0; padding: 10px; border-radius: 5px; }}
                .pass {{ background-color: #d4edda; }}
                .fail {{ background-color: #f8d7da; }}
                .warning {{ background-color: #fff3cd; }}
                .skip {{ background-color: #e2e3e5; }}
                .error {{ background-color: #f5c6cb; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Validation Report: {report.suite_name}</h1>
                <p>Generated: {report.start_time.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>Duration: {(report.end_time - report.start_time).total_seconds():.2f} seconds</p>
            </div>
            
            <div class="summary">
                <h2>Summary</h2>
                <p>Total Tests: {report.total_tests}</p>
                <p>Passed: {report.passed_tests}</p>
                <p>Failed: {report.failed_tests}</p>
                <p>Warnings: {report.warning_tests}</p>
                <p>Skipped: {report.skipped_tests}</p>
                <p>Errors: {report.error_tests}</p>
                <p>Success Rate: {report.get_success_rate():.1f}%</p>
            </div>
            
            <div class="results">
                <h2>Test Results</h2>
        """
        
        for result in report.test_results:
            status_class = result['result']
            html_content += f"""
                <div class="test-result {status_class}">
                    <h3>{result['name']}</h3>
                    <p><strong>Description:</strong> {result['description']}</p>
                    <p><strong>Category:</strong> {result['category']}</p>
                    <p><strong>Result:</strong> {result['result'].upper()}</p>
                    <p><strong>Execution Time:</strong> {result['execution_time']:.3f} seconds</p>
            """
            
            if result['error_message']:
                html_content += f"<p><strong>Error:</strong> {result['error_message']}</p>"
            
            if result['output']:
                html_content += f"<p><strong>Output:</strong> {result['output']}</p>"
            
            html_content += "</div>"
        
        html_content += """
            </div>
        </body>
        </html>
        """
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

# Decorators for easy test creation
def validation_test(name: str, description: str, category: TestCategory = TestCategory.FUNCTIONAL,
                   level: ValidationLevel = ValidationLevel.STANDARD, timeout: float = 30.0,
                   dependencies: List[str] = None):
    """Decorator to create validation tests"""
    def decorator(func):
        func._validation_test = ValidationTest(
            name, description, category, func, level, timeout, dependencies
        )
        return func
    return decorator

def validation_suite(name: str, description: str):
    """Decorator to create validation suites"""
    def decorator(cls):
        suite = ValidationSuite(name, description)
        
        # Find all validation tests in the class
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if hasattr(attr, '_validation_test'):
                suite.add_test(attr._validation_test)
        
        # Set setup and teardown if they exist
        if hasattr(cls, 'setup'):
            suite.set_setup(cls.setup)
        if hasattr(cls, 'teardown'):
            suite.set_teardown(cls.teardown)
        
        cls._validation_suite = suite
        return cls
    return decorator
