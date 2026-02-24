"""
Unit tests for Workload Classifier.

Requirements: FR-2.1, FR-2.2, FR-2.3, FR-2.4, FR-2.6
"""
import pytest
from src.services.ai_ml.workload_classifier import (
    WorkloadClassifier,
    WorkloadClassification
)


class TestWorkloadClassifier:
    """Test Workload Classifier functionality."""
    
    def test_classify_idle_workload(self):
        """Test classification of idle workload (< 10% utilization)."""
        classifier = WorkloadClassifier(dynamodb_client=None)
        
        # Idle pattern: consistently low utilization
        utilization_pattern = [5.0, 3.0, 7.0, 4.0, 6.0, 5.5, 4.5, 3.5, 6.5, 5.0, 4.0, 7.5]
        
        workload_type, confidence = classifier.apply_classification_rules(utilization_pattern)
        
        assert workload_type == "idle"
        assert confidence > 0.8
    
    def test_classify_training_workload(self):
        """Test classification of training workload (> 70% continuous)."""
        classifier = WorkloadClassifier(dynamodb_client=None)
        
        # Training pattern: high continuous utilization with low variance
        utilization_pattern = [85.0, 87.0, 84.0, 86.0, 85.5, 86.5, 85.0, 87.5, 86.0, 85.5, 86.5, 85.0]
        
        workload_type, confidence = classifier.apply_classification_rules(utilization_pattern)
        
        assert workload_type == "training"
        assert confidence > 0.7
    
    def test_classify_inference_workload(self):
        """Test classification of inference workload (20-70% with spikes)."""
        classifier = WorkloadClassifier(dynamodb_client=None)
        
        # Inference pattern: moderate utilization with high variance (spikes)
        utilization_pattern = [30.0, 60.0, 25.0, 65.0, 35.0, 55.0, 28.0, 62.0, 32.0, 58.0, 27.0, 63.0]
        
        workload_type, confidence = classifier.apply_classification_rules(utilization_pattern)
        
        assert workload_type == "inference"
        assert confidence > 0.6
    
    def test_classify_unknown_workload(self):
        """Test classification with insufficient data."""
        classifier = WorkloadClassifier(dynamodb_client=None)
        
        # Insufficient data
        utilization_pattern = []
        
        workload_type, confidence = classifier.apply_classification_rules(utilization_pattern)
        
        assert workload_type == "unknown"
        assert confidence == 0.0
    
    def test_training_vs_inference_distinction(self):
        """Test that training and inference are correctly distinguished."""
        classifier = WorkloadClassifier(dynamodb_client=None)
        
        # Training: high utilization, low variance
        training_pattern = [80.0, 82.0, 81.0, 83.0, 80.5, 82.5, 81.5, 83.5, 80.0, 82.0, 81.0, 83.0]
        training_type, _ = classifier.apply_classification_rules(training_pattern)
        
        # Inference: moderate utilization, high variance
        inference_pattern = [40.0, 65.0, 35.0, 60.0, 38.0, 62.0, 37.0, 63.0, 39.0, 61.0, 36.0, 64.0]
        inference_type, _ = classifier.apply_classification_rules(inference_pattern)
        
        assert training_type == "training"
        assert inference_type == "inference"
        assert training_type != inference_type
    
    def test_workload_classification_to_dict(self):
        """Test WorkloadClassification serialization."""
        classification = WorkloadClassification(
            instance_id="i-123",
            workload_type="training",
            confidence=0.95,
            classification_method="cloudwatch-metrics",
            gpu_utilization_avg=85.0,
            gpu_utilization_pattern=[85.0, 86.0, 84.0],
            timestamp="2026-02-24T12:00:00"
        )
        
        data_dict = classification.to_dict()
        
        assert data_dict['instance_id'] == "i-123"
        assert data_dict['workload_type'] == "training"
        assert data_dict['confidence'] == 0.95
        assert data_dict['classification_method'] == "cloudwatch-metrics"
    
    def test_edge_case_single_data_point(self):
        """Test classification with single data point."""
        classifier = WorkloadClassifier(dynamodb_client=None)
        
        # Single high utilization point
        utilization_pattern = [85.0]
        
        workload_type, confidence = classifier.apply_classification_rules(utilization_pattern)
        
        # Should classify based on average, but with lower confidence
        assert workload_type in ["training", "unknown"]
    
    def test_edge_case_boundary_values(self):
        """Test classification at threshold boundaries."""
        classifier = WorkloadClassifier(dynamodb_client=None)
        
        # Exactly at idle threshold (10%)
        idle_boundary = [10.0] * 12
        idle_type, _ = classifier.apply_classification_rules(idle_boundary)
        
        # Exactly at training threshold (70%)
        training_boundary = [70.0] * 12
        training_type, _ = classifier.apply_classification_rules(training_boundary)
        
        # Should not be idle at exactly 10%
        assert idle_type != "idle"
        
        # Should not be training at exactly 70% (needs > 70%)
        assert training_type != "training"
