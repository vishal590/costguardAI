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
    
    def __init__(self, region: str = 'us-east-1', pricing_client=None, dynamodb_client=None, dynamodb_resource=None):
        """
        Initialize Pricing API client.
        
        Args:
            region: AWS region (Pricing API is only available in us-east-1)
            pricing_client: Optional boto3 Pricing client (for testing)
            dynamodb_client: Optional boto3 DynamoDB client (for testing)
            dynamodb_resource: Optional boto3 DynamoDB resource (for testing)
        """
        # Pricing API is only available in us-east-1
        self.pricing_client = pricing_client or boto3.client('pricing', region_name='us-east-1')
        self.dynamodb_client = dynamodb_client or boto3.client('dynamodb', region_name=region)
        self.dynamodb_resource = dynamodb_resource or boto3.resource('dynamodb', region_name=region)
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
            
            if cached_pricing and cached_pricing.source == "aws_pricing" and not self.is_pricing_stale(cached_pricing):
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
                {'Type': 'TERM_MATCH', 'Field': 'regionCode', 'Value': region}
            ]
            
            request = {'ServiceCode': service_code, 'Filters': filters, 'MaxResults': 100}
            products, seen = [], set()
            while True:
                response = self.pricing_client.get_products(**request)
                products.extend(response.get('PriceList', []))
                token = response.get('NextToken')
                if not token: break
                if token in seen: raise ValueError('Repeated pricing page token')
                seen.add(token)
                request['NextToken'] = token
            response = {'PriceList': products}
            # Parse pricing data
            prices = self._parse_pricing_response(response, service)
            
            # Create PricingData object
            pricing_data = PricingData(
                service=service,
                region=region,
                prices=prices,
                currency='USD',
                last_updated=datetime.now(timezone.utc),
                ttl=86400, source="aws_pricing",
                pricing_profile="Linux/shared EC2; x86 Lambda; on-demand standard DynamoDB; standard S3; Single-AZ PostgreSQL/general-purpose RDS"
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
        try:
            from datetime import datetime, timezone
            from decimal import Decimal
            
            # Calculate TTL (24 hours from now)
            ttl_timestamp = int((datetime.now(timezone.utc).timestamp() + pricing.ttl))
            
            # Create cache key
            cache_key = f"{service}#{region}"
            
            # Convert prices dict to string format for DynamoDB
            prices_dict = {k: str(v) for k, v in pricing.prices.items()}
            
            # Get table
            table = self.dynamodb_resource.Table(self.table_name)
            
            # Prepare item
            item = {
                'cache_key': cache_key,
                'service': service,
                'region': region,
                'prices': prices_dict,
                'currency': pricing.currency,
                'source': pricing.source,
                'pricing_profile': pricing.pricing_profile,
                'last_updated': pricing.last_updated.isoformat(),
                'ttl': ttl_timestamp
            }
            
            # Write to DynamoDB
            table.put_item(Item=item)
            
        except ClientError as e:
            # Log error but don't fail - caching is optional
            # Table might not exist yet (will be created on first deployment)
            if e.response['Error']['Code'] != 'ResourceNotFoundException':
                print(f"Failed to cache pricing data: {str(e)}")
        except Exception as e:
            # Log error but don't fail
            print(f"Failed to cache pricing data: {str(e)}")
    
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
        try:
            from datetime import datetime, timezone
            from decimal import Decimal
            
            # Create cache key
            cache_key = f"{service}#{region}"
            
            # Get table
            table = self.dynamodb_resource.Table(self.table_name)
            
            # Get from DynamoDB
            response = table.get_item(Key={'cache_key': cache_key})
            
            if 'Item' not in response:
                return None
            
            item = response['Item']
            
            # Check if TTL has expired (DynamoDB will auto-delete, but check anyway)
            ttl = item.get('ttl', 0)
            if ttl > 0:
                current_timestamp = int(datetime.now(timezone.utc).timestamp())
                if current_timestamp >= ttl:
                    return None
            
            # Parse prices from string format
            prices_dict = item.get('prices', {})
            prices = {k: Decimal(v) for k, v in prices_dict.items()}
            
            # Reconstruct PricingData
            pricing_data = PricingData(
                service=item.get('service', service),
                region=item.get('region', region),
                prices=prices,
                currency=item.get('currency', 'USD'),
                last_updated=datetime.fromisoformat(item.get('last_updated', datetime.now(timezone.utc).isoformat())),
                ttl=86400, source=item.get("source", "legacy_unverified"), pricing_profile=item.get("pricing_profile", "unspecified")
            )
            
            return pricing_data
            
        except ClientError as e:
            # Table might not exist yet - return None (will fetch from API)
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                return None
            # Log other errors but don't fail
            print(f"Failed to get pricing from cache: {str(e)}")
            return None
        except Exception as e:
            # Log error but don't fail
            print(f"Failed to get pricing from cache: {str(e)}")
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
        candidates = {}
        for encoded in response.get('PriceList', []):
            product = json.loads(encoded) if isinstance(encoded, str) else encoded
            attrs = product.get('product', {}).get('attributes', {})
            usage = attrs.get('usagetype', '')
            for term in product.get('terms', {}).get('OnDemand', {}).values():
                for dimension in term.get('priceDimensions', {}).values():
                    if dimension.get('beginRange', '0') != '0': continue
                    unit, key = dimension.get('unit', ''), None
                    if service == 'ec2' and unit == 'Hrs' and attrs.get('operatingSystem') == 'Linux' and attrs.get('tenancy') == 'Shared' and attrs.get('preInstalledSw', 'NA') == 'NA' and attrs.get('capacitystatus', 'Used') == 'Used':
                        key = attrs.get('instanceType')
                    elif service == 'lambda' and 'ARM' not in usage.upper() and 'Edge' not in usage:
                        if unit == 'Requests' and 'Request' in usage: key = 'request'
                        elif unit == 'GB-Seconds' and 'GB-Second' in usage: key = 'gb_second'
                    elif service == 'dynamodb' and 'IA' not in usage and 'Replicated' not in usage:
                        if 'ReadRequestUnits' in usage: key = 'read_unit'
                        elif 'WriteRequestUnits' in usage: key = 'write_unit'
                    elif service == 's3':
                        group = attrs.get('group', '')
                        if unit == 'GB-Mo' and attrs.get('storageClass') == 'General Purpose' and attrs.get('volumeType') == 'Standard': key = 'storage_gb'
                        elif unit == 'Requests' and group == 'S3-API-Tier1': key = 'put_request'
                        elif unit == 'Requests' and group == 'S3-API-Tier2': key = 'get_request'
                    elif service == 'rds' and attrs.get('deploymentOption') == 'Single-AZ':
                        if unit == 'Hrs' and attrs.get('databaseEngine') == 'PostgreSQL': key = attrs.get('instanceType')
                        elif unit == 'GB-Mo' and 'GP2' in usage.upper() and attrs.get('databaseEngine') in (None, 'Any', 'PostgreSQL'): key = 'storage_gb'
                    value = dimension.get('pricePerUnit', {}).get('USD')
                    if key and value is not None:
                        rate = Decimal(value)
                        if rate.is_finite() and rate >= 0: candidates.setdefault(key, set()).add(rate)
        # Conflicting product profiles cannot become an arbitrary price.
        return {key: next(iter(values)) for key, values in candidates.items() if len(values) == 1}

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
