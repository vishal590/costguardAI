"""
Integration tests for Bedrock cost tracking API endpoints

Tests the complete flow from API Gateway request to Bedrock cost tracking response.
Validates requirements FR-7.1, FR-7.4
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from src.ai_ml_handler import (
    handle_bedrock_costs,
    handle_bedrock_cost_per_invocation
)
from src.services.ai_ml.bedrock_cost_tracker import (
    BedrockCosts,
    ModelRecommendation
)


class TestBedrockCostsAPI:
    """Integration tests for Bedrock costs API endpoint"""
    
    def test_bedrock_costs_success(self):
        """
        Test successful Bedrock costs request
        
        Validates: FR-7.1, FR-7.2
        """
        # Create mock event
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/bedrock-costs',
            'queryStringParameters': {
                'start_date': start_date,
                'end_date': end_date
            }
        }
        
        # Mock Bedrock costs
        mock_costs = [
            BedrockCosts(
                date=datetime.now(),
                model_id='anthropic.claude-v2',
                invocations=1000,
                input_tokens=500000,
                output_tokens=250000,
                total_cost=8.26,
                cost_per_invocation=0.00826
            ),
            BedrockCosts(
                date=datetime.now(),
                model_id='amazon.titan-text-express-v1',
                invocations=2000,
                input_tokens=1000000,
                output_tokens=500000,
                total_cost=0.30,
                cost_per_invocation=0.00015
            )
        ]
        
        with patch('src.ai_ml_handler.BedrockCostTracker') as mock_tracker_class:
            mock_tracker = Mock()
            mock_tracker.track_bedrock_costs.return_value = mock_costs
            mock_tracker_class.return_value = mock_tracker
            
            # Call handler
            response = handle_bedrock_costs(event)
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['total_models'] == 2
        assert len(body['models']) == 2
        
        # Verify first model
        model1 = body['models'][0]
        assert model1['model_id'] == 'anthropic.claude-v2'
        assert model1['invocations'] == 1000
        assert model1['input_tokens'] == 500000
        assert model1['output_tokens'] == 250000
        assert model1['total_cost'] == 8.26
        
        # Verify totals
        assert body['totals']['total_cost'] == 8.56
        assert body['totals']['total_invocations'] == 3000
        assert body['totals']['total_input_tokens'] == 1500000
        assert body['totals']['total_output_tokens'] == 750000
    
    def test_bedrock_costs_with_model_filter(self):
        """
        Test Bedrock costs filtered by model
        
        Validates: FR-7.2
        """
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/bedrock-costs',
            'queryStringParameters': {
                'start_date': start_date,
                'end_date': end_date,
                'model': 'anthropic.claude-v2'
            }
        }
        
        mock_costs = [
            BedrockCosts(
                date=datetime.now(),
                model_id='anthropic.claude-v2',
                invocations=1000,
                input_tokens=500000,
                output_tokens=250000,
                total_cost=8.26,
                cost_per_invocation=0.00826
            )
        ]
        
        with patch('src.ai_ml_handler.BedrockCostTracker') as mock_tracker_class:
            mock_tracker = Mock()
            mock_tracker.track_bedrock_costs.return_value = mock_costs
            mock_tracker_class.return_value = mock_tracker
            
            response = handle_bedrock_costs(event)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['model_filter'] == 'anthropic.claude-v2'
        assert body['total_models'] == 1
        assert body['models'][0]['model_id'] == 'anthropic.claude-v2'
        
        # Verify tracker was called with model filter
        mock_tracker.track_bedrock_costs.assert_called_once()
        call_args = mock_tracker.track_bedrock_costs.call_args
        assert call_args[0][2] == 'anthropic.claude-v2'  # Third argument is model_id
    
    def test_bedrock_costs_missing_parameters(self):
        """Test Bedrock costs with missing required parameters"""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/bedrock-costs',
            'queryStringParameters': {}
        }
        
        response = handle_bedrock_costs(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETERS'
    
    def test_bedrock_costs_invalid_date_format(self):
        """Test Bedrock costs with invalid date format"""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/bedrock-costs',
            'queryStringParameters': {
                'start_date': 'invalid-date',
                'end_date': '2024-01-01'
            }
        }
        
        response = handle_bedrock_costs(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_PARAMETER'
    
    def test_bedrock_costs_invalid_date_range(self):
        """Test Bedrock costs with invalid date range (start > end)"""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/bedrock-costs',
            'queryStringParameters': {
                'start_date': '2024-12-31',
                'end_date': '2024-01-01'
            }
        }
        
        response = handle_bedrock_costs(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_DATE_RANGE'
    
    def test_bedrock_costs_future_date(self):
        """Test Bedrock costs with future end date"""
        future_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        start_date = datetime.now().strftime('%Y-%m-%d')
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/bedrock-costs',
            'queryStringParameters': {
                'start_date': start_date,
                'end_date': future_date
            }
        }
        
        response = handle_bedrock_costs(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_DATE_RANGE'


class TestBedrockCostPerInvocationAPI:
    """Integration tests for Bedrock cost-per-invocation API"""
    
    def test_cost_per_invocation_success(self):
        """
        Test successful cost-per-invocation request
        
        Validates: FR-7.3, FR-7.4
        """
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/bedrock-cost-per-invocation',
            'queryStringParameters': {
                'start_date': start_date,
                'end_date': end_date,
                'model': 'anthropic.claude-v2'
            }
        }
        
        # Mock responses
        mock_costs = [
            BedrockCosts(
                date=datetime.now(),
                model_id='anthropic.claude-v2',
                invocations=1000,
                input_tokens=500000,
                output_tokens=250000,
                total_cost=8.26,
                cost_per_invocation=0.00826
            )
        ]
        
        mock_token_usage = {
            'input_tokens': 500000,
            'output_tokens': 250000,
            'total_tokens': 750000
        }
        
        with patch('src.ai_ml_handler.BedrockCostTracker') as mock_tracker_class:
            mock_tracker = Mock()
            mock_tracker.calculate_cost_per_invocation.return_value = 0.00826
            mock_tracker.track_token_usage.return_value = mock_token_usage
            mock_tracker.track_bedrock_costs.return_value = mock_costs
            mock_tracker.recommend_cost_optimized_models.return_value = []
            mock_tracker_class.return_value = mock_tracker
            
            response = handle_bedrock_cost_per_invocation(event)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['model_id'] == 'anthropic.claude-v2'
        assert body['cost_per_invocation'] == 0.00826
        assert body['total_invocations'] == 1000
        assert body['total_cost'] == 8.26
        
        # Verify token usage
        assert body['token_usage']['input_tokens'] == 500000
        assert body['token_usage']['output_tokens'] == 250000
        assert body['token_usage']['total_tokens'] == 750000
        assert body['token_usage']['avg_input_tokens_per_invocation'] == 500
        assert body['token_usage']['avg_output_tokens_per_invocation'] == 250
        
        # Verify cost breakdown
        assert 'cost_breakdown' in body
        assert 'cost_per_1k_input_tokens' in body['cost_breakdown']
        assert 'cost_per_1k_output_tokens' in body['cost_breakdown']
    
    def test_cost_per_invocation_with_recommendations(self):
        """
        Test cost-per-invocation with model recommendations
        
        Validates: FR-7.6
        """
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/bedrock-cost-per-invocation',
            'queryStringParameters': {
                'start_date': start_date,
                'end_date': end_date,
                'model': 'anthropic.claude-v2'
            }
        }
        
        mock_costs = [
            BedrockCosts(
                date=datetime.now(),
                model_id='anthropic.claude-v2',
                invocations=1000,
                input_tokens=500000,
                output_tokens=250000,
                total_cost=8.26,
                cost_per_invocation=0.00826
            )
        ]
        
        mock_recommendations = [
            ModelRecommendation(
                current_model='anthropic.claude-v2',
                recommended_model='anthropic.claude-instant-v1',
                current_cost_per_1k_tokens=0.01102,
                recommended_cost_per_1k_tokens=0.00163,
                savings_percent=85.2,
                reason='Claude Instant provides fast responses at lower cost for simpler tasks'
            )
        ]
        
        with patch('src.ai_ml_handler.BedrockCostTracker') as mock_tracker_class:
            mock_tracker = Mock()
            mock_tracker.calculate_cost_per_invocation.return_value = 0.00826
            mock_tracker.track_token_usage.return_value = {
                'input_tokens': 500000,
                'output_tokens': 250000,
                'total_tokens': 750000
            }
            mock_tracker.track_bedrock_costs.return_value = mock_costs
            mock_tracker.recommend_cost_optimized_models.return_value = mock_recommendations
            mock_tracker_class.return_value = mock_tracker
            
            response = handle_bedrock_cost_per_invocation(event)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Verify recommendations
        assert 'recommendations' in body
        assert len(body['recommendations']) == 1
        
        rec = body['recommendations'][0]
        assert rec['recommended_model'] == 'anthropic.claude-instant-v1'
        assert rec['savings_percent'] == 85.2
        assert 'estimated_monthly_savings' in rec
        assert rec['reason'] == 'Claude Instant provides fast responses at lower cost for simpler tasks'
    
    def test_cost_per_invocation_missing_parameters(self):
        """Test cost-per-invocation with missing required parameters"""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/bedrock-cost-per-invocation',
            'queryStringParameters': {
                'start_date': '2024-01-01'
                # Missing end_date and model
            }
        }
        
        response = handle_bedrock_cost_per_invocation(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETERS'
    
    def test_cost_per_invocation_no_data(self):
        """Test cost-per-invocation when no data is found"""
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/bedrock-cost-per-invocation',
            'queryStringParameters': {
                'start_date': start_date,
                'end_date': end_date,
                'model': 'nonexistent.model'
            }
        }
        
        with patch('src.ai_ml_handler.BedrockCostTracker') as mock_tracker_class:
            mock_tracker = Mock()
            mock_tracker.calculate_cost_per_invocation.return_value = 0.0
            mock_tracker.track_token_usage.return_value = {
                'input_tokens': 0,
                'output_tokens': 0,
                'total_tokens': 0
            }
            mock_tracker.track_bedrock_costs.return_value = []  # No data
            mock_tracker_class.return_value = mock_tracker
            
            response = handle_bedrock_cost_per_invocation(event)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['error']['code'] == 'NO_DATA'
    
    def test_cost_per_invocation_invalid_date_format(self):
        """Test cost-per-invocation with invalid date format"""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/bedrock-cost-per-invocation',
            'queryStringParameters': {
                'start_date': 'invalid',
                'end_date': '2024-01-01',
                'model': 'anthropic.claude-v2'
            }
        }
        
        response = handle_bedrock_cost_per_invocation(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_PARAMETER'
