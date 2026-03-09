"""
GPU Cost Tracker for Phase 6: AI/ML Workload Cost Management.

This module tracks EC2 GPU instance costs by workload type, calculating cost per GPU hour
and identifying idle GPU instances.

Requirements: FR-1.1, FR-1.3, FR-1.5, FR-1.6
"""
import logging
from typing import List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from botocore.exceptions import ClientError

from .error_handler import (
    retry_with_exponential_backoff,
    handle_cost_explorer_error,
    validate_minimum_data,
    AIMLError
)

logger = logging.getLogger(__name__)

# GPU instance type patterns
GPU_INSTANCE_PATTERNS = ['p3.', 'p4.', 'p4d.', 'p5.', 'g4.', 'g5.', 'g6.']


@dataclass
class GPUCostData:
    """GPU cost data model."""
    date: str
    instance_id: str
    instance_type: str
    workload_type: str  # "training", "inference", "idle", "unknown"
    cost: float
    gpu_hours: float
    cost_per_gpu_hour: float
    utilization: float  # 0-100%
    classification_confidence: float  # 0-1
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class GPUCostTracker:
    """
    Tracks EC2 GPU instance costs by workload type.
    
    Requirements: FR-1.1, FR-1.3, FR-1.5, FR-1.6
    """
    
    def __init__(self, dynamodb_client, cost_explorer_client=None):
        """
        Initialize GPU Cost Tracker.
        
        Args:
            dynamodb_client: DynamoDB client for data storage
            cost_explorer_client: Cost Explorer client (optional, will create if not provided)
        """
        self.dynamodb = dynamodb_client
        self.cost_explorer = cost_explorer_client
        self._default_session = None
        
    @retry_with_exponential_backoff(max_retries=3)
    def collect_gpu_costs(
        self,
        start_date: str,
        end_date: str,
        workload_type: Optional[str] = None,
        instance_type: Optional[str] = None,
        boto3_session=None
    ) -> List[GPUCostData]:
        """
        Collect GPU costs from Cost Explorer for specified date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            workload_type: Optional filter by workload type
            instance_type: Optional filter by instance type
            boto3_session: Optional boto3 session for cross-account access
            
        Returns:
            List of GPUCostData objects
            
        Requirements: FR-1.1, FR-1.6
        """
        logger.info(f"Collecting GPU costs from {start_date} to {end_date}")
        
        try:
            # Use provided session or default Cost Explorer client
            if boto3_session:
                ce_client = boto3_session.client('ce')
            elif not self.cost_explorer:
                import boto3
                ce_client = boto3.client('ce')
            else:
                ce_client = self.cost_explorer
            
            # Query Cost Explorer for EC2 costs grouped by instance type.
            # Cost Explorer allows at most 2 GroupBy dimensions; we use SERVICE and INSTANCE_TYPE.
            response = ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date,
                    'End': end_date
                },
                Granularity='DAILY',
                Metrics=['UnblendedCost', 'UsageQuantity'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                    {'Type': 'DIMENSION', 'Key': 'INSTANCE_TYPE'}
                ],
                Filter={
                    'Dimensions': {
                        'Key': 'SERVICE',
                        'Values': ['Amazon Elastic Compute Cloud - Compute']
                    }
                }
            )
            
            # Parse response and filter for GPU instances
            gpu_costs = []
            for result in response.get('ResultsByTime', []):
                date = result['TimePeriod']['Start']
                
                for group in result.get('Groups', []):
                    keys = group['Keys']
                    if len(keys) < 2:
                        continue
                    
                    service = keys[0]  # Should be EC2
                    instance_type = keys[1] if len(keys) > 1 else ''
                    
                    # Filter for GPU instance types
                    if not any(pattern in instance_type for pattern in GPU_INSTANCE_PATTERNS):
                        continue
                    
                    # Extract cost and usage
                    cost = float(group['Metrics']['UnblendedCost']['Amount'])
                    usage_quantity = float(group['Metrics'].get('UsageQuantity', {}).get('Amount', 0))
                    
                    # Calculate GPU hours (usage quantity is typically in hours for EC2)
                    gpu_hours = usage_quantity
                    
                    # Calculate cost per GPU hour
                    cost_per_gpu_hour = self.calculate_cost_per_gpu_hour(cost, gpu_hours) if gpu_hours > 0 else 0.0
                    
                    # Try to get workload classification from DynamoDB or default to "unknown"
                    detected_workload_type = "unknown"
                    utilization = 0.0
                    classification_confidence = 0.0
                    
                    # Instance ID not available when grouping only by SERVICE+INSTANCE_TYPE (no USAGE_TYPE)
                    instance_id = "unknown"
                    
                    gpu_cost_data = GPUCostData(
                        date=date,
                        instance_id=instance_id,
                        instance_type=instance_type,
                        workload_type=detected_workload_type,
                        cost=cost,
                        gpu_hours=gpu_hours,
                        cost_per_gpu_hour=cost_per_gpu_hour,
                        utilization=utilization,
                        classification_confidence=classification_confidence
                    )
                    
                    # Apply filters if provided
                    if workload_type and workload_type != gpu_cost_data.workload_type:
                        continue
                    if instance_type and instance_type != gpu_cost_data.instance_type:
                        continue
                    
                    gpu_costs.append(gpu_cost_data)
            
            logger.info(f"Collected {len(gpu_costs)} GPU cost records")
            return gpu_costs
        except ClientError as e:
            # Handle Cost Explorer errors
            error_result = handle_cost_explorer_error(e, cache_data=None)
            if 'data' in error_result:
                return error_result['data']
            raise
    
    def filter_gpu_instances(self, cost_data: List[dict]) -> List[dict]:
        """
        Filter cost data to only GPU instance types.
        
        Args:
            cost_data: Raw cost data from Cost Explorer
            
        Returns:
            Filtered list containing only GPU instances
            
        Requirements: FR-1.1
        """
        gpu_costs = []
        for item in cost_data:
            instance_type = item.get('instance_type', '')
            if any(pattern in instance_type for pattern in GPU_INSTANCE_PATTERNS):
                gpu_costs.append(item)
        
        logger.info(f"Filtered {len(gpu_costs)} GPU instances from {len(cost_data)} total instances")
        return gpu_costs
    
    def calculate_cost_per_gpu_hour(self, cost: float, gpu_hours: float) -> float:
        """
        Calculate cost per GPU hour for a workload.
        
        Args:
            cost: Total cost
            gpu_hours: Total GPU hours
            
        Returns:
            Cost per GPU hour
            
        Requirements: FR-1.3
        """
        if gpu_hours == 0:
            return 0.0
        return cost / gpu_hours
    
    def identify_idle_gpus(self, utilization_data: List[dict], threshold: float = 10.0) -> List[str]:
        """
        Identify GPU instances with utilization below threshold.
        
        Args:
            utilization_data: List of GPU utilization data
            threshold: Utilization threshold percentage (default: 10%)
            
        Returns:
            List of idle GPU instance IDs
            
        Requirements: FR-1.5
        """
        idle_gpus = []
        for item in utilization_data:
            if item.get('utilization', 0) < threshold:
                idle_gpus.append(item.get('instance_id'))
        
        logger.info(f"Identified {len(idle_gpus)} idle GPUs (threshold: {threshold}%)")
        return idle_gpus
