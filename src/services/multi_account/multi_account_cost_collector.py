"""
Multi-Account Cost Collector

Collects cost data from multiple AWS accounts in parallel using cross-account roles.
Implements retry logic and graceful failure handling.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError

from .cross_account_role_manager import CrossAccountRoleManager
from .repositories import MultiAccountCostRepository


logger = logging.getLogger(__name__)


@dataclass
class AccountCostData:
    """Cost data for a single account"""
    account_id: str
    start_date: date
    end_date: date
    total_cost: Decimal
    costs_by_service: Dict[str, Decimal]
    costs_by_day: Dict[str, Decimal]
    collection_timestamp: datetime
    status: str  # "SUCCESS", "FAILED", "PARTIAL"
    error_message: Optional[str] = None


@dataclass
class CollectionResult:
    """Result of collecting costs from multiple accounts"""
    total_accounts: int
    successful: int
    failed: int
    failed_accounts: List[str]
    collection_duration: float
    account_data: List[AccountCostData]


class MultiAccountCostCollector:
    """
    Collects cost data from multiple AWS accounts in parallel.
    
    Uses cross-account roles to access Cost Explorer API in member accounts.
    Implements parallel processing, retry logic, and graceful failure handling.
    """
    
    def __init__(
        self,
        role_manager: Optional[CrossAccountRoleManager] = None,
        cost_repository: Optional[MultiAccountCostRepository] = None,
        max_workers: int = 10,
        timeout_seconds: int = 60,
        max_retries: int = 3
    ):
        """
        Initialize the Multi-Account Cost Collector.
        
        Args:
            role_manager: Manager for cross-account role operations
            cost_repository: Repository for storing cost data
            max_workers: Maximum number of concurrent account collections
            timeout_seconds: Timeout for each account collection
            max_retries: Maximum number of retry attempts for failed collections
        """
        self.role_manager = role_manager or CrossAccountRoleManager()
        self.cost_repository = cost_repository or MultiAccountCostRepository()
        self.max_workers = max_workers
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
    
    def collect_all_accounts(
        self,
        org_id: str,
        account_ids: List[str],
        start_date: date,
        end_date: date
    ) -> CollectionResult:
        """
        Collect cost data from all accounts in organization.
        
        Args:
            org_id: Organization ID
            account_ids: List of account IDs to collect from
            start_date: Start date for cost data
            end_date: End date for cost data
            
        Returns:
            CollectionResult with summary and detailed data
        """
        logger.info(
            f"Starting cost collection for {len(account_ids)} accounts "
            f"from {start_date} to {end_date}"
        )
        
        start_time = time.time()
        
        # Collect costs in parallel
        account_data = self.collect_parallel(account_ids, start_date, end_date)
        
        # Calculate summary statistics
        successful = sum(1 for data in account_data if data.status == "SUCCESS")
        failed = sum(1 for data in account_data if data.status == "FAILED")
        failed_accounts = [data.account_id for data in account_data if data.status == "FAILED"]
        
        duration = time.time() - start_time
        
        result = CollectionResult(
            total_accounts=len(account_ids),
            successful=successful,
            failed=failed,
            failed_accounts=failed_accounts,
            collection_duration=duration,
            account_data=account_data
        )
        
        logger.info(
            f"Cost collection completed: {successful}/{len(account_ids)} successful, "
            f"{failed} failed, duration: {duration:.2f}s"
        )
        
        return result
    
    def collect_account(
        self,
        account_id: str,
        start_date: date,
        end_date: date,
        role_name: str = "CostGuardCollectorRole",
        external_id: Optional[str] = None
    ) -> AccountCostData:
        """
        Collect cost data from a single account with retry logic.
        
        Args:
            account_id: AWS account ID
            start_date: Start date for cost data
            end_date: End date for cost data
            role_name: Name of the cross-account role
            external_id: External ID for role assumption
            
        Returns:
            AccountCostData with cost information
        """
        logger.info(f"Collecting costs for account {account_id}")
        
        # Retry logic
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return self._collect_account_once(
                    account_id, start_date, end_date, role_name, external_id
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries} failed for account {account_id}: {e}"
                )
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    sleep_time = 2 ** attempt
                    time.sleep(sleep_time)
        
        # All retries failed
        logger.error(f"Failed to collect costs for account {account_id} after {self.max_retries} attempts")
        return AccountCostData(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            total_cost=Decimal("0"),
            costs_by_service={},
            costs_by_day={},
            collection_timestamp=datetime.utcnow(),
            status="FAILED",
            error_message=str(last_error)
        )
    
    def _collect_account_once(
        self,
        account_id: str,
        start_date: date,
        end_date: date,
        role_name: str,
        external_id: Optional[str]
    ) -> AccountCostData:
        """
        Collect cost data from a single account (single attempt).
        
        Args:
            account_id: AWS account ID
            start_date: Start date for cost data
            end_date: End date for cost data
            role_name: Name of the cross-account role
            external_id: External ID for role assumption
            
        Returns:
            AccountCostData with cost information
            
        Raises:
            ClientError: If AWS API calls fail
        """
        # Assume cross-account role
        credentials = self.role_manager.assume_role(
            account_id=account_id,
            role_name=role_name,
            external_id=external_id
        )
        
        # Create Cost Explorer client with assumed role credentials
        session = self.role_manager.create_boto3_session(credentials)
        ce_client = session.client('ce')
        
        # Query Cost Explorer
        response = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date.strftime('%Y-%m-%d'),
                'End': end_date.strftime('%Y-%m-%d')
            },
            Granularity='DAILY',
            Metrics=['UnblendedCost'],
            GroupBy=[
                {'Type': 'DIMENSION', 'Key': 'SERVICE'}
            ]
        )
        
        # Parse response
        costs_by_service = {}
        costs_by_day = {}
        total_cost = Decimal("0")
        
        for result in response.get('ResultsByTime', []):
            day_date = datetime.strptime(result['TimePeriod']['Start'], '%Y-%m-%d').date()
            day_total = Decimal("0")
            
            for group in result.get('Groups', []):
                service = group['Keys'][0]
                cost = Decimal(group['Metrics']['UnblendedCost']['Amount'])
                
                # Aggregate by service
                if service in costs_by_service:
                    costs_by_service[service] += cost
                else:
                    costs_by_service[service] = cost
                
                day_total += cost
            
            # Store daily total
            costs_by_day[day_date.strftime('%Y-%m-%d')] = day_total
            total_cost += day_total
        
        account_data = AccountCostData(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            total_cost=total_cost,
            costs_by_service=costs_by_service,
            costs_by_day=costs_by_day,
            collection_timestamp=datetime.utcnow(),
            status="SUCCESS"
        )
        
        # Store in DynamoDB
        self._store_cost_data(account_data)
        
        logger.info(f"Successfully collected costs for account {account_id}: ${total_cost}")
        return account_data
    
    def collect_parallel(
        self,
        account_ids: List[str],
        start_date: date,
        end_date: date,
        role_name: str = "CostGuardCollectorRole",
        external_id: Optional[str] = None
    ) -> List[AccountCostData]:
        """
        Collect cost data from multiple accounts in parallel.
        
        Args:
            account_ids: List of AWS account IDs
            start_date: Start date for cost data
            end_date: End date for cost data
            role_name: Name of the cross-account role
            external_id: External ID for role assumption
            
        Returns:
            List of AccountCostData for all accounts
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_account = {
                executor.submit(
                    self.collect_account,
                    account_id,
                    start_date,
                    end_date,
                    role_name,
                    external_id
                ): account_id
                for account_id in account_ids
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_account, timeout=self.timeout_seconds * len(account_ids)):
                account_id = future_to_account[future]
                try:
                    account_data = future.result(timeout=self.timeout_seconds)
                    results.append(account_data)
                except TimeoutError:
                    logger.error(f"Timeout collecting costs for account {account_id}")
                    results.append(AccountCostData(
                        account_id=account_id,
                        start_date=start_date,
                        end_date=end_date,
                        total_cost=Decimal("0"),
                        costs_by_service={},
                        costs_by_day={},
                        collection_timestamp=datetime.utcnow(),
                        status="FAILED",
                        error_message="Timeout"
                    ))
                except Exception as e:
                    logger.error(f"Error collecting costs for account {account_id}: {e}")
                    results.append(AccountCostData(
                        account_id=account_id,
                        start_date=start_date,
                        end_date=end_date,
                        total_cost=Decimal("0"),
                        costs_by_service={},
                        costs_by_day={},
                        collection_timestamp=datetime.utcnow(),
                        status="FAILED",
                        error_message=str(e)
                    ))
        
        return results
    
    def _store_cost_data(self, account_data: AccountCostData) -> None:
        """
        Store collected cost data in DynamoDB.
        
        Args:
            account_data: Cost data to store
        """
        try:
            self.cost_repository.save_cost_data(
                account_id=account_data.account_id,
                date=account_data.start_date,
                total_cost=float(account_data.total_cost),
                costs_by_service={k: float(v) for k, v in account_data.costs_by_service.items()},
                costs_by_day={k: float(v) for k, v in account_data.costs_by_day.items()}
            )
        except Exception as e:
            logger.error(f"Failed to store cost data for account {account_data.account_id}: {e}")
            # Don't raise - we still want to return the collected data
