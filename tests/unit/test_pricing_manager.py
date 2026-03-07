"""
Unit tests for Pricing Manager.
"""
import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock, patch
import json

from src.services.pricing_manager import PricingManager
from src.utils.types import PricingData


class TestPricingManager:
    """Test PricingManager initialization."""
    
    def test_init_with_default_region(self):
        """Test initialization with default region."""
        mock_pricing_client = Mock()
        mock_dynamodb_client = Mock()
        
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_client=mock_dynamodb_client
        )
        
        assert manager.pricing_client == mock_pricing_client
        assert manager.dynamodb_client == mock_dynamodb_client
        assert manager.region == 'us-east-1'
    
    def test_init_with_custom_region(self):
        """Test initialization with custom region."""
        mock_pricing_client = Mock()
        mock_dynamodb_client = Mock()
        
        manager = PricingManager(
            region='us-west-2',
            pricing_client=mock_pricing_client,
            dynamodb_client=mock_dynamodb_client
        )
        
        assert manager.region == 'us-west-2'


class TestIsPricingStale:
    """Test is_pricing_stale method."""
    
    def test_pricing_is_stale_when_old(self):
        """Test that pricing is stale when older than max_age_hours."""
        mock_pricing_client = Mock()
        mock_dynamodb_client = Mock()
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_client=mock_dynamodb_client
        )
        
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        pricing = PricingData(
            service='ec2',
            region='us-east-1',
            prices={'t2.micro': Decimal('0.0116')},
            currency='USD',
            last_updated=old_time,
            ttl=86400
        )
        
        assert manager.is_pricing_stale(pricing, max_age_hours=24) is True
    
    def test_pricing_is_fresh_when_recent(self):
        """Test that pricing is fresh when within max_age_hours."""
        mock_pricing_client = Mock()
        mock_dynamodb_client = Mock()
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_client=mock_dynamodb_client
        )
        
        recent_time = datetime.now(timezone.utc) - timedelta(hours=1)
        pricing = PricingData(
            service='ec2',
            region='us-east-1',
            prices={'t2.micro': Decimal('0.0116')},
            currency='USD',
            last_updated=recent_time,
            ttl=86400
        )
        
        assert manager.is_pricing_stale(pricing, max_age_hours=24) is False
    
    def test_pricing_is_stale_when_none(self):
        """Test that None pricing is considered stale."""
        mock_pricing_client = Mock()
        mock_dynamodb_client = Mock()
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_client=mock_dynamodb_client
        )
        
        assert manager.is_pricing_stale(None) is True


class TestGetLocationName:
    """Test _get_location_name helper method."""
    
    def test_get_location_name_for_known_regions(self):
        """Test location name mapping for known regions."""
        mock_pricing_client = Mock()
        mock_dynamodb_client = Mock()
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_client=mock_dynamodb_client
        )
        
        assert manager._get_location_name('us-east-1') == 'US East (N. Virginia)'
        assert manager._get_location_name('us-west-2') == 'US West (Oregon)'
        assert manager._get_location_name('eu-west-1') == 'EU (Ireland)'
    
    def test_get_location_name_for_unknown_region(self):
        """Test location name defaults for unknown regions."""
        mock_pricing_client = Mock()
        mock_dynamodb_client = Mock()
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_client=mock_dynamodb_client
        )
        
        assert manager._get_location_name('unknown-region') == 'US East (N. Virginia)'


class TestGetDefaultPrices:
    """Test _get_default_prices helper method."""
    
    def test_get_default_prices_for_ec2(self):
        """Test default prices for EC2."""
        mock_pricing_client = Mock()
        mock_dynamodb_client = Mock()
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_client=mock_dynamodb_client
        )
        
        prices = manager._get_default_prices('ec2')
        
        assert 't2.micro' in prices
        assert prices['t2.micro'] == Decimal('0.0116')
    
    def test_get_default_prices_for_lambda(self):
        """Test default prices for Lambda."""
        mock_pricing_client = Mock()
        mock_dynamodb_client = Mock()
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_client=mock_dynamodb_client
        )
        
        prices = manager._get_default_prices('lambda')
        
        assert 'request' in prices
        assert 'gb_second' in prices
    
    def test_get_default_prices_for_unknown_service(self):
        """Test default prices for unknown service."""
        mock_pricing_client = Mock()
        mock_dynamodb_client = Mock()
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_client=mock_dynamodb_client
        )
        
        prices = manager._get_default_prices('unknown')
        
        assert prices == {}


