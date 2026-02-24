"""
Property-based tests for Organization Discovery Service

Feature: multi-account-cost-management
"""
import pytest
from datetime import datetime
from unittest.mock import Mock
from hypothesis import given, strategies as st, settings
from decimal import Decimal

from src.services.multi_account.organization_discovery import OrganizationDiscoveryService
from src.services.multi_account.models import Account


# Custom strategies for generating test data
@st.composite
def account_data_strategy(draw):
    """Generate random account data"""
    account_id = draw(st.text(min_size=12, max_size=12, alphabet='0123456789'))
    return {
        'Id': account_id,
        'Arn': f'arn:aws:organizations::123456789012:account/o-123456789/{account_id}',
        'Name': draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))),
        'Email': f'{draw(st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=("Ll", "Nd"))))}@example.com',
        'Status': draw(st.sampled_from(['ACTIVE', 'SUSPENDED', 'PENDING_CLOSURE'])),
        'JoinedMethod': draw(st.sampled_from(['CREATED', 'INVITED'])),
        'JoinedTimestamp': datetime(2024, 1, 1)
    }


class TestOrganizationDiscoveryProperties:
    """Property-based tests for Organization Discovery Service"""
    
    @given(accounts=st.lists(account_data_strategy(), min_size=1, max_size=20, unique_by=lambda x: x['Id']))
    @settings(max_examples=20, deadline=None)
    def test_property_1_organization_discovery_completeness(self, accounts):
        """
        Property 1: Organization Discovery Completeness
        
        For any organization, when the system discovers the organization structure,
        all active accounts in the organization should be included in the discovered
        account list.
        
        Validates: Requirements 1.2
        
        Feature: multi-account-cost-management, Property 1: Organization Discovery Completeness
        """
        # Setup mocks
        mock_dynamodb = Mock()
        mock_dynamodb.put_item.return_value = {}
        
        mock_organizations = Mock()
        
        # Mock paginator to return generated accounts
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{'Accounts': accounts}]
        mock_organizations.get_paginator.return_value = mock_paginator
        
        # Create service
        service = OrganizationDiscoveryService(
            dynamodb_client=mock_dynamodb,
            organizations_client=mock_organizations
        )
        
        # Execute
        result = service.get_all_accounts('o-test123')
        
        # Property: All accounts from API should be in result
        assert len(result) == len(accounts), "All accounts should be discovered"
        
        # Property: No duplicate accounts
        result_ids = [acc.id for acc in result]
        assert len(result_ids) == len(set(result_ids)), "No duplicate accounts should exist"
        
        # Property: All account IDs from API should be in result
        api_account_ids = {acc['Id'] for acc in accounts}
        result_account_ids = {acc.id for acc in result}
        assert api_account_ids == result_account_ids, "All API account IDs should be in result"
        
        # Property: All accounts should be Account objects
        assert all(isinstance(acc, Account) for acc in result), "All results should be Account objects"
    
    @given(
        accounts=st.lists(account_data_strategy(), min_size=0, max_size=10, unique_by=lambda x: x['Id']),
        call_count=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=20, deadline=None)
    def test_property_discovery_idempotence(self, accounts, call_count):
        """
        Property: Discovery Idempotence
        
        For any organization, calling get_all_accounts multiple times should
        return the same results (idempotent operation).
        
        Validates: Requirements 1.2
        
        Feature: multi-account-cost-management, Property: Discovery Idempotence
        """
        # Setup mocks
        mock_dynamodb = Mock()
        mock_dynamodb.put_item.return_value = {}
        
        mock_organizations = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{'Accounts': accounts}]
        mock_organizations.get_paginator.return_value = mock_paginator
        
        # Create service
        service = OrganizationDiscoveryService(
            dynamodb_client=mock_dynamodb,
            organizations_client=mock_organizations
        )
        
        # Execute multiple times
        results = []
        for _ in range(call_count):
            result = service.get_all_accounts('o-test123')
            results.append(result)
        
        # Property: All calls should return same number of accounts
        result_lengths = [len(r) for r in results]
        assert all(length == result_lengths[0] for length in result_lengths), \
            "All calls should return same number of accounts"
        
        # Property: All calls should return same account IDs
        if len(accounts) > 0:
            first_ids = {acc.id for acc in results[0]}
            for result in results[1:]:
                result_ids = {acc.id for acc in result}
                assert first_ids == result_ids, "All calls should return same account IDs"
    
    @given(
        active_accounts=st.lists(account_data_strategy(), min_size=1, max_size=10, unique_by=lambda x: x['Id']),
        inactive_count=st.integers(min_value=0, max_value=5)
    )
    @settings(max_examples=20, deadline=None)
    def test_property_all_accounts_included(self, active_accounts, inactive_count):
        """
        Property: All Accounts Included
        
        For any organization with N accounts, the discovery should return exactly N accounts,
        regardless of their status (ACTIVE, SUSPENDED, etc.).
        
        Validates: Requirements 1.2
        
        Feature: multi-account-cost-management, Property: All Accounts Included
        """
        # Add some inactive accounts
        all_accounts = list(active_accounts)
        for i in range(inactive_count):
            inactive_account = {
                'Id': f'99999999{i:04d}',
                'Arn': f'arn:aws:organizations::123456789012:account/o-123456789/99999999{i:04d}',
                'Name': f'Inactive Account {i}',
                'Email': f'inactive{i}@example.com',
                'Status': 'SUSPENDED',
                'JoinedMethod': 'CREATED',
                'JoinedTimestamp': datetime(2024, 1, 1)
            }
            all_accounts.append(inactive_account)
        
        # Setup mocks
        mock_dynamodb = Mock()
        mock_dynamodb.put_item.return_value = {}
        
        mock_organizations = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{'Accounts': all_accounts}]
        mock_organizations.get_paginator.return_value = mock_paginator
        
        # Create service
        service = OrganizationDiscoveryService(
            dynamodb_client=mock_dynamodb,
            organizations_client=mock_organizations
        )
        
        # Execute
        result = service.get_all_accounts('o-test123')
        
        # Property: Should return all accounts regardless of status
        assert len(result) == len(all_accounts), \
            "Should return all accounts regardless of status"
        
        # Property: Should include both active and inactive accounts
        result_statuses = {acc.status for acc in result}
        api_statuses = {acc['Status'] for acc in all_accounts}
        assert result_statuses == api_statuses, \
            "Should preserve all account statuses"
