"""
Property-based tests for AdvisorCacheManager.

Feature: ai-cost-advisor
Properties tested:
- Property 4: Response Caching Correctness
- Property 5: Cache Invalidation Consistency
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta, UTC
from unittest.mock import Mock

from src.services.advisor_cache_manager import AdvisorCacheManager
from src.utils.types import AdvisorResponse


# Feature: ai-cost-advisor, Property 4: Response Caching Correctness
@given(
    query_hash=st.text(min_size=1, max_size=100),
    response_text=st.text(min_size=1, max_size=1000),
    confidence=st.floats(min_value=0.0, max_value=1.0)
)
@settings(max_examples=100, deadline=None)
def test_response_caching_correctness(query_hash, response_text, confidence):
    """
    Property 4: Response Caching Correctness
    
    For any query, if a cached response exists and is within TTL,
    the system should return the cached response; otherwise, it should
    invoke Bedrock and cache the new response.
    
    Validates: Requirements 9.1, 9.2, 9.3, 9.4
    """
    dynamodb_mock = Mock()
    
    # Setup: Store response in cache
    now = datetime.now(UTC)
    dynamodb_mock.get_item.return_value = {
        'Item': {
            'query_hash': {'S': query_hash},
            'response_text': {'S': response_text},
            'confidence': {'N': str(confidence)},
            'cached_at': {'S': now.isoformat()},
            'ttl': {'N': str(int((now + timedelta(hours=24)).timestamp()))}
        }
    }
    
    manager = AdvisorCacheManager(dynamodb_client=dynamodb_mock)
    
    # Property: Cached response should be returned
    result = manager.get_cached_response(query_hash)
    
    assert result is not None
    assert result.response_text == response_text
    assert result.confidence == confidence
    assert result.cached is True


# Feature: ai-cost-advisor, Property 4: Response Caching Correctness (TTL expiration)
@given(
    query_hash=st.text(min_size=1, max_size=100),
    hours_ago=st.integers(min_value=25, max_value=100)
)
@settings(max_examples=100, deadline=None)
def test_expired_cache_returns_none(query_hash, hours_ago):
    """
    Property 4: Response Caching Correctness (Expiration)
    
    For any query with an expired cache entry (beyond TTL),
    the system should return None (cache miss).
    
    Validates: Requirements 9.1, 9.4
    """
    dynamodb_mock = Mock()
    
    # Setup: Entry cached beyond TTL
    cached_at = datetime.now(UTC) - timedelta(hours=hours_ago)
    dynamodb_mock.get_item.return_value = {
        'Item': {
            'query_hash': {'S': query_hash},
            'response_text': {'S': 'Expired response'},
            'confidence': {'N': '0.8'},
            'cached_at': {'S': cached_at.isoformat()},
            'ttl': {'N': str(int((cached_at + timedelta(hours=24)).timestamp()))}
        }
    }
    
    manager = AdvisorCacheManager(dynamodb_client=dynamodb_mock, ttl_hours=24)
    
    # Property: Expired cache should return None
    result = manager.get_cached_response(query_hash)
    
    assert result is None
    assert manager.cache_misses > 0


# Feature: ai-cost-advisor, Property 5: Cache Invalidation Consistency
@given(
    query_hash=st.text(min_size=1, max_size=100)
)
@settings(max_examples=100, deadline=None)
def test_cache_invalidation_consistency(query_hash):
    """
    Property 5: Cache Invalidation Consistency
    
    For any significant cost data change, all related cache entries
    should be invalidated to prevent stale responses.
    
    Validates: Requirements 9.5
    """
    dynamodb_mock = Mock()
    
    manager = AdvisorCacheManager(dynamodb_client=dynamodb_mock)
    
    # Property: Invalidation should call delete_item
    manager.invalidate_cache(query_hash)
    
    dynamodb_mock.delete_item.assert_called_once()
    call_args = dynamodb_mock.delete_item.call_args
    assert call_args[1]['Key']['query_hash']['S'] == query_hash


# Feature: ai-cost-advisor, Property 4: Cache storage correctness
@given(
    query_hash=st.text(min_size=1, max_size=100),
    response_text=st.text(min_size=1, max_size=1000),
    confidence=st.floats(min_value=0.0, max_value=1.0)
)
@settings(max_examples=100, deadline=None)
def test_cache_storage_correctness(query_hash, response_text, confidence):
    """
    Property 4: Cache Storage Correctness
    
    For any response, storing it in cache should preserve all
    essential fields (response_text, confidence, query_hash).
    
    Validates: Requirements 9.2, 9.3
    """
    dynamodb_mock = Mock()
    
    manager = AdvisorCacheManager(dynamodb_client=dynamodb_mock)
    
    response = AdvisorResponse(
        response_text=response_text,
        recommendations=[],
        cost_data={},
        confidence=confidence,
        cached=False
    )
    
    # Property: Storage should preserve fields
    manager.store_response(query_hash, response)
    
    dynamodb_mock.put_item.assert_called_once()
    call_args = dynamodb_mock.put_item.call_args
    item = call_args[1]['Item']
    
    assert item['query_hash']['S'] == query_hash
    assert item['response_text']['S'] == response_text
    assert float(item['confidence']['N']) == confidence


# Feature: ai-cost-advisor, Property 4: Cache hit rate calculation
@given(
    hits=st.integers(min_value=0, max_value=1000),
    misses=st.integers(min_value=0, max_value=1000)
)
@settings(max_examples=100, deadline=None)
def test_cache_hit_rate_calculation(hits, misses):
    """
    Property 4: Cache Hit Rate Calculation
    
    For any number of cache hits and misses, the hit rate should
    be correctly calculated as (hits / total) * 100.
    
    Validates: Requirements 9.6
    """
    manager = AdvisorCacheManager()
    
    manager.cache_hits = hits
    manager.cache_misses = misses
    
    hit_rate = manager.get_cache_hit_rate()
    
    total = hits + misses
    if total == 0:
        assert hit_rate == 0.0
    else:
        expected_rate = (hits / total) * 100
        assert abs(hit_rate - expected_rate) < 0.01  # Allow small floating point error


# Feature: ai-cost-advisor, Property 4: Cache never fails
@given(
    query_hash=st.text(min_size=1, max_size=100)
)
@settings(max_examples=100, deadline=None)
def test_cache_operations_never_fail(query_hash):
    """
    Property: Cache Operations Never Fail
    
    For any cache operation, even with errors, the system should
    handle gracefully without raising exceptions.
    
    Validates: Requirements 9.1-9.5
    """
    # Test with no client
    manager = AdvisorCacheManager()
    
    # All operations should succeed without errors
    result = manager.get_cached_response(query_hash)
    assert result is None
    
    response = AdvisorResponse(
        response_text="Test",
        recommendations=[],
        cost_data={},
        confidence=0.8,
        cached=False
    )
    
    manager.store_response(query_hash, response)
    manager.invalidate_cache(query_hash)
    hit_rate = manager.get_cache_hit_rate()
    
    assert isinstance(hit_rate, float)


# Feature: ai-cost-advisor, Property 4: Cache statistics consistency
@given(
    operations=st.lists(
        st.sampled_from(['hit', 'miss']),
        min_size=1,
        max_size=100
    )
)
@settings(max_examples=100, deadline=None)
def test_cache_statistics_consistency(operations):
    """
    Property: Cache Statistics Consistency
    
    For any sequence of cache operations, the statistics should
    accurately reflect the number of hits and misses.
    
    Validates: Requirements 9.6
    """
    manager = AdvisorCacheManager()
    
    expected_hits = operations.count('hit')
    expected_misses = operations.count('miss')
    
    # Simulate operations
    for op in operations:
        if op == 'hit':
            manager.cache_hits += 1
        else:
            manager.cache_misses += 1
    
    # Property: Statistics should match
    assert manager.cache_hits == expected_hits
    assert manager.cache_misses == expected_misses
    
    total = expected_hits + expected_misses
    expected_rate = (expected_hits / total) * 100 if total > 0 else 0.0
    actual_rate = manager.get_cache_hit_rate()
    
    assert abs(actual_rate - expected_rate) < 0.01


# Feature: ai-cost-advisor, Property 4: TTL consistency
@given(
    ttl_hours=st.integers(min_value=1, max_value=168)  # 1 hour to 1 week
)
@settings(max_examples=100, deadline=None)
def test_ttl_consistency(ttl_hours):
    """
    Property: TTL Consistency
    
    For any TTL value, the cache manager should respect it
    when determining cache freshness.
    
    Validates: Requirements 9.2, 9.3
    """
    manager = AdvisorCacheManager(ttl_hours=ttl_hours)
    
    assert manager.ttl_hours == ttl_hours
    
    # Test with entry just before expiry
    dynamodb_mock = Mock()
    cached_at = datetime.now(UTC) - timedelta(hours=ttl_hours - 1)
    dynamodb_mock.get_item.return_value = {
        'Item': {
            'query_hash': {'S': 'test'},
            'response_text': {'S': 'Test'},
            'confidence': {'N': '0.8'},
            'cached_at': {'S': cached_at.isoformat()},
            'ttl': {'N': str(int((cached_at + timedelta(hours=ttl_hours)).timestamp()))}
        }
    }
    
    manager.dynamodb_client = dynamodb_mock
    
    # Should still be valid (not expired)
    result = manager.get_cached_response("test")
    assert result is not None
