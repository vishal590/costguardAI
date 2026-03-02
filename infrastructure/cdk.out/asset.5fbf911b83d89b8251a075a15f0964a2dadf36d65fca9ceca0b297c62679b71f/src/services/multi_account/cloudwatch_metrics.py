"""
CloudWatch Metrics Service for Multi-Account Cost Management

This service provides custom CloudWatch metrics for monitoring the performance
and health of the multi-account cost management system.

Metrics tracked:
- MultiAccountCostCollection.Duration
- MultiAccountCostCollection.SuccessRate
- CostAggregation.CacheHitRate
- AllocationEngine.UnallocatedPercentage
"""

import boto3
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MetricData:
    """Represents a CloudWatch metric data point."""
    metric_name: str
    value: float
    unit: str
    dimensions: Dict[str, str]
    timestamp: Optional[datetime] = None


class CloudWatchMetricsService:
    """Service for publishing custom CloudWatch metrics."""
    
    def __init__(self, namespace: str = "CostGuard/MultiAccount"):
        """Initialize the CloudWatch metrics service."""
        self.cloudwatch = boto3.client('cloudwatch')
        self.namespace = namespace
        
    def put_metric(self, metric_name: str, value: float, unit: str = 'Count', 
                   dimensions: Optional[Dict[str, str]] = None) -> None:
        """Put a single metric to CloudWatch."""
        try:
            metric_data = {
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit,
                'Timestamp': datetime.utcnow()
            }
            
            if dimensions:
                metric_data['Dimensions'] = [
                    {'Name': k, 'Value': v} for k, v in dimensions.items()
                ]
            
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=[metric_data]
            )
            
            logger.info(f"Published metric {metric_name}: {value} {unit}")
            
        except Exception as e:
            logger.error(f"Failed to publish metric {metric_name}: {str(e)}")
    
    def put_metrics_batch(self, metrics: List[MetricData]) -> None:
        """Put multiple metrics to CloudWatch in a batch."""
        try:
            metric_data = []
            
            for metric in metrics:
                data = {
                    'MetricName': metric.metric_name,
                    'Value': metric.value,
                    'Unit': metric.unit,
                    'Timestamp': metric.timestamp or datetime.utcnow()
                }
                
                if metric.dimensions:
                    data['Dimensions'] = [
                        {'Name': k, 'Value': v} for k, v in metric.dimensions.items()
                    ]
                
                metric_data.append(data)
            
            # CloudWatch allows max 20 metrics per batch
            for i in range(0, len(metric_data), 20):
                batch = metric_data[i:i+20]
                self.cloudwatch.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=batch
                )
            
            logger.info(f"Published {len(metrics)} metrics in batch")
            
        except Exception as e:
            logger.error(f"Failed to publish metrics batch: {str(e)}")
    
    def record_cost_collection_duration(self, duration_seconds: float, 
                                      account_count: int) -> None:
        """Record cost collection duration metric."""
        self.put_metric(
            metric_name='MultiAccountCostCollection.Duration',
            value=duration_seconds,
            unit='Seconds',
            dimensions={
                'AccountCount': str(account_count)
            }
        )
    
    def record_cost_collection_success_rate(self, successful_accounts: int, 
                                          total_accounts: int) -> None:
        """Record cost collection success rate metric."""
        success_rate = (successful_accounts / total_accounts * 100) if total_accounts > 0 else 0
        
        self.put_metric(
            metric_name='MultiAccountCostCollection.SuccessRate',
            value=success_rate,
            unit='Percent',
            dimensions={
                'TotalAccounts': str(total_accounts)
            }
        )
    
    def record_cache_hit_rate(self, cache_hits: int, total_requests: int, 
                             cache_type: str = 'CostAggregation') -> None:
        """Record cache hit rate metric."""
        hit_rate = (cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        self.put_metric(
            metric_name=f'{cache_type}.CacheHitRate',
            value=hit_rate,
            unit='Percent',
            dimensions={
                'CacheType': cache_type
            }
        )
    
    def record_unallocated_percentage(self, unallocated_amount: float, 
                                    total_amount: float, 
                                    organization_id: str) -> None:
        """Record unallocated cost percentage metric."""
        unallocated_percentage = (unallocated_amount / total_amount * 100) if total_amount > 0 else 0
        
        self.put_metric(
            metric_name='AllocationEngine.UnallocatedPercentage',
            value=unallocated_percentage,
            unit='Percent',
            dimensions={
                'OrganizationId': organization_id
            }
        )
    
    def record_api_response_time(self, endpoint: str, duration_ms: float) -> None:
        """Record API response time metric."""
        self.put_metric(
            metric_name='API.ResponseTime',
            value=duration_ms,
            unit='Milliseconds',
            dimensions={
                'Endpoint': endpoint
            }
        )
    
    def record_lambda_error(self, function_name: str, error_type: str) -> None:
        """Record Lambda function error metric."""
        self.put_metric(
            metric_name='Lambda.Errors',
            value=1,
            unit='Count',
            dimensions={
                'FunctionName': function_name,
                'ErrorType': error_type
            }
        )
    
    def record_dynamodb_throttle(self, table_name: str, operation: str) -> None:
        """Record DynamoDB throttling metric."""
        self.put_metric(
            metric_name='DynamoDB.Throttles',
            value=1,
            unit='Count',
            dimensions={
                'TableName': table_name,
                'Operation': operation
            }
        )


class MetricsCollector:
    """Context manager for collecting metrics during operations."""
    
    def __init__(self, metrics_service: CloudWatchMetricsService, 
                 operation_name: str, dimensions: Optional[Dict[str, str]] = None):
        """Initialize the metrics collector."""
        self.metrics_service = metrics_service
        self.operation_name = operation_name
        self.dimensions = dimensions or {}
        self.start_time = None
        self.success = False
        
    def __enter__(self):
        """Start timing the operation."""
        self.start_time = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Record metrics when operation completes."""
        if self.start_time:
            duration = time.time() - self.start_time
            
            # Record duration
            self.metrics_service.put_metric(
                metric_name=f'{self.operation_name}.Duration',
                value=duration,
                unit='Seconds',
                dimensions=self.dimensions
            )
            
            # Record success/failure
            success_value = 1 if exc_type is None else 0
            self.metrics_service.put_metric(
                metric_name=f'{self.operation_name}.Success',
                value=success_value,
                unit='Count',
                dimensions=self.dimensions
            )
            
            if exc_type:
                # Record error details
                self.metrics_service.put_metric(
                    metric_name=f'{self.operation_name}.Errors',
                    value=1,
                    unit='Count',
                    dimensions={
                        **self.dimensions,
                        'ErrorType': exc_type.__name__
                    }
                )
    
    def add_dimension(self, key: str, value: str) -> None:
        """Add a dimension to the metrics."""
        self.dimensions[key] = value
    
    def record_custom_metric(self, metric_name: str, value: float, 
                           unit: str = 'Count') -> None:
        """Record a custom metric during the operation."""
        self.metrics_service.put_metric(
            metric_name=f'{self.operation_name}.{metric_name}',
            value=value,
            unit=unit,
            dimensions=self.dimensions
        )


# Global metrics service instance
_metrics_service = None


def get_metrics_service() -> CloudWatchMetricsService:
    """Get the global metrics service instance."""
    global _metrics_service
    if _metrics_service is None:
        _metrics_service = CloudWatchMetricsService()
    return _metrics_service


def metrics_collector(operation_name: str, 
                     dimensions: Optional[Dict[str, str]] = None) -> MetricsCollector:
    """Create a metrics collector for an operation."""
    return MetricsCollector(get_metrics_service(), operation_name, dimensions)