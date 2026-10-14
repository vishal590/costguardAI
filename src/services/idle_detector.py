"""Observed-window low-usage rules for EC2, RDS and Lambda.

Unsupported services and incomplete metric coverage remain unknown.
Matching a rule does not establish workload inactivity or safe termination.
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
        """Match a fully observed low-usage rule, never infer inactivity from absence."""
        from ..utils.types import IdleStatus
        from .time_values import parse_utc_timestamp
        import math
        def unknown(reason):
            return IdleStatus(resource_id=resource.resource_id, is_idle=False, idle_duration=0,
                metrics_used={}, confidence=None, observation_status='unavailable', reason=reason)
        profiles = {'ec2': ('AWS/EC2', 'InstanceId', [('CPUUtilization', 'Maximum', 5.0), ('NetworkIn', 'Sum', 0.0), ('NetworkOut', 'Sum', 0.0)]),
                    'rds': ('AWS/RDS', 'DBInstanceIdentifier', [('DatabaseConnections', 'Maximum', 0.0)]),
                    'lambda': ('AWS/Lambda', 'FunctionName', [('Invocations', 'Sum', 0.0)])}
        if resource.service not in profiles: return unknown('No observed-window adapter for this service')
        if self.cloudwatch is None: return unknown('CloudWatch client is unavailable')
        if getattr(getattr(self.cloudwatch, 'meta', None), 'region_name', None) != resource.region:
            return unknown('CloudWatch region does not match the observed resource')
        if resource.service == 'ec2':
            family = str((resource.properties or {}).get('instance_type') or '').split('.')[0]
            if not family or family.startswith(('g', 'p', 'inf', 'trn', 'dl', 'f', 'vt')):
                return unknown('CPU rules do not establish accelerator workload inactivity')
            if resource.state != 'running': return unknown('Instance is not in running state')
        if resource.service == 'rds' and resource.state != 'available': return unknown('Database is not available for this rule')
        if resource.service == 'lambda' and resource.state != 'Active': return unknown('Function is not active')
        identity = (resource.properties or {}).get('function_name') if resource.service == 'lambda' else resource.resource_id
        if not identity: return unknown('Metric resource identity is unavailable')
        criteria = self.get_idle_criteria(resource.service)
        period = 300
        duration = criteria.duration_minutes*60
        if duration <= 0 or duration % period or duration//period > 1439: return unknown('Unsupported observation window')
        end_epoch = int(datetime.now(UTC).timestamp())//period*period-period
        start_epoch = end_epoch-duration
        expected = set(range(start_epoch, end_epoch, period))
        namespace, dimension, rules = profiles[resource.service]
        maxima, matches = {}, True
        try:
            for metric, statistic, threshold in rules:
                response = self.cloudwatch.get_metric_statistics(Namespace=namespace, MetricName=metric,
                    Dimensions=[{'Name': dimension, 'Value': identity}],
                    StartTime=datetime.fromtimestamp(start_epoch, UTC), EndTime=datetime.fromtimestamp(end_epoch, UTC),
                    Period=period, Statistics=[statistic, 'SampleCount'])
                points = {}
                for point in response.get('Datapoints', []):
                    stamp = int(parse_utc_timestamp(point['Timestamp']).timestamp())
                    value, samples = float(point[statistic]), float(point['SampleCount'])
                    if not math.isfinite(value) or value < 0 or not math.isfinite(samples) or samples <= 0:
                        return unknown('Invalid metric observation')
                    if stamp in points and points[stamp] != value: return unknown('Conflicting metric buckets')
                    points[stamp] = value
                if set(points) != expected: return unknown('Incomplete metric buckets; missing data is not zero usage')
                maxima[metric] = max(points.values())
                matches = matches and all(value < threshold if metric == 'CPUUtilization' else value <= threshold for value in points.values())
            return IdleStatus(resource_id=resource.resource_id, is_idle=matches,
                idle_duration=criteria.duration_minutes if matches else 0, metrics_used=maxima, confidence=None,
                observation_status='rule_matched' if matches else 'rule_not_matched',
                reason='Observed low-usage rule; this does not verify workload inactivity',
                window_start=datetime.fromtimestamp(start_epoch, UTC).isoformat(), window_end=datetime.fromtimestamp(end_epoch, UTC).isoformat())
        except Exception as error:
            logger.debug('Observed idle evidence unavailable: %s', type(error).__name__)
            return unknown('Metric evidence could not be retrieved')

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
    