class TestCachePricingData:
    """Test cache_pricing_data method."""
    
    def test_cache_pricing_data_stores_in_dynamodb(self):
        """Test that pricing data is stored in DynamoDB."""
        from unittest.mock import MagicMock
        
        mock_pricing_client = Mock()
        mock_dynamodb_resource = MagicMock()
        mock_table = MagicMock()
        mock_dynamodb_resource.Table.return_value = mock_table
        
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_resource=mock_dynamodb_resource
        )
        
        pricing = PricingData(
            service='ec2',
            region='us-east-1',
            prices={'t2.micro': Decimal('0.0116')},
            currency='USD',
            last_updated=datetime.now(timezone.utc),
            ttl=86400
        )
        
        manager.cache_pricing_data('ec2', 'us-east-1', pricing)
        
        # Verify put_item was called on the table
        assert mock_table.put_item.called
        call_args = mock_table.put_item.call_args
        
        # Verify the item structure (using resource API format - plain dict)
        item = call_args[1]['Item']
        assert item['cache_key'] == 'ec2#us-east-1'
        assert item['service'] == 'ec2'
        assert item['region'] == 'us-east-1'
        assert 't2.micro' in item['prices']


class TestGetFromCache:
    """Test _get_from_cache method."""
    
    def test_get_from_cache_returns_cached_data(self):
        """Test retrieving cached pricing data."""
        from unittest.mock import MagicMock
        
        mock_pricing_client = Mock()
        mock_dynamodb_resource = MagicMock()
        mock_table = MagicMock()
        mock_dynamodb_resource.Table.return_value = mock_table
        
        # Mock DynamoDB response (resource API format - plain dict)
        cached_time = datetime.now(timezone.utc)
        future_ttl = int((cached_time.timestamp() + 86400))
        mock_table.get_item.return_value = {
            'Item': {
                'cache_key': 'ec2#us-east-1',
                'service': 'ec2',
                'region': 'us-east-1',
                'prices': {'t2.micro': '0.0116'},  # Already converted to dict
                'currency': 'USD',
                'last_updated': cached_time.isoformat(),
                'ttl': future_ttl
            }
        }
        
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_resource=mock_dynamodb_resource
        )
        
        result = manager._get_from_cache('ec2', 'us-east-1')
        
        assert result is not None
        assert result.service == 'ec2'
        assert result.region == 'us-east-1'
        assert 't2.micro' in result.prices
    
    def test_get_from_cache_returns_none_when_not_found(self):
        """Test that None is returned when cache miss."""
        from unittest.mock import MagicMock
        
        mock_pricing_client = Mock()
        mock_dynamodb_resource = MagicMock()
        mock_table = MagicMock()
        mock_dynamodb_resource.Table.return_value = mock_table
        mock_table.get_item.return_value = {}  # No Item key means cache miss
        
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_resource=mock_dynamodb_resource
        )
        
        result = manager._get_from_cache('ec2', 'us-east-1')
        
        assert result is None


