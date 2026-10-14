"""
Idle GPU Detector for Phase 6: AI/ML Workload Cost Management.

This module identifies GPU instances with low utilization (<10%), calculates
idle time and wasted cost, and generates idle GPU alerts.

Requirements: FR-1.5
"""
import logging
import os
from typing import List, Optional
from datetime import datetime, timedelta, UTC
import math
import json
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
    wasted_cost: Optional[float]  # Cost during idle period
    cost_per_hour: Optional[float]  # Hourly cost
    first_idle_time: str  # ISO timestamp
    last_check_time: str  # ISO timestamp
    recommendation: str  # Review suggestion, not execution approval
    observation_status: str = 'rule_matched'
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    utilization_basis: str = 'mean_of_hourly_operator_declared_all_device_maxima'
    workload_inactivity_verified: bool = False
    monetary_status: str = 'unavailable'
    
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
    wasted_cost: Optional[float]
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
        self.last_observation_report = {'inventory_completeness': 'unverified', 'has_more': None}
    
    def _window(self, start_date, end_date):
        start = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=UTC)
        end = datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=UTC)
        if start.strftime('%Y-%m-%d') != start_date or end.strftime('%Y-%m-%d') != end_date:
            raise ValueError('Use YYYY-MM-DD dates')
        if not 1 <= (end-start).days <= 31 or end.date() > datetime.now(UTC).date():
            raise ValueError('Use 1-31 completed daily dates with an exclusive end')
        return start, end

    def _metric_contract(self):
        try:
            profile = json.loads(os.environ.get('GPU_UTILIZATION_METRIC_CONTRACT', '{}'))
            if (not isinstance(profile, dict) or profile.get('aggregation') != 'all_device_maximum'
                    or not isinstance(profile.get('namespace'), str) or not profile['namespace']
                    or profile['namespace'].startswith('AWS/') or len(profile['namespace']) > 255
                    or not isinstance(profile.get('metric_name'), str) or not profile['metric_name']
                    or 'cpu' in profile['metric_name'].lower() or len(profile['metric_name']) > 255): return None
            return profile
        except Exception: return None

    def identify_idle_gpus(self, start_date: str, end_date: str, threshold: float = DEFAULT_IDLE_THRESHOLD, *, instance_id=None, instance_type=None) -> List[IdleGPU]:
        """Review complete dated custom GPU evidence; never substitute CPU or invented money."""
        import re
        start, end = self._window(start_date, end_date)
        if instance_id is not None and (not isinstance(instance_id, str) or not re.fullmatch(r'i-(?:[a-f0-9]{8}|[a-f0-9]{17})', instance_id)):
            raise ValueError('Supply one valid EC2 instance ID')
        if instance_type is not None and (not isinstance(instance_type, str) or not re.fullmatch(r'[gp][0-9][a-z0-9-]*\.[a-z0-9]+', instance_type)):
            raise ValueError('Supply one supported g/p-family instance type')
        self.last_utilization_rows = []
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 100:
            raise ValueError('GPU threshold must be a finite percentage from 0 to 100')
        self.last_observation_report = {'discovery_performed': False, 'observed_instance_count': None,
            'unavailable_evidence_count': None, 'unavailable_examples': [], 'inventory_completeness': 'unverified',
            'metric_source_verified': False, 'instance_limit': 20, 'has_more': None,
            'metric_contract_status': 'configured' if self._metric_contract() else 'unconfigured_or_invalid'}
        if self._metric_contract() is None: return []
        instances = self._get_gpu_instances(start_date, end_date, instance_id=instance_id, instance_type=instance_type)
        report = self.last_observation_report
        report.update({'discovery_performed': True, 'observed_instance_count': len(instances), 'unavailable_evidence_count': 0})
        candidates = []
        for instance in instances:
            evidence = self._get_gpu_evidence(instance['instance_id'], start_date, end_date)
            if evidence is None:
                report['unavailable_evidence_count'] += 1
                if len(report['unavailable_examples']) < 20:
                    report['unavailable_examples'].append({'instance_id': instance['instance_id'], 'reason': 'Complete valid hourly GPU evidence is unavailable'})
                self.last_utilization_rows.append({'instance_id': instance['instance_id'], 'instance_type': instance['instance_type'],
                    'region': instance['region'], 'avg_utilization': None, 'max_utilization': None,
                    'observation_status': 'unavailable', 'window_start': start.isoformat(), 'window_end': end.isoformat(),
                    'utilization_basis': 'hourly_operator_declared_all_device_maxima', 'observed_hour_count': None})
                continue
            self.last_utilization_rows.append({'instance_id': instance['instance_id'], 'instance_type': instance['instance_type'],
                'region': instance['region'], 'avg_utilization': statistics.mean(evidence.values()),
                'max_utilization': max(evidence.values()), 'observation_status': 'available',
                'window_start': start.isoformat(), 'window_end': end.isoformat(),
                'utilization_basis': 'hourly_operator_declared_all_device_maxima', 'observed_hour_count': len(evidence)})
            if all(value < threshold for value in evidence.values()):
                candidates.append(IdleGPU(instance['instance_id'], instance['instance_type'],
                    statistics.mean(evidence.values()), float(len(evidence)), None, None,
                    datetime.fromtimestamp(min(evidence), UTC).isoformat(), datetime.now(UTC).isoformat(),
                    'Review workload requirements; low GPU utilization does not prove safe removal.',
                    window_start=start.isoformat(), window_end=end.isoformat()))
        report['unavailable_examples_truncated'] = report['unavailable_evidence_count'] > len(report['unavailable_examples'])
        return candidates

    def observe_utilization(self, start_date, end_date, *, instance_id=None, instance_type=None):
        self.identify_idle_gpus(start_date, end_date, 0, instance_id=instance_id, instance_type=instance_type)
        return self.last_utilization_rows

    def calculate_idle_time(self, instance_id: str, start_date: str, end_date: str,
                            threshold: float = DEFAULT_IDLE_THRESHOLD) -> Optional[float]:
        evidence = self._get_gpu_evidence(instance_id, start_date, end_date)
        return float(sum(value < threshold for value in evidence.values())) if evidence else None

    def calculate_wasted_cost(self, instance_id: str, instance_type: str, start_date: str,
                              end_date: str, threshold: float = DEFAULT_IDLE_THRESHOLD) -> Optional[float]:
        return None  # Low utilization and generic rates cannot establish avoidable charges.

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
                alert_id=f"idle-gpu-{idle_gpu.instance_id}-{datetime.now(UTC).timestamp()}",
                instance_id=idle_gpu.instance_id,
                instance_type=idle_gpu.instance_type,
                utilization=idle_gpu.utilization,
                idle_hours=idle_gpu.idle_hours,
                wasted_cost=idle_gpu.wasted_cost,
                severity=severity,
                message=message,
                timestamp=datetime.now(UTC).isoformat()
            )
            
            alerts.append(alert)
        
        logger.info(f"Generated {len(alerts)} idle GPU alerts")
        return alerts
    
    def _get_gpu_instances(self, start_date: str, end_date: str, *, instance_id=None, instance_type=None) -> List[dict]:
        import boto3
        import re
        if self.cloudwatch is None: self.cloudwatch = boto3.client('cloudwatch')
        ec2 = boto3.client('ec2', region_name=self.cloudwatch.meta.region_name)
        rows, seen = [], set()
        paginator = ec2.get_paginator('describe_instances')
        pages = 0
        request = {'Filters': [{'Name': 'instance-state-name', 'Values': ['running']},
                              {'Name': 'instance-type', 'Values': [instance_type] if instance_type else ['g*', 'p*']}]}
        if instance_id: request['InstanceIds'] = [instance_id]
        for page in paginator.paginate(**request):
            pages += 1
            for reservation in page.get('Reservations', []):
                for instance in reservation.get('Instances', []):
                    kind = instance.get('InstanceType', '')
                    if not re.match(r'^[gp][0-9]', kind) or instance['InstanceId'] in seen: continue
                    if len(rows) >= 20:
                        self.last_observation_report['has_more'] = True
                        return rows
                    seen.add(instance['InstanceId'])
                    rows.append({'instance_id': instance['InstanceId'], 'instance_type': kind,
                                 'region': ec2.meta.region_name})
            if pages >= 5 and page.get('NextToken'):
                self.last_observation_report['has_more'] = True
                return rows
        self.last_observation_report['has_more'] = False
        return rows

    def _get_gpu_evidence(self, instance_id, start_date, end_date):
        from ..time_values import parse_utc_timestamp
        start, end = self._window(start_date, end_date)
        profile = self._metric_contract()
        if profile is None: return None
        try:
            if self.cloudwatch is None:
                import boto3
                self.cloudwatch = boto3.client('cloudwatch')
            response = self.cloudwatch.get_metric_statistics(Namespace=profile['namespace'], MetricName=profile['metric_name'],
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}], StartTime=start, EndTime=end,
                Period=3600, Statistics=['Maximum', 'SampleCount'], Unit='Percent')
            expected = set(range(int(start.timestamp()), int(end.timestamp()), 3600))
            points = {}
            for point in response.get('Datapoints', []):
                stamp = int(parse_utc_timestamp(point['Timestamp']).timestamp())
                value, samples = float(point['Maximum']), float(point['SampleCount'])
                if stamp not in expected or not math.isfinite(value) or not 0 <= value <= 100 or not math.isfinite(samples) or samples <= 0: return None
                if stamp in points and points[stamp] != value: return None
                points[stamp] = value
            return points if set(points) == expected else None
        except Exception: return None

    def _get_gpu_utilization(self, instance_id, start_date, end_date) -> List[float]:
        evidence = self._get_gpu_evidence(instance_id, start_date, end_date)
        return [evidence[stamp] for stamp in sorted(evidence)] if evidence else []

    def _calculate_idle_hours(self, utilization_data, threshold, start_date, end_date) -> Optional[float]:
        start, end = self._window(start_date, end_date)
        expected = int((end-start).total_seconds()/3600)
        if len(utilization_data) != expected: return None
        if any(not math.isfinite(value) or not 0 <= value <= 100 for value in utilization_data): return None
        return float(sum(value < threshold for value in utilization_data))

    def _get_instance_cost_per_hour(self, instance_type: str) -> Optional[float]:
        return None  # Instance type alone does not establish region/lifecycle/OS/billing profile.

    def _generate_recommendation(self, avg_utilization, idle_hours, wasted_cost):
        return 'Review the observed GPU rule and workload requirements; monetary savings are unavailable.'

    def _determine_severity(self, wasted_cost) -> str:
        return 'info'

    def _generate_alert_message(self, idle_gpu, severity) -> str:
        return (f'{idle_gpu.instance_id} matched a low-GPU-utilization rule over {idle_gpu.idle_hours:.1f} observed hours. '
                'Workload inactivity, safe removal and monetary savings are unverified.')
