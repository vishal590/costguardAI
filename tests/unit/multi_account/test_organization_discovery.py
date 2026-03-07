"""
Unit tests for Organization Discovery Service
"""
import os
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from botocore.exceptions import ClientError

from src.services.multi_account.organization_discovery import OrganizationDiscoveryService
from src.services.multi_account.models import Organization, Account, OUHierarchy


class TestOrganizationDiscoveryService:
    """Test suite for OrganizationDiscoveryService"""
    
    @pytest.fixture
    def mock_dynamodb(self):
        """Mock DynamoDB client"""
        return Mock()
    
    @pytest.fixture
    def mock_organizations(self):
        """Mock Organizations client"""
        return Mock()
    
    @pytest.fixture
    def service(self, mock_dynamodb, mock_organizations):
        """Create service instance with mocked clients"""
        return OrganizationDiscoveryService(
            dynamodb_client=mock_dynamodb,
            organizations_client=mock_organizations
        )
    
    def test_discover_organization_success(self, service, mock_organizations, mock_dynamodb):
        """Test successful organization discovery"""
        # Mock Organizations API response
        mock_organizations.describe_organization.return_value = {
            'Organization': {
                'Id': 'o-123456789',
                'Arn': 'arn:aws:organizations::123456789012:organization/o-123456789',
                'MasterAccountId': '123456789012',
                'FeatureSet': 'ALL'
            }
        }
        
        # Mock DynamoDB put_item
        mock_dynamodb.put_item.return_value = {}
        
        # Execute
        result = service.discover_organization()
        
        # Verify
        assert isinstance(result, Organization)
        assert result.id == 'o-123456789'
        assert result.master_account_id == '123456789012'
        assert result.feature_set == 'ALL'
        
        # Verify Organizations API was called
        mock_organizations.describe_organization.assert_called_once()
        
        # Verify caching was attempted
        mock_dynamodb.put_item.assert_called_once()
    
    def test_discover_organization_api_error(self, service, mock_organizations):
        """Test organization discovery with API error"""
        # Mock API error
        mock_organizations.describe_organization.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'DescribeOrganization'
        )
        
        # Execute and verify exception
        with pytest.raises(ClientError):
            service.discover_organization()
    
    def test_get_all_accounts_success(self, service, mock_organizations, mock_dynamodb):
        """Test successful account retrieval"""
        # Mock paginator
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {
                'Accounts': [
                    {
                        'Id': '111111111111',
                        'Arn': 'arn:aws:organizations::123456789012:account/o-123456789/111111111111',
                        'Name': 'Account 1',
                        'Email': 'account1@example.com',
                        'Status': 'ACTIVE',
                        'JoinedMethod': 'CREATED',
                        'JoinedTimestamp': datetime(2024, 1, 1)
                    },
                    {
                        'Id': '222222222222',
                        'Arn': 'arn:aws:organizations::123456789012:account/o-123456789/222222222222',
                        'Name': 'Account 2',
                        'Email': 'account2@example.com',
                        'Status': 'ACTIVE',
                        'JoinedMethod': 'INVITED',
                        'JoinedTimestamp': datetime(2024, 1, 2)
                    }
                ]
            }
        ]
        mock_organizations.get_paginator.return_value = mock_paginator
        
        # Mock DynamoDB
        mock_dynamodb.put_item.return_value = {}
        
        # Execute
        result = service.get_all_accounts('o-123456789')
        
        # Verify
        assert len(result) == 2
        assert all(isinstance(acc, Account) for acc in result)
        assert result[0].id == '111111111111'
        assert result[0].name == 'Account 1'
        assert result[1].id == '222222222222'
        assert result[1].name == 'Account 2'
        
        # Verify API was called
        mock_organizations.get_paginator.assert_called_once_with('list_accounts')
    
    def test_get_all_accounts_empty(self, service, mock_organizations, mock_dynamodb):
        """Test account retrieval with no accounts"""
        # Mock empty paginator
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{'Accounts': []}]
        mock_organizations.get_paginator.return_value = mock_paginator
        
        # Execute
        result = service.get_all_accounts('o-123456789')
        
        # Verify
        assert len(result) == 0
    
    def test_get_ou_hierarchy_success(self, service, mock_organizations):
        """Test successful OU hierarchy retrieval"""
        # Mock list_roots
        mock_organizations.list_roots.return_value = {
            'Roots': [{'Id': 'r-root123'}]
        }
        
        # Track which parent IDs have been queried to avoid infinite recursion
        queried_parents = set()
        
        # Mock OU paginator - return OUs only for root, empty for child OUs
        def ou_paginate_side_effect(ParentId):
            if ParentId in queried_parents:
                return [{'OrganizationalUnits': []}]
            queried_parents.add(ParentId)
            
            if ParentId == 'r-root123':
                return [
                    {
                        'OrganizationalUnits': [
                            {
                                'Id': 'ou-111',
                                'Arn': 'arn:aws:organizations::123456789012:ou/o-123456789/ou-111',
                                'Name': 'Production'
                            },
                            {
                                'Id': 'ou-222',
                                'Arn': 'arn:aws:organizations::123456789012:ou/o-123456789/ou-222',
                                'Name': 'Development'
                            }
                        ]
                    }
                ]
            else:
                return [{'OrganizationalUnits': []}]
        
        mock_ou_paginator = Mock()
        mock_ou_paginator.paginate.side_effect = ou_paginate_side_effect
        
        # Mock account paginator
        mock_account_paginator = Mock()
        mock_account_paginator.paginate.return_value = [
            {
                'Accounts': [
                    {'Id': '111111111111'},
                    {'Id': '222222222222'}
                ]
            }
        ]
        
        # Setup get_paginator to return appropriate paginator
        def get_paginator_side_effect(operation):
            if operation == 'list_organizational_units_for_parent':
                return mock_ou_paginator
            elif operation == 'list_accounts_for_parent':
                return mock_account_paginator
        
        mock_organizations.get_paginator.side_effect = get_paginator_side_effect
        
        # Execute
        result = service.get_ou_hierarchy('o-123456789')
        
        # Verify
        assert isinstance(result, OUHierarchy)
        assert result.root_id == 'r-root123'
        assert len(result.ous) == 2
        assert result.ous[0].name == 'Production'
        assert result.ous[1].name == 'Development'
        assert 'ou-111' in result.accounts_by_ou
        assert 'ou-222' in result.accounts_by_ou
    
    def test_refresh_organization_cache(self, service, mock_organizations, mock_dynamodb):
        """Test organization cache refresh"""
        # Mock describe_organization
        mock_organizations.describe_organization.return_value = {
            'Organization': {
                'Id': 'o-123456789',
                'Arn': 'arn:aws:organizations::123456789012:organization/o-123456789',
                'MasterAccountId': '123456789012',
                'FeatureSet': 'ALL'
            }
        }
        
        # Mock list_accounts paginator
        mock_account_paginator = Mock()
        mock_account_paginator.paginate.return_value = [
            {
                'Accounts': [
                    {
                        'Id': '111111111111',
                        'Arn': 'arn:aws:organizations::123456789012:account/o-123456789/111111111111',
                        'Name': 'Account 1',
                        'Email': 'account1@example.com',
                        'Status': 'ACTIVE',
                        'JoinedMethod': 'CREATED',
                        'JoinedTimestamp': datetime(2024, 1, 1)
                    }
                ]
            }
        ]
        
        # Mock list_roots
        mock_organizations.list_roots.return_value = {
            'Roots': [{'Id': 'r-root123'}]
        }
        
        # Mock OU paginator (empty)
        mock_ou_paginator = Mock()
        mock_ou_paginator.paginate.return_value = [{'OrganizationalUnits': []}]
        
        # Setup get_paginator
        def get_paginator_side_effect(operation):
            if operation == 'list_accounts':
                return mock_account_paginator
            elif operation == 'list_organizational_units_for_parent':
                return mock_ou_paginator
        
        mock_organizations.get_paginator.side_effect = get_paginator_side_effect
        
        # Mock DynamoDB
        mock_dynamodb.put_item.return_value = {}
        
        # Execute
        service.refresh_organization_cache('o-123456789')
        
        # Verify all discovery methods were called
        mock_organizations.describe_organization.assert_called()
        assert mock_organizations.get_paginator.call_count >= 1
        mock_organizations.list_roots.assert_called_once()
    
    def test_cache_organization_dynamodb_error(self, service, mock_organizations, mock_dynamodb):
        """Test organization discovery continues even if caching fails"""
        # Mock Organizations API
        mock_organizations.describe_organization.return_value = {
            'Organization': {
                'Id': 'o-123456789',
                'Arn': 'arn:aws:organizations::123456789012:organization/o-123456789',
                'MasterAccountId': '123456789012',
                'FeatureSet': 'ALL'
            }
        }
        
        # Mock DynamoDB error
        mock_dynamodb.put_item.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Table not found'}},
            'PutItem'
        )
        
        # Execute - should not raise exception
        result = service.discover_organization()
        
        # Verify organization was still discovered
        assert isinstance(result, Organization)
        assert result.id == 'o-123456789'
    
    def test_cache_ttl_from_environment_variable(self, mock_dynamodb, mock_organizations):
        """Test that cache_ttl_hours can be read from environment variable"""
        with patch.dict(os.environ, {'ORG_CACHE_TTL_HOURS': '12'}):
            service = OrganizationDiscoveryService(
                dynamodb_client=mock_dynamodb,
                organizations_client=mock_organizations
            )
            assert service.cache_ttl_hours == 12
    
    def test_cache_ttl_default_when_not_in_environment(self, mock_dynamodb, mock_organizations):
        """Test that cache_ttl_hours defaults to 24 when not in environment"""
        with patch.dict(os.environ, {}, clear=True):
            service = OrganizationDiscoveryService(
                dynamodb_client=mock_dynamodb,
                organizations_client=mock_organizations
            )
            assert service.cache_ttl_hours == 24
    
    def test_cache_ttl_explicit_override(self, mock_dynamodb, mock_organizations):
        """Test that explicitly passing cache_ttl_hours overrides environment variable"""
        with patch.dict(os.environ, {'ORG_CACHE_TTL_HOURS': '12'}):
            service = OrganizationDiscoveryService(
                dynamodb_client=mock_dynamodb,
                organizations_client=mock_organizations,
                cache_ttl_hours=18
            )
            assert service.cache_ttl_hours == 18
