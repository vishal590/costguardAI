"""
Property-Based Tests for Cost-Per-Training Calculator

Tests Property 6: Cost-Per-Training Accuracy
Validates: Requirements FR-4.1, FR-4.3

Property 6: Cost-Per-Training Accuracy
For any training job with known total cost, the calculated cost per training 
should include all cost components (compute + storage + data transfer) and 
sum to the total cost within 2%.
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
from src.services.ai_ml.cost_per_training_calculator import (
    CostPerTrainingCalculator,
    TrainingCosts,
    TrainingJobMetadata,
    CostPerTraining,
    InstanceComparison
)


# Strategies for generating test data
@st.composite
def training_data(draw):
    """Generate valid training data for testing."""
    compute_cost = draw(st.floats(min_value=10.0, max_value=10000.0))
    storage_cost = draw(st.floats(min_value=1.0, max_value=1000.0))
    data_transfer_cost = draw(st.floats(min_value=0.5, max_value=500.0))
    duration_hours = draw(st.floats(min_value=0.1, max_value=100.0))
    
    return {
        'compute_cost': compute_cost,
        'storage_cost': storage_cost,
        'data_transfer_cost': data_transfer_cost,
        'total_cost': compute_cost + storage_cost + data_transfer_cost,
        'duration_hours': duration_hours
    }


class TestCostPerTrainingProperties:
    """Property-based tests for cost-per-training calculator."""
    
    @given(data=training_data())
    @settings(max_examples=100)
    def test_property_6_cost_per_training_accuracy(self, data):
        """
        Property 6: Cost-Per-Training Accuracy
        
        For any training job with known total cost, the calculated cost per 
        training should include all cost components (compute + storage + data 
        transfer) and sum to the total cost within 2%.
        
        Feature: ai-ml-workload-costs, Property 6: Cost-Per-Training Accuracy
        Validates: Requirements FR-4.1, FR-4.3
        """
        # Create calculator with mock clients
        calculator = CostPerTrainingCalculator()
        
        # Mock the methods to return our test data
        calculator.get_training_job_metadata = lambda job_id: TrainingJobMetadata(
            job_id=job_id,
            model="test-model",
            dataset="test-dataset",
            instance_type="ml.p3.2xlarge",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 1) + timedelta(hours=data['duration_hours']),
            duration_hours=data['duration_hours'],
            source="sagemaker"
        )
        
        calculator.get_training_costs = lambda job_id: TrainingCosts(
            compute_cost=data['compute_cost'],
            storage_cost=data['storage_cost'],
            data_transfer_cost=data['data_transfer_cost']
        )
        
        # Calculate cost per training
        result = calculator.calculate_cost_per_training("test-job-123")
        
        # Verify total cost equals sum of components within 2%
        component_sum = result.compute_cost + result.storage_cost + result.data_transfer_cost
        tolerance = data['total_cost'] * 0.02  # 2%
        assert abs(result.total_cost - component_sum) <= tolerance
        
        # Verify individual components match
        assert abs(result.compute_cost - data['compute_cost']) < 0.01
        assert abs(result.storage_cost - data['storage_cost']) < 0.01
        assert abs(result.data_transfer_cost - data['data_transfer_cost']) < 0.01
        
        # Verify duration matches
        assert abs(result.training_hours - data['duration_hours']) < 0.01
    
    @given(
        total_cost=st.floats(min_value=10.0, max_value=10000.0),
        duration_hours=st.floats(min_value=0.1, max_value=100.0)
    )
    @settings(max_examples=100)
    def test_cost_per_hour_calculation(self, total_cost, duration_hours):
        """
        Test that cost per hour is exactly total_cost / duration_hours.
        
        Feature: ai-ml-workload-costs, Property 6: Cost-Per-Training Accuracy
        Validates: Requirements FR-4.5
        """
        calculator = CostPerTrainingCalculator()
        
        calculator.get_training_job_metadata = lambda job_id: TrainingJobMetadata(
            job_id=job_id,
            model="test-model",
            dataset="test-dataset",
            instance_type="ml.p3.2xlarge",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 1) + timedelta(hours=duration_hours),
            duration_hours=duration_hours,
            source="sagemaker"
        )
        
        calculator.get_training_costs = lambda job_id: TrainingCosts(
            compute_cost=total_cost,
            storage_cost=0.0,
            data_transfer_cost=0.0
        )
        
        result = calculator.calculate_cost_per_training("test-job-123")
        
        expected_cost_per_hour = total_cost / duration_hours
        assert abs(result.cost_per_hour - expected_cost_per_hour) < 1e-10
    
    @given(data=training_data())
    @settings(max_examples=100)
    def test_cost_components_sum_to_total(self, data):
        """
        Test that compute + storage + data transfer costs sum to total cost.
        
        Feature: ai-ml-workload-costs, Property 6: Cost-Per-Training Accuracy
        Validates: Requirements FR-4.3
        """
        calculator = CostPerTrainingCalculator()
        
        calculator.get_training_job_metadata = lambda job_id: TrainingJobMetadata(
            job_id=job_id,
            model="test-model",
            dataset="test-dataset",
            instance_type="ml.p3.2xlarge",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 1) + timedelta(hours=data['duration_hours']),
            duration_hours=data['duration_hours'],
            source="sagemaker"
        )
        
        calculator.get_training_costs = lambda job_id: TrainingCosts(
            compute_cost=data['compute_cost'],
            storage_cost=data['storage_cost'],
            data_transfer_cost=data['data_transfer_cost']
        )
        
        result = calculator.calculate_cost_per_training("test-job-123")
        
        # Sum of components should equal total cost
        component_sum = result.compute_cost + result.storage_cost + result.data_transfer_cost
        assert abs(component_sum - result.total_cost) < 0.01
    
    @given(
        compute_pct=st.floats(min_value=0.0, max_value=1.0),
        storage_pct=st.floats(min_value=0.0, max_value=1.0),
        total_cost=st.floats(min_value=100.0, max_value=10000.0),
        duration=st.floats(min_value=1.0, max_value=100.0)
    )
    @settings(max_examples=100)
    def test_cost_breakdown_proportions(self, compute_pct, storage_pct, total_cost, duration):
        """
        Test that cost breakdown maintains correct proportions.
        
        Feature: ai-ml-workload-costs, Property 6: Cost-Per-Training Accuracy
        """
        # Normalize percentages to sum to 1.0
        total_pct = compute_pct + storage_pct
        if total_pct > 0:
            compute_pct = compute_pct / total_pct
            storage_pct = storage_pct / total_pct
        else:
            compute_pct = 1.0
            storage_pct = 0.0
        
        data_transfer_pct = 1.0 - compute_pct - storage_pct
        
        compute_cost = total_cost * compute_pct
        storage_cost = total_cost * storage_pct
        data_transfer_cost = total_cost * data_transfer_pct
        
        calculator = CostPerTrainingCalculator()
        
        calculator.get_training_job_metadata = lambda job_id: TrainingJobMetadata(
            job_id=job_id,
            model="test-model",
            dataset="test-dataset",
            instance_type="ml.p3.2xlarge",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 1) + timedelta(hours=duration),
            duration_hours=duration,
            source="sagemaker"
        )
        
        calculator.get_training_costs = lambda job_id: TrainingCosts(
            compute_cost=compute_cost,
            storage_cost=storage_cost,
            data_transfer_cost=data_transfer_cost
        )
        
        result = calculator.calculate_cost_per_training("test-job-123")
        
        # Verify proportions are maintained
        if result.total_cost > 0:
            assert abs(result.compute_cost / result.total_cost - compute_pct) < 0.01
            assert abs(result.storage_cost / result.total_cost - storage_pct) < 0.01
    
    @given(
        duration=st.floats(min_value=1.0, max_value=100.0),
        cost=st.floats(min_value=100.0, max_value=10000.0)
    )
    @settings(max_examples=100)
    def test_cost_per_hour_scales_linearly(self, duration, cost):
        """
        Test that doubling duration halves cost per hour (linear scaling).
        
        Feature: ai-ml-workload-costs, Property 6: Cost-Per-Training Accuracy
        """
        calculator = CostPerTrainingCalculator()
        
        # First calculation
        calculator.get_training_job_metadata = lambda job_id: TrainingJobMetadata(
            job_id=job_id,
            model="test-model",
            dataset="test-dataset",
            instance_type="ml.p3.2xlarge",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 1) + timedelta(hours=duration),
            duration_hours=duration,
            source="sagemaker"
        )
        
        calculator.get_training_costs = lambda job_id: TrainingCosts(
            compute_cost=cost,
            storage_cost=0.0,
            data_transfer_cost=0.0
        )
        
        result1 = calculator.calculate_cost_per_training("test-job-1")
        
        # Second calculation with double duration
        calculator.get_training_job_metadata = lambda job_id: TrainingJobMetadata(
            job_id=job_id,
            model="test-model",
            dataset="test-dataset",
            instance_type="ml.p3.2xlarge",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 1) + timedelta(hours=duration * 2),
            duration_hours=duration * 2,
            source="sagemaker"
        )
        
        result2 = calculator.calculate_cost_per_training("test-job-2")
        
        # Cost per hour should be halved
        expected_ratio = 0.5
        actual_ratio = result2.cost_per_hour / result1.cost_per_hour
        assert abs(actual_ratio - expected_ratio) < 0.01
    
    @given(
        instance_types=st.lists(
            st.sampled_from(['ml.p3.2xlarge', 'ml.p3.8xlarge', 'ml.g4dn.xlarge']),
            min_size=2,
            max_size=5,
            unique=True
        )
    )
    @settings(max_examples=100)
    def test_instance_comparison_consistency(self, instance_types):
        """
        Test that instance type comparisons are consistent.
        
        Feature: ai-ml-workload-costs, Property 6: Cost-Per-Training Accuracy
        Validates: Requirements FR-4.6
        """
        calculator = CostPerTrainingCalculator()
        
        comparisons = calculator.compare_instance_types(
            model="test-model",
            instance_types=instance_types
        )
        
        assert len(comparisons) == len(instance_types)
        
        # Verify baseline (first instance) has zero savings
        assert comparisons[0].savings_vs_baseline == 0.0
        assert comparisons[0].savings_percent == 0.0
        
        # Verify all comparisons have valid data
        for comp in comparisons:
            assert comp.estimated_duration_hours > 0
            assert comp.estimated_cost >= 0
            assert comp.cost_per_hour >= 0
    
    @given(
        duration=st.floats(min_value=1.0, max_value=100.0),
        cost=st.floats(min_value=100.0, max_value=10000.0)
    )
    @settings(max_examples=100)
    def test_zero_duration_returns_zero_cost_per_hour(self, duration, cost):
        """
        Test that zero duration results in zero cost per hour (avoid division by zero).
        
        Feature: ai-ml-workload-costs, Property 6: Cost-Per-Training Accuracy
        """
        calculator = CostPerTrainingCalculator()
        
        calculator.get_training_job_metadata = lambda job_id: TrainingJobMetadata(
            job_id=job_id,
            model="test-model",
            dataset="test-dataset",
            instance_type="ml.p3.2xlarge",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 1),
            duration_hours=0.0,
            source="sagemaker"
        )
        
        calculator.get_training_costs = lambda job_id: TrainingCosts(
            compute_cost=cost,
            storage_cost=0.0,
            data_transfer_cost=0.0
        )
        
        result = calculator.calculate_cost_per_training("test-job-123")
        
        # Should return zero cost per hour (avoid division by zero)
        assert result.cost_per_hour == 0.0
