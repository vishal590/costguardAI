"""
Property-based tests for AdvisorEngine.

Feature: ai-cost-advisor
Properties tested:
- Property 6: Conversation Context Continuity
- Property 11: Response Time Bounds
- Property 12: Error Message Clarity
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, UTC
from unittest.mock import Mock
import time

from src.services.advisor_engine import AdvisorEngine
from src.utils.types import (
    QueryIntent, CostContext, ConversationTurn,
    AdvisorResponse, Recommendation, Insight
)


# Feature: ai-cost-advisor, Property 6: Conversation Context Continuity
@given(
    num_turns=st.integers(min_value=1, max_value=10),
    query=st.text(min_size=5, max_size=100)
)
@settings(max_examples=100, deadline=None)
def test_conversation_context_continuity(num_turns, query):
    """
    Property 6: Conversation Context Continuity
    
    For any follow-up query in a session, the system should include
    previous conversation turns in the context, enabling natural
    conversation flow.
    
    Validates: Requirements 7.1, 7.2, 7.3
    """
    # Setup mocks
    query_processor = Mock()
    context_manager = Mock()
    bedrock_client = Mock()
    response_formatter = Mock()
    cache_manager = Mock()
    insight_generator = Mock()
    dynamodb_client = Mock()
    
    # Mock conversation history with num_turns
    history_items = []
    for i in range(num_turns):
        history_items.append({
            "query": {"S": f"Query {i}"},
            "response": {"S": f"Response {i}"},
            "timestamp_iso": {"S": datetime.now(UTC).isoformat()}
        })
    
    dynamodb_client.query.return_value = {"Items": history_items}
    
    engine = AdvisorEngine(
        query_processor=query_processor,
        context_manager=context_manager,
        bedrock_client=bedrock_client,
        response_formatter=response_formatter,
        cache_manager=cache_manager,
        insight_generator=insight_generator,
        dynamodb_client=dynamodb_client
    )
    
    # Property: Retrieved history should match stored turns
    result = engine.get_conversation_history("session123")
    
    assert len(result) == num_turns
    assert all(isinstance(turn, ConversationTurn) for turn in result)


# Feature: ai-cost-advisor, Property 11: Response Time Bounds (Cached)
@given(
    query=st.text(min_size=5, max_size=100)
)
@settings(max_examples=50, deadline=None)
def test_cached_response_time_bounds(query):
    """
    Property 11: Response Time Bounds (Cached Queries)
    
    For any cached query, response time should be under 500ms.
    
    Validates: Requirements 16.1
    """
    # Setup mocks
    query_processor = Mock()
    context_manager = Mock()
    bedrock_client = Mock()
    response_formatter = Mock()
    cache_manager = Mock()
    insight_generator = Mock()
    
    # Mock query parsing (fast)
    intent = QueryIntent(
        intent_type="cost_analysis",
        services=["ec2"],
        time_range=(datetime.now(UTC), datetime.now(UTC)),
        accounts=[],
        entities={}
    )
    query_processor.parse_query.return_value = intent
    
    # Mock cache hit (fast)
    cached_response = AdvisorResponse(
        response_text="Cached response",
        recommendations=[],
        cost_data={},
        confidence=0.9,
        cached=False
    )
    cache_manager.get_cached_response.return_value = cached_response
    
    engine = AdvisorEngine(
        query_processor=query_processor,
        context_manager=context_manager,
        bedrock_client=bedrock_client,
        response_formatter=response_formatter,
        cache_manager=cache_manager,
        insight_generator=insight_generator
    )
    
    # Property: Cached response should be fast
    start_time = time.time()
    result = engine.process_query(query, "user123", "session456")
    elapsed_time = time.time() - start_time
    
    assert result.cached is True
    assert elapsed_time < 0.5  # Under 500ms


# Feature: ai-cost-advisor, Property 12: Error Message Clarity
@given(
    error_message=st.text(min_size=1, max_size=100)
)
@settings(max_examples=100, deadline=None)
def test_error_message_clarity(error_message):
    """
    Property 12: Error Message Clarity
    
    For any error condition, the system should return a user-friendly
    error message without technical jargon.
    
    Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5
    """
    # Setup mocks
    query_processor = Mock()
    context_manager = Mock()
    bedrock_client = Mock()
    response_formatter = Mock()
    cache_manager = Mock()
    insight_generator = Mock()
    
    # Mock error
    query_processor.parse_query.side_effect = Exception(error_message)
    
    engine = AdvisorEngine(
        query_processor=query_processor,
        context_manager=context_manager,
        bedrock_client=bedrock_client,
        response_formatter=response_formatter,
        cache_manager=cache_manager,
        insight_generator=insight_generator
    )
    
    # Property: Error response should be user-friendly
    result = engine.process_query("test query", "user123", "session456")
    
    assert result is not None
    assert isinstance(result, AdvisorResponse)
    assert len(result.response_text) > 0
    assert result.confidence == 0.0
    
    # Should contain apologetic language
    response_lower = result.response_text.lower()
    assert any(word in response_lower for word in ["apologize", "sorry", "error", "unable"])


# Feature: ai-cost-advisor, Property 6: Conversation history ordering
@given(
    num_turns=st.integers(min_value=2, max_value=10)
)
@settings(max_examples=100, deadline=None)
def test_conversation_history_chronological_order(num_turns):
    """
    Property 6: Conversation History Chronological Order
    
    For any conversation history, turns should be returned in
    chronological order (oldest first).
    
    Validates: Requirements 7.1, 7.2
    """
    # Setup mocks
    query_processor = Mock()
    context_manager = Mock()
    bedrock_client = Mock()
    response_formatter = Mock()
    cache_manager = Mock()
    insight_generator = Mock()
    dynamodb_client = Mock()
    
    # Mock conversation history with timestamps
    # DynamoDB returns in reverse order (most recent first)
    base_time = datetime(2026, 2, 1, tzinfo=UTC)
    history_items = []
    for i in range(num_turns - 1, -1, -1):  # Reverse order
        timestamp = base_time.replace(hour=i)
        history_items.append({
            "query": {"S": f"Query {i}"},
            "response": {"S": f"Response {i}"},
            "timestamp_iso": {"S": timestamp.isoformat()}
        })
    
    dynamodb_client.query.return_value = {"Items": history_items}
    
    engine = AdvisorEngine(
        query_processor=query_processor,
        context_manager=context_manager,
        bedrock_client=bedrock_client,
        response_formatter=response_formatter,
        cache_manager=cache_manager,
        insight_generator=insight_generator,
        dynamodb_client=dynamodb_client
    )
    
    # Property: History should be in chronological order
    result = engine.get_conversation_history("session123")
    
    for i in range(len(result) - 1):
        assert result[i].timestamp <= result[i + 1].timestamp


# Feature: ai-cost-advisor, Property 6: Cache key consistency
@given(
    query=st.text(min_size=5, max_size=100),
    services=st.lists(st.sampled_from(["ec2", "s3", "lambda", "dynamodb"]), min_size=1, max_size=3)
)
@settings(max_examples=100, deadline=None)
def test_cache_key_consistency(query, services):
    """
    Property: Cache Key Consistency
    
    For any query and intent, the cache key should be consistent
    across multiple generations.
    
    Validates: Requirements 9.1, 9.2
    """
    query_processor = Mock()
    context_manager = Mock()
    bedrock_client = Mock()
    response_formatter = Mock()
    cache_manager = Mock()
    insight_generator = Mock()
    
    engine = AdvisorEngine(
        query_processor=query_processor,
        context_manager=context_manager,
        bedrock_client=bedrock_client,
        response_formatter=response_formatter,
        cache_manager=cache_manager,
        insight_generator=insight_generator
    )
    
    intent = QueryIntent(
        intent_type="cost_analysis",
        services=services,
        time_range=(datetime(2026, 2, 1, tzinfo=UTC), datetime(2026, 2, 28, tzinfo=UTC)),
        accounts=[],
        entities={}
    )
    
    # Property: Same query and intent should produce same cache key
    key1 = engine._generate_cache_key(query, intent)
    key2 = engine._generate_cache_key(query, intent)
    
    assert key1 == key2
    assert isinstance(key1, str)
    assert len(key1) > 0


# Feature: ai-cost-advisor, Property: Proactive insights never fail
@given(
    user_id=st.text(min_size=1, max_size=50)
)
@settings(max_examples=100, deadline=None)
def test_proactive_insights_never_fail(user_id):
    """
    Property: Proactive Insights Never Fail
    
    For any user, generating proactive insights should never raise
    an exception, even if individual insight generators fail.
    
    Validates: Requirements 12.1-12.5
    """
    query_processor = Mock()
    context_manager = Mock()
    bedrock_client = Mock()
    response_formatter = Mock()
    cache_manager = Mock()
    insight_generator = Mock()
    
    # Mock some generators to fail
    insight_generator.generate_daily_summary.side_effect = Exception("Error")
    insight_generator.detect_anomalies.return_value = []
    insight_generator.suggest_optimizations.return_value = []
    insight_generator.check_forecast_alerts.side_effect = Exception("Error")
    
    engine = AdvisorEngine(
        query_processor=query_processor,
        context_manager=context_manager,
        bedrock_client=bedrock_client,
        response_formatter=response_formatter,
        cache_manager=cache_manager,
        insight_generator=insight_generator
    )
    
    # Property: Should return empty list, not raise exception
    result = engine.generate_proactive_insights(user_id)
    
    assert isinstance(result, list)


# Feature: ai-cost-advisor, Property: Query processing always returns response
@given(
    query=st.text(min_size=1, max_size=200),
    user_id=st.text(min_size=1, max_size=50),
    session_id=st.text(min_size=1, max_size=50)
)
@settings(max_examples=100, deadline=None)
def test_query_processing_always_returns_response(query, user_id, session_id):
    """
    Property: Query Processing Always Returns Response
    
    For any query, user, and session, the system should always
    return an AdvisorResponse, even if errors occur.
    
    Validates: Requirements 11.1-11.5
    """
    query_processor = Mock()
    context_manager = Mock()
    bedrock_client = Mock()
    response_formatter = Mock()
    cache_manager = Mock()
    insight_generator = Mock()
    
    # Mock potential failure
    query_processor.parse_query.side_effect = Exception("Parse error")
    
    engine = AdvisorEngine(
        query_processor=query_processor,
        context_manager=context_manager,
        bedrock_client=bedrock_client,
        response_formatter=response_formatter,
        cache_manager=cache_manager,
        insight_generator=insight_generator
    )
    
    # Property: Should always return AdvisorResponse
    result = engine.process_query(query, user_id, session_id)
    
    assert isinstance(result, AdvisorResponse)
    assert isinstance(result.response_text, str)
    assert len(result.response_text) > 0
