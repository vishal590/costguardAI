"""
End-to-End Integration Tests for Cost Estimation

Tests the complete flow from API request through metric collection,
pricing fetch, and cost estimation calculation.

Requirements:
- 4.1: GET /api/cost-estimation/current endpoint
- 4.2: Return costs for all supported services
- 4.7: Response format validation
"""

import json
import unittest
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from unittest.mock import patch, MagicMock

from src.lambda_handler import handler
from src.utils.types import CostEstimate, PricingData


class TestEstimationEndToEnd(unittest.TestCase):
    """End-to-end tests for cost estimation flow"""

    def setUp(self):
        """Set up test fixtures"""
        self.maxDiff = None

    @patch('src.lambda_handler.CloudWatchMetricsCollector')
    @patch('src.lambda_handler.PricingManager')
    @patch('src.lambda_handler.CostEstimator')
    def test_end_to_end_estimation_current(self, mock_estimator_class, mock_pricing_class, mock_collector_class):
        """Test complete flow for /api/cost-estimation/current endpoint"""
        # Mock CloudWatch collector
        mock_collector = MagicMock()
        mock_collector_class.return_value = mock_collector
        
        # Mock collect_metrics to return sample metrics
        mock_collector.collect_metrics.return_value = {
            'ec2': [MagicMock(instance_id='i-123', instance_type='t2.micro', running_hours=Decimal('1.0'))],
            'lambda': [MagicMock(function_name='my-func', invocations=100, duration_ms=Decimal('500'), memory_mb=128)],
        }
        
        # Mock pricing manager
        mock_pricing = MagicMock()
        mock_pricing_class.return_value = mock_pricing
        mock_pricing.get_pricing_data.return_value = PricingData(
            service='ec2',
            region='us-east-1',
            prices={'instance_hour': Decimal('0.0116')},
            currency='USD',
            last_updated=datetime.now(UTC),
            ttl=int((datetime.now(UTC) + timedelta(days=1)).timestamp())
        )
        
        # Mock cost estimator
        mock_estimator = MagicMock()
        mock_estimator_class.return_value = mock_estimator
        mock_estimator.estimate_cost.return_value = CostEstimate(
            service='ec2',
            estimated_cost=Decimal('0.0116'),
            currency='USD',
            confidence_lower=Decimal('0.0104'),
            confidence_upper=Decimal('0.0128'),
            timestamp=datetime.now(UTC),
            period_start=datetime.now(UTC) - timedelta(hours=1),
            period_end=datetime.now(UTC),
            metrics_count=1
        )
        mock_estimator.calculate_total_estimate.return_value = Decimal('0.0232')
        
        # Create API Gateway event
        event = {
            'httpMethod': 'GET',
            'path': '/api/cost-estimation/current',
            'queryStringParameters': {
                'hours': '1'
            },
            'headers': {}
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response structure
        self.assertEqual(response['statusCode'], 200)
        
        body = json.loads(response['body'])
        self.assertTrue(body['success'])
        self.assertIn('estimates', body)
        self.assertIn('totalCost', body)
        self.assertIn('currency', body)
        self.assertIn('timestamp', body)
        self.assertIn('period', body)
        
        # Verify estimates list
        self.assertGreater(len(body['estimates']), 0)
        
        # Verify each estimate has required fields
        for estimate in body['estimates']:
            self.assertIn('service', estimate)
            self.assertIn('estimatedCost', estimate)
            self.assertIn('currency', estimate)
            self.assertIn('confidenceLower', estimate)
            self.assertIn('confidenceUpper', estimate)
            self.assertIn('timestamp', estimate)
            self.assertIn('periodStart', estimate)
            self.assertIn('periodEnd', estimate)
            self.assertIn('metricsCount', estimate)
        
        # Verify total cost
        self.assertIsInstance(body['totalCost'], (str, float, int))
        if isinstance(body['totalCost'], str):
            total_cost = Decimal(body['totalCost'])
        else:
            total_cost = Decimal(str(body['totalCost']))
        self.assertGreaterEqual(total_cost, Decimal('0'))
        
        # Verify methods were called
        self.assertTrue(mock_collector.collect_metrics.called)
        self.assertTrue(mock_pricing.get_pricing_data.called)
        self.assertTrue(mock_estimator.estimate_cost.called)

    @patch('src.lambda_handler.CloudWatchMetricsCollector')
    @patch('src.lambda_handler.PricingManager')
    @patch('src.lambda_handler.CostEstimator')
    def test_end_to_end_estimation_service(self, mock_estimator_class, mock_pricing_class, mock_collector_class):
        """Test complete flow for /api/cost-estimation/service/{service} endpoint"""
        # Mock CloudWatch collector
        mock_collector = MagicMock()
        mock_collector_class.return_value = mock_collector
        mock_collector.collect_metrics.return_value = {
            'ec2': [MagicMock(instance_id='i-123', instance_type='t2.micro', running_hours=Decimal('1.0'))]
        }
        
        # Mock pricing manager
        mock_pricing = MagicMock()
        mock_pricing_class.return_value = mock_pricing
        mock_pricing.get_pricing_data.return_value = PricingData(
            service='ec2',
            region='us-east-1',
            prices={'instance_hour': Decimal('0.0116')},
            currency='USD',
            last_updated=datetime.now(UTC),
            ttl=int((datetime.now(UTC) + timedelta(days=1)).timestamp())
        )
        
        # Mock cost estimator - return proper CostEstimate dataclass
        mock_estimator = MagicMock()
        mock_estimator_class.return_value = mock_estimator
        mock_estimator.estimate_cost.return_value = CostEstimate(
            service='ec2',
            estimated_cost=Decimal('0.0116'),
            currency='USD',
            confidence_lower=Decimal('0.0104'),
            confidence_upper=Decimal('0.0128'),
            timestamp=datetime.now(UTC),
            period_start=datetime.now(UTC) - timedelta(hours=24),
            period_end=datetime.now(UTC),
            metrics_count=1
        )
        
        # Create API Gateway event
        event = {
            'httpMethod': 'GET',
            'path': '/api/cost-estimation/service/ec2',
            'pathParameters': {
                'service': 'ec2'
            },
            'queryStringParameters': {
                'hours': '24'
            },
            'headers': {}
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response structure
        self.assertEqual(response['statusCode'], 200)
        
        body = json.loads(response['body'])
        self.assertTrue(body['success'])
        self.assertIn('service', body)
        self.assertIn('estimatedCost', body)
        
        # Verify cost is non-negative
        estimated_cost = Decimal(str(body['estimatedCost']))
        self.assertGreaterEqual(estimated_cost, Decimal('0'))
        
        # Verify methods were called
        self.assertTrue(mock_collector.collect_metrics.called)
        self.assertTrue(mock_pricing.get_pricing_data.called)
        self.assertTrue(mock_estimator.estimate_cost.called)

    @patch('src.lambda_handler.CloudWatchMetricsCollector')
    @patch('src.lambda_handler.PricingManager')
    @patch('src.lambda_handler.CostEstimator')
    def test_end_to_end_handles_cloudwatch_errors(self, mock_estimator_class, mock_pricing_class, mock_collector_class):
        """Test that CloudWatch errors are handled gracefully with error isolation"""
        # Mock CloudWatch collector to raise error
        mock_collector = MagicMock()
        mock_collector_class.return_value = mock_collector
        mock_collector.collect_metrics.side_effect = Exception("CloudWatch API error")
        
        # Create API Gateway event
        event = {
            'httpMethod': 'GET',
            'path': '/api/cost-estimation/current',
            'queryStringParameters': {},
            'headers': {}
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify error response
        self.assertEqual(response['statusCode'], 500)
        body = json.loads(response['body'])
        self.assertFalse(body['success'])
        self.assertIn('error', body)

    @patch('src.lambda_handler.CloudWatchMetricsCollector')
    @patch('src.lambda_handler.PricingManager')
    @patch('src.lambda_handler.CostEstimator')
    def test_end_to_end_with_no_metrics(self, mock_estimator_class, mock_pricing_class, mock_collector_class):
        """Test handling when no metrics are found"""
        # Mock CloudWatch collector to return empty metrics
        mock_collector = MagicMock()
        mock_collector_class.return_value = mock_collector
        mock_collector.collect_metrics.return_value = {'ec2': []}
        
        # Mock pricing manager
        mock_pricing = MagicMock()
        mock_pricing_class.return_value = mock_pricing
        
        # Mock cost estimator
        mock_estimator = MagicMock()
        mock_estimator_class.return_value = mock_estimator
        
        # Create API Gateway event
        event = {
            'httpMethod': 'GET',
            'path': '/api/cost-estimation/service/ec2',
            'pathParameters': {'service': 'ec2'},
            'queryStringParameters': {},
            'headers': {}
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response is successful with zero cost
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertTrue(body['success'])
        self.assertEqual(body['service'], 'ec2')
        self.assertEqual(body['estimatedCost'], 0.0)
        self.assertIn('message', body)


if __name__ == '__main__':
    unittest.main()
