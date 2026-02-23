"""
Unit tests for ContextManager.
"""
import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import Mock, MagicMock, patch

from src.services.context_manager import ContextManager
from src.utils.types import QueryIntent, CostContext, BudgetStatus


class TestContextManagerInitialization:
    """Tests for ContextManager initialization."""
    
    def test_context_manager_initialization(self):
        """Test ContextManager initializes correctly."""
        manager = ContextManager()
        assert manager is not None
        assert manager.cost_explorer_client is None
        assert manager.dynamodb_client is None
    
    def test_context_manager_with_clients(self):
        """Test ContextManager initializes with clients."""
        cost_explorer_mock = Mock()
        dynamodb_mock = Mock()
        budgets_mock = Mock()
        
        manager = ContextManager(
            cost_explorer_client=cost_explorer_mock,
            dynamodb_client=dynamodb_mock,
            budgets_client=budgets_mock
        )
        
        assert manager.cost_explorer_client == cost_explorer_mock
        assert manager.dynamodb_client == dynamodb_mock
        assert manager.budgets_client == budgets_mock


class TestHistoricalCostRetrieval:
    """Tests for historical cost retrieval."""
    
    def test_get_historical_costs_success(self):
        """Test successful historical cost retrieval."""
        cost_explorer_mock = Mock()
        
        # Setup mock response
        cost_explorer_mock.get_cost_and_usage.return_value = {
            'ResultsByTime': [
                {
                    'TimePeriod': {'Start': '2026-02-01', 'End': '2026-02-01'},
                    'Groups': [
                        {
                            'Keys': ['ec2'],
                            'Metrics': {
                                'BlendedCost': {'Amount': '25.50', 'Unit': 'USD'},
                                'UnblendedCost': {'Amount': '25.50', 'Unit': 'USD'}
                            }
                        }
                    ]
                }
            ]
        }
        
        manager = ContextManager(cost_explorer_client=cost_explorer_mock)
        
        start_date = datetime(2026, 2, 1, tzinfo=UTC)
        end_date = datetime(2026, 2, 2, tzinfo=UTC)
        
        costs = manager.get_historical_costs(['ec2'], start_date, end_date)
        
        assert 'ec2' in costs
        assert len(costs['ec2']) == 1
        assert costs['ec2'][0]['date'] == '2026-02-01'
        assert costs['ec2'][0]['blended_cost'] == 25.50
        assert costs['ec2'][0]['currency'] == 'USD'
    
    def test_get_historical_costs_multiple_services(self):
        """Test retrieving costs for multiple services."""
        cost_explorer_mock = Mock()
        
        cost_explorer_mock.get_cost_and_usage.return_value = {
            'ResultsByTime': [
                {
                    'TimePeriod': {'Start': '2026-02-01', 'End': '2026-02-01'},
                    'Groups': [
                        {
                            'Keys': ['ec2'],
                            'Metrics': {
                                'BlendedCost': {'Amount': '25.50', 'Unit': 'USD'},
                                'UnblendedCost': {'Amount': '25.50', 'Unit': 'USD'}
                            }
                        },
                        {
                            'Keys': ['s3'],
                            'Metrics': {
                                'BlendedCost': {'Amount': '5.25', 'Unit': 'USD'},
                                'UnblendedCost': {'Amount': '5.25', 'Unit': 'USD'}
                            }
                        }
                    ]
                }
            ]
        }
        
        manager = ContextManager(cost_explorer_client=cost_explorer_mock)
        
        start_date = datetime(2026, 2, 1, tzinfo=UTC)
        end_date = datetime(2026, 2, 2, tzinfo=UTC)
        
        costs = manager.get_historical_costs(['ec2', 's3'], start_date, end_date)
        
        assert 'ec2' in costs
        assert 's3' in costs
        assert costs['ec2'][0]['blended_cost'] == 25.50
        assert costs['s3'][0]['blended_cost'] == 5.25
    
    def test_get_historical_costs_no_client(self):
        """Test historical cost retrieval without client."""
        manager = ContextManager()
        
        start_date = datetime(2026, 2, 1, tzinfo=UTC)
        end_date = datetime(2026, 2, 2, tzinfo=UTC)
        
        costs = manager.get_historical_costs(['ec2'], start_date, end_date)
        
        assert costs == {}
    
    def test_get_historical_costs_api_error(self):
        """Test handling of Cost Explorer API errors."""
        cost_explorer_mock = Mock()
        cost_explorer_mock.get_cost_and_usage.side_effect = Exception("API Error")
        
        manager = ContextManager(cost_explorer_client=cost_explorer_mock)
        
        start_date = datetime(2026, 2, 1, tzinfo=UTC)
        end_date = datetime(2026, 2, 2, tzinfo=UTC)
        
        costs = manager.get_historical_costs(['ec2'], start_date, end_date)
        
        assert costs == {}
    
    def test_get_historical_costs_empty_response(self):
        """Test handling of empty Cost Explorer response."""
        cost_explorer_mock = Mock()
        cost_explorer_mock.get_cost_and_usage.return_value = {'ResultsByTime': []}
        
        manager = ContextManager(cost_explorer_client=cost_explorer_mock)
        
        start_date = datetime(2026, 2, 1, tzinfo=UTC)
        end_date = datetime(2026, 2, 2, tzinfo=UTC)
        
        costs = manager.get_historical_costs(['ec2'], start_date, end_date)
        
        assert costs == {}


