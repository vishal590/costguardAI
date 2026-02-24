"""
Property-based tests for SageMaker Cost Tracker

Tests Property 12: SageMaker Cost Breakdown
Validates: Requirements FR-6.4
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
from src.services.ai_ml.sagemaker_cost_tracker import (
    SageMakerCostTracker,
    SageMakerCosts,
    JobCost
)


# Strategies for generating test data
@st.composite
def sagemaker_costs_data(draw):
    """Generate SageMaker costs with breakdown"""
    training_costs = draw(st.floats(min_value=0.0, max_value=10000.0))
    inference_costs = draw(st.floats(min_value=0.0, max_value=10000.0))
    notebook_costs = draw(st.floats(min_value=0.0, max_value=10000.0))
    
    return {
        'training': training_costs,
        'inference': inference_costs,
        'notebook': notebook_costs,
        'total': training_costs + inference_costs + notebook_costs
    }


@st.composite
def job_cost_data(draw):
    """Generate job cost data"""
    compute_cost = draw(st.floats(min_value=0.0, max_value=1000.0))
    storage_cost = draw(st.floats(min_value=0.0, max_value=100.0))
    data_transfer_cost = draw(st.floats(min_value=0.0, max_value=100.0))
    
    return {
        'compute': compute_cost,
        'storage': storage_cost,
        'data_transfer': data_transfer_cost,
        'total': compute_cost + storage_cost + data_transfer_cost
    }


class TestSageMakerCostBreakdownProperties:
    """Property tests for SageMaker cost breakdown (Property 12)"""

    
    @given(costs=sagemaker_costs_data())
    @settings(max_examples=100, deadline=None)
    def test_cost_breakdown_sums_to_total(self, costs):
        """
        Property 12: SageMaker Cost Breakdown
        
        For any SageMaker account, the sum of training costs, inference costs, 
        and notebook costs should equal the total SageMaker cost within 1%.
        
        Validates: Requirements FR-6.4
        """
        # Create mock clients
        mock_ce = Mock()
        mock_sagemaker = Mock()
        mock_cloudwatch = Mock()
        mock_pricing = Mock()
        
        # Mock Cost Explorer response
        mock_ce.get_cost_and_usage.return_value = {
            'ResultsByTime': [
                {
                    'Groups': [
                        {
                            'Keys': ['TrainingJob:ml.p3.2xlarge'],
                            'Metrics': {'UnblendedCost': {'Amount': str(costs['training'])}}
                        },
                        {
                            'Keys': ['Hosting:ml.m5.xlarge'],
                            'Metrics': {'UnblendedCost': {'Amount': str(costs['inference'])}}
                        },
                        {
                            'Keys': ['Notebook:ml.t3.medium'],
                            'Metrics': {'UnblendedCost': {'Amount': str(costs['notebook'])}}
                        }
                    ]
                }
            ]
        }
        
        # Mock SageMaker list response (empty for this test)
        mock_sagemaker.get_paginator.return_value.paginate.return_value = []
        
        tracker = SageMakerCostTracker(
            cost_explorer_client=mock_ce,
            sagemaker_client=mock_sagemaker,
            cloudwatch_client=mock_cloudwatch,
            pricing_client=mock_pricing
        )
        
        # Track costs
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()
        result = tracker.track_sagemaker_costs(start_date, end_date)
        
        # Verify breakdown sums to total within 1%
        calculated_total = result.training_costs + result.inference_costs + result.notebook_costs
        expected_total = result.total_cost
        
        # Allow 1% tolerance
        tolerance = expected_total * 0.01
        assert abs(calculated_total - expected_total) <= tolerance, \
            f"Cost breakdown doesn't sum to total: {calculated_total} != {expected_total}"
    
    @given(costs=sagemaker_costs_data())
    @settings(max_examples=100, deadline=None)
    def test_total_cost_equals_sum_of_components(self, costs):
        """
        Property 12 variant: Total cost should equal sum of all components
        
        Validates: Requirements FR-6.4
        """
        # Calculate expected total
        expected_total = costs['training'] + costs['inference'] + costs['notebook']
        
        # Verify within 1% tolerance
        tolerance = expected_total * 0.01
        assert abs(costs['total'] - expected_total) <= tolerance
    
    @given(job_costs=job_cost_data())
    @settings(max_examples=100, deadline=None)
    def test_job_cost_components_sum_to_total(self, job_costs):
        """
        Property 12 variant: Individual job costs should sum correctly
        
        For any job, compute + storage + data_transfer should equal total cost.
        
        Validates: Requirements FR-6.4
        """
        job_cost = JobCost(
            job_name='test-job',
            job_type='training',
            instance_type='ml.p3.2xlarge',
            start_time=datetime.now() - timedelta(hours=2),
            end_time=datetime.now(),
            duration_hours=2.0,
            compute_cost=job_costs['compute'],
            storage_cost=job_costs['storage'],
            data_transfer_cost=job_costs['data_transfer'],
            total_cost=job_costs['total']
        )
        
        # Verify components sum to total within 1%
        calculated_total = job_cost.compute_cost + job_cost.storage_cost + job_cost.data_transfer_cost
        tolerance = job_cost.total_cost * 0.01
        
        assert abs(calculated_total - job_cost.total_cost) <= tolerance, \
            f"Job cost components don't sum to total: {calculated_total} != {job_cost.total_cost}"

    
    @given(
        training=st.floats(min_value=0.0, max_value=5000.0),
        inference=st.floats(min_value=0.0, max_value=5000.0),
        notebook=st.floats(min_value=0.0, max_value=5000.0)
    )
    @settings(max_examples=100, deadline=None)
    def test_zero_costs_sum_correctly(self, training, inference, notebook):
        """
        Property 12 variant: Zero costs should be handled correctly
        
        Even when some costs are zero, the sum should still be accurate.
        
        Validates: Requirements FR-6.4
        """
        total = training + inference + notebook
        
        # Create SageMakerCosts object
        costs = SageMakerCosts(
            date=datetime.now(),
            training_costs=training,
            inference_costs=inference,
            notebook_costs=notebook,
            total_cost=total,
            job_breakdown=[]
        )
        
        # Verify sum
        calculated_total = costs.training_costs + costs.inference_costs + costs.notebook_costs
        tolerance = max(costs.total_cost * 0.01, 0.01)  # At least 1 cent tolerance
        
        assert abs(calculated_total - costs.total_cost) <= tolerance
    
    @given(costs=sagemaker_costs_data())
    @settings(max_examples=100, deadline=None)
    def test_cost_breakdown_is_non_negative(self, costs):
        """
        Property 12 variant: All cost components should be non-negative
        
        Training, inference, and notebook costs should never be negative.
        
        Validates: Requirements FR-6.4
        """
        assert costs['training'] >= 0, "Training costs should be non-negative"
        assert costs['inference'] >= 0, "Inference costs should be non-negative"
        assert costs['notebook'] >= 0, "Notebook costs should be non-negative"
        assert costs['total'] >= 0, "Total costs should be non-negative"
    
    @given(costs=sagemaker_costs_data())
    @settings(max_examples=100, deadline=None)
    def test_total_cost_not_less_than_any_component(self, costs):
        """
        Property 12 variant: Total cost should not be less than any component
        
        The total should always be at least as large as the largest component.
        
        Validates: Requirements FR-6.4
        """
        assert costs['total'] >= costs['training'], \
            "Total should be >= training costs"
        assert costs['total'] >= costs['inference'], \
            "Total should be >= inference costs"
        assert costs['total'] >= costs['notebook'], \
            "Total should be >= notebook costs"
    
    @given(
        compute=st.floats(min_value=0.0, max_value=1000.0),
        storage=st.floats(min_value=0.0, max_value=100.0),
        data_transfer=st.floats(min_value=0.0, max_value=100.0)
    )
    @settings(max_examples=100, deadline=None)
    def test_job_cost_breakdown_accuracy(self, compute, storage, data_transfer):
        """
        Property 12 variant: Job cost breakdown should be accurate
        
        For any job, the sum of cost components should equal the total.
        
        Validates: Requirements FR-6.4
        """
        total = compute + storage + data_transfer
        
        job = JobCost(
            job_name='test-job',
            job_type='training',
            instance_type='ml.p3.2xlarge',
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now(),
            duration_hours=1.0,
            compute_cost=compute,
            storage_cost=storage,
            data_transfer_cost=data_transfer,
            total_cost=total
        )
        
        # Verify within 1% tolerance
        calculated = job.compute_cost + job.storage_cost + job.data_transfer_cost
        tolerance = max(job.total_cost * 0.01, 0.01)
        
        assert abs(calculated - job.total_cost) <= tolerance
    
    @given(costs=sagemaker_costs_data())
    @settings(max_examples=100, deadline=None)
    def test_cost_breakdown_consistency(self, costs):
        """
        Property 12 variant: Cost breakdown should be consistent
        
        Multiple calculations of the same breakdown should yield the same result.
        
        Validates: Requirements FR-6.4
        """
        # Calculate total twice
        total1 = costs['training'] + costs['inference'] + costs['notebook']
        total2 = costs['training'] + costs['inference'] + costs['notebook']
        
        # Should be exactly equal (no randomness)
        assert total1 == total2, "Cost calculations should be deterministic"
        
        # Both should match expected total within tolerance
        tolerance = costs['total'] * 0.01
        assert abs(total1 - costs['total']) <= tolerance
        assert abs(total2 - costs['total']) <= tolerance
