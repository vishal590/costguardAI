"""
Idle GPU Detector for Phase 6: AI/ML Workload Cost Management.

This module identifies GPU instances with low utilization (<10%), calculates
idle time and wasted cost, and generates idle GPU alerts.

Requirements: FR-1.5
"""
import logging
from typing import List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import statistics

logger = logging.getLogger(__name__)


@dataclass
class IdleGPU:
    """Idle GPU data model."""
    instance_id: str
    instance_type: str
    utilization: float  # Average GPU utilization (0-100%)
    idle_hours: float  # Hours below idle threshold
    wasted_cost: float  # Cost during idle period
    cost_per_hour: float  # Hourly cost
    first_idle_time: str  # ISO timestamp
    last_check_time: str  # ISO timestamp
    recommendation: str  # Action recommendation
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class IdleGPUAlert:
    """Idle GPU alert data model."""
    alert_id: str
    instance_id: str
    instance_type: str
    utilization: float
    idle_hours: float
    wasted_cost: float
    severity: str  # "low", "medium", "high", "critical"
    message: str
    timestamp: str
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class IdleGPUDetector:
    """
    Identifies idle GPU instances and calculates wasted costs.
    
    Requirements: FR-1.5
    """
    
    # Default idle threshold (can be overridden)
    DEFAULT_IDLE_THRESHOLD = 10.0  # <10% utilization
    
    # Alert severity thresholds (based on wasted cost)
    SEVERITY_THRESHOLDS = {
        'low': 10.0,      # $10/day wasted
        'medium': 50.0,   # $50/day wasted
        'high': 100.0,    # $100/day wasted
        'critical': 500.0  # $500/day wasted
    }
    
    def __init__(
        self,
        dynamodb_client,
        cloudwatch_client=None,
        cost_explorer_client=None
    ):
        """
        Initialize Idle GPU Detector.
        
        Args:
            dynamodb_client: DynamoDB client for data storage
            cloudwatch_client: CloudWatch client for GPU metrics (optional)
            cost_explorer_client: Cost Explorer client for cost data (optional)
        """
        self.dynamodb = dynamodb_client
        self.cloudwatch = cloudwatch_client
        self.cost_explorer = cost_explorer_client
    
    def identify_idle_gpus(
        self,
        start_date: str,
        end_date: str,
        threshold: float = DEFAULT_IDLE_THRESHOLD
    ) -> List[IdleGPU]:
        """
        Identify GPU instances with utilization below threshold.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            threshold: Utilization threshold percentage (default: 10%)
            
        Returns:
            List of IdleGPU objects
            
        Requirements: FR-1.5
        """
        logger.info(f"Identifying idle GPUs from {start_date} to {end_date} (threshold: {threshold}%)")
        
        # Get all GPU instances
        gpu_instances = self._get_gpu_instances(start_date, end_date)
        
        idle_gpus = []
        for instance in gpu_instances:
            # Get GPU utilization metrics
            utilization_data = self._get_gpu_utilization(
                instance['instance_id'],
                start_date,
                end_date
            )
            
            if not utilization_data:
                logger.warning(f"No utilization data for {instance['instance_id']}")
                continue
            
            # Calculate average utilization
            avg_utilization = statistics.mean(utilization_data)
            
            # Check if idle
            if avg_utilization < threshold:
                # Calculate idle hours and wasted cost
                idle_hours = self._calculate_idle_hours(
                    utilization_data,
                    threshold,
                    start_date,
                    end_date
                )
                
                cost_per_hour = self._get_instance_cost_per_hour(
                    instance['instance_type']
                )
                
                wasted_cost = idle_hours * cost_per_hour
                
                # Generate recommendation
                recommendation = self._generate_recommendation(
                    avg_utilization,
                    idle_hours,
                    wasted_cost
                )
                
                idle_gpu = IdleGPU(
                    instance_id=instance['instance_id'],
                    instance_type=instance['instance_type'],
                    utilization=avg_utilization,
                    idle_hours=idle_hours,
                    wasted_cost=wasted_cost,
                    cost_per_hour=cost_per_hour,
                    first_idle_time=start_date,
                    last_check_time=datetime.utcnow().isoformat(),
                    recommendation=recommendation
                )
                
                idle_gpus.append(idle_gpu)
        
        logger.info(f"Identified {len(idle_gpus)} idle GPUs")
        return idle_gpus
    
    def calculate_idle_time(
        self,
        instance_id: str,
        start_date: str,
        end_date: str,
        threshold: float = DEFAULT_IDLE_THRESHOLD
    ) -> float:
        """
        Calculate total idle time for a GPU instance.
        
        Args:
            instance_id: EC2 instance ID
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            threshold: Utilization threshold percentage (default: 10%)
            
        Returns:
            Idle time in hours
            
        Requirements: FR-1.5
        """
        utilization_data = self._get_gpu_utilization(
            instance_id,
            start_date,
            end_date
        )
        
        if not utilization_data:
            return 0.0
        
        return self._calculate_idle_hours(
            utilization_data,
            threshold,
            start_date,
            end_date
        )
    
    def calculate_wasted_cost(
        self,
        instance_id: str,
        instance_type: str,
        start_date: str,
        end_date: str,
        threshold: float = DEFAULT_IDLE_THRESHOLD
    ) -> float:
        """
        Calculate wasted cost during idle period.
        
        Args:
            instance_id: EC2 instance ID
            instance_type: EC2 instance type
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            threshold: Utilization threshold percentage (default: 10%)
            
        Returns:
            Wasted cost in USD
            
        Requirements: FR-1.5
        """
        idle_hours = self.calculate_idle_time(
            instance_id,
            start_date,
            end_date,
            threshold
        )
        
        cost_per_hour = self._get_instance_cost_per_hour(instance_type)
        
        return idle_hours * cost_per_hour
    
    def generate_idle_alerts(
        self,
        start_date: str,
        end_date: str,
        threshold: float = DEFAULT_IDLE_THRESHOLD
    ) -> List[IdleGPUAlert]:
        """
        Generate alerts for idle GPU instances.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            threshold: Utilization threshold percentage (default: 10%)
            
        Returns:
            List of IdleGPUAlert objects
            
        Requirements: FR-1.5
        """
        logger.info(f"Generating idle GPU alerts from {start_date} to {end_date}")
        
        idle_gpus = self.identify_idle_gpus(start_date, end_date, threshold)
        
        alerts = []
        for idle_gpu in idle_gpus:
            # Determine severity based on wasted cost
            severity = self._determine_severity(idle_gpu.wasted_cost)
            
            # Generate alert message
            message = self._generate_alert_message(idle_gpu, severity)
            
            alert = IdleGPUAlert(
                alert_id=f"idle-gpu-{idle_gpu.instance_id}-{datetime.utcnow().timestamp()}",
                instance_id=idle_gpu.instance_id,
                instance_type=idle_gpu.instance_type,
                utilization=idle_gpu.utilization,
                idle_hours=idle_gpu.idle_hours,
                wasted_cost=idle_gpu.wasted_cost,
                severity=severity,
                message=message,
                timestamp=datetime.utcnow().isoformat()
            )
            
            alerts.append(alert)
        
        logger.info(f"Generated {len(alerts)} idle GPU alerts")
        return alerts
    
    def _get_gpu_instances(
        self,
        start_date: str,
        end_date: str
    ) -> List[dict]:
        """
        Get all GPU instances in the specified date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of GPU instance metadata
        """
        logger.info(f"Retrieving GPU instances from {start_date} to {end_date}")
        
        import boto3
        ec2_client = boto3.client('ec2')
        
        # GPU instance type patterns
        gpu_patterns = ['p3.', 'p4.', 'p4d.', 'p5.', 'g4.', 'g5.', 'g6.']
        
        try:
            # Get all EC2 instances
            response = ec2_client.describe_instances(
                Filters=[
                    {'Name': 'instance-state-name', 'Values': ['running', 'stopped']}
                ]
            )
            
            gpu_instances = []
            for reservation in response.get('Reservations', []):
                for instance in reservation.get('Instances', []):
                    instance_type = instance.get('InstanceType', '')
                    
                    # Filter for GPU instance types
                    if any(pattern in instance_type for pattern in gpu_patterns):
                        gpu_instances.append({
                            'instance_id': instance['InstanceId'],
                            'instance_type': instance_type,
                            'state': instance.get('State', {}).get('Name', 'unknown'),
                            'launch_time': instance.get('LaunchTime', '').isoformat() if instance.get('LaunchTime') else None
                        })
            
            logger.info(f"Found {len(gpu_instances)} GPU instances")
            return gpu_instances
            
        except Exception as e:
            logger.error(f"Error retrieving GPU instances: {e}")
            return []
    
    def _get_gpu_utilization(
        self,
        instance_id: str,
        start_date: str,
        end_date: str
    ) -> List[float]:
        """
        Get GPU utilization metrics from CloudWatch.
        
        Args:
            instance_id: EC2 instance ID
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of GPU utilization percentages
        """
        logger.info(f"Retrieving GPU utilization for {instance_id}")
        
        if not self.cloudwatch:
            import boto3
            self.cloudwatch = boto3.client('cloudwatch')
        
        try:
            from datetime import datetime
            
            # Parse dates
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            utilization_values = []
            
            # Try GPUUtilization metric first
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
                
                for datapoint in sorted(response.get('Datapoints', []), key=lambda x: x['Timestamp']):
                    utilization_values.append(float(datapoint['Average']))
                    
            except Exception as e:
                logger.warning(f"GPUUtilization metric not available for {instance_id}: {e}")
                # Fallback to CPUUtilization
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
            
            logger.info(f"Retrieved {len(utilization_values)} utilization data points for {instance_id}")
            return utilization_values
            
        except Exception as e:
            logger.error(f"Error retrieving GPU utilization for {instance_id}: {e}")
            return []
    
    def _calculate_idle_hours(
        self,
        utilization_data: List[float],
        threshold: float,
        start_date: str,
        end_date: str
    ) -> float:
        """
        Calculate total idle hours based on utilization data.
        
        Args:
            utilization_data: List of GPU utilization percentages
            threshold: Utilization threshold percentage
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            Idle hours
        """
        if not utilization_data:
            return 0.0
        
        # Count data points below threshold
        idle_points = sum(1 for util in utilization_data if util < threshold)
        
        # Calculate time range in hours
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        total_hours = (end - start).total_seconds() / 3600
        
        # Calculate idle hours (proportional to idle points)
        idle_ratio = idle_points / len(utilization_data)
        idle_hours = total_hours * idle_ratio
        
        return idle_hours
    
    def _get_instance_cost_per_hour(self, instance_type: str) -> float:
        """
        Get hourly cost for an instance type.
        
        Args:
            instance_type: EC2 instance type
            
        Returns:
            Cost per hour in USD
        """
        # TODO: Implement Pricing API integration
        # For now, use approximate costs for common GPU instances
        approximate_costs = {
            'p3.2xlarge': 3.06,
            'p3.8xlarge': 12.24,
            'p3.16xlarge': 24.48,
            'p4d.24xlarge': 32.77,
            'p5.48xlarge': 98.32,
            'g4dn.xlarge': 0.526,
            'g4dn.2xlarge': 0.752,
            'g4dn.4xlarge': 1.204,
            'g4dn.8xlarge': 2.176,
            'g4dn.12xlarge': 3.912,
            'g4dn.16xlarge': 4.352,
            'g5.xlarge': 1.006,
            'g5.2xlarge': 1.212,
            'g5.4xlarge': 1.624,
            'g5.8xlarge': 2.448,
            'g5.12xlarge': 5.672,
            'g5.16xlarge': 4.896,
            'g5.24xlarge': 8.144,
            'g5.48xlarge': 16.288,
        }
        
        return approximate_costs.get(instance_type, 5.0)  # Default $5/hour
    
    def _generate_recommendation(
        self,
        avg_utilization: float,
        idle_hours: float,
        wasted_cost: float
    ) -> str:
        """
        Generate action recommendation based on idle metrics.
        
        Args:
            avg_utilization: Average GPU utilization
            idle_hours: Total idle hours
            wasted_cost: Wasted cost in USD
            
        Returns:
            Recommendation string
        """
        if avg_utilization < 5.0:
            return "STOP: GPU is nearly unused. Consider stopping or terminating this instance."
        elif avg_utilization < 10.0 and wasted_cost > 100.0:
            return "STOP: GPU is idle and wasting significant cost. Stop instance when not in use."
        elif avg_utilization < 10.0:
            return "REVIEW: GPU utilization is low. Consider stopping when not actively training/inferencing."
        else:
            return "MONITOR: GPU utilization is borderline. Continue monitoring."
    
    def _determine_severity(self, wasted_cost: float) -> str:
        """
        Determine alert severity based on wasted cost.
        
        Args:
            wasted_cost: Wasted cost in USD
            
        Returns:
            Severity level: "low", "medium", "high", "critical"
        """
        if wasted_cost >= self.SEVERITY_THRESHOLDS['critical']:
            return 'critical'
        elif wasted_cost >= self.SEVERITY_THRESHOLDS['high']:
            return 'high'
        elif wasted_cost >= self.SEVERITY_THRESHOLDS['medium']:
            return 'medium'
        else:
            return 'low'
    
    def _generate_alert_message(
        self,
        idle_gpu: IdleGPU,
        severity: str
    ) -> str:
        """
        Generate alert message for idle GPU.
        
        Args:
            idle_gpu: IdleGPU object
            severity: Alert severity level
            
        Returns:
            Alert message string
        """
        return (
            f"{severity.upper()} ALERT: GPU instance {idle_gpu.instance_id} "
            f"({idle_gpu.instance_type}) has been idle for {idle_gpu.idle_hours:.1f} hours "
            f"with {idle_gpu.utilization:.1f}% average utilization. "
            f"Wasted cost: ${idle_gpu.wasted_cost:.2f}. "
            f"Recommendation: {idle_gpu.recommendation}"
        )
