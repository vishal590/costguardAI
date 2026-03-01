"""
Pricing Manager for Phase 1.5.

This module manages AWS pricing data with caching and refresh logic.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, Optional
import boto3
from botocore.exceptions import ClientError
import json
import os

from src.utils.types import PricingData
from src.utils.error_handler import format_error


class PricingManager:
    """Manages AWS pricing data with caching."""
    
    def __init__(self, region: str = 'us-east-1', pricing_client=None, dynamodb_client=None):
        """
        Initialize Pricing API client.
        
        Args:
            region: AWS region (Pricing API is only available in us-east-1)
            pricing_client: Optional boto3 Pricing client (for testing)
            dynamodb_client: Optional boto3 DynamoDB client (for testing)
        """
        # Pricing API is only available in us-east-1
        self.pricing_client = pricing_client or boto3.client('pricing', region_name='us-east-1')
        self.dynamodb_client = dynamodb_client or boto3.client('dynamodb', region_name=region)
        self.region = region
        self.table_name = os.environ.get('PRICING_CACHE_TABLE', 'costguard-pricing-cache')
    
    def get_pricing_data(
        self,
        service: str,
        region: str
    ) -> PricingData:
        """
        Get pricing data for a service, using cache if available.
        
        Args:
            service: AWS service name
            region: AWS region
            
        Returns:
            Pricing data
        """
        try:
            # Try to get from cache first
            cached_pricing = self._get_from_cache(service, region)
            
            if cached_pricing and not self.is_pricing_stale(cached_pricing):
                return cached_pricing
            
            # Cache miss or stale, fetch from API
            return self.refresh_pricing_data(service, region)
            
        except Exception as e:
            raise Exception(f"Failed to get pricing data: {str(e)}")
    
    def refresh_pricing_data(
        self,
        service: str,
        region: str
    ) -> PricingData:
        """
        Refresh pricing data from AWS Pricing API.
        
        Args:
            service: AWS service name
            region: AWS region
            
        Returns:
            Updated pricing data
        """
        try:
            # Fetch from Pricing API
            pricing_data = self.fetch_from_pricing_api(service, region)
            
            # Cache the new data
            self.cache_pricing_data(service, region, pricing_data)
            
            return pricing_data
            
        except Exception as e:
            raise Exception(f"Failed to refresh pricing data: {str(e)}")
    
    def is_pricing_stale(
        self,
        pricing: PricingData,
        max_age_hours: int = 24
    ) -> bool:
        """
        Check if pricing data is stale.
        
        Args:
            pricing: Pricing data to check
            max_age_hours: Maximum age in hours before considered stale
            
        Returns:
            True if stale, False otherwise
        """
        if not pricing or not pricing.last_updated:
            return True
        
        now = datetime.now(timezone.utc)
        age = now - pricing.last_updated
        
        return age.total_seconds() > (max_age_hours * 3600)
    
    def fetch_from_pricing_api(
        self,
        service: str,
        region: str
    ) -> PricingData:
        """
        Fetch pricing data from AWS Pricing API.
        
        Args:
            service: AWS service name
            region: AWS region
            
        Returns:
            Pricing data from API
        """
        try:
            # Map service names to AWS Pricing API service codes
            service_code_map = {
                'ec2': 'AmazonEC2',
                'lambda': 'AWSLambda',
                'dynamodb': 'AmazonDynamoDB',
                's3': 'AmazonS3',
                'rds': 'AmazonRDS'
            }
            
            service_code = service_code_map.get(service.lower(), service)
            
            # Build filters for the region
            filters = [
                {'Type': 'TERM_MATCH', 'Field': 'ServiceCode', 'Value': service_code},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': self._get_location_name(region)}
            ]
            
            # Get pricing data
            response = self.pricing_client.get_products(
                ServiceCode=service_code,
                Filters=filters,
                MaxResults=100
            )
            
            # Parse pricing data
            prices = self._parse_pricing_response(response, service)
            
            # Create PricingData object
            pricing_data = PricingData(
                service=service,
                region=region,
                prices=prices,
                currency='USD',
                last_updated=datetime.now(timezone.utc),
                ttl=86400  # 24 hours
            )
            
            return pricing_data
            
        except ClientError as e:
            error_info = format_error(e)
            raise Exception(f"Failed to fetch from Pricing API: {error_info.message}")
    
    def cache_pricing_data(
        self,
        service: str,
        region: str,
        pricing: PricingData
    ) -> None:
        """
        Cache pricing data in DynamoDB.
        
        Args:
            service: AWS service name
            region: AWS region
            pricing: Pricing data to cache
        """
        # Caching disabled - pricing cache table not yet implemented
        # TODO: Create costguard-pricing-cache table and enable caching
        pass
    
    def _get_from_cache(
        self,
        service: str,
        region: str
    ) -> Optional[PricingData]:
        """
        Get pricing data from DynamoDB cache.
        
        Args:
            service: AWS service name
            region: AWS region
            
        Returns:
            Cached pricing data or None
        """
        # Caching disabled - pricing cache table not yet implemented
        # TODO: Create costguard-pricing-cache table and enable caching
        return None
            Cached pricing data or None if not found
        """
        try:
            pk = f"PRICING#{service}#{region}"
            sk = "METADATA"
            
            response = self.dynamodb_client.get_item(
                TableName=self.table_name,
                Key={
                    'pk': {'S': pk},
                    'sk': {'S': sk}
                }
            )
            
            if 'Item' not in response:
                return None
            
            item = response['Item']
            
            # Parse prices from JSON
            prices_json = item['prices']['S']
            prices = {k: Decimal(v) for k, v in json.loads(prices_json).items()}
            
            # Parse last_updated
            last_updated = datetime.fromisoformat(item['last_updated']['S'])
            
            return PricingData(
                service=item['service']['S'],
                region=item['region']['S'],
                prices=prices,
                currency=item['currency']['S'],
                last_updated=last_updated,
                ttl=int(item['ttl']['N'])
            )
            
        except ClientError:
            return None
        except Exception:
            return None
    
    def _get_location_name(self, region: str) -> str:
        """
        Map AWS region code to location name used in Pricing API.
        
        Args:
            region: AWS region code (e.g., 'us-east-1')
            
        Returns:
            Location name for Pricing API
        """
        location_map = {
            'us-east-1': 'US East (N. Virginia)',
            'us-east-2': 'US East (Ohio)',
            'us-west-1': 'US West (N. California)',
            'us-west-2': 'US West (Oregon)',
            'eu-west-1': 'EU (Ireland)',
            'eu-central-1': 'EU (Frankfurt)',
            'ap-southeast-1': 'Asia Pacific (Singapore)',
            'ap-northeast-1': 'Asia Pacific (Tokyo)'
        }
        
        return location_map.get(region, 'US East (N. Virginia)')
    
    def _parse_pricing_response(
        self,
        response: Dict,
        service: str
    ) -> Dict[str, Decimal]:
        """
        Parse pricing response from AWS Pricing API.
        
        Args:
            response: Response from get_products API call
            service: Service name
            
        Returns:
            Dictionary of prices
        """
        prices = {}
        
        try:
            for price_item in response.get('PriceList', []):
                price_data = json.loads(price_item)
                
                # Extract pricing information based on service
                if service == 'ec2':
                    # Get instance type and price
                    product = price_data.get('product', {})
                    attributes = product.get('attributes', {})
                    instance_type = attributes.get('instanceType')
                    
                    if instance_type:
                        # Get on-demand pricing
                        terms = price_data.get('terms', {})
                        on_demand = terms.get('OnDemand', {})
                        
                        for term_key, term_value in on_demand.items():
                            price_dimensions = term_value.get('priceDimensions', {})
                            for dim_key, dim_value in price_dimensions.items():
                                price_per_unit = dim_value.get('pricePerUnit', {})
                                usd_price = price_per_unit.get('USD')
                                
                                if usd_price:
                                    prices[instance_type] = Decimal(usd_price)
                                    break
                
                elif service == 'lambda':
                    # Lambda has request and duration pricing
                    product = price_data.get('product', {})
                    attributes = product.get('attributes', {})
                    group = attributes.get('group', '')
                    
                    terms = price_data.get('terms', {})
                    on_demand = terms.get('OnDemand', {})
                    
                    for term_key, term_value in on_demand.items():
                        price_dimensions = term_value.get('priceDimensions', {})
                        for dim_key, dim_value in price_dimensions.items():
                            price_per_unit = dim_value.get('pricePerUnit', {})
                            usd_price = price_per_unit.get('USD')
                            
                            if usd_price:
                                if 'Request' in group:
                                    prices['request'] = Decimal(usd_price)
                                elif 'Duration' in group or 'GB-Second' in group:
                                    prices['gb_second'] = Decimal(usd_price)
                
                # Add more service-specific parsing as needed
                
        except Exception as e:
            # If parsing fails, return default prices
            prices = self._get_default_prices(service)
        
        # If no prices found, use defaults
        if not prices:
            prices = self._get_default_prices(service)
        
        return prices
    
    def _get_default_prices(self, service: str) -> Dict[str, Decimal]:
        """
        Get default prices for a service (fallback).
        
        Args:
            service: Service name
            
        Returns:
            Dictionary of default prices
        """
        defaults = {
            'ec2': {
                't2.micro': Decimal('0.0116'),
                't2.small': Decimal('0.023'),
                't2.medium': Decimal('0.0464')
            },
            'lambda': {
                'request': Decimal('0.0000002'),
                'gb_second': Decimal('0.0000166667')
            },
            'dynamodb': {
                'read_unit': Decimal('0.00025'),
                'write_unit': Decimal('0.00125')
            },
            's3': {
                'storage_gb': Decimal('0.023'),
                'get_request': Decimal('0.0004'),
                'put_request': Decimal('0.005')
            },
            'rds': {
                'db.t3.micro': Decimal('0.017'),
                'storage_gb': Decimal('0.115'),
                'iops': Decimal('0.10')
            }
        }
        
        return defaults.get(service, {})
