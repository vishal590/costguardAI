"""
Unit tests for Phase 2 AI Cost Forecasting data models.

Tests dataclass creation, validation, and type conversions for:
- ForecastDataPoint
- ForecastMetadata
- ForecastResponse
- CachedForecast
- ProcessedData
- BedrockRequest
- BedrockResponse
- Custom exceptions
"""

import pytest
from datetime import datetime, UTC
from src.utils.types import (
    ForecastDataPoint,
    ForecastMetadata,
    ForecastResponse,
    CachedForecast,
    ProcessedData,
    BedrockRequest,
    BedrockResponse,
    InsufficientDataError,
    BedrockAPIError,
    BedrockRateLimitError,
    BedrockInvalidResponseError
)


class TestForecastDataPoint:
    """Tests for ForecastDataPoint dataclass."""
    
    def test_create_forecast_data_point(self):
        """Test creating a forecast data point with all fields."""
        point = ForecastDataPoint(
            date="2026-03-01",
            predicted_cost=10.50,
            confidence_lower=9.00,
            confidence_upper=12.00,
            currency="USD"
        )
        
        assert point.date == "2026-03-01"
        assert point.predicted_cost == 10.50
        assert point.confidence_lower == 9.00
        assert point.confidence_upper == 12.00
        assert point.currency == "USD"
    
    def test_forecast_data_point_default_currency(self):
        """Test that currency defaults to USD."""
        point = ForecastDataPoint(
            date="2026-03-01",
            predicted_cost=10.50,
            confidence_lower=9.00,
            confidence_upper=12.00
        )
        
        assert point.currency == "USD"
    
    def test_forecast_data_point_with_zero_cost(self):
        """Test forecast data point with zero cost."""
        point = ForecastDataPoint(
            date="2026-03-01",
            predicted_cost=0.0,
            confidence_lower=0.0,
            confidence_upper=0.0
        )
        
        assert point.predicted_cost == 0.0
        assert point.confidence_lower == 0.0
        assert point.confidence_upper == 0.0


class TestForecastMetadata:
    """Tests for ForecastMetadata dataclass."""
    
    def test_create_forecast_metadata_service_specific(self):
        """Test creating metadata for service-specific forecast."""
        metadata = ForecastMetadata(
            timestamp="2026-02-21T10:30:00Z",
            forecast_horizon=30,
            granularity="daily",
            model_used="amazon.nova-lite-v1:0",
            service="ec2",
            services_included=None,
            cache_hit=False,
            historical_data_days=90
        )
        
        assert metadata.timestamp == "2026-02-21T10:30:00Z"
        assert metadata.forecast_horizon == 30
        assert metadata.granularity == "daily"
        assert metadata.model_used == "amazon.nova-lite-v1:0"
        assert metadata.service == "ec2"
        assert metadata.services_included is None
        assert metadata.cache_hit is False
        assert metadata.historical_data_days == 90
    
    def test_create_forecast_metadata_total(self):
        """Test creating metadata for total forecast."""
        metadata = ForecastMetadata(
            timestamp="2026-02-21T10:30:00Z",
            forecast_horizon=30,
            granularity="daily",
            model_used="amazon.nova-lite-v1:0",
            service=None,
            services_included=["ec2", "lambda", "s3"],
            cache_hit=True,
            historical_data_days=90
        )
        
        assert metadata.service is None
        assert metadata.services_included == ["ec2", "lambda", "s3"]
        assert metadata.cache_hit is True


class TestForecastResponse:
    """Tests for ForecastResponse dataclass."""
    
    def test_create_forecast_response(self):
        """Test creating a complete forecast response."""
        data_points = [
            ForecastDataPoint(
                date="2026-03-01",
                predicted_cost=10.50,
                confidence_lower=9.00,
                confidence_upper=12.00
            ),
            ForecastDataPoint(
                date="2026-03-02",
                predicted_cost=11.00,
                confidence_lower=9.50,
                confidence_upper=12.50
            )
        ]
        
        metadata = ForecastMetadata(
            timestamp="2026-02-21T10:30:00Z",
            forecast_horizon=2,
            granularity="daily",
            model_used="amazon.nova-lite-v1:0",
            service="ec2",
            services_included=None,
            cache_hit=False,
            historical_data_days=90
        )
        
        response = ForecastResponse(
            success=True,
            forecast_data=data_points,
            metadata=metadata
        )
        
        assert response.success is True
        assert len(response.forecast_data) == 2
        assert response.forecast_data[0].date == "2026-03-01"
        assert response.metadata.forecast_horizon == 2
    
    def test_create_error_forecast_response(self):
        """Test creating an error forecast response."""
        response = ForecastResponse(
            success=False,
            forecast_data=[],
            metadata=ForecastMetadata(
                timestamp="2026-02-21T10:30:00Z",
                forecast_horizon=0,
                granularity="daily",
                model_used="",
                service=None,
                services_included=None,
                cache_hit=False,
                historical_data_days=0
            )
        )
        
        assert response.success is False
        assert len(response.forecast_data) == 0


