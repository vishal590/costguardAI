"""
Property-Based Tests for Environment Configuration

Tests Property 22: Environment Configuration Reading
Tests Property 23: Manual Trigger Parameter Support

Property 22: For any handler execution, if a required environment variable is missing,
then the handler should log an error and return a 500 status code.

Property 23: For any manual invocation with custom parameters, the collector should use
the provided parameters instead of defaults; if account_ids is provided, only those accounts
should be processed; if not provided, all accounts should be discovered and processed.

Validates: Requirements 12.1-12.7, 15.1-15.6
"""

import json
import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from datetime import date, timedelta

from src.multi_account_cost_collector_handler import lambda_handler, manual_trigger_handler


@given(
    has_org_id=st.booleans(),
    has_external_id=st.booleans(),
    days_to_collect=st.integers(min_value=1, max_value=30)
)
@settings(max_examples=30, deadline=5000)
def test_property_22_environment_configuration_reading(has_org_id, has_external_id, days_to_collect):
    """
    Property 22: Environment Configuration Reading
    
    For any handler execution, if a required environment variable (ORGANIZATION_ID)
    is missing, then the handler should log an error and return a 500 status code.
    
    Feature: phase-5-handlers, Property 22: Environment Configuration Reading
    **Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5, 15.6**
    """
    # Create EventBridge event
    event = {
        'source': 'aws.events',
        'detail-type': 'Scheduled Event'
    }
    
    # Set up environment variables
    env_vars = {
        'DAYS_TO_COLLECT': str(days_to_collect),
        'LOG_LEVEL': 'INFO'
    }
    
    if has_org_id:
        env_vars['ORGANIZATION_ID'] = 'o-test123456'
    
    if has_external_id:
        env_vars['EXTERNAL_ID'] = 'test-external-id'
    
    with patch.dict('os.environ', env_vars, clear=True):
        if not has_org_id:
            # Should fail with missing ORGANIZATION_ID
            response = lambda_handler(event, {})
            
            # Verify error response
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert 'error' in body
            assert 'ORGANIZATION_ID' in body['message'] or 'required' in body['message'].lower()
        else:
            # Should succeed (with mocked services)
            with patch('src.multi_account_cost_collector_handler.OrganizationDiscoveryService') as mock_discovery:
                mock_org_service = Mock()
                mock_discovery.return_value = mock_org_service
                
                # Create mock organization data
                mock_org_data = Mock()
                mock_org_data.accounts = [Mock(id='account-1'), Mock(id='account-2')]
                mock_org_service.discover_organization.return_value = mock_org_data
                
                with patch('src.multi_account_cost_collector_handler.MultiAccountCostCollector') as mock_collector_class:
                    mock_collector = Mock()
                    mock_collector_class.return_value = mock_collector
                    
                    # Create mock collection result
                    mock_result = Mock()
                    mock_result.total_accounts = 2
                    mock_result.successful = 2
                    mock_result.failed = 0
                    mock_result.failed_accounts = []
                    mock_result.collection_duration = 10.5
                    mock_result.account_data = [
                        Mock(total_cost=Decimal('100.00'), status='SUCCESS'),
                        Mock(total_cost=Decimal('200.00'), status='SUCCESS')
                    ]
                    
                    mock_collector.collect_all_accounts.return_value = mock_result
                    
                    # Call handler
                    response = lambda_handler(event, {})
                    
                    # Verify success response
                    assert response['statusCode'] in [200, 207]
                    body = json.loads(response['body'])
                    assert 'summary' in body
                    
                    # Verify days_to_collect was used
                    call_args = mock_collector.collect_all_accounts.call_args
                    start_date = call_args[1]['start_date']
                    end_date = call_args[1]['end_date']
                    
                    # Verify date range matches days_to_collect
                    date_diff = (end_date - start_date).days
                    assert date_diff == days_to_collect


@given(
    provide_org_id=st.booleans(),
    provide_account_ids=st.booleans(),
    provide_dates=st.booleans(),
    account_count=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=30, deadline=5000)
