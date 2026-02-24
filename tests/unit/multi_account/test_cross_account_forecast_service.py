"""
Unit tests for Cross-Account Forecast Service

Tests forecasting at organization, OU, and account levels.
Validates Requirements 13.1-13.3.
"""
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, MagicMock

from src.services.multi_account.cross_account_forecast_service import CrossAccountForecastService
from src.services.multi_account.models import Account, AccountCostData
from src.utils.types import ForecastResponse, ForecastDataPoint, ForecastMetadata


@pytest.fixture
def mock_forecast_engine():
    """Mock forecast engine"""
    return Mock()


@pytest.fixture
def mock_account_repo():
    """Mock account repository"""
    return Mock()


@pytest.fixture
def mock_cost_repo():
    """Mock cost repository"""
    return Mock()


@pytest.fixture
def forecast_service(mock_forecast_engine, mock_account_repo, mock_cost_repo):
    """Create forecast service with mocked dependencies"""
    return CrossAccountForecastService(
        forecast_engine=mock_forecast_engine,
        account_repository=mock_account_repo,
        cost_repository=mock_cost_repo
    )


def test_forecast_organization_costs(forecast_service, mock_forecast_engine, mock_account_repo, mock_cost_repo):
    """Test organization-level forecast generation (Requirement 13.1)"""
    # Given
    org_id = "o-123456789"
    
    # Mock accounts
    mock_account_repo.list_by_organization.return_value = [
        Account(
            id="111111111111",
            arn="",
            name="Account 1",
            email="account1@example.com",
            status="ACTIVE",
            joined_method="",
            joined_timestamp=datetime.utcnow()
        ),
        Account(
            id="222222222222",
            arn="",
            name="Account 2",
            email="account2@example.com",
            status="ACTIVE",
            joined_method="",
            joined_timestamp=datetime.utcnow()
        )
    ]
    
    # Mock cost repository to return None (no historical data)
    mock_cost_repo.get.return_value = None
    
    # Mock forecast response
    mock_forecast_engine.generate_forecast.return_value = ForecastResponse(
        success=True,
        forecast_data=[
            ForecastDataPoint(
                date="2026-02-25",
                predicted_cost=100.0,
                confidence_lower=90.0,
                confidence_upper=110.0,
                currency="USD"
            ),
            ForecastDataPoint(
                date="2026-02-26",
                predicted_cost=105.0,
                confidence_lower=95.0,
                confidence_upper=115.0,
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
    
    # When
    result = forecast_service.forecast_organization_costs(org_id, days=30)
    
    # Then
    assert result["org_id"] == org_id
    assert result["account_count"] == 2
    assert result["forecast_horizon"] == 30
    assert len(result["forecast_data"]) == 2
    assert result["total_forecasted_cost"] == Decimal("205.0")


def test_forecast_organization_costs_no_accounts(forecast_service, mock_account_repo):
    """Test organization forecast with no accounts"""
    # Given
    org_id = "o-123456789"
    mock_account_repo.list_by_organization.return_value = []
    
    # When
    result = forecast_service.forecast_organization_costs(org_id)
    
    # Then
    assert result["org_id"] == org_id
    assert result["account_count"] == 0
    assert result["total_forecasted_cost"] == Decimal("0")
    assert "error" in result


def test_forecast_ou_costs(forecast_service, mock_forecast_engine, mock_cost_repo):
    """Test OU-level forecast generation (Requirement 13.2)"""
    # Given
    ou_id = "ou-abc123"
    account_ids = ["111111111111", "222222222222"]
    
    # Mock cost repository to return None (no historical data)
    mock_cost_repo.get.return_value = None
    
    # Mock forecast response
    mock_forecast_engine.generate_forecast.return_value = ForecastResponse(
        success=True,
        forecast_data=[
            ForecastDataPoint(
                date="2026-02-25",
                predicted_cost=50.0,
                confidence_lower=45.0,
                confidence_upper=55.0,
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
    
    # When
    result = forecast_service.forecast_ou_costs(ou_id, account_ids, days=30)
    
    # Then
    assert result["ou_id"] == ou_id
    assert result["account_count"] == 2
    assert result["forecast_horizon"] == 30
    assert len(result["forecast_data"]) == 1
    assert result["total_forecasted_cost"] == Decimal("50.0")


def test_forecast_ou_costs_no_accounts(forecast_service):
    """Test OU forecast with no accounts"""
    # Given
    ou_id = "ou-abc123"
    account_ids = []
    
    # When
    result = forecast_service.forecast_ou_costs(ou_id, account_ids)
    
    # Then
    assert result["ou_id"] == ou_id
    assert result["account_count"] == 0
    assert result["total_forecasted_cost"] == Decimal("0")
    assert "error" in result


def test_forecast_account_costs(forecast_service, mock_forecast_engine):
    """Test account-level forecast generation (Requirement 13.3)"""
    # Given
    account_id = "111111111111"
    
    # Mock forecast response
    mock_forecast_engine.generate_forecast.return_value = ForecastResponse(
        success=True,
        forecast_data=[
            ForecastDataPoint(
                date="2026-02-25",
                predicted_cost=25.0,
                confidence_lower=20.0,
                confidence_upper=30.0,
                currency="USD"
            ),
            ForecastDataPoint(
                date="2026-02-26",
                predicted_cost=27.0,
                confidence_lower=22.0,
                confidence_upper=32.0,
                currency="USD"
            ),
            ForecastDataPoint(
                date="2026-02-27",
                predicted_cost=28.0,
                confidence_lower=23.0,
                confidence_upper=33.0,
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
    
    # When
    result = forecast_service.forecast_account_costs(account_id, days=30)
    
    # Then
    assert result["account_id"] == account_id
    assert result["forecast_horizon"] == 30
    assert len(result["forecast_data"]) == 3
    assert result["total_forecasted_cost"] == Decimal("80.0")


def test_forecast_with_weekly_granularity(forecast_service, mock_forecast_engine, mock_account_repo, mock_cost_repo):
    """Test forecast with weekly granularity"""
    # Given
    org_id = "o-123456789"
    
    mock_account_repo.list_by_organization.return_value = [
        Account(
            id="111111111111",
            arn="",
            name="Account 1",
            email="account1@example.com",
            status="ACTIVE",
            joined_method="",
            joined_timestamp=datetime.utcnow()
        )
    ]
    
    # Mock cost repository to return None (no historical data)
    mock_cost_repo.get.return_value = None
    
    # Mock forecast response with weekly data
    mock_forecast_engine.generate_forecast.return_value = ForecastResponse(
        success=True,
        forecast_data=[
            ForecastDataPoint(
                date="2026-02-25",
                predicted_cost=700.0,  # Week total
                confidence_lower=650.0,
                confidence_upper=750.0,
                currency="USD"
            )
        ],
        metadata=ForecastMetadata(
            timestamp="2026-02-24T10:00:00Z",
            forecast_horizon=30,
            granularity="weekly",
            model_used="anthropic.claude-v2",
            service=None,
            services_included=None,
            cache_hit=False,
            historical_data_days=90
        )
    )
    
    # When
    result = forecast_service.forecast_organization_costs(org_id, days=30, granularity="weekly")
    
    # Then
    assert result["granularity"] == "weekly"
    assert result["total_forecasted_cost"] == Decimal("700.0")


def test_forecast_calls_engine_with_correct_parameters(forecast_service, mock_forecast_engine, mock_account_repo, mock_cost_repo):
    """Test that forecast engine is called with correct parameters"""
    # Given
    org_id = "o-123456789"
    days = 14
    granularity = "daily"
    
    mock_account_repo.list_by_organization.return_value = [
        Account(
            id="111111111111",
            arn="",
            name="Account 1",
            email="account1@example.com",
            status="ACTIVE",
            joined_method="",
            joined_timestamp=datetime.utcnow()
        )
    ]
    
    # Mock cost repository to return None (no historical data)
    mock_cost_repo.get.return_value = None
    
    mock_forecast_engine.generate_forecast.return_value = ForecastResponse(
        success=True,
        forecast_data=[],
        metadata=ForecastMetadata(
            timestamp="2026-02-24T10:00:00Z",
            forecast_horizon=14,
            granularity="daily",
            model_used="anthropic.claude-v2",
            service=None,
            services_included=None,
            cache_hit=False,
            historical_data_days=90
        )
    )
    
    # When
    forecast_service.forecast_organization_costs(org_id, days=days, granularity=granularity)
    
    # Then
    mock_forecast_engine.generate_forecast.assert_called_once_with(
        service=None,
        days=days,
        granularity=granularity
    )
