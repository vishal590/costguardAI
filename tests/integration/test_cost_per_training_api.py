"""
Integration Tests for Cost-Per-Training API Endpoints

Tests the cost-per-training and training-comparison API endpoints end-to-end.

Requirements: FR-4.2, FR-4.6, API-4.1, API-4.2
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from src.ai_ml_handler import handler
from src.services.ai_ml.cost_per_training_calculator import (
    CostPerTrainingCalculator,
    CostPerTraining,
    TrainingCosts,
    TrainingJobMetadata,
    InstanceComparison
)


class TestCostPerTrainingAPI:
    """Integration tests for cost-per-training API endpoint."""
    
    def test_cost_per_training_success(self):
        """
        Test successful cost-per-training calculation.
        
        Requirements: API-4.1, FR-4.1
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/cost-per-training',
            'queryStringParameters': {
                'job_id': 'training-job-123'
            }
        }
        
        with patch('src.ai_ml_handler.CostPerTrainingCalculator') as mock_calc_class:
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            
            mock_result = CostPerTraining(
                job_id='training-job-123',
                model='bert-large',
                dataset='wikipedia',
                date=datetime(2024, 1, 1),
                training_hours=24.5,
                total_cost=2450.0,
                cost_per_hour=100.0,
                compute_cost=2000.0,
                storage_cost=350.0,
                data_transfer_cost=100.0,
                instance_type='ml.p3.8xlarge'
            )
            mock_calc.calculate_cost_per_training.return_value = mock_result
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            assert body['job_id'] == 'training-job-123'
            assert body['model'] == 'bert-large'
            assert body['dataset'] == 'wikipedia'
            assert body['training_hours'] == 24.5
            assert body['total_cost'] == 2450.0
            assert body['cost_per_hour'] == 100.0
            assert body['instance_type'] == 'ml.p3.8xlarge'
            assert body['cost_breakdown']['compute_cost'] == 2000.0
            assert body['cost_breakdown']['storage_cost'] == 350.0
            assert body['cost_breakdown']['data_transfer_cost'] == 100.0
    
    def test_cost_per_training_missing_job_id(self):
        """
        Test cost-per-training with missing job_id parameter.
        
        Requirements: API-4.1
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/cost-per-training',
            'queryStringParameters': {}
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETER'
        assert 'job_id is required' in body['error']['message']
    
    def test_cost_per_training_job_not_found(self):
        """
        Test cost-per-training with non-existent job.
        
        Requirements: API-4.1
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/cost-per-training',
            'queryStringParameters': {
                'job_id': 'non-existent-job'
            }
        }
        
        with patch('src.ai_ml_handler.CostPerTrainingCalculator') as mock_calc_class:
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            mock_calc.calculate_cost_per_training.side_effect = ValueError("Training job non-existent-job not found")
            
            response = handler(event, None)
            
            assert response['statusCode'] == 404
            body = json.loads(response['body'])
            assert body['error']['code'] == 'JOB_NOT_FOUND'
    
    def test_cost_per_training_sagemaker_job(self):
        """
        Test cost-per-training with SageMaker training job.
        
        Requirements: FR-4.2
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/cost-per-training',
            'queryStringParameters': {
                'job_id': 'sagemaker-job-456'
            }
        }
        
        with patch('src.ai_ml_handler.CostPerTrainingCalculator') as mock_calc_class:
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            
            mock_result = CostPerTraining(
                job_id='sagemaker-job-456',
                model='resnet-50',
                dataset='imagenet',
                date=datetime(2024, 1, 15),
                training_hours=12.0,
                total_cost=1200.0,
                cost_per_hour=100.0,
                compute_cost=1000.0,
                storage_cost=150.0,
                data_transfer_cost=50.0,
                instance_type='ml.p3.2xlarge'
            )
            mock_calc.calculate_cost_per_training.return_value = mock_result
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            assert body['job_id'] == 'sagemaker-job-456'
            assert body['model'] == 'resnet-50'
    
    def test_cost_per_training_ec2_job(self):
        """
        Test cost-per-training with EC2 training job.
        
        Requirements: FR-4.2
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/cost-per-training',
            'queryStringParameters': {
                'job_id': 'ec2-training-789'
            }
        }
        
        with patch('src.ai_ml_handler.CostPerTrainingCalculator') as mock_calc_class:
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            
            mock_result = CostPerTraining(
                job_id='ec2-training-789',
                model='gpt-2',
                dataset='openwebtext',
                date=datetime(2024, 1, 20),
                training_hours=48.0,
                total_cost=4800.0,
                cost_per_hour=100.0,
                compute_cost=4000.0,
                storage_cost=600.0,
                data_transfer_cost=200.0,
                instance_type='p3.8xlarge'
            )
            mock_calc.calculate_cost_per_training.return_value = mock_result
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            assert body['job_id'] == 'ec2-training-789'
            assert body['instance_type'] == 'p3.8xlarge'
    
    def test_cost_per_training_cost_component_aggregation(self):
        """
        Test that cost components are properly aggregated.
        
        Requirements: FR-4.3
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/cost-per-training',
            'queryStringParameters': {
                'job_id': 'test-job-999'
            }
        }
        
        with patch('src.ai_ml_handler.CostPerTrainingCalculator') as mock_calc_class:
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            
            mock_result = CostPerTraining(
                job_id='test-job-999',
                model='test-model',
                dataset='test-dataset',
                date=datetime(2024, 1, 1),
                training_hours=10.0,
                total_cost=1075.0,
                cost_per_hour=107.5,
                compute_cost=850.0,
                storage_cost=175.0,
                data_transfer_cost=50.0,
                instance_type='ml.g4dn.xlarge'
            )
            mock_calc.calculate_cost_per_training.return_value = mock_result
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            # Verify all cost components are present
            assert 'cost_breakdown' in body
            assert body['cost_breakdown']['compute_cost'] == 850.0
            assert body['cost_breakdown']['storage_cost'] == 175.0
            assert body['cost_breakdown']['data_transfer_cost'] == 50.0
            
            # Verify total equals sum of components
            total_from_components = (
                body['cost_breakdown']['compute_cost'] +
                body['cost_breakdown']['storage_cost'] +
                body['cost_breakdown']['data_transfer_cost']
            )
            assert abs(total_from_components - body['total_cost']) < 0.01


class TestTrainingComparisonAPI:
    """Integration tests for training comparison API endpoint."""
    
    def test_training_comparison_success(self):
        """
        Test successful training cost comparison.
        
        Requirements: API-4.2, FR-4.6
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/training-comparison',
            'queryStringParameters': {
                'model': 'bert-base',
                'instance_types': 'ml.p3.2xlarge,ml.p3.8xlarge,ml.g4dn.xlarge'
            }
        }
        
        with patch('src.ai_ml_handler.CostPerTrainingCalculator') as mock_calc_class:
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            
            mock_comparisons = [
                InstanceComparison(
                    instance_type='ml.p3.2xlarge',
                    estimated_duration_hours=10.0,
                    estimated_cost=306.0,
                    cost_per_hour=30.6,
                    savings_vs_baseline=0.0,
                    savings_percent=0.0
                ),
                InstanceComparison(
                    instance_type='ml.p3.8xlarge',
                    estimated_duration_hours=5.0,
                    estimated_cost=612.0,
                    cost_per_hour=122.4,
                    savings_vs_baseline=-306.0,
                    savings_percent=-100.0
                ),
                InstanceComparison(
                    instance_type='ml.g4dn.xlarge',
                    estimated_duration_hours=20.0,
                    estimated_cost=105.2,
                    cost_per_hour=5.26,
                    savings_vs_baseline=200.8,
                    savings_percent=65.6
                )
            ]
            mock_calc.compare_instance_types.return_value = mock_comparisons
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            assert body['model'] == 'bert-base'
            assert body['baseline_instance'] == 'ml.p3.2xlarge'
            assert len(body['comparisons']) == 3
            
            # Verify comparison data
            assert body['comparisons'][0]['instance_type'] == 'ml.p3.2xlarge'
            assert body['comparisons'][0]['savings_vs_baseline'] == 0.0
            assert body['comparisons'][2]['instance_type'] == 'ml.g4dn.xlarge'
            assert body['comparisons'][2]['savings_percent'] == 65.6
    
    def test_training_comparison_with_baseline(self):
        """
        Test training comparison with custom baseline instance.
        
        Requirements: API-4.2, FR-4.6
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/training-comparison',
            'queryStringParameters': {
                'model': 'resnet-50',
                'instance_types': 'ml.p3.2xlarge,ml.p3.8xlarge',
                'baseline_instance': 'ml.p3.8xlarge'
            }
        }
        
        with patch('src.ai_ml_handler.CostPerTrainingCalculator') as mock_calc_class:
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            
            mock_comparisons = [
                InstanceComparison(
                    instance_type='ml.p3.2xlarge',
                    estimated_duration_hours=10.0,
                    estimated_cost=306.0,
                    cost_per_hour=30.6,
                    savings_vs_baseline=-306.0,
                    savings_percent=-100.0
                ),
                InstanceComparison(
                    instance_type='ml.p3.8xlarge',
                    estimated_duration_hours=5.0,
                    estimated_cost=612.0,
                    cost_per_hour=122.4,
                    savings_vs_baseline=0.0,
                    savings_percent=0.0
                )
            ]
            mock_calc.compare_instance_types.return_value = mock_comparisons
            
            response = handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            assert body['baseline_instance'] == 'ml.p3.8xlarge'
    
    def test_training_comparison_missing_model(self):
        """
        Test training comparison with missing model parameter.
        
        Requirements: API-4.2
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/training-comparison',
            'queryStringParameters': {
                'instance_types': 'ml.p3.2xlarge,ml.p3.8xlarge'
            }
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETER'
        assert 'model is required' in body['error']['message']
    
    def test_training_comparison_missing_instance_types(self):
        """
        Test training comparison with missing instance_types parameter.
        
        Requirements: API-4.2
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/training-comparison',
            'queryStringParameters': {
                'model': 'bert-base'
            }
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETER'
        assert 'instance_types is required' in body['error']['message']
    
    def test_training_comparison_empty_instance_types(self):
        """
        Test training comparison with empty instance_types list.
        
        Requirements: API-4.2
        """
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/training-comparison',
            'queryStringParameters': {
                'model': 'bert-base',
                'instance_types': ''
            }
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        # Empty string gets parsed but results in empty list after split/strip
        # The handler checks if instance_types_str is falsy, so it returns MISSING_PARAMETER
        assert body['error']['code'] == 'MISSING_PARAMETER'
