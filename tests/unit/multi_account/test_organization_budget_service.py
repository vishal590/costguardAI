"""
Unit tests for Organization Budget Service

Tests budget creation, monitoring, and hierarchical rollup.
Validates Requirements 11.1-11.7 and 12.1-12.7.
"""
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, MagicMock

from src.services.multi_account.organization_budget_service import OrganizationBudgetService
from src.services.multi_account.models import Account, AccountCostData, EntityType


@pytest.fixture
def mock_budget_repo():
    """Mock budget repository"""
    return Mock()


@pytest.fixture
def mock_account_repo():
    """Mock account repository"""
    return Mock()


@pytest.fixture
def mock_cost_repo():
    """Mock cost repository"""
    return Mock()


@pytest.fixture
def budget_service(mock_budget_repo, mock_account_repo, mock_cost_repo):
    """Create budget service with mocked dependencies"""
    return OrganizationBudgetService(
        budget_repository=mock_budget_repo,
        account_repository=mock_account_repo,
        cost_repository=mock_cost_repo
    )


def test_create_organization_budget(budget_service, mock_budget_repo):
    """Test creating organization-level budget (Requirement 11.1)"""
    # Given
    org_id = "o-123456789"
    budget_amount = Decimal("10000.00")
    
    # When
    budget_id = budget_service.create_organization_budget(org_id, budget_amount)
    
    # Then
    assert budget_id.startswith("budget-")
    mock_budget_repo.save.assert_called_once()
    call_args = mock_budget_repo.save.call_args[1]
    assert call_args["entity_id"] == org_id
    assert call_args["entity_type"] == EntityType.ORGANIZATION.value
    assert call_args["budget_amount"] == budget_amount


def test_create_ou_budget(budget_service, mock_budget_repo):
    """Test creating OU-level budget (Requirement 11.2)"""
    # Given
    ou_id = "ou-abc123"
    budget_amount = Decimal("5000.00")
    
    # When
    budget_id = budget_service.create_ou_budget(ou_id, budget_amount)
    
    # Then
    assert budget_id.startswith("budget-")
    mock_budget_repo.save.assert_called_once()
    call_args = mock_budget_repo.save.call_args[1]
    assert call_args["entity_id"] == ou_id
    assert call_args["entity_type"] == EntityType.OU.value
    assert call_args["budget_amount"] == budget_amount


def test_create_account_budget(budget_service, mock_budget_repo):
    """Test creating account-level budget (Requirement 11.3)"""
    # Given
    account_id = "123456789012"
    budget_amount = Decimal("1000.00")
    
    # When
    budget_id = budget_service.create_account_budget(account_id, budget_amount)
    
    # Then
    assert budget_id.startswith("budget-")
    mock_budget_repo.save.assert_called_once()
    call_args = mock_budget_repo.save.call_args[1]
    assert call_args["entity_id"] == account_id
    assert call_args["entity_type"] == EntityType.ACCOUNT.value
    assert call_args["budget_amount"] == budget_amount


def test_calculate_ou_utilization(budget_service, mock_budget_repo, mock_cost_repo):
    """Test OU budget utilization calculation (Requirement 12.1)"""
    # Given
    ou_id = "ou-abc123"
    account_ids = ["111111111111", "222222222222"]
    date = "2026-02-24"
    
    # Mock OU budget
    mock_budget_repo.list_by_entity.return_value = [{
        "budget_id": "budget-1",
        "budget_amount": Decimal("5000.00"),
        "entity_id": ou_id,
        "entity_type": EntityType.OU.value
    }]
    
    # Mock account costs
    mock_cost_repo.get.side_effect = [
        AccountCostData(
            account_id="111111111111",
            start_date=date,
            end_date=date,
            total_cost=Decimal("2000.00"),
            costs_by_service={},
            costs_by_day={},
            collection_timestamp=datetime.utcnow(),
            status="SUCCESS"
        ),
        AccountCostData(
            account_id="222222222222",
            start_date=date,
            end_date=date,
            total_cost=Decimal("1500.00"),
            costs_by_service={},
            costs_by_day={},
            collection_timestamp=datetime.utcnow(),
            status="SUCCESS"
        )
    ]
    
    # When
    result = budget_service.calculate_ou_utilization(ou_id, account_ids, date)
    
    # Then
    assert result["ou_id"] == ou_id
    assert result["budget_amount"] == Decimal("5000.00")
    assert result["current_spend"] == Decimal("3500.00")
    assert result["utilization_percentage"] == 70.0
    assert result["status"] == "OK"


