"""
Cost Aggregation Engine

Aggregates cost data across multiple accounts, OUs, and organizations.
Implements caching for performance optimization.
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional
from dataclasses import dataclass

from .models import AggregatedCosts, AccountSpending
from .repositories import MultiAccountCostRepository, AccountRepository, OrganizationRepository
from .cloudwatch_metrics import get_metrics_service


logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry for aggregated costs"""
    data: AggregatedCosts
    timestamp: datetime
    ttl_seconds: int = 3600  # 1 hour


class CostAggregationEngine:
    """
    Aggregates cost data across multiple accounts.
    
    Provides organization-level, OU-level, and service-level aggregations
    with caching for performance optimization.
    """
    
    def __init__(
        self,
        cost_repository: Optional[MultiAccountCostRepository] = None,
        account_repository: Optional[AccountRepository] = None,
        org_repository: Optional[OrganizationRepository] = None,
        cache_ttl_seconds: int = 3600
    ):
        """
        Initialize the Cost Aggregation Engine.
        
        Args:
            cost_repository: Repository for cost data
            account_repository: Repository for account metadata
            org_repository: Repository for organization data
            cache_ttl_seconds: Cache TTL in seconds (default: 1 hour)
        """
        self.cost_repository = cost_repository or MultiAccountCostRepository()
        self.account_repository = account_repository or AccountRepository()
        self.org_repository = org_repository or OrganizationRepository()
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: Dict[str, CacheEntry] = {}
    
    def aggregate_organization_costs(
        self,
        org_id: str,
        account_ids: List[str],
        start_date: str,
        end_date: str,
        use_cache: bool = True
    ) -> AggregatedCosts:
        """
        Aggregate costs for entire organization.
        
        Args:
            org_id: Organization ID
            account_ids: List of account IDs in organization
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            use_cache: Whether to use cached results
            
        Returns:
            AggregatedCosts with organization-level aggregation
        """
        logger.info(
            f"Aggregating costs for organization {org_id} "
            f"from {start_date} to {end_date}"
        )
        
        # Check cache
        cache_key = f"org:{org_id}:{start_date}:{end_date}"
        if use_cache:
            cached = self._get_from_cache(cache_key)
            if cached:
                logger.info(f"Returning cached aggregation for {cache_key}")
                return cached
        
        # Aggregate costs from all accounts
        total_cost = Decimal("0")
        costs_by_account: Dict[str, Decimal] = {}
        costs_by_service: Dict[str, Decimal] = {}
        costs_by_day: Dict[str, Decimal] = {}
        
        for account_id in account_ids:
            # Get service costs
            account_costs = self._get_account_costs(account_id, start_date, end_date)
            
            if not account_costs:
                logger.warning(f"No cost data found for account {account_id}")
                continue
            
            # Aggregate by account
            account_total = sum(account_costs.values(), Decimal("0"))
            costs_by_account[account_id] = account_total
            total_cost += account_total
            
            # Aggregate by service
            for service, cost in account_costs.items():
                costs_by_service[service] = costs_by_service.get(service, Decimal("0")) + cost
            
            # Get daily costs separately
            daily_costs = self._get_account_daily_costs(account_id, start_date, end_date)
            for day, cost in daily_costs.items():
                costs_by_day[day] = costs_by_day.get(day, Decimal("0")) + cost
        
        aggregated = AggregatedCosts(
            entity_id=org_id,
            entity_type="ORGANIZATION",
            start_date=start_date,
            end_date=end_date,
            total_cost=total_cost,
            account_count=len(account_ids),
            costs_by_account=costs_by_account,
            costs_by_service=costs_by_service,
            costs_by_day=costs_by_day
        )
        
        # Store in cache
        self._put_in_cache(cache_key, aggregated)
        
        logger.info(
            f"Aggregated costs for organization {org_id}: "
            f"${total_cost} across {len(account_ids)} accounts"
        )
        
        return aggregated

    
    def aggregate_ou_costs(
        self,
        ou_id: str,
        account_ids: List[str],
        start_date: str,
        end_date: str,
        use_cache: bool = True
    ) -> AggregatedCosts:
        """
        Aggregate costs for organizational unit.
        
        Args:
            ou_id: Organizational Unit ID
            account_ids: List of account IDs in OU
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            use_cache: Whether to use cached results
            
        Returns:
            AggregatedCosts with OU-level aggregation
        """
        logger.info(
            f"Aggregating costs for OU {ou_id} "
            f"from {start_date} to {end_date}"
        )
        
        # Check cache
        cache_key = f"ou:{ou_id}:{start_date}:{end_date}"
        if use_cache:
            cached = self._get_from_cache(cache_key)
            if cached:
                logger.info(f"Returning cached aggregation for {cache_key}")
                return cached
        
        # Aggregate costs from all accounts in OU
        total_cost = Decimal("0")
        costs_by_account: Dict[str, Decimal] = {}
        costs_by_service: Dict[str, Decimal] = {}
        costs_by_day: Dict[str, Decimal] = {}
        
        for account_id in account_ids:
            # Get service costs
            account_costs = self._get_account_costs(account_id, start_date, end_date)
            
            if not account_costs:
                logger.warning(f"No cost data found for account {account_id}")
                continue
            
            # Aggregate by account
            account_total = sum(account_costs.values(), Decimal("0"))
            costs_by_account[account_id] = account_total
            total_cost += account_total
            
            # Aggregate by service
            for service, cost in account_costs.items():
                costs_by_service[service] = costs_by_service.get(service, Decimal("0")) + cost
            
            # Get daily costs separately
            daily_costs = self._get_account_daily_costs(account_id, start_date, end_date)
            for day, cost in daily_costs.items():
                costs_by_day[day] = costs_by_day.get(day, Decimal("0")) + cost
        
        aggregated = AggregatedCosts(
            entity_id=ou_id,
            entity_type="OU",
            start_date=start_date,
            end_date=end_date,
            total_cost=total_cost,
            account_count=len(account_ids),
            costs_by_account=costs_by_account,
            costs_by_service=costs_by_service,
            costs_by_day=costs_by_day
        )
        
        # Store in cache
        self._put_in_cache(cache_key, aggregated)
        
        logger.info(
            f"Aggregated costs for OU {ou_id}: "
            f"${total_cost} across {len(account_ids)} accounts"
        )
        
        return aggregated
    
    def aggregate_by_service(
        self,
        account_ids: List[str],
        start_date: str,
        end_date: str
    ) -> Dict[str, Decimal]:
        """
        Aggregate costs by service across accounts.
        
        Args:
            account_ids: List of account IDs
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Dictionary mapping service name to total cost
        """
        logger.info(
            f"Aggregating costs by service for {len(account_ids)} accounts "
            f"from {start_date} to {end_date}"
        )
        
        costs_by_service: Dict[str, Decimal] = {}
        
        for account_id in account_ids:
            account_costs = self._get_account_costs(account_id, start_date, end_date)
            
            if not account_costs:
                continue
            
            # Aggregate service costs
            for service, cost in account_costs.items():
                costs_by_service[service] = costs_by_service.get(service, Decimal("0")) + cost
        
        logger.info(f"Aggregated costs for {len(costs_by_service)} services")
        return costs_by_service
    
    def get_top_spending_accounts(
        self,
        org_id: str,
        account_ids: List[str],
        start_date: str,
        end_date: str,
        limit: int = 5
    ) -> List[AccountSpending]:
        """
        Get top spending accounts in organization.
        
        Args:
            org_id: Organization ID
            account_ids: List of account IDs
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            limit: Number of top accounts to return
            
        Returns:
            List of AccountSpending sorted by total cost (descending)
        """
        logger.info(
            f"Getting top {limit} spending accounts for organization {org_id}"
        )
        
        # Calculate total cost per account
        account_totals: List[tuple] = []
        total_org_cost = Decimal("0")
        
        for account_id in account_ids:
            account_costs = self._get_account_costs(account_id, start_date, end_date)
            
            if not account_costs:
                continue
            
            account_total = sum(account_costs.values(), Decimal("0"))
            total_org_cost += account_total
            
            # Get account name
            account_name = self._get_account_name(account_id)
            
            account_totals.append((account_id, account_name, account_total))
        
        # Sort by cost (descending) and take top N
        account_totals.sort(key=lambda x: x[2], reverse=True)
        top_accounts = account_totals[:limit]
        
        # Calculate percentages
        result = []
        for account_id, account_name, total_cost in top_accounts:
            percentage = float(total_cost / total_org_cost * 100) if total_org_cost > 0 else 0.0
            result.append(AccountSpending(
                account_id=account_id,
                account_name=account_name,
                total_cost=total_cost,
                percentage_of_total=percentage
            ))
        
        logger.info(f"Found {len(result)} top spending accounts")
        return result
    
    def _get_account_costs(
        self,
        account_id: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Decimal]:
        """
        Get cost data for a single account.
        
        Args:
            account_id: Account ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Dictionary with service costs (not daily costs to avoid double counting)
        """
        try:
            cost_data = self.cost_repository.get_cost_data(account_id, start_date)
            
            if not cost_data:
                return {}
            
            # Return only service costs (daily costs are derived from service costs)
            all_costs = {}
            
            # Add service costs
            if 'costs_by_service' in cost_data:
                for service, cost in cost_data['costs_by_service'].items():
                    all_costs[service] = Decimal(str(cost))
            
            return all_costs
            
        except Exception as e:
            logger.error(f"Error getting costs for account {account_id}: {e}")
            return {}
    
    def _get_account_daily_costs(
        self,
        account_id: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Decimal]:
        """
        Get daily cost data for a single account.
        
        Args:
            account_id: Account ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Dictionary mapping date to cost
        """
        try:
            cost_data = self.cost_repository.get_cost_data(account_id, start_date)
            
            if not cost_data:
                return {}
            
            daily_costs = {}
            
            # Add daily costs
            if 'costs_by_day' in cost_data:
                for day, cost in cost_data['costs_by_day'].items():
                    daily_costs[day] = Decimal(str(cost))
            
            return daily_costs
            
        except Exception as e:
            logger.error(f"Error getting daily costs for account {account_id}: {e}")
            return {}
    
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
    
    def _get_from_cache(self, cache_key: str) -> Optional[AggregatedCosts]:
        """
        Get aggregated costs from cache if valid.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached AggregatedCosts or None if not found/expired
        """
        metrics_service = get_metrics_service()
        
        if cache_key not in self._cache:
            # Cache miss
            metrics_service.record_cache_hit_rate(0, 1, 'CostAggregation')
            return None
        
        entry = self._cache[cache_key]
        age_seconds = (datetime.utcnow() - entry.timestamp).total_seconds()
        
        if age_seconds > entry.ttl_seconds:
            # Cache expired
            del self._cache[cache_key]
            metrics_service.record_cache_hit_rate(0, 1, 'CostAggregation')
            return None
        
        # Cache hit
        metrics_service.record_cache_hit_rate(1, 1, 'CostAggregation')
        return entry.data
    
    def _put_in_cache(self, cache_key: str, data: AggregatedCosts) -> None:
        """
        Store aggregated costs in cache.
        
        Args:
            cache_key: Cache key
            data: Aggregated costs to cache
        """
        self._cache[cache_key] = CacheEntry(
            data=data,
            timestamp=datetime.utcnow(),
            ttl_seconds=self.cache_ttl_seconds
        )
    
    def clear_cache(self) -> None:
        """Clear all cached aggregations."""
        self._cache.clear()
        logger.info("Cache cleared")
