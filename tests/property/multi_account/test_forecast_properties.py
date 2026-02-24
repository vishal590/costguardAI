"""
Property-Based Tests for Cross-Account Forecasting

Tests universal properties of multi-account forecasting.
"""
import pytest
from decimal import Decimal
from datetime import datetime
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock

from src.services.multi_account.cross_account_forecast_service import CrossAccountForecastService
from src.services.multi_account.models import Account
from src.utils.types import ForecastResponse, ForecastDataPoint, ForecastMetadata


@given(
    account_forecasts=st.lists(
        st.decimals(min_value=10, max_value=10000, places=2),
        min_size=2,
        max_size=10
    )
)
@settings(max_examples=20)
def test_property_11_cross_account_forecast_consistency(account_forecasts):
    """
    Property 11: Cross-Account Forecast Consistency
    
    For any organization, sum of per-account forecasts should approximately
    equal the organization-level forecast (within 10% margin).
    
    Validates: Requirements 13.4
    """
    # Create fresh mocks for each test iteration
    forecast_engine = Mock()
    account_repo = Mock()
    cost_repo = Mock()
    cost_repo.get.return_value = None  # No historical data
    service = CrossAccountForecastService(forecast_engine, account_repo, cost_repo)
    
    # Given: Organization with multiple accounts
    org_id = "o-test123"
    num_accounts = len(account_forecasts)
    
    # Mock accounts
    accounts = [
        Account(
            id=f"acc{i:012d}",
            arn="",
            name=f"Account {i}",
            email=f"account{i}@example.com",
            status="ACTIVE",
            joined_method="",
            joined_timestamp=datetime.utcnow()
        )
        for i in range(num_accounts)
    ]
    account_repo.list_by_organization.return_value = accounts
    
    # Calculate expected org forecast (sum of account forecasts)
    expected_org_forecast = sum(account_forecasts)
    
    # Mock organization-level forecast
    forecast_engine.generate_forecast.return_value = ForecastResponse(
        success=True,
        forecast_data=[
            ForecastDataPoint(
                date="2026-02-25",
                predicted_cost=float(expected_org_forecast),
                confidence_lower=float(expected_org_forecast * Decimal("0.9")),
                confidence_upper=float(expected_org_forecast * Decimal("1.1")),
                currency="USD"
            )
        ],
        metadata=ForecastMetadata(
            timestamp="2026-02-24T10:00:00Z",
            forecast_horizon=30,
            granularity="daily",
            model_used="anthropic.claude-v2",
            service=None,
            services_included=None,
            cache_hit=False,
            historical_data_days=90
        )
    )
    
    # When: Generate organization forecast
    org_result = service.forecast_organization_costs(org_id, days=30)
    
    # Then: Organization forecast should equal sum of account forecasts
    org_forecast = org_result["total_forecasted_cost"]
    sum_account_forecasts = sum(account_forecasts)
    
    # Allow 10% margin for aggregation differences
    margin = sum_account_forecasts * Decimal("0.10")
    assert abs(org_forecast - sum_account_forecasts) <= margin, \
        f"Org forecast ({org_forecast}) differs from sum of accounts ({sum_account_forecasts}) by more than 10%"


@given(
    daily_forecasts=st.lists(
        st.decimals(min_value=1, max_value=1000, places=2),
        min_size=7,
        max_size=30
    )
)
@settings(max_examples=20)
def test_property_forecast_total_consistency(daily_forecasts):
    """
    Property: Forecast Total Consistency
    
    For any forecast, the total forecasted cost should equal the sum
    of all daily predictions.
    
    Validates: Requirements 13.1, 13.2, 13.3
    """
    # Create fresh mocks
    forecast_engine = Mock()
    account_repo = Mock()
    cost_repo = Mock()
    service = CrossAccountForecastService(forecast_engine, account_repo, cost_repo)
    
    # Given: Account with daily forecasts
    account_id = "111111111111"
    
    # Mock forecast response with daily data
    forecast_data_points = [
        ForecastDataPoint(
            date=f"2026-02-{25+i:02d}" if 25+i <= 28 else f"2026-03-{(25+i-28):02d}",
            predicted_cost=float(cost),
            confidence_lower=float(cost * Decimal("0.9")),
            confidence_upper=float(cost * Decimal("1.1")),
            currency="USD"
        )
        for i, cost in enumerate(daily_forecasts)
    ]
    
    forecast_engine.generate_forecast.return_value = ForecastResponse(
        success=True,
        forecast_data=forecast_data_points,
        metadata=ForecastMetadata(
            timestamp="2026-02-24T10:00:00Z",
            forecast_horizon=30,
            granularity="daily",
            model_used="anthropic.claude-v2",
            service=None,
            services_included=None,
            cache_hit=False,
            historical_data_days=90
        )
    )
    
    # When: Generate account forecast
    result = service.forecast_account_costs(account_id, days=30)
    
    # Then: Total should equal sum of daily forecasts
    expected_total = sum(daily_forecasts)
    actual_total = result["total_forecasted_cost"]
    
    # Allow small rounding differences
    assert abs(actual_total - expected_total) < Decimal("0.01"), \
        f"Total forecast ({actual_total}) doesn't match sum of daily forecasts ({expected_total})"


@given(
    forecast_horizon=st.integers(min_value=7, max_value=30)
)
@settings(max_examples=20)
def test_property_forecast_horizon_consistency(forecast_horizon):
    """
    Property: Forecast Horizon Consistency
    
    For any forecast horizon, the number of forecast data points should
    match the requested horizon (for daily granularity).
    
    Validates: Requirements 13.6
    """
    # Create fresh mocks
    forecast_engine = Mock()
    account_repo = Mock()
    cost_repo = Mock()
    service = CrossAccountForecastService(forecast_engine, account_repo, cost_repo)
    
    # Given: Account and forecast horizon
    account_id = "111111111111"
    
    # Mock forecast response with correct number of days
    forecast_data_points = [
        ForecastDataPoint(
            date=f"2026-02-{25+i:02d}" if 25+i <= 28 else f"2026-03-{(25+i-28):02d}",
            predicted_cost=100.0,
            confidence_lower=90.0,
            confidence_upper=110.0,
            currency="USD"
        )
        for i in range(forecast_horizon)
    ]
    
    forecast_engine.generate_forecast.return_value = ForecastResponse(
        success=True,
        forecast_data=forecast_data_points,
        metadata=ForecastMetadata(
            timestamp="2026-02-24T10:00:00Z",
            forecast_horizon=forecast_horizon,
            granularity="daily",
            model_used="anthropic.claude-v2",
            service=None,
            services_included=None,
            cache_hit=False,
            historical_data_days=90
        )
    )
    
    # When: Generate forecast
    result = service.forecast_account_costs(account_id, days=forecast_horizon, granularity="daily")
    
    # Then: Number of data points should match horizon
    assert len(result["forecast_data"]) == forecast_horizon, \
        f"Expected {forecast_horizon} data points, got {len(result['forecast_data'])}"
