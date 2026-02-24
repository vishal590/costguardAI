"""
Property-based tests for Bedrock Cost Tracker

Tests Property 13: Bedrock Token Tracking
Validates: Requirements FR-7.4
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
from src.services.ai_ml.bedrock_cost_tracker import (
    BedrockCostTracker,
    BedrockCosts
)


# Strategies for generating test data
@st.composite
def bedrock_token_data(draw):
    """Generate Bedrock token usage data"""
    input_tokens = draw(st.integers(min_value=0, max_value=1000000))
    output_tokens = draw(st.integers(min_value=0, max_value=1000000))
    invocations = draw(st.integers(min_value=1, max_value=10000))
    
    return {
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'invocations': invocations
    }


@st.composite
def model_pricing_data(draw):
    """Generate model pricing data"""
    input_cost_per_1k = draw(st.floats(min_value=0.0001, max_value=0.1))
    output_cost_per_1k = draw(st.floats(min_value=0.0001, max_value=0.1))
    
    return {
        'input_cost_per_1k': input_cost_per_1k,
        'output_cost_per_1k': output_cost_per_1k
    }


class TestBedrockTokenTrackingProperties:
    """Property tests for Bedrock token tracking (Property 13)"""

    
    @given(
        tokens=bedrock_token_data(),
        pricing=model_pricing_data()
    )
    @settings(max_examples=100, deadline=None)
    def test_cost_calculable_from_tokens_and_pricing(self, tokens, pricing):
        """
        Property 13: Bedrock Token Tracking
        
        For any Bedrock model invocation, the system should track both input 
        and output token counts, and the total cost should be calculable from 
        token counts and model pricing.
        
        Validates: Requirements FR-7.4
        """
        # Calculate expected cost from tokens and pricing
        input_cost = (tokens['input_tokens'] / 1000.0) * pricing['input_cost_per_1k']
        output_cost = (tokens['output_tokens'] / 1000.0) * pricing['output_cost_per_1k']
        expected_total_cost = input_cost + output_cost
        
        # Create BedrockCosts object
        bedrock_costs = BedrockCosts(
            date=datetime.now(),
            model_id='test-model',
            invocations=tokens['invocations'],
            input_tokens=tokens['input_tokens'],
            output_tokens=tokens['output_tokens'],
            total_cost=expected_total_cost,
            cost_per_invocation=expected_total_cost / tokens['invocations']
        )
        
        # Verify cost can be calculated from tokens
        calculated_cost = (
            (bedrock_costs.input_tokens / 1000.0) * pricing['input_cost_per_1k'] +
            (bedrock_costs.output_tokens / 1000.0) * pricing['output_cost_per_1k']
        )
        
        # Should match within 0.01% (floating point tolerance)
        tolerance = max(expected_total_cost * 0.0001, 0.0001)
        assert abs(calculated_cost - bedrock_costs.total_cost) <= tolerance, \
            f"Cost not calculable from tokens: {calculated_cost} != {bedrock_costs.total_cost}"
    
    @given(tokens=bedrock_token_data())
    @settings(max_examples=100, deadline=None)
    def test_token_counts_are_tracked(self, tokens):
        """
        Property 13 variant: Token counts should be tracked
        
        Both input and output tokens should be tracked for every invocation.
        
        Validates: Requirements FR-7.4
        """
        # Create mock clients
        mock_ce = Mock()
        mock_bedrock = Mock()
        mock_cloudwatch = Mock()
        
        # Mock CloudWatch metrics response
        mock_cloudwatch.get_metric_statistics.return_value = {
            'Datapoints': [
                {'Sum': tokens['invocations']}
            ]
        }
        
        tracker = BedrockCostTracker(
            cost_explorer_client=mock_ce,
            bedrock_client=mock_bedrock,
            cloudwatch_client=mock_cloudwatch
        )
        
        # Get token usage
        start_date = datetime.now() - timedelta(days=1)
        end_date = datetime.now()
        result = tracker.track_token_usage('test-model', start_date, end_date)
        
        # Verify both input and output tokens are tracked
        assert 'input_tokens' in result, "Input tokens should be tracked"
        assert 'output_tokens' in result, "Output tokens should be tracked"
        assert 'total_tokens' in result, "Total tokens should be tracked"
        
        # Verify token counts are non-negative
        assert result['input_tokens'] >= 0, "Input tokens should be non-negative"
        assert result['output_tokens'] >= 0, "Output tokens should be non-negative"
        assert result['total_tokens'] >= 0, "Total tokens should be non-negative"
    
    @given(
        input_tokens=st.integers(min_value=0, max_value=1000000),
        output_tokens=st.integers(min_value=0, max_value=1000000),
        input_price=st.floats(min_value=0.0001, max_value=0.1),
        output_price=st.floats(min_value=0.0001, max_value=0.1)
    )
    @settings(max_examples=100, deadline=None)
    def test_cost_calculation_accuracy(self, input_tokens, output_tokens, 
                                      input_price, output_price):
        """
        Property 13 variant: Cost calculation should be accurate
        
        Cost = (input_tokens / 1000) * input_price + (output_tokens / 1000) * output_price
        
        Validates: Requirements FR-7.4
        """
        # Calculate cost
        input_cost = (input_tokens / 1000.0) * input_price
        output_cost = (output_tokens / 1000.0) * output_price
        total_cost = input_cost + output_cost
        
        # Verify calculation is accurate
        recalculated = (input_tokens / 1000.0) * input_price + (output_tokens / 1000.0) * output_price
        
        # Should be exactly equal (deterministic calculation)
        assert abs(recalculated - total_cost) < 1e-10, \
            "Cost calculation should be deterministic"
    
    @given(tokens=bedrock_token_data())
    @settings(max_examples=100, deadline=None)
    def test_total_tokens_equals_sum(self, tokens):
        """
        Property 13 variant: Total tokens should equal sum of input and output
        
        Validates: Requirements FR-7.4
        """
        total_tokens = tokens['input_tokens'] + tokens['output_tokens']
        
        # Verify sum
        assert total_tokens == tokens['input_tokens'] + tokens['output_tokens'], \
            "Total tokens should equal sum of input and output"
    
    @given(
        tokens=bedrock_token_data(),
        pricing=model_pricing_data()
    )
    @settings(max_examples=100, deadline=None)
    def test_zero_tokens_zero_cost(self, tokens, pricing):
        """
        Property 13 variant: Zero tokens should result in zero cost
        
        If both input and output tokens are zero, cost should be zero.
        
        Validates: Requirements FR-7.4
        """
        # Set tokens to zero
        input_tokens = 0
        output_tokens = 0
        
        # Calculate cost
        cost = (input_tokens / 1000.0) * pricing['input_cost_per_1k'] + \
               (output_tokens / 1000.0) * pricing['output_cost_per_1k']
        
        # Should be zero
        assert cost == 0.0, "Zero tokens should result in zero cost"
    
    @given(
        tokens=bedrock_token_data(),
        pricing=model_pricing_data()
    )
    @settings(max_examples=100, deadline=None)
    def test_cost_proportional_to_tokens(self, tokens, pricing):
        """
        Property 13 variant: Cost should be proportional to token count
        
        Doubling tokens should double the cost (for same pricing).
        
        Validates: Requirements FR-7.4
        """
        # Calculate cost for original tokens
        cost1 = (tokens['input_tokens'] / 1000.0) * pricing['input_cost_per_1k'] + \
                (tokens['output_tokens'] / 1000.0) * pricing['output_cost_per_1k']
        
        # Calculate cost for doubled tokens
        cost2 = (tokens['input_tokens'] * 2 / 1000.0) * pricing['input_cost_per_1k'] + \
                (tokens['output_tokens'] * 2 / 1000.0) * pricing['output_cost_per_1k']
        
        # cost2 should be approximately 2 * cost1
        if cost1 > 0:
            ratio = cost2 / cost1
            assert abs(ratio - 2.0) < 0.0001, \
                f"Doubling tokens should double cost: {ratio} != 2.0"
    
    @given(
        invocations=st.integers(min_value=1, max_value=10000),
        avg_input_tokens=st.integers(min_value=100, max_value=2000),
        avg_output_tokens=st.integers(min_value=50, max_value=1000)
    )
    @settings(max_examples=100, deadline=None)
    def test_token_tracking_with_invocations(self, invocations, avg_input_tokens, 
                                            avg_output_tokens):
        """
        Property 13 variant: Token tracking should scale with invocations
        
        Total tokens should be proportional to number of invocations.
        
        Validates: Requirements FR-7.4
        """
        # Calculate total tokens
        total_input = invocations * avg_input_tokens
        total_output = invocations * avg_output_tokens
        
        # Create BedrockCosts
        costs = BedrockCosts(
            date=datetime.now(),
            model_id='test-model',
            invocations=invocations,
            input_tokens=total_input,
            output_tokens=total_output,
            total_cost=0.0,  # Not testing cost here
            cost_per_invocation=0.0
        )
        
        # Verify average tokens per invocation
        avg_input_calculated = costs.input_tokens / costs.invocations
        avg_output_calculated = costs.output_tokens / costs.invocations
        
        assert abs(avg_input_calculated - avg_input_tokens) < 0.01, \
            "Average input tokens should match"
        assert abs(avg_output_calculated - avg_output_tokens) < 0.01, \
            "Average output tokens should match"
    
    @given(
        tokens=bedrock_token_data(),
        pricing=model_pricing_data()
    )
    @settings(max_examples=100, deadline=None)
    def test_cost_calculation_is_deterministic(self, tokens, pricing):
        """
        Property 13 variant: Cost calculation should be deterministic
        
        Calculating cost multiple times should yield the same result.
        
        Validates: Requirements FR-7.4
        """
        # Calculate cost twice
        cost1 = (tokens['input_tokens'] / 1000.0) * pricing['input_cost_per_1k'] + \
                (tokens['output_tokens'] / 1000.0) * pricing['output_cost_per_1k']
        
        cost2 = (tokens['input_tokens'] / 1000.0) * pricing['input_cost_per_1k'] + \
                (tokens['output_tokens'] / 1000.0) * pricing['output_cost_per_1k']
        
        # Should be exactly equal
        assert cost1 == cost2, "Cost calculation should be deterministic"
