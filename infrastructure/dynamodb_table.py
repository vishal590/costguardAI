"""
DynamoDB Table Definition for Cost Data Pipeline

This module defines the DynamoDB table infrastructure using AWS CDK (Python).
The table stores AWS cost data with efficient access patterns for querying by date and service.

Requirements:
- 3.2: Partition key format: COST#YYYY-MM
- 3.3: Sort key format: SERVICE#service-name
- 10.3: On-demand billing mode for Free Tier compatibility
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


class CostDataStack(Stack):
    """CDK Stack for Cost Data Pipeline DynamoDB table"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create DynamoDB table
        self.cost_data_table = CostDataTable(self, "CostDataTableConstruct")
