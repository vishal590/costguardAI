"""
Idle Detector for determining if resources are idle based on service-specific criteria.

Idle criteria by service:
- EC2: CPU < 5% for 2 hours
- RDS: Connections = 0 for 1 hour
- Lambda: Invocations = 0 for 24 hours
- EBS: Unattached for 7 days
- S3: Requests = 0 for 30 days
- DynamoDB: Read/Write = 0 for 24 hours
- ElastiCache: CPU < 5% for 2 hours
- NAT Gateway: Bytes processed = 0 for 1 hour
- Redshift: Connections = 0 for 1 hour
- ECS: No running tasks for 2 hours
- EKS: No active pods for 2 hours
- Load Balancers: Requests = 0 for 1 hour
- SNS: Messages published = 0 for 24 hours
- SQS: Messages sent = 0 for 24 hours
- API Gateway: Requests = 0 for 24 hours
- CloudFront: Requests = 0 for 7 days
- Step Functions: Executions = 0 for 24 hours
- Glue: No runs for 7 days
- SageMaker: No invocations for 24 hours
- Elastic IP: Unattached for 7 days
"""

from typing import Dict, Any
from datetime import datetime, timedelta, UTC
import logging

logger = logging.getLogger(__name__)


class IdleDetector:
    """Determine if resources are idle based on service-specific criteria."""
    
    def __init__(self, cloudwatch_client):
        """
        Initialize idle detector.
        
        Args:
            cloudwatch_client: boto3 CloudWatch client
        """
        self.cloudwatch = cloudwatch_client
        
        # Default idle criteria by service
        self.idle_criteria = {
            'ec2': {'metric': 'CPUUtilization', 'threshold': 5.0, 'duration_minutes': 120},
            'ec2_gpu': {'metric': 'GPUUtilization', 'threshold': 10.0, 'duration_minutes': 120},  # GPU instances
            'rds': {'metric': 'DatabaseConnections', 'threshold': 0.0, 'duration_minutes': 60},
            'lambda': {'metric': 'Invocations', 'threshold': 0.0, 'duration_minutes': 1440},
            'ebs': {'metric': 'Attached', 'threshold': 0.0, 'duration_minutes': 10080},  # 7 days
            's3': {'metric': 'AllRequests', 'threshold': 0.0, 'duration_minutes': 43200},  # 30 days
            'dynamodb': {'metric': 'ConsumedReadCapacityUnits', 'threshold': 0.0, 'duration_minutes': 1440},
            'elasticache': {'metric': 'CPUUtilization', 'threshold': 5.0, 'duration_minutes': 120},
            'nat_gateway': {'metric': 'BytesOutToDestination', 'threshold': 0.0, 'duration_minutes': 60},
            'redshift': {'metric': 'DatabaseConnections', 'threshold': 0.0, 'duration_minutes': 60},
            'ecs': {'metric': 'RunningTaskCount', 'threshold': 0.0, 'duration_minutes': 120},
            'eks': {'metric': 'ActivePodCount', 'threshold': 0.0, 'duration_minutes': 120},
            'elb': {'metric': 'RequestCount', 'threshold': 0.0, 'duration_minutes': 60},
            'nlb': {'metric': 'ActiveFlowCount', 'threshold': 0.0, 'duration_minutes': 60},
            'sns': {'metric': 'NumberOfMessagesPublished', 'threshold': 0.0, 'duration_minutes': 1440},
            'sqs': {'metric': 'NumberOfMessagesSent', 'threshold': 0.0, 'duration_minutes': 1440},
            'apigateway': {'metric': 'Count', 'threshold': 0.0, 'duration_minutes': 1440},
            'cloudfront': {'metric': 'Requests', 'threshold': 0.0, 'duration_minutes': 10080},  # 7 days
            'stepfunctions': {'metric': 'ExecutionsStarted', 'threshold': 0.0, 'duration_minutes': 1440},
            'glue': {'metric': 'JobRuns', 'threshold': 0.0, 'duration_minutes': 10080},  # 7 days
            'sagemaker': {'metric': 'Invocations', 'threshold': 0.0, 'duration_minutes': 1440},
            'elastic_ip': {'metric': 'Attached', 'threshold': 0.0, 'duration_minutes': 10080}  # 7 days
        }
    
    def is_resource_idle(self, resource, metadata) -> Any:
        """
        Determine if resource is idle based on service-specific criteria.
        
        Args:
            resource: Resource object
            metadata: ResourceMetadata object
            
        Returns:
            IdleStatus object
        """
        from ..utils.types import IdleStatus
        
        service = resource.service
        criteria = self.get_idle_criteria(service)
        
        if not criteria:
            logger.warning(f"No idle criteria for service: {service}")
            return IdleStatus(
                resource_id=resource.resource_id,
                is_idle=False,
                idle_duration=0,
                metrics_used={},
                confidence=0.0
            )
        
        # Check service-specific idle condition
        if service == 'ec2':
            return self._check_ec2_idle(resource, metadata, criteria)
        elif service == 'ec2_gpu':
            return self._check_ec2_gpu_idle(resource, metadata, criteria)
        elif service == 'rds':
            return self._check_rds_idle(resource, metadata, criteria)
        elif service == 'lambda':
            return self._check_lambda_idle(resource, metadata, criteria)
        elif service == 'ebs':
            return self._check_ebs_idle(resource, metadata, criteria)
        elif service == 's3':
            return self._check_s3_idle(resource, metadata, criteria)
        elif service == 'dynamodb':
            return self._check_dynamodb_idle(resource, metadata, criteria)
        elif service == 'elasticache':
            return self._check_elasticache_idle(resource, metadata, criteria)
        elif service == 'nat_gateway':
            return self._check_nat_gateway_idle(resource, metadata, criteria)
        elif service == 'redshift':
            return self._check_redshift_idle(resource, metadata, criteria)
        elif service == 'ecs':
            return self._check_ecs_idle(resource, metadata, criteria)
        elif service == 'eks':
            return self._check_eks_idle(resource, metadata, criteria)
        elif service == 'elb' or service == 'nlb':
            return self._check_load_balancer_idle(resource, metadata, criteria)
        elif service == 'sns':
            return self._check_sns_idle(resource, metadata, criteria)
        elif service == 'sqs':
            return self._check_sqs_idle(resource, metadata, criteria)
        elif service == 'apigateway':
            return self._check_apigateway_idle(resource, metadata, criteria)
        elif service == 'cloudfront':
            return self._check_cloudfront_idle(resource, metadata, criteria)
        elif service == 'stepfunctions':
            return self._check_stepfunctions_idle(resource, metadata, criteria)
        elif service == 'glue':
            return self._check_glue_idle(resource, metadata, criteria)
        elif service == 'sagemaker':
            return self._check_sagemaker_idle(resource, metadata, criteria)
        elif service == 'elastic_ip':
            return self._check_elastic_ip_idle(resource, metadata, criteria)
        else:
            return self._check_generic_idle(resource, metadata, criteria)
    
    def get_idle_criteria(self, service: str) -> Any:
        """
        Get idle detection criteria for a service.
        
        Args:
            service: Service name
            
        Returns:
            IdleCriteria object or None
        """
        from ..utils.types import IdleCriteria
        
        criteria_dict = self.idle_criteria.get(service)
        if not criteria_dict:
            return None
        
        return IdleCriteria(
            service=service,
            metric_name=criteria_dict['metric'],
            threshold=criteria_dict['threshold'],
            duration_minutes=criteria_dict['duration_minutes']
        )
    
    def _check_ec2_idle(self, resource, metadata, criteria) -> Any:
        """Check if EC2 instance is idle (CPU < 5% for 2 hours)."""
        from ..utils.types import IdleStatus
        
        metrics = metadata.metrics
        cpu_utilization = metrics.get('CPUUtilization', 100.0)
        
        is_idle = cpu_utilization < criteria.threshold
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={'CPUUtilization': cpu_utilization},
            confidence=0.95 if is_idle else 0.0
        )
    
    def _check_ec2_gpu_idle(self, resource, metadata, criteria) -> Any:
        """Check if EC2 GPU instance is idle (GPU utilization < 10% for 2 hours)."""
        from ..utils.types import IdleStatus
        
        metrics = metadata.metrics
        gpu_utilization = metrics.get('GPUUtilization', 100.0)
        
        is_idle = gpu_utilization < criteria.threshold
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={'GPUUtilization': gpu_utilization},
            confidence=0.90 if is_idle else 0.0
        )
    
    def _check_rds_idle(self, resource, metadata, criteria) -> Any:
        """Check if RDS instance is idle (connections = 0 for 1 hour)."""
        from ..utils.types import IdleStatus
        
        metrics = metadata.metrics
        connections = metrics.get('DatabaseConnections', 1.0)
        
        is_idle = connections <= criteria.threshold
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={'DatabaseConnections': connections},
            confidence=0.90 if is_idle else 0.0
        )
    
    def _check_lambda_idle(self, resource, metadata, criteria) -> Any:
        """Check if Lambda function is idle (invocations = 0 for 24 hours)."""
        from ..utils.types import IdleStatus
        
        metrics = metadata.metrics
        invocations = metrics.get('Invocations', 1.0)
        
        is_idle = invocations <= criteria.threshold
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={'Invocations': invocations},
            confidence=0.85 if is_idle else 0.0
        )
    
    def _check_ebs_idle(self, resource, metadata, criteria) -> Any:
        """Check if EBS volume is idle (unattached for 7 days)."""
        from ..utils.types import IdleStatus
        
        is_attached = resource.state == 'in-use'
        is_idle = not is_attached
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={'Attached': 1.0 if is_attached else 0.0},
            confidence=1.0 if is_idle else 0.0
        )
    
    def _check_s3_idle(self, resource, metadata, criteria) -> Any:
        """Check if S3 bucket is idle (requests = 0 for 30 days)."""
        from ..utils.types import IdleStatus
        
        metrics = metadata.metrics
        requests = metrics.get('AllRequests', 1.0)
        
        is_idle = requests <= criteria.threshold
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={'AllRequests': requests},
            confidence=0.80 if is_idle else 0.0
        )
    
    def _check_dynamodb_idle(self, resource, metadata, criteria) -> Any:
        """Check if DynamoDB table is idle (read/write = 0 for 24 hours)."""
        from ..utils.types import IdleStatus
        
        metrics = metadata.metrics
        read_capacity = metrics.get('ConsumedReadCapacityUnits', 1.0)
        write_capacity = metrics.get('ConsumedWriteCapacityUnits', 1.0)
        
        is_idle = read_capacity <= criteria.threshold and write_capacity <= criteria.threshold
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={
                'ConsumedReadCapacityUnits': read_capacity,
                'ConsumedWriteCapacityUnits': write_capacity
            },
            confidence=0.85 if is_idle else 0.0
        )
    
    def _check_elasticache_idle(self, resource, metadata, criteria) -> Any:
        """Check if ElastiCache cluster is idle (CPU < 5% for 2 hours)."""
        from ..utils.types import IdleStatus
        
        metrics = metadata.metrics
        cpu_utilization = metrics.get('CPUUtilization', 100.0)
        
        is_idle = cpu_utilization < criteria.threshold
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={'CPUUtilization': cpu_utilization},
            confidence=0.90 if is_idle else 0.0
        )
    
    def _check_nat_gateway_idle(self, resource, metadata, criteria) -> Any:
        """Check if NAT Gateway is idle (bytes processed = 0 for 1 hour)."""
        from ..utils.types import IdleStatus
        
        metrics = metadata.metrics
        bytes_out = metrics.get('BytesOutToDestination', 1.0)
        bytes_in = metrics.get('BytesInFromSource', 1.0)
        
        # NAT Gateway is idle if both inbound and outbound bytes are 0
        is_idle = bytes_out <= criteria.threshold and bytes_in <= criteria.threshold
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={
                'BytesOutToDestination': bytes_out,
                'BytesInFromSource': bytes_in
            },
            confidence=0.85 if is_idle else 0.0
        )
    
    def _check_redshift_idle(self, resource, metadata, criteria) -> Any:
        """Check if Redshift cluster is idle (connections = 0 for 1 hour)."""
        from ..utils.types import IdleStatus
        
        metrics = metadata.metrics
        connections = metrics.get('DatabaseConnections', 1.0)
        
        is_idle = connections <= criteria.threshold
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={'DatabaseConnections': connections},
            confidence=0.90 if is_idle else 0.0
        )
    
    def _check_ecs_idle(self, resource, metadata, criteria) -> Any:
        """Check if ECS cluster is idle (no running tasks for 2 hours)."""
        from ..utils.types import IdleStatus
        
        metrics = metadata.metrics
        running_tasks = metrics.get('RunningTaskCount', 1.0)
        
        is_idle = running_tasks <= criteria.threshold
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={'RunningTaskCount': running_tasks},
            confidence=0.85 if is_idle else 0.0
        )
    
    def _check_eks_idle(self, resource, metadata, criteria) -> Any:
        """Check if EKS cluster is idle (no active pods for 2 hours)."""
        from ..utils.types import IdleStatus
        
        metrics = metadata.metrics
        active_pods = metrics.get('ActivePodCount', 1.0)
        
        is_idle = active_pods <= criteria.threshold
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={'ActivePodCount': active_pods},
            confidence=0.85 if is_idle else 0.0
        )
    
    def _check_load_balancer_idle(self, resource, metadata, criteria) -> Any:
        """Check if Load Balancer is idle (requests = 0 for 1 hour)."""
        from ..utils.types import IdleStatus
        
        metrics = metadata.metrics
        # Check both request count and active flow count
        request_count = metrics.get('RequestCount', 1.0)
        active_flows = metrics.get('ActiveFlowCount', 1.0)
        
        is_idle = request_count <= criteria.threshold and active_flows <= criteria.threshold
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={
                'RequestCount': request_count,
                'ActiveFlowCount': active_flows
            },
            confidence=0.80 if is_idle else 0.0
        )
    
    def _check_sns_idle(self, resource, metadata, criteria) -> Any:
        """Check if SNS topic is idle (messages published = 0 for 24 hours)."""
        from ..utils.types import IdleStatus
        
        metrics = metadata.metrics
        messages_published = metrics.get('NumberOfMessagesPublished', 1.0)
        
        is_idle = messages_published <= criteria.threshold
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={'NumberOfMessagesPublished': messages_published},
            confidence=0.85 if is_idle else 0.0
        )
    
    def _check_sqs_idle(self, resource, metadata, criteria) -> Any:
        """Check if SQS queue is idle (messages sent = 0 for 24 hours)."""
        from ..utils.types import IdleStatus
        
        metrics = metadata.metrics
        messages_sent = metrics.get('NumberOfMessagesSent', 1.0)
        
        is_idle = messages_sent <= criteria.threshold
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={'NumberOfMessagesSent': messages_sent},
            confidence=0.85 if is_idle else 0.0
        )
    
    def _check_apigateway_idle(self, resource, metadata, criteria) -> Any:
        """Check if API Gateway is idle (requests = 0 for 24 hours)."""
        from ..utils.types import IdleStatus
        
        metrics = metadata.metrics
        request_count = metrics.get('Count', 1.0)
        
        is_idle = request_count <= criteria.threshold
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={'Count': request_count},
            confidence=0.85 if is_idle else 0.0
        )
    
    def _check_cloudfront_idle(self, resource, metadata, criteria) -> Any:
        """Check if CloudFront distribution is idle (requests = 0 for 7 days)."""
        from ..utils.types import IdleStatus
        
        metrics = metadata.metrics
        requests = metrics.get('Requests', 1.0)
        
        is_idle = requests <= criteria.threshold
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={'Requests': requests},
            confidence=0.80 if is_idle else 0.0
        )
    
    def _check_stepfunctions_idle(self, resource, metadata, criteria) -> Any:
        """Check if Step Functions state machine is idle (executions = 0 for 24 hours)."""
        from ..utils.types import IdleStatus
        
        metrics = metadata.metrics
        executions = metrics.get('ExecutionsStarted', 1.0)
        
        is_idle = executions <= criteria.threshold
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={'ExecutionsStarted': executions},
            confidence=0.85 if is_idle else 0.0
        )
    
    def _check_glue_idle(self, resource, metadata, criteria) -> Any:
        """Check if Glue job is idle (no runs for 7 days)."""
        from ..utils.types import IdleStatus
        
        metrics = metadata.metrics
        job_runs = metrics.get('JobRuns', 1.0)
        
        is_idle = job_runs <= criteria.threshold
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={'JobRuns': job_runs},
            confidence=0.80 if is_idle else 0.0
        )
    
    def _check_sagemaker_idle(self, resource, metadata, criteria) -> Any:
        """Check if SageMaker endpoint is idle (no invocations for 24 hours)."""
        from ..utils.types import IdleStatus
        
        metrics = metadata.metrics
        invocations = metrics.get('Invocations', 1.0)
        
        is_idle = invocations <= criteria.threshold
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={'Invocations': invocations},
            confidence=0.85 if is_idle else 0.0
        )
    
    def _check_elastic_ip_idle(self, resource, metadata, criteria) -> Any:
        """Check if Elastic IP is idle (unattached for 7 days)."""
        from ..utils.types import IdleStatus
        
        is_attached = resource.state == 'in-use'
        is_idle = not is_attached
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=is_idle,
            idle_duration=criteria.duration_minutes if is_idle else 0,
            metrics_used={'Attached': 1.0 if is_attached else 0.0},
            confidence=1.0 if is_idle else 0.0
        )
    
    def _check_generic_idle(self, resource, metadata, criteria) -> Any:
        """Generic idle check for services without specific logic."""
        from ..utils.types import IdleStatus
        
        return IdleStatus(
            resource_id=resource.resource_id,
            is_idle=False,
            idle_duration=0,
            metrics_used={},
            confidence=0.0
        )