def test_property_23_manual_trigger_parameter_support(provide_org_id, provide_account_ids, 
                                                      provide_dates, account_count):
    """
    Property 23: Manual Trigger Parameter Support
    
    For any manual invocation with custom parameters, the collector should use
    the provided parameters instead of defaults; if account_ids is provided, only
    those accounts should be processed; if not provided, all accounts should be
    discovered and processed.
    
    Feature: phase-5-handlers, Property 23: Manual Trigger Parameter Support
    **Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7**
    """
    # Create manual trigger event
    event = {}
    
    if provide_org_id:
        event['org_id'] = 'o-manual123456'
    
    if provide_account_ids:
        event['account_ids'] = [f'account-{i}' for i in range(account_count)]
    
    if provide_dates:
        event['start_date'] = '2024-01-01'
        event['end_date'] = '2024-01-31'
    
    # Set up environment variables (fallback values)
    env_vars = {
        'ORGANIZATION_ID': 'o-env123456',
        'EXTERNAL_ID': 'test-external-id',
        'DAYS_TO_COLLECT': '7',
        'LOG_LEVEL': 'INFO'
    }
    
    with patch.dict('os.environ', env_vars):
        with patch('src.multi_account_cost_collector_handler.OrganizationDiscoveryService') as mock_discovery:
            mock_org_service = Mock()
            mock_discovery.return_value = mock_org_service
            
            # Create mock organization data (for discovery path)
            mock_org_data = Mock()
            mock_org_data.accounts = [Mock(id=f'discovered-{i}') for i in range(5)]
            mock_org_service.discover_organization.return_value = mock_org_data
            
            with patch('src.multi_account_cost_collector_handler.MultiAccountCostCollector') as mock_collector_class:
                mock_collector = Mock()
                mock_collector_class.return_value = mock_collector
                
                # Create mock collection result
                expected_count = account_count if provide_account_ids else 5
                mock_result = Mock()
                mock_result.total_accounts = expected_count
                mock_result.successful = expected_count
                mock_result.failed = 0
                mock_result.failed_accounts = []
                mock_result.collection_duration = 15.0
                mock_result.account_data = [
                    Mock(total_cost=Decimal('100.00'), status='SUCCESS')
                    for _ in range(expected_count)
                ]
                
                mock_collector.collect_all_accounts.return_value = mock_result
                
                # Call manual trigger handler
                response = manual_trigger_handler(event, {})
                
                # Verify response
                assert response['statusCode'] == 200
                body = json.loads(response['body'])
                assert 'summary' in body
                
                # Verify collector was called
                assert mock_collector.collect_all_accounts.called
                call_args = mock_collector.collect_all_accounts.call_args
                
                # Verify org_id parameter
                if provide_org_id:
                    assert call_args[1]['org_id'] == 'o-manual123456'
                else:
                    assert call_args[1]['org_id'] == 'o-env123456'
                
                # Verify account_ids parameter
                if provide_account_ids:
                    # Should use provided account IDs
                    assert call_args[1]['account_ids'] == event['account_ids']
                    # Discovery should not be called
                    assert not mock_org_service.discover_organization.called
                else:
                    # Should discover accounts
                    assert mock_org_service.discover_organization.called
                    # Should use discovered account IDs
                    assert len(call_args[1]['account_ids']) == 5
                
                # Verify date parameters
                if provide_dates:
                    assert call_args[1]['start_date'] == date(2024, 1, 1)
                    assert call_args[1]['end_date'] == date(2024, 1, 31)
                else:
                    # Should use default (last 7 days)
                    start_date = call_args[1]['start_date']
                    end_date = call_args[1]['end_date']
                    assert (end_date - start_date).days == 7


