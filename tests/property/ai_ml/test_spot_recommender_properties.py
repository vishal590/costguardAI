"""
Property-based tests for Spot Instance Recommender.

Tests universal properties that should hold for all spot instance recommendations.
Each test runs 100 iterations with randomly generated inputs.

Feature: ai-ml-workload-costs
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
from src.services.ai_ml.spot_instance_recommender import (
    SpotInstanceRecommender,
    SpotRecommendation,
    SpotSavings,
    WhatIfScenario
)


# Strategies for generating test data
@st.composite
def instance_type_strategy(draw):
    """Generate valid GPU instance types."""
    families = ['p3', 'p4', 'p4d', 'p5', 'g4dn', 'g5', 'g6']
    sizes = ['xlarge', '2xlarge', '8xlarge', '16xlarge', '24xlarge', '48xlarge']
    family = draw(st.sampled_from(families))
    size = draw(st.sampled_from(sizes))
    return f"{family}.{size}"


@st.composite
def pricing_strategy(draw):
    """Generate realistic pricing data."""
    on_demand_price = draw(st.floats(min_value=0.5, max_value=100.0))
    # Spot prices are typically 30-90% cheaper
    discount_percent = draw(st.floats(min_value=0.3, max_value=0.9))
    spot_price = on_demand_price * (1 - discount_percent)
    return on_demand_price, spot_price


@st.composite
def runtime_hours_strategy(draw):
    """Generate realistic runtime hours."""
    return draw(st.floats(min_value=1.0, max_value=720.0))  # 1 hour to 30 days


class TestSpotSavingsCalculation:
    """
    Property 7: Spot Savings Calculation
    
    Validates: Requirements FR-5.2
    
    For any on-demand instance and equivalent spot instance, the calculated savings
    should equal the difference in hourly costs multiplied by runtime hours,
    accurate within 5%.
    """
    
    @settings(max_examples=100, deadline=None)
    @given(
        instance_type=instance_type_strategy(),
        pricing=pricing_strategy(),
        runtime_hours=runtime_hours_strategy()
    )
    def test_spot_savings_equals_price_difference_times_hours(
        self, instance_type, pricing, runtime_hours
    ):
        """
        Property: Savings = (on_demand_price - spot_price) * runtime_hours
        
        Feature: ai-ml-workload-costs, Property 7: Spot Savings Calculation
        Validates: Requirements FR-5.2
        """
        on_demand_price, spot_price = pricing
        
        # Calculate expected savings
        expected_savings_per_hour = on_demand_price - spot_price
        expected_total_savings = expected_savings_per_hour * runtime_hours
        
        # Create recommender and calculate savings
        recommender = SpotInstanceRecommender()
        
        # Mock the pricing methods
        recommender._get_on_demand_price = lambda x: on_demand_price
        recommender._get_spot_price = lambda x: spot_price
        
        savings = recommender.calculate_spot_savings(instance_type, instance_type)
        
        # Verify savings calculation (within 5% tolerance)
        tolerance = 0.05
        assert abs(savings.savings_per_hour - expected_savings_per_hour) <= expected_savings_per_hour * tolerance
        
        # Verify monthly savings calculation
        expected_monthly = expected_savings_per_hour * 730  # average hours per month
        assert abs(savings.estimated_monthly_savings - expected_monthly) <= expected_monthly * tolerance
    
    @settings(max_examples=100)
    @given(
        instance_type=instance_type_strategy(),
        pricing=pricing_strategy()
    )
    def test_spot_savings_percent_is_accurate(self, instance_type, pricing):
        """
        Property: Savings percent = (savings_per_hour / on_demand_price) * 100
        
        Feature: ai-ml-workload-costs, Property 7: Spot Savings Calculation
        Validates: Requirements FR-5.2
        """
        on_demand_price, spot_price = pricing
        
        # Calculate expected savings percent
        expected_savings_per_hour = on_demand_price - spot_price
        expected_percent = (expected_savings_per_hour / on_demand_price * 100) if on_demand_price > 0 else 0
        
        # Create recommender and calculate savings
        recommender = SpotInstanceRecommender()
        recommender._get_on_demand_price = lambda x: on_demand_price
        recommender._get_spot_price = lambda x: spot_price
        
        savings = recommender.calculate_spot_savings(instance_type, instance_type)
        
        # Verify savings percent (within 5% tolerance)
        tolerance = 0.05
        assert abs(savings.savings_percent - expected_percent) <= expected_percent * tolerance or expected_percent < 1
    
    @settings(max_examples=100)
    @given(
        instance_type=instance_type_strategy(),
        pricing=pricing_strategy()
    )
    def test_spot_savings_are_non_negative(self, instance_type, pricing):
        """
        Property: Savings should always be non-negative (spot <= on-demand)
        
        Feature: ai-ml-workload-costs, Property 7: Spot Savings Calculation
        Validates: Requirements FR-5.2
        """
        on_demand_price, spot_price = pricing
        
        # Ensure spot price is not higher than on-demand
        spot_price = min(spot_price, on_demand_price)
        
        recommender = SpotInstanceRecommender()
        recommender._get_on_demand_price = lambda x: on_demand_price
        recommender._get_spot_price = lambda x: spot_price
        
        savings = recommender.calculate_spot_savings(instance_type, instance_type)
        
        # Verify all savings values are non-negative
        assert savings.savings_per_hour >= 0
        assert savings.savings_percent >= 0
        assert savings.estimated_monthly_savings >= 0
    
    @settings(max_examples=100)
    @given(
        instance_type=instance_type_strategy(),
        on_demand_price=st.floats(min_value=1.0, max_value=100.0)
    )
    def test_spot_savings_with_zero_discount(self, instance_type, on_demand_price):
        """
        Property: When spot price equals on-demand, savings should be zero
        
        Feature: ai-ml-workload-costs, Property 7: Spot Savings Calculation
        Validates: Requirements FR-5.2
        """
        spot_price = on_demand_price  # No discount
        
        recommender = SpotInstanceRecommender()
        recommender._get_on_demand_price = lambda x: on_demand_price
        recommender._get_spot_price = lambda x: spot_price
        
        savings = recommender.calculate_spot_savings(instance_type, instance_type)
        
        # Verify zero savings
        assert abs(savings.savings_per_hour) < 0.01
        assert abs(savings.savings_percent) < 0.01
        assert abs(savings.estimated_monthly_savings) < 0.01
    
    @settings(max_examples=100)
    @given(
        instance_type=instance_type_strategy(),
        on_demand_price=st.floats(min_value=1.0, max_value=100.0)
    )
    def test_spot_savings_with_maximum_discount(self, instance_type, on_demand_price):
        """
        Property: With 90% discount, savings should be 90% of on-demand cost
        
        Feature: ai-ml-workload-costs, Property 7: Spot Savings Calculation
        Validates: Requirements FR-5.2
        """
        spot_price = on_demand_price * 0.1  # 90% discount
        
        recommender = SpotInstanceRecommender()
        recommender._get_on_demand_price = lambda x: on_demand_price
        recommender._get_spot_price = lambda x: spot_price
        
        savings = recommender.calculate_spot_savings(instance_type, instance_type)
        
        # Verify 90% savings (within 5% tolerance)
        expected_savings_per_hour = on_demand_price * 0.9
        tolerance = 0.05
        assert abs(savings.savings_per_hour - expected_savings_per_hour) <= expected_savings_per_hour * tolerance
        assert abs(savings.savings_percent - 90.0) <= 90.0 * tolerance
    
    @settings(max_examples=100)
    @given(
        instance_type=instance_type_strategy(),
        pricing=pricing_strategy()
    )
    def test_spot_savings_components_are_consistent(self, instance_type, pricing):
        """
        Property: All savings components should be mathematically consistent
        
        Feature: ai-ml-workload-costs, Property 7: Spot Savings Calculation
        Validates: Requirements FR-5.2
        """
        on_demand_price, spot_price = pricing
        
        recommender = SpotInstanceRecommender()
        recommender._get_on_demand_price = lambda x: on_demand_price
        recommender._get_spot_price = lambda x: spot_price
        
        savings = recommender.calculate_spot_savings(instance_type, instance_type)
        
        # Verify consistency between components
        # savings_per_hour = on_demand_price - spot_price
        assert abs(savings.savings_per_hour - (savings.on_demand_price - savings.spot_price)) < 0.01
        
        # savings_percent = (savings_per_hour / on_demand_price) * 100
        if savings.on_demand_price > 0:
            expected_percent = (savings.savings_per_hour / savings.on_demand_price) * 100
            assert abs(savings.savings_percent - expected_percent) < 0.1
        
        # estimated_monthly_savings = savings_per_hour * 730
        expected_monthly = savings.savings_per_hour * 730
        assert abs(savings.estimated_monthly_savings - expected_monthly) < 0.01
    
    @settings(max_examples=100)
    @given(
        instance_type=instance_type_strategy(),
        pricing=pricing_strategy()
    )
    def test_spot_savings_scale_linearly_with_price(self, instance_type, pricing):
        """
        Property: Doubling prices should double absolute savings
        
        Feature: ai-ml-workload-costs, Property 7: Spot Savings Calculation
        Validates: Requirements FR-5.2
        """
        on_demand_price, spot_price = pricing
        
        recommender = SpotInstanceRecommender()
        
        # Calculate savings with original prices
        recommender._get_on_demand_price = lambda x: on_demand_price
        recommender._get_spot_price = lambda x: spot_price
        savings1 = recommender.calculate_spot_savings(instance_type, instance_type)
        
        # Calculate savings with doubled prices
        recommender._get_on_demand_price = lambda x: on_demand_price * 2
        recommender._get_spot_price = lambda x: spot_price * 2
        savings2 = recommender.calculate_spot_savings(instance_type, instance_type)
        
        # Verify savings doubled (within 5% tolerance)
        tolerance = 0.05
        expected_doubled = savings1.savings_per_hour * 2
        assert abs(savings2.savings_per_hour - expected_doubled) <= expected_doubled * tolerance
        
        # Savings percent should remain the same
        assert abs(savings2.savings_percent - savings1.savings_percent) <= savings1.savings_percent * tolerance


class TestSpotRecommendationAccuracy:
    """Additional property tests for spot recommendations."""
    
    @settings(max_examples=100)
    @given(
        workload_id=st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        instance_type=instance_type_strategy(),
        pricing=pricing_strategy(),
        training_hours=st.floats(min_value=1.0, max_value=168.0)
    )
    def test_recommendation_savings_match_calculation(
        self, workload_id, instance_type, pricing, training_hours
    ):
        """
        Property: Recommendation savings should match manual calculation
        
        Feature: ai-ml-workload-costs, Property 7: Spot Savings Calculation
        Validates: Requirements FR-5.2
        """
        on_demand_price, spot_price = pricing
        
        recommender = SpotInstanceRecommender()
        recommender._get_on_demand_price = lambda x: on_demand_price
        recommender._get_spot_price = lambda x: spot_price
        recommender._get_interruption_risk = lambda x, y=None: 0.1
        
        # Mock workload metadata
        recommender._get_workload_metadata = lambda x: {
            'instance_type': instance_type,
            'workload_type': 'training',
            'duration_hours': training_hours,
            'state': 'running'
        }
        
        recommendations = recommender.recommend_spot_instances(workload_id)
        
        if recommendations and recommendations[0].suitable:
            rec = recommendations[0]
            
            # Calculate expected savings
            expected_current_cost = on_demand_price * training_hours
            expected_spot_cost = spot_price * training_hours
            expected_savings = expected_current_cost - expected_spot_cost
            
            # Verify recommendation matches calculation (within 5% tolerance)
            tolerance = 0.05
            assert abs(rec.current_cost - expected_current_cost) <= expected_current_cost * tolerance
            assert abs(rec.spot_cost - expected_spot_cost) <= expected_spot_cost * tolerance
            assert abs(rec.savings - expected_savings) <= expected_savings * tolerance


class TestSpotSuitabilityCriteria:
    """
    Property 11: Spot Suitability Criteria
    
    Validates: Requirements FR-5.1
    
    For any workload classified as "training" with batch processing characteristics,
    the system should recommend spot instances; for any workload classified as
    "inference" with real-time requirements, it should not recommend spot instances.
    """
    
    @settings(max_examples=100, deadline=None)
    @given(
        workload_id=st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        instance_type=instance_type_strategy(),
        training_hours=st.floats(min_value=1.0, max_value=168.0)
    )
    def test_training_workloads_are_spot_suitable(
        self, workload_id, instance_type, training_hours
    ):
        """
        Property: Training workloads with sufficient duration should be spot suitable
        
        Feature: ai-ml-workload-costs, Property 11: Spot Suitability Criteria
        Validates: Requirements FR-5.1
        """
        recommender = SpotInstanceRecommender()
        
        # Mock workload metadata for training workload
        recommender._get_workload_metadata = lambda x: {
            'instance_type': instance_type,
            'workload_type': 'training',
            'duration_hours': training_hours,
            'state': 'running'
        }
        
        # Mock pricing
        recommender._get_on_demand_price = lambda x: 10.0
        recommender._get_spot_price = lambda x: 3.0
        recommender._get_interruption_risk = lambda x, y=None: 0.1
        
        recommendations = recommender.recommend_spot_instances(workload_id)
        
        assert len(recommendations) > 0
        rec = recommendations[0]
        
        # Training workloads >= 1 hour should be suitable
        if training_hours >= recommender.min_training_duration:
            assert rec.suitable is True
            assert 'suitable' in rec.reason.lower()
        else:
            assert rec.suitable is False
            assert 'duration too short' in rec.reason.lower()
    
    @settings(max_examples=100)
    @given(
        workload_id=st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        instance_type=instance_type_strategy(),
        duration_hours=st.floats(min_value=0.1, max_value=168.0)
    )
    def test_inference_workloads_are_not_spot_suitable(
        self, workload_id, instance_type, duration_hours
    ):
        """
        Property: Inference workloads should NOT be spot suitable (real-time requirements)
        
        Feature: ai-ml-workload-costs, Property 11: Spot Suitability Criteria
        Validates: Requirements FR-5.1
        """
        recommender = SpotInstanceRecommender()
        
        # Mock workload metadata for inference workload
        recommender._get_workload_metadata = lambda x: {
            'instance_type': instance_type,
            'workload_type': 'inference',
            'duration_hours': duration_hours,
            'state': 'running'
        }
        
        # Mock pricing
        recommender._get_on_demand_price = lambda x: 10.0
        recommender._get_spot_price = lambda x: 3.0
        recommender._get_interruption_risk = lambda x, y=None: 0.1
        
        recommendations = recommender.recommend_spot_instances(workload_id)
        
        assert len(recommendations) > 0
        rec = recommendations[0]
        
        # Inference workloads should never be suitable
        assert rec.suitable is False
        assert 'inference' in rec.reason.lower() or 'not suitable' in rec.reason.lower()
    
    @settings(max_examples=100)
    @given(
        workload_id=st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        instance_type=instance_type_strategy(),
        duration_hours=st.floats(min_value=0.1, max_value=168.0)
    )
    def test_idle_workloads_are_not_spot_suitable(
        self, workload_id, instance_type, duration_hours
    ):
        """
        Property: Idle workloads should NOT be spot suitable
        
        Feature: ai-ml-workload-costs, Property 11: Spot Suitability Criteria
        Validates: Requirements FR-5.1
        """
        recommender = SpotInstanceRecommender()
        
        # Mock workload metadata for idle workload
        recommender._get_workload_metadata = lambda x: {
            'instance_type': instance_type,
            'workload_type': 'idle',
            'duration_hours': duration_hours,
            'state': 'running'
        }
        
        # Mock pricing
        recommender._get_on_demand_price = lambda x: 10.0
        recommender._get_spot_price = lambda x: 3.0
        recommender._get_interruption_risk = lambda x, y=None: 0.1
        
        recommendations = recommender.recommend_spot_instances(workload_id)
        
        assert len(recommendations) > 0
        rec = recommendations[0]
        
        # Idle workloads should never be suitable
        assert rec.suitable is False
        assert 'idle' in rec.reason.lower() or 'not suitable' in rec.reason.lower()
    
    @settings(max_examples=100)
    @given(
        workload_id=st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        instance_type=instance_type_strategy(),
        duration_hours=st.floats(min_value=0.1, max_value=0.9)
    )
    def test_short_duration_training_not_spot_suitable(
        self, workload_id, instance_type, duration_hours
    ):
        """
        Property: Training workloads with duration < 1 hour should NOT be spot suitable
        
        Feature: ai-ml-workload-costs, Property 11: Spot Suitability Criteria
        Validates: Requirements FR-5.1
        """
        recommender = SpotInstanceRecommender()
        
        # Mock workload metadata for short training workload
        recommender._get_workload_metadata = lambda x: {
            'instance_type': instance_type,
            'workload_type': 'training',
            'duration_hours': duration_hours,
            'state': 'running'
        }
        
        # Mock pricing
        recommender._get_on_demand_price = lambda x: 10.0
        recommender._get_spot_price = lambda x: 3.0
        recommender._get_interruption_risk = lambda x, y=None: 0.1
        
        recommendations = recommender.recommend_spot_instances(workload_id)
        
        assert len(recommendations) > 0
        rec = recommendations[0]
        
        # Short duration training should not be suitable
        assert rec.suitable is False
        assert 'duration too short' in rec.reason.lower()
    
    @settings(max_examples=100)
    @given(
        workload_id=st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        instance_type=instance_type_strategy()
    )
    def test_unknown_workload_type_not_spot_suitable(
        self, workload_id, instance_type
    ):
        """
        Property: Workloads with unknown type should NOT be spot suitable
        
        Feature: ai-ml-workload-costs, Property 11: Spot Suitability Criteria
        Validates: Requirements FR-5.1
        """
        recommender = SpotInstanceRecommender()
        
        # Mock workload metadata for unknown workload
        recommender._get_workload_metadata = lambda x: {
            'instance_type': instance_type,
            'workload_type': 'unknown',
            'duration_hours': 24.0,
            'state': 'running'
        }
        
        # Mock pricing
        recommender._get_on_demand_price = lambda x: 10.0
        recommender._get_spot_price = lambda x: 3.0
        recommender._get_interruption_risk = lambda x, y=None: 0.1
        
        recommendations = recommender.recommend_spot_instances(workload_id)
        
        assert len(recommendations) > 0
        rec = recommendations[0]
        
        # Unknown workload type should not be suitable
        assert rec.suitable is False
        assert 'unknown' in rec.reason.lower() or 'not suitable' in rec.reason.lower()
    
    @settings(max_examples=100)
    @given(
        workload_id=st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        instance_type=instance_type_strategy(),
        training_hours=st.floats(min_value=1.0, max_value=168.0)
    )
    def test_suitability_reason_is_provided(
        self, workload_id, instance_type, training_hours
    ):
        """
        Property: All recommendations should include a reason for suitability decision
        
        Feature: ai-ml-workload-costs, Property 11: Spot Suitability Criteria
        Validates: Requirements FR-5.1
        """
        recommender = SpotInstanceRecommender()
        
        # Mock workload metadata
        recommender._get_workload_metadata = lambda x: {
            'instance_type': instance_type,
            'workload_type': 'training',
            'duration_hours': training_hours,
            'state': 'running'
        }
        
        # Mock pricing
        recommender._get_on_demand_price = lambda x: 10.0
        recommender._get_spot_price = lambda x: 3.0
        recommender._get_interruption_risk = lambda x, y=None: 0.1
        
        recommendations = recommender.recommend_spot_instances(workload_id)
        
        assert len(recommendations) > 0
        rec = recommendations[0]
        
        # Reason should always be provided
        assert rec.reason is not None
        assert len(rec.reason) > 0
        assert isinstance(rec.reason, str)
    
    @settings(max_examples=100)
    @given(
        workload_id=st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        instance_type=instance_type_strategy(),
        training_hours=st.floats(min_value=1.0, max_value=168.0)
    )
    def test_suitable_workloads_have_positive_savings(
        self, workload_id, instance_type, training_hours
    ):
        """
        Property: Spot suitable workloads should show positive savings
        
        Feature: ai-ml-workload-costs, Property 11: Spot Suitability Criteria
        Validates: Requirements FR-5.1, FR-5.2
        """
        recommender = SpotInstanceRecommender()
        
        # Mock workload metadata for training workload
        recommender._get_workload_metadata = lambda x: {
            'instance_type': instance_type,
            'workload_type': 'training',
            'duration_hours': training_hours,
            'state': 'running'
        }
        
        # Mock pricing with guaranteed discount
        on_demand_price = 10.0
        spot_price = 3.0
        recommender._get_on_demand_price = lambda x: on_demand_price
        recommender._get_spot_price = lambda x: spot_price
        recommender._get_interruption_risk = lambda x, y=None: 0.1
        
        recommendations = recommender.recommend_spot_instances(workload_id)
        
        assert len(recommendations) > 0
        rec = recommendations[0]
        
        # If suitable, should have positive savings
        if rec.suitable:
            assert rec.savings > 0
            assert rec.savings_percent > 0
            assert rec.spot_cost < rec.current_cost
    
    @settings(max_examples=100)
    @given(
        workload_id=st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        instance_type=instance_type_strategy(),
        workload_type=st.sampled_from(['training', 'inference', 'idle', 'unknown']),
        duration_hours=st.floats(min_value=0.1, max_value=168.0)
    )
    def test_suitability_is_deterministic(
        self, workload_id, instance_type, workload_type, duration_hours
    ):
        """
        Property: Suitability decision should be deterministic for same inputs
        
        Feature: ai-ml-workload-costs, Property 11: Spot Suitability Criteria
        Validates: Requirements FR-5.1
        """
        recommender = SpotInstanceRecommender()
        
        # Mock workload metadata
        recommender._get_workload_metadata = lambda x: {
            'instance_type': instance_type,
            'workload_type': workload_type,
            'duration_hours': duration_hours,
            'state': 'running'
        }
        
        # Mock pricing
        recommender._get_on_demand_price = lambda x: 10.0
        recommender._get_spot_price = lambda x: 3.0
        recommender._get_interruption_risk = lambda x, y=None: 0.1
        
        # Get recommendations twice
        recommendations1 = recommender.recommend_spot_instances(workload_id)
        recommendations2 = recommender.recommend_spot_instances(workload_id)
        
        assert len(recommendations1) > 0
        assert len(recommendations2) > 0
        
        # Suitability should be the same
        assert recommendations1[0].suitable == recommendations2[0].suitable
        assert recommendations1[0].reason == recommendations2[0].reason


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
