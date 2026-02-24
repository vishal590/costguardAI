"""
Property-based tests for Multi-Account Cost Collector

Feature: multi-account-cost-management
"""
import pytest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock
from hypothesis import given, strategies as st, settings, assume
from botocore.exceptions import ClientError

from src.services.multi_account.multi_account_cost_collector import (
    MultiAccountCostCollector,
    AccountCostData,
    CollectionResult
)
from src.services.multi_account.cross_account_role_manager import Credentials


# Custom strategies
@st.composite
def account_id_list_strategy(draw):
    """Generate list of unique valid AWS account IDs"""
    count = draw(st.integers(min_value=1, max_value=20))
    # Use a set to ensure uniqueness
    account_ids = set()
    while len(account_ids) < count:
        account_id = ''.join([str(draw(st.integers(min_value=0, max_value=9))) for _ in range(12)])
        account_ids.add(account_id)
    return list(account_ids)


@st.composite
def date_range_strategy(draw):
    """Generate valid date ranges"""
    start_year = draw(st.integers(min_value=2020, max_value=2024))
    start_month = draw(st.integers(min_value=1, max_value=12))
    start_day = draw(st.integers(min_value=1, max_value=28))  # Safe for all months
    
    start_date = date(start_year, start_month, start_day)
    
    # End date is 1-30 days after start
    days_diff = draw(st.integers(min_value=1, max_value=30))
    end_year = start_year
    end_month = start_month
    end_day = start_day + days_diff
    
    # Simple date arithmetic (not handling month/year overflow for simplicity)
    if end_day > 28:
        end_day = 28
    
    end_date = date(end_year, end_month, end_day)
    
    return start_date, end_date


@st.composite
def failure_rate_strategy(draw):
    """Generate failure rate between 0 and 1"""
    return draw(st.floats(min_value=0.0, max_value=1.0))