class TestForecastDataIntegration:
    """Tests for forecast data integration."""
    
    def test_get_forecast_data_success(self):
        """Test successful forecast data retrieval."""
        dynamodb_mock = Mock()
        
        # Setup mock response
        dynamodb_mock.query.return_value = {
            'Items': [
                {
                    'date': {'S': '2026-02-24'},
                    'predicted_cost': {'N': '30.00'},
                    'confidence_lower': {'N': '25.00'},
                    'confidence_upper': {'N': '35.00'}
                },
                {
                    'date': {'S': '2026-02-25'},
                    'predicted_cost': {'N': '32.00'},
                    'confidence_lower': {'N': '27.00'},
                    'confidence_upper': {'N': '37.00'}
                }
            ]
        }
        
        manager = ContextManager(dynamodb_client=dynamodb_mock)
        
        forecasts = manager.get_forecast_data(['ec2'], days=30)
        
        assert forecasts is not None
        assert 'ec2' in forecasts
        assert len(forecasts['ec2']) == 2
        assert forecasts['ec2'][0]['date'] == '2026-02-24'
        assert forecasts['ec2'][0]['predicted_cost'] == 30.00
        assert forecasts['ec2'][0]['confidence_lower'] == 25.00
        assert forecasts['ec2'][0]['confidence_upper'] == 35.00
    
    def test_get_forecast_data_multiple_services(self):
        """Test retrieving forecasts for multiple services."""
        dynamodb_mock = Mock()
        
        def mock_query(**kwargs):
            service = kwargs['ExpressionAttributeValues'][':svc']['S']
            return {
                'Items': [
                    {
                        'date': {'S': '2026-02-24'},
                        'predicted_cost': {'N': '30.00' if service == 'ec2' else '10.00'},
                        'confidence_lower': {'N': '25.00' if service == 'ec2' else '8.00'},
                        'confidence_upper': {'N': '35.00' if service == 'ec2' else '12.00'}
                    }
                ]
            }
        
        dynamodb_mock.query = mock_query
        
        manager = ContextManager(dynamodb_client=dynamodb_mock)
        
        forecasts = manager.get_forecast_data(['ec2', 's3'], days=30)
        
        assert forecasts is not None
        assert 'ec2' in forecasts
        assert 's3' in forecasts
        assert forecasts['ec2'][0]['predicted_cost'] == 30.00
        assert forecasts['s3'][0]['predicted_cost'] == 10.00
    
    def test_get_forecast_data_no_client(self):
        """Test forecast data retrieval without client."""
        manager = ContextManager()
        
        forecasts = manager.get_forecast_data(['ec2'], days=30)
        
        assert forecasts is None
    
    def test_get_forecast_data_api_error(self):
        """Test handling of DynamoDB errors."""
        dynamodb_mock = Mock()
        dynamodb_mock.query.side_effect = Exception("DB Error")
        
        manager = ContextManager(dynamodb_client=dynamodb_mock)
        
        forecasts = manager.get_forecast_data(['ec2'], days=30)
        
        assert forecasts is None
    
    def test_get_forecast_data_empty_response(self):
        """Test handling of empty forecast response."""
        dynamodb_mock = Mock()
        dynamodb_mock.query.return_value = {'Items': []}
        
        manager = ContextManager(dynamodb_client=dynamodb_mock)
        
        forecasts = manager.get_forecast_data(['ec2'], days=30)
        
        assert forecasts is None


