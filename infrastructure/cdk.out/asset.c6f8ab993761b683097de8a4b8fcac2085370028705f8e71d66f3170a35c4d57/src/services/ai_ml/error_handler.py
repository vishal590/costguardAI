"""
AI/ML Error Handler with retry logic and exponential backoff.

This module provides comprehensive error handling for AI/ML cost tracking services:
1. Cost Explorer API errors (rate limits, timeouts)
2. CloudWatch API errors (missing metrics)
3. SageMaker API errors (job not found)
4. Bedrock API errors (model not found)
5. Retry logic with exponential backoff

Requirements: NFR-4.2, NFR-4.3, NFR-4.4
"""

import time
import logging
from typing import Callable, Any, Optional, Dict
from functools import wraps
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class AIMLError(Exception):
    """Base exception for AI/ML cost tracking errors"""
    pass


class RateLimitError(AIMLError):
    """Raised when API rate limit is exceeded"""
    pass


class DataNotFoundError(AIMLError):
    """Raised when requested data is not found"""
    pass


class InsufficientDataError(AIMLError):
    """Raised when insufficient data is available for analysis"""
    pass


class APITimeoutError(AIMLError):
    """Raised when API request times out"""
    pass


def retry_with_exponential_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    retryable_errors: tuple = (RateLimitError, APITimeoutError)
):
    """
    Decorator to retry function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        retryable_errors: Tuple of exception types to retry
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_errors as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        delay = min(delay * exponential_base, max_delay)
                    else:
                        logger.error(
                            f"All {max_retries} retry attempts failed for {func.__name__}: {e}"
                        )
                except Exception as e:
                    # Non-retryable error, raise immediately
                    logger.error(f"Non-retryable error in {func.__name__}: {e}")
                    raise
            
            # If we get here, all retries failed
            raise last_exception
        
        return wrapper
    return decorator


def handle_cost_explorer_error(error: ClientError, cache_data: Optional[Dict] = None) -> Dict:
    """
    Handle Cost Explorer API errors.
    
    Args:
        error: ClientError from boto3
        cache_data: Optional cached data to return on error
        
    Returns:
        Error response dict or cached data
        
    Raises:
        RateLimitError: If rate limit exceeded
        APITimeoutError: If request timed out
        AIMLError: For other errors
    """
    error_code = error.response.get('Error', {}).get('Code', 'Unknown')
    error_message = error.response.get('Error', {}).get('Message', str(error))
    
    logger.error(f"Cost Explorer API error: {error_code} - {error_message}")
    
    if error_code == 'ThrottlingException' or error_code == 'TooManyRequestsException':
        raise RateLimitError(f"Cost Explorer rate limit exceeded: {error_message}")
    
    elif error_code == 'ServiceUnavailable' or error_code == '503':
        if cache_data:
            logger.info("Returning cached data due to service unavailability")
            return {
                'data': cache_data,
                'cached': True,
                'warning': 'Data from cache due to service unavailability'
            }
        raise AIMLError(f"Cost Explorer service unavailable: {error_message}")
    
    elif error_code == 'ValidationException' or error_code == '400':
        logger.error(f"Invalid request to Cost Explorer: {error_message}")
        raise AIMLError("Unable to retrieve GPU costs: Invalid request parameters")
    
    elif error_code == 'RequestTimeout' or 'timeout' in error_message.lower():
        raise APITimeoutError(f"Cost Explorer request timed out: {error_message}")
    
    else:
        raise AIMLError(f"Cost Explorer error: {error_code} - {error_message}")


def handle_cloudwatch_error(
    error: ClientError,
    instance_type: Optional[str] = None,
    fallback_classification: Optional[str] = None
) -> Dict:
    """
    Handle CloudWatch API errors.
    
    Args:
        error: ClientError from boto3
        instance_type: Optional instance type for fallback classification
        fallback_classification: Optional fallback classification from tags
        
    Returns:
        Error response dict with fallback data
    """
    error_code = error.response.get('Error', {}).get('Code', 'Unknown')
    error_message = error.response.get('Error', {}).get('Message', str(error))
    
    logger.error(f"CloudWatch API error: {error_code} - {error_message}")
    
    if error_code == 'ResourceNotFoundException' or 'not found' in error_message.lower():
        # Missing metrics - use fallback
        if fallback_classification:
            logger.info(f"Using manual classification tag: {fallback_classification}")
            return {
                'classification': fallback_classification,
                'confidence': 1.0,
                'source': 'manual_tag',
                'warning': 'CloudWatch metrics not available, using manual classification'
            }
        elif instance_type:
            # Default classification based on instance type
            default_class = 'training' if 'p3' in instance_type or 'p4' in instance_type else 'inference'
            logger.info(f"Using default classification based on instance type: {default_class}")
            return {
                'classification': default_class,
                'confidence': 0.3,
                'source': 'instance_type_default',
                'warning': 'CloudWatch metrics not available, using default classification'
            }
        else:
            return {
                'classification': 'unknown',
                'confidence': 0.0,
                'source': 'error',
                'error': 'Insufficient data for classification'
            }
    
    elif error_code == 'InvalidParameterValue':
        logger.error(f"Invalid CloudWatch parameters: {error_message}")
        return {
            'classification': 'unknown',
            'confidence': 0.0,
            'source': 'error',
            'error': 'Invalid parameters for metric retrieval'
        }
    
    else:
        raise AIMLError(f"CloudWatch error: {error_code} - {error_message}")


def handle_sagemaker_error(
    error: ClientError,
    cache_data: Optional[Dict] = None
) -> Dict:
    """
    Handle SageMaker API errors.
    
    Args:
        error: ClientError from boto3
        cache_data: Optional cached data to return on error
        
    Returns:
        Error response dict or cached data
        
    Raises:
        DataNotFoundError: If job/endpoint not found
        AIMLError: For other errors
    """
    error_code = error.response.get('Error', {}).get('Code', 'Unknown')
    error_message = error.response.get('Error', {}).get('Message', str(error))
    
    logger.error(f"SageMaker API error: {error_code} - {error_message}")
    
    if error_code == 'ResourceNotFound' or 'not found' in error_message.lower():
        raise DataNotFoundError(f"SageMaker resource not found: {error_message}")
    
    elif error_code == 'AccessDeniedException' or error_code == 'UnauthorizedOperation':
        logger.error(f"Permission denied for SageMaker: {error_message}")
        raise AIMLError("Unable to access SageMaker resources: Permission denied")
    
    elif error_code == 'RequestTimeout' or 'timeout' in error_message.lower():
        if cache_data:
            logger.info("Returning cached data due to SageMaker timeout")
            return {
                'data': cache_data,
                'cached': True,
                'warning': 'Data from cache due to API timeout'
            }
        raise APITimeoutError(f"SageMaker request timed out: {error_message}")
    
    else:
        raise AIMLError(f"SageMaker error: {error_code} - {error_message}")


def handle_bedrock_error(error: ClientError, continue_on_error: bool = True) -> Optional[Dict]:
    """
    Handle Bedrock API errors.
    
    Args:
        error: ClientError from boto3
        continue_on_error: Whether to continue processing other models on error
        
    Returns:
        Error response dict if continue_on_error, None otherwise
        
    Raises:
        DataNotFoundError: If model not found
        RateLimitError: If rate limit exceeded
        AIMLError: For other errors (if not continue_on_error)
    """
    error_code = error.response.get('Error', {}).get('Code', 'Unknown')
    error_message = error.response.get('Error', {}).get('Message', str(error))
    
    logger.error(f"Bedrock API error: {error_code} - {error_message}")
    
    if error_code == 'ResourceNotFoundException' or 'not found' in error_message.lower():
        if continue_on_error:
            logger.warning(f"Model not found, continuing with other models: {error_message}")
            return {
                'error': 'Model not found',
                'message': error_message
            }
        raise DataNotFoundError(f"Bedrock model not found: {error_message}")
    
    elif error_code == 'ThrottlingException' or error_code == 'TooManyRequestsException':
        raise RateLimitError(f"Bedrock rate limit exceeded: {error_message}")
    
    elif error_code == 'ModelInvocationException':
        if continue_on_error:
            logger.warning(f"Model invocation failed, continuing with other models: {error_message}")
            return {
                'error': 'Invocation failed',
                'message': error_message
            }
        raise AIMLError(f"Bedrock invocation failed: {error_message}")
    
    else:
        if continue_on_error:
            logger.warning(f"Bedrock error, continuing with other models: {error_code} - {error_message}")
            return {
                'error': error_code,
                'message': error_message
            }
        raise AIMLError(f"Bedrock error: {error_code} - {error_message}")


def handle_pricing_error(error: ClientError, last_known_price: Optional[float] = None) -> Dict:
    """
    Handle Pricing API errors (for spot instances).
    
    Args:
        error: ClientError from boto3
        last_known_price: Optional last known price to use as fallback
        
    Returns:
        Error response dict with fallback data
        
    Raises:
        AIMLError: If no fallback data available
    """
    error_code = error.response.get('Error', {}).get('Code', 'Unknown')
    error_message = error.response.get('Error', {}).get('Message', str(error))
    
    logger.error(f"Pricing API error: {error_code} - {error_message}")
    
    if error_code == 'ResourceNotFoundException' or 'not available' in error_message.lower():
        if last_known_price:
            logger.info(f"Using last known price: ${last_known_price}")
            return {
                'price': last_known_price,
                'stale': True,
                'warning': 'Using last known price, current pricing data unavailable'
            }
        raise AIMLError("Spot pricing data unavailable for this region/instance type")
    
    elif 'not supported' in error_message.lower():
        raise AIMLError("Spot instances not available in this region")
    
    else:
        if last_known_price:
            logger.info(f"Using last known price due to error: ${last_known_price}")
            return {
                'price': last_known_price,
                'stale': True,
                'warning': f'Using last known price due to API error: {error_code}'
            }
        raise AIMLError(f"Pricing API error: {error_code} - {error_message}")


def validate_minimum_data(
    data_points: int,
    minimum_required: int = 1,
    data_type: str = "data points"
) -> None:
    """
    Validate that minimum data requirements are met.
    
    Args:
        data_points: Number of data points available
        minimum_required: Minimum number required
        data_type: Description of data type for error message
        
    Raises:
        InsufficientDataError: If insufficient data available
    """
    if data_points < minimum_required:
        raise InsufficientDataError(
            f"Insufficient {data_type}: {data_points} available, {minimum_required} required"
        )


def safe_api_call(
    func: Callable,
    error_handler: Callable,
    *args,
    **kwargs
) -> Any:
    """
    Safely execute an API call with error handling.
    
    Args:
        func: Function to call
        error_handler: Error handler function to use
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func
        
    Returns:
        Result from func or error handler
    """
    try:
        return func(*args, **kwargs)
    except ClientError as e:
        return error_handler(e)
    except Exception as e:
        logger.error(f"Unexpected error in {func.__name__}: {e}")
        raise AIMLError(f"Unexpected error: {str(e)}")
