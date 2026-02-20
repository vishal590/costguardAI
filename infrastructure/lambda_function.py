"""
Lambda Function Definition for Cost Data Pipeline

This module defines the Lambda function infrastructure using AWS CDK (Python).
The Lambda function handles cost data fetching and querying operations.

Phase 1 Requirements:
- 10.1: Python 3.11 runtime
- 10.2: 256 MB memory, 30 second timeout

Phase 1.5 Requirements:
- 3.2: Pricing cache TTL configuration
- 7.2: Metrics collection period configuration
"""

from aws_cdk import (
    Duration,
    aws_lambda as lambda_,
    aws_dynamodb as dynamodb,
)
from constructs import Construct


class CostDataLambda(Construct):
    """Lambda function for cost data pipeline operations"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        table: dynamodb.Table,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create Lambda function
        self.function = lambda_.Function(
            self,
            "CostDataFunction",
            function_name="costguard-cost-data-handler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="lambda_handler.handler",
            code=lambda_.Code.from_asset("../src"),  # Package src directory
            memory_size=256,  # MB
            timeout=Duration.seconds(30),
            environment={
                # Phase 1 environment variables
                "DYNAMODB_TABLE_NAME": table.table_name,
                "AWS_REGION": self.node.try_get_context("region") or "us-east-1",
                # Phase 1.5 environment variables
                "PRICING_CACHE_TTL_HOURS": "24",  # Refresh pricing data every 24 hours
                "METRICS_COLLECTION_PERIOD": "300",  # 5 minutes (in seconds)
                "ESTIMATION_CONFIDENCE_LEVEL": "0.95",  # 95% confidence interval
            },
        )

        # Grant Lambda permissions to access DynamoDB table
        table.grant_read_write_data(self.function)
