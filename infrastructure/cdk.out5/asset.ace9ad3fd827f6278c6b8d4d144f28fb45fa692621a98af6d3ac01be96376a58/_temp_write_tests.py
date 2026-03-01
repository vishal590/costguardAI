content = """\"\"\"Integration tests for GPU Prevention Integration - Requirements: IR-2.3\"\"\"
import pytest
from unittest.mock import Mock
from src.services.ai_ml.prevention_integration import GPUPreventionIntegration, GPUCostSavings
from src.services.ai_ml.idle_detector import IdleGPU


class TestGPUPreventionIntegration:
    def setup_method(self):
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
        self.idle_gpu_detector.identify_idle_gpus.return_value = []
        result = self.integration.run_gpu_prevention_cycle("2024-01-01", "2024-01-02", dry_run=True)
        assert result["success"] is True
        assert result["idle_gpus_found"] == 0
    
    def test_run_gpu_prevention_cycle_with_idle_gpus_dry_run(self):
        idle_gpu1 = IdleGPU("i-gpu001", "p3.2xlarge", 5.0, 48.0, 3.06, 146.88, "high")
        idle_gpu2 = IdleGPU("i-gpu002", "g5.xlarge", 8.0, 24.0, 1.006, 24.14, "medium")
        self.idle_gpu_detector.identify_idle_gpus.return_value = [idle_gpu1, idle_gpu2]
        result = self.integration.run_gpu_prevention_cycle("2024-01-01", "2024-01-02", dry_run=True)
        assert result["success"] is True
        assert result["idle_gpus_found"] == 2
        assert result["actions_planned"] == 2
        assert result["actions_executed"] == 0
        assert result["total_savings"] > 0
        assert result["dry_run"] is True
        assert self.dynamodb_client.put_item.called
    
    def test_run_gpu_prevention_cycle_with_execution(self):
        idle_gpu = IdleGPU("i-gpu001", "p3.2xlarge", 3.0, 72.0, 3.06, 220.32, "critical")
        self.idle_gpu_detector.identify_idle_gpus.return_value = [idle_gpu]
        result = self.integration.run_gpu_prevention_cycle("2024-01-01", "2024-01-02", dry_run=False)
        assert result["success"] is True
        assert result["idle_gpus_found"] == 1
        assert result["actions_planned"] == 1
        assert result["actions_executed"] == 1
        assert result["dry_run"] is False
        assert self.ec2_client.stop_instances.called or self.ec2_client.terminate_instances.called
    
    def test_get_gpu_cost_savings_no_actions(self):
        self.dynamodb_client.scan.return_value = {"Items": []}
        savings = self.integration.get_gpu_cost_savings("2024-01-01", "2024-01-31")
        assert savings.period_start == "2024-01-01"
        assert savings.period_end == "2024-01-31"
        assert savings.total_savings == 0.0
        assert savings.actions_count == 0
    
    def test_get_gpu_cost_savings_with_actions(self):
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
                }
            ]
        }
        savings = self.integration.get_gpu_cost_savings("2024-01-01", "2024-01-31")
        assert savings.total_savings == pytest.approx(1101.6, rel=0.01)
        assert savings.actions_count == 1
    
    def test_projected_savings_calculation_stop(self):
        idle_gpu = IdleGPU("i-gpu001", "p3.2xlarge", 8.0, 24.0, 3.06, 150.0, "high")
        expected_savings = 3.06 * 12 * 30
        self.idle_gpu_detector.identify_idle_gpus.return_value = [idle_gpu]
        result = self.integration.run_gpu_prevention_cycle("2024-01-01", "2024-01-02", dry_run=True)
        assert result["total_savings"] == pytest.approx(expected_savings, rel=0.01)
    
    def test_projected_savings_calculation_terminate(self):
        idle_gpu = IdleGPU("i-gpu001", "p4d.24xlarge", 2.0, 168.0, 32.77, 5505.36, "critical")
        expected_savings = 32.77 * 24 * 30
        self.idle_gpu_detector.identify_idle_gpus.return_value = [idle_gpu]
        result = self.integration.run_gpu_prevention_cycle("2024-01-01", "2024-01-02", dry_run=True)
        assert result["total_savings"] == pytest.approx(expected_savings, rel=0.01)
    
    def test_error_handling_ec2_failure(self):
        idle_gpu = IdleGPU("i-gpu001", "p3.2xlarge", 5.0, 24.0, 3.06, 73.44, "medium")
        self.idle_gpu_detector.identify_idle_gpus.return_value = [idle_gpu]
        self.ec2_client.stop_instances.side_effect = Exception("EC2 API error")
        result = self.integration.run_gpu_prevention_cycle("2024-01-01", "2024-01-02", dry_run=False)
        assert result["success"] is True
        assert result["actions_planned"] >= 1
    
    def test_multiple_instance_types_tracking(self):
        idle_gpus = [
            IdleGPU("i-p3", "p3.2xlarge", 5.0, 24.0, 3.06, 73.44, "medium"),
            IdleGPU("i-p4", "p4d.24xlarge", 3.0, 48.0, 32.77, 1572.96, "critical"),
            IdleGPU("i-g5", "g5.xlarge", 8.0, 12.0, 1.006, 12.07, "low"),
            IdleGPU("i-g4", "g4dn.xlarge", 7.0, 36.0, 0.526, 18.94, "medium")
        ]
        self.idle_gpu_detector.identify_idle_gpus.return_value = idle_gpus
        result = self.integration.run_gpu_prevention_cycle("2024-01-01", "2024-01-02", dry_run=True)
        assert result["success"] is True
        assert result["idle_gpus_found"] == 4
        assert result["actions_planned"] == 4
        assert result["total_savings"] > 0
    
    def test_dynamodb_storage_format(self):
        idle_gpu = IdleGPU("i-gpu001", "p3.2xlarge", 5.0, 24.0, 3.06, 73.44, "medium")
        self.idle_gpu_detector.identify_idle_gpus.return_value = [idle_gpu]
        result = self.integration.run_gpu_prevention_cycle("2024-01-01", "2024-01-02", dry_run=True)
        assert self.dynamodb_client.put_item.called
        call_args = self.dynamodb_client.put_item.call_args_list[0]
        item = call_args[1]["Item"]
        assert "action_id" in item
        assert "instance_id" in item
        assert "instance_type" in item
        assert "action_type" in item
        assert "S" in item["action_id"]
        assert "S" in item["instance_id"]
        assert "N" in item["idle_hours"]
        assert "N" in item["cost_saved"]
    
    def test_integration_with_phase3_idle_detector(self):
        idle_gpu = IdleGPU("i-gpu001", "p3.2xlarge", 8.0, 24.0, 3.06, 73.44, "medium")
        self.idle_gpu_detector.identify_idle_gpus.return_value = [idle_gpu]
        result = self.integration.run_gpu_prevention_cycle("2024-01-01", "2024-01-02", dry_run=True)
        self.idle_gpu_detector.identify_idle_gpus.assert_called_once_with("2024-01-01", "2024-01-02", 10.0)
        assert result["success"] is True
        assert result["idle_gpus_found"] == 1
"""

with open('tests/integration/ai_ml/test_prevention_integration.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("File written successfully")
