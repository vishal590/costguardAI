"""
Forecast Cache Manager for DynamoDB-based caching with intelligent features.

This module manages forecast caching to minimize Bedrock API costs:
1. Cache key generation
2. Cache retrieval with TTL checking
3. Adaptive TTL based on access frequency
4. Cache invalidation
5. Persistent cache hit rate tracking
6. Access frequency tracking
7. Cache warming for common queries
"""

from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, UTC, timedelta
import json
import hashlib
import uuid
from botocore.exceptions import ClientError


class ForecastCacheManager:
    """Manages forecast caching in DynamoDB."""
    
    def __init__(self, dynamodb_client, table_name: str, ttl_hours: int = 24, metrics_table_name: Optional[str] = None):
        """
        Initialize cache manager with intelligent caching features.
        
        Args:
            dynamodb_client: boto3 DynamoDB client
            table_name: Name of DynamoDB table for cache
            ttl_hours: Base time-to-live in hours (default 24)
            metrics_table_name: Optional table name for cache metrics (uses cache table if None)
        """
        self.dynamodb_client = dynamodb_client
        self.table_name = table_name
        self.metrics_table_name = metrics_table_name or table_name
        self.base_ttl_hours = ttl_hours
        self.cache_hits = 0
        self.cache_misses = 0
        self._data_revision = None
        self._cache_disabled = False
        self._scope_date = datetime.now(UTC).date().isoformat()
        # Adaptive TTL: frequently accessed forecasts get longer TTL
        self.max_ttl_hours = ttl_hours * 2  # Max 48 hours for frequently accessed
        
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
        if self._data_revision is None:
            try:
                response = self.dynamodb_client.get_item(TableName=self.table_name,
                    Key={'cache_key': {'S': 'CACHE_DATA_REVISION'}}, ConsistentRead=True)
                self._data_revision = response.get('Item', {}).get('revision', {}).get('S', 'initial')
            except (ClientError, ValueError, TypeError, KeyError):
                self._data_revision = uuid.uuid4().hex
                self._cache_disabled = True
        service_str = service if service else "total"
        key_parts = ["forecast-contract-v4", self._scope_date, self._data_revision, service_str, str(days), granularity]
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
        if self._cache_disabled: return None
        
        try:
            response = self.dynamodb_client.get_item(
                TableName=self.table_name,
                Key={'cache_key': {'S': cache_key}}
            )
            
            if 'Item' not in response:
                self.cache_misses += 1
                self._record_cache_miss(cache_key)
                return None
            
            item = response['Item']
            
            # Check TTL expiration
            ttl = int(item['ttl']['N'])
            current_time = int(datetime.now(UTC).timestamp())
            
            try:
                created = datetime.fromisoformat(item['created_at']['S'].replace('Z', '+00:00'))
                if created.tzinfo is None: raise ValueError('Missing cache timestamp timezone')
                maximum_age = int((created+timedelta(hours=self.max_ttl_hours)).timestamp())
                if created.timestamp() > current_time+300: raise ValueError('Future cache creation time')
            except (KeyError, ValueError, TypeError):
                self.cache_misses += 1
                return None
            if current_time >= min(ttl, maximum_age):
                # Expired
                self.cache_misses += 1
                self._record_cache_miss(cache_key)
                return None
            
            # Cache hit - parse forecast data and update access tracking
            self.cache_hits += 1
            forecast_data = json.loads(item['forecast_data']['S'])
            
            # Track access and potentially extend TTL for frequently accessed forecasts
            access_count = int(item.get('access_count', {'N': '0'})['N']) + 1
            self._update_access_tracking(cache_key, access_count, item)
            
            return forecast_data
            
        except ClientError as e:
            # Log error but don't fail - treat as cache miss
            print(f"Cache retrieval error: {e}")
            self.cache_misses += 1
            self._record_cache_miss(cache_key)
            return None
        except (KeyError, ValueError, TypeError, OverflowError) as e:
            # Malformed cache entry - treat as miss
            print(f"Cache parse error: {e}")
            self.cache_misses += 1
            self._record_cache_miss(cache_key)
            return None
        
    def store_forecast(
        self,
        forecast: Dict[str, Any],
        service: Optional[str],
        days: int,
        granularity: str
    ) -> None:
        """
        Store forecast in cache with adaptive TTL.
        
        Args:
            forecast: Forecast data to cache
            service: Service name (None for total)
            days: Forecast horizon
            granularity: Time resolution
        """
        cache_key = self.get_cache_key(service, days, granularity)
        if self._cache_disabled: return
        
        # Check if this forecast was previously cached (for adaptive TTL)
        previous_access_count = self._get_access_count(cache_key)
        
        # Adaptive TTL: Frequently accessed forecasts get longer TTL
        # Access count thresholds: 0-2 = base TTL, 3-5 = +25%, 6+ = +50%
        if previous_access_count >= 6:
            ttl_multiplier = 1.5  # 50% longer TTL
        elif previous_access_count >= 3:
            ttl_multiplier = 1.25  # 25% longer TTL
        else:
            ttl_multiplier = 1.0  # Base TTL
        
        adaptive_ttl_hours = min(int(self.base_ttl_hours * ttl_multiplier), self.max_ttl_hours)
        
        # Calculate TTL (Unix timestamp)
        ttl_time = datetime.now(UTC) + timedelta(hours=adaptive_ttl_hours)
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
                    'last_accessed': {'S': created_at},
                    'access_count': {'N': str(previous_access_count)},  # Preserve access count
                    'service': {'S': service if service else 'total'},
                    'days': {'N': str(days)},
                    'granularity': {'S': granularity},
                    'adaptive_ttl_hours': {'N': str(adaptive_ttl_hours)}  # Track adaptive TTL
                }
            )
        except ClientError as e:
            # Log error but don't fail the forecast request
            print(f"Cache storage error: {e}")
        
    def invalidate_all(self) -> None:
        """Advance dataset revision without scanning/deleting forecasts.

        Managers pin a revision before lookup, so in-flight model work stores
        under its original revision. Old entries expire through their TTL.
        Failure propagates so a cost refresh cannot claim successful invalidation.
        """
        self.dynamodb_client.put_item(TableName=self.table_name, Item={
            'cache_key': {'S': 'CACHE_DATA_REVISION'},
            'revision': {'S': uuid.uuid4().hex},
            'updated_at': {'S': datetime.now(UTC).isoformat()}
        })

    def track_cache_hit_rate(self) -> float:
        """
        Calculate and return cache hit rate (in-memory).
        
        Returns:
            Cache hit rate as percentage (0.0 to 1.0)
        """
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total
    
    def get_persistent_cache_hit_rate(self) -> Optional[float]:
        """
        Get persistent cache hit rate from DynamoDB metrics.
        
        Returns:
            Cache hit rate as percentage (0.0 to 1.0) or None if no metrics
        """
        try:
            metrics_key = 'CACHE_METRICS:AGGREGATE'
            response = self.dynamodb_client.get_item(
                TableName=self.metrics_table_name,
                Key={'cache_key': {'S': metrics_key}}
            )
            
            if 'Item' not in response:
                return None
            
            item = response['Item']
            total_hits = int(item.get('total_hits', {'N': '0'})['N'])
            total_misses = int(item.get('total_misses', {'N': '0'})['N'])
            
            total = total_hits + total_misses
            if total == 0:
                return 0.0
            
            return total_hits / total
            
        except ClientError:
            return None
    
    def _update_access_tracking(self, cache_key: str, access_count: int, item: Dict) -> None:
        """
        Update access tracking for a cached forecast (intelligent caching).
        
        Args:
            cache_key: Cache key
            access_count: New access count
            item: Current cache item
        """
        try:
            # Update access count and last accessed time
            current_ttl = int(item['ttl']['N'])
            current_time = int(datetime.now(UTC).timestamp())
            
            # Calculate remaining TTL
            remaining_seconds = current_ttl - current_time
            remaining_hours = remaining_seconds / 3600
            
            # If frequently accessed and TTL is low, extend it
            if access_count >= 3 and remaining_hours < self.base_ttl_hours * 0.5:
                # Extend TTL for frequently accessed forecasts
                if access_count >= 6:
                    new_ttl_hours = min(self.base_ttl_hours * 1.5, self.max_ttl_hours)
                else:
                    new_ttl_hours = min(self.base_ttl_hours * 1.25, self.max_ttl_hours)
                
                new_ttl = int((datetime.now(UTC) + timedelta(hours=new_ttl_hours)).timestamp())
            else:
                new_ttl = current_ttl
            
            created_at = item.get('created_at', {}).get('S')
            if not created_at: return
            created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            if created.tzinfo is None: return
            new_ttl = min(new_ttl, int((created+timedelta(hours=self.max_ttl_hours)).timestamp()))
            self.dynamodb_client.update_item(
                TableName=self.table_name,
                Key={'cache_key': {'S': cache_key}},
                UpdateExpression='SET access_count = :count, last_accessed = :accessed, #expiry = :ttl',
                ConditionExpression='created_at = :original',
                ExpressionAttributeNames={'#expiry': 'ttl'},
                ExpressionAttributeValues={
                    ':count': {'N': str(access_count)},
                    ':accessed': {'S': datetime.now(UTC).isoformat()},
                    ':ttl': {'N': str(new_ttl)}, ':original': {'S': created_at}
                }
            )
            
            # Update aggregate metrics
            self._update_aggregate_metrics(hit=True)
            
        except ClientError as e:
            # Log but don't fail
            print(f"Access tracking update error: {e}")
    
    def _record_cache_miss(self, cache_key: str) -> None:
        """
        Record a cache miss in persistent metrics.
        
        Args:
            cache_key: Cache key that was missed
        """
        try:
            self._update_aggregate_metrics(hit=False)
        except ClientError as e:
            # Log but don't fail
            print(f"Cache miss recording error: {e}")
    
    def _update_aggregate_metrics(self, hit: bool) -> None:
        """
        Update aggregate cache metrics in DynamoDB (persistent tracking).
        
        Args:
            hit: True if cache hit, False if cache miss
        """
        try:
            metrics_key = 'CACHE_METRICS:AGGREGATE'
            current_time = int(datetime.now(UTC).timestamp())
            
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
                    Key={'cache_key': {'S': metrics_key}},
                    UpdateExpression=update_expr,
                    ExpressionAttributeValues=expr_values
                )
            except ClientError as e:
                # If item doesn't exist, create it
                if e.response['Error']['Code'] == 'ValidationException':
                    self.dynamodb_client.put_item(
                        TableName=self.metrics_table_name,
                        Item={
                            'cache_key': {'S': metrics_key},
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
            print(f"Aggregate metrics update error: {e}")
    
    def _get_access_count(self, cache_key: str) -> int:
        """
        Get access count for a cache key.
        
        Args:
            cache_key: Cache key to check
            
        Returns:
            Access count (0 if not found)
        """
        try:
            response = self.dynamodb_client.get_item(
                TableName=self.table_name,
                Key={'cache_key': {'S': cache_key}},
                ProjectionExpression='access_count'
            )
            
            if 'Item' not in response:
                return 0
            
            return int(response['Item'].get('access_count', {'N': '0'})['N'])
            
        except ClientError:
            return 0
    
    def warm_cache(
        self, 
        common_queries: List[Dict[str, Any]], 
        forecast_generator: Optional[Callable[[Optional[str], int, str], Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Warm cache by pre-generating forecasts for common queries (intelligent caching).
        
        This method can be called periodically (e.g., via EventBridge) to pre-generate
        forecasts for frequently requested parameters, improving cache hit rates.
        
        Args:
            common_queries: List of query dicts with keys: service (optional), days, granularity
                           Example: [{'service': None, 'days': 30, 'granularity': 'daily'}]
            forecast_generator: Optional callable that generates forecasts. Should accept
                               (service, days, granularity) and return a forecast dict.
                               If None, only checks cache status without generating.
        
        Returns:
            Dict with warming results: {'warmed': int, 'cached': int, 'failed': int, 'details': List}
        """
        results = {
            'warmed': 0,  # Newly generated and cached
            'cached': 0,  # Already in cache
            'failed': 0,  # Generation failed
            'details': []
        }
        
        try:
            for query in common_queries:
                service = query.get('service')
                days = query.get('days', 30)
                granularity = query.get('granularity', 'daily')
                cache_key = self.get_cache_key(service, days, granularity)
                
                # Check if already cached
                cached = self.get_cached_forecast(service, days, granularity)
                if cached:
                    results['cached'] += 1
                    results['details'].append({
                        'cache_key': cache_key,
                        'status': 'cached',
                        'service': service,
                        'days': days,
                        'granularity': granularity
                    })
                    continue
                
                # Generate forecast if generator provided
                if forecast_generator:
                    try:
                        forecast_data = forecast_generator(service, days, granularity)
                        if forecast_data:
                            # Store in cache
                            self.store_forecast(forecast_data, service, days, granularity)
                            results['warmed'] += 1
                            results['details'].append({
                                'cache_key': cache_key,
                                'status': 'warmed',
                                'service': service,
                                'days': days,
                                'granularity': granularity
                            })
                        else:
                            results['failed'] += 1
                            results['details'].append({
                                'cache_key': cache_key,
                                'status': 'failed',
                                'error': 'Generator returned None',
                                'service': service,
                                'days': days,
                                'granularity': granularity
                            })
                    except Exception as e:
                        results['failed'] += 1
                        results['details'].append({
                            'cache_key': cache_key,
                            'status': 'failed',
                            'error': str(e),
                            'service': service,
                            'days': days,
                            'granularity': granularity
                        })
                else:
                    # No generator - just track what needs warming
                    results['details'].append({
                        'cache_key': cache_key,
                        'status': 'pending',
                        'service': service,
                        'days': days,
                        'granularity': granularity,
                        'note': 'No forecast generator provided - use external scheduler to call forecast API'
                    })
                
        except Exception as e:
            print(f"Cache warming error: {e}")
            results['failed'] += 1
        
        return results