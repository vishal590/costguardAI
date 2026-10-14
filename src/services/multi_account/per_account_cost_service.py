"""
Per-Account Cost Service

Provides detailed cost breakdown and analysis for individual accounts.
Supports account comparison and anomaly detection.
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from .models import AccountCostData
from .repositories import MultiAccountCostRepository, AccountRepository


logger = logging.getLogger(__name__)


@dataclass
class AccountCostBreakdown:
    """Detailed cost breakdown for an account"""
    account_id: str
    account_name: str
    start_date: str
    end_date: str
    total_cost: Decimal
    costs_by_service: Dict[str, Decimal]
    costs_by_day: Dict[str, Decimal]
    top_services: List[Tuple[str, Decimal]]  # [(service, cost), ...]
    complete: bool = True
    missing_dates: List[str] = field(default_factory=list)


@dataclass
class AccountComparison:
    """Comparison between two accounts"""
    account1_id: str
    account1_name: str
    account1_cost: Decimal
    account2_id: str
    account2_name: str
    account2_cost: Decimal
    cost_difference: Decimal
    percentage_difference: float
    service_differences: Dict[str, Decimal]  # service -> cost_diff


@dataclass
class CostAnomaly:
    """Detected cost anomaly for an account"""
    account_id: str
    account_name: str
    current_period_cost: Decimal
    previous_period_cost: Decimal
    increase_amount: Decimal
    increase_percentage: float
    is_anomalous: bool
    threshold_percentage: float


class PerAccountCostService:
    """
    Provides per-account cost breakdown and analysis.
    
    Supports retrieving detailed cost data, comparing accounts,
    and detecting cost anomalies.
    """
    
    def __init__(
        self,
        cost_repository: Optional[MultiAccountCostRepository] = None,
        account_repository: Optional[AccountRepository] = None
    ):
        """
        Initialize the Per-Account Cost Service.
        
        Args:
            cost_repository: Repository for cost data
            account_repository: Repository for account metadata
        """
        self.cost_repository = cost_repository or MultiAccountCostRepository()
        self.account_repository = account_repository or AccountRepository()
    
    def get_account_costs(
        self,
        account_id: str,
        start_date: str,
        end_date: str,
        top_services_limit: int = 5
    ) -> AccountCostBreakdown:
        """
        Get detailed cost breakdown for a specific account.
        
        Args:
            account_id: Account ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            top_services_limit: Number of top services to include
            
        Returns:
            AccountCostBreakdown with detailed cost information
            
        Validates: Requirements 5.1, 5.2, 5.3
        """
        logger.info(
            f"Getting cost breakdown for account {account_id} "
            f"from {start_date} to {end_date}"
        )
        
        # Get account name
        account_name = self._get_account_name(account_id)
        
        # Get cost data
        cost_data = self.cost_repository.get_period(account_id, start_date, end_date)
        
        if not cost_data:
            logger.warning(f"No cost data found for account {account_id}")
            return AccountCostBreakdown(
                account_id=account_id,
                account_name=account_name,
                start_date=start_date,
                end_date=end_date,
                total_cost=Decimal("0"),
                costs_by_service={},
                costs_by_day={},
                top_services=[]
            )
        
        # Extract costs
        costs_by_service = {}
        if 'costs_by_service' in cost_data:
            for service, cost in cost_data['costs_by_service'].items():
                costs_by_service[service] = Decimal(str(cost))
        
        costs_by_day = {}
        if 'costs_by_day' in cost_data:
            for day, cost in cost_data['costs_by_day'].items():
                costs_by_day[day] = Decimal(str(cost))
        
        # Calculate total cost
        total_cost = sum(costs_by_service.values(), Decimal("0"))
        
        # Get top services
        top_services = sorted(
            costs_by_service.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_services_limit]
        
        breakdown = AccountCostBreakdown(
            account_id=account_id,
            account_name=account_name,
            start_date=start_date,
            end_date=end_date,
            total_cost=total_cost,
            costs_by_service=costs_by_service,
            costs_by_day=costs_by_day,
            top_services=top_services, complete=cost_data["complete"], missing_dates=cost_data["missing_dates"]
        )
        
        logger.info(
            f"Retrieved cost breakdown for account {account_id}: "
            f"${total_cost} across {len(costs_by_service)} services"
        )
        
        return breakdown
    
    def compare_accounts(
        self,
        account1_id: str,
        account2_id: str,
        start_date: str,
        end_date: str
    ) -> AccountComparison:
        """
        Compare costs between two accounts.
        
        Args:
            account1_id: First account ID
            account2_id: Second account ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            AccountComparison with cost differences
            
        Validates: Requirements 5.4, 5.7
        """
        logger.info(
            f"Comparing costs between accounts {account1_id} and {account2_id}"
        )
        
        # Get cost breakdowns for both accounts
        breakdown1 = self.get_account_costs(account1_id, start_date, end_date)
        breakdown2 = self.get_account_costs(account2_id, start_date, end_date)
        
        # Calculate differences
        cost_difference = breakdown1.total_cost - breakdown2.total_cost
        
        # Calculate percentage difference
        if breakdown2.total_cost > 0:
            percentage_difference = float(
                (cost_difference / breakdown2.total_cost) * 100
            )
        else:
            percentage_difference = 0.0 if breakdown1.total_cost == 0 else 100.0
        
        # Calculate service-level differences
        service_differences = {}
        all_services = set(breakdown1.costs_by_service.keys()) | set(breakdown2.costs_by_service.keys())
        
        for service in all_services:
            cost1 = breakdown1.costs_by_service.get(service, Decimal("0"))
            cost2 = breakdown2.costs_by_service.get(service, Decimal("0"))
            service_differences[service] = cost1 - cost2
        
        comparison = AccountComparison(
            account1_id=account1_id,
            account1_name=breakdown1.account_name,
            account1_cost=breakdown1.total_cost,
            account2_id=account2_id,
            account2_name=breakdown2.account_name,
            account2_cost=breakdown2.total_cost,
            cost_difference=cost_difference,
            percentage_difference=percentage_difference,
            service_differences=service_differences
        )
        
        logger.info(
            f"Account comparison: {account1_id} (${breakdown1.total_cost}) vs "
            f"{account2_id} (${breakdown2.total_cost}), "
            f"difference: ${cost_difference} ({percentage_difference:.1f}%)"
        )
        
        return comparison
    
    def detect_anomalies(
        self,
        account_id: str,
        current_start_date: str,
        current_end_date: str,
        threshold_percentage: float = 50.0
    ) -> CostAnomaly:
        """
        Detect cost anomalies for an account.
        
        Compares current period costs to previous period costs.
        Flags as anomalous if increase exceeds threshold.
        
        Args:
            account_id: Account ID
            current_start_date: Current period start date (YYYY-MM-DD)
            current_end_date: Current period end date (YYYY-MM-DD)
            threshold_percentage: Anomaly threshold (default: 50%)
            
        Returns:
            CostAnomaly with anomaly detection results
            
        Validates: Requirements 5.6
        """
        logger.info(
            f"Detecting cost anomalies for account {account_id} "
            f"with threshold {threshold_percentage}%"
        )
        
        # Get account name
        account_name = self._get_account_name(account_id)
        
        # Get current period costs
        current_breakdown = self.get_account_costs(
            account_id,
            current_start_date,
            current_end_date
        )
        
        # Calculate previous period dates
        current_start = datetime.strptime(current_start_date, "%Y-%m-%d")
        current_end = datetime.strptime(current_end_date, "%Y-%m-%d")
        period_length = (current_end - current_start).days + 1
        
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=period_length - 1)
        
        previous_start_date = previous_start.strftime("%Y-%m-%d")
        previous_end_date = previous_end.strftime("%Y-%m-%d")
        
        # Get previous period costs
        previous_breakdown = self.get_account_costs(
            account_id,
            previous_start_date,
            previous_end_date
        )
        
        # Calculate increase
        increase_amount = current_breakdown.total_cost - previous_breakdown.total_cost
        
        # Calculate percentage increase
        if previous_breakdown.total_cost > 0:
            increase_percentage = float(
                (increase_amount / previous_breakdown.total_cost) * 100
            )
        else:
            increase_percentage = 0.0 if current_breakdown.total_cost == 0 else 100.0
        
        # Determine if anomalous
        is_anomalous = increase_percentage > threshold_percentage
        
        anomaly = CostAnomaly(
            account_id=account_id,
            account_name=account_name,
            current_period_cost=current_breakdown.total_cost,
            previous_period_cost=previous_breakdown.total_cost,
            increase_amount=increase_amount,
            increase_percentage=increase_percentage,
            is_anomalous=is_anomalous,
            threshold_percentage=threshold_percentage
        )
        
        if is_anomalous:
            logger.warning(
                f"ANOMALY DETECTED for account {account_id}: "
                f"Cost increased by {increase_percentage:.1f}% "
                f"(${increase_amount}) from ${previous_breakdown.total_cost} "
                f"to ${current_breakdown.total_cost}"
            )
        else:
            logger.info(
                f"No anomaly detected for account {account_id}: "
                f"Cost change: {increase_percentage:.1f}%"
            )
        
        return anomaly
    
    def _get_account_name(self, account_id: str) -> str:
        """
        Get account name from repository.
        
        Args:
            account_id: Account ID
            
        Returns:
            Account name or account ID if not found
        """
        try:
            account = self.account_repository.get_account(account_id)
            return account.get('name', account_id) if account else account_id
        except Exception as e:
            logger.warning(f"Could not get name for account {account_id}: {e}")
            return account_id
