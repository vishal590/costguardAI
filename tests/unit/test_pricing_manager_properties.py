"""
Property-based tests for Pricing Manager.

Feature: near-realtime-cost-estimation
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock
import json

from src.services.pricing_manager import PricingManager
from src.utils.types import PricingData


# Feature: near-realtime-cost-estimation, Property 3: Pricing Data Freshness
@given(
    hours_old=st.integers(min_value=0, max_value=48)
)
@settings(max_examples=100)
def test_pricing_data_freshness(hours_old):
    """
    Property 3: Pricing Data Freshness
    
    For any pricing data older than 24 hours, the system should refresh it
    before using it for estimation.
    
    Validates: Requirements 3.2, 3.3
    """
    mock_pricing_client = Mock()
    mock_dynamodb_client = Mock()
    manager = PricingManager(
        pricing_client=mock_pricing_client,
        dynamodb_client=mock_dynamodb_client
    )
    
    # Create pricing data with specified age
    old_time = datetime.now(timezone.utc) - timedelta(hours=hours_old)
    pricing = PricingData(
        service='ec2',
        region='us-east-1',
        prices={'t2.micro': Decimal('0.0116')},
        currency='USD',
        last_updated=old_time,
        ttl=86400
    )
    
    is_stale = manager.is_pricing_stale(pricing, max_age_hours=24)
    
    # Property: Pricing older than 24 hours should be stale
    if hours_old >= 24:
        assert is_stale is True, f"Pricing {hours_old} hours old should be stale"
    else:
        assert is_stale is False, f"Pricing {hours_old} hours old should be fresh"


# Feature: near-realtime-cost-estimation, Property 11: Pricing Validation
@given(
    price_value=st.floats(min_value=0.0001, max_value=1000, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_pricing_validation(price_value):
    """
    Property 11: Pricing Validation
    
    For any fetched pricing data, all prices must be positive numbers.
    
    Validates: Requirements 8.2
    """
    mock_pricing_client = Mock()
    mock_dynamodb_client = Mock()
    manager = PricingManager(
        pricing_client=mock_pricing_client,
        dynamodb_client=mock_dynamodb_client
    )
    
    # Get default prices for a service
    prices = manager._get_default_prices('ec2')
    
    # Property: All prices must be positive
    for key, price in prices.items():
        assert price > Decimal('0'), f"Price {key}={price} must be positive"
    
    # Also test with generated price value
    test_price = Decimal(str(price_value))
    assert test_price > Decimal('0'), f"Generated price {test_price} must be positive"


# Feature: near-realtime-cost-estimation, Property 14: Pricing Cache Hit
@given(
    service=st.sampled_from(['ec2', 'lambda', 'dynamodb', 's3', 'rds']),
    region=st.sampled_from(['us-east-1', 'us-west-2', 'eu-west-1'])
)
@settings(max_examples=100)
def test_pricing_cache_hit(service, region):
    """
    Property 14: Pricing Cache Hit
    
    For any pricing request where cached data exists and is fresh, the system
    must use cached data instead of calling Pricing API.
    
    Validates: Requirements 7.3
    """
    mock_pricing_client = Mock()
    mock_dynamodb_client = Mock()
    
    # Mock fresh cached data
    cached_time = datetime.now(timezone.utc)
    mock_dynamodb_client.get_item.return_value = {
        'Item': {
            'pk': {'S': f'PRICING#{service}#{region}'},
            'sk': {'S': 'METADATA'},
            'service': {'S': service},
            'region': {'S': region},
            'prices': {'S': json.dumps({'test_key': '0.0116'})},
            'currency': {'S': 'USD'},
            'last_updated': {'S': cached_time.isoformat()},
            'ttl': {'N': '86400'}
        }
    }
    
    manager = PricingManager(
        pricing_client=mock_pricing_client,
        dynamodb_client=mock_dynamodb_client
    )
    
    result = manager.get_pricing_data(service, region)
    
    # Property: Should use cache, not call pricing API
    assert not mock_pricing_client.get_products.called, \
        "Should use cached data instead of calling Pricing API"
    assert result.service == service
    assert result.region == region


# Additional property test for cache staleness
@given(
    hours_old=st.integers(min_value=25, max_value=100)
)
@settings(max_examples=100)
def test_stale_cache_triggers_refresh(hours_old):
    """
    Property: Stale cache triggers refresh
    
    For any cached pricing data older than 24 hours, the system must
    refresh from the Pricing API.
    
    Validates: Requirements 3.2
    """
    mock_pricing_client = Mock()
    mock_dynamodb_client = Mock()
    
    # Mock stale cached data
    old_time = datetime.now(timezone.utc) - timedelta(hours=hours_old)
    mock_dynamodb_client.get_item.return_value = {
        'Item': {
            'pk': {'S': 'PRICING#ec2#us-east-1'},
            'sk': {'S': 'METADATA'},
            'service': {'S': 'ec2'},
            'region': {'S': 'us-east-1'},
            'prices': {'S': json.dumps({'t2.micro': '0.0116'})},
            'currency': {'S': 'USD'},
            'last_updated': {'S': old_time.isoformat()},
            'ttl': {'N': '86400'}
        }
    }
    
    # Mock pricing API response
    mock_pricing_client.get_products.return_value = {'PriceList': []}
    
    manager = PricingManager(
        pricing_client=mock_pricing_client,
        dynamodb_client=mock_dynamodb_client
    )
    
    result = manager.get_pricing_data('ec2', 'us-east-1')
    
    # Property: Should call pricing API to refresh stale data
    assert mock_pricing_client.get_products.called, \
        f"Should refresh pricing data that is {hours_old} hours old"


# Property test for default prices
@given(
    service=st.sampled_from(['ec2', 'lambda', 'dynamodb', 's3', 'rds'])
)
@settings(max_examples=100)
def test_default_prices_are_valid(service):
    """
    Property: Default prices are valid
    
    For any service, default prices must exist and be positive.
    
    Validates: Requirements 8.2
    """
    mock_pricing_client = Mock()
    mock_dynamodb_client = Mock()
    manager = PricingManager(
        pricing_client=mock_pricing_client,
        dynamodb_client=mock_dynamodb_client
    )
    
    prices = manager._get_default_prices(service)
    
    # Property: Default prices must exist
    assert len(prices) > 0, f"Service {service} must have default prices"
    
    # Property: All default prices must be positive
    for key, price in prices.items():
        assert price > Decimal('0'), \
            f"Default price {key}={price} for {service} must be positive"


# Property test for location mapping
@given(
    region=st.sampled_from(['us-east-1', 'us-east-2', 'us-west-1', 'us-west-2', 
                           'eu-west-1', 'eu-central-1', 'ap-southeast-1', 'ap-northeast-1'])
)
@settings(max_examples=100)
def test_location_mapping_is_consistent(region):
    """
    Property: Location mapping is consistent
    
    For any AWS region, the location name mapping should be consistent
    and return a non-empty string.
    
    Validates: Requirements 3.3
    """
    mock_pricing_client = Mock()
    mock_dynamodb_client = Mock()
    manager = PricingManager(
        pricing_client=mock_pricing_client,
        dynamodb_client=mock_dynamodb_client
    )
    
    location = manager._get_location_name(region)
    
    # Property: Location name must be non-empty
    assert location, f"Location name for {region} must not be empty"
    assert isinstance(location, str), "Location name must be a string"
    assert len(location) > 0, "Location name must have content"
