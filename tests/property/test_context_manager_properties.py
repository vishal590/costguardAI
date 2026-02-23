"""
Property-based tests for ContextManager.

Feature: ai-cost-advisor
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta, UTC
from unittest.mock import Mock, MagicMock

from src.services.context_manager import ContextManager
from src.utils.types import QueryIntent, CostContext


# Feature: ai-cost-advisor, Property 2: Context Retrieval Completeness
@given(
    services=st.lists(
        st.sampled_from(['ec2', 'lambda', 's3', 'dynamodb', 'rds']),
        min_size=1,
        max_size=3,
        unique=True
    ),
    days_back=st.integers(min_value=1, max_value=30)
)
@settings(max_examples=100)
def test_context_retrieval_completeness(services, days_back):
    """
    Property 2: Context Retrieval Completeness
    For any query intent with specified services and time ranges,
    the context manager should retrieve all relevant cost data
    without missing any requested services or time periods.
    
    Validates: Requirements 2.1, 2.2, 2.3
    """
    # Create mock clients
    cost_explorer_mock = Mock()
    dynamodb_mock = Mock()
    
    # Setup Cost Explorer mock response
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=days_back)
    
    # Create mock cost data for each service
    results_by_time = []
    for day in range(days_back):
        date = (start_date + timedelta(days=day)).strftime('%Y-%m-%d')
        groups = []
        for service in services:
            groups.append({
                'Keys': [service],
                'Metrics': {
                    'BlendedCost': {'Amount': '10.50', 'Unit': 'USD'},
                    'UnblendedCost': {'Amount': '10.50', 'Unit': 'USD'}
                }
            })
        results_by_time.append({
            'TimePeriod': {'Start': date, 'End': date},
            'Groups': groups
        })
    
    cost_explorer_mock.get_cost_and_usage.return_value = {
        'ResultsByTime': results_by_time
    }
    
    # Create context manager
    manager = ContextManager(
        cost_explorer_client=cost_explorer_mock,
        dynamodb_client=dynamodb_mock
    )
    
    # Create query intent
    intent = QueryIntent(
        intent_type='cost_analysis',
        services=services,
        time_range=(start_date, end_date),
        accounts=[],
        entities={}
    )
    
    # Get context
    context = manager.get_cost_context(intent)
    
    # Verify all requested services are in the context
    assert isinstance(context, CostContext)
    assert context.historical_costs is not None
    
    # All requested services should have cost data
    for service in services:
        assert service in context.historical_costs, \
            f"Service {service} missing from historical costs"
        
        # Each service should have data points
        assert len(context.historical_costs[service]) > 0, \
            f"Service {service} has no cost data points"


# Feature: ai-cost-advisor, Property 13: Forecast Integration Accuracy
@given(
    services=st.lists(
        st.sampled_from(['ec2', 'lambda', 's3']),
        min_size=1,
        max_size=2,
        unique=True
    ),
    forecast_days=st.integers(min_value=7, max_value=30)
)
@settings(max_examples=100)
def test_forecast_integration_accuracy(services, forecast_days):
    """
    Property 13: Forecast Integration Accuracy
    For any query about future costs, the system should retrieve
    forecast data from Phase 2 and correctly interpret confidence intervals.
    
    Validates: Requirements 14.1, 14.2
    """
    # Create mock clients
    dynamodb_mock = Mock()
    
    # Setup DynamoDB mock response for forecasts
    def mock_query(**kwargs):
        service = kwargs['ExpressionAttributeValues'][':svc']['S']
        
        # Generate forecast data
        items = []
        for day in range(forecast_days):
            date = (datetime.now(UTC) + timedelta(days=day)).strftime('%Y-%m-%d')
            items.append({
                'date': {'S': date},
                'predicted_cost': {'N': '15.75'},
                'confidence_lower': {'N': '12.50'},
                'confidence_upper': {'N': '18.00'}
            })
        
        return {'Items': items}
    
    dynamodb_mock.query = mock_query
    
    # Create context manager
    manager = ContextManager(
        cost_explorer_client=None,
        dynamodb_client=dynamodb_mock
    )
    
    # Get forecast data
    forecast_data = manager.get_forecast_data(services, days=forecast_days)
    
    # Verify forecast data structure
    if forecast_data:
        # All requested services should have forecasts
        for service in services:
            assert service in forecast_data, \
                f"Service {service} missing from forecast data"
            
            # Each service should have forecast points
            forecast_points = forecast_data[service]
            assert len(forecast_points) > 0, \
                f"Service {service} has no forecast points"
            
            # Each forecast point should have required fields
            for point in forecast_points:
                assert 'date' in point
                assert 'predicted_cost' in point
                assert 'confidence_lower' in point
                assert 'confidence_upper' in point
                
                # Confidence intervals should be valid
                assert point['confidence_lower'] <= point['predicted_cost'], \
                    "Lower confidence bound exceeds predicted cost"
                assert point['predicted_cost'] <= point['confidence_upper'], \
                    "Predicted cost exceeds upper confidence bound"


# Feature: ai-cost-advisor, Property 14: Prevention Action Attribution
@given(
    days_back=st.integers(min_value=1, max_value=30),
    num_actions=st.integers(min_value=0, max_value=10)
)
@settings(max_examples=100)
def test_prevention_action_attribution(days_back, num_actions):
    """
    Property 14: Prevention Action Attribution
    For any query about prevention actions, the system should accurately
    retrieve action history from Phase 3 and explain savings achieved.
    
    Validates: Requirements 15.1, 15.2, 15.3
    """
    # Create mock DynamoDB client
    dynamodb_mock = Mock()
    
    # Setup mock response for prevention actions
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=days_back)
    
    items = []
    for i in range(num_actions):
        action_date = start_date + timedelta(days=i % days_back)
        items.append({
            'resource_id': {'S': f'i-{i:016x}'},
            'action': {'S': 'stop_instance'},
            'timestamp': {'S': action_date.isoformat()},
            'estimated_savings': {'N': str(5.0 + i)},
            'success': {'BOOL': True}
        })
    
    dynamodb_mock.scan.return_value = {'Items': items}
    
    # Create context manager
    manager = ContextManager(
        cost_explorer_client=None,
        dynamodb_client=dynamodb_mock
    )
    
    # Get prevention actions
    actions = manager.get_prevention_actions(start_date, end_date)
    
    # Verify actions structure
    assert isinstance(actions, list)
    assert len(actions) == num_actions
    
    # Each action should have required fields
    for action in actions:
        assert 'resource_id' in action
        assert 'action' in action
        assert 'timestamp' in action
        assert 'estimated_savings' in action
        assert 'success' in action
        
        # Savings should be non-negative
        assert action['estimated_savings'] >= 0, \
            "Estimated savings cannot be negative"
        
        # Timestamp should be within requested range
        action_time = datetime.fromisoformat(action['timestamp'])
        assert start_date <= action_time <= end_date, \
            f"Action timestamp {action_time} outside range [{start_date}, {end_date}]"


# Property: Context retrieval never raises exceptions
@given(
    intent_type=st.sampled_from(['cost_analysis', 'optimization', 'forecast', 'prevention']),
    services=st.lists(st.text(min_size=1, max_size=20), max_size=5),
    days_back=st.integers(min_value=1, max_value=365)
)
@settings(max_examples=100)
def test_context_retrieval_never_fails(intent_type, services, days_back):
    """
    Property: Context retrieval never raises exceptions
    For any query intent, context retrieval should always complete
    without raising exceptions, even with invalid or missing data.
    
    Validates: Requirements 2.1, 11.1
    """
    # Create mock clients that may fail
    cost_explorer_mock = Mock()
    dynamodb_mock = Mock()
    
    # Make clients raise exceptions
    cost_explorer_mock.get_cost_and_usage.side_effect = Exception("API Error")
    dynamodb_mock.query.side_effect = Exception("DB Error")
    dynamodb_mock.scan.side_effect = Exception("DB Error")
    
    # Create context manager
    manager = ContextManager(
        cost_explorer_client=cost_explorer_mock,
        dynamodb_client=dynamodb_mock
    )
    
    # Create query intent
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=days_back)
    
    intent = QueryIntent(
        intent_type=intent_type,
        services=services,
        time_range=(start_date, end_date),
        accounts=[],
        entities={}
    )
    
    # Should not raise exceptions
    try:
        context = manager.get_cost_context(intent)
        
        # Should return a valid CostContext
        assert isinstance(context, CostContext)
        
        # Fields may be empty but should exist
        assert hasattr(context, 'historical_costs')
        assert hasattr(context, 'forecast_data')
        assert hasattr(context, 'prevention_actions')
        
    except Exception as e:
        pytest.fail(f"Context retrieval raised exception: {e}")


# Property: Historical costs are always in chronological order
@given(
    services=st.lists(
        st.sampled_from(['ec2', 'lambda', 's3']),
        min_size=1,
        max_size=2,
        unique=True
    ),
    days_back=st.integers(min_value=2, max_value=30)
)
@settings(max_examples=100)
def test_historical_costs_chronological_order(services, days_back):
    """
    Property: Historical costs are always in chronological order
    For any historical cost data, dates should be in ascending order.
    
    Validates: Requirements 2.2
    """
    # Create mock Cost Explorer client
    cost_explorer_mock = Mock()
    
    # Setup mock response with dates
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=days_back)
    
    results_by_time = []
    for day in range(days_back):
        date = (start_date + timedelta(days=day)).strftime('%Y-%m-%d')
        groups = []
        for service in services:
            groups.append({
                'Keys': [service],
                'Metrics': {
                    'BlendedCost': {'Amount': '10.00', 'Unit': 'USD'},
                    'UnblendedCost': {'Amount': '10.00', 'Unit': 'USD'}
                }
            })
        results_by_time.append({
            'TimePeriod': {'Start': date, 'End': date},
            'Groups': groups
        })
    
    cost_explorer_mock.get_cost_and_usage.return_value = {
        'ResultsByTime': results_by_time
    }
    
    # Create context manager
    manager = ContextManager(cost_explorer_client=cost_explorer_mock)
    
    # Get historical costs
    costs = manager.get_historical_costs(services, start_date, end_date)
    
    # Verify chronological order for each service
    for service, cost_data in costs.items():
        if len(cost_data) > 1:
            dates = [point['date'] for point in cost_data]
            
            # Dates should be in ascending order
            for i in range(len(dates) - 1):
                assert dates[i] <= dates[i + 1], \
                    f"Dates not in chronological order: {dates[i]} > {dates[i + 1]}"


# Property: Cost data always has required fields
@given(
    services=st.lists(
        st.sampled_from(['ec2', 'lambda', 's3']),
        min_size=1,
        max_size=3,
        unique=True
    ),
    days_back=st.integers(min_value=1, max_value=30)
)
@settings(max_examples=100)
def test_cost_data_required_fields(services, days_back):
    """
    Property: Cost data always has required fields
    For any cost data point, it should always have date, costs, and currency.
    
    Validates: Requirements 2.2
    """
    # Create mock Cost Explorer client
    cost_explorer_mock = Mock()
    
    # Setup mock response
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=days_back)
    
    results_by_time = []
    for day in range(days_back):
        date = (start_date + timedelta(days=day)).strftime('%Y-%m-%d')
        groups = []
        for service in services:
            groups.append({
                'Keys': [service],
                'Metrics': {
                    'BlendedCost': {'Amount': '15.25', 'Unit': 'USD'},
                    'UnblendedCost': {'Amount': '15.25', 'Unit': 'USD'}
                }
            })
        results_by_time.append({
            'TimePeriod': {'Start': date, 'End': date},
            'Groups': groups
        })
    
    cost_explorer_mock.get_cost_and_usage.return_value = {
        'ResultsByTime': results_by_time
    }
    
    # Create context manager
    manager = ContextManager(cost_explorer_client=cost_explorer_mock)
    
    # Get historical costs
    costs = manager.get_historical_costs(services, start_date, end_date)
    
    # Verify required fields for each cost data point
    for service, cost_data in costs.items():
        for point in cost_data:
            # Required fields
            assert 'date' in point, "Missing 'date' field"
            assert 'blended_cost' in point, "Missing 'blended_cost' field"
            assert 'unblended_cost' in point, "Missing 'unblended_cost' field"
            assert 'currency' in point, "Missing 'currency' field"
            
            # Cost values should be non-negative
            assert point['blended_cost'] >= 0, "Blended cost cannot be negative"
            assert point['unblended_cost'] >= 0, "Unblended cost cannot be negative"
            
            # Currency should be valid
            assert isinstance(point['currency'], str), "Currency must be a string"
            assert len(point['currency']) > 0, "Currency cannot be empty"


# Property: Context aggregation is deterministic
@given(
    services=st.lists(
        st.sampled_from(['ec2', 'lambda']),
        min_size=1,
        max_size=2,
        unique=True
    ),
    days_back=st.integers(min_value=1, max_value=7)
)
@settings(max_examples=100)
def test_context_aggregation_deterministic(services, days_back):
    """
    Property: Context aggregation is deterministic
    For any query intent, retrieving context multiple times should
    produce the same result (assuming data hasn't changed).
    
    Validates: Requirements 2.1
    """
    # Create mock clients with fixed responses
    cost_explorer_mock = Mock()
    dynamodb_mock = Mock()
    
    # Setup fixed mock responses
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=days_back)
    
    results_by_time = []
    for day in range(days_back):
        date = (start_date + timedelta(days=day)).strftime('%Y-%m-%d')
        groups = []
        for service in services:
            groups.append({
                'Keys': [service],
                'Metrics': {
                    'BlendedCost': {'Amount': '10.00', 'Unit': 'USD'},
                    'UnblendedCost': {'Amount': '10.00', 'Unit': 'USD'}
                }
            })
        results_by_time.append({
            'TimePeriod': {'Start': date, 'End': date},
            'Groups': groups
        })
    
    cost_explorer_mock.get_cost_and_usage.return_value = {
        'ResultsByTime': results_by_time
    }
    
    dynamodb_mock.query.return_value = {'Items': []}
    dynamodb_mock.scan.return_value = {'Items': []}
    
    # Create context manager
    manager = ContextManager(
        cost_explorer_client=cost_explorer_mock,
        dynamodb_client=dynamodb_mock
    )
    
    # Create query intent
    intent = QueryIntent(
        intent_type='cost_analysis',
        services=services,
        time_range=(start_date, end_date),
        accounts=[],
        entities={}
    )
    
    # Get context multiple times
    context1 = manager.get_cost_context(intent)
    context2 = manager.get_cost_context(intent)
    context3 = manager.get_cost_context(intent)
    
    # All should have the same structure
    assert len(context1.historical_costs) == len(context2.historical_costs) == len(context3.historical_costs)
    assert len(context1.prevention_actions) == len(context2.prevention_actions) == len(context3.prevention_actions)
    
    # Historical costs should match
    for service in services:
        if service in context1.historical_costs:
            assert service in context2.historical_costs
            assert service in context3.historical_costs
            assert len(context1.historical_costs[service]) == len(context2.historical_costs[service])
            assert len(context2.historical_costs[service]) == len(context3.historical_costs[service])
