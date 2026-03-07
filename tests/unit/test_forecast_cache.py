"""
Unit tests for Forecast Cache Manager.

Tests cover:
- Cache key generation
- Cache hit/miss scenarios
- TTL expiration
- Cache invalidation
- Hit rate tracking
"""

import pytest
import json
import time
from unittest.mock import Mock, MagicMock
from datetime import datetime, UTC, timedelta
from botocore.exceptions import ClientError

from src.services.forecast_cache import ForecastCacheManager


class TestForecastCacheManager:
    """Test suite for ForecastCacheManager."""
    
    @pytest.fixture
    def mock_dynamodb_client(self):
        """Create mock DynamoDB client."""
        return Mock()
    
    @pytest.fixture
    def cache_manager(self, mock_dynamodb_client):
        """Create ForecastCacheManager instance."""
        return ForecastCacheManager(
            dynamodb_client=mock_dynamodb_client,
            table_name='test-forecast-cache',
            ttl_hours=24
        )
    
    @pytest.fixture
    def sample_forecast(self):
        """Create sample forecast data."""
        return {
            'success': True,
            'forecast_data': [
                {
                    'date': '2024-02-01',
                    'predicted_cost': 25.0,
                    'confidence_lower': 20.0,
                    'confidence_upper': 30.0
                }
            ],
            'metadata': {
                'timestamp': '2024-01-31T12:00:00Z',
                'forecast_horizon': 1,
                'granularity': 'daily'
            }
        }
    
    def test_initialization(self, mock_dynamodb_client):
        """Test cache manager initialization."""
        manager = ForecastCacheManager(
            dynamodb_client=mock_dynamodb_client,
            table_name='test-table',
            ttl_hours=48
        )
        
        assert manager.dynamodb_client == mock_dynamodb_client
        assert manager.table_name == 'test-table'
        assert manager.base_ttl_hours == 48
        assert manager.cache_hits == 0
        assert manager.cache_misses == 0
    
    def test_get_cache_key_with_service(self, cache_manager):
        """Test cache key generation for service-specific forecast."""
        key = cache_manager.get_cache_key('EC2', 30, 'daily')
        
        assert key.startswith('forecast:EC2:30:daily:')
        assert len(key) > 20  # Has hash suffix
    
    def test_get_cache_key_without_service(self, cache_manager):
        """Test cache key generation for total forecast."""
        key = cache_manager.get_cache_key(None, 30, 'daily')
        
        assert key.startswith('forecast:total:30:daily:')
    
    def test_get_cache_key_uniqueness(self, cache_manager):
        """Test different parameters generate different keys."""
        key1 = cache_manager.get_cache_key('EC2', 30, 'daily')
        key2 = cache_manager.get_cache_key('Lambda', 30, 'daily')
        key3 = cache_manager.get_cache_key('EC2', 14, 'daily')
        key4 = cache_manager.get_cache_key('EC2', 30, 'weekly')
        
        assert key1 != key2
        assert key1 != key3
        assert key1 != key4
        assert key2 != key3
    
    def test_get_cache_key_deterministic(self, cache_manager):
        """Test same parameters always generate same key."""
        key1 = cache_manager.get_cache_key('EC2', 30, 'daily')
        key2 = cache_manager.get_cache_key('EC2', 30, 'daily')
        
        assert key1 == key2
    
    def test_get_cached_forecast_miss_no_item(self, cache_manager, mock_dynamodb_client):
        """Test cache miss when item doesn't exist."""
        mock_dynamodb_client.get_item.return_value = {}
        
        result = cache_manager.get_cached_forecast('EC2', 30, 'daily')
        
        assert result is None
        assert cache_manager.cache_misses == 1
        assert cache_manager.cache_hits == 0
    
    def test_get_cached_forecast_miss_expired(self, cache_manager, mock_dynamodb_client, sample_forecast):
        """Test cache miss when TTL expired."""
        # Create expired item (TTL in the past)
        expired_ttl = int((datetime.now(UTC) - timedelta(hours=1)).timestamp())
        
        mock_dynamodb_client.get_item.return_value = {
            'Item': {
                'cache_key': {'S': 'test-key'},
                'forecast_data': {'S': json.dumps(sample_forecast)},
                'ttl': {'N': str(expired_ttl)},
                'created_at': {'S': '2024-01-30T12:00:00Z'}
            }
        }
        
        result = cache_manager.get_cached_forecast('EC2', 30, 'daily')
        
        assert result is None
        assert cache_manager.cache_misses == 1
        assert cache_manager.cache_hits == 0
    
    def test_get_cached_forecast_hit(self, cache_manager, mock_dynamodb_client, sample_forecast):
        """Test cache hit with valid item."""
        # Create valid item (TTL in the future)
        valid_ttl = int((datetime.now(UTC) + timedelta(hours=12)).timestamp())
        
        mock_dynamodb_client.get_item.return_value = {
            'Item': {
                'cache_key': {'S': 'test-key'},
                'forecast_data': {'S': json.dumps(sample_forecast)},
                'ttl': {'N': str(valid_ttl)},
                'created_at': {'S': '2024-01-31T12:00:00Z'}
            }
        }
        
        result = cache_manager.get_cached_forecast('EC2', 30, 'daily')
        
        assert result is not None
        assert result == sample_forecast
        assert cache_manager.cache_hits == 1
        assert cache_manager.cache_misses == 0
    
    def test_get_cached_forecast_handles_client_error(self, cache_manager, mock_dynamodb_client):
        """Test cache retrieval handles DynamoDB errors gracefully."""
        mock_dynamodb_client.get_item.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
            'GetItem'
        )
        
        result = cache_manager.get_cached_forecast('EC2', 30, 'daily')
        
        assert result is None
        assert cache_manager.cache_misses == 1
    
    def test_get_cached_forecast_handles_malformed_data(self, cache_manager, mock_dynamodb_client):
        """Test cache retrieval handles malformed cache entries."""
        mock_dynamodb_client.get_item.return_value = {
            'Item': {
                'cache_key': {'S': 'test-key'},
                'forecast_data': {'S': 'invalid json'},
                'ttl': {'N': '9999999999'}
            }
        }
        
        result = cache_manager.get_cached_forecast('EC2', 30, 'daily')
        
        assert result is None
        assert cache_manager.cache_misses == 1
    
    def test_store_forecast(self, cache_manager, mock_dynamodb_client, sample_forecast):
        """Test storing forecast in cache."""
        # Mock _get_access_count call (no existing cache entry)
        mock_dynamodb_client.get_item.return_value = {}
        
        cache_manager.store_forecast(sample_forecast, 'EC2', 30, 'daily')
        
        # Verify put_item was called
        assert mock_dynamodb_client.put_item.called
        call_args = mock_dynamodb_client.put_item.call_args
        
        # Check table name
        assert call_args[1]['TableName'] == 'test-forecast-cache'
        
        # Check item structure
        item = call_args[1]['Item']
        assert 'cache_key' in item
        assert 'forecast_data' in item
        assert 'ttl' in item
        assert 'created_at' in item
        assert item['service']['S'] == 'EC2'
        assert item['days']['N'] == '30'
        assert item['granularity']['S'] == 'daily'
        
        # Verify forecast data is JSON
        forecast_data = json.loads(item['forecast_data']['S'])
        assert forecast_data == sample_forecast
    
    def test_store_forecast_with_none_service(self, cache_manager, mock_dynamodb_client, sample_forecast):
        """Test storing total forecast (service=None)."""
        # Mock _get_access_count call (no existing cache entry)
        mock_dynamodb_client.get_item.return_value = {}
        
        cache_manager.store_forecast(sample_forecast, None, 30, 'daily')
        
        call_args = mock_dynamodb_client.put_item.call_args
        item = call_args[1]['Item']
        
        assert item['service']['S'] == 'total'
    
    def test_store_forecast_sets_ttl(self, cache_manager, mock_dynamodb_client, sample_forecast):
        """Test TTL is set correctly."""
        # Mock _get_access_count call (no existing cache entry)
        mock_dynamodb_client.get_item.return_value = {}
        
        before_time = datetime.now(UTC) + timedelta(hours=24)
        
        cache_manager.store_forecast(sample_forecast, 'EC2', 30, 'daily')
        
        after_time = datetime.now(UTC) + timedelta(hours=24)
        
        call_args = mock_dynamodb_client.put_item.call_args
        item = call_args[1]['Item']
        ttl = int(item['ttl']['N'])
        
        # TTL should be approximately 24 hours from now
        assert int(before_time.timestamp()) <= ttl <= int(after_time.timestamp())
    
    def test_store_forecast_handles_error(self, cache_manager, mock_dynamodb_client, sample_forecast):
        """Test store handles DynamoDB errors gracefully."""
        # Mock _get_access_count call (no existing cache entry)
        mock_dynamodb_client.get_item.return_value = {}
        
        mock_dynamodb_client.put_item.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
            'PutItem'
        )
        
        # Should not raise exception
        cache_manager.store_forecast(sample_forecast, 'EC2', 30, 'daily')
    
    def test_invalidate_all_empty_cache(self, cache_manager, mock_dynamodb_client):
        """Test invalidating empty cache."""
        mock_dynamodb_client.scan.return_value = {'Items': []}
        
        cache_manager.invalidate_all()
        
        # Scan should be called
        assert mock_dynamodb_client.scan.called
        # No delete calls since cache is empty
        assert not mock_dynamodb_client.delete_item.called
    
    def test_invalidate_all_with_items(self, cache_manager, mock_dynamodb_client):
        """Test invalidating cache with items."""
        mock_dynamodb_client.scan.return_value = {
            'Items': [
                {'cache_key': {'S': 'key1'}},
                {'cache_key': {'S': 'key2'}},
                {'cache_key': {'S': 'key3'}}
            ]
        }
        
        cache_manager.invalidate_all()
        
        # Should delete all 3 items
        assert mock_dynamodb_client.delete_item.call_count == 3
    
    def test_invalidate_all_with_pagination(self, cache_manager, mock_dynamodb_client):
        """Test invalidating cache with paginated results."""
        # First page
        mock_dynamodb_client.scan.side_effect = [
            {
                'Items': [
                    {'cache_key': {'S': 'key1'}},
                    {'cache_key': {'S': 'key2'}}
                ],
                'LastEvaluatedKey': {'cache_key': {'S': 'key2'}}
            },
            # Second page
            {
                'Items': [
                    {'cache_key': {'S': 'key3'}}
                ]
            }
        ]
        
        cache_manager.invalidate_all()
        
        # Should scan twice (pagination)
        assert mock_dynamodb_client.scan.call_count == 2
        # Should delete all 3 items
        assert mock_dynamodb_client.delete_item.call_count == 3
    
    def test_invalidate_all_handles_error(self, cache_manager, mock_dynamodb_client):
        """Test invalidate handles DynamoDB errors gracefully."""
        mock_dynamodb_client.scan.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
            'Scan'
        )
        
        # Should not raise exception
        cache_manager.invalidate_all()
    
    def test_track_cache_hit_rate_no_requests(self, cache_manager):
        """Test hit rate with no requests."""
        rate = cache_manager.track_cache_hit_rate()
        
        assert rate == 0.0
    
    def test_track_cache_hit_rate_all_hits(self, cache_manager):
        """Test hit rate with all hits."""
        cache_manager.cache_hits = 10
        cache_manager.cache_misses = 0
        
        rate = cache_manager.track_cache_hit_rate()
        
        assert rate == 1.0
    
    def test_track_cache_hit_rate_all_misses(self, cache_manager):
        """Test hit rate with all misses."""
        cache_manager.cache_hits = 0
        cache_manager.cache_misses = 10
        
        rate = cache_manager.track_cache_hit_rate()
        
        assert rate == 0.0
    
    def test_track_cache_hit_rate_mixed(self, cache_manager):
        """Test hit rate with mixed hits and misses."""
        cache_manager.cache_hits = 8
        cache_manager.cache_misses = 2
        
        rate = cache_manager.track_cache_hit_rate()
        
        assert rate == 0.8
    
    def test_cache_hit_rate_updates_with_operations(self, cache_manager, mock_dynamodb_client, sample_forecast):
        """Test hit rate updates as cache operations occur."""
        # Initial rate
        assert cache_manager.track_cache_hit_rate() == 0.0
        
        # Cache miss
        mock_dynamodb_client.get_item.return_value = {}
        cache_manager.get_cached_forecast('EC2', 30, 'daily')
        assert cache_manager.track_cache_hit_rate() == 0.0
        
        # Cache hit
        valid_ttl = int((datetime.now(UTC) + timedelta(hours=12)).timestamp())
        mock_dynamodb_client.get_item.return_value = {
            'Item': {
                'cache_key': {'S': 'test-key'},
                'forecast_data': {'S': json.dumps(sample_forecast)},
                'ttl': {'N': str(valid_ttl)},
                'created_at': {'S': '2024-01-31T12:00:00Z'}
            }
        }
        cache_manager.get_cached_forecast('EC2', 30, 'daily')
        assert cache_manager.track_cache_hit_rate() == 0.5
        
        # Another hit
        cache_manager.get_cached_forecast('Lambda', 30, 'daily')
        assert cache_manager.track_cache_hit_rate() == pytest.approx(0.666, rel=0.01)


