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

from ..utils.types import AdvisorResponse

logger = logging.getLogger(__name__)


class AdvisorCacheManager:
    """Cache frequently asked questions."""
    
    def __init__(
        self,
        dynamodb_client=None,
        ttl_hours: int = 24
    ):
        """
        Initialize cache manager.
        
        Args:
            dynamodb_client: DynamoDB client
            ttl_hours: Cache TTL in hours
        """
        self.dynamodb_client = dynamodb_client
        self.ttl_hours = ttl_hours
        self.table_name = "advisor-cache"
        
        # Track cache statistics
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
                return None
            
            # Check TTL
            cached_at = datetime.fromisoformat(item['cached_at']['S'])
            expiry = cached_at + timedelta(hours=self.ttl_hours)
            
            if datetime.now(UTC) > expiry:
                logger.debug(f"Cache expired for query {query_hash[:8]}...")
                self.cache_misses += 1
                return None
            
            # Reconstruct AdvisorResponse
            cached_response = AdvisorResponse(
                response_text=item['response_text']['S'],
                recommendations=[],  # Simplified: not storing recommendations
                cost_data={},
                confidence=float(item.get('confidence', {}).get('N', 0.8)),
                cached=True
            )
            
            logger.info(f"Cache hit for query {query_hash[:8]}...")
            self.cache_hits += 1
            return cached_response
            
        except Exception as e:
            logger.error(f"Error retrieving from cache: {e}")
            self.cache_misses += 1
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
                "confidence": {"N": str(response.confidence)},
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
        Calculate cache hit rate percentage.
        
        Returns:
            Hit rate as percentage (0-100)
        """
        total_requests = self.cache_hits + self.cache_misses
        
        if total_requests == 0:
            return 0.0
        
        hit_rate = (self.cache_hits / total_requests) * 100
        
        logger.info(f"Cache hit rate: {hit_rate:.1f}% ({self.cache_hits}/{total_requests})")
        return hit_rate
