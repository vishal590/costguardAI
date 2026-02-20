"""
Property-based tests for Cost Estimator.

Feature: near-realtime-cost-estimation
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
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
    CostEstimate
)


# Feature: near-realtime-cost-estimation, Property 2: Non-Negative Cost Estimates
@given(
    running_hours=st.floats(min_value=0, max_value=720, allow_nan=False, allow_infinity=False),
    network_out=st.floats(min_value=0, max_value=1e12, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_non_negative_cost_estimates_ec2(running_hours, network_out):
    """
    Property 2: Non-Negative Cost Estimates
    
    For any valid metrics and pricing data, estimated costs must be non-negative values.
    
    Validates: Requirements 2.1-2.5, 8.1
    """
    estimator = CostEstimator()
    
    metrics = [
        EC2Metrics(
            instance_id='i-test',
            instance_type='t2.micro',
            cpu_utilization=Decimal('50'),
            network_in=Decimal('1000'),
            network_out=Decimal(str(network_out)),
            disk_read_bytes=Decimal('1000'),
            running_hours=Decimal(str(running_hours))
        )
    ]
    
    pricing = EC2Pricing(
        instance_prices={'t2.micro': Decimal('0.0116')},
        data_transfer_out=Decimal('0.09'),
        currency='USD'
    )
    
    cost = estimator.estimate_ec2_cost(metrics, pricing)
    
    # Property: Cost must be non-negative
    assert cost >= Decimal('0'), f"Cost {cost} must be non-negative"


# Feature: near-realtime-cost-estimation, Property 12: Estimation Bounds Check
@given(
    invocations=st.integers(min_value=0, max_value=1000000),
    duration_ms=st.floats(min_value=0, max_value=900000, allow_nan=False, allow_infinity=False),
    memory_mb=st.integers(min_value=128, max_value=10240)
)
@settings(max_examples=100)
def test_estimation_bounds_check_lambda(invocations, duration_ms, memory_mb):
    """
    Property 12: Estimation Bounds Check
    
    For any calculated estimate, the result must be within reasonable bounds
    (not infinity, not NaN).
    
    Validates: Requirements 8.3
    """
    estimator = CostEstimator()
    
    metrics = [
        LambdaMetrics(
            function_name='test-function',
            invocations=invocations,
            duration_ms=Decimal(str(duration_ms)),
            memory_mb=memory_mb,
            errors=0
        )
    ]
    
    pricing = LambdaPricing(
        price_per_request=Decimal('0.0000002'),
        price_per_gb_second=Decimal('0.0000166667'),
        currency='USD'
    )
    
    cost = estimator.estimate_lambda_cost(metrics, pricing)
    
    # Property: Cost must be finite and not NaN
    assert cost.is_finite(), f"Cost {cost} must be finite"
    assert not cost.is_nan(), f"Cost {cost} must not be NaN"
    assert cost >= Decimal('0'), f"Cost {cost} must be non-negative"


# Feature: near-realtime-cost-estimation, Property 15: Confidence Interval Validity
@given(
    estimate_value=st.floats(min_value=0.01, max_value=10000, allow_nan=False, allow_infinity=False),
    metrics_count=st.integers(min_value=1, max_value=200)
)
@settings(max_examples=100)
def test_confidence_interval_validity(estimate_value, metrics_count):
    """
    Property 15: Confidence Interval Validity
    
    For any cost estimate with confidence interval, the lower bound must be less than
    or equal to the estimate, and the estimate must be less than or equal to the upper bound.
    
    Validates: Requirements 2.8
    """
    estimator = CostEstimator()
    
    estimate = Decimal(str(estimate_value))
    
    lower, upper = estimator.calculate_confidence_interval(estimate, metrics_count)
    
    # Property: lower <= estimate <= upper
    assert lower <= estimate, f"Lower bound {lower} must be <= estimate {estimate}"
    assert estimate <= upper, f"Estimate {estimate} must be <= upper bound {upper}"
    
    # Property: Bounds must be non-negative
    assert lower >= Decimal('0'), f"Lower bound {lower} must be non-negative"
    assert upper >= Decimal('0'), f"Upper bound {upper} must be non-negative"


# Additional property: Total cost is sum of individual costs
@given(
    num_estimates=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=100)
def test_total_cost_is_sum_of_estimates(num_estimates):
    """
    Property: Total cost equals sum of individual estimates
    
    For any list of cost estimates, the total should equal the sum of individual costs.
    
    Validates: Requirements 2.6
    """
    estimator = CostEstimator()
    
    now = datetime.now(timezone.utc)
    estimates = []
    expected_total = Decimal('0')
    
    for i in range(num_estimates):
        cost = Decimal(str(i + 1))
        expected_total += cost
        
        estimates.append(
            CostEstimate(
                service=f'service{i}',
                estimated_cost=cost,
                currency='USD',
                confidence_lower=cost * Decimal('0.9'),
                confidence_upper=cost * Decimal('1.1'),
                timestamp=now,
                period_start=now,
                period_end=now,
                metrics_count=100
            )
        )
    
    total = estimator.calculate_total_estimate(estimates)
    
    # Property: Total must equal sum
    assert total == expected_total, f"Total {total} must equal sum {expected_total}"


# Property: Confidence interval width decreases with more metrics
@given(
    estimate_value=st.floats(min_value=100, max_value=1000, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_confidence_interval_narrows_with_more_metrics(estimate_value):
    """
    Property: Confidence interval narrows with more metrics
    
    For any estimate, having more metrics should result in a narrower confidence interval.
    
    Validates: Requirements 2.8
    """
    estimator = CostEstimator()
    
    estimate = Decimal(str(estimate_value))
    
    # Calculate intervals for different sample sizes
    lower_small, upper_small = estimator.calculate_confidence_interval(estimate, 5)
    lower_large, upper_large = estimator.calculate_confidence_interval(estimate, 150)
    
    width_small = upper_small - lower_small
    width_large = upper_large - lower_large
    
    # Property: Larger sample should have narrower interval
    assert width_large <= width_small, \
        f"Interval with 150 metrics ({width_large}) should be <= interval with 5 metrics ({width_small})"


# Property: Empty metrics result in zero cost
@given(
    service=st.sampled_from(['ec2', 'lambda', 'dynamodb', 's3', 'rds'])
)
@settings(max_examples=100)
def test_empty_metrics_result_in_zero_cost(service):
    """
    Property: Empty metrics result in zero cost
    
    For any service with no metrics, the estimated cost should be zero.
    
    Validates: Requirements 2.1-2.5
    """
    estimator = CostEstimator()
    
    if service == 'ec2':
        pricing = EC2Pricing(
            instance_prices={'t2.micro': Decimal('0.0116')},
            data_transfer_out=Decimal('0.09'),
            currency='USD'
        )
        cost = estimator.estimate_ec2_cost([], pricing)
    elif service == 'lambda':
        pricing = LambdaPricing(
            price_per_request=Decimal('0.0000002'),
            price_per_gb_second=Decimal('0.0000166667'),
            currency='USD'
        )
        cost = estimator.estimate_lambda_cost([], pricing)
    elif service == 'dynamodb':
        pricing = DynamoDBPricing(
            price_per_read_unit=Decimal('0.00025'),
            price_per_write_unit=Decimal('0.00125'),
            currency='USD'
        )
        cost = estimator.estimate_dynamodb_cost([], pricing)
    elif service == 's3':
        pricing = S3Pricing(
            price_per_gb_storage=Decimal('0.023'),
            price_per_get_request=Decimal('0.0004'),
            price_per_put_request=Decimal('0.005'),
            currency='USD'
        )
        cost = estimator.estimate_s3_cost([], pricing)
    else:  # rds
        pricing = RDSPricing(
            instance_prices={'db.t3.micro': Decimal('0.017')},
            storage_price_per_gb=Decimal('0.115'),
            iops_price=Decimal('0.10'),
            currency='USD'
        )
        cost = estimator.estimate_rds_cost([], pricing)
    
    # Property: Empty metrics should result in zero cost
    assert cost == Decimal('0'), f"Empty metrics for {service} should result in zero cost"
