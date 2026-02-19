"""
Lambda Function Definition for Cost Data Pipeline

This module defines the Lambda function infrastructure using AWS CDK (Python).
The Lambda function handles cost data fetching and querying operations.

Requirements:
- 10.1: Python 3.11 runtime
- 10.2: 256 MB memory, 30 second timeout
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
                "DYNAMODB_TABLE_NAME": table.table_name,
                "AWS_REGION": self.node.try_get_context("region") or "us-east-1",
            },
        )

        # Grant Lambda permissions to access DynamoDB table
        table.grant_read_write_data(self.function)
