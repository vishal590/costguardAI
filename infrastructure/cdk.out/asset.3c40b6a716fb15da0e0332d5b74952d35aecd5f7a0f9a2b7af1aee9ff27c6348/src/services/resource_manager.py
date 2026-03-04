"""
Resource Manager for discovering and managing resources across 20+ AWS services.

Supported services:
- Compute: EC2, Lambda, ECS, EKS
- Database: RDS, DynamoDB, ElastiCache, Redshift
- Storage: EBS, S3
- Networking: NAT Gateway, Elastic IP, Load Balancers
- Application: SNS, SQS, API Gateway, Step Functions
- Analytics: Glue, SageMaker
- CDN: CloudFront
"""

from typing import List, Dict, Any
from datetime import datetime, UTC
import logging

logger = logging.getLogger(__name__)


class ResourceManager:
    """Discover and manage resources across multiple AWS services."""
    
    def __init__(self, aws_clients: Dict[str, Any], dynamodb_client):
        """
        Initialize resource manager.
        
        Args:
            aws_clients: Dict of boto3 clients by service name
            dynamodb_client: DynamoDB client for inventory storage
        """
        self.clients = aws_clients
        self.dynamodb = dynamodb_client
        self.inventory_table = "resource-inventory"
        
    def discover_resources(self, services: List[str]) -> List[Any]:
        """
        Discover all resources across specified services.
        
        Args:
            services: List of service names to discover
            
        Returns:
            List of Resource objects
        """
        logger.info(f"Discovering resources for services: {services}")
        all_resources = []
        
        for service in services:
            try:
                resources = self._discover_service_resources(service)
                all_resources.extend(resources)
                logger.info(f"Discovered {len(resources)} {service} resources")
            except Exception as e:
                logger.error(f"Failed to discover {service} resources: {e}")
                continue
        
        # Update inventory
        self.update_inventory(all_resources)
        
        return all_resources
    
    def get_resource_metadata(self, resource) -> Any:
        """
        Get detailed metadata for a resource.
        
        Args:
            resource: Resource object
            
        Returns:
            ResourceMetadata object
        """
        from ..utils.types import ResourceMetadata
        
        # Get CloudWatch metrics
        metrics = self._get_cloudwatch_metrics(resource)
        
        # Estimate cost per hour
        cost_per_hour = self._estimate_resource_cost(resource)
        
        # Get last activity timestamp
        last_activity = self._get_last_activity(resource, metrics)
        
        return ResourceMetadata(
            resource=resource,
            cost_per_hour=cost_per_hour,
            last_activity=last_activity,
            metrics=metrics
        )
    
    def update_inventory(self, resources: List[Any]) -> None:
        """
        Update resource inventory in DynamoDB.
        
        Args:
            resources: List of Resource objects
        """
        logger.info(f"Updating inventory with {len(resources)} resources")
        
        timestamp = datetime.now(UTC).isoformat()
        
        for resource in resources:
            try:
                self.dynamodb.put_item(
                    TableName=self.inventory_table,
                    Item={
                        'resource_id': {'S': resource.resource_id},
                        'timestamp': {'S': timestamp},
                        'resource_type': {'S': resource.resource_type},
                        'service': {'S': resource.service},
                        'region': {'S': resource.region},
                        'state': {'S': resource.state},
                        'tags': {'M': self._format_tags(resource.tags)},
                        'creation_date': {'S': resource.creation_date}
                    }
                )
            except Exception as e:
                logger.error(f"Failed to update inventory for {resource.resource_id}: {e}")
    
    def _discover_service_resources(self, service: str) -> List[Any]:
        """Discover resources for a specific service."""
        discovery_methods = {
            'ec2': self._discover_ec2,
            'rds': self._discover_rds,
            'lambda': self._discover_lambda,
            's3': self._discover_s3,
            'dynamodb': self._discover_dynamodb,
            'ebs': self._discover_ebs,
            'elasticache': self._discover_elasticache,
            'redshift': self._discover_redshift,
            'ecs': self._discover_ecs,
            'eks': self._discover_eks,
            'nat_gateway': self._discover_nat_gateways,
            'elastic_ip': self._discover_elastic_ips,
            'elb': self._discover_load_balancers,
            'sns': self._discover_sns,
            'sqs': self._discover_sqs,
            'apigateway': self._discover_api_gateway,
            'stepfunctions': self._discover_step_functions,
            'glue': self._discover_glue,
            'sagemaker': self._discover_sagemaker,
            'cloudfront': self._discover_cloudfront
        }
        
        method = discovery_methods.get(service)
        if method:
            return method()
        else:
            logger.warning(f"No discovery method for service: {service}")
            return []
    
    def _discover_ec2(self) -> List[Any]:
        """Discover EC2 instances."""
        from ..utils.types import Resource
        
        ec2 = self.clients.get('ec2')
        if not ec2:
            return []
        
        resources = []
        response = ec2.describe_instances()
        
        for reservation in response.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                resources.append(Resource(
                    resource_id=instance['InstanceId'],
                    resource_type='instance',
                    service='ec2',
                    region=ec2.meta.region_name,
                    tags=self._extract_tags(instance.get('Tags', [])),
                    state=instance['State']['Name'],
                    creation_date=instance['LaunchTime'].isoformat()
                ))
        
        return resources
    
    def _discover_rds(self) -> List[Any]:
        """Discover RDS instances."""
        from ..utils.types import Resource
        
        rds = self.clients.get('rds')
        if not rds:
            return []
        
        resources = []
        response = rds.describe_db_instances()
        
        for db in response.get('DBInstances', []):
            resources.append(Resource(
                resource_id=db['DBInstanceIdentifier'],
                resource_type='db_instance',
                service='rds',
                region=rds.meta.region_name,
                tags=self._extract_tags(db.get('TagList', [])),
                state=db['DBInstanceStatus'],
                creation_date=db['InstanceCreateTime'].isoformat()
            ))
        
        return resources
    
    def _discover_lambda(self) -> List[Any]:
        """Discover Lambda functions."""
        from ..utils.types import Resource
        
        lambda_client = self.clients.get('lambda')
        if not lambda_client:
            return []
        
        resources = []
        response = lambda_client.list_functions()
        
        for func in response.get('Functions', []):
            resources.append(Resource(
                resource_id=func['FunctionArn'],
                resource_type='function',
                service='lambda',
                region=lambda_client.meta.region_name,
                tags={},  # Would need separate call to get tags
                state='Active',
                creation_date=func.get('LastModified', '')
            ))
        
        return resources
    
    # Placeholder methods for other services
    def _discover_s3(self) -> List[Any]:
        """Discover S3 buckets."""
        return []
    
    def _discover_dynamodb(self) -> List[Any]:
        """Discover DynamoDB tables."""
        return []
    
    def _discover_ebs(self) -> List[Any]:
        """Discover EBS volumes."""
        return []
    
    def _discover_elasticache(self) -> List[Any]:
        """Discover ElastiCache clusters."""
        return []
    
    def _discover_redshift(self) -> List[Any]:
        """Discover Redshift clusters."""
        return []
    
    def _discover_ecs(self) -> List[Any]:
        """Discover ECS clusters."""
        return []
    
    def _discover_eks(self) -> List[Any]:
        """Discover EKS clusters."""
        return []
    
    def _discover_nat_gateways(self) -> List[Any]:
        """Discover NAT Gateways."""
        return []
    
    def _discover_elastic_ips(self) -> List[Any]:
        """Discover Elastic IPs."""
        return []
    
    def _discover_load_balancers(self) -> List[Any]:
        """Discover Load Balancers."""
        return []
    
    def _discover_sns(self) -> List[Any]:
        """Discover SNS topics."""
        return []
    
    def _discover_sqs(self) -> List[Any]:
        """Discover SQS queues."""
        return []
    
    def _discover_api_gateway(self) -> List[Any]:
        """Discover API Gateway APIs."""
        return []
    
    def _discover_step_functions(self) -> List[Any]:
        """Discover Step Functions state machines."""
        return []
    
    def _discover_glue(self) -> List[Any]:
        """Discover Glue jobs."""
        return []
    
    def _discover_sagemaker(self) -> List[Any]:
        """Discover SageMaker endpoints."""
        return []
    
    def _discover_cloudfront(self) -> List[Any]:
        """Discover CloudFront distributions."""
        return []
    
    def _get_cloudwatch_metrics(self, resource) -> Dict[str, float]:
        """Get CloudWatch metrics for a resource."""
        # Placeholder - would query CloudWatch
        return {}
    
    def _estimate_resource_cost(self, resource) -> float:
        """Estimate hourly cost for a resource."""
        # Placeholder - would use pricing data
        return 0.0
    
    def _get_last_activity(self, resource, metrics: Dict[str, float]) -> str:
        """Get last activity timestamp for a resource."""
        # Placeholder - would analyze metrics
        return datetime.now(UTC).isoformat()
    
    def _extract_tags(self, tag_list: List[Dict[str, str]]) -> Dict[str, str]:
        """Extract tags from AWS tag list format."""
        return {tag['Key']: tag['Value'] for tag in tag_list}
    
    def _format_tags(self, tags: Dict[str, str]) -> Dict[str, Dict[str, str]]:
        """Format tags for DynamoDB."""
        return {k: {'S': v} for k, v in tags.items()}
