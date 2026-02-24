"""
Unit tests for AI/ML Error Handler.

Tests error handling scenarios including rate limits, missing data, and API timeouts.

Requirements: NFR-4.2, NFR-4.3
"""

import pytest
import time
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

from src.services.ai_ml.error_handler import (
    AIMLError,
    RateLimitError,
    DataNotFoundError,
    InsufficientDataError,
    APITimeoutError,
    retry_with_exponential_backoff,
    handle_cost_explorer_error,
    handle_cloudwatch_error,
    handle_sagemaker_error,
    handle_bedrock_error,
    handle_pricing_error,
    validate_minimum_data,
    safe_api_call
)


class TestCustomExceptions:
    """Test custom exception classes."""
    
    def test_aiml_error_inheritance(self):
        """Test that AIMLError is base exception."""
        error = AIMLError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"
    
    def test_rate_limit_error_inheritance(self):
        """Test RateLimitError inherits from AIMLError."""
        error = RateLimitError("rate limit exceeded")
        assert isinstance(error, AIMLError)
        assert isinstance(error, Exception)

    
    def test_data_not_found_error(self):
        """Test DataNotFoundError."""
        error = DataNotFoundError("resource not found")
        assert isinstance(error, AIMLError)
        assert str(error) == "resource not found"
    
    def test_insufficient_data_error(self):
        """Test InsufficientDataError."""
        error = InsufficientDataError("not enough data")
        assert isinstance(error, AIMLError)
    
    def test_api_timeout_error(self):
        """Test APITimeoutError."""
        error = APITimeoutError("request timed out")
        assert isinstance(error, AIMLError)


class TestRetryWithExponentialBackoff:
    """Test retry decorator with exponential backoff."""
    
    def test_successful_call_no_retry(self):
        """Test successful call doesn't retry."""
        call_count = 0
        
        @retry_with_exponential_backoff(max_retries=3)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = successful_func()
        assert result == "success"
        assert call_count == 1
    
    def test_retry_on_rate_limit_error(self):
        """Test retry on RateLimitError."""
        call_count = 0
        
        @retry_with_exponential_backoff(max_retries=3, initial_delay=0.01)
        def rate_limited_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError("rate limit exceeded")
            return "success"
        
        result = rate_limited_func()
        assert result == "success"
        assert call_count == 3

    
    def test_max_retries_exceeded(self):
        """Test that max retries are respected."""
        call_count = 0
        
        @retry_with_exponential_backoff(max_retries=2, initial_delay=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise RateLimitError("always fails")
        
        with pytest.raises(RateLimitError):
            always_fails()
        
        assert call_count == 3  # Initial + 2 retries


class TestHandleCostExplorerError:
    """Test Cost Explorer error handling."""
    
    def test_throttling_exception_raises_rate_limit_error(self):
        """Test ThrottlingException raises RateLimitError."""
        error = ClientError(
            {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
            'GetCostAndUsage'
        )
        
        with pytest.raises(RateLimitError) as exc_info:
            handle_cost_explorer_error(error)
        
        assert "rate limit exceeded" in str(exc_info.value).lower()
    
    def test_service_unavailable_with_cache_returns_cached_data(self):
        """Test service unavailable returns cached data if available."""
        error = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service down'}},
            'GetCostAndUsage'
        )
        
        cache_data = {'costs': [100, 200]}
        result = handle_cost_explorer_error(error, cache_data)
        
        assert result['data'] == cache_data
        assert result['cached'] is True
        assert 'warning' in result
    
    def test_request_timeout_raises_api_timeout_error(self):
        """Test RequestTimeout raises APITimeoutError."""
        error = ClientError(
            {'Error': {'Code': 'RequestTimeout', 'Message': 'Request timed out'}},
            'GetCostAndUsage'
        )
        
        with pytest.raises(APITimeoutError):
            handle_cost_explorer_error(error)


class TestHandleCloudWatchError:
    """Test CloudWatch error handling."""
    
    def test_resource_not_found_with_manual_classification(self):
        """Test missing metrics with manual classification tag."""
        error = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Metrics not found'}},
            'GetMetricStatistics'
        )
        
        result = handle_cloudwatch_error(error, fallback_classification='training')
        
        assert result['classification'] == 'training'
        assert result['confidence'] == 1.0
        assert result['source'] == 'manual_tag'
        assert 'warning' in result


class TestValidateMinimumData:
    """Test data validation."""
    
    def test_sufficient_data_passes(self):
        """Test sufficient data doesn't raise."""
        validate_minimum_data(10, minimum_required=5)
        # Should not raise
    
    def test_insufficient_data_raises(self):
        """Test insufficient data raises InsufficientDataError."""
        with pytest.raises(InsufficientDataError) as exc_info:
            validate_minimum_data(3, minimum_required=5, data_type="metrics")
        
        assert "3 available" in str(exc_info.value)
        assert "5 required" in str(exc_info.value)
        assert "metrics" in str(exc_info.value)
