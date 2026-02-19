"""
API Gateway Definition for Cost Data Pipeline

This module defines the API Gateway infrastructure using AWS CDK (Python).
The API Gateway exposes REST endpoints for fetching and querying cost data.

Requirements:
- 6.1: POST /api/cost-data/fetch endpoint
- 6.2: GET /api/cost-data endpoint
- 6.3: API key authentication
"""

from aws_cdk import (
    aws_apigateway as apigateway,
    aws_lambda as lambda_,
)
from constructs import Construct


class CostDataAPI(Construct):
    """API Gateway for cost data pipeline"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        lambda_function: lambda_.Function,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create REST API
        self.api = apigateway.RestApi(
            self,
            "CostDataAPI",
            rest_api_name="costguard-cost-data-api",
            description="API for AWS Cost Data Pipeline",
            deploy_options=apigateway.StageOptions(
                stage_name="prod",
                throttling_rate_limit=10,  # Requests per second
                throttling_burst_limit=20,  # Burst capacity
            ),
        )

        # Create API key
        self.api_key = self.api.add_api_key(
            "CostDataAPIKey",
            api_key_name="costguard-api-key",
        )

        # Create usage plan
        usage_plan = self.api.add_usage_plan(
            "CostDataUsagePlan",
            name="costguard-usage-plan",
            throttle=apigateway.ThrottleSettings(
                rate_limit=10,  # Requests per second
                burst_limit=20,  # Burst capacity
            ),
            quota=apigateway.QuotaSettings(
                limit=10000,  # Requests per month
                period=apigateway.Period.MONTH,
            ),
        )

        # Associate API key with usage plan
        usage_plan.add_api_key(self.api_key)
        usage_plan.add_api_stage(stage=self.api.deployment_stage)

        # Create Lambda integration
        lambda_integration = apigateway.LambdaIntegration(
            lambda_function,
            proxy=True,
            allow_test_invoke=True,
        )

        # Create /api resource
        api_resource = self.api.root.add_resource("api")

        # Create /api/cost-data resource
        cost_data_resource = api_resource.add_resource("cost-data")

        # Add GET /api/cost-data endpoint (query cost data)
        cost_data_resource.add_method(
            "GET",
            lambda_integration,
            api_key_required=True,
        )

        # Create /api/cost-data/fetch resource
        fetch_resource = cost_data_resource.add_resource("fetch")

        # Add POST /api/cost-data/fetch endpoint (fetch and store cost data)
        fetch_resource.add_method(
            "POST",
            lambda_integration,
            api_key_required=True,
        )
