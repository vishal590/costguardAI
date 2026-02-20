"""
Unit tests for validation utilities.
"""
import pytest

from src.utils.validation import (
    validate_granularity,
    validate_service_name,
    validate_metric_value,
    validate_pricing_value,
    validate_time_range
)


class TestValidateGranularity:
    """Test validate_granularity function."""
    
    def test_validate_granularity_accepts_daily(self):
        """Test that DAILY is valid."""
        assert validate_granularity('DAILY') is True
    
    def test_validate_granularity_accepts_monthly(self):
        """Test that MONTHLY is valid."""
        assert validate_granularity('MONTHLY') is True
    
    def test_validate_granularity_accepts_hourly(self):
        """Test that HOURLY is valid."""
        assert validate_granularity('HOURLY') is True
    
    def test_validate_granularity_rejects_invalid(self):
        """Test that invalid granularity is rejected."""
        assert validate_granularity('WEEKLY') is False
        assert validate_granularity('yearly') is False
        assert validate_granularity('') is False


class TestValidateServiceName:
    """Test validate_service_name function."""
    
    def test_validate_service_name_accepts_ec2(self):
        """Test that ec2 is valid."""
        assert validate_service_name('ec2') is True
    
    def test_validate_service_name_accepts_lambda(self):
        """Test that lambda is valid."""
        assert validate_service_name('lambda') is True
    
    def test_validate_service_name_accepts_dynamodb(self):
        """Test that dynamodb is valid."""
        assert validate_service_name('dynamodb') is True
    
    def test_validate_service_name_accepts_s3(self):
        """Test that s3 is valid."""
        assert validate_service_name('s3') is True
    
    def test_validate_service_name_accepts_rds(self):
        """Test that rds is valid."""
        assert validate_service_name('rds') is True
    
    def test_validate_service_name_case_insensitive(self):
        """Test that service name validation is case insensitive."""
        assert validate_service_name('EC2') is True
        assert validate_service_name('Lambda') is True
        assert validate_service_name('DynamoDB') is True
    
    def test_validate_service_name_rejects_invalid(self):
        """Test that invalid service names are rejected."""
        assert validate_service_name('sqs') is False
        assert validate_service_name('sns') is False
        assert validate_service_name('') is False
        assert validate_service_name('invalid') is False


class TestValidateMetricValue:
    """Test validate_metric_value function."""
    
    def test_validate_metric_value_accepts_positive(self):
        """Test that positive values are valid."""
        assert validate_metric_value(1.0) is True
        assert validate_metric_value(100.5) is True
        assert validate_metric_value(0.001) is True
    
    def test_validate_metric_value_accepts_zero(self):
        """Test that zero is valid."""
        assert validate_metric_value(0.0) is True
        assert validate_metric_value(0) is True
    
    def test_validate_metric_value_rejects_negative(self):
        """Test that negative values are rejected."""
        assert validate_metric_value(-1.0) is False
        assert validate_metric_value(-0.001) is False
        assert validate_metric_value(-100) is False


class TestValidatePricingValue:
    """Test validate_pricing_value function."""
    
    def test_validate_pricing_value_accepts_positive(self):
        """Test that positive values are valid."""
        assert validate_pricing_value(0.001) is True
        assert validate_pricing_value(1.0) is True
        assert validate_pricing_value(100.5) is True
    
    def test_validate_pricing_value_rejects_zero(self):
        """Test that zero is rejected."""
        assert validate_pricing_value(0.0) is False
        assert validate_pricing_value(0) is False
    
    def test_validate_pricing_value_rejects_negative(self):
        """Test that negative values are rejected."""
        assert validate_pricing_value(-1.0) is False
        assert validate_pricing_value(-0.001) is False


class TestValidateTimeRange:
    """Test validate_time_range function."""
    
    def test_validate_time_range_accepts_valid_range(self):
        """Test that valid time ranges are accepted."""
        assert validate_time_range('2024-01-01T00:00:00Z', '2024-01-02T00:00:00Z') is True
        assert validate_time_range('2024-01-01T00:00:00+00:00', '2024-01-01T01:00:00+00:00') is True
    
    def test_validate_time_range_rejects_invalid_range(self):
        """Test that invalid time ranges are rejected (end before start)."""
        assert validate_time_range('2024-01-02T00:00:00Z', '2024-01-01T00:00:00Z') is False
    
    def test_validate_time_range_rejects_equal_times(self):
        """Test that equal start and end times are rejected."""
        assert validate_time_range('2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z') is False
    
    def test_validate_time_range_rejects_invalid_format(self):
        """Test that invalid time formats are rejected."""
        assert validate_time_range('invalid', '2024-01-01T00:00:00Z') is False
        assert validate_time_range('2024-01-01T00:00:00Z', 'invalid') is False
        assert validate_time_range('invalid', 'invalid') is False
    
    def test_validate_time_range_handles_none_values(self):
        """Test that None values are handled gracefully."""
        assert validate_time_range(None, '2024-01-01T00:00:00Z') is False
        assert validate_time_range('2024-01-01T00:00:00Z', None) is False
