"""
Forecast Cache Manager for DynamoDB-based caching.

This module manages forecast caching to minimize Bedrock API costs:
1. Cache key generation
2. Cache retrieval with TTL checking
3. Cache storage with 24-hour TTL
4. Cache invalidation
5. Cache hit rate tracking
"""

from typing import Optional, Dict, Any
from datetime import datetime, UTC, timedelta
import json
import hashlib
from botocore.exceptions import ClientError


class ForecastCacheManager:
    """Manages forecast caching in DynamoDB."""
    
    def __init__(self, dynamodb_client, table_name: str, ttl_hours: int = 24):
        """
        Initialize cache manager.
        
        Args:
            dynamodb_client: boto3 DynamoDB client
            table_name: Name of DynamoDB table for cache
            ttl_hours: Time-to-live in hours (default 24)
        """
        self.dynamodb_client = dynamodb_client
        self.table_name = table_name
        self.ttl_hours = ttl_hours
        self.cache_hits = 0
        self.cache_misses = 0
        
    def get_cache_key(
        self,
        service: Optional[str],
        days: int,
        granularity: str
    ) -> str:
        """
        Generate cache key from parameters.
        
        Args:
            service: Service name (None for total)
            days: Forecast horizon
            granularity: Time resolution
            
        Returns:
            Cache key string
        """
        # Create deterministic key from parameters
        service_str = service if service else "total"
        key_parts = [service_str, str(days), granularity]
        key_string = ":".join(key_parts)
        
        # Use hash for consistent key format
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]
        
        return f"forecast:{service_str}:{days}:{granularity}:{key_hash}"
        
    def get_cached_forecast(
        self,
        service: Optional[str],
        days: int,
        granularity: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached forecast if exists and not expired.
        
        Args:
            service: Service name (None for total)
            days: Forecast horizon
            granularity: Time resolution
            
        Returns:
            Cached forecast dict if found and valid, None otherwise
        """
        cache_key = self.get_cache_key(service, days, granularity)
        
        try:
            response = self.dynamodb_client.get_item(
                TableName=self.table_name,
                Key={'cache_key': {'S': cache_key}}
            )
            
            if 'Item' not in response:
                self.cache_misses += 1
                return None
            
            item = response['Item']
            
            # Check TTL expiration
            ttl = int(item['ttl']['N'])
            current_time = int(datetime.now(UTC).timestamp())
            
            if current_time >= ttl:
                # Expired
                self.cache_misses += 1
                return None
            
            # Cache hit - parse forecast data
            self.cache_hits += 1
            forecast_data = json.loads(item['forecast_data']['S'])
            
            return forecast_data
            
        except ClientError as e:
            # Log error but don't fail - treat as cache miss
            print(f"Cache retrieval error: {e}")
            self.cache_misses += 1
            return None
        except (KeyError, json.JSONDecodeError) as e:
            # Malformed cache entry - treat as miss
            print(f"Cache parse error: {e}")
            self.cache_misses += 1
            return None
        
    def store_forecast(
        self,
        forecast: Dict[str, Any],
        service: Optional[str],
        days: int,
        granularity: str
    ) -> None:
        """
        Store forecast in cache with TTL.
        
        Args:
            forecast: Forecast data to cache
            service: Service name (None for total)
            days: Forecast horizon
            granularity: Time resolution
        """
        cache_key = self.get_cache_key(service, days, granularity)
        
        # Calculate TTL (Unix timestamp)
        ttl_time = datetime.now(UTC) + timedelta(hours=self.ttl_hours)
        ttl = int(ttl_time.timestamp())
        
        # Current timestamp
        created_at = datetime.now(UTC).isoformat()
        
        try:
            self.dynamodb_client.put_item(
                TableName=self.table_name,
                Item={
                    'cache_key': {'S': cache_key},
                    'forecast_data': {'S': json.dumps(forecast)},
                    'ttl': {'N': str(ttl)},
                    'created_at': {'S': created_at},
                    'service': {'S': service if service else 'total'},
                    'days': {'N': str(days)},
                    'granularity': {'S': granularity}
                }
            )
        except ClientError as e:
            # Log error but don't fail the forecast request
            print(f"Cache storage error: {e}")
        
    def invalidate_all(self) -> None:
        """
        Invalidate all cached forecasts.
        
        This is called when new cost data is fetched to ensure
        forecasts are regenerated with latest data.
        """
        try:
            # Scan all items in cache table
            response = self.dynamodb_client.scan(
                TableName=self.table_name,
                ProjectionExpression='cache_key'
            )
            
            # Delete each item
            for item in response.get('Items', []):
                cache_key = item['cache_key']['S']
                self.dynamodb_client.delete_item(
                    TableName=self.table_name,
                    Key={'cache_key': {'S': cache_key}}
                )
            
            # Handle pagination if needed
            while 'LastEvaluatedKey' in response:
                response = self.dynamodb_client.scan(
                    TableName=self.table_name,
                    ProjectionExpression='cache_key',
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                
                for item in response.get('Items', []):
                    cache_key = item['cache_key']['S']
                    self.dynamodb_client.delete_item(
                        TableName=self.table_name,
                        Key={'cache_key': {'S': cache_key}}
                    )
                    
        except ClientError as e:
            # Log error but don't fail
            print(f"Cache invalidation error: {e}")
        
    def track_cache_hit_rate(self) -> float:
        """
        Calculate and return cache hit rate.
        
        Returns:
            Cache hit rate as percentage (0.0 to 1.0)
        """
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total
