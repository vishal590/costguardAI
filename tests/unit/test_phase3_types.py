"""
Unit tests for Phase 3 data models and types.
"""
import pytest
from datetime import datetime, UTC
from src.utils.types import (
    BudgetStatus,
    ThresholdEvent,
    Resource,
    ResourceMetadata,
    IdleStatus,
    IdleCriteria,
    SafetyCheck,
    SafetyConfig,
    ActionResult,
    PlannedAction,
    ApprovalRequest,
    ApprovalResponse,
    RollbackResult
)


class TestBudgetStatus:
    """Tests for BudgetStatus dataclass."""
    
    def test_budget_status_creation(self):
        """Test creating a BudgetStatus object."""
        budget = BudgetStatus(
            budget_name="test-budget",
            limit=1000.0,
            actual_spend=800.0,
            forecasted_spend=850.0,
            utilization_percent=85.0,
            currency="USD",
            time_period="2024-01"
        )
        
        assert budget.budget_name == "test-budget"
        assert budget.limit == 1000.0
        assert budget.actual_spend == 800.0
        assert budget.forecasted_spend == 850.0
        assert budget.utilization_percent == 85.0
        assert budget.currency == "USD"
        assert budget.time_period == "2024-01"
    
    def test_budget_status_at_warning_threshold(self):
        """Test budget at 80% warning threshold."""
        budget = BudgetStatus(
            budget_name="warning-budget",
            limit=1000.0,
            actual_spend=800.0,
            forecasted_spend=800.0,
            utilization_percent=80.0,
            currency="USD",
            time_period="2024-01"
        )
        
        assert budget.utilization_percent == 80.0
    
    def test_budget_status_at_action_threshold(self):
        """Test budget at 90% action threshold."""
        budget = BudgetStatus(
            budget_name="action-budget",
            limit=1000.0,
            actual_spend=900.0,
            forecasted_spend=900.0,
            utilization_percent=90.0,
            currency="USD",
            time_period="2024-01"
        )
        
        assert budget.utilization_percent == 90.0


class TestThresholdEvent:
    """Tests for ThresholdEvent dataclass."""
    
    def test_threshold_event_warning(self):
        """Test creating a warning threshold event."""
        budget = BudgetStatus(
            budget_name="test-budget",
            limit=1000.0,
            actual_spend=800.0,
            forecasted_spend=850.0,
            utilization_percent=85.0,
            currency="USD",
            time_period="2024-01"
        )
        
        event = ThresholdEvent(
            budget_name="test-budget",
            threshold_type="warning",
            utilization_percent=85.0,
            timestamp=datetime.now(UTC).isoformat(),
            budget_status=budget
        )
        
        assert event.budget_name == "test-budget"
        assert event.threshold_type == "warning"
        assert event.utilization_percent == 85.0
        assert event.budget_status == budget
    
    def test_threshold_event_action(self):
        """Test creating an action threshold event."""
        budget = BudgetStatus(
            budget_name="test-budget",
            limit=1000.0,
            actual_spend=900.0,
            forecasted_spend=950.0,
            utilization_percent=95.0,
            currency="USD",
            time_period="2024-01"
        )
        
        event = ThresholdEvent(
            budget_name="test-budget",
            threshold_type="action",
            utilization_percent=95.0,
            timestamp=datetime.now(UTC).isoformat(),
            budget_status=budget
        )
        
        assert event.threshold_type == "action"
        assert event.utilization_percent == 95.0


