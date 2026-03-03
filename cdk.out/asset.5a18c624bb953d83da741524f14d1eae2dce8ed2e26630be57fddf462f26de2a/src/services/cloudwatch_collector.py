"""
CloudWatch Metrics Collector for Phase 1.5.

This module collects usage metrics from CloudWatch for cost estimation.
"""
from typing import List, Dict, Optional
from datetime import datetime
from decimal import Decimal
import boto3
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
            instances_response = ec2_client.describe_instances(
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
                        running_hours=running_hours
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
                Period=period,
                Statistics=[statistic]
            )
            
            datapoints = response.get('Datapoints', [])
            
            if not datapoints:
                return Decimal('0')
            
            # Aggregate all datapoints
            total = sum(dp.get(statistic, 0) for dp in datapoints)
            return Decimal(str(total))
            
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
            functions_response = lambda_client.list_functions()
            
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
                    errors=int(errors)
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
            tables_response = dynamodb_client.list_tables()
            
            dynamodb_metrics_list = []
            
            for table_name in tables_response.get('TableNames', []):
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
                    consumed_write_capacity=write_capacity
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
            buckets_response = s3_client.list_buckets()
            
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
                    put_requests=int(put_requests)
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
            instances_response = rds_client.describe_db_instances()
            
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
                    running_hours=running_hours
                )
                
                rds_metrics_list.append(rds_metrics)
            
            return rds_metrics_list
            
        except ClientError as e:
            error_info = format_error(e)
            raise Exception(f"Failed to collect RDS metrics: {error_info['message']}")