class TestMultiAccountCostCollectorProperties:
    """Property-based tests for Multi-Account Cost Collector"""
    
    @given(
        account_ids=account_id_list_strategy(),
        date_range=date_range_strategy(),
        failure_rate=failure_rate_strategy()
    )
    @settings(max_examples=20, deadline=None)
    def test_property_3_cost_collection_resilience(self, account_ids, date_range, failure_rate):
        """
        Property 3: Cost Collection Resilience
        
        For any list of accounts with some failures, successful accounts should
        have valid cost data and failed accounts should not break the collection.
        
        Validates: Requirements 3.4, 18.1
        
        Feature: multi-account-cost-management, Property 3: Cost Collection Resilience
        """
        start_date, end_date = date_range
        
        # Setup mock role manager
        mock_role_manager = Mock()
        mock_role_manager.assume_role.return_value = Credentials(
            access_key_id='AKIAIOSFODNN7EXAMPLE',
            secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            session_token='FwoGZXIvYXdzEBYaDH...',
            expiration=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        # Mock boto3 session
        mock_session = Mock()
        mock_ce_client = Mock()
        mock_session.client.return_value = mock_ce_client
        mock_role_manager.create_boto3_session.return_value = mock_session
        
        # Mock Cost Explorer to fail for some accounts based on failure_rate
        call_count = [0]
        
        def mock_get_cost_and_usage(*args, **kwargs):
            call_count[0] += 1
            # Fail based on failure rate
            if (call_count[0] / len(account_ids)) <= failure_rate:
                raise ClientError(
                    {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
                    'GetCostAndUsage'
                )
            return {
                'ResultsByTime': [
                    {
                        'TimePeriod': {'Start': start_date.strftime('%Y-%m-%d'), 'End': end_date.strftime('%Y-%m-%d')},
                        'Groups': [
                            {
                                'Keys': ['Amazon EC2'],
                                'Metrics': {'UnblendedCost': {'Amount': '100.00', 'Unit': 'USD'}}
                            }
                        ]
                    }
                ]
            }
        
        mock_ce_client.get_cost_and_usage.side_effect = mock_get_cost_and_usage
        
        # Create collector with reduced retries for faster testing
        collector = MultiAccountCostCollector(
            role_manager=mock_role_manager,
            cost_repository=Mock(),
            max_retries=1,
            max_workers=5
        )
        
        # Execute
        results = collector.collect_parallel(
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date
        )
        
        # Property 1: All accounts should have a result
        assert len(results) == len(account_ids), \
            "Should have result for every account"
        
        # Property 2: Successful accounts should have valid cost data
        successful = [r for r in results if r.status == 'SUCCESS']
        for result in successful:
            assert result.total_cost >= 0, \
                "Successful accounts should have non-negative costs"
            assert result.account_id in account_ids, \
                "Result should be for a requested account"
            assert result.start_date == start_date, \
                "Result should have correct start date"
            assert result.end_date == end_date, \
                "Result should have correct end date"
        
        # Property 3: Failed accounts should have status FAILED
        failed = [r for r in results if r.status == 'FAILED']
        for result in failed:
            assert result.total_cost == Decimal('0'), \
                "Failed accounts should have zero cost"
            assert result.error_message is not None, \
                "Failed accounts should have error message"
        
        # Property 4: Total results = successful + failed
        assert len(successful) + len(failed) == len(account_ids), \
            "All accounts should be either successful or failed"
        
        # Property 5: No duplicate account IDs in results
        result_account_ids = [r.account_id for r in results]
        assert len(result_account_ids) == len(set(result_account_ids)), \
            "Should not have duplicate account IDs in results"
    
    @given(
        account_ids=account_id_list_strategy(),
        date_range=date_range_strategy()
    )
    @settings(max_examples=20, deadline=None)
    def test_property_8_parallel_collection_equivalence(self, account_ids, date_range):
        """
        Property 8: Parallel Collection Equivalence
        
        For any list of accounts, collecting in parallel should produce
        equivalent results to collecting sequentially (same total costs).
        
        Validates: Requirements 3.2
        
        Feature: multi-account-cost-management, Property 8: Parallel Collection Equivalence
        """
        # Skip if too few accounts (parallel vs sequential doesn't matter)
        assume(len(account_ids) >= 2)
        
        start_date, end_date = date_range
        
        # Setup mock role manager
        mock_role_manager = Mock()
        mock_role_manager.assume_role.return_value = Credentials(
            access_key_id='AKIAIOSFODNN7EXAMPLE',
            secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            session_token='FwoGZXIvYXdzEBYaDH...',
            expiration=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        # Mock boto3 session
        mock_session = Mock()
        mock_ce_client = Mock()
        mock_session.client.return_value = mock_ce_client
        mock_role_manager.create_boto3_session.return_value = mock_session
        
        # Mock Cost Explorer to return consistent data
        mock_ce_client.get_cost_and_usage.return_value = {
            'ResultsByTime': [
                {
                    'TimePeriod': {'Start': start_date.strftime('%Y-%m-%d'), 'End': end_date.strftime('%Y-%m-%d')},
                    'Groups': [
                        {
                            'Keys': ['Amazon EC2'],
                            'Metrics': {'UnblendedCost': {'Amount': '100.00', 'Unit': 'USD'}}
                        }
                    ]
                }
            ]
        }
        
        # Create collector
        collector = MultiAccountCostCollector(
            role_manager=mock_role_manager,
            cost_repository=Mock(),
            max_workers=5
        )
        
        # Execute parallel collection
        parallel_results = collector.collect_parallel(
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date
        )
        
        # Execute sequential collection (max_workers=1)
        collector_sequential = MultiAccountCostCollector(
            role_manager=mock_role_manager,
            cost_repository=Mock(),
            max_workers=1
        )
        
        sequential_results = collector_sequential.collect_parallel(
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date
        )
        
        # Property 1: Same number of results
        assert len(parallel_results) == len(sequential_results), \
            "Parallel and sequential should return same number of results"
        
        # Property 2: Same account IDs
        parallel_ids = {r.account_id for r in parallel_results}
        sequential_ids = {r.account_id for r in sequential_results}
        assert parallel_ids == sequential_ids, \
            "Parallel and sequential should process same accounts"
        
        # Property 3: Same total costs (order may differ)
        parallel_costs = {r.account_id: r.total_cost for r in parallel_results}
        sequential_costs = {r.account_id: r.total_cost for r in sequential_results}
        
        for account_id in account_ids:
            assert parallel_costs[account_id] == sequential_costs[account_id], \
                f"Account {account_id} should have same cost in parallel and sequential"
        
        # Property 4: Same success/failure status
        parallel_status = {r.account_id: r.status for r in parallel_results}
        sequential_status = {r.account_id: r.status for r in sequential_results}
        
        for account_id in account_ids:
            assert parallel_status[account_id] == sequential_status[account_id], \
                f"Account {account_id} should have same status in parallel and sequential"
    
    @given(
        account_ids=account_id_list_strategy(),
        date_range=date_range_strategy()
    )
    @settings(max_examples=20, deadline=None)
    def test_property_collection_result_consistency(self, account_ids, date_range):
        """
        Property: Collection Result Consistency
        
        For any collection result, the summary statistics should match
        the detailed account data.
        
        Validates: Requirements 3.1, 3.2
        
        Feature: multi-account-cost-management, Property: Collection Result Consistency
        """
        start_date, end_date = date_range
        
        # Setup mock role manager
        mock_role_manager = Mock()
        mock_role_manager.assume_role.return_value = Credentials(
            access_key_id='AKIAIOSFODNN7EXAMPLE',
            secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            session_token='FwoGZXIvYXdzEBYaDH...',
            expiration=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        # Mock boto3 session
        mock_session = Mock()
        mock_ce_client = Mock()
        mock_session.client.return_value = mock_ce_client
        mock_role_manager.create_boto3_session.return_value = mock_session
        
        # Mock Cost Explorer
        mock_ce_client.get_cost_and_usage.return_value = {
            'ResultsByTime': [
                {
                    'TimePeriod': {'Start': start_date.strftime('%Y-%m-%d'), 'End': end_date.strftime('%Y-%m-%d')},
                    'Groups': [
                        {
                            'Keys': ['Amazon EC2'],
                            'Metrics': {'UnblendedCost': {'Amount': '100.00', 'Unit': 'USD'}}
                        }
                    ]
                }
            ]
        }
        
        # Create collector
        collector = MultiAccountCostCollector(
            role_manager=mock_role_manager,
            cost_repository=Mock(),
            max_workers=5
        )
        
        # Execute
        result = collector.collect_all_accounts(
            org_id='o-1234567890',
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date
        )
        
        # Property 1: Total accounts matches input
        assert result.total_accounts == len(account_ids), \
            "Total accounts should match input count"
        
        # Property 2: Successful + failed = total
        assert result.successful + result.failed == result.total_accounts, \
            "Successful + failed should equal total accounts"
        
        # Property 3: Failed accounts list matches failed count
        assert len(result.failed_accounts) == result.failed, \
            "Failed accounts list length should match failed count"
        
        # Property 4: Account data length matches total
        assert len(result.account_data) == result.total_accounts, \
            "Account data length should match total accounts"
        
        # Property 5: Collection duration is positive
        assert result.collection_duration > 0, \
            "Collection duration should be positive"
        
        # Property 6: All account IDs in results
        result_ids = {data.account_id for data in result.account_data}
        assert result_ids == set(account_ids), \
            "All account IDs should be in results"
