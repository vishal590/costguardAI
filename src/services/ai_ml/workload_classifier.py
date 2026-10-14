"""Declared workload labels and uncalibrated GPU-pattern observations."""
from dataclasses import dataclass, asdict, field
from datetime import datetime, UTC
from typing import Optional, List, Dict
import math
import os
import re
import statistics
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from .idle_detector import IdleGPUDetector
from ..time_values import parse_utc_timestamp


class ClassificationStoreUnavailable(RuntimeError): pass
class ClassificationConflict(RuntimeError): pass


@dataclass
class WorkloadClassification:
    instance_id: str
    workload_type: str
    confidence: Optional[float]
    classification_method: str
    gpu_utilization_avg: Optional[float]
    gpu_utilization_pattern: List[float]
    timestamp: str
    confidence_method: str = 'unavailable'
    workload_identity_verified: bool = False
    utilization_pattern_label: str = 'unavailable'
    utilization_basis: str = 'hourly_operator_declared_all_device_maxima'
    data_quality: Dict = field(default_factory=dict)
    manual_label: Dict = field(default_factory=dict)
    hourly_observations: List[Dict] = field(default_factory=list)

    def to_dict(self): return asdict(self)


class WorkloadClassifier:
    TRAINING_THRESHOLD = 70.0
    IDLE_THRESHOLD = 10.0
    MIN_DATA_POINTS = 12

    def __init__(self, dynamodb_client, cloudwatch_client=None, ec2_client=None):
        self.dynamodb, self.cloudwatch, self.ec2 = dynamodb_client, cloudwatch_client, ec2_client
        self.table_name = os.environ.get('WORKLOAD_CLASSIFICATIONS_TABLE', 'costguard-workload-classifications')
        self.last_manual_info = None
        self.last_metric_info = None
        self.last_hourly_observations = []

    @staticmethod
    def _identity(instance_id):
        if not isinstance(instance_id, str) or not re.fullmatch(r'i-(?:[a-f0-9]{8}|[a-f0-9]{17})', instance_id):
            raise ValueError('Supply one valid EC2 instance ID')

    def _db(self):
        if self.dynamodb is None:
            import boto3
            self.dynamodb = boto3.client('dynamodb')
        return self.dynamodb

    def _instance(self, instance_id):
        if self.ec2 is None:
            import boto3
            self.ec2 = boto3.client('ec2')
        response = self.ec2.describe_instances(InstanceIds=[instance_id])
        rows = [row for reservation in response.get('Reservations', []) for row in reservation.get('Instances', []) if row.get('InstanceId') == instance_id]
        if len(rows) != 1: raise ClassificationStoreUnavailable('Instance metadata is unavailable')
        return rows[0]

    def _stored_override(self, instance_id):
        try:
            response = self._db().get_item(TableName=self.table_name,
                Key={'instance_id': {'S': instance_id}, 'date': {'S': 'MANUAL'}}, ConsistentRead=True)
            encoded = response.get('Item')
            if not encoded: return None
            if encoded.get('schema_version', {}).get('N') != '2': raise ValueError('Unknown label schema')
            version = int(encoded['version']['N'])
            if not 1 <= version <= 2**53-1: raise ValueError('Invalid label version')
            decoder = TypeDeserializer()
            item = {key: decoder.deserialize(value) for key, value in encoded.items()}
            enabled = item.get('override_enabled')
            if not isinstance(enabled, bool) or item.get('kind') != 'manual_workload_label': raise ValueError('Invalid label kind')
            if enabled and item.get('workload_type') not in ('training', 'inference', 'idle'): raise ValueError('Invalid declared label')
            stamp = parse_utc_timestamp(item['updated_at'])
            if stamp > datetime.now(UTC): raise ValueError('Future label timestamp')
            return {'version': version, 'override_enabled': enabled,
                'workload_type': item.get('workload_type') if enabled else None,
                'reason': item.get('reason') if isinstance(item.get('reason'), str) else None,
                'updated_at': stamp.isoformat(), 'actor_id': item.get('actor_id') if isinstance(item.get('actor_id'), str) else None,
                'region': item.get('region') if isinstance(item.get('region'), str) else None}
        except Exception as error:
            raise ClassificationStoreUnavailable('Declared workload-label storage is unavailable') from error

    def read_manual_label(self, instance_id):
        self._identity(instance_id)
        stored = self._stored_override(instance_id)
        result = {'instance_id': instance_id, 'version': stored['version'] if stored else 0,
            'application_override': stored, 'effective_label': None, 'effective_source': 'none',
            'confidence': None, 'confidence_method': 'unavailable', 'workload_identity_verified': False}
        if stored and stored['override_enabled']:
            result.update({'effective_label': stored['workload_type'], 'effective_source': 'application_operator_label'})
        else:
            instance = self._instance(instance_id)
            values, invalid = set(), False
            for tag in instance.get('Tags', []):
                key, value = tag.get('Key', ''), tag.get('Value', '')
                if key.replace('-', '').replace('_', '').casefold() != 'workloadtype': continue
                value = value.strip().casefold()
                if value not in ('training', 'inference', 'idle'): invalid = True
                else: values.add(value)
            if len(values) == 1 and not invalid:
                result.update({'effective_label': next(iter(values)), 'effective_source': 'EC2_operator_tag'})
            elif len(values) > 1 or invalid:
                result['effective_source'] = 'conflicting_or_invalid_EC2_tags'
        self.last_manual_info = result
        return result

    def save_manual_label(self, instance_id, workload_type, expected_version, actor_id, reason=''):
        if workload_type not in ('training', 'inference', 'idle'): raise ValueError('Choose training, inference or idle')
        return self._write_manual_label(instance_id, workload_type, expected_version, actor_id, reason)

    def clear_manual_label(self, instance_id, expected_version, actor_id, reason=''):
        # Retain the version pointer so a cleared label cannot reset optimistic concurrency.
        return self._write_manual_label(instance_id, None, expected_version, actor_id, reason)

    def _write_manual_label(self, instance_id, workload_type, expected_version, actor_id, reason):
        self._identity(instance_id)
        if isinstance(expected_version, bool) or not isinstance(expected_version, int) or not 0 <= expected_version < 2**53-1:
            raise ValueError('expected_version must come from the current manual-label read')
        if not isinstance(actor_id, str) or not actor_id: raise ValueError('Authenticated actor is required')
        if not isinstance(reason, str) or len(reason) > 1024: raise ValueError('Reason must be text of at most 1024 characters')
        stored = self._stored_override(instance_id)
        if expected_version != (stored['version'] if stored else 0): raise ClassificationConflict('Manual label changed; refresh before saving')
        self._instance(instance_id)  # Resolve current account/region identity before writing metadata.
        now = datetime.now(UTC).isoformat()
        item = {'instance_id': instance_id, 'date': 'MANUAL', 'schema_version': 2, 'version': expected_version+1,
            'kind': 'manual_workload_label', 'override_enabled': workload_type is not None, 'workload_type': workload_type,
            'confidence': None, 'confidence_method': 'unavailable', 'reason': reason.strip(),
            'updated_at': now, 'actor_id': actor_id, 'region': self.ec2.meta.region_name,
            'workload_identity_verified': False}
        serializer = TypeSerializer()
        parameters = {'TableName': self.table_name, 'Item': {key: serializer.serialize(value) for key, value in item.items()},
            'ConditionExpression': 'attribute_not_exists(instance_id)' if expected_version == 0 else '#version = :version AND schema_version = :schema'}
        if expected_version:
            parameters['ExpressionAttributeNames'] = {'#version': 'version'}
            parameters['ExpressionAttributeValues'] = {':version': {'N': str(expected_version)}, ':schema': {'N': '2'}}
        try:
            history = dict(item, date=f'HISTORY#{expected_version+1:016d}', kind='manual_workload_label_change',
                previous_version=expected_version, operation='set' if workload_type is not None else 'clear')
            history_put = {'TableName': self.table_name,
                'Item': {key: serializer.serialize(value) for key, value in history.items()},
                'ConditionExpression': 'attribute_not_exists(instance_id)'}
            self._db().transact_write_items(TransactItems=[{'Put': parameters}, {'Put': history_put}])
        except Exception as error:
            response = getattr(error, 'response', {})
            code = response.get('Error', {}).get('Code')
            conditional = code == 'ConditionalCheckFailedException' or (code == 'TransactionCanceledException'
                and any(reason.get('Code') == 'ConditionalCheckFailed' for reason in response.get('CancellationReasons', [])))
            if conditional:
                raise ClassificationConflict('Manual label changed; refresh before saving') from error
            raise ClassificationStoreUnavailable('Manual workload label could not be saved') from error
        return self.read_manual_label(instance_id)

    def read_label_history(self, instance_id, before_version=None):
        """Newest-first bounded retained revisions; legacy history is not fabricated."""
        self._identity(instance_id)
        if before_version is not None and (isinstance(before_version, bool) or not isinstance(before_version, int)
                or not 1 <= before_version <= 2**53-1):
            raise ValueError('before_version must be a positive safe integer')
        pointer = self._stored_override(instance_id)
        current_version = pointer['version'] if pointer else 0
        maximum = min(current_version, before_version-1) if before_version is not None else current_version
        result = {'instance_id': instance_id, 'current_pointer_version': current_version,
            'changes': [], 'has_more': False, 'next_before_version': None,
            'history_scope': 'retained_changes_since_atomic_history_implementation',
            'legacy_history_complete': False, 'retention': 'no_ttl_current_source_configuration'}
        if maximum < 1: return result
        try:
            response = self._db().query(TableName=self.table_name,
                KeyConditionExpression='instance_id = :id AND #date BETWEEN :start AND :end',
                ExpressionAttributeNames={'#date': 'date'},
                ExpressionAttributeValues={':id': {'S': instance_id}, ':start': {'S': 'HISTORY#0000000000000001'},
                    ':end': {'S': f'HISTORY#{maximum:016d}'}},
                ConsistentRead=True, ScanIndexForward=False, Limit=20)
            decoder = TypeDeserializer()
            previous = maximum+1
            for encoded in response.get('Items', []):
                item = {key: decoder.deserialize(value) for key, value in encoded.items()}
                raw_version = item.get('version')
                version = int(raw_version)
                enabled = item.get('override_enabled')
                stamp = parse_utc_timestamp(item['updated_at'])
                if (isinstance(raw_version, bool) or raw_version != version or not 1 <= version < previous
                        or item.get('instance_id') != instance_id or item.get('date') != f'HISTORY#{version:016d}'
                        or item.get('kind') != 'manual_workload_label_change' or item.get('schema_version') != 2
                        or item.get('previous_version') != version-1 or not isinstance(enabled, bool)
                        or item.get('operation') != ('set' if enabled else 'clear')
                        or (enabled and item.get('workload_type') not in ('training', 'inference', 'idle'))
                        or not isinstance(item.get('actor_id'), str) or not item['actor_id']
                        or not isinstance(item.get('reason'), str) or len(item['reason']) > 1024
                        or not isinstance(item.get('region'), str)
                        or stamp > datetime.now(UTC)):
                    raise ValueError('Invalid retained declaration change')
                previous = version
                result['changes'].append({'version': version, 'previous_version': version-1,
                    'operation': item['operation'], 'workload_type': item.get('workload_type') if enabled else None,
                    'actor_id': item['actor_id'], 'reason': item['reason'], 'updated_at': stamp.isoformat(),
                    'region': item.get('region'), 'workload_identity_verified': False})
            result['has_more'] = bool(response.get('LastEvaluatedKey'))
            if result['has_more']:
                if not result['changes']: raise ValueError('Empty history continuation')
                result['next_before_version'] = result['changes'][-1]['version']
            return result
        except Exception as error:
            raise ClassificationStoreUnavailable('Declared workload-label history is unavailable') from error

    def get_manual_classification(self, instance_id):
        return self.read_manual_label(instance_id)['effective_label']

    def classify_workload(self, instance_id, start_date, end_date):
        self._identity(instance_id)
        IdleGPUDetector(None)._window(start_date, end_date)
        manual = self.read_manual_label(instance_id)
        pattern = self.get_gpu_utilization_pattern(instance_id, start_date, end_date)
        label = self._pattern_label(pattern)
        return WorkloadClassification(instance_id, manual['effective_label'] or 'unknown', None,
            manual['effective_source'] if manual['effective_label'] else 'utilization_pattern_only',
            statistics.mean(pattern) if pattern else None, pattern, datetime.now(UTC).isoformat(),
            utilization_pattern_label=label, data_quality=self.last_metric_info or {}, manual_label=manual,
            hourly_observations=self.last_hourly_observations)

    def get_gpu_utilization_pattern(self, instance_id, start_date, end_date):
        self._identity(instance_id)
        if self.ec2 is None:
            import boto3
            self.ec2 = boto3.client('ec2')
        if self.cloudwatch is None:
            import boto3
            self.cloudwatch = boto3.client('cloudwatch', region_name=self.ec2.meta.region_name)
        self.last_hourly_observations = []
        detector = IdleGPUDetector(None, cloudwatch_client=self.cloudwatch)
        if self.cloudwatch.meta.region_name != self.ec2.meta.region_name:
            self.last_metric_info = {'status': 'unavailable', 'reason': 'Resource/metric regions differ'}
            return []
        evidence = detector._get_gpu_evidence(instance_id, start_date, end_date)
        start, end = detector._window(start_date, end_date)
        profile = detector._metric_contract()
        self.last_hourly_observations = [{'timestamp': datetime.fromtimestamp(stamp, UTC).isoformat(),
            'maximum_percent': evidence[stamp]} for stamp in sorted(evidence)] if evidence else []
        self.last_metric_info = {'status': 'available' if evidence else 'unavailable',
            'window_start': start.isoformat(), 'window_end': end.isoformat(),
            'region': self.cloudwatch.meta.region_name, 'instance_id': instance_id,
            'metric_contract_status': 'configured' if profile else 'not_configured',
            'metric_namespace': profile['namespace'] if profile else None,
            'metric_name': profile['metric_name'] if profile else None,
            'statistic': 'Maximum', 'period_seconds': 3600, 'unit': 'Percent',
            'expected_hour_count': int((end-start).total_seconds()/3600),
            'observed_hour_count': len(evidence) if evidence is not None else None,
            'basis': 'configured_hourly_all_device_maxima', 'metric_source_verified': False,
            'complete_hourly_coverage': evidence is not None, 'application_workload_verified': False,
            'reason': None if evidence else 'Configured complete GPU metric evidence is unavailable'}
        return [evidence[stamp] for stamp in sorted(evidence)] if evidence else []

    @staticmethod
    def _pattern_label(pattern):
        if not pattern or any(not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100 for value in pattern): return 'unavailable'
        if all(value < 10 for value in pattern): return 'low_hourly_maxima'
        if all(value >= 70 for value in pattern): return 'sustained_high_hourly_maxima'
        return 'mixed_or_midrange_hourly_maxima'

    def apply_classification_rules(self, utilization_pattern):
        return 'unknown', None  # Utilization alone cannot establish training/inference/workload identity.

    def store_classification(self, instance_id, classification):
        raise ValueError('Use versioned manual-label writes; pattern observations are not authoritative labels')
