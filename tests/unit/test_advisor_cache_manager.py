"""
Unit tests for AdvisorCacheManager.
"""
import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import Mock, MagicMock

from src.services.advisor_cache_manager import AdvisorCacheManager
from src.utils.types import AdvisorResponse


class TestCacheManagerInitialization:
    """Tests for AdvisorCacheManager initialization."""
    
    def test_cache_manager_initialization(self):
        """Test AdvisorCacheManager initializes correctly."""
        manager = AdvisorCacheManager()
        assert manager is not None
        assert manager.ttl_hours == 24
        assert manager.table_name == "advisor-cache"
        assert manager.cache_hits == 0
        assert manager.cache_misses == 0
    
    def test_cache_manager_with_custom_ttl(self):
        """Test AdvisorCacheManager with custom TTL."""
        manager = AdvisorCacheManager(ttl_hours=12)
        assert manager.ttl_hours == 12
    
    def test_cache_manager_with_dynamodb_client(self):
        """Test AdvisorCacheManager with DynamoDB client."""
        dynamodb_mock = Mock()
        manager = AdvisorCacheManager(dynamodb_client=dynamodb_mock)
        assert manager.dynamodb_client == dynamodb_mock


class TestCacheRetrieval:
    """Tests for cache retrieval."""
    
    def test_get_cached_response_no_client(self):
        """Test cache retrieval without DynamoDB client."""
        manager = AdvisorCacheManager()
        
        result = manager.get_cached_response("test_hash")
        
        assert result is None
        assert manager.cache_misses == 1
        assert manager.cache_hits == 0
    
    def test_get_cached_response_cache_miss(self):
        """Test cache retrieval when entry doesn't exist."""
        dynamodb_mock = Mock()
        dynamodb_mock.get_item.return_value = {}
        
        manager = AdvisorCacheManager(dynamodb_client=dynamodb_mock)
        
        result = manager.get_cached_response("test_hash")
        
        assert result is None
        assert manager.cache_misses == 1
        dynamodb_mock.get_item.assert_called_once()
    
    def test_get_cached_response_cache_hit(self):
        """Test successful cache retrieval."""
        dynamodb_mock = Mock()
        
        now = datetime.now(UTC)
        dynamodb_mock.get_item.return_value = {
            'Item': {
                'query_hash': {'S': 'test_hash'},
                'response_text': {'S': 'Cached response text'},
                'confidence': {'N': '0.9'},
                'cached_at': {'S': now.isoformat()},
                'ttl': {'N': str(int((now + timedelta(hours=24)).timestamp()))}
            }
        }
        
        manager = AdvisorCacheManager(dynamodb_client=dynamodb_mock)
        
        result = manager.get_cached_response("test_hash")
        
        assert result is not None
        assert isinstance(result, AdvisorResponse)
        assert result.response_text == 'Cached response text'
        assert result.confidence == 0.9
        assert result.cached is True
        assert manager.cache_hits == 1
        assert manager.cache_misses == 0
    
    def test_get_cached_response_expired(self):
        """Test cache retrieval with expired entry."""
        dynamodb_mock = Mock()
        
        # Entry cached 25 hours ago (expired with 24h TTL)
        cached_at = datetime.now(UTC) - timedelta(hours=25)
        dynamodb_mock.get_item.return_value = {
            'Item': {
                'query_hash': {'S': 'test_hash'},
                'response_text': {'S': 'Expired response'},
                'confidence': {'N': '0.8'},
                'cached_at': {'S': cached_at.isoformat()},
                'ttl': {'N': str(int((cached_at + timedelta(hours=24)).timestamp()))}
            }
        }
        
        manager = AdvisorCacheManager(dynamodb_client=dynamodb_mock)
        
        result = manager.get_cached_response("test_hash")
        
        assert result is None
        assert manager.cache_misses == 1
        assert manager.cache_hits == 0
    
    def test_get_cached_response_api_error(self):
        """Test cache retrieval with DynamoDB error."""
        dynamodb_mock = Mock()
        dynamodb_mock.get_item.side_effect = Exception("DynamoDB error")
        
        manager = AdvisorCacheManager(dynamodb_client=dynamodb_mock)
        
        result = manager.get_cached_response("test_hash")
        
        assert result is None
        assert manager.cache_misses == 1
    
    def test_get_cached_response_missing_confidence(self):
        """Test cache retrieval with missing confidence field."""
        dynamodb_mock = Mock()
        
        now = datetime.now(UTC)
        dynamodb_mock.get_item.return_value = {
            'Item': {
                'query_hash': {'S': 'test_hash'},
                'response_text': {'S': 'Response without confidence'},
                'cached_at': {'S': now.isoformat()},
                'ttl': {'N': str(int((now + timedelta(hours=24)).timestamp()))}
            }
        }
        
        manager = AdvisorCacheManager(dynamodb_client=dynamodb_mock)
        
        result = manager.get_cached_response("test_hash")
        
        assert result is not None
        assert result.confidence == 0.8  # Default value


