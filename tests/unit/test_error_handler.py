"""
Unit tests for error handler module.

Tests specific examples and edge cases for error handling and retry logic.
"""
import pytest
import time
from botocore.exceptions import ClientError
from unittest.mock import Mock

from src.utils.error_handler import (
    format_error,
    is_retryable_error,
    calculate_backoff_delay,
    with_retry
)
from src.utils.types import RetryConfig, ErrorResponse


def create_client_error(error_code: str, http_status: int, message: str = "Test error"):
    """Helper to create a mock ClientError."""
    error_response = {
        'Error': {
            'Code': error_code,
            'Message': message
        },
        'ResponseMetadata': {
            'HTTPStatusCode': http_status,
            'RequestId': 'test-request-id-123'
        }
    }
    return ClientError(error_response, 'test_operation')


class TestFormatError:
    """Test format_error with various exception types."""
    
    def test_format_client_error_throttling(self):
        """Test formatting a DynamoDB throttling error."""
        error = create_client_error('ThrottlingException', 400)
        result = format_error(error)
        
        assert isinstance(result, ErrorResponse)
        assert result.code == 'DYNAMODB_THROTTLING'
        assert result.message == 'Test error'
        assert result.details['aws_error_code'] == 'ThrottlingException'
        assert result.details['request_id'] == 'test-request-id-123'
    
    def test_format_client_error_provisioned_throughput(self):
        """Test formatting a DynamoDB provisioned throughput error."""
        error = create_client_error('ProvisionedThroughputExceededException', 400)
        result = format_error(error)
        
        assert result.code == 'DYNAMODB_THROTTLING'
        assert result.message == 'Test error'
    
    def test_format_client_error_access_denied(self):
        """Test formatting an access denied error."""
        error = create_client_error('AccessDeniedException', 403)
        result = format_error(error)
        
        assert result.code == 'COST_EXPLORER_ACCESS_DENIED'
        assert result.message == 'Test error'
    
    def test_format_client_error_validation(self):
        """Test formatting a validation error."""
        error = create_client_error('ValidationException', 400)
        result = format_error(error)
        
        assert result.code == 'VALIDATION_ERROR'
        assert result.message == 'Test error'
    
    def test_format_client_error_unknown(self):
        """Test formatting an unknown AWS error."""
        error = create_client_error('UnknownException', 500)
        result = format_error(error)
        
        assert result.code == 'INTERNAL_ERROR'
        assert result.message == 'Test error'
    
    def test_format_value_error(self):
        """Test formatting a ValueError."""
        error = ValueError("Invalid input")
        result = format_error(error)
        
        assert result.code == 'VALIDATION_ERROR'
        assert result.message == 'Invalid input'
        assert result.details['error_type'] == 'ValueError'
    
    def test_format_generic_exception(self):
        """Test formatting a generic exception."""
        error = RuntimeError("Something went wrong")
        result = format_error(error)
        
        assert result.code == 'INTERNAL_ERROR'
        assert result.message == 'Something went wrong'
        assert result.details['error_type'] == 'RuntimeError'


class TestIsRetryableError:
    """Test is_retryable_error with various error codes."""
    
    def test_retryable_429_rate_limit(self):
        """Test that HTTP 429 is retryable."""
        error = create_client_error('RequestLimitExceeded', 429)
        assert is_retryable_error(error) is True
    
    def test_retryable_503_service_unavailable(self):
        """Test that HTTP 503 is retryable."""
        error = create_client_error('ServiceUnavailable', 503)
        assert is_retryable_error(error) is True
    
    def test_retryable_throttling_exception(self):
        """Test that ThrottlingException is retryable."""
        error = create_client_error('ThrottlingException', 400)
        assert is_retryable_error(error) is True
    
    def test_retryable_provisioned_throughput(self):
        """Test that ProvisionedThroughputExceededException is retryable."""
        error = create_client_error('ProvisionedThroughputExceededException', 400)
        assert is_retryable_error(error) is True
    
    def test_non_retryable_400_bad_request(self):
        """Test that HTTP 400 is not retryable."""
        error = create_client_error('ValidationException', 400)
        assert is_retryable_error(error) is False
    
    def test_non_retryable_403_forbidden(self):
        """Test that HTTP 403 is not retryable."""
        error = create_client_error('AccessDeniedException', 403)
        assert is_retryable_error(error) is False
    
    def test_non_retryable_401_unauthorized(self):
        """Test that HTTP 401 is not retryable."""
        error = create_client_error('UnauthorizedException', 401)
        assert is_retryable_error(error) is False
    
    def test_non_retryable_generic_exception(self):
        """Test that generic exceptions are not retryable."""
        error = ValueError("Invalid input")
        assert is_retryable_error(error) is False


