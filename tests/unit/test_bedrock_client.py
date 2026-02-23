"""
Unit tests for BedrockAdvisorClient.
"""
import pytest
import json
from datetime import datetime, UTC
from unittest.mock import Mock, MagicMock, patch

from src.services.bedrock_advisor_client import BedrockAdvisorClient
from src.utils.types import CostContext, ConversationTurn, QueryIntent, BudgetStatus


class TestBedrockClientInitialization:
    """Tests for BedrockAdvisorClient initialization."""
    
    def test_bedrock_client_initialization(self):
        """Test BedrockAdvisorClient initializes correctly."""
        client = BedrockAdvisorClient()
        assert client is not None
        assert client.model_id == "amazon.nova-lite-v1:0"
        assert client.max_retries == 3
    
    def test_bedrock_client_with_custom_model(self):
        """Test BedrockAdvisorClient with custom model ID."""
        client = BedrockAdvisorClient(model_id="custom-model-id")
        assert client.model_id == "custom-model-id"
    
    def test_bedrock_client_with_custom_retries(self):
        """Test BedrockAdvisorClient with custom max retries."""
        client = BedrockAdvisorClient(max_retries=5)
        assert client.max_retries == 5


class TestPromptConstruction:
    """Tests for prompt construction."""
    
    def test_build_prompt_simple_query(self):
        """Test building prompt with simple query."""
        client = BedrockAdvisorClient()
        
        context = CostContext(
            historical_costs={},
            forecast_data=None,
            prevention_actions=[],
            current_budget=None,
            anomalies=[]
        )
        
        prompt = client.build_prompt("What are my costs?", context, [])
        
        assert "What are my costs?" in prompt
        assert "advisor" in prompt.lower()
    
    def test_build_prompt_with_historical_costs(self):
        """Test building prompt with historical cost data."""
        client = BedrockAdvisorClient()
        
        context = CostContext(
            historical_costs={
                'ec2': [
                    {'date': '2026-02-20', 'blended_cost': 25.50, 'unblended_cost': 25.50, 'currency': 'USD'}
                ],
                's3': [
                    {'date': '2026-02-20', 'blended_cost': 5.25, 'unblended_cost': 5.25, 'currency': 'USD'}
                ]
            },
            forecast_data=None,
            prevention_actions=[],
            current_budget=None,
            anomalies=[]
        )
        
        prompt = client.build_prompt("Show me EC2 costs", context, [])
        
        assert "ec2" in prompt.lower()
        assert "$" in prompt
        assert "25.50" in prompt or "30.75" in prompt  # Total or individual
    
    def test_build_prompt_with_forecast_data(self):
        """Test building prompt with forecast data."""
        client = BedrockAdvisorClient()
        
        context = CostContext(
            historical_costs={},
            forecast_data={
                'ec2': [
                    {'date': '2026-02-24', 'predicted_cost': 30.00, 'confidence_lower': 25.00, 'confidence_upper': 35.00}
                ]
            },
            prevention_actions=[],
            current_budget=None,
            anomalies=[]
        )
        
        prompt = client.build_prompt("What will my costs be?", context, [])
        
        assert "forecast" in prompt.lower() or "predict" in prompt.lower()
        assert "$" in prompt
    
    def test_build_prompt_with_prevention_actions(self):
        """Test building prompt with prevention actions."""
        client = BedrockAdvisorClient()
        
        context = CostContext(
            historical_costs={},
            forecast_data=None,
            prevention_actions=[
                {'resource_id': 'i-123', 'action': 'stop', 'estimated_savings': 15.50}
            ],
            current_budget=None,
            anomalies=[]
        )
        
        prompt = client.build_prompt("What actions were taken?", context, [])
        
        assert "prevention" in prompt.lower() or "action" in prompt.lower()
        assert "$" in prompt or "15.50" in prompt
    
    def test_build_prompt_with_budget(self):
        """Test building prompt with budget status."""
        client = BedrockAdvisorClient()
        
        budget = BudgetStatus(
            budget_name="Monthly Budget",
            limit=100.00,
            actual_spend=75.00,
            forecasted_spend=90.00,
            utilization_percent=75.0,
            currency="USD",
            time_period="2026-02"
        )
        
        context = CostContext(
            historical_costs={},
            forecast_data=None,
            prevention_actions=[],
            current_budget=budget,
            anomalies=[]
        )
        
        prompt = client.build_prompt("Am I over budget?", context, [])
        
        assert "budget" in prompt.lower()
        assert "75.00" in prompt or "100.00" in prompt
    
    def test_build_prompt_with_conversation_history(self):
        """Test building prompt with conversation history."""
        client = BedrockAdvisorClient()
        
        context = CostContext(
            historical_costs={},
            forecast_data=None,
            prevention_actions=[],
            current_budget=None,
            anomalies=[]
        )
        
        history = [
            ConversationTurn(
                query="What are my EC2 costs?",
                response="Your EC2 costs are $25.50",
                timestamp=datetime.now(UTC),
                context_used=context
            )
        ]
        
        prompt = client.build_prompt("What about S3?", context, history)
        
        assert "previous" in prompt.lower() or "conversation" in prompt.lower()
        assert "EC2" in prompt or "ec2" in prompt.lower()
    
    def test_build_prompt_truncates_long_content(self):
        """Test that prompt is truncated if too long."""
        client = BedrockAdvisorClient()
        
        # Create very long query
        long_query = "What are my costs? " * 1000
        
        context = CostContext(
            historical_costs={},
            forecast_data=None,
            prevention_actions=[],
            current_budget=None,
            anomalies=[]
        )
        
        prompt = client.build_prompt(long_query, context, [])
        
        # Prompt should be truncated
        assert len(prompt) <= 4100
        if len(long_query) > 4000:
            assert "truncated" in prompt.lower()


