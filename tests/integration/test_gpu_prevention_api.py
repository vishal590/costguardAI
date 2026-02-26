"""Integration tests for GPU Prevention API endpoints - Requirements: IR-2.3"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from src.ai_ml_handler import handle_gpu_prevention, handle_gpu_cost_savings


class TestGPUPreventionAPI:
    """Test GPU Prevention API endpoints."""
    
    @patch('src.ai_ml_handler.get_dynamodb_client')
    @patch('src.ai_ml_handler.IdleGPUDetector')
    @patch('src.ai_ml_handler.GPUPreventionIntegration')
    def test_gpu_prevention_endpoint_success(self, mock_integration_class, mock_detector_class, mock_dynamodb):
        """Test POST /api/ai-ml/gpu-prevention endpoint with valid request."""
        # Setup mocks
        mock_dynamodb_instance = Mock()
        mock_dynamodb.return_value = mock_dynamodb_instance
        
        mock_detector = Mock()
        mock_detector_class.return_value = mock_detector
        
        mock_integration = Mock()
        mock_integration_class.return_value = mock_integration
        mock_integration.run_gpu_prevention_cycle.return_value = {
            "success": True,
            "idle_gpus_found": 3,
            "actions_planned": 2,
            "actions_executed": 0,
            "total_savings": 1500.00,
            "dry_run": True
        }
        
        # Create event
        event = {
            'httpMethod': 'POST',
            'path': '/api/ai-ml/gpu-prevention',
            'body': json.dumps({
                'start_date': '2024-01-01',
                'end_date': '2024-01-31',
                'threshold': 10.0,
                'dry_run': True
            })
        }
        
        # Execute
        response = handle_gpu_prevention(event)
        
        # Verify
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        assert body['idle_gpus_found'] == 3
        assert body['actions_planned'] == 2
        assert body['actions_executed'] == 0
        assert body['total_savings'] == 1500.00
        assert body['dry_run'] is True
        
        # Verify integration was called correctly
        mock_integration.run_gpu_prevention_cycle.assert_called_once_with(
            start_date='2024-01-01',
            end_date='2024-01-31',
            threshold=10.0,
            dry_run=True
        )
    
    @patch('src.ai_ml_handler.get_dynamodb_client')
    @patch('src.ai_ml_handler.IdleGPUDetector')
    @patch('src.ai_ml_handler.GPUPreventionIntegration')
    def test_gpu_prevention_endpoint_with_execution(self, mock_integration_class, mock_detector_class, mock_dynamodb):
        """Test POST /api/ai-ml/gpu-prevention endpoint with dry_run=false."""
        # Setup mocks
        mock_dynamodb_instance = Mock()
        mock_dynamodb.return_value = mock_dynamodb_instance
        
        mock_detector = Mock()
        mock_detector_class.return_value = mock_detector
        
        mock_integration = Mock()
        mock_integration_class.return_value = mock_integration
        mock_integration.run_gpu_prevention_cycle.return_value = {
            "success": True,
            "idle_gpus_found": 3,
            "actions_planned": 2,
            "actions_executed": 2,
            "total_savings": 1500.00,
            "dry_run": False
        }
        
        # Create event
        event = {
            'httpMethod': 'POST',
            'path': '/api/ai-ml/gpu-prevention',
            'body': json.dumps({
                'start_date': '2024-01-01',
                'end_date': '2024-01-31',
                'threshold': 10.0,
                'dry_run': False
            })
        }
        
        # Execute
        response = handle_gpu_prevention(event)
        
        # Verify
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        assert body['actions_executed'] == 2
        assert body['dry_run'] is False
    
    def test_gpu_prevention_endpoint_missing_dates(self):
        """Test POST /api/ai-ml/gpu-prevention endpoint with missing dates."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/ai-ml/gpu-prevention',
            'body': json.dumps({
                'threshold': 10.0,
                'dry_run': True
            })
        }
        
        response = handle_gpu_prevention(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETERS'
    
    def test_gpu_prevention_endpoint_invalid_date_format(self):
        """Test POST /api/ai-ml/gpu-prevention endpoint with invalid date format."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/ai-ml/gpu-prevention',
            'body': json.dumps({
                'start_date': '01/01/2024',  # Invalid format
                'end_date': '2024-01-31',
                'threshold': 10.0,
                'dry_run': True
            })
        }
        
        response = handle_gpu_prevention(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_DATE_FORMAT'
    
    def test_gpu_prevention_endpoint_invalid_date_range(self):
        """Test POST /api/ai-ml/gpu-prevention endpoint with invalid date range."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/ai-ml/gpu-prevention',
            'body': json.dumps({
                'start_date': '2024-01-31',
                'end_date': '2024-01-01',  # End before start
                'threshold': 10.0,
                'dry_run': True
            })
        }
        
        response = handle_gpu_prevention(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_DATE_RANGE'
    
    @patch('src.ai_ml_handler.get_dynamodb_client')
    @patch('src.ai_ml_handler.IdleGPUDetector')
    @patch('src.ai_ml_handler.GPUPreventionIntegration')
    def test_gpu_cost_savings_endpoint_success(self, mock_integration_class, mock_detector_class, mock_dynamodb):
        """Test GET /api/ai-ml/gpu-cost-savings endpoint with valid request."""
        # Setup mocks
        mock_dynamodb_instance = Mock()
        mock_dynamodb.return_value = mock_dynamodb_instance
        
        mock_detector = Mock()
        mock_detector_class.return_value = mock_detector
        
        mock_integration = Mock()
        mock_integration_class.return_value = mock_integration
        
        # Create mock savings object
        mock_savings = Mock()
        mock_savings.to_dict.return_value = {
            "period_start": "2024-01-01",
            "period_end": "2024-01-31",
            "total_savings": 5000.00,
            "actions_count": 10,
            "instances_stopped": 7,
            "instances_terminated": 3,
            "avg_idle_hours": 48.5,
            "breakdown_by_instance_type": {
                "p3.2xlarge": 1500.00,
                "g4dn.xlarge": 500.00,
                "g5.2xlarge": 3000.00
            }
        }
        mock_integration.get_gpu_cost_savings.return_value = mock_savings
        
        # Create event
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/gpu-cost-savings',
            'queryStringParameters': {
                'start_date': '2024-01-01',
                'end_date': '2024-01-31'
            }
        }
        
        # Execute
        response = handle_gpu_cost_savings(event)
        
        # Verify
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['period_start'] == '2024-01-01'
        assert body['period_end'] == '2024-01-31'
        assert body['total_savings'] == 5000.00
        assert body['actions_count'] == 10
        assert body['instances_stopped'] == 7
        assert body['instances_terminated'] == 3
        assert body['avg_idle_hours'] == 48.5
        assert 'breakdown_by_instance_type' in body
        
        # Verify integration was called correctly
        mock_integration.get_gpu_cost_savings.assert_called_once_with(
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
    
    @patch('src.ai_ml_handler.get_dynamodb_client')
    @patch('src.ai_ml_handler.IdleGPUDetector')
    @patch('src.ai_ml_handler.GPUPreventionIntegration')
    def test_gpu_cost_savings_endpoint_no_savings(self, mock_integration_class, mock_detector_class, mock_dynamodb):
        """Test GET /api/ai-ml/gpu-cost-savings endpoint with no savings."""
        # Setup mocks
        mock_dynamodb_instance = Mock()
        mock_dynamodb.return_value = mock_dynamodb_instance
        
        mock_detector = Mock()
        mock_detector_class.return_value = mock_detector
        
        mock_integration = Mock()
        mock_integration_class.return_value = mock_integration
        
        # Create mock savings object with no savings
        mock_savings = Mock()
        mock_savings.to_dict.return_value = {
            "period_start": "2024-01-01",
            "period_end": "2024-01-31",
            "total_savings": 0.0,
            "actions_count": 0,
            "instances_stopped": 0,
            "instances_terminated": 0,
            "avg_idle_hours": 0.0,
            "breakdown_by_instance_type": {}
        }
        mock_integration.get_gpu_cost_savings.return_value = mock_savings
        
        # Create event
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/gpu-cost-savings',
            'queryStringParameters': {
                'start_date': '2024-01-01',
                'end_date': '2024-01-31'
            }
        }
        
        # Execute
        response = handle_gpu_cost_savings(event)
        
        # Verify
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['total_savings'] == 0.0
        assert body['actions_count'] == 0
    
    def test_gpu_cost_savings_endpoint_missing_dates(self):
        """Test GET /api/ai-ml/gpu-cost-savings endpoint with missing dates."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/gpu-cost-savings',
            'queryStringParameters': {}
        }
        
        response = handle_gpu_cost_savings(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETERS'
    
    def test_gpu_cost_savings_endpoint_invalid_date_format(self):
        """Test GET /api/ai-ml/gpu-cost-savings endpoint with invalid date format."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/gpu-cost-savings',
            'queryStringParameters': {
                'start_date': '01/01/2024',  # Invalid format
                'end_date': '2024-01-31'
            }
        }
        
        response = handle_gpu_cost_savings(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_DATE_FORMAT'
    
    def test_gpu_cost_savings_endpoint_invalid_date_range(self):
        """Test GET /api/ai-ml/gpu-cost-savings endpoint with invalid date range."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/gpu-cost-savings',
            'queryStringParameters': {
                'start_date': '2024-01-31',
                'end_date': '2024-01-01'  # End before start
            }
        }
        
        response = handle_gpu_cost_savings(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_DATE_RANGE'
