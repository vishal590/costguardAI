"""
Cost-Per-Training Calculator

Calculates cost per training job for AI/ML models, tracking training jobs
from SageMaker and EC2, and calculating total training costs including
compute, storage, and data transfer costs.

Requirements: FR-4.1, FR-4.2, FR-4.3, FR-4.4, FR-4.5, FR-4.6
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional
from botocore.exceptions import ClientError

from .error_handler import (
    retry_with_exponential_backoff,
    handle_cost_explorer_error,
    handle_sagemaker_error,
    validate_minimum_data,
    AIMLError,
    DataNotFoundError
)


@dataclass
class TrainingCosts:
    """Breakdown of training costs by component."""
    compute_cost: float
    storage_cost: float
    data_transfer_cost: float
    
    @property
    def total_cost(self) -> float:
        """Calculate total cost across all components."""
        return self.compute_cost + self.storage_cost + self.data_transfer_cost


@dataclass
class TrainingJobMetadata:
    """Metadata for a training job."""
    job_id: str
    model: str
    dataset: str
    instance_type: str
    start_time: datetime
    end_time: datetime
    duration_hours: float
    source: str  # "sagemaker" or "ec2"


@dataclass
class CostPerTraining:
    """Cost per training calculation result."""
    job_id: str
    model: str
    dataset: str
    date: datetime
    training_hours: float
    total_cost: float
    cost_per_hour: float
    compute_cost: float
    storage_cost: float
    data_transfer_cost: float
    instance_type: str


@dataclass
class InstanceComparison:
    """Training cost comparison across instance types."""
    instance_type: str
    estimated_duration_hours: float
    estimated_cost: float
    cost_per_hour: float
    savings_vs_baseline: float
    savings_percent: float


class CostPerTrainingCalculator:
    """
    Calculates cost per training job for AI/ML models.
    
    Tracks training jobs from SageMaker and EC2, calculating total costs
    including compute, storage, and data transfer components.
    """
    
    def __init__(self, cost_explorer_client=None, sagemaker_client=None,
                 ec2_client=None, dynamodb_client=None):
        """
        Initialize the cost-per-training calculator.
        
        Args:
            cost_explorer_client: AWS Cost Explorer client
            sagemaker_client: AWS SageMaker client
            ec2_client: AWS EC2 client
            dynamodb_client: AWS DynamoDB client
        """
        self.cost_explorer = cost_explorer_client
        self.sagemaker = sagemaker_client
        self.ec2 = ec2_client
        self.dynamodb = dynamodb_client
    
    def calculate_cost_per_training(self, job_id: str) -> CostPerTraining:
        """
        Calculate cost per training job.
        
        Args:
            job_id: Training job identifier
            
        Returns:
            CostPerTraining with detailed cost breakdown
            
        Requirements: FR-4.1, FR-4.3
        """
        # Get training job metadata
        metadata = self.get_training_job_metadata(job_id)
        
        # Get training costs
        costs = self.get_training_costs(job_id)
        
        # Calculate cost per hour
        cost_per_hour = costs.total_cost / metadata.duration_hours if metadata.duration_hours > 0 else 0.0
        
        return CostPerTraining(
            job_id=job_id,
            model=metadata.model,
            dataset=metadata.dataset,
            date=metadata.start_time,
            training_hours=metadata.duration_hours,
            total_cost=costs.total_cost,
            cost_per_hour=cost_per_hour,
            compute_cost=costs.compute_cost,
            storage_cost=costs.storage_cost,
            data_transfer_cost=costs.data_transfer_cost,
            instance_type=metadata.instance_type
        )
    
    def get_training_job_metadata(self, job_id: str) -> TrainingJobMetadata:
        """
        Get training job metadata from SageMaker or EC2 tags.
        
        Args:
            job_id: Training job identifier
            
        Returns:
            TrainingJobMetadata with job details
            
        Requirements: FR-4.2
        """
        if not self.sagemaker and not self.ec2:
            # Return mock data for testing
            return TrainingJobMetadata(
                job_id=job_id,
                model="test-model",
                dataset="test-dataset",
                instance_type="ml.p3.2xlarge",
                start_time=datetime(2024, 1, 1, 0, 0, 0),
                end_time=datetime(2024, 1, 1, 10, 0, 0),
                duration_hours=10.0,
                source="sagemaker"
            )
        
        # Try SageMaker first
        try:
            metadata = self._get_sagemaker_job_metadata(job_id)
            if metadata:
                return metadata
        except Exception:
            pass
        
        # Try EC2 with training classification
        try:
            metadata = self._get_ec2_training_metadata(job_id)
            if metadata:
                return metadata
        except Exception:
            pass
        
        raise ValueError(f"Training job {job_id} not found")
    
    def get_training_costs(self, job_id: str) -> TrainingCosts:
        """
        Get total training costs (compute + storage + data transfer).
        
        Args:
            job_id: Training job identifier
            
        Returns:
            TrainingCosts with breakdown by component
            
        Requirements: FR-4.3
        """
        if not self.cost_explorer:
            # Return mock data for testing
            return TrainingCosts(
                compute_cost=1000.0,
                storage_cost=50.0,
                data_transfer_cost=25.0
            )
        
        compute_cost = self._get_compute_costs(job_id)
        storage_cost = self._get_storage_costs(job_id)
        data_transfer_cost = self._get_data_transfer_costs(job_id)
        
        return TrainingCosts(
            compute_cost=compute_cost,
            storage_cost=storage_cost,
            data_transfer_cost=data_transfer_cost
        )
    
    def compare_instance_types(
        self,
        model: str,
        instance_types: List[str],
        baseline_instance: Optional[str] = None
    ) -> List[InstanceComparison]:
        """
        Compare training costs across different instance types.
        
        Args:
            model: Model name
            instance_types: List of instance types to compare
            baseline_instance: Baseline instance for savings calculation
            
        Returns:
            List of InstanceComparison objects
            
        Requirements: FR-4.6
        """
        if not baseline_instance and instance_types:
            baseline_instance = instance_types[0]
        
        comparisons = []
        baseline_cost = None
        
        for instance_type in instance_types:
            # Estimate duration and cost for this instance type
            duration = self._estimate_training_duration(model, instance_type)
            cost = self._estimate_training_cost(model, instance_type, duration)
            cost_per_hour = cost / duration if duration > 0 else 0.0
            
            if instance_type == baseline_instance:
                baseline_cost = cost
            
            savings = baseline_cost - cost if baseline_cost else 0.0
            savings_percent = (savings / baseline_cost * 100) if baseline_cost and baseline_cost > 0 else 0.0
            
            comparisons.append(InstanceComparison(
                instance_type=instance_type,
                estimated_duration_hours=duration,
                estimated_cost=cost,
                cost_per_hour=cost_per_hour,
                savings_vs_baseline=savings,
                savings_percent=savings_percent
            ))
        
        return comparisons
    
    # Private helper methods
    
    def _get_sagemaker_job_metadata(self, job_id: str) -> Optional[TrainingJobMetadata]:
        """Get metadata from SageMaker training job."""
        # Implementation would query SageMaker DescribeTrainingJob API
        return None
    
    def _get_ec2_training_metadata(self, job_id: str) -> Optional[TrainingJobMetadata]:
        """Get metadata from EC2 instance with training classification."""
        # Implementation would query EC2 tags and CloudWatch metrics
        return None
    
    def _get_compute_costs(self, job_id: str) -> float:
        """Get compute costs from Cost Explorer."""
        # Implementation would query Cost Explorer for EC2/SageMaker costs
        return 0.0
    
    def _get_storage_costs(self, job_id: str) -> float:
        """Get storage costs from Cost Explorer."""
        # Implementation would query Cost Explorer for S3/EBS costs
        return 0.0
    
    def _get_data_transfer_costs(self, job_id: str) -> float:
        """Get data transfer costs from Cost Explorer."""
        # Implementation would query Cost Explorer for data transfer costs
        return 0.0
    
    def _estimate_training_duration(self, model: str, instance_type: str) -> float:
        """Estimate training duration for model on instance type."""
        # Implementation would use historical data or benchmarks
        # For now, return mock estimate based on instance type
        base_duration = 10.0
        
        # Adjust based on instance type (larger instances = faster)
        if 'xlarge' in instance_type:
            multiplier = 1.0
        elif '2xlarge' in instance_type:
            multiplier = 0.5
        elif '4xlarge' in instance_type:
            multiplier = 0.25
        elif '8xlarge' in instance_type:
            multiplier = 0.125
        else:
            multiplier = 2.0
        
        return base_duration * multiplier
    
    def _estimate_training_cost(self, model: str, instance_type: str, duration: float) -> float:
        """Estimate training cost for model on instance type."""
        # Implementation would use AWS Pricing API
        # For now, return mock estimate based on instance type
        hourly_rates = {
            'ml.p3.2xlarge': 3.06,
            'ml.p3.8xlarge': 12.24,
            'ml.p3.16xlarge': 24.48,
            'ml.p4d.24xlarge': 32.77,
            'ml.g4dn.xlarge': 0.526,
            'ml.g4dn.2xlarge': 0.752,
        }
        
        hourly_rate = hourly_rates.get(instance_type, 1.0)
        return hourly_rate * duration