class TestBedrockAPIInvocation:
    """Tests for Bedrock API invocation."""
    
    def test_invoke_bedrock_success(self):
        """Test successful Bedrock API invocation."""
        bedrock_mock = Mock()
        
        # Setup mock response
        bedrock_mock.invoke_model.return_value = {
            'body': Mock(read=lambda: json.dumps({'completion': 'Your costs are $25.50'}).encode())
        }
        
        client = BedrockAdvisorClient(bedrock_client=bedrock_mock)
        
        response = client._invoke_bedrock("What are my costs?")
        
        assert response == "Your costs are $25.50"
        bedrock_mock.invoke_model.assert_called_once()
    
    def test_invoke_bedrock_with_output_format(self):
        """Test Bedrock invocation with 'output' response format."""
        bedrock_mock = Mock()
        
        # Setup mock response with 'output' key
        bedrock_mock.invoke_model.return_value = {
            'body': Mock(read=lambda: json.dumps({'output': 'Your costs are $30.00'}).encode())
        }
        
        client = BedrockAdvisorClient(bedrock_client=bedrock_mock)
        
        response = client._invoke_bedrock("What are my costs?")
        
        assert response == "Your costs are $30.00"
    
    def test_invoke_bedrock_no_client(self):
        """Test Bedrock invocation without client."""
        client = BedrockAdvisorClient()
        
        response = client._invoke_bedrock("What are my costs?")
        
        assert "unable to access" in response.lower()
    
    def test_invoke_bedrock_api_error(self):
        """Test handling of Bedrock API errors."""
        bedrock_mock = Mock()
        bedrock_mock.invoke_model.side_effect = Exception("API Error")
        
        client = BedrockAdvisorClient(bedrock_client=bedrock_mock)
        
        with pytest.raises(Exception):
            client._invoke_bedrock("What are my costs?")
    
    def test_invoke_bedrock_unexpected_format(self):
        """Test handling of unexpected response format."""
        bedrock_mock = Mock()
        
        # Setup mock response with unexpected format
        bedrock_mock.invoke_model.return_value = {
            'body': Mock(read=lambda: json.dumps({'unexpected_key': 'value'}).encode())
        }
        
        client = BedrockAdvisorClient(bedrock_client=bedrock_mock)
        
        response = client._invoke_bedrock("What are my costs?")
        
        assert "unexpected response format" in response.lower()


