"""
IAM Roles and Policies for Cost Data Pipeline

This module defines IAM roles and policies using AWS CDK (Python).
The roles grant necessary permissions for Lambda to access Cost Explorer, DynamoDB, CloudWatch, Pricing API, and Bedrock.

Phase 1 Requirements:
- 1.1: Cost Explorer read access
- 3.5: DynamoDB read/write access
- 7.6: Query operations
- 9.1: CloudWatch Logs access

Phase 1.5 Requirements:
- 1.1: CloudWatch Metrics read access (GetMetricStatistics, ListMetrics)
- 3.3: Pricing API read access (GetProducts)

Phase 2 Requirements:
- 2.1: Bedrock InvokeModel permission
- 4.1: DynamoDB read/write access for forecast cache table
"""

from aws_cdk import (
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_dynamodb as dynamodb,
)
from constructs import Construct


class CostDataIAMRole(Construct):
    """IAM role and policies for Cost Data Lambda function"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        lambda_function: lambda_.Function,
        table: dynamodb.Table,
        forecast_cache_table: dynamodb.Table = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Cost Explorer read policy
        cost_explorer_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ce:GetCostAndUsage",
                "ce:GetDimensionValues",
            ],
            resources=["*"],  # Cost Explorer doesn't support resource-level permissions
        )

        # CloudWatch Metrics read policy (Phase 1.5)
        cloudwatch_metrics_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "cloudwatch:GetMetricStatistics",
                "cloudwatch:ListMetrics",
            ],
            resources=["*"],  # CloudWatch metrics don't support resource-level permissions
        )

        # Pricing API read policy (Phase 1.5)
        pricing_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "pricing:GetProducts",
            ],
            resources=["*"],  # Pricing API doesn't support resource-level permissions
        )

        # Bedrock InvokeModel policy (Phase 2)
        bedrock_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:InvokeModel",
            ],
            resources=["*"],  # Bedrock doesn't support resource-level permissions
        )

        # DynamoDB read/write policy for cost data table
        dynamodb_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "dynamodb:PutItem",
                "dynamodb:GetItem",
                "dynamodb:Query",
                "dynamodb:BatchWriteItem",
            ],
            resources=[
                table.table_arn,
            ],
        )

        # DynamoDB read/write policy for forecast cache table (Phase 2)
        if forecast_cache_table:
            forecast_cache_policy = iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:PutItem",
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                    "dynamodb:DeleteItem",
                    "dynamodb:BatchWriteItem",
                ],
                resources=[
                    forecast_cache_table.table_arn,
                ],
            )
            lambda_function.add_to_role_policy(forecast_cache_policy)

        # CloudWatch Logs policy (automatically added by CDK, but explicit for clarity)
        cloudwatch_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
            ],
            resources=[
                f"arn:aws:logs:{self.node.try_get_context('region') or 'us-east-1'}:*:log-group:/aws/lambda/{lambda_function.function_name}:*"
            ],
        )

        # Add policies to Lambda function role
        lambda_function.add_to_role_policy(cost_explorer_policy)
        lambda_function.add_to_role_policy(cloudwatch_metrics_policy)
        lambda_function.add_to_role_policy(pricing_policy)
        lambda_function.add_to_role_policy(bedrock_policy)
        lambda_function.add_to_role_policy(dynamodb_policy)
        lambda_function.add_to_role_policy(cloudwatch_policy)
