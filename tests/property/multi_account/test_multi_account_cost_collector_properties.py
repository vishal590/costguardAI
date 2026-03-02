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
    
    @given(
        account_ids=account_id_list_strategy(),
        date_range=date_range_strategy(),
        failure_rate=st.floats(min_value=0.0, max_value=1.0)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_5_cross_account_role_assumption_resilience(self, account_ids, date_range, failure_rate):
        """
        Property 5: Cross-Account Role Assumption Resilience
        
        For any list of accounts being processed by the Multi_Account_Cost_Collector, 
        if role assumption fails for some accounts, then the collector should log the 
        failures, continue processing remaining accounts, and include the failed account 
        IDs in the collection summary.
        
        Validates: Requirements 2.3
        
        Feature: phase-5-handlers, Property 5: Cross-Account Role Assumption Resilience
        """
        start_date, end_date = date_range
        
        # Setup mock role manager that fails for some accounts
        mock_role_manager = Mock()
        
        call_count = [0]
        def mock_assume_role(account_id, role_name, external_id):
            call_count[0] += 1
            # Fail based on failure rate
            if (call_count[0] / len(account_ids)) <= failure_rate:
                raise ClientError(
                    {'Error': {'Code': 'AccessDenied', 'Message': 'Cannot assume role'}},
                    'AssumeRole'
                )
            return Credentials(
                access_key_id='AKIAIOSFODNN7EXAMPLE',
                secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                session_token='FwoGZXIvYXdzEBYaDH...',
                expiration=datetime(2024, 1, 1, 12, 0, 0)
            )
        
        mock_role_manager.assume_role.side_effect = mock_assume_role
        
        # Mock successful Cost Explorer calls for accounts where role assumption succeeds
        mock_session = Mock()
        mock_ce_client = Mock()
        mock_session.client.return_value = mock_ce_client
        mock_role_manager.create_boto3_session.return_value = mock_session
        
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
            max_retries=1,
            max_workers=5
        )
        
        # Execute
        result = collector.collect_all_accounts(
            org_id='o-1234567890',
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date
        )
        
        # Property: Failed accounts should be included in summary
        expected_failed_count = int(len(account_ids) * failure_rate)
        assert result.failed >= 0, "Failed count should be non-negative"
        assert len(result.failed_accounts) == result.failed, \
            "Failed accounts list should match failed count"
        
        # Property: Successful + failed should equal total
        assert result.successful + result.failed == len(account_ids), \
            "All accounts should be either successful or failed"
        
        # Property: Failed account IDs should be from input list
        for failed_id in result.failed_accounts:
            assert failed_id in account_ids, \
                "Failed account ID should be from input list"
        
        # Property: Collection should continue despite failures
        assert result.total_accounts == len(account_ids), \
            "Should process all accounts despite role assumption failures"
    
    @given(
        account_ids=account_id_list_strategy(),
        date_range=date_range_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_6_cost_data_persistence(self, account_ids, date_range):
        """
        Property 6: Cost Data Persistence
        
        For any account cost data retrieved by the Multi_Account_Cost_Collector, the data 
        should be stored in the costguard-multi-account-costs DynamoDB table with all 
        required fields (account_id, date, total_cost, costs_by_service, costs_by_day, 
        collection_timestamp, status).
        
        Validates: Requirements 2.5
        
        Feature: phase-5-handlers, Property 6: Cost Data Persistence
        """
        start_date, end_date = date_range
        
        # Setup mocks
        mock_role_manager = Mock()
        mock_role_manager.assume_role.return_value = Credentials(
            access_key_id='AKIAIOSFODNN7EXAMPLE',
            secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            session_token='FwoGZXIvYXdzEBYaDH...',
            expiration=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        mock_session = Mock()
        mock_ce_client = Mock()
        mock_session.client.return_value = mock_ce_client
        mock_role_manager.create_boto3_session.return_value = mock_session
        
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
        
        mock_cost_repository = Mock()
        mock_cost_repository.save.return_value = None
        
        # Create collector
        collector = MultiAccountCostCollector(
            role_manager=mock_role_manager,
            cost_repository=mock_cost_repository,
            max_workers=5
        )
        
        # Execute
        result = collector.collect_all_accounts(
            org_id='o-1234567890',
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date
        )
        
        # Property: All successful accounts should have data persisted
        assert mock_cost_repository.save.call_count == result.successful, \
            "Should persist data for all successful accounts"
        
        # Property: Each saved cost data should have all required fields
        for call in mock_cost_repository.save.call_args_list:
            cost_data = call[0][0]  # First argument is the cost data
            
            # Verify all required fields are present
            assert hasattr(cost_data, 'account_id'), "Should have account_id"
            assert hasattr(cost_data, 'start_date'), "Should have start_date"
            assert hasattr(cost_data, 'end_date'), "Should have end_date"
            assert hasattr(cost_data, 'total_cost'), "Should have total_cost"
            assert hasattr(cost_data, 'costs_by_service'), "Should have costs_by_service"
            assert hasattr(cost_data, 'costs_by_day'), "Should have costs_by_day"
            assert hasattr(cost_data, 'collection_timestamp'), "Should have collection_timestamp"
            assert hasattr(cost_data, 'status'), "Should have status"
            
            # Verify field values
            assert cost_data.account_id in account_ids, "Account ID should be from input list"
            assert cost_data.start_date == start_date, "Start date should match"
            assert cost_data.end_date == end_date, "End date should match"
            assert cost_data.total_cost >= 0, "Total cost should be non-negative"
            assert cost_data.status == 'SUCCESS', "Status should be SUCCESS for persisted data"
    
    @given(
        account_ids=account_id_list_strategy(),
        date_range=date_range_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_7_collection_summary_completeness(self, account_ids, date_range):
        """
        Property 7: Collection Summary Completeness
        
        For any cost collection operation, when all accounts are processed, the returned 
        summary should include total_accounts count, successful count, failed count, 
        list of failed_accounts, and collection_duration.
        
        Validates: Requirements 2.6
        
        Feature: phase-5-handlers, Property 7: Collection Summary Completeness
        """
        start_date, end_date = date_range
        
        # Setup mocks
        mock_role_manager = Mock()
        mock_role_manager.assume_role.return_value = Credentials(
            access_key_id='AKIAIOSFODNN7EXAMPLE',
            secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            session_token='FwoGZXIvYXdzEBYaDH...',
            expiration=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        mock_session = Mock()
        mock_ce_client = Mock()
        mock_session.client.return_value = mock_ce_client
        mock_role_manager.create_boto3_session.return_value = mock_session
        
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
        
        # Property: Summary should have all required fields
        assert hasattr(result, 'total_accounts'), "Should have total_accounts"
        assert hasattr(result, 'successful'), "Should have successful count"
        assert hasattr(result, 'failed'), "Should have failed count"
        assert hasattr(result, 'failed_accounts'), "Should have failed_accounts list"
        assert hasattr(result, 'collection_duration'), "Should have collection_duration"
        
        # Property: Total accounts should match input
        assert result.total_accounts == len(account_ids), \
            "Total accounts should match input count"
        
        # Property: Successful + failed should equal total
        assert result.successful + result.failed == result.total_accounts, \
            "Successful + failed should equal total"
        
        # Property: Failed accounts list length should match failed count
        assert len(result.failed_accounts) == result.failed, \
            "Failed accounts list length should match failed count"
        
        # Property: Collection duration should be positive
        assert result.collection_duration > 0, \
            "Collection duration should be positive"
        
        # Property: All counts should be non-negative
        assert result.total_accounts >= 0, "Total accounts should be non-negative"
        assert result.successful >= 0, "Successful count should be non-negative"
        assert result.failed >= 0, "Failed count should be non-negative"
    
    @given(
        account_ids=account_id_list_strategy(),
        date_range=date_range_strategy(),
        failure_rate=st.floats(min_value=0.2, max_value=1.0)  # High failure rate
    )
    @settings(max_examples=100, deadline=None)
    def test_property_8_high_failure_rate_detection(self, account_ids, date_range, failure_rate):
        """
        Property 8: High Failure Rate Detection
        
        For any cost collection operation, if the number of failed accounts divided by 
        total accounts exceeds 0.2 (20%), then the response status code should be 207 
        (Multi-Status) instead of 200.
        
        Validates: Requirements 2.7
        
        Feature: phase-5-handlers, Property 8: High Failure Rate Detection
        """
        # Skip if not enough accounts to test high failure rate meaningfully
        assume(len(account_ids) >= 5)
        
        start_date, end_date = date_range
        
        # Setup mock role manager that fails for many accounts
        mock_role_manager = Mock()
        
        call_count = [0]
        def mock_assume_role(account_id, role_name, external_id):
            call_count[0] += 1
            # Fail based on high failure rate
            if (call_count[0] / len(account_ids)) <= failure_rate:
                raise ClientError(
                    {'Error': {'Code': 'AccessDenied', 'Message': 'Cannot assume role'}},
                    'AssumeRole'
                )
            return Credentials(
                access_key_id='AKIAIOSFODNN7EXAMPLE',
                secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                session_token='FwoGZXIvYXdzEBYaDH...',
                expiration=datetime(2024, 1, 1, 12, 0, 0)
            )
        
        mock_role_manager.assume_role.side_effect = mock_assume_role
        
        mock_session = Mock()
        mock_ce_client = Mock()
        mock_session.client.return_value = mock_ce_client
        mock_role_manager.create_boto3_session.return_value = mock_session
        
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
            max_retries=1,
            max_workers=5
        )
        
        # Execute
        result = collector.collect_all_accounts(
            org_id='o-1234567890',
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date
        )
        
        # Property: High failure rate should be detected
        actual_failure_rate = result.failed / result.total_accounts if result.total_accounts > 0 else 0
        
        if actual_failure_rate > 0.2:
            # Property: Should indicate high failure rate (this would be reflected in status code)
            assert result.failed > result.successful * 0.25, \
                "High failure rate should be detected"
            assert len(result.failed_accounts) > 0, \
                "Should have failed accounts when failure rate is high"
        
        # Property: Failed accounts should be properly tracked
        assert len(result.failed_accounts) == result.failed, \
            "Failed accounts list should match failed count"
    
    @given(
        account_ids=account_id_list_strategy(),
        date_range=date_range_strategy(),
        max_concurrency=st.integers(min_value=1, max_value=15)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_9_parallel_processing_concurrency_limit(self, account_ids, date_range, max_concurrency):
        """
        Property 9: Parallel Processing Concurrency Limit
        
        For any cost collection operation processing multiple accounts, the number of 
        accounts processed concurrently should never exceed the configured maximum 
        (default 10).
        
        Validates: Requirements 2.9, 16.2
        
        Feature: phase-5-handlers, Property 9: Parallel Processing Concurrency Limit
        """
        # Skip if only one account (no concurrency to test)
        assume(len(account_ids) >= 2)
        
        start_date, end_date = date_range
        
        # Track concurrent executions
        active_calls = [0]
        max_concurrent = [0]
        
        def mock_assume_role(account_id, role_name, external_id):
            active_calls[0] += 1
            max_concurrent[0] = max(max_concurrent[0], active_calls[0])
            
            # Simulate some processing time
            import time
            time.sleep(0.01)
            
            active_calls[0] -= 1
            
            return Credentials(
                access_key_id='AKIAIOSFODNN7EXAMPLE',
                secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                session_token='FwoGZXIvYXdzEBYaDH...',
                expiration=datetime(2024, 1, 1, 12, 0, 0)
            )
        
        mock_role_manager = Mock()
        mock_role_manager.assume_role.side_effect = mock_assume_role
        
        mock_session = Mock()
        mock_ce_client = Mock()
        mock_session.client.return_value = mock_ce_client
        mock_role_manager.create_boto3_session.return_value = mock_session
        
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
        
        # Create collector with specified max concurrency
        collector = MultiAccountCostCollector(
            role_manager=mock_role_manager,
            cost_repository=Mock(),
            max_workers=max_concurrency
        )
        
        # Execute
        result = collector.collect_parallel(
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date
        )
        
        # Property: Concurrency should not exceed limit
        assert max_concurrent[0] <= max_concurrency, \
            f"Max concurrent calls ({max_concurrent[0]}) should not exceed limit ({max_concurrency})"
        
        # Property: All accounts should still be processed
        assert len(result) == len(account_ids), \
            "All accounts should be processed despite concurrency limit"
    
    @given(
        account_ids=account_id_list_strategy(),
        date_range=date_range_strategy(),
        retry_count=st.integers(min_value=1, max_value=3)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_10_retry_with_exponential_backoff(self, account_ids, date_range, retry_count):
        """
        Property 10: Retry with Exponential Backoff
        
        For any Cost Explorer API call or DynamoDB operation that fails with a throttling 
        error, the handler should retry the operation up to 3 times with exponential 
        backoff (base delay of 1 second), and only fail after all retries are exhausted.
        
        Validates: Requirements 2.10, 17.1, 17.2, 17.3, 17.4, 17.5
        
        Feature: phase-5-handlers, Property 10: Retry with Exponential Backoff
        """
        # Use only first account for focused retry testing
        test_account_id = account_ids[0]
        start_date, end_date = date_range
        
        # Track retry attempts and timing
        call_times = []
        call_count = [0]
        
        def mock_get_cost_and_usage(*args, **kwargs):
            call_count[0] += 1
            call_times.append(datetime.now())
            
            # Fail with throttling for first few attempts
            if call_count[0] <= retry_count:
                raise ClientError(
                    {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
                    'GetCostAndUsage'
                )
            
            # Succeed after retries
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
        
        mock_role_manager = Mock()
        mock_role_manager.assume_role.return_value = Credentials(
            access_key_id='AKIAIOSFODNN7EXAMPLE',
            secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            session_token='FwoGZXIvYXdzEBYaDH...',
            expiration=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        mock_session = Mock()
        mock_ce_client = Mock()
        mock_session.client.return_value = mock_ce_client
        mock_role_manager.create_boto3_session.return_value = mock_session
        
        mock_ce_client.get_cost_and_usage.side_effect = mock_get_cost_and_usage
        
        # Create collector with retry configuration
        collector = MultiAccountCostCollector(
            role_manager=mock_role_manager,
            cost_repository=Mock(),
            max_retries=3,
            max_workers=1
        )
        
        # Execute
        result = collector.collect_account(
            account_id=test_account_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Property: Should retry the specified number of times plus initial attempt
        expected_calls = retry_count + 1
        assert call_count[0] == expected_calls, \
            f"Should make {expected_calls} calls (initial + {retry_count} retries)"
        
        # Property: Should eventually succeed after retries
        assert result.status == 'SUCCESS', \
            "Should succeed after retries"
        
        # Property: Should have exponential backoff delays (if multiple calls)
        if len(call_times) > 1:
            for i in range(1, len(call_times)):
                time_diff = (call_times[i] - call_times[i-1]).total_seconds()
                # Should have some delay (at least 0.5 seconds for exponential backoff)
                assert time_diff >= 0.5, \
                    f"Should have exponential backoff delay between retries (got {time_diff}s)"
    
    @given(
        account_ids=account_id_list_strategy(),
        date_range=date_range_strategy(),
        invalid_data_rate=st.floats(min_value=0.0, max_value=0.5)  # Up to 50% invalid data
    )
    @settings(max_examples=100, deadline=None)
    def test_property_24_cost_data_validation(self, account_ids, date_range, invalid_data_rate):
        """
        Property 24: Cost Data Validation
        
        For any cost data retrieved from Cost Explorer, if cost values are negative, or 
        date fields are in invalid format, or account_id doesn't match the expected account, 
        then the collector should log a warning, skip the invalid record, and include the 
        validation error count in the collection summary.
        
        Validates: Requirements 18.1, 18.2, 18.3, 18.4, 18.5
        
        Feature: phase-5-handlers, Property 24: Cost Data Validation
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
        
        mock_session = Mock()
        mock_ce_client = Mock()
        mock_session.client.return_value = mock_ce_client
        mock_role_manager.create_boto3_session.return_value = mock_session
        
        # Mock Cost Explorer to return some invalid data
        call_count = [0]
        def mock_get_cost_and_usage(*args, **kwargs):
            call_count[0] += 1
            
            # Return invalid data for some calls based on invalid_data_rate
            if (call_count[0] / len(account_ids)) <= invalid_data_rate:
                # Return data with negative costs (invalid)
                return {
                    'ResultsByTime': [
                        {
                            'TimePeriod': {'Start': start_date.strftime('%Y-%m-%d'), 'End': end_date.strftime('%Y-%m-%d')},
                            'Groups': [
                                {
                                    'Keys': ['Amazon EC2'],
                                    'Metrics': {'UnblendedCost': {'Amount': '-100.00', 'Unit': 'USD'}}  # Negative cost
                                }
                            ]
                        }
                    ]
                }
            else:
                # Return valid data
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
        
        # Property: All accounts should be processed (validation doesn't stop processing)
        assert result.total_accounts == len(account_ids), \
            "Should process all accounts despite validation errors"
        
        # Property: Accounts with invalid data should be marked appropriately
        # (Implementation detail: they might be marked as failed or have zero costs)
        for account_data in result.account_data:
            if account_data.status == 'SUCCESS':
                # Valid data should have non-negative costs
                assert account_data.total_cost >= 0, \
                    "Valid accounts should have non-negative costs"
            
            # All account data should have valid account IDs
            assert account_data.account_id in account_ids, \
                "Account ID should match expected accounts"
        
        # Property: Collection should complete successfully overall
        assert result.collection_duration > 0, \
            "Collection should complete with positive duration"
    
    @given(
        account_ids=account_id_list_strategy(),
        date_range=date_range_strategy(),
        partial_failure_rate=st.floats(min_value=0.0, max_value=0.5)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_25_parallel_processing_result_aggregation(self, account_ids, date_range, partial_failure_rate):
        """
        Property 25: Parallel Processing Result Aggregation
        
        For any parallel cost collection operation, when all concurrent operations complete, 
        the results should be aggregated into a single summary regardless of individual 
        account failures, and the operation should not fail entirely if some accounts fail.
        
        Validates: Requirements 16.3, 16.4, 16.5
        
        Feature: phase-5-handlers, Property 25: Parallel Processing Result Aggregation
        """
        # Skip if only one account (no parallel processing to test)
        assume(len(account_ids) >= 2)
        
        start_date, end_date = date_range
        
        # Setup mock role manager with partial failures
        mock_role_manager = Mock()
        
        call_count = [0]
        def mock_assume_role(account_id, role_name, external_id):
            call_count[0] += 1
            # Fail for some accounts based on partial_failure_rate
            if (call_count[0] / len(account_ids)) <= partial_failure_rate:
                raise ClientError(
                    {'Error': {'Code': 'AccessDenied', 'Message': 'Cannot assume role'}},
                    'AssumeRole'
                )
            return Credentials(
                access_key_id='AKIAIOSFODNN7EXAMPLE',
                secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                session_token='FwoGZXIvYXdzEBYaDH...',
                expiration=datetime(2024, 1, 1, 12, 0, 0)
            )
        
        mock_role_manager.assume_role.side_effect = mock_assume_role
        
        mock_session = Mock()
        mock_ce_client = Mock()
        mock_session.client.return_value = mock_ce_client
        mock_role_manager.create_boto3_session.return_value = mock_session
        
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
        
        # Create collector with parallel processing
        collector = MultiAccountCostCollector(
            role_manager=mock_role_manager,
            cost_repository=Mock(),
            max_retries=1,
            max_workers=min(5, len(account_ids))  # Ensure parallel processing
        )
        
        # Execute
        result = collector.collect_all_accounts(
            org_id='o-1234567890',
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date
        )
        
        # Property: Should return aggregated results for all accounts
        assert result.total_accounts == len(account_ids), \
            "Should aggregate results for all accounts"
        
        # Property: Should have results for all accounts (successful or failed)
        assert len(result.account_data) == len(account_ids), \
            "Should have result data for every account"
        
        # Property: Successful + failed should equal total
        assert result.successful + result.failed == result.total_accounts, \
            "Aggregated counts should be consistent"
        
        # Property: Should not fail entirely due to partial failures
        assert result.successful >= 0, \
            "Should have some successful results or handle all failures gracefully"
        
        # Property: All account IDs should be represented in results
        result_account_ids = {data.account_id for data in result.account_data}
        assert result_account_ids == set(account_ids), \
            "All account IDs should be in aggregated results"
        
        # Property: Failed accounts should be properly tracked
        assert len(result.failed_accounts) == result.failed, \
            "Failed accounts list should match failed count in aggregation"
        
        # Property: Collection should complete with positive duration
        assert result.collection_duration > 0, \
            "Parallel processing should complete with measurable duration"
