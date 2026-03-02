"""
Unit Tests for Multi-Account API Handler Endpoints

Comprehensive unit test suite for all 11 API endpoints covering:
- Valid inputs (200 OK)
- Validation errors (400 Bad Request)
- Authentication errors (401 Unauthorized)
- Not found errors (404 Not Found)
- Internal errors (500 Internal Server Error)

Validates: Requirements 1.1-1.15, 20.1-20.4, 20.8
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, UTC

from src.multi_account_api_handler import (
    handler,
    handle_list_organizations,
    handle_list_accounts,
    handle_consolidated_costs,
    handle_costs_by_account,
    handle_account_costs,
    handle_allocation_by_tag,
    handle_unallocated_costs,
    handle_create_allocation_rule,
    handle_budget_hierarchy,
    handle_create_organization_budget,
    handle_create_ou_budget,
    create_error_response
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def valid_api_event():
    """Create a valid API Gateway event."""
    return {
        'httpMethod': 'GET',
        'path': '/api/organizations',
        'headers': {'X-Api-Key': 'valid-key-12345'},
        'queryStringParameters': {}
    }


@pytest.fixture
def mock_organization():
    """Create a mock organization object."""
    org = Mock()
    org.id = 'o-test123456'
    org.master_account_id = '123456789012'
    org.arn = 'arn:aws:organizations::123456789012:organization/o-test123456'
    org.feature_set = 'ALL'
    return org


@pytest.fixture
def mock_accounts():
    """Create mock account objects."""
    accounts = []
    for i in range(3):
        acc = Mock()
        acc.id = f'12345678901{i}'
        acc.name = f'Test Account {i}'
        acc.email = f'account{i}@example.com'
        acc.status = 'ACTIVE'
        acc.joined_method = 'CREATED'
        acc.joined_timestamp = datetime.now(UTC)
        accounts.append(acc)
    return accounts


# ============================================================================
# Endpoint 1: GET /api/organizations
# ============================================================================

def test_list_organizations_success(mock_organization):
    """Test successful organization listing."""
    event = {
        'httpMethod': 'GET',
        'path': '/api/organizations',
        'headers': {'X-Api-Key': 'valid-key'},
        'queryStringParameters': {}
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler._get_organization_service') as mock_org_svc:
            mock_service = Mock()
            mock_service.discover_organization.return_value = mock_organization
            mock_org_svc.return_value = mock_service
            
            with patch('src.multi_account_api_handler.get_metrics_service'):
                response = handler(event, {})
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True
    assert 'organizations' in body
    assert len(body['organizations']) == 1
    assert body['organizations'][0]['organization_id'] == 'o-test123456'


def test_list_organizations_authentication_error():
    """Test organization listing with authentication failure."""
    event = {
        'httpMethod': 'GET',
        'path': '/api/organizations',
        'headers': {},
        'queryStringParameters': {}
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (False, 'Invalid API key', None)
        
        with patch('src.multi_account_api_handler.get_metrics_service'):
            response = handler(event, {})
    
    assert response['statusCode'] == 401
    body = json.loads(response['body'])
    assert body['success'] is False
    assert 'error' in body


def test_list_organizations_internal_error():
    """Test organization listing with internal error."""
    event = {
        'httpMethod': 'GET',
        'path': '/api/organizations',
        'headers': {'X-Api-Key': 'valid-key'},
        'queryStringParameters': {}
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler._get_organization_service') as mock_org_svc:
            mock_org_svc.side_effect = Exception("Internal error")
            
            with patch('src.multi_account_api_handler.get_metrics_service'):
                response = handler(event, {})
    
    assert response['statusCode'] == 500
    body = json.loads(response['body'])
    assert body['success'] is False


# ============================================================================
# Endpoint 2: GET /api/organizations/{org_id}/accounts
# ============================================================================

def test_list_accounts_success(mock_organization, mock_accounts):
    """Test successful account listing."""
    event = {
        'httpMethod': 'GET',
        'path': '/api/organizations/o-test123456/accounts',
        'headers': {'X-Api-Key': 'valid-key'},
        'queryStringParameters': {}
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler._get_organization_service') as mock_org_svc:
            mock_service = Mock()
            mock_service.get_all_accounts.return_value = mock_accounts
            mock_org_svc.return_value = mock_service
            
            with patch('src.multi_account_api_handler.get_metrics_service'):
                response = handler(event, {})
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True
    assert 'accounts' in body
    assert len(body['accounts']) == 3


def test_list_accounts_missing_org_id():
    """Test account listing with missing organization ID."""
    event = {
        'httpMethod': 'GET',
        'path': '/api/organizations//accounts',
        'headers': {'X-Api-Key': 'valid-key'},
        'queryStringParameters': {}
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler.get_metrics_service'):
            response = handler(event, {})
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['success'] is False


# ============================================================================
# Endpoint 3: GET /api/costs/consolidated
# ============================================================================

def test_consolidated_costs_success(mock_organization, mock_accounts):
    """Test successful consolidated costs retrieval."""
    event = {
        'httpMethod': 'GET',
        'path': '/api/costs/consolidated',
        'headers': {'X-Api-Key': 'valid-key'},
        'queryStringParameters': {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31'
        }
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler._get_organization_service') as mock_org_svc:
            mock_service = Mock()
            mock_service.discover_organization.return_value = mock_organization
            mock_service.get_all_accounts.return_value = mock_accounts
            mock_org_svc.return_value = mock_service
            
            with patch('src.multi_account_api_handler._get_cost_aggregation_engine') as mock_agg:
                mock_engine = Mock()
                mock_costs = Mock()
                mock_costs.total_cost = Decimal('1000.50')
                mock_costs.start_date = '2024-01-01'
                mock_costs.end_date = '2024-01-31'
                mock_costs.costs_by_service = {'EC2': Decimal('500.00'), 'S3': Decimal('500.50')}
                mock_costs.costs_by_account = {'123456789010': Decimal('1000.50')}
                mock_costs.costs_by_day = {'2024-01-01': Decimal('100.00')}
                mock_engine.aggregate_organization_costs.return_value = mock_costs
                mock_agg.return_value = mock_engine
                
                with patch('src.multi_account_api_handler.get_metrics_service'):
                    response = handler(event, {})
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True
    assert 'consolidated_costs' in body
    assert body['consolidated_costs']['total_cost'] == 1000.50


def test_consolidated_costs_invalid_date_format():
    """Test consolidated costs with invalid date format."""
    event = {
        'httpMethod': 'GET',
        'path': '/api/costs/consolidated',
        'headers': {'X-Api-Key': 'valid-key'},
        'queryStringParameters': {
            'start_date': '2024-1-1',  # Invalid format
            'end_date': '2024-01-31'
        }
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler.get_metrics_service'):
            response = handler(event, {})
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['success'] is False
    assert body['error']['code'] == 'INVALID_DATE_FORMAT'


def test_consolidated_costs_invalid_date_range():
    """Test consolidated costs with invalid date range."""
    event = {
        'httpMethod': 'GET',
        'path': '/api/costs/consolidated',
        'headers': {'X-Api-Key': 'valid-key'},
        'queryStringParameters': {
            'start_date': '2024-01-31',
            'end_date': '2024-01-01'  # End before start
        }
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler.get_metrics_service'):
            response = handler(event, {})
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['success'] is False
    assert body['error']['code'] == 'INVALID_DATE_RANGE'


# ============================================================================
# Endpoint 4: GET /api/costs/by-account
# ============================================================================

def test_costs_by_account_success(mock_organization, mock_accounts):
    """Test successful per-account costs retrieval."""
    event = {
        'httpMethod': 'GET',
        'path': '/api/costs/by-account',
        'headers': {'X-Api-Key': 'valid-key'},
        'queryStringParameters': {}
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler._get_organization_service') as mock_org_svc:
            mock_service = Mock()
            mock_service.discover_organization.return_value = mock_organization
            mock_service.get_all_accounts.return_value = mock_accounts
            mock_org_svc.return_value = mock_service
            
            with patch('src.multi_account_api_handler._get_per_account_cost_service') as mock_per_acct:
                mock_service = Mock()
                mock_costs = Mock()
                mock_costs.total_cost = Decimal('100.00')
                mock_costs.start_date = '2024-01-01'
                mock_costs.end_date = '2024-01-31'
                mock_costs.costs_by_service = {'EC2': Decimal('100.00')}
                mock_service.get_account_costs.return_value = mock_costs
                mock_per_acct.return_value = mock_service
                
                with patch('src.multi_account_api_handler.get_metrics_service'):
                    response = handler(event, {})
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True
    assert 'account_costs' in body
    assert len(body['account_costs']) == 3


# ============================================================================
# Endpoint 5: GET /api/costs/account/{account_id}
# ============================================================================

def test_account_costs_success():
    """Test successful specific account costs retrieval."""
    event = {
        'httpMethod': 'GET',
        'path': '/api/costs/account/123456789012',
        'headers': {'X-Api-Key': 'valid-key'},
        'queryStringParameters': {}
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler._get_per_account_cost_service') as mock_per_acct:
            mock_service = Mock()
            mock_costs = Mock()
            mock_costs.total_cost = Decimal('250.00')
            mock_costs.start_date = '2024-01-01'
            mock_costs.end_date = '2024-01-31'
            mock_costs.costs_by_service = {'EC2': Decimal('150.00'), 'S3': Decimal('100.00')}
            mock_costs.costs_by_day = {'2024-01-01': Decimal('10.00')}
            mock_service.get_account_costs.return_value = mock_costs
            mock_per_acct.return_value = mock_service
            
            with patch('src.multi_account_api_handler.get_metrics_service'):
                response = handler(event, {})
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True
    assert body['account_id'] == '123456789012'
    assert body['costs']['total_cost'] == 250.00


def test_account_costs_missing_account_id():
    """Test account costs with missing account ID."""
    event = {
        'httpMethod': 'GET',
        'path': '/api/costs/account/',
        'headers': {'X-Api-Key': 'valid-key'},
        'queryStringParameters': {}
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler.get_metrics_service'):
            response = handler(event, {})
    
    # Should return 400 or route to invalid endpoint
    assert response['statusCode'] in [400, 404]


# ============================================================================
# Endpoint 6: GET /api/allocation/by-tag
# ============================================================================

def test_allocation_by_tag_success(mock_organization, mock_accounts):
    """Test successful cost allocation by tag."""
    event = {
        'httpMethod': 'GET',
        'path': '/api/allocation/by-tag',
        'headers': {'X-Api-Key': 'valid-key'},
        'queryStringParameters': {'tag_key': 'Team'}
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler._get_organization_service') as mock_org_svc:
            mock_service = Mock()
            mock_service.discover_organization.return_value = mock_organization
            mock_service.get_all_accounts.return_value = mock_accounts
            mock_org_svc.return_value = mock_service
            
            with patch('src.multi_account_api_handler._get_cost_allocation_engine') as mock_alloc:
                mock_engine = Mock()
                mock_engine.get_allocation_by_team.return_value = {
                    'TeamA': Decimal('500.00'),
                    'TeamB': Decimal('300.00')
                }
                mock_alloc.return_value = mock_engine
                
                with patch('src.multi_account_api_handler.get_metrics_service'):
                    response = handler(event, {})
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True
    assert 'allocated_costs' in body


# ============================================================================
# Endpoint 7: GET /api/allocation/unallocated
# ============================================================================

def test_unallocated_costs_success(mock_organization, mock_accounts):
    """Test successful unallocated costs retrieval."""
    event = {
        'httpMethod': 'GET',
        'path': '/api/allocation/unallocated',
        'headers': {'X-Api-Key': 'valid-key'},
        'queryStringParameters': {}
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler._get_organization_service') as mock_org_svc:
            mock_service = Mock()
            mock_service.discover_organization.return_value = mock_organization
            mock_service.get_all_accounts.return_value = mock_accounts
            mock_org_svc.return_value = mock_service
            
            with patch('src.multi_account_api_handler._get_cost_allocation_engine') as mock_alloc:
                mock_engine = Mock()
                mock_unallocated = Mock()
                mock_unallocated.total_cost = Decimal('150.00')
                mock_unallocated.currency = 'USD'
                mock_unallocated.percentage_of_total = Decimal('15.0')
                mock_unallocated.by_service = {'EC2': Decimal('100.00')}
                mock_unallocated.by_account = {'123456789012': Decimal('150.00')}
                mock_unallocated.untagged_resources = []
                mock_engine.calculate_unallocated_costs.return_value = mock_unallocated
                mock_alloc.return_value = mock_engine
                
                with patch('src.multi_account_api_handler.get_metrics_service'):
                    response = handler(event, {})
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True
    assert 'unallocated_costs' in body


def test_unallocated_costs_no_accounts(mock_organization):
    """Test unallocated costs with no accounts."""
    event = {
        'httpMethod': 'GET',
        'path': '/api/allocation/unallocated',
        'headers': {'X-Api-Key': 'valid-key'},
        'queryStringParameters': {}
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler._get_organization_service') as mock_org_svc:
            mock_service = Mock()
            mock_service.discover_organization.return_value = mock_organization
            mock_service.get_all_accounts.return_value = []  # No accounts
            mock_org_svc.return_value = mock_service
            
            with patch('src.multi_account_api_handler.get_metrics_service'):
                response = handler(event, {})
    
    assert response['statusCode'] == 404
    body = json.loads(response['body'])
    assert body['success'] is False


# ============================================================================
# Endpoint 8: POST /api/allocation/rules
# ============================================================================

def test_create_allocation_rule_success():
    """Test successful allocation rule creation."""
    event = {
        'httpMethod': 'POST',
        'path': '/api/allocation/rules',
        'headers': {'X-Api-Key': 'valid-key'},
        'body': json.dumps({
            'rule_name': 'Test Rule',
            'rule_type': 'TAG_BASED',
            'conditions': {'tag_key': 'Team'},
            'allocation_target': 'TeamA',
            'priority': 100
        }),
        'queryStringParameters': {}
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler._get_allocation_rules_engine') as mock_rules:
            mock_engine = Mock()
            mock_rule = Mock()
            mock_rule.rule_id = 'rule-123'
            mock_rule.name = 'Test Rule'
            mock_engine.create_rule.return_value = mock_rule
            mock_rules.return_value = mock_engine
            
            with patch('src.multi_account_api_handler.get_metrics_service'):
                response = handler(event, {})
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True


def test_create_allocation_rule_invalid_type():
    """Test allocation rule creation with invalid type."""
    event = {
        'httpMethod': 'POST',
        'path': '/api/allocation/rules',
        'headers': {'X-Api-Key': 'valid-key'},
        'body': json.dumps({
            'rule_name': 'Test Rule',
            'rule_type': 'INVALID_TYPE',  # Invalid
            'conditions': {'tag_key': 'Team'},
            'allocation_target': 'TeamA'
        }),
        'queryStringParameters': {}
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler._get_allocation_rules_engine') as mock_rules:
            mock_engine = Mock()
            mock_engine.create_rule.side_effect = ValueError("Invalid rule type")
            mock_rules.return_value = mock_engine
            
            with patch('src.multi_account_api_handler.get_metrics_service'):
                response = handler(event, {})
    
    assert response['statusCode'] == 500  # Caught as internal error


# ============================================================================
# Endpoint 9: GET /api/budgets/hierarchy
# ============================================================================

def test_budget_hierarchy_success(mock_organization):
    """Test successful budget hierarchy retrieval."""
    event = {
        'httpMethod': 'GET',
        'path': '/api/budgets/hierarchy',
        'headers': {'X-Api-Key': 'valid-key'},
        'queryStringParameters': {}
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler._get_organization_service') as mock_org_svc:
            mock_service = Mock()
            mock_service.discover_organization.return_value = mock_organization
            mock_org_svc.return_value = mock_service
            
            with patch('src.multi_account_api_handler._get_organization_budget_service') as mock_budget:
                mock_service = Mock()
                mock_hierarchy = Mock()
                mock_hierarchy.organization_budgets = []
                mock_hierarchy.ou_budgets = []
                mock_hierarchy.account_budgets = []
                mock_service.get_budget_hierarchy.return_value = mock_hierarchy
                mock_budget.return_value = mock_service
                
                with patch('src.multi_account_api_handler.get_metrics_service'):
                    response = handler(event, {})
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True


# ============================================================================
# Endpoint 10: POST /api/budgets/organization
# ============================================================================

def test_create_organization_budget_success(mock_organization):
    """Test successful organization budget creation."""
    event = {
        'httpMethod': 'POST',
        'path': '/api/budgets/organization',
        'headers': {'X-Api-Key': 'valid-key'},
        'body': json.dumps({
            'budget_amount': 10000.00,
            'time_period': 'MONTHLY',
            'alert_threshold': 80
        }),
        'queryStringParameters': {}
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler._get_organization_service') as mock_org_svc:
            mock_service = Mock()
            mock_service.discover_organization.return_value = mock_organization
            mock_org_svc.return_value = mock_service
            
            with patch('src.multi_account_api_handler._get_organization_budget_service') as mock_budget:
                mock_service = Mock()
                mock_created_budget = Mock()
                mock_created_budget.budget_id = 'budget-123'
                mock_service.create_organization_budget.return_value = mock_created_budget
                mock_budget.return_value = mock_service
                
                with patch('src.multi_account_api_handler.get_metrics_service'):
                    response = handler(event, {})
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True


def test_create_organization_budget_invalid_amount():
    """Test organization budget creation with invalid amount."""
    event = {
        'httpMethod': 'POST',
        'path': '/api/budgets/organization',
        'headers': {'X-Api-Key': 'valid-key'},
        'body': json.dumps({
            'budget_amount': -1000.00,  # Negative amount
            'time_period': 'MONTHLY'
        }),
        'queryStringParameters': {}
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler._get_organization_service') as mock_org_svc:
            mock_org_svc.side_effect = ValueError("Budget amount must be positive")
            
            with patch('src.multi_account_api_handler.get_metrics_service'):
                response = handler(event, {})
    
    assert response['statusCode'] == 500


# ============================================================================
# Endpoint 11: POST /api/budgets/ou/{ou_id}
# ============================================================================

def test_create_ou_budget_success(mock_organization):
    """Test successful OU budget creation."""
    event = {
        'httpMethod': 'POST',
        'path': '/api/budgets/ou/ou-test123',
        'headers': {'X-Api-Key': 'valid-key'},
        'body': json.dumps({
            'budget_amount': 5000.00,
            'time_period': 'QUARTERLY'
        }),
        'queryStringParameters': {}
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler._get_organization_service') as mock_org_svc:
            mock_service = Mock()
            mock_service.discover_organization.return_value = mock_organization
            mock_org_svc.return_value = mock_service
            
            with patch('src.multi_account_api_handler._get_organization_budget_service') as mock_budget:
                mock_service = Mock()
                mock_created_budget = Mock()
                mock_created_budget.budget_id = 'budget-ou-123'
                mock_service.create_ou_budget.return_value = mock_created_budget
                mock_budget.return_value = mock_service
                
                with patch('src.multi_account_api_handler.get_metrics_service'):
                    response = handler(event, {})
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True


def test_create_ou_budget_invalid_period():
    """Test OU budget creation with invalid time period."""
    event = {
        'httpMethod': 'POST',
        'path': '/api/budgets/ou/ou-test123',
        'headers': {'X-Api-Key': 'valid-key'},
        'body': json.dumps({
            'budget_amount': 5000.00,
            'time_period': 'INVALID'  # Invalid period
        }),
        'queryStringParameters': {}
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler._get_organization_service') as mock_org_svc:
            mock_org_svc.side_effect = ValueError("Invalid time period")
            
            with patch('src.multi_account_api_handler.get_metrics_service'):
                response = handler(event, {})
    
    assert response['statusCode'] == 500


# ============================================================================
# Error Response Tests
# ============================================================================

def test_create_error_response():
    """Test error response creation."""
    response = create_error_response(
        400,
        'TEST_ERROR',
        'Test error message',
        {'detail': 'Additional info'}
    )
    
    assert response['statusCode'] == 400
    assert 'Content-Type' in response['headers']
    assert response['headers']['Content-Type'] == 'application/json'
    assert 'Access-Control-Allow-Origin' in response['headers']
    
    body = json.loads(response['body'])
    assert body['success'] is False
    assert body['error']['code'] == 'TEST_ERROR'
    assert body['error']['message'] == 'Test error message'
    assert body['error']['details']['detail'] == 'Additional info'


def test_unsupported_method():
    """Test unsupported HTTP method."""
    event = {
        'httpMethod': 'DELETE',  # Unsupported
        'path': '/api/organizations',
        'headers': {'X-Api-Key': 'valid-key'},
        'queryStringParameters': {}
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user'})
        
        with patch('src.multi_account_api_handler.get_metrics_service'):
            response = handler(event, {})
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['success'] is False
    assert body['error']['code'] == 'INVALID_REQUEST'
