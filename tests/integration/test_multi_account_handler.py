"""
Integration tests for Multi-Account Lambda Handler.

Tests the main Lambda handler for multi-account operations.
"""
import pytest
from unittest.mock import Mock, patch
from decimal import Decimal
from datetime import datetime, UTC

from src.multi_account_handler import handler
from src.services.multi_account.models import (
    Organization, Account, AggregatedCosts, AllocationResult
)


class TestMultiAccountHandler:
    """Test cases for multi-account Lambda handler."""
    
    @patch('src.multi_account_handler._get_organization_service')
    def test_discover_organization_success(self, mock_get_org_service):
        """Test successful organization discovery operation."""
        # Mock organization service
        mock_org_service = Mock()
        mock_get_org_service.return_value = mock_org_service
        
        # Mock organization and accounts
        mock_organization = Organization(
            id='o-example123456',
            master_account_id='123456789012',
            arn='arn:aws:organizations::123456789012:organization/o-example123456',
            feature_set='ALL'
        )
        
        mock_accounts = [
            Account(
                id='123456789012',
                arn='arn:aws:organizations::123456789012:account/o-example123456/123456789012',
                name='Management Account',
                email='admin@example.com',
                status='ACTIVE',
                joined_method='INVITED',
                joined_timestamp=datetime.now(UTC)
            ),
            Account(
                id='123456789013',
                arn='arn:aws:organizations::123456789012:account/o-example123456/123456789013',
                name='Development Account',
                email='dev@example.com',
                status='ACTIVE',
                joined_method='CREATED',
                joined_timestamp=datetime.now(UTC)
            )
        ]
        
        mock_org_service.discover_organization.return_value = mock_organization
        mock_org_service.get_all_accounts.return_value = mock_accounts
        
        # Test event
        event = {
            'operation': 'discover_organization',
            'parameters': {}
        }
        
        # Execute handler
        response = handler(event, {})
        
        # Verify response
        assert response['success'] is True
        assert 'data' in response
        assert 'organization' in response['data']
        assert 'accounts' in response['data']
        assert response['data']['account_count'] == 2
        assert response['data']['organization']['id'] == 'o-example123456'
        assert len(response['data']['accounts']) == 2
        
        # Verify service calls
        mock_org_service.discover_organization.assert_called_once()
        mock_org_service.get_all_accounts.assert_called_once_with('o-example123456')
    
    @patch('src.multi_account_handler._get_cost_collector')
    def test_collect_costs_all_accounts_success(self, mock_get_collector):
        """Test successful cost collection for all accounts."""
        # Mock cost collector
        mock_collector = Mock()
        mock_get_collector.return_value = mock_collector
        
        # Mock collection results
        mock_results = [
            Mock(
                account_id='123456789012',
                success=True,
                cost_data=[{'service': 'EC2', 'cost': Decimal('100.00')}],
                error_message=None
            ),
            Mock(
                account_id='123456789013',
                success=True,
                cost_data=[{'service': 'S3', 'cost': Decimal('50.00')}],
                error_message=None
            )
        ]
        
        mock_collector.collect_all_accounts.return_value = mock_results
        
        # Test event
        event = {
            'operation': 'collect_costs',
            'parameters': {
                'start_date': '2024-01-01',
                'end_date': '2024-01-31'
            }
        }
        
        # Execute handler
        response = handler(event, {})
        
        # Verify response
        assert response['success'] is True
        assert 'data' in response
        assert 'collection_results' in response['data']
        assert 'summary' in response['data']
        assert response['data']['summary']['total_accounts'] == 2
        assert response['data']['summary']['successful_accounts'] == 2
        assert response['data']['summary']['failed_accounts'] == 0
        assert response['data']['summary']['total_data_points'] == 2
        
        # Verify service calls
        mock_collector.collect_all_accounts.assert_called_once_with(
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
    
    @patch('src.multi_account_handler._get_cost_collector')
    def test_collect_costs_specific_accounts_success(self, mock_get_collector):
        """Test successful cost collection for specific accounts."""
        # Mock cost collector
        mock_collector = Mock()
        mock_get_collector.return_value = mock_collector
        
        # Mock collection result
        mock_result = Mock(
            success=True,
            cost_data=[{'service': 'EC2', 'cost': Decimal('100.00')}],
            error_message=None
        )
        
        mock_collector.collect_account.return_value = mock_result
        
        # Test event
        event = {
            'operation': 'collect_costs',
            'parameters': {
                'account_ids': ['123456789012'],
                'start_date': '2024-01-01',
                'end_date': '2024-01-31'
            }
        }
        
        # Execute handler
        response = handler(event, {})
        
        # Verify response
        assert response['success'] is True
        assert 'data' in response
        assert len(response['data']['collection_results']) == 1
        assert response['data']['collection_results'][0]['account_id'] == '123456789012'
        assert response['data']['collection_results'][0]['success'] is True
        assert response['data']['collection_results'][0]['cost_data_points'] == 1
        
        # Verify service calls
        mock_collector.collect_account.assert_called_once_with(
            account_id='123456789012',
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
    
    @patch('src.multi_account_handler._get_cost_aggregation_engine')
    @patch('src.multi_account_handler._get_organization_service')
    def test_aggregate_costs_organization_success(self, mock_get_org_service, mock_get_aggregation):
        """Test successful organization-level cost aggregation."""
        # Mock organization service
        mock_org_service = Mock()
        mock_get_org_service.return_value = mock_org_service
        
        mock_accounts = [
            Account(
                id='123456789012', 
                arn='arn:aws:organizations::123456789012:account/o-example123456/123456789012',
                name='Account 1', 
                email='test1@example.com', 
                status='ACTIVE', 
                joined_method='INVITED',
                joined_timestamp=datetime.now(UTC)
            ),
            Account(
                id='123456789013', 
                arn='arn:aws:organizations::123456789012:account/o-example123456/123456789013',
                name='Account 2', 
                email='test2@example.com', 
                status='ACTIVE', 
                joined_method='CREATED',
                joined_timestamp=datetime.now(UTC)
            )
        ]
        mock_org_service.get_all_accounts.return_value = mock_accounts
        
        # Mock aggregation engine
        mock_aggregation_engine = Mock()
        mock_get_aggregation.return_value = mock_aggregation_engine
        
        # Mock aggregated costs
        mock_aggregated_costs = AggregatedCosts(
            entity_id='o-example123456',
            entity_type='ORGANIZATION',
            start_date='2024-01-01',
            end_date='2024-01-31',
            total_cost=Decimal('150.00'),
            account_count=2,
            costs_by_account={'123456789012': Decimal('100.00'), '123456789013': Decimal('50.00')},
            costs_by_service={'EC2': Decimal('100.00'), 'S3': Decimal('50.00')},
            costs_by_day={'2024-01-01': Decimal('75.00'), '2024-01-02': Decimal('75.00')}
        )
        
        mock_aggregation_engine.aggregate_organization_costs.return_value = mock_aggregated_costs
        
        # Test event
        event = {
            'operation': 'aggregate_costs',
            'parameters': {
                'aggregation_type': 'organization',
                'org_id': 'o-example123456',
                'start_date': '2024-01-01',
                'end_date': '2024-01-31'
            }
        }
        
        # Execute handler
        response = handler(event, {})
        
        # Verify response
        assert response['success'] is True
        assert 'data' in response
        assert response['data']['aggregation_type'] == 'organization'
        assert response['data']['organization_id'] == 'o-example123456'
        assert response['data']['total_cost'] == 150.0
        assert response['data']['costs_by_service']['EC2'] == 100.0
        assert response['data']['costs_by_service']['S3'] == 50.0
        assert response['data']['costs_by_account']['123456789012'] == 100.0
        assert response['data']['costs_by_account']['123456789013'] == 50.0
        
        # Verify service calls
        mock_org_service.get_all_accounts.assert_called_once_with('o-example123456')
        mock_aggregation_engine.aggregate_organization_costs.assert_called_once_with(
            org_id='o-example123456',
            account_ids=['123456789012', '123456789013'],
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
    
    @patch('src.multi_account_handler._get_cost_allocation_engine')
    @patch('src.multi_account_handler._get_organization_service')
    def test_allocate_costs_by_tags_success(self, mock_get_org_service, mock_get_allocation):
        """Test successful cost allocation by tags."""
        # Mock organization service
        mock_org_service = Mock()
        mock_get_org_service.return_value = mock_org_service
        
        mock_accounts = [
            Account(
                id='123456789012', 
                arn='arn:aws:organizations::123456789012:account/o-example123456/123456789012',
                name='Account 1', 
                email='test1@example.com', 
                status='ACTIVE', 
                joined_method='INVITED',
                joined_timestamp=datetime.now(UTC)
            )
        ]
        mock_org_service.get_all_accounts.return_value = mock_accounts
        
        # Mock allocation engine
        mock_allocation_engine = Mock()
        mock_get_allocation.return_value = mock_allocation_engine
        
        # Mock team costs
        mock_team_costs = {
            'Engineering': Decimal('100.00'),
            'Marketing': Decimal('50.00')
        }
        mock_allocation_engine.get_allocation_by_team.return_value = mock_team_costs
        
        # Test event
        event = {
            'operation': 'allocate_costs',
            'parameters': {
                'allocation_type': 'by_tags',
                'org_id': 'o-example123456',
                'tag_key': 'Team',
                'start_date': '2024-01-01',
                'end_date': '2024-01-31'
            }
        }
        
        # Execute handler
        response = handler(event, {})
        
        # Verify response
        assert response['success'] is True
        assert 'data' in response
        assert response['data']['allocation_type'] == 'by_tags'
        assert response['data']['tag_key'] == 'Team'
        assert response['data']['organization_id'] == 'o-example123456'
        assert response['data']['allocated_costs']['Engineering'] == 100.0
        assert response['data']['allocated_costs']['Marketing'] == 50.0
        assert 'unallocated_costs' in response['data']
        assert 'total_cost' in response['data']['unallocated_costs']
        assert 'percentage_of_total' in response['data']['unallocated_costs']
        assert response['data']['total_allocated'] == 150.0
        
        # Verify service calls
        mock_org_service.get_all_accounts.assert_called_once_with('o-example123456')
        mock_allocation_engine.get_allocation_by_team.assert_called_once_with(
            org_id='o-example123456',
            account_ids=['123456789012'],
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
    
    def test_handler_missing_operation(self):
        """Test handler with missing operation parameter."""
        event = {
            'parameters': {}
        }
        
        response = handler(event, {})
        
        assert response['success'] is False
        assert response['error']['code'] == 'MISSING_OPERATION'
        assert 'Operation is required' in response['error']['message']
    
    def test_handler_invalid_operation(self):
        """Test handler with invalid operation."""
        event = {
            'operation': 'invalid_operation',
            'parameters': {}
        }
        
        response = handler(event, {})
        
        assert response['success'] is False
        assert response['error']['code'] == 'INVALID_OPERATION'
        assert 'Unsupported operation: invalid_operation' in response['error']['message']
    
    def test_aggregate_costs_missing_org_id(self):
        """Test cost aggregation with missing org_id."""
        event = {
            'operation': 'aggregate_costs',
            'parameters': {
                'aggregation_type': 'organization'
            }
        }
        
        response = handler(event, {})
        
        assert response['success'] is False
        assert response['error']['code'] == 'MISSING_PARAMETER'
        assert 'org_id is required' in response['error']['message']
    
    def test_allocate_costs_missing_org_id(self):
        """Test cost allocation with missing org_id."""
        event = {
            'operation': 'allocate_costs',
            'parameters': {
                'allocation_type': 'by_tags'
            }
        }
        
        response = handler(event, {})
        
        assert response['success'] is False
        assert response['error']['code'] == 'MISSING_PARAMETER'
        assert 'org_id is required' in response['error']['message']