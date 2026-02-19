"""
Property-based tests for retry logic and error handling.

Feature: cost-data-pipeline
"""
import pytest
from hypothesis import given, strategies as st, settings
from botocore.exceptions import ClientError
from unittest.mock import Mock

from src.utils.error_handler import (
    format_error,
    is_retryable_error,
    calculate_backoff_delay,
    with_retry
)
from src.utils.types import RetryConfig, ErrorResponse


# Helper function to create ClientError
def create_client_error(error_code: str, http_status: int, message: str = "Test error"):
    """Create a mock ClientError for testing."""
    error_response = {
        'Error': {
            'Code': error_code,
            'Message': message
        },
        'ResponseMetadata': {
            'HTTPStatusCode': http_status,
            'RequestId': 'test-request-id'
        }
    }
    return ClientError(error_response, 'test_operation')


# Feature: cost-data-pipeline, Property 7: Retryable errors trigger exponential backoff
@given(
    st.integers(min_value=0, max_value=5),
    st.floats(min_value=0.1, max_value=2.0),
    st.floats(min_value=5.0, max_value=20.0)
)
@settings(max_examples=100)
def test_retryable_errors_trigger_exponential_backoff(attempt, base_delay, max_delay):
    """
    Property 7: Retryable errors trigger exponential backoff
    For any API call that returns a retryable error (429, 503, or ProvisionedThroughputExceededException),
    the function should retry with exponential backoff, attempting a maximum of 3 retries
    with increasing delays.
    
    Validates: Requirements 4.1, 4.2, 4.5, 5.1
    """
    config = RetryConfig(
        max_retries=3,
        base_delay=base_delay,
        max_delay=max_delay
    )
    
    # Calculate backoff delay
    delay = calculate_backoff_delay(attempt, config)
    
    # Expected delay without jitter
    expected_base = min(base_delay * (2 ** attempt), max_delay)
    
    # Delay should be within jitter range (0.5 to 1.5 times expected)
    assert expected_base * 0.5 <= delay <= expected_base * 1.5, \
        f"Delay {delay} not in expected range [{expected_base * 0.5}, {expected_base * 1.5}]"
    
    # Delay should not exceed max_delay * 1.5 (accounting for jitter)
    assert delay <= max_delay * 1.5, f"Delay {delay} exceeds max_delay {max_delay} with jitter"


# Feature: cost-data-pipeline, Property 8: Non-retryable errors return immediately
@given(st.sampled_from([400, 401, 403]))
@settings(max_examples=100)
def test_non_retryable_errors_return_immediately(http_status):
    """
    Property 8: Non-retryable errors return immediately
    For any API call that returns a non-retryable error (400, 403),
    the function should not retry and should return an error response
    with the appropriate status code.
    
    Validates: Requirements 4.3, 4.4, 5.2
    """
    # Create a non-retryable error
    error = create_client_error('ValidationException', http_status)
    
    # Check that it's not retryable
    assert is_retryable_error(error) is False, \
        f"HTTP {http_status} should not be retryable"
    
    # Test with_retry raises immediately without retrying
    call_count = 0
    
    def failing_operation():
        nonlocal call_count
        call_count += 1
        raise error
    
    config = RetryConfig(max_retries=3, base_delay=0.01, max_delay=1.0)
    
    with pytest.raises(ClientError):
        with_retry(failing_operation, config)
    
    # Should only be called once (no retries)
    assert call_count == 1, f"Expected 1 call, got {call_count}"


# Feature: cost-data-pipeline, Property 9: Retry exhaustion returns detailed error
@given(
    st.integers(min_value=1, max_value=5),
    st.sampled_from(['ThrottlingException', 'ServiceUnavailable'])
)
@settings(max_examples=100)
def test_retry_exhaustion_returns_detailed_error(max_retries, error_code):
    """
    Property 9: Retry exhaustion returns detailed error
    For any operation that fails after maximum retries, the function should
    return an error response containing success: false, error code, error message,
    and details about the failure.
    
    Validates: Requirements 4.6, 5.3
    """
    # Create a retryable error
    error = create_client_error(error_code, 503)
    
    # Verify it's retryable
    assert is_retryable_error(error) is True
    
    # Test with_retry exhausts retries
    call_count = 0
    
    def failing_operation():
        nonlocal call_count
        call_count += 1
        raise error
    
    config = RetryConfig(max_retries=max_retries, base_delay=0.001, max_delay=0.01)
    
    with pytest.raises(ClientError) as exc_info:
        with_retry(failing_operation, config)
    
    # Should be called max_retries + 1 times (initial + retries)
    assert call_count == max_retries + 1, \
        f"Expected {max_retries + 1} calls, got {call_count}"
    
    # Format the error and verify it contains detailed information
    error_response = format_error(exc_info.value)
    
    assert isinstance(error_response, ErrorResponse)
    assert error_response.code is not None
    assert error_response.message is not None
    assert error_response.details is not None
    assert 'aws_error_code' in error_response.details


# Additional property test: Verify format_error handles various exception types
@given(st.text(min_size=1, max_size=100))
@settings(max_examples=100)
def test_format_error_handles_all_exceptions(error_message):
    """
    Property: format_error produces valid ErrorResponse for all exceptions
    For any exception, format_error should produce a valid ErrorResponse
    with code, message, and optional details.
    """
    # Test with ValueError
    error = ValueError(error_message)
    response = format_error(error)
    
    assert isinstance(response, ErrorResponse)
    assert response.code == 'VALIDATION_ERROR'
    assert response.message == error_message
    assert response.details is not None
    assert response.details['error_type'] == 'ValueError'
    
    # Test with generic Exception
    error = Exception(error_message)
    response = format_error(error)
    
    assert isinstance(response, ErrorResponse)
    assert response.code == 'INTERNAL_ERROR'
    assert response.message == error_message
    assert response.details is not None
    assert response.details['error_type'] == 'Exception'
