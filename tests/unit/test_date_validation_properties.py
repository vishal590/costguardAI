"""
Property-based tests for date validation utilities.

Feature: cost-data-pipeline
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta

from src.utils.date_utils import (
    validate_date_format,
    validate_date_range
)


# Feature: cost-data-pipeline, Property 1: Date validation rejects invalid formats
@given(st.text())
@settings(max_examples=100)
def test_date_validation_rejects_invalid_formats(input_str):
    """
    Property 1: Date validation rejects invalid formats
    For any string input, if it does not match the YYYY-MM-DD format,
    then the validation function should return false.
    
    Validates: Requirements 2.1, 2.2
    """
    result = validate_date_format(input_str)
    
    # If the result is True, the string must match YYYY-MM-DD format
    if result:
        # Must match the pattern
        assert len(input_str) == 10
        assert input_str[4] == '-'
        assert input_str[7] == '-'
        # Must be a valid date
        try:
            datetime.strptime(input_str, '%Y-%m-%d')
        except ValueError:
            pytest.fail(f"validate_date_format returned True for invalid date: {input_str}")


# Feature: cost-data-pipeline, Property 2: Date range validation rejects invalid ranges
@given(
    st.dates(min_value=datetime(2000, 1, 1).date(), max_value=datetime(2099, 12, 31).date()),
    st.dates(min_value=datetime(2000, 1, 1).date(), max_value=datetime(2099, 12, 31).date())
)
@settings(max_examples=100)
def test_date_range_validation_rejects_invalid_ranges(date1, date2):
    """
    Property 2: Date range validation rejects invalid ranges
    For any pair of valid dates, if the start date is after the end date,
    then the validation function should return false.
    
    Validates: Requirements 2.3
    """
    start_str = date1.strftime('%Y-%m-%d')
    end_str = date2.strftime('%Y-%m-%d')
    
    result = validate_date_range(start_str, end_str)
    
    # If start is after end, result must be False
    if date1 > date2:
        assert result is False, f"Expected False for start={start_str} > end={end_str}"
    # If start is before or equal to end, result must be True
    else:
        assert result is True, f"Expected True for start={start_str} <= end={end_str}"
