"""Explicit runtime request observations with unavailable endpoint-attributed unit costs."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, List, Tuple
import math
from .inference_counter import observe_counter


@dataclass
class InferenceCosts:
    compute_cost: Optional[float]
    api_cost: Optional[float]
    data_transfer_cost: Optional[float]

    @property
    def total_cost(self):
        values = (self.compute_cost, self.api_cost, self.data_transfer_cost)
        return sum(values) if all(value is not None for value in values) else None


@dataclass
class CostPerInference:
    model: Optional[str]
    endpoint: str
    date: datetime
    total_requests: Optional[int]
    total_cost: Optional[float]
    cost_per_inference: Optional[float]
    compute_cost: Optional[float]
    api_cost: Optional[float]
    data_transfer_cost: Optional[float]
    source: Optional[str] = None
    cost_attribution_status: str = 'unavailable'
    data_quality: Dict = field(default_factory=dict)


@dataclass
class CostTrend:
    date: datetime
    cost_per_inference: Optional[float]
    total_requests: Optional[int]
    total_cost: Optional[float]
    observation_status: str = 'unavailable'


class CostPerInferenceCalculator:
    def __init__(self, cost_explorer_client=None, cloudwatch_client=None,
                 dynamodb_client=None, api_gateway_client=None):
        self.cost_explorer, self.cloudwatch = cost_explorer_client, cloudwatch_client
        self.dynamodb, self.api_gateway = dynamodb_client, api_gateway_client
        self.last_counter_observation = None

    def _counter(self, endpoint, start_date, end_date, *, source, variant=None, stage=None):
        if self.cloudwatch is None:
            import boto3
            self.cloudwatch = boto3.client('cloudwatch')
        self.last_counter_observation = observe_counter(self.cloudwatch, source, endpoint, start_date, end_date, variant=variant, stage=stage)
        return self.last_counter_observation

    def calculate_cost_per_inference(self, model, endpoint, start_date, end_date, *, source=None, variant=None, stage=None):
        counter = self._counter(endpoint, start_date, end_date, source=source, variant=variant, stage=stage)
        return CostPerInference(model, endpoint, start_date, counter['total_count'], None, None, None, None, None,
                                source=source, data_quality=counter)

    def get_inference_request_count(self, endpoint, start_date, end_date, *, source=None, variant=None, stage=None):
        return self._counter(endpoint, start_date, end_date, source=source, variant=variant, stage=stage)['total_count']

    def get_inference_costs(self, endpoint, start_date, end_date):
        return InferenceCosts(None, None, None)

    def track_cost_trends(self, model, endpoint, days=30, *, source=None, variant=None, stage=None) -> List[CostTrend]:
        if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 31: raise ValueError('Select 1-31 completed days')
        end = datetime.combine(datetime.now(UTC).date(), datetime.min.time(), UTC)
        counter = self._counter(endpoint, end-timedelta(days=days), end, source=source, variant=variant, stage=stage)
        return [CostTrend(datetime.fromisoformat(row['date']).replace(tzinfo=UTC), None, row['count'], None,
                          'available' if row['count'] is not None else 'unavailable') for row in counter['daily']]

    def check_cost_threshold(self, model, endpoint, threshold, start_date, end_date, **counter_scope):
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or threshold <= 0:
            raise ValueError('Cost threshold must be a positive finite amount')
        return None, None  # Unattributed account costs cannot establish an endpoint threshold breach.

    def _get_compute_costs(self, *args): return None
    def _get_api_costs(self, *args): return None
    def _get_data_transfer_costs(self, *args): return None