class TestResource:
    """Tests for Resource dataclass."""
    
    def test_resource_creation(self):
        """Test creating a Resource object."""
        resource = Resource(
            resource_id="i-1234567890abcdef0",
            resource_type="instance",
            service="ec2",
            region="us-east-1",
            tags={"Environment": "dev", "Name": "test-instance"},
            state="running",
            creation_date="2024-01-01T00:00:00Z"
        )
        
        assert resource.resource_id == "i-1234567890abcdef0"
        assert resource.resource_type == "instance"
        assert resource.service == "ec2"
        assert resource.region == "us-east-1"
        assert resource.tags["Environment"] == "dev"
        assert resource.state == "running"
    
    def test_resource_with_protected_tag(self):
        """Test resource with protected tag."""
        resource = Resource(
            resource_id="i-protected",
            resource_type="instance",
            service="ec2",
            region="us-east-1",
            tags={"Environment": "production"},
            state="running",
            creation_date="2024-01-01T00:00:00Z"
        )
        
        assert resource.tags["Environment"] == "production"
    
    def test_resource_empty_tags(self):
        """Test resource with no tags."""
        resource = Resource(
            resource_id="i-notags",
            resource_type="instance",
            service="ec2",
            region="us-east-1",
            tags={},
            state="running",
            creation_date="2024-01-01T00:00:00Z"
        )
        
        assert resource.tags == {}


class TestResourceMetadata:
    """Tests for ResourceMetadata dataclass."""
    
    def test_resource_metadata_creation(self):
        """Test creating ResourceMetadata."""
        resource = Resource(
            resource_id="i-test",
            resource_type="instance",
            service="ec2",
            region="us-east-1",
            tags={},
            state="running",
            creation_date="2024-01-01T00:00:00Z"
        )
        
        metadata = ResourceMetadata(
            resource=resource,
            cost_per_hour=0.10,
            last_activity="2024-01-15T12:00:00Z",
            metrics={"CPUUtilization": 2.5, "NetworkIn": 1000.0}
        )
        
        assert metadata.resource == resource
        assert metadata.cost_per_hour == 0.10
        assert metadata.metrics["CPUUtilization"] == 2.5


class TestIdleStatus:
    """Tests for IdleStatus dataclass."""
    
    def test_idle_status_idle(self):
        """Test idle resource status."""
        status = IdleStatus(
            resource_id="i-idle",
            is_idle=True,
            idle_duration=120,
            metrics_used={"CPUUtilization": 2.0},
            confidence=0.95
        )
        
        assert status.is_idle is True
        assert status.idle_duration == 120
        assert status.confidence == 0.95
    
    def test_idle_status_active(self):
        """Test active resource status."""
        status = IdleStatus(
            resource_id="i-active",
            is_idle=False,
            idle_duration=0,
            metrics_used={"CPUUtilization": 75.0},
            confidence=0.0
        )
        
        assert status.is_idle is False
        assert status.idle_duration == 0


class TestIdleCriteria:
    """Tests for IdleCriteria dataclass."""
    
    def test_idle_criteria_ec2(self):
        """Test EC2 idle criteria."""
        criteria = IdleCriteria(
            service="ec2",
            metric_name="CPUUtilization",
            threshold=5.0,
            duration_minutes=120
        )
        
        assert criteria.service == "ec2"
        assert criteria.metric_name == "CPUUtilization"
        assert criteria.threshold == 5.0
        assert criteria.duration_minutes == 120
    
    def test_idle_criteria_rds(self):
        """Test RDS idle criteria."""
        criteria = IdleCriteria(
            service="rds",
            metric_name="DatabaseConnections",
            threshold=0.0,
            duration_minutes=60
        )
        
        assert criteria.service == "rds"
        assert criteria.threshold == 0.0


class TestSafetyCheck:
    """Tests for SafetyCheck dataclass."""
    
    def test_safety_check_safe(self):
        """Test safe action."""
        check = SafetyCheck(
            is_safe=True,
            blocked_reason=None,
            checks_performed=["tag_check", "whitelist_check", "active_usage_check"]
        )
        
        assert check.is_safe is True
        assert check.blocked_reason is None
        assert len(check.checks_performed) == 3
    
    def test_safety_check_blocked(self):
        """Test blocked action."""
        check = SafetyCheck(
            is_safe=False,
            blocked_reason="Resource has protected tag",
            checks_performed=["tag_check"]
        )
        
        assert check.is_safe is False
        assert check.blocked_reason == "Resource has protected tag"