def test_calculate_org_utilization(budget_service, mock_budget_repo, mock_account_repo, mock_cost_repo):
    """Test organization budget utilization calculation (Requirement 12.2)"""
    # Given
    org_id = "o-123456789"
    date = "2026-02-24"
    
    # Mock organization budget
    mock_budget_repo.list_by_entity.return_value = [{
        "budget_id": "budget-org",
        "budget_amount": Decimal("10000.00"),
        "entity_id": org_id,
        "entity_type": EntityType.ORGANIZATION.value
    }]
    
    # Mock accounts
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
    
    # Mock account costs
    mock_cost_repo.get.side_effect = [
        AccountCostData(
            account_id="111111111111",
            start_date=date,
            end_date=date,
            total_cost=Decimal("4000.00"),
            costs_by_service={},
            costs_by_day={},
            collection_timestamp=datetime.utcnow(),
            status="SUCCESS"
        ),
        AccountCostData(
            account_id="222222222222",
            start_date=date,
            end_date=date,
            total_cost=Decimal("3000.00"),
            costs_by_service={},
            costs_by_day={},
            collection_timestamp=datetime.utcnow(),
            status="SUCCESS"
        )
    ]
    
    # When
    result = budget_service.calculate_org_utilization(org_id, date)
    
    # Then
    assert result["org_id"] == org_id
    assert result["budget_amount"] == Decimal("10000.00")
    assert result["current_spend"] == Decimal("7000.00")
    assert result["utilization_percentage"] == 70.0
    assert result["status"] == "OK"



def test_monitor_budget_warning_threshold(budget_service, mock_budget_repo):
    """Test budget monitoring at 80% threshold (Requirement 11.6)"""
    # Given
    budget_id = "budget-123"
    current_spend = Decimal("850.00")
    
    mock_budget_repo.get.return_value = {
        "budget_id": budget_id,
        "budget_amount": Decimal("1000.00")
    }
    
    # When
    alerts = budget_service.monitor_budget(budget_id, current_spend)
    
    # Then
    assert len(alerts) == 1
    assert alerts[0]["level"] == "WARNING"
    assert alerts[0]["utilization"] == 85.0


def test_monitor_budget_critical_threshold(budget_service, mock_budget_repo):
    """Test budget monitoring at 100% threshold (Requirement 11.7)"""
    # Given
    budget_id = "budget-123"
    current_spend = Decimal("1200.00")
    
    mock_budget_repo.get.return_value = {
        "budget_id": budget_id,
        "budget_amount": Decimal("1000.00")
    }
    
    # When
    alerts = budget_service.monitor_budget(budget_id, current_spend)
    
    # Then
    assert len(alerts) == 1
    assert alerts[0]["level"] == "CRITICAL"
    assert alerts[0]["utilization"] == 120.0


def test_monitor_budget_no_alerts(budget_service, mock_budget_repo):
    """Test budget monitoring with no alerts"""
    # Given
    budget_id = "budget-123"
    current_spend = Decimal("500.00")
    
    mock_budget_repo.get.return_value = {
        "budget_id": budget_id,
        "budget_amount": Decimal("1000.00")
    }
    
    # When
    alerts = budget_service.monitor_budget(budget_id, current_spend)
    
    # Then
    assert len(alerts) == 0


