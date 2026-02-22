"""
Property-based tests for PreventionEngine.

Tests correctness properties:
- Property 5: Dry Run Safety
- Property 6: Audit Trail Completeness  
- Property 10: Configuration Validation
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, MagicMock
from datetime import datetime, UTC

from src.services.prevention_engine import PreventionEngine
from src.utils.types import (
    BudgetStatus, ThresholdEvent, Resource, ResourceMetadata,
    IdleStatus, SafetyCheck, ActionResult, PlannedAction
)


# Strategies for generating test data
@st.composite
def resource_strategy(draw):
    """Generate random Resource."""
    resource_types = ["ec2", "rds", "lambda", "ebs", "dynamodb", "nat_gateway"]
    return Resource(
        resource_id=draw(st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-"))),
        resource_type=draw(st.sampled_from(resource_types)),
        service=draw(st.sampled_from(resource_types)),
        region=draw(st.sampled_from(["us-east-1", "us-west-2", "eu-west-1"])),
        tags=draw(st.dictionaries(st.text(min_size=1, max_size=10), st.text(min_size=1, max_size=20), max_size=5)),
        state=draw(st.sampled_from(["running", "stopped", "available"])),
        creation_date=datetime.now(UTC).isoformat()
    )


@st.composite
def planned_action_strategy(draw):
    """Generate random PlannedAction."""
    resource_types = ["ec2", "rds", "lambda", "ebs", "dynamodb", "nat_gateway"]
    actions = ["stop", "delete", "limit_concurrency", "snapshot_and_delete", "switch_to_ondemand"]
    
    return PlannedAction(
        resource_id=draw(st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-"))),
        resource_type=draw(st.sampled_from(resource_types)),
        action=draw(st.sampled_from(actions)),
        reason=draw(st.text(min_size=10, max_size=50)),
        estimated_savings=draw(st.floats(min_value=0.01, max_value=1000.0))
    )


@st.composite
def config_strategy(draw):
    """Generate random configuration."""
    warning_threshold = draw(st.integers(min_value=50, max_value=89))
    action_threshold = draw(st.integers(min_value=warning_threshold + 1, max_value=100))
    
    return {
        "enabled": draw(st.booleans()),
        "dry_run_mode": draw(st.booleans()),
        "approval_required": draw(st.booleans()),
        "enabled_services": draw(st.lists(
            st.sampled_from(["ec2", "rds", "lambda", "ebs", "s3", "dynamodb"]),
            min_size=1,
            max_size=6,
            unique=True
        )),
        "budget_thresholds": {
            "warning": warning_threshold,
            "action": action_threshold
        },
        "poll_interval_minutes": draw(st.integers(min_value=1, max_value=60)),
        "inventory_refresh_minutes": draw(st.integers(min_value=5, max_value=120))
    }


# Feature: automated-cost-prevention, Property 5: Dry Run Safety
class TestProperty5DryRunSafety:
    """
    Property 5: Dry Run Safety
    
    For any execution in dry run mode, no actual resource management actions
    should be performed, only logged.
    
    Validates: Requirements 6.1, 6.2
    """
    
    @settings(max_examples=100)
    @given(
        planned_actions=st.lists(planned_action_strategy(), min_size=1, max_size=10)
    )
    def test_dry_run_never_executes_actions(self, planned_actions):
        """
        Property: In dry run mode, action executor should never be called.
        
        For any list of planned actions, when dry_run_mode is True,
        the action executor's execute_action method should not be called.
        """
        # Setup mocks
        action_executor = Mock()
        notification_service = Mock()
        
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=action_executor,
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=notification_service,
            config={"enabled": True, "dry_run_mode": True}
        )
        
        # Execute dry run
        engine._handle_dry_run(planned_actions)
        
        # Property: Action executor should never be called in dry run
        action_executor.execute_action.assert_not_called()
        
        # Property: Dry run report should be sent
        notification_service.send_dry_run_report.assert_called_once()
    
    @settings(max_examples=100)
    @given(
        planned_actions=st.lists(planned_action_strategy(), min_size=1, max_size=10)
    )
    def test_dry_run_logs_all_planned_actions(self, planned_actions):
        """
        Property: Dry run should report all planned actions.
        
        For any list of planned actions, the dry run report should include
        all actions and their estimated savings.
        """
        notification_service = Mock()
        
        engine = PreventionEngine(
            budget_monitor=Mock(),
            resource_manager=Mock(),
            idle_detector=Mock(),
            safety_guard=Mock(),
            action_executor=Mock(),
            approval_manager=Mock(),
            rollback_manager=Mock(),
            notification_service=notification_service,
            config={"enabled": True, "dry_run_mode": True}
        )
        
        engine._handle_dry_run(planned_actions)
        
        # Property: Report should be called with all actions
        call_args = notification_service.send_dry_run_report.call_args
        reported_actions = call_args[0][0]
        total_savings = call_args[0][1]
        
        assert len(reported_actions) == len(planned_actions)
        assert total_savings == sum(a.estimated_savings for a in planned_actions)


# Feature: automated-cost-prevention, Property 6: Audit Trail Completeness
class TestProperty6AuditTrailCompleteness:
    """
    Property 6: Audit Trail Completeness
    
    For any automated action, there must be a corresponding audit log entry
    with complete details (resource, action, result, timestamp).
    
    Validates: Requirements 12.1-12.8
    """
    
    @settings(max_examples=100)
    @given(
        planned_actions=st.lists(planned_action_strategy(), min_size=1, max_size=5)
    )
    def test_all_actions_create_audit_entries(self, planned_actions):
        """
        Property: Every action execution creates an audit entry.
        
        For any list of planned actions, the rollback manager should store
        pre-action state for each action (audit trail).
        """
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
            config={"enabled": True, "dry_run_mode": False}
        )
        
        engine._execute_actions(planned_actions)
        
        # Property: Rollback manager should store state for each action
        assert rollback_manager.store_pre_action_state.call_count == len(planned_actions)
    
    @settings(max_examples=100)
    @given(
        planned_actions=st.lists(planned_action_strategy(), min_size=1, max_size=5)
    )
    def test_action_results_sent_to_notification(self, planned_actions):
        """
        Property: All action results are included in notifications.
        
        For any list of executed actions, the notification service should
        receive all action results.
        """
        action_executor = Mock()
        action_executor.execute_action.return_value = ActionResult(
            resource_id="test",
            action="stop",
            success=True,
            error_message=None,
            pre_action_state={},
            post_action_state={},
            estimated_savings=10.0,
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
            config={"enabled": True, "dry_run_mode": False}
        )
        
        engine._execute_actions(planned_actions)
        
        # Property: Notification should be sent with all results
        notification_service.send_action_notification.assert_called_once()
        call_args = notification_service.send_action_notification.call_args
        results = call_args[0][0]
        
        assert len(results) == len(planned_actions)


# Feature: automated-cost-prevention, Property 10: Configuration Validation
class TestProperty10ConfigurationValidation:
    """
    Property 10: Configuration Validation
    
    For any configuration change, the system should validate the configuration
    before applying it.
    
    Validates: Requirements 11.6
    """
    
    @settings(max_examples=100)
    @given(config=config_strategy())
    def test_valid_config_accepted(self, config):
        """
        Property: Valid configurations are accepted.
        
        For any configuration that meets validation rules, the system
        should accept and apply it.
        """
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
        
        # Property: Valid config should not raise exception
        validated = engine._validate_config(config)
        
        # Property: Validated config should preserve key values
        assert validated["enabled"] == config["enabled"]
        assert validated["dry_run_mode"] == config["dry_run_mode"]
        assert validated["budget_thresholds"]["warning"] == config["budget_thresholds"]["warning"]
        assert validated["budget_thresholds"]["action"] == config["budget_thresholds"]["action"]
    
    @settings(max_examples=100)
    @given(
        warning=st.integers(min_value=1, max_value=100),
        action=st.integers(min_value=1, max_value=100)
    )
    def test_invalid_threshold_order_rejected(self, warning, action):
        """
        Property: Invalid threshold ordering is rejected.
        
        For any configuration where warning >= action threshold,
        validation should fail.
        """
        if warning >= action:
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
                "budget_thresholds": {"warning": warning, "action": action}
            }
            
            # Property: Invalid config should raise ValueError
            with pytest.raises(ValueError):
                engine._validate_config(invalid_config)
    
    @settings(max_examples=100)
    @given(
        threshold=st.integers(min_value=-1000, max_value=1000)
    )
    def test_out_of_range_thresholds_rejected(self, threshold):
        """
        Property: Thresholds outside 0-100 range are rejected.
        
        For any threshold value outside the valid range (0-100),
        validation should fail.
        """
        if threshold <= 0 or threshold > 100:
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
                "budget_thresholds": {"warning": threshold, "action": 90}
            }
            
            # Property: Out of range threshold should raise ValueError
            with pytest.raises(ValueError):
                engine._validate_config(invalid_config)
    
    @settings(max_examples=100)
    @given(config=config_strategy())
    def test_update_config_validates_before_applying(self, config):
        """
        Property: Configuration updates are validated before application.
        
        For any configuration update, validation should occur before
        the configuration is applied to the engine.
        """
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
        
        # Property: Valid config update should succeed
        engine.update_config(config)
        
        # Property: Config should be applied
        assert engine.config["enabled"] == config["enabled"]
        assert engine.config["dry_run_mode"] == config["dry_run_mode"]
