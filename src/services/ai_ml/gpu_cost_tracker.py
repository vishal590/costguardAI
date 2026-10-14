"""
GPU Cost Tracker for Phase 6: AI/ML Workload Cost Management.

This module retains provider EC2 GPU-family type/usage charge observations.
Aggregate rows do not establish resource identity, device-hours or workload classification.

Requirements: FR-1.1, FR-1.3, FR-1.5, FR-1.6
"""
import logging
from typing import List, Optional
from datetime import datetime, timedelta, UTC
from decimal import Decimal
import math
import re
import hashlib
from dataclasses import dataclass, asdict
from botocore.exceptions import ClientError

from .error_handler import (
    retry_with_exponential_backoff,
    handle_cost_explorer_error,
    validate_minimum_data,
    AIMLError
)

logger = logging.getLogger(__name__)

# GPU instance type patterns
GPU_INSTANCE_PATTERNS = ['p3.', 'p4.', 'p4d.', 'p5.', 'g4.', 'g5.', 'g6.']


@dataclass
class GPUCostData:
    """Daily instance-type/usage-type observations, without resource or device-hour attribution."""
    date: str
    instance_id: Optional[str]
    instance_type: str
    workload_type: str
    cost: float
    gpu_hours: Optional[float]
    cost_per_gpu_hour: Optional[float]
    utilization: Optional[float]
    classification_confidence: Optional[float]
    record_id: Optional[str] = None
    usage_type: Optional[str] = None
    instance_hours: Optional[float] = None
    usage_unit: Optional[str] = None
    currency: str = 'USD'
    is_estimated: Optional[bool] = None
    period_end: Optional[str] = None
    result_scope: str = 'observed_instance_type_usage_costs'
    resource_attribution_verified: bool = False

    def to_dict(self): return asdict(self)


class GPUCostDataUnavailable(AIMLError):
    pass


class GPUWorkloadAttributionUnavailable(AIMLError):
    pass


