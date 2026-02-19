#!/usr/bin/env python3
"""
AWS CDK App for Cost Data Pipeline

This is the main entry point for the CDK application.
It creates all infrastructure components: DynamoDB table, Lambda function, IAM roles, and API Gateway.

Usage:
    cdk deploy
"""

from aws_cdk import App, Environment
from dynamodb_table import CostDataStack
from lambda_function import CostDataLambda
from iam_roles import CostDataIAMRole
from api_gateway import CostDataAPI


class CostDataPipelineStack(CostDataStack):
    """Complete infrastructure stack for Cost Data Pipeline"""

    def __init__(self, scope: App, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # DynamoDB table (created by parent CostDataStack)
        table = self.cost_data_table.table

        # Lambda function
        lambda_construct = CostDataLambda(
            self, "CostDataLambdaConstruct", table=table
        )
        lambda_function = lambda_construct.function

        # IAM roles and policies
        CostDataIAMRole(
            self,
            "CostDataIAMRoleConstruct",
            lambda_function=lambda_function,
            table=table,
        )

        # API Gateway
        api_construct = CostDataAPI(
            self, "CostDataAPIConstruct", lambda_function=lambda_function
        )

        # Output API endpoint and API key ID
        from aws_cdk import CfnOutput

        CfnOutput(
            self,
            "APIEndpoint",
            value=api_construct.api.url,
            description="API Gateway endpoint URL",
        )

        CfnOutput(
            self,
            "APIKeyID",
            value=api_construct.api_key.key_id,
            description="API Key ID (use AWS CLI to retrieve key value)",
        )


# Create CDK app
app = App()

# Create stack
CostDataPipelineStack(
    app,
    "CostDataPipelineStack",
    env=Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1",
    ),
)

app.synth()
