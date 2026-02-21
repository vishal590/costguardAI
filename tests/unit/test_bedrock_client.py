"""
Unit tests for Bedrock Client.

Tests cover:
- Client initialization
- Prompt building
- Response parsing
- Retry logic with exponential backoff
- Error handling
"""

import pytest
import json
import time
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, date, timedelta
from src.services.bedrock_client import BedrockClient
from src.utils.types import (
    ProcessedData,
    BedrockResponse,
    BedrockAPIError,
    BedrockRateLimitError,
    BedrockInvalidResponseError
)


class TestBedrockClient:
    """Test suite for BedrockClient."""
    
    @pytest.fixture
    def mock_boto_client(self):
        """Create mock boto3 bedrock-runtime client."""
        with patch('boto3.client') as mock_client:
            yield mock_client
    
    @pytest.fixture
    def bedrock_client(self, mock_boto_client):
        """Create BedrockClient instance with mocked boto3."""
        return BedrockClient()
    
    @pytest.fixture
    def sample_historical_data(self):
        """Create sample historical data."""
        timestamps = [
            (date(2024, 1, 1) + timedelta(days=i)).isoformat()
            for i in range(30)
        ]
        costs = [10.0 + i * 0.5 for i in range(30)]
        
        return ProcessedData(
            timestamps=timestamps,
            costs=costs,
            service='EC2',
            total_days=30
        )
    
    def test_initialization_default(self, mock_boto_client):
        """Test client initialization with defaults."""
        client = BedrockClient()
        
        assert client.model_id == "amazon.nova-lite-v1:0"
        mock_boto_client.assert_called_once_with('bedrock-runtime', region_name='us-east-1')
    
    def test_initialization_custom_model(self, mock_boto_client):
        """Test client initialization with custom model."""
        client = BedrockClient(model_id="amazon.nova-micro-v1:0")
        
        assert client.model_id == "amazon.nova-micro-v1:0"
    
    def test_initialization_custom_region(self, mock_boto_client):
        """Test client initialization with custom region."""
        client = BedrockClient(region="us-west-2")
        
        mock_boto_client.assert_called_once_with('bedrock-runtime', region_name='us-west-2')
    
    def test_build_prompt_structure(self, bedrock_client, sample_historical_data):
        """Test prompt building includes required elements."""
        prompt = bedrock_client.build_prompt(sample_historical_data, 7)
        
        # Check prompt contains key elements
        assert "time series forecasting" in prompt.lower()
        assert "7-day forecast" in prompt
        assert "confidence intervals" in prompt.lower()
        assert str(sample_historical_data.total_days) in prompt
        assert "JSON" in prompt
        
        # Check historical data is included
        assert "2024-01-01" in prompt
        assert "10.0" in prompt
    
    def test_build_prompt_with_confidence_level(self, bedrock_client, sample_historical_data):
        """Test prompt includes confidence level."""
        prompt = bedrock_client.build_prompt(sample_historical_data, 14, confidence_level=0.90)
        
        assert "90%" in prompt
    
    def test_parse_response_valid_json(self, bedrock_client, sample_historical_data):
        """Test parsing valid Bedrock response."""
        response = {
            'content': [{
                'text': json.dumps({
                    'forecasts': [
                        {
                            'date': '2024-01-31',
                            'predicted_cost': 25.0,
                            'confidence_lower': 20.0,
                            'confidence_upper': 30.0
                        },
                        {
                            'date': '2024-02-01',
                            'predicted_cost': 26.0,
                            'confidence_lower': 21.0,
                            'confidence_upper': 31.0
                        }
                    ]
                })
            }]
        }
        
        result = bedrock_client.parse_response(response, sample_historical_data, 2)
        
        assert len(result['predictions']) == 2
        assert result['predictions'][0] == 25.0
        assert result['confidence_lower'][0] == 20.0
        assert result['confidence_upper'][0] == 30.0
        assert len(result['dates']) == 2
    
    def test_parse_response_with_markdown_code_block(self, bedrock_client, sample_historical_data):
        """Test parsing response wrapped in markdown code block."""
        response = {
            'content': [{
                'text': '```json\n' + json.dumps({
                    'forecasts': [
                        {
                            'date': '2024-01-31',
                            'predicted_cost': 25.0,
                            'confidence_lower': 20.0,
                            'confidence_upper': 30.0
                        }
                    ]
                }) + '\n```'
            }]
        }
        
        result = bedrock_client.parse_response(response, sample_historical_data, 1)
        
        assert len(result['predictions']) == 1
        assert result['predictions'][0] == 25.0
    
    def test_parse_response_ensures_non_negative(self, bedrock_client, sample_historical_data):
        """Test parsing ensures all values are non-negative."""
        response = {
            'content': [{
                'text': json.dumps({
                    'forecasts': [
                        {
                            'date': '2024-01-31',
                            'predicted_cost': -5.0,  # Negative value
                            'confidence_lower': -10.0,
                            'confidence_upper': 10.0
                        }
                    ]
                })
            }]
        }
        
        result = bedrock_client.parse_response(response, sample_historical_data, 1)
        
        # All values should be non-negative
        assert result['predictions'][0] >= 0
        assert result['confidence_lower'][0] >= 0
        assert result['confidence_upper'][0] >= 0
    
    def test_parse_response_fixes_invalid_intervals(self, bedrock_client, sample_historical_data):
        """Test parsing fixes invalid confidence intervals."""
        response = {
            'content': [{
                'text': json.dumps({
                    'forecasts': [
                        {
                            'date': '2024-01-31',
                            'predicted_cost': 25.0,
                            'confidence_lower': 30.0,  # Lower > predicted
                            'confidence_upper': 20.0   # Upper < predicted
                        }
                    ]
                })
            }]
        }
        
        result = bedrock_client.parse_response(response, sample_historical_data, 1)
        
        # Intervals should be fixed
        assert result['confidence_lower'][0] <= result['predictions'][0]
        assert result['confidence_upper'][0] >= result['predictions'][0]
    
    def test_parse_response_pads_short_forecast(self, bedrock_client, sample_historical_data):
        """Test parsing pads forecast if fewer days returned."""
        response = {
            'content': [{
                'text': json.dumps({
                    'forecasts': [
                        {
                            'date': '2024-01-31',
                            'predicted_cost': 25.0,
                            'confidence_lower': 20.0,
                            'confidence_upper': 30.0
                        }
                    ]
                })
            }]
        }
        
        # Request 3 days but only got 1
        result = bedrock_client.parse_response(response, sample_historical_data, 3)
        
        assert len(result['predictions']) == 3
        assert len(result['dates']) == 3
    
    def test_parse_response_invalid_json_raises_error(self, bedrock_client, sample_historical_data):
        """Test parsing invalid JSON raises error."""
        response = {
            'content': [{
                'text': 'This is not JSON'
            }]
        }
        
        with pytest.raises(BedrockInvalidResponseError):
            bedrock_client.parse_response(response, sample_historical_data, 1)
    
    def test_parse_response_missing_forecasts_key_raises_error(self, bedrock_client, sample_historical_data):
        """Test parsing response without forecasts key raises error."""
        response = {
            'content': [{
                'text': json.dumps({'predictions': []})  # Wrong key
            }]
        }
        
        with pytest.raises(BedrockInvalidResponseError):
            bedrock_client.parse_response(response, sample_historical_data, 1)
    
    def test_parse_response_no_content_raises_error(self, bedrock_client, sample_historical_data):
        """Test parsing response without content raises error."""
        response = {'content': []}
        
        with pytest.raises(BedrockInvalidResponseError):
            bedrock_client.parse_response(response, sample_historical_data, 1)
    
    def test_retry_with_backoff_succeeds_first_try(self, bedrock_client):
        """Test retry logic succeeds on first attempt."""
        mock_func = Mock(return_value="success")
        
        result = bedrock_client.retry_with_backoff(mock_func, max_retries=3)
        
        assert result == "success"
        assert mock_func.call_count == 1
    
    def test_retry_with_backoff_succeeds_after_retries(self, bedrock_client):
        """Test retry logic succeeds after rate limit errors."""
        mock_func = Mock(side_effect=[
            BedrockRateLimitError("Rate limit 1"),
            BedrockRateLimitError("Rate limit 2"),
            "success"
        ])
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = bedrock_client.retry_with_backoff(mock_func, max_retries=3)
        
        assert result == "success"
        assert mock_func.call_count == 3
    
    def test_retry_with_backoff_exhausts_retries(self, bedrock_client):
        """Test retry logic exhausts all retries."""
        mock_func = Mock(side_effect=BedrockRateLimitError("Rate limit"))
        
        with patch('time.sleep'):
            with pytest.raises(BedrockRateLimitError):
                bedrock_client.retry_with_backoff(mock_func, max_retries=2)
        
        assert mock_func.call_count == 3  # Initial + 2 retries
    
    def test_retry_with_backoff_exponential_delay(self, bedrock_client):
        """Test retry logic uses exponential backoff."""
        mock_func = Mock(side_effect=[
            BedrockRateLimitError("Rate limit 1"),
            BedrockRateLimitError("Rate limit 2"),
            BedrockRateLimitError("Rate limit 3"),
            "success"
        ])
        
        with patch('time.sleep') as mock_sleep:
            bedrock_client.retry_with_backoff(mock_func, max_retries=3)
        
        # Check exponential backoff: 1s, 2s, 4s
        assert mock_sleep.call_count == 3
        mock_sleep.assert_any_call(1)  # 2^0
        mock_sleep.assert_any_call(2)  # 2^1
        mock_sleep.assert_any_call(4)  # 2^2
    
    def test_retry_with_backoff_does_not_retry_api_errors(self, bedrock_client):
        """Test retry logic doesn't retry non-rate-limit errors."""
        mock_func = Mock(side_effect=BedrockAPIError("API error"))
        
        with pytest.raises(BedrockAPIError):
            bedrock_client.retry_with_backoff(mock_func, max_retries=3)
        
        assert mock_func.call_count == 1  # No retries
    
    def test_invoke_model_throttling_exception(self, bedrock_client):
        """Test _invoke_model handles throttling exception."""
        bedrock_client.client.exceptions.ThrottlingException = type('ThrottlingException', (Exception,), {})
        bedrock_client.client.invoke_model = Mock(
            side_effect=bedrock_client.client.exceptions.ThrottlingException("Throttled")
        )
        
        with pytest.raises(BedrockRateLimitError):
            bedrock_client._invoke_model({})
    
    def test_invoke_model_timeout_exception(self, bedrock_client):
        """Test _invoke_model handles timeout exception."""
        bedrock_client.client.exceptions.ModelTimeoutException = type('ModelTimeoutException', (Exception,), {})
        bedrock_client.client.invoke_model = Mock(
            side_effect=bedrock_client.client.exceptions.ModelTimeoutException("Timeout")
        )
        
        with pytest.raises(BedrockAPIError):
            bedrock_client._invoke_model({})
    
    def test_invoke_model_service_unavailable(self, bedrock_client):
        """Test _invoke_model handles service unavailable."""
        bedrock_client.client.exceptions.ServiceUnavailableException = type('ServiceUnavailableException', (Exception,), {})
        bedrock_client.client.invoke_model = Mock(
            side_effect=bedrock_client.client.exceptions.ServiceUnavailableException("Unavailable")
        )
        
        with pytest.raises(BedrockAPIError):
            bedrock_client._invoke_model({})
    
    def test_invoke_model_generic_exception(self, bedrock_client):
        """Test _invoke_model handles generic exceptions."""
        bedrock_client.client.invoke_model = Mock(side_effect=Exception("Unknown error"))
        
        with pytest.raises(BedrockAPIError):
            bedrock_client._invoke_model({})
    
    def test_invoke_forecast_end_to_end(self, bedrock_client, sample_historical_data):
        """Test complete invoke_forecast flow."""
        # Mock successful Bedrock response
        mock_response = {
            'body': Mock(read=Mock(return_value=json.dumps({
                'content': [{
                    'text': json.dumps({
                        'forecasts': [
                            {
                                'date': '2024-01-31',
                                'predicted_cost': 25.0,
                                'confidence_lower': 20.0,
                                'confidence_upper': 30.0
                            }
                        ]
                    })
                }]
            }).encode()))
        }
        
        bedrock_client.client.invoke_model = Mock(return_value=mock_response)
        
        result = bedrock_client.invoke_forecast(sample_historical_data, 1)
        
        assert isinstance(result, BedrockResponse)
        assert len(result.predictions) == 1
        assert result.predictions[0] == 25.0
        assert result.model_id == "amazon.nova-lite-v1:0"
        assert result.latency_ms >= 0  # Mock is instant, so latency can be 0
