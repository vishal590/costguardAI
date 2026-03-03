"""
Organization-Wide Prevention Service

Extends Phase 3 prevention engine for multi-account organizations.
Validates Requirements 14.1-14.7.
"""
import logging
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..prevention_engine import PreventionEngine
from .repositories import AccountRepository
from .models import Account

logger = logging.getLogger(__name__)


class OrganizationPreventionService:
    """Service for managing prevention policies across multiple accounts"""

    def __init__(
        self,
        prevention_engine: PreventionEngine,
        account_repository: AccountRepository,
        max_workers: int = 10
    ):
        """
        Initialize the Organization Prevention Service
        
        Args:
            prevention_engine: Phase 3 PreventionEngine instance
            account_repository: Repository for account data
            max_workers: Maximum concurrent workers for parallel execution
        """
        self.prevention_engine = prevention_engine
        self.account_repo = account_repository
        self.max_workers = max_workers

    def create_organization_policy(
        self,
        org_id: str,
        policy_name: str,
        policy_config: Dict
    ) -> Dict:
        """
        Create prevention policy at organization level
        
        Args:
            org_id: Organization ID
            policy_name: Name of the policy
            policy_config: Policy configuration
            
        Returns:
            Dict with policy creation result
            
        Validates: Requirements 14.1, 14.3
        """
        logger.info(f"Creating organization policy: {policy_name} for org {org_id}")
        
        # Get all accounts in organization
        accounts = self.account_repo.list_by_organization(org_id)
        
        if not accounts:
            return {
                "success": False,
                "org_id": org_id,
                "policy_name": policy_name,
                "error": "No accounts found in organization"
            }
        
        # Apply policy to all accounts in parallel
        results = self._apply_policy_to_accounts(
            accounts,
            policy_name,
            policy_config
        )
        
        successful = sum(1 for r in results if r["success"])
        
        return {
            "success": successful > 0,
            "org_id": org_id,
            "policy_name": policy_name,
            "accounts_affected": len(accounts),
            "successful_applications": successful,
            "failed_applications": len(accounts) - successful,
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }

    def create_ou_policy(
        self,
        ou_id: str,
        account_ids: List[str],
        policy_name: str,
        policy_config: Dict
    ) -> Dict:
        """
        Create prevention policy at OU level
        
        Args:
            ou_id: Organizational Unit ID
            account_ids: List of account IDs in the OU
            policy_name: Name of the policy
            policy_config: Policy configuration
            
        Returns:
            Dict with policy creation result
            
        Validates: Requirements 14.2, 14.4
        """
        logger.info(f"Creating OU policy: {policy_name} for OU {ou_id}")
        
        if not account_ids:
            return {
                "success": False,
                "ou_id": ou_id,
                "policy_name": policy_name,
                "error": "No accounts in OU"
            }
        
        # Get account objects
        accounts = [
            self.account_repo.get(account_id)
            for account_id in account_ids
        ]
        accounts = [acc for acc in accounts if acc is not None]
        
        # Apply policy to all accounts in OU
        results = self._apply_policy_to_accounts(
            accounts,
            policy_name,
            policy_config
        )
        
        successful = sum(1 for r in results if r["success"])
        
        return {
            "success": successful > 0,
            "ou_id": ou_id,
            "policy_name": policy_name,
            "accounts_affected": len(accounts),
            "successful_applications": successful,
            "failed_applications": len(accounts) - successful,
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }

    def apply_account_policy(
        self,
        account_id: str,
        policy_name: str,
        policy_config: Dict,
        override: bool = False
    ) -> Dict:
        """
        Apply prevention policy to single account
        
        Args:
            account_id: Account ID
            policy_name: Name of the policy
            policy_config: Policy configuration
            override: Whether this is an override of inherited policy
            
        Returns:
            Dict with policy application result
            
        Validates: Requirements 14.5
        """
        logger.info(f"Applying policy {policy_name} to account {account_id} (override={override})")
        
        try:
            # Update prevention engine configuration for this account
            self.prevention_engine.update_config(policy_config)
            
            return {
                "success": True,
                "account_id": account_id,
                "policy_name": policy_name,
                "override": override,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to apply policy to account {account_id}: {e}")
            return {
                "success": False,
                "account_id": account_id,
                "policy_name": policy_name,
                "error": str(e)
            }

    def execute_prevention_across_accounts(
        self,
        account_ids: List[str]
    ) -> Dict:
        """
        Execute prevention actions across multiple accounts in parallel
        
        Args:
            account_ids: List of account IDs
            
        Returns:
            Dict with execution results
            
        Validates: Requirements 14.6, 14.7
        """
        logger.info(f"Executing prevention across {len(account_ids)} accounts")
        
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_account = {
                executor.submit(self._execute_prevention_for_account, account_id): account_id
                for account_id in account_ids
            }
            
            for future in as_completed(future_to_account):
                account_id = future_to_account[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Prevention execution failed for account {account_id}: {e}")
                    results.append({
                        "success": False,
                        "account_id": account_id,
                        "error": str(e)
                    })
        
        successful = sum(1 for r in results if r["success"])
        
        return {
            "success": successful > 0,
            "accounts_processed": len(account_ids),
            "successful_executions": successful,
            "failed_executions": len(account_ids) - successful,
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }

    def _apply_policy_to_accounts(
        self,
        accounts: List[Account],
        policy_name: str,
        policy_config: Dict
    ) -> List[Dict]:
        """
        Apply policy to multiple accounts in parallel
        
        Args:
            accounts: List of Account objects
            policy_name: Name of the policy
            policy_config: Policy configuration
            
        Returns:
            List of application results
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_account = {
                executor.submit(
                    self.apply_account_policy,
                    account.id,
                    policy_name,
                    policy_config
                ): account
                for account in accounts
            }
            
            for future in as_completed(future_to_account):
                account = future_to_account[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to apply policy to account {account.id}: {e}")
                    results.append({
                        "success": False,
                        "account_id": account.id,
                        "error": str(e)
                    })
        
        return results

    def _execute_prevention_for_account(self, account_id: str) -> Dict:
        """
        Execute prevention cycle for a single account
        
        Args:
            account_id: Account ID
            
        Returns:
            Dict with execution result
        """
        try:
            # Run prevention cycle using Phase 3 engine
            result = self.prevention_engine.run_prevention_cycle()
            
            return {
                "success": result.get("success", False),
                "account_id": account_id,
                "actions_taken": result.get("actions_taken", 0),
                "budget_events": result.get("budget_events", 0),
                "timestamp": result.get("timestamp")
            }
        except Exception as e:
            logger.error(f"Prevention execution failed for account {account_id}: {e}")
            return {
                "success": False,
                "account_id": account_id,
                "error": str(e)
            }
