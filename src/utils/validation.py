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
