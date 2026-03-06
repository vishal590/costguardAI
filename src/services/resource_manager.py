"""
Resource Manager for discovering and managing resources across 22 AWS services.

Supported services:
- Compute: EC2, Lambda, ECS, EKS
- Database: RDS, DynamoDB, ElastiCache, Redshift
- Storage: EBS, S3
- Networking: NAT Gateway, Elastic IP, Load Balancers (ALB/NLB/ELB)
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
            'alb': self._discover_load_balancers,  # Application Load Balancer
            'nlb': self._discover_load_balancers,  # Network Load Balancer
            'sns': self._discover_sns,
            'sqs': self._discover_sqs,
            'apigateway': self._discover_api_gateway,
            'api_gateway': self._discover_api_gateway,  # Support both naming conventions
            'stepfunctions': self._discover_step_functions,
            'step_functions': self._discover_step_functions,  # Support both naming conventions
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
        from ..utils.types import Resource
        
        s3 = self.clients.get('s3')
        if not s3:
            return []
        
        resources = []
        try:
            # List all buckets
            response = s3.list_buckets()
            
            for bucket in response.get('Buckets', []):
                bucket_name = bucket['Name']
                creation_date = bucket.get('CreationDate', datetime.now(UTC))
                
                # Get bucket location (region)
                try:
                    location_response = s3.get_bucket_location(Bucket=bucket_name)
                    region = location_response.get('LocationConstraint', 'us-east-1')
                    # us-east-1 returns None, so default to us-east-1
                    if not region:
                        region = 'us-east-1'
                except Exception:
                    # Default to us-east-1 if location cannot be determined
                    region = 'us-east-1'
                
                # Get bucket tags
                tags = {}
                try:
                    tag_response = s3.get_bucket_tagging(Bucket=bucket_name)
                    tags = self._extract_tags(tag_response.get('TagSet', []))
                except Exception:
                    # Bucket may not have tags or tagging may not be allowed
                    pass
                
                # Check if bucket exists and is accessible
                try:
                    s3.head_bucket(Bucket=bucket_name)
                    state = 'Active'
                except Exception:
                    state = 'Inaccessible'
                
                resources.append(Resource(
                    resource_id=bucket_name,
                    resource_type='bucket',
                    service='s3',
                    region=region,
                    tags=tags,
                    state=state,
                    creation_date=creation_date.isoformat() if isinstance(creation_date, datetime) else creation_date
                ))
        except Exception as e:
            logger.error(f"Error discovering S3 buckets: {e}")
        
        return resources
    
    def _discover_dynamodb(self) -> List[Any]:
        """Discover DynamoDB tables."""
        from ..utils.types import Resource
        
        dynamodb = self.clients.get('dynamodb')
        if not dynamodb:
            return []
        
        resources = []
        try:
            # List all tables
            paginator = dynamodb.get_paginator('list_tables')
            
            for page in paginator.paginate():
                for table_name in page.get('TableNames', []):
                    try:
                        # Get table details
                        table_response = dynamodb.describe_table(TableName=table_name)
                        table = table_response.get('Table', {})
                        
                        # Get table tags
                        tags = {}
                        try:
                            tag_response = dynamodb.list_tags_of_resource(
                                ResourceArn=table.get('TableArn', '')
                            )
                            tags = self._extract_tags(tag_response.get('Tags', []))
                        except Exception:
                            pass
                        
                        creation_date = table.get('CreationDateTime', datetime.now(UTC))
                        
                        resources.append(Resource(
                            resource_id=table_name,
                            resource_type='table',
                            service='dynamodb',
                            region=dynamodb.meta.region_name,
                            tags=tags,
                            state=table.get('TableStatus', 'UNKNOWN'),
                            creation_date=creation_date.isoformat() if isinstance(creation_date, datetime) else creation_date
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to describe DynamoDB table {table_name}: {e}")
                        continue
        except Exception as e:
            logger.error(f"Error discovering DynamoDB tables: {e}")
        
        return resources
    
    def _discover_ebs(self) -> List[Any]:
        """Discover EBS volumes."""
        from ..utils.types import Resource
        
        ec2 = self.clients.get('ec2')
        if not ec2:
            return []
        
        resources = []
        try:
            response = ec2.describe_volumes()
            
            for volume in response.get('Volumes', []):
                resources.append(Resource(
                    resource_id=volume['VolumeId'],
                    resource_type='volume',
                    service='ebs',
                    region=ec2.meta.region_name,
                    tags=self._extract_tags(volume.get('Tags', [])),
                    state=volume.get('State', 'unknown'),
                    creation_date=volume.get('CreateTime', datetime.now(UTC)).isoformat() if isinstance(volume.get('CreateTime'), datetime) else volume.get('CreateTime', datetime.now(UTC).isoformat())
                ))
        except Exception as e:
            logger.error(f"Error discovering EBS volumes: {e}")
        
        return resources
    
    def _discover_elasticache(self) -> List[Any]:
        """Discover ElastiCache clusters."""
        from ..utils.types import Resource
        
        elasticache = self.clients.get('elasticache')
        if not elasticache:
            return []
        
        resources = []
        try:
            # List all cache clusters
            paginator = elasticache.get_paginator('describe_cache_clusters')
            
            for page in paginator.paginate(ShowCacheNodeInfo=False):
                for cluster in page.get('CacheClusters', []):
                    cluster_id = cluster.get('CacheClusterId', '')
                    
                    # Get cluster tags
                    tags = {}
                    try:
                        # Try using ARN from cluster response
                        cluster_arn = cluster.get('ARN', '')
                        if cluster_arn:
                            tag_response = elasticache.list_tags_for_resource(
                                ResourceName=cluster_arn
                            )
                            tags = self._extract_tags(tag_response.get('TagList', []))
                    except Exception:
                        # Tags may not be available or resource may not support tagging
                        pass
                    
                    creation_date = cluster.get('CacheClusterCreateTime', datetime.now(UTC))
                    
                    resources.append(Resource(
                        resource_id=cluster_id,
                        resource_type='cache_cluster',
                        service='elasticache',
                        region=elasticache.meta.region_name,
                        tags=tags,
                        state=cluster.get('CacheClusterStatus', 'unknown'),
                        creation_date=creation_date.isoformat() if isinstance(creation_date, datetime) else creation_date
                    ))
        except Exception as e:
            logger.error(f"Error discovering ElastiCache clusters: {e}")
        
        return resources
    
    def _discover_redshift(self) -> List[Any]:
        """Discover Redshift clusters."""
        from ..utils.types import Resource
        
        redshift = self.clients.get('redshift')
        if not redshift:
            return []
        
        resources = []
        try:
            paginator = redshift.get_paginator('describe_clusters')
            
            for page in paginator.paginate():
                for cluster in page.get('Clusters', []):
                    cluster_id = cluster.get('ClusterIdentifier', '')
                    
                    # Get cluster tags
                    tags = {}
                    try:
                        tag_response = redshift.describe_tags(
                            ResourceName=f"arn:aws:redshift:{redshift.meta.region_name}:{cluster_id}"
                        )
                        # Redshift tags come in a different format
                        tag_dict = {}
                        for tag in tag_response.get('TaggedResources', []):
                            tag_info = tag.get('Tag', {})
                            tag_dict[tag_info.get('Key', '')] = tag_info.get('Value', '')
                        tags = tag_dict
                    except Exception:
                        pass
                    
                    creation_date = cluster.get('ClusterCreateTime', datetime.now(UTC))
                    
                    resources.append(Resource(
                        resource_id=cluster_id,
                        resource_type='cluster',
                        service='redshift',
                        region=redshift.meta.region_name,
                        tags=tags,
                        state=cluster.get('ClusterStatus', 'unknown'),
                        creation_date=creation_date.isoformat() if isinstance(creation_date, datetime) else creation_date
                    ))
        except Exception as e:
            logger.error(f"Error discovering Redshift clusters: {e}")
        
        return resources
    
    def _discover_ecs(self) -> List[Any]:
        """Discover ECS clusters."""
        from ..utils.types import Resource
        
        ecs = self.clients.get('ecs')
        if not ecs:
            return []
        
        resources = []
        try:
            paginator = ecs.get_paginator('list_clusters')
            
            for page in paginator.paginate():
                cluster_arns = page.get('clusterArns', [])
                if not cluster_arns:
                    continue
                
                # Describe clusters in batches
                for i in range(0, len(cluster_arns), 10):  # ECS describe_clusters supports up to 10 at a time
                    batch = cluster_arns[i:i+10]
                    try:
                        cluster_response = ecs.describe_clusters(clusters=batch)
                        
                        for cluster in cluster_response.get('clusters', []):
                            cluster_arn = cluster.get('clusterArn', '')
                            cluster_name = cluster.get('clusterName', '')
                            
                            # Get cluster tags
                            tags = {}
                            try:
                                tag_response = ecs.list_tags_for_resource(resourceArn=cluster_arn)
                                tags = self._extract_tags(tag_response.get('tags', []))
                            except Exception:
                                pass
                            
                            creation_date = cluster.get('registeredAt', datetime.now(UTC))
                            
                            resources.append(Resource(
                                resource_id=cluster_name,
                                resource_type='cluster',
                                service='ecs',
                                region=ecs.meta.region_name,
                                tags=tags,
                                state=cluster.get('status', 'UNKNOWN'),
                                creation_date=creation_date.isoformat() if isinstance(creation_date, datetime) else creation_date
                            ))
                    except Exception as e:
                        logger.warning(f"Failed to describe ECS clusters: {e}")
                        continue
        except Exception as e:
            logger.error(f"Error discovering ECS clusters: {e}")
        
        return resources
    
    def _discover_eks(self) -> List[Any]:
        """Discover EKS clusters."""
        from ..utils.types import Resource
        
        eks = self.clients.get('eks')
        if not eks:
            return []
        
        resources = []
        try:
            paginator = eks.get_paginator('list_clusters')
            
            for page in paginator.paginate():
                cluster_names = page.get('clusters', [])
                
                for cluster_name in cluster_names:
                    try:
                        cluster_response = eks.describe_cluster(name=cluster_name)
                        cluster = cluster_response.get('cluster', {})
                        
                        # Get cluster tags
                        tags = cluster.get('tags', {})
                        
                        creation_date = cluster.get('createdAt', datetime.now(UTC))
                        
                        resources.append(Resource(
                            resource_id=cluster_name,
                            resource_type='cluster',
                            service='eks',
                            region=eks.meta.region_name,
                            tags=tags,
                            state=cluster.get('status', 'UNKNOWN'),
                            creation_date=creation_date.isoformat() if isinstance(creation_date, datetime) else creation_date
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to describe EKS cluster {cluster_name}: {e}")
                        continue
        except Exception as e:
            logger.error(f"Error discovering EKS clusters: {e}")
        
        return resources
    
    def _discover_nat_gateways(self) -> List[Any]:
        """Discover NAT Gateways."""
        from ..utils.types import Resource
        
        ec2 = self.clients.get('ec2')
        if not ec2:
            return []
        
        resources = []
        try:
            response = ec2.describe_nat_gateways()
            
            for nat_gateway in response.get('NatGateways', []):
                # Get NAT Gateway tags
                tags = {}
                if 'Tags' in nat_gateway:
                    tags = self._extract_tags(nat_gateway.get('Tags', []))
                
                creation_date = nat_gateway.get('CreateTime', datetime.now(UTC))
                
                resources.append(Resource(
                    resource_id=nat_gateway['NatGatewayId'],
                    resource_type='nat_gateway',
                    service='nat_gateway',
                    region=ec2.meta.region_name,
                    tags=tags,
                    state=nat_gateway.get('State', 'unknown'),
                    creation_date=creation_date.isoformat() if isinstance(creation_date, datetime) else creation_date
                ))
        except Exception as e:
            logger.error(f"Error discovering NAT Gateways: {e}")
        
        return resources
    
    def _discover_elastic_ips(self) -> List[Any]:
        """Discover Elastic IPs."""
        from ..utils.types import Resource
        
        ec2 = self.clients.get('ec2')
        if not ec2:
            return []
        
        resources = []
        try:
            response = ec2.describe_addresses()
            
            for address in response.get('Addresses', []):
                allocation_id = address.get('AllocationId', '')
                public_ip = address.get('PublicIp', '')
                
                # Elastic IPs don't have tags in the describe_addresses response
                # Need separate call to get tags
                tags = {}
                try:
                    if allocation_id:
                        tag_response = ec2.describe_tags(
                            Filters=[
                                {'Name': 'resource-id', 'Values': [allocation_id]}
                            ]
                        )
                        tags = self._extract_tags(tag_response.get('Tags', []))
                except Exception:
                    pass
                
                # Elastic IPs don't have a creation date in the response
                creation_date = datetime.now(UTC)
                
                # Determine state: in-use if associated with instance, available if not
                state = 'in-use' if address.get('InstanceId') or address.get('NetworkInterfaceId') else 'available'
                
                resources.append(Resource(
                    resource_id=allocation_id or public_ip,
                    resource_type='elastic_ip',
                    service='elastic_ip',
                    region=ec2.meta.region_name,
                    tags=tags,
                    state=state,
                    creation_date=creation_date.isoformat()
                ))
        except Exception as e:
            logger.error(f"Error discovering Elastic IPs: {e}")
        
        return resources
    
    def _discover_load_balancers(self) -> List[Any]:
        """Discover Load Balancers (ALB, NLB, ELB)."""
        from ..utils.types import Resource
        
        elbv2 = self.clients.get('elbv2')  # ALB and NLB
        elb = self.clients.get('elb')  # Classic ELB
        resources = []
        
        # Discover ALB and NLB (Application and Network Load Balancers)
        if elbv2:
            try:
                paginator = elbv2.get_paginator('describe_load_balancers')
                
                for page in paginator.paginate():
                    for lb in page.get('LoadBalancers', []):
                        lb_arn = lb.get('LoadBalancerArn', '')
                        lb_name = lb.get('LoadBalancerName', '')
                        
                        # Get load balancer tags
                        tags = {}
                        try:
                            tag_response = elbv2.describe_tags(ResourceArns=[lb_arn])
                            for tag_desc in tag_response.get('TagDescriptions', []):
                                if tag_desc.get('ResourceArn') == lb_arn:
                                    tags = self._extract_tags(tag_desc.get('Tags', []))
                                    break
                        except Exception:
                            pass
                        
                        creation_date = lb.get('CreatedTime', datetime.now(UTC))
                        lb_type = lb.get('Type', 'application')  # application, network, or gateway
                        
                        # Extract region from availability zones
                        region = elbv2.meta.region_name
                        if lb.get('AvailabilityZones'):
                            az = lb['AvailabilityZones'][0].get('ZoneName', '')
                            if az:
                                # Remove last character from AZ (e.g., us-east-1a -> us-east-1)
                                region = az[:-1] if len(az) > 1 else region
                        
                        resources.append(Resource(
                            resource_id=lb_name,
                            resource_type=f'{lb_type}_load_balancer',
                            service='elb' if lb_type == 'application' else 'nlb',
                            region=region,
                            tags=tags,
                            state=lb.get('State', {}).get('Code', 'unknown'),
                            creation_date=creation_date.isoformat() if isinstance(creation_date, datetime) else creation_date
                        ))
            except Exception as e:
                logger.error(f"Error discovering ALB/NLB load balancers: {e}")
        
        # Discover Classic ELB
        if elb:
            try:
                response = elb.describe_load_balancers()
                
                for lb in response.get('LoadBalancerDescriptions', []):
                    lb_name = lb.get('LoadBalancerName', '')
                    
                    # Get load balancer tags
                    tags = {}
                    try:
                        tag_response = elb.describe_tags(LoadBalancerNames=[lb_name])
                        for tag_desc in tag_response.get('TagDescriptions', []):
                            if tag_desc.get('LoadBalancerName') == lb_name:
                                tags = self._extract_tags(tag_desc.get('Tags', []))
                                break
                    except Exception:
                        pass
                    
                    creation_date = lb.get('CreatedTime', datetime.now(UTC))
                    
                    resources.append(Resource(
                        resource_id=lb_name,
                        resource_type='classic_load_balancer',
                        service='elb',
                        region=elb.meta.region_name,
                        tags=tags,
                        state='active',  # Classic ELB doesn't have state in describe response
                        creation_date=creation_date.isoformat() if isinstance(creation_date, datetime) else creation_date
                    ))
            except Exception as e:
                logger.error(f"Error discovering Classic ELB load balancers: {e}")
        
        return resources
    
    def _discover_sns(self) -> List[Any]:
        """Discover SNS topics."""
        from ..utils.types import Resource
        
        sns = self.clients.get('sns')
        if not sns:
            return []
        
        resources = []
        try:
            paginator = sns.get_paginator('list_topics')
            
            for page in paginator.paginate():
                for topic_arn in page.get('Topics', []):
                    topic_arn_str = topic_arn.get('TopicArn', '')
                    topic_name = topic_arn_str.split(':')[-1] if topic_arn_str else ''
                    
                    # Get topic attributes (includes creation time)
                    try:
                        attrs_response = sns.get_topic_attributes(TopicArn=topic_arn_str)
                        attributes = attrs_response.get('Attributes', {})
                        
                        # Get topic tags
                        tags = {}
                        try:
                            tag_response = sns.list_tags_for_resource(ResourceArn=topic_arn_str)
                            tags = self._extract_tags(tag_response.get('Tags', []))
                        except Exception:
                            pass
                        
                        # Extract region from ARN
                        arn_parts = topic_arn_str.split(':')
                        region = arn_parts[3] if len(arn_parts) > 3 else sns.meta.region_name
                        
                        # Creation time may not be available in attributes
                        creation_date = datetime.now(UTC)
                        
                        resources.append(Resource(
                            resource_id=topic_arn_str,
                            resource_type='topic',
                            service='sns',
                            region=region,
                            tags=tags,
                            state='Active',
                            creation_date=creation_date.isoformat()
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to get attributes for SNS topic {topic_arn_str}: {e}")
                        continue
        except Exception as e:
            logger.error(f"Error discovering SNS topics: {e}")
        
        return resources
    
    def _discover_sqs(self) -> List[Any]:
        """Discover SQS queues."""
        from ..utils.types import Resource
        
        sqs = self.clients.get('sqs')
        if not sqs:
            return []
        
        resources = []
        try:
            # List all queues
            response = sqs.list_queues()
            queue_urls = response.get('QueueUrls', [])
            
            for queue_url in queue_urls:
                try:
                    # Get queue name from URL
                    queue_name = queue_url.split('/')[-1]
                    
                    # Get queue attributes
                    attrs_response = sqs.get_queue_attributes(
                        QueueUrl=queue_url,
                        AttributeNames=['All']
                    )
                    attributes = attrs_response.get('Attributes', {})
                    
                    # Get queue tags
                    tags = {}
                    try:
                        tag_response = sqs.list_queue_tags(QueueUrl=queue_url)
                        tags = tag_response.get('Tags', {})
                    except Exception:
                        pass
                    
                    # Extract region from queue URL
                    # Queue URL format: https://sqs.region.amazonaws.com/account/queue-name
                    url_parts = queue_url.split('.')
                    region = url_parts[1] if len(url_parts) > 1 else sqs.meta.region_name
                    
                    # CreatedTimestamp is in seconds since epoch
                    created_timestamp = attributes.get('CreatedTimestamp', '')
                    if created_timestamp:
                        creation_date = datetime.fromtimestamp(int(created_timestamp), tz=UTC)
                    else:
                        creation_date = datetime.now(UTC)
                    
                    resources.append(Resource(
                        resource_id=queue_url,
                        resource_type='queue',
                        service='sqs',
                        region=region,
                        tags=tags,
                        state='Active',
                        creation_date=creation_date.isoformat()
                    ))
                except Exception as e:
                    logger.warning(f"Failed to get attributes for SQS queue {queue_url}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error discovering SQS queues: {e}")
        
        return resources
    
    def _discover_api_gateway(self) -> List[Any]:
        """Discover API Gateway APIs (REST APIs)."""
        from ..utils.types import Resource
        
        apigateway = self.clients.get('apigateway')
        if not apigateway:
            return []
        
        resources = []
        try:
            # List REST APIs
            paginator = apigateway.get_paginator('get_rest_apis')
            
            for page in paginator.paginate():
                for api in page.get('items', []):
                    api_id = api.get('id', '')
                    api_name = api.get('name', '')
                    
                    # Get API tags
                    tags = {}
                    try:
                        tag_response = apigateway.get_tags(resourceArn=f"arn:aws:apigateway:{apigateway.meta.region_name}::/restapis/{api_id}")
                        tags = tag_response.get('tags', {})
                    except Exception:
                        pass
                    
                    creation_date = api.get('createdDate', datetime.now(UTC))
                    
                    resources.append(Resource(
                        resource_id=api_id,
                        resource_type='rest_api',
                        service='apigateway',
                        region=apigateway.meta.region_name,
                        tags=tags,
                        state=api.get('endpointConfiguration', {}).get('types', ['EDGE'])[0],
                        creation_date=creation_date.isoformat() if isinstance(creation_date, datetime) else creation_date
                    ))
        except Exception as e:
            logger.error(f"Error discovering API Gateway APIs: {e}")
        
        return resources
    
    def _discover_step_functions(self) -> List[Any]:
        """Discover Step Functions state machines."""
        from ..utils.types import Resource
        
        stepfunctions = self.clients.get('stepfunctions')
        if not stepfunctions:
            return []
        
        resources = []
        try:
            paginator = stepfunctions.get_paginator('list_state_machines')
            
            for page in paginator.paginate():
                for state_machine in page.get('stateMachines', []):
                    state_machine_arn = state_machine.get('stateMachineArn', '')
                    state_machine_name = state_machine.get('name', '')
                    
                    # Get state machine tags
                    tags = {}
                    try:
                        tag_response = stepfunctions.list_tags_for_resource(resourceArn=state_machine_arn)
                        tags = self._extract_tags(tag_response.get('tags', []))
                    except Exception:
                        pass
                    
                    creation_date = state_machine.get('creationDate', datetime.now(UTC))
                    
                    resources.append(Resource(
                        resource_id=state_machine_arn,
                        resource_type='state_machine',
                        service='stepfunctions',
                        region=stepfunctions.meta.region_name,
                        tags=tags,
                        state=state_machine.get('status', 'ACTIVE'),
                        creation_date=creation_date.isoformat() if isinstance(creation_date, datetime) else creation_date
                    ))
        except Exception as e:
            logger.error(f"Error discovering Step Functions state machines: {e}")
        
        return resources
    
    def _discover_glue(self) -> List[Any]:
        """Discover Glue jobs."""
        from ..utils.types import Resource
        
        glue = self.clients.get('glue')
        if not glue:
            return []
        
        resources = []
        try:
            paginator = glue.get_paginator('get_jobs')
            
            for page in paginator.paginate():
                for job in page.get('Jobs', []):
                    job_name = job.get('Name', '')
                    
                    # Get job tags
                    tags = {}
                    try:
                        tag_response = glue.get_tags(ResourceArn=f"arn:aws:glue:{glue.meta.region_name}:{job_name}")
                        tags = tag_response.get('Tags', {})
                    except Exception:
                        pass
                    
                    creation_date = job.get('CreatedOn', datetime.now(UTC))
                    
                    resources.append(Resource(
                        resource_id=job_name,
                        resource_type='job',
                        service='glue',
                        region=glue.meta.region_name,
                        tags=tags,
                        state=job.get('LastRun', {}).get('JobRunState', 'UNKNOWN') if job.get('LastRun') else 'IDLE',
                        creation_date=creation_date.isoformat() if isinstance(creation_date, datetime) else creation_date
                    ))
        except Exception as e:
            logger.error(f"Error discovering Glue jobs: {e}")
        
        return resources
    
    def _discover_sagemaker(self) -> List[Any]:
        """Discover SageMaker endpoints."""
        from ..utils.types import Resource
        
        sagemaker = self.clients.get('sagemaker')
        if not sagemaker:
            return []
        
        resources = []
        try:
            # Discover SageMaker endpoints
            paginator = sagemaker.get_paginator('list_endpoints')
            
            for page in paginator.paginate():
                for endpoint in page.get('Endpoints', []):
                    endpoint_name = endpoint.get('EndpointName', '')
                    
                    # Get endpoint details
                    try:
                        endpoint_response = sagemaker.describe_endpoint(EndpointName=endpoint_name)
                        endpoint_details = endpoint_response.get('Endpoint', {})
                        
                        # Get endpoint tags
                        tags = {}
                        try:
                            tag_response = sagemaker.list_tags(ResourceArn=endpoint_details.get('EndpointArn', ''))
                            tags = {tag.get('Key', ''): tag.get('Value', '') for tag in tag_response.get('Tags', [])}
                        except Exception:
                            pass
                        
                        creation_date = endpoint_details.get('CreationTime', datetime.now(UTC))
                        
                        resources.append(Resource(
                            resource_id=endpoint_name,
                            resource_type='endpoint',
                            service='sagemaker',
                            region=sagemaker.meta.region_name,
                            tags=tags,
                            state=endpoint_details.get('EndpointStatus', 'Unknown'),
                            creation_date=creation_date.isoformat() if isinstance(creation_date, datetime) else creation_date
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to describe SageMaker endpoint {endpoint_name}: {e}")
                        continue
        except Exception as e:
            logger.error(f"Error discovering SageMaker endpoints: {e}")
        
        return resources
    
    def _discover_cloudfront(self) -> List[Any]:
        """Discover CloudFront distributions."""
        from ..utils.types import Resource
        
        cloudfront = self.clients.get('cloudfront')
        if not cloudfront:
            return []
        
        resources = []
        try:
            paginator = cloudfront.get_paginator('list_distributions')
            
            for page in paginator.paginate():
                distribution_list = page.get('DistributionList', {})
                
                for distribution in distribution_list.get('Items', []):
                    distribution_id = distribution.get('Id', '')
                    
                    # Get distribution tags
                    tags = {}
                    try:
                        tag_response = cloudfront.list_tags_for_resource(Resource=distribution.get('ARN', ''))
                        tag_list = tag_response.get('Tags', {}).get('Items', [])
                        tags = {tag.get('Key', ''): tag.get('Value', '') for tag in tag_list}
                    except Exception:
                        pass
                    
                    creation_date = distribution.get('LastModifiedTime', datetime.now(UTC))
                    status = distribution.get('Status', 'Unknown')
                    
                    # CloudFront is global, but we'll use the client's region for consistency
                    resources.append(Resource(
                        resource_id=distribution_id,
                        resource_type='distribution',
                        service='cloudfront',
                        region='global',  # CloudFront is global
                        tags=tags,
                        state=status,
                        creation_date=creation_date.isoformat() if isinstance(creation_date, datetime) else creation_date
                    ))
        except Exception as e:
            logger.error(f"Error discovering CloudFront distributions: {e}")
        
        return resources
    
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
