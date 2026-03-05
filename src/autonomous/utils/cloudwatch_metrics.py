"""
CloudWatch Metrics Utility for Autonomous Action Loops

Provides centralized CloudWatch metrics emission for monitoring autonomous
actions. Limits to 5 custom metrics to stay within AWS Free Tier.

Metrics:
1. ActionSuccessRate - Success rate by action type
2. ConfidenceScore - Average confidence score across all actions
3. CumulativeSavings - Total cost savings from all actions
4. ActiveActions - Count of in-progress actions
5. BudgetUtilization - Percentage of Free Tier budget used

Usage:
    from autonomous.utils.cloudwatch_metrics import MetricsPublisher
    
    publisher = MetricsPublisher()
    publisher.publish_action_success_rate('schedule', 0.95)
    publisher.publish_cumulative_savings(150.50)
"""

import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Union

import boto3
from botocore.exceptions import ClientError

# CloudWatch client
cloudwatch = boto3.client('cloudwatch')

# Metric namespace (using existing Phase 6 namespace)
METRIC_NAMESPACE = 'CostGuard/AIML'

# Demo mode flag
DEMO_MODE = os.environ.get('DEMO_MODE', 'false').lower() == 'true'


class MetricsPublisher:
    """
    Publishes CloudWatch metrics for autonomous actions.
    
    Limits to 5 custom metrics to stay within Free Tier (10 metrics free).
    """
    
    def __init__(self, namespace: str = METRIC_NAMESPACE):
        """
        Initialize metrics publisher.
        
        Args:
            namespace: CloudWatch metric namespace
        """
        self.namespace = namespace
        self.cloudwatch = cloudwatch
    
    def publish_action_success_rate(
        self,
        action_type: str,
        success_rate: float,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Publish action success rate metric.
        
        Args:
            action_type: Type of action (schedule, spot_migration, right_sizing, etc.)
            success_rate: Success rate as decimal (0.0 to 1.0)
            timestamp: Optional timestamp (defaults to now)
            
        Returns:
            bool: True if published successfully
            
        Requirements: 9.1
        """
        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=[
                    {
                        'MetricName': 'ActionSuccessRate',
                        'Value': success_rate * 100,  # Convert to percentage
                        'Unit': 'Percent',
                        'Timestamp': timestamp or datetime.utcnow(),
                        'Dimensions': [
                            {
                                'Name': 'ActionType',
                                'Value': action_type
                            },
                            {
                                'Name': 'DemoMode',
                                'Value': 'true' if DEMO_MODE else 'false'
                            }
                        ]
                    }
                ]
            )
            return True
        except ClientError as e:
            print(f"Error publishing ActionSuccessRate metric: {e}")
            return False
    
    def publish_confidence_score(
        self,
        average_confidence: float,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Publish average confidence score metric.
        
        Args:
            average_confidence: Average confidence score (0.0 to 1.0)
            timestamp: Optional timestamp (defaults to now)
            
        Returns:
            bool: True if published successfully
            
        Requirements: 9.2
        """
        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=[
                    {
                        'MetricName': 'ConfidenceScore',
                        'Value': average_confidence,
                        'Unit': 'None',
                        'Timestamp': timestamp or datetime.utcnow(),
                        'Dimensions': [
                            {
                                'Name': 'DemoMode',
                                'Value': 'true' if DEMO_MODE else 'false'
                            }
                        ]
                    }
                ]
            )
            return True
        except ClientError as e:
            print(f"Error publishing ConfidenceScore metric: {e}")
            return False
    
    def publish_cumulative_savings(
        self,
        total_savings: Union[float, Decimal],
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Publish cumulative cost savings metric.
        
        Args:
            total_savings: Total cost savings in dollars
            timestamp: Optional timestamp (defaults to now)
            
        Returns:
            bool: True if published successfully
            
        Requirements: 9.3
        """
        try:
            savings_value = float(total_savings) if isinstance(total_savings, Decimal) else total_savings
            
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=[
                    {
                        'MetricName': 'CumulativeSavings',
                        'Value': abs(savings_value),  # Use absolute value
                        'Unit': 'None',  # Dollars
                        'Timestamp': timestamp or datetime.utcnow(),
                        'Dimensions': [
                            {
                                'Name': 'DemoMode',
                                'Value': 'true' if DEMO_MODE else 'false'
                            }
                        ]
                    }
                ]
            )
            return True
        except ClientError as e:
            print(f"Error publishing CumulativeSavings metric: {e}")
            return False
    
    def publish_active_actions(
        self,
        count: int,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Publish count of active (in-progress) actions.
        
        Args:
            count: Number of actions currently in progress
            timestamp: Optional timestamp (defaults to now)
            
        Returns:
            bool: True if published successfully
            
        Requirements: 9.4
        """
        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=[
                    {
                        'MetricName': 'ActiveActions',
                        'Value': count,
                        'Unit': 'Count',
                        'Timestamp': timestamp or datetime.utcnow(),
                        'Dimensions': [
                            {
                                'Name': 'DemoMode',
                                'Value': 'true' if DEMO_MODE else 'false'
                            }
                        ]
                    }
                ]
            )
            return True
        except ClientError as e:
            print(f"Error publishing ActiveActions metric: {e}")
            return False
    
    def publish_budget_utilization(
        self,
        utilization_percent: float,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Publish Free Tier budget utilization percentage.
        
        Args:
            utilization_percent: Percentage of Free Tier budget used (0-100)
            timestamp: Optional timestamp (defaults to now)
            
        Returns:
            bool: True if published successfully
            
        Requirements: 9.4, 7.6
        """
        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=[
                    {
                        'MetricName': 'BudgetUtilization',
                        'Value': utilization_percent,
                        'Unit': 'Percent',
                        'Timestamp': timestamp or datetime.utcnow(),
                        'Dimensions': [
                            {
                                'Name': 'DemoMode',
                                'Value': 'true' if DEMO_MODE else 'false'
                            }
                        ]
                    }
                ]
            )
            return True
        except ClientError as e:
            print(f"Error publishing BudgetUtilization metric: {e}")
            return False
    
    def publish_batch_metrics(
        self,
        metrics: List[Dict]
    ) -> bool:
        """
        Publish multiple metrics in a single API call.
        
        Args:
            metrics: List of metric data dictionaries
            
        Returns:
            bool: True if published successfully
            
        Example:
            publisher.publish_batch_metrics([
                {
                    'MetricName': 'ActionSuccessRate',
                    'Value': 95.0,
                    'Unit': 'Percent',
                    'Dimensions': [{'Name': 'ActionType', 'Value': 'schedule'}]
                },
                {
                    'MetricName': 'CumulativeSavings',
                    'Value': 150.50,
                    'Unit': 'None'
                }
            ])
        """
        try:
            # Add namespace and timestamp to all metrics
            for metric in metrics:
                if 'Timestamp' not in metric:
                    metric['Timestamp'] = datetime.utcnow()
                if 'Dimensions' not in metric:
                    metric['Dimensions'] = []
                # Add DemoMode dimension if not present
                if not any(d['Name'] == 'DemoMode' for d in metric['Dimensions']):
                    metric['Dimensions'].append({
                        'Name': 'DemoMode',
                        'Value': 'true' if DEMO_MODE else 'false'
                    })
            
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=metrics
            )
            return True
        except ClientError as e:
            print(f"Error publishing batch metrics: {e}")
            return False
    
    @staticmethod
    def get_metric_statistics(
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        period: int = 300,
        statistics: List[str] = None,
        dimensions: List[Dict] = None
    ) -> Optional[Dict]:
        """
        Retrieve metric statistics from CloudWatch.
        
        Args:
            metric_name: Name of the metric
            start_time: Start time for statistics
            end_time: End time for statistics
            period: Period in seconds (default: 300 = 5 minutes)
            statistics: List of statistics to retrieve (default: ['Average', 'Sum'])
            dimensions: Optional dimensions to filter by
            
        Returns:
            Dict with metric statistics or None if error
        """
        try:
            if statistics is None:
                statistics = ['Average', 'Sum', 'Maximum', 'Minimum']
            
            params = {
                'Namespace': METRIC_NAMESPACE,
                'MetricName': metric_name,
                'StartTime': start_time,
                'EndTime': end_time,
                'Period': period,
                'Statistics': statistics
            }
            
            if dimensions:
                params['Dimensions'] = dimensions
            
            response = cloudwatch.get_metric_statistics(**params)
            return response
        except ClientError as e:
            print(f"Error retrieving metric statistics: {e}")
            return None


# Singleton instance
_metrics_publisher = None


def get_metrics_publisher() -> MetricsPublisher:
    """Get singleton metrics publisher instance."""
    global _metrics_publisher
    if _metrics_publisher is None:
        _metrics_publisher = MetricsPublisher()
    return _metrics_publisher
