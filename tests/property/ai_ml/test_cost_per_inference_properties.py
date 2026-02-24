"""
Property-Based Tests for Cost-Per-Inference Calculator

Tests Property 5: Cost-Per-Inference Accuracy
Validates: Requirements FR-3.1, FR-3.4

Property 5: Cost-Per-Inference Accuracy
For any inference endpoint with known total cost and request count, the calculated 
cost per inference should equal total cost divided by request count, accurate within 0.01%.
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
from src.services.ai_ml.cost_per_inference_calculator import (
    CostPerInferenceCalculator,
    InferenceCosts,
    CostPerInference
)


# Strategies for generating test data
@st.composite
def inference_data(draw):
    """Generate valid inference data for testing."""
    total_requests = draw(st.integers(min_value=1, max_value=1000000))
    compute_cost = draw(st.floats(min_value=0.01, max_value=10000.0))
    api_cost = draw(st.floats(min_value=0.0, max_value=1000.0))
    data_transfer_cost = draw(st.floats(min_value=0.0, max_value=500.0))
    
    return {
        'total_requests': total_requests,
        'compute_cost': compute_cost,
        'api_cost': api_cost,
        'data_transfer_cost': data_transfer_cost,
        'total_cost': compute_cost + api_cost + data_transfer_cost
    }


class TestCostPerInferenceProperties:
    """Property-based tests for cost-per-inference calculator."""
    
    @given(data=inference_data())
    @settings(max_examples=100)
    def test_property_5_cost_per_inference_accuracy(self, data):
        """
        Property 5: Cost-Per-Inference Accuracy
        
        For any inference endpoint with known total cost and request count,
        the calculated cost per inference should equal total cost divided by
        request count, accurate within 0.01%.
        
        Feature: ai-ml-workload-costs, Property 5: Cost-Per-Inference Accuracy
        Validates: Requirements FR-3.1, FR-3.4
        """
        # Create calculator with mock clients
        calculator = CostPerInferenceCalculator()
        
        # Mock the methods to return our test data
        calculator.get_inference_request_count = lambda *args: data['total_requests']
        calculator.get_inference_costs = lambda *args: InferenceCosts(
            compute_cost=data['compute_cost'],
            api_cost=data['api_cost'],
            data_transfer_cost=data['data_transfer_cost']
        )
        
        # Calculate cost per inference
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)
        result = calculator.calculate_cost_per_inference(
            model="test-model",
            endpoint="test-endpoint",
            start_date=start_date,
            end_date=end_date
        )
        
        # Expected cost per inference
        expected_cost_per_inference = data['total_cost'] / data['total_requests']
        
        # Verify accuracy within 0.01%
        tolerance = expected_cost_per_inference * 0.0001  # 0.01%
        assert abs(result.cost_per_inference - expected_cost_per_inference) <= tolerance
        
        # Verify total cost matches sum of components
        assert abs(result.total_cost - data['total_cost']) < 0.01
        
        # Verify request count matches
        assert result.total_requests == data['total_requests']
    
    @given(
        total_requests=st.integers(min_value=1, max_value=1000000),
        total_cost=st.floats(min_value=0.01, max_value=10000.0)
    )
    @settings(max_examples=100)
    def test_cost_per_inference_division_accuracy(self, total_requests, total_cost):
        """
        Test that cost per inference is exactly total_cost / total_requests.
        
        Feature: ai-ml-workload-costs, Property 5: Cost-Per-Inference Accuracy
        """
        calculator = CostPerInferenceCalculator()
        
        # Mock methods
        calculator.get_inference_request_count = lambda *args: total_requests
        calculator.get_inference_costs = lambda *args: InferenceCosts(
            compute_cost=total_cost,
            api_cost=0.0,
            data_transfer_cost=0.0
        )
        
        result = calculator.calculate_cost_per_inference(
            model="test-model",
            endpoint="test-endpoint",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31)
        )
        
        expected = total_cost / total_requests
        
        # Should be exact (within floating point precision)
        assert abs(result.cost_per_inference - expected) < 1e-10
    
    @given(data=inference_data())
    @settings(max_examples=100)
    def test_cost_components_sum_to_total(self, data):
        """
        Test that compute + API + data transfer costs sum to total cost.
        
        Feature: ai-ml-workload-costs, Property 5: Cost-Per-Inference Accuracy
        Validates: Requirements FR-3.3
        """
        calculator = CostPerInferenceCalculator()
        
        calculator.get_inference_request_count = lambda *args: data['total_requests']
        calculator.get_inference_costs = lambda *args: InferenceCosts(
            compute_cost=data['compute_cost'],
            api_cost=data['api_cost'],
            data_transfer_cost=data['data_transfer_cost']
        )
        
        result = calculator.calculate_cost_per_inference(
            model="test-model",
            endpoint="test-endpoint",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31)
        )
        
        # Sum of components should equal total cost
        component_sum = result.compute_cost + result.api_cost + result.data_transfer_cost
        assert abs(component_sum - result.total_cost) < 0.01
    
    @given(
        requests=st.integers(min_value=1, max_value=1000000),
        cost=st.floats(min_value=0.01, max_value=10000.0)
    )
    @settings(max_examples=100)
    def test_zero_requests_returns_zero_cost(self, requests, cost):
        """
        Test that zero requests results in zero cost per inference.
        
        Feature: ai-ml-workload-costs, Property 5: Cost-Per-Inference Accuracy
        """
        calculator = CostPerInferenceCalculator()
        
        # Mock to return zero requests
        calculator.get_inference_request_count = lambda *args: 0
        calculator.get_inference_costs = lambda *args: InferenceCosts(
            compute_cost=cost,
            api_cost=0.0,
            data_transfer_cost=0.0
        )
        
        result = calculator.calculate_cost_per_inference(
            model="test-model",
            endpoint="test-endpoint",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31)
        )
        
        # Should return zero cost per inference (avoid division by zero)
        assert result.cost_per_inference == 0.0
        assert result.total_requests == 0
    
    @given(
        compute_pct=st.floats(min_value=0.0, max_value=1.0),
        api_pct=st.floats(min_value=0.0, max_value=1.0),
        total_cost=st.floats(min_value=1.0, max_value=10000.0),
        requests=st.integers(min_value=1, max_value=1000000)
    )
    @settings(max_examples=100)
    def test_cost_breakdown_proportions(self, compute_pct, api_pct, total_cost, requests):
        """
        Test that cost breakdown maintains correct proportions.
        
        Feature: ai-ml-workload-costs, Property 5: Cost-Per-Inference Accuracy
        """
        # Normalize percentages to sum to 1.0
        total_pct = compute_pct + api_pct
        if total_pct > 0:
            compute_pct = compute_pct / total_pct
            api_pct = api_pct / total_pct
        else:
            compute_pct = 1.0
            api_pct = 0.0
        
        data_transfer_pct = 1.0 - compute_pct - api_pct
        
        compute_cost = total_cost * compute_pct
        api_cost = total_cost * api_pct
        data_transfer_cost = total_cost * data_transfer_pct
        
        calculator = CostPerInferenceCalculator()
        calculator.get_inference_request_count = lambda *args: requests
        calculator.get_inference_costs = lambda *args: InferenceCosts(
            compute_cost=compute_cost,
            api_cost=api_cost,
            data_transfer_cost=data_transfer_cost
        )
        
        result = calculator.calculate_cost_per_inference(
            model="test-model",
            endpoint="test-endpoint",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31)
        )
        
        # Verify proportions are maintained
        if result.total_cost > 0:
            assert abs(result.compute_cost / result.total_cost - compute_pct) < 0.01
            assert abs(result.api_cost / result.total_cost - api_pct) < 0.01
    
    @given(
        requests=st.integers(min_value=1, max_value=1000000),
        cost=st.floats(min_value=0.01, max_value=10000.0)
    )
    @settings(max_examples=100)
    def test_cost_per_inference_scales_linearly(self, requests, cost):
        """
        Test that doubling requests halves cost per inference (linear scaling).
        
        Feature: ai-ml-workload-costs, Property 5: Cost-Per-Inference Accuracy
        """
        calculator = CostPerInferenceCalculator()
        
        # First calculation
        calculator.get_inference_request_count = lambda *args: requests
        calculator.get_inference_costs = lambda *args: InferenceCosts(
            compute_cost=cost,
            api_cost=0.0,
            data_transfer_cost=0.0
        )
        
        result1 = calculator.calculate_cost_per_inference(
            model="test-model",
            endpoint="test-endpoint",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31)
        )
        
        # Second calculation with double requests
        calculator.get_inference_request_count = lambda *args: requests * 2
        
        result2 = calculator.calculate_cost_per_inference(
            model="test-model",
            endpoint="test-endpoint",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31)
        )
        
        # Cost per inference should be halved
        expected_ratio = 0.5
        actual_ratio = result2.cost_per_inference / result1.cost_per_inference
        assert abs(actual_ratio - expected_ratio) < 0.01
    
    @given(
        days=st.integers(min_value=1, max_value=90),
        daily_requests=st.integers(min_value=100, max_value=10000),
        daily_cost=st.floats(min_value=1.0, max_value=1000.0)
    )
    @settings(max_examples=100)
    def test_cost_trends_consistency(self, days, daily_requests, daily_cost):
        """
        Test that cost trends maintain consistency over time.
        
        Feature: ai-ml-workload-costs, Property 5: Cost-Per-Inference Accuracy
        Validates: Requirements FR-3.5
        """
        calculator = CostPerInferenceCalculator()
        
        # Mock consistent daily metrics
        calculator.get_inference_request_count = lambda *args: daily_requests
        calculator.get_inference_costs = lambda *args: InferenceCosts(
            compute_cost=daily_cost,
            api_cost=0.0,
            data_transfer_cost=0.0
        )
        
        trends = calculator.track_cost_trends(
            model="test-model",
            endpoint="test-endpoint",
            days=min(days, 30)  # Limit to 30 days for performance
        )
        
        # All trends should have same cost per inference (consistent workload)
        expected_cost_per_inference = daily_cost / daily_requests
        
        for trend in trends:
            if trend.total_requests > 0:
                assert abs(trend.cost_per_inference - expected_cost_per_inference) < 0.01
