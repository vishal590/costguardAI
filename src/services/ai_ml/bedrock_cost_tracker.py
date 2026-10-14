"""
Bedrock Cost Tracker Service

Tracks Bedrock model invocation costs, calculates cost per invocation,
tracks token usage, and recommends cost-optimized models.

Requirements: FR-7.1, FR-7.2, FR-7.3, FR-7.4, FR-7.6
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
import math
from typing import List, Dict, Optional
import boto3
from decimal import Decimal
from botocore.exceptions import ClientError

from .error_handler import (
    retry_with_exponential_backoff,
    handle_cost_explorer_error,
    handle_bedrock_error,
    validate_minimum_data,
    AIMLError,
    DataNotFoundError
)


@dataclass
class BedrockCosts:
    """Bedrock costs by model"""
    date: datetime
    model_id: str
    invocations: int
    input_tokens: int
    output_tokens: int
    total_cost: float
    cost_per_invocation: float


@dataclass
class ModelRecommendation:
    """Model recommendation for cost optimization"""
    current_model: str
    recommended_model: str
    current_cost_per_1k_tokens: float
    recommended_cost_per_1k_tokens: float
    savings_percent: float
    reason: str


class BedrockAttributionUnavailable(AIMLError):
    """Service usage labels cannot establish model-attributed billing."""


class BedrockCostTracker:
    """
    Tracks Bedrock model invocation costs.
    
    Responsibilities:
    - Track Bedrock invocation costs
    - Calculate cost per invocation
    - Track token usage
    - Recommend cost-optimized models
    """
    
    def __init__(self, cost_explorer_client=None, bedrock_client=None, 
                 cloudwatch_client=None, cache_manager=None):
        """Initialize Bedrock cost tracker with AWS clients"""
        self.cost_explorer = cost_explorer_client or boto3.client('ce')
        self.bedrock = bedrock_client or boto3.client('bedrock-runtime')
        self.cloudwatch = cloudwatch_client or boto3.client('cloudwatch')
        self.cache_manager = cache_manager


    
    @retry_with_exponential_backoff(max_retries=3)
    def track_bedrock_costs(self, start_date: datetime, end_date: datetime,
                           model_id: Optional[str] = None) -> List[BedrockCosts]:
        """Retain observed service costs without inventing model-level rows."""
        from .observed_service_costs import observe_service_costs
        if model_id: raise BedrockAttributionUnavailable('Model-attributed billing is unavailable from service usage-type labels')
        self.last_cost_report = observe_service_costs(self.cost_explorer, 'Amazon Bedrock', start_date, end_date)
        self.last_cost_report.update({'data_contract': 'bedrock_observed_v2', 'model_attribution_status': 'unavailable',
            'total_models': None, 'models': [], 'total_invocations': None, 'total_input_tokens': None,
            'total_output_tokens': None, 'average_cost_per_invocation': None})
        return []  # No verified model billing identities are present in this source.

    def calculate_cost_per_invocation(self, model_id: str, start_date: datetime, 
                                      end_date: datetime) -> float:
        """
        Calculate cost per invocation for a model.
        
        Args:
            model_id: Bedrock model ID
            start_date: Start date
            end_date: End date
            
        Returns:
            Cost per invocation in USD
            
        Requirements: FR-7.3
        """
        raise BedrockAttributionUnavailable('Model-attributed charges are unavailable; no cost-per-invocation ratio can be established')

    def track_token_usage(self, model_id: str, start_date: datetime, 
                         end_date: datetime) -> Dict[str, int]:
        """
        Track input and output token counts.
        
        Args:
            model_id: Bedrock model ID
            start_date: Start date
            end_date: End date
            
        Returns:
            Dict with input_tokens and output_tokens
            
        Requirements: FR-7.4
        """
        metrics = self._get_model_metrics(model_id, start_date, end_date)
        metrics['total_tokens'] = metrics['input_tokens']+metrics['output_tokens'] if metrics['input_tokens'] is not None and metrics['output_tokens'] is not None else None
        return metrics

    def recommend_cost_optimized_models(self, current_model: str, 
                                       usage_pattern: Dict) -> List[ModelRecommendation]:
        """
        Recommend cost-optimized models based on usage patterns.
        
        Args:
            current_model: Current model being used
            usage_pattern: Dict with usage characteristics
            
        Returns:
            List of model recommendations sorted by savings
            
        Requirements: FR-7.6
        """
        recommendations = []
        
        # Get current model pricing
        current_pricing = self._get_model_pricing(current_model)
        if current_pricing is None: return []
        
        # Get alternative models
        alternatives = self._get_alternative_models(current_model)
        
        for alt_model in alternatives:
            alt_pricing = self._get_model_pricing(alt_model)
            if alt_pricing is None: continue
            
            # Calculate savings
            current_cost_per_1k = current_pricing['cost_per_1k_tokens']
            alt_cost_per_1k = alt_pricing['cost_per_1k_tokens']
            
            if alt_cost_per_1k < current_cost_per_1k:
                savings_percent = (
                    (current_cost_per_1k - alt_cost_per_1k) / current_cost_per_1k * 100
                )
                
                reason = self._get_recommendation_reason(
                    current_model, alt_model, usage_pattern
                )
                
                recommendations.append(ModelRecommendation(
                    current_model=current_model,
                    recommended_model=alt_model,
                    current_cost_per_1k_tokens=current_cost_per_1k,
                    recommended_cost_per_1k_tokens=alt_cost_per_1k,
                    savings_percent=savings_percent,
                    reason=reason
                ))
        
        # Sort by savings (highest first)
        recommendations.sort(key=lambda x: x.savings_percent, reverse=True)
        
        return recommendations

    
    def _extract_model_from_usage_type(self, usage_type: str) -> Optional[str]:
        """A billing usage label does not establish a ModelId."""
        return None

    def _get_model_metrics(self, model_id: str, start_date: datetime, end_date: datetime) -> Dict:
        """Read actual runtime invocation/token counters; missing days remain unknown."""
        from ..time_values import parse_utc_timestamp
        if not isinstance(model_id, str) or not model_id or len(model_id) > 2048 or any(character.isspace() for character in model_id):
            raise ValueError('Supply one explicit model ID of at most 2048 characters')
        start, end = start_date.date(), end_date.date()
        days = (end-start).days
        if not 1 <= days <= 31 or end > datetime.now(UTC).date(): raise ValueError('Use 1-31 completed daily dates with an exclusive end')
        start_time = datetime.combine(start, datetime.min.time(), UTC)
        end_time = datetime.combine(end, datetime.min.time(), UTC)
        expected = {int((start_time+timedelta(days=offset)).timestamp()) for offset in range(days)}
        result = {'invocations': None, 'input_tokens': None, 'output_tokens': None, 'metric_observations': {},
                  'namespace': 'AWS/Bedrock', 'dimension': {'ModelId': model_id},
                  'region': getattr(getattr(self.cloudwatch, 'meta', None), 'region_name', None),
                  'billing_attribution_verified': False, 'cached_tokens_included': False,
                  'scope': 'runtime_model_id_daily_metric_observations'}
        for field, metric in [('invocations', 'Invocations'), ('input_tokens', 'InputTokenCount'), ('output_tokens', 'OutputTokenCount')]:
            points = {}
            try:
                response = self.cloudwatch.get_metric_statistics(Namespace='AWS/Bedrock', MetricName=metric,
                    Dimensions=[{'Name': 'ModelId', 'Value': model_id}], StartTime=start_time, EndTime=end_time,
                    Period=86400, Statistics=['Sum', 'SampleCount'], Unit='Count')
                for point in response.get('Datapoints', []):
                    stamp = int(parse_utc_timestamp(point['Timestamp']).timestamp())
                    amount, samples = float(point['Sum']), float(point['SampleCount'])
                    if (stamp not in expected or not math.isfinite(amount) or amount < 0 or amount > 2**53
                            or amount != int(amount) or not math.isfinite(samples) or samples <= 0): raise ValueError('Invalid metric count')
                    if stamp in points and points[stamp] != int(amount): raise ValueError('Conflicting metric days')
                    points[stamp] = int(amount)
                total = sum(points.values()) if points else None
                if total is not None and total > 2**53: raise ValueError('Counter precision is unavailable')
                complete = set(points) == expected
                result[field] = total if complete else None
                result['metric_observations'][field] = {'status': 'available' if complete else 'partial' if points else 'unavailable',
                    'observed_total': total, 'complete_daily_coverage': complete,
                    'missing_dates': [datetime.fromtimestamp(stamp, UTC).date().isoformat() for stamp in sorted(expected-set(points))]}
            except Exception:
                result['metric_observations'][field] = {'status': 'unavailable', 'observed_total': None,
                    'complete_daily_coverage': False, 'reason': 'Metric observations could not be read or validated',
                    'missing_dates': [datetime.fromtimestamp(stamp, UTC).date().isoformat() for stamp in sorted(expected)]}
        return result

    def _get_model_pricing(self, model_id: str) -> Optional[Dict[str, float]]:
        """Unknown model/region/tier/profile pricing has no monetary fallback."""
        return None

    def _get_alternative_models(self, current_model: str) -> List[str]:
        """Get alternative models for recommendations"""
        # Map models to alternatives
        alternatives_map = {
            'anthropic.claude-v2': [
                'anthropic.claude-instant-v1',
                'amazon.titan-text-express-v1',
                'meta.llama2-13b-chat-v1'
            ],
            'anthropic.claude-instant-v1': [
                'amazon.titan-text-express-v1',
                'meta.llama2-13b-chat-v1'
            ],
            'amazon.titan-text-express-v1': [
                'meta.llama2-13b-chat-v1'
            ],
            'meta.llama2-13b-chat-v1': [
                'amazon.titan-text-express-v1'
            ],
            'ai21.j2-ultra-v1': [
                'anthropic.claude-instant-v1',
                'amazon.titan-text-express-v1'
            ]
        }
        
        return alternatives_map.get(current_model, [])
    
    def _get_recommendation_reason(self, current_model: str, recommended_model: str, 
                                  usage_pattern: Dict) -> str:
        """Generate explanation for recommendation"""
        if 'titan' in recommended_model.lower():
            return "Amazon Titan offers excellent price/performance for general text tasks"
        elif 'claude-instant' in recommended_model.lower():
            return "Claude Instant provides fast responses at lower cost for simpler tasks"
        elif 'llama' in recommended_model.lower():
            return "Llama 2 offers good performance at competitive pricing"
        else:
            return "Lower-cost alternative with similar capabilities"
