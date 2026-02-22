"""
Unit tests for Lambda handler.

Tests routing to Phase 3 endpoints, backward compatibility with Phase 1/1.5/2,
and error handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json

from src.lambda_handler import (
    handler,
    handle_prevention_status,
    handle_prevention_enable,
    handle_prevention_disable,
    handle_prevention_resources,
    handle_prevention_rollback,
    handle_prevention_history,
    _get_prevention_engine
)


class TestPhase3Routing:
    """Test routing to Phase 3 endpoints."""
    
    def test_route_to_prevention_status(self):
        """Test routing to prevention status endpoint."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/prevention/status'
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_engine:
            mock_engine_instance = Mock()
            mock_engine_instance.get_status.return_value = {'enabled': False}
            mock_engine.return_value = mock_engine_instance
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert 'status' in body
    
    def test_route_to_prevention_enable(self):
        """Test routing to prevention enable endpoint."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/prevention/enable'
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_engine:
            mock_engine_instance = Mock()
            mock_engine_instance.enable.return_value = None
            mock_engine_instance.get_status.return_value = {'enabled': True}
            mock_engine.return_value = mock_engine_instance
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert body['message'] == 'Prevention system enabled'
    
    def test_route_to_prevention_disable(self):
        """Test routing to prevention disable endpoint."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/prevention/disable'
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_engine:
            mock_engine_instance = Mock()
            mock_engine_instance.disable.return_value = None
            mock_engine_instance.get_status.return_value = {'enabled': False}
            mock_engine.return_value = mock_engine_instance
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert body['message'] == 'Prevention system disabled'
    
    def test_route_to_prevention_resources(self):
        """Test routing to prevention resources endpoint."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/prevention/resources',
            'queryStringParameters': {'service': 'ec2'}
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_engine:
            mock_engine_instance = Mock()
            mock_engine_instance.get_resources.return_value = []
            mock_engine.return_value = mock_engine_instance
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert 'resources' in body
            assert 'count' in body
    
    def test_route_to_prevention_rollback(self):
        """Test routing to prevention rollback endpoint."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/prevention/rollback',
            'body': json.dumps({'action_id': 'action-123'})
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_engine:
            mock_engine_instance = Mock()
            mock_engine_instance.execute_rollback.return_value = {
                'success': True,
                'action_id': 'action-123',
                'resource_id': 'i-123'
            }
            mock_engine.return_value = mock_engine_instance
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert body['action_id'] == 'action-123'
    
    def test_route_to_prevention_history(self):
        """Test routing to prevention history endpoint."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/prevention/history',
            'queryStringParameters': {'limit': '50'}
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_engine:
            mock_engine_instance = Mock()
            mock_engine.return_value = mock_engine_instance
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert 'history' in body


class TestPhase1Compatibility:
    """Test Phase 1 endpoints still work."""
    
    def test_phase1_fetch_endpoint_works(self):
        """Test Phase 1 /fetch endpoint still works."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/fetch',
            'body': json.dumps({
                'startDate': '2024-01-01',
                'endDate': '2024-01-31',
                'granularity': 'DAILY'
            })
        }
        
        with patch('src.lambda_handler.fetch_cost_data') as mock_fetch, \
             patch('src.lambda_handler.store_cost_data') as mock_store:
            
            mock_fetch.return_value = []
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert 'data' in body
    
    def test_phase1_query_endpoint_works(self):
        """Test Phase 1 /cost-data endpoint still works."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/cost-data',
            'queryStringParameters': {'limit': '100'}
        }
        
        with patch('src.lambda_handler.query_cost_data') as mock_query:
            mock_query.return_value = []
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert 'data' in body
            assert 'count' in body


class TestPhase15Compatibility:
    """Test Phase 1.5 endpoints still work."""
    
    def test_phase15_estimation_current_works(self):
        """Test Phase 1.5 /cost-estimation/current endpoint still works."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/cost-estimation/current',
            'queryStringParameters': {'hours': '1'}
        }
        
        with patch('src.lambda_handler.CloudWatchMetricsCollector') as mock_collector, \
             patch('src.lambda_handler.PricingManager') as mock_pricing, \
             patch('src.lambda_handler.CostEstimator') as mock_estimator:
            
            mock_collector_instance = Mock()
            mock_collector_instance.collect_metrics.return_value = {}
            mock_collector.return_value = mock_collector_instance
            
            mock_pricing.return_value = Mock()
            mock_estimator.return_value = Mock()
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert 'estimates' in body
    
    def test_phase15_estimation_service_works(self):
        """Test Phase 1.5 /cost-estimation/service/{service} endpoint still works."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/cost-estimation/service/ec2',
            'queryStringParameters': {'hours': '1'}
        }
        
        with patch('src.lambda_handler.CloudWatchMetricsCollector') as mock_collector, \
             patch('src.lambda_handler.PricingManager') as mock_pricing, \
             patch('src.lambda_handler.CostEstimator') as mock_estimator:
            
            mock_collector_instance = Mock()
            mock_collector_instance.collect_metrics.return_value = {'ec2': []}
            mock_collector.return_value = mock_collector_instance
            
            mock_pricing.return_value = Mock()
            mock_estimator.return_value = Mock()
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True


class TestPhase2Compatibility:
    """Test Phase 2 endpoints still work."""
    
    def test_phase2_forecast_endpoint_works(self):
        """Test Phase 2 /cost-forecast endpoint still works."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/cost-forecast',
            'queryStringParameters': {'days': '7', 'granularity': 'daily'}
        }
        
        with patch('src.lambda_handler.get_dynamodb_client'), \
             patch('src.lambda_handler.BedrockClient'), \
             patch('src.lambda_handler.HistoricalDataRetriever'), \
             patch('src.lambda_handler.ForecastCacheManager'), \
             patch('src.lambda_handler.ForecastEngine') as mock_engine:
            
            mock_engine_instance = Mock()
            mock_forecast_response = Mock()
            mock_forecast_response.success = True
            mock_forecast_response.forecast_data = []
            mock_forecast_response.metadata = Mock(
                timestamp='2024-01-01T00:00:00Z',
                forecast_horizon=7,
                granularity='daily',
                model_used='test',
                service=None,
                services_included=[],
                cache_hit=False,
                historical_data_days=90
            )
            mock_engine_instance.generate_forecast.return_value = mock_forecast_response
            mock_engine.return_value = mock_engine_instance
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert 'forecast_data' in body
    
    def test_phase2_forecast_service_endpoint_works(self):
        """Test Phase 2 /cost-forecast/service/{service} endpoint still works."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/cost-forecast/service/lambda',
            'queryStringParameters': {'days': '7', 'granularity': 'daily'}
        }
        
        with patch('src.lambda_handler.get_dynamodb_client'), \
             patch('src.lambda_handler.BedrockClient'), \
             patch('src.lambda_handler.HistoricalDataRetriever'), \
             patch('src.lambda_handler.ForecastCacheManager'), \
             patch('src.lambda_handler.ForecastEngine') as mock_engine:
            
            mock_engine_instance = Mock()
            mock_forecast_response = Mock()
            mock_forecast_response.success = True
            mock_forecast_response.forecast_data = []
            mock_forecast_response.metadata = Mock(
                timestamp='2024-01-01T00:00:00Z',
                forecast_horizon=7,
                granularity='daily',
                model_used='test',
                service='lambda',
                services_included=['lambda'],
                cache_hit=False,
                historical_data_days=90
            )
            mock_engine_instance.generate_forecast.return_value = mock_forecast_response
            mock_engine.return_value = mock_engine_instance
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert body['metadata']['service'] == 'lambda'


class TestPreventionStatusEndpoint:
    """Test prevention status endpoint."""
    
    def test_get_status_success(self):
        """Test getting prevention status successfully."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/prevention/status'
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_engine:
            mock_engine_instance = Mock()
            mock_engine_instance.get_status.return_value = {
                'enabled': True,
                'dry_run_mode': False,
                'approval_required': False
            }
            mock_engine.return_value = mock_engine_instance
            
            response = handle_prevention_status(event)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert body['status']['enabled'] is True
    
    def test_get_status_error_handling(self):
        """Test error handling in status endpoint."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/prevention/status'
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_engine:
            mock_engine.side_effect = Exception("Test error")
            
            response = handle_prevention_status(event)
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert body['success'] is False


class TestPreventionEnableDisable:
    """Test prevention enable/disable endpoints."""
    
    def test_enable_prevention(self):
        """Test enabling prevention system."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/prevention/enable'
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_engine:
            mock_engine_instance = Mock()
            mock_engine_instance.get_status.return_value = {'enabled': True}
            mock_engine.return_value = mock_engine_instance
            
            response = handle_prevention_enable(event)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert 'enabled' in body['message'].lower()
            mock_engine_instance.enable.assert_called_once()
    
    def test_disable_prevention(self):
        """Test disabling prevention system."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/prevention/disable'
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_engine:
            mock_engine_instance = Mock()
            mock_engine_instance.get_status.return_value = {'enabled': False}
            mock_engine.return_value = mock_engine_instance
            
            response = handle_prevention_disable(event)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert 'disabled' in body['message'].lower()
            mock_engine_instance.disable.assert_called_once()


class TestPreventionResourcesEndpoint:
    """Test prevention resources endpoint."""
    
    def test_get_resources_without_filters(self):
        """Test getting all resources without filters."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/prevention/resources',
            'queryStringParameters': None
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_engine:
            from src.utils.types import Resource
            
            mock_resource = Resource(
                resource_id='i-123',
                resource_type='ec2',
                service='ec2',
                region='us-east-1',
                tags={},
                state='running',
                creation_date='2024-01-01T00:00:00Z'
            )
            
            mock_engine_instance = Mock()
            mock_engine_instance.get_resources.return_value = [mock_resource]
            mock_engine.return_value = mock_engine_instance
            
            response = handle_prevention_resources(event)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert body['count'] == 1
            assert body['resources'][0]['resource_id'] == 'i-123'
    
    def test_get_resources_with_service_filter(self):
        """Test getting resources filtered by service."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/prevention/resources',
            'queryStringParameters': {'service': 'ec2'}
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_engine:
            mock_engine_instance = Mock()
            mock_engine_instance.get_resources.return_value = []
            mock_engine.return_value = mock_engine_instance
            
            response = handle_prevention_resources(event)
            
            assert response['statusCode'] == 200
            mock_engine_instance.get_resources.assert_called_once()
            call_args = mock_engine_instance.get_resources.call_args
            assert call_args[1]['filters']['service'] == 'ec2'


class TestPreventionRollbackEndpoint:
    """Test prevention rollback endpoint."""
    
    def test_rollback_success(self):
        """Test successful rollback."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/prevention/rollback',
            'body': json.dumps({'action_id': 'action-123'})
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_engine:
            mock_engine_instance = Mock()
            mock_engine_instance.execute_rollback.return_value = {
                'success': True,
                'action_id': 'action-123',
                'resource_id': 'i-123',
                'message': 'Rollback successful'
            }
            mock_engine.return_value = mock_engine_instance
            
            response = handle_prevention_rollback(event)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert body['action_id'] == 'action-123'
    
    def test_rollback_missing_action_id(self):
        """Test rollback with missing action_id."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/prevention/rollback',
            'body': json.dumps({})
        }
        
        response = handle_prevention_rollback(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False
        assert 'action_id' in body['error']['message'].lower()
    
    def test_rollback_failure(self):
        """Test failed rollback."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/prevention/rollback',
            'body': json.dumps({'action_id': 'action-123'})
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_engine:
            mock_engine_instance = Mock()
            mock_engine_instance.execute_rollback.return_value = {
                'success': False,
                'action_id': 'action-123',
                'error': 'Action not found'
            }
            mock_engine.return_value = mock_engine_instance
            
            response = handle_prevention_rollback(event)
            
            assert response['statusCode'] == 400
            body = json.loads(response['body'])
            assert body['success'] is False


