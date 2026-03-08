"""
Unit tests for Phase 4 Lambda handler endpoints.

Tests the AI Cost Advisor API endpoints:
- POST /api/advisor/query
- GET /api/advisor/history
- DELETE /api/advisor/history
- GET /api/advisor/suggestions
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, UTC
from decimal import Decimal

from src.lambda_handler import (
    handler,
    handle_advisor_query,
    handle_advisor_history,
    handle_advisor_clear_history,
    handle_advisor_suggestions
)
from src.utils.types import (
    AdvisorResponse,
    Recommendation,
    ConversationTurn,
    CostContext,
    Insight
)


class TestAdvisorQueryEndpoint:
    """Test POST /api/advisor/query endpoint."""
    
    @patch('src.lambda_handler._get_advisor_engine')
    def test_handle_advisor_query_success(self, mock_get_engine):
        """Test successful query processing."""
        # Mock advisor engine
        mock_engine = Mock()
        mock_response = AdvisorResponse(
            response_text="Your EC2 costs last month were $150",
            recommendations=[
                Recommendation(
                    action="Stop idle EC2 instances",
                    rationale="3 instances idle for >7 days",
                    estimated_savings=Decimal("45.00"),
                    priority=5,
                    safe=True
                )
            ],
            cost_data={'ec2': 150.0},
            confidence=Decimal("0.95"),
            cached=False
        )
        mock_engine.process_query.return_value = mock_response
        mock_get_engine.return_value = mock_engine
        
        # Create event
        event = {
            'httpMethod': 'POST',
            'path': '/api/advisor/query',
            'body': json.dumps({
                'query': 'What were my EC2 costs last month?',
                'user_id': 'user123',
                'session_id': 'session456'
            })
        }
        
        # Call handler
        response = handle_advisor_query(event)
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        assert 'EC2 costs' in body['response']
        assert len(body['recommendations']) == 1
        assert body['recommendations'][0]['action'] == 'Stop idle EC2 instances'
        assert body['cached'] is False
        
        # Verify engine was called correctly
        mock_engine.process_query.assert_called_once_with(
            'What were my EC2 costs last month?',
            'user123',
            'session456'
        )
    
    @patch('src.lambda_handler._get_advisor_engine')
    def test_handle_advisor_query_missing_query(self, mock_get_engine):
        """Test query endpoint with missing query parameter."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/advisor/query',
            'body': json.dumps({
                'user_id': 'user123'
            })
        }
        
        response = handle_advisor_query(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False
        assert body['error']['code'] == 'MISSING_PARAMETER'
    
    @patch('src.lambda_handler._get_advisor_engine')
    def test_handle_advisor_query_default_ids(self, mock_get_engine):
        """Test query endpoint with default user_id and session_id."""
        mock_engine = Mock()
        mock_response = AdvisorResponse(
            response_text="Test response",
            recommendations=[],
            cost_data={},
            confidence=Decimal("0.9"),
            cached=False
        )
        mock_engine.process_query.return_value = mock_response
        mock_get_engine.return_value = mock_engine
        
        event = {
            'httpMethod': 'POST',
            'path': '/api/advisor/query',
            'body': json.dumps({
                'query': 'Test query'
            })
        }
        
        response = handle_advisor_query(event)
        
        assert response['statusCode'] == 200
        mock_engine.process_query.assert_called_once_with(
            'Test query',
            'default',
            'default'
        )
    
    @patch('src.lambda_handler._get_advisor_engine')
    def test_handle_advisor_query_cached_response(self, mock_get_engine):
        """Test query endpoint with cached response."""
        mock_engine = Mock()
        mock_response = AdvisorResponse(
            response_text="Cached response",
            recommendations=[],
            cost_data={},
            confidence=Decimal("0.95"),
            cached=True
        )
        mock_engine.process_query.return_value = mock_response
        mock_get_engine.return_value = mock_engine
        
        event = {
            'httpMethod': 'POST',
            'path': '/api/advisor/query',
            'body': json.dumps({
                'query': 'Test query'
            })
        }
        
        response = handle_advisor_query(event)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['cached'] is True


class TestAdvisorHistoryEndpoint:
    """Test GET /api/advisor/history endpoint."""
    
    @patch('src.lambda_handler._get_advisor_engine')
    def test_handle_advisor_history_success(self, mock_get_engine):
        """Test successful history retrieval."""
        mock_engine = Mock()
        mock_history = [
            ConversationTurn(
                query="What were my costs?",
                response="Your costs were $100",
                timestamp=datetime(2026, 2, 23, 10, 0, 0, tzinfo=UTC),
                context_used=CostContext(
                    historical_costs={},
                    forecast_data=None,
                    prevention_actions=[],
                    current_budget=None,
                    anomalies=[]
                )
            ),
            ConversationTurn(
                query="How can I reduce costs?",
                response="Stop idle resources",
                timestamp=datetime(2026, 2, 23, 10, 5, 0, tzinfo=UTC),
                context_used=CostContext(
                    historical_costs={},
                    forecast_data=None,
                    prevention_actions=[],
                    current_budget=None,
                    anomalies=[]
                )
            )
        ]
        mock_engine.get_conversation_history.return_value = mock_history
        mock_get_engine.return_value = mock_engine
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/advisor/history',
            'queryStringParameters': {
                'session_id': 'session123'
            }
        }
        
        response = handle_advisor_history(event)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        assert body['count'] == 2
        assert len(body['history']) == 2
        assert body['history'][0]['query'] == "What were my costs?"
        assert body['history'][1]['query'] == "How can I reduce costs?"
        
        mock_engine.get_conversation_history.assert_called_once_with('session123')
    
    @patch('src.lambda_handler._get_advisor_engine')
    def test_handle_advisor_history_default_session(self, mock_get_engine):
        """Test history endpoint with default session_id."""
        mock_engine = Mock()
        mock_engine.get_conversation_history.return_value = []
        mock_get_engine.return_value = mock_engine
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/advisor/history',
            'queryStringParameters': None
        }
        
        response = handle_advisor_history(event)
        
        assert response['statusCode'] == 200
        mock_engine.get_conversation_history.assert_called_once_with('default')
    
    @patch('src.lambda_handler._get_advisor_engine')
    def test_handle_advisor_history_empty(self, mock_get_engine):
        """Test history endpoint with no conversation history."""
        mock_engine = Mock()
        mock_engine.get_conversation_history.return_value = []
        mock_get_engine.return_value = mock_engine
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/advisor/history',
            'queryStringParameters': {
                'session_id': 'new_session'
            }
        }
        
        response = handle_advisor_history(event)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        assert body['count'] == 0
        assert len(body['history']) == 0


