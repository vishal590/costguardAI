"""
Error handling and retry logic for the Cost Data Pipeline.
"""
import time
import random
from typing import Callable, TypeVar, List
from botocore.exceptions import ClientError
from .types import ErrorResponse, RetryConfig

T = TypeVar('T')


def format_error(error: Exception) -> ErrorResponse:
    """
    Format an exception as a structured ErrorResponse.
    
    Args:
        error: The exception to format
        
    Returns:
        ErrorResponse with appropriate code, message, and details
    """
    # Handle boto3 ClientError
    if isinstance(error, ClientError):
        error_code = error.response.get('Error', {}).get('Code', 'UNKNOWN')
        error_message = error.response.get('Error', {}).get('Message', str(error))
        
        # Map AWS error codes to our error codes
        if error_code == 'ThrottlingException' or error_code == 'ProvisionedThroughputExceededException':
            code = 'DYNAMODB_THROTTLING'
        elif error_code == 'AccessDeniedException':
            code = 'COST_EXPLORER_ACCESS_DENIED'
        elif error_code == 'ValidationException':
            code = 'VALIDATION_ERROR'
        else:
            code = 'INTERNAL_ERROR'
            
        return ErrorResponse(
            code=code,
            message=error_message,
            details={
                'aws_error_code': error_code,
                'request_id': error.response.get('ResponseMetadata', {}).get('RequestId')
            }
        )
    
    # Handle ValueError (validation errors)
    if isinstance(error, ValueError):
        return ErrorResponse(
            code='VALIDATION_ERROR',
            message=str(error),
            details={'error_type': 'ValueError'}
        )
    
    # Handle generic exceptions
    return ErrorResponse(
        code='INTERNAL_ERROR',
        message=str(error),
        details={'error_type': type(error).__name__}
    )


def is_retryable_error(error: Exception) -> bool:
    """
    Determine if an error is retryable.
    
    Retryable errors:
    - HTTP 429 (Rate Limit)
    - HTTP 503 (Service Unavailable)
    - ProvisionedThroughputExceededException (DynamoDB)
    - ThrottlingException (DynamoDB)
    
    Non-retryable errors:
    - HTTP 400 (Bad Request)
    - HTTP 401 (Unauthorized)
    - HTTP 403 (Forbidden)
    - ValidationException (DynamoDB)
    
    Args:
        error: The exception to check
        
    Returns:
        True if the error should be retried, False otherwise
    """
    if isinstance(error, ClientError):
        error_code = error.response.get('Error', {}).get('Code', '')
        http_status = error.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 0)
        
        # Check for retryable error codes
        retryable_codes = [
            'ThrottlingException',
            'ProvisionedThroughputExceededException',
            'RequestLimitExceeded',
            'ServiceUnavailable'
        ]
        
        if error_code in retryable_codes:
            return True
        
        # Check for retryable HTTP status codes
        if http_status in [429, 503]:
            return True
        
        # Non-retryable status codes
        if http_status in [400, 401, 403]:
            return False
    
    # Default to non-retryable for unknown errors
    return False


def calculate_backoff_delay(attempt: int, config: RetryConfig) -> float:
    """
    Calculate exponential backoff delay with jitter.
    
    Formula: delay = min(base_delay * 2^attempt, max_delay) * (0.5 + random(0, 0.5))
    
    Args:
        attempt: The retry attempt number (0-indexed)
        config: Retry configuration
        
    Returns:
        Delay in seconds with jitter applied
    """
    # Calculate exponential backoff
    delay = min(config.base_delay * (2 ** attempt), config.max_delay)
    
    # Add jitter: multiply by random value between 0.5 and 1.5
    jitter = 0.5 + random.random()
    
    return delay * jitter


def with_retry(
    operation: Callable[[], T],
    config: RetryConfig,
    retryable_errors: List[str] = None
) -> T:
    """
    Execute an operation with retry logic.
    
    Args:
        operation: The function to execute
        config: Retry configuration
        retryable_errors: Optional list of specific error codes to retry (not used currently)
        
    Returns:
        The result of the operation
        
    Raises:
        The last exception if all retries are exhausted
    """
    last_error = None
    
    for attempt in range(config.max_retries + 1):
        try:
            return operation()
        except Exception as error:
            last_error = error
            
            # Check if we should retry
            if not is_retryable_error(error):
                raise
            
            # Check if we've exhausted retries
            if attempt >= config.max_retries:
                raise
            
            # Calculate delay and wait
            delay = calculate_backoff_delay(attempt, config)
            time.sleep(delay)
    
    # This should never be reached, but just in case
    if last_error:
        raise last_error
    raise RuntimeError("Retry logic failed unexpectedly")
