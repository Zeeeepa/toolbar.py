# error_healer.py
"""
Comprehensive error handling with logging and fallback methods.
"""

import logging
import traceback
import time
from functools import wraps
from typing import Callable, Any, Optional, Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ErrorHealer:
    """Handles errors with comprehensive logging and fallback methods."""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.error_log: List[Dict] = []
    
    def log_error(self, error: Exception, context: str = "", method_name: str = ""):
        """Log an error with context information."""
        error_info = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "method_name": method_name,
            "traceback": traceback.format_exc()
        }
        self.error_log.append(error_info)
        logger.error(f"Error in {method_name}: {str(error)}\nContext: {context}\n{traceback.format_exc()}")
    
    def with_retry(self, fallback_method: Optional[Callable] = None):
        """Decorator to add retry logic with fallback to methods."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                last_error = None
                
                for attempt in range(self.max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_error = e
                        self.log_error(e, context=f"Attempt {attempt + 1}/{self.max_retries + 1}", 
                                     method_name=func.__name__)
                        
                        if attempt < self.max_retries:
                            logger.info(f"Retrying {func.__name__} in {self.retry_delay} seconds...")
                            time.sleep(self.retry_delay)
                
                # If we've exhausted all retries, try the fallback method if provided
                if fallback_method:
                    try:
                        logger.info(f"Primary method {func.__name__} failed, trying fallback method {fallback_method.__name__}")
                        return fallback_method(*args, **kwargs)
                    except Exception as fallback_error:
                        self.log_error(fallback_error, context="Fallback method failed", 
                                     method_name=fallback_method.__name__)
                        raise last_error  # Raise the original error, not the fallback error
                
                # If no fallback or fallback also failed, raise the last error
                raise last_error
            
            return wrapper
        return decorator
    
    def safe_execute(self, func: Callable, *args, fallback_method: Optional[Callable] = None, 
                   context: str = "", **kwargs) -> Any:
        """Safely execute a function with error handling and fallback."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.log_error(e, context=context, method_name=func.__name__)
            
            if fallback_method:
                try:
                    logger.info(f"Primary method {func.__name__} failed, trying fallback method {fallback_method.__name__}")
                    return fallback_method(*args, **kwargs)
                except Exception as fallback_error:
                    self.log_error(fallback_error, context="Fallback method failed", 
                                 method_name=fallback_method.__name__)
                    return None
            
            return None
    
    def get_error_summary(self) -> Dict:
        """Get a summary of all errors that have occurred."""
        if not self.error_log:
            return {"total_errors": 0, "error_types": {}}
        
        error_types = {}
        for error in self.error_log:
            error_type = error["error_type"]
            if error_type not in error_types:
                error_types[error_type] = 0
            error_types[error_type] += 1
        
        return {
            "total_errors": len(self.error_log),
            "error_types": error_types,
            "latest_error": self.error_log[-1] if self.error_log else None
        }
    
    def clear_error_log(self):
        """Clear the error log."""
        self.error_log.clear()
        logger.info("Error log cleared")


# Example usage
if __name__ == "__main__":
    healer = ErrorHealer(max_retries=2, retry_delay=0.5)
    
    # Example function that might fail
    @healer.with_retry()
    def might_fail(value):
        if value < 0:
            raise ValueError("Negative value not allowed")
        return value * 2
    
    # Example fallback function
    def fallback_function(value):
        return abs(value) * 2
    
    # Test with a failing value
    try:
        result = might_fail(-5)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Final error: {e}")
    
    # Test with safe_execute
    result = healer.safe_execute(might_fail, -5, fallback_method=fallback_function, context="Testing safe_execute")
    print(f"Safe execute result: {result}")
    
    # Print error summary
    print("\nError Summary:")
    summary = healer.get_error_summary()
    print(f"Total errors: {summary['total_errors']}")
    print(f"Error types: {summary['error_types']}")