"""
Integration tests for Spot Instance Recommendation API endpoints.

Tests the complete flow from API Gateway request through Lambda handler
to SpotInstanceRecommender service and back.

Feature: ai-ml-workload-costs
Requirements: FR-5.2, FR-5.5, API-5.1, API-5.2
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.ai_ml_handler import handler
from src.services.ai_ml.spot_instance_recommender import (
    SpotRecommendation,
    SpotSavings,
    WhatIfScenario
)


class TestSpotRecommendationsAPI:
    """Integration tests for GET /api/ai-ml/spot-recommendations endpoint."""
    
    def test_spot_recommendations_success(self):
        """
        Test successful spot recommendations request.
        
        Requirements: API-5.1, FR-5.1, FR-5.2
        """
        # Create mock event
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/spot-recommendations',
            'queryStringParameters': {
                'workload_id': 'i-1234567890abcdef0'
            }
        }
        
        # Mock SpotInstanceRecommender
        mock_recommendation = SpotRecommendation(
            workload_id='i-1234567890abcdef0',
            current_instance='p3.2xlarge',
            current_cost=73.44,
            recommended_spot_instance='p3.2xlarge',
            spot_cost=22.03,
            savings=51.41,
            savings_percent=70.0,
            interruption_risk=0.05,
            suitable=True,
            reason='Training workload suitable for spot instances. Estimated savings: $51.41 (70.0%)'
        )
        
        with patch('src.ai_ml_handler.SpotInstanceRecommender') as MockRecommender:
            mock_instance = MockRecommender.return_value
            mock_instance.recommend_spot_instances.return_value = [mock_recommendation]
            
            # Call handler
            response = handler(event, None)
        
        # Verify response
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['workload_id'] == 'i-1234567890abcdef0'
        assert len(body['recommendations']) == 1
        
        rec = body['recommendations'][0]
        assert rec['current_instance'] == 'p3.2xlarge'
        assert rec['suitable'] is True
        assert rec['savings'] == 51.41
        assert rec['savings_percent'] == 70.0
        assert rec['interruption_risk'] == 0.05
    
    def test_spot_recommendations_with_scenarios(self):
        """
        Test spot recommendations with what-if scenarios.
        
        Requirements: API-5.1, FR-5.5
        """
        # Create mock event with scenarios
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/spot-recommendations',
            'queryStringParameters': {
                'workload_id': 'i-1234567890abcdef0',
                'include_scenarios': 'true'
            }
        }
        
        # Mock recommendation
        mock_recommendation = SpotRecommendation(
            workload_id='i-1234567890abcdef0',
            current_instance='p3.2xlarge',
            current_cost=73.44,
            recommended_spot_instance='p3.2xlarge',
            spot_cost=22.03,
            savings=51.41,
            savings_percent=70.0,
            interruption_risk=0.05,
            suitable=True,
            reason='Training workload suitable for spot instances'
        )
        
        # Mock scenarios
        mock_scenarios = [
            WhatIfScenario(
                scenario_name='100% Spot Usage',
                workload_id='i-1234567890abcdef0',
                instance_type='p3.2xlarge',
                spot_usage_percent=100.0,
                estimated_savings=51.41,
                estimated_interruptions=1,
                recommendation='Maximum savings but higher interruption risk'
            ),
            WhatIfScenario(
                scenario_name='50% Spot, 50% On-Demand',
                workload_id='i-1234567890abcdef0',
                instance_type='p3.2xlarge',
                spot_usage_percent=50.0,
                estimated_savings=25.71,
                estimated_interruptions=0,
                recommendation='Balanced approach with moderate savings and lower risk'
            )
        ]
        
        with patch('src.ai_ml_handler.SpotInstanceRecommender') as MockRecommender:
            mock_instance = MockRecommender.return_value
            mock_instance.recommend_spot_instances.return_value = [mock_recommendation]
            mock_instance.generate_what_if_scenarios.return_value = mock_scenarios
            
            # Call handler
            response = handler(event, None)
        
        # Verify response
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert 'what_if_scenarios' in body
        assert len(body['what_if_scenarios']) == 2
        
        scenario1 = body['what_if_scenarios'][0]
        assert scenario1['scenario_name'] == '100% Spot Usage'
        assert scenario1['spot_usage_percent'] == 100.0
        assert scenario1['estimated_savings'] == 51.41
    
    def test_spot_recommendations_not_suitable(self):
        """
        Test spot recommendations for unsuitable workload.
        
        Requirements: API-5.1, FR-5.1
        """
        # Create mock event
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/spot-recommendations',
            'queryStringParameters': {
                'workload_id': 'i-inference-instance'
            }
        }
        
        # Mock unsuitable recommendation
        mock_recommendation = SpotRecommendation(
            workload_id='i-inference-instance',
            current_instance='p3.2xlarge',
            current_cost=0.0,
            recommended_spot_instance='p3.2xlarge',
            spot_cost=0.0,
            savings=0.0,
            savings_percent=0.0,
            interruption_risk=0.0,
            suitable=False,
            reason="Workload type 'inference' not suitable for spot instances (only training workloads)"
        )
        
        with patch('src.ai_ml_handler.SpotInstanceRecommender') as MockRecommender:
            mock_instance = MockRecommender.return_value
            mock_instance.recommend_spot_instances.return_value = [mock_recommendation]
            
            # Call handler
            response = handler(event, None)
        
        # Verify response
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        rec = body['recommendations'][0]
        assert rec['suitable'] is False
        assert 'inference' in rec['reason'].lower()
        assert rec['savings'] == 0.0
    
    def test_spot_recommendations_missing_workload_id(self):
        """
        Test spot recommendations with missing workload_id.
        
        Requirements: API-5.1
        """
        # Create mock event without workload_id
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/spot-recommendations',
            'queryStringParameters': {}
        }
        
        # Call handler
        response = handler(event, None)
        
        # Verify error response
        assert response['statusCode'] == 400
        
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETER'
        assert 'workload_id' in body['error']['message']
    
    def test_spot_recommendations_error_handling(self):
        """
        Test error handling in spot recommendations endpoint.
        
        Requirements: API-5.1
        """
        # Create mock event
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/spot-recommendations',
            'queryStringParameters': {
                'workload_id': 'i-error-instance'
            }
        }
        
        with patch('src.ai_ml_handler.SpotInstanceRecommender') as MockRecommender:
            mock_instance = MockRecommender.return_value
            mock_instance.recommend_spot_instances.side_effect = Exception('AWS API error')
            
            # Call handler
            response = handler(event, None)
        
        # Verify error response
        assert response['statusCode'] == 500
        
        body = json.loads(response['body'])
        assert 'error' in body


class TestSpotSavingsAPI:
    """Integration tests for GET /api/ai-ml/spot-savings endpoint."""
    
    def test_spot_savings_success(self):
        """
        Test successful spot savings calculation.
        
        Requirements: API-5.2, FR-5.2
        """
        # Create mock event
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/spot-savings',
            'queryStringParameters': {
                'current_instance': 'p3.2xlarge'
            }
        }
        
        # Mock SpotSavings
        mock_savings = SpotSavings(
            current_instance='p3.2xlarge',
            spot_instance='p3.2xlarge',
            on_demand_price=3.06,
            spot_price=0.92,
            savings_per_hour=2.14,
            savings_percent=69.93,
            estimated_monthly_savings=1562.20
        )
        
        with patch('src.ai_ml_handler.SpotInstanceRecommender') as MockRecommender:
            mock_instance = MockRecommender.return_value
            mock_instance.calculate_spot_savings.return_value = mock_savings
            mock_instance.get_spot_interruption_risk.return_value = 0.05
            
            # Call handler
            response = handler(event, None)
        
        # Verify response
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['current_instance'] == 'p3.2xlarge'
        assert body['spot_instance'] == 'p3.2xlarge'
        
        pricing = body['pricing']
        assert pricing['on_demand_price'] == 3.06
        assert pricing['spot_price'] == 0.92
        
        savings = body['savings']
        assert savings['savings_per_hour'] == 2.14
        assert savings['savings_percent'] == 69.93
        assert savings['estimated_monthly_savings'] == 1562.20
        
        assert body['interruption_risk'] == 0.05
    
    def test_spot_savings_with_different_spot_instance(self):
        """
        Test spot savings with different spot instance type.
        
        Requirements: API-5.2, FR-5.2
        """
        # Create mock event
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/spot-savings',
            'queryStringParameters': {
                'current_instance': 'p3.2xlarge',
                'spot_instance': 'p3.8xlarge'
            }
        }
        
        # Mock SpotSavings
        mock_savings = SpotSavings(
            current_instance='p3.2xlarge',
            spot_instance='p3.8xlarge',
            on_demand_price=3.06,
            spot_price=3.67,
            savings_per_hour=-0.61,
            savings_percent=-19.93,
            estimated_monthly_savings=-445.30
        )
        
        with patch('src.ai_ml_handler.SpotInstanceRecommender') as MockRecommender:
            mock_instance = MockRecommender.return_value
            mock_instance.calculate_spot_savings.return_value = mock_savings
            mock_instance.get_spot_interruption_risk.return_value = 0.08
            
            # Call handler
            response = handler(event, None)
        
        # Verify response
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['current_instance'] == 'p3.2xlarge'
        assert body['spot_instance'] == 'p3.8xlarge'
        
        # Verify negative savings (more expensive)
        savings = body['savings']
        assert savings['savings_per_hour'] < 0
    
    def test_spot_savings_missing_current_instance(self):
        """
        Test spot savings with missing current_instance.
        
        Requirements: API-5.2
        """
        # Create mock event without current_instance
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/spot-savings',
            'queryStringParameters': {}
        }
        
        # Call handler
        response = handler(event, None)
        
        # Verify error response
        assert response['statusCode'] == 400
        
        body = json.loads(response['body'])
        assert body['error']['code'] == 'MISSING_PARAMETER'
        assert 'current_instance' in body['error']['message']
    
    def test_spot_savings_defaults_to_same_instance(self):
        """
        Test that spot_instance defaults to current_instance.
        
        Requirements: API-5.2
        """
        # Create mock event without spot_instance
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/spot-savings',
            'queryStringParameters': {
                'current_instance': 'g5.xlarge'
            }
        }
        
        # Mock SpotSavings
        mock_savings = SpotSavings(
            current_instance='g5.xlarge',
            spot_instance='g5.xlarge',
            on_demand_price=1.006,
            spot_price=0.302,
            savings_per_hour=0.704,
            savings_percent=69.98,
            estimated_monthly_savings=513.92
        )
        
        with patch('src.ai_ml_handler.SpotInstanceRecommender') as MockRecommender:
            mock_instance = MockRecommender.return_value
            mock_instance.calculate_spot_savings.return_value = mock_savings
            mock_instance.get_spot_interruption_risk.return_value = 0.10
            
            # Call handler
            response = handler(event, None)
        
        # Verify response
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        # Verify spot_instance defaults to current_instance
        assert body['current_instance'] == body['spot_instance']
    
    def test_spot_savings_error_handling(self):
        """
        Test error handling in spot savings endpoint.
        
        Requirements: API-5.2
        """
        # Create mock event
        event = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/spot-savings',
            'queryStringParameters': {
                'current_instance': 'invalid-instance'
            }
        }
        
        with patch('src.ai_ml_handler.SpotInstanceRecommender') as MockRecommender:
            mock_instance = MockRecommender.return_value
            mock_instance.calculate_spot_savings.side_effect = Exception('Invalid instance type')
            
            # Call handler
            response = handler(event, None)
        
        # Verify error response
        assert response['statusCode'] == 500
        
        body = json.loads(response['body'])
        assert 'error' in body


class TestSpotRecommendationsIntegration:
    """End-to-end integration tests for spot recommendations."""
    
    def test_complete_spot_recommendation_flow(self):
        """
        Test complete flow: recommendations -> savings calculation.
        
        Requirements: FR-5.1, FR-5.2, FR-5.4, FR-5.5
        """
        workload_id = 'i-training-job-123'
        
        # Step 1: Get recommendations
        event1 = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/spot-recommendations',
            'queryStringParameters': {
                'workload_id': workload_id,
                'include_scenarios': 'true'
            }
        }
        
        mock_recommendation = SpotRecommendation(
            workload_id=workload_id,
            current_instance='p4d.24xlarge',
            current_cost=786.48,
            recommended_spot_instance='p4d.24xlarge',
            spot_cost=235.94,
            savings=550.54,
            savings_percent=70.0,
            interruption_risk=0.08,
            suitable=True,
            reason='Training workload suitable for spot instances'
        )
        
        mock_scenarios = [
            WhatIfScenario(
                scenario_name='100% Spot Usage',
                workload_id=workload_id,
                instance_type='p4d.24xlarge',
                spot_usage_percent=100.0,
                estimated_savings=550.54,
                estimated_interruptions=2,
                recommendation='Maximum savings but higher interruption risk'
            )
        ]
        
        with patch('src.ai_ml_handler.SpotInstanceRecommender') as MockRecommender:
            mock_instance = MockRecommender.return_value
            mock_instance.recommend_spot_instances.return_value = [mock_recommendation]
            mock_instance.generate_what_if_scenarios.return_value = mock_scenarios
            
            response1 = handler(event1, None)
        
        assert response1['statusCode'] == 200
        body1 = json.loads(response1['body'])
        
        # Verify recommendations
        assert body1['recommendations'][0]['suitable'] is True
        assert body1['recommendations'][0]['savings'] > 500
        
        # Verify scenarios
        assert len(body1['what_if_scenarios']) == 1
        assert body1['what_if_scenarios'][0]['estimated_savings'] > 500
        
        # Step 2: Get detailed savings for the recommended instance
        event2 = {
            'httpMethod': 'GET',
            'path': '/api/ai-ml/spot-savings',
            'queryStringParameters': {
                'current_instance': 'p4d.24xlarge'
            }
        }
        
        mock_savings = SpotSavings(
            current_instance='p4d.24xlarge',
            spot_instance='p4d.24xlarge',
            on_demand_price=32.77,
            spot_price=9.83,
            savings_per_hour=22.94,
            savings_percent=70.0,
            estimated_monthly_savings=16746.20
        )
        
        with patch('src.ai_ml_handler.SpotInstanceRecommender') as MockRecommender:
            mock_instance = MockRecommender.return_value
            mock_instance.calculate_spot_savings.return_value = mock_savings
            mock_instance.get_spot_interruption_risk.return_value = 0.08
            
            response2 = handler(event2, None)
        
        assert response2['statusCode'] == 200
        body2 = json.loads(response2['body'])
        
        # Verify savings match recommendation
        assert body2['savings']['savings_percent'] == 70.0
        assert body2['savings']['estimated_monthly_savings'] > 16000


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
