"""
Property-Based Tests for Budget Service

Tests universal properties of budget management and hierarchical rollup.
"""
import pytest
from decimal import Decimal
from datetime import datetime
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock

from src.services.multi_account.organization_budget_service import OrganizationBudgetService
from src.services.multi_account.models import Account, AccountCostData, EntityType


@given(
    ou_budget=st.decimals(min_value=1000, max_value=100000, places=2),
    account_budgets=st.lists(
        st.decimals(min_value=100, max_value=10000, places=2),
        min_size=2,
        max_size=5
    )
)
@settings(max_examples=20)
def test_property_7_budget_rollup_consistency(ou_budget, account_budgets):
    """
    Property 7: Budget Rollup Consistency
    
    For any OU, sum of account budgets should not exceed OU budget.
    
    Validates: Requirements 12.1, 12.2
    """
    # Create fresh mocks for each test iteration
    budget_repo = Mock()
    account_repo = Mock()
    cost_repo = Mock()
    service = OrganizationBudgetService(budget_repo, account_repo, cost_repo)
    
    # Given: OU budget and account budgets
    ou_id = "ou-test123"
    date = "2026-02-24"
    
    # Ensure account budgets don't exceed OU budget
    total_account_budgets = sum(account_budgets)
    if total_account_budgets > ou_budget:
        # Scale down account budgets proportionally
        scale_factor = ou_budget / total_account_budgets * Decimal("0.9")  # 90% to leave margin
        account_budgets = [budget * scale_factor for budget in account_budgets]
    
    # Mock OU budget
    budget_repo.list_by_entity.return_value = [{
        "budget_id": "budget-ou",
        "budget_amount": ou_budget,
        "entity_id": ou_id,
        "entity_type": EntityType.OU.value
    }]
    
    # Create mock accounts with costs equal to their budgets
    account_ids = [f"acc{i:012d}" for i in range(len(account_budgets))]
    mock_costs = []
    for i, budget in enumerate(account_budgets):
        mock_costs.append(
            AccountCostData(
                account_id=account_ids[i],
                start_date=date,
                end_date=date,
                total_cost=budget,  # Spend exactly the budget
                costs_by_service={},
                costs_by_day={},
                collection_timestamp=datetime.utcnow(),
                status="SUCCESS"
            )
        )
    
    cost_repo.get.side_effect = mock_costs
    
    # When: Calculate OU utilization
    result = service.calculate_ou_utilization(ou_id, account_ids, date)
    
    # Then: Sum of account costs should not exceed OU budget
    total_account_spend = sum(account_budgets)
    assert result["current_spend"] == total_account_spend
    assert result["current_spend"] <= ou_budget, \
        f"Account costs ({total_account_spend}) exceed OU budget ({ou_budget})"


@given(
    org_budget=st.decimals(min_value=10000, max_value=500000, places=2),
    ou_budgets=st.lists(
        st.decimals(min_value=1000, max_value=50000, places=2),
        min_size=2,
        max_size=4
    )
)
@settings(max_examples=20)
def test_property_7_org_budget_rollup(org_budget, ou_budgets):
    """
    Property 7: Organization Budget Rollup
    
    For any organization, sum of OU budgets should not exceed org budget.
    
    Validates: Requirements 12.1, 12.2
    """
    # Create fresh mocks for each test iteration
    budget_repo = Mock()
    account_repo = Mock()
    cost_repo = Mock()
    service = OrganizationBudgetService(budget_repo, account_repo, cost_repo)
    
    # Given: Organization budget and OU budgets
    org_id = "o-test123"
    date = "2026-02-24"
    
    # Ensure OU budgets don't exceed org budget
    total_ou_budgets = sum(ou_budgets)
    if total_ou_budgets > org_budget:
        # Scale down OU budgets proportionally
        scale_factor = org_budget / total_ou_budgets * Decimal("0.9")
        ou_budgets = [budget * scale_factor for budget in ou_budgets]
    
    # Mock organization budget
    budget_repo.list_by_entity.return_value = [{
        "budget_id": "budget-org",
        "budget_amount": org_budget,
        "entity_id": org_id,
        "entity_type": EntityType.ORGANIZATION.value
    }]
    
    # Create mock accounts across OUs with costs
    accounts = []
    mock_costs = []
    account_counter = 0
    
    for ou_budget in ou_budgets:
        # Each OU has 2 accounts
        for _ in range(2):
            account_id = f"acc{account_counter:012d}"
            accounts.append(
                Account(
                    id=account_id,
                    arn="",
                    name=f"Account {account_counter}",
                    email=f"account{account_counter}@example.com",
                    status="ACTIVE",
                    joined_method="",
                    joined_timestamp=datetime.utcnow()
                )
            )
            # Each account spends half of its OU budget
            mock_costs.append(
                AccountCostData(
                    account_id=account_id,
                    start_date=date,
                    end_date=date,
                    total_cost=ou_budget / 2,
                    costs_by_service={},
                    costs_by_day={},
                    collection_timestamp=datetime.utcnow(),
                    status="SUCCESS"
                )
            )
            account_counter += 1
    
    account_repo.list_by_organization.return_value = accounts
    cost_repo.get.side_effect = mock_costs
    
    # When: Calculate organization utilization
    result = service.calculate_org_utilization(org_id, date)
    
    # Then: Sum of OU costs should not exceed org budget
    total_ou_spend = sum(ou_budgets)
    # Use approximate comparison for Decimal precision
    assert abs(result["current_spend"] - total_ou_spend) < Decimal("0.01"), \
        f"Spend mismatch: {result['current_spend']} vs {total_ou_spend}"
    assert result["current_spend"] <= org_budget, \
        f"OU costs ({total_ou_spend}) exceed org budget ({org_budget})"


@given(
    budget_amount=st.decimals(min_value=1000, max_value=100000, places=2),
    spend_percentage=st.floats(min_value=0.0, max_value=1.5)
)
@settings(max_examples=20)
def test_property_budget_alert_thresholds(budget_amount, spend_percentage):
    """
    Property: Budget Alert Thresholds
    
    Budget alerts should be generated at correct thresholds:
    - WARNING at 80%+
    - CRITICAL at 100%+
    
    Validates: Requirements 11.6, 11.7
    """
    # Create fresh mocks for each test iteration
    budget_repo = Mock()
    account_repo = Mock()
    cost_repo = Mock()
    service = OrganizationBudgetService(budget_repo, account_repo, cost_repo)
    
    # Given: Budget and spending
    budget_id = "budget-test"
    current_spend = budget_amount * Decimal(str(spend_percentage))
    
    budget_repo.get.return_value = {
        "budget_id": budget_id,
        "budget_amount": budget_amount
    }
    
    # When: Monitor budget
    alerts = service.monitor_budget(budget_id, current_spend)
    
    # Then: Alerts should match thresholds
    utilization = float(current_spend / budget_amount * 100)
    
    if utilization >= 100:
        assert len(alerts) == 1
        assert alerts[0]["level"] == "CRITICAL"
    elif utilization >= 80:
        assert len(alerts) == 1
        assert alerts[0]["level"] == "WARNING"
    else:
        assert len(alerts) == 0
