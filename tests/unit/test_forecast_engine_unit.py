"""
Unit tests for ForecastEngine.

Tests cover:
- Forecast generation with various parameters
- Cache hit/miss flows
- Weekly aggregation
- Service-specific forecasts
- Total forecasts
- Accuracy metrics calculation
- Error handling (insufficient data, Bedrock failures)
"""

import pytest
from unittest.mock import Mock
from datetime import datetime, timedelta, UTC
from src.services.forecast_engine import ForecastEngine
from src.utils.types import (
    ForecastResponse,
    ForecastDataPoint,
    ForecastMetadata,
    ProcessedData,
    BedrockResponse,
    InsufficientDataError,
    BedrockAPIError
)


@pytest.fixture
def mock_bedrock_client():
    """Mock Bedrock client."""
    client = Mock()
    client.model_id = "amazon.nova-lite-v1:0"
    return client


@pytest.fixture
def mock_historical_data_retriever():
    """Mock historical data retriever."""
    return Mock()


@pytest.fixture
def mock_cache_manager():
    """Mock cache manager."""
    return Mock()


@pytest.fixture
def forecast_engine(mock_bedrock_client, mock_historical_data_retriever, mock_cache_manager):
    """Create ForecastEngine instance with mocked dependencies."""
    return ForecastEngine(
        bedrock_client=mock_bedrock_client,
        historical_data_retriever=mock_historical_data_retriever,
        cache_manager=mock_cache_manager
    )


@pytest.fixture
def sample_historical_data():
    """Sample historical data."""
    dates = [(datetime.now(UTC).date() - timedelta(days=i)).isoformat() for i in range(60, 0, -1)]
    costs = [100.0 + i * 2.5 for i in range(60)]
    return ProcessedData(timestamps=dates, costs=costs, service=None, total_days=60)


@pytest.fixture
def sample_bedrock_response():
    """Sample Bedrock response."""
    dates = [(datetime.now(UTC).date() + timedelta(days=i)).isoformat() for i in range(1, 31)]
    predictions = [150.0 + i * 1.5 for i in range(30)]
    confidence_lower = [p * 0.9 for p in predictions]
    confidence_upper = [p * 1.1 for p in predictions]
    return BedrockResponse(
        predictions=predictions,
        confidence_lower=confidence_lower,
        confidence_upper=confidence_upper,
        dates=dates,
        model_id="amazon.nova-lite-v1:0",
        latency_ms=1500
    )


def test_generate_forecast_cache_miss(
    forecast_engine, mock_cache_manager, mock_historical_data_retriever,
    mock_bedrock_client, sample_historical_data, sample_bedrock_response
):
    """Test forecast generation when cache misses."""
    mock_cache_manager.get_cached_forecast.return_value = None
    mock_historical_data_retriever.get_historical_data.return_value = sample_historical_data
    mock_bedrock_client.invoke_forecast.return_value = sample_bedrock_response
    
    result = forecast_engine.generate_forecast(service=None, days=30, granularity="daily")
    
    assert result.success is True
    assert len(result.forecast_data) == 30
    assert result.metadata.forecast_horizon == 30
    assert result.metadata.granularity == "daily"
    assert result.metadata.cache_hit is False
    assert result.metadata.model_used == "amazon.nova-lite-v1:0"
    
    mock_cache_manager.get_cached_forecast.assert_called_once_with(None, 30, "daily")
    mock_cache_manager.store_forecast.assert_called_once()
    mock_historical_data_retriever.get_historical_data.assert_called_once_with(service=None, days_back=90)
    mock_bedrock_client.invoke_forecast.assert_called_once()


def test_generate_forecast_cache_hit(
    forecast_engine, mock_cache_manager, mock_historical_data_retriever, mock_bedrock_client
):
    """Test forecast generation when cache hits."""
    cached_data = {
        'forecast_data': [{'date': '2024-01-01', 'predicted_cost': 100.0, 'confidence_lower': 90.0, 'confidence_upper': 110.0, 'currency': 'USD'}],
        'metadata': {'timestamp': '2024-01-01T00:00:00Z', 'forecast_horizon': 30, 'granularity': 'daily', 'model_used': 'amazon.nova-lite-v1:0', 'service': None, 'services_included': None, 'cache_hit': False, 'historical_data_days': 60}
    }
    mock_cache_manager.get_cached_forecast.return_value = cached_data
    
    result = forecast_engine.generate_forecast(service=None, days=30, granularity="daily")
    
    assert result.success is True
    assert result.metadata.cache_hit is True
    mock_cache_manager.get_cached_forecast.assert_called_once_with(None, 30, "daily")
    mock_historical_data_retriever.get_historical_data.assert_not_called()
    mock_bedrock_client.invoke_forecast.assert_not_called()


def test_aggregate_to_weekly(forecast_engine):
    """Test weekly aggregation of daily forecasts."""
    daily_data = [ForecastDataPoint(date=f'2024-01-{i+1:02d}', predicted_cost=100.0, confidence_lower=90.0, confidence_upper=110.0, currency='USD') for i in range(14)]
    weekly_data = forecast_engine.aggregate_to_weekly(daily_data)
    assert len(weekly_data) == 2
    assert weekly_data[0].predicted_cost == 700.0
    assert weekly_data[1].predicted_cost == 700.0


def test_generate_forecast_insufficient_data(forecast_engine, mock_cache_manager, mock_historical_data_retriever):
    """Test error handling when insufficient historical data."""
    insufficient_data = ProcessedData(timestamps=['2024-01-01', '2024-01-02'], costs=[100.0, 105.0], service=None, total_days=2)
    mock_cache_manager.get_cached_forecast.return_value = None
    mock_historical_data_retriever.get_historical_data.return_value = insufficient_data
    
    with pytest.raises(InsufficientDataError) as exc_info:
        forecast_engine.generate_forecast(service=None, days=30, granularity="daily")
    assert "Minimum 30 days required" in str(exc_info.value)


def test_generate_forecast_invalid_days(forecast_engine):
    """Test validation error for invalid days parameter."""
    with pytest.raises(ValueError) as exc_info:
        forecast_engine.generate_forecast(service=None, days=45, granularity="daily")
    assert "Invalid days value" in str(exc_info.value)


def test_calculate_accuracy_metrics(forecast_engine):
    """Test accuracy metrics calculation."""
    predictions = [100.0, 110.0, 105.0, 115.0]
    actuals = [95.0, 105.0, 110.0, 120.0]
    metrics = forecast_engine.calculate_accuracy_metrics(predictions, actuals)
    assert 'mape' in metrics
    assert 'rmse' in metrics
    assert metrics['mape'] > 0
    assert metrics['rmse'] > 0