class TestGetPricingData:
    """Test get_pricing_data method."""
    
    def test_get_pricing_data_uses_cache_when_fresh(self):
        """Test that fresh cached data is used."""
        from unittest.mock import MagicMock
        
        mock_pricing_client = Mock()
        mock_dynamodb_resource = MagicMock()
        mock_table = MagicMock()
        mock_dynamodb_resource.Table.return_value = mock_table
        
        # Mock cached data (resource API format - plain dict)
        cached_time = datetime.now(timezone.utc)
        future_ttl = int((cached_time.timestamp() + 86400))
        mock_table.get_item.return_value = {
            'Item': {
                'cache_key': 'ec2#us-east-1',
                'service': 'ec2',
                'region': 'us-east-1',
                'prices': {'t2.micro': '0.0116'},
                'currency': 'USD',
                'last_updated': cached_time.isoformat(),
                'ttl': future_ttl
            }
        }
        
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_resource=mock_dynamodb_resource
        )
        
        result = manager.get_pricing_data('ec2', 'us-east-1')
        
        # Should use cache, not call pricing API
        assert not mock_pricing_client.get_products.called
        assert result.service == 'ec2'
    
    def test_get_pricing_data_refreshes_when_stale(self):
        """Test that stale data triggers refresh."""
        from unittest.mock import MagicMock
        
        mock_pricing_client = Mock()
        mock_dynamodb_resource = MagicMock()
        mock_table = MagicMock()
        mock_dynamodb_resource.Table.return_value = mock_table
        
        # Mock stale cached data (resource API format - plain dict)
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        mock_table.get_item.return_value = {
            'Item': {
                'cache_key': 'ec2#us-east-1',
                'service': 'ec2',
                'region': 'us-east-1',
                'prices': {'t2.micro': '0.0116'},
                'currency': 'USD',
                'last_updated': old_time.isoformat(),
                'ttl': int(old_time.timestamp() + 86400)  # Already expired
            }
        }
        
        # Mock pricing API response
        mock_pricing_client.get_products.return_value = {'PriceList': []}
        
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_resource=mock_dynamodb_resource
        )
        
        result = manager.get_pricing_data('ec2', 'us-east-1')
        
        # Should call pricing API to refresh
        assert mock_pricing_client.get_products.called


class TestFetchFromPricingAPI:
    """Test fetch_from_pricing_api method."""
    
    def test_fetch_from_pricing_api_calls_api(self):
        """Test that pricing API is called."""
        mock_pricing_client = Mock()
        mock_dynamodb_client = Mock()
        mock_pricing_client.get_products.return_value = {'PriceList': []}
        
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_client=mock_dynamodb_client
        )
        
        result = manager.fetch_from_pricing_api('ec2', 'us-east-1')
        
        assert mock_pricing_client.get_products.called
        assert result.service == 'ec2'
        assert result.region == 'us-east-1'
    
    def test_fetch_from_pricing_api_uses_defaults_on_parse_error(self):
        """Test that default prices are used when parsing fails."""
        mock_pricing_client = Mock()
        mock_dynamodb_client = Mock()
        mock_pricing_client.get_products.return_value = {'PriceList': ['invalid json']}
        
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_client=mock_dynamodb_client
        )
        
        result = manager.fetch_from_pricing_api('ec2', 'us-east-1')
        
        # Should fall back to default prices
        assert 't2.micro' in result.prices



class TestGetPricingDataErrorHandling:
    """Test error handling in get_pricing_data."""
    
    def test_get_pricing_data_raises_exception_on_failure(self):
        """Test that exceptions are properly raised."""
        from unittest.mock import MagicMock
        
        mock_pricing_client = Mock()
        mock_dynamodb_resource = MagicMock()
        mock_table = MagicMock()
        mock_dynamodb_resource.Table.return_value = mock_table
        
        # Mock to return no cache, then fail on refresh
        mock_table.get_item.return_value = {}  # No Item key means cache miss
        mock_pricing_client.get_products.side_effect = Exception("API error")
        
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_resource=mock_dynamodb_resource
        )
        
        with pytest.raises(Exception) as exc_info:
            manager.get_pricing_data('ec2', 'us-east-1')
        
        assert "Failed to get pricing data" in str(exc_info.value)


