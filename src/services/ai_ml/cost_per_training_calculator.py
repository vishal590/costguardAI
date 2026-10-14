"""Observed training/resource metadata without unverified billed-cost attribution."""
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Optional, Dict, List
import math
import re
from .error_handler import DataNotFoundError
from ..time_values import parse_utc_timestamp


@dataclass
class TrainingCosts:
    compute_cost: Optional[float]
    storage_cost: Optional[float]
    data_transfer_cost: Optional[float]

    @property
    def total_cost(self):
        values = (self.compute_cost, self.storage_cost, self.data_transfer_cost)
        return sum(values) if all(value is not None for value in values) else None


@dataclass
class TrainingJobMetadata:
    job_id: str
    model: Optional[str]
    dataset: Optional[str]
    instance_type: Optional[str]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    duration_hours: Optional[float]
    source: str
    timing_basis: str = 'unavailable'
    observed_at: str = ''
    region: Optional[str] = None
    status: Optional[str] = None
    instance_launch_time: Optional[str] = None
    labels_verified: bool = False


@dataclass
class CostPerTraining:
    job_id: str
    model: Optional[str]
    dataset: Optional[str]
    date: Optional[datetime]
    training_hours: Optional[float]
    total_cost: Optional[float]
    cost_per_hour: Optional[float]
    compute_cost: Optional[float]
    storage_cost: Optional[float]
    data_transfer_cost: Optional[float]
    instance_type: Optional[str]
    cost_attribution_status: str = 'unavailable'
    metadata: Dict = field(default_factory=dict)


@dataclass
class InstanceComparison:
    instance_type: str
    estimated_duration_hours: Optional[float]
    estimated_cost: Optional[float]
    cost_per_hour: Optional[float]
    savings_vs_baseline: Optional[float]
    savings_percent: Optional[float]


class CostPerTrainingCalculator:
    def __init__(self, cost_explorer_client=None, sagemaker_client=None, ec2_client=None, cloudwatch_client=None):
        self.cost_explorer, self.sagemaker, self.ec2 = cost_explorer_client, sagemaker_client, ec2_client
        self.cloudwatch = cloudwatch_client
        self.last_comparison_report = None

    def calculate_cost_per_training(self, job_id: str, *, source=None):
        metadata = self.get_training_job_metadata(job_id, source=source)
        return CostPerTraining(job_id, metadata.model, metadata.dataset, metadata.start_time,
            metadata.duration_hours, None, None, None, None, None, metadata.instance_type,
            metadata={'source': metadata.source, 'timing_basis': metadata.timing_basis,
                'start_time': metadata.start_time.isoformat() if metadata.start_time else None,
                'end_time': metadata.end_time.isoformat() if metadata.end_time else None,
                'observed_at': metadata.observed_at, 'region': metadata.region, 'status': metadata.status,
                'instance_launch_time': metadata.instance_launch_time, 'labels_verified': False,
                'billing_attribution_verified': False})

    def get_training_job_metadata(self, job_id, *, source=None):
        if not isinstance(job_id, str) or not job_id or len(job_id) > 256 or any(character.isspace() for character in job_id):
            raise ValueError('Supply one explicit job/resource identity')
        if source == 'sagemaker':
            if not re.fullmatch(r'[a-zA-Z0-9](-*[a-zA-Z0-9]){0,62}', job_id) or len(job_id) > 63: raise ValueError('Supply a valid SageMaker training job name')
            return self._get_sagemaker_job_metadata(job_id)
        if source == 'ec2_instance': return self._get_ec2_training_metadata(job_id)
        raise ValueError('Select source=sagemaker or source=ec2_instance')

    def get_training_costs(self, job_id): return TrainingCosts(None, None, None)

    def compare_instance_types(self, model, instance_types, baseline_instance=None):
        if not isinstance(model, str) or not model or len(model) > 256: raise ValueError('Supply a model label')
        if not isinstance(instance_types, list) or not 1 <= len(instance_types) <= 20: raise ValueError('Select 1-20 instance types')
        if any(not isinstance(kind, str) or not re.fullmatch(r'(?:ml\.)?[a-z0-9-]+\.[a-z0-9]+', kind) for kind in instance_types): raise ValueError('Invalid instance type')
        if baseline_instance is not None and baseline_instance not in instance_types: raise ValueError('Baseline must be in selected types')
        self.last_comparison_report = {'status': 'unavailable', 'reason': 'Matched workload benchmarks and billing profiles are unavailable',
            'model_label': model, 'selected_instance_types': list(dict.fromkeys(instance_types)),
            'baseline_instance': baseline_instance, 'performance_compatibility_verified': False}
        return []

    @staticmethod
    def _time(value):
        if value is None: return None
        moment = parse_utc_timestamp(value)
        if moment > datetime.now(UTC): raise ValueError('Observed time is in the future')
        return moment

    def _get_sagemaker_job_metadata(self, job_id):
        if self.sagemaker is None:
            import boto3
            self.sagemaker = boto3.client('sagemaker')
        response = self.sagemaker.describe_training_job(TrainingJobName=job_id)
        start, end = self._time(response.get('TrainingStartTime')), self._time(response.get('TrainingEndTime'))
        if start is not None and end is not None and end < start: raise ValueError('Provider job times are inconsistent')
        seconds = response.get('TrainingTimeInSeconds')
        duration = seconds/3600.0 if not isinstance(seconds, bool) and isinstance(seconds, int) and math.isfinite(seconds) and seconds >= 1 else None
        hyper = response.get('HyperParameters', {})
        label = lambda key: hyper.get(key) if isinstance(hyper.get(key), str) else None
        resource = response.get('ResourceConfig', {})
        kind = None if resource.get('InstanceGroups') else resource.get('SelectedInstanceType') or resource.get('InstanceType')
        return TrainingJobMetadata(job_id, label('model_name'), label('dataset'), kind, start, end, duration,
            'sagemaker', 'provider_reported_training_seconds' if duration is not None else 'unavailable',
            datetime.now(UTC).isoformat(), getattr(getattr(self.sagemaker, 'meta', None), 'region_name', None), response.get('TrainingJobStatus'))

    def _get_ec2_training_metadata(self, job_id):
        if not re.fullmatch(r'i-(?:[a-f0-9]{8}|[a-f0-9]{17})', job_id): raise ValueError('EC2 source requires one instance ID')
        if self.ec2 is None:
            import boto3
            self.ec2 = boto3.client('ec2')
        response = self.ec2.describe_instances(InstanceIds=[job_id])
        matches = [instance for reservation in response.get('Reservations', []) for instance in reservation.get('Instances', []) if instance.get('InstanceId') == job_id]
        if len(matches) != 1: raise DataNotFoundError('Instance metadata is unavailable')
        instance = matches[0]
        tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
        launch = self._time(instance.get('LaunchTime'))
        return TrainingJobMetadata(job_id, tags.get('Model'), tags.get('Dataset'), instance.get('InstanceType'),
            None, None, None, 'ec2_instance', 'job_timing_unavailable_from_instance_uptime', datetime.now(UTC).isoformat(),
            getattr(getattr(self.ec2, 'meta', None), 'region_name', None), instance.get('State', {}).get('Name'),
            launch.isoformat() if launch else None)

    def _get_compute_costs(self, job_id): return None
    def _get_storage_costs(self, job_id): return None
    def _get_data_transfer_costs(self, job_id): return None
    def _estimate_training_duration(self, model, instance_type): return None
    def _estimate_training_cost(self, model, instance_type, duration): return None
