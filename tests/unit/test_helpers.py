"""
Unit tests for helper utilities.
"""
import pytest
from datetime import datetime, timedelta
from src.utils.helpers import (
    calculate_ttl,
    normalize_service_name,
    calculate_cost_summary
)
from src.utils.types import CostRecord


class TestCalculateTTL:
    """Tests for calculate_ttl function."""
    
    def test_calculate_ttl_with_positive_days(self):
        """Test TTL calculation with positive days."""
        days = 365
        result = calculate_ttl(days)
        
        # Verify it's a Unix timestamp (integer)
        assert isinstance(result, int)
        
        # Verify it's approximately 365 days from now (within 1 second tolerance)
        expected = int((datetime.now() + timedelta(days=days)).timestamp())
        assert abs(result - expected) <= 1
    
    def test_calculate_ttl_with_zero_days(self):
        """Test TTL calculation with zero days."""
        result = calculate_ttl(0)
        
        # Should be approximately now
        expected = int(datetime.now().timestamp())
        assert abs(result - expected) <= 1
    
    def test_calculate_ttl_with_various_day_values(self):
        """Test TTL calculation with various day values."""
        test_cases = [1, 7, 30, 90, 365]
        
        for days in test_cases:
            result = calculate_ttl(days)
            expected = int((datetime.now() + timedelta(days=days)).timestamp())
            assert abs(result - expected) <= 1, f"Failed for {days} days"


class TestNormalizeServiceName:
    """Tests for normalize_service_name function."""
    
    def test_normalize_service_name_with_spaces(self):
        """Test normalization with spaces."""
        service = "Amazon Elastic Compute Cloud"
        result = normalize_service_name(service)
        assert result == "amazon-elastic-compute-cloud"
    
    def test_normalize_service_name_with_uppercase(self):
        """Test normalization with uppercase letters."""
        service = "AWS Lambda"
        result = normalize_service_name(service)
        assert result == "aws-lambda"
    
    def test_normalize_service_name_already_normalized(self):
        """Test normalization with already normalized name."""
        service = "s3"
        result = normalize_service_name(service)
        assert result == "s3"
    
    def test_normalize_service_name_with_various_names(self):
        """Test normalization with various service names."""
        test_cases = [
            ("Amazon S3", "amazon-s3"),
            ("Amazon DynamoDB", "amazon-dynamodb"),
            ("AWS Cost Explorer", "aws-cost-explorer"),
            ("EC2 Container Service", "ec2-container-service"),
        ]
        
        for service, expected in test_cases:
            result = normalize_service_name(service)
            assert result == expected, f"Failed for {service}"


class TestCalculateCostSummary:
    """Tests for calculate_cost_summary function."""
    
    def test_calculate_cost_summary_with_empty_list(self):
        """Test summary calculation with empty list."""
        result = calculate_cost_summary([])
        
        assert result['totalCost'] == 0.0
        assert result['serviceCount'] == 0
        assert result['recordCount'] == 0
    
    def test_calculate_cost_summary_with_single_record(self):
        """Test summary calculation with single record."""
        records = [
            CostRecord(
                date="2025-01-01",
                service="EC2",
                blended_cost=100.50,
                unblended_cost=100.50,
                currency="USD",
                unit="USD"
            )
        ]
        
        result = calculate_cost_summary(records)
        
        assert result['totalCost'] == 100.50
        assert result['serviceCount'] == 1
        assert result['recordCount'] == 1
    
    def test_calculate_cost_summary_with_multiple_records_same_service(self):
        """Test summary calculation with multiple records from same service."""
        records = [
            CostRecord(
                date="2025-01-01",
                service="EC2",
                blended_cost=100.00,
                unblended_cost=100.00,
                currency="USD",
                unit="USD"
            ),
            CostRecord(
                date="2025-01-02",
                service="EC2",
                blended_cost=150.00,
                unblended_cost=150.00,
                currency="USD",
                unit="USD"
            )
        ]
        
        result = calculate_cost_summary(records)
        
        assert result['totalCost'] == 250.00
        assert result['serviceCount'] == 1  # Same service
        assert result['recordCount'] == 2
    
    def test_calculate_cost_summary_with_multiple_services(self):
        """Test summary calculation with multiple services."""
        records = [
            CostRecord(
                date="2025-01-01",
                service="EC2",
                blended_cost=100.00,
                unblended_cost=100.00,
                currency="USD",
                unit="USD"
            ),
            CostRecord(
                date="2025-01-01",
                service="S3",
                blended_cost=50.00,
                unblended_cost=50.00,
                currency="USD",
                unit="USD"
            ),
            CostRecord(
                date="2025-01-01",
                service="Lambda",
                blended_cost=25.50,
                unblended_cost=25.50,
                currency="USD",
                unit="USD"
            )
        ]
        
        result = calculate_cost_summary(records)
        
        assert result['totalCost'] == 175.50
        assert result['serviceCount'] == 3
        assert result['recordCount'] == 3
    
    def test_calculate_cost_summary_with_various_datasets(self):
        """Test summary calculation with various cost datasets."""
        # Dataset with decimal precision
        records = [
            CostRecord(
                date="2025-01-01",
                service="EC2",
                blended_cost=123.456,
                unblended_cost=123.456,
                currency="USD",
                unit="USD"
            ),
            CostRecord(
                date="2025-01-01",
                service="S3",
                blended_cost=78.901,
                unblended_cost=78.901,
                currency="USD",
                unit="USD"
            )
        ]
        
        result = calculate_cost_summary(records)
        
        # Should round to 2 decimal places
        assert result['totalCost'] == 202.36
        assert result['serviceCount'] == 2
        assert result['recordCount'] == 2
