"""
Comprehensive Unit Tests for Service Layer Components

Tests business logic, error handling, and edge cases for all service layer components.
"""
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from src.services.multi_account.allocation_rules_engine import AllocationRulesEngine
from src.services.multi_account.organization_budget_service import OrganizationBudgetService
from src.services.multi_account.cost_aggregation_engine import CostAggregationEngine
from src.services.multi_account.cost_allocation_engine import CostAllocationEngine
from src.services.multi_account.per_account_cost_service import PerAccountCostService
from src.services.multi_account.models import (
    AllocationRule, Account, AccountCostData, AggregatedCosts
)


class TestAllocationRulesEngineEdgeCases:
    """Test edge cases for AllocationRulesEngine"""
    
    def test_validate_rule_empty_allocation_target(self):
        """Test validation fails with empty allocation target"""
        engine = AllocationRulesEngine()
        
        with pytest.raises(ValueError, match="allocation_target"):
            engine.validate_rule(
                rule_type="TAG_BASED",
                conditions={"tag_key": "Team", "tag_value": "Engineering"},
                allocation_target=""
            )
    
    def test_validate_rule_none_allocation_target(self):
        """Test validation fails with None allocation target"""
        engine = AllocationRulesEngine()
        
        with pytest.raises(ValueError, match="allocation_target"):
            engine.validate_rule(
                rule_type="TAG_BASED",
                conditions={"tag_key": "Team", "tag_value": "Engineering"},
                allocation_target=None
            )
    
    def test_validate_percentage_rule_boundary_values(self):
        """Test percentage rule validation at boundary values"""
        engine = AllocationRulesEngine()
        
        # Test 0% - should fail
        with pytest.raises(ValueError, match="percentage"):
            engine.validate_rule(
                rule_type="PERCENTAGE",
                conditions={"percentage": 0},
                allocation_target="Target"
            )
        
        # Test 100% - should pass
        engine.validate_rule(
            rule_type="PERCENTAGE",
            conditions={"percentage": 100},
            allocation_target="Target"
        )
        
        # Test 100.01% - should fail
        with pytest.raises(ValueError, match="percentage"):
            engine.validate_rule(
                rule_type="PERCENTAGE",
                conditions={"percentage": 100.01},
                allocation_target="Target"
            )
    
    def test_get_rules_for_organization_empty_list(self):
        """Test getting rules when organization has no rules"""
        mock_repo = Mock()
        mock_repo.list_by_organization = MagicMock(return_value=[])
        
        engine = AllocationRulesEngine(rule_repository=mock_repo)
        rules = engine.get_rules_for_organization("o-123456789")
        
        assert rules == []
    
    def test_apply_rules_by_priority_empty_rules(self):
        """Test applying rules with empty rule list"""
        engine = AllocationRulesEngine()
        
        allocations = engine.apply_rules_by_priority([], {})
        
        assert allocations == {}
    
    def test_update_rule_not_found(self):
        """Test updating non-existent rule"""
        mock_repo = Mock()
        mock_repo.list_by_organization = MagicMock(return_value=[])
        
        engine = AllocationRulesEngine(rule_repository=mock_repo)
        
        with pytest.raises(ValueError, match="not found"):
            engine.update_rule(
                org_id="o-123456789",
                rule_id="non-existent",
                name="New Name"
            )


