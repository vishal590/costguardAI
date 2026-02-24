"""
Integration tests for Workload Classification.

Tests the workload classifier with various GPU utilization patterns
and manual override functionality.

Requirements: FR-2.1, FR-2.3
"""
import pytest
from unittest.mock import Mock, MagicMock
from src.services.ai_ml.workload_classifier import WorkloadClassifier, WorkloadClassification


class TestWorkloadClassificationIntegration:
    """Integration tests for workload classification with various utilization patterns."""
    
    def test_classify_training_workload_high_continuous_utilization(self):
        """
        Test classification of training workload with high continuous GPU utilization.
        Requirements: FR-2.1, FR-2.4
        """
        # Setup
        mock_dynamodb = Mock()
        classifier = WorkloadClassifier(mock_dynamodb)
        
        # Mock high continuous utilization pattern (training)
        high_utilization = [85.0, 87.0, 84.0, 86.0, 85.5, 86.5, 85.0, 87.5, 86.0, 85.5, 86.5, 85.0]
        classifier.get_gpu_utilization_pattern = Mock(return_value=high_utilization)
        classifier.get_manual_classification = Mock(return_value=None)
        classifier.store_classification = Mock()
        
        # Execute
        classification = classifier.classify_workload('i-training-123', '2026-02-01', '2026-02-24')
        
        # Verify
        assert classification.workload_type == 'training'
        assert classification.confidence > 0.8
        assert classification.classification_method == 'cloudwatch-metrics'
        assert classification.gpu_utilization_avg > 70.0
        assert len(classification.gpu_utilization_pattern) == 12
        
        # Verify classification was stored
        classifier.store_classification.assert_called_once()
    
    def test_classify_inference_workload_moderate_spiky_utilization(self):
        """
        Test classification of inference workload with moderate spiky GPU utilization.
        Requirements: FR-2.1, FR-2.4
        """
        # Setup
        mock_dynamodb = Mock()
        classifier = WorkloadClassifier(mock_dynamodb)
        
        # Mock moderate spiky utilization pattern (inference)
        spiky_utilization = [30.0, 60.0, 25.0, 65.0, 35.0, 55.0, 28.0, 62.0, 32.0, 58.0, 27.0, 63.0]
        classifier.get_gpu_utilization_pattern = Mock(return_value=spiky_utilization)
        classifier.get_manual_classification = Mock(return_value=None)
        classifier.store_classification = Mock()
        
        # Execute
        classification = classifier.classify_workload('i-inference-456', '2026-02-01', '2026-02-24')
        
        # Verify
        assert classification.workload_type == 'inference'
        assert classification.confidence > 0.7
        assert classification.classification_method == 'cloudwatch-metrics'
        assert 20.0 <= classification.gpu_utilization_avg <= 70.0
        assert len(classification.gpu_utilization_pattern) == 12
        
        # Verify classification was stored
        classifier.store_classification.assert_called_once()
    
    def test_classify_idle_workload_low_utilization(self):
        """
        Test classification of idle workload with low GPU utilization.
        Requirements: FR-2.1, FR-2.4
        """
        # Setup
        mock_dynamodb = Mock()
        classifier = WorkloadClassifier(mock_dynamodb)
        
        # Mock low utilization pattern (idle)
        low_utilization = [5.0, 3.0, 7.0, 4.0, 6.0, 5.5, 4.5, 6.5, 5.0, 4.0, 6.0, 5.0]
        classifier.get_gpu_utilization_pattern = Mock(return_value=low_utilization)
        classifier.get_manual_classification = Mock(return_value=None)
        classifier.store_classification = Mock()
        
        # Execute
        classification = classifier.classify_workload('i-idle-789', '2026-02-01', '2026-02-24')
        
        # Verify
        assert classification.workload_type == 'idle'
        assert classification.confidence > 0.8
        assert classification.classification_method == 'cloudwatch-metrics'
        assert classification.gpu_utilization_avg < 10.0
        assert len(classification.gpu_utilization_pattern) == 12
        
        # Verify classification was stored
        classifier.store_classification.assert_called_once()
    
    def test_classify_unknown_workload_insufficient_data(self):
        """
        Test classification returns unknown when insufficient data is available.
        Requirements: FR-2.1
        """
        # Setup
        mock_dynamodb = Mock()
        classifier = WorkloadClassifier(mock_dynamodb)
        
        # Mock insufficient data (less than MIN_DATA_POINTS)
        insufficient_data = [50.0, 55.0, 52.0]  # Only 3 points, need 12
        classifier.get_gpu_utilization_pattern = Mock(return_value=insufficient_data)
        classifier.get_manual_classification = Mock(return_value=None)
        classifier.store_classification = Mock()
        
        # Execute
        classification = classifier.classify_workload('i-unknown-999', '2026-02-01', '2026-02-24')
        
        # Verify
        assert classification.workload_type == 'unknown'
        assert classification.confidence == 0.0
        assert classification.classification_method == 'cloudwatch-metrics'
        assert classification.gpu_utilization_avg == 0.0
        assert len(classification.gpu_utilization_pattern) == 0
        
        # Verify classification was NOT stored (unknown classification)
        classifier.store_classification.assert_not_called()
    
    def test_manual_classification_override_training(self):
        """
        Test manual classification override for training workload.
        Requirements: FR-2.3, FR-2.5
        """
        # Setup
        mock_dynamodb = Mock()
        classifier = WorkloadClassifier(mock_dynamodb)
        
        # Mock manual classification tag
        classifier.get_manual_classification = Mock(return_value='training')
        classifier.store_classification = Mock()
        
        # Execute
        classification = classifier.classify_workload('i-manual-123', '2026-02-01', '2026-02-24')
        
        # Verify
        assert classification.workload_type == 'training'
        assert classification.confidence == 1.0
        assert classification.classification_method == 'manual-tag'
        assert classification.gpu_utilization_avg == 0.0
        assert len(classification.gpu_utilization_pattern) == 0
        
        # Verify manual classification check was called
        classifier.get_manual_classification.assert_called_once_with('i-manual-123')
    
    def test_manual_classification_override_inference(self):
        """
        Test manual classification override for inference workload.
        Requirements: FR-2.3, FR-2.5
        """
        # Setup
        mock_dynamodb = Mock()
        classifier = WorkloadClassifier(mock_dynamodb)
        
        # Mock manual classification tag
        classifier.get_manual_classification = Mock(return_value='inference')
        classifier.store_classification = Mock()
        
        # Execute
        classification = classifier.classify_workload('i-manual-456', '2026-02-01', '2026-02-24')
        
        # Verify
        assert classification.workload_type == 'inference'
        assert classification.confidence == 1.0
        assert classification.classification_method == 'manual-tag'
    
    def test_manual_classification_override_idle(self):
        """
        Test manual classification override for idle workload.
        Requirements: FR-2.3, FR-2.5
        """
        # Setup
        mock_dynamodb = Mock()
        classifier = WorkloadClassifier(mock_dynamodb)
        
        # Mock manual classification tag
        classifier.get_manual_classification = Mock(return_value='idle')
        classifier.store_classification = Mock()
        
        # Execute
        classification = classifier.classify_workload('i-manual-789', '2026-02-01', '2026-02-24')
        
        # Verify
        assert classification.workload_type == 'idle'
        assert classification.confidence == 1.0
        assert classification.classification_method == 'manual-tag'
    
    def test_manual_override_ignores_conflicting_metrics(self):
        """
        Test that manual classification overrides conflicting CloudWatch metrics.
        Requirements: FR-2.3, FR-2.5
        """
        # Setup
        mock_dynamodb = Mock()
        classifier = WorkloadClassifier(mock_dynamodb)
        
        # Mock manual classification as 'idle' but with high utilization metrics
        classifier.get_manual_classification = Mock(return_value='idle')
        high_utilization = [85.0, 87.0, 84.0, 86.0, 85.5, 86.5, 85.0, 87.5, 86.0, 85.5, 86.5, 85.0]
        classifier.get_gpu_utilization_pattern = Mock(return_value=high_utilization)
        classifier.store_classification = Mock()
        
        # Execute
        classification = classifier.classify_workload('i-override-999', '2026-02-01', '2026-02-24')
        
        # Verify manual classification takes precedence
        assert classification.workload_type == 'idle'  # Manual says idle
        assert classification.confidence == 1.0
        assert classification.classification_method == 'manual-tag'
        
        # Verify GPU utilization was NOT retrieved (manual override happens first)
        classifier.get_gpu_utilization_pattern.assert_not_called()
    
    def test_classification_with_edge_case_utilization_patterns(self):
        """
        Test classification with edge case utilization patterns.
        Requirements: FR-2.1, FR-2.4
        """
        mock_dynamodb = Mock()
        classifier = WorkloadClassifier(mock_dynamodb)
        classifier.get_manual_classification = Mock(return_value=None)
        classifier.store_classification = Mock()
        
        # Test case 1: Exactly at training threshold (70%)
        threshold_utilization = [70.0] * 12
        classifier.get_gpu_utilization_pattern = Mock(return_value=threshold_utilization)
        classification = classifier.classify_workload('i-edge-1', '2026-02-01', '2026-02-24')
        assert classification.workload_type in ['training', 'unknown']  # Could be either
        
        # Test case 2: Exactly at idle threshold (10%)
        idle_threshold = [10.0] * 12
        classifier.get_gpu_utilization_pattern = Mock(return_value=idle_threshold)
        classification = classifier.classify_workload('i-edge-2', '2026-02-01', '2026-02-24')
        assert classification.workload_type in ['idle', 'unknown']  # Could be either
        
        # Test case 3: High variance but low average (ambiguous)
        high_variance_low_avg = [0.0, 100.0, 0.0, 100.0, 0.0, 100.0, 0.0, 100.0, 0.0, 100.0, 0.0, 100.0]
        classifier.get_gpu_utilization_pattern = Mock(return_value=high_variance_low_avg)
        classification = classifier.classify_workload('i-edge-3', '2026-02-01', '2026-02-24')
        # Should classify as inference (high variance) or unknown
        assert classification.workload_type in ['inference', 'unknown']
    
    def test_classification_consistency_over_time(self):
        """
        Test that classification is consistent when called multiple times with same data.
        Requirements: FR-2.1, FR-2.2
        """
        # Setup
        mock_dynamodb = Mock()
        classifier = WorkloadClassifier(mock_dynamodb)
        
        # Mock consistent utilization pattern
        utilization = [85.0, 87.0, 84.0, 86.0, 85.5, 86.5, 85.0, 87.5, 86.0, 85.5, 86.5, 85.0]
        classifier.get_gpu_utilization_pattern = Mock(return_value=utilization)
        classifier.get_manual_classification = Mock(return_value=None)
        classifier.store_classification = Mock()
        
        # Execute multiple times
        classification1 = classifier.classify_workload('i-consistent-123', '2026-02-01', '2026-02-24')
        classification2 = classifier.classify_workload('i-consistent-123', '2026-02-01', '2026-02-24')
        classification3 = classifier.classify_workload('i-consistent-123', '2026-02-01', '2026-02-24')
        
        # Verify consistency
        assert classification1.workload_type == classification2.workload_type == classification3.workload_type
        assert abs(classification1.confidence - classification2.confidence) < 0.01
        assert abs(classification2.confidence - classification3.confidence) < 0.01
        assert classification1.classification_method == classification2.classification_method == classification3.classification_method
