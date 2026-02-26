"""
Integration tests for Multi-Account GPU Cost Integration

Tests cross-account GPU cost collection, aggregation, and organization-wide reporting.
Validates Requirements IR-2.5, NFR-3.4
"""
import pytest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

from src.services.ai_ml.multi_account_gpu_integration import (
    MultiAccountGPUIntegration,
    MultiAccountGPUCosts
)
from src.services.ai_ml.gpu_cost_tracker import GPUCostData
from src.services.multi_account.cross_account_role_manager import Credentials


@pytest.fixture
def mock_role_manager():
    """Mock cross-account role manager"""
    manager = Mock()
    
    # Mock assume_role to return credentials
    manager.assume_role.return_value = Credentials(
        access_key_id="AKIAIOSFODNN7EXAMPLE",
        secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        session_token="FwoGZXIvYXdzEBYaDH...",
        expiration="2024-01-01T12:00:00Z"
    )
    
    # Mock create_boto3_session
    mock_session = Mock()
    manager.create_boto3_session.return_value = mock_session
    
    return manager


@pytest.fixture
def mock_gpu_cost_tracker():
    """Mock GPU cost tracker"""
    tracker = Mock()
    
    # Mock collect_gpu_costs to return sample data
    tracker.collect_gpu_costs.return_value = [
        GPUCostData(
            date="2024-01-01",
            instance_id="i-1234567890abcdef0",
            instance_type="p3.2xlarge",
            workload_type="training",
            cost=10.0,
            gpu_hours=5.0,
            cost_per_gpu_hour=2.0,
            utilization=85.0,
            classification_confidence=0.95
        ),
        GPUCostData(
            date="2024-01-01",
            instance_id="i-0987654321fedcba0",
            instance_type="g5.xlarge",
            workload_type="inference",
            cost=5.0,
            gpu_hours=10.0,
            cost_per_gpu_hour=0.5,
            utilization=45.0,
            classification_confidence=0.88
        )
    ]
    
    return tracker


@pytest.fixture
def integration_service(mock_role_manager, mock_gpu_cost_tracker):
    """Create integration service with mocked dependencies"""
    return MultiAccountGPUIntegration(
        role_manager=mock_role_manager,
        gpu_cost_tracker=mock_gpu_cost_tracker
    )


def test_collect_gpu_costs_single_account(integration_service, mock_role_manager, mock_gpu_cost_tracker):
    """Test collecting GPU costs from a single account"""
    # Arrange
    org_id = "o-123456789"
    account_ids = ["111111111111"]
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 31)
    
    # Act
    result = integration_service.collect_gpu_costs_all_accounts(
        org_id=org_id,
        account_ids=account_ids,
        start_date=start_date,
        end_date=end_date
    )
    
    # Assert
    assert result.org_id == org_id
    assert result.account_count == 1
    assert result.total_gpu_cost == Decimal("15.0")  # 10 + 5
    assert "111111111111" in result.costs_by_account
    assert result.costs_by_account["111111111111"] == Decimal("15.0")
    
    # Verify role assumption was called
    mock_role_manager.assume_role.assert_called_once()
    
    # Verify GPU cost collection was called
    mock_gpu_cost_tracker.collect_gpu_costs.assert_called_once()


def test_collect_gpu_costs_multiple_accounts(integration_service, mock_role_manager, mock_gpu_cost_tracker):
    """Test collecting GPU costs from multiple accounts"""
    # Arrange
    org_id = "o-123456789"
    account_ids = ["111111111111", "222222222222", "333333333333"]
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 31)
    
    # Act
    result = integration_service.collect_gpu_costs_all_accounts(
        org_id=org_id,
        account_ids=account_ids,
        start_date=start_date,
        end_date=end_date
    )
    
    # Assert
    assert result.org_id == org_id
    assert result.account_count == 3
    assert result.total_gpu_cost == Decimal("45.0")  # 15 * 3 accounts
    assert len(result.costs_by_account) == 3
    
    # Verify role assumption was called for each account
    assert mock_role_manager.assume_role.call_count == 3
    
    # Verify GPU cost collection was called for each account
    assert mock_gpu_cost_tracker.collect_gpu_costs.call_count == 3