class TestCachedForecast:
    """Tests for CachedForecast dataclass."""
    
    def test_create_cached_forecast(self):
        """Test creating a cached forecast."""
        forecast_response = ForecastResponse(
            success=True,
            forecast_data=[],
            metadata=ForecastMetadata(
                timestamp="2026-02-21T10:30:00Z",
                forecast_horizon=30,
                granularity="daily",
                model_used="amazon.nova-lite-v1:0",
                service="ec2",
                services_included=None,
                cache_hit=False,
                historical_data_days=90
            )
        )
        
        now = datetime.now(UTC)
        ttl = int(now.timestamp()) + 86400  # 24 hours
        
        cached = CachedForecast(
            cache_key="ec2_30_daily",
            forecast_response=forecast_response,
            created_at=now,
            ttl=ttl
        )
        
        assert cached.cache_key == "ec2_30_daily"
        assert cached.forecast_response.success is True
        assert cached.created_at == now
        assert cached.ttl == ttl


class TestProcessedData:
    """Tests for ProcessedData dataclass."""
    
    def test_create_processed_data(self):
        """Test creating processed historical data."""
        data = ProcessedData(
            timestamps=["2026-01-01", "2026-01-02", "2026-01-03"],
            costs=[10.0, 11.0, 12.0],
            service="ec2",
            total_days=3
        )
        
        assert len(data.timestamps) == 3
        assert len(data.costs) == 3
        assert data.service == "ec2"
        assert data.total_days == 3
    
    def test_create_processed_data_total(self):
        """Test creating processed data for total forecast."""
        data = ProcessedData(
            timestamps=["2026-01-01", "2026-01-02"],
            costs=[50.0, 55.0],
            service=None,
            total_days=2
        )
        
        assert data.service is None
        assert data.total_days == 2


class TestBedrockRequest:
    """Tests for BedrockRequest dataclass."""
    
    def test_create_bedrock_request(self):
        """Test creating a Bedrock API request."""
        processed_data = ProcessedData(
            timestamps=["2026-01-01", "2026-01-02"],
            costs=[10.0, 11.0],
            service="ec2",
            total_days=2
        )
        
        request = BedrockRequest(
            historical_data=processed_data,
            forecast_horizon=30,
            confidence_level=0.95
        )
        
        assert request.historical_data.service == "ec2"
        assert request.forecast_horizon == 30
        assert request.confidence_level == 0.95
    
    def test_bedrock_request_default_confidence(self):
        """Test that confidence level defaults to 0.95."""
        processed_data = ProcessedData(
            timestamps=["2026-01-01"],
            costs=[10.0],
            service="ec2",
            total_days=1
        )
        
        request = BedrockRequest(
            historical_data=processed_data,
            forecast_horizon=30
        )
        
        assert request.confidence_level == 0.95


class TestBedrockResponse:
    """Tests for BedrockResponse dataclass."""
    
    def test_create_bedrock_response(self):
        """Test creating a Bedrock API response."""
        response = BedrockResponse(
            predictions=[10.0, 11.0, 12.0],
            confidence_lower=[9.0, 10.0, 11.0],
            confidence_upper=[11.0, 12.0, 13.0],
            dates=["2026-03-01", "2026-03-02", "2026-03-03"],
            model_id="amazon.nova-lite-v1:0",
            latency_ms=1500
        )
        
        assert len(response.predictions) == 3
        assert len(response.confidence_lower) == 3
        assert len(response.confidence_upper) == 3
        assert len(response.dates) == 3
        assert response.model_id == "amazon.nova-lite-v1:0"
        assert response.latency_ms == 1500


class TestCustomExceptions:
    """Tests for Phase 2 custom exceptions."""
    
    def test_insufficient_data_error(self):
        """Test InsufficientDataError can be raised and caught."""
        with pytest.raises(InsufficientDataError) as exc_info:
            raise InsufficientDataError("Need at least 30 days of data")
        
        assert "30 days" in str(exc_info.value)
    
    def test_bedrock_api_error(self):
        """Test BedrockAPIError can be raised and caught."""
        with pytest.raises(BedrockAPIError) as exc_info:
            raise BedrockAPIError("Bedrock API call failed")
        
        assert "failed" in str(exc_info.value)
    
    def test_bedrock_rate_limit_error(self):
        """Test BedrockRateLimitError can be raised and caught."""
        with pytest.raises(BedrockRateLimitError) as exc_info:
            raise BedrockRateLimitError("Rate limit exceeded")
        
        assert "Rate limit" in str(exc_info.value)
    
    def test_bedrock_invalid_response_error(self):
        """Test BedrockInvalidResponseError can be raised and caught."""
        with pytest.raises(BedrockInvalidResponseError) as exc_info:
            raise BedrockInvalidResponseError("Invalid JSON response")
        
        assert "Invalid JSON" in str(exc_info.value)
    
    def test_exceptions_are_distinct(self):
        """Test that custom exceptions are distinct types."""
        assert InsufficientDataError != BedrockAPIError
        assert BedrockAPIError != BedrockRateLimitError
        assert BedrockRateLimitError != BedrockInvalidResponseError
