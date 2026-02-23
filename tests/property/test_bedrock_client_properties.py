"""
Property-based tests for BedrockAdvisorClient.

Feature: ai-cost-advisor
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta, UTC
from unittest.mock import Mock, MagicMock

from src.services.bedrock_advisor_client import BedrockAdvisorClient
from src.utils.types import CostContext, ConversationTurn, QueryIntent


# Feature: ai-cost-advisor, Property 3: Bedrock Prompt Structure
@given(
    query=st.text(min_size=5, max_size=200),
    num_history_turns=st.integers(min_value=0, max_value=5),
    num_services=st.integers(min_value=0, max_value=3)
)
@settings(max_examples=100)
def test_bedrock_prompt_structure(query, num_history_turns, num_services):
    """
    Property 3: Bedrock Prompt Structure
    For any query with context and conversation history, the constructed
    Bedrock prompt should include all three components (query, context, history)
    in the correct format.
    
    Validates: Requirements 3.2
    """
    client = BedrockAdvisorClient()
    
    # Create mock context
    services = [f"service{i}" for i in range(num_services)]
    historical_costs = {}
    for service in services:
        historical_costs[service] = [
            {'date': '2026-02-20', 'blended_cost': 10.0, 'unblended_cost': 10.0, 'currency': 'USD'}
        ]
    
    context = CostContext(
        historical_costs=historical_costs,
        forecast_data=None,
        prevention_actions=[],
        current_budget=None,
        anomalies=[]
    )
    
    # Create mock conversation history
    history = []
    for i in range(num_history_turns):
        history.append(ConversationTurn(
            query=f"Previous query {i}",
            response=f"Previous response {i}",
            timestamp=datetime.now(UTC),
            context_used=context
        ))
    
    # Build prompt
    prompt = client.build_prompt(query, context, history)
    
    # Verify prompt structure
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    
    # Prompt should contain the query
    assert query in prompt or "Context truncated" in prompt, \
        "Prompt should contain the user query"
    
    # Prompt should contain system instruction
    assert "advisor" in prompt.lower() or "cost" in prompt.lower(), \
        "Prompt should contain system instruction"
    
    # If history exists, prompt should reference it
    if num_history_turns > 0:
        assert "previous" in prompt.lower() or "conversation" in prompt.lower(), \
            "Prompt should reference conversation history when it exists"
    
    # If services exist, prompt should reference cost data
    if num_services > 0:
        assert "cost" in prompt.lower() or "$" in prompt, \
            "Prompt should reference cost data when services exist"
    
    # Prompt should be under length limit (4000 chars as per implementation)
    assert len(prompt) <= 4100, \
        f"Prompt length {len(prompt)} exceeds maximum"


# Property: Prompt construction is deterministic
@given(
    query=st.text(min_size=1, max_size=100),
    num_services=st.integers(min_value=0, max_value=3)
)
@settings(max_examples=100)
def test_prompt_construction_deterministic(query, num_services):
    """
    Property: Prompt construction is deterministic
    For any query and context, building the prompt multiple times
    should produce the same result.
    
    Validates: Requirements 3.2
    """
    client = BedrockAdvisorClient()
    
    # Create mock context
    services = [f"service{i}" for i in range(num_services)]
    historical_costs = {}
    for service in services:
        historical_costs[service] = [
            {'date': '2026-02-20', 'blended_cost': 15.0, 'unblended_cost': 15.0, 'currency': 'USD'}
        ]
    
    context = CostContext(
        historical_costs=historical_costs,
        forecast_data=None,
        prevention_actions=[],
        current_budget=None,
        anomalies=[]
    )
    
    history = []
    
    # Build prompt multiple times
    prompt1 = client.build_prompt(query, context, history)
    prompt2 = client.build_prompt(query, context, history)
    prompt3 = client.build_prompt(query, context, history)
    
    # All should be identical
    assert prompt1 == prompt2 == prompt3, \
        "Prompt construction should be deterministic"


# Property: Retry logic respects max retries
@given(max_retries=st.integers(min_value=1, max_value=5))
@settings(max_examples=100, deadline=None)  # Disable deadline due to sleep
def test_retry_logic_respects_max_retries(max_retries):
    """
    Property: Retry logic respects max retries
    For any max_retries value, the retry logic should attempt
    exactly that many times before giving up.
    
    Validates: Requirements 3.3
    """
    client = BedrockAdvisorClient(max_retries=max_retries)
    
    # Create a function that always fails with retryable error
    call_count = [0]
    
    def failing_function():
        call_count[0] += 1
        raise Exception("Throttling error - rate limit exceeded")
    
    # Mock time.sleep to speed up test
    import unittest.mock
    with unittest.mock.patch('time.sleep'):
        # Should raise after max_retries attempts
        with pytest.raises(Exception):
            client.retry_with_backoff(failing_function)
    
    # Should have attempted exactly max_retries times
    assert call_count[0] == max_retries, \
        f"Expected {max_retries} attempts, got {call_count[0]}"


# Property: Retry logic succeeds on eventual success
@given(
    max_retries=st.integers(min_value=2, max_value=5),
    success_on_attempt=st.integers(min_value=1, max_value=4)
)
@settings(max_examples=100, deadline=None)  # Disable deadline due to sleep
def test_retry_logic_succeeds_eventually(max_retries, success_on_attempt):
    """
    Property: Retry logic succeeds on eventual success
    For any function that succeeds on attempt N (where N <= max_retries),
    the retry logic should return the successful result.
    
    Validates: Requirements 3.3
    """
    assume(success_on_attempt <= max_retries)
    
    client = BedrockAdvisorClient(max_retries=max_retries)
    
    # Create a function that succeeds on specific attempt
    call_count = [0]
    
    def eventually_succeeding_function():
        call_count[0] += 1
        if call_count[0] < success_on_attempt:
            raise Exception("Throttling error")
        return "Success!"
    
    # Mock time.sleep to speed up test
    import unittest.mock
    with unittest.mock.patch('time.sleep'):
        # Should succeed
        result = client.retry_with_backoff(eventually_succeeding_function)
    
    assert result == "Success!"
    assert call_count[0] == success_on_attempt


# Property: Non-retryable errors fail immediately
@given(error_message=st.sampled_from([
    "Invalid request",
    "Bad request",
    "Authentication failed",
    "Permission denied"
]))
@settings(max_examples=100)
def test_non_retryable_errors_fail_immediately(error_message):
    """
    Property: Non-retryable errors fail immediately
    For any non-retryable error, the retry logic should fail
    on the first attempt without retrying.
    
    Validates: Requirements 3.3, 3.5
    """
    client = BedrockAdvisorClient(max_retries=3)
    
    call_count = [0]
    
    def failing_function():
        call_count[0] += 1
        raise Exception(error_message)
    
    # Should raise immediately
    with pytest.raises(Exception):
        client.retry_with_backoff(failing_function)
    
    # Should have attempted only once
    assert call_count[0] == 1, \
        f"Non-retryable error should fail immediately, got {call_count[0]} attempts"


# Property: Response parsing never raises exceptions
@given(response_text=st.text(min_size=0, max_size=1000))
@settings(max_examples=100)
def test_response_parsing_never_fails(response_text):
    """
    Property: Response parsing never raises exceptions
    For any response text, parsing should always complete
    without raising exceptions, even for malformed input.
    
    Validates: Requirements 3.4
    """
    client = BedrockAdvisorClient()
    
    # Should not raise exceptions
    try:
        advisor_response = client.parse_response(response_text)
        
        # Should return a valid AdvisorResponse
        assert hasattr(advisor_response, 'response_text')
        assert hasattr(advisor_response, 'recommendations')
        assert hasattr(advisor_response, 'cost_data')
        assert hasattr(advisor_response, 'confidence')
        assert hasattr(advisor_response, 'cached')
        
        # Response text should match input
        assert advisor_response.response_text == response_text
        
        # Recommendations should be a list
        assert isinstance(advisor_response.recommendations, list)
        
        # Cost data should be a dict
        assert isinstance(advisor_response.cost_data, dict)
        
    except Exception as e:
        pytest.fail(f"Response parsing raised exception: {e}")


# Property: Recommendation extraction is consistent
@given(response_text=st.text(min_size=10, max_size=500))
@settings(max_examples=100)
def test_recommendation_extraction_consistent(response_text):
    """
    Property: Recommendation extraction is consistent
    For any response text, extracting recommendations multiple times
    should produce the same result.
    
    Validates: Requirements 3.4
    """
    client = BedrockAdvisorClient()
    
    # Extract recommendations multiple times
    recs1 = client._extract_recommendations(response_text)
    recs2 = client._extract_recommendations(response_text)
    recs3 = client._extract_recommendations(response_text)
    
    # All should be identical
    assert len(recs1) == len(recs2) == len(recs3)
    
    for r1, r2, r3 in zip(recs1, recs2, recs3):
        assert r1.action == r2.action == r3.action
        assert r1.estimated_savings == r2.estimated_savings == r3.estimated_savings


# Property: Cost data extraction is consistent
@given(response_text=st.text(min_size=10, max_size=500))
@settings(max_examples=100)
def test_cost_data_extraction_consistent(response_text):
    """
    Property: Cost data extraction is consistent
    For any response text, extracting cost data multiple times
    should produce the same result.
    
    Validates: Requirements 3.4
    """
    client = BedrockAdvisorClient()
    
    # Extract cost data multiple times
    data1 = client._extract_cost_data(response_text)
    data2 = client._extract_cost_data(response_text)
    data3 = client._extract_cost_data(response_text)
    
    # All should be identical
    assert data1 == data2 == data3


# Property: Prompt length is bounded
@given(
    query=st.text(min_size=1, max_size=5000),
    num_services=st.integers(min_value=0, max_value=10),
    num_history_turns=st.integers(min_value=0, max_value=10)
)
@settings(max_examples=100)
def test_prompt_length_bounded(query, num_services, num_history_turns):
    """
    Property: Prompt length is bounded
    For any query, context, and history, the prompt length
    should never exceed the maximum limit.
    
    Validates: Requirements 3.2, 17.3
    """
    client = BedrockAdvisorClient()
    
    # Create large context
    services = [f"service{i}" for i in range(num_services)]
    historical_costs = {}
    for service in services:
        historical_costs[service] = [
            {'date': f'2026-02-{i:02d}', 'blended_cost': 100.0, 'unblended_cost': 100.0, 'currency': 'USD'}
            for i in range(1, 29)
        ]
    
    context = CostContext(
        historical_costs=historical_costs,
        forecast_data=None,
        prevention_actions=[],
        current_budget=None,
        anomalies=[]
    )
    
    # Create large history
    history = []
    for i in range(num_history_turns):
        history.append(ConversationTurn(
            query=f"Previous query {i}" * 50,  # Long query
            response=f"Previous response {i}" * 50,  # Long response
            timestamp=datetime.now(UTC),
            context_used=context
        ))
    
    # Build prompt
    prompt = client.build_prompt(query, context, history)
    
    # Prompt should be bounded (4000 chars + some buffer for truncation message)
    assert len(prompt) <= 4100, \
        f"Prompt length {len(prompt)} exceeds maximum bound"