class GPUCostTracker:
    """
    Tracks EC2 GPU instance costs by workload type.
    
    Requirements: FR-1.1, FR-1.3, FR-1.5, FR-1.6
    """
    
    def __init__(self, dynamodb_client, cost_explorer_client=None):
        """
        Initialize GPU Cost Tracker.
        
        Args:
            dynamodb_client: DynamoDB client for data storage
            cost_explorer_client: Cost Explorer client (optional, will create if not provided)
        """
        self.dynamodb = dynamodb_client
        self.cost_explorer = cost_explorer_client
        self._default_session = None
        
    @retry_with_exponential_backoff(max_retries=3)
    def collect_gpu_costs(self, start_date: str, end_date: str, workload_type: Optional[str] = None,
                          instance_type: Optional[str] = None, boto3_session=None) -> List[GPUCostData]:
        """Read observed GPU-family compute charges without inventing instance/device identity."""
        start, end = datetime.strptime(start_date, '%Y-%m-%d').date(), datetime.strptime(end_date, '%Y-%m-%d').date()
        if start.isoformat() != start_date or end.isoformat() != end_date or not 1 <= (end-start).days <= 31 or end > datetime.now(UTC).date():
            raise ValueError('Use 1-31 completed daily dates with an exclusive end')
        if workload_type not in (None, 'unknown', 'training', 'inference', 'idle'): raise ValueError('Unknown workload filter')
        if workload_type not in (None, 'unknown'):
            raise GPUWorkloadAttributionUnavailable('Instance-type billing does not establish workload attribution')
        if instance_type is not None and (not isinstance(instance_type, str) or not re.fullmatch(r'[gp][0-9][a-z0-9-]*\.[a-z0-9]+', instance_type)):
            raise ValueError('Supply a supported g/p-family instance type')
        import boto3
        client = boto3_session.client('ce') if boto3_session else self.cost_explorer or boto3.client('ce')
        expected = {(start+timedelta(days=offset)).isoformat() for offset in range((end-start).days)}
        request = {'TimePeriod': {'Start': start_date, 'End': end_date}, 'Granularity': 'DAILY',
            'Metrics': ['UnblendedCost', 'UsageQuantity'],
            'Filter': {'Dimensions': {'Key': 'SERVICE', 'Values': ['Amazon Elastic Compute Cloud - Compute']}},
            'GroupBy': [{'Type': 'DIMENSION', 'Key': 'INSTANCE_TYPE'}, {'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'}]}
        rows, flags, seen = {}, {}, set()
        try:
            for page_number in range(100):
                response = client.get_cost_and_usage(**request)
                for period in response.get('ResultsByTime', []):
                    day = period['TimePeriod']['Start']
                    if day not in expected or period['TimePeriod']['End'] != (datetime.fromisoformat(day).date()+timedelta(days=1)).isoformat():
                        raise ValueError('Unexpected provider period')
                    flag = period.get('Estimated')
                    flag = flag if isinstance(flag, bool) else None
                    if day not in flags: flags[day] = flag
                    elif flags[day] is True or flag is True: flags[day] = True
                    elif flags[day] is None or flag is None: flags[day] = None
                    for group in period.get('Groups', []):
                        keys = group['Keys']
                        if not isinstance(keys, list) or len(keys) != 2 or any(not isinstance(key, str) for key in keys): raise ValueError('Invalid cost dimensions')
                        kind, usage = keys
                        if not re.fullmatch(r'[gp][0-9][a-z0-9-]*\.[a-z0-9]+', kind) or instance_type is not None and kind != instance_type: continue
                        metric = group['Metrics']['UnblendedCost']
                        if metric.get('Unit') != 'USD' or isinstance(metric.get('Amount'), bool): raise ValueError('Unsupported cost unit')
                        amount = Decimal(str(metric['Amount']))
                        if not amount.is_finite() or not math.isfinite(float(amount)): raise ValueError('Invalid amount')
                        quantity = group['Metrics'].get('UsageQuantity', {})
                        hours, unit = None, quantity.get('Unit')
                        if unit == 'Hrs' and not isinstance(quantity.get('Amount'), bool):
                            try:
                                value = Decimal(str(quantity.get('Amount')))
                                if value.is_finite() and value >= 0 and math.isfinite(float(value)): hours = float(value)
                            except Exception:
                                pass
                        identity = (day, kind, usage)
                        observation = (amount, hours, unit)
                        if identity in rows and rows[identity] != observation: raise ValueError('Conflicting duplicate observations')
                        rows[identity] = observation
                        if len(rows) > 50000: raise ValueError('Observation row limit exceeded')
                token = response.get('NextPageToken')
                if not token: break
                if token in seen: raise ValueError('Repeated provider token')
                seen.add(token)
                request['NextPageToken'] = token
            else: raise ValueError('Provider page limit exceeded')
        except Exception as error:
            raise GPUCostDataUnavailable('GPU-family provider cost observations are unavailable') from error
        costs = []
        for (day, kind, usage), (amount, hours, unit) in sorted(rows.items()):
            key = hashlib.sha256(f'{day}|{kind}|{usage}'.encode()).hexdigest()
            costs.append(GPUCostData(day, None, kind, 'unknown', float(amount), None, None, None, None,
                'aggregate:'+key, usage, hours, unit, 'USD', flags.get(day),
                (datetime.fromisoformat(day).date()+timedelta(days=1)).isoformat()))
        observed_dates = {row.date for row in costs}
        total = float(sum((value[0] for value in rows.values()), Decimal('0'))) if rows else None
        if total is not None and not math.isfinite(total): raise GPUCostDataUnavailable('Cost total is unavailable')
        self.last_observation_report = {'status': 'observed' if rows else 'no_observations',
            'metric': 'UnblendedCost', 'currency': 'USD' if rows else None, 'observed_total': total,
            'missing_dates': sorted(expected-observed_dates), 'complete_date_coverage': expected == observed_dates,
            'estimated_dates': sorted(day for day in observed_dates if flags.get(day) is True),
            'unknown_estimate_dates': sorted(day for day in observed_dates if flags.get(day) is None),
            'invoice_coverage_verified': False, 'resource_attribution_verified': False,
            'device_hours_available': False, 'workload_attribution_status': 'unavailable',
            'usage_scope': 'provider_Hrs_quantity_per_usage_type_is_not_device_hours',
            'service_filter': 'Amazon Elastic Compute Cloud - Compute', 'observed_at': datetime.now(UTC).isoformat()}
        return costs

    def filter_gpu_instances(self, cost_data: List[dict]) -> List[dict]:
        """
        Filter cost data to only GPU instance types.
        
        Args:
            cost_data: Raw cost data from Cost Explorer
            
        Returns:
            Filtered list containing only GPU instances
            
        Requirements: FR-1.1
        """
        gpu_costs = []
        for item in cost_data:
            instance_type = item.get('instance_type', '')
            if re.fullmatch(r'[gp][0-9][a-z0-9-]*\.[a-z0-9]+', instance_type):
                gpu_costs.append(item)
        
        logger.info(f"Filtered {len(gpu_costs)} GPU instances from {len(cost_data)} total instances")
        return gpu_costs
    
    def calculate_cost_per_gpu_hour(self, cost: float, gpu_hours: float) -> float:
        """
        Calculate cost per GPU hour for a workload.
        
        Args:
            cost: Total cost
            gpu_hours: Total GPU hours
            
        Returns:
            Cost per GPU hour
            
        Requirements: FR-1.3
        """
        if isinstance(gpu_hours, bool) or not isinstance(gpu_hours, (int, float)) or not math.isfinite(gpu_hours) or gpu_hours <= 0: return None
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost): return None
        return cost/gpu_hours
    
    def identify_idle_gpus(self, utilization_data: List[dict], threshold: float = 10.0) -> List[str]:
        """
        Identify GPU instances with utilization below threshold.
        
        Args:
            utilization_data: List of GPU utilization data
            threshold: Utilization threshold percentage (default: 10%)
            
        Returns:
            List of idle GPU instance IDs
            
        Requirements: FR-1.5
        """
        idle_gpus = []
        for item in utilization_data:
            value = item.get('utilization')
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value < threshold and item.get('instance_id'):
                idle_gpus.append(item.get('instance_id'))
        
        logger.info(f"Identified {len(idle_gpus)} idle GPUs (threshold: {threshold}%)")
        return idle_gpus
