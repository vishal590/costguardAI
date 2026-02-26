"""
Integration tests for AI/ML Lambda Handler.

Tests the main Lambda handler for AI/ML workload cost management operations.
Requirements: API-1.1, FR-1.1, FR-1.3, FR-1.6
"""
import pytest
import json
from unittest.mock import Mock, patch
from decimal import Decimal

from src.ai_ml_handler import handler
from src.services.ai_ml.gpu_cost_tracker import GPUCostData


class TestAIMLHandler:
    """Test cases for AI/ML Lambda handler."""
    
    @patch('src.ai_ml_handler.get_dynamodb_client')
    @patch('src.ai_ml_handler.GPUCostTracker')
    def test_gpu_costs_success(self, mock_tracker_class, mock_get_dynamodb):
        """Test successful GPU cost retrieval. Requirements: API-1.1, FR-1.1, FR-1.6"""
        # Mock DynamoDB client
        mock_dynamodb = Mock()
        mock_dynamodb.get_item.return_value = {}  # No cached data
        mock_dynamodb.put_item.return_value = {}
        mock_get_dynamodb.return_value = mock_dynamodb
        
        # Mock GPU cost tracker
        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        
        # Mock GPU cost data
        mock_gpu_costs = [
            GPUCostData(
                date='2026-02-24',
                instance_id='i-123',
                instance_type='p3.2xlarge',
                workload_type='training',
                cost=100.0,
                gpu_hours=10.0,
                cost_per_gpu_hour=10.0,
                utilization=85.0,
                classification_confidence=0.95
            ),
            GPUCostData(
                date='2026-02-24',
                instance_id='i-456',
                instance_type='g5.xlarge',
                workload_type='inference',
                cost=50.0,
                gpu_hours=8.0,
                cost_per_gpu_hour=6.25,
                utilization=45.0,
                classification_confidence=0.88
            )
        ]
        
        mock_tracker.collect_gpu_costs.return_value = mock_gpu_costs
        
        # Test event
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/gpu-costs',
            'queryStringParameters': {
                'start_date': '2026-02-24',
                'end_date': '2026-02-24'
            }
        }
        
        # Execute handler
        response = handler(event, {})
        
        # Verify response structure
        assert response['statusCode'] == 200
        assert 'headers' in response
        assert response['headers']['Content-Type'] == 'application/json'
        assert response['headers']['Access-Control-Allow-Origin'] == '*'
        
        # Parse response body
        body = json.loads(response['body'])
        
        # Verify response data
        assert 'gpu_costs' in body
        assert 'total_cost' in body
        assert 'total_gpu_hours' in body
        assert 'average_cost_per_gpu_hour' in body
        
        assert len(body['gpu_costs']) == 2
        assert body['total_cost'] == 150.0
        assert body['total_gpu_hours'] == 18.0
        assert body['average_cost_per_gpu_hour'] == pytest.approx(8.333, rel=0.01)
        
        # Verify first GPU cost entry
        assert body['gpu_costs'][0]['instance_id'] == 'i-123'
        assert body['gpu_costs'][0]['instance_type'] == 'p3.2xlarge'
        assert body['gpu_costs'][0]['workload_type'] == 'training'
        assert body['gpu_costs'][0]['cost'] == 100.0
        assert body['gpu_costs'][0]['gpu_hours'] == 10.0
        assert body['gpu_costs'][0]['cost_per_gpu_hour'] == 10.0
        assert body['gpu_costs'][0]['utilization'] == 85.0
        
        # Verify service calls
        assert mock_get_dynamodb.called  # Called for cache manager
        mock_tracker_class.assert_called_once_with(mock_dynamodb)
        mock_tracker.collect_gpu_costs.assert_called_once_with(
            '2026-02-24',
            '2026-02-24',
            None,
            None
        )
    
    @patch('src.ai_ml_handler.get_dynamodb_client')
    @patch('src.ai_ml_handler.GPUCostTracker')
    def test_gpu_costs_with_filters(self, mock_tracker_class, mock_get_dynamodb):
        """Test GPU cost retrieval with workload and instance type filters."""
        # Mock DynamoDB client
        mock_dynamodb = Mock()
        mock_get_dynamodb.return_value = mock_dynamodb
        
        # Mock GPU cost tracker
        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        
        # Mock filtered GPU cost data (only training workloads on p3 instances)
        mock_gpu_costs = [
            GPUCostData(
                date='2026-02-24',
                instance_id='i-123',
                instance_type='p3.2xlarge',
                workload_type='training',
                cost=100.0,
                gpu_hours=10.0,
                cost_per_gpu_hour=10.0,
                utilization=85.0,
                classification_confidence=0.95
            )
        ]
        
        mock_tracker.collect_gpu_costs.return_value = mock_gpu_costs
        
        # Test event with filters
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/gpu-costs',
            'queryStringParameters': {
                'start_date': '2026-02-24',
                'end_date': '2026-02-24',
                'workload_type': 'training',
                'instance_type': 'p3.2xlarge'
            }
        }
        
        # Execute handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert len(body['gpu_costs']) == 1
        assert body['gpu_costs'][0]['workload_type'] == 'training'
        assert body['gpu_costs'][0]['instance_type'] == 'p3.2xlarge'
        
        # Verify service calls with filters
        mock_tracker.collect_gpu_costs.assert_called_once_with(
            '2026-02-24',
            '2026-02-24',
            'training',
            'p3.2xlarge'
        )
    
    @patch('src.ai_ml_handler.get_dynamodb_client')
    @patch('src.ai_ml_handler.GPUCostTracker')
    def test_gpu_costs_empty_results(self, mock_tracker_class, mock_get_dynamodb):
        """Test GPU cost retrieval with no results."""
        # Mock DynamoDB client
        mock_dynamodb = Mock()
        mock_get_dynamodb.return_value = mock_dynamodb
        
        # Mock GPU cost tracker
        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        
        # Mock empty results
        mock_tracker.collect_gpu_costs.return_value = []
        
        # Test event
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/gpu-costs',
            'queryStringParameters': {
                'start_date': '2026-02-24',
                'end_date': '2026-02-24'
            }
        }
        
        # Execute handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['gpu_costs'] == []
        assert body['total_cost'] == 0
        assert body['total_gpu_hours'] == 0
        assert body['average_cost_per_gpu_hour'] == 0
    
    def test_gpu_costs_missing_start_date(self):
        """Test GPU cost retrieval with missing start_date parameter."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/gpu-costs',
            'queryStringParameters': {
                'end_date': '2026-02-24'
            }
        }
        
        response = handler(event, {})
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETER'
        assert 'start_date and end_date are required' in body['error']['message']
    
    def test_gpu_costs_missing_end_date(self):
        """Test GPU cost retrieval with missing end_date parameter."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/gpu-costs',
            'queryStringParameters': {
                'start_date': '2026-02-24'
            }
        }
        
        response = handler(event, {})
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETER'
        assert 'start_date and end_date are required' in body['error']['message']
    
    def test_gpu_costs_missing_query_parameters(self):
        """Test GPU cost retrieval with no query parameters."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/gpu-costs'
        }
        
        response = handler(event, {})
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETER'
    
    def test_gpu_costs_invalid_date_format(self):
        """Test GPU cost retrieval with invalid date format."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/gpu-costs',
            'queryStringParameters': {
                'start_date': '24-02-2026',  # Invalid format
                'end_date': '2026-02-24'
            }
        }
        
        response = handler(event, {})
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_DATE_FORMAT'
        assert 'YYYY-MM-DD' in body['error']['message']
    
    def test_gpu_costs_invalid_date_range(self):
        """Test GPU cost retrieval with invalid date range (start after end)."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/gpu-costs',
            'queryStringParameters': {
                'start_date': '2026-02-25',
                'end_date': '2026-02-24'  # End before start
            }
        }
        
        response = handler(event, {})
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_DATE_RANGE'
        assert 'start_date must be before end_date' in body['error']['message']
    
    def test_unsupported_method(self):
        """Test handler with unsupported HTTP method."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/ai-ml/gpu-costs',
            'queryStringParameters': {
                'start_date': '2026-02-24',
                'end_date': '2026-02-24'
            }
        }
        
        response = handler(event, {})
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_REQUEST'
        assert 'Unsupported method POST' in body['error']['message']
    
    def test_unsupported_path(self):
        """Test handler with unsupported path."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/invalid-endpoint',
            'queryStringParameters': {
                'start_date': '2026-02-24',
                'end_date': '2026-02-24'
            }
        }
        
        response = handler(event, {})
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_REQUEST'
        assert 'Unsupported' in body['error']['message']


class TestWorkloadClassificationEndpoints:
    """Integration tests for workload classification endpoints. Requirements: API-2.1, API-2.2, FR-2.1, FR-2.3"""
    
    @patch('src.ai_ml_handler.get_dynamodb_client')
    @patch('src.ai_ml_handler.WorkloadClassifier')
    def test_get_workload_classification_success(self, mock_classifier_class, mock_get_dynamodb):
        """Test successful workload classification retrieval. Requirements: API-2.1, FR-2.1, FR-2.2"""
        from src.services.ai_ml.workload_classifier import WorkloadClassification
        
        # Mock DynamoDB client
        mock_dynamodb = Mock()
        mock_get_dynamodb.return_value = mock_dynamodb
        
        # Mock workload classifier
        mock_classifier = Mock()
        mock_classifier_class.return_value = mock_classifier
        
        # Mock classification result
        mock_classification = WorkloadClassification(
            instance_id='i-123',
            workload_type='training',
            confidence=0.95,
            classification_method='cloudwatch-metrics',
            gpu_utilization_avg=85.0,
            gpu_utilization_pattern=[85.0, 87.0, 84.0, 86.0, 85.5, 86.5, 85.0, 87.5, 86.0, 85.5, 86.5, 85.0],
            timestamp='2026-02-24T12:00:00'
        )
        
        mock_classifier.classify_workload.return_value = mock_classification
        
        # Test event
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/workload-classification',
            'queryStringParameters': {
                'instance_id': 'i-123',
                'start_date': '2026-02-01',
                'end_date': '2026-02-24'
            }
        }
        
        # Execute handler
        response = handler(event, {})
        
        # Verify response structure
        assert response['statusCode'] == 200
        assert 'headers' in response
        assert response['headers']['Content-Type'] == 'application/json'
        
        # Parse response body
        body = json.loads(response['body'])
        
        # Verify response data
        assert 'classification' in body
        classification = body['classification']
        
        assert classification['instance_id'] == 'i-123'
        assert classification['workload_type'] == 'training'
        assert classification['confidence'] == 0.95
        assert classification['classification_method'] == 'cloudwatch-metrics'
        assert classification['gpu_utilization_avg'] == 85.0
        assert len(classification['gpu_utilization_pattern']) == 12
        
        # Verify service calls
        mock_get_dynamodb.assert_called_once()
        mock_classifier_class.assert_called_once_with(mock_dynamodb)
        mock_classifier.classify_workload.assert_called_once_with('i-123', '2026-02-01', '2026-02-24')
    
    @patch('src.ai_ml_handler.get_dynamodb_client')
    @patch('src.ai_ml_handler.WorkloadClassifier')
    def test_get_workload_classification_inference(self, mock_classifier_class, mock_get_dynamodb):
        """Test workload classification for inference workload. Requirements: FR-2.1, FR-2.4"""
        from src.services.ai_ml.workload_classifier import WorkloadClassification
        
        # Mock DynamoDB client
        mock_dynamodb = Mock()
        mock_get_dynamodb.return_value = mock_dynamodb
        
        # Mock workload classifier
        mock_classifier = Mock()
        mock_classifier_class.return_value = mock_classifier
        
        # Mock inference classification result
        mock_classification = WorkloadClassification(
            instance_id='i-456',
            workload_type='inference',
            confidence=0.88,
            classification_method='cloudwatch-metrics',
            gpu_utilization_avg=45.0,
            gpu_utilization_pattern=[30.0, 60.0, 25.0, 65.0, 35.0, 55.0, 28.0, 62.0, 32.0, 58.0, 27.0, 63.0],
            timestamp='2026-02-24T12:00:00'
        )
        
        mock_classifier.classify_workload.return_value = mock_classification
        
        # Test event
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/workload-classification',
            'queryStringParameters': {
                'instance_id': 'i-456',
                'start_date': '2026-02-01',
                'end_date': '2026-02-24'
            }
        }
        
        # Execute handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        classification = body['classification']
        assert classification['workload_type'] == 'inference'
        assert classification['confidence'] == 0.88
        assert classification['gpu_utilization_avg'] == 45.0
    
    def test_get_workload_classification_missing_instance_id(self):
        """Test workload classification with missing instance_id parameter."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/workload-classification',
            'queryStringParameters': {
                'start_date': '2026-02-01',
                'end_date': '2026-02-24'
            }
        }
        
        response = handler(event, {})
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETER'
        assert 'instance_id is required' in body['error']['message']
    
    def test_get_workload_classification_missing_dates(self):
        """Test workload classification with missing date parameters."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/workload-classification',
            'queryStringParameters': {
                'instance_id': 'i-123'
            }
        }
        
        response = handler(event, {})
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETER'
        assert 'start_date and end_date are required' in body['error']['message']
    
    @patch('src.ai_ml_handler.get_dynamodb_client')
    @patch('src.ai_ml_handler.WorkloadClassifier')
    def test_post_workload_classification_manual_override(self, mock_classifier_class, mock_get_dynamodb):
        """Test manual workload classification override. Requirements: API-2.2, FR-2.3, FR-2.5"""
        # Mock DynamoDB client
        mock_dynamodb = Mock()
        mock_get_dynamodb.return_value = mock_dynamodb
        
        # Mock workload classifier
        mock_classifier = Mock()
        mock_classifier_class.return_value = mock_classifier
        
        # Test event
        event = {
            'httpMethod': 'POST',
            'path': '/api/ai-ml/workload-classification',
            'body': json.dumps({
                'instance_id': 'i-789',
                'workload_type': 'training',
                'reason': 'Known training workload'
            })
        }
        
        # Execute handler
        response = handler(event, {})
        
        # Verify response structure
        assert response['statusCode'] == 200
        assert 'headers' in response
        
        # Parse response body
        body = json.loads(response['body'])
        
        # Verify response data
        assert 'classification' in body
        assert 'message' in body
        
        classification = body['classification']
        assert classification['instance_id'] == 'i-789'
        assert classification['workload_type'] == 'training'
        assert classification['confidence'] == 1.0
        assert classification['classification_method'] == 'manual-tag'
        
        assert 'Manual classification set to training' in body['message']
        
        # Verify service calls
        mock_get_dynamodb.assert_called_once()
        mock_classifier_class.assert_called_once_with(mock_dynamodb)
        mock_classifier.store_classification.assert_called_once()
    
    @patch('src.ai_ml_handler.get_dynamodb_client')
    @patch('src.ai_ml_handler.WorkloadClassifier')
    def test_post_workload_classification_all_types(self, mock_classifier_class, mock_get_dynamodb):
        """Test manual classification for all workload types. Requirements: FR-2.3"""
        # Mock DynamoDB client
        mock_dynamodb = Mock()
        mock_get_dynamodb.return_value = mock_dynamodb
        
        # Mock workload classifier
        mock_classifier = Mock()
        mock_classifier_class.return_value = mock_classifier
        
        # Test all valid workload types
        for workload_type in ['training', 'inference', 'idle']:
            event = {
                'httpMethod': 'POST',
                'path': '/api/ai-ml/workload-classification',
                'body': json.dumps({
                    'instance_id': f'i-{workload_type}',
                    'workload_type': workload_type
                })
            }
            
            response = handler(event, {})
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['classification']['workload_type'] == workload_type
    
    def test_post_workload_classification_missing_instance_id(self):
        """Test manual classification with missing instance_id."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/ai-ml/workload-classification',
            'body': json.dumps({
                'workload_type': 'training'
            })
        }
        
        response = handler(event, {})
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETER'
        assert 'instance_id is required' in body['error']['message']
    
    def test_post_workload_classification_missing_workload_type(self):
        """Test manual classification with missing workload_type."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/ai-ml/workload-classification',
            'body': json.dumps({
                'instance_id': 'i-123'
            })
        }
        
        response = handler(event, {})
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETER'
        assert 'workload_type is required' in body['error']['message']
    
    def test_post_workload_classification_invalid_workload_type(self):
        """Test manual classification with invalid workload_type."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/ai-ml/workload-classification',
            'body': json.dumps({
                'instance_id': 'i-123',
                'workload_type': 'invalid_type'
            })
        }
        
        response = handler(event, {})
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_WORKLOAD_TYPE'
        assert 'must be one of' in body['error']['message']
    
    def test_post_workload_classification_invalid_json(self):
        """Test manual classification with invalid JSON body."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/ai-ml/workload-classification',
            'body': 'invalid json'
        }
        
        response = handler(event, {})
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'INVALID_JSON'
        assert 'valid JSON' in body['error']['message']
