"""
Workload Classifier for Phase 6: AI/ML Workload Cost Management.

This module classifies GPU workloads as training, inference, or idle based on
CloudWatch GPU utilization metrics and EC2 tags.

Requirements: FR-2.1, FR-2.2, FR-2.3, FR-2.4, FR-2.5, FR-2.6
"""
import logging
from typing import List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
import statistics

logger = logging.getLogger(__name__)


@dataclass
class WorkloadClassification:
    """Workload classification data model."""
    instance_id: str
    workload_type: str  # "training", "inference", "idle", "unknown"
    confidence: float  # 0-1
    classification_method: str  # "cloudwatch-metrics", "manual-tag"
    gpu_utilization_avg: float
    gpu_utilization_pattern: List[float]
    timestamp: str
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class WorkloadClassifier:
    """
    Classifies GPU workloads as training, inference, or idle.
    
    Requirements: FR-2.1, FR-2.2, FR-2.3, FR-2.4, FR-2.5, FR-2.6
    """
    
    # Classification thresholds
    TRAINING_THRESHOLD = 70.0  # >70% continuous utilization
    INFERENCE_MIN_THRESHOLD = 20.0  # 20-70% with spikes
    INFERENCE_MAX_THRESHOLD = 70.0
    IDLE_THRESHOLD = 10.0  # <10% utilization
    
    # Minimum data points required for classification
    MIN_DATA_POINTS = 12  # At least 1 hour of 5-minute intervals
    
    def __init__(self, dynamodb_client, cloudwatch_client=None, ec2_client=None):
        """
        Initialize Workload Classifier.
        
        Args:
            dynamodb_client: DynamoDB client for storing classifications
            cloudwatch_client: CloudWatch client for GPU metrics (optional)
            ec2_client: EC2 client for reading tags (optional)
        """
        self.dynamodb = dynamodb_client
        self.cloudwatch = cloudwatch_client
        self.ec2 = ec2_client
    
    def classify_workload(
        self,
        instance_id: str,
        start_date: str,
        end_date: str
    ) -> WorkloadClassification:
        """
        Classify workload based on CloudWatch GPU metrics or manual tags.
        
        Args:
            instance_id: EC2 instance ID
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            WorkloadClassification object
            
        Requirements: FR-2.1, FR-2.2, FR-2.3
        """
        logger.info(f"Classifying workload for instance {instance_id}")
        
        # Check for manual classification first
        manual_classification = self.get_manual_classification(instance_id)
        if manual_classification:
            logger.info(f"Using manual classification: {manual_classification}")
            return WorkloadClassification(
                instance_id=instance_id,
                workload_type=manual_classification,
                confidence=1.0,
                classification_method="manual-tag",
                gpu_utilization_avg=0.0,
                gpu_utilization_pattern=[],
                timestamp=datetime.utcnow().isoformat()
            )
        
        # Get GPU utilization pattern from CloudWatch
        utilization_pattern = self.get_gpu_utilization_pattern(
            instance_id, start_date, end_date
        )
        
        if not utilization_pattern or len(utilization_pattern) < self.MIN_DATA_POINTS:
            logger.warning(f"Insufficient data for classification: {len(utilization_pattern)} points")
            return WorkloadClassification(
                instance_id=instance_id,
                workload_type="unknown",
                confidence=0.0,
                classification_method="cloudwatch-metrics",
                gpu_utilization_avg=0.0,
                gpu_utilization_pattern=[],
                timestamp=datetime.utcnow().isoformat()
            )
        
        # Apply classification rules
        workload_type, confidence = self.apply_classification_rules(utilization_pattern)
        avg_utilization = statistics.mean(utilization_pattern)
        
        classification = WorkloadClassification(
            instance_id=instance_id,
            workload_type=workload_type,
            confidence=confidence,
            classification_method="cloudwatch-metrics",
            gpu_utilization_avg=avg_utilization,
            gpu_utilization_pattern=utilization_pattern,
            timestamp=datetime.utcnow().isoformat()
        )
        
        # Store classification in DynamoDB
        self.store_classification(instance_id, classification)
        
        return classification
    
    def get_gpu_utilization_pattern(
        self,
        instance_id: str,
        start_date: str,
        end_date: str
    ) -> List[float]:
        """
        Retrieve GPU utilization metrics from CloudWatch.
        
        Args:
            instance_id: EC2 instance ID
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of GPU utilization percentages
            
        Requirements: FR-2.1
        """
        logger.info(f"Retrieving GPU utilization for {instance_id} from {start_date} to {end_date}")
        
        if not self.cloudwatch:
            import boto3
            self.cloudwatch = boto3.client('cloudwatch')
        
        try:
            from datetime import datetime, timedelta
            
            # Parse dates
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            # Get GPU utilization metrics (5-minute intervals)
            # Try GPUUtilization metric first (for GPU instances with NVIDIA drivers)
            utilization_values = []
            
            try:
                response = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/EC2',
                    MetricName='GPUUtilization',
                    Dimensions=[
                        {'Name': 'InstanceId', 'Value': instance_id}
                    ],
                    StartTime=start_dt,
                    EndTime=end_dt,
                    Period=300,  # 5-minute intervals
                    Statistics=['Average']
                )
                
                # Extract utilization values
                for datapoint in sorted(response.get('Datapoints', []), key=lambda x: x['Timestamp']):
                    utilization_values.append(float(datapoint['Average']))
                    
            except Exception as e:
                logger.warning(f"GPUUtilization metric not available for {instance_id}: {e}")
                # Fallback to CPUUtilization if GPUUtilization is not available
                # (some GPU instances may not have GPUUtilization metric enabled)
                try:
                    response = self.cloudwatch.get_metric_statistics(
                        Namespace='AWS/EC2',
                        MetricName='CPUUtilization',
                        Dimensions=[
                            {'Name': 'InstanceId', 'Value': instance_id}
                        ],
                        StartTime=start_dt,
                        EndTime=end_dt,
                        Period=300,
                        Statistics=['Average']
                    )
                    
                    for datapoint in sorted(response.get('Datapoints', []), key=lambda x: x['Timestamp']):
                        utilization_values.append(float(datapoint['Average']))
                        
                except Exception as e2:
                    logger.error(f"Failed to get CPUUtilization for {instance_id}: {e2}")
                    return []
            
            logger.info(f"Retrieved {len(utilization_values)} GPU utilization data points")
            return utilization_values
            
        except Exception as e:
            logger.error(f"Error retrieving GPU utilization for {instance_id}: {e}")
            return []
    
    def apply_classification_rules(
        self,
        utilization_pattern: List[float]
    ) -> Tuple[str, float]:
        """
        Apply classification rules to determine workload type and confidence.
        
        Classification rules (FR-2.4):
        - Training: GPU utilization > 70% continuously for > 1 hour
        - Inference: GPU utilization 20-70% with frequent spikes
        - Idle: GPU utilization < 10%
        
        Args:
            utilization_pattern: List of GPU utilization percentages
            
        Returns:
            Tuple of (workload_type, confidence_score)
            
        Requirements: FR-2.4
        """
        if not utilization_pattern:
            return "unknown", 0.0
        
        avg_utilization = statistics.mean(utilization_pattern)
        
        # Idle: average utilization < 10%
        if avg_utilization < self.IDLE_THRESHOLD:
            confidence = 1.0 - (avg_utilization / self.IDLE_THRESHOLD) * 0.2
            return "idle", min(confidence, 1.0)
        
        # Training: high continuous utilization > 70%
        if avg_utilization > self.TRAINING_THRESHOLD:
            # Check for continuity (low variance indicates continuous usage)
            variance = statistics.variance(utilization_pattern) if len(utilization_pattern) > 1 else 0
            std_dev = variance ** 0.5
            
            # High utilization with low variance = training
            if std_dev < 15.0:  # Low variance threshold
                confidence = 0.8 + (avg_utilization - self.TRAINING_THRESHOLD) / 100.0
                return "training", min(confidence, 1.0)
        
        # Inference: moderate utilization with spikes (20-70%)
        if self.INFERENCE_MIN_THRESHOLD <= avg_utilization <= self.INFERENCE_MAX_THRESHOLD:
            # Check for spikes (high variance indicates bursty usage)
            variance = statistics.variance(utilization_pattern) if len(utilization_pattern) > 1 else 0
            std_dev = variance ** 0.5
            
            # Moderate utilization with high variance = inference
            if std_dev > 10.0:  # High variance threshold
                confidence = 0.7 + (std_dev / 50.0) * 0.2
                return "inference", min(confidence, 1.0)
        
        # Default: unknown with low confidence
        return "unknown", 0.3
    
    def get_manual_classification(self, instance_id: str) -> Optional[str]:
        """
        Check for manual classification via EC2 tags.
        
        Args:
            instance_id: EC2 instance ID
            
        Returns:
            Manual workload type or None
            
        Requirements: FR-2.3
        """
        logger.info(f"Checking for manual classification tag on {instance_id}")
        
        if not self.ec2:
            import boto3
            self.ec2 = boto3.client('ec2')
        
        try:
            # Get instance tags
            response = self.ec2.describe_tags(
                Filters=[
                    {'Name': 'resource-id', 'Values': [instance_id]},
                    {'Name': 'key', 'Values': ['WorkloadType', 'workload-type', 'Workload-Type']}
                ]
            )
            
            # Check for workload type tags
            for tag in response.get('Tags', []):
                tag_key = tag.get('Key', '').lower()
                tag_value = tag.get('Value', '').lower()
                
                # Check if it's a workload type tag
                if 'workload' in tag_key and 'type' in tag_key:
                    # Validate tag value
                    if tag_value in ['training', 'inference', 'idle']:
                        logger.info(f"Found manual classification tag: {tag_value}")
                        return tag_value
            
            return None
            
        except Exception as e:
            logger.warning(f"Error reading EC2 tags for {instance_id}: {e}")
            return None
    
    def store_classification(
        self,
        instance_id: str,
        classification: WorkloadClassification
    ) -> None:
        """
        Store classification in DynamoDB with timestamp.
        
        Args:
            instance_id: EC2 instance ID
            classification: WorkloadClassification object
            
        Requirements: FR-2.6
        """
        try:
            import boto3
            import os
            from datetime import datetime, timezone, timedelta
            
            # Get table name from environment or use default
            table_name = os.environ.get('WORKLOAD_CLASSIFICATIONS_TABLE', 'costguard-workload-classifications')
            
            # Use DynamoDB resource for easier item operations
            if not hasattr(self, 'dynamodb_resource'):
                self.dynamodb_resource = boto3.resource('dynamodb')
            
            table = self.dynamodb_resource.Table(table_name)
            
            # Calculate TTL (30 days from now)
            ttl = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
            
            # Prepare item for DynamoDB
            item = {
                'instance_id': instance_id,
                'timestamp': classification.timestamp,
                'workload_type': classification.workload_type,
                'confidence': classification.confidence,
                'classification_method': classification.classification_method,
                'gpu_utilization_avg': classification.gpu_utilization_avg,
                'gpu_utilization_pattern': classification.gpu_utilization_pattern,
                'ttl': ttl
            }
            
            # Store in DynamoDB
            table.put_item(Item=item)
            
            logger.info(f"Stored classification for {instance_id}: {classification.workload_type} (confidence: {classification.confidence:.2f})")
            
        except Exception as e:
            # Log error but don't fail - storage is optional
            logger.warning(f"Failed to store classification for {instance_id}: {e}")
            # Continue execution even if storage fails
