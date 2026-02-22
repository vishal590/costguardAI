"""
Unit tests for PreventionEngine.

Tests:
- Initialization and configuration management
- Budget monitoring workflow
- Prevention workflow orchestration
- Dry run mode
- Approval workflow
- Action execution
- Configuration validation
- Status and control methods
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, UTC
from dataclasses import asdict

from src.services.prevention_engine import PreventionEngine
from src.utils.types import (
    BudgetStatus, ThresholdEvent, Resource, ResourceMetadata,
    IdleStatus, SafetyCheck, ActionResult, PlannedAction,
    ApprovalRequest, ApprovalResponse, RollbackResult
)


class TestPreventionEngineInit:
    """Test PreventionEngine initialization."""
    
    def test_init_with_config(self):
        """Test initialization with provided config."""
        config = {
            "enabled": True,
            "dry_run_mode": False,
            "enabled_services": ["ec2", "rds"]
        }
        
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=Mock(),
            config=config
        )
        
        assert engine.config["enabled"] is True
        assert engine.config["dry_run_mode"] is False
        assert "ec2" in engine.config["enabled_services"]
    
    def test_init_without_config_uses_defaults(self):
        """Test initialization without config uses defaults."""
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=Mock()
        )
        
        assert engine.config["enabled"] is False
        assert engine.config["dry_run_mode"] is True
        assert len(engine.config["enabled_services"]) > 20
        assert engine.config["budget_thresholds"]["warning"] == 80
        assert engine.config["budget_thresholds"]["action"] == 90


class TestConfigurationValidation:
    """Test configuration validation."""
    
    def test_validate_valid_config(self):
        """Test validation accepts valid config."""
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=Mock()
        )
        
        valid_config = {
            "enabled": True,
            "dry_run_mode": False,
            "budget_thresholds": {"warning": 75, "action": 85}
        }
        
        validated = engine._validate_config(valid_config)
        assert validated["budget_thresholds"]["warning"] == 75
        assert validated["budget_thresholds"]["action"] == 85
    
    def test_validate_rejects_invalid_threshold_order(self):
        """Test validation rejects warning >= action threshold."""
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=Mock()
        )
        
        invalid_config = {
            "budget_thresholds": {"warning": 90, "action": 80}
        }
        
        with pytest.raises(ValueError, match="Warning threshold must be less than action threshold"):
            engine._validate_config(invalid_config)
    
    def test_validate_rejects_invalid_threshold_range(self):
        """Test validation rejects thresholds outside 0-100."""
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=Mock()
        )
        
        invalid_config = {
            "budget_thresholds": {"warning": 150, "action": 200}
        }
        
        with pytest.raises(ValueError, match="must be between 0 and 100"):
            engine._validate_config(invalid_config)
    
    def test_validate_rejects_non_boolean_fields(self):
        """Test validation rejects non-boolean for boolean fields."""
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=Mock()
        )
        
        invalid_config = {"enabled": "yes"}
        
        with pytest.raises(ValueError, match="must be boolean"):
            engine._validate_config(invalid_config)
    
    def test_validate_rejects_invalid_services_list(self):
        """Test validation rejects non-list enabled_services."""
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=Mock()
        )
        
        invalid_config = {"enabled_services": "ec2,rds"}
        
        with pytest.raises(ValueError, match="must be a list"):
            engine._validate_config(invalid_config)


class TestBudgetMonitoringWorkflow:
    """Test budget monitoring workflow."""
    
    def test_run_prevention_cycle_when_disabled(self):
        """Test prevention cycle skips when disabled."""
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=Mock(),
            config={"enabled": False}
        )
        
        result = engine.run_prevention_cycle()
        
        assert result["success"] is True
        assert result["skipped"] is True
        assert result["reason"] == "disabled"
    
    def test_run_prevention_cycle_with_no_events(self):
        """Test prevention cycle with no budget events."""
        budget_monitor = Mock()
        budget_monitor.poll_budgets.return_value = []
        
        engine = PreventionEngine(
            budget_monitor=budget_monitor,
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=Mock(),
            config={"enabled": True}
        )
        
        result = engine.run_prevention_cycle()
        
        assert result["success"] is True
        assert result["budget_events"] == 0
        assert result["actions_taken"] == 0
    
    def test_run_prevention_cycle_with_warning_event(self):
        """Test prevention cycle sends warning notification."""
        budget_status = BudgetStatus(
            budget_name="test-budget",
            limit=1000.0,
            actual_spend=850.0,
            forecasted_spend=900.0,
            utilization_percent=85.0,
            currency="USD",
            time_period="2024-01"
        )
        
        threshold_event = ThresholdEvent(
            budget_name="test-budget",
            threshold_type="warning",
            utilization_percent=85.0,
            timestamp=datetime.now(UTC).isoformat(),
            budget_status=budget_status
        )
        
        budget_monitor = Mock()
        budget_monitor.poll_budgets.return_value = [threshold_event]
        
        notification_service = Mock()
        
        engine = PreventionEngine(
            budget_monitor=budget_monitor,
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=notification_service,
            config={"enabled": True}
        )
        
        result = engine.run_prevention_cycle()
        
        assert result["success"] is True
        assert result["budget_events"] == 1
        notification_service.send_warning.assert_called_once_with(budget_status)


class TestPreventionWorkflow:
    """Test prevention workflow execution."""
    
    def test_prevention_workflow_discovers_resources(self):
        """Test prevention workflow discovers resources."""
        budget_status = BudgetStatus(
            budget_name="test-budget",
            limit=1000.0,
            actual_spend=950.0,
            forecasted_spend=1000.0,
            utilization_percent=95.0,
            currency="USD",
            time_period="2024-01"
        )
        
        threshold_event = ThresholdEvent(
            budget_name="test-budget",
            threshold_type="action",
            utilization_percent=95.0,
            timestamp=datetime.now(UTC).isoformat(),
            budget_status=budget_status
        )
        
        budget_monitor = Mock()
        budget_monitor.poll_budgets.return_value = [threshold_event]
        
        resource_manager = Mock()
        resource_manager.discover_resources.return_value = []
        
        engine = PreventionEngine(
            budget_monitor=budget_monitor,
            resource_manager=resource_manager,
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=Mock(),
            config={"enabled": True, "enabled_services": ["ec2", "rds"]}
        )
        
        engine.run_prevention_cycle()
        
        resource_manager.discover_resources.assert_called_once()
    
    def test_prevention_workflow_detects_idle_resources(self):
        """Test prevention workflow detects idle resources."""
        resource = Resource(
            resource_id="i-123",
            resource_type="ec2",
            service="ec2",
            region="us-east-1",
            tags={},
            state="running",
            creation_date="2024-01-01T00:00:00Z"
        )
        
        metadata = ResourceMetadata(
            resource=resource,
            cost_per_hour=0.10,
            last_activity="2024-01-01T00:00:00Z",
            metrics={"CPUUtilization": 2.0}
        )
        
        idle_status = IdleStatus(
            resource_id="i-123",
            is_idle=True,
            idle_duration=180,
            metrics_used={"CPUUtilization": 2.0},
            confidence=0.95
        )
        
        budget_status = BudgetStatus(
            budget_name="test-budget",
            limit=1000.0,
            actual_spend=950.0,
            forecasted_spend=1000.0,
            utilization_percent=95.0,
            currency="USD",
            time_period="2024-01"
        )
        
        threshold_event = ThresholdEvent(
            budget_name="test-budget",
            threshold_type="action",
            utilization_percent=95.0,
            timestamp=datetime.now(UTC).isoformat(),
            budget_status=budget_status
        )
        
        budget_monitor = Mock()
        budget_monitor.poll_budgets.return_value = [threshold_event]
        
        resource_manager = Mock()
        resource_manager.discover_resources.return_value = [resource]
        resource_manager.get_resource_metadata.return_value = metadata
        
        idle_detector = Mock()
        idle_detector.is_resource_idle.return_value = idle_status
        
        safety_guard = Mock()
        safety_guard.is_action_safe.return_value = SafetyCheck(
            is_safe=False,
            blocked_reason="Test block",
            checks_performed=["tags"]
        )
        
        engine = PreventionEngine(
            budget_monitor=budget_monitor,
            resource_manager=resource_manager,
            idle_detector=idle_detector,
            safety_guard=safety_guard,
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=Mock(),
            config={"enabled": True, "enabled_services": ["ec2"]}
        )
        
        engine.run_prevention_cycle()
        
        idle_detector.is_resource_idle.assert_called_once()


class TestDryRunMode:
    """Test dry run mode."""
    
    def test_dry_run_mode_logs_without_executing(self):
        """Test dry run mode logs actions without executing."""
        resource = Resource(
            resource_id="i-123",
            resource_type="ec2",
            service="ec2",
            region="us-east-1",
            tags={},
            state="running",
            creation_date="2024-01-01T00:00:00Z"
        )
        
        metadata = ResourceMetadata(
            resource=resource,
            cost_per_hour=0.10,
            last_activity="2024-01-01T00:00:00Z",
            metrics={"CPUUtilization": 2.0}
        )
        
        idle_status = IdleStatus(
            resource_id="i-123",
            is_idle=True,
            idle_duration=180,
            metrics_used={"CPUUtilization": 2.0},
            confidence=0.95
        )
        
        budget_status = BudgetStatus(
            budget_name="test-budget",
            limit=1000.0,
            actual_spend=950.0,
            forecasted_spend=1000.0,
            utilization_percent=95.0,
            currency="USD",
            time_period="2024-01"
        )
        
        threshold_event = ThresholdEvent(
            budget_name="test-budget",
            threshold_type="action",
            utilization_percent=95.0,
            timestamp=datetime.now(UTC).isoformat(),
            budget_status=budget_status
        )
        
        budget_monitor = Mock()
        budget_monitor.poll_budgets.return_value = [threshold_event]
        
        resource_manager = Mock()
        resource_manager.discover_resources.return_value = [resource]
        resource_manager.get_resource_metadata.return_value = metadata
        
        idle_detector = Mock()
        idle_detector.is_resource_idle.return_value = idle_status
        
        safety_guard = Mock()
        safety_guard.is_action_safe.return_value = SafetyCheck(
            is_safe=True,
            blocked_reason=None,
            checks_performed=["tags", "whitelist"]
        )
        
        action_executor = Mock()
        notification_service = Mock()
        
        engine = PreventionEngine(
            budget_monitor=budget_monitor,
            resource_manager=resource_manager,
            idle_detector=idle_detector,
            safety_guard=safety_guard,
            action_executor=action_executor,
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=notification_service,
            config={"enabled": True, "dry_run_mode": True, "enabled_services": ["ec2"]}
        )
        
        result = engine.run_prevention_cycle()
        
        # Should not execute actions in dry run
        action_executor.execute_action.assert_not_called()
        
        # Should send dry run report
        notification_service.send_dry_run_report.assert_called_once()


class TestActionExecution:
    """Test action execution."""
    
    def test_execute_actions_sorts_by_cost(self):
        """Test actions are executed in order of cost impact."""
        planned_actions = [
            PlannedAction(
                resource_id="i-1",
                resource_type="ec2",
                action="stop",
                reason="idle",
                estimated_savings=10.0
            ),
            PlannedAction(
                resource_id="i-2",
                resource_type="ec2",
                action="stop",
                reason="idle",
                estimated_savings=50.0
            ),
            PlannedAction(
                resource_id="i-3",
                resource_type="ec2",
                action="stop",
                reason="idle",
                estimated_savings=25.0
            )
        ]
        
        action_executor = Mock()
        action_executor.execute_action.return_value = ActionResult(
            resource_id="test",
            action="stop",
            success=True,
            error_message=None,
            pre_action_state={},
            post_action_state={},
            estimated_savings=0.0,
            timestamp=datetime.now(UTC).isoformat()
        )
        
        rollback_manager = Mock()
        notification_service = Mock()
        
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=action_executor,
            approval_manager=Mock(),
            rollback_manager=rollback_manager,
            notification_service=notification_service,
            config={"enabled": True}
        )
        
        engine._execute_actions(planned_actions)
        
        # Verify actions were executed in order of cost (highest first)
        calls = action_executor.execute_action.call_args_list
        assert len(calls) == 3
        # First call should be for i-2 (highest cost)
        assert calls[0][0][0].resource_id == "i-2"
        # Second call should be for i-3
        assert calls[1][0][0].resource_id == "i-3"
        # Third call should be for i-1 (lowest cost)
        assert calls[2][0][0].resource_id == "i-1"
    
    def test_execute_actions_continues_on_failure(self):
        """Test action execution continues when one action fails."""
        planned_actions = [
            PlannedAction(
                resource_id="i-1",
                resource_type="ec2",
                action="stop",
                reason="idle",
                estimated_savings=10.0
            ),
            PlannedAction(
                resource_id="i-2",
                resource_type="ec2",
                action="stop",
                reason="idle",
                estimated_savings=20.0
            )
        ]
        
        action_executor = Mock()
        # First action fails, second succeeds
        action_executor.execute_action.side_effect = [
            Exception("Test error"),
            ActionResult(
                resource_id="i-1",
                action="stop",
                success=True,
                error_message=None,
                pre_action_state={},
                post_action_state={},
                estimated_savings=10.0,
                timestamp=datetime.now(UTC).isoformat()
            )
        ]
        
        rollback_manager = Mock()
        notification_service = Mock()
        
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=action_executor,
            approval_manager=Mock(),
            rollback_manager=rollback_manager,
            notification_service=notification_service,
            config={"enabled": True}
        )
        
        count = engine._execute_actions(planned_actions)
        
        # Should have attempted both actions
        assert action_executor.execute_action.call_count == 2
        # Only one succeeded
        assert count == 1


class TestStatusAndControl:
    """Test status and control methods."""
    
    def test_get_status_returns_config(self):
        """Test get_status returns current configuration."""
        config = {
            "enabled": True,
            "dry_run_mode": False,
            "approval_required": True,
            "enabled_services": ["ec2", "rds"],
            "budget_thresholds": {"warning": 80, "action": 90}
        }
        
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=Mock(),
            config=config
        )
        
        status = engine.get_status()
        
        assert status["enabled"] is True
        assert status["dry_run_mode"] is False
        assert status["approval_required"] is True
        assert "ec2" in status["enabled_services"]
    
    def test_enable_sets_enabled_true(self):
        """Test enable() sets enabled to True."""
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=Mock(),
            config={"enabled": False}
        )
        
        engine.enable()
        
        assert engine.config["enabled"] is True
    
    def test_disable_sets_enabled_false(self):
        """Test disable() sets enabled to False."""
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=Mock(),
            config={"enabled": True}
        )
        
        engine.disable()
        
        assert engine.config["enabled"] is False
    
    def test_update_config_validates_and_applies(self):
        """Test update_config validates before applying."""
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=Mock(),
            config={"enabled": False}
        )
        
        engine.update_config({"enabled": True, "dry_run_mode": False})
        
        assert engine.config["enabled"] is True
        assert engine.config["dry_run_mode"] is False
    
    def test_update_config_rejects_invalid(self):
        """Test update_config rejects invalid configuration."""
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=Mock()
        )
        
        with pytest.raises(ValueError):
            engine.update_config({"budget_thresholds": {"warning": 95, "action": 85}})


class TestResourceAndHistoryMethods:
    """Test resource and history query methods."""
    
    def test_get_resources_without_filters(self):
        """Test get_resources returns all resources."""
        resources = [
            Resource(
                resource_id="i-1",
                resource_type="ec2",
                service="ec2",
                region="us-east-1",
                tags={},
                state="running",
                creation_date="2024-01-01T00:00:00Z"
            ),
            Resource(
                resource_id="db-1",
                resource_type="rds",
                service="rds",
                region="us-east-1",
                tags={},
                state="available",
                creation_date="2024-01-01T00:00:00Z"
            )
        ]
        
        resource_manager = Mock()
        resource_manager.discover_resources.return_value = resources
        
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=resource_manager,
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=Mock()
        )
        
        result = engine.get_resources()
        
        assert len(result) == 2
    
    def test_get_resources_with_service_filter(self):
        """Test get_resources filters by service."""
        resources = [
            Resource(
                resource_id="i-1",
                resource_type="ec2",
                service="ec2",
                region="us-east-1",
                tags={},
                state="running",
                creation_date="2024-01-01T00:00:00Z"
            ),
            Resource(
                resource_id="db-1",
                resource_type="rds",
                service="rds",
                region="us-east-1",
                tags={},
                state="available",
                creation_date="2024-01-01T00:00:00Z"
            )
        ]
        
        resource_manager = Mock()
        resource_manager.discover_resources.return_value = resources
        
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=resource_manager,
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=Mock()
        )
        
        result = engine.get_resources(filters={"service": "ec2"})
        
        assert len(result) == 1
        assert result[0].service == "ec2"
    
    def test_execute_rollback_calls_rollback_manager(self):
        """Test execute_rollback delegates to rollback manager."""
        rollback_result = RollbackResult(
            action_id="action-123",
            resource_id="i-123",
            success=True,
            restored_state={"state": "running"},
            timestamp=datetime.now(UTC).isoformat()
        )
        
        rollback_manager = Mock()
        rollback_manager.execute_rollback.return_value = rollback_result
        
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=rollback_manager,
            notification_service=Mock()
        )
        
        result = engine.execute_rollback("action-123")
        
        assert result["success"] is True
        assert result["action_id"] == "action-123"
        rollback_manager.execute_rollback.assert_called_once_with("action-123")