class TestResponseParsing:
    """Tests for response parsing."""
    
    def test_parse_response_simple(self):
        """Test parsing simple response."""
        client = BedrockAdvisorClient()
        
        response = client.parse_response("Your EC2 costs are $25.50")
        
        assert response.response_text == "Your EC2 costs are $25.50"
        assert isinstance(response.recommendations, list)
        assert isinstance(response.cost_data, dict)
        assert response.cached is False
    
    def test_parse_response_with_recommendations(self):
        """Test parsing response with recommendations."""
        client = BedrockAdvisorClient()
        
        response_text = """
        Your costs are high. I recommend:
        - Stop idle EC2 instance i-123 to save $15.50/month
        - Delete unused S3 buckets to save $5.00/month
        """
        
        response = client.parse_response(response_text)
        
        # Should extract some recommendations
        assert len(response.recommendations) > 0
        # Recommendations should have actions
        assert all(len(rec.action) > 0 for rec in response.recommendations)
    
    def test_parse_response_extracts_costs(self):
        """Test that cost data is extracted from response."""
        client = BedrockAdvisorClient()
        
        response_text = "Your EC2 costs are $25.50 and S3 costs are $10.25"
        
        response = client.parse_response(response_text)
        
        assert 'mentioned_costs' in response.cost_data
        assert len(response.cost_data['mentioned_costs']) >= 2
    
    def test_parse_response_extracts_percentages(self):
        """Test that percentages are extracted from response."""
        client = BedrockAdvisorClient()
        
        response_text = "Your costs increased by 45% this month"
        
        response = client.parse_response(response_text)
        
        assert 'mentioned_percentages' in response.cost_data
        assert 45.0 in response.cost_data['mentioned_percentages']


class TestRetryLogic:
    """Tests for retry logic."""
    
    @patch('time.sleep')  # Mock sleep to speed up test
    def test_retry_with_backoff_success_first_try(self, mock_sleep):
        """Test retry logic when function succeeds on first try."""
        client = BedrockAdvisorClient()
        
        def successful_function():
            return "Success!"
        
        result = client.retry_with_backoff(successful_function)
        
        assert result == "Success!"
        mock_sleep.assert_not_called()
    
    @patch('time.sleep')
    def test_retry_with_backoff_success_after_retries(self, mock_sleep):
        """Test retry logic when function succeeds after retries."""
        client = BedrockAdvisorClient(max_retries=3)
        
        call_count = [0]
        
        def eventually_successful():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("Throttling error")
            return "Success!"
        
        result = client.retry_with_backoff(eventually_successful)
        
        assert result == "Success!"
        assert call_count[0] == 2
        assert mock_sleep.call_count == 1  # Slept once before second attempt
    
    @patch('time.sleep')
    def test_retry_with_backoff_all_retries_fail(self, mock_sleep):
        """Test retry logic when all retries fail."""
        client = BedrockAdvisorClient(max_retries=3)
        
        def always_failing():
            raise Exception("Throttling error")
        
        with pytest.raises(Exception):
            client.retry_with_backoff(always_failing)
        
        assert mock_sleep.call_count == 2  # Slept before 2nd and 3rd attempts
    
    @patch('time.sleep')
    def test_retry_with_backoff_exponential_delay(self, mock_sleep):
        """Test that retry uses exponential backoff."""
        client = BedrockAdvisorClient(max_retries=4)
        
        def always_failing():
            raise Exception("Throttling error")
        
        with pytest.raises(Exception):
            client.retry_with_backoff(always_failing)
        
        # Check exponential backoff: 1s, 2s, 4s
        calls = mock_sleep.call_args_list
        assert calls[0][0][0] == 1  # First retry: 1 second
        assert calls[1][0][0] == 2  # Second retry: 2 seconds
        assert calls[2][0][0] == 4  # Third retry: 4 seconds


class TestErrorHandling:
    """Tests for error handling."""
    
    def test_is_retryable_error_throttling(self):
        """Test that throttling errors are retryable."""
        client = BedrockAdvisorClient()
        
        error = Exception("Throttling exception occurred")
        assert client._is_retryable_error(error) is True
    
    def test_is_retryable_error_rate_limit(self):
        """Test that rate limit errors are retryable."""
        client = BedrockAdvisorClient()
        
        error = Exception("Rate limit exceeded")
        assert client._is_retryable_error(error) is True
    
    def test_is_retryable_error_503(self):
        """Test that 503 errors are retryable."""
        client = BedrockAdvisorClient()
        
        error = Exception("Service unavailable (503)")
        assert client._is_retryable_error(error) is True
    
    def test_is_retryable_error_429(self):
        """Test that 429 errors are retryable."""
        client = BedrockAdvisorClient()
        
        error = Exception("Too many requests (429)")
        assert client._is_retryable_error(error) is True
    
    def test_is_not_retryable_error_invalid_request(self):
        """Test that invalid request errors are not retryable."""
        client = BedrockAdvisorClient()
        
        error = Exception("Invalid request")
        assert client._is_retryable_error(error) is False
    
    def test_is_not_retryable_error_auth(self):
        """Test that authentication errors are not retryable."""
        client = BedrockAdvisorClient()
        
        error = Exception("Authentication failed")
        assert client._is_retryable_error(error) is False