class TestOrganizationBudgetServiceEdgeCases:
    """Test edge cases for OrganizationBudgetService"""
    
    def test_calculate_ou_utilization_no_budget(self):
        """Test OU utilization calculation when no budget exists"""
        mock_budget_repo = Mock()
        mock_budget_repo.list_by_entity = MagicMock(return_value=[])
        mock_account_repo = Mock()
        mock_cost_repo = Mock()
        
        service = OrganizationBudgetService(
            budget_repository=mock_budget_repo,
            account_repository=mock_account_repo,
            cost_repository=mock_cost_repo
        )
        
        result = service.calculate_ou_utilization(
            ou_id="ou-123",
            account_ids=["123456789012"],
            date="2024-01-15"
        )
        
        assert result["status"] == "NO_BUDGET"
        assert result["budget_amount"] == Decimal("0")
        assert result["utilization_percentage"] == 0.0
    
    def test_calculate_org_utilization_no_accounts(self):
        """Test organization utilization with no accounts"""
        mock_budget_repo = Mock()
        mock_budget_repo.list_by_entity = MagicMock(return_value=[{
            "budget_amount": Decimal("10000.00")
        }])
        mock_account_repo = Mock()
        mock_account_repo.list_by_organization = MagicMock(return_value=[])
        mock_cost_repo = Mock()
        
        service = OrganizationBudgetService(
            budget_repository=mock_budget_repo,
            account_repository=mock_account_repo,
            cost_repository=mock_cost_repo
        )
        
        result = service.calculate_org_utilization(
            org_id="o-123456789",
            date="2024-01-15"
        )
        
        assert result["current_spend"] == Decimal("0")
        assert result["utilization_percentage"] == 0.0
    
    def test_monitor_budget_no_budget(self):
        """Test monitoring non-existent budget"""
        mock_budget_repo = Mock()
        mock_budget_repo.get = MagicMock(return_value=None)
        mock_account_repo = Mock()
        mock_cost_repo = Mock()
        
        service = OrganizationBudgetService(
            budget_repository=mock_budget_repo,
            account_repository=mock_account_repo,
            cost_repository=mock_cost_repo
        )
        
        alerts = service.monitor_budget("budget-123", Decimal("1000.00"))
        
        assert alerts == []
    
    def test_monitor_budget_zero_budget_amount(self):
        """Test monitoring budget with zero amount"""
        mock_budget_repo = Mock()
        mock_budget_repo.get = MagicMock(return_value={
            "budget_amount": Decimal("0.00")
        })
        mock_account_repo = Mock()
        mock_cost_repo = Mock()
        
        service = OrganizationBudgetService(
            budget_repository=mock_budget_repo,
            account_repository=mock_account_repo,
            cost_repository=mock_cost_repo
        )
        
        alerts = service.monitor_budget("budget-123", Decimal("1000.00"))
        
        # Should not crash with division by zero
        assert isinstance(alerts, list)
    
    def test_get_budget_hierarchy_accounts_without_budgets(self):
        """Test budget hierarchy when accounts have no budgets"""
        mock_budget_repo = Mock()
        mock_budget_repo.list_by_entity = MagicMock(side_effect=[
            [{"budget_amount": Decimal("10000.00")}],  # Org budget
            []  # Account budget (empty)
        ])
        
        mock_account = Mock()
        mock_account.id = "123456789012"
        mock_account.name = "Test Account"
        
        mock_account_repo = Mock()
        mock_account_repo.list_by_organization = MagicMock(return_value=[mock_account])
        
        mock_cost_repo = Mock()
        mock_cost_repo.get = MagicMock(return_value=None)
        
        service = OrganizationBudgetService(
            budget_repository=mock_budget_repo,
            account_repository=mock_account_repo,
            cost_repository=mock_cost_repo
        )
        
        result = service.get_budget_hierarchy("o-123456789", "2024-01-15")
        
        # Should return hierarchy with org but no account details
        assert "organization" in result
        assert "accounts" in result
        assert len(result["accounts"]) == 0


class TestCostAggregationEngineEdgeCases:
    """Test edge cases for CostAggregationEngine"""
    
    def test_aggregate_organization_costs_empty_accounts(self):
        """Test aggregation with empty account list"""
        mock_cost_repo = Mock()
        mock_account_repo = Mock()
        
        engine = CostAggregationEngine(
            cost_repository=mock_cost_repo,
            account_repository=mock_account_repo
        )
        
        result = engine.aggregate_organization_costs(
            org_id="o-123456789",
            account_ids=[]
        )
        
        assert result.total_cost == Decimal("0")
        assert result.account_count == 0
    
    def test_aggregate_organization_costs_no_cost_data(self):
        """Test aggregation when accounts have no cost data"""
        mock_cost_repo = Mock()
        mock_cost_repo.list_by_date = MagicMock(return_value=[])
        mock_account_repo = Mock()
        
        engine = CostAggregationEngine(
            cost_repository=mock_cost_repo,
            account_repository=mock_account_repo
        )
        
        result = engine.aggregate_organization_costs(
            org_id="o-123456789",
            account_ids=["123456789012", "234567890123"]
        )
        
        assert result.total_cost == Decimal("0")
    
    def test_aggregate_by_service_null_values(self):
        """Test service aggregation with null cost values"""
        mock_cost_data = Mock()
        mock_cost_data.account_id = "123456789012"
        mock_cost_data.total_cost = Decimal("100.00")
        mock_cost_data.costs_by_service = {
            "EC2": Decimal("50.00"),
            "S3": None,  # Null value
            "Lambda": Decimal("50.00")
        }
        
        mock_cost_repo = Mock()
        mock_cost_repo.list_by_date = MagicMock(return_value=[mock_cost_data])
        mock_account_repo = Mock()
        
        engine = CostAggregationEngine(
            cost_repository=mock_cost_repo,
            account_repository=mock_account_repo
        )
        
        # Should handle null values gracefully
        result = engine.aggregate_by_service(
            org_id="o-123456789",
            account_ids=["123456789012"]
        )
        
        assert isinstance(result, dict)


