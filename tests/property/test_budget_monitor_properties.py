"""
Property-based tests for BudgetMonitor.

Feature: automated-cost-prevention, Property 1: Budget Threshold Detection
For any budget with utilization >= 80%, the Budget_Monitor should trigger 
a threshold event within 5 minutes of the threshold being crossed.
Validates: Requirements 1.2, 1.3
"""
import pytest
from hypothesis import given, strategies as st, assume, settings
from unittest.mock import Mock
from src.services.budget_monitor import BudgetMonitor
from src.utils.types import BudgetStatus


def create_budget_monitor():
    """Helper function to create BudgetMonitor instance."""
    mock_budgets_client = Mock()
    mock_cost_estimator = Mock()
    return BudgetMonitor(mock_budgets_client, mock_cost_estimator)


class TestBudgetMonitorProperties:
    """Property-based tests for BudgetMonitor."""
    
    @settings(max_examples=100)
    @given(
        budget_name=st.text(min_size=1, max_size=50),
        limit=st.floats(min_value=100.0, max_value=100000.0),
        utilization_percent=st.floats(min_value=80.0, max_value=200.0)
    )
    def test_property_budget_threshold_detection_warning(
        self, 
        budget_name, 
        limit, 
        utilization_percent
    ):
        """
        Property 1: Budget Threshold Detection (Warning)
        
        For any budget with utilization >= 80% and < 90%, 
        the Budget_Monitor should trigger a warning threshold event.
        
        Validates: Requirements 1.2
        """
        # Feature: automated-cost-prevention, Property 1: Budget Threshold Detection
        
        budget_monitor = create_budget_monitor()
        
        # Ensure utilization is in warning range (80% <= x < 90%)
        assume(80.0 <= utilization_percent < 90.0)
        
        # Calculate actual and forecasted spend based on utilization
        actual_spend = (utilization_percent / 100.0) * limit
        forecasted_spend = actual_spend
        
        # Create budget status
        budget_status = BudgetStatus(
            budget_name=budget_name,
            limit=limit,
            actual_spend=actual_spend,
            forecasted_spend=forecasted_spend,
            utilization_percent=utilization_percent,
            currency="USD",
            time_period="2024-01"
        )
        
        # Check thresholds
        event = budget_monitor.check_thresholds(budget_status)
        
        # Property: Should trigger warning event
        assert event is not None, f"Expected warning event for {utilization_percent}% utilization"
        assert event.threshold_type == "warning", f"Expected 'warning' but got '{event.threshold_type}' for {utilization_percent}%"
        assert event.budget_name == budget_name
        assert event.utilization_percent == utilization_percent
    
    @settings(max_examples=100)
    @given(
        budget_name=st.text(min_size=1, max_size=50),
        limit=st.floats(min_value=100.0, max_value=100000.0),
        utilization_percent=st.floats(min_value=90.0, max_value=200.0)
    )
    def test_property_budget_threshold_detection_action(
        self, 
        budget_name, 
        limit, 
        utilization_percent
    ):
        """
        Property 1: Budget Threshold Detection (Action)
        
        For any budget with utilization >= 90%, 
        the Budget_Monitor should trigger an action threshold event.
        
        Validates: Requirements 1.3
        """
        # Feature: automated-cost-prevention, Property 1: Budget Threshold Detection
        
        budget_monitor = create_budget_monitor()
        
        # Ensure utilization is in action range (>= 90%)
        assume(utilization_percent >= 90.0)
        
        # Calculate actual and forecasted spend based on utilization
        actual_spend = (utilization_percent / 100.0) * limit
        forecasted_spend = actual_spend
        
        # Create budget status
        budget_status = BudgetStatus(
            budget_name=budget_name,
            limit=limit,
            actual_spend=actual_spend,
            forecasted_spend=forecasted_spend,
            utilization_percent=utilization_percent,
            currency="USD",
            time_period="2024-01"
        )
        
        # Check thresholds
        event = budget_monitor.check_thresholds(budget_status)
        
        # Property: Should trigger action event
        assert event is not None, f"Expected action event for {utilization_percent}% utilization"
        assert event.threshold_type == "action", f"Expected 'action' but got '{event.threshold_type}' for {utilization_percent}%"
        assert event.budget_name == budget_name
        assert event.utilization_percent == utilization_percent
    
    @settings(max_examples=100)
    @given(
        budget_name=st.text(min_size=1, max_size=50),
        limit=st.floats(min_value=100.0, max_value=100000.0),
        utilization_percent=st.floats(min_value=0.0, max_value=79.99)
    )
    def test_property_budget_threshold_no_event_below_warning(
        self, 
        budget_name, 
        limit, 
        utilization_percent
    ):
        """
        Property 1: Budget Threshold Detection (Below Warning)
        
        For any budget with utilization < 80%, 
        the Budget_Monitor should NOT trigger any threshold event.
        
        Validates: Requirements 1.2, 1.3
        """
        # Feature: automated-cost-prevention, Property 1: Budget Threshold Detection
        
        budget_monitor = create_budget_monitor()
        
        # Ensure utilization is below warning threshold
        assume(utilization_percent < 80.0)
        
        # Calculate actual and forecasted spend based on utilization
        actual_spend = (utilization_percent / 100.0) * limit
        forecasted_spend = actual_spend
        
        # Create budget status
        budget_status = BudgetStatus(
            budget_name=budget_name,
            limit=limit,
            actual_spend=actual_spend,
            forecasted_spend=forecasted_spend,
            utilization_percent=utilization_percent,
            currency="USD",
            time_period="2024-01"
        )
        
        # Check thresholds
        event = budget_monitor.check_thresholds(budget_status)
        
        # Property: Should NOT trigger any event
        assert event is None, f"Expected no event for {utilization_percent}% utilization, but got {event.threshold_type if event else None}"
    
    @settings(max_examples=100)
    @given(
        limit=st.floats(min_value=100.0, max_value=100000.0),
        actual_spend=st.floats(min_value=0.0, max_value=100000.0),
        forecasted_spend=st.floats(min_value=0.0, max_value=100000.0)
    )
    def test_property_utilization_calculation_consistency(
        self, 
        limit, 
        actual_spend, 
        forecasted_spend
    ):
        """
        Property: Utilization Calculation Consistency
        
        For any budget, the calculated utilization should be consistent
        with the formula: (forecasted_spend / limit) when forecasted is available,
        or (actual_spend / limit) otherwise.
        """
        # Feature: automated-cost-prevention, Property 1: Budget Threshold Detection
        
        budget_monitor = create_budget_monitor()
        
        # Test with forecasted spend
        budget_with_forecast = {
            'BudgetLimit': {'Amount': str(limit)},
            'CalculatedSpend': {
                'ActualSpend': {'Amount': str(actual_spend)},
                'ForecastedSpend': {'Amount': str(forecasted_spend)}
            }
        }
        
        utilization = budget_monitor.calculate_utilization(budget_with_forecast)
        expected_utilization = forecasted_spend / limit if limit > 0 else 0.0
        
        # Property: Calculated utilization should match expected
        assert abs(utilization - expected_utilization) < 0.0001, \
            f"Expected {expected_utilization}, got {utilization}"
    
    @settings(max_examples=100)
    @given(
        limit=st.floats(min_value=100.0, max_value=100000.0),
        actual_spend=st.floats(min_value=0.0, max_value=100000.0)
    )
    def test_property_utilization_without_forecast(
        self, 
        limit, 
        actual_spend
    ):
        """
        Property: Utilization Calculation Without Forecast
        
        For any budget without forecasted spend, the calculated utilization 
        should use actual spend.
        """
        # Feature: automated-cost-prevention, Property 1: Budget Threshold Detection
        
        budget_monitor = create_budget_monitor()
        
        # Test without forecasted spend
        budget_without_forecast = {
            'BudgetLimit': {'Amount': str(limit)},
            'CalculatedSpend': {
                'ActualSpend': {'Amount': str(actual_spend)}
            }
        }
        
        utilization = budget_monitor.calculate_utilization(budget_without_forecast)
        expected_utilization = actual_spend / limit if limit > 0 else 0.0
        
        # Property: Calculated utilization should match expected
        assert abs(utilization - expected_utilization) < 0.0001, \
            f"Expected {expected_utilization}, got {utilization}"
    
    @settings(max_examples=100)
    @given(
        budget_name=st.text(min_size=1, max_size=50),
        limit=st.floats(min_value=100.0, max_value=100000.0),
        utilization_percent=st.floats(min_value=0.0, max_value=200.0)
    )
    def test_property_threshold_type_correctness(
        self, 
        budget_name, 
        limit, 
        utilization_percent
    ):
        """
        Property: Threshold Type Correctness
        
        For any budget:
        - If utilization >= 90%, threshold_type must be "action"
        - If 80% <= utilization < 90%, threshold_type must be "warning"
        - If utilization < 80%, no event should be triggered
        """
        # Feature: automated-cost-prevention, Property 1: Budget Threshold Detection
        
        budget_monitor = create_budget_monitor()
        
        # Calculate spend
        actual_spend = (utilization_percent / 100.0) * limit
        
        # Create budget status
        budget_status = BudgetStatus(
            budget_name=budget_name,
            limit=limit,
            actual_spend=actual_spend,
            forecasted_spend=actual_spend,
            utilization_percent=utilization_percent,
            currency="USD",
            time_period="2024-01"
        )
        
        # Check thresholds
        event = budget_monitor.check_thresholds(budget_status)
        
        # Property: Verify correct threshold type based on utilization
        if utilization_percent >= 90.0:
            assert event is not None, f"Expected event for {utilization_percent}%"
            assert event.threshold_type == "action", \
                f"Expected 'action' for {utilization_percent}%, got '{event.threshold_type}'"
        elif utilization_percent >= 80.0:
            assert event is not None, f"Expected event for {utilization_percent}%"
            assert event.threshold_type == "warning", \
                f"Expected 'warning' for {utilization_percent}%, got '{event.threshold_type}'"
        else:
            assert event is None, \
                f"Expected no event for {utilization_percent}%, got {event.threshold_type if event else None}"
