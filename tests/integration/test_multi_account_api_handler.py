"""
Integration tests for Multi-Account API Handler.

Tests all API endpoints with authentication and error handling.
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, UTC

from src.multi_account_api_handler import handler
from src.services.multi_account.models import (
    Organization, Account, AggregatedCosts, AccountCostData, 
    AllocationResult, AllocationRule
)
from src.services.multi_account.per_account_cost_service import AccountCostBreakdown


class TestMultiAccountAPIHandler:
    """Integration tests for multi-account API endpoints."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.valid_api_key = "cg_test_api_key_12345678901234567890"
        self.valid_headers = {
            'X-API-Key': self.valid_api_key,
            'Content-Type': 'application/json'
        }
        
        # Mock user context
        self.user_context = {
            'api_key_id': 'key_123',
            'user_id': 'test_user',
            'permissions': ['read', 'write'],
            'rate_limit': 100
        }
    
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    @patch('src.multi_account_api_handler._get_organization_service')
    def test_list_organizations_success(self, mock_get_org_service, mock_auth):
        """Test GET /api/organizations endpoint success."""
        # Setup mocks
        mock_auth.return_value = (True, None, self.user_context)
        
        mock_org_service = Mock()
        mock_organization = Organization(
            id='o-123456789',
            arn='arn:aws:organizations::123456789012:organization/o-123456789',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        mock_org_service.discover_organization.return_value = mock_organization
        mock_get_org_service.return_value = mock_org_service
        
        # Create event
        event = {
            'httpMethod': 'GET',
            'path': '/api/organizations',
            'headers': self.valid_headers,
            'queryStringParameters': None
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        assert len(body['organizations']) == 1
        assert body['organizations'][0]['organization_id'] == 'o-123456789'
        assert body['count'] == 1
        
        # Verify service calls
        mock_auth.assert_called_once_with(event)
        mock_org_service.discover_organization.assert_called_once()
    
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    @patch('src.multi_account_api_handler._get_organization_service')
    def test_list_accounts_success(self, mock_get_org_service, mock_auth):
        """Test GET /api/organizations/{org_id}/accounts endpoint success."""
        # Setup mocks
        mock_auth.return_value = (True, None, self.user_context)
        
        mock_org_service = Mock()
        mock_accounts = [
            Account(
                id='123456789012',
                arn='arn:aws:organizations::123456789012:account/o-123456789/123456789012',
                name='Production',
                email='prod@example.com',
                status='ACTIVE',
                joined_method='CREATED',
                joined_timestamp=datetime.now(UTC)
            ),
            Account(
                id='123456789013',
                arn='arn:aws:organizations::123456789012:account/o-123456789/123456789013',
                name='Development',
                email='dev@example.com',
                status='ACTIVE',
                joined_method='INVITED',
                joined_timestamp=datetime.now(UTC)
            )
        ]
        mock_org_service.get_all_accounts.return_value = mock_accounts
        mock_get_org_service.return_value = mock_org_service
        
        # Create event
        event = {
            'httpMethod': 'GET',
            'path': '/api/organizations/o-123456789/accounts',
            'headers': self.valid_headers,
            'queryStringParameters': None
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        assert len(body['accounts']) == 2
        assert body['organization_id'] == 'o-123456789'
        assert body['count'] == 2
        
        # Verify service calls
        mock_auth.assert_called_once_with(event)
        mock_org_service.get_all_accounts.assert_called_once()
    
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    @patch('src.multi_account_api_handler._get_cost_aggregation_engine')
    @patch('src.multi_account_api_handler._get_organization_service')
    def test_consolidated_costs_success(self, mock_get_org_service, mock_get_aggregation_engine, mock_auth):
        """Test GET /api/costs/consolidated endpoint success."""
        # Setup mocks
        mock_auth.return_value = (True, None, self.user_context)
        
        # Mock organization service
        mock_org_service = Mock()
        mock_organization = Organization(
            id='o-123456789',
            arn='arn:aws:organizations::123456789012:organization/o-123456789',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        mock_accounts = [
            Account(
                id='123456789012',
                arn='arn:aws:organizations::123456789012:account/o-123456789/123456789012',
                name='Production',
                email='prod@example.com',
                status='ACTIVE',
                joined_method='CREATED',
                joined_timestamp=datetime.now(UTC)
            ),
            Account(
                id='123456789013',
                arn='arn:aws:organizations::123456789012:account/o-123456789/123456789013',
                name='Development',
                email='dev@example.com',
                status='ACTIVE',
                joined_method='INVITED',
                joined_timestamp=datetime.now(UTC)
            )
        ]
        mock_org_service.discover_organization.return_value = mock_organization
        mock_org_service.get_all_accounts.return_value = mock_accounts
        mock_get_org_service.return_value = mock_org_service
        
        mock_aggregation_engine = Mock()
        mock_consolidated_costs = AggregatedCosts(
            entity_id='o-123456789',
            entity_type='ORGANIZATION',
            start_date='2024-01-01',
            end_date='2024-01-31',
            total_cost=Decimal('1500.00'),
            account_count=2,
            costs_by_account={'123456789012': Decimal('900.00'), '123456789013': Decimal('600.00')},
            costs_by_service={'EC2': Decimal('800.00'), 'S3': Decimal('700.00')},
            costs_by_day={'2024-01-01': Decimal('50.00'), '2024-01-02': Decimal('48.00')}
        )
        mock_aggregation_engine.aggregate_organization_costs.return_value = mock_consolidated_costs
        mock_get_aggregation_engine.return_value = mock_aggregation_engine
        
        # Create event
        event = {
            'httpMethod': 'GET',
            'path': '/api/costs/consolidated',
            'headers': self.valid_headers,
            'queryStringParameters': {
                'start_date': '2024-01-01',
                'end_date': '2024-01-31',
                'granularity': 'MONTHLY'
            }
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        assert body['consolidated_costs']['total_cost'] == 1500.0
        assert body['consolidated_costs']['period_start'] == '2024-01-01'
        assert body['consolidated_costs']['period_end'] == '2024-01-31'
        assert len(body['consolidated_costs']['by_service']) == 2
        assert len(body['consolidated_costs']['by_account']) == 2
        
        # Verify service calls
        mock_auth.assert_called_once_with(event)
        mock_org_service.discover_organization.assert_called_once()
        mock_org_service.get_all_accounts.assert_called_once_with('o-123456789')
        mock_aggregation_engine.aggregate_organization_costs.assert_called_once_with(
            org_id='o-123456789',
            account_ids=['123456789012', '123456789013'],
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
    
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    @patch('src.multi_account_api_handler._get_per_account_cost_service')
    @patch('src.multi_account_api_handler._get_organization_service')
    def test_costs_by_account_success(self, mock_get_org_service, mock_get_per_account_service, mock_auth):
        """Test GET /api/costs/by-account endpoint success."""
        # Setup mocks
        mock_auth.return_value = (True, None, self.user_context)
        
        # Mock organization service
        mock_org_service = Mock()
        mock_accounts = [
            Account(
                id='123456789012',
                arn='arn:aws:organizations::123456789012:account/o-example123456/123456789012',
                name='Production',
                email='prod@example.com',
                status='ACTIVE',
                joined_method='CREATED',
                joined_timestamp=datetime.now(UTC)
            )
        ]
        mock_org_service.get_all_accounts.return_value = mock_accounts
        mock_get_org_service.return_value = mock_org_service
        
        # Mock per-account service
        mock_per_account_service = Mock()
        mock_account_costs = AccountCostBreakdown(
            account_id='123456789012',
            account_name='Production',
            start_date='2024-01-01',
            end_date='2024-01-31',
            total_cost=Decimal('900.00'),
            costs_by_service={'EC2': Decimal('500.00'), 'S3': Decimal('400.00')},
            costs_by_day={'2024-01-01': Decimal('30.00'), '2024-01-02': Decimal('29.00')},
            top_services=[('EC2', Decimal('500.00')), ('S3', Decimal('400.00'))]
        )
        mock_per_account_service.get_account_costs.return_value = mock_account_costs
        mock_get_per_account_service.return_value = mock_per_account_service
        
        # Create event
        event = {
            'httpMethod': 'GET',
            'path': '/api/costs/by-account',
            'headers': self.valid_headers,
            'queryStringParameters': {
                'start_date': '2024-01-01',
                'end_date': '2024-01-31'
            }
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        assert len(body['account_costs']) == 1
        assert body['account_costs'][0]['account_id'] == '123456789012'
        assert body['account_costs'][0]['total_cost'] == 900.0
        assert body['count'] == 1
        
        # Verify service calls
        mock_auth.assert_called_once_with(event)
        mock_org_service.get_all_accounts.assert_called_once()
        mock_per_account_service.get_account_costs.assert_called_once_with(
            account_id='123456789012',
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
    
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    @patch('src.multi_account_api_handler._get_per_account_cost_service')
    def test_account_costs_success(self, mock_get_per_account_service, mock_auth):
        """Test GET /api/costs/account/{account_id} endpoint success."""
        # Setup mocks
        mock_auth.return_value = (True, None, self.user_context)
        
        mock_per_account_service = Mock()
        mock_account_costs = AccountCostBreakdown(
            account_id='123456789012',
            account_name='Production',
            start_date='2024-01-01',
            end_date='2024-01-31',
            total_cost=Decimal('900.00'),
            costs_by_service={'EC2': Decimal('500.00'), 'S3': Decimal('400.00')},
            costs_by_day={'2024-01-01': Decimal('30.00'), '2024-01-02': Decimal('29.00')},
            top_services=[('EC2', Decimal('500.00')), ('S3', Decimal('400.00'))]
        )
        mock_per_account_service.get_account_costs.return_value = mock_account_costs
        mock_get_per_account_service.return_value = mock_per_account_service
        
        # Create event
        event = {
            'httpMethod': 'GET',
            'path': '/api/costs/account/123456789012',
            'headers': self.valid_headers,
            'queryStringParameters': {
                'start_date': '2024-01-01',
                'end_date': '2024-01-31'
            }
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        assert body['account_id'] == '123456789012'
        assert body['costs']['total_cost'] == 900.0
        assert body['costs']['currency'] == 'USD'
        assert len(body['costs']['by_service']) == 2
        
        # Verify service calls
        mock_auth.assert_called_once_with(event)
        mock_per_account_service.get_account_costs.assert_called_once_with(
            account_id='123456789012',
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
    
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    @patch('src.multi_account_api_handler._get_cost_allocation_engine')
    @patch('src.multi_account_api_handler._get_organization_service')
    def test_allocation_by_tag_success(self, mock_get_org_service, mock_get_allocation_engine, mock_auth):
        """Test GET /api/allocation/by-tag endpoint success."""
        # Setup mocks
        mock_auth.return_value = (True, None, self.user_context)
        
        # Mock organization service
        mock_org_service = Mock()
        mock_organization = Organization(
            id='o-123456789',
            arn='arn:aws:organizations::123456789012:organization/o-123456789',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        mock_accounts = [
            Account(
                id='123456789012',
                arn='arn:aws:organizations::123456789012:account/o-123456789/123456789012',
                name='Production',
                email='prod@example.com',
                status='ACTIVE',
                joined_method='CREATED',
                joined_timestamp=datetime.now(UTC)
            )
        ]
        mock_org_service.discover_organization.return_value = mock_organization
        mock_org_service.get_all_accounts.return_value = mock_accounts
        mock_get_org_service.return_value = mock_org_service
        
        mock_allocation_engine = Mock()
        mock_team_costs = {
            'frontend': Decimal('600.00'),
            'backend': Decimal('900.00')
        }
        mock_allocation_engine.get_allocation_by_team.return_value = mock_team_costs
        mock_get_allocation_engine.return_value = mock_allocation_engine
        
        # Create event
        event = {
            'httpMethod': 'GET',
            'path': '/api/allocation/by-tag',
            'headers': self.valid_headers,
            'queryStringParameters': {
                'tag_key': 'Team',
                'start_date': '2024-01-01',
                'end_date': '2024-01-31'
            }
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        assert body['tag_key'] == 'Team'
        assert len(body['allocated_costs']) == 2
        assert body['allocated_costs']['frontend']['total_cost'] == 600.0
        assert body['allocated_costs']['backend']['total_cost'] == 900.0
        
        # Verify service calls
        mock_auth.assert_called_once_with(event)
        mock_org_service.discover_organization.assert_called_once()
        mock_org_service.get_all_accounts.assert_called_once_with('o-123456789')
        mock_allocation_engine.get_allocation_by_team.assert_called_once_with(
            org_id='o-123456789',
            account_ids=['123456789012'],
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
    
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    @patch('src.multi_account_api_handler._get_allocation_rules_engine')
    @patch('src.multi_account_api_handler._get_organization_service')
    def test_create_allocation_rule_success(self, mock_get_org_service, mock_get_rules_engine, mock_auth):
        """Test POST /api/allocation/rules endpoint success."""
        # Setup mocks
        mock_auth.return_value = (True, None, self.user_context)
        
        # Mock organization service
        mock_org_service = Mock()
        mock_organization = Organization(
            id='o-123456789',
            arn='arn:aws:organizations::123456789012:organization/o-123456789',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        mock_org_service.discover_organization.return_value = mock_organization
        mock_get_org_service.return_value = mock_org_service
        
        mock_rules_engine = Mock()
        mock_rule = AllocationRule(
            rule_id='rule_123',
            name='VPC Cost Split',
            priority=100,
            rule_type='percentage',
            conditions={'service': 'VPC'},
            allocation_target='infrastructure'
        )
        mock_rules_engine.create_rule.return_value = mock_rule
        mock_get_rules_engine.return_value = mock_rules_engine
        
        # Create event
        event = {
            'httpMethod': 'POST',
            'path': '/api/allocation/rules',
            'headers': self.valid_headers,
            'body': json.dumps({
                'rule_name': 'VPC Cost Split',
                'rule_type': 'percentage',
                'conditions': {'service': 'VPC'},
                'allocation_target': 'infrastructure',
                'priority': 100
            })
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 201
        body = json.loads(response['body'])
        assert body['success'] is True
        assert body['rule']['rule_id'] == 'rule_123'
        assert body['rule']['rule_name'] == 'VPC Cost Split'
        assert body['rule']['rule_type'] == 'percentage'
        assert body['message'] == 'Allocation rule created successfully'
        
        # Verify service calls
        mock_auth.assert_called_once_with(event)
        mock_org_service.discover_organization.assert_called_once()
        mock_rules_engine.create_rule.assert_called_once_with(
            org_id='o-123456789',
            name='VPC Cost Split',
            priority=100,
            rule_type='percentage',
            conditions={'service': 'VPC'},
            allocation_target='infrastructure'
        )
    
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    def test_authentication_failure(self, mock_auth):
        """Test authentication failure."""
        # Setup mock to return authentication failure
        mock_auth.return_value = (False, 'Invalid API key', None)
        
        # Create event without API key
        event = {
            'httpMethod': 'GET',
            'path': '/api/organizations',
            'headers': {},
            'queryStringParameters': None
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert body['success'] is False
        assert body['error']['code'] == 'AUTHENTICATION_FAILED'
        assert 'Invalid API key' in body['error']['message']
        
        # Verify auth was called
        mock_auth.assert_called_once_with(event)
    
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    def test_rate_limit_exceeded(self, mock_auth):
        """Test rate limit exceeded."""
        # Setup mock to return rate limit exceeded
        mock_auth.return_value = (False, 'Rate limit exceeded. Maximum 100 requests per minute.', self.user_context)
        
        # Create event
        event = {
            'httpMethod': 'GET',
            'path': '/api/organizations',
            'headers': self.valid_headers,
            'queryStringParameters': None
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 429
        body = json.loads(response['body'])
        assert body['success'] is False
        assert body['error']['code'] == 'RATE_LIMIT_EXCEEDED'
        assert 'Rate limit exceeded' in body['error']['message']
        
        # Verify auth was called
        mock_auth.assert_called_once_with(event)
    
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    def test_invalid_endpoint(self, mock_auth):
        """Test invalid endpoint."""
        # Setup mocks
        mock_auth.return_value = (True, None, self.user_context)
        
        # Create event with invalid path
        event = {
            'httpMethod': 'GET',
            'path': '/api/invalid/endpoint',
            'headers': self.valid_headers,
            'queryStringParameters': None
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False
        assert body['error']['code'] == 'INVALID_REQUEST'
        assert 'Unsupported method' in body['error']['message']
        
        # Verify auth was called
        mock_auth.assert_called_once_with(event)
    
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    def test_invalid_date_format(self, mock_auth):
        """Test invalid date format in query parameters."""
        # Setup mocks
        mock_auth.return_value = (True, None, self.user_context)
        
        # Create event with invalid date format
        event = {
            'httpMethod': 'GET',
            'path': '/api/costs/consolidated',
            'headers': self.valid_headers,
            'queryStringParameters': {
                'start_date': 'invalid-date',
                'end_date': '2024-01-31'
            }
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False
        assert body['error']['code'] == 'INVALID_DATE_FORMAT'
        assert 'Invalid start date format' in body['error']['message']
        
        # Verify auth was called
        mock_auth.assert_called_once_with(event)
    
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    def test_missing_required_parameter(self, mock_auth):
        """Test missing required parameter in POST request."""
        # Setup mocks
        mock_auth.return_value = (True, None, self.user_context)
        
        # Create event with missing required parameter
        event = {
            'httpMethod': 'POST',
            'path': '/api/allocation/rules',
            'headers': self.valid_headers,
            'body': json.dumps({
                'rule_type': 'percentage',
                'conditions': {'service': 'VPC'}
                # Missing rule_name
            })
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False
        assert body['error']['code'] == 'MISSING_PARAMETER'
        assert 'rule_name is required' in body['error']['message']
        
        # Verify auth was called
        mock_auth.assert_called_once_with(event)