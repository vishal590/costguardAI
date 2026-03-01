"""
Date validation and formatting utilities.
"""
import re
from datetime import datetime, date, timedelta
from typing import Tuple


def validate_date_format(date_str: str) -> bool:
    """
    Validate date matches YYYY-MM-DD format.
    
    Args:
        date_str: Date string to validate
        
    Returns:
        True if valid format, False otherwise
    """
    pattern = r'^\d{4}-\d{2}-\d{2}$'
    if not re.match(pattern, date_str):
        return False
    
    # Also validate it's a real date
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def validate_date_range(start_date: str, end_date: str) -> bool:
    """
    Validate start date is before or equal to end date.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        True if valid range, False otherwise
    """
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        return start <= end
    except ValueError:
        return False


def format_date_for_api(dt: date) -> str:
    """
    Format date as YYYY-MM-DD.
    
    Args:
        dt: Date object
        
    Returns:
        Date string in YYYY-MM-DD format
    """
    return dt.strftime('%Y-%m-%d')


def calculate_default_date_range() -> Tuple[str, str]:
    """
    Calculate 12 months ago to today.
    
    Returns:
        Tuple of (start_date, end_date) in YYYY-MM-DD format
    """
    today = date.today()
    twelve_months_ago = today - timedelta(days=365)
    return (format_date_for_api(twelve_months_ago), format_date_for_api(today))
