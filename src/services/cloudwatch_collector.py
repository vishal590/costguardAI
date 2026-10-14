"""
CloudWatch Metrics Collector for Phase 1.5.

This module collects usage metrics from CloudWatch for cost estimation.
"""
from typing import List, Dict, Optional, Any
from datetime import datetime
from decimal import Decimal
import boto3
import math
from botocore.exceptions import ClientError

from src.utils.types import (
    MetricDataPoint,
    EC2Metrics,
    LambdaMetrics,
    DynamoDBMetrics,
    S3Metrics,
    RDSMetrics
)
from src.utils.error_handler import format_error, with_retry


class CloudWatchMetricsCollector:
    """Collects metrics from CloudWatch for cost estimation."""
    
    def __init__(self, region: str = 'us-east-1', client=None):
        """
        Initialize CloudWatch client.
        
        Args:
            region: AWS region for CloudWatch client
            client: Optional boto3 CloudWatch client (for testing)
        """
        self.client = client or boto3.client('cloudwatch', region_name=region)
        self.region = region
    
    @staticmethod
    def _list_all(client, operation, result_key, **parameters):
        if client.can_paginate(operation):
            pages = client.get_paginator(operation).paginate(**parameters)
        else:
            response = getattr(client, operation)(**parameters)
            if any(response.get(key) for key in ('NextToken', 'NextMarker', 'Marker', 'ContinuationToken', 'NextContinuationToken', 'LastEvaluatedTableName', 'IsTruncated')):
                raise ValueError('Resource list is truncated but the installed SDK has no paginator')
            pages = [response]
        return {result_key: [item for page in pages for item in page.get(result_key, [])]}

    def collect_metrics(
        self,
        services: List[str],
        start_time: datetime,
        end_time: datetime,
        period: int = 300
    ) -> Dict[str, List[MetricDataPoint]]:
        """
        Collect metrics for multiple services.
        
        Args:
            services: List of service names to collect metrics for
            start_time: Start of time range
            end_time: End of time range
            period: Metric aggregation period in seconds (default: 300 = 5 minutes)
            
        Returns:
            Dictionary mapping service names to lists of metric data points
        """
        results = {}
        
        for service in services:
            service_lower = service.lower()
            
            try:
                if service_lower == 'ec2':
                    metrics = self.collect_ec2_metrics(start_time, end_time)
                    results['ec2'] = self._convert_to_datapoints(metrics, 'ec2')
                    
                elif service_lower == 'lambda':
                    metrics = self.collect_lambda_metrics(start_time, end_time)
                    results['lambda'] = self._convert_to_datapoints(metrics, 'lambda')
                    
                elif service_lower == 'dynamodb':
                    metrics = self.collect_dynamodb_metrics(start_time, end_time)
                    results['dynamodb'] = self._convert_to_datapoints(metrics, 'dynamodb')
                    
                elif service_lower == 's3':
                    metrics = self.collect_s3_metrics(start_time, end_time)
                    results['s3'] = self._convert_to_datapoints(metrics, 's3')
                    
                elif service_lower == 'rds':
                    metrics = self.collect_rds_metrics(start_time, end_time)
                    results['rds'] = self._convert_to_datapoints(metrics, 'rds')
                    
                else:
                    # Skip unsupported services
                    continue
                    
            except Exception as e:
                # Log error but continue with other services
                print(f"Error collecting metrics for {service}: {str(e)}")
                results[service_lower] = []
        
        return results
    
    def collect_service_metrics(
        self,
        services: List[str],
        start_time: datetime,
        end_time: datetime,
        period: int = 300
    ) -> Dict[str, Any]:
        """
        Collect service-specific metrics (returns original metric objects, not just datapoints).
        
        Args:
            services: List of service names to collect metrics for
            start_time: Start of time range
            end_time: End of time range
            period: Metric aggregation period in seconds (default: 300 = 5 minutes)
            
        Returns:
            Dictionary mapping service names to lists of service-specific metric objects
            (EC2Metrics, LambdaMetrics, etc.)
        """
        results = {}
        
        for service in services:
            service_lower = service.lower()
            
            try:
                if service_lower == 'ec2':
                    results['ec2'] = self.collect_ec2_metrics(start_time, end_time)
                elif service_lower == 'lambda':
                    results['lambda'] = self.collect_lambda_metrics(start_time, end_time)
                elif service_lower == 'dynamodb':
                    results['dynamodb'] = self.collect_dynamodb_metrics(start_time, end_time)
                elif service_lower == 's3':
                    results['s3'] = self.collect_s3_metrics(start_time, end_time)
                elif service_lower == 'rds':
                    results['rds'] = self.collect_rds_metrics(start_time, end_time)
                else:
                    # Skip unsupported services
                    continue
                    
            except Exception as e:
                # Log error but continue with other services
                print(f"Error collecting metrics for {service}: {str(e)}")
                results[service_lower] = []
        
        return results
    
    def _convert_to_datapoints(
        self,
        metrics: List,
        service: str
    ) -> List[MetricDataPoint]:
        """
        Convert service-specific metrics to generic MetricDataPoint format.
        
        Args:
            metrics: List of service-specific metrics
            service: Service name
            
        Returns:
            List of MetricDataPoint objects
        """
        datapoints = []
        timestamp = datetime.now()
        
        for metric in metrics:
            # Create a datapoint for each metric
            if service == 'ec2':
                datapoints.append(MetricDataPoint(
                    timestamp=timestamp,
                    value=metric.cpu_utilization,
                    unit='Percent',
                    metric_name=f'{metric.instance_id}_cpu'
                ))
            elif service == 'lambda':
                datapoints.append(MetricDataPoint(
                    timestamp=timestamp,
                    value=Decimal(str(metric.invocations)),
                    unit='Count',
                    metric_name=f'{metric.function_name}_invocations'
                ))
            elif service == 'dynamodb':
                datapoints.append(MetricDataPoint(
                    timestamp=timestamp,
                    value=metric.consumed_read_capacity,
                    unit='Count',
                    metric_name=f'{metric.table_name}_read_capacity'
                ))
            elif service == 's3':
                datapoints.append(MetricDataPoint(
                    timestamp=timestamp,
                    value=Decimal(str(metric.number_of_objects)),
                    unit='Count',
                    metric_name=f'{metric.bucket_name}_objects'
                ))
            elif service == 'rds':
                datapoints.append(MetricDataPoint(
                    timestamp=timestamp,
                    value=Decimal(str(metric.database_connections)),
                    unit='Count',
                    metric_name=f'{metric.instance_id}_connections'
                ))
        
        return datapoints
    
    def collect_ec2_metrics(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[EC2Metrics]:
        """
        Collect EC2 metrics from CloudWatch.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            List of EC2 metrics
        """
        try:
            # Get list of EC2 instances
            ec2_client = boto3.client('ec2', region_name=self.region)
            instances_response = self._list_all(ec2_client, 'describe_instances', 'Reservations',
                Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'stopped']}]
            )
            
            ec2_metrics_list = []
            
            for reservation in instances_response.get('Reservations', []):
                for instance in reservation.get('Instances', []):
                    instance_id = instance['InstanceId']
                    instance_type = instance['InstanceType']
                    
                    # Collect metrics for this instance
                    cpu_util = self._get_metric_statistics(
                        namespace='AWS/EC2',
                        metric_name='CPUUtilization',
                        dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                        start_time=start_time,
                        end_time=end_time,
                        statistic='Average'
                    )
                    
                    network_in = self._get_metric_statistics(
                        namespace='AWS/EC2',
                        metric_name='NetworkIn',
                        dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                        start_time=start_time,
                        end_time=end_time,
                        statistic='Sum'
                    )
                    
                    network_out = self._get_metric_statistics(
                        namespace='AWS/EC2',
                        metric_name='NetworkOut',
                        dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                        start_time=start_time,
                        end_time=end_time,
                        statistic='Sum'
                    )
                    
                    disk_read = self._get_metric_statistics(
                        namespace='AWS/EC2',
                        metric_name='DiskReadBytes',
                        dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                        start_time=start_time,
                        end_time=end_time,
                        statistic='Sum'
                    )
                    
                    # Calculate running hours
                    time_diff = end_time - start_time
                    running_hours = Decimal(str(time_diff.total_seconds() / 3600))
                    
                    ec2_metrics = EC2Metrics(
                        instance_id=instance_id,
                        instance_type=instance_type,
                        cpu_utilization=cpu_util,
                        network_in=network_in,
                        network_out=network_out,
                        disk_read_bytes=disk_read,
                        running_hours=running_hours,
                        billing_profile='linux_shared_ondemand' if instance.get('PlatformDetails') == 'Linux/UNIX' and instance.get('Placement', {}).get('Tenancy') == 'default' and not instance.get('InstanceLifecycle') else 'unsupported'
                    )
                    
                    ec2_metrics_list.append(ec2_metrics)
            
            return ec2_metrics_list
            
        except ClientError as e:
            error_info = format_error(e)
            raise Exception(f"Failed to collect EC2 metrics: {error_info['message']}")
    
    def _get_metric_statistics(
        self,
        namespace: str,
        metric_name: str,
        dimensions: List[Dict[str, str]],
        start_time: datetime,
        end_time: datetime,
        statistic: str = 'Average',
        period: int = 300
    ) -> Decimal:
        """
        Get metric statistics from CloudWatch.
        
        Args:
            namespace: CloudWatch namespace
            metric_name: Name of the metric
            dimensions: Metric dimensions
            start_time: Start time
            end_time: End time
            statistic: Statistic type (Average, Sum, etc.)
            period: Period in seconds
            
        Returns:
            Aggregated metric value as Decimal
        """
        try:
            response = self.client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=start_time,
                EndTime=end_time,
                Period=max(period, math.ceil((end_time-start_time).total_seconds()/1439/60)*60),
                Statistics=[statistic, 'SampleCount'] if statistic == 'Average' else [statistic]
            )
            
            datapoints = response.get('Datapoints', [])
            
            if not datapoints:
                raise ValueError(f'No observed {namespace}/{metric_name} datapoints')
            values = [Decimal(str(point[statistic])) for point in datapoints]
            if any(not value.is_finite() or value < 0 for value in values):
                raise ValueError('Invalid nonnegative usage observation')
            if statistic == 'Average':
                counts = [Decimal(str(point['SampleCount'])) for point in datapoints]
                if any(not count.is_finite() or count <= 0 for count in counts):
                    raise ValueError('Invalid metric sample count')
                return sum((value*count for value, count in zip(values, counts)), Decimal('0')) / sum(counts)
            if statistic == 'Sum': return sum(values, Decimal('0'))
            if statistic == 'Minimum': return min(values)
            if statistic == 'Maximum': return max(values)
            raise ValueError('Unsupported metric aggregation')
            
        except ClientError as e:
            error_info = format_error(e)
            raise Exception(f"Failed to get metric statistics: {error_info['message']}")
    
    def collect_lambda_metrics(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[LambdaMetrics]:
        """
        Collect Lambda metrics from CloudWatch.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            List of Lambda metrics
        """
        try:
            # Get list of Lambda functions
            lambda_client = boto3.client('lambda', region_name=self.region)
            functions_response = self._list_all(lambda_client, 'list_functions', 'Functions')
            
            lambda_metrics_list = []
            
            for function in functions_response.get('Functions', []):
                function_name = function['FunctionName']
                memory_mb = function['MemorySize']
                
                # Collect metrics for this function
                invocations = self._get_metric_statistics(
                    namespace='AWS/Lambda',
                    metric_name='Invocations',
                    dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                    start_time=start_time,
                    end_time=end_time,
                    statistic='Sum'
                )
                
                duration = self._get_metric_statistics(
                    namespace='AWS/Lambda',
                    metric_name='Duration',
                    dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                    start_time=start_time,
                    end_time=end_time,
                    statistic='Average'
                )
                
                errors = self._get_metric_statistics(
                    namespace='AWS/Lambda',
                    metric_name='Errors',
                    dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                    start_time=start_time,
                    end_time=end_time,
                    statistic='Sum'
                )
                
                lambda_metrics = LambdaMetrics(
                    function_name=function_name,
                    invocations=int(invocations),
                    duration_ms=duration,
                    memory_mb=memory_mb,
                    errors=int(errors),
                    billing_profile='x86_lambda' if function.get('Architectures', ['x86_64']) == ['x86_64'] else 'unsupported'
                )
                
                lambda_metrics_list.append(lambda_metrics)
            
            return lambda_metrics_list
            
        except ClientError as e:
            error_info = format_error(e)
            raise Exception(f"Failed to collect Lambda metrics: {error_info['message']}")
    
    def collect_dynamodb_metrics(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[DynamoDBMetrics]:
        """
        Collect DynamoDB metrics from CloudWatch.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            List of DynamoDB metrics
        """
        try:
            # Get list of DynamoDB tables
            dynamodb_client = boto3.client('dynamodb', region_name=self.region)
            tables_response = self._list_all(dynamodb_client, 'list_tables', 'TableNames')
            
            dynamodb_metrics_list = []
            
            for table_name in tables_response.get('TableNames', []):
                description = dynamodb_client.describe_table(TableName=table_name)['Table']
                profile = 'standard_ondemand' if description.get('BillingModeSummary', {}).get('BillingMode') == 'PAY_PER_REQUEST' and description.get('TableClassSummary', {}).get('TableClass', 'STANDARD') == 'STANDARD' else 'unsupported'
                # Collect metrics for this table
                read_capacity = self._get_metric_statistics(
                    namespace='AWS/DynamoDB',
                    metric_name='ConsumedReadCapacityUnits',
                    dimensions=[{'Name': 'TableName', 'Value': table_name}],
                    start_time=start_time,
                    end_time=end_time,
                    statistic='Sum'
                )
                
                write_capacity = self._get_metric_statistics(
                    namespace='AWS/DynamoDB',
                    metric_name='ConsumedWriteCapacityUnits',
                    dimensions=[{'Name': 'TableName', 'Value': table_name}],
                    start_time=start_time,
                    end_time=end_time,
                    statistic='Sum'
                )
                
                dynamodb_metrics = DynamoDBMetrics(
                    table_name=table_name,
                    consumed_read_capacity=read_capacity,
                    consumed_write_capacity=write_capacity, billing_profile=profile
                )
                
                dynamodb_metrics_list.append(dynamodb_metrics)
            
            return dynamodb_metrics_list
            
        except ClientError as e:
            error_info = format_error(e)
            raise Exception(f"Failed to collect DynamoDB metrics: {error_info['message']}")
    
    def collect_s3_metrics(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[S3Metrics]:
        """
        Collect S3 metrics from CloudWatch.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            List of S3 metrics
        """
        try:
            # Get list of S3 buckets
            s3_client = boto3.client('s3', region_name=self.region)
            buckets_response = self._list_all(s3_client, 'list_buckets', 'Buckets')
            
            s3_metrics_list = []
            
            for bucket in buckets_response.get('Buckets', []):
                bucket_name = bucket['Name']
                
                # Collect metrics for this bucket
                num_objects = self._get_metric_statistics(
                    namespace='AWS/S3',
                    metric_name='NumberOfObjects',
                    dimensions=[
                        {'Name': 'BucketName', 'Value': bucket_name},
                        {'Name': 'StorageType', 'Value': 'AllStorageTypes'}
                    ],
                    start_time=start_time,
                    end_time=end_time,
                    statistic='Average'
                )
                
                bucket_size = self._get_metric_statistics(
                    namespace='AWS/S3',
                    metric_name='BucketSizeBytes',
                    dimensions=[
                        {'Name': 'BucketName', 'Value': bucket_name},
                        {'Name': 'StorageType', 'Value': 'StandardStorage'}
                    ],
                    start_time=start_time,
                    end_time=end_time,
                    statistic='Average'
                )
                
                # Note: Request metrics require enabling in S3, default to 0
                get_requests = Decimal('0')
                put_requests = Decimal('0')
                
                s3_metrics = S3Metrics(
                    bucket_name=bucket_name,
                    number_of_objects=int(num_objects),
                    bucket_size_bytes=bucket_size,
                    get_requests=int(get_requests),
                    put_requests=int(put_requests), billing_profile='storage_only_missing_requests'
                )
                
                s3_metrics_list.append(s3_metrics)
            
            return s3_metrics_list
            
        except ClientError as e:
            error_info = format_error(e)
            raise Exception(f"Failed to collect S3 metrics: {error_info['message']}")
    
    def collect_rds_metrics(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[RDSMetrics]:
        """
        Collect RDS metrics from CloudWatch.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            List of RDS metrics
        """
        try:
            # Get list of RDS instances
            rds_client = boto3.client('rds', region_name=self.region)
            instances_response = self._list_all(rds_client, 'describe_db_instances', 'DBInstances')
            
            rds_metrics_list = []
            
            for db_instance in instances_response.get('DBInstances', []):
                instance_id = db_instance['DBInstanceIdentifier']
                instance_type = db_instance['DBInstanceClass']
                storage_gb = Decimal(str(db_instance.get('AllocatedStorage', 0)))
                
                # Collect metrics for this instance
                connections = self._get_metric_statistics(
                    namespace='AWS/RDS',
                    metric_name='DatabaseConnections',
                    dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': instance_id}],
                    start_time=start_time,
                    end_time=end_time,
                    statistic='Average'
                )
                
                read_iops = self._get_metric_statistics(
                    namespace='AWS/RDS',
                    metric_name='ReadIOPS',
                    dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': instance_id}],
                    start_time=start_time,
                    end_time=end_time,
                    statistic='Average'
                )
                
                write_iops = self._get_metric_statistics(
                    namespace='AWS/RDS',
                    metric_name='WriteIOPS',
                    dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': instance_id}],
                    start_time=start_time,
                    end_time=end_time,
                    statistic='Average'
                )
                
                # Calculate running hours
                time_diff = end_time - start_time
                running_hours = Decimal(str(time_diff.total_seconds() / 3600))
                
                rds_metrics = RDSMetrics(
                    instance_id=instance_id,
                    instance_type=instance_type,
                    database_connections=int(connections),
                    read_iops=read_iops,
                    write_iops=write_iops,
                    storage_gb=storage_gb,
                    running_hours=running_hours,
                    billing_profile='postgres_singleaz_gp2' if db_instance.get('Engine') == 'postgres' and db_instance.get('MultiAZ') is False and db_instance.get('StorageType') == 'gp2' else 'unsupported'
                )
                
                rds_metrics_list.append(rds_metrics)
            
            return rds_metrics_list
            
        except ClientError as e:
            error_info = format_error(e)
            raise Exception(f"Failed to collect RDS metrics: {error_info['message']}")
    
    def store_metrics(
        self,
        service: str,
        service_metrics: List[Any],
        start_time: datetime,
        end_time: datetime
    ) -> None:
        """
        Store collected metrics in DynamoDB (optional feature).
        
        Args:
            service: Service name
            service_metrics: List of service-specific metrics
            start_time: Collection start time
            end_time: Collection end time
        """
        try:
            import json
            from datetime import datetime, timezone, timedelta
            
            # Get table (may not exist yet)
            table = self.dynamodb_resource.Table(self.metrics_table_name)
            
            # Store each metric
            for metric in service_metrics:
                # Create metric record
                metric_id = f"{service}#{metric.instance_id if hasattr(metric, 'instance_id') else metric.function_name if hasattr(metric, 'function_name') else metric.table_name if hasattr(metric, 'table_name') else metric.bucket_name if hasattr(metric, 'bucket_name') else 'unknown'}"
                timestamp = datetime.now(timezone.utc).isoformat()
                
                # Convert metric to dict
                metric_dict = {
                    'metric_id': metric_id,
                    'service': service,
                    'timestamp': timestamp,
                    'period_start': start_time.isoformat(),
                    'period_end': end_time.isoformat(),
                    'metric_data': json.dumps({
                        k: str(v) if isinstance(v, Decimal) else v
                        for k, v in metric.__dict__.items()
                    }),
                    'ttl': int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())  # Keep for 30 days
                }
                
                # Write to DynamoDB
                table.put_item(Item=metric_dict)
                
        except ClientError as e:
            # Table might not exist yet - log but don't fail
            if e.response['Error']['Code'] != 'ResourceNotFoundException':
                print(f"Failed to store metrics: {str(e)}")
        except Exception as e:
            # Log error but don't fail - metrics storage is optional
            print(f"Failed to store metrics: {str(e)}")