class TestCostAllocationEngineEdgeCases:
    """Test edge cases for CostAllocationEngine"""
    
    def test_allocate_by_tags_empty_cost_data(self):
        """Test tag allocation with no cost data"""
        mock_cost_repo = Mock()
        mock_cost_repo.list_by_date = MagicMock(return_value=[])
        
        engine = CostAllocationEngine(cost_repository=mock_cost_repo)
        
        result = engine.allocate_by_tags(
            org_id="o-123456789",
            account_ids=["123456789012"],
            tag_key="Team"
        )
        
        assert result == {}
    
    def test_calculate_unallocated_costs_no_data(self):
        """Test unallocated cost calculation with no data"""
        mock_cost_repo = Mock()
        mock_cost_repo.list_by_date = MagicMock(return_value=[])
        
        engine = CostAllocationEngine(cost_repository=mock_cost_repo)
        
        result = engine.calculate_unallocated_costs()
        
        assert result.total_cost == Decimal("0")
        assert result.unallocated_cost == Decimal("0")
    
    def test_get_allocation_by_team_default_tag(self):
        """Test team allocation uses default 'Team' tag"""
        mock_cost_repo = Mock()
        mock_cost_repo.list_by_date = MagicMock(return_value=[])
        
        engine = CostAllocationEngine(cost_repository=mock_cost_repo)
        
        # Should not raise error with default tag
        result = engine.get_allocation_by_team(
            org_id="o-123456789",
            account_ids=["123456789012"]
        )
        
        assert isinstance(result, dict)


class TestPerAccountCostServiceEdgeCases:
    """Test edge cases for PerAccountCostService"""
    
    def test_get_account_costs_no_data(self):
        """Test getting costs for account with no data"""
        mock_cost_repo = Mock()
        mock_cost_repo.get = MagicMock(return_value=None)
        
        service = PerAccountCostService(cost_repository=mock_cost_repo)
        
        result = service.get_account_costs(
            account_id="123456789012",
            date="2024-01-15"
        )
        
        assert result is None
    
    def test_get_costs_by_account_empty_list(self):
        """Test getting costs with empty account list"""
        mock_cost_repo = Mock()
        
        service = PerAccountCostService(cost_repository=mock_cost_repo)
        
        result = service.get_costs_by_account(
            account_ids=[],
            date="2024-01-15"
        )
        
        assert result == {}
    
    def test_get_costs_by_account_mixed_data(self):
        """Test getting costs when some accounts have data and some don't"""
        mock_cost_data = Mock()
        mock_cost_data.account_id = "123456789012"
        mock_cost_data.total_cost = Decimal("100.00")
        
        mock_cost_repo = Mock()
        mock_cost_repo.get = MagicMock(side_effect=[
            mock_cost_data,  # First account has data
            None,  # Second account has no data
            mock_cost_data  # Third account has data
        ])
        
        service = PerAccountCostService(cost_repository=mock_cost_repo)
        
        result = service.get_costs_by_account(
            account_ids=["123456789012", "234567890123", "345678901234"],
            date="2024-01-15"
        )
        
        # Should only include accounts with data
        assert len(result) == 2
        assert "123456789012" in result
        assert "234567890123" not in result
        assert "345678901234" in result


class TestServiceLayerErrorHandling:
    """Test error handling across service layer"""
    
    def test_allocation_rules_engine_repository_error(self):
        """Test AllocationRulesEngine handles repository errors"""
        mock_repo = Mock()
        mock_repo.save_rule = MagicMock(side_effect=Exception("DynamoDB error"))
        
        engine = AllocationRulesEngine(rule_repository=mock_repo)
        
        with pytest.raises(Exception, match="DynamoDB error"):
            engine.create_rule(
                org_id="o-123456789",
                name="Test Rule",
                priority=100,
                rule_type="TAG_BASED",
                conditions={"tag_key": "Team", "tag_value": "Engineering"},
                allocation_target="Engineering"
            )
    
    def test_budget_service_repository_error(self):
        """Test OrganizationBudgetService handles repository errors"""
        mock_budget_repo = Mock()
        mock_budget_repo.save = MagicMock(side_effect=Exception("DynamoDB error"))
        mock_account_repo = Mock()
        mock_cost_repo = Mock()
        
        service = OrganizationBudgetService(
            budget_repository=mock_budget_repo,
            account_repository=mock_account_repo,
            cost_repository=mock_cost_repo
        )
        
        with pytest.raises(Exception, match="DynamoDB error"):
            service.create_organization_budget(
                org_id="o-123456789",
                budget_amount=Decimal("10000.00"),
                period="MONTHLY"
            )
    
    def test_cost_aggregation_engine_invalid_date_format(self):
        """Test CostAggregationEngine with invalid date format"""
        mock_cost_repo = Mock()
        mock_account_repo = Mock()
        
        engine = CostAggregationEngine(
            cost_repository=mock_cost_repo,
            account_repository=mock_account_repo
        )
        
        # Should handle invalid date format gracefully
        # (actual validation happens at handler level)
        result = engine.aggregate_organization_costs(
            org_id="o-123456789",
            account_ids=["123456789012"],
            start_date="invalid-date",
            end_date="2024-01-31"
        )
        
        assert isinstance(result, AggregatedCosts)