class TestRefreshPricingDataErrorHandling:
    """Test error handling in refresh_pricing_data."""
    
    def test_refresh_pricing_data_raises_exception_on_failure(self):
        """Test that exceptions are properly raised during refresh."""
        from botocore.exceptions import ClientError
        
        mock_pricing_client = Mock()
        mock_dynamodb_client = Mock()
        
        # Mock pricing API to raise error
        error_response = {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}}
        mock_pricing_client.get_products.side_effect = ClientError(error_response, 'get_products')
        
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_client=mock_dynamodb_client
        )
        
        with pytest.raises(Exception) as exc_info:
            manager.refresh_pricing_data('ec2', 'us-east-1')
        
        assert "Failed to refresh pricing data" in str(exc_info.value)


class TestFetchFromPricingAPIErrorHandling:
    """Test error handling in fetch_from_pricing_api."""
    
    def test_fetch_from_pricing_api_raises_exception_on_client_error(self):
        """Test that ClientError is properly handled."""
        from botocore.exceptions import ClientError
        
        mock_pricing_client = Mock()
        mock_dynamodb_client = Mock()
        
        # Mock pricing API to raise error with proper response structure
        error_response = {
            'Error': {'Code': 'Throttling', 'Message': 'Rate exceeded'},
            'ResponseMetadata': {'RequestId': 'test-request-id'}
        }
        mock_pricing_client.get_products.side_effect = ClientError(error_response, 'get_products')
        
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_client=mock_dynamodb_client
        )
        
        with pytest.raises(Exception) as exc_info:
            manager.fetch_from_pricing_api('ec2', 'us-east-1')
        
        assert "Failed to fetch from Pricing API" in str(exc_info.value)


class TestCachePricingDataErrorHandling:
    """Test error handling in cache_pricing_data."""
    
    def test_cache_pricing_data_raises_exception_on_client_error(self):
        """Test that ClientError is properly handled during caching."""
        from botocore.exceptions import ClientError
        from unittest.mock import MagicMock
        
        mock_pricing_client = Mock()
        mock_dynamodb_resource = MagicMock()
        mock_table = MagicMock()
        mock_dynamodb_resource.Table.return_value = mock_table
        
        # Mock DynamoDB to raise error with proper response structure
        error_response = {
            'Error': {'Code': 'ProvisionedThroughputExceededException', 'Message': 'Throughput exceeded'},
            'ResponseMetadata': {'RequestId': 'test-request-id'}
        }
        mock_table.put_item.side_effect = ClientError(error_response, 'put_item')
        
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_resource=mock_dynamodb_resource
        )
        
        pricing = PricingData(
            service='ec2',
            region='us-east-1',
            prices={'t2.micro': Decimal('0.0116')},
            currency='USD',
            last_updated=datetime.now(timezone.utc),
            ttl=86400
        )
        
        # Should not raise exception - caching errors are logged but don't fail
        # The method catches ClientError and logs it
        manager.cache_pricing_data('ec2', 'us-east-1', pricing)
        
        # Verify put_item was called (even though it failed)
        assert mock_table.put_item.called


class TestGetFromCacheErrorHandling:
    """Test error handling in _get_from_cache."""
    
    def test_get_from_cache_returns_none_on_client_error(self):
        """Test that ClientError returns None."""
        from botocore.exceptions import ClientError
        from unittest.mock import MagicMock
        
        mock_pricing_client = Mock()
        mock_dynamodb_resource = MagicMock()
        mock_table = MagicMock()
        mock_dynamodb_resource.Table.return_value = mock_table
        
        # Mock DynamoDB to raise error with proper response structure
        error_response = {
            'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Table not found'},
            'ResponseMetadata': {'RequestId': 'test-request-id'}
        }
        mock_table.get_item.side_effect = ClientError(error_response, 'get_item')
        
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_resource=mock_dynamodb_resource
        )
        
        result = manager._get_from_cache('ec2', 'us-east-1')
        
        assert result is None
    
    def test_get_from_cache_returns_none_on_parse_error(self):
        """Test that parsing errors return None."""
        from unittest.mock import MagicMock
        
        mock_pricing_client = Mock()
        mock_dynamodb_resource = MagicMock()
        mock_table = MagicMock()
        mock_dynamodb_resource.Table.return_value = mock_table
        
        # Mock DynamoDB response with invalid data (resource API format)
        mock_table.get_item.return_value = {
            'Item': {
                'cache_key': 'ec2#us-east-1',
                'service': 'ec2',
                'region': 'us-east-1',
                'prices': {},  # Empty prices dict
                'currency': 'USD',
                'last_updated': 'invalid date',  # Invalid ISO format
                'ttl': 0  # Expired TTL
            }
        }
        
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_resource=mock_dynamodb_resource
        )
        
        result = manager._get_from_cache('ec2', 'us-east-1')
        
        # Should return None due to parse error or expired TTL
        assert result is None


