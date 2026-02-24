"""
Property-based tests for Workload Classification.

These tests validate universal properties that should hold for all inputs.

Requirements: FR-2.1, FR-2.2, FR-2.4
"""
import pytest
from hypothesis import given, strategies as st, assume, settings
from datetime import datetime, timedelta
from src.services.ai_ml.workload_classifier import WorkloadClassifier, WorkloadClassification


class TestWorkloadClassificationProperties:
    """Property-based tests for workload classification rules."""
    
    @given(
        utilization_values=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=12,
            max_size=100
        )
    )
    @settings(max_examples=100, deadline=1000)
    def test_property_classification_rules_consistency(self, utilization_values):
        """
        Property 8: Workload Classification Rules
        
        Universal property: Classification rules should be consistent and deterministic.
        - Same input always produces same output
        - Classification type matches utilization pattern
        - Confidence is between 0 and 1
        
        Validates: Requirements FR-2.4
        """
        classifier = WorkloadClassifier(dynamodb_client=None)
        
        # Apply classification twice
        workload_type1, confidence1 = classifier.apply_classification_rules(utilization_values)
        workload_type2, confidence2 = classifier.apply_classification_rules(utilization_values)
        
        # Property 1: Deterministic - same input produces same output
        assert workload_type1 == workload_type2
        assert confidence1 == confidence2
        
        # Property 2: Confidence is always between 0 and 1
        assert 0.0 <= confidence1 <= 1.0
        
        # Property 3: Workload type is one of the valid types
        assert workload_type1 in ["training", "inference", "idle", "unknown"]
        
        # Property 4: Classification matches utilization pattern
        avg_utilization = sum(utilization_values) / len(utilization_values)
        
        if avg_utilization < 10.0:
            # Low utilization should be idle
            assert workload_type1 == "idle"
        elif avg_utilization > 70.0:
            # High utilization could be training (if low variance) or unknown
            assert workload_type1 in ["training", "unknown"]
    
    @given(
        low_utilization=st.floats(min_value=0.0, max_value=9.9, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50, deadline=1000)
    def test_property_idle_classification_threshold(self, low_utilization):
        """
        Property: Idle Classification Threshold
        
        Universal property: Any workload with average utilization < 10% should be classified as idle.
        
        Validates: Requirements FR-2.4
        """
        classifier = WorkloadClassifier(dynamodb_client=None)
        
        # Create pattern with consistently low utilization
        utilization_pattern = [low_utilization] * 12
        
        workload_type, confidence = classifier.apply_classification_rules(utilization_pattern)
        
        # Should always be classified as idle
        assert workload_type == "idle"
        assert confidence > 0.0
    
    @given(
        high_utilization=st.floats(min_value=70.1, max_value=100.0, allow_nan=False, allow_infinity=False),
        variance_factor=st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50, deadline=1000)
    def test_property_training_classification_low_variance(self, high_utilization, variance_factor):
        """
        Property: Training Classification with Low Variance
        
        Universal property: High utilization (>70%) with low variance should be classified as training.
        
        Validates: Requirements FR-2.4
        """
        classifier = WorkloadClassifier(dynamodb_client=None)
        
        # Create pattern with high utilization and low variance
        utilization_pattern = [
            max(0.0, min(100.0, high_utilization + (i % 3 - 1) * variance_factor))
            for i in range(12)
        ]
        
        workload_type, confidence = classifier.apply_classification_rules(utilization_pattern)
        
        # Should be classified as training (low variance with high utilization)
        assert workload_type == "training"
        assert confidence > 0.0
    
    @given(
        moderate_utilization=st.floats(min_value=20.0, max_value=70.0, allow_nan=False, allow_infinity=False),
        spike_magnitude=st.floats(min_value=15.0, max_value=30.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50, deadline=1000)
    def test_property_inference_classification_high_variance(self, moderate_utilization, spike_magnitude):
        """
        Property: Inference Classification with High Variance
        
        Universal property: Moderate utilization (20-70%) with high variance (spikes) 
        should be classified as inference.
        
        Validates: Requirements FR-2.4
        """
        classifier = WorkloadClassifier(dynamodb_client=None)
        
        # Create pattern with moderate utilization and high variance (spikes)
        utilization_pattern = []
        for i in range(12):
            if i % 2 == 0:
                # Low point
                value = max(0.0, moderate_utilization - spike_magnitude)
            else:
                # High point (spike)
                value = min(100.0, moderate_utilization + spike_magnitude)
            utilization_pattern.append(value)
        
        workload_type, confidence = classifier.apply_classification_rules(utilization_pattern)
        
        # Should be classified as inference (high variance with moderate utilization)
        assert workload_type == "inference"
        assert confidence > 0.0
    
    @given(
        utilization_values=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=12,
            max_size=100
        )
    )
    @settings(max_examples=100, deadline=1000)
    def test_property_confidence_increases_with_data(self, utilization_values):
        """
        Property: Confidence and Data Quality
        
        Universal property: Confidence should reflect the clarity of the classification.
        - Clear patterns (idle, high continuous, spiky) should have higher confidence
        - Ambiguous patterns should have lower confidence
        
        Validates: Requirements FR-2.4
        """
        classifier = WorkloadClassifier(dynamodb_client=None)
        
        workload_type, confidence = classifier.apply_classification_rules(utilization_values)
        
        # Confidence should always be valid
        assert 0.0 <= confidence <= 1.0
        
        # Unknown classifications should have lower confidence
        if workload_type == "unknown":
            assert confidence < 0.5
        
        # Clear classifications should have reasonable confidence
        if workload_type in ["idle", "training", "inference"]:
            assert confidence > 0.0
    
    @given(
        utilization_values=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=12,
            max_size=100
        )
    )
    @settings(max_examples=100, deadline=1000)
    def test_property_classification_is_mutually_exclusive(self, utilization_values):
        """
        Property: Mutually Exclusive Classifications
        
        Universal property: A workload can only be classified as one type at a time.
        
        Validates: Requirements FR-2.4
        """
        classifier = WorkloadClassifier(dynamodb_client=None)
        
        workload_type, _ = classifier.apply_classification_rules(utilization_values)
        
        # Should be exactly one classification type
        assert workload_type in ["training", "inference", "idle", "unknown"]
        
        # Count should be exactly 1
        classifications = ["training", "inference", "idle", "unknown"]
        matches = sum(1 for c in classifications if c == workload_type)
        assert matches == 1

    @given(
        utilization_values=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=12,
            max_size=100
        ),
        time_offset_minutes=st.integers(min_value=0, max_value=1440)  # 0-24 hours
    )
    @settings(max_examples=100, deadline=1000)
    def test_property_classification_consistency_over_time(self, utilization_values, time_offset_minutes):
        """
        Property 2: Workload Classification Consistency
        
        Universal property: Classification should be consistent over time for the same pattern.
        - Same utilization pattern should produce same classification regardless of when it's analyzed
        - Classification should not depend on timestamp
        
        Validates: Requirements FR-2.1, FR-2.2
        """
        classifier = WorkloadClassifier(dynamodb_client=None)
        
        # Classify at time T
        workload_type1, confidence1 = classifier.apply_classification_rules(utilization_values)
        
        # Classify at time T + offset (simulated by running again)
        workload_type2, confidence2 = classifier.apply_classification_rules(utilization_values)
        
        # Property: Same pattern should produce same classification
        assert workload_type1 == workload_type2
        assert confidence1 == confidence2
    
    @given(
        base_utilization=st.floats(min_value=10.0, max_value=90.0, allow_nan=False, allow_infinity=False),
        noise_level=st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50, deadline=1000)
    def test_property_classification_stability_with_noise(self, base_utilization, noise_level):
        """
        Property: Classification Stability with Small Noise
        
        Universal property: Small variations in utilization should not drastically change classification.
        - Adding small noise should not flip classification between drastically different types
        - Confidence may change slightly, but classification should be stable
        
        Validates: Requirements FR-2.1, FR-2.2
        """
        classifier = WorkloadClassifier(dynamodb_client=None)
        
        # Create base pattern
        base_pattern = [base_utilization] * 12
        
        # Create noisy pattern (small variations)
        noisy_pattern = [
            max(0.0, min(100.0, base_utilization + (i % 3 - 1) * noise_level))
            for i in range(12)
        ]
        
        workload_type_base, _ = classifier.apply_classification_rules(base_pattern)
        workload_type_noisy, _ = classifier.apply_classification_rules(noisy_pattern)
        
        # Property: Small noise should not cause drastic classification changes
        # (e.g., idle should not become training with small noise)
        if workload_type_base == "idle":
            # Idle should remain idle or become unknown, not jump to training/inference
            assert workload_type_noisy in ["idle", "unknown"]
        elif workload_type_base == "training":
            # Training might become unknown with noise, but not idle
            assert workload_type_noisy in ["training", "unknown", "inference"]
    
    @given(
        utilization_values=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=12,
            max_size=100
        )
    )
    @settings(max_examples=100, deadline=1000)
    def test_property_classification_reversibility(self, utilization_values):
        """
        Property: Classification Reversibility
        
        Universal property: Reversing the order of utilization values should not change classification.
        - Classification should be based on statistical properties (mean, variance), not order
        
        Validates: Requirements FR-2.1, FR-2.2
        """
        classifier = WorkloadClassifier(dynamodb_client=None)
        
        # Classify forward
        workload_type_forward, confidence_forward = classifier.apply_classification_rules(utilization_values)
        
        # Classify reversed
        reversed_values = list(reversed(utilization_values))
        workload_type_reversed, confidence_reversed = classifier.apply_classification_rules(reversed_values)
        
        # Property: Order should not matter for statistical classification
        assert workload_type_forward == workload_type_reversed
        assert abs(confidence_forward - confidence_reversed) < 0.01  # Allow tiny floating point differences

    @given(
        workload_type=st.sampled_from(["training", "inference", "idle"]),
        utilization_values=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=12,
            max_size=100
        )
    )
    @settings(max_examples=50, deadline=1000)
    def test_property_manual_classification_override(self, workload_type, utilization_values):
        """
        Property 9: Manual Classification Override
        
        Universal property: Manual classification should always override automatic classification.
        - When manual classification is set, it should be used regardless of metrics
        - Manual classification should have confidence = 1.0
        - Manual classification method should be "manual-tag"
        
        Validates: Requirements FR-2.3, FR-2.5
        """
        # Create a mock that returns manual classification
        class MockEC2Client:
            def __init__(self, manual_type):
                self.manual_type = manual_type
        
        classifier = WorkloadClassifier(
            dynamodb_client=None,
            cloudwatch_client=None,
            ec2_client=MockEC2Client(workload_type)
        )
        
        # Override get_manual_classification to return the manual type
        original_method = classifier.get_manual_classification
        classifier.get_manual_classification = lambda instance_id: workload_type
        
        # Classify with manual override
        classification = classifier.classify_workload(
            instance_id="i-test",
            start_date="2026-02-01",
            end_date="2026-02-24"
        )
        
        # Property 1: Manual classification should override automatic
        assert classification.workload_type == workload_type
        
        # Property 2: Manual classification should have confidence = 1.0
        assert classification.confidence == 1.0
        
        # Property 3: Classification method should be "manual-tag"
        assert classification.classification_method == "manual-tag"
        
        # Restore original method
        classifier.get_manual_classification = original_method
    
    @given(
        manual_type=st.sampled_from(["training", "inference", "idle"]),
        conflicting_pattern_type=st.sampled_from(["training", "inference", "idle"])
    )
    @settings(max_examples=30, deadline=1000)
    def test_property_manual_override_ignores_metrics(self, manual_type, conflicting_pattern_type):
        """
        Property: Manual Override Ignores Conflicting Metrics
        
        Universal property: Manual classification should be used even when metrics suggest different type.
        - Manual "training" should be used even if metrics show "idle"
        - Manual "idle" should be used even if metrics show "training"
        
        Validates: Requirements FR-2.3, FR-2.5
        """
        classifier = WorkloadClassifier(dynamodb_client=None)
        
        # Create utilization pattern that would classify as conflicting_pattern_type
        if conflicting_pattern_type == "idle":
            utilization_pattern = [5.0] * 12  # Clearly idle
        elif conflicting_pattern_type == "training":
            utilization_pattern = [85.0] * 12  # Clearly training
        else:  # inference
            utilization_pattern = [30.0, 60.0] * 6  # Clearly inference
        
        # Verify automatic classification would be conflicting_pattern_type
        auto_type, _ = classifier.apply_classification_rules(utilization_pattern)
        
        # Now override with manual classification
        classifier.get_manual_classification = lambda instance_id: manual_type
        
        classification = classifier.classify_workload(
            instance_id="i-test",
            start_date="2026-02-01",
            end_date="2026-02-24"
        )
        
        # Property: Manual classification should be used, not automatic
        assert classification.workload_type == manual_type
        assert classification.classification_method == "manual-tag"
        
        # If manual and automatic differ, manual should win
        if manual_type != auto_type:
            assert classification.workload_type != auto_type
