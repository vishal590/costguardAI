"""
Property-based tests for AI/ML Cache Manager

Tests Property 14: Cache Consistency
Validates: Requirements NFR-5.2
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta, UTC
from unittest.mock import Mock, MagicMock
import json
import time
from src.services.ai_ml.ai_ml_cache_manager import AIMLCacheManager


# Strategies for generating test data
@st.composite
def cache_type_strategy(draw):
    """Generate cache type strings"""
    cache_types = [
        'gpu_costs',
        'workload_classification',
        'cost_per_inference',
        'cost_per_training',
        'sagemaker_costs',
        'bedrock_costs'
    ]
    return draw(st.sampled_from(cache_types))


@st.composite
def cache_params_strategy(draw):
    """Generate cache parameter dictionaries"""
    # Generate random parameters
    num_params = draw(st.integers(min_value=1, max_value=5))
    params = {}
    
    for i in range(num_params):
        key = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))
        value = draw(st.one_of(
            st.text(min_size=1, max_size=50),
            st.integers(min_value=0, max_value=1000000),
            st.floats(min_value=0.0, max_value=1000000.0, allow_nan=False, allow_infinity=False)
        ))
        params[key] = str(value)  # Convert to string for consistency
    
    return params


@st.composite
def cache_data_strategy(draw):
    """Generate cache data dictionaries"""
    return {
        'costs': draw(st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False)),
        'timestamp': datetime.now(UTC).isoformat(),
        'items': draw(st.lists(st.dictionaries(
            keys=st.text(min_size=1, max_size=20),
            values=st.one_of(st.text(), st.integers(), st.floats(allow_nan=False, allow_infinity=False))
        ), min_size=0, max_size=10))
    }


class TestCacheConsistencyProperties:
    """Property tests for cache consistency (Property 14)"""

    @given(
        cache_type=cache_type_strategy(),
        params=cache_params_strategy(),
        data=cache_data_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_cache_key_deterministic(self, cache_type, params, data):
        """
        Feature: ai-ml-workload-costs, Property 14: Cache Consistency
        
        For any cache type and parameters, generating the cache key multiple times
        should produce the same result (deterministic key generation).
        """
        # Create mock DynamoDB client
        mock_dynamodb = Mock()
        
        # Create cache manager
        cache_manager = AIMLCacheManager(mock_dynamodb)
        
        # Generate cache key multiple times
        key1 = cache_manager.get_cache_key(cache_type, **params)
        key2 = cache_manager.get_cache_key(cache_type, **params)
        key3 = cache_manager.get_cache_key(cache_type, **params)
        
        # All keys should be identical
        assert key1 == key2 == key3, "Cache key generation should be deterministic"
        
        # Key should start with 'aiml:' prefix
        assert key1.startswith('aiml:'), "Cache key should have aiml: prefix"
        
        # Key should contain cache type
        assert cache_type in key1, "Cache key should contain cache type"

    @given(
        cache_type=cache_type_strategy(),
        params=cache_params_strategy(),
        data=cache_data_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_cache_stores_and_retrieves_within_ttl(self, cache_type, params, data):
        """
        Feature: ai-ml-workload-costs, Property 14: Cache Consistency
        
        For any cache data stored with a TTL, retrieving it within the TTL period
        should return the same data.
        """
        # Create mock DynamoDB client
        mock_dynamodb = Mock()
        
        # Create cache manager with 24-hour TTL
        cache_manager = AIMLCacheManager(mock_dynamodb, ttl_hours=24)
        
        # Store data
        cache_manager.store_data(data, cache_type, **params)
        
        # Verify put_item was called
        assert mock_dynamodb.put_item.called, "store_data should call put_item"
        
        # Get the stored item
        put_call_args = mock_dynamodb.put_item.call_args
        stored_item = put_call_args[1]['Item']
        
        # Verify stored data structure
        assert 'cache_key' in stored_item
        assert 'data' in stored_item
        assert 'ttl' in stored_item
        assert 'created_at' in stored_item
        assert 'cache_type' in stored_item
        
        # Verify data is JSON serializable
        stored_data = json.loads(stored_item['data']['S'])
        assert stored_data == data, "Stored data should match original data"
        
        # Verify TTL is set correctly (should be ~24 hours from now)
        ttl_timestamp = int(stored_item['ttl']['N'])
        current_timestamp = int(datetime.now(UTC).timestamp())
        ttl_diff_hours = (ttl_timestamp - current_timestamp) / 3600
        
        # TTL should be approximately 24 hours (allow 1 minute tolerance)
        assert 23.98 <= ttl_diff_hours <= 24.02, f"TTL should be ~24 hours, got {ttl_diff_hours}"

    @given(
        cache_type=cache_type_strategy(),
        params=cache_params_strategy(),
        data=cache_data_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_cache_miss_when_not_found(self, cache_type, params, data):
        """
        Feature: ai-ml-workload-costs, Property 14: Cache Consistency
        
        For any cache query where data doesn't exist, the cache should return None
        and increment cache miss counter.
        """
        # Create mock DynamoDB client that returns no item
        mock_dynamodb = Mock()
        mock_dynamodb.get_item.return_value = {}  # No 'Item' key
        
        # Create cache manager
        cache_manager = AIMLCacheManager(mock_dynamodb)
        
        # Try to get cached data
        result = cache_manager.get_cached_data(cache_type, **params)
        
        # Should return None
        assert result is None, "Cache miss should return None"
        
        # Cache miss counter should increment
        assert cache_manager.cache_misses == 1, "Cache miss counter should increment"
        assert cache_manager.cache_hits == 0, "Cache hit counter should remain 0"

    @given(
        cache_type=cache_type_strategy(),
        params=cache_params_strategy(),
        data=cache_data_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_cache_miss_when_expired(self, cache_type, params, data):
        """
        Feature: ai-ml-workload-costs, Property 14: Cache Consistency
        
        For any cached data with an expired TTL, retrieving it should return None
        (cache miss) even though the data exists.
        """
        # Create mock DynamoDB client
        mock_dynamodb = Mock()
        
        # Create expired cache entry (TTL in the past)
        expired_ttl = int((datetime.now(UTC) - timedelta(hours=1)).timestamp())
        
        mock_dynamodb.get_item.return_value = {
            'Item': {
                'cache_key': {'S': 'test_key'},
                'data': {'S': json.dumps(data)},
                'ttl': {'N': str(expired_ttl)},
                'created_at': {'S': datetime.now(UTC).isoformat()},
                'cache_type': {'S': cache_type}
            }
        }
        
        # Create cache manager
        cache_manager = AIMLCacheManager(mock_dynamodb)
        
        # Try to get cached data
        result = cache_manager.get_cached_data(cache_type, **params)
        
        # Should return None because TTL expired
        assert result is None, "Expired cache should return None"
        
        # Should count as cache miss
        assert cache_manager.cache_misses == 1, "Expired cache should count as miss"
        assert cache_manager.cache_hits == 0, "Expired cache should not count as hit"

    @given(
        cache_type=cache_type_strategy(),
        params=cache_params_strategy(),
        data=cache_data_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_cache_hit_when_valid(self, cache_type, params, data):
        """
        Feature: ai-ml-workload-costs, Property 14: Cache Consistency
        
        For any cached data with a valid TTL, retrieving it should return the data
        and increment cache hit counter.
        """
        # Create mock DynamoDB client
        mock_dynamodb = Mock()
        
        # Create valid cache entry (TTL in the future)
        valid_ttl = int((datetime.now(UTC) + timedelta(hours=23)).timestamp())
        
        mock_dynamodb.get_item.return_value = {
            'Item': {
                'cache_key': {'S': 'test_key'},
                'data': {'S': json.dumps(data)},
                'ttl': {'N': str(valid_ttl)},
                'created_at': {'S': datetime.now(UTC).isoformat()},
                'cache_type': {'S': cache_type}
            }
        }
        
        # Create cache manager
        cache_manager = AIMLCacheManager(mock_dynamodb)
        
        # Try to get cached data
        result = cache_manager.get_cached_data(cache_type, **params)
        
        # Should return the data
        assert result == data, "Valid cache should return stored data"
        
        # Should count as cache hit
        assert cache_manager.cache_hits == 1, "Valid cache should count as hit"
        assert cache_manager.cache_misses == 0, "Valid cache should not count as miss"

    @given(
        cache_type=cache_type_strategy(),
        params1=cache_params_strategy(),
        params2=cache_params_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_different_params_generate_different_keys(self, cache_type, params1, params2):
        """
        Feature: ai-ml-workload-costs, Property 14: Cache Consistency
        
        For any two different parameter sets, the generated cache keys should be different
        (unless parameters happen to be identical).
        """
        # Skip if params are identical
        assume(params1 != params2)
        
        # Create mock DynamoDB client
        mock_dynamodb = Mock()
        
        # Create cache manager
        cache_manager = AIMLCacheManager(mock_dynamodb)
        
        # Generate cache keys
        key1 = cache_manager.get_cache_key(cache_type, **params1)
        key2 = cache_manager.get_cache_key(cache_type, **params2)
        
        # Keys should be different
        assert key1 != key2, "Different parameters should generate different cache keys"

    @given(
        cache_type=cache_type_strategy(),
        data=cache_data_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_cache_hit_rate_calculation(self, cache_type, data):
        """
        Feature: ai-ml-workload-costs, Property 14: Cache Consistency
        
        For any sequence of cache hits and misses, the hit rate should be calculated
        correctly as hits / (hits + misses).
        """
        # Create mock DynamoDB client
        mock_dynamodb = Mock()
        
        # Create cache manager
        cache_manager = AIMLCacheManager(mock_dynamodb)
        
        # Simulate some hits and misses
        cache_manager.cache_hits = 7
        cache_manager.cache_misses = 3
        
        # Calculate hit rate
        hit_rate = cache_manager.get_cache_hit_rate()
        
        # Should be 0.7 (7 hits out of 10 total)
        assert abs(hit_rate - 0.7) < 0.001, f"Hit rate should be 0.7, got {hit_rate}"
        
        # Test with no requests
        cache_manager.cache_hits = 0
        cache_manager.cache_misses = 0
        hit_rate = cache_manager.get_cache_hit_rate()
        assert hit_rate == 0.0, "Hit rate should be 0.0 when no requests"
        
        # Test with all hits
        cache_manager.cache_hits = 10
        cache_manager.cache_misses = 0
        hit_rate = cache_manager.get_cache_hit_rate()
        assert hit_rate == 1.0, "Hit rate should be 1.0 when all hits"
        
        # Test with all misses
        cache_manager.cache_hits = 0
        cache_manager.cache_misses = 10
        hit_rate = cache_manager.get_cache_hit_rate()
        assert hit_rate == 0.0, "Hit rate should be 0.0 when all misses"

    @given(
        cache_type=cache_type_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_cache_invalidation_by_type(self, cache_type):
        """
        Feature: ai-ml-workload-costs, Property 14: Cache Consistency
        
        For any cache type, invalidating all entries of that type should delete
        only entries matching that type.
        """
        # Create mock DynamoDB client
        mock_dynamodb = Mock()
        
        # Mock scan to return some items
        mock_dynamodb.scan.return_value = {
            'Items': [
                {'cache_key': {'S': 'key1'}},
                {'cache_key': {'S': 'key2'}},
                {'cache_key': {'S': 'key3'}}
            ]
        }
        
        # Create cache manager
        cache_manager = AIMLCacheManager(mock_dynamodb)
        
        # Invalidate by type
        count = cache_manager.invalidate_by_type(cache_type)
        
        # Should have deleted 3 items
        assert count == 3, f"Should have invalidated 3 items, got {count}"
        
        # Should have called delete_item 3 times
        assert mock_dynamodb.delete_item.call_count == 3, "Should call delete_item for each item"

    def test_cache_stats_structure(self):
        """
        Feature: ai-ml-workload-costs, Property 14: Cache Consistency
        
        For any cache manager, get_cache_stats should return a dictionary with
        the correct structure and fields.
        """
        # Create mock DynamoDB client
        mock_dynamodb = Mock()
        
        # Create cache manager
        cache_manager = AIMLCacheManager(mock_dynamodb)
        
        # Set some stats
        cache_manager.cache_hits = 15
        cache_manager.cache_misses = 5
        
        # Get stats
        stats = cache_manager.get_cache_stats()
        
        # Verify structure
        assert 'cache_hits' in stats
        assert 'cache_misses' in stats
        assert 'hit_rate' in stats
        assert 'total_requests' in stats
        
        # Verify values
        assert stats['cache_hits'] == 15
        assert stats['cache_misses'] == 5
        assert stats['total_requests'] == 20
        assert abs(stats['hit_rate'] - 0.75) < 0.001