class TestParsePricingResponse:
    """Test _parse_pricing_response method."""
    
    def test_parse_pricing_response_for_ec2(self):
        """Test parsing EC2 pricing response."""
        mock_pricing_client = Mock()
        mock_dynamodb_client = Mock()
        
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_client=mock_dynamodb_client
        )
        
        # Mock EC2 pricing response
        response = {
            'PriceList': [
                json.dumps({
                    'product': {
                        'attributes': {
                            'instanceType': 't2.micro'
                        }
                    },
                    'terms': {
                        'OnDemand': {
                            'term1': {
                                'priceDimensions': {
                                    'dim1': {
                                        'pricePerUnit': {
                                            'USD': '0.0116'
                                        }
                                    }
                                }
                            }
                        }
                    }
                })
            ]
        }
        
        prices = manager._parse_pricing_response(response, 'ec2')
        
        assert 't2.micro' in prices
        assert prices['t2.micro'] == Decimal('0.0116')
    
    def test_parse_pricing_response_for_lambda(self):
        """Test parsing Lambda pricing response."""
        mock_pricing_client = Mock()
        mock_dynamodb_client = Mock()
        
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_client=mock_dynamodb_client
        )
        
        # Mock Lambda pricing response
        response = {
            'PriceList': [
                json.dumps({
                    'product': {
                        'attributes': {
                            'group': 'AWS-Lambda-Requests'
                        }
                    },
                    'terms': {
                        'OnDemand': {
                            'term1': {
                                'priceDimensions': {
                                    'dim1': {
                                        'pricePerUnit': {
                                            'USD': '0.0000002'
                                        }
                                    }
                                }
                            }
                        }
                    }
                }),
                json.dumps({
                    'product': {
                        'attributes': {
                            'group': 'AWS-Lambda-Duration-GB-Second'
                        }
                    },
                    'terms': {
                        'OnDemand': {
                            'term1': {
                                'priceDimensions': {
                                    'dim1': {
                                        'pricePerUnit': {
                                            'USD': '0.0000166667'
                                        }
                                    }
                                }
                            }
                        }
                    }
                })
            ]
        }
        
        prices = manager._parse_pricing_response(response, 'lambda')
        
        assert 'request' in prices
        assert 'gb_second' in prices
    
    def test_parse_pricing_response_returns_defaults_on_error(self):
        """Test that default prices are returned on parsing error."""
        mock_pricing_client = Mock()
        mock_dynamodb_client = Mock()
        
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_client=mock_dynamodb_client
        )
        
        # Invalid response
        response = {
            'PriceList': ['invalid json']
        }
        
        prices = manager._parse_pricing_response(response, 'ec2')
        
        # Should return default prices
        assert 't2.micro' in prices
    
    def test_parse_pricing_response_returns_defaults_when_empty(self):
        """Test that default prices are returned when no prices found."""
        mock_pricing_client = Mock()
        mock_dynamodb_client = Mock()
        
        manager = PricingManager(
            pricing_client=mock_pricing_client,
            dynamodb_client=mock_dynamodb_client
        )
        
        # Empty response
        response = {'PriceList': []}
        
        prices = manager._parse_pricing_response(response, 'ec2')
        
        # Should return default prices
        assert 't2.micro' in prices