class TestPreventionActionIntegration:
    """Tests for prevention action integration."""
    
    def test_get_prevention_actions_success(self):
        """Test successful prevention action retrieval."""
        dynamodb_mock = Mock()
        
        # Setup mock response
        dynamodb_mock.scan.return_value = {
            'Items': [
                {
                    'resource_id': {'S': 'i-1234567890abcdef0'},
                    'action': {'S': 'stop_instance'},
                    'timestamp': {'S': '2026-02-20T10:00:00+00:00'},
                    'estimated_savings': {'N': '15.50'},
                    'success': {'BOOL': True}
                },
                {
                    'resource_id': {'S': 'i-abcdef1234567890a'},
                    'action': {'S': 'terminate_instance'},
                    'timestamp': {'S': '2026-02-21T14:30:00+00:00'},
                    'estimated_savings': {'N': '25.00'},
                    'success': {'BOOL': True}
                }
            ]
        }
        
        manager = ContextManager(dynamodb_client=dynamodb_mock)
        
        start_date = datetime(2026, 2, 20, tzinfo=UTC)
        end_date = datetime(2026, 2, 22, tzinfo=UTC)
        
        actions = manager.get_prevention_actions(start_date, end_date)
        
        assert len(actions) == 2
        assert actions[0]['resource_id'] == 'i-1234567890abcdef0'
        assert actions[0]['action'] == 'stop_instance'
        assert actions[0]['estimated_savings'] == 15.50
        assert actions[0]['success'] is True
    
    def test_get_prevention_actions_no_client(self):
        """Test prevention action retrieval without client."""
        manager = ContextManager()
        
        start_date = datetime(2026, 2, 20, tzinfo=UTC)
        end_date = datetime(2026, 2, 22, tzinfo=UTC)
        
        actions = manager.get_prevention_actions(start_date, end_date)
        
        assert actions == []
    
    def test_get_prevention_actions_api_error(self):
        """Test handling of DynamoDB errors."""
        dynamodb_mock = Mock()
        dynamodb_mock.scan.side_effect = Exception("DB Error")
        
        manager = ContextManager(dynamodb_client=dynamodb_mock)
        
        start_date = datetime(2026, 2, 20, tzinfo=UTC)
        end_date = datetime(2026, 2, 22, tzinfo=UTC)
        
        actions = manager.get_prevention_actions(start_date, end_date)
        
        assert actions == []
    
    def test_get_prevention_actions_empty_response(self):
        """Test handling of empty prevention action response."""
        dynamodb_mock = Mock()
        dynamodb_mock.scan.return_value = {'Items': []}
        
        manager = ContextManager(dynamodb_client=dynamodb_mock)
        
        start_date = datetime(2026, 2, 20, tzinfo=UTC)
        end_date = datetime(2026, 2, 22, tzinfo=UTC)
        
        actions = manager.get_prevention_actions(start_date, end_date)
        
        assert actions == []


