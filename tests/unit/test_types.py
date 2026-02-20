"""
Unit tests for Phase 1.5 data models and types.
"""
import pytest
from datetime import datetime
from decimal import Decimal

from src.utils.types import (
    MetricDataPoint,
    EC2Metrics,
    LambdaMetrics,
    DynamoDBMetrics,
    S3Metrics,
    RDSMetrics,
    PricingData,
    EC2Pricing,
    LambdaPricing,
    DynamoDBPricing,
    S3Pricing,
    RDSPricing,
    CostEstimate,
    EstimationResponse
)


class TestMetricDataPoint:
    """Test MetricDataPoint dataclass."""
    
    def test_create_metric_data_point(self):
        """Test creating a MetricDataPoint."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        metric = MetricDataPoint(
            timestamp=timestamp,
            value=Decimal('10.5'),
            unit='Count',
            metric_name='TestMetric'
        )
        
        assert metric.timestamp == timestamp
        assert metric.value == Decimal('10.5')
        assert metric.unit == 'Count'
        assert metric.metric_name == 'TestMetric'


class TestEC2Metrics:
    """Test EC2Metrics dataclass."""
    
    def test_create_ec2_metrics(self):
        """Test creating EC2Metrics."""
        metrics = EC2Metrics(
            instance_id='i-1234567890abcdef0',
            instance_type='t2.micro',
            cpu_utilization=Decimal('45.5'),
            network_in=Decimal('1024'),
            network_out=Decimal('512'),
            disk_read_bytes=Decimal('2048'),
            running_hours=Decimal('1.5')
        )
        
        assert metrics.instance_id == 'i-1234567890abcdef0'
        assert metrics.instance_type == 't2.micro'
        assert metrics.cpu_utilization == Decimal('45.5')
        assert metrics.network_in == Decimal('1024')
        assert metrics.network_out == Decimal('512')
        assert metrics.disk_read_bytes == Decimal('2048')
        assert metrics.running_hours == Decimal('1.5')


class TestLambdaMetrics:
    """Test LambdaMetrics dataclass."""
    
    def test_create_lambda_metrics(self):
        """Test creating LambdaMetrics."""
        metrics = LambdaMetrics(
            function_name='my-function',
            invocations=100,
            duration_ms=Decimal('250.5'),
            memory_mb=128,
            errors=2
        )
        
        assert metrics.function_name == 'my-function'
        assert metrics.invocations == 100
        assert metrics.duration_ms == Decimal('250.5')
        assert metrics.memory_mb == 128
        assert metrics.errors == 2


class TestDynamoDBMetrics:
    """Test DynamoDBMetrics dataclass."""
    
    def test_create_dynamodb_metrics(self):
        """Test creating DynamoDBMetrics."""
        metrics = DynamoDBMetrics(
            table_name='my-table',
            consumed_read_capacity=Decimal('50.5'),
            consumed_write_capacity=Decimal('25.3')
        )
        
        assert metrics.table_name == 'my-table'
        assert metrics.consumed_read_capacity == Decimal('50.5')
        assert metrics.consumed_write_capacity == Decimal('25.3')


class TestS3Metrics:
    """Test S3Metrics dataclass."""
    
    def test_create_s3_metrics(self):
        """Test creating S3Metrics."""
        metrics = S3Metrics(
            bucket_name='my-bucket',
            number_of_objects=1000,
            bucket_size_bytes=Decimal('1073741824'),  # 1 GB
            get_requests=500,
            put_requests=100
        )
        
        assert metrics.bucket_name == 'my-bucket'
        assert metrics.number_of_objects == 1000
        assert metrics.bucket_size_bytes == Decimal('1073741824')
        assert metrics.get_requests == 500
        assert metrics.put_requests == 100


class TestRDSMetrics:
    """Test RDSMetrics dataclass."""
    
    def test_create_rds_metrics(self):
        """Test creating RDSMetrics."""
        metrics = RDSMetrics(
            instance_id='mydb-instance',
            instance_type='db.t3.micro',
            database_connections=10,
            read_iops=Decimal('100.5'),
            write_iops=Decimal('50.3'),
            storage_gb=Decimal('20'),
            running_hours=Decimal('2.5')
        )
        
        assert metrics.instance_id == 'mydb-instance'
        assert metrics.instance_type == 'db.t3.micro'
        assert metrics.database_connections == 10
        assert metrics.read_iops == Decimal('100.5')
        assert metrics.write_iops == Decimal('50.3')
        assert metrics.storage_gb == Decimal('20')
        assert metrics.running_hours == Decimal('2.5')


class TestPricingData:
    """Test PricingData dataclass."""
    
    def test_create_pricing_data(self):
        """Test creating PricingData."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        pricing = PricingData(
            service='ec2',
            region='us-east-1',
            prices={'t2.micro': Decimal('0.0116')},
            currency='USD',
            last_updated=timestamp,
            ttl=86400
        )
        
        assert pricing.service == 'ec2'
        assert pricing.region == 'us-east-1'
        assert pricing.prices == {'t2.micro': Decimal('0.0116')}
        assert pricing.currency == 'USD'
        assert pricing.last_updated == timestamp
        assert pricing.ttl == 86400


