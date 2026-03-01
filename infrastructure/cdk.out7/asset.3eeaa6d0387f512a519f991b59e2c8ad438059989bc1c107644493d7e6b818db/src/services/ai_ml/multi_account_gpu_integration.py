"""
Multi-Account GPU Cost Integration

Integrates GPU cost tracking with Phase 5 multi-account infrastructure.
Supports cross-account GPU cost collection, aggregation, and organization-wide reporting.
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import List, Dict, Optional
from dataclasses import dataclass

from ..multi_account.cross_account_role_manager import CrossAccountRoleManager, Credentials
from ..multi_account.models import AccountCostData, AggregatedCosts
from .gpu_cost_tracker import GPUCostTracker, GPUCostData
from .workload_classifier import WorkloadClassifier
from .error_handler import retry_with_exponential_backoff, handle_cost_explorer_error


logger = logging.getLogger(__name__)


@dataclass
class MultiAccountGPUCosts:
    """GPU costs aggregated across multiple accounts"""
    org_id: str
    start_date: date
    end_date: date
    total_gpu_cost: Decimal
    account_count: int
    costs_by_account: Dict[str, Decimal]
    costs_by_workload_type: Dict[str, Decimal]  # training, inference, idle
    costs_by_instance_type: Dict[str, Decimal]  # p3.2xlarge, p4d.24xlarge, etc.
    gpu_hours_by_account: Dict[str, float]
    utilization_by_account: Dict[str, float]


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
        
        total_gpu_cost = Decimal("0")
        costs_by_account: Dict[str, Decimal] = {}
        costs_by_workload_type: Dict[str, Decimal] = {
            "training": Decimal("0"),
            "inference": Decimal("0"),
            "idle": Decimal("0")
        }
        costs_by_instance_type: Dict[str, Decimal] = {}
        gpu_hours_by_account: Dict[str, float] = {}
        utilization_by_account: Dict[str, float] = {}
        
        for account_id in account_ids:
            try:
                # Collect GPU costs for this account
                account_gpu_costs = self._collect_account_gpu_costs(
                    account_id=account_id,
                    start_date=start_date,
                    end_date=end_date,
                    role_name=role_name,
                    external_id=external_id
                )
                
                # Aggregate by account
                account_total = sum(
                    Decimal(str(cost.cost)) for cost in account_gpu_costs
                )
                costs_by_account[account_id] = account_total
                total_gpu_cost += account_total
                
                # Aggregate by workload type
                for cost_data in account_gpu_costs:
                    workload_type = cost_data.workload_type
                    costs_by_workload_type[workload_type] += Decimal(str(cost_data.cost))
                    
                    # Aggregate by instance type
                    instance_type = cost_data.instance_type
                    if instance_type not in costs_by_instance_type:
                        costs_by_instance_type[instance_type] = Decimal("0")
                    costs_by_instance_type[instance_type] += Decimal(str(cost_data.cost))
                
                # Calculate GPU hours and utilization for account
                total_gpu_hours = sum(cost.gpu_hours for cost in account_gpu_costs)
                avg_utilization = (
                    sum(cost.utilization for cost in account_gpu_costs) / len(account_gpu_costs)
                    if account_gpu_costs else 0.0
                )
                
                gpu_hours_by_account[account_id] = total_gpu_hours
                utilization_by_account[account_id] = avg_utilization
                
                logger.info(
                    f"Collected GPU costs for account {account_id}: "
                    f"${account_total}, {total_gpu_hours} GPU hours"
                )
                
            except Exception as e:
                logger.error(f"Failed to collect GPU costs for account {account_id}: {e}")
                # Continue with other accounts
                costs_by_account[account_id] = Decimal("0")
                gpu_hours_by_account[account_id] = 0.0
                utilization_by_account[account_id] = 0.0
        
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
            utilization_by_account=utilization_by_account
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
                start_date=start_date,
                end_date=end_date,
                boto3_session=session
            )
            
            return gpu_costs
            
        except Exception as e:
            logger.error(f"Error collecting GPU costs for account {account_id}: {e}")
            return []
    
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
            multi_account_costs.costs_by_account.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        # Calculate percentages
        total_cost = multi_account_costs.total_gpu_cost
        result = []
        
        for account_id, cost in sorted_accounts:
            percentage = float(cost / total_cost * 100) if total_cost > 0 else 0.0
            gpu_hours = multi_account_costs.gpu_hours_by_account.get(account_id, 0.0)
            utilization = multi_account_costs.utilization_by_account.get(account_id, 0.0)
            
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
        
        # Calculate organization-wide metrics
        total_gpu_hours = sum(multi_account_costs.gpu_hours_by_account.values())
        avg_utilization = (
            sum(multi_account_costs.utilization_by_account.values()) / len(account_ids)
            if account_ids else 0.0
        )
        
        # Calculate idle GPU cost percentage
        idle_cost = multi_account_costs.costs_by_workload_type.get("idle", Decimal("0"))
        idle_percentage = (
            float(idle_cost / multi_account_costs.total_gpu_cost * 100)
            if multi_account_costs.total_gpu_cost > 0 else 0.0
        )
        
        return {
            "total_gpu_hours": total_gpu_hours,
            "avg_utilization": avg_utilization,
            "idle_cost_percentage": idle_percentage,
            "total_gpu_cost": float(multi_account_costs.total_gpu_cost)
        }