def test_get_budget_hierarchy(budget_service, mock_budget_repo, mock_account_repo, mock_cost_repo):
    """Test budget hierarchy visualization (Requirement 12.5)"""
    # Given
    org_id = "o-123456789"
    date = "2026-02-24"
    
    # Mock organization budget
    mock_budget_repo.list_by_entity.side_effect = [
        # Organization budget
        [{
            "budget_id": "budget-org",
            "budget_amount": Decimal("10000.00"),
            "entity_id": org_id,
            "entity_type": EntityType.ORGANIZATION.value
        }],
        # Account 1 budget
        [{
            "budget_id": "budget-acc1",
            "budget_amount": Decimal("5000.00"),
            "entity_id": "111111111111",
            "entity_type": EntityType.ACCOUNT.value
        }],
        # Account 2 budget
        [{
            "budget_id": "budget-acc2",
            "budget_amount": Decimal("3000.00"),
            "entity_id": "222222222222",
            "entity_type": EntityType.ACCOUNT.value
        }]
    ]
    
    # Mock accounts
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
    
    # Mock account costs
    mock_cost_repo.get.side_effect = [
        # For org calculation
        AccountCostData(
            account_id="111111111111",
            start_date=date,
            end_date=date,
            total_cost=Decimal("4000.00"),
            costs_by_service={},
            costs_by_day={},
            collection_timestamp=datetime.utcnow(),
            status="SUCCESS"
        ),
        AccountCostData(
            account_id="222222222222",
            start_date=date,
            end_date=date,
            total_cost=Decimal("2500.00"),
            costs_by_service={},
            costs_by_day={},
            collection_timestamp=datetime.utcnow(),
            status="SUCCESS"
        ),
        # For account details
        AccountCostData(
            account_id="111111111111",
            start_date=date,
            end_date=date,
            total_cost=Decimal("4000.00"),
            costs_by_service={},
            costs_by_day={},
            collection_timestamp=datetime.utcnow(),
            status="SUCCESS"
        ),
        AccountCostData(
            account_id="222222222222",
            start_date=date,
            end_date=date,
            total_cost=Decimal("2500.00"),
            costs_by_service={},
            costs_by_day={},
            collection_timestamp=datetime.utcnow(),
            status="SUCCESS"
        )
    ]
    
    # When
    result = budget_service.get_budget_hierarchy(org_id, date)
    
    # Then
    assert "organization" in result
    assert result["organization"]["org_id"] == org_id
    assert result["organization"]["current_spend"] == Decimal("6500.00")
    
    assert "accounts" in result
    assert len(result["accounts"]) == 2
    assert result["accounts"][0]["account_id"] == "111111111111"
    assert result["accounts"][0]["utilization_percentage"] == 80.0
    assert result["accounts"][1]["account_id"] == "222222222222"
    assert result["accounts"][1]["utilization_percentage"] == pytest.approx(83.33, rel=0.01)


def test_calculate_ou_utilization_no_budget(budget_service, mock_budget_repo):
    """Test OU utilization when no budget exists"""
    # Given
    ou_id = "ou-abc123"
    account_ids = ["111111111111"]
    date = "2026-02-24"
    
    mock_budget_repo.list_by_entity.return_value = []
    
    # When
    result = budget_service.calculate_ou_utilization(ou_id, account_ids, date)
    
    # Then
    assert result["status"] == "NO_BUDGET"
    assert result["budget_amount"] == Decimal("0")


def test_calculate_org_utilization_no_budget(budget_service, mock_budget_repo):
    """Test organization utilization when no budget exists"""
    # Given
    org_id = "o-123456789"
    date = "2026-02-24"
    
    mock_budget_repo.list_by_entity.return_value = []
    
    # When
    result = budget_service.calculate_org_utilization(org_id, date)
    
    # Then
    assert result["status"] == "NO_BUDGET"
    assert result["budget_amount"] == Decimal("0")


def test_budget_status_exceeded(budget_service):
    """Test budget status when exceeded"""
    status = budget_service._get_budget_status(120.0)
    assert status == "EXCEEDED"


def test_budget_status_warning(budget_service):
    """Test budget status at warning threshold"""
    status = budget_service._get_budget_status(85.0)
    assert status == "WARNING"


def test_budget_status_ok(budget_service):
    """Test budget status when OK"""
    status = budget_service._get_budget_status(50.0)
    assert status == "OK"