class TestEC2Pricing:
    """Test EC2Pricing dataclass."""
    
    def test_create_ec2_pricing(self):
        """Test creating EC2Pricing."""
        pricing = EC2Pricing(
            instance_prices={
                't2.micro': Decimal('0.0116'),
                't2.small': Decimal('0.023')
            },
            data_transfer_out=Decimal('0.09'),
            currency='USD'
        )
        
        assert pricing.instance_prices['t2.micro'] == Decimal('0.0116')
        assert pricing.instance_prices['t2.small'] == Decimal('0.023')
        assert pricing.data_transfer_out == Decimal('0.09')
        assert pricing.currency == 'USD'


class TestLambdaPricing:
    """Test LambdaPricing dataclass."""
    
    def test_create_lambda_pricing(self):
        """Test creating LambdaPricing."""
        pricing = LambdaPricing(
            price_per_request=Decimal('0.0000002'),
            price_per_gb_second=Decimal('0.0000166667'),
            currency='USD'
        )
        
        assert pricing.price_per_request == Decimal('0.0000002')
        assert pricing.price_per_gb_second == Decimal('0.0000166667')
        assert pricing.currency == 'USD'


class TestDynamoDBPricing:
    """Test DynamoDBPricing dataclass."""
    
    def test_create_dynamodb_pricing(self):
        """Test creating DynamoDBPricing."""
        pricing = DynamoDBPricing(
            price_per_read_unit=Decimal('0.00025'),
            price_per_write_unit=Decimal('0.00125'),
            currency='USD'
        )
        
        assert pricing.price_per_read_unit == Decimal('0.00025')
        assert pricing.price_per_write_unit == Decimal('0.00125')
        assert pricing.currency == 'USD'


class TestS3Pricing:
    """Test S3Pricing dataclass."""
    
    def test_create_s3_pricing(self):
        """Test creating S3Pricing."""
        pricing = S3Pricing(
            price_per_gb_storage=Decimal('0.023'),
            price_per_get_request=Decimal('0.0004'),
            price_per_put_request=Decimal('0.005'),
            currency='USD'
        )
        
        assert pricing.price_per_gb_storage == Decimal('0.023')
        assert pricing.price_per_get_request == Decimal('0.0004')
        assert pricing.price_per_put_request == Decimal('0.005')
        assert pricing.currency == 'USD'


class TestRDSPricing:
    """Test RDSPricing dataclass."""
    
    def test_create_rds_pricing(self):
        """Test creating RDSPricing."""
        pricing = RDSPricing(
            instance_prices={
                'db.t3.micro': Decimal('0.017'),
                'db.t3.small': Decimal('0.034')
            },
            storage_price_per_gb=Decimal('0.115'),
            iops_price=Decimal('0.10'),
            currency='USD'
        )
        
        assert pricing.instance_prices['db.t3.micro'] == Decimal('0.017')
        assert pricing.instance_prices['db.t3.small'] == Decimal('0.034')
        assert pricing.storage_price_per_gb == Decimal('0.115')
        assert pricing.iops_price == Decimal('0.10')
        assert pricing.currency == 'USD'