class TestSafetyConfig:
    """Tests for SafetyConfig dataclass."""
    
    def test_safety_config_creation(self):
        """Test creating SafetyConfig."""
        config = SafetyConfig(
            protected_tags=["Environment=production", "CostGuard=protected"],
            whitelist_ids=["i-critical1", "i-critical2"],
            minimum_idle_minutes={"ec2": 120, "rds": 60},
            dry_run_mode=True
        )
        
        assert len(config.protected_tags) == 2
        assert len(config.whitelist_ids) == 2
        assert config.minimum_idle_minutes["ec2"] == 120
        assert config.dry_run_mode is True


class TestActionResult:
    """Tests for ActionResult dataclass."""
    
    def test_action_result_success(self):
        """Test successful action result."""
        result = ActionResult(
            resource_id="i-test",
            action="stop",
            success=True,
            error_message=None,
            pre_action_state={"state": "running"},
            post_action_state={"state": "stopped"},
            estimated_savings=72.0,
            timestamp=datetime.now(UTC).isoformat()
        )
        
        assert result.success is True
        assert result.error_message is None
        assert result.estimated_savings == 72.0
    
    def test_action_result_failure(self):
        """Test failed action result."""
        result = ActionResult(
            resource_id="i-test",
            action="stop",
            success=False,
            error_message="Permission denied",
            pre_action_state={"state": "running"},
            post_action_state={},
            estimated_savings=0.0,
            timestamp=datetime.now(UTC).isoformat()
        )
        
        assert result.success is False
        assert result.error_message == "Permission denied"


class TestPlannedAction:
    """Tests for PlannedAction dataclass."""
    
    def test_planned_action_creation(self):
        """Test creating PlannedAction."""
        action = PlannedAction(
            resource_id="i-test",
            resource_type="instance",
            action="stop",
            reason="Budget threshold exceeded - resource is idle",
            estimated_savings=72.0
        )
        
        assert action.resource_id == "i-test"
        assert action.action == "stop"
        assert action.estimated_savings == 72.0


class TestApprovalRequest:
    """Tests for ApprovalRequest dataclass."""
    
    def test_approval_request_creation(self):
        """Test creating ApprovalRequest."""
        actions = [
            PlannedAction(
                resource_id="i-1",
                resource_type="instance",
                action="stop",
                reason="Idle",
                estimated_savings=72.0
            ),
            PlannedAction(
                resource_id="i-2",
                resource_type="instance",
                action="stop",
                reason="Idle",
                estimated_savings=50.0
            )
        ]
        
        request = ApprovalRequest(
            request_id="req-123",
            actions=actions,
            total_estimated_savings=122.0,
            expires_at="2024-01-15T13:00:00Z"
        )
        
        assert request.request_id == "req-123"
        assert len(request.actions) == 2
        assert request.total_estimated_savings == 122.0


class TestApprovalResponse:
    """Tests for ApprovalResponse dataclass."""
    
    def test_approval_response_approved(self):
        """Test approved response."""
        response = ApprovalResponse(
            request_id="req-123",
            approved=True,
            approved_by="admin@example.com",
            timestamp=datetime.now(UTC).isoformat()
        )
        
        assert response.approved is True
        assert response.approved_by == "admin@example.com"
    
    def test_approval_response_denied(self):
        """Test denied response."""
        response = ApprovalResponse(
            request_id="req-123",
            approved=False,
            approved_by="admin@example.com",
            timestamp=datetime.now(UTC).isoformat()
        )
        
        assert response.approved is False


class TestRollbackResult:
    """Tests for RollbackResult dataclass."""
    
    def test_rollback_result_success(self):
        """Test successful rollback."""
        result = RollbackResult(
            action_id="action-123",
            resource_id="i-test",
            success=True,
            restored_state={"state": "running"},
            timestamp=datetime.now(UTC).isoformat()
        )
        
        assert result.success is True
        assert result.restored_state["state"] == "running"
    
    def test_rollback_result_failure(self):
        """Test failed rollback."""
        result = RollbackResult(
            action_id="action-123",
            resource_id="i-test",
            success=False,
            restored_state={},
            timestamp=datetime.now(UTC).isoformat()
        )
        
        assert result.success is False
