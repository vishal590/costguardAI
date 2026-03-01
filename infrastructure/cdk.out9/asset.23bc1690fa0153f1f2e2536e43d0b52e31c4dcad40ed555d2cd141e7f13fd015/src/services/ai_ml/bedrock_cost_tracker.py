"""
Bedrock Cost Tracker Service

Tracks Bedrock model invocation costs, calculates cost per invocation,
tracks token usage, and recommends cost-optimized models.

Requirements: FR-7.1, FR-7.2, FR-7.3, FR-7.4, FR-7.6
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
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
        """
        Track Bedrock costs by model.
        
        Args:
            start_date: Start date for cost tracking
            end_date: End date for cost tracking
            model_id: Optional model ID filter
            
        Returns:
            List of BedrockCosts by model
            
        Requirements: FR-7.1, FR-7.2
        """
        # Try to get cached data first
        cache_data = None
        if self.cache_manager:
            cache_key = f"bedrock_costs_{start_date.strftime('%Y-%m-%d')}_{end_date.strftime('%Y-%m-%d')}_{model_id or 'all'}"
            cache_data = self.cache_manager.get(cache_key)
            if cache_data:
                return cache_data
        
        # Get Bedrock costs from Cost Explorer
        filters = {
            'Dimensions': {
                'Key': 'SERVICE',
                'Values': ['Amazon Bedrock']
            }
        }
        
        try:
            response = self.cost_explorer.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Granularity='DAILY',
                Metrics=['UnblendedCost'],
                Filter=filters,
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'}
                ]
            )
        except ClientError as e:
            # Handle Cost Explorer errors with fallback to cached data
            error_result = handle_cost_explorer_error(e, cache_data)
            if 'data' in error_result:
                return error_result['data']
            raise
        
        # Parse costs by model
        model_costs = {}
        
        for result in response.get('ResultsByTime', []):
            for group in result.get('Groups', []):
                usage_type = group['Keys'][0]
                cost = float(group['Metrics']['UnblendedCost']['Amount'])
                
                # Extract model from usage type (e.g., "ModelInvocation-Claude")
                if 'ModelInvocation' in usage_type:
                    model = self._extract_model_from_usage_type(usage_type)
                    
                    if model_id and model != model_id:
                        continue
                    
                    if model not in model_costs:
                        model_costs[model] = {
                            'cost': 0.0,
                            'invocations': 0,
                            'input_tokens': 0,
                            'output_tokens': 0
                        }
                    
                    model_costs[model]['cost'] += cost
        
        # Get invocation and token metrics from CloudWatch
        for model in model_costs.keys():
            metrics = self._get_model_metrics(model, start_date, end_date)
            model_costs[model]['invocations'] = metrics['invocations']
            model_costs[model]['input_tokens'] = metrics['input_tokens']
            model_costs[model]['output_tokens'] = metrics['output_tokens']
        
        # Build response
        bedrock_costs = []
        for model, data in model_costs.items():
            cost_per_invocation = (
                data['cost'] / data['invocations'] 
                if data['invocations'] > 0 else 0.0
            )
            
            bedrock_costs.append(BedrockCosts(
                date=start_date,
                model_id=model,
                invocations=data['invocations'],
                input_tokens=data['input_tokens'],
                output_tokens=data['output_tokens'],
                total_cost=data['cost'],
                cost_per_invocation=cost_per_invocation
            ))
        
        return bedrock_costs

    
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
        costs = self.track_bedrock_costs(start_date, end_date, model_id)
        
        if not costs:
            return 0.0
        
        return costs[0].cost_per_invocation
    
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
        
        return {
            'input_tokens': metrics['input_tokens'],
            'output_tokens': metrics['output_tokens'],
            'total_tokens': metrics['input_tokens'] + metrics['output_tokens']
        }
    
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
        
        # Get alternative models
        alternatives = self._get_alternative_models(current_model)
        
        for alt_model in alternatives:
            alt_pricing = self._get_model_pricing(alt_model)
            
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

    
    def _extract_model_from_usage_type(self, usage_type: str) -> str:
        """Extract model name from usage type string"""
        # Usage types like "ModelInvocation-Claude-v2" or "ModelInvocation-Titan"
        if 'Claude' in usage_type:
            return 'anthropic.claude-v2'
        elif 'Titan' in usage_type:
            return 'amazon.titan-text-express-v1'
        elif 'Llama' in usage_type:
            return 'meta.llama2-13b-chat-v1'
        elif 'Jurassic' in usage_type:
            return 'ai21.j2-ultra-v1'
        else:
            return 'unknown'
    
    def _get_model_metrics(self, model_id: str, start_date: datetime, 
                          end_date: datetime) -> Dict[str, int]:
        """Get invocation and token metrics from CloudWatch"""
        try:
            # Get invocation count
            invocations_response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/Bedrock',
                MetricName='Invocations',
                Dimensions=[
                    {'Name': 'ModelId', 'Value': model_id}
                ],
                StartTime=start_date,
                EndTime=end_date,
                Period=86400,  # Daily
                Statistics=['Sum']
            )
            
            invocations = 0
            if invocations_response['Datapoints']:
                invocations = sum(dp['Sum'] for dp in invocations_response['Datapoints'])
            
            # Get token counts (estimated from invocations)
            # Typical: 1000 input tokens, 500 output tokens per invocation
            input_tokens = int(invocations * 1000)
            output_tokens = int(invocations * 500)
            
            return {
                'invocations': int(invocations),
                'input_tokens': input_tokens,
                'output_tokens': output_tokens
            }
        except ClientError as e:
            # Handle CloudWatch errors - return defaults
            error_result = handle_bedrock_error(e, continue_on_error=True)
            if error_result:
                # Log error but continue with defaults
                return {
                    'invocations': 0,
                    'input_tokens': 0,
                    'output_tokens': 0
                }
            raise
        except Exception:
            # Return defaults if metrics unavailable
            return {
                'invocations': 0,
                'input_tokens': 0,
                'output_tokens': 0
            }
    
    def _get_model_pricing(self, model_id: str) -> Dict[str, float]:
        """Get pricing for a Bedrock model"""
        # Pricing per 1000 tokens (approximate as of 2024)
        pricing_map = {
            'anthropic.claude-v2': {
                'cost_per_1k_tokens': 0.01102,  # Average of input/output
                'input_cost_per_1k': 0.00800,
                'output_cost_per_1k': 0.02400
            },
            'anthropic.claude-instant-v1': {
                'cost_per_1k_tokens': 0.00163,
                'input_cost_per_1k': 0.00080,
                'output_cost_per_1k': 0.00240
            },
            'amazon.titan-text-express-v1': {
                'cost_per_1k_tokens': 0.00020,
                'input_cost_per_1k': 0.00020,
                'output_cost_per_1k': 0.00060
            },
            'meta.llama2-13b-chat-v1': {
                'cost_per_1k_tokens': 0.00075,
                'input_cost_per_1k': 0.00075,
                'output_cost_per_1k': 0.00100
            },
            'ai21.j2-ultra-v1': {
                'cost_per_1k_tokens': 0.01880,
                'input_cost_per_1k': 0.01880,
                'output_cost_per_1k': 0.01880
            }
        }
        
        return pricing_map.get(model_id, {
            'cost_per_1k_tokens': 0.01,
            'input_cost_per_1k': 0.01,
            'output_cost_per_1k': 0.01
        })
    
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
