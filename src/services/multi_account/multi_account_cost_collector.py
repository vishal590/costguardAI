"""
Multi-Account Cost Collector

Collects cost data from multiple AWS accounts in parallel using cross-account roles.
Implements retry logic and graceful failure handling.
"""
import logging
import os
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
from .cloudwatch_metrics import get_metrics_service, metrics_collector


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
        max_workers: Optional[int] = None,
        timeout_seconds: int = 60,
        max_retries: int = 3
    ):
        """
        Initialize the Multi-Account Cost Collector.
        
        Args:
            role_manager: Manager for cross-account role operations
            cost_repository: Repository for storing cost data
            max_workers: Maximum number of concurrent account collections.
                         If None, reads from MAX_PARALLEL_ACCOUNTS environment variable.
                         Defaults to 10 if not set.
            timeout_seconds: Timeout for each account collection
            max_retries: Maximum number of retry attempts for failed collections
        """
        self.role_manager = role_manager or CrossAccountRoleManager()
        self.cost_repository = cost_repository or MultiAccountCostRepository()
        
        # Read max_workers from environment variable if not provided
        if max_workers is None:
            max_workers = int(os.environ.get('MAX_PARALLEL_ACCOUNTS', '10'))
        
        self.max_workers = max_workers
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        
        logger.info(f"Initialized MultiAccountCostCollector with max_workers={self.max_workers}")
    
    def collect_all_accounts(
        self,
        org_id: str,
        account_ids: List[str],
        start_date: date,
        end_date: date,
        role_name: Optional[str] = None,
        external_id: Optional[str] = None
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
        
        external_id = external_id or os.environ.get('EXTERNAL_ID')
        if not external_id: raise ValueError('Configure the external ID used by member role trust policies')
        metrics_service = get_metrics_service()
        
        with metrics_collector('MultiAccountCostCollection', 
                             {'OrganizationId': org_id, 'AccountCount': str(len(account_ids))}) as collector:
            
            start_time = time.time()
            
            # Collect costs in parallel
            account_data = self.collect_parallel(account_ids, start_date, end_date, role_name, external_id)
            
            # Calculate summary statistics
            successful = sum(1 for data in account_data if data.status == "SUCCESS")
            failed = sum(1 for data in account_data if data.status == "FAILED")
            failed_accounts = [data.account_id for data in account_data if data.status == "FAILED"]
            
            duration = time.time() - start_time
            
            # Record metrics
            metrics_service.record_cost_collection_duration(duration, len(account_ids))
            metrics_service.record_cost_collection_success_rate(successful, len(account_ids))
            
            collector.record_custom_metric('AccountsProcessed', len(account_ids))
            collector.record_custom_metric('SuccessfulAccounts', successful)
            collector.record_custom_metric('FailedAccounts', failed)
            
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
        role_name: Optional[str] = None,
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
        
        role_name = role_name or self.role_manager.default_role_name
        external_id = external_id or os.environ.get('EXTERNAL_ID')
        if not external_id: raise ValueError('Configure the external ID used by member role trust policies')
        if not isinstance(start_date, date) or not isinstance(end_date, date) or end_date <= start_date:
            raise ValueError('Supply date objects with an exclusive end after start')
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
        
        period = {'Start': start_date.isoformat(), 'End': end_date.isoformat()}
        def pages(grouping):
            request = dict(TimePeriod=period, Granularity='DAILY', Metrics=['UnblendedCost'], GroupBy=grouping)
            seen = set()
            while True:
                page = ce_client.get_cost_and_usage(**request)
                yield from page.get('ResultsByTime', [])
                token = page.get('NextPageToken')
                if not token: break
                if token in seen: raise ValueError('Repeated Cost Explorer page token')
                seen.add(token)
                request['NextPageToken'] = token
        costs_by_service, costs_by_day, daily_services, daily_tags = {}, {}, {}, {}
        daily_estimates = {}
        total_cost = Decimal('0')
        for result in pages([{'Type': 'DIMENSION', 'Key': 'SERVICE'}]):
            day = result['TimePeriod']['Start']
            flag = result.get('Estimated') if type(result.get('Estimated')) is bool else None
            previous = daily_estimates.get(day, flag)
            daily_estimates[day] = True if previous is True or flag is True else None if previous is None or flag is None else False
            daily_services.setdefault(day, {})
            for group in result.get('Groups', []):
                metric = group['Metrics']['UnblendedCost']
                if metric.get('Unit') != 'USD': raise ValueError('Only USD collection is supported')
                service, amount = group['Keys'][0], Decimal(metric['Amount'])
                if not amount.is_finite(): raise ValueError('Observed cost must be finite')
                costs_by_service[service] = costs_by_service.get(service, Decimal('0')) + amount
                daily_services[day][service] = daily_services[day].get(service, Decimal('0')) + amount
                costs_by_day[day] = costs_by_day.get(day, Decimal('0')) + amount
                total_cost += amount
            costs_by_day.setdefault(day, Decimal('0'))
        expected_days = {(start_date+timedelta(days=index)).isoformat() for index in range((end_date-start_date).days)}
        if set(costs_by_day) != expected_days:
            raise ValueError('Cost Explorer did not return every requested daily period')
        collect_tags = os.environ.get('COLLECT_ALLOCATION_TAGS', 'false').lower() == 'true'
        if collect_tags:
            tag_coverage = {day: set() for day in costs_by_day}
            daily_tags = {day: {} for day in costs_by_day}
            for tag_key in ('Team', 'Project', 'Environment'):
                for result in pages([{'Type': 'TAG', 'Key': tag_key}, {'Type': 'DIMENSION', 'Key': 'SERVICE'}]):
                    day = result['TimePeriod']['Start']
                    if day not in daily_tags: raise ValueError('Tag collection returned an unexpected date')
                    tag_coverage[day].add(tag_key)
                    flag = result.get('Estimated') if type(result.get('Estimated')) is bool else None
                    previous = daily_estimates.get(day)
                    daily_estimates[day] = True if previous is True or flag is True else None if previous is None or flag is None else False
                    for group in result.get('Groups', []):
                        tagged, service = group['Keys']
                        key, separator, value = tagged.partition('$')
                        if not separator or key != tag_key or not value: continue
                        if group['Metrics']['UnblendedCost'].get('Unit') != 'USD': raise ValueError('Only USD allocation collection is supported')
                        amount = Decimal(group['Metrics']['UnblendedCost']['Amount'])
                        if not amount.is_finite(): raise ValueError('Allocation cost must be finite')
                        category = tag_key + ':' + value
                        services = daily_tags[day].setdefault(category, {})
                        services[service] = services.get(service, Decimal('0')) + amount
            if any(keys != {'Team', 'Project', 'Environment'} for keys in tag_coverage.values()):
                raise ValueError('Daily tag collection is incomplete; no full allocation coverage was established')
        # Store real daily records; aggregate return values are not written as a single day.
        from .models import AccountCostData as StoredCostData
        for day, amount in costs_by_day.items():
            self.cost_repository.save(StoredCostData(
                account_id=account_id, start_date=day, end_date=day, total_cost=amount,
                costs_by_service=daily_services[day], costs_by_day={day: amount},
                collection_timestamp=datetime.utcnow(), status='SUCCESS',
                costs_by_tag_service=daily_tags.get(day) if collect_tags else None, is_estimated=daily_estimates.get(day)))
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
        
        logger.info(f"Successfully collected costs for account {account_id}: ${total_cost}")
        return account_data
    
    def collect_parallel(
        self,
        account_ids: List[str],
        start_date: date,
        end_date: date,
        role_name: Optional[str] = None,
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
        """Persist an explicitly single-day record through the repository API."""
        if len(account_data.costs_by_day) != 1:
            raise ValueError("Daily persistence requires a single-day record")
        self.cost_repository.save(account_data)
