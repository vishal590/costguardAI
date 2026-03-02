"""
Property-based tests for Idle GPU Detector.

Tests universal properties that should hold for all idle GPU detection scenarios.

Requirements: FR-1.5
"""
import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from unittest.mock import Mock
from src.services.ai_ml.idle_detector import IdleGPUDetector


# Strategy for generating GPU utilization data
gpu_utilization_strategy = st.lists(
    st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=100
)


class TestIdleDetectorProperties:
    """Property-based tests for IdleGPUDetector."""
    
    @given(utilization_data=gpu_utilization_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_idle_detection_threshold(self, utilization_data):
        """
        Property 4: Idle GPU Detection
        
        For any GPU instance with average utilization below 10%, the system should
        classify it as idle; for any instance with average utilization above 10%,
        it should not be classified as idle.
        
        **Validates: Requirements FR-1.5**
        
        Feature: ai-ml-workload-costs, Property 4: Idle GPU Detection
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # Calculate average utilization
        avg_utilization = sum(utilization_data) / len(utilization_data)
        
        # Mock GPU instances
        detector._get_gpu_instances = Mock(return_value=[
            {'instance_id': 'i-test-123', 'instance_type': 'p3.2xlarge'}
        ])
        
        # Mock utilization data
        detector._get_gpu_utilization = Mock(return_value=utilization_data)
        
        # Execute
        idle_gpus = detector.identify_idle_gpus(
            '2026-02-01',
            '2026-02-24',
            threshold=10.0
        )
        
        # Verify property
        if avg_utilization < 10.0:
            # Should be classified as idle
            assert len(idle_gpus) == 1, \
                f"GPU with {avg_utilization:.2f}% utilization should be idle"
            assert idle_gpus[0].instance_id == 'i-test-123'
            assert idle_gpus[0].utilization < 10.0
        else:
            # Should NOT be classified as idle
            assert len(idle_gpus) == 0, \
                f"GPU with {avg_utilization:.2f}% utilization should NOT be idle"
    
    @given(
        utilization_data=gpu_utilization_strategy,
        threshold=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_idle_detection_custom_threshold(self, utilization_data, threshold):
        """
        Property: Idle detection respects custom thresholds
        
        For any GPU instance and any threshold, instances with average utilization
        below the threshold should be classified as idle, and instances above should not.
        
        **Validates: Requirements FR-1.5**
        
        Feature: ai-ml-workload-costs, Property: Custom threshold idle detection
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # Calculate average utilization
        avg_utilization = sum(utilization_data) / len(utilization_data)
        
        # Mock GPU instances
        detector._get_gpu_instances = Mock(return_value=[
            {'instance_id': 'i-test-456', 'instance_type': 'g4dn.xlarge'}
        ])
        
        # Mock utilization data
        detector._get_gpu_utilization = Mock(return_value=utilization_data)
        
        # Execute
        idle_gpus = detector.identify_idle_gpus(
            '2026-02-01',
            '2026-02-24',
            threshold=threshold
        )
        
        # Verify property
        # Note: Idle detection uses strict less-than comparison (< threshold)
        # For edge cases where avg_utilization equals threshold (within floating point tolerance),
        # we skip the test since the behavior is undefined at the boundary
        tolerance = 0.0001
        if abs(avg_utilization - threshold) < tolerance:
            # Skip edge case where values are essentially equal
            assume(False)
        
        if avg_utilization < threshold:
            assert len(idle_gpus) == 1, \
                f"GPU with {avg_utilization:.2f}% utilization should be idle (threshold: {threshold:.2f}%)"
        else:
            assert len(idle_gpus) == 0, \
                f"GPU with {avg_utilization:.2f}% utilization should NOT be idle (threshold: {threshold:.2f}%)"
    
    @given(
        utilization_data=gpu_utilization_strategy,
        instance_type=st.sampled_from([
            'p3.2xlarge', 'p4d.24xlarge', 'p5.48xlarge',
            'g4dn.xlarge', 'g5.xlarge'
        ])
    )
    @settings(max_examples=100, deadline=None)
    def test_property_wasted_cost_calculation(self, utilization_data, instance_type):
        """
        Property: Wasted cost is proportional to idle time and hourly cost
        
        For any GPU instance, the wasted cost should equal idle_hours * cost_per_hour.
        
        **Validates: Requirements FR-1.5**
        
        Feature: ai-ml-workload-costs, Property: Wasted cost calculation
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # Calculate average utilization
        avg_utilization = sum(utilization_data) / len(utilization_data)
        
        # Only test idle instances
        assume(avg_utilization < 10.0)
        
        # Mock GPU instances
        detector._get_gpu_instances = Mock(return_value=[
            {'instance_id': 'i-test-789', 'instance_type': instance_type}
        ])
        
        # Mock utilization data
        detector._get_gpu_utilization = Mock(return_value=utilization_data)
        
        # Execute
        idle_gpus = detector.identify_idle_gpus(
            '2026-02-01T00:00:00',
            '2026-02-01T10:00:00',  # 10 hours
            threshold=10.0
        )
        
        # Verify property
        # Note: Idle detection uses strict less-than comparison (< threshold)
        # When avg_utilization equals threshold exactly, it's NOT classified as idle
        # So we need to ensure avg_utilization is strictly less than threshold
        # Use a small tolerance to avoid floating point edge cases
        if avg_utilization >= 9.9999:
            # Skip this test case - not idle or too close to threshold
            assume(False)
        
        assert len(idle_gpus) == 1
        idle_gpu = idle_gpus[0]
        
        # Wasted cost should equal idle_hours * cost_per_hour
        expected_wasted_cost = idle_gpu.idle_hours * idle_gpu.cost_per_hour
        assert abs(idle_gpu.wasted_cost - expected_wasted_cost) < 0.01, \
            f"Wasted cost {idle_gpu.wasted_cost} != idle_hours {idle_gpu.idle_hours} * cost_per_hour {idle_gpu.cost_per_hour}"
    
    @given(utilization_data=gpu_utilization_strategy)
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_property_idle_hours_bounded(self, utilization_data):
        """
        Property: Idle hours cannot exceed total time range
        
        For any GPU instance, the calculated idle hours should be between 0 and
        the total time range.
        
        **Validates: Requirements FR-1.5**
        
        Feature: ai-ml-workload-costs, Property: Idle hours bounds
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # Calculate average utilization
        avg_utilization = sum(utilization_data) / len(utilization_data)
        
        # Only test idle instances
        assume(avg_utilization < 10.0)
        
        # Mock GPU instances
        detector._get_gpu_instances = Mock(return_value=[
            {'instance_id': 'i-test-999', 'instance_type': 'p3.2xlarge'}
        ])
        
        # Mock utilization data
        detector._get_gpu_utilization = Mock(return_value=utilization_data)
        
        # Execute with 24-hour time range
        idle_gpus = detector.identify_idle_gpus(
            '2026-02-01T00:00:00',
            '2026-02-02T00:00:00',  # 24 hours
            threshold=10.0
        )
        
        # Verify property
        assert len(idle_gpus) == 1
        idle_gpu = idle_gpus[0]
        
        # Idle hours should be between 0 and 24
        assert 0.0 <= idle_gpu.idle_hours <= 24.0, \
            f"Idle hours {idle_gpu.idle_hours} should be between 0 and 24"
    
    @given(
        utilization_data=gpu_utilization_strategy,
        threshold=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_severity_monotonic(self, utilization_data, threshold):
        """
        Property: Alert severity increases with wasted cost
        
        For any two idle GPUs, if GPU A has higher wasted cost than GPU B,
        then GPU A's severity should be >= GPU B's severity.
        
        **Validates: Requirements FR-1.5**
        
        Feature: ai-ml-workload-costs, Property: Severity monotonicity
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # Calculate average utilization
        avg_utilization = sum(utilization_data) / len(utilization_data)
        
        # Only test idle instances
        assume(avg_utilization < threshold)
        
        # Create two idle GPUs with different costs
        detector._get_gpu_instances = Mock(return_value=[
            {'instance_id': 'i-cheap-123', 'instance_type': 'g4dn.xlarge'},  # $0.526/hour
            {'instance_id': 'i-expensive-456', 'instance_type': 'p5.48xlarge'}  # $98.32/hour
        ])
        
        # Mock same utilization for both
        detector._get_gpu_utilization = Mock(return_value=utilization_data)
        
        # Execute
        alerts = detector.generate_idle_alerts(
            '2026-02-01T00:00:00',
            '2026-02-02T00:00:00',  # 24 hours
            threshold=threshold
        )
        
        # Verify property
        if len(alerts) == 2:
            # Find alerts by instance
            cheap_alert = next(a for a in alerts if a.instance_id == 'i-cheap-123')
            expensive_alert = next(a for a in alerts if a.instance_id == 'i-expensive-456')
            
            # Expensive GPU should have higher or equal severity
            severity_order = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
            
            assert severity_order[expensive_alert.severity] >= severity_order[cheap_alert.severity], \
                f"Expensive GPU (${expensive_alert.wasted_cost:.2f}) should have >= severity than cheap GPU (${cheap_alert.wasted_cost:.2f})"
    
    @given(utilization_data=gpu_utilization_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_idle_ratio_consistency(self, utilization_data):
        """
        Property: Idle hours ratio matches idle data points ratio
        
        For any GPU instance, the ratio of idle hours to total hours should
        approximately equal the ratio of idle data points to total data points.
        
        **Validates: Requirements FR-1.5**
        
        Feature: ai-ml-workload-costs, Property: Idle ratio consistency
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # Calculate idle ratio from data
        idle_points = sum(1 for util in utilization_data if util < 10.0)
        idle_ratio = idle_points / len(utilization_data)
        
        # Only test if there's some idle time
        assume(idle_ratio > 0.0)
        
        # Mock utilization data
        detector._get_gpu_utilization = Mock(return_value=utilization_data)
        
        # Execute with 10-hour time range
        idle_hours = detector.calculate_idle_time(
            'i-test-123',
            '2026-02-01T00:00:00',
            '2026-02-01T10:00:00',  # 10 hours
            threshold=10.0
        )
        
        # Verify property
        expected_idle_hours = 10.0 * idle_ratio
        assert abs(idle_hours - expected_idle_hours) < 0.1, \
            f"Idle hours {idle_hours} should approximately equal {expected_idle_hours} (ratio: {idle_ratio})"
    
    @given(
        utilization_data=gpu_utilization_strategy,
        instance_type=st.sampled_from([
            'p3.2xlarge', 'p4d.24xlarge', 'g4dn.xlarge'
        ])
    )
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_property_recommendation_consistency(self, utilization_data, instance_type):
        """
        Property: Recommendations are consistent with utilization levels
        
        For any GPU instance:
        - If avg utilization < 5%, recommendation should be "STOP"
        - If avg utilization < 10% and high cost, recommendation should be "STOP"
        - If avg utilization < 10%, recommendation should be "REVIEW" or "STOP"
        - Otherwise, recommendation should be "MONITOR"
        
        **Validates: Requirements FR-1.5**
        
        Feature: ai-ml-workload-costs, Property: Recommendation consistency
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # Calculate average utilization
        avg_utilization = sum(utilization_data) / len(utilization_data)
        
        # Only test idle instances
        assume(avg_utilization < 10.0)
        
        # Mock GPU instances
        detector._get_gpu_instances = Mock(return_value=[
            {'instance_id': 'i-test-rec', 'instance_type': instance_type}
        ])
        
        # Mock utilization data
        detector._get_gpu_utilization = Mock(return_value=utilization_data)
        
        # Execute with 100-hour time range to get significant cost
        idle_gpus = detector.identify_idle_gpus(
            '2026-02-01T00:00:00',
            '2026-02-05T04:00:00',  # 100 hours
            threshold=10.0
        )
        
        # Verify property
        assert len(idle_gpus) == 1
        idle_gpu = idle_gpus[0]
        recommendation = idle_gpu.recommendation
        
        if avg_utilization < 5.0:
            assert 'STOP' in recommendation, \
                f"GPU with {avg_utilization:.2f}% utilization should have STOP recommendation"
        elif avg_utilization < 10.0 and idle_gpu.wasted_cost > 100.0:
            assert 'STOP' in recommendation, \
                f"Idle GPU with ${idle_gpu.wasted_cost:.2f} wasted cost should have STOP recommendation"
        elif avg_utilization < 10.0:
            assert 'REVIEW' in recommendation or 'STOP' in recommendation, \
                f"Idle GPU should have REVIEW or STOP recommendation"
        else:
            assert 'MONITOR' in recommendation, \
                f"GPU with {avg_utilization:.2f}% utilization should have MONITOR recommendation"