def test_aggregate_by_workload_type(integration_service):
    """Test aggregating GPU costs by workload type"""
    # Arrange
    org_id = "o-123456789"
    account_ids = ["111111111111"]
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 31)
    
    # Act
    result = integration_service.collect_gpu_costs_all_accounts(
        org_id=org_id,
        account_ids=account_ids,
        start_date=start_date,
        end_date=end_date
    )
    
    # Assert
    assert "training" in result.costs_by_workload_type
    assert "inference" in result.costs_by_workload_type
    assert "idle" in result.costs_by_workload_type
    assert result.costs_by_workload_type["training"] == Decimal("10.0")
    assert result.costs_by_workload_type["inference"] == Decimal("5.0")
    assert result.costs_by_workload_type["idle"] == Decimal("0.0")


def test_aggregate_by_instance_type(integration_service):
    """Test aggregating GPU costs by instance type"""
    # Arrange
    org_id = "o-123456789"
    account_ids = ["111111111111"]
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 31)
    
    # Act
    result = integration_service.collect_gpu_costs_all_accounts(
        org_id=org_id,
        account_ids=account_ids,
        start_date=start_date,
        end_date=end_date
    )
    
    # Assert
    assert "p3.2xlarge" in result.costs_by_instance_type
    assert "g5.xlarge" in result.costs_by_instance_type
    assert result.costs_by_instance_type["p3.2xlarge"] == Decimal("10.0")
    assert result.costs_by_instance_type["g5.xlarge"] == Decimal("5.0")


def test_get_top_gpu_spending_accounts(integration_service, mock_gpu_cost_tracker):
    """Test getting top GPU spending accounts"""
    # Arrange
    org_id = "o-123456789"
    account_ids = ["111111111111", "222222222222", "333333333333"]
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 31)
    
    # Mock different costs for each account
    def mock_collect_costs(*args, **kwargs):
        session = kwargs.get('boto3_session')
        # Return different costs based on which account (simulated)
        return [
            GPUCostData(
                date="2024-01-01",
                instance_id="i-test",
                instance_type="p3.2xlarge",
                workload_type="training",
                cost=10.0,
                gpu_hours=5.0,
                cost_per_gpu_hour=2.0,
                utilization=85.0,
                classification_confidence=0.95
            )
        ]
    
    mock_gpu_cost_tracker.collect_gpu_costs.side_effect = mock_collect_costs
    
    # Act
    result = integration_service.get_top_gpu_spending_accounts(
        org_id=org_id,
        account_ids=account_ids,
        start_date=start_date,
        end_date=end_date,
        limit=2
    )
    
    # Assert
    assert len(result) == 2
    assert all("account_id" in account for account in result)
    assert all("gpu_cost" in account for account in result)
    assert all("percentage_of_total" in account for account in result)
    assert all("gpu_hours" in account for account in result)
    assert all("avg_utilization" in account for account in result)


def test_get_organization_gpu_utilization(integration_service):
    """Test getting organization-wide GPU utilization metrics"""
    # Arrange
    org_id = "o-123456789"
    account_ids = ["111111111111", "222222222222"]
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 31)
    
    # Act
    result = integration_service.get_organization_gpu_utilization(
        org_id=org_id,
        account_ids=account_ids,
        start_date=start_date,
        end_date=end_date
    )
    
    # Assert
    assert "total_gpu_hours" in result
    assert "avg_utilization" in result
    assert "idle_cost_percentage" in result
    assert "total_gpu_cost" in result
    assert result["total_gpu_hours"] > 0
    assert 0 <= result["avg_utilization"] <= 100
    assert 0 <= result["idle_cost_percentage"] <= 100


