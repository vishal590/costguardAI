"""
Validation utilities for input parameters.
"""
from typing import Set

# Valid granularity values
VALID_GRANULARITIES: Set[str] = {'DAILY', 'MONTHLY', 'HOURLY'}


def validate_granularity(granularity: str) -> bool:
    """
    Validate granularity is DAILY, MONTHLY, or HOURLY.
    
    Args:
        granularity: Granularity value to validate
        
    Returns:
        True if valid, False otherwise
    """
    return granularity in VALID_GRANULARITIES


# ============================================================================
# Phase 1.5 Validation Functions
# ============================================================================

# Valid service names for Phase 1.5
VALID_SERVICES: Set[str] = {'ec2', 'lambda', 'dynamodb', 's3', 'rds'}


def validate_service_name(service: str) -> bool:
    """
    Validate service name is one of the supported services.
    
    Args:
        service: Service name to validate
        
    Returns:
        True if valid, False otherwise
    """
    return service.lower() in VALID_SERVICES


def validate_metric_value(value: float) -> bool:
    """
    Validate metric value is non-negative.
    
    Args:
        value: Metric value to validate
        
    Returns:
        True if valid (non-negative), False otherwise
    """
    return value >= 0


def validate_pricing_value(price: float) -> bool:
    """
    Validate pricing value is positive.
    
    Args:
        price: Price value to validate
        
    Returns:
        True if valid (positive), False otherwise
    """
    return price > 0


def validate_time_range(start_time: str, end_time: str) -> bool:
    """
    Validate time range is valid (start before end).
    
    Args:
        start_time: Start time (ISO format string)
        end_time: End time (ISO format string)
        
    Returns:
        True if valid, False otherwise
    """
    try:
        from datetime import datetime
        start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        return start < end
    except (ValueError, AttributeError):
        return False


# ============================================================================
# Phase 2: AI Cost Forecasting Validation Functions
# ============================================================================

# Valid forecast horizons (days)
VALID_FORECAST_DAYS: Set[int] = {7, 14, 30}

# Valid forecast granularities
VALID_FORECAST_GRANULARITIES: Set[str] = {'daily', 'weekly'}


def validate_forecast_days(days: int) -> bool:
    """
    Validate forecast horizon is 7, 14, or 30 days.
    
    Args:
        days: Number of days to forecast
        
    Returns:
        True if valid, False otherwise
    """
    return days in VALID_FORECAST_DAYS


def validate_forecast_granularity(granularity: str) -> bool:
    """
    Validate forecast granularity is 'daily' or 'weekly'.
    
    Args:
        granularity: Granularity value to validate
        
    Returns:
        True if valid, False otherwise
    """
    return granularity.lower() in VALID_FORECAST_GRANULARITIES


def validate_confidence_interval(lower: float, predicted: float, upper: float) -> bool:
    """
    Validate confidence interval bounds are correctly ordered.
    
    Args:
        lower: Lower bound
        predicted: Predicted value
        upper: Upper bound
        
    Returns:
        True if lower <= predicted <= upper, False otherwise
    """
    return lower <= predicted <= upper


def validate_forecast_data_point(data_point: dict) -> bool:
    """
    Validate forecast data point has all required fields.
    
    Args:
        data_point: Dictionary with forecast data
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = {'date', 'predicted_cost', 'confidence_lower', 'confidence_upper', 'currency'}
    return all(field in data_point for field in required_fields)