class TestPreventionHistoryEndpoint:
    """Test prevention history endpoint."""
    
    def test_get_history_with_defaults(self):
        """Test getting history with default parameters."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/prevention/history',
            'queryStringParameters': None
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_engine:
            mock_engine.return_value = Mock()
            
            response = handle_prevention_history(event)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert 'history' in body
    
    def test_get_history_with_filters(self):
        """Test getting history with date filters."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/prevention/history',
            'queryStringParameters': {
                'start_date': '2024-01-01',
                'end_date': '2024-01-31',
                'limit': '50'
            }
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_engine:
            mock_engine.return_value = Mock()
            
            response = handle_prevention_history(event)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True


class TestErrorHandling:
    """Test error handling across all endpoints."""
    
    def test_unsupported_method_and_path(self):
        """Test handling of unsupported method/path combinations."""
        event = {
            'httpMethod': 'DELETE',
            'path': '/api/unknown'
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False
        assert 'INVALID_REQUEST' in body['error']['code']
    
    def test_exception_handling(self):
        """Test handling of unexpected exceptions."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/prevention/status'
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_engine:
            mock_engine.side_effect = Exception("Unexpected error")
            
            response = handler(event, None)
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert body['success'] is False


class TestGetPreventionEngine:
    """Test _get_prevention_engine helper function."""
    
    def test_creates_prevention_engine(self):
        """Test that _get_prevention_engine creates a PreventionEngine instance."""
        with patch('src.lambda_handler.BudgetMonitor'), \
             patch('src.lambda_handler.ResourceManager'), \
             patch('src.lambda_handler.IdleDetector'), \
             patch('src.lambda_handler.SafetyGuard'), \
             patch('src.lambda_handler.ActionExecutor'), \
             patch('src.lambda_handler.ApprovalManager'), \
             patch('src.lambda_handler.RollbackManager'), \
             patch('src.lambda_handler.NotificationService'), \
             patch('src.lambda_handler.PreventionEngine') as mock_engine:
            
            engine = _get_prevention_engine()
            
            # Verify PreventionEngine was instantiated
            mock_engine.assert_called_once()
            
            # Verify all required components were passed
            call_kwargs = mock_engine.call_args[1]
            assert 'budget_monitor' in call_kwargs
            assert 'resource_manager' in call_kwargs
            assert 'idle_detector' in call_kwargs
            assert 'safety_guard' in call_kwargs
            assert 'action_executor' in call_kwargs
            assert 'approval_manager' in call_kwargs
            assert 'rollback_manager' in call_kwargs
            assert 'notification_service' in call_kwargs


class TestEventBridgeIntegration:
    """Test EventBridge scheduled event handling."""
    
    def test_eventbridge_scheduled_event(self):
        """Test handling EventBridge scheduled event"""
        event = {
            'source': 'aws.events',
            'detail-type': 'Scheduled Event',
            'time': '2024-01-15T10:00:00Z',
            'resources': ['arn:aws:events:us-east-1:123456789012:rule/cost-prevention']
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.monitor_budgets.return_value = {
                'status': 'success',
                'budgets_checked': 2
            }
            mock_get_engine.return_value = mock_engine
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert 'result' in body
            mock_engine.monitor_budgets.assert_called_once()
    
    def test_eventbridge_custom_event(self):
        """Test handling custom budget monitoring event"""
        event = {
            'type': 'budget-monitoring',
            'time': '2024-01-15T10:00:00Z'
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.monitor_budgets.return_value = {
                'status': 'success'
            }
            mock_get_engine.return_value = mock_engine
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
    
    def test_eventbridge_event_with_error(self):
        """Test handling EventBridge event when engine raises error"""
        event = {
            'type': 'budget-monitoring',
            'time': '2024-01-15T10:00:00Z'
        }
        
        with patch('src.lambda_handler._get_prevention_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.monitor_budgets.side_effect = Exception("Engine error")
            mock_get_engine.return_value = mock_engine
            
            response = handler(event, None)
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert body['success'] is False

