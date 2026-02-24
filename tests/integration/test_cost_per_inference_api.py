"""
Integration Tests for Cost-Per-Inference API Endpoints

Tests the cost-per-inference and inference-trends API endpoints end-to-end.

Requirements: FR-3.2, FR-3.3, API-3.1, API-3.2
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from src.ai_ml_handler import handler
from src.services.ai_ml.cost_per_inference_calculator import (
    CostPerInferenceCalculator,
    CostPerInference,
    InferenceCosts,
    CostTrend
)


class TestCostPerInferenceAPI:
    """Integration tests for cost-per-inference API endpoints."""
    
    def test_cost_per_inference_success(self):
        """
        Test successful cost-per-inference calculation.
        
        Requirements: API-3.1, FR-3.1
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/cost-per-inference',
            'queryStringParameters': {
                'start_date': '2024-01-01',
                'end_date': '2024-01-31',
                'model': 'gpt-4',
                'endpoint': 'prod-endpoint'
            }
        }
        
        # Mock the calculator
        with patch('src.ai_ml_handler.CostPerInferenceCalculator') as mock_calc_class:
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            
            mock_result = CostPerInference(
                model='gpt-4',
                endpoint='prod-endpoint',
                date=datetime(2024, 1, 1),
                total_requests=100000,
                total_cost=1250.0,
                cost_per_inference=0.0125,
                compute_cost=1000.0,
                api_cost=200.0,
                data_transfer_cost=50.0
            )
            mock_calc.calculate_cost_per_inference.return_value = mock_result
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            assert body['model'] == 'gpt-4'
            assert body['endpoint'] == 'prod-endpoint'
            assert body['total_requests'] == 100000
            assert body['total_cost'] == 1250.0
            assert body['cost_per_inference'] == 0.0125
            assert body['cost_breakdown']['compute_cost'] == 1000.0
            assert body['cost_breakdown']['api_cost'] == 200.0
            assert body['cost_breakdown']['data_transfer_cost'] == 50.0
    
    def test_cost_per_inference_with_defaults(self):
        """
        Test cost-per-inference with default model and endpoint.
        
        Requirements: API-3.1
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/cost-per-inference',
            'queryStringParameters': {
                'start_date': '2024-01-01',
                'end_date': '2024-01-31'
            }
        }
        
        with patch('src.ai_ml_handler.CostPerInferenceCalculator') as mock_calc_class:
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            
            mock_result = CostPerInference(
                model='default-model',
                endpoint='default-endpoint',
                date=datetime(2024, 1, 1),
                total_requests=1000,
                total_cost=125.0,
                cost_per_inference=0.125,
                compute_cost=100.0,
                api_cost=20.0,
                data_transfer_cost=5.0
            )
            mock_calc.calculate_cost_per_inference.return_value = mock_result
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            assert body['model'] == 'default-model'
            assert body['endpoint'] == 'default-endpoint'
    
    def test_cost_per_inference_missing_dates(self):
        """
        Test cost-per-inference with missing date parameters.
        
        Requirements: API-3.1
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/cost-per-inference',
            'queryStringParameters': {
                'model': 'gpt-4'
            }
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETER'
        assert 'start_date and end_date are required' in body['error']['message']
    
    def test_cost_per_inference_invalid_date_format(self):
        """
        Test cost-per-inference with invalid date format.
        
        Requirements: API-3.1
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/cost-per-inference',
            'queryStringParameters': {
                'start_date': '01/01/2024',
                'end_date': '01/31/2024'
            }
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_DATE_FORMAT'
    
    def test_cost_per_inference_invalid_date_range(self):
        """
        Test cost-per-inference with invalid date range (end before start).
        
        Requirements: API-3.1
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/cost-per-inference',
            'queryStringParameters': {
                'start_date': '2024-01-31',
                'end_date': '2024-01-01'
            }
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_DATE_RANGE'
    
    def test_cost_per_inference_multiple_sources(self):
        """
        Test cost-per-inference with multiple inference sources.
        
        Requirements: FR-3.2
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/cost-per-inference',
            'queryStringParameters': {
                'start_date': '2024-01-01',
                'end_date': '2024-01-31',
                'model': 'multi-source-model',
                'endpoint': 'multi-endpoint'
            }
        }
        
        with patch('src.ai_ml_handler.CostPerInferenceCalculator') as mock_calc_class:
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            
            # Simulate requests from multiple sources
            mock_result = CostPerInference(
                model='multi-source-model',
                endpoint='multi-endpoint',
                date=datetime(2024, 1, 1),
                total_requests=500000,  # API Gateway + Lambda + SageMaker + Bedrock
                total_cost=6250.0,
                cost_per_inference=0.0125,
                compute_cost=5000.0,
                api_cost=1000.0,
                data_transfer_cost=250.0
            )
            mock_calc.calculate_cost_per_inference.return_value = mock_result
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            assert body['total_requests'] == 500000
            assert body['total_cost'] == 6250.0
    
    def test_cost_per_inference_cost_component_aggregation(self):
        """
        Test that cost components are properly aggregated.
        
        Requirements: FR-3.3
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/cost-per-inference',
            'queryStringParameters': {
                'start_date': '2024-01-01',
                'end_date': '2024-01-31',
                'model': 'test-model',
                'endpoint': 'test-endpoint'
            }
        }
        
        with patch('src.ai_ml_handler.CostPerInferenceCalculator') as mock_calc_class:
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            
            mock_result = CostPerInference(
                model='test-model',
                endpoint='test-endpoint',
                date=datetime(2024, 1, 1),
                total_requests=10000,
                total_cost=1000.0,
                cost_per_inference=0.1,
                compute_cost=700.0,
                api_cost=250.0,
                data_transfer_cost=50.0
            )
            mock_calc.calculate_cost_per_inference.return_value = mock_result
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            # Verify all cost components are present
            assert 'cost_breakdown' in body
            assert body['cost_breakdown']['compute_cost'] == 700.0
            assert body['cost_breakdown']['api_cost'] == 250.0
            assert body['cost_breakdown']['data_transfer_cost'] == 50.0
            
            # Verify total equals sum of components
            total_from_components = (
                body['cost_breakdown']['compute_cost'] +
                body['cost_breakdown']['api_cost'] +
                body['cost_breakdown']['data_transfer_cost']
            )
            assert abs(total_from_components - body['total_cost']) < 0.01