class TestCalculateBackoffDelay:
    """Test calculate_backoff_delay produces increasing delays."""
    
    def test_backoff_delay_increases(self):
        """Test that backoff delay increases with each attempt."""
        config = RetryConfig(max_retries=3, base_delay=1.0, max_delay=8.0)
        
        delays = []
        for attempt in range(4):
            delay = calculate_backoff_delay(attempt, config)
            delays.append(delay)
        
        # Delays should generally increase (accounting for jitter)
        # Attempt 0: ~1.0s, Attempt 1: ~2.0s, Attempt 2: ~4.0s, Attempt 3: ~8.0s
        assert delays[0] < 2.0  # First delay should be around 1.0s
        assert delays[1] < 4.0  # Second delay should be around 2.0s
        assert delays[2] < 7.0  # Third delay should be around 4.0s
        assert delays[3] <= 12.0  # Fourth delay capped at max_delay with jitter
    
    def test_backoff_delay_respects_max_delay(self):
        """Test that backoff delay never exceeds max_delay * 1.5 (with jitter)."""
        config = RetryConfig(max_retries=10, base_delay=1.0, max_delay=5.0)
        
        for attempt in range(10):
            delay = calculate_backoff_delay(attempt, config)
            # With jitter, max is max_delay * 1.5
            assert delay <= 7.5, f"Delay {delay} exceeds max with jitter at attempt {attempt}"
    
    def test_backoff_delay_has_jitter(self):
        """Test that backoff delay includes jitter (randomness)."""
        config = RetryConfig(max_retries=3, base_delay=1.0, max_delay=8.0)
        
        # Calculate multiple delays for the same attempt
        delays = [calculate_backoff_delay(1, config) for _ in range(10)]
        
        # Delays should vary due to jitter
        assert len(set(delays)) > 1, "Delays should vary due to jitter"
    
    def test_backoff_delay_zero_attempt(self):
        """Test backoff delay for first attempt (attempt 0)."""
        config = RetryConfig(max_retries=3, base_delay=1.0, max_delay=8.0)
        delay = calculate_backoff_delay(0, config)
        
        # First attempt: base_delay * 2^0 = 1.0, with jitter: 0.5 to 1.5
        assert 0.5 <= delay <= 1.5


class TestWithRetry:
    """Test with_retry attempts correct number of retries."""
    
    def test_successful_operation_no_retry(self):
        """Test that successful operation doesn't retry."""
        call_count = 0
        
        def successful_operation():
            nonlocal call_count
            call_count += 1
            return "success"
        
        config = RetryConfig(max_retries=3, base_delay=0.01, max_delay=1.0)
        result = with_retry(successful_operation, config)
        
        assert result == "success"
        assert call_count == 1
    
    def test_retryable_error_retries_then_succeeds(self):
        """Test that retryable error retries and eventually succeeds."""
        call_count = 0
        
        def eventually_successful():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise create_client_error('ThrottlingException', 429)
            return "success"
        
        config = RetryConfig(max_retries=3, base_delay=0.001, max_delay=0.01)
        result = with_retry(eventually_successful, config)
        
        assert result == "success"
        assert call_count == 3
    
    def test_retryable_error_exhausts_retries(self):
        """Test that retryable error exhausts all retries."""
        call_count = 0
        
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise create_client_error('ServiceUnavailable', 503)
        
        config = RetryConfig(max_retries=3, base_delay=0.001, max_delay=0.01)
        
        with pytest.raises(ClientError):
            with_retry(always_fails, config)
        
        # Should be called 4 times: initial + 3 retries
        assert call_count == 4
    
    def test_non_retryable_error_no_retry(self):
        """Test that non-retryable error doesn't retry."""
        call_count = 0
        
        def fails_with_validation_error():
            nonlocal call_count
            call_count += 1
            raise create_client_error('ValidationException', 400)
        
        config = RetryConfig(max_retries=3, base_delay=0.01, max_delay=1.0)
        
        with pytest.raises(ClientError):
            with_retry(fails_with_validation_error, config)
        
        # Should only be called once (no retries)
        assert call_count == 1
    
    def test_retry_with_different_max_retries(self):
        """Test retry with different max_retries values."""
        for max_retries in [1, 2, 5]:
            call_count = 0
            
            def always_fails():
                nonlocal call_count
                call_count += 1
                raise create_client_error('ThrottlingException', 429)
            
            config = RetryConfig(max_retries=max_retries, base_delay=0.001, max_delay=0.01)
            
            with pytest.raises(ClientError):
                with_retry(always_fails, config)
            
            # Should be called max_retries + 1 times
            assert call_count == max_retries + 1
    
    def test_retry_waits_between_attempts(self):
        """Test that retry actually waits between attempts."""
        call_times = []
        
        def fails_twice():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise create_client_error('ThrottlingException', 429)
            return "success"
        
        config = RetryConfig(max_retries=3, base_delay=0.01, max_delay=0.1)
        result = with_retry(fails_twice, config)
        
        assert result == "success"
        assert len(call_times) == 3
        
        # Verify there was a delay between calls
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        
        # Should have some delay (at least a few milliseconds)
        assert delay1 > 0.001
        assert delay2 > 0.001