class TestContextAggregation:
    """Tests for context aggregation."""
    
    def test_get_cost_context_cost_analysis(self):
        """Test context aggregation for cost analysis intent."""
        cost_explorer_mock = Mock()
        dynamodb_mock = Mock()
        
        # Setup mocks
        cost_explorer_mock.get_cost_and_usage.return_value = {
            'ResultsByTime': [
                {
                    'TimePeriod': {'Start': '2026-02-01', 'End': '2026-02-01'},
                    'Groups': [
                        {
                            'Keys': ['ec2'],
                            'Metrics': {
                                'BlendedCost': {'Amount': '25.50', 'Unit': 'USD'},
                                'UnblendedCost': {'Amount': '25.50', 'Unit': 'USD'}
                            }
                        }
                    ]
                }
            ]
        }
        
        dynamodb_mock.query.return_value = {'Items': []}
        dynamodb_mock.scan.return_value = {'Items': []}
        
        manager = ContextManager(
            cost_explorer_client=cost_explorer_mock,
            dynamodb_client=dynamodb_mock
        )
        
        intent = QueryIntent(
            intent_type='cost_analysis',
            services=['ec2'],
            time_range=(datetime(2026, 2, 1, tzinfo=UTC), datetime(2026, 2, 2, tzinfo=UTC)),
            accounts=[],
            entities={}
        )
        
        context = manager.get_cost_context(intent)
        
        assert isinstance(context, CostContext)
        assert 'ec2' in context.historical_costs
        assert context.forecast_data is None  # Not requested for cost_analysis
        assert context.prevention_actions == []
    
    def test_get_cost_context_forecast_intent(self):
        """Test context aggregation for forecast intent."""
        cost_explorer_mock = Mock()
        dynamodb_mock = Mock()
        
        # Setup mocks
        cost_explorer_mock.get_cost_and_usage.return_value = {
            'ResultsByTime': []
        }
        
        dynamodb_mock.query.return_value = {
            'Items': [
                {
                    'date': {'S': '2026-02-24'},
                    'predicted_cost': {'N': '30.00'},
                    'confidence_lower': {'N': '25.00'},
                    'confidence_upper': {'N': '35.00'}
                }
            ]
        }
        
        dynamodb_mock.scan.return_value = {'Items': []}
        
        manager = ContextManager(
            cost_explorer_client=cost_explorer_mock,
            dynamodb_client=dynamodb_mock
        )
        
        intent = QueryIntent(
            intent_type='forecast',
            services=['ec2'],
            time_range=(datetime(2026, 2, 1, tzinfo=UTC), datetime(2026, 2, 2, tzinfo=UTC)),
            accounts=[],
            entities={}
        )
        
        context = manager.get_cost_context(intent)
        
        assert isinstance(context, CostContext)
        assert context.forecast_data is not None
        assert 'ec2' in context.forecast_data
    
    def test_get_cost_context_prevention_intent(self):
        """Test context aggregation for prevention intent."""
        cost_explorer_mock = Mock()
        dynamodb_mock = Mock()
        
        # Setup mocks
        cost_explorer_mock.get_cost_and_usage.return_value = {
            'ResultsByTime': []
        }
        
        dynamodb_mock.query.return_value = {'Items': []}
        dynamodb_mock.scan.return_value = {
            'Items': [
                {
                    'resource_id': {'S': 'i-1234567890abcdef0'},
                    'action': {'S': 'stop_instance'},
                    'timestamp': {'S': '2026-02-20T10:00:00+00:00'},
                    'estimated_savings': {'N': '15.50'},
                    'success': {'BOOL': True}
                }
            ]
        }
        
        manager = ContextManager(
            cost_explorer_client=cost_explorer_mock,
            dynamodb_client=dynamodb_mock
        )
        
        intent = QueryIntent(
            intent_type='prevention',
            services=['ec2'],
            time_range=(datetime(2026, 2, 1, tzinfo=UTC), datetime(2026, 2, 2, tzinfo=UTC)),
            accounts=[],
            entities={}
        )
        
        context = manager.get_cost_context(intent)
        
        assert isinstance(context, CostContext)
        assert len(context.prevention_actions) == 1
        assert context.prevention_actions[0]['resource_id'] == 'i-1234567890abcdef0'
    
    def test_get_cost_context_optimization_intent(self):
        """Test context aggregation for optimization intent."""
        cost_explorer_mock = Mock()
        dynamodb_mock = Mock()
        
        # Setup mocks
        cost_explorer_mock.get_cost_and_usage.return_value = {
            'ResultsByTime': []
        }
        
        dynamodb_mock.query.return_value = {'Items': []}
        dynamodb_mock.scan.return_value = {
            'Items': [
                {
                    'resource_id': {'S': 'i-1234567890abcdef0'},
                    'action': {'S': 'stop_instance'},
                    'timestamp': {'S': '2026-02-20T10:00:00+00:00'},
                    'estimated_savings': {'N': '15.50'},
                    'success': {'BOOL': True}
                }
            ]
        }
        
        manager = ContextManager(
            cost_explorer_client=cost_explorer_mock,
            dynamodb_client=dynamodb_mock
        )
        
        intent = QueryIntent(
            intent_type='optimization',
            services=['ec2'],
            time_range=(datetime(2026, 2, 1, tzinfo=UTC), datetime(2026, 2, 2, tzinfo=UTC)),
            accounts=[],
            entities={}
        )
        
        context = manager.get_cost_context(intent)
        
        assert isinstance(context, CostContext)
        assert len(context.prevention_actions) == 1  # Optimization includes prevention actions


class TestErrorHandling:
    """Tests for error handling."""
    
    def test_get_cost_context_with_all_errors(self):
        """Test context aggregation when all data sources fail."""
        cost_explorer_mock = Mock()
        dynamodb_mock = Mock()
        
        # Make all calls fail
        cost_explorer_mock.get_cost_and_usage.side_effect = Exception("API Error")
        dynamodb_mock.query.side_effect = Exception("DB Error")
        dynamodb_mock.scan.side_effect = Exception("DB Error")
        
        manager = ContextManager(
            cost_explorer_client=cost_explorer_mock,
            dynamodb_client=dynamodb_mock
        )
        
        intent = QueryIntent(
            intent_type='cost_analysis',
            services=['ec2'],
            time_range=(datetime(2026, 2, 1, tzinfo=UTC), datetime(2026, 2, 2, tzinfo=UTC)),
            accounts=[],
            entities={}
        )
        
        # Should not raise exception
        context = manager.get_cost_context(intent)
        
        assert isinstance(context, CostContext)
        assert context.historical_costs == {}
        assert context.forecast_data is None
        assert context.prevention_actions == []
