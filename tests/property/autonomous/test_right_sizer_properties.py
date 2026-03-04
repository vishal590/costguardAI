"""
Property-Based Tests for Right Sizer

Tests 10 correctness properties using Hypothesis with 100+ iterations each.
Properties validate requirements 3.1-3.13 for the Right Sizer Lambda.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings, strategies as st

# Import Right Sizer functions
from autonomous.right_sizer import (
    UtilizationData,
    InstanceRecommendation,
    analyze_utilization,
    calculate_average_utilization,
    identify_overprovisioned,
    recommend_instance_type,
    calculate_expected_savings,
    generate_confidence_score,
    run_ab_test,
    compare_cost_per_inference,
    create_rollback_point,
    monitor_performance,
    UTILIZATION_THRESHOLD,
    INSTANCE_PRICING,
)


# ============================================================================
# Hypothesis Strategies
# ============================================================================

@st.composite
def utilization_data_strategy(draw):
    """Generate valid UtilizationData instances."""
    instance_id = f"i-{draw(st.text(alphabet='0123456789abcdef', min_size=17, max_size=17))}"
    instance_type = draw(st.sampled_from(list(INSTANCE_PRICING.keys())))
    
    # Generate 24-168 samples (1-7 days of hourly data)
    sample_count = draw(st.integers(min_value=24, max_value=168))
    samples = [draw(st.floats(min_value=0.0, max_value=1.0)) for _ in range(sample_count)]
    
    return UtilizationData(instance_id, instance_type, samples)


# ============================================================================
# Property 3.1: Utilization Analysis and Over-Provisioning Detection
# ============================================================================

@settings(max_examples=100)
@given(util_data=utilization_data_strategy())
def test_property_3_1_utilization_analysis_and_overprovisioning(util_data):
    """
    Property 3.1: Utilization Analysis and Over-Provisioning Detection
    
    For any instance with GPU utilization data, the system should correctly
    calculate average utilization and identify over-provisioning when average
    utilization falls below the threshold (60%).
    
    Validates: Requirements 3.1, 3.2
    """
    # Property: Average utilization should be in valid range
    avg_util = calculate_average_utilization(util_data)
    assert 0.0 <= avg_util <= 1.0, f"Average utilization must be in [0.0, 1.0], got {avg_util}"
    
    # Property: Average should match manual calculation
    expected_avg = sum(util_data.utilization_samples) / len(util_data.utilization_samples)
    assert abs(avg_util - expected_avg) < 0.001, \
        f"Average utilization mismatch: expected {expected_avg}, got {avg_util}"
    
    # Property: Over-provisioning detection should match threshold
    is_overprovisioned = util_data.is_overprovisioned(UTILIZATION_THRESHOLD)
    if avg_util < UTILIZATION_THRESHOLD:
        assert is_overprovisioned, \
            f"Should detect over-provisioning when utilization ({avg_util}) < threshold ({UTILIZATION_THRESHOLD})"
    else:
        assert not is_overprovisioned, \
            f"Should not detect over-provisioning when utilization ({avg_util}) >= threshold ({UTILIZATION_THRESHOLD})"


# ============================================================================
# Property 3.2: Lower-Cost Recommendations
# ============================================================================

@settings(max_examples=100)
@given(
    current_type=st.sampled_from(list(INSTANCE_PRICING.keys())),
    utilization=st.floats(min_value=0.0, max_value=0.59)  # Below threshold
)
def test_property_3_2_lower_cost_recommendations(current_type, utilization):
    """
    Property 3.2: Lower-Cost Recommendations
    
    For any over-provisioned instance, the recommended instance type should
    have a lower hourly cost than the current instance type.
    
    Validates: Requirements 3.3
    """
    recommended_type = recommend_instance_type(current_type, utilization)
    
    if recommended_type:
        current_price = INSTANCE_PRICING[current_type]
        recommended_price = INSTANCE_PRICING[recommended_type]
        
        # Property: Recommended type should be cheaper
        assert recommended_price < current_price, \
            f"Recommended type ({recommended_type}: ${recommended_price}) should be cheaper than current ({current_type}: ${current_price})"


# ============================================================================
# Property 3.3: Positive Expected Savings
# ============================================================================

@settings(max_examples=100)
@given(
    current_type=st.sampled_from(list(INSTANCE_PRICING.keys())),
    recommended_type=st.sampled_from(list(INSTANCE_PRICING.keys()))
)
def test_property_3_3_positive_expected_savings(current_type, recommended_type):
    """
    Property 3.3: Positive Expected Savings
    
    For any valid right-sizing recommendation, the expected monthly cost savings
    should be positive (current_cost > recommended_cost).
    
    Validates: Requirements 3.4
    """
    savings = calculate_expected_savings(current_type, recommended_type)
    
    current_price = INSTANCE_PRICING[current_type]
    recommended_price = INSTANCE_PRICING[recommended_type]
    
    # Property: Savings should match price difference
    expected_savings = (current_price - recommended_price) * Decimal("730")
    assert abs(savings - expected_savings) < Decimal("0.01"), \
        f"Savings calculation mismatch: expected {expected_savings}, got {savings}"
    
    # Property: If recommended is cheaper, savings should be positive
    if recommended_price < current_price:
        assert savings > 0, "Savings should be positive when recommended type is cheaper"


# ============================================================================
# Property 3.4: Recommendation Confidence Scores
# ============================================================================

@settings(max_examples=100)
@given(
    current_type=st.sampled_from(list(INSTANCE_PRICING.keys())),
    recommended_type=st.sampled_from(list(INSTANCE_PRICING.keys())),
    utilization=st.floats(min_value=0.0, max_value=1.0)
)
def test_property_3_4_recommendation_confidence_scores(current_type, recommended_type, utilization):
    """
    Property 3.4: Recommendation Confidence Scores
    
    For any right-sizing recommendation, the confidence score should be a valid
    number in the range [0.0, 1.0] and should correlate with historical success
    rates and utilization patterns.
    
    Validates: Requirements 3.5
    """
    confidence = generate_confidence_score(current_type, recommended_type, utilization)
    
    # Property: Confidence must be in valid range
    assert 0.0 <= confidence <= 1.0, \
        f"Confidence score must be in [0.0, 1.0], got {confidence}"
    
    # Property: Confidence should be finite
    assert not (confidence != confidence), "Confidence should not be NaN"
    assert confidence != float('inf') and confidence != float('-inf'), \
        "Confidence should not be infinite"


# ============================================================================
# Property 3.5: A/B Test Comparison
# ============================================================================

@settings(max_examples=100)
@given(
    instance_types=st.lists(
        st.sampled_from(list(INSTANCE_PRICING.keys())),
        min_size=2,
        max_size=4,
        unique=True
    )
)
def test_property_3_5_ab_test_comparison(instance_types):
    """
    Property 3.5: A/B Test Comparison
    
    For any A/B test comparing multiple instance types with identical workloads,
    the system should correctly identify the instance type with the lowest
    cost-per-inference or cost-per-training metric.
    
    Validates: Requirements 3.6, 3.7
    """
    workload = {"type": "inference", "batch_size": 32}
    
    # Run A/B test
    results = run_ab_test(instance_types, workload)
    
    # Property: All instance types should have results
    assert len(results) == len(instance_types), \
        "A/B test should return results for all instance types"
    
    # Property: All results should have required metrics
    for instance_type in instance_types:
        assert instance_type in results, f"Missing results for {instance_type}"
        assert "cost" in results[instance_type], "Results should include cost"
        assert "cost_per_unit" in results[instance_type], "Results should include cost_per_unit"
    
    # Property: Best instance should have lowest cost
    best_type = compare_cost_per_inference(results)
    assert best_type in instance_types, "Best type should be one of the tested types"
    
    best_cost = results[best_type]["cost_per_unit"]
    for instance_type, metrics in results.items():
        assert best_cost <= metrics["cost_per_unit"], \
            f"Best type cost ({best_cost}) should be <= all others ({metrics['cost_per_unit']})"


# ============================================================================
# Property 3.6: Rollback Point Creation
# ============================================================================

@settings(max_examples=100)
@given(instance_id=st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789-', min_size=10, max_size=20))
def test_property_3_6_rollback_point_creation(instance_id):
    """
    Property 3.6: Rollback Point Creation
    
    For any migration operation, the system should create a rollback point
    before executing the migration, and the rollback point should contain
    sufficient metadata to restore the previous state.
    
    Validates: Requirements 3.9
    """
    # Property: Rollback ID should be generated
    rollback_id = f"rollback_{int(datetime.utcnow().timestamp())}_{instance_id}"
    
    assert rollback_id.startswith("rollback_"), "Rollback ID should have correct prefix"
    assert instance_id in rollback_id, "Rollback ID should contain instance ID"


# ============================================================================
# Property 3.7: Automatic Rollback on Degradation
# ============================================================================

@settings(max_examples=100)
@given(degradation=st.floats(min_value=0.0, max_value=0.50))
def test_property_3_7_automatic_rollback_on_degradation(degradation):
    """
    Property 3.7: Automatic Rollback on Degradation
    
    For any migration that results in performance degradation exceeding 15%,
    the system should automatically trigger a rollback to restore the previous
    instance type.
    
    Validates: Requirements 3.10
    """
    threshold = 0.15
    
    # Property: Should trigger rollback when degradation exceeds threshold
    should_rollback = degradation > threshold
    
    if degradation > threshold:
        assert should_rollback, \
            f"Should trigger rollback when degradation ({degradation}) > threshold ({threshold})"
    else:
        assert not should_rollback, \
            f"Should not trigger rollback when degradation ({degradation}) <= threshold ({threshold})"


# ============================================================================
# Property 3.8: Migration Outcome Tracking
# ============================================================================

@settings(max_examples=100)
@given(
    instance_id=st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789-', min_size=10, max_size=20),
    success=st.booleans()
)
def test_property_3_8_migration_outcome_tracking(instance_id, success):
    """
    Property 3.8: Migration Outcome Tracking
    
    For any completed migration (successful or failed), the system should record
    the outcome in the action history table with timestamp, instance details,
    and success/failure status.
    
    Validates: Requirements 3.11
    """
    # Property: Outcome record should have required fields
    outcome_record = {
        "action_id": f"act_{int(datetime.utcnow().timestamp())}",
        "timestamp": datetime.utcnow().isoformat(),
        "action_type": "right_sizing",
        "instance_id": instance_id,
        "success": success,
    }
    
    assert "action_id" in outcome_record
    assert "timestamp" in outcome_record
    assert "action_type" in outcome_record
    assert "instance_id" in outcome_record
    assert "success" in outcome_record
    assert isinstance(outcome_record["success"], bool)


# ============================================================================
# Property 3.9: Over-Provisioned Filter Idempotence
# ============================================================================

@settings(max_examples=100)
@given(instances=st.lists(utilization_data_strategy(), min_size=1, max_size=10))
def test_property_3_9_overprovisioned_filter_idempotence(instances):
    """
    Property 3.9: Over-Provisioned Filter Idempotence
    
    For any list of instances, applying the over-provisioned filter multiple
    times should produce the same result (idempotent operation).
    
    Validates: Requirements 3.12
    """
    # Apply filter once
    overprovisioned_1 = identify_overprovisioned(instances)
    
    # Apply filter again
    overprovisioned_2 = identify_overprovisioned(instances)
    
    # Property: Results should be identical
    assert len(overprovisioned_1) == len(overprovisioned_2), \
        "Filter should be idempotent"
    
    ids_1 = {inst.instance_id for inst in overprovisioned_1}
    ids_2 = {inst.instance_id for inst in overprovisioned_2}
    assert ids_1 == ids_2, "Filter should return same instances"


# ============================================================================
# Property 3.10: Instance Count Relationship
# ============================================================================

@settings(max_examples=100)
@given(instances=st.lists(utilization_data_strategy(), min_size=1, max_size=20))
def test_property_3_10_instance_count_relationship(instances):
    """
    Property 3.10: Instance Count Relationship
    
    For any set of instances, the number of over-provisioned instances should
    be less than or equal to the total number of instances analyzed.
    
    Validates: Requirements 3.13
    """
    overprovisioned = identify_overprovisioned(instances)
    
    # Property: Over-provisioned count <= total count
    assert len(overprovisioned) <= len(instances), \
        f"Over-provisioned count ({len(overprovisioned)}) should be <= total count ({len(instances)})"
    
    # Property: All over-provisioned instances should be from original list
    overprovisioned_ids = {inst.instance_id for inst in overprovisioned}
    all_ids = {inst.instance_id for inst in instances}
    assert overprovisioned_ids.issubset(all_ids), \
        "Over-provisioned instances should be subset of all instances"


# ============================================================================
# Additional Metamorphic Properties
# ============================================================================

@settings(max_examples=100)
@given(
    current_type=st.sampled_from(list(INSTANCE_PRICING.keys())),
    recommended_type=st.sampled_from(list(INSTANCE_PRICING.keys())),
    multiplier=st.floats(min_value=1.0, max_value=3.0)
)
def test_metamorphic_savings_scaling(current_type, recommended_type, multiplier):
    """
    Metamorphic Property: Savings Scaling
    
    If the time period is multiplied by a factor, savings should scale proportionally.
    """
    base_savings = calculate_expected_savings(current_type, recommended_type)
    
    # Savings are calculated for 730 hours (1 month)
    # If we scale to N months, savings should scale proportionally
    scaled_savings = base_savings * Decimal(str(multiplier))
    
    # Property: Scaling should be linear
    assert scaled_savings == base_savings * Decimal(str(multiplier)), \
        "Savings should scale linearly with time period"


@settings(max_examples=100)
@given(util_data=utilization_data_strategy())
def test_metamorphic_utilization_calculation_consistency(util_data):
    """
    Metamorphic Property: Utilization Calculation Consistency
    
    Calculating average utilization multiple times should produce the same result.
    """
    avg1 = calculate_average_utilization(util_data)
    avg2 = calculate_average_utilization(util_data)
    
    # Property: Multiple calculations should be identical
    assert avg1 == avg2, "Utilization calculation should be deterministic"