class TestInvokeAdvisor:
    """Tests for invoke_advisor method."""
    
    @patch('time.sleep')
    def test_invoke_advisor_success(self, mock_sleep):
        """Test successful advisor invocation."""
        bedrock_mock = Mock()
        bedrock_mock.invoke_model.return_value = {
            'body': Mock(read=lambda: json.dumps({'completion': 'Your costs are $25.50'}).encode())
        }
        
        client = BedrockAdvisorClient(bedrock_client=bedrock_mock)
        
        context = CostContext(
            historical_costs={},
            forecast_data=None,
            prevention_actions=[],
            current_budget=None,
            anomalies=[]
        )
        
        response = client.invoke_advisor("What are my costs?", context, [])
        
        assert response == "Your costs are $25.50"
        bedrock_mock.invoke_model.assert_called_once()
    
    @patch('time.sleep')
    def test_invoke_advisor_with_retry(self, mock_sleep):
        """Test advisor invocation with retry."""
        bedrock_mock = Mock()
        
        # First call fails, second succeeds
        bedrock_mock.invoke_model.side_effect = [
            Exception("Throttling error"),
            {'body': Mock(read=lambda: json.dumps({'completion': 'Success'}).encode())}
        ]
        
        client = BedrockAdvisorClient(bedrock_client=bedrock_mock, max_retries=2)
        
        context = CostContext(
            historical_costs={},
            forecast_data=None,
            prevention_actions=[],
            current_budget=None,
            anomalies=[]
        )
        
        response = client.invoke_advisor("What are my costs?", context, [])
        
        assert response == "Success"
        assert bedrock_mock.invoke_model.call_count == 2


class TestRecommendationExtraction:
    """Tests for recommendation extraction."""
    
    def test_extract_recommendations_with_savings(self):
        """Test extracting recommendations with savings estimates."""
        client = BedrockAdvisorClient()
        
        response_text = """
        I recommend stopping idle instance i-123 to save $15.50 per month.
        You should also consider deleting unused S3 buckets.
        """
        
        recommendations = client._extract_recommendations(response_text)
        
        assert len(recommendations) > 0
        # At least one recommendation should have savings
        assert any(rec.estimated_savings > 0 for rec in recommendations)
    
    def test_extract_recommendations_limits_to_five(self):
        """Test that recommendation extraction limits to 5 recommendations."""
        client = BedrockAdvisorClient()
        
        response_text = """
        I recommend:
        - Action 1
        - Action 2
        - Action 3
        - Action 4
        - Action 5
        - Action 6
        - Action 7
        """
        
        recommendations = client._extract_recommendations(response_text)
        
        assert len(recommendations) <= 5


class TestCostDataExtraction:
    """Tests for cost data extraction."""
    
    def test_extract_cost_data_with_amounts(self):
        """Test extracting cost amounts from text."""
        client = BedrockAdvisorClient()
        
        response_text = "Your EC2 costs are $25.50 and S3 costs are $10.25"
        
        cost_data = client._extract_cost_data(response_text)
        
        assert 'mentioned_costs' in cost_data
        assert 25.50 in cost_data['mentioned_costs']
        assert 10.25 in cost_data['mentioned_costs']
    
    def test_extract_cost_data_with_percentages(self):
        """Test extracting percentages from text."""
        client = BedrockAdvisorClient()
        
        response_text = "Costs increased by 45% and utilization is at 75%"
        
        cost_data = client._extract_cost_data(response_text)
        
        assert 'mentioned_percentages' in cost_data
        assert 45.0 in cost_data['mentioned_percentages']
        assert 75.0 in cost_data['mentioned_percentages']
    
    def test_extract_cost_data_empty_text(self):
        """Test extracting cost data from empty text."""
        client = BedrockAdvisorClient()
        
        cost_data = client._extract_cost_data("")
        
        assert isinstance(cost_data, dict)
