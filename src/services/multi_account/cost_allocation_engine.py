"""
Cost Allocation Engine

Allocates costs based on resource tags and custom allocation rules.
Tracks allocated vs unallocated costs.
"""
import logging
from decimal import Decimal
from typing import List, Dict, Optional
from dataclasses import dataclass

from .models import AllocationRule, AllocationResult, AccountCostData
from .repositories import MultiAccountCostRepository, AllocationRuleRepository
from .cloudwatch_metrics import get_metrics_service


logger = logging.getLogger(__name__)


class CostAllocationEngine:
    """
    Allocates costs based on tags and custom rules.
    
    Supports tag-based allocation, rule application, and unallocated cost tracking.
    """
    
    def __init__(
        self,
        cost_repository: Optional[MultiAccountCostRepository] = None,
        rule_repository: Optional[AllocationRuleRepository] = None
    ):
        """
        Initialize the Cost Allocation Engine.
        
        Args:
            cost_repository: Repository for cost data
            rule_repository: Repository for allocation rules
        """
        self.cost_repository = cost_repository or MultiAccountCostRepository()
        self.rule_repository = rule_repository or AllocationRuleRepository()
    
    def allocate_by_tags(self, account_id, start_date, end_date, tag_keys=None):
        """Allocate one tag dimension across stored daily records without double counting."""
        from datetime import date, timedelta
        from .report_data import AllocationDataUnavailable
        keys = tag_keys or ['Team']
        if len(keys) != 1 or keys[0] not in ('Team', 'Project', 'Environment'):
            raise ValueError('Select one supported tag dimension to avoid overlapping allocation totals')
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
        if end < start or (end - start).days > 365:
            raise ValueError('Select an ordered period of at most 366 days')
        total_cost, allocated_cost, categories = Decimal('0'), Decimal('0'), {}
        day = start
        while day <= end:
            data = self.cost_repository.get_cost_data(account_id, day.isoformat())
            if data is None or getattr(data, 'costs_by_tag_service', None) is None:
                raise AllocationDataUnavailable('Daily tag/service allocation data is unavailable')
            total_cost += data.total_cost
            for category, services in data.costs_by_tag_service.items():
                if category.startswith(keys[0] + ':'):
                    amount = sum(services.values(), Decimal('0'))
                    categories[category] = categories.get(category, Decimal('0')) + amount
                    allocated_cost += amount
            day += timedelta(days=1)
        return AllocationResult(total_cost=total_cost, allocated_cost=allocated_cost,
            unallocated_cost=total_cost - allocated_cost,
            allocation_percentage=float(allocated_cost / total_cost * 100) if total_cost else 0.0,
            allocations_by_category=categories)

    def apply_allocation_rules(
        self,
        costs: AccountCostData,
        rules: List[AllocationRule]
    ) -> AllocationResult:
        """
        Apply custom allocation rules to cost data.
        
        Rules are applied in priority order (highest priority first).
        Only the highest-priority matching rule is applied to each cost item.
        
        Args:
            costs: Account cost data
            rules: List of allocation rules
            
        Returns:
            AllocationResult with allocated and unallocated costs
            
        Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
        """
        logger.info(
            f"Applying {len(rules)} allocation rules to account {costs.account_id}"
        )
        
        # Sort rules by priority (highest first)
        sorted_rules = sorted(rules, key=lambda r: r.priority, reverse=True)
        
        total_cost = costs.total_cost
        allocations_by_category: Dict[str, Decimal] = {}
        allocated_services: set = set()
        
        # Apply rules to each service
        for service, cost in costs.costs_by_service.items():
            # Find first matching rule (highest priority)
            for rule in sorted_rules:
                if self._rule_matches(rule, service, costs):
                    # Apply this rule
                    target = rule.allocation_target
                    allocations_by_category[target] = allocations_by_category.get(
                        target, Decimal("0")
                    ) + cost
                    allocated_services.add(service)
                    logger.debug(
                        f"Applied rule '{rule.name}' (priority {rule.priority}) "
                        f"to {service}: ${cost} -> {target}"
                    )
                    break  # Only apply highest-priority matching rule
        
        # Calculate allocated and unallocated costs
        allocated_cost = sum(allocations_by_category.values(), Decimal("0"))
        unallocated_cost = total_cost - allocated_cost
        
        # Calculate allocation percentage
        allocation_percentage = float(
            (allocated_cost / total_cost * 100) if total_cost > 0 else 0.0
        )
        
        result = AllocationResult(
            total_cost=total_cost,
            allocated_cost=allocated_cost,
            unallocated_cost=unallocated_cost,
            allocation_percentage=allocation_percentage,
            allocations_by_category=allocations_by_category
        )
        
        logger.info(
            f"Applied rules: allocated ${allocated_cost} ({allocation_percentage:.1f}%) "
            f"of ${total_cost}, unallocated: ${unallocated_cost}"
        )
        
        return result
    
    def calculate_unallocated_costs(
        self,
        account_id: str,
        start_date: str,
        end_date: str,
        tag_keys: Optional[List[str]] = None
    ) -> Decimal:
        """
        Calculate costs that cannot be allocated.
        
        Args:
            account_id: Account ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            tag_keys: List of tag keys to use for allocation
            
        Returns:
            Unallocated cost amount
            
        Validates: Requirements 7.1, 7.2, 7.3
        """
        logger.info(
            f"Calculating unallocated costs for account {account_id}"
        )
        
        # Get allocation result
        result = self.allocate_by_tags(account_id, start_date, end_date, tag_keys)
        
        # Record unallocated percentage metric
        metrics_service = get_metrics_service()
        metrics_service.record_unallocated_percentage(
            float(result.unallocated_cost),
            float(result.total_cost),
            account_id  # Using account_id as organization identifier
        )
        
        logger.info(
            f"Unallocated costs for account {account_id}: ${result.unallocated_cost}"
        )
        
        return result.unallocated_cost
    
    def get_allocation_by_team(
        self,
        org_id: str,
        account_ids: List[str],
        start_date: str,
        end_date: str
    ) -> Dict[str, Decimal]:
        """
        Get costs allocated by team across multiple accounts.
        
        Args:
            org_id: Organization ID
            account_ids: List of account IDs
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Dictionary mapping team name to total allocated cost
            
        Validates: Requirements 6.2, 6.7
        """
        logger.info(
            f"Getting team allocations for organization {org_id} "
            f"across {len(account_ids)} accounts"
        )
        
        team_costs: Dict[str, Decimal] = {}
        
        # Aggregate team costs across all accounts
        for account_id in account_ids:
            result = self.allocate_by_tags(
                account_id,
                start_date,
                end_date,
                tag_keys=['Team']
            )
            
            # Extract team allocations
            for category, cost in result.allocations_by_category.items():
                if category.startswith('Team:'):
                    team_name = category.split(':', 1)[1]
                    team_costs[team_name] = team_costs.get(team_name, Decimal("0")) + cost
        
        logger.info(
            f"Found allocations for {len(team_costs)} teams "
            f"across {len(account_ids)} accounts"
        )
        
        return team_costs
    
    def _rule_matches(
        self,
        rule: AllocationRule,
        service: str,
        costs: AccountCostData
    ) -> bool:
        """
        Check if an allocation rule matches a service.
        
        Args:
            rule: Allocation rule
            service: Service name
            costs: Account cost data
            
        Returns:
            True if rule matches, False otherwise
        """
        # TAG_BASED rules
        if rule.rule_type == "TAG_BASED":
            # Check if service has required tags
            if 'tag_key' in rule.conditions and 'tag_value' in rule.conditions:
                tag_key = rule.conditions['tag_key']
                tag_value = rule.conditions['tag_value']
                
                # Check if cost data has this tag
                if hasattr(costs, 'costs_by_tag') and costs.costs_by_tag:
                    tag_string = f"{tag_key}:{tag_value}"
                    return tag_string in costs.costs_by_tag
            
            return False
        
        # PERCENTAGE rules (match all services)
        elif rule.rule_type == "PERCENTAGE":
            return True
        
        # FIXED rules (match specific services)
        elif rule.rule_type == "FIXED":
            if 'service' in rule.conditions:
                return service == rule.conditions['service']
            return False
        
        # Unknown rule type
        return False
