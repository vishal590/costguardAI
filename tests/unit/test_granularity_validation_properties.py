"""
Property-based tests for granularity validation.

Feature: cost-data-pipeline
"""
import pytest
from hypothesis import given, strategies as st, settings

from src.utils.validation import validate_granularity, VALID_GRANULARITIES


# Feature: cost-data-pipeline, Property 3: Granularity validation accepts only valid values
@given(st.text())
@settings(max_examples=100)
def test_granularity_validation_accepts_only_valid_values(input_str):
    """
    Property 3: Granularity validation accepts only valid values
    For any string input, the validation function should return true only if
    the input is exactly "DAILY", "MONTHLY", or "HOURLY".
    
    Validates: Requirements 2.4, 2.5
    """
    result = validate_granularity(input_str)
    
    # Result should be True only if input is in the valid set
    if input_str in VALID_GRANULARITIES:
        assert result is True, f"Expected True for valid granularity: {input_str}"
    else:
        assert result is False, f"Expected False for invalid granularity: {input_str}"
