"""
AI/ML Cost Cache Manager for DynamoDB-based caching.

This module manages AI/ML cost caching to minimize Cost Explorer API costs:
1. Cache key generation for GPU costs, workload classifications, etc.
2. Cache retrieval with TTL checking (24-hour default)
3. Cache storage with configurable TTL
4. Cache invalidation
5. Cache hit rate tracking

Requirements: NFR-5.2, NFR-5.3
"""

from typing import Optional, Dict, Any
from datetime import datetime, UTC, timedelta
import json
import hashlib
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class AIMLCacheManager:
    """Manages AI/ML cost caching in DynamoDB."""
    
    def __init__(self, dynamodb_client, table_name: str = 'ai-ml-cost-cache', ttl_hours: int = 24):
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
        cache_type: str,
        **params
    ) -> str:
        """
        Generate cache key from parameters.
        
        Args:
            cache_type: Type of cache (gpu_costs, workload_classification, etc.)
            **params: Additional parameters for cache key
            
        Returns:
            Cache key string
        """
        # Sort params for deterministic key generation
        sorted_params = sorted(params.items())
        param_str = ":".join(f"{k}={v}" for k, v in sorted_params)
        
        # Create key string
        key_string = f"{cache_type}:{param_str}"
        
        # Use hash for consistent key format
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]
        
        return f"aiml:{cache_type}:{key_hash}"
        
    def get_cached_data(
        self,
        cache_type: str,
        **params
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached data if exists and not expired.
        
        Args:
            cache_type: Type of cache
            **params: Parameters for cache key
            
        Returns:
            Cached data dict if found and valid, None otherwise
        """
        cache_key = self.get_cache_key(cache_type, **params)
        
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
            
            # Cache hit - parse data
            self.cache_hits += 1
            cached_data = json.loads(item['data']['S'])
            
            logger.info(f"Cache hit for {cache_type}: {cache_key}")
            return cached_data
            
        except ClientError as e:
            # Log error but don't fail - treat as cache miss
            logger.warning(f"Cache retrieval error: {e}")
            self.cache_misses += 1
            return None
        except (KeyError, json.JSONDecodeError) as e:
            # Malformed cache entry - treat as miss
            logger.warning(f"Cache parse error: {e}")
            self.cache_misses += 1
            return None
        
    def store_data(
        self,
        data: Dict[str, Any],
        cache_type: str,
        **params
    ) -> None:
        """
        Store data in cache with TTL.
        
        Args:
            data: Data to cache
            cache_type: Type of cache
            **params: Parameters for cache key
        """
        cache_key = self.get_cache_key(cache_type, **params)
        
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
                    'data': {'S': json.dumps(data)},
                    'ttl': {'N': str(ttl)},
                    'created_at': {'S': created_at},
                    'cache_type': {'S': cache_type},
                    'params': {'S': json.dumps(params)}
                }
            )
            logger.info(f"Cached {cache_type}: {cache_key}")
        except ClientError as e:
            # Log error but don't fail the request
            logger.error(f"Cache storage error: {e}")
        
    def invalidate_by_type(self, cache_type: str) -> int:
        """
        Invalidate all cached data of a specific type.
        
        Args:
            cache_type: Type of cache to invalidate
            
        Returns:
            Number of items invalidated
        """
        invalidated_count = 0
        
        try:
            # Scan for items of this type
            response = self.dynamodb_client.scan(
                TableName=self.table_name,
                FilterExpression='cache_type = :type',
                ExpressionAttributeValues={
                    ':type': {'S': cache_type}
                },
                ProjectionExpression='cache_key'
            )
            
            # Delete each item
            for item in response.get('Items', []):
                cache_key = item['cache_key']['S']
                self.dynamodb_client.delete_item(
                    TableName=self.table_name,
                    Key={'cache_key': {'S': cache_key}}
                )
                invalidated_count += 1
            
            # Handle pagination if needed
            while 'LastEvaluatedKey' in response:
                response = self.dynamodb_client.scan(
                    TableName=self.table_name,
                    FilterExpression='cache_type = :type',
                    ExpressionAttributeValues={
                        ':type': {'S': cache_type}
                    },
                    ProjectionExpression='cache_key',
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                
                for item in response.get('Items', []):
                    cache_key = item['cache_key']['S']
                    self.dynamodb_client.delete_item(
                        TableName=self.table_name,
                        Key={'cache_key': {'S': cache_key}}
                    )
                    invalidated_count += 1
            
            logger.info(f"Invalidated {invalidated_count} items of type {cache_type}")
            return invalidated_count
                    
        except ClientError as e:
            # Log error but don't fail
            logger.error(f"Cache invalidation error: {e}")
            return invalidated_count
        
    def invalidate_all(self) -> int:
        """
        Invalidate all cached data.
        
        Returns:
            Number of items invalidated
        """
        invalidated_count = 0
        
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
                invalidated_count += 1
            
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
                    invalidated_count += 1
            
            logger.info(f"Invalidated all {invalidated_count} cached items")
            return invalidated_count
                    
        except ClientError as e:
            # Log error but don't fail
            logger.error(f"Cache invalidation error: {e}")
            return invalidated_count
        
    def get_cache_hit_rate(self) -> float:
        """
        Calculate and return cache hit rate.
        
        Returns:
            Cache hit rate as percentage (0.0 to 1.0)
        """
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict with cache hits, misses, and hit rate
        """
        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': self.get_cache_hit_rate(),
            'total_requests': self.cache_hits + self.cache_misses
        }
