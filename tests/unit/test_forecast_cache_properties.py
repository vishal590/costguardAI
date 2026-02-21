"""
Property-based tests for Forecast Cache Manager.

Tests Properties 9, 10, and 11 from Phase 2 design.
"""

import json
from datetime import datetime, UTC, timedelta
from unittest.mock import Mock
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from src.services.forecast_cache import ForecastCacheManager


class TestForecastCacheProperties:
    """Property-based tests for cache manager."""
    
    def _create_cache_manager(self):
        """Create ForecastCacheManager instance with mocked DynamoDB."""
        mock_client = Mock()
        return ForecastCacheManager(
            dynamodb_client=mock_client,
            table_name='test-cache',
            ttl_hours=24
        ), mock_client
    
    @settings(
        max_examples=100,
        deadline=2000,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        service1=st.one_of(st.none(), st.sampled_from(['EC2', 'Lambda', 'DynamoDB', 'S3', 'RDS'])),
        service2=st.one_of(st.none(), st.sampled_from(['EC2', 'Lambda', 'DynamoDB', 'S3', 'RDS'])),
        days1=st.sampled_from([7, 14, 30]),
        days2=st.sampled_from([7, 14, 30]),
        granularity1=st.sampled_from(['daily', 'weekly']),
        granularity2=st.sampled_from(['daily', 'weekly'])
    )
    def test_property_9_cache_key_uniqueness(
        self, service1, service2, days1, days2, granularity1, granularity2
    ):
        """
        Property 9: Cache Key Uniqueness
        
        For any two forecast requests with different parameters
        (service, days, or granularity), they should generate
        different cache keys.
        
        Validates: Requirements 4.5
        """
        cache_manager, _ = self._create_cache_manager()
        
        key1 = cache_manager.get_cache_key(service1, days1, granularity1)
        key2 = cache_manager.get_cache_key(service2, days2, granularity2)
        
        # If parameters are different, keys should be different
        if (service1, days1, granularity1) != (service2, days2, granularity2):
            assert key1 != key2
        else:
            # Same parameters should produce same key
            assert key1 == key2
    
    @settings(
        max_examples=100,
        deadline=2000,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        service=st.one_of(st.none(), st.sampled_from(['EC2', 'Lambda', 'DynamoDB'])),
        days=st.sampled_from([7, 14, 30]),
        granularity=st.sampled_from(['daily', 'weekly']),
        ttl_offset_hours=st.integers(min_value=-48, max_value=48)
    )
    def test_property_10_cache_ttl_enforcement(
        self, service, days, granularity, ttl_offset_hours
    ):
        """
        Property 10: Cache TTL Enforcement
        
        For any cached forecast, if the current time exceeds the TTL,
        the cache should return None (cache miss).
        
        Validates: Requirements 4.3
        """
        cache_manager, mock_client = self._create_cache_manager()
        
        # Create forecast with TTL offset from current time
        ttl_time = datetime.now(UTC) + timedelta(hours=ttl_offset_hours)
        ttl = int(ttl_time.timestamp())
        
        sample_forecast = {
            'success': True,
            'forecast_data': [{'date': '2024-02-01', 'predicted_cost': 25.0}]
        }
        
        mock_client.get_item.return_value = {
            'Item': {
                'cache_key': {'S': 'test-key'},
                'forecast_data': {'S': json.dumps(sample_forecast)},
                'ttl': {'N': str(ttl)},
                'created_at': {'S': datetime.now(UTC).isoformat()}
            }
        }
        
        result = cache_manager.get_cached_forecast(service, days, granularity)
        
        # If TTL is in the past (negative or zero offset), should be cache miss
        if ttl_offset_hours <= 0:
            assert result is None
            assert cache_manager.cache_misses > 0
        else:
            # TTL in future, should be cache hit
            assert result is not None
            assert cache_manager.cache_hits > 0
    
    @settings(
        max_examples=100,
        deadline=2000,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        num_items=st.integers(min_value=0, max_value=10),
        service=st.one_of(st.none(), st.sampled_from(['EC2', 'Lambda'])),
        days=st.sampled_from([7, 14, 30]),
        granularity=st.sampled_from(['daily', 'weekly'])
    )
    def test_property_11_cache_invalidation_completeness(
        self, num_items, service, days, granularity
    ):
        """
        Property 11: Cache Invalidation Completeness
        
        For any cache state, after calling invalidate_all(),
        all subsequent cache lookups should return None (cache miss).
        
        Validates: Requirements 4.4
        """
        cache_manager, mock_client = self._create_cache_manager()
        
        # Create cache items
        items = [
            {'cache_key': {'S': f'key{i}'}}
            for i in range(num_items)
        ]
        
        mock_client.scan.return_value = {'Items': items}
        
        # Invalidate all
        cache_manager.invalidate_all()
        
        # Verify all items were deleted
        assert mock_client.delete_item.call_count == num_items
        
        # After invalidation, cache lookups should miss
        mock_client.get_item.return_value = {}  # No item found
        
        result = cache_manager.get_cached_forecast(service, days, granularity)
        
        assert result is None
        assert cache_manager.cache_misses > 0
    
    @settings(
        max_examples=100,
        deadline=2000,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        service=st.one_of(st.none(), st.sampled_from(['EC2', 'Lambda', 'DynamoDB'])),
        days=st.sampled_from([7, 14, 30]),
        granularity=st.sampled_from(['daily', 'weekly'])
    )
    def test_cache_key_determinism(self, service, days, granularity):
        """
        Test that cache keys are deterministic.
        
        For any parameters, calling get_cache_key multiple times
        should always return the same key.
        
        Validates: Requirements 4.5
        """
        cache_manager, _ = self._create_cache_manager()
        
        key1 = cache_manager.get_cache_key(service, days, granularity)
        key2 = cache_manager.get_cache_key(service, days, granularity)
        key3 = cache_manager.get_cache_key(service, days, granularity)
        
        assert key1 == key2 == key3
    
    @settings(
        max_examples=100,
        deadline=2000,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        service=st.one_of(st.none(), st.sampled_from(['EC2', 'Lambda'])),
        days=st.sampled_from([7, 14, 30]),
        granularity=st.sampled_from(['daily', 'weekly']),
        ttl_hours=st.integers(min_value=1, max_value=72)
    )
    def test_ttl_calculation_correctness(
        self, service, days, granularity, ttl_hours
    ):
        """
        Test that TTL is calculated correctly.
        
        For any TTL hours setting, stored forecasts should have
        TTL set to approximately that many hours in the future.
        
        Validates: Requirements 4.1, 4.3
        """
        cache_manager = ForecastCacheManager(
            dynamodb_client=Mock(),
            table_name='test-cache',
            ttl_hours=ttl_hours
        )
        
        sample_forecast = {'success': True, 'forecast_data': []}
        
        before_time = datetime.now(UTC) + timedelta(hours=ttl_hours)
        
        cache_manager.store_forecast(sample_forecast, service, days, granularity)
        
        after_time = datetime.now(UTC) + timedelta(hours=ttl_hours)
        
        # Verify put_item was called with correct TTL
        call_args = cache_manager.dynamodb_client.put_item.call_args
        item = call_args[1]['Item']
        ttl = int(item['ttl']['N'])
        
        # TTL should be approximately ttl_hours from now
        assert int(before_time.timestamp()) <= ttl <= int(after_time.timestamp())
    
    @settings(
        max_examples=100,
        deadline=2000,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        hits=st.integers(min_value=0, max_value=100),
        misses=st.integers(min_value=0, max_value=100)
    )
    def test_hit_rate_calculation(self, hits, misses):
        """
        Test that hit rate is calculated correctly.
        
        For any number of hits and misses, the hit rate should
        equal hits / (hits + misses).
        
        Validates: Requirements 4.6
        """
        cache_manager, _ = self._create_cache_manager()
        
        cache_manager.cache_hits = hits
        cache_manager.cache_misses = misses
        
        rate = cache_manager.track_cache_hit_rate()
        
        if hits + misses == 0:
            assert rate == 0.0
        else:
            expected_rate = hits / (hits + misses)
            assert rate == pytest.approx(expected_rate, rel=0.001)