def test_handle_account_collection_failure(integration_service, mock_role_manager, mock_gpu_cost_tracker):
    """Test graceful handling of account collection failures"""
    # Arrange
    org_id = "o-123456789"
    account_ids = ["111111111111", "222222222222"]
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 31)
    
    # Mock failure for second account
    def mock_assume_role(*args, **kwargs):
        account_id = kwargs.get('account_id')
        if account_id == "222222222222":
            raise Exception("Access denied")
        return Credentials(
            access_key_id="AKIAIOSFODNN7EXAMPLE",
            secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            session_token="FwoGZXIvYXdzEBYaDH...",
            expiration="2024-01-01T12:00:00Z"
        )
    
    mock_role_manager.assume_role.side_effect = mock_assume_role
    
    # Act
    result = integration_service.collect_gpu_costs_all_accounts(
        org_id=org_id,
        account_ids=account_ids,
        start_date=start_date,
        end_date=end_date
    )
    
    # Assert - should continue with successful accounts
    assert result.account_count == 2
    assert "111111111111" in result.costs_by_account
    assert "222222222222" in result.costs_by_account
    assert result.costs_by_account["222222222222"] == Decimal("0.0")


def test_cross_account_role_usage(integration_service, mock_role_manager):
    """Test that cross-account roles are used correctly"""
    # Arrange
    org_id = "o-123456789"
    account_ids = ["111111111111"]
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 31)
    role_name = "CustomCostRole"
    external_id = "unique-external-id-123"
    
    # Act
    integration_service.collect_gpu_costs_all_accounts(
        org_id=org_id,
        account_ids=account_ids,
        start_date=start_date,
        end_date=end_date,
        role_name=role_name,
        external_id=external_id
    )
    
    # Assert
    mock_role_manager.assume_role.assert_called_once_with(
        account_id="111111111111",
        role_name=role_name,
        external_id=external_id
    )


def test_gpu_hours_tracking(integration_service):
    """Test GPU hours are tracked correctly across accounts"""
    # Arrange
    org_id = "o-123456789"
    account_ids = ["111111111111"]
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 31)
    
    # Act
    result = integration_service.collect_gpu_costs_all_accounts(
        org_id=org_id,
        account_ids=account_ids,
        start_date=start_date,
        end_date=end_date
    )
    
    # Assert
    assert "111111111111" in result.gpu_hours_by_account
    assert result.gpu_hours_by_account["111111111111"] == 15.0  # 5 + 10 from mock data


def test_utilization_tracking(integration_service):
    """Test GPU utilization is tracked correctly across accounts"""
    # Arrange
    org_id = "o-123456789"
    account_ids = ["111111111111"]
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 31)
    
    # Act
    result = integration_service.collect_gpu_costs_all_accounts(
        org_id=org_id,
        account_ids=account_ids,
        start_date=start_date,
        end_date=end_date
    )
    
    # Assert
    assert "111111111111" in result.utilization_by_account
    # Average of 85.0 and 45.0
    assert result.utilization_by_account["111111111111"] == 65.0


def test_empty_account_list(integration_service):
    """Test handling of empty account list"""
    # Arrange
    org_id = "o-123456789"
    account_ids = []
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 31)
    
    # Act
    result = integration_service.collect_gpu_costs_all_accounts(
        org_id=org_id,
        account_ids=account_ids,
        start_date=start_date,
        end_date=end_date
    )
    
    # Assert
    assert result.account_count == 0
    assert result.total_gpu_cost == Decimal("0.0")
    assert len(result.costs_by_account) == 0


def test_aggregate_gpu_costs_by_workload_method(integration_service):
    """Test the aggregate_gpu_costs_by_workload convenience method"""
    # Arrange
    org_id = "o-123456789"
    account_ids = ["111111111111"]
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 31)
    
    # Act
    result = integration_service.aggregate_gpu_costs_by_workload(
        org_id=org_id,
        account_ids=account_ids,
        start_date=start_date,
        end_date=end_date
    )
    
    # Assert
    assert isinstance(result, dict)
    assert "training" in result
    assert "inference" in result
    assert "idle" in result
    assert result["training"] == Decimal("10.0")
    assert result["inference"] == Decimal("5.0")
