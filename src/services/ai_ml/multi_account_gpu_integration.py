"""
Multi-Account GPU Cost Integration

Integrates GPU cost tracking with Phase 5 multi-account infrastructure.
Supports cross-account GPU cost collection, aggregation, and organization-wide reporting.
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from ..multi_account.cross_account_role_manager import CrossAccountRoleManager, Credentials
from ..multi_account.models import AccountCostData, AggregatedCosts
from .gpu_cost_tracker import GPUCostTracker, GPUCostData, GPUCostDataUnavailable
from .workload_classifier import WorkloadClassifier
from .error_handler import retry_with_exponential_backoff, handle_cost_explorer_error


logger = logging.getLogger(__name__)


@dataclass
class MultiAccountGPUCosts:
    """GPU costs aggregated across multiple accounts"""
    org_id: str
    start_date: date
    end_date: date
    total_gpu_cost: Optional[Decimal]
    account_count: int
    costs_by_account: Dict[str, Optional[Decimal]]
    costs_by_workload_type: Dict[str, Optional[Decimal]]  # training, inference, idle
    costs_by_instance_type: Dict[str, Decimal]  # p3.2xlarge, p4d.24xlarge, etc.
    gpu_hours_by_account: Dict[str, Optional[float]]
    utilization_by_account: Dict[str, Optional[float]]
    observed_partial_cost: Optional[Decimal] = None
    account_data_quality: Dict[str, Dict] = field(default_factory=dict)
    result_scope: str = 'observed_type_usage_costs_with_unavailable_attribution'


class MultiAccountGPUIntegration:
    """
    Integrates GPU cost tracking with multi-account infrastructure.
    
    Provides:
    - Cross-account GPU cost collection
    - Organization-wide GPU cost aggregation
    - Multi-account workload classification
    - Cross-account GPU utilization tracking
    """
    
    def __init__(
        self,
        role_manager: Optional[CrossAccountRoleManager] = None,
        gpu_cost_tracker: Optional[GPUCostTracker] = None,
        workload_classifier: Optional[WorkloadClassifier] = None
    ):
        """
        Initialize Multi-Account GPU Integration.
        
        Args:
            role_manager: Manager for cross-account role operations
            gpu_cost_tracker: GPU cost tracking service
            workload_classifier: Workload classification service
        """
        self.role_manager = role_manager or CrossAccountRoleManager()
        self.gpu_cost_tracker = gpu_cost_tracker
        self.workload_classifier = workload_classifier
    
    @retry_with_exponential_backoff(max_retries=3)
    def collect_gpu_costs_all_accounts(
        self,
        org_id: str,
        account_ids: List[str],
        start_date: date,
        end_date: date,
        role_name: str = "CostGuardCollectorRole",
        external_id: Optional[str] = None
    ) -> MultiAccountGPUCosts:
        """
        Collect GPU costs from all accounts in organization.
        
        Args:
            org_id: Organization ID
            account_ids: List of account IDs to collect from
            start_date: Start date for cost data
            end_date: End date for cost data
            role_name: Name of the cross-account role
            external_id: External ID for role assumption
            
        Returns:
            MultiAccountGPUCosts with aggregated GPU costs
        """
        logger.info(
            f"Collecting GPU costs for {len(account_ids)} accounts "
            f"from {start_date} to {end_date}"
        )
        
        account_ids = list(dict.fromkeys(account_ids))
        if not 1 <= len(account_ids) <= 25: raise ValueError('Select 1-25 accounts')
        total_gpu_cost = Decimal('0')
        costs_by_account, costs_by_instance_type, account_quality = {}, {}, {}
        costs_by_workload_type = {'training': None, 'inference': None, 'idle': None, 'unknown': None}
        gpu_hours_by_account, utilization_by_account = {}, {}
        observed_any = False
        for account_id in account_ids:
            gpu_hours_by_account[account_id], utilization_by_account[account_id] = None, None
            try:
                records = self._collect_account_gpu_costs(account_id, start_date, end_date, role_name, external_id)
                quality = dict(self.gpu_cost_tracker.last_observation_report)
                account_quality[account_id] = quality
                amount = sum((Decimal(str(record.cost)) for record in records), Decimal('0')) if records else None
                costs_by_account[account_id] = amount
                if amount is not None:
                    observed_any = True
                    total_gpu_cost += amount
                    costs_by_workload_type['unknown'] = (costs_by_workload_type['unknown'] or Decimal('0'))+amount
                for record in records:
                    costs_by_instance_type[record.instance_type] = costs_by_instance_type.get(record.instance_type, Decimal('0'))+Decimal(str(record.cost))
            except Exception as error:
                logger.warning('GPU account observation unavailable for %s: %s', account_id, type(error).__name__)
                costs_by_account[account_id] = None
                account_quality[account_id] = {'status': 'unavailable', 'complete_date_coverage': False}
        observed_partial_cost = total_gpu_cost if observed_any else None
        complete = all(costs_by_account.get(account) is not None and account_quality[account].get('complete_date_coverage') is True for account in account_ids)
        total_gpu_cost = total_gpu_cost if complete else None
        result = MultiAccountGPUCosts(
            org_id=org_id,
            start_date=start_date,
            end_date=end_date,
            total_gpu_cost=total_gpu_cost,
            account_count=len(account_ids),
            costs_by_account=costs_by_account,
            costs_by_workload_type=costs_by_workload_type,
            costs_by_instance_type=costs_by_instance_type,
            gpu_hours_by_account=gpu_hours_by_account,
            utilization_by_account=utilization_by_account,
            observed_partial_cost=observed_partial_cost, account_data_quality=account_quality
        )
        
        logger.info(
            f"Collected GPU costs for organization {org_id}: "
            f"${total_gpu_cost} across {len(account_ids)} accounts"
        )
        
        return result
    
    def _collect_account_gpu_costs(
        self,
        account_id: str,
        start_date: date,
        end_date: date,
        role_name: str,
        external_id: Optional[str]
    ) -> List[GPUCostData]:
        """
        Collect GPU costs from a single account using cross-account role.
        
        Args:
            account_id: AWS account ID
            start_date: Start date for cost data
            end_date: End date for cost data
            role_name: Name of the cross-account role
            external_id: External ID for role assumption
            
        Returns:
            List of GPUCostData for the account
        """
        try:
            # Assume cross-account role
            credentials = self.role_manager.assume_role(
                account_id=account_id,
                role_name=role_name,
                external_id=external_id
            )
            
            # Create boto3 session with assumed role credentials
            session = self.role_manager.create_boto3_session(credentials)
            
            # Collect GPU costs using the assumed role session
            gpu_costs = self.gpu_cost_tracker.collect_gpu_costs(
                start_date=start_date.date().isoformat() if isinstance(start_date, datetime) else start_date.isoformat(),
                end_date=end_date.date().isoformat() if isinstance(end_date, datetime) else end_date.isoformat(),
                boto3_session=session
            )
            
            return gpu_costs
            
        except Exception as e:
            logger.error(f"Error collecting GPU costs for account {account_id}: {e}")
            raise GPUCostDataUnavailable('Account GPU cost observations are unavailable') from e
    
    def aggregate_gpu_costs_by_workload(
        self,
        org_id: str,
        account_ids: List[str],
        start_date: date,
        end_date: date
    ) -> Dict[str, Decimal]:
        """
        Aggregate GPU costs by workload type across all accounts.
        
        Args:
            org_id: Organization ID
            account_ids: List of account IDs
            start_date: Start date for cost data
            end_date: End date for cost data
            
        Returns:
            Dictionary mapping workload type to total cost
        """
        logger.info(
            f"Aggregating GPU costs by workload for organization {org_id}"
        )
        
        multi_account_costs = self.collect_gpu_costs_all_accounts(
            org_id=org_id,
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date
        )
        
        return multi_account_costs.costs_by_workload_type
    
    def get_top_gpu_spending_accounts(
        self,
        org_id: str,
        account_ids: List[str],
        start_date: date,
        end_date: date,
        limit: int = 5
    ) -> List[Dict[str, any]]:
        """
        Get top GPU spending accounts in organization.
        
        Args:
            org_id: Organization ID
            account_ids: List of account IDs
            start_date: Start date for cost data
            end_date: End date for cost data
            limit: Number of top accounts to return
            
        Returns:
            List of account spending summaries sorted by GPU cost (descending)
        """
        logger.info(
            f"Getting top {limit} GPU spending accounts for organization {org_id}"
        )
        
        multi_account_costs = self.collect_gpu_costs_all_accounts(
            org_id=org_id,
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date
        )
        
        # Sort accounts by GPU cost
        sorted_accounts = sorted(
            [(account, cost) for account, cost in multi_account_costs.costs_by_account.items() if cost is not None],
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        # Calculate percentages
        total_cost = multi_account_costs.total_gpu_cost
        result = []
        
        for account_id, cost in sorted_accounts:
            percentage = float(cost / total_cost * 100) if total_cost is not None and total_cost > 0 else None
            gpu_hours = multi_account_costs.gpu_hours_by_account.get(account_id)
            utilization = multi_account_costs.utilization_by_account.get(account_id)
            
            result.append({
                "account_id": account_id,
                "gpu_cost": float(cost),
                "percentage_of_total": percentage,
                "gpu_hours": gpu_hours,
                "avg_utilization": utilization
            })
        
        return result
    
    def get_organization_gpu_utilization(
        self,
        org_id: str,
        account_ids: List[str],
        start_date: date,
        end_date: date
    ) -> Dict[str, float]:
        """
        Get GPU utilization metrics across organization.
        
        Args:
            org_id: Organization ID
            account_ids: List of account IDs
            start_date: Start date for metrics
            end_date: End date for metrics
            
        Returns:
            Dictionary with organization-wide GPU utilization metrics
        """
        logger.info(
            f"Getting GPU utilization for organization {org_id}"
        )
        
        multi_account_costs = self.collect_gpu_costs_all_accounts(
            org_id=org_id,
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date
        )
        
        return {'total_gpu_hours': None, 'avg_utilization': None, 'idle_cost_percentage': None,
                'total_gpu_cost': float(multi_account_costs.total_gpu_cost) if multi_account_costs.total_gpu_cost is not None else None,
                'observed_partial_cost': float(multi_account_costs.observed_partial_cost) if multi_account_costs.observed_partial_cost is not None else None,
                'account_data_quality': multi_account_costs.account_data_quality,
                'result_scope': 'billing_type_aggregates_without_device_utilization'}