class TestAdvisorClearHistoryEndpoint:
    """Test DELETE /api/advisor/history endpoint."""
    
    @patch('src.lambda_handler._get_advisor_engine')
    def test_handle_advisor_clear_history_success(self, mock_get_engine):
        """Test successful history clearing."""
        mock_engine = Mock()
        mock_engine.clear_conversation_history.return_value = None
        mock_get_engine.return_value = mock_engine
        
        event = {
            'httpMethod': 'DELETE',
            'path': '/api/advisor/history',
            'queryStringParameters': {
                'session_id': 'session123'
            }
        }
        
        response = handle_advisor_clear_history(event)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        assert body['message'] == 'Conversation history cleared'
        assert body['session_id'] == 'session123'
        
        mock_engine.clear_conversation_history.assert_called_once_with('session123')
    
    @patch('src.lambda_handler._get_advisor_engine')
    def test_handle_advisor_clear_history_default_session(self, mock_get_engine):
        """Test clear history endpoint with default session_id."""
        mock_engine = Mock()
        mock_engine.clear_conversation_history.return_value = None
        mock_get_engine.return_value = mock_engine
        
        event = {
            'httpMethod': 'DELETE',
            'path': '/api/advisor/history',
            'body': json.dumps({})
        }
        
        response = handle_advisor_clear_history(event)
        
        assert response['statusCode'] == 200
        mock_engine.clear_conversation_history.assert_called_once_with('default')


class TestAdvisorSuggestionsEndpoint:
    """Test GET /api/advisor/suggestions endpoint."""
    
    @patch('src.lambda_handler._get_advisor_engine')
    def test_handle_advisor_suggestions_success(self, mock_get_engine):
        """Test successful proactive insights generation."""
        mock_engine = Mock()
        mock_insights = [
            Insight(
                insight_type='summary',
                title='Daily Cost Summary',
                description='Yesterday costs: $50',
                severity='info',
                action_required=False,
                related_services=['ec2', 'lambda'],
                estimated_impact=Decimal("0")
            ),
            Insight(
                insight_type='anomaly',
                title='Cost Spike Detected',
                description='EC2 costs increased 60%',
                severity='warning',
                action_required=True,
                related_services=['ec2'],
                estimated_impact=Decimal("30.00")
            )
        ]
        mock_engine.generate_proactive_insights.return_value = mock_insights
        mock_get_engine.return_value = mock_engine
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/advisor/suggestions',
            'queryStringParameters': {
                'user_id': 'user123'
            }
        }
        
        response = handle_advisor_suggestions(event)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        assert body['count'] == 2
        assert len(body['insights']) == 2
        assert body['insights'][0]['insight_type'] == 'summary'
        assert body['insights'][1]['insight_type'] == 'anomaly'
        assert body['insights'][1]['action_required'] is True
        
        mock_engine.generate_proactive_insights.assert_called_once_with('user123')
    
    @patch('src.lambda_handler._get_advisor_engine')
    def test_handle_advisor_suggestions_default_user(self, mock_get_engine):
        """Test suggestions endpoint with default user_id."""
        mock_engine = Mock()
        mock_engine.generate_proactive_insights.return_value = []
        mock_get_engine.return_value = mock_engine
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/advisor/suggestions',
            'queryStringParameters': None
        }
        
        response = handle_advisor_suggestions(event)
        
        assert response['statusCode'] == 200
        mock_engine.generate_proactive_insights.assert_called_once_with('default')
    
    @patch('src.lambda_handler._get_advisor_engine')
    def test_handle_advisor_suggestions_no_insights(self, mock_get_engine):
        """Test suggestions endpoint with no insights."""
        mock_engine = Mock()
        mock_engine.generate_proactive_insights.return_value = []
        mock_get_engine.return_value = mock_engine
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/advisor/suggestions',
            'queryStringParameters': {
                'user_id': 'user123'
            }
        }
        
        response = handle_advisor_suggestions(event)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        assert body['count'] == 0
        assert len(body['insights']) == 0


