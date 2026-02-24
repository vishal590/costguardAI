"""
Unit tests for GPU Cost Tracker.

Requirements: FR-1.1, FR-1.3, FR-1.5, FR-1.6
"""
import pytest
from src.services.ai_ml.gpu_cost_tracker import GPUCostTracker, GPUCostData, GPU_INSTANCE_PATTERNS


class TestGPUCostTracker:
    """Test GPU Cost Tracker functionality."""
    
    def test_filter_gpu_instances(self):
        """Test filtering of GPU instances from mixed instance types."""
        tracker = GPUCostTracker(dynamodb_client=None)
        
        cost_data = [
            {'instance_type': 'p3.2xlarge', 'cost': 100},
            {'instance_type': 't2.micro', 'cost': 10},
            {'instance_type': 'p4d.24xlarge', 'cost': 500},
            {'instance_type': 'm5.large', 'cost': 20},
            {'instance_type': 'g5.xlarge', 'cost': 80},
        ]
        
        gpu_costs = tracker.filter_gpu_instances(cost_data)
        
        assert len(gpu_costs) == 3
        assert all(any(pattern in item['instance_type'] for pattern in GPU_INSTANCE_PATTERNS) for item in gpu_costs)
    
    def test_calculate_cost_per_gpu_hour(self):
        """Test cost per GPU hour calculation."""
        tracker = GPUCostTracker(dynamodb_client=None)
        
        cost_per_hour = tracker.calculate_cost_per_gpu_hour(cost=100.0, gpu_hours=10.0)
        assert cost_per_hour == 10.0
        
        # Test zero hours
        cost_per_hour = tracker.calculate_cost_per_gpu_hour(cost=100.0, gpu_hours=0.0)
        assert cost_per_hour == 0.0
    
    def test_identify_idle_gpus(self):
        """Test idle GPU identification."""
        tracker = GPUCostTracker(dynamodb_client=None)
        
        utilization_data = [
            {'instance_id': 'i-1', 'utilization': 5.0},
            {'instance_id': 'i-2', 'utilization': 80.0},
            {'instance_id': 'i-3', 'utilization': 9.5},
            {'instance_id': 'i-4', 'utilization': 15.0},
        ]
        
        idle_gpus = tracker.identify_idle_gpus(utilization_data, threshold=10.0)
        
        assert len(idle_gpus) == 2
        assert 'i-1' in idle_gpus
        assert 'i-3' in idle_gpus
    
    def test_gpu_cost_data_to_dict(self):
        """Test GPUCostData serialization."""
        cost_data = GPUCostData(
            date='2026-02-24',
            instance_id='i-123',
            instance_type='p3.2xlarge',
            workload_type='training',
            cost=100.0,
            gpu_hours=10.0,
            cost_per_gpu_hour=10.0,
            utilization=85.0,
            classification_confidence=0.95
        )
        
        data_dict = cost_data.to_dict()
        
        assert data_dict['instance_id'] == 'i-123'
        assert data_dict['cost'] == 100.0
        assert data_dict['workload_type'] == 'training'
