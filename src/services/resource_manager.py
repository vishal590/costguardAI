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

from typing import List, Dict, Any, Optional
from datetime import datetime, UTC
import logging
import os

logger = logging.getLogger(__name__)

# Service name (config) -> boto3 client name for lazy creation
_BOTO_SERVICE_MAP = {
    'ec2': 'ec2', 'rds': 'rds', 'lambda': 'lambda', 's3': 's3', 'dynamodb': 'dynamodb',
    'elasticache': 'elasticache', 'redshift': 'redshift', 'ecs': 'ecs', 'eks': 'eks',
    'nat_gateway': 'ec2', 'elastic_ip': 'ec2', 'elb': 'elb',
    'alb': 'elbv2', 'nlb': 'elbv2',
    'sns': 'sns', 'sqs': 'sqs', 'api_gateway': 'apigateway', 'apigateway': 'apigateway',
    'step_functions': 'stepfunctions', 'stepfunctions': 'stepfunctions',
    'glue': 'glue', 'sagemaker': 'sagemaker', 'cloudfront': 'cloudfront',
}


class ResourceManager:
    """Discover and manage resources across multiple AWS services."""
    
    def __init__(self, aws_clients: Dict[str, Any], dynamodb_client):
        """
        Initialize resource manager.
        
        Args:
            aws_clients: Dict of boto3 clients by service name (can be empty; clients created lazily)
            dynamodb_client: DynamoDB client for inventory storage
        """
        self._clients = dict(aws_clients) if aws_clients else {}
        self.clients = self._clients  # for tests / backward compat
        self.last_discovery_report = None
        self._discovery_active = False
        self.dynamodb = dynamodb_client
        self.inventory_table = os.environ.get("RESOURCE_INVENTORY_TABLE", "costguard-resource-inventory")
        
    def _get_client(self, boto_name: str):
        """Get boto3 client, creating lazily to avoid init-time 500s in Lambda."""
        if boto_name not in self._clients:
            try:
                import boto3
                self._clients[boto_name] = boto3.client(boto_name)
            except Exception as e:
                self._record_discovery_issue('client_unavailable')
                logger.warning(f"Could not create {boto_name} client: {e}")
                return None
        client = self._clients.get(boto_name)
        if client is None: self._record_discovery_issue('client_unavailable')
        return client
        
    def _bounded_pages(self, pages, result_path, operation):
        """Inspect at most five provider pages/100 listed identities per operation."""
        report = {'service': getattr(self, '_active_discovery_service', 'unavailable'), 'operation': operation,
            'page_limit': 5, 'item_limit': 100, 'pages_read': 0, 'listed_items_seen': 0,
            'retained_items': 0, 'bound_reached': False, 'provider_listing_exhausted': False,
            'status': 'reading'}
        if self._discovery_active and len(self._listing_reports) < 50: self._listing_reports.append(report)
        iterator = iter(pages)
        try:
            for _ in range(5):
                try: page = next(iterator)
                except StopIteration:
                    report['provider_listing_exhausted'] = True; break
                if not isinstance(page, dict): raise ValueError('Invalid listing page')
                report['pages_read'] += 1
                container = page
                for name in result_path[:-1]:
                    container = container.get(name, {})
                    if not isinstance(container, dict): raise ValueError('Invalid nested listing')
                rows = container.get(result_path[-1], [])
                if not isinstance(rows, list): raise ValueError('Invalid listing items')
                # EC2 reservations are grouping envelopes, not individual resource identities.
                if result_path == ('Reservations',):
                    rows = [instance for reservation in rows for instance in reservation.get('Instances', [])]
                report['listed_items_seen'] += len(rows)
                remaining = 100-report['retained_items']
                kept = rows[:remaining]
                report['retained_items'] += len(kept)
                bounded_page = dict(page)
                target = bounded_page
                original = page
                for name in result_path[:-1]:
                    target[name] = dict(original.get(name, {}))
                    target, original = target[name], original.get(name, {})
                target[result_path[-1]] = [{'Instances': kept}] if result_path == ('Reservations',) else kept
                if report['retained_items'] >= 100:
                    report['bound_reached'] = True
                yield bounded_page
                if report['bound_reached']: break
            else:
                report['bound_reached'] = True
            report['status'] = 'bounded_selection' if report['bound_reached'] else 'observed_provider_pages'
            if report['bound_reached']: self._record_discovery_issue('listing_selection_bound_reached')
        except Exception:
            report['status'] = 'unavailable_or_partial'
            raise
        finally:
            if report['status'] == 'reading':
                report['status'] = 'unavailable_or_partial'
                self._record_discovery_issue('listing_consumer_stopped')

    def _list_all(self, client, operation, result_key, **parameters):
        """Collect a bounded selection; unpageable truncation remains explicit."""
        if client.can_paginate(operation):
            pages = client.get_paginator(operation).paginate(**parameters)
        else:
            response = getattr(client, operation)(**parameters)
            if any(response.get(key) for key in ('NextToken', 'NextMarker', 'Marker',
                    'ContinuationToken', 'NextContinuationToken', 'IsTruncated')):
                raise ValueError('Resource list is truncated but SDK pagination is unavailable')
            pages = [response]
        return {result_key: [item for page in self._bounded_pages(pages, (result_key,), operation) for item in page.get(result_key, [])]}

    def _record_discovery_issue(self, category):
        if not self._discovery_active: return
        self._discovery_issue_count += 1
        if len(self._discovery_issues) < 50:
            self._discovery_issues.append({'service': self._active_discovery_service, 'category': category})

    def discover_resources(self, services: List[str]) -> List[Any]:
        """Return observed resources and retain bounded discovery diagnostics."""
        all_resources, service_results = [], []
        services = list(dict.fromkeys(services))
        load_balancer_services = {service for service in services if service in ('elb', 'alb', 'nlb')}
        adapter_services = list(dict.fromkeys('load_balancers' if service in load_balancer_services else service for service in services))
        duplicate_count, conflicts = 0, set()
        self._discovery_issues, self._discovery_issue_count = [], 0
        self._listing_reports = []
        self._discovery_active = True
        started_at = datetime.now(UTC).isoformat()
        try:
            for service in adapter_services:
                self._active_discovery_service = service
                before = self._discovery_issue_count
                resources = []
                try:
                    resources = self._discover_load_balancers(load_balancer_services) if service == 'load_balancers' else self._discover_service_resources(service)
                    if service == 'load_balancers':
                        resources = [resource for resource in resources if resource.service in load_balancer_services]
                    all_resources.extend(resources)
                except Exception as error:
                    self._record_discovery_issue('service_read_failed')
                    logger.warning('Resource discovery unavailable for %s: %s', service, type(error).__name__)
                issue_count = self._discovery_issue_count-before
                service_results.append({'service': service,
                    'requested_services': sorted(load_balancer_services) if service == 'load_balancers' else [service],
                    'observed_resources': len(resources),
                    'reported_issue_count': issue_count,
                    'read_status': 'observed_with_reported_issues' if issue_count else 'observed_no_reported_issues'})
            unique = {}
            raw_count = len(all_resources)
            for resource in all_resources:
                identity = (resource.service, resource.region, resource.resource_id)
                if identity in conflicts: continue
                if identity in unique:
                    duplicate_count += 1
                    if unique[identity] != resource:
                        self._active_discovery_service = resource.service
                        self._record_discovery_issue('conflicting_resource_observations')
                        conflicts.add(identity)
                        del unique[identity]
                else:
                    unique[identity] = resource
            all_resources = list(unique.values())
        finally:
            self._discovery_active = False
        self.last_discovery_report = {'started_at': started_at, 'completed_at': datetime.now(UTC).isoformat(),
            'requested_services': list(services), 'service_results': service_results,
            'raw_observation_count': raw_count, 'unique_observed_resources': len(all_resources),
            'duplicate_observation_count': duplicate_count, 'conflicting_resource_count': len(conflicts),
            'reported_issue_count': self._discovery_issue_count, 'issue_examples': self._discovery_issues,
            'issue_examples_truncated': self._discovery_issue_count > len(self._discovery_issues),
            'inventory_completeness': 'unverified', 'all_metadata_reads_verified': False,
            'listing_limits': {'page_limit_per_operation': 5, 'item_limit_per_operation': 100,
                'scope': 'listed_identities_not_all_SDK_requests_or_wall_clock'},
            'listing_reports': self._listing_reports}
        persistence = self.update_inventory(all_resources)
        self.last_discovery_report['inventory_persistence'] = persistence
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
    
    @staticmethod
    def _inventory_key(account, resource):
        """Namespace the deployed string key without changing live resource identifiers."""
        import hashlib
        import json
        parts = [account, resource.service, resource.region, resource.resource_id]
        if any(not isinstance(part, str) or not part for part in parts): raise ValueError('Incomplete inventory identity')
        if len(resource.service) > 128 or len(resource.region) > 64 or len(resource.resource_id) > 2048:
            raise ValueError('Oversized inventory identity')
        return 'v2#'+hashlib.sha256(json.dumps(parts, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()

    def update_inventory(self, resources: List[Any]) -> Dict[str, Any]:
        """Persist independent scoped observations; no complete snapshot or migration."""
        import re
        from boto3.dynamodb.types import TypeSerializer
        report = {'schema_version': 2, 'attempted_rows': 0, 'stored_rows': 0, 'failed_rows': 0,
            'superseded_rows': 0, 'requested_rows': len(resources), 'failure_examples': [],
            'failure_examples_truncated': False, 'snapshot_complete': False,
            'account_scope_basis': 'configured_backend_account_not_independently_verified',
            'legacy_rows_migrated': False}
        if not self.dynamodb:
            report['status'] = 'not_configured'; return report
        account = os.environ.get('BACKEND_ACCOUNT_ID', '')
        if not re.fullmatch(r'[0-9]{12}', account):
            report['status'] = 'account_scope_not_configured'; return report
        observed_at = datetime.now(UTC)
        timestamp = observed_at.isoformat()
        epoch = int(observed_at.timestamp())
        epoch_us = int(observed_at.timestamp()*1_000_000)
        report['observed_at'] = timestamp
        serializer = TypeSerializer()
        for resource in resources:
            report['attempted_rows'] += 1
            try:
                key = self._inventory_key(account, resource)
                self.dynamodb.put_item(TableName=self.inventory_table,
                    Item={'resource_id': {'S': key}, 'raw_resource_id': {'S': resource.resource_id},
                        'schema_version': {'N': '2'}, 'account_id': {'S': account},
                        'timestamp': {'S': timestamp}, 'observation_epoch_us': {'N': str(epoch_us)},
                        'last_updated': {'N': str(epoch)}, 'ttl': {'N': str(epoch+90*24*60*60)},
                        'properties': serializer.serialize(resource.properties or {}),
                        'inventory_completeness': {'S': 'unverified'},
                        'resource_type': {'S': resource.resource_type}, 'service': {'S': resource.service},
                        'region': {'S': resource.region}, 'state': {'S': resource.state},
                        'tags': {'M': self._format_tags(resource.tags)},
                        'creation_date': serializer.serialize(resource.creation_date)},
                    ConditionExpression='attribute_not_exists(observation_epoch_us) OR observation_epoch_us <= :observed',
                    ExpressionAttributeValues={':observed': {'N': str(epoch_us)}})
                report['stored_rows'] += 1
            except Exception as error:
                if getattr(error, 'response', {}).get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
                    report['superseded_rows'] += 1; continue
                report['failed_rows'] += 1
                if len(report['failure_examples']) < 20:
                    report['failure_examples'].append({'resource_id': str(getattr(resource, 'resource_id', None) or 'unavailable')[:256],
                        'service': str(getattr(resource, 'service', None) or 'unavailable')[:128], 'region': str(getattr(resource, 'region', None) or 'unavailable')[:64],
                        'reason': 'inventory_observation_not_persisted'})
                logger.warning('Inventory observation write unavailable: %s', type(error).__name__)
        report['completed_at'] = datetime.now(UTC).isoformat()
        report['failure_examples_truncated'] = report['failed_rows'] > len(report['failure_examples'])
        report['status'] = 'partial_or_unavailable' if report['failed_rows'] else 'newer_observations_retained' if report['superseded_rows'] else 'observations_persisted'
        return report

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
            self._record_discovery_issue('discovery_operation_failed')
            logger.warning(f"No discovery method for service: {service}")
            return []
    
    @staticmethod
    def validate_inspection(service, identifier):
        import re
        if service not in ('ec2', 'rds', 'lambda'): raise ValueError('Direct inspection supports ec2, rds and lambda')
        if not isinstance(identifier, str): raise ValueError('A bare resource identifier is required')
        if service == 'ec2':
            valid = re.fullmatch(r'i-(?:[a-f0-9]{8}|[a-f0-9]{17})', identifier)
        elif service == 'rds':
            valid = re.fullmatch(r'[A-Za-z][A-Za-z0-9-]{0,62}', identifier) and not identifier.endswith('-') and '--' not in identifier
        else:
            valid = re.fullmatch(r'[A-Za-z0-9_-]{1,64}', identifier)
        if not valid: raise ValueError('Use a valid bare EC2 ID, RDS instance name or unqualified Lambda function name; ARN/region/alias selectors are unsupported')

    def inspect_resource(self, service, identifier):
        """Observe one known resource without an inventory scan, write or eligibility assertion."""
        self.validate_inspection(service, identifier)
        client = self._get_client(service)
        if client is None: raise RuntimeError('Resource inspection client is unavailable')
        region = client.meta.region_name
        if not isinstance(region, str) or not region: raise RuntimeError('Inspection region is unavailable')
        if service == 'ec2':
            rows = self._discover_ec2(identifier)
            matches = [row for row in rows if row.resource_id == identifier]
        elif service == 'rds':
            rows = self._discover_rds(identifier.lower())
            matches = [row for row in rows if row.resource_id.casefold() == identifier.casefold()]
        else:
            rows = self._discover_lambda(identifier)
            matches = [row for row in rows if (row.properties or {}).get('function_name') == identifier]
        if len(rows) != 1 or len(matches) != 1 or matches[0].region != region:
            raise RuntimeError('Resource identity could not be observed unambiguously')
        return matches[0]

    @staticmethod
    def _lambda_resource(details, region):
        from ..utils.types import Resource
        config = details['Configuration']
        return Resource(resource_id=config['FunctionArn'], resource_type='function', service='lambda',
            region=region, tags=details.get('Tags', {}), state=config.get('State', 'unknown'), creation_date=None,
            properties={'function_name': config['FunctionName'], 'last_modified': config.get('LastModified')})

    def _discover_ec2(self, instance_id=None) -> List[Any]:
        """Discover EC2 instances."""
        from ..utils.types import Resource
        
        ec2 = self._get_client('ec2')
        if not ec2:
            return []
        
        resources = []
        response = ec2.describe_instances(InstanceIds=[instance_id]) if instance_id else self._list_all(ec2, 'describe_instances', 'Reservations')
        
        for reservation in response.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                resources.append(Resource(
                    resource_id=instance['InstanceId'],
                    resource_type='instance',
                    service='ec2',
                    region=ec2.meta.region_name,
                    tags=self._extract_tags(instance.get('Tags', [])),
                    state=instance['State']['Name'],
                    creation_date=None,
                    properties={'last_launch_time': self._observed_timestamp(instance.get('LaunchTime')), 'instance_type': instance.get('InstanceType'), 'platform_details': instance.get('PlatformDetails'), 'tenancy': instance.get('Placement', {}).get('Tenancy'), 'lifecycle': instance.get('InstanceLifecycle'), 'root_device_type': instance.get('RootDeviceType')}
                ))
        
        return resources
    
    def _discover_rds(self, instance_id=None) -> List[Any]:
        """Discover RDS instances."""
        from ..utils.types import Resource
        
        rds = self._get_client('rds')
        if not rds:
            return []
        
        resources = []
        response = rds.describe_db_instances(DBInstanceIdentifier=instance_id) if instance_id else self._list_all(rds, 'describe_db_instances', 'DBInstances')
        
        for db in response.get('DBInstances', []):
            resources.append(Resource(
                resource_id=db['DBInstanceIdentifier'],
                resource_type='db_instance',
                service='rds',
                region=rds.meta.region_name,
                tags=self._extract_tags(db.get('TagList', [])),
                state=db['DBInstanceStatus'],
                creation_date=self._observed_timestamp(db.get('InstanceCreateTime')),
                properties={'engine': db.get('Engine'), 'multi_az': db.get('MultiAZ'),
                            'cluster_id': db.get('DBClusterIdentifier'),
                            'replica_source': db.get('ReadReplicaSourceDBInstanceIdentifier'),
                            'read_replicas': db.get('ReadReplicaDBInstanceIdentifiers', []),
                            'topology_observed': True}
            ))
        
        return resources
    
    def _discover_lambda(self, function_name=None) -> List[Any]:
        """Discover Lambda functions."""
        from ..utils.types import Resource
        
        lambda_client = self._get_client('lambda')
        if not lambda_client:
            return []
        
        if function_name:
            return [self._lambda_resource(lambda_client.get_function(FunctionName=function_name), lambda_client.meta.region_name)]
        resources = []
        response = self._list_all(lambda_client, 'list_functions', 'Functions')
        
        for func in response.get('Functions', []):
            try:
                details = lambda_client.get_function(FunctionName=func['FunctionArn'])
                resources.append(self._lambda_resource(details, lambda_client.meta.region_name))
            except Exception as error:
                self._record_discovery_issue('discovery_operation_failed')
                logger.warning('Lambda resource detail unavailable: %s', type(error).__name__)

        return resources
    
    # Placeholder methods for other services
    def _discover_s3(self) -> List[Any]:
        """Discover S3 buckets."""
        from ..utils.types import Resource
        
        s3 = self._get_client('s3')
        if not s3:
            return []
        
        resources = []
        try:
            # List all buckets
            response = self._list_all(s3, 'list_buckets', 'Buckets')
            
            for bucket in response.get('Buckets', []):
                bucket_name = bucket['Name']
                creation_date = bucket.get('CreationDate')
                
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
                    creation_date=self._observed_timestamp(creation_date)
                ))
        except Exception as e:
            self._record_discovery_issue('discovery_operation_failed')
            logger.error(f"Error discovering S3 buckets: {e}")
        
        return resources
    
    def _discover_dynamodb(self) -> List[Any]:
        """Discover DynamoDB tables."""
        from ..utils.types import Resource
        
        dynamodb = self._get_client('dynamodb')
        if not dynamodb:
            return []
        
        resources = []
        try:
            # List all tables
            paginator = dynamodb.get_paginator('list_tables')
            
            for page in self._bounded_pages(paginator.paginate(), ('TableNames',), 'list_tables'):
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
                            self._record_discovery_issue('metadata_read_failed')
                        
                        creation_date = table.get('CreationDateTime')
                        
                        resources.append(Resource(
                            resource_id=table_name,
                            resource_type='table',
                            service='dynamodb',
                            region=dynamodb.meta.region_name,
                            tags=tags,
                            state=table.get('TableStatus', 'UNKNOWN'),
                            creation_date=self._observed_timestamp(creation_date)
                        ))
                    except Exception as e:
                        self._record_discovery_issue('discovery_operation_failed')
                        logger.warning(f"Failed to describe DynamoDB table {table_name}: {e}")
                        continue
        except Exception as e:
            self._record_discovery_issue('discovery_operation_failed')
            logger.error(f"Error discovering DynamoDB tables: {e}")
        
        return resources
    
    def _discover_ebs(self) -> List[Any]:
        """Discover EBS volumes."""
        from ..utils.types import Resource
        
        ec2 = self._get_client('ec2')
        if not ec2:
            return []
        
        resources = []
        try:
            response = self._list_all(ec2, 'describe_volumes', 'Volumes')
            
            for volume in response.get('Volumes', []):
                resources.append(Resource(
                    resource_id=volume['VolumeId'],
                    resource_type='volume',
                    service='ebs',
                    region=ec2.meta.region_name,
                    tags=self._extract_tags(volume.get('Tags', [])),
                    state=volume.get('State', 'unknown'),
                    creation_date=self._observed_timestamp(volume.get('CreateTime'))
                ))
        except Exception as e:
            self._record_discovery_issue('discovery_operation_failed')
            logger.error(f"Error discovering EBS volumes: {e}")
        
        return resources
    
    def _discover_elasticache(self) -> List[Any]:
        """Discover ElastiCache clusters."""
        from ..utils.types import Resource
        
        elasticache = self._get_client('elasticache')
        if not elasticache:
            return []
        
        resources = []
        try:
            # List all cache clusters
            paginator = elasticache.get_paginator('describe_cache_clusters')
            
            for page in self._bounded_pages(paginator.paginate(ShowCacheNodeInfo=False), ('CacheClusters',), 'describe_cache_clusters'):
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
                    
                    creation_date = cluster.get('CacheClusterCreateTime')
                    
                    resources.append(Resource(
                        resource_id=cluster_id,
                        resource_type='cache_cluster',
                        service='elasticache',
                        region=elasticache.meta.region_name,
                        tags=tags,
                        state=cluster.get('CacheClusterStatus', 'unknown'),
                        creation_date=self._observed_timestamp(creation_date)
                    ))
        except Exception as e:
            self._record_discovery_issue('discovery_operation_failed')
            logger.error(f"Error discovering ElastiCache clusters: {e}")
        
        return resources
    
    def _discover_redshift(self) -> List[Any]:
        """Discover Redshift clusters."""
        from ..utils.types import Resource
        
        redshift = self._get_client('redshift')
        if not redshift:
            return []
        
        resources = []
        try:
            paginator = redshift.get_paginator('describe_clusters')
            
            for page in self._bounded_pages(paginator.paginate(), ('Clusters',), 'describe_clusters'):
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
                        self._record_discovery_issue('metadata_read_failed')
                    
                    creation_date = cluster.get('ClusterCreateTime')
                    
                    resources.append(Resource(
                        resource_id=cluster_id,
                        resource_type='cluster',
                        service='redshift',
                        region=redshift.meta.region_name,
                        tags=tags,
                        state=cluster.get('ClusterStatus', 'unknown'),
                        creation_date=self._observed_timestamp(creation_date)
                    ))
        except Exception as e:
            self._record_discovery_issue('discovery_operation_failed')
            logger.error(f"Error discovering Redshift clusters: {e}")
        
        return resources
    
    def _discover_ecs(self) -> List[Any]:
        """Discover ECS clusters."""
        from ..utils.types import Resource
        
        ecs = self._get_client('ecs')
        if not ecs:
            return []
        
        resources = []
        try:
            paginator = ecs.get_paginator('list_clusters')
            
            for page in self._bounded_pages(paginator.paginate(), ('clusterArns',), 'list_clusters'):
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
                                self._record_discovery_issue('metadata_read_failed')
                            
                            creation_date = cluster.get('registeredAt')
                            
                            resources.append(Resource(
                                resource_id=cluster_name,
                                resource_type='cluster',
                                service='ecs',
                                region=ecs.meta.region_name,
                                tags=tags,
                                state=cluster.get('status', 'UNKNOWN'),
                                creation_date=self._observed_timestamp(creation_date)
                            ))
                    except Exception as e:
                        self._record_discovery_issue('discovery_operation_failed')
                        logger.warning(f"Failed to describe ECS clusters: {e}")
                        continue
        except Exception as e:
            self._record_discovery_issue('discovery_operation_failed')
            logger.error(f"Error discovering ECS clusters: {e}")
        
        return resources
    
    def _discover_eks(self) -> List[Any]:
        """Discover EKS clusters."""
        from ..utils.types import Resource
        
        eks = self._get_client('eks')
        if not eks:
            return []
        
        resources = []
        try:
            paginator = eks.get_paginator('list_clusters')
            
            for page in self._bounded_pages(paginator.paginate(), ('clusters',), 'list_clusters'):
                cluster_names = page.get('clusters', [])
                
                for cluster_name in cluster_names:
                    try:
                        cluster_response = eks.describe_cluster(name=cluster_name)
                        cluster = cluster_response.get('cluster', {})
                        
                        # Get cluster tags
                        tags = cluster.get('tags', {})
                        
                        creation_date = cluster.get('createdAt')
                        
                        resources.append(Resource(
                            resource_id=cluster_name,
                            resource_type='cluster',
                            service='eks',
                            region=eks.meta.region_name,
                            tags=tags,
                            state=cluster.get('status', 'UNKNOWN'),
                            creation_date=self._observed_timestamp(creation_date)
                        ))
                    except Exception as e:
                        self._record_discovery_issue('discovery_operation_failed')
                        logger.warning(f"Failed to describe EKS cluster {cluster_name}: {e}")
                        continue
        except Exception as e:
            self._record_discovery_issue('discovery_operation_failed')
            logger.error(f"Error discovering EKS clusters: {e}")
        
        return resources
    
    def _discover_nat_gateways(self) -> List[Any]:
        """Discover NAT Gateways."""
        from ..utils.types import Resource
        
        ec2 = self._get_client('ec2')
        if not ec2:
            return []
        
        resources = []
        try:
            response = self._list_all(ec2, 'describe_nat_gateways', 'NatGateways')
            
            for nat_gateway in response.get('NatGateways', []):
                # Get NAT Gateway tags
                tags = {}
                if 'Tags' in nat_gateway:
                    tags = self._extract_tags(nat_gateway.get('Tags', []))
                
                creation_date = nat_gateway.get('CreateTime')
                
                resources.append(Resource(
                    resource_id=nat_gateway['NatGatewayId'],
                    resource_type='nat_gateway',
                    service='nat_gateway',
                    region=ec2.meta.region_name,
                    tags=tags,
                    state=nat_gateway.get('State', 'unknown'),
                    creation_date=self._observed_timestamp(creation_date)
                ))
        except Exception as e:
            self._record_discovery_issue('discovery_operation_failed')
            logger.error(f"Error discovering NAT Gateways: {e}")
        
        return resources
    
    def _discover_elastic_ips(self) -> List[Any]:
        """Discover Elastic IPs."""
        from ..utils.types import Resource
        
        ec2 = self._get_client('ec2')
        if not ec2:
            return []
        
        resources = []
        try:
            response = self._list_all(ec2, 'describe_addresses', 'Addresses')
            
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
                    self._record_discovery_issue('metadata_read_failed')
                
                # Elastic IPs don't have a creation date in the response
                creation_date = None
                
                # Determine state: in-use if associated with instance, available if not
                state = 'in-use' if address.get('InstanceId') or address.get('NetworkInterfaceId') else 'available'
                
                resources.append(Resource(
                    resource_id=allocation_id or public_ip,
                    resource_type='elastic_ip',
                    service='elastic_ip',
                    region=ec2.meta.region_name,
                    tags=tags,
                    state=state,
                    creation_date=self._observed_timestamp(creation_date)
                ))
        except Exception as e:
            self._record_discovery_issue('discovery_operation_failed')
            logger.error(f"Error discovering Elastic IPs: {e}")
        
        return resources
    
    def _discover_load_balancers(self, selected_services=None) -> List[Any]:
        """Discover Load Balancers (ALB, NLB, ELB)."""
        from ..utils.types import Resource
        
        selected_services = {'elb', 'alb', 'nlb'} if selected_services is None else set(selected_services)
        elbv2 = self._get_client('elbv2') if selected_services & {'alb', 'nlb'} else None
        elb = self._get_client('elb') if 'elb' in selected_services else None
        resources = []
        
        # Discover ALB and NLB (Application and Network Load Balancers)
        if elbv2:
            try:
                paginator = elbv2.get_paginator('describe_load_balancers')
                
                for page in self._bounded_pages(paginator.paginate(), ('LoadBalancers',), 'describe_load_balancers'):
                    for lb in page.get('LoadBalancers', []):
                        lb_service = {'application': 'alb', 'network': 'nlb'}.get(lb.get('Type'))
                        if lb_service not in selected_services: continue
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
                            self._record_discovery_issue('metadata_read_failed')
                        
                        creation_date = lb.get('CreatedTime')
                        lb_type = lb.get('Type', 'application')  # application, network, or gateway
                        
                        # Extract region from availability zones
                        region = elbv2.meta.region_name
                        resources.append(Resource(
                            resource_id=lb_arn,
                            resource_type=f'{lb_type}_load_balancer',
                            service={'application': 'alb', 'network': 'nlb'}.get(lb_type, 'unsupported_load_balancer'),
                            region=region,
                            tags=tags,
                            state=lb.get('State', {}).get('Code', 'unknown'),
                            creation_date=self._observed_timestamp(creation_date)
                        ))
            except Exception as e:
                self._record_discovery_issue('discovery_operation_failed')
                logger.error(f"Error discovering ALB/NLB load balancers: {e}")
        
        # Discover Classic ELB
        if elb:
            try:
                response = self._list_all(elb, 'describe_load_balancers', 'LoadBalancerDescriptions')
                
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
                        self._record_discovery_issue('metadata_read_failed')
                    
                    creation_date = lb.get('CreatedTime')
                    
                    resources.append(Resource(
                        resource_id=lb_name,
                        resource_type='classic_load_balancer',
                        service='elb',
                        region=elb.meta.region_name,
                        tags=tags,
                        state='active',  # Classic ELB doesn't have state in describe response
                        creation_date=self._observed_timestamp(creation_date)
                    ))
            except Exception as e:
                self._record_discovery_issue('discovery_operation_failed')
                logger.error(f"Error discovering Classic ELB load balancers: {e}")
        
        return resources
    
    def _discover_sns(self) -> List[Any]:
        """Discover SNS topics."""
        from ..utils.types import Resource
        
        sns = self._get_client('sns')
        if not sns:
            return []
        
        resources = []
        try:
            paginator = sns.get_paginator('list_topics')
            
            for page in self._bounded_pages(paginator.paginate(), ('Topics',), 'list_topics'):
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
                            self._record_discovery_issue('metadata_read_failed')
                        
                        # Extract region from ARN
                        arn_parts = topic_arn_str.split(':')
                        region = arn_parts[3] if len(arn_parts) > 3 else sns.meta.region_name
                        
                        # Creation time may not be available in attributes
                        creation_date = None
                        
                        resources.append(Resource(
                            resource_id=topic_arn_str,
                            resource_type='topic',
                            service='sns',
                            region=region,
                            tags=tags,
                            state='Active',
                            creation_date=self._observed_timestamp(creation_date)
                        ))
                    except Exception as e:
                        self._record_discovery_issue('discovery_operation_failed')
                        logger.warning(f"Failed to get attributes for SNS topic {topic_arn_str}: {e}")
                        continue
        except Exception as e:
            self._record_discovery_issue('discovery_operation_failed')
            logger.error(f"Error discovering SNS topics: {e}")
        
        return resources
    
    def _discover_sqs(self) -> List[Any]:
        """Discover SQS queues."""
        from ..utils.types import Resource
        
        sqs = self._get_client('sqs')
        if not sqs:
            return []
        
        resources = []
        try:
            # List all queues
            response = self._list_all(sqs, 'list_queues', 'QueueUrls', MaxResults=1000)
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
                        self._record_discovery_issue('metadata_read_failed')
                    
                    # Extract region from queue URL
                    # Queue URL format: https://sqs.region.amazonaws.com/account/queue-name
                    url_parts = queue_url.split('.')
                    region = url_parts[1] if len(url_parts) > 1 else sqs.meta.region_name
                    
                    # CreatedTimestamp is in seconds since epoch
                    created_timestamp = attributes.get('CreatedTimestamp', '')
                    if created_timestamp:
                        creation_date = datetime.fromtimestamp(int(created_timestamp), tz=UTC)
                    else:
                        creation_date = None
                    
                    resources.append(Resource(
                        resource_id=queue_url,
                        resource_type='queue',
                        service='sqs',
                        region=region,
                        tags=tags,
                        state='Active',
                        creation_date=self._observed_timestamp(creation_date)
                    ))
                except Exception as e:
                    self._record_discovery_issue('discovery_operation_failed')
                    logger.warning(f"Failed to get attributes for SQS queue {queue_url}: {e}")
                    continue
        except Exception as e:
            self._record_discovery_issue('discovery_operation_failed')
            logger.error(f"Error discovering SQS queues: {e}")
        
        return resources
    
    def _discover_api_gateway(self) -> List[Any]:
        """Discover API Gateway APIs (REST APIs)."""
        from ..utils.types import Resource
        
        apigateway = self._get_client('apigateway')
        if not apigateway:
            return []
        
        resources = []
        try:
            # List REST APIs
            paginator = apigateway.get_paginator('get_rest_apis')
            
            for page in self._bounded_pages(paginator.paginate(), ('items',), 'get_rest_apis'):
                for api in page.get('items', []):
                    api_id = api.get('id', '')
                    api_name = api.get('name', '')
                    
                    # Get API tags
                    tags = {}
                    try:
                        tag_response = apigateway.get_tags(resourceArn=f"arn:aws:apigateway:{apigateway.meta.region_name}::/restapis/{api_id}")
                        tags = tag_response.get('tags', {})
                    except Exception:
                        self._record_discovery_issue('metadata_read_failed')
                    
                    creation_date = api.get('createdDate')
                    
                    resources.append(Resource(
                        resource_id=api_id,
                        resource_type='rest_api',
                        service='apigateway',
                        region=apigateway.meta.region_name,
                        tags=tags,
                        state=api.get('endpointConfiguration', {}).get('types', ['EDGE'])[0],
                        creation_date=self._observed_timestamp(creation_date)
                    ))
        except Exception as e:
            self._record_discovery_issue('discovery_operation_failed')
            logger.error(f"Error discovering API Gateway APIs: {e}")
        
        return resources
    
    def _discover_step_functions(self) -> List[Any]:
        """Discover Step Functions state machines."""
        from ..utils.types import Resource
        
        stepfunctions = self._get_client('stepfunctions')
        if not stepfunctions:
            return []
        
        resources = []
        try:
            paginator = stepfunctions.get_paginator('list_state_machines')
            
            for page in self._bounded_pages(paginator.paginate(), ('stateMachines',), 'list_state_machines'):
                for state_machine in page.get('stateMachines', []):
                    state_machine_arn = state_machine.get('stateMachineArn', '')
                    state_machine_name = state_machine.get('name', '')
                    
                    # Get state machine tags
                    tags = {}
                    try:
                        tag_response = stepfunctions.list_tags_for_resource(resourceArn=state_machine_arn)
                        tags = self._extract_tags(tag_response.get('tags', []))
                    except Exception:
                        self._record_discovery_issue('metadata_read_failed')
                    
                    creation_date = state_machine.get('creationDate')
                    
                    resources.append(Resource(
                        resource_id=state_machine_arn,
                        resource_type='state_machine',
                        service='stepfunctions',
                        region=stepfunctions.meta.region_name,
                        tags=tags,
                        state=state_machine.get('status', 'ACTIVE'),
                        creation_date=self._observed_timestamp(creation_date)
                    ))
        except Exception as e:
            self._record_discovery_issue('discovery_operation_failed')
            logger.error(f"Error discovering Step Functions state machines: {e}")
        
        return resources
    
    def _discover_glue(self) -> List[Any]:
        """Discover Glue jobs."""
        from ..utils.types import Resource
        
        glue = self._get_client('glue')
        if not glue:
            return []
        
        resources = []
        try:
            paginator = glue.get_paginator('get_jobs')
            
            for page in self._bounded_pages(paginator.paginate(), ('Jobs',), 'get_jobs'):
                for job in page.get('Jobs', []):
                    job_name = job.get('Name', '')
                    
                    # Get job tags
                    tags = {}
                    try:
                        tag_response = glue.get_tags(ResourceArn=f"arn:aws:glue:{glue.meta.region_name}:{job_name}")
                        tags = tag_response.get('Tags', {})
                    except Exception:
                        self._record_discovery_issue('metadata_read_failed')
                    
                    creation_date = job.get('CreatedOn')
                    
                    resources.append(Resource(
                        resource_id=job_name,
                        resource_type='job',
                        service='glue',
                        region=glue.meta.region_name,
                        tags=tags,
                        state=job.get('LastRun', {}).get('JobRunState', 'UNKNOWN') if job.get('LastRun') else 'IDLE',
                        creation_date=self._observed_timestamp(creation_date)
                    ))
        except Exception as e:
            self._record_discovery_issue('discovery_operation_failed')
            logger.error(f"Error discovering Glue jobs: {e}")
        
        return resources
    
    def _discover_sagemaker(self) -> List[Any]:
        """Discover SageMaker endpoints."""
        from ..utils.types import Resource
        
        sagemaker = self._get_client('sagemaker')
        if not sagemaker:
            return []
        
        resources = []
        try:
            # Discover SageMaker endpoints
            paginator = sagemaker.get_paginator('list_endpoints')
            
            for page in self._bounded_pages(paginator.paginate(), ('Endpoints',), 'list_endpoints'):
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
                            self._record_discovery_issue('metadata_read_failed')
                        
                        creation_date = endpoint_details.get('CreationTime')
                        
                        resources.append(Resource(
                            resource_id=endpoint_name,
                            resource_type='endpoint',
                            service='sagemaker',
                            region=sagemaker.meta.region_name,
                            tags=tags,
                            state=endpoint_details.get('EndpointStatus', 'Unknown'),
                            creation_date=self._observed_timestamp(creation_date)
                        ))
                    except Exception as e:
                        self._record_discovery_issue('discovery_operation_failed')
                        logger.warning(f"Failed to describe SageMaker endpoint {endpoint_name}: {e}")
                        continue
        except Exception as e:
            self._record_discovery_issue('discovery_operation_failed')
            logger.error(f"Error discovering SageMaker endpoints: {e}")
        
        return resources
    
    def _discover_cloudfront(self) -> List[Any]:
        """Discover CloudFront distributions."""
        from ..utils.types import Resource
        
        cloudfront = self._get_client('cloudfront')
        if not cloudfront:
            return []
        
        resources = []
        try:
            paginator = cloudfront.get_paginator('list_distributions')
            
            for page in self._bounded_pages(paginator.paginate(), ('DistributionList', 'Items'), 'list_distributions'):
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
                        self._record_discovery_issue('metadata_read_failed')
                    
                    creation_date = None  # LastModifiedTime is not a creation timestamp
                    status = distribution.get('Status', 'Unknown')
                    
                    # CloudFront is global, but we'll use the client's region for consistency
                    resources.append(Resource(
                        resource_id=distribution_id,
                        resource_type='distribution',
                        service='cloudfront',
                        region='global',  # CloudFront is global
                        tags=tags,
                        state=status,
                        creation_date=self._observed_timestamp(creation_date)
                    ))
        except Exception as e:
            self._record_discovery_issue('discovery_operation_failed')
            logger.error(f"Error discovering CloudFront distributions: {e}")
        
        return resources
    
    def _get_cloudwatch_metrics(self, resource) -> Dict[str, float]:
        """
        Get CloudWatch metrics for a resource.
        
        Args:
            resource: Resource object
            
        Returns:
            Dictionary of metric names to values
        """
        try:
            import boto3
            from datetime import timedelta
            
            cloudwatch = self._get_client('cloudwatch')
            if not cloudwatch:
                cloudwatch = boto3.client('cloudwatch')
            
            metrics = {}
            end_time = datetime.now(UTC)
            start_time = end_time - timedelta(hours=24)  # Last 24 hours
            
            # Service-specific metric queries
            if resource.service == 'ec2':
                # Get CPU utilization
                try:
                    response = cloudwatch.get_metric_statistics(
                        Namespace='AWS/EC2',
                        MetricName='CPUUtilization',
                        Dimensions=[{'Name': 'InstanceId', 'Value': resource.resource_id}],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=3600,  # 1 hour periods
                        Statistics=['Average']
                    )
                    if response.get('Datapoints'):
                        # Get most recent average
                        latest = max(response['Datapoints'], key=lambda x: x['Timestamp'])
                        metrics['cpu_utilization'] = latest['Average']
                except Exception as e:
                    logger.debug(f"Could not get CPU metrics for {resource.resource_id}: {e}")
            
            elif resource.service == 'lambda':
                # Get invocation count
                try:
                    response = cloudwatch.get_metric_statistics(
                        Namespace='AWS/Lambda',
                        MetricName='Invocations',
                        Dimensions=[{'Name': 'FunctionName', 'Value': resource.resource_id}],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=3600,
                        Statistics=['Sum']
                    )
                    if response.get('Datapoints'):
                        latest = max(response['Datapoints'], key=lambda x: x['Timestamp'])
                        metrics['invocations'] = latest['Sum']
                except Exception as e:
                    logger.debug(f"Could not get Lambda metrics for {resource.resource_id}: {e}")
            
            elif resource.service == 'rds':
                # Get CPU utilization
                try:
                    response = cloudwatch.get_metric_statistics(
                        Namespace='AWS/RDS',
                        MetricName='CPUUtilization',
                        Dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': resource.resource_id}],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=3600,
                        Statistics=['Average']
                    )
                    if response.get('Datapoints'):
                        latest = max(response['Datapoints'], key=lambda x: x['Timestamp'])
                        metrics['cpu_utilization'] = latest['Average']
                except Exception as e:
                    logger.debug(f"Could not get RDS metrics for {resource.resource_id}: {e}")
            
            return metrics
            
        except Exception as e:
            logger.warning(f"Error getting CloudWatch metrics for {resource.resource_id}: {e}")
            return {}
    
    def _estimate_resource_cost(self, resource) -> Optional[float]:
        """Return only a matching Linux/shared on-demand EC2 compute hourly rate."""
        import math
        properties = resource.properties or {}
        if (resource.service != 'ec2' or properties.get('platform_details') != 'Linux/UNIX'
                or properties.get('tenancy') != 'default' or properties.get('lifecycle')
                or not properties.get('instance_type')):
            return None
        try:
            from .pricing_manager import PricingManager
            pricing = PricingManager(region=resource.region).get_pricing_data('ec2', resource.region)
            if pricing.source != 'aws_pricing' or pricing.currency != 'USD' or pricing.region != resource.region:
                return None
            rate = pricing.prices.get(properties['instance_type'])
            if rate is None or isinstance(rate, bool): return None
            rate = float(rate)
            return rate if math.isfinite(rate) and rate >= 0 else None
        except Exception as error:
            logger.debug('Resource compute rate unavailable: %s', type(error).__name__)
            return None

    def _get_last_activity(self, resource, metrics: Dict[str, float]) -> Optional[str]:
        """Latest positive metric bucket in seven days, not a proven last activity time."""
        import math
        from datetime import timedelta
        from .time_values import parse_utc_timestamp
        profiles = {'ec2': ('AWS/EC2', 'NetworkIn', 'InstanceId'),
                    'lambda': ('AWS/Lambda', 'Invocations', 'FunctionName')}
        if resource.service not in profiles: return None
        try:
            cloudwatch = self._get_client('cloudwatch')
            if cloudwatch is None or cloudwatch.meta.region_name != resource.region: return None
            namespace, metric, dimension = profiles[resource.service]
            identity = (resource.properties or {}).get('function_name') if resource.service == 'lambda' else resource.resource_id
            if not identity: return None
            end = datetime.now(UTC)
            start = end-timedelta(days=7)
            response = cloudwatch.get_metric_statistics(Namespace=namespace, MetricName=metric,
                Dimensions=[{'Name': dimension, 'Value': identity}],
                StartTime=start, EndTime=end, Period=3600, Statistics=['Sum'])
            active = []
            for point in response.get('Datapoints', []):
                value = float(point['Sum'])
                stamp = parse_utc_timestamp(point['Timestamp'])
                if not math.isfinite(value) or value < 0: return None
                if value > 0 and start <= stamp <= end: active.append(stamp)
            return max(active).isoformat() if active else None
        except Exception as error:
            logger.debug('Observed activity bucket unavailable: %s', type(error).__name__)
            return None

    @staticmethod
    def _observed_timestamp(value) -> Optional[str]:
        """Normalize a supplied aware timestamp without inventing missing dates."""
        from .time_values import parse_utc_timestamp
        try:
            moment = parse_utc_timestamp(value)
            return moment.isoformat() if moment <= datetime.now(UTC) else None
        except (ValueError, TypeError):
            return None

    def _extract_tags(self, tag_list: List[Dict[str, str]]) -> Dict[str, str]:
        """Extract tags from AWS tag list format."""
        return {tag['Key']: tag['Value'] for tag in tag_list}
    
    def _format_tags(self, tags: Dict[str, str]) -> Dict[str, Dict[str, str]]:
        """Format tags for DynamoDB."""
        return {k: {'S': v} for k, v in tags.items()}