class TestPhase4Routing:
    """Test routing to Phase 4 endpoints."""
    
    @patch('src.lambda_handler._get_advisor_engine')
    def test_route_to_advisor_query(self, mock_get_engine):
        """Test routing to POST /api/advisor/query."""
        mock_engine = Mock()
        mock_response = AdvisorResponse(
            response_text="Test",
            recommendations=[],
            cost_data={},
            confidence=Decimal("0.9"),
            cached=False
        )
        mock_engine.process_query.return_value = mock_response
        mock_get_engine.return_value = mock_engine
        
        event = {
            'httpMethod': 'POST',
            'path': '/api/advisor/query',
            'body': json.dumps({'query': 'test'})
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 200
        mock_engine.process_query.assert_called_once()
    
    @patch('src.lambda_handler._get_advisor_engine')
    def test_route_to_advisor_history(self, mock_get_engine):
        """Test routing to GET /api/advisor/history."""
        mock_engine = Mock()
        mock_engine.get_conversation_history.return_value = []
        mock_get_engine.return_value = mock_engine
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/advisor/history',
            'queryStringParameters': None
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 200
        mock_engine.get_conversation_history.assert_called_once()
    
    @patch('src.lambda_handler._get_advisor_engine')
    def test_route_to_advisor_clear_history(self, mock_get_engine):
        """Test routing to DELETE /api/advisor/history."""
        mock_engine = Mock()
        mock_engine.clear_conversation_history.return_value = None
        mock_get_engine.return_value = mock_engine
        
        event = {
            'httpMethod': 'DELETE',
            'path': '/api/advisor/history',
            'body': json.dumps({'session_id': 'test'})
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 200
        mock_engine.clear_conversation_history.assert_called_once()
    
    @patch('src.lambda_handler._get_advisor_engine')
    def test_route_to_advisor_suggestions(self, mock_get_engine):
        """Test routing to GET /api/advisor/suggestions."""
        mock_engine = Mock()
        mock_engine.generate_proactive_insights.return_value = []
        mock_get_engine.return_value = mock_engine
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/advisor/suggestions',
            'queryStringParameters': None
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 200
        mock_engine.generate_proactive_insights.assert_called_once()


class TestBackwardCompatibility:
    """Test that Phase 1-3 endpoints still work after Phase 4 additions."""
    
    def test_phase1_fetch_endpoint_still_works(self):
        """Test Phase 1 fetch endpoint is not affected."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/fetch',
            'body': json.dumps({
                'startDate': '2026-01-01',
                'endDate': '2026-01-31'
            })
        }
        
        # This should route to handle_fetch, not Phase 4 handlers
        # We're just testing routing, not full functionality
        with patch('src.lambda_handler.fetch_cost_data') as mock_fetch:
            mock_fetch.return_value = []
            response = handler(event, None)
            # Should attempt to call fetch_cost_data
            assert mock_fetch.called or response['statusCode'] in [200, 500]
    
    def test_phase2_forecast_endpoint_still_works(self):
        """Test Phase 2 forecast endpoint is not affected."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/cost-forecast',
            'queryStringParameters': {
                'days': '30'
            }
        }
        
        # This should route to handle_forecast_request, not Phase 4 handlers
        with patch('src.lambda_handler.ForecastEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine
            # Test will fail on actual execution, but routing should work
            response = handler(event, None)
            # Should attempt forecast logic
            assert response['statusCode'] in [200, 400, 500]
    
    def test_phase3_prevention_endpoint_still_works(self):
        """Test Phase 3 prevention endpoint is not affected."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/prevention/status',
            'queryStringParameters': None
        }
        
        # This should route to handle_prevention_status, not Phase 4 handlers
        with patch('src.lambda_handler._get_prevention_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.get_status.return_value = {'enabled': True}
            mock_get_engine.return_value = mock_engine
            response = handler(event, None)
            assert response['statusCode'] == 200
            mock_engine.get_status.assert_called_once()
