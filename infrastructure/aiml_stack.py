"""
AWS CDK Infrastructure Stack for AI/ML Workload Cost Management (Phase 6)

This CDK stack extends the existing CostGuard infrastructure to support
AI/ML workload cost tracking and optimization.

Includes:
- AI/ML DynamoDB tables (GPU costs, workload classifications, cache)
- AI/ML Lambda function with Phase 6 handler
- Extended API Gateway with AI/ML endpoints
- IAM roles and permissions for GPU/SageMaker/Bedrock access
- CloudWatch alarms for monitoring
- SNS topics for notifications

Requirements: All Phase 6 AI/ML workload cost management requirements
"""

import os
import json
import re
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_apigateway as apigateway,
    aws_sns as sns,
    aws_iam as iam,
    aws_logs as logs,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    CfnOutput,
)
from constructs import Construct


class AIMLStack(Stack):
    """
    CDK Stack for AI/ML Workload Cost Management (Phase 6).
    
    Extends the existing CostGuard infrastructure with AI/ML cost tracking capabilities.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # =====================================================================
        # AI/ML DynamoDB Tables
        # =====================================================================

        # GPU costs tracking table
        gpu_costs_table = dynamodb.Table(
            self, "GPUCostsTable",
            table_name="costguard-gpu-costs",
            partition_key=dynamodb.Attribute(
                name="instance_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            time_to_live_attribute="ttl",
            point_in_time_recovery=False,  # Free tier constraint
        )

        # Add GSI for workload type queries
        gpu_costs_table.add_global_secondary_index(
            index_name="workload-type-index",
            partition_key=dynamodb.Attribute(
                name="workload_type",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Workload classifications table
        workload_classifications_table = dynamodb.Table(
            self, "WorkloadClassificationsTable",
            table_name="costguard-workload-classifications",
            partition_key=dynamodb.Attribute(
                name="instance_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="date",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            time_to_live_attribute="ttl",
            point_in_time_recovery=False,  # Free tier constraint
        )

        # AI/ML cache table
        aiml_cache_table = dynamodb.Table(
            self, "AIMLCacheTable",
            table_name="costguard-aiml-cache",
            partition_key=dynamodb.Attribute(
                name="cache_key",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            time_to_live_attribute="ttl",
            point_in_time_recovery=False,  # Free tier constraint
        )

        # =====================================================================
        # IAM Role for AI/ML Lambda
        # =====================================================================

        aiml_lambda_role = iam.Role(
            self, "AIMLLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
        )

        # Add EC2 permissions for GPU instance tracking
        aiml_lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ec2:DescribeInstances",
                "ec2:DescribeInstanceTypes",
                "ec2:DescribeSpotPriceHistory",
            ],
            resources=["*"],
        ))

        # Add SageMaker permissions
        aiml_lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "sagemaker:ListTrainingJobs",
                "sagemaker:DescribeTrainingJob",
                "sagemaker:ListEndpoints",
                "sagemaker:DescribeEndpoint",
                "sagemaker:DescribeEndpointConfig",
                "sagemaker:ListNotebookInstances",
                "sagemaker:DescribeNotebookInstance",
            ],
            resources=["*"],
        ))

        # Add Bedrock permissions
        aiml_lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:ListModelInvocationJobs",
                "bedrock:GetModelInvocationJob",
                "bedrock:InvokeModel",
            ],
            resources=[
                f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
            ],
        ))

        # Add CloudWatch permissions for metrics
        aiml_lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "cloudwatch:GetMetricStatistics",
                "cloudwatch:GetMetricData",
                "cloudwatch:ListMetrics",
            ],
            resources=["*"],
        ))

        # Add Cost Explorer permissions
        aiml_lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ce:GetCostAndUsage",
                "ce:GetCostForecast",
            ],
            resources=["*"],
        ))

        aiml_lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW, actions=["pricing:GetProducts"], resources=["*"],
        ))

        # Add Organizations permissions for multi-account support
        aiml_lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "organizations:ListAccounts",
                "organizations:DescribeOrganization",
            ],
            resources=["*"],
        ))

        # Add STS permissions for cross-account access
        aiml_lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["sts:AssumeRole"],
            resources=["arn:aws:iam::*:role/CostGuardCrossAccountRole"],
        ))

        # Grant DynamoDB permissions
        gpu_costs_table.grant_read_write_data(aiml_lambda_role)
        workload_classifications_table.grant_read_write_data(aiml_lambda_role)
        # Transactional declaration/history Put operations use the granted PutItem permission.
        aiml_cache_table.grant_read_write_data(aiml_lambda_role)

        # Add DynamoDB permissions for multi-account tables (from Phase 5)
        aiml_lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:Query",
                "dynamodb:Scan",
            ],
            resources=[
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/costguard-organizations",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/costguard-accounts",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/costguard-multi-account-costs",
            ],
        ))

        # =====================================================================
        # Lambda Function
        # =====================================================================

        gpu_history_table = self.node.try_get_context('gpu_action_history_table') or os.environ.get('GPU_PREVENTION_ACTIONS_TABLE', '')
        if gpu_history_table:
            if not isinstance(gpu_history_table, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{3,255}', gpu_history_table):
                raise ValueError('gpu_action_history_table must be an existing table name')
            history = dynamodb.Table.from_table_name(self, 'HistoricalGPUActions', gpu_history_table)
            history.grant_read_data(aiml_lambda_role)
        metric_contract = self.node.try_get_context('gpu_utilization_metric_contract')
        gpu_metric_contract = json.dumps(metric_contract) if isinstance(metric_contract, dict) else metric_contract or os.environ.get('GPU_UTILIZATION_METRIC_CONTRACT', '')
        if not isinstance(gpu_metric_contract, str): raise ValueError('GPU metric contract must be an object or JSON string')

        aiml_handler = lambda_.Function(
            self, "AIMLHandler",
            function_name="CostGuard-AIMLHandler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="src.ai_ml_handler.handler",
            code=lambda_.Code.from_asset(
                os.path.join(os.path.dirname(__file__), ".."),  # Project root (parent of infrastructure/)
                exclude=[
                    # Local runtime bundles, credentials and generated output are not Lambda code.
                    ".artifacts", ".artifacts/**", ".aws", ".aws/**",
                    ".env", ".env.*", ".codex", ".agents", "htmlcov",
                    "*.key", "*.pem", "*.whl", "*.zip", "*.tar.gz", "*.tgz", "cdk.context.json",
                    "**/__pycache__", "**/*.pyc", "node_modules",
                    "cdk.out",
                    "infrastructure",
                    ".git",
                    ".github",
                    ".hypothesis",
                    ".kiro",
                    "tests",
                    "docs",
                    "scripts",
                    "htmlcov",
                    "*.md",
                    ".coverage",
                    ".coveragerc",
                    ".pytest_cache",
                    ".ruff_cache",
                    "__pycache__",
                    "*.pyc",
                    "*.pyo",
                    "*.pyd",
                    ".venv",
                    "venv",
                    "env",
                    ".env",
                    "*.egg-info",
                    "dist",
                    "build",
                    ".mypy_cache",
                    ".tox",
                    "*.log",
                    "*.txt",
                    "*.ps1",
                    "*.py[cod]",
                    "*$py.class",
                ]
            ),
            role=aiml_lambda_role,
            timeout=Duration.minutes(5),
            memory_size=512,
            environment={
                "BACKEND_API_KEY": self.node.try_get_context("bff_aiml_key") or os.environ.get("BFF_AIML_API_KEY", ""),
                "BACKEND_ACCOUNT_ID": Stack.of(self).account,
                "ALLOW_DIRECT_API_KEYS": self.node.try_get_context("allow_direct_api_keys") or "false",
                "GPU_COSTS_TABLE": gpu_costs_table.table_name,
                "GPU_PREVENTION_ACTIONS_TABLE": gpu_history_table,
                "GPU_UTILIZATION_METRIC_CONTRACT": gpu_metric_contract,
                "WORKLOAD_CLASSIFICATIONS_TABLE": workload_classifications_table.table_name,
                "AIML_CACHE_TABLE": aiml_cache_table.table_name,
                "ORGANIZATIONS_TABLE": "costguard-organizations",
                "ACCOUNTS_TABLE": "costguard-accounts",
                "MULTI_ACCOUNT_COSTS_TABLE": "costguard-multi-account-costs",
                "CROSS_ACCOUNT_ROLE_NAME": "CostGuardCrossAccountRole",
                "CACHE_TTL_SECONDS": "3600",  # 1 hour
                "LOG_LEVEL": "INFO",
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # =====================================================================
        # CloudWatch Log Group
        # =====================================================================

        aiml_log_group = logs.LogGroup(
            self, "AIMLLogGroup",
            log_group_name=f"/aws/lambda/{aiml_handler.function_name}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # =====================================================================
        # API Gateway
        # =====================================================================

        aiml_api = apigateway.RestApi(
            self, "AIMLAPI",
            rest_api_name="CostGuard-AIMLAPI",
            description="REST API for CostGuard AI/ML Workload Cost Management",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
            ),
        )

        # Lambda integration
        aiml_integration = apigateway.LambdaIntegration(aiml_handler)

        # Create /api resource
        api_resource = aiml_api.root.add_resource("api")

        # Create /ai-ml resource
        aiml_resource = api_resource.add_resource("ai-ml")

        # GPU cost tracking endpoints
        gpu_costs = aiml_resource.add_resource("gpu-costs")
        gpu_costs.add_method("GET", aiml_integration)

        gpu_utilization = aiml_resource.add_resource("gpu-utilization")
        gpu_utilization.add_method("GET", aiml_integration)

        idle_gpus = aiml_resource.add_resource("idle-gpus")
        idle_gpus.add_method("GET", aiml_integration)

        gpu_prevention = aiml_resource.add_resource("gpu-prevention")
        gpu_prevention.add_method("POST", aiml_integration)

        gpu_cost_savings = aiml_resource.add_resource("gpu-cost-savings")
        gpu_cost_savings.add_method("GET", aiml_integration)

        # Workload classification endpoints
        workload_classification = aiml_resource.add_resource("workload-classification")
        workload_classification.add_method("GET", aiml_integration)
        workload_classification.add_method("POST", aiml_integration)

        # Cost per inference endpoints
        cost_per_inference = aiml_resource.add_resource("cost-per-inference")
        cost_per_inference.add_method("GET", aiml_integration)

        inference_trends = aiml_resource.add_resource("inference-trends")
        inference_trends.add_method("GET", aiml_integration)

        # Cost per training endpoints
        cost_per_training = aiml_resource.add_resource("cost-per-training")
        cost_per_training.add_method("GET", aiml_integration)

        training_comparison = aiml_resource.add_resource("training-comparison")
        training_comparison.add_method("GET", aiml_integration)

        # Spot instance recommendation endpoints
        spot_recommendations = aiml_resource.add_resource("spot-recommendations")
        spot_recommendations.add_method("GET", aiml_integration)

        spot_savings = aiml_resource.add_resource("spot-savings")
        spot_savings.add_method("GET", aiml_integration)

        # SageMaker cost tracking endpoints
        sagemaker_costs = aiml_resource.add_resource("sagemaker-costs")
        sagemaker_costs.add_method("GET", aiml_integration)

        sagemaker_idle_endpoints = aiml_resource.add_resource("sagemaker-idle-endpoints")
        sagemaker_idle_endpoints.add_method("GET", aiml_integration)

        # Bedrock cost tracking endpoints
        bedrock_costs = aiml_resource.add_resource("bedrock-costs")
        bedrock_costs.add_method("GET", aiml_integration)

        bedrock_cost_per_invocation = aiml_resource.add_resource("bedrock-cost-per-invocation")
        bedrock_cost_per_invocation.add_method("GET", aiml_integration)

        # Multi-account GPU cost endpoints
        multi_account = aiml_resource.add_resource("multi-account")

        multi_account_gpu_costs = multi_account.add_resource("gpu-costs")
        multi_account_gpu_costs.add_method("GET", aiml_integration)

        multi_account_gpu_utilization = multi_account.add_resource("gpu-utilization")
        multi_account_gpu_utilization.add_method("GET", aiml_integration)

        multi_account_top_gpu_accounts = multi_account.add_resource("top-gpu-accounts")
        multi_account_top_gpu_accounts.add_method("GET", aiml_integration)

        # =====================================================================
        # CloudWatch Alarms
        # =====================================================================

        # Lambda errors alarm
        lambda_errors_alarm = cloudwatch.Alarm(
            self, "LambdaErrorsAlarm",
            alarm_name="CostGuard-AIML-LambdaErrors",
            alarm_description="Alert when AI/ML Lambda errors exceed 5 per hour",
            metric=aiml_handler.metric_errors(period=Duration.hours(1)),
            threshold=5,
            evaluation_periods=1,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )

        # API response time alarm
        api_response_time_alarm = cloudwatch.Alarm(
            self, "APIResponseTimeAlarm",
            alarm_name="CostGuard-AIML-APIResponseTime",
            alarm_description="Alert when AI/ML API response time exceeds 5 seconds",
            metric=aiml_handler.metric_duration(
                period=Duration.minutes(5),
                statistic="Average",
            ),
            threshold=5000,  # 5 seconds in milliseconds
            evaluation_periods=3,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )

        # =====================================================================
        # SNS Topic for Notifications
        # =====================================================================

        aiml_notifications_topic = sns.Topic(
            self, "AIMLNotificationsTopic",
            topic_name="costguard-aiml-notifications",
            display_name="CostGuard AI/ML Notifications",
        )

        # Subscribe alarms to SNS topic
        lambda_errors_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(aiml_notifications_topic)
        )
        api_response_time_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(aiml_notifications_topic)
        )

        # Grant SNS publish permissions
        aiml_notifications_topic.grant_publish(aiml_lambda_role)

        # =====================================================================
        # Outputs
        # =====================================================================

        CfnOutput(
            self, "AIMLAPIEndpoint",
            value=aiml_api.url,
            description="AI/ML API Gateway endpoint",
        )

        CfnOutput(
            self, "AIMLHandlerFunctionName",
            value=aiml_handler.function_name,
            description="AI/ML Handler Lambda function name",
        )

        CfnOutput(
            self, "NotificationsTopicArn",
            value=aiml_notifications_topic.topic_arn,
            description="SNS topic for AI/ML notifications",
        )

        CfnOutput(
            self, "GPUCostsTableName",
            value=gpu_costs_table.table_name,
            description="GPU Costs DynamoDB table name",
        )

        CfnOutput(
            self, "WorkloadClassificationsTableName",
            value=workload_classifications_table.table_name,
            description="Workload Classifications DynamoDB table name",
        )

        CfnOutput(
            self, "AIMLCacheTableName",
            value=aiml_cache_table.table_name,
            description="AI/ML Cache DynamoDB table name",
        )
