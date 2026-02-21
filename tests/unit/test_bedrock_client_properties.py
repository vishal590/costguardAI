"""
Property-based tests for Bedrock Client.

Tests Properties 14 and 18 from Phase 2 design.
"""

import json
from datetime import datetime, UTC
from unittest.mock import Mock, patch
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from src.services.bedrock_client import BedrockClient
from src.utils.types import ProcessedData, BedrockRateLimitError


class TestBedrockClientProperties:
    """Property-based tests for Bedrock client."""
    
    def _create_bedrock_client(self):
        """Create BedrockClient instance with mocked boto3 client."""
        with patch('boto3.client') as mock_boto3:
            mock_client = Mock()
            mock_boto3.return_value = mock_client
            client = BedrockClient()
            return client
    
    @settings(
        max_examples=100,
        deadline=None,  # Disable deadline for timing tests with sleep
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        retry_count=st.integers(min_value=1, max_value=3),
        service=st.sampled_from(['EC2', 'Lambda', 'DynamoDB', 'S3', 'RDS'])
    )
    def test_property_14_retry_logic_for_rate_limiting(
        self, retry_count, service
    ):
        """
        Property 14: Retry Logic for Rate Limiting
        
        For any Bedrock API call that returns a rate limit error,
        the system should retry up to 3 times with exponential backoff
        before failing.
        
        Validates: Requirements 2.5, 7.2
        """
        bedrock_client = self._create_bedrock_client()
        
        # Create mock that fails with rate limit error for retry_count times
        call_count = 0
        
        def mock_operation():
            nonlocal call_count
            call_count += 1
            if call_count <= retry_count:
                raise BedrockRateLimitError("Rate limit exceeded")
            return {"success": True}
        
        # Test retry logic
        if retry_count <= 3:
            # Should succeed after retries
            result = bedrock_client.retry_with_backoff(mock_operation, max_retries=3)
            assert result == {"success": True}
            assert call_count == retry_count + 1  # Initial + retries
        else:
            # Should fail after max retries
            with pytest.raises(BedrockRateLimitError):
                bedrock_client.retry_with_backoff(mock_operation, max_retries=3)
            assert call_count == 4  # Initial + 3 retries
    
    @settings(
        max_examples=100,
        deadline=2000,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        num_days=st.integers(min_value=30, max_value=90),
        service=st.sampled_from(['EC2', 'Lambda', 'DynamoDB', 'S3', 'RDS']),
        forecast_horizon=st.integers(min_value=1, max_value=30),
        confidence_level=st.floats(min_value=0.80, max_value=0.99)
    )
    def test_property_18_bedrock_prompt_structure(
        self, num_days, service, forecast_horizon, confidence_level
    ):
        """
        Property 18: Bedrock Prompt Structure
        
        For any Bedrock request, the prompt should include instructions
        for time series forecasting and confidence interval calculation.
        
        Validates: Requirements 2.6
        """
        bedrock_client = self._create_bedrock_client()
        
        # Generate sample historical data
        timestamps = [f"2024-01-{i+1:02d}" for i in range(min(num_days, 30))]
        costs = [10.0 + i * 0.5 for i in range(len(timestamps))]
        
        historical_data = ProcessedData(
            timestamps=timestamps,
            costs=costs,
            service=service,
            total_days=len(timestamps)
        )
        
        # Build prompt
        prompt = bedrock_client.build_prompt(
            historical_data, forecast_horizon, confidence_level
        )
        
        # Verify prompt structure
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        
        # Check for required elements in prompt
        assert "time series" in prompt.lower() or "forecast" in prompt.lower()
        assert "confidence" in prompt.lower() or "interval" in prompt.lower()
        assert str(forecast_horizon) in prompt
        
        # Check that historical data is included
        assert any(str(cost) in prompt for cost in costs[:5])  # Check first 5 costs
        
        # Check for JSON format instruction
        assert "json" in prompt.lower() or "format" in prompt.lower()
    
    @settings(
        max_examples=100,
        deadline=None,  # Disable deadline for timing tests with sleep
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        num_retries=st.integers(min_value=0, max_value=5)
    )
    def test_exponential_backoff_timing(self, num_retries):
        """
        Test that exponential backoff follows expected timing pattern.
        
        Validates: Requirements 2.5, 7.2
        """
        bedrock_client = self._create_bedrock_client()
        
        call_count = 0
        
        def mock_operation():
            nonlocal call_count
            call_count += 1
            if call_count <= num_retries:
                raise BedrockRateLimitError("Rate limit exceeded")
            return {"success": True}
        
        import time
        start_time = time.time()
        
        try:
            bedrock_client.retry_with_backoff(mock_operation, max_retries=3)
        except BedrockRateLimitError:
            pass  # Expected if num_retries > 3
        
        elapsed_time = time.time() - start_time
        
        # Calculate expected minimum delay
        # Delays: 1s, 2s, 4s for retries 1, 2, 3
        expected_delays = [1, 2, 4]
        actual_retries = min(num_retries, 3)
        expected_min_delay = sum(expected_delays[:actual_retries])
        
        if actual_retries > 0:
            # Allow some tolerance for execution time
            assert elapsed_time >= expected_min_delay * 0.9
    
    @settings(
        max_examples=100,
        deadline=2000,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        service=st.sampled_from(['EC2', 'Lambda', 'DynamoDB', 'S3', 'RDS']),
        num_forecasts=st.integers(min_value=1, max_value=30)
    )
    def test_prompt_includes_all_historical_data(
        self, service, num_forecasts
    ):
        """
        Test that prompt includes all historical data points.
        
        Validates: Requirements 2.6
        """
        bedrock_client = self._create_bedrock_client()
        
        # Generate historical data
        timestamps = [f"2024-01-{i+1:02d}" for i in range(30)]
        costs = [10.0 + i * 0.5 for i in range(30)]
        
        historical_data = ProcessedData(
            timestamps=timestamps,
            costs=costs,
            service=service,
            total_days=30
        )
        
        # Build prompt
        prompt = bedrock_client.build_prompt(historical_data, num_forecasts)
        
        # Verify all timestamps are in prompt
        for timestamp in timestamps:
            assert timestamp in prompt