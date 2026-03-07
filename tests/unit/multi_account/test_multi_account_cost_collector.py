"""
Unit tests for Multi-Account Cost Collector
"""
import os
import pytest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch
from botocore.exceptions import ClientError

from src.services.multi_account.multi_account_cost_collector import (
    MultiAccountCostCollector,
    AccountCostData,
    CollectionResult
)
from src.services.multi_account.cross_account_role_manager import Credentials


class TestMultiAccountCostCollector:
    """Unit tests for MultiAccountCostCollector"""
    
    @pytest.fixture
    def mock_role_manager(self):
        """Create mock role manager"""
        manager = Mock()
        manager.assume_role.return_value = Credentials(
            access_key_id='AKIAIOSFODNN7EXAMPLE',
            secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            session_token='FwoGZXIvYXdzEBYaDH...',
            expiration=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        # Mock boto3 session
        mock_session = Mock()
        mock_ce_client = Mock()
        mock_session.client.return_value = mock_ce_client
        manager.create_boto3_session.return_value = mock_session
        
        return manager
    
    @pytest.fixture
    def mock_cost_repository(self):
        """Create mock cost repository"""
        return Mock()
    
    @pytest.fixture
    def mock_ce_response(self):
        """Create mock Cost Explorer response"""
        return {
            'ResultsByTime': [
                {
                    'TimePeriod': {'Start': '2024-01-01', 'End': '2024-01-02'},
                    'Groups': [
                        {
                            'Keys': ['Amazon EC2'],
                            'Metrics': {'UnblendedCost': {'Amount': '100.50', 'Unit': 'USD'}}
                        },
                        {
                            'Keys': ['Amazon S3'],
                            'Metrics': {'UnblendedCost': {'Amount': '25.75', 'Unit': 'USD'}}
                        }
                    ]
                },
                {
                    'TimePeriod': {'Start': '2024-01-02', 'End': '2024-01-03'},
                    'Groups': [
                        {
                            'Keys': ['Amazon EC2'],
                            'Metrics': {'UnblendedCost': {'Amount': '105.25', 'Unit': 'USD'}}
                        },
                        {
                            'Keys': ['Amazon S3'],
                            'Metrics': {'UnblendedCost': {'Amount': '30.00', 'Unit': 'USD'}}
                        }
                    ]
                }
            ]
        }
    
    def test_collect_account_success(self, mock_role_manager, mock_cost_repository, mock_ce_response):
        """Test successful single account collection"""
        # Setup
        collector = MultiAccountCostCollector(
            role_manager=mock_role_manager,
            cost_repository=mock_cost_repository
        )
        
        # Mock Cost Explorer response
        mock_ce_client = mock_role_manager.create_boto3_session.return_value.client.return_value
        mock_ce_client.get_cost_and_usage.return_value = mock_ce_response
        
        # Execute
        result = collector.collect_account(
            account_id='123456789012',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 3),
            external_id='test-external-id'
        )
        
        # Verify
        assert result.account_id == '123456789012'
        assert result.status == 'SUCCESS'
        assert result.total_cost == Decimal('261.50')  # Sum of all costs
        assert 'Amazon EC2' in result.costs_by_service
        assert 'Amazon S3' in result.costs_by_service
        assert result.costs_by_service['Amazon EC2'] == Decimal('205.75')
        assert result.costs_by_service['Amazon S3'] == Decimal('55.75')
        assert len(result.costs_by_day) == 2
        
        # Verify role assumption
        mock_role_manager.assume_role.assert_called_once_with(
            account_id='123456789012',
            role_name='CostGuardCollectorRole',
            external_id='test-external-id'
        )
        
        # Verify Cost Explorer call
        mock_ce_client.get_cost_and_usage.assert_called_once()
        
        # Verify data was stored
        mock_cost_repository.save_cost_data.assert_called_once()
    
    def test_collect_account_with_retry(self, mock_role_manager, mock_cost_repository, mock_ce_response):
        """Test account collection with retry on failure"""
        # Setup
        collector = MultiAccountCostCollector(
            role_manager=mock_role_manager,
            cost_repository=mock_cost_repository,
            max_retries=3
        )
        
        # Mock Cost Explorer to fail twice then succeed
        mock_ce_client = mock_role_manager.create_boto3_session.return_value.client.return_value
        mock_ce_client.get_cost_and_usage.side_effect = [
            ClientError({'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}}, 'GetCostAndUsage'),
            ClientError({'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}}, 'GetCostAndUsage'),
            mock_ce_response
        ]
        
        # Execute
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = collector.collect_account(
                account_id='123456789012',
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 3)
            )
        
        # Verify
        assert result.status == 'SUCCESS'
        assert mock_ce_client.get_cost_and_usage.call_count == 3
    
    def test_collect_account_failure_after_retries(self, mock_role_manager, mock_cost_repository):
        """Test account collection failure after all retries"""
        # Setup
        collector = MultiAccountCostCollector(
            role_manager=mock_role_manager,
            cost_repository=mock_cost_repository,
            max_retries=3
        )
        
        # Mock Cost Explorer to always fail
        mock_ce_client = mock_role_manager.create_boto3_session.return_value.client.return_value
        mock_ce_client.get_cost_and_usage.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'GetCostAndUsage'
        )
        
        # Execute
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = collector.collect_account(
                account_id='123456789012',
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 3)
            )
        
        # Verify
        assert result.status == 'FAILED'
        assert result.total_cost == Decimal('0')
        assert result.error_message is not None
        assert 'AccessDenied' in result.error_message
        assert mock_ce_client.get_cost_and_usage.call_count == 3
    
    def test_collect_parallel_success(self, mock_role_manager, mock_cost_repository, mock_ce_response):
        """Test parallel collection from multiple accounts"""
        # Setup
        collector = MultiAccountCostCollector(
            role_manager=mock_role_manager,
            cost_repository=mock_cost_repository,
            max_workers=3
        )
        
        # Mock Cost Explorer response
        mock_ce_client = mock_role_manager.create_boto3_session.return_value.client.return_value
        mock_ce_client.get_cost_and_usage.return_value = mock_ce_response
        
        account_ids = ['111111111111', '222222222222', '333333333333']
        
        # Execute
        results = collector.collect_parallel(
            account_ids=account_ids,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 3)
        )
        
        # Verify
        assert len(results) == 3
        assert all(r.status == 'SUCCESS' for r in results)
        assert {r.account_id for r in results} == set(account_ids)
        assert mock_role_manager.assume_role.call_count == 3
    
    def test_collect_parallel_with_failures(self, mock_role_manager, mock_cost_repository, mock_ce_response):
        """Test parallel collection with some failures"""
        # Setup
        collector = MultiAccountCostCollector(
            role_manager=mock_role_manager,
            cost_repository=mock_cost_repository,
            max_workers=3,
            max_retries=1  # Reduce retries for faster test
        )
        
        # Mock Cost Explorer to fail for specific accounts
        mock_ce_client = mock_role_manager.create_boto3_session.return_value.client.return_value
        
        def mock_get_cost_and_usage(*args, **kwargs):
            # Fail for account 222222222222
            if mock_role_manager.assume_role.call_count == 2:
                raise ClientError(
                    {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
                    'GetCostAndUsage'
                )
            return mock_ce_response
        
        mock_ce_client.get_cost_and_usage.side_effect = mock_get_cost_and_usage
        
        account_ids = ['111111111111', '222222222222', '333333333333']
        
        # Execute
        with patch('time.sleep'):  # Mock sleep to speed up test
            results = collector.collect_parallel(
                account_ids=account_ids,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 3)
            )
        
        # Verify
        assert len(results) == 3
        successful = [r for r in results if r.status == 'SUCCESS']
        failed = [r for r in results if r.status == 'FAILED']
        assert len(successful) >= 1  # At least one should succeed
        assert len(failed) >= 1  # At least one should fail
    
    def test_collect_all_accounts(self, mock_role_manager, mock_cost_repository, mock_ce_response):
        """Test collecting from all accounts with summary"""
        # Setup
        collector = MultiAccountCostCollector(
            role_manager=mock_role_manager,
            cost_repository=mock_cost_repository,
            max_workers=2
        )
        
        # Mock Cost Explorer response
        mock_ce_client = mock_role_manager.create_boto3_session.return_value.client.return_value
        mock_ce_client.get_cost_and_usage.return_value = mock_ce_response
        
        account_ids = ['111111111111', '222222222222']
        
        # Execute
        result = collector.collect_all_accounts(
            org_id='o-1234567890',
            account_ids=account_ids,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 3)
        )
        
        # Verify
        assert isinstance(result, CollectionResult)
        assert result.total_accounts == 2
        assert result.successful == 2
        assert result.failed == 0
        assert len(result.failed_accounts) == 0
        assert result.collection_duration > 0
        assert len(result.account_data) == 2
    
    def test_collect_all_accounts_with_failures(self, mock_role_manager, mock_cost_repository):
        """Test collecting from all accounts with some failures"""
        # Setup
        collector = MultiAccountCostCollector(
            role_manager=mock_role_manager,
            cost_repository=mock_cost_repository,
            max_workers=2,
            max_retries=1
        )
        
        # Mock Cost Explorer to fail for all accounts
        mock_ce_client = mock_role_manager.create_boto3_session.return_value.client.return_value
        mock_ce_client.get_cost_and_usage.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'GetCostAndUsage'
        )
        
        account_ids = ['111111111111', '222222222222']
        
        # Execute
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = collector.collect_all_accounts(
                org_id='o-1234567890',
                account_ids=account_ids,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 3)
            )
        
        # Verify
        assert result.total_accounts == 2
        assert result.successful == 0
        assert result.failed == 2
        assert len(result.failed_accounts) == 2
        assert set(result.failed_accounts) == set(account_ids)
    
    def test_storage_failure_does_not_break_collection(self, mock_role_manager, mock_cost_repository, mock_ce_response):
        """Test that storage failures don't prevent data collection"""
        # Setup
        collector = MultiAccountCostCollector(
            role_manager=mock_role_manager,
            cost_repository=mock_cost_repository
        )
        
        # Mock Cost Explorer response
        mock_ce_client = mock_role_manager.create_boto3_session.return_value.client.return_value
        mock_ce_client.get_cost_and_usage.return_value = mock_ce_response
        
        # Mock repository to fail
        mock_cost_repository.save_cost_data.side_effect = Exception("DynamoDB error")
        
        # Execute
        result = collector.collect_account(
            account_id='123456789012',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 3)
        )
        
        # Verify - collection should still succeed even if storage fails
        assert result.status == 'SUCCESS'
        assert result.total_cost > 0
    
    def test_max_workers_from_environment_variable(self, mock_role_manager, mock_cost_repository):
        """Test that max_workers can be read from environment variable"""
        with patch.dict(os.environ, {'MAX_PARALLEL_ACCOUNTS': '20'}):
            collector = MultiAccountCostCollector(
                role_manager=mock_role_manager,
                cost_repository=mock_cost_repository
            )
            assert collector.max_workers == 20
    
    def test_max_workers_default_when_not_in_environment(self, mock_role_manager, mock_cost_repository):
        """Test that max_workers defaults to 10 when not in environment"""
        with patch.dict(os.environ, {}, clear=True):
            collector = MultiAccountCostCollector(
                role_manager=mock_role_manager,
                cost_repository=mock_cost_repository
            )
            assert collector.max_workers == 10
    
    def test_max_workers_explicit_override(self, mock_role_manager, mock_cost_repository):
        """Test that explicitly passing max_workers overrides environment variable"""
        with patch.dict(os.environ, {'MAX_PARALLEL_ACCOUNTS': '20'}):
            collector = MultiAccountCostCollector(
                role_manager=mock_role_manager,
                cost_repository=mock_cost_repository,
                max_workers=15
            )
            assert collector.max_workers == 15