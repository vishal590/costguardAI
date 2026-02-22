"""
Unit tests for BudgetMonitor.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, UTC
from src.services.budget_monitor import BudgetMonitor
from src.utils.types import BudgetStatus, ThresholdEvent


class TestBudgetMonitor:
    """Tests for BudgetMonitor class."""
    
    @pytest.fixture
    def mock_budgets_client(self):
        """Create mock AWS Budgets client."""
        client = Mock()
        return client
    
    @pytest.fixture
    def mock_cost_estimator(self):
        """Create mock cost estimator."""
        estimator = Mock()
        return estimator
    
    @pytest.fixture
    def budget_monitor(self, mock_budgets_client, mock_cost_estimator):
        """Create BudgetMonitor instance."""
        return BudgetMonitor(mock_budgets_client, mock_cost_estimator)
    
    def test_initialization(self, budget_monitor):
        """Test BudgetMonitor initialization."""
        assert budget_monitor.warning_threshold == 0.80
        assert budget_monitor.action_threshold == 0.90
    
    def test_calculate_utilization_with_forecasted_spend(self, budget_monitor):
        """Test utilization calculation with forecasted spend."""
        budget = {
            'BudgetLimit': {'Amount': '1000.0'},
            'CalculatedSpend': {
                'ActualSpend': {'Amount': '700.0'},
                'ForecastedSpend': {'Amount': '850.0'}
            }
        }
        
        utilization = budget_monitor.calculate_utilization(budget)
        assert utilization == 0.85  # 850 / 1000
    
    def test_calculate_utilization_with_actual_spend_only(self, budget_monitor):
        """Test utilization calculation with only actual spend."""
        budget = {
            'BudgetLimit': {'Amount': '1000.0'},
            'CalculatedSpend': {
                'ActualSpend': {'Amount': '800.0'}
            }
        }
        
        utilization = budget_monitor.calculate_utilization(budget)
        assert utilization == 0.80  # 800 / 1000
    
    def test_calculate_utilization_zero_limit(self, budget_monitor):
        """Test utilization calculation with zero limit."""
        budget = {
            'BudgetLimit': {'Amount': '0.0'},
            'CalculatedSpend': {
                'ActualSpend': {'Amount': '100.0'}
            }
        }
        
        utilization = budget_monitor.calculate_utilization(budget)
        assert utilization == 0.0
    
    def test_check_thresholds_below_warning(self, budget_monitor):
        """Test threshold check when below warning threshold."""
        budget_status = BudgetStatus(
            budget_name="test-budget",
            limit=1000.0,
            actual_spend=700.0,
            forecasted_spend=750.0,
            utilization_percent=75.0,
            currency="USD",
            time_period="2024-01"
        )
        
        event = budget_monitor.check_thresholds(budget_status)
        assert event is None
    
    def test_check_thresholds_at_warning(self, budget_monitor):
        """Test threshold check at warning threshold (80%)."""
        budget_status = BudgetStatus(
            budget_name="test-budget",
            limit=1000.0,
            actual_spend=800.0,
            forecasted_spend=800.0,
            utilization_percent=80.0,
            currency="USD",
            time_period="2024-01"
        )
        
        event = budget_monitor.check_thresholds(budget_status)
        assert event is not None
        assert event.threshold_type == "warning"
        assert event.utilization_percent == 80.0
    
    def test_check_thresholds_between_warning_and_action(self, budget_monitor):
        """Test threshold check between warning and action thresholds."""
        budget_status = BudgetStatus(
            budget_name="test-budget",
            limit=1000.0,
            actual_spend=850.0,
            forecasted_spend=850.0,
            utilization_percent=85.0,
            currency="USD",
            time_period="2024-01"
        )
        
        event = budget_monitor.check_thresholds(budget_status)
        assert event is not None
        assert event.threshold_type == "warning"
    
    def test_check_thresholds_at_action(self, budget_monitor):
        """Test threshold check at action threshold (90%)."""
        budget_status = BudgetStatus(
            budget_name="test-budget",
            limit=1000.0,
            actual_spend=900.0,
            forecasted_spend=900.0,
            utilization_percent=90.0,
            currency="USD",
            time_period="2024-01"
        )
        
        event = budget_monitor.check_thresholds(budget_status)
        assert event is not None
        assert event.threshold_type == "action"
        assert event.utilization_percent == 90.0
    
    def test_check_thresholds_above_action(self, budget_monitor):
        """Test threshold check above action threshold."""
        budget_status = BudgetStatus(
            budget_name="test-budget",
            limit=1000.0,
            actual_spend=950.0,
            forecasted_spend=950.0,
            utilization_percent=95.0,
            currency="USD",
            time_period="2024-01"
        )
        
        event = budget_monitor.check_thresholds(budget_status)
        assert event is not None
        assert event.threshold_type == "action"
    
    def test_poll_budgets_success(self, budget_monitor, mock_budgets_client):
        """Test successful budget polling."""
        # Mock budgets response
        mock_budgets_client.describe_budgets.return_value = {
            'Budgets': [
                {
                    'BudgetName': 'monthly-budget',
                    'BudgetLimit': {'Amount': '1000.0', 'Unit': 'USD'},
                    'CalculatedSpend': {
                        'ActualSpend': {'Amount': '850.0'},
                        'ForecastedSpend': {'Amount': '900.0'}
                    },
                    'TimePeriod': {'Start': '2024-01-01', 'End': '2024-01-31'}
                }
            ]
        }
        
        # Mock _get_account_id
        budget_monitor._get_account_id = Mock(return_value='123456789012')
        
        events = budget_monitor.poll_budgets()
        
        assert len(events) == 1
        assert events[0].threshold_type == "action"
        assert events[0].budget_name == "monthly-budget"
    
    def test_poll_budgets_multiple_budgets(self, budget_monitor, mock_budgets_client):
        """Test polling multiple budgets."""
        # Mock multiple budgets
        mock_budgets_client.describe_budgets.return_value = {
            'Budgets': [
                {
                    'BudgetName': 'budget-1',
                    'BudgetLimit': {'Amount': '1000.0', 'Unit': 'USD'},
                    'CalculatedSpend': {
                        'ActualSpend': {'Amount': '850.0'},
                        'ForecastedSpend': {'Amount': '850.0'}
                    },
                    'TimePeriod': {'Start': '2024-01-01', 'End': '2024-01-31'}
                },
                {
                    'BudgetName': 'budget-2',
                    'BudgetLimit': {'Amount': '500.0', 'Unit': 'USD'},
                    'CalculatedSpend': {
                        'ActualSpend': {'Amount': '450.0'},
                        'ForecastedSpend': {'Amount': '450.0'}
                    },
                    'TimePeriod': {'Start': '2024-01-01', 'End': '2024-01-31'}
                }
            ]
        }
        
        # Mock _get_account_id
        budget_monitor._get_account_id = Mock(return_value='123456789012')
        
        events = budget_monitor.poll_budgets()
        
        assert len(events) == 2
        assert events[0].threshold_type == "warning"
        assert events[1].threshold_type == "action"
    
    def test_poll_budgets_no_threshold_events(self, budget_monitor, mock_budgets_client):
        """Test polling when no thresholds are crossed."""
        # Mock budget below thresholds
        mock_budgets_client.describe_budgets.return_value = {
            'Budgets': [
                {
                    'BudgetName': 'safe-budget',
                    'BudgetLimit': {'Amount': '1000.0', 'Unit': 'USD'},
                    'CalculatedSpend': {
                        'ActualSpend': {'Amount': '500.0'},
                        'ForecastedSpend': {'Amount': '600.0'}
                    },
                    'TimePeriod': {'Start': '2024-01-01', 'End': '2024-01-31'}
                }
            ]
        }
        
        # Mock _get_account_id
        budget_monitor._get_account_id = Mock(return_value='123456789012')
        
        events = budget_monitor.poll_budgets()
        
        assert len(events) == 0
    
    def test_poll_budgets_api_error_fallback(self, budget_monitor, mock_budgets_client):
        """Test fallback to cost estimator when API fails."""
        # Mock API error
        mock_budgets_client.describe_budgets.side_effect = Exception("API Error")
        
        # Mock _get_account_id
        budget_monitor._get_account_id = Mock(return_value='123456789012')
        
        events = budget_monitor.poll_budgets()
        
        # Should return fallback budget status
        assert len(events) == 0  # Fallback returns 0% utilization
    
    def test_create_budget_status(self, budget_monitor):
        """Test creating BudgetStatus from AWS budget dict."""
        budget = {
            'BudgetName': 'test-budget',
            'BudgetLimit': {'Amount': '1000.0', 'Unit': 'USD'},
            'CalculatedSpend': {
                'ActualSpend': {'Amount': '800.0'},
                'ForecastedSpend': {'Amount': '850.0'}
            },
            'TimePeriod': {'Start': '2024-01-01', 'End': '2024-01-31'}
        }
        
        status = budget_monitor._create_budget_status(budget)
        
        assert status.budget_name == 'test-budget'
        assert status.limit == 1000.0
        assert status.actual_spend == 800.0
        assert status.forecasted_spend == 850.0
        assert status.utilization_percent == 85.0
        assert status.currency == 'USD'
    
    def test_create_threshold_event(self, budget_monitor):
        """Test creating ThresholdEvent."""
        budget_status = BudgetStatus(
            budget_name="test-budget",
            limit=1000.0,
            actual_spend=900.0,
            forecasted_spend=900.0,
            utilization_percent=90.0,
            currency="USD",
            time_period="2024-01"
        )
        
        event = budget_monitor._create_threshold_event(budget_status, "action")
        
        assert event.budget_name == "test-budget"
        assert event.threshold_type == "action"
        assert event.utilization_percent == 90.0
        assert event.budget_status == budget_status
    
    def test_threshold_edge_case_exactly_80_percent(self, budget_monitor):
        """Test edge case: exactly 80% utilization."""
        budget_status = BudgetStatus(
            budget_name="edge-budget",
            limit=1000.0,
            actual_spend=800.0,
            forecasted_spend=800.0,
            utilization_percent=80.0,
            currency="USD",
            time_period="2024-01"
        )
        
        event = budget_monitor.check_thresholds(budget_status)
        assert event is not None
        assert event.threshold_type == "warning"
    
    def test_threshold_edge_case_exactly_90_percent(self, budget_monitor):
        """Test edge case: exactly 90% utilization."""
        budget_status = BudgetStatus(
            budget_name="edge-budget",
            limit=1000.0,
            actual_spend=900.0,
            forecasted_spend=900.0,
            utilization_percent=90.0,
            currency="USD",
            time_period="2024-01"
        )
        
        event = budget_monitor.check_thresholds(budget_status)
        assert event is not None
        assert event.threshold_type == "action"
    
    def test_threshold_edge_case_just_below_80_percent(self, budget_monitor):
        """Test edge case: just below 80% utilization."""
        budget_status = BudgetStatus(
            budget_name="edge-budget",
            limit=1000.0,
            actual_spend=799.0,
            forecasted_spend=799.0,
            utilization_percent=79.9,
            currency="USD",
            time_period="2024-01"
        )
        
        event = budget_monitor.check_thresholds(budget_status)
        assert event is None