class TestInferenceTrendsAPI:
    """Integration tests for inference trends API endpoint."""
    
    def test_inference_trends_success(self):
        """
        Test successful inference trends retrieval.
        
        Requirements: API-3.2, FR-3.5
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/inference-trends',
            'queryStringParameters': {
                'model': 'gpt-4',
                'endpoint': 'prod-endpoint',
                'days': '7'
            }
        }
        
        with patch('src.ai_ml_handler.CostPerInferenceCalculator') as mock_calc_class:
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            
            # Create 7 days of trend data
            trends = []
            for i in range(7):
                date = datetime(2024, 1, 1) + timedelta(days=i)
                trends.append(CostTrend(
                    date=date,
                    cost_per_inference=0.01 + (i * 0.001),
                    total_requests=10000 + (i * 1000),
                    total_cost=100.0 + (i * 10.0)
                ))
            
            mock_calc.track_cost_trends.return_value = trends
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            assert body['model'] == 'gpt-4'
            assert body['endpoint'] == 'prod-endpoint'
            assert body['days'] == 7
            assert len(body['trends']) == 7
            
            # Verify trend data structure
            for i, trend in enumerate(body['trends']):
                assert 'date' in trend
                assert 'cost_per_inference' in trend
                assert 'total_requests' in trend
                assert 'total_cost' in trend
    
    def test_inference_trends_default_days(self):
        """
        Test inference trends with default days (30).
        
        Requirements: API-3.2
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/inference-trends',
            'queryStringParameters': {
                'model': 'gpt-4'
            }
        }
        
        with patch('src.ai_ml_handler.CostPerInferenceCalculator') as mock_calc_class:
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            
            trends = [
                CostTrend(
                    date=datetime(2024, 1, 1) + timedelta(days=i),
                    cost_per_inference=0.01,
                    total_requests=10000,
                    total_cost=100.0
                )
                for i in range(30)
            ]
            mock_calc.track_cost_trends.return_value = trends
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            assert body['days'] == 30
            assert len(body['trends']) == 30
    
    def test_inference_trends_missing_model(self):
        """
        Test inference trends with missing model parameter.
        
        Requirements: API-3.2
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/inference-trends',
            'queryStringParameters': {
                'days': '7'
            }
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETER'
        assert 'model is required' in body['error']['message']
    
    def test_inference_trends_invalid_days(self):
        """
        Test inference trends with invalid days parameter.
        
        Requirements: API-3.2
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/inference-trends',
            'queryStringParameters': {
                'model': 'gpt-4',
                'days': '100'  # Exceeds max of 90
            }
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_DAYS'
    
    def test_inference_trends_non_numeric_days(self):
        """
        Test inference trends with non-numeric days parameter.
        
        Requirements: API-3.2
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/inference-trends',
            'queryStringParameters': {
                'model': 'gpt-4',
                'days': 'invalid'
            }
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_DAYS'
