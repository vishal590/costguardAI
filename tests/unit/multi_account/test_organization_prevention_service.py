"""
Unit tests for Organization Prevention Service

Tests prevention policy management at organization, OU, and account levels.
Validates Requirements 14.1-14.7.
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from src.services.multi_account.organization_prevention_service import OrganizationPreventionService
from src.services.multi_account.models import Account


@pytest.fixture
def mock_prevention_engine():
    """Mock prevention engine"""
    engine = Mock()
    engine.run_prevention_cycle.return_value = {
        "success": True,
        "actions_taken": 2,
        "budget_events": 1,
        "timestamp": "2026-02-24T10:00:00Z"
    }
    return engine


@pytest.fixture
def mock_account_repo():
    """Mock account repository"""
    return Mock()


@pytest.fixture
def prevention_service(mock_prevention_engine, mock_account_repo):
    """Create prevention service with mocked dependencies"""
    return OrganizationPreventionService(
        prevention_engine=mock_prevention_engine,
        account_repository=mock_account_repo,
        max_workers=2
    )


def test_create_organization_policy(prevention_service, mock_account_repo, mock_prevention_engine):
    """Test organization-level policy creation (Requirement 14.1)"""
    # Given
    org_id = "o-123456789"
    policy_name = "cost-prevention-policy"
    policy_config = {
        "enabled": True,
        "dry_run_mode": False,
        "budget_thresholds": {"warning": 80, "action": 90}
    }
    
    mock_account_repo.list_by_organization.return_value = [
        Account(
            id="111111111111",
            arn="",
            name="Account 1",
            email="account1@example.com",
            status="ACTIVE",
            joined_method="",
            joined_timestamp=datetime.utcnow()
        ),
        Account(
            id="222222222222",
            arn="",
            name="Account 2",
            email="account2@example.com",
            status="ACTIVE",
            joined_method="",
            joined_timestamp=datetime.utcnow()
        )
    ]
    
    # When
    result = prevention_service.create_organization_policy(org_id, policy_name, policy_config)
    
    # Then
    assert result["success"] is True
    assert result["org_id"] == org_id
    assert result["policy_name"] == policy_name
    assert result["accounts_affected"] == 2
    assert result["successful_applications"] == 2
    assert result["failed_applications"] == 0


def test_create_organization_policy_no_accounts(prevention_service, mock_account_repo):
    """Test organization policy with no accounts"""
    # Given
    org_id = "o-123456789"
    policy_name = "cost-prevention-policy"
    policy_config = {"enabled": True}
    
    mock_account_repo.list_by_organization.return_value = []
    
    # When
    result = prevention_service.create_organization_policy(org_id, policy_name, policy_config)
    
    # Then
    assert result["success"] is False
    assert "error" in result


def test_create_ou_policy(prevention_service, mock_account_repo, mock_prevention_engine):
    """Test OU-level policy creation (Requirement 14.2)"""
    # Given
    ou_id = "ou-abc123"
    account_ids = ["111111111111", "222222222222"]
    policy_name = "ou-prevention-policy"
    policy_config = {
        "enabled": True,
        "approval_required": True
    }
    
    mock_account_repo.get.side_effect = [
        Account(
            id="111111111111",
            arn="",
            name="Account 1",
            email="account1@example.com",
            status="ACTIVE",
            joined_method="",
            joined_timestamp=datetime.utcnow()
        ),
        Account(
            id="222222222222",
            arn="",
            name="Account 2",
            email="account2@example.com",
            status="ACTIVE",
            joined_method="",
            joined_timestamp=datetime.utcnow()
        )
    ]
    
    # When
    result = prevention_service.create_ou_policy(ou_id, account_ids, policy_name, policy_config)
    
    # Then
    assert result["success"] is True
    assert result["ou_id"] == ou_id
    assert result["policy_name"] == policy_name
    assert result["accounts_affected"] == 2


def test_create_ou_policy_no_accounts(prevention_service):
    """Test OU policy with no accounts"""
    # Given
    ou_id = "ou-abc123"
    account_ids = []
    policy_name = "ou-prevention-policy"
    policy_config = {"enabled": True}
    
    # When
    result = prevention_service.create_ou_policy(ou_id, account_ids, policy_name, policy_config)
    
    # Then
    assert result["success"] is False
    assert "error" in result


def test_apply_account_policy(prevention_service, mock_prevention_engine):
    """Test account-level policy application (Requirement 14.5)"""
    # Given
    account_id = "111111111111"
    policy_name = "account-policy"
    policy_config = {
        "enabled": True,
        "dry_run_mode": True
    }
    
    # When
    result = prevention_service.apply_account_policy(account_id, policy_name, policy_config)
    
    # Then
    assert result["success"] is True
    assert result["account_id"] == account_id
    assert result["policy_name"] == policy_name
    assert result["override"] is False
    mock_prevention_engine.update_config.assert_called_once_with(policy_config)


def test_apply_account_policy_with_override(prevention_service, mock_prevention_engine):
    """Test account-level policy override"""
    # Given
    account_id = "111111111111"
    policy_name = "override-policy"
    policy_config = {"enabled": False}
    
    # When
    result = prevention_service.apply_account_policy(
        account_id, policy_name, policy_config, override=True
    )
    
    # Then
    assert result["success"] is True
    assert result["override"] is True


def test_apply_account_policy_failure(prevention_service, mock_prevention_engine):
    """Test account policy application failure"""
    # Given
    account_id = "111111111111"
    policy_name = "failing-policy"
    policy_config = {"invalid": "config"}
    
    mock_prevention_engine.update_config.side_effect = ValueError("Invalid config")
    
    # When
    result = prevention_service.apply_account_policy(account_id, policy_name, policy_config)
    
    # Then
    assert result["success"] is False
    assert "error" in result


def test_execute_prevention_across_accounts(prevention_service, mock_prevention_engine):
    """Test parallel prevention execution (Requirement 14.7)"""
    # Given
    account_ids = ["111111111111", "222222222222", "333333333333"]
    
    # When
    result = prevention_service.execute_prevention_across_accounts(account_ids)
    
    # Then
    assert result["success"] is True
    assert result["accounts_processed"] == 3
    assert result["successful_executions"] == 3
    assert result["failed_executions"] == 0
    assert len(result["results"]) == 3


def test_execute_prevention_with_failures(prevention_service, mock_prevention_engine):
    """Test prevention execution with some failures"""
    # Given
    account_ids = ["111111111111", "222222222222"]
    
    # Mock one success and one failure
    mock_prevention_engine.run_prevention_cycle.side_effect = [
        {
            "success": True,
            "actions_taken": 2,
            "budget_events": 1,
            "timestamp": "2026-02-24T10:00:00Z"
        },
        Exception("Prevention failed")
    ]
    
    # When
    result = prevention_service.execute_prevention_across_accounts(account_ids)
    
    # Then
    assert result["success"] is True  # At least one succeeded
    assert result["accounts_processed"] == 2
    assert result["successful_executions"] == 1
    assert result["failed_executions"] == 1


def test_policy_application_parallel_processing(prevention_service, mock_account_repo, mock_prevention_engine):
    """Test that policies are applied in parallel"""
    # Given
    org_id = "o-123456789"
    policy_name = "parallel-policy"
    policy_config = {"enabled": True}
    
    # Create 5 accounts
    accounts = [
        Account(
            id=f"{i:012d}",
            arn="",
            name=f"Account {i}",
            email=f"account{i}@example.com",
            status="ACTIVE",
            joined_method="",
            joined_timestamp=datetime.utcnow()
        )
        for i in range(5)
    ]
    mock_account_repo.list_by_organization.return_value = accounts
    
    # When
    result = prevention_service.create_organization_policy(org_id, policy_name, policy_config)
    
    # Then
    assert result["success"] is True
    assert result["accounts_affected"] == 5
    assert result["successful_applications"] == 5
