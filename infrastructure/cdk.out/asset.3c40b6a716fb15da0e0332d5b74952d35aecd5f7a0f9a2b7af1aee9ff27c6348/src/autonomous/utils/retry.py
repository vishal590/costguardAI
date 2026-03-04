"""
Retry with Exponential Backoff

Provides retry logic with exponential backoff and jitter for resilient operations.

Requirements: 10.1, 10.2
"""
import random
import time
from functools import wraps
from typing import Callable, Any, Optional, Tuple, Type


def retry_with_backoff(
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable:
    """
    Decorator for retrying a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 5)
        base_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 60.0)
        exponential_base: Base for exponential calculation (default: 2.0)
        jitter: Whether to add random jitter to delay (default: True)
        exceptions: Tuple of exception types to catch and retry (default: all exceptions)
    
    Returns:
        Decorated function with retry logic
    
    Example:
        @retry_with_backoff(max_retries=3, base_delay=0.5)
        def api_call():
            # Make API call that might fail
            pass
    
    Requirements: 10.1, 10.2
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    # Don't retry on last attempt
                    if attempt == max_retries:
                        print(f"Max retries ({max_retries}) reached for {func.__name__}")
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay = delay * (0.5 + random.random())
                    
                    print(f"Retry {attempt + 1}/{max_retries} for {func.__name__} after {delay:.2f}s (error: {e})")
                    
                    time.sleep(delay)
            
            # Should never reach here, but raise last exception if we do
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


def calculate_backoff_delay(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True
) -> float:
    """
    Calculate exponential backoff delay for a given attempt.
    
    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        jitter: Whether to add random jitter
    
    Returns:
        Delay in seconds
    
    Requirements: 10.1, 10.2
    """
    # Calculate exponential delay
    delay = min(base_delay * (exponential_base ** attempt), max_delay)
    
    # Add jitter (random factor between 0.5 and 1.5)
    if jitter:
        delay = delay * (0.5 + random.random())
    
    return delay


class RetryableOperation:
    """
    Context manager for retryable operations with exponential backoff.
    
    Example:
        with RetryableOperation(max_retries=3) as retry:
            result = retry.execute(lambda: api_call())
    
    Requirements: 10.1, 10.2
    """
    
    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        exceptions: Tuple[Type[Exception], ...] = (Exception,)
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.exceptions = exceptions
        self.attempt = 0
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Suppress exceptions if we're still retrying
        if exc_type and issubclass(exc_type, self.exceptions) and self.attempt < self.max_retries:
            return True
        return False
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with retry logic.
        
        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
        
        Returns:
            Result of function execution
        
        Raises:
            Last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            self.attempt = attempt
            
            try:
                return func(*args, **kwargs)
                
            except self.exceptions as e:
                last_exception = e
                
                # Don't retry on last attempt
                if attempt == self.max_retries:
                    print(f"Max retries ({self.max_retries}) reached")
                    raise
                
                # Calculate delay
                delay = calculate_backoff_delay(
                    attempt,
                    self.base_delay,
                    self.max_delay,
                    self.exponential_base,
                    self.jitter
                )
                
                print(f"Retry {attempt + 1}/{self.max_retries} after {delay:.2f}s (error: {e})")
                
                time.sleep(delay)
        
        # Should never reach here
        if last_exception:
            raise last_exception


# Predefined retry configurations for common use cases

# For API calls (5 retries, 1s base delay)
retry_api_call = retry_with_backoff(
    max_retries=5,
    base_delay=1.0,
    max_delay=60.0
)

# For checkpoint saves (3 retries, 0.5s base delay)
retry_checkpoint_save = retry_with_backoff(
    max_retries=3,
    base_delay=0.5,
    max_delay=30.0
)

# For database operations (5 retries, 0.5s base delay)
retry_db_operation = retry_with_backoff(
    max_retries=5,
    base_delay=0.5,
    max_delay=30.0
)

# For S3 operations (3 retries, 1s base delay)
retry_s3_operation = retry_with_backoff(
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0
)
