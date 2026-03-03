"""
Cross-Account AI Advisor Service

Extends Phase 4 AI advisor to work with multi-account data.
Provides organization-wide context and account-specific insights.
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal

from ..context_manager import ContextManager
from ...utils.types import CostContext, QueryIntent
from .models import AggregatedCosts, AllocationResult
from .repositories import (
    OrganizationRepository,
    AccountRepository,
    MultiAccountCostRepository
)
from .cost_aggregation_engine import CostAggregationEngine
from .cost_allocation_engine import CostAllocationEngine


logger = logging.getLogger(__name__)


class CrossAccountAdvisorService:
    """
    Extends AI advisor for multi-account organizations.
    
    Provides organization-wide context, account-specific insights,
    and cost allocation insights for AI advisor queries.
    """
    
    def __init__(
        self,
        context_manager: Optional[ContextManager] = None,
        org_repository: Optional[OrganizationRepository] = None,
        account_repository: Optional[AccountRepository] = None,
        cost_repository: Optional[MultiAccountCostRepository] = None,
        aggregation_engine: Optional[CostAggregationEngine] = None,
        allocation_engine: Optional[CostAllocationEngine] = None
    ):
        """
        Initialize Cross-Account Advisor Service.
        
        Args:
            context_manager: Phase 4 context manager
            org_repository: Organization repository
            account_repository: Account repository
            cost_repository: Multi-account cost repository
            aggregation_engine: Cost aggregation engine
            allocation_engine: Cost allocation engine
        """
        self.context_manager = context_manager or ContextManager()
        self.org_repository = org_repository or OrganizationRepository()
        self.account_repository = account_repository or AccountRepository()
        self.cost_repository = cost_repository or MultiAccountCostRepository()
        self.aggregation_engine = aggregation_engine or CostAggregationEngine()
        self.allocation_engine = allocation_engine or CostAllocationEngine()
        
        logger.info("CrossAccountAdvisorService initialized")
    
    def get_organization_context(
        self,
        org_id: str,
        intent: QueryIntent
    ) -> Dict[str, Any]:
        """
        Get organization-wide context for AI advisor.
        
        Provides context from all accounts in the organization,
        including aggregated costs, top spending accounts, and
        organization-level trends.
        
        Args:
            org_id: Organization ID
            intent: Parsed query intent
            
        Returns:
            Dictionary with organization-wide context
            
        Validates: Requirement 15.1
        """
        logger.info(f"Getting organization context for {org_id}")
        
        try:
            # Get all accounts in organization
            accounts = self.account_repository.list_by_organization(org_id)
            account_ids = [acc.id for acc in accounts]
            
            if not account_ids:
                logger.warning(f"No accounts found for organization {org_id}")
                return {
                    'organization_id': org_id,
                    'account_count': 0,
                    'error': 'No accounts found'
                }
            
            # Get date range from intent
            start_date, end_date = self._get_date_range(intent)
            
            # Aggregate organization costs
            aggregated = self.aggregation_engine.aggregate_organization_costs(
                org_id=org_id,
                account_ids=account_ids,
                start_date=start_date,
                end_date=end_date
            )
            
            # Get top spending accounts
            top_accounts = self.aggregation_engine.get_top_spending_accounts(
                org_id=org_id,
                account_ids=account_ids,
                start_date=start_date,
                end_date=end_date,
                limit=5
            )
            
            # Get cost allocation insights
            allocation_insights = self._get_organization_allocation_insights(
                org_id=org_id,
                account_ids=account_ids,
                start_date=start_date,
                end_date=end_date
            )
            
            context = {
                'organization_id': org_id,
                'account_count': len(account_ids),
                'time_period': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'total_cost': float(aggregated.total_cost),
                'costs_by_service': {
                    service: float(cost)
                    for service, cost in aggregated.costs_by_service.items()
                },
                'costs_by_account': {
                    account_id: float(cost)
                    for account_id, cost in aggregated.costs_by_account.items()
                },
                'top_spending_accounts': [
                    {
                        'account_id': acc.account_id,
                        'account_name': acc.account_name,
                        'total_cost': float(acc.total_cost),
                        'percentage': acc.percentage_of_total
                    }
                    for acc in top_accounts
                ],
                'allocation_insights': allocation_insights
            }
            
            logger.info(
                f"Retrieved organization context: ${aggregated.total_cost} "
                f"across {len(account_ids)} accounts"
            )
            
            return context
            
        except Exception as e:
            logger.error(f"Error getting organization context: {e}", exc_info=True)
            return {
                'organization_id': org_id,
                'error': str(e)
            }
    
    def get_account_context(
        self,
        account_id: str,
        intent: QueryIntent
    ) -> Dict[str, Any]:
        """
        Get account-specific context for AI advisor.
        
        Provides context from a specific account, including
        costs by service, allocation status, and trends.
        
        Args:
            account_id: Account ID
            intent: Parsed query intent
            
        Returns:
            Dictionary with account-specific context
            
        Validates: Requirement 15.2
        """
        logger.info(f"Getting account context for {account_id}")
        
        try:
            # Get account metadata
            account = self.account_repository.get(account_id)
            
            if not account:
                logger.warning(f"Account {account_id} not found")
                return {
                    'account_id': account_id,
                    'error': 'Account not found'
                }
            
            # Get date range from intent
            start_date, end_date = self._get_date_range(intent)
            
            # Get account costs
            cost_data = self.cost_repository.get(account_id, start_date)
            
            if not cost_data:
                logger.warning(f"No cost data found for account {account_id}")
                return {
                    'account_id': account_id,
                    'account_name': account.name,
                    'error': 'No cost data found'
                }
            
            # Get allocation insights for this account
            allocation_result = self.allocation_engine.allocate_by_tags(
                account_id=account_id,
                start_date=start_date,
                end_date=end_date
            )
            
            context = {
                'account_id': account_id,
                'account_name': account.name,
                'account_status': account.status,
                'time_period': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'total_cost': float(cost_data.total_cost),
                'costs_by_service': {
                    service: float(cost)
                    for service, cost in cost_data.costs_by_service.items()
                },
                'allocation': {
                    'total_cost': float(allocation_result.total_cost),
                    'allocated_cost': float(allocation_result.allocated_cost),
                    'unallocated_cost': float(allocation_result.unallocated_cost),
                    'allocation_percentage': allocation_result.allocation_percentage,
                    'allocations_by_category': {
                        category: float(cost)
                        for category, cost in allocation_result.allocations_by_category.items()
                    }
                }
            }
            
            logger.info(
                f"Retrieved account context: ${cost_data.total_cost} "
                f"for account {account_id}"
            )
            
            return context
            
        except Exception as e:
            logger.error(f"Error getting account context: {e}", exc_info=True)
            return {
                'account_id': account_id,
                'error': str(e)
            }
    
    def enhance_prompt_with_multi_account_context(
        self,
        base_prompt: str,
        org_id: Optional[str] = None,
        account_id: Optional[str] = None,
        intent: Optional[QueryIntent] = None
    ) -> str:
        """
        Enhance AI advisor prompt with multi-account context.
        
        Adds organization-wide or account-specific context to
        the base prompt for better AI responses.
        
        Args:
            base_prompt: Base prompt for AI advisor
            org_id: Optional organization ID
            account_id: Optional account ID
            intent: Optional query intent
            
        Returns:
            Enhanced prompt with multi-account context
            
        Validates: Requirement 15.5
        """
        logger.info("Enhancing prompt with multi-account context")
        
        if not intent:
            # Create default intent for last 30 days
            intent = QueryIntent(
                intent_type='cost_analysis',
                services=[],
                time_range=(
                    datetime.now() - timedelta(days=30),
                    datetime.now()
                ),
                accounts=[],
                entities={}
            )
        
        enhanced_prompt = base_prompt
        
        # Add organization context if provided
        if org_id:
            org_context = self.get_organization_context(org_id, intent)
            
            enhanced_prompt += "\n\n## Organization Context\n"
            enhanced_prompt += f"Organization ID: {org_context.get('organization_id')}\n"
            enhanced_prompt += f"Total Accounts: {org_context.get('account_count')}\n"
            enhanced_prompt += f"Total Cost: ${org_context.get('total_cost', 0):.2f}\n"
            
            if 'top_spending_accounts' in org_context:
                enhanced_prompt += "\nTop Spending Accounts:\n"
                for acc in org_context['top_spending_accounts'][:3]:
                    enhanced_prompt += (
                        f"- {acc['account_name']} ({acc['account_id']}): "
                        f"${acc['total_cost']:.2f} ({acc['percentage']:.1f}%)\n"
                    )
            
            if 'allocation_insights' in org_context:
                insights = org_context['allocation_insights']
                enhanced_prompt += (
                    f"\nCost Allocation: {insights.get('allocation_percentage', 0):.1f}% allocated, "
                    f"${insights.get('unallocated_cost', 0):.2f} unallocated\n"
                )
        
        # Add account context if provided
        elif account_id:
            account_context = self.get_account_context(account_id, intent)
            
            enhanced_prompt += "\n\n## Account Context\n"
            enhanced_prompt += f"Account: {account_context.get('account_name')} ({account_context.get('account_id')})\n"
            enhanced_prompt += f"Total Cost: ${account_context.get('total_cost', 0):.2f}\n"
            
            if 'allocation' in account_context:
                alloc = account_context['allocation']
                enhanced_prompt += (
                    f"Allocation: {alloc.get('allocation_percentage', 0):.1f}% allocated, "
                    f"${alloc.get('unallocated_cost', 0):.2f} unallocated\n"
                )
        
        logger.debug(f"Enhanced prompt length: {len(enhanced_prompt)} characters")
        
        return enhanced_prompt
    
    def get_cross_account_insights(
        self,
        org_id: str,
        intent: QueryIntent
    ) -> List[Dict[str, Any]]:
        """
        Generate cross-account cost insights.
        
        Analyzes cost patterns across accounts and provides
        recommendations for optimization.
        
        Args:
            org_id: Organization ID
            intent: Query intent
            
        Returns:
            List of insights
            
        Validates: Requirement 15.6, 15.7
        """
        logger.info(f"Generating cross-account insights for {org_id}")
        
        insights = []
        
        try:
            # Get organization context
            org_context = self.get_organization_context(org_id, intent)
            
            if 'error' in org_context:
                return insights
            
            # Insight 1: High unallocated costs
            if 'allocation_insights' in org_context:
                alloc = org_context['allocation_insights']
                if alloc.get('allocation_percentage', 100) < 70:
                    insights.append({
                        'type': 'allocation_warning',
                        'severity': 'medium',
                        'title': 'High Unallocated Costs',
                        'description': (
                            f"{100 - alloc.get('allocation_percentage', 0):.1f}% of costs "
                            f"(${alloc.get('unallocated_cost', 0):.2f}) are unallocated. "
                            "Consider improving resource tagging."
                        ),
                        'recommendation': 'Add Team, Project, or Environment tags to resources'
                    })
            
            # Insight 2: Account spending concentration
            top_accounts = org_context.get('top_spending_accounts', [])
            if top_accounts and len(top_accounts) > 0:
                top_percentage = sum(acc['percentage'] for acc in top_accounts[:3])
                if top_percentage > 80:
                    insights.append({
                        'type': 'concentration_warning',
                        'severity': 'low',
                        'title': 'Spending Concentrated in Few Accounts',
                        'description': (
                            f"Top 3 accounts represent {top_percentage:.1f}% of total spending. "
                            "Review these accounts for optimization opportunities."
                        ),
                        'recommendation': 'Focus cost optimization efforts on top spending accounts'
                    })
            
            # Insight 3: Service cost distribution
            costs_by_service = org_context.get('costs_by_service', {})
            if costs_by_service:
                total_cost = org_context.get('total_cost', 0)
                top_service = max(costs_by_service.items(), key=lambda x: x[1])
                service_percentage = (top_service[1] / total_cost * 100) if total_cost > 0 else 0
                
                if service_percentage > 50:
                    insights.append({
                        'type': 'service_concentration',
                        'severity': 'low',
                        'title': f'High {top_service[0]} Costs',
                        'description': (
                            f"{top_service[0]} represents {service_percentage:.1f}% "
                            f"(${top_service[1]:.2f}) of total costs."
                        ),
                        'recommendation': f'Review {top_service[0]} usage for optimization opportunities'
                    })
            
            logger.info(f"Generated {len(insights)} cross-account insights")
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}", exc_info=True)
        
        return insights
    
    def _get_organization_allocation_insights(
        self,
        org_id: str,
        account_ids: List[str],
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        Get cost allocation insights for organization.
        
        Args:
            org_id: Organization ID
            account_ids: List of account IDs
            start_date: Start date
            end_date: End date
            
        Returns:
            Dictionary with allocation insights
            
        Validates: Requirement 15.3
        """
        total_cost = Decimal("0")
        total_allocated = Decimal("0")
        total_unallocated = Decimal("0")
        
        team_costs: Dict[str, Decimal] = {}
        
        for account_id in account_ids:
            try:
                # Get allocation for this account
                result = self.allocation_engine.allocate_by_tags(
                    account_id=account_id,
                    start_date=start_date,
                    end_date=end_date
                )
                
                total_cost += result.total_cost
                total_allocated += result.allocated_cost
                total_unallocated += result.unallocated_cost
                
                # Aggregate team costs
                for category, cost in result.allocations_by_category.items():
                    if category.startswith('Team:'):
                        team_name = category.split(':', 1)[1]
                        team_costs[team_name] = team_costs.get(team_name, Decimal("0")) + cost
                
            except Exception as e:
                logger.warning(f"Error getting allocation for account {account_id}: {e}")
                continue
        
        allocation_percentage = float(
            (total_allocated / total_cost * 100) if total_cost > 0 else 0.0
        )
        
        return {
            'total_cost': float(total_cost),
            'allocated_cost': float(total_allocated),
            'unallocated_cost': float(total_unallocated),
            'allocation_percentage': allocation_percentage,
            'team_costs': {
                team: float(cost)
                for team, cost in team_costs.items()
            }
        }
    
    def _get_date_range(self, intent: QueryIntent) -> tuple[str, str]:
        """
        Get date range from query intent.
        
        Args:
            intent: Query intent
            
        Returns:
            Tuple of (start_date, end_date) in YYYY-MM-DD format
        """
        if intent.time_range:
            start_date = intent.time_range[0].strftime('%Y-%m-%d')
            end_date = intent.time_range[1].strftime('%Y-%m-%d')
        else:
            # Default to last 30 days
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        return start_date, end_date