class TestIntelligentCaching:
    """Test intelligent caching features."""
    
    @pytest.fixture
    def mock_dynamodb_client(self):
        """Create mock DynamoDB client."""
        return Mock()
    
    @pytest.fixture
    def cache_manager(self, mock_dynamodb_client):
        """Create ForecastCacheManager instance."""
        return ForecastCacheManager(
            dynamodb_client=mock_dynamodb_client,
            table_name='test-forecast-cache',
            ttl_hours=24
        )
    
    def test_adaptive_ttl_for_frequently_accessed_forecast(self, cache_manager, mock_dynamodb_client):
        """Test that frequently accessed forecasts get longer TTL."""
        import json
        
        # Mock existing cache item with high access count
        cache_key = cache_manager.get_cache_key('ec2', 30, 'daily')
        future_ttl = int((datetime.now(UTC) + timedelta(hours=12)).timestamp())
        
        mock_dynamodb_client.get_item.return_value = {
            'Item': {
                'cache_key': {'S': cache_key},
                'forecast_data': {'S': json.dumps({'test': 'data'})},
                'ttl': {'N': str(future_ttl)},
                'access_count': {'N': '6'},  # High access count
                'last_accessed': {'S': datetime.now(UTC).isoformat()}
            }
        }
        
        # Get cached forecast (should update TTL)
        cache_manager.get_cached_forecast('ec2', 30, 'daily')
        
        # Verify update_item was called (may be called multiple times - for cache entry and metrics)
        assert mock_dynamodb_client.update_item.called
        
        # Find the update_item call for the cache entry (not metrics)
        update_calls = [call for call in mock_dynamodb_client.update_item.call_args_list 
                       if call[1]['TableName'] == 'test-forecast-cache']
        
        assert len(update_calls) > 0
        call_args = update_calls[0]
        expr_values = call_args[1]['ExpressionAttributeValues']
        
        # Verify access_count was incremented
        assert ':count' in expr_values
        assert expr_values[':count']['N'] == '7'  # 6 + 1
    
    def test_persistent_cache_hit_rate_retrieval(self, cache_manager, mock_dynamodb_client):
        """Test retrieving persistent cache hit rate from DynamoDB."""
        metrics_key = 'CACHE_METRICS:AGGREGATE'
        
        mock_dynamodb_client.get_item.return_value = {
            'Item': {
                'cache_key': {'S': metrics_key},
                'total_hits': {'N': '80'},
                'total_misses': {'N': '20'}
            }
        }
        
        hit_rate = cache_manager.get_persistent_cache_hit_rate()
        
        assert hit_rate == 0.8  # 80 / (80 + 20)
        assert mock_dynamodb_client.get_item.called
    
    def test_persistent_cache_hit_rate_no_metrics(self, cache_manager, mock_dynamodb_client):
        """Test persistent cache hit rate returns None when no metrics exist."""
        mock_dynamodb_client.get_item.return_value = {}
        
        hit_rate = cache_manager.get_persistent_cache_hit_rate()
        
        assert hit_rate is None
    
    def test_store_forecast_with_adaptive_ttl(self, cache_manager, mock_dynamodb_client):
        """Test storing forecast with adaptive TTL based on previous access count."""
        import json
        
        cache_key = cache_manager.get_cache_key('ec2', 30, 'daily')
        
        # Mock previous cache entry with high access count
        mock_dynamodb_client.get_item.return_value = {
            'Item': {
                'cache_key': {'S': cache_key},
                'access_count': {'N': '6'}  # High access count
            }
        }
        
        forecast_data = {'test': 'forecast'}
        cache_manager.store_forecast(forecast_data, 'ec2', 30, 'daily')
        
        # Verify put_item was called
        assert mock_dynamodb_client.put_item.called
        call_args = mock_dynamodb_client.put_item.call_args
        item = call_args[1]['Item']
        
        # Verify adaptive_ttl_hours is set (should be 36 hours for 6+ accesses: 24 * 1.5)
        assert 'adaptive_ttl_hours' in item
        assert int(item['adaptive_ttl_hours']['N']) == 36  # 24 * 1.5
    
    def test_access_count_tracking(self, cache_manager, mock_dynamodb_client):
        """Test that access count is tracked and updated."""
        import json
        
        cache_key = cache_manager.get_cache_key('ec2', 30, 'daily')
        future_ttl = int((datetime.now(UTC) + timedelta(hours=12)).timestamp())
        
        # First access
        mock_dynamodb_client.get_item.return_value = {
            'Item': {
                'cache_key': {'S': cache_key},
                'forecast_data': {'S': json.dumps({'test': 'data'})},
                'ttl': {'N': str(future_ttl)},
                'access_count': {'N': '0'}
            }
        }
        
        cache_manager.get_cached_forecast('ec2', 30, 'daily')
        
        # Verify update_item was called (may be called multiple times)
        assert mock_dynamodb_client.update_item.called
        
        # Find the update_item call for the cache entry (not metrics)
        update_calls = [call for call in mock_dynamodb_client.update_item.call_args_list 
                       if call[1]['TableName'] == 'test-forecast-cache']
        
        assert len(update_calls) > 0
        call_args = update_calls[0]
        expr_values = call_args[1]['ExpressionAttributeValues']
        assert expr_values[':count']['N'] == '1'
    
    def test_cache_warming(self, cache_manager, mock_dynamodb_client):
        """Test cache warming for common queries."""
        common_queries = [
            {'service': None, 'days': 30, 'granularity': 'daily'},
            {'service': 'ec2', 'days': 7, 'granularity': 'daily'}
        ]
        
        # Mock get_item to return no cached items
        mock_dynamodb_client.get_item.return_value = {}
        
        # Test without generator (should return pending status)
        results = cache_manager.warm_cache(common_queries)
        
        assert results['warmed'] == 0
        assert results['cached'] == 0
        assert len(results['details']) == 2
        assert results['details'][0]['status'] == 'pending'
        
        # Test with generator
        def mock_generator(service, days, granularity):
            return {'test': 'forecast', 'service': service, 'days': days}
        
        mock_dynamodb_client.get_item.return_value = {}
        results = cache_manager.warm_cache(common_queries, forecast_generator=mock_generator)
        
        assert results['warmed'] == 2
        assert mock_dynamodb_client.put_item.call_count >= 2  # Should store forecasts