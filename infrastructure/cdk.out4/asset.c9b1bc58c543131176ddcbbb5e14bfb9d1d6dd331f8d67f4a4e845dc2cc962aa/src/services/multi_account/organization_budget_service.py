"""
Organization Budget Service

Manages organization-wide budgets with hierarchical rollup.
Validates Requirements 11.1-11.7 and 12.1-12.7.
"""
import logging
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime
import uuid

from .repositories import BudgetRepository, AccountRepository, MultiAccountCostRepository
from .models import EntityType

logger = logging.getLogger(__name__)


class OrganizationBudgetService:
    """Service for managing organization-wide budgets"""

    def __init__(
        self,
        budget_repository: BudgetRepository,
        account_repository: AccountRepository,
        cost_repository: MultiAccountCostRepository
    ):
        """
        Initialize the Organization Budget Service
        
        Args:
            budget_repository: Repository for budget data
            account_repository: Repository for account data
            cost_repository: Repository for cost data
        """
        self.budget_repo = budget_repository
        self.account_repo = account_repository
        self.cost_repo = cost_repository

    def create_organization_budget(
        self,
        org_id: str,
        budget_amount: Decimal,
        period: str = "MONTHLY"
    ) -> str:
        """
        Create budget at organization level
        
        Args:
            org_id: Organization ID
            budget_amount: Budget amount
            period: Budget period (MONTHLY, QUARTERLY, ANNUAL)
            
        Returns:
            Budget ID
            
        Validates: Requirements 11.1, 11.4
        """
        budget_id = f"budget-{uuid.uuid4()}"
        
        self.budget_repo.save(
            budget_id=budget_id,
            entity_id=org_id,
            entity_type=EntityType.ORGANIZATION.value,
            budget_amount=budget_amount,
            period=period
        )
        
        logger.info(f"Created organization budget: {budget_id} for {org_id}")
        return budget_id

    def create_ou_budget(
        self,
        ou_id: str,
        budget_amount: Decimal,
        period: str = "MONTHLY"
    ) -> str:
        """
        Create budget at OU level
        
        Args:
            ou_id: Organizational Unit ID
            budget_amount: Budget amount
            period: Budget period
            
        Returns:
            Budget ID
            
        Validates: Requirements 11.2, 11.5
        """
        budget_id = f"budget-{uuid.uuid4()}"
        
        self.budget_repo.save(
            budget_id=budget_id,
            entity_id=ou_id,
            entity_type=EntityType.OU.value,
            budget_amount=budget_amount,
            period=period
        )
        
        logger.info(f"Created OU budget: {budget_id} for {ou_id}")
        return budget_id

    def create_account_budget(
        self,
        account_id: str,
        budget_amount: Decimal,
        period: str = "MONTHLY"
    ) -> str:
        """
        Create budget at account level
        
        Args:
            account_id: Account ID
            budget_amount: Budget amount
            period: Budget period
            
        Returns:
            Budget ID
            
        Validates: Requirements 11.3
        """
        budget_id = f"budget-{uuid.uuid4()}"
        
        self.budget_repo.save(
            budget_id=budget_id,
            entity_id=account_id,
            entity_type=EntityType.ACCOUNT.value,
            budget_amount=budget_amount,
            period=period
        )
        
        logger.info(f"Created account budget: {budget_id} for {account_id}")
        return budget_id

    def calculate_ou_utilization(
        self,
        ou_id: str,
        account_ids: List[str],
        date: str
    ) -> Dict:
        """
        Calculate OU budget utilization by summing account costs
        
        Args:
            ou_id: Organizational Unit ID
            account_ids: List of account IDs in the OU
            date: Date in YYYY-MM-DD format
            
        Returns:
            Dict with utilization data
            
        Validates: Requirements 12.1, 12.3
        """
        # Get OU budget
        budgets = self.budget_repo.list_by_entity(ou_id, EntityType.OU.value)
        if not budgets:
            return {
                "ou_id": ou_id,
                "budget_amount": Decimal("0"),
                "current_spend": Decimal("0"),
                "utilization_percentage": 0.0,
                "status": "NO_BUDGET"
            }
        
        budget = budgets[0]
        budget_amount = budget["budget_amount"]
        
        # Sum costs from all accounts in OU
        total_spend = Decimal("0")
        for account_id in account_ids:
            cost_data = self.cost_repo.get(account_id, date)
            if cost_data:
                total_spend += cost_data.total_cost
        
        # Calculate utilization
        utilization = float(total_spend / budget_amount * 100) if budget_amount > 0 else 0.0
        
        return {
            "ou_id": ou_id,
            "budget_amount": budget_amount,
            "current_spend": total_spend,
            "utilization_percentage": utilization,
            "status": self._get_budget_status(utilization)
        }

    def calculate_org_utilization(
        self,
        org_id: str,
        date: str
    ) -> Dict:
        """
        Calculate organization budget utilization by summing all account costs
        
        Args:
            org_id: Organization ID
            date: Date in YYYY-MM-DD format
            
        Returns:
            Dict with utilization data
            
        Validates: Requirements 12.2, 12.4
        """
        # Get organization budget
        budgets = self.budget_repo.list_by_entity(org_id, EntityType.ORGANIZATION.value)
        if not budgets:
            return {
                "org_id": org_id,
                "budget_amount": Decimal("0"),
                "current_spend": Decimal("0"),
                "utilization_percentage": 0.0,
                "status": "NO_BUDGET"
            }
        
        budget = budgets[0]
        budget_amount = budget["budget_amount"]
        
        # Get all accounts in organization
        accounts = self.account_repo.list_by_organization(org_id)
        
        # Sum costs from all accounts
        total_spend = Decimal("0")
        for account in accounts:
            cost_data = self.cost_repo.get(account.id, date)
            if cost_data:
                total_spend += cost_data.total_cost
        
        # Calculate utilization
        utilization = float(total_spend / budget_amount * 100) if budget_amount > 0 else 0.0
        
        return {
            "org_id": org_id,
            "budget_amount": budget_amount,
            "current_spend": total_spend,
            "utilization_percentage": utilization,
            "status": self._get_budget_status(utilization)
        }

    def monitor_budget(self, budget_id: str, current_spend: Decimal) -> List[Dict]:
        """
        Monitor budget and generate alerts
        
        Args:
            budget_id: Budget ID
            current_spend: Current spending amount
            
        Returns:
            List of alerts (if any)
            
        Validates: Requirements 11.6, 11.7
        """
        budget = self.budget_repo.get(budget_id)
        if not budget:
            return []
        
        budget_amount = budget["budget_amount"]
        utilization = float(current_spend / budget_amount * 100) if budget_amount > 0 else 0.0
        
        alerts = []
        
        # 80% warning threshold
        if utilization >= 80 and utilization < 100:
            alerts.append({
                "level": "WARNING",
                "budget_id": budget_id,
                "utilization": utilization,
                "message": f"Budget at {utilization:.1f}% utilization (warning threshold: 80%)"
            })
        
        # 100% critical threshold
        if utilization >= 100:
            alerts.append({
                "level": "CRITICAL",
                "budget_id": budget_id,
                "utilization": utilization,
                "message": f"Budget exceeded at {utilization:.1f}% utilization"
            })
        
        return alerts

    def get_budget_hierarchy(self, org_id: str, date: str) -> Dict:
        """
        Get budget hierarchy visualization
        
        Args:
            org_id: Organization ID
            date: Date for cost calculation
            
        Returns:
            Budget hierarchy with utilization at all levels
            
        Validates: Requirements 12.5, 12.6
        """
        # Get organization utilization
        org_util = self.calculate_org_utilization(org_id, date)
        
        # Get all accounts
        accounts = self.account_repo.list_by_organization(org_id)
        
        # Get account budgets and utilization
        account_details = []
        for account in accounts:
            budgets = self.budget_repo.list_by_entity(account.id, EntityType.ACCOUNT.value)
            cost_data = self.cost_repo.get(account.id, date)
            
            if budgets:
                budget = budgets[0]
                current_spend = cost_data.total_cost if cost_data else Decimal("0")
                utilization = float(current_spend / budget["budget_amount"] * 100) if budget["budget_amount"] > 0 else 0.0
                
                account_details.append({
                    "account_id": account.id,
                    "account_name": account.name,
                    "budget_amount": budget["budget_amount"],
                    "current_spend": current_spend,
                    "utilization_percentage": utilization,
                    "status": self._get_budget_status(utilization)
                })
        
        return {
            "organization": org_util,
            "accounts": account_details
        }

    def _get_budget_status(self, utilization: float) -> str:
        """
        Get budget status based on utilization percentage
        
        Args:
            utilization: Utilization percentage
            
        Returns:
            Status string
        """
        if utilization >= 100:
            return "EXCEEDED"
        elif utilization >= 80:
            return "WARNING"
        else:
            return "OK"
