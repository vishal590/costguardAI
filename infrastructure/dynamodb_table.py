"""
DynamoDB Table Definition for Cost Data Pipeline

This module defines the DynamoDB table infrastructure using AWS CDK (Python).
The table stores AWS cost data with efficient access patterns for querying by date and service.

Phase 1 Requirements:
- 3.2: Partition key format: COST#YYYY-MM
- 3.3: Sort key format: SERVICE#service-name
- 10.3: On-demand billing mode for Free Tier compatibility

Phase 2 Requirements:
- 4.1: Forecast cache table with cache_key partition key
- 4.3: TTL attribute for automatic cache expiration
- 9.4: On-demand billing for Free Tier compatibility
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
)
from constructs import Construct


class CostDataTable(Construct):
    """DynamoDB table for storing AWS cost data"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create DynamoDB table with partition key and sort key
        self.table = dynamodb.Table(
            self,
            "CostDataTable",
            table_name="costguard-cost-data",
            partition_key=dynamodb.Attribute(
                name="pk", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,  # On-demand billing
            time_to_live_attribute="ttl",  # Enable TTL for automatic cleanup
            removal_policy=RemovalPolicy.RETAIN,  # Retain table on stack deletion
            point_in_time_recovery=False,  # Disabled for Free Tier
        )


class ForecastCacheTable(Construct):
    """DynamoDB table for storing forecast cache (Phase 2)"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create DynamoDB table for forecast cache
        self.table = dynamodb.Table(
            self,
            "ForecastCacheTable",
            table_name="costguard-forecast-cache",
            partition_key=dynamodb.Attribute(
                name="cache_key", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,  # On-demand billing
            time_to_live_attribute="ttl",  # Enable TTL for automatic cache expiration
            removal_policy=RemovalPolicy.RETAIN,  # Retain table on stack deletion
            point_in_time_recovery=False,  # Disabled for Free Tier
        )


class PricingCacheTable(Construct):
    """DynamoDB table for storing pricing cache (Phase 1.5)"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create DynamoDB table for pricing cache
        self.table = dynamodb.Table(
            self,
            "PricingCacheTable",
            table_name="costguard-pricing-cache",
            partition_key=dynamodb.Attribute(
                name="cache_key", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,  # On-demand billing
            time_to_live_attribute="ttl",  # Enable TTL for automatic cache expiration (24 hours)
            removal_policy=RemovalPolicy.RETAIN,  # Retain table on stack deletion
            point_in_time_recovery=False,  # Disabled for Free Tier
        )


class CostDataStack(Stack):
    """CDK Stack for Cost Data Pipeline DynamoDB tables"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create DynamoDB table for cost data
        self.cost_data_table = CostDataTable(self, "CostDataTableConstruct")

        # Create DynamoDB table for forecast cache (Phase 2)
        self.forecast_cache_table = ForecastCacheTable(self, "ForecastCacheTableConstruct")
        
        # Create DynamoDB table for pricing cache (Phase 1.5)
        self.pricing_cache_table = PricingCacheTable(self, "PricingCacheTableConstruct")