class TestCacheStorage:
    """Tests for cache storage."""
    
    def test_store_response_no_client(self):
        """Test storing response without DynamoDB client."""
        manager = AdvisorCacheManager()
        
        response = AdvisorResponse(
            response_text="Test response",
            recommendations=[],
            cost_data={},
            confidence=0.9,
            cached=False
        )
        
        # Should not raise error
        manager.store_response("test_hash", response)
    
    def test_store_response_success(self):
        """Test successful response storage."""
        dynamodb_mock = Mock()
        
        manager = AdvisorCacheManager(dynamodb_client=dynamodb_mock)
        
        response = AdvisorResponse(
            response_text="Test response",
            recommendations=[],
            cost_data={},
            confidence=0.9,
            cached=False
        )
        
        manager.store_response("test_hash", response)
        
        dynamodb_mock.put_item.assert_called_once()
        call_args = dynamodb_mock.put_item.call_args
        
        assert call_args[1]['TableName'] == 'advisor-cache'
        assert call_args[1]['Item']['query_hash']['S'] == 'test_hash'
        assert call_args[1]['Item']['response_text']['S'] == 'Test response'
        assert call_args[1]['Item']['confidence']['N'] == '0.9'
    
    def test_store_response_with_custom_ttl(self):
        """Test storing response with custom TTL."""
        dynamodb_mock = Mock()
        
        manager = AdvisorCacheManager(dynamodb_client=dynamodb_mock, ttl_hours=24)
        
        response = AdvisorResponse(
            response_text="Test response",
            recommendations=[],
            cost_data={},
            confidence=0.8,
            cached=False
        )
        
        manager.store_response("test_hash", response, ttl_hours=12)
        
        dynamodb_mock.put_item.assert_called_once()
        # TTL should be set for 12 hours from now
    
    def test_store_response_api_error(self):
        """Test storing response with DynamoDB error."""
        dynamodb_mock = Mock()
        dynamodb_mock.put_item.side_effect = Exception("DynamoDB error")
        
        manager = AdvisorCacheManager(dynamodb_client=dynamodb_mock)
        
        response = AdvisorResponse(
            response_text="Test response",
            recommendations=[],
            cost_data={},
            confidence=0.8,
            cached=False
        )
        
        # Should not raise error
        manager.store_response("test_hash", response)


class TestCacheInvalidation:
    """Tests for cache invalidation."""
    
    def test_invalidate_cache_no_client(self):
        """Test cache invalidation without DynamoDB client."""
        manager = AdvisorCacheManager()
        
        # Should not raise error
        manager.invalidate_cache("test_hash")
    
    def test_invalidate_cache_success(self):
        """Test successful cache invalidation."""
        dynamodb_mock = Mock()
        
        manager = AdvisorCacheManager(dynamodb_client=dynamodb_mock)
        
        manager.invalidate_cache("test_hash")
        
        dynamodb_mock.delete_item.assert_called_once()
        call_args = dynamodb_mock.delete_item.call_args
        
        assert call_args[1]['TableName'] == 'advisor-cache'
        assert call_args[1]['Key']['query_hash']['S'] == 'test_hash'
    
    def test_invalidate_cache_api_error(self):
        """Test cache invalidation with DynamoDB error."""
        dynamodb_mock = Mock()
        dynamodb_mock.delete_item.side_effect = Exception("DynamoDB error")
        
        manager = AdvisorCacheManager(dynamodb_client=dynamodb_mock)
        
        # Should not raise error
        manager.invalidate_cache("test_hash")


class TestCacheHitRate:
    """Tests for cache hit rate calculation."""
    
    def test_get_cache_hit_rate_no_requests(self):
        """Test hit rate with no requests."""
        manager = AdvisorCacheManager()
        
        hit_rate = manager.get_cache_hit_rate()
        
        assert hit_rate == 0.0
    
    def test_get_cache_hit_rate_all_hits(self):
        """Test hit rate with all cache hits."""
        manager = AdvisorCacheManager()
        
        manager.cache_hits = 10
        manager.cache_misses = 0
        
        hit_rate = manager.get_cache_hit_rate()
        
        assert hit_rate == 100.0
    
    def test_get_cache_hit_rate_all_misses(self):
        """Test hit rate with all cache misses."""
        manager = AdvisorCacheManager()
        
        manager.cache_hits = 0
        manager.cache_misses = 10
        
        hit_rate = manager.get_cache_hit_rate()
        
        assert hit_rate == 0.0
    
    def test_get_cache_hit_rate_mixed(self):
        """Test hit rate with mixed hits and misses."""
        manager = AdvisorCacheManager()
        
        manager.cache_hits = 40
        manager.cache_misses = 60
        
        hit_rate = manager.get_cache_hit_rate()
        
        assert hit_rate == 40.0
    
    def test_get_cache_hit_rate_target_met(self):
        """Test hit rate meets 40% target."""
        manager = AdvisorCacheManager()
        
        manager.cache_hits = 45
        manager.cache_misses = 55
        
        hit_rate = manager.get_cache_hit_rate()
        
        assert hit_rate >= 40.0  # Meets target


class TestCacheManagerIntegration:
    """Integration tests for AdvisorCacheManager."""
    
    def test_cache_workflow_hit(self):
        """Test complete cache workflow with hit."""
        dynamodb_mock = Mock()
        
        now = datetime.now(UTC)
        dynamodb_mock.get_item.return_value = {
            'Item': {
                'query_hash': {'S': 'test_hash'},
                'response_text': {'S': 'Cached response'},
                'confidence': {'N': '0.9'},
                'cached_at': {'S': now.isoformat()},
                'ttl': {'N': str(int((now + timedelta(hours=24)).timestamp()))}
            }
        }
        
        manager = AdvisorCacheManager(dynamodb_client=dynamodb_mock)
        
        # First request - cache hit
        result = manager.get_cached_response("test_hash")
        
        assert result is not None
        assert result.cached is True
        assert manager.cache_hits == 1
        assert manager.cache_misses == 0
        assert manager.get_cache_hit_rate() == 100.0
    
    def test_cache_workflow_miss_then_store(self):
        """Test cache miss followed by storage."""
        dynamodb_mock = Mock()
        dynamodb_mock.get_item.return_value = {}
        
        manager = AdvisorCacheManager(dynamodb_client=dynamodb_mock)
        
        # First request - cache miss
        result = manager.get_cached_response("test_hash")
        assert result is None
        assert manager.cache_misses == 1
        
        # Store response
        response = AdvisorResponse(
            response_text="New response",
            recommendations=[],
            cost_data={},
            confidence=0.8,
            cached=False
        )
        manager.store_response("test_hash", response)
        
        dynamodb_mock.put_item.assert_called_once()
    
    def test_cache_workflow_invalidation(self):
        """Test cache invalidation workflow."""
        dynamodb_mock = Mock()
        
        manager = AdvisorCacheManager(dynamodb_client=dynamodb_mock)
        
        # Store response
        response = AdvisorResponse(
            response_text="Response to invalidate",
            recommendations=[],
            cost_data={},
            confidence=0.8,
            cached=False
        )
        manager.store_response("test_hash", response)
        
        # Invalidate
        manager.invalidate_cache("test_hash")
        
        dynamodb_mock.delete_item.assert_called_once()
    
    def test_cache_statistics_tracking(self):
        """Test cache statistics are tracked correctly."""
        dynamodb_mock = Mock()
        
        manager = AdvisorCacheManager(dynamodb_client=dynamodb_mock)
        
        # Simulate 3 misses
        dynamodb_mock.get_item.return_value = {}
        for i in range(3):
            manager.get_cached_response(f"hash_{i}")
        
        assert manager.cache_misses == 3
        assert manager.cache_hits == 0
        
        # Simulate 2 hits
        now = datetime.now(UTC)
        dynamodb_mock.get_item.return_value = {
            'Item': {
                'query_hash': {'S': 'test_hash'},
                'response_text': {'S': 'Cached'},
                'confidence': {'N': '0.8'},
                'cached_at': {'S': now.isoformat()},
                'ttl': {'N': str(int((now + timedelta(hours=24)).timestamp()))}
            }
        }
        
        for i in range(2):
            manager.get_cached_response(f"hash_{i}")
        
        assert manager.cache_hits == 2
        assert manager.cache_misses == 3
        assert manager.get_cache_hit_rate() == 40.0  # 2/5 = 40%
