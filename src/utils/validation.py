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
