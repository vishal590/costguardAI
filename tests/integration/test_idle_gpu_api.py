"""
Integration tests for Idle GPU API endpoint.

Tests the GET /api/ai-ml/idle-gpus endpoint end-to-end.

Requirements: API-1.3, FR-1.5
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from src.ai_ml_handler import handler
from src.services.ai_ml.idle_detector import IdleGPU


class TestIdleGPUAPI:
    """Integration tests for idle GPU API endpoint."""
    
    @patch('src.ai_ml_handler.get_dynamodb_client')
    @patch('src.ai_ml_handler.IdleGPUDetector')
    def test_idle_gpus_endpoint_success(self, mock_detector_class, mock_dynamodb):
        """
        Test successful idle GPU retrieval.
        Requirements: API-1.3, FR-1.5
        """
        # Setup mock
        mock_detector = Mock()
        mock_detector_class.return_value = mock_detector
        
        # Mock idle GPUs
        idle_gpus = [
            IdleGPU(
                instance_id='i-idle-123',
                instance_type='p3.2xlarge',
                utilization=5.0,
                idle_hours=10.0,
                wasted_cost=30.6,
                cost_per_hour=3.06,
                first_idle_time='2026-02-01',
                last_check_time='2026-02-24',
                recommendation='REVIEW: GPU utilization is low.'
            ),
            IdleGPU(
                instance_id='i-idle-456',
                instance_type='g4dn.xlarge',
                utilization=3.0,
                idle_hours=20.0,
                wasted_cost=10.52,
                cost_per_hour=0.526,
                first_idle_time='2026-02-01',
                last_check_time='2026-02-24',
                recommendation='STOP: GPU is nearly unused.'
            )
        ]
        mock_detector.identify_idle_gpus.return_value = idle_gpus
        
        # Create event
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/idle-gpus',
            'queryStringParameters': {
                'start_date': '2026-02-01',
                'end_date': '2026-02-24',
                'threshold': '10.0'
            }
        }
        
        # Execute
        response = handler(event, None)
        
        # Verify
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert 'idle_gpus' in body
        assert len(body['idle_gpus']) == 2
        assert body['count'] == 2
        assert body['total_wasted_cost'] == pytest.approx(41.12, rel=0.01)
        assert body['total_idle_hours'] == pytest.approx(30.0, rel=0.01)
        assert body['threshold'] == 10.0
        
        # Verify detector was called correctly
        mock_detector.identify_idle_gpus.assert_called_once_with('2026-02-01', '2026-02-24', 10.0)
    
    @patch('src.ai_ml_handler.get_dynamodb_client')
    @patch('src.ai_ml_handler.IdleGPUDetector')
    def test_idle_gpus_endpoint_default_threshold(self, mock_detector_class, mock_dynamodb):
        """
        Test idle GPU retrieval with default threshold.
        Requirements: API-1.3
        """
        # Setup mock
        mock_detector = Mock()
        mock_detector_class.return_value = mock_detector
        mock_detector.identify_idle_gpus.return_value = []
        
        # Create event without threshold
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/idle-gpus',
            'queryStringParameters': {
                'start_date': '2026-02-01',
                'end_date': '2026-02-24'
            }
        }
        
        # Execute
        response = handler(event, None)
        
        # Verify
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['threshold'] == 10.0  # Default threshold
        
        # Verify detector was called with default threshold
        mock_detector.identify_idle_gpus.assert_called_once_with('2026-02-01', '2026-02-24', 10.0)
    
    @patch('src.ai_ml_handler.get_dynamodb_client')
    @patch('src.ai_ml_handler.IdleGPUDetector')
    def test_idle_gpus_endpoint_custom_threshold(self, mock_detector_class, mock_dynamodb):
        """
        Test idle GPU retrieval with custom threshold.
        Requirements: API-1.3
        """
        # Setup mock
        mock_detector = Mock()
        mock_detector_class.return_value = mock_detector
        mock_detector.identify_idle_gpus.return_value = []
        
        # Create event with custom threshold
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/idle-gpus',
            'queryStringParameters': {
                'start_date': '2026-02-01',
                'end_date': '2026-02-24',
                'threshold': '20.0'
            }
        }
        
        # Execute
        response = handler(event, None)
        
        # Verify
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['threshold'] == 20.0
        
        # Verify detector was called with custom threshold
        mock_detector.identify_idle_gpus.assert_called_once_with('2026-02-01', '2026-02-24', 20.0)
    
    def test_idle_gpus_endpoint_missing_start_date(self):
        """
        Test error handling for missing start_date.
        Requirements: API-1.3
        """
        # Create event without start_date
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/idle-gpus',
            'queryStringParameters': {
                'end_date': '2026-02-24'
            }
        }
        
        # Execute
        response = handler(event, None)
        
        # Verify
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETER'
        assert 'start_date' in body['error']['message']
    
    def test_idle_gpus_endpoint_missing_end_date(self):
        """
        Test error handling for missing end_date.
        Requirements: API-1.3
        """
        # Create event without end_date
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/idle-gpus',
            'queryStringParameters': {
                'start_date': '2026-02-01'
            }
        }
        
        # Execute
        response = handler(event, None)
        
        # Verify
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETER'
        assert 'end_date' in body['error']['message']
    
    def test_idle_gpus_endpoint_invalid_date_format(self):
        """
        Test error handling for invalid date format.
        Requirements: API-1.3
        """
        # Create event with invalid date format
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/idle-gpus',
            'queryStringParameters': {
                'start_date': '02/01/2026',  # Invalid format
                'end_date': '2026-02-24'
            }
        }
        
        # Execute
        response = handler(event, None)
        
        # Verify
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_DATE_FORMAT'
    
    def test_idle_gpus_endpoint_invalid_date_range(self):
        """
        Test error handling for invalid date range (end before start).
        Requirements: API-1.3
        """
        # Create event with end_date before start_date
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/idle-gpus',
            'queryStringParameters': {
                'start_date': '2026-02-24',
                'end_date': '2026-02-01'
            }
        }
        
        # Execute
        response = handler(event, None)
        
        # Verify
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_DATE_RANGE'
    
    def test_idle_gpus_endpoint_invalid_threshold_negative(self):
        """
        Test error handling for negative threshold.
        Requirements: API-1.3
        """
        # Create event with negative threshold
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/idle-gpus',
            'queryStringParameters': {
                'start_date': '2026-02-01',
                'end_date': '2026-02-24',
                'threshold': '-5.0'
            }
        }
        
        # Execute
        response = handler(event, None)
        
        # Verify
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_THRESHOLD'
        assert 'between 0 and 100' in body['error']['message']
    
    def test_idle_gpus_endpoint_invalid_threshold_too_high(self):
        """
        Test error handling for threshold > 100.
        Requirements: API-1.3
        """
        # Create event with threshold > 100
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/idle-gpus',
            'queryStringParameters': {
                'start_date': '2026-02-01',
                'end_date': '2026-02-24',
                'threshold': '150.0'
            }
        }
        
        # Execute
        response = handler(event, None)
        
        # Verify
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_THRESHOLD'
        assert 'between 0 and 100' in body['error']['message']
    
    def test_idle_gpus_endpoint_invalid_threshold_not_number(self):
        """
        Test error handling for non-numeric threshold.
        Requirements: API-1.3
        """
        # Create event with non-numeric threshold
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/idle-gpus',
            'queryStringParameters': {
                'start_date': '2026-02-01',
                'end_date': '2026-02-24',
                'threshold': 'invalid'
            }
        }
        
        # Execute
        response = handler(event, None)
        
        # Verify
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_THRESHOLD'
        assert 'valid number' in body['error']['message']
    
    @patch('src.ai_ml_handler.get_dynamodb_client')
    @patch('src.ai_ml_handler.IdleGPUDetector')
    def test_idle_gpus_endpoint_no_idle_gpus(self, mock_detector_class, mock_dynamodb):
        """
        Test response when no idle GPUs are found.
        Requirements: API-1.3
        """
        # Setup mock
        mock_detector = Mock()
        mock_detector_class.return_value = mock_detector
        mock_detector.identify_idle_gpus.return_value = []
        
        # Create event
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/idle-gpus',
            'queryStringParameters': {
                'start_date': '2026-02-01',
                'end_date': '2026-02-24'
            }
        }
        
        # Execute
        response = handler(event, None)
        
        # Verify
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['idle_gpus'] == []
        assert body['count'] == 0
        assert body['total_wasted_cost'] == 0
        assert body['total_idle_hours'] == 0
    
    @patch('src.ai_ml_handler.get_dynamodb_client')
    @patch('src.ai_ml_handler.IdleGPUDetector')
    def test_idle_gpus_endpoint_response_format(self, mock_detector_class, mock_dynamodb):
        """
        Test that response includes all required fields.
        Requirements: API-1.3
        """
        # Setup mock
        mock_detector = Mock()
        mock_detector_class.return_value = mock_detector
        
        idle_gpu = IdleGPU(
            instance_id='i-test-123',
            instance_type='p3.2xlarge',
            utilization=5.0,
            idle_hours=10.0,
            wasted_cost=30.6,
            cost_per_hour=3.06,
            first_idle_time='2026-02-01',
            last_check_time='2026-02-24',
            recommendation='REVIEW'
        )
        mock_detector.identify_idle_gpus.return_value = [idle_gpu]
        
        # Create event
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/idle-gpus',
            'queryStringParameters': {
                'start_date': '2026-02-01',
                'end_date': '2026-02-24'
            }
        }
        
        # Execute
        response = handler(event, None)
        
        # Verify
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Check all required fields
        assert 'idle_gpus' in body
        assert 'count' in body
        assert 'total_wasted_cost' in body
        assert 'total_idle_hours' in body
        assert 'threshold' in body
        assert 'date_range' in body
        assert 'start_date' in body['date_range']
        assert 'end_date' in body['date_range']
        
        # Check idle GPU fields
        gpu = body['idle_gpus'][0]
        assert 'instance_id' in gpu
        assert 'instance_type' in gpu
        assert 'utilization' in gpu
        assert 'idle_hours' in gpu
        assert 'wasted_cost' in gpu
        assert 'cost_per_hour' in gpu
        assert 'recommendation' in gpu