class TestCostEstimate:
    """Test CostEstimate dataclass."""
    
    def test_create_cost_estimate(self):
        """Test creating CostEstimate."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        period_start = datetime(2024, 1, 1, 11, 0, 0)
        period_end = datetime(2024, 1, 1, 12, 0, 0)
        
        estimate = CostEstimate(
            service='ec2',
            estimated_cost=Decimal('1.50'),
            currency='USD',
            confidence_lower=Decimal('1.40'),
            confidence_upper=Decimal('1.60'),
            timestamp=timestamp,
            period_start=period_start,
            period_end=period_end,
            metrics_count=100
        )
        
        assert estimate.service == 'ec2'
        assert estimate.estimated_cost == Decimal('1.50')
        assert estimate.currency == 'USD'
        assert estimate.confidence_lower == Decimal('1.40')
        assert estimate.confidence_upper == Decimal('1.60')
        assert estimate.timestamp == timestamp
        assert estimate.period_start == period_start
        assert estimate.period_end == period_end
        assert estimate.metrics_count == 100


class TestEstimationResponse:
    """Test EstimationResponse dataclass."""
    
    def test_create_estimation_response(self):
        """Test creating EstimationResponse."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        period_start = datetime(2024, 1, 1, 11, 0, 0)
        period_end = datetime(2024, 1, 1, 12, 0, 0)
        
        estimate = CostEstimate(
            service='ec2',
            estimated_cost=Decimal('1.50'),
            currency='USD',
            confidence_lower=Decimal('1.40'),
            confidence_upper=Decimal('1.60'),
            timestamp=timestamp,
            period_start=period_start,
            period_end=period_end,
            metrics_count=100
        )
        
        response = EstimationResponse(
            success=True,
            estimates=[estimate],
            total_cost=Decimal('1.50'),
            currency='USD',
            timestamp=timestamp,
            period='1h'
        )
        
        assert response.success is True
        assert len(response.estimates) == 1
        assert response.estimates[0].service == 'ec2'
        assert response.total_cost == Decimal('1.50')
        assert response.currency == 'USD'
        assert response.timestamp == timestamp
        assert response.period == '1h'
    
    def test_create_estimation_response_multiple_estimates(self):
        """Test creating EstimationResponse with multiple estimates."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        period_start = datetime(2024, 1, 1, 11, 0, 0)
        period_end = datetime(2024, 1, 1, 12, 0, 0)
        
        ec2_estimate = CostEstimate(
            service='ec2',
            estimated_cost=Decimal('1.50'),
            currency='USD',
            confidence_lower=Decimal('1.40'),
            confidence_upper=Decimal('1.60'),
            timestamp=timestamp,
            period_start=period_start,
            period_end=period_end,
            metrics_count=100
        )
        
        lambda_estimate = CostEstimate(
            service='lambda',
            estimated_cost=Decimal('0.25'),
            currency='USD',
            confidence_lower=Decimal('0.20'),
            confidence_upper=Decimal('0.30'),
            timestamp=timestamp,
            period_start=period_start,
            period_end=period_end,
            metrics_count=50
        )
        
        response = EstimationResponse(
            success=True,
            estimates=[ec2_estimate, lambda_estimate],
            total_cost=Decimal('1.75'),
            currency='USD',
            timestamp=timestamp,
            period='1h'
        )
        
        assert response.success is True
        assert len(response.estimates) == 2
        assert response.estimates[0].service == 'ec2'
        assert response.estimates[1].service == 'lambda'
        assert response.total_cost == Decimal('1.75')


class TestTypeConversions:
    """Test type conversions and edge cases."""
    
    def test_decimal_precision(self):
        """Test Decimal precision is maintained."""
        metric = MetricDataPoint(
            timestamp=datetime.now(),
            value=Decimal('10.123456789'),
            unit='Count',
            metric_name='test'
        )
        
        assert metric.value == Decimal('10.123456789')
    
    def test_zero_values(self):
        """Test handling of zero values."""
        metrics = EC2Metrics(
            instance_id='i-123',
            instance_type='t2.micro',
            cpu_utilization=Decimal('0'),
            network_in=Decimal('0'),
            network_out=Decimal('0'),
            disk_read_bytes=Decimal('0'),
            running_hours=Decimal('0')
        )
        
        assert metrics.cpu_utilization == Decimal('0')
        assert metrics.network_in == Decimal('0')