@given(
    org_id=st.text(alphabet=st.characters(blacklist_characters='\x00'), min_size=10, max_size=20),
    external_id=st.text(alphabet=st.characters(blacklist_characters='\x00'), min_size=10, max_size=30),
    days=st.integers(min_value=1, max_value=90)
)
@settings(max_examples=20, deadline=3000)
def test_property_22_environment_variable_values(org_id, external_id, days):
    """
    Property 22: Environment Configuration Reading (Values)
    
    Handler should correctly read and use environment variable values.
    
    Feature: phase-5-handlers, Property 22: Environment Configuration Reading
    **Validates: Requirements 15.1, 15.2, 15.3**
    """
    event = {
        'source': 'aws.events',
        'detail-type': 'Scheduled Event'
    }
    
    env_vars = {
        'ORGANIZATION_ID': org_id,
        'EXTERNAL_ID': external_id,
        'DAYS_TO_COLLECT': str(days),
        'LOG_LEVEL': 'INFO'
    }
    
    with patch.dict('os.environ', env_vars):
        with patch('src.multi_account_cost_collector_handler.OrganizationDiscoveryService') as mock_discovery:
            mock_org_service = Mock()
            mock_discovery.return_value = mock_org_service
            
            mock_org_data = Mock()
            mock_org_data.accounts = [Mock(id='test-account')]
            mock_org_service.discover_organization.return_value = mock_org_data
            
            with patch('src.multi_account_cost_collector_handler.MultiAccountCostCollector') as mock_collector_class:
                mock_collector = Mock()
                mock_collector_class.return_value = mock_collector
                
                mock_result = Mock()
                mock_result.total_accounts = 1
                mock_result.successful = 1
                mock_result.failed = 0
                mock_result.failed_accounts = []
                mock_result.collection_duration = 5.0
                mock_result.account_data = [Mock(total_cost=Decimal('50.00'), status='SUCCESS')]
                
                mock_collector.collect_all_accounts.return_value = mock_result
                
                # Call handler
                response = lambda_handler(event, {})
                
                # Verify success
                assert response['statusCode'] in [200, 207]
                
                # Verify collector was called with correct org_id
                call_args = mock_collector.collect_all_accounts.call_args
                assert call_args[1]['org_id'] == org_id
                
                # Verify date range matches days
                start_date = call_args[1]['start_date']
                end_date = call_args[1]['end_date']
                assert (end_date - start_date).days == days


@given(
    selective_accounts=st.lists(
        st.text(alphabet=st.characters(whitelist_categories=('Nd',)), min_size=12, max_size=12),
        min_size=1,
        max_size=5
    ),
    start_date_str=st.dates(min_value=date(2024, 1, 1), max_value=date(2024, 12, 31)).map(lambda d: d.isoformat()),
    end_date_str=st.dates(min_value=date(2024, 1, 1), max_value=date(2024, 12, 31)).map(lambda d: d.isoformat())
)
@settings(max_examples=20, deadline=3000)
def test_property_23_selective_account_processing(selective_accounts, start_date_str, end_date_str):
    """
    Property 23: Manual Trigger Parameter Support (Selective Processing)
    
    When account_ids is provided in manual trigger, only those accounts should be processed.
    
    Feature: phase-5-handlers, Property 23: Manual Trigger Parameter Support
    **Validates: Requirements 12.6, 12.7**
    """
    # Ensure start_date <= end_date
    start_date = date.fromisoformat(start_date_str)
    end_date = date.fromisoformat(end_date_str)
    if start_date > end_date:
        start_date, end_date = end_date, start_date
        start_date_str, end_date_str = end_date_str, start_date_str
    
    # Create manual trigger event with selective accounts
    event = {
        'org_id': 'o-selective123',
        'account_ids': selective_accounts,
        'start_date': start_date_str,
        'end_date': end_date_str
    }
    
    env_vars = {
        'ORGANIZATION_ID': 'o-env123456',
        'EXTERNAL_ID': 'test-external-id',
        'LOG_LEVEL': 'INFO'
    }
    
    with patch.dict('os.environ', env_vars):
        with patch('src.multi_account_cost_collector_handler.OrganizationDiscoveryService') as mock_discovery:
            mock_org_service = Mock()
            mock_discovery.return_value = mock_org_service
            
            with patch('src.multi_account_cost_collector_handler.MultiAccountCostCollector') as mock_collector_class:
                mock_collector = Mock()
                mock_collector_class.return_value = mock_collector
                
                mock_result = Mock()
                mock_result.total_accounts = len(selective_accounts)
                mock_result.successful = len(selective_accounts)
                mock_result.failed = 0
                mock_result.failed_accounts = []
                mock_result.collection_duration = 10.0
                mock_result.account_data = [
                    Mock(total_cost=Decimal('100.00'), status='SUCCESS')
                    for _ in selective_accounts
                ]
                
                mock_collector.collect_all_accounts.return_value = mock_result
                
                # Call manual trigger handler
                response = manual_trigger_handler(event, {})
                
                # Verify success
                assert response['statusCode'] == 200
                
                # Verify discovery was NOT called (selective processing)
                assert not mock_org_service.discover_organization.called
                
                # Verify collector was called with exact account list
                call_args = mock_collector.collect_all_accounts.call_args
                assert call_args[1]['account_ids'] == selective_accounts
                
                # Verify dates were used
                assert call_args[1]['start_date'] == start_date
                assert call_args[1]['end_date'] == end_date
