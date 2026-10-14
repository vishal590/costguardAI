"""
Advisor Cache Manager for caching query responses.

This module manages response caching to minimize Bedrock API calls:
1. Store responses with 24-hour TTL
2. Retrieve cached responses
3. Invalidate stale cache entries
4. Track cache hit rate
"""

from typing import Optional
from datetime import datetime, timedelta, UTC
import logging
import json
from botocore.exceptions import ClientError

from ..utils.types import AdvisorResponse

logger = logging.getLogger(__name__)


class AdvisorCacheManager:
    """Cache frequently asked questions."""
    
    def __init__(
        self,
        dynamodb_client=None,
        ttl_hours: int = 24,
        metrics_table_name: Optional[str] = None
    ):
        """
        Initialize cache manager.
        
        Args:
            dynamodb_client: DynamoDB client
            ttl_hours: Cache TTL in hours
            metrics_table_name: Optional table name for cache metrics (uses cache table if None)
        """
        self.dynamodb_client = dynamodb_client
        self.ttl_hours = ttl_hours
        self.table_name = "advisor-cache"
        self.metrics_table_name = metrics_table_name or self.table_name
        
        # Track cache statistics (in-memory for current session)
        self.cache_hits = 0
        self.cache_misses = 0
        
        logger.info(f"AdvisorCacheManager initialized with {ttl_hours}h TTL")
    
    def get_cached_response(self, query_hash: str) -> Optional[AdvisorResponse]:
        """
        Retrieve cached response if available and fresh.
        
        Args:
            query_hash: Hash of the query
            
        Returns:
            Cached AdvisorResponse or None
        """
        if not self.dynamodb_client:
            logger.warning("No DynamoDB client, cache disabled")
            self.cache_misses += 1
            return None
        
        try:
            response = self.dynamodb_client.get_item(
                TableName=self.table_name,
                Key={
                    "query_hash": {"S": query_hash}
                }
            )
            
            item = response.get('Item')
            if not item:
                logger.debug(f"Cache miss for query {query_hash[:8]}...")
                self.cache_misses += 1
                self._update_aggregate_metrics(hit=False)
                return None
            
            # Check TTL
            cached_at = datetime.fromisoformat(item['cached_at']['S'])
            expiry = cached_at + timedelta(hours=self.ttl_hours)
            
            if cached_at.tzinfo is None or cached_at > datetime.now(UTC)+timedelta(minutes=5):
                return None
            expiry = min(expiry, datetime.fromtimestamp(int(item['ttl']['N']), UTC))
            if datetime.now(UTC) >= expiry:
                logger.debug(f"Cache expired for query {query_hash[:8]}...")
                self.cache_misses += 1
                self._update_aggregate_metrics(hit=False)
                return None
            
            # Reconstruct AdvisorResponse
            cached_response = AdvisorResponse(
                response_text=item['response_text']['S'],
                recommendations=[],  # Simplified: not storing recommendations
                cost_data=json.loads(item.get('cost_data', {'S': '{}'})['S']),
                confidence=None,  # Legacy constant confidence is not calibrated.
                cached=True
            )
            
            logger.info(f"Cache hit for query {query_hash[:8]}...")
            self.cache_hits += 1
            self._update_aggregate_metrics(hit=True)
            return cached_response
            
        except Exception as e:
            logger.error(f"Error retrieving from cache: {e}")
            self.cache_misses += 1
            self._update_aggregate_metrics(hit=False)
            return None
    
    def store_response(
        self,
        query_hash: str,
        response: AdvisorResponse,
        ttl_hours: Optional[int] = None
    ) -> None:
        """
        Store response in cache with TTL.
        
        Args:
            query_hash: Hash of the query
            response: AdvisorResponse to cache
            ttl_hours: Override default TTL
        """
        if not self.dynamodb_client:
            logger.warning("No DynamoDB client, cannot cache response")
            return
        
        ttl_hours = ttl_hours or self.ttl_hours
        
        try:
            now = datetime.now(UTC)
            ttl_timestamp = int((now + timedelta(hours=ttl_hours)).timestamp())
            
            item = {
                "query_hash": {"S": query_hash},
                "response_text": {"S": response.response_text},
                "cost_data": {"S": json.dumps(response.cost_data, default=str)},
                "confidence": {"NULL": True},
                "confidence_method": {"S": "unavailable"},
                "cached_at": {"S": now.isoformat()},
                "ttl": {"N": str(ttl_timestamp)}
            }
            
            self.dynamodb_client.put_item(
                TableName=self.table_name,
                Item=item
            )
            
            logger.debug(f"Stored response in cache: {query_hash[:8]}...")
            
        except Exception as e:
            logger.error(f"Error storing in cache: {e}")
    
    def invalidate_cache(self, pattern: str) -> None:
        """
        Invalidate cache entries matching pattern.
        
        Args:
            pattern: Pattern to match (simplified: exact hash match)
        """
        if not self.dynamodb_client:
            logger.warning("No DynamoDB client, cannot invalidate cache")
            return
        
        try:
            # Simplified: delete specific entry
            self.dynamodb_client.delete_item(
                TableName=self.table_name,
                Key={
                    "query_hash": {"S": pattern}
                }
            )
            
            logger.info(f"Invalidated cache entry: {pattern[:8]}...")
            
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
    
    def get_cache_hit_rate(self) -> float:
        """
        Calculate cache hit rate percentage (in-memory).
        
        Returns:
            Hit rate as percentage (0-100)
        """
        total_requests = self.cache_hits + self.cache_misses
        
        if total_requests == 0:
            return 0.0
        
        hit_rate = (self.cache_hits / total_requests) * 100
        
        logger.info(f"Cache hit rate (in-memory): {hit_rate:.1f}% ({self.cache_hits}/{total_requests})")
        return hit_rate
    
    def get_persistent_cache_hit_rate(self) -> Optional[float]:
        """
        Get persistent cache hit rate from DynamoDB metrics.
        
        Returns:
            Cache hit rate as percentage (0.0 to 100.0) or None if no metrics
        """
        if not self.dynamodb_client:
            return None
        
        try:
            metrics_key = 'CACHE_METRICS:AGGREGATE'
            # Advisor cache table uses 'query_hash' as partition key
            # If using the same table, use 'query_hash'; otherwise use 'cache_key'
            key_name = 'query_hash' if self.metrics_table_name == self.table_name else 'cache_key'
            response = self.dynamodb_client.get_item(
                TableName=self.metrics_table_name,
                Key={key_name: {'S': metrics_key}}
            )
            
            if 'Item' not in response:
                return None
            
            item = response['Item']
            total_hits = int(item.get('total_hits', {}).get('N', '0'))
            total_misses = int(item.get('total_misses', {}).get('N', '0'))
            
            total = total_hits + total_misses
            if total == 0:
                return 0.0
            
            hit_rate = (total_hits / total) * 100
            logger.info(f"Persistent cache hit rate: {hit_rate:.1f}% ({total_hits}/{total})")
            return hit_rate
            
        except ClientError:
            return None
        except Exception as e:
            logger.error(f"Error getting persistent cache hit rate: {e}")
            return None
    
    def _update_aggregate_metrics(self, hit: bool) -> None:
        """
        Update aggregate cache metrics in DynamoDB (persistent tracking).
        
        Args:
            hit: True if cache hit, False if cache miss
        """
        if not self.dynamodb_client:
            return
        
        try:
            metrics_key = 'CACHE_METRICS:AGGREGATE'
            current_time = int(datetime.now(UTC).timestamp())
            
            # Advisor cache table uses 'query_hash' as partition key
            # If using the same table, use 'query_hash'; otherwise use 'cache_key'
            key_name = 'query_hash' if self.metrics_table_name == self.table_name else 'cache_key'
            
            # Use update with ADD to increment counters atomically
            update_expr = 'ADD total_hits :inc_hits, total_misses :inc_misses SET last_updated = :time'
            expr_values = {
                ':inc_hits': {'N': '1' if hit else '0'},
                ':inc_misses': {'N': '0' if hit else '1'},
                ':time': {'N': str(current_time)}
            }
            
            # Try to update, create if doesn't exist
            try:
                self.dynamodb_client.update_item(
                    TableName=self.metrics_table_name,
                    Key={key_name: {'S': metrics_key}},
                    UpdateExpression=update_expr,
                    ExpressionAttributeValues=expr_values
                )
            except ClientError as e:
                # If item doesn't exist, create it
                if e.response['Error']['Code'] == 'ValidationException':
                    self.dynamodb_client.put_item(
                        TableName=self.metrics_table_name,
                        Item={
                            key_name: {'S': metrics_key},
                            'total_hits': {'N': '1' if hit else '0'},
                            'total_misses': {'N': '0' if hit else '1'},
                            'last_updated': {'N': str(current_time)},
                            'ttl': {'N': str(current_time + 86400 * 90)}  # Keep metrics for 90 days
                        }
                    )
                else:
                    raise
                    
        except ClientError as e:
            # Log but don't fail
            logger.debug(f"Aggregate metrics update error: {e}")
        except Exception as e:
            logger.debug(f"Error updating aggregate metrics: {e}")