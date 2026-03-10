"""
Forecast Engine for AI-powered cost forecasting.

This module orchestrates the forecast generation process by:
1. Retrieving historical cost data
2. Validating and preprocessing data
3. Calling Bedrock for AI predictions
4. Managing forecast cache
5. Returning formatted forecast responses
"""

from dataclasses import asdict
from typing import Optional, List, Dict
from datetime import datetime, timedelta, UTC
from src.utils.types import (
    ForecastResponse,
    ForecastDataPoint,
    ForecastMetadata,
    ProcessedData,
    InsufficientDataError,
    BedrockAPIError,
    BedrockRateLimitError
)


class ForecastEngine:
    """Main orchestrator for forecast generation."""
    
    def __init__(self, bedrock_client, historical_data_retriever, cache_manager):
        """
        Initialize forecast engine with dependencies.
        
        Args:
            bedrock_client: BedrockClient instance
            historical_data_retriever: HistoricalDataRetriever instance
            cache_manager: ForecastCacheManager instance
        """
        self.bedrock_client = bedrock_client
        self.historical_data_retriever = historical_data_retriever
        self.cache_manager = cache_manager
        
    def generate_forecast(
        self,
        service: Optional[str] = None,
        days: int = 30,
        granularity: str = "daily"
    ) -> ForecastResponse:
        """
        Generate cost forecast for specified parameters.
        
        Args:
            service: Service name (None for total forecast)
            days: Forecast horizon (7, 14, or 30)
            granularity: Time resolution ("daily" or "weekly")
            
        Returns:
            ForecastResponse with predictions and metadata
            
        Raises:
            InsufficientDataError: Less than 30 days of historical data
            BedrockAPIError: Bedrock API failure
            ValidationError: Invalid parameters
        """
        # Validate parameters
        self._validate_parameters(days, granularity)
        
        # Check cache first
        cached_forecast = self.cache_manager.get_cached_forecast(service, days, granularity)
        if cached_forecast:
            # Return cached forecast with cache_hit=True
            return self._deserialize_cached_forecast(cached_forecast, cache_hit=True)
        
        # Retrieve historical data (30 days to keep prompt smaller and complete within API Gateway 29s; cache helps repeat requests)
        historical_data = self.historical_data_retriever.get_historical_data(
            service=service,
            days_back=30
        )
        
        # Validate historical data (minimum days)
        self.validate_historical_data(historical_data)
        
        # If all costs are zero, return a zero forecast (no Bedrock call)
        if all(cost == 0.0 for cost in historical_data.costs):
            forecast_data = self._build_zero_forecast(days, granularity, historical_data)
            metadata = ForecastMetadata(
                timestamp=datetime.now(UTC).isoformat(),
                forecast_horizon=days,
                granularity=granularity,
                model_used="zero-forecast",
                service=service,
                services_included=None if service else self._get_all_services(historical_data),
                cache_hit=False,
                historical_data_days=historical_data.total_days
            )
            forecast_dict = {
                'success': True,
                'forecast_data': [asdict(p) for p in forecast_data],
                'metadata': asdict(metadata),
            }
            self.cache_manager.store_forecast(forecast_dict, service, days, granularity)
            return ForecastResponse(success=True, forecast_data=forecast_data, metadata=metadata)
        
        # Call Bedrock for predictions
        bedrock_response = self.bedrock_client.invoke_forecast(
            historical_data=historical_data,
            forecast_horizon=days,
            confidence_level=0.95
        )
        
        # Build forecast data points
        forecast_data = []
        for i in range(len(bedrock_response.predictions)):
            forecast_data.append(ForecastDataPoint(
                date=bedrock_response.dates[i],
                predicted_cost=bedrock_response.predictions[i],
                confidence_lower=bedrock_response.confidence_lower[i],
                confidence_upper=bedrock_response.confidence_upper[i],
                currency="USD"
            ))
        
        # Apply weekly aggregation if requested
        if granularity == "weekly":
            forecast_data = self.aggregate_to_weekly(forecast_data)
        
        # Build metadata
        metadata = ForecastMetadata(
            timestamp=datetime.now(UTC).isoformat(),
            forecast_horizon=days,
            granularity=granularity,
            model_used=bedrock_response.model_id,
            service=service,
            services_included=None if service else self._get_all_services(historical_data),
            cache_hit=False,
            historical_data_days=historical_data.total_days
        )
        
        # Build response
        forecast_response = ForecastResponse(
            success=True,
            forecast_data=forecast_data,
            metadata=metadata
        )
        
        # Store in cache (must pass a JSON-serializable dict; dataclasses are not serializable by default)
        forecast_dict = {
            'success': forecast_response.success,
            'forecast_data': [asdict(p) for p in forecast_response.forecast_data],
            'metadata': asdict(forecast_response.metadata),
        }
        self.cache_manager.store_forecast(forecast_dict, service, days, granularity)
        
        return forecast_response
        
    def validate_historical_data(self, data: ProcessedData) -> bool:
        """
        Validate historical data completeness and quality.
        
        Args:
            data: ProcessedData to validate
            
        Returns:
            True if valid
            
        Raises:
            InsufficientDataError: Data doesn't meet requirements
        """
        # Check minimum 7 days (allow 7-day forecast with limited history)
        if data.total_days < 7:
            raise InsufficientDataError(
                f"Insufficient historical data. Minimum 7 days required, found {data.total_days} days."
            )
        
        # All-zero costs are handled in generate_forecast (return zero forecast); no need to raise here
        return True
        
    def aggregate_to_weekly(self, daily_data: List[ForecastDataPoint]) -> List[ForecastDataPoint]:
        """
        Aggregate daily predictions into weekly totals.
        
        Args:
            daily_data: List of daily forecast data points
            
        Returns:
            List of weekly forecast data points
        """
        if not daily_data:
            return []
        
        weekly_data = []
        current_week = []
        week_start_date = None
        
        for point in daily_data:
            if not current_week:
                week_start_date = point.date
            
            current_week.append(point)
            
            # Check if we've completed a week (7 days) or reached the end
            if len(current_week) == 7 or point == daily_data[-1]:
                # Aggregate the week
                weekly_point = ForecastDataPoint(
                    date=week_start_date,
                    predicted_cost=sum(p.predicted_cost for p in current_week),
                    confidence_lower=sum(p.confidence_lower for p in current_week),
                    confidence_upper=sum(p.confidence_upper for p in current_week),
                    currency="USD"
                )
                weekly_data.append(weekly_point)
                current_week = []
        
        return weekly_data
        
    def calculate_accuracy_metrics(
        self,
        predictions: List[float],
        actuals: List[float]
    ) -> Dict[str, float]:
        """
        Calculate accuracy metrics (MAPE and RMSE) for backtesting.
        
        Args:
            predictions: Predicted costs
            actuals: Actual costs
            
        Returns:
            Dict with 'mape' and 'rmse' keys
        """
        if len(predictions) != len(actuals) or len(predictions) == 0:
            raise ValueError("Predictions and actuals must have same non-zero length")
        
        # Calculate MAPE (Mean Absolute Percentage Error)
        mape_sum = 0.0
        valid_points = 0
        for pred, actual in zip(predictions, actuals):
            if actual != 0:  # Avoid division by zero
                mape_sum += abs((actual - pred) / actual)
                valid_points += 1
        
        mape = (mape_sum / valid_points * 100) if valid_points > 0 else 0.0
        
        # Calculate RMSE (Root Mean Squared Error)
        squared_errors = [(pred - actual) ** 2 for pred, actual in zip(predictions, actuals)]
        mse = sum(squared_errors) / len(squared_errors)
        rmse = mse ** 0.5
        
        return {
            'mape': mape,
            'rmse': rmse
        }
        
    def _build_zero_forecast(
        self, days: int, granularity: str, historical_data: ProcessedData
    ) -> List[ForecastDataPoint]:
        """Build a forecast of zeros when historical data is all zero (no Bedrock call)."""
        if not historical_data.timestamps:
            start = datetime.now(UTC).date()
        else:
            last_str = historical_data.timestamps[-1]
            last_date = datetime.strptime(last_str, "%Y-%m-%d").date()
            start = last_date + timedelta(days=1)
        daily_data = []
        for i in range(days):
            d = start + timedelta(days=i)
            daily_data.append(ForecastDataPoint(
                date=d.strftime("%Y-%m-%d"),
                predicted_cost=0.0,
                confidence_lower=0.0,
                confidence_upper=0.0,
                currency="USD"
            ))
        if granularity == "weekly":
            return self.aggregate_to_weekly(daily_data)
        return daily_data

    def _validate_parameters(self, days: int, granularity: str) -> None:
        """Validate forecast parameters."""
        if days not in [7, 14, 30]:
            raise ValueError(f"Invalid days value. Must be 7, 14, or 30. Got: {days}")
        
        if granularity not in ["daily", "weekly"]:
            raise ValueError(f"Invalid granularity. Must be 'daily' or 'weekly'. Got: {granularity}")
    
    def _get_all_services(self, data: ProcessedData) -> Optional[List[str]]:
        """Extract list of services from historical data (for total forecasts)."""
        # For now, return None as we don't track individual services in ProcessedData
        # This would be enhanced in future to track which services were aggregated
        return None
    
    def _deserialize_cached_forecast(self, cached_data: Dict, cache_hit: bool) -> ForecastResponse:
        """
        Deserialize cached forecast data into ForecastResponse.
        
        Args:
            cached_data: Cached forecast dictionary
            cache_hit: Whether this was a cache hit
            
        Returns:
            ForecastResponse object
        """
        # Extract forecast data
        forecast_data = []
        for point_data in cached_data['forecast_data']:
            forecast_data.append(ForecastDataPoint(
                date=point_data['date'],
                predicted_cost=point_data['predicted_cost'],
                confidence_lower=point_data['confidence_lower'],
                confidence_upper=point_data['confidence_upper'],
                currency=point_data.get('currency', 'USD')
            ))
        
        # Extract metadata
        metadata_data = cached_data['metadata']
        metadata = ForecastMetadata(
            timestamp=metadata_data['timestamp'],
            forecast_horizon=metadata_data['forecast_horizon'],
            granularity=metadata_data['granularity'],
            model_used=metadata_data['model_used'],
            service=metadata_data.get('service'),
            services_included=metadata_data.get('services_included'),
            cache_hit=cache_hit,  # Override with actual cache hit status
            historical_data_days=metadata_data['historical_data_days']
        )
        
        return ForecastResponse(
            success=True,
            forecast_data=forecast_data,
            metadata=metadata
        )
