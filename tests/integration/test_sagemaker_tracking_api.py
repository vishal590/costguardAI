"""
Integration tests for SageMaker cost tracking API endpoints

Tests the complete flow from API Gateway request to SageMaker cost tracking response.
Validates requirements FR-6.1, FR-6.2, FR-6.6
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from src.ai_ml_handler import (
    handle_sagemaker_costs,
    handle_sagemaker_idle_endpoints
)
from src.services.ai_ml.sagemaker_cost_tracker import (
    SageMakerCosts,
    JobCost,
    EndpointMetrics
)


class TestSageMakerCostsAPI:
    """Integration tests for SageMaker costs API endpoint"""
    
    def test_sagemaker_costs_success(self):
        """
        Test successful SageMaker costs request
        
        Validates: FR-6.1, FR-6.2, FR-6.3, FR-6.4
        """
        # Create mock event
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/sagemaker-costs',
            'queryStringParameters': {
                'start_date': start_date,
                'end_date': end_date
            }
        }
        
        # Mock SageMaker costs
        mock_costs = SageMakerCosts(
            date=datetime.now(),
            training_costs=1500.0,
            inference_costs=800.0,
            notebook_costs=200.0,
            total_cost=2500.0,
            job_breakdown=[]
        )
        
        with patch('src.ai_ml_handler.SageMakerCostTracker') as mock_tracker_class, \
             patch('src.ai_ml_handler.get_cache_manager') as mock_cache_manager:
            mock_tracker = Mock()
            mock_tracker.track_sagemaker_costs.return_value = mock_costs
            mock_tracker_class.return_value = mock_tracker
            
            # Mock cache manager to return None (cache miss)
            mock_cache = Mock()
            mock_cache.get_cached_data.return_value = None
            mock_cache_manager.return_value = mock_cache
            
            # Call handler
            response = handle_sagemaker_costs(event)
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['training_costs'] == 1500.0
        assert body['inference_costs'] == 800.0
        assert body['notebook_costs'] == 200.0
        assert body['total_cost'] == 2500.0
        assert 'job_breakdown' in body

    
    def test_sagemaker_costs_with_job_breakdown(self):
        """
        Test SageMaker costs with detailed job breakdown
        
        Validates: FR-6.1, FR-6.4
        """
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/sagemaker-costs',
            'queryStringParameters': {
                'start_date': start_date,
                'end_date': end_date
            }
        }
        
        # Create job breakdown
        job1 = JobCost(
            job_name='training-job-1',
            job_type='training',
            instance_type='ml.p3.2xlarge',
            start_time=datetime.now() - timedelta(hours=5),
            end_time=datetime.now() - timedelta(hours=3),
            duration_hours=2.0,
            compute_cost=7.65,
            storage_cost=0.38,
            data_transfer_cost=0.23,
            total_cost=8.26
        )
        
        mock_costs = SageMakerCosts(
            date=datetime.now(),
            training_costs=8.26,
            inference_costs=0.0,
            notebook_costs=0.0,
            total_cost=8.26,
            job_breakdown=[job1]
        )
        
        with patch('src.ai_ml_handler.SageMakerCostTracker') as mock_tracker_class, \
             patch('src.ai_ml_handler.get_cache_manager') as mock_cache_manager:
            mock_tracker = Mock()
            mock_tracker.track_sagemaker_costs.return_value = mock_costs
            mock_tracker_class.return_value = mock_tracker
            
            # Mock cache manager to return None (cache miss)
            mock_cache = Mock()
            mock_cache.get_cached_data.return_value = None
            mock_cache_manager.return_value = mock_cache
            
            response = handle_sagemaker_costs(event)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert len(body['job_breakdown']) == 1
        job = body['job_breakdown'][0]
        assert job['job_name'] == 'training-job-1'
        assert job['job_type'] == 'training'
        assert job['instance_type'] == 'ml.p3.2xlarge'
        assert job['total_cost'] == 8.26

    
    def test_sagemaker_costs_with_job_type_filter(self):
        """
        Test SageMaker costs filtered by job type
        
        Validates: FR-6.4
        """
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/sagemaker-costs',
            'queryStringParameters': {
                'start_date': start_date,
                'end_date': end_date,
                'job_type': 'training'
            }
        }
        
        mock_costs = SageMakerCosts(
            date=datetime.now(),
            training_costs=1500.0,
            inference_costs=800.0,
            notebook_costs=200.0,
            total_cost=2500.0,
            job_breakdown=[]
        )
        
        with patch('src.ai_ml_handler.SageMakerCostTracker') as mock_tracker_class, \
             patch('src.ai_ml_handler.get_cache_manager') as mock_cache_manager:
            mock_tracker = Mock()
            mock_tracker.track_sagemaker_costs.return_value = mock_costs
            mock_tracker_class.return_value = mock_tracker
            
            # Mock cache manager to return None (cache miss)
            mock_cache = Mock()
            mock_cache.get_cached_data.return_value = None
            mock_cache_manager.return_value = mock_cache
            
            response = handle_sagemaker_costs(event)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # When filtering by training, only training costs should be in total
        assert body['training_costs'] == 1500.0
        assert body['inference_costs'] == 0
        assert body['notebook_costs'] == 0
        assert body['total_cost'] == 1500.0
    
    def test_sagemaker_costs_missing_parameters(self):
        """Test SageMaker costs with missing required parameters"""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/sagemaker-costs',
            'queryStringParameters': {}
        }
        
        response = handle_sagemaker_costs(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETER'

    
    def test_sagemaker_costs_invalid_date_format(self):
        """Test SageMaker costs with invalid date format"""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/sagemaker-costs',
            'queryStringParameters': {
                'start_date': 'invalid-date',
                'end_date': '2024-01-01'
            }
        }
        
        response = handle_sagemaker_costs(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_DATE_FORMAT'
    
    def test_sagemaker_costs_invalid_job_type(self):
        """Test SageMaker costs with invalid job type"""
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/sagemaker-costs',
            'queryStringParameters': {
                'start_date': start_date,
                'end_date': end_date,
                'job_type': 'invalid_type'
            }
        }
        
        response = handle_sagemaker_costs(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_JOB_TYPE'


class TestSageMakerIdleEndpointsAPI:
    """Integration tests for SageMaker idle endpoints API"""
    
    def test_idle_endpoints_success(self):
        """
        Test successful idle endpoints request
        
        Validates: FR-6.6
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/sagemaker-idle-endpoints',
            'queryStringParameters': {}
        }

        
        # Mock idle endpoints
        idle_endpoint = EndpointMetrics(
            endpoint_name='idle-endpoint-1',
            instance_type='ml.m5.xlarge',
            instance_count=1,
            requests_per_hour=5.0,
            avg_latency_ms=100.0,
            cost_per_hour=0.23,
            is_idle=True
        )
        
        with patch('src.ai_ml_handler.SageMakerCostTracker') as mock_tracker_class:
            mock_tracker = Mock()
            mock_tracker.identify_idle_endpoints.return_value = [idle_endpoint]
            mock_tracker_class.return_value = mock_tracker
            
            response = handle_sagemaker_idle_endpoints(event)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['threshold'] == 10
        assert body['idle_endpoint_count'] == 1
        assert len(body['idle_endpoints']) == 1
        
        endpoint = body['idle_endpoints'][0]
        assert endpoint['endpoint_name'] == 'idle-endpoint-1'
        assert endpoint['requests_per_hour'] == 5.0
        assert endpoint['is_idle'] is True
        assert 'recommendation' in endpoint
    
    def test_idle_endpoints_with_custom_threshold(self):
        """
        Test idle endpoints with custom threshold
        
        Validates: FR-6.6
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/sagemaker-idle-endpoints',
            'queryStringParameters': {
                'threshold': '20'
            }
        }
        
        with patch('src.ai_ml_handler.SageMakerCostTracker') as mock_tracker_class:
            mock_tracker = Mock()
            mock_tracker.identify_idle_endpoints.return_value = []
            mock_tracker_class.return_value = mock_tracker
            
            response = handle_sagemaker_idle_endpoints(event)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['threshold'] == 20
        mock_tracker.identify_idle_endpoints.assert_called_once_with(20)

    
    def test_idle_endpoints_calculates_waste(self):
        """
        Test that idle endpoints response includes waste calculations
        
        Validates: FR-6.6
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/sagemaker-idle-endpoints',
            'queryStringParameters': {}
        }
        
        idle_endpoints = [
            EndpointMetrics(
                endpoint_name='idle-1',
                instance_type='ml.m5.xlarge',
                instance_count=1,
                requests_per_hour=3.0,
                avg_latency_ms=100.0,
                cost_per_hour=0.23,
                is_idle=True
            ),
            EndpointMetrics(
                endpoint_name='idle-2',
                instance_type='ml.m5.2xlarge',
                instance_count=2,
                requests_per_hour=5.0,
                avg_latency_ms=120.0,
                cost_per_hour=0.92,
                is_idle=True
            )
        ]
        
        with patch('src.ai_ml_handler.SageMakerCostTracker') as mock_tracker_class:
            mock_tracker = Mock()
            mock_tracker.identify_idle_endpoints.return_value = idle_endpoints
            mock_tracker_class.return_value = mock_tracker
            
            response = handle_sagemaker_idle_endpoints(event)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Verify waste calculations
        expected_hourly_waste = 0.23 + 0.92
        assert body['total_wasted_cost_per_hour'] == expected_hourly_waste
        assert body['estimated_monthly_waste'] == expected_hourly_waste * 24 * 30
    
    def test_idle_endpoints_invalid_threshold(self):
        """Test idle endpoints with invalid threshold"""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/sagemaker-idle-endpoints',
            'queryStringParameters': {
                'threshold': 'invalid'
            }
        }
        
        response = handle_sagemaker_idle_endpoints(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_PARAMETER'
    
    def test_idle_endpoints_negative_threshold(self):
        """Test idle endpoints with negative threshold"""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/sagemaker-idle-endpoints',
            'queryStringParameters': {
                'threshold': '-5'
            }
        }
        
        response = handle_sagemaker_idle_endpoints(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_THRESHOLD'
