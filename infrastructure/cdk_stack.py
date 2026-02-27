"""
AWS CDK Infrastructure Stack for CostGuard

This CDK stack defines all infrastructure for CostGuard Phases 1, 1.5, 2, and 3:
- DynamoDB tables for cost data, forecasts, prevention config, inventory, audit, and approvals
- Lambda function with appropriate IAM permissions
- API Gateway REST API with all endpoints
- SNS topics for notifications
- EventBridge schedule for automated budget monitoring
- All necessary IAM roles and permissions

Requirements: All infrastructure requirements across all phases
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_apigateway as apigateway,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_logs as logs,
    CfnOutput,
)
from constructs import Construct


class CostGuardStack(Stack):
    """
    CDK Stack for CostGuard cost management and automated prevention system.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # =====================================================================
        # DynamoDB Tables
        # =====================================================================

        # Phase 1: Cost data storage
        cost_data_table = dynamodb.Table(
            self, "CostDataTable",
            table_name="costguard-cost-data",
            partition_key=dynamodb.Attribute(
                name="date_service",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            point_in_time_recovery=True,
        )

        # Phase 2: Forecast cache
        forecast_cache_table = dynamodb.Table(
            self, "ForecastCacheTable",
            table_name="costguard-forecast-cache",
            partition_key=dynamodb.Attribute(
                name="cache_key",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            time_to_live_attribute="ttl",
        )

        # Phase 3: Prevention configuration
        prevention_config_table = dynamodb.Table(
            self, "PreventionConfigTable",
            table_name="costguard-prevention-config",
            partition_key=dynamodb.Attribute(
                name="config_key",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Phase 3: Resource inventory
        resource_inventory_table = dynamodb.Table(
            self, "ResourceInventoryTable",
            table_name="costguard-resource-inventory",
            partition_key=dynamodb.Attribute(
                name="resource_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            time_to_live_attribute="ttl",
        )

        # Add GSI for service-based queries
        resource_inventory_table.add_global_secondary_index(
            index_name="service-index",
            partition_key=dynamodb.Attribute(
                name="service",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="last_updated",
                type=dynamodb.AttributeType.NUMBER
            ),
        )

        # Phase 3: Prevention audit log
        prevention_audit_table = dynamodb.Table(
            self, "PreventionAuditTable",
            table_name="costguard-prevention-audit",
            partition_key=dynamodb.Attribute(
                name="action_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            time_to_live_attribute="ttl",
        )

        # Add GSIs for audit queries
        prevention_audit_table.add_global_secondary_index(
            index_name="timestamp-index",
            partition_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.NUMBER
            ),
        )

        prevention_audit_table.add_global_secondary_index(
            index_name="resource-index",
            partition_key=dynamodb.Attribute(
                name="resource_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.NUMBER
            ),
        )

        # Phase 3: Approval requests
        approval_requests_table = dynamodb.Table(
            self, "ApprovalRequestsTable",
            table_name="costguard-approval-requests",
            partition_key=dynamodb.Attribute(
                name="request_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            time_to_live_attribute="ttl",
        )

        # Add GSI for status-based queries
        approval_requests_table.add_global_secondary_index(
            index_name="status-index",
            partition_key=dynamodb.Attribute(
                name="status",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.NUMBER
            ),
        )

        # =====================================================================
        # SNS Topics (Phase 3)
        # =====================================================================

        warnings_topic = sns.Topic(
            self, "PreventionWarningsTopic",
            topic_name="costguard-prevention-warnings",
            display_name="CostGuard Prevention Warnings",
        )

        actions_topic = sns.Topic(
            self, "PreventionActionsTopic",
            topic_name="costguard-prevention-actions",
            display_name="CostGuard Prevention Actions",
        )

        errors_topic = sns.Topic(
            self, "PreventionErrorsTopic",
            topic_name="costguard-prevention-errors",
            display_name="CostGuard Prevention Errors",
        )

        # =====================================================================
        # Lambda Function
        # =====================================================================

        # Create Lambda execution role
        lambda_role = iam.Role(
            self, "LambdaExecutionRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("lambda.amazonaws.com"),
                iam.ServicePrincipal("events.amazonaws.com"),
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
        )

        # Add custom policies for CostGuard
        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["budgets:ViewBudget", "budgets:DescribeBudget"],
            resources=["*"],
        ))

        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ce:GetCostAndUsage",
                "ce:GetCostForecast",
            ],
            resources=["*"],
        ))

        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["bedrock:InvokeModel"],
            resources=[
                f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
            ],
        ))

        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ec2:DescribeInstances",
                "ec2:DescribeVolumes",
                "ec2:DescribeNatGateways",
                "ec2:DescribeSnapshots",
                "rds:DescribeDBInstances",
                "rds:DescribeDBClusters",
                "lambda:ListFunctions",
                "lambda:GetFunction",
                "s3:ListAllMyBuckets",
                "s3:GetBucketLocation",
                "s3:GetBucketTagging",
                "dynamodb:ListTables",
                "dynamodb:DescribeTable",
                "elasticache:DescribeCacheClusters",
                "elasticache:DescribeReplicationGroups",
                "sns:ListTopics",
                "sns:GetTopicAttributes",
                "sqs:ListQueues",
                "sqs:GetQueueAttributes",
                "elasticloadbalancing:DescribeLoadBalancers",
                "elasticloadbalancing:DescribeTargetGroups",
                "redshift:DescribeClusters",
                "es:ListDomainNames",
                "es:DescribeElasticsearchDomain",
                "kinesis:ListStreams",
                "kinesis:DescribeStream",
                "ecs:ListClusters",
                "ecs:DescribeClusters",
                "eks:ListClusters",
                "eks:DescribeCluster",
                "cloudfront:ListDistributions",
                "apigateway:GET",
            ],
            resources=["*"],
        ))

        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "cloudwatch:GetMetricStatistics",
                "cloudwatch:GetMetricData",
                "cloudwatch:ListMetrics",
            ],
            resources=["*"],
        ))

        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ec2:StopInstances",
                "ec2:StartInstances",
                "ec2:CreateSnapshot",
                "ec2:DeleteVolume",
                "ec2:CreateVolume",
                "ec2:DeleteNatGateway",
                "rds:StopDBInstance",
                "rds:StartDBInstance",
                "rds:StopDBCluster",
                "rds:StartDBCluster",
                "lambda:PutFunctionConcurrency",
                "lambda:DeleteFunctionConcurrency",
                "dynamodb:UpdateTable",
            ],
            resources=["*"],
            conditions={
                "StringNotEquals": {
                    "aws:ResourceTag/Environment": "production",
                    "aws:ResourceTag/CostGuard": "protected",
                }
            },
        ))

        # Grant DynamoDB permissions
        cost_data_table.grant_read_write_data(lambda_role)
        forecast_cache_table.grant_read_write_data(lambda_role)
        prevention_config_table.grant_read_write_data(lambda_role)
        resource_inventory_table.grant_read_write_data(lambda_role)
        prevention_audit_table.grant_read_write_data(lambda_role)
        approval_requests_table.grant_read_write_data(lambda_role)

        # Grant SNS publish permissions
        warnings_topic.grant_publish(lambda_role)
        actions_topic.grant_publish(lambda_role)
        errors_topic.grant_publish(lambda_role)

        # Create Lambda function
        costguard_lambda = lambda_.Function(
            self, "CostGuardLambda",
            function_name="CostGuardLambda",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="src.lambda_handler.handler",
            code=lambda_.Code.from_asset(
                "../",
                exclude=[
                    "infrastructure/*",
                    "cdk.out/*",
                    ".git/*",
                    ".hypothesis/*",
                    "tests/*",
                    "docs/*",
                    "scripts/*",
                    "*.md",
                    ".coverage",
                    ".pytest_cache/*",
                    "__pycache__/*",
                    "*.pyc",
                    ".venv/*",
                    "venv/*",
                ]
            ),
            role=lambda_role,
            timeout=Duration.minutes(15),
            memory_size=512,
            environment={
                "COST_DATA_TABLE": cost_data_table.table_name,
                "FORECAST_CACHE_TABLE": forecast_cache_table.table_name,
                "PREVENTION_CONFIG_TABLE": prevention_config_table.table_name,
                "RESOURCE_INVENTORY_TABLE": resource_inventory_table.table_name,
                "PREVENTION_AUDIT_TABLE": prevention_audit_table.table_name,
                "APPROVAL_REQUESTS_TABLE": approval_requests_table.table_name,
                "PREVENTION_ENABLED": "false",
                "DRY_RUN_MODE": "true",
                "APPROVAL_REQUIRED": "true",
                "APPROVAL_TIMEOUT_MINUTES": "30",
                "BUDGET_POLL_INTERVAL_MINUTES": "5",
                "RESOURCE_REFRESH_INTERVAL_MINUTES": "15",
                "WARNING_THRESHOLD_PERCENT": "80",
                "ACTION_THRESHOLD_PERCENT": "90",
                "SNS_TOPIC_WARNINGS": warnings_topic.topic_arn,
                "SNS_TOPIC_ACTIONS": actions_topic.topic_arn,
                "SNS_TOPIC_ERRORS": errors_topic.topic_arn,
                "LOG_LEVEL": "INFO",
                "BEDROCK_MODEL_ID": "anthropic.claude-3-sonnet-20240229-v1:0",
                "FORECAST_CACHE_TTL_HOURS": "24",
                "ROLLBACK_WINDOW_HOURS": "24",
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # =====================================================================
        # API Gateway
        # =====================================================================

        api = apigateway.RestApi(
            self, "CostGuardAPI",
            rest_api_name="CostGuardAPI",
            description="REST API for CostGuard cost management and automated prevention",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
            ),
        )

        # Lambda integration
        lambda_integration = apigateway.LambdaIntegration(costguard_lambda)

        # Create /api resource
        api_resource = api.root.add_resource("api")

        # Phase 1 endpoints
        fetch_resource = api_resource.add_resource("fetch")
        fetch_resource.add_method("POST", lambda_integration)

        cost_data_resource = api_resource.add_resource("cost-data")
        cost_data_resource.add_method("GET", lambda_integration)

        # Phase 1.5 endpoints
        cost_estimation_resource = api_resource.add_resource("cost-estimation")
        cost_estimation_current = cost_estimation_resource.add_resource("current")
        cost_estimation_current.add_method("GET", lambda_integration)

        cost_estimation_service = cost_estimation_resource.add_resource("service")
        cost_estimation_service_param = cost_estimation_service.add_resource("{service}")
        cost_estimation_service_param.add_method("GET", lambda_integration)

        # Phase 2 endpoints
        cost_forecast_resource = api_resource.add_resource("cost-forecast")
        cost_forecast_resource.add_method("GET", lambda_integration)

        cost_forecast_service = cost_forecast_resource.add_resource("service")
        cost_forecast_service_param = cost_forecast_service.add_resource("{service}")
        cost_forecast_service_param.add_method("GET", lambda_integration)

        # Phase 3 endpoints
        prevention_resource = api_resource.add_resource("prevention")

        prevention_status = prevention_resource.add_resource("status")
        prevention_status.add_method("GET", lambda_integration)

        prevention_enable = prevention_resource.add_resource("enable")
        prevention_enable.add_method("POST", lambda_integration)

        prevention_disable = prevention_resource.add_resource("disable")
        prevention_disable.add_method("POST", lambda_integration)

        prevention_resources = prevention_resource.add_resource("resources")
        prevention_resources.add_method("GET", lambda_integration)

        prevention_rollback = prevention_resource.add_resource("rollback")
        prevention_rollback.add_method("POST", lambda_integration)

        prevention_history = prevention_resource.add_resource("history")
        prevention_history.add_method("GET", lambda_integration)

        # =====================================================================
        # EventBridge Schedule (Phase 3)
        # =====================================================================

        # Create EventBridge rule for budget monitoring
        budget_monitor_rule = events.Rule(
            self, "BudgetMonitorRule",
            rule_name="costguard-budget-monitor",
            description="Trigger CostGuard Lambda every 5 minutes for budget monitoring",
            schedule=events.Schedule.rate(Duration.minutes(5)),
        )

        # Add Lambda as target
        budget_monitor_rule.add_target(
            targets.LambdaFunction(
                costguard_lambda,
                event=events.RuleTargetInput.from_object({
                    "type": "budget-monitoring",
                    "source": "eventbridge-scheduler",
                }),
            )
        )

        # =====================================================================
        # Outputs
        # =====================================================================

        CfnOutput(
            self, "APIEndpoint",
            value=api.url,
            description="CostGuard API Gateway endpoint",
        )

        CfnOutput(
            self, "LambdaFunctionName",
            value=costguard_lambda.function_name,
            description="CostGuard Lambda function name",
        )

        CfnOutput(
            self, "WarningsTopicArn",
            value=warnings_topic.topic_arn,
            description="SNS topic for prevention warnings",
        )

        CfnOutput(
            self, "ActionsTopicArn",
            value=actions_topic.topic_arn,
            description="SNS topic for prevention actions",
        )

        CfnOutput(
            self, "ErrorsTopicArn",
            value=errors_topic.topic_arn,
            description="SNS topic for prevention errors",
        )
