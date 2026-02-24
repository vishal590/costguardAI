"""
Integration tests for Multi-Account Cost Collector Lambda Handler
"""
import json
import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch
from decimal import Decimal

from src.multi_account_cost_collector_handler import (
    lambda_handler,
    manual_trigger_handler
)


class TestMultiAccountCostCollectorHandler:
    """Integration tests for Lambda handler"""
    
    @pytest.fixture
    def eventbridge_event(self):
        """Create mock EventBridge scheduled event"""
        return {
            'version': '0',
            'id': 'test-event-id',
            'detail-type': 'Scheduled Event',
            'source': 'aws.events',
            'account': '123456789012',
            'time': '2024-01-01T00:00:00Z',
            'region': 'us-east-1',
            'resources': ['arn:aws:events:us-east-1:123456789012:rule/daily-cost-collection'],
            'detail': {}
        }
    
    @patch.dict('os.environ', {'DAYS_TO_COLLECT': '7'})
    def test_lambda_handler_missing_org_id(self, eventbridge_event):
        """Test Lambda invocation without ORGANIZATION_ID"""
        # Execute
        response = lambda_handler(eventbridge_event, None)
        
        # Verify
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'ORGANIZATION_ID' in body['message']
    
    def test_manual_trigger_missing_org_id(self):
        """Test manual trigger without org_id"""
        # Create manual trigger event without org_id
        manual_event = {
            'account_ids': ['111111111111']
        }
        
        # Execute
        response = manual_trigger_handler(manual_event, None)
        
        # Verify
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'org_id' in body['message']
    
    @patch('src.multi_account_cost_collector_handler.MultiAccountCostCollector')
    def test_manual_trigger_with_custom_params(self, mock_collector_class):
        """Test manual trigger with custom parameters"""
        # Setup mock
        from src.services.multi_account.multi_account_cost_collector import CollectionResult, AccountCostData
        
        mock_result = CollectionResult(
            total_accounts=2,
            successful=2,
            failed=0,
            failed_accounts=[],
            collection_duration=5.5,
            account_data=[
                AccountCostData(
                    account_id='111111111111',
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 1, 7),
                    total_cost=Decimal('150.00'),
                    costs_by_service={},
                    costs_by_day={},
                    collection_timestamp=None,
                    status='SUCCESS'
                ),
                AccountCostData(
                    account_id='222222222222',
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 1, 7),
                    total_cost=Decimal('200.00'),
                    costs_by_service={},
                    costs_by_day={},
                    collection_timestamp=None,
                    status='SUCCESS'
                )
            ]
        )
        
        mock_collector = Mock()
        mock_collector.collect_all_accounts.return_value = mock_result
        mock_collector_class.return_value = mock_collector
        
        # Create manual trigger event
        manual_event = {
            'org_id': 'o-1234567890',
            'account_ids': ['111111111111', '222222222222'],
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',
            'external_id': 'custom-external-id'
        }
        
        # Execute
        response = manual_trigger_handler(manual_event, None)
        
        # Verify
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['message'] == 'Manual cost collection completed'
        assert body['summary']['total_accounts'] == 2
        assert body['summary']['successful'] == 2
        assert body['summary']['failed'] == 0
        
        # Verify collector was called with custom params
        mock_collector.collect_all_accounts.assert_called_once()
        call_args = mock_collector.collect_all_accounts.call_args
        assert call_args[1]['account_ids'] == ['111111111111', '222222222222']
        assert call_args[1]['start_date'] == date(2024, 1, 1)
        assert call_args[1]['end_date'] == date(2024, 1, 31)
