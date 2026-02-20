"""
Unit tests for Cost Estimator.
"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal

from src.services.cost_estimator import CostEstimator
from src.utils.types import (
    EC2Metrics,
    LambdaMetrics,
    DynamoDBMetrics,
    S3Metrics,
    RDSMetrics,
    EC2Pricing,
    LambdaPricing,
    DynamoDBPricing,
    S3Pricing,
    RDSPricing,
    CostEstimate,
    PricingData,
    MetricDataPoint
)


class TestCostEstimator:
    """Test CostEstimator initialization."""
    
    def test_init(self):
        """Test initialization."""
        estimator = CostEstimator()
        assert estimator is not None


class TestEstimateEC2Cost:
    """Test EC2 cost estimation."""
    
    def test_estimate_ec2_cost_with_metrics(self):
        """Test EC2 cost estimation with metrics."""
        estimator = CostEstimator()
        
        metrics = [
            EC2Metrics(
                instance_id='i-123',
                instance_type='t2.micro',
                cpu_utilization=Decimal('50'),
                network_in=Decimal('1000'),
                network_out=Decimal('1073741824'),  # 1 GB
                disk_read_bytes=Decimal('1000'),
                running_hours=Decimal('1')
            )
        ]
        
        pricing = EC2Pricing(
            instance_prices={'t2.micro': Decimal('0.0116')},
            data_transfer_out=Decimal('0.09'),
            currency='USD'
        )
        
        cost = estimator.estimate_ec2_cost(metrics, pricing)
        
        # Expected: 1 hour * $0.0116 + 1 GB * $0.09 = $0.1016
        assert cost > Decimal('0')
        assert cost == Decimal('0.0116') + Decimal('0.09')
    
    def test_estimate_ec2_cost_with_empty_metrics(self):
        """Test EC2 cost estimation with no metrics."""
        estimator = CostEstimator()
        
        pricing = EC2Pricing(
            instance_prices={'t2.micro': Decimal('0.0116')},
            data_transfer_out=Decimal('0.09'),
            currency='USD'
        )
        
        cost = estimator.estimate_ec2_cost([], pricing)
        
        assert cost == Decimal('0')
    
    def test_estimate_ec2_cost_uses_default_price_for_unknown_instance(self):
        """Test that default price is used for unknown instance types."""
        estimator = CostEstimator()
        
        metrics = [
            EC2Metrics(
                instance_id='i-123',
                instance_type='unknown.type',
                cpu_utilization=Decimal('50'),
                network_in=Decimal('1000'),
                network_out=Decimal('0'),
                disk_read_bytes=Decimal('1000'),
                running_hours=Decimal('1')
            )
        ]
        
        pricing = EC2Pricing(
            instance_prices={'t2.micro': Decimal('0.0116')},
            data_transfer_out=Decimal('0.09'),
            currency='USD'
        )
        
        cost = estimator.estimate_ec2_cost(metrics, pricing)
        
        # Should use default price
        assert cost == Decimal('0.0116')


class TestEstimateLambdaCost:
    """Test Lambda cost estimation."""
    
    def test_estimate_lambda_cost_with_metrics(self):
        """Test Lambda cost estimation with metrics."""
        estimator = CostEstimator()
        
        metrics = [
            LambdaMetrics(
                function_name='my-function',
                invocations=1000,
                duration_ms=Decimal('250'),
                memory_mb=128,
                errors=0
            )
        ]
        
        pricing = LambdaPricing(
            price_per_request=Decimal('0.0000002'),
            price_per_gb_second=Decimal('0.0000166667'),
            currency='USD'
        )
        
        cost = estimator.estimate_lambda_cost(metrics, pricing)
        
        # Expected: 1000 requests * $0.0000002 + GB-seconds cost
        # GB-seconds = 1000 * 0.25s * (128/1024)GB = 31.25 GB-seconds
        # Cost = $0.0002 + 31.25 * $0.0000166667 ≈ $0.000720835
        assert cost > Decimal('0')
    
    def test_estimate_lambda_cost_with_empty_metrics(self):
        """Test Lambda cost estimation with no metrics."""
        estimator = CostEstimator()
        
        pricing = LambdaPricing(
            price_per_request=Decimal('0.0000002'),
            price_per_gb_second=Decimal('0.0000166667'),
            currency='USD'
        )
        
        cost = estimator.estimate_lambda_cost([], pricing)
        
        assert cost == Decimal('0')


class TestEstimateDynamoDBCost:
    """Test DynamoDB cost estimation."""
    
    def test_estimate_dynamodb_cost_with_metrics(self):
        """Test DynamoDB cost estimation with metrics."""
        estimator = CostEstimator()
        
        metrics = [
            DynamoDBMetrics(
                table_name='my-table',
                consumed_read_capacity=Decimal('100'),
                consumed_write_capacity=Decimal('50')
            )
        ]
        
        pricing = DynamoDBPricing(
            price_per_read_unit=Decimal('0.00025'),
            price_per_write_unit=Decimal('0.00125'),
            currency='USD'
        )
        
        cost = estimator.estimate_dynamodb_cost(metrics, pricing)
        
        # Expected: 100 * $0.00025 + 50 * $0.00125 = $0.025 + $0.0625 = $0.0875
        assert cost == Decimal('0.0875')
    
    def test_estimate_dynamodb_cost_with_empty_metrics(self):
        """Test DynamoDB cost estimation with no metrics."""
        estimator = CostEstimator()
        
        pricing = DynamoDBPricing(
            price_per_read_unit=Decimal('0.00025'),
            price_per_write_unit=Decimal('0.00125'),
            currency='USD'
        )
        
        cost = estimator.estimate_dynamodb_cost([], pricing)
        
        assert cost == Decimal('0')


class TestEstimateS3Cost:
    """Test S3 cost estimation."""
    
    def test_estimate_s3_cost_with_metrics(self):
        """Test S3 cost estimation with metrics."""
        estimator = CostEstimator()
        
        metrics = [
            S3Metrics(
                bucket_name='my-bucket',
                number_of_objects=1000,
                bucket_size_bytes=Decimal('10737418240'),  # 10 GB
                get_requests=5000,
                put_requests=1000
            )
        ]
        
        pricing = S3Pricing(
            price_per_gb_storage=Decimal('0.023'),
            price_per_get_request=Decimal('0.0004'),
            price_per_put_request=Decimal('0.005'),
            currency='USD'
        )
        
        cost = estimator.estimate_s3_cost(metrics, pricing)
        
        # Expected: 10 GB * $0.023 + 5000 * $0.0004 + 1000 * $0.005
        # = $0.23 + $2.0 + $5.0 = $7.23
        assert cost == Decimal('7.23')
    
    def test_estimate_s3_cost_with_empty_metrics(self):
        """Test S3 cost estimation with no metrics."""
        estimator = CostEstimator()
        
        pricing = S3Pricing(
            price_per_gb_storage=Decimal('0.023'),
            price_per_get_request=Decimal('0.0004'),
            price_per_put_request=Decimal('0.005'),
            currency='USD'
        )
        
        cost = estimator.estimate_s3_cost([], pricing)
        
        assert cost == Decimal('0')


class TestEstimateRDSCost:
    """Test RDS cost estimation."""
    
    def test_estimate_rds_cost_with_metrics(self):
        """Test RDS cost estimation with metrics."""
        estimator = CostEstimator()
        
        metrics = [
            RDSMetrics(
                instance_id='mydb',
                instance_type='db.t3.micro',
                database_connections=10,
                read_iops=Decimal('100'),
                write_iops=Decimal('50'),
                storage_gb=Decimal('20'),
                running_hours=Decimal('1')
            )
        ]
        
        pricing = RDSPricing(
            instance_prices={'db.t3.micro': Decimal('0.017')},
            storage_price_per_gb=Decimal('0.115'),
            iops_price=Decimal('0.10'),
            currency='USD'
        )
        
        cost = estimator.estimate_rds_cost(metrics, pricing)
        
        # Expected: 1 hour * $0.017 + 20 GB * $0.115 + avg_iops * $0.10
        # avg_iops = (100 + 50) / 2 = 75
        # = $0.017 + $2.3 + $7.5 = $9.817
        assert cost == Decimal('9.817')
    
    def test_estimate_rds_cost_with_empty_metrics(self):
        """Test RDS cost estimation with no metrics."""
        estimator = CostEstimator()
        
        pricing = RDSPricing(
            instance_prices={'db.t3.micro': Decimal('0.017')},
            storage_price_per_gb=Decimal('0.115'),
            iops_price=Decimal('0.10'),
            currency='USD'
        )
        
        cost = estimator.estimate_rds_cost([], pricing)
        
        assert cost == Decimal('0')


class TestCalculateConfidenceInterval:
    """Test confidence interval calculation."""
    
    def test_calculate_confidence_interval_with_large_sample(self):
        """Test confidence interval with large sample size."""
        estimator = CostEstimator()
        
        estimate = Decimal('100')
        metrics_count = 150
        
        lower, upper = estimator.calculate_confidence_interval(estimate, metrics_count)
        
        # With 150 metrics, margin should be 10%
        assert lower == Decimal('90')
        assert upper == Decimal('110')
    
    def test_calculate_confidence_interval_with_small_sample(self):
        """Test confidence interval with small sample size."""
        estimator = CostEstimator()
        
        estimate = Decimal('100')
        metrics_count = 5
        
        lower, upper = estimator.calculate_confidence_interval(estimate, metrics_count)
        
        # With 5 metrics, margin should be 30%
        assert lower == Decimal('70')
        assert upper == Decimal('130')
    
    def test_calculate_confidence_interval_with_zero_metrics(self):
        """Test confidence interval with zero metrics."""
        estimator = CostEstimator()
        
        estimate = Decimal('100')
        metrics_count = 0
        
        lower, upper = estimator.calculate_confidence_interval(estimate, metrics_count)
        
        assert lower == Decimal('0')
        assert upper == Decimal('0')
    
    def test_calculate_confidence_interval_lower_bound_not_negative(self):
        """Test that lower bound is never negative."""
        estimator = CostEstimator()
        
        estimate = Decimal('10')
        metrics_count = 5  # 30% margin = 3, so lower would be 7
        
        lower, upper = estimator.calculate_confidence_interval(estimate, metrics_count)
        
        assert lower >= Decimal('0')
        assert lower == Decimal('7')


class TestCalculateTotalEstimate:
    """Test total cost aggregation."""
    
    def test_calculate_total_estimate_with_multiple_estimates(self):
        """Test total calculation with multiple estimates."""
        estimator = CostEstimator()
        
        now = datetime.now(timezone.utc)
        estimates = [
            CostEstimate(
                service='ec2',
                estimated_cost=Decimal('10'),
                currency='USD',
                confidence_lower=Decimal('9'),
                confidence_upper=Decimal('11'),
                timestamp=now,
                period_start=now,
                period_end=now,
                metrics_count=100
            ),
            CostEstimate(
                service='lambda',
                estimated_cost=Decimal('5'),
                currency='USD',
                confidence_lower=Decimal('4.5'),
                confidence_upper=Decimal('5.5'),
                timestamp=now,
                period_start=now,
                period_end=now,
                metrics_count=100
            )
        ]
        
        total = estimator.calculate_total_estimate(estimates)
        
        assert total == Decimal('15')
    
    def test_calculate_total_estimate_with_empty_list(self):
        """Test total calculation with empty list."""
        estimator = CostEstimator()
        
        total = estimator.calculate_total_estimate([])
        
        assert total == Decimal('0')


class TestEstimateCost:
    """Test generic estimate_cost method."""
    
    def test_estimate_cost_creates_cost_estimate(self):
        """Test that estimate_cost creates a CostEstimate object."""
        estimator = CostEstimator()
        
        metrics = [
            MetricDataPoint(
                timestamp=datetime.now(timezone.utc),
                value=Decimal('10'),
                unit='Count',
                metric_name='test'
            )
        ]
        
        pricing_data = PricingData(
            service='ec2',
            region='us-east-1',
            prices={'t2.micro': Decimal('0.0116')},
            currency='USD',
            last_updated=datetime.now(timezone.utc),
            ttl=86400
        )
        
        result = estimator.estimate_cost('ec2', metrics, pricing_data)
        
        assert isinstance(result, CostEstimate)
        assert result.service == 'ec2'
        assert result.currency == 'USD'
        assert result.metrics_count == 1
