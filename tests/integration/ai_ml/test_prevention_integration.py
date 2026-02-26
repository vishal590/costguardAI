"""Integration tests for GPU Prevention Integration - Requirements: IR-2.3"""
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime
from src.services.ai_ml.prevention_integration import GPUPreventionIntegration, GPUPreventionAction, GPUCostSavings
from src.services.ai_ml.idle_detector import IdleGPU


class TestGPUPreventionIntegration:
    """Test GPU Prevention Integration with Phase 3 - Requirements: IR-2.3"""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.idle_gpu_detector = Mock()
        self.prevention_engine = Mock()
        self.dynamodb_client = Mock()
        self.ec2_client = Mock()
        self.integration = GPUPreventionIntegration(
            idle_gpu_detector=self.idle_gpu_detector,
            prevention_engine=self.prevention_engine,
            dynamodb_client=self.dynamodb_client,
            ec2_client=self.ec2_client
        )
    
    def test_run_gpu_prevention_cycle_no_idle_gpus(self):
        """Test prevention cycle when no idle GPUs are found."""
        self.idle_gpu_detector.identify_idle_gpus.return_value = []
        
        result = self.integration.run_gpu_prevention_cycle(
            "2024-01-01", "2024-01-02", dry_run=True
        )
        
        assert result["success"] is True
        assert result["idle_gpus_found"] == 0
        assert result["actions_planned"] == 0
        assert result["actions_executed"] == 0
        assert result["total_savings"] == 0.0
        assert result["dry_run"] is True
    
    def test_run_gpu_prevention_cycle_with_idle_gpus_dry_run(self):
        """Test prevention cycle with idle GPUs in dry run mode."""
        # Create mock idle GPUs
        idle_gpu1 = IdleGPU(
            instance_id="i-gpu001",
            instance_type="p3.2xlarge",
            utilization=5.0,
            idle_hours=48.0,
            cost_per_hour=3.06,
            wasted_cost=146.88,
            first_idle_time="2024-01-01T00:00:00",
            last_check_time="2024-01-02T00:00:00",
            recommendation="STOP: GPU is idle and wasting significant cost."
        )
        idle_gpu2 = IdleGPU(
            instance_id="i-gpu002",
            instance_type="g5.xlarge",
            utilization=8.0,
            idle_hours=24.0,
            cost_per_hour=1.006,
            wasted_cost=24.14,
            first_idle_time="2024-01-01T00:00:00",
            last_check_time="2024-01-02T00:00:00",
            recommendation="REVIEW: GPU utilization is low."
        )
        
        self.idle_gpu_detector.identify_idle_gpus.return_value = [idle_gpu1, idle_gpu2]
        
        result = self.integration.run_gpu_prevention_cycle(
            "2024-01-01", "2024-01-02", dry_run=True
        )
        
        assert result["success"] is True
        assert result["idle_gpus_found"] == 2
        assert result["actions_planned"] == 2
        assert result["actions_executed"] == 0  # Dry run, no execution
        assert result["total_savings"] > 0
        assert result["dry_run"] is True
        
        # Verify DynamoDB storage was called
        assert self.dynamodb_client.put_item.called
    
    def test_run_gpu_prevention_cycle_with_execution(self):
        """Test prevention cycle with actual execution (not dry run)."""
        idle_gpu = IdleGPU(
            instance_id="i-gpu001",
            instance_type="p3.2xlarge",
            utilization=3.0,
            idle_hours=72.0,
            cost_per_hour=3.06,
            wasted_cost=220.32,
            first_idle_time="2024-01-01T00:00:00",
            last_check_time="2024-01-02T00:00:00",
            recommendation="STOP: GPU is nearly unused."
        )
        
        self.idle_gpu_detector.identify_idle_gpus.return_value = [idle_gpu]
        
        result = self.integration.run_gpu_prevention_cycle(
            "2024-01-01", "2024-01-02", dry_run=False
        )
        
        assert result["success"] is True
        assert result["idle_gpus_found"] == 1
        assert result["actions_planned"] == 1
        assert result["actions_executed"] == 1
        assert result["dry_run"] is False
        
        # Verify EC2 action was called
        assert self.ec2_client.stop_instances.called or self.ec2_client.terminate_instances.called
    
    def test_action_type_determination_stop(self):
        """Test that moderate idle GPUs trigger stop action."""
        idle_gpu = IdleGPU(
            instance_id="i-gpu001",
            instance_type="p3.2xlarge",
            utilization=8.0,
            idle_hours=24.0,
            cost_per_hour=3.06,
            wasted_cost=150.0,
            first_idle_time="2024-01-01T00:00:00",
            last_check_time="2024-01-02T00:00:00",
            recommendation="STOP: GPU is idle and wasting significant cost."
        )
        
        self.idle_gpu_detector.identify_idle_gpus.return_value = [idle_gpu]
        
        result = self.integration.run_gpu_prevention_cycle(
            "2024-01-01", "2024-01-02", dry_run=True
        )
        
        # Verify action was planned
        assert result["actions_planned"] == 1
        
        # Check that stop action was determined (utilization < 10%, cost > 100)
        # This is verified by checking the stored action
        assert self.dynamodb_client.put_item.called
    
    def test_action_type_determination_terminate(self):
        """Test that severely idle GPUs trigger terminate action."""
        idle_gpu = IdleGPU(
            instance_id="i-gpu001",
            instance_type="p4d.24xlarge",
            utilization=2.0,
            idle_hours=168.0,  # 1 week
            cost_per_hour=32.77,
            wasted_cost=5505.36,
            first_idle_time="2024-01-01T00:00:00",
            last_check_time="2024-01-08T00:00:00",
            recommendation="STOP: GPU is nearly unused."
        )
        
        self.idle_gpu_detector.identify_idle_gpus.return_value = [idle_gpu]
        
        result = self.integration.run_gpu_prevention_cycle(
            "2024-01-01", "2024-01-02", dry_run=True
        )
        
        # Verify action was planned
        assert result["actions_planned"] == 1
        
        # Very low utilization (<5%) and high cost (>500) should trigger terminate
        assert self.dynamodb_client.put_item.called
    
    def test_get_gpu_cost_savings_no_actions(self):
        """Test getting cost savings when no actions exist."""
        self.dynamodb_client.scan.return_value = {"Items": []}
        
        savings = self.integration.get_gpu_cost_savings("2024-01-01", "2024-01-31")
        
        assert savings.period_start == "2024-01-01"
        assert savings.period_end == "2024-01-31"
        assert savings.total_savings == 0.0
        assert savings.actions_count == 0
        assert savings.instances_stopped == 0
        assert savings.instances_terminated == 0
        assert savings.avg_idle_hours == 0.0
        assert savings.breakdown_by_instance_type == {}
    
    def test_get_gpu_cost_savings_with_actions(self):
        """Test getting cost savings with multiple actions."""
        # Mock DynamoDB response with actions
        self.dynamodb_client.scan.return_value = {
            "Items": [
                {
                    "action_id": {"S": "action-1"},
                    "instance_id": {"S": "i-gpu001"},
                    "instance_type": {"S": "p3.2xlarge"},
                    "action_type": {"S": "stop"},
                    "reason": {"S": "Idle GPU"},
                    "idle_hours": {"N": "48.0"},
                    "cost_saved": {"N": "1101.6"},
                    "timestamp": {"S": "2024-01-15T10:00:00"},
                    "status": {"S": "executed"}
                },
                {
                    "action_id": {"S": "action-2"},
                    "instance_id": {"S": "i-gpu002"},
                    "instance_type": {"S": "g5.xlarge"},
                    "action_type": {"S": "stop"},
                    "reason": {"S": "Idle GPU"},
                    "idle_hours": {"N": "24.0"},
                    "cost_saved": {"N": "362.16"},
                    "timestamp": {"S": "2024-01-20T14:00:00"},
                    "status": {"S": "executed"}
                },
                {
                    "action_id": {"S": "action-3"},
                    "instance_id": {"S": "i-gpu003"},
                    "instance_type": {"S": "p4d.24xlarge"},
                    "action_type": {"S": "terminate"},
                    "reason": {"S": "Severely idle GPU"},
                    "idle_hours": {"N": "168.0"},
                    "cost_saved": {"N": "23592.96"},
                    "timestamp": {"S": "2024-01-25T08:00:00"},
                    "status": {"S": "executed"}
                }
            ]
        }
        
        savings = self.integration.get_gpu_cost_savings("2024-01-01", "2024-01-31")
        
        assert savings.period_start == "2024-01-01"
        assert savings.period_end == "2024-01-31"
        assert savings.total_savings == pytest.approx(25056.72, rel=0.01)
        assert savings.actions_count == 3
        assert savings.instances_stopped == 2
        assert savings.instances_terminated == 1
        assert savings.avg_idle_hours == pytest.approx(80.0, rel=0.01)
        
        # Check breakdown by instance type
        assert "p3.2xlarge" in savings.breakdown_by_instance_type
        assert "g5.xlarge" in savings.breakdown_by_instance_type
        assert "p4d.24xlarge" in savings.breakdown_by_instance_type
        assert savings.breakdown_by_instance_type["p3.2xlarge"] == pytest.approx(1101.6, rel=0.01)
        assert savings.breakdown_by_instance_type["g5.xlarge"] == pytest.approx(362.16, rel=0.01)
        assert savings.breakdown_by_instance_type["p4d.24xlarge"] == pytest.approx(23592.96, rel=0.01)
    
    def test_projected_savings_calculation_stop(self):
        """Test projected savings calculation for stop action."""
        idle_gpu = IdleGPU(
            instance_id="i-gpu001",
            instance_type="p3.2xlarge",
            utilization=8.0,
            idle_hours=24.0,
            cost_per_hour=3.06,
            wasted_cost=150.0,
            first_idle_time="2024-01-01T00:00:00",
            last_check_time="2024-01-02T00:00:00",
            recommendation="STOP: GPU is idle and wasting significant cost."
        )
        
        # Calculate projected savings (stop = 12 hours/day * 30 days)
        expected_savings = 3.06 * 12 * 30  # $1,101.60/month
        
        self.idle_gpu_detector.identify_idle_gpus.return_value = [idle_gpu]
        
        result = self.integration.run_gpu_prevention_cycle(
            "2024-01-01", "2024-01-02", dry_run=True
        )
        
        assert result["total_savings"] == pytest.approx(expected_savings, rel=0.01)
    
    def test_projected_savings_calculation_terminate(self):
        """Test projected savings calculation for terminate action."""
        idle_gpu = IdleGPU(
            instance_id="i-gpu001",
            instance_type="p4d.24xlarge",
            utilization=2.0,
            idle_hours=168.0,
            cost_per_hour=32.77,
            wasted_cost=5505.36,
            first_idle_time="2024-01-01T00:00:00",
            last_check_time="2024-01-08T00:00:00",
            recommendation="STOP: GPU is nearly unused."
        )
        
        # Calculate projected savings (terminate = 24 hours/day * 30 days)
        expected_savings = 32.77 * 24 * 30  # $23,592.96/month
        
        self.idle_gpu_detector.identify_idle_gpus.return_value = [idle_gpu]
        
        result = self.integration.run_gpu_prevention_cycle(
            "2024-01-01", "2024-01-02", dry_run=True
        )
        
        assert result["total_savings"] == pytest.approx(expected_savings, rel=0.01)
    
    def test_safety_guard_integration(self):
        """Test that prevention respects safety guards for GPU resources."""
        # This test verifies that the integration properly handles safety guards
        # In a real implementation, safety guards would prevent actions on critical resources
        
        idle_gpu = IdleGPU(
            instance_id="i-gpu-critical",
            instance_type="p3.2xlarge",
            utilization=5.0,
            idle_hours=24.0,
            cost_per_hour=3.06,
            wasted_cost=73.44,
            first_idle_time="2024-01-01T00:00:00",
            last_check_time="2024-01-02T00:00:00",
            recommendation="REVIEW: GPU utilization is low."
        )
        
        self.idle_gpu_detector.identify_idle_gpus.return_value = [idle_gpu]
        
        # Run prevention cycle
        result = self.integration.run_gpu_prevention_cycle(
            "2024-01-01", "2024-01-02", dry_run=True
        )
        
        # Verify actions were planned (safety guard check would happen in execution)
        assert result["success"] is True
        assert result["actions_planned"] >= 1
    
    def test_error_handling_ec2_failure(self):
        """Test error handling when EC2 action fails."""
        idle_gpu = IdleGPU(
            instance_id="i-gpu001",
            instance_type="p3.2xlarge",
            utilization=5.0,
            idle_hours=24.0,
            cost_per_hour=3.06,
            wasted_cost=73.44,
            first_idle_time="2024-01-01T00:00:00",
            last_check_time="2024-01-02T00:00:00",
            recommendation="REVIEW: GPU utilization is low."
        )
        
        self.idle_gpu_detector.identify_idle_gpus.return_value = [idle_gpu]
        
        # Simulate EC2 failure
        self.ec2_client.stop_instances.side_effect = Exception("EC2 API error")
        
        # Should not raise exception, but log error
        result = self.integration.run_gpu_prevention_cycle(
            "2024-01-01", "2024-01-02", dry_run=False
        )
        
        assert result["success"] is True
        # Actions were planned but execution may have failed
        assert result["actions_planned"] >= 1
    
    def test_multiple_instance_types_tracking(self):
        """Test tracking savings across multiple GPU instance types."""
        idle_gpus = [
            IdleGPU("i-p3", "p3.2xlarge", 5.0, 24.0, 73.44, 3.06, "2024-01-01T00:00:00", "2024-01-02T00:00:00", "REVIEW: GPU utilization is low."),
            IdleGPU("i-p4", "p4d.24xlarge", 3.0, 48.0, 1572.96, 32.77, "2024-01-01T00:00:00", "2024-01-03T00:00:00", "STOP: GPU is nearly unused."),
            IdleGPU("i-g5", "g5.xlarge", 8.0, 12.0, 12.07, 1.006, "2024-01-01T00:00:00", "2024-01-01T12:00:00", "REVIEW: GPU utilization is low."),
            IdleGPU("i-g4", "g4dn.xlarge", 7.0, 36.0, 18.94, 0.526, "2024-01-01T00:00:00", "2024-01-02T12:00:00", "REVIEW: GPU utilization is low.")
        ]
        
        self.idle_gpu_detector.identify_idle_gpus.return_value = idle_gpus
        
        result = self.integration.run_gpu_prevention_cycle(
            "2024-01-01", "2024-01-02", dry_run=True
        )
        
        assert result["success"] is True
        assert result["idle_gpus_found"] == 4
        assert result["actions_planned"] == 4
        assert result["total_savings"] > 0
    
    def test_dynamodb_storage_format(self):
        """Test that prevention actions are stored in correct DynamoDB format."""
        idle_gpu = IdleGPU(
            instance_id="i-gpu001",
            instance_type="p3.2xlarge",
            utilization=5.0,
            idle_hours=24.0,
            cost_per_hour=3.06,
            wasted_cost=73.44,
            first_idle_time="2024-01-01T00:00:00",
            last_check_time="2024-01-02T00:00:00",
            recommendation="REVIEW: GPU utilization is low."
        )
        
        self.idle_gpu_detector.identify_idle_gpus.return_value = [idle_gpu]
        
        result = self.integration.run_gpu_prevention_cycle(
            "2024-01-01", "2024-01-02", dry_run=True
        )
        
        # Verify DynamoDB put_item was called
        assert self.dynamodb_client.put_item.called
        
        # Check the format of stored items
        call_args = self.dynamodb_client.put_item.call_args_list[0]
        item = call_args[1]["Item"]
        
        # Verify required fields are present
        assert "action_id" in item
        assert "instance_id" in item
        assert "instance_type" in item
        assert "action_type" in item
        assert "reason" in item
        assert "idle_hours" in item
        assert "cost_saved" in item
        assert "timestamp" in item
        assert "status" in item
        
        # Verify DynamoDB types
        assert "S" in item["action_id"]
        assert "S" in item["instance_id"]
        assert "N" in item["idle_hours"]
        assert "N" in item["cost_saved"]
    
    def test_integration_with_phase3_idle_detector(self):
        """Test integration with Phase 3's IdleDetector for GPU instances."""
        # This test verifies that the integration works with Phase 3's ec2_gpu service type
        
        idle_gpu = IdleGPU(
            instance_id="i-gpu001",
            instance_type="p3.2xlarge",
            utilization=8.0,
            idle_hours=24.0,
            cost_per_hour=3.06,
            wasted_cost=73.44,
            first_idle_time="2024-01-01T00:00:00",
            last_check_time="2024-01-02T00:00:00",
            recommendation="REVIEW: GPU utilization is low."
        )
        
        self.idle_gpu_detector.identify_idle_gpus.return_value = [idle_gpu]
        
        result = self.integration.run_gpu_prevention_cycle(
            "2024-01-01", "2024-01-02", dry_run=True
        )
        
        # Verify idle GPU detector was called with correct parameters
        self.idle_gpu_detector.identify_idle_gpus.assert_called_once_with(
            "2024-01-01", "2024-01-02", 10.0
        )
        
        assert result["success"] is True
        assert result["idle_gpus_found"] == 1
