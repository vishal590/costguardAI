"""Read-only GPU review previews and unverified historical action observations."""
from dataclasses import dataclass, asdict, field
from datetime import datetime, UTC
from decimal import Decimal
from typing import List, Dict, Any, Optional
import math
import os
from boto3.dynamodb.types import TypeDeserializer
from ..time_values import parse_utc_timestamp


class GPUActionHistoryUnavailable(RuntimeError):
    pass


@dataclass
class GPUPreventionAction:
    action_id: str
    instance_id: str
    instance_type: str
    action_type: str
    reason: str
    idle_hours: float
    cost_saved: Optional[float]
    timestamp: str
    status: str

    def to_dict(self): return asdict(self)


@dataclass
class GPUCostSavings:
    period_start: str
    period_end: str
    total_savings: Optional[float] = None
    actions_count: Optional[int] = None
    instances_stopped: Optional[int] = None
    instances_terminated: Optional[int] = None
    avg_idle_hours: Optional[float] = None
    breakdown_by_instance_type: Optional[Dict] = None
    data_contract: str = 'gpu_action_observations_v2'
    savings_status: str = 'unavailable'
    resource_outcomes_verified: bool = False
    result_scope: str = 'returned_unverified_action_records'
    action_records: List[Dict] = field(default_factory=list)
    read_metadata: Dict = field(default_factory=dict)

    def to_dict(self): return asdict(self)


class GPUPreventionIntegration:
    def __init__(self, idle_gpu_detector, prevention_engine, dynamodb_client, ec2_client=None):
        self.idle_gpu_detector, self.prevention_engine = idle_gpu_detector, prevention_engine
        self.dynamodb, self.ec2 = dynamodb_client, ec2_client
        self.actions_table = os.environ.get('GPU_PREVENTION_ACTIONS_TABLE', '')

    def run_gpu_prevention_cycle(self, start_date: str, end_date: str, threshold: float = 10.0,
                                 dry_run: bool = True) -> Dict[str, Any]:
        if not isinstance(dry_run, bool): raise ValueError('dry_run must be boolean')
        if not dry_run: raise ValueError('GPU resource execution is unavailable; only review previews are supported')
        candidates = self.idle_gpu_detector.identify_idle_gpus(start_date, end_date, threshold)
        return {'success': True, 'data_contract': 'gpu_review_preview_v2', 'dry_run': True,
                'execution_enabled': False, 'actions_planned': 0, 'actions_executed': 0,
                'total_savings': None, 'review_candidate_count': len(candidates),
                'review_candidates': [candidate.to_dict() for candidate in candidates],
                'observation_report': self.idle_gpu_detector.last_observation_report,
                'workload_inactivity_verified': False}

    def get_gpu_cost_savings(self, start_date: str, end_date: str) -> GPUCostSavings:
        """Read retained records without converting projections/status labels into savings."""
        start = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=UTC)
        end = datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=UTC)
        if start.strftime('%Y-%m-%d') != start_date or end.strftime('%Y-%m-%d') != end_date:
            raise ValueError('Use YYYY-MM-DD dates')
        if not 1 <= (end-start).days <= 31 or end.date() > datetime.now(UTC).date():
            raise ValueError('Use 1-31 completed daily dates with an exclusive end')
        if not self.actions_table or self.dynamodb is None:
            raise GPUActionHistoryUnavailable('Historical GPU action storage is not configured')
        decoder = TypeDeserializer()
        request = {'TableName': self.actions_table, 'ConsistentRead': True, 'Limit': 500}
        rows, seen_tokens, identities = [], set(), set()
        scanned, invalid, has_more = 0, 0, False
        try:
            for page_number in range(20):
                response = self.dynamodb.scan(**request)
                for encoded in response.get('Items', []):
                    scanned += 1
                    try:
                        item = {key: decoder.deserialize(value) for key, value in encoded.items()}
                        stamp = parse_utc_timestamp(item.get('timestamp'))
                        if not start <= stamp < end: continue
                        identity = item.get('action_id')
                        if not isinstance(identity, str) or not identity or len(identity) > 256: raise ValueError('Invalid action identity')
                        if identity in identities: continue
                        identities.add(identity)
                        def text(key):
                            value = item.get(key)
                            return value if isinstance(value, str) and len(value) <= 2048 else None
                        projected = item.get('cost_saved')
                        if isinstance(projected, bool) or not isinstance(projected, (Decimal, int, float)):
                            projected = None
                        elif not math.isfinite(float(projected)) or projected < 0:
                            projected = None
                        else: projected = float(projected)
                        rows.append({'action_id': identity, 'instance_id': text('instance_id'), 'instance_type': text('instance_type'),
                            'action_type': text('action_type'), 'recorded_status': text('status'), 'reason': text('reason'),
                            'timestamp': stamp.isoformat(), 'timestamp_epoch': stamp.timestamp(),
                            'recorded_projected_savings': projected, 'projection_status': 'legacy_unverified',
                            'resource_outcome_verification': 'unverified'})
                    except Exception:
                        invalid += 1
                token = response.get('LastEvaluatedKey')
                if not token: break
                token_key = repr(token)
                if token_key in seen_tokens: raise ValueError('Repeated action page token')
                seen_tokens.add(token_key)
                request['ExclusiveStartKey'] = token
            else:
                has_more = bool(token)
        except Exception as error:
            raise GPUActionHistoryUnavailable('Historical GPU action records are unavailable') from error
        rows.sort(key=lambda row: (row['timestamp_epoch'], row['action_id']), reverse=True)
        matched = len(rows)
        selected = rows[:100]
        return GPUCostSavings(start_date, end_date, actions_count=len(selected), action_records=selected,
            read_metadata={'record_limit': 100, 'scan_page_limit': 20, 'scanned_records': scanned,
                'matched_observed_records': matched, 'invalid_record_count': invalid,
                'has_more': has_more or matched > len(selected), 'scan_exhausted': not has_more,
                'date_scope_verified_for_invalid_records': False, 'ordering': 'timestamp_descending_within_scanned_selection',
                'consistency': 'live_paginated_read_not_atomic_snapshot'})

    def _execute_gpu_prevention_actions(self, planned_actions):
        raise RuntimeError('GPU execution requires a separate verified safety/audit/approval implementation')

    def _stop_instance(self, instance_id): raise RuntimeError('GPU resource execution is unavailable')
    def _terminate_instance(self, instance_id): raise RuntimeError('GPU resource execution is unavailable')
    def _store_prevention_actions(self, actions): raise RuntimeError('Review previews do not persist execution records')
    def _update_savings_tracking(self, actions): raise RuntimeError('Projected values are not verified savings')
