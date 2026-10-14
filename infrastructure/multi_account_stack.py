"""
AWS CDK Infrastructure Stack for Multi-Account Cost Management (Phase 5)

This CDK stack extends the existing CostGuard infrastructure to support
multi-account cost management across AWS Organizations.

Includes:
- Multi-account DynamoDB tables (organizations, accounts, costs, rules, budgets)
- Multi-account Lambda functions (cost collector, API handler, main handler)
- Extended API Gateway with multi-account endpoints
- Cross-account IAM roles and permissions
- EventBridge rules for automated cost collection
- CloudWatch alarms for monitoring
- SNS topics for notifications

Requirements: All Phase 5 multi-account requirements
"""

import os

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_apigateway as apigateway,
    aws_sns as sns,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_logs as logs,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    CfnOutput,
)
from constructs import Construct


class MultiAccountStack(Stack):
    """
    CDK Stack for Multi-Account Cost Management (Phase 5).
    
    Extends the existing CostGuard infrastructure with multi-account capabilities.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # =====================================================================
        # Multi-Account DynamoDB Tables
        # =====================================================================

        # Organizations table - cache organization structure
        organizations_table = dynamodb.Table(
            self, "OrganizationsTable",
            table_name="costguard-organizations",
            partition_key=dynamodb.Attribute(
                name="org_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            time_to_live_attribute="ttl",  # 24-hour cache expiration
            point_in_time_recovery=False,  # Free tier constraint
        )

        # Accounts table - store account metadata
        accounts_table = dynamodb.Table(
            self, "AccountsTable",
            table_name="costguard-accounts",
            partition_key=dynamodb.Attribute(
                name="account_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            point_in_time_recovery=False,  # Free tier constraint
        )

        # Add GSI for querying accounts by organization
        accounts_table.add_global_secondary_index(
            index_name="org_id-index",
            partition_key=dynamodb.Attribute(
                name="org_id",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Multi-account costs table - store cost data by account
        multi_account_costs_table = dynamodb.Table(
            self, "MultiAccountCostsTable",
            table_name="costguard-multi-account-costs",
            partition_key=dynamodb.Attribute(
                name="account_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="date",
                type=dynamodb.AttributeType.STRING  # YYYY-MM-DD format
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            point_in_time_recovery=False,  # Free tier constraint
        )

        # Add GSI for querying costs by date across accounts
        multi_account_costs_table.add_global_secondary_index(
            index_name="date-index",
            partition_key=dynamodb.Attribute(
                name="date",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Allocation rules table - store cost allocation rules
        allocation_rules_table = dynamodb.Table(
            self, "AllocationRulesTable",
            table_name="costguard-allocation-rules",
            partition_key=dynamodb.Attribute(
                name="rule_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            point_in_time_recovery=False,  # Free tier constraint
        )

        # Add GSI for querying rules by organization and priority
        allocation_rules_table.add_global_secondary_index(
            index_name="org_id-priority-index",
            partition_key=dynamodb.Attribute(
                name="org_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="priority",
                type=dynamodb.AttributeType.NUMBER
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Budgets table - store organization/OU/account budgets
        budgets_table = dynamodb.Table(
            self, "BudgetsTable",
            table_name="costguard-budgets",
            partition_key=dynamodb.Attribute(
                name="budget_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            point_in_time_recovery=False,  # Free tier constraint
        )

        # Add GSI for querying budgets by entity (org/OU/account)
        budgets_table.add_global_secondary_index(
            index_name="entity_id-type-index",
            partition_key=dynamodb.Attribute(
                name="entity_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="entity_type",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # =====================================================================
        # IAM Roles for Multi-Account Access
        # =====================================================================

        # Multi-account Lambda execution role
        business_metrics_table = dynamodb.Table(self, "BusinessMetricsTable",
            table_name="costguard-business-metrics", partition_key=dynamodb.Attribute(name="metric_key", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="date", type=dynamodb.AttributeType.STRING), billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST, removal_policy=RemovalPolicy.RETAIN)

        organization_policies_table = dynamodb.Table(self, "OrganizationPoliciesTable",
            table_name="costguard-organization-policies", partition_key=dynamodb.Attribute(name="scope_key", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST, removal_policy=RemovalPolicy.RETAIN)

        multi_account_lambda_role = iam.Role(
            self, "MultiAccountLambdaRole",
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

        # Add AWS Organizations permissions
        multi_account_lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "organizations:ListAccounts",
                "organizations:ListOrganizationalUnitsForParent",
                "organizations:ListRoots",
                "organizations:DescribeOrganization",
                "organizations:ListParents",
                "organizations:ListChildren",
            ],
            resources=["*"],
        ))

        # Add STS permissions for cross-account role assumption
        multi_account_lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["sts:AssumeRole"],
            resources=["arn:aws:iam::*:role/CostGuardCrossAccountRole"],
        ))

        # Add Cost Explorer permissions (for management account)
        multi_account_lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ce:GetCostAndUsage",
                "ce:GetCostForecast",
                "ce:GetReservationUtilization", "ce:GetReservationCoverage",
                "ce:GetSavingsPlansUtilization", "ce:GetSavingsPlansCoverage", "ce:GetSavingsPlansUtilizationDetails",
                "ce:GetUsageForecast",
                "ce:ListCostCategoryDefinitions",
                "ce:GetCostCategories",
            ],
            resources=["*"],
        ))

        # Add Bedrock permissions for AI advisor
        multi_account_lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["bedrock:InvokeModel"],
            resources=[
                f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0",
                f"arn:aws:bedrock:{self.region}::foundation-model/amazon.nova-lite-v1:0"
            ],
        ))

        # Grant DynamoDB permissions for all multi-account tables
        organizations_table.grant_read_write_data(multi_account_lambda_role)
        accounts_table.grant_read_write_data(multi_account_lambda_role)
        multi_account_costs_table.grant_read_write_data(multi_account_lambda_role)
        allocation_rules_table.grant_read_write_data(multi_account_lambda_role)
        budgets_table.grant_read_write_data(multi_account_lambda_role)
        organization_policies_table.grant_read_write_data(multi_account_lambda_role)
        business_metrics_table.grant_read_write_data(multi_account_lambda_role)

        # Add DynamoDB permissions for API authentication tables
        # These tables are created separately by setup_api_auth.py
        multi_account_lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:Query",
                "dynamodb:Scan",
            ],
            resources=[
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/costguard-api-keys",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/costguard-rate-limits",
            ],
        ))

        # =====================================================================
        # Lambda Functions
        # =====================================================================

        # Multi-account cost collector Lambda
        multi_account_cost_collector = lambda_.Function(
            self, "MultiAccountCostCollector",
            function_name="CostGuard-MultiAccountCostCollector",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="src.multi_account_cost_collector_handler.lambda_handler",
            code=lambda_.Code.from_asset(
                os.path.join(os.path.dirname(__file__), ".."),  # Repository root
                exclude=[
                    # Local runtime bundles, credentials and generated output are not Lambda code.
                    ".artifacts", ".artifacts/**", ".aws", ".aws/**",
                    ".env", ".env.*", ".codex", ".agents", "htmlcov",
                    "*.key", "*.pem", "*.whl", "*.zip", "*.tar.gz", "*.tgz", "cdk.context.json",
                    "**/__pycache__", "**/*.pyc", "node_modules",
                    "cdk.out/*",
                    "infrastructure/cdk.out/*",
                    "infrastructure/*",
                    ".git/*",
                    ".hypothesis/*",
                    ".kiro/*",
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
            role=multi_account_lambda_role,
            timeout=Duration.minutes(15),
            memory_size=1024,  # Higher memory for parallel processing
            environment={
                "COLLECT_ALLOCATION_TAGS": "true",
                "EXTERNAL_ID": self.node.try_get_context("cross_account_external_id") or os.environ.get("EXTERNAL_ID", ""),
                "ORGANIZATIONS_TABLE": organizations_table.table_name,
                "ACCOUNTS_TABLE": accounts_table.table_name,
                "MULTI_ACCOUNT_COSTS_TABLE": multi_account_costs_table.table_name,
                "ALLOCATION_RULES_TABLE": allocation_rules_table.table_name,
                "BUDGETS_TABLE": budgets_table.table_name,
                "BUSINESS_METRICS_TABLE": business_metrics_table.table_name,
                "ORGANIZATION_POLICIES_TABLE": organization_policies_table.table_name,
                "CROSS_ACCOUNT_ROLE_NAME": "CostGuardCrossAccountRole",
                "MAX_PARALLEL_ACCOUNTS": "10",  # Configurable: Number of accounts processed in parallel (default: 10)
                "COLLECTION_TIMEOUT_SECONDS": "60",
                "LOG_LEVEL": "INFO",
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Multi-account API handler Lambda
        multi_account_api_handler = lambda_.Function(
            self, "MultiAccountAPIHandler",
            function_name="CostGuard-MultiAccountAPIHandler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="src.multi_account_api_handler.handler",
            code=lambda_.Code.from_asset(
                os.path.join(os.path.dirname(__file__), ".."),  # Repository root
                exclude=[
                    # Local runtime bundles, credentials and generated output are not Lambda code.
                    ".artifacts", ".artifacts/**", ".aws", ".aws/**",
                    ".env", ".env.*", ".codex", ".agents", "htmlcov",
                    "*.key", "*.pem", "*.whl", "*.zip", "*.tar.gz", "*.tgz", "cdk.context.json",
                    "**/__pycache__", "**/*.pyc", "node_modules",
                    "cdk.out/*",
                    "infrastructure/cdk.out/*",
                    "infrastructure/*",
                    ".git/*",
                    ".hypothesis/*",
                    ".kiro/*",
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
            role=multi_account_lambda_role,
            timeout=Duration.minutes(5),
            memory_size=512,
            environment={
                "COLLECT_ALLOCATION_TAGS": "true",
                "EXTERNAL_ID": self.node.try_get_context("cross_account_external_id") or os.environ.get("EXTERNAL_ID", ""),
                "ORGANIZATIONS_TABLE": organizations_table.table_name,
                "ACCOUNTS_TABLE": accounts_table.table_name,
                "MULTI_ACCOUNT_COSTS_TABLE": multi_account_costs_table.table_name,
                "ALLOCATION_RULES_TABLE": allocation_rules_table.table_name,
                "BUDGETS_TABLE": budgets_table.table_name,
                "BUSINESS_METRICS_TABLE": business_metrics_table.table_name,
                "ORGANIZATION_POLICIES_TABLE": organization_policies_table.table_name,
                "API_RATE_LIMIT_PER_MINUTE": "100",
                "CACHE_TTL_SECONDS": "3600",  # 1 hour
                "LOG_LEVEL": "INFO",
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Configurable organization sync frequency (default: 4 hours)
        # Can be overridden via CDK context: cdk deploy -c org-sync-hours=2
        org_sync_hours = self.node.try_get_context("org-sync-hours") or 4

        # Multi-account main handler Lambda
        multi_account_handler = lambda_.Function(
            self, "MultiAccountHandler",
            function_name="CostGuard-MultiAccountHandler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="src.multi_account_handler.handler",
            code=lambda_.Code.from_asset(
                os.path.join(os.path.dirname(__file__), ".."),  # Repository root
                exclude=[
                    # Local runtime bundles, credentials and generated output are not Lambda code.
                    ".artifacts", ".artifacts/**", ".aws", ".aws/**",
                    ".env", ".env.*", ".codex", ".agents", "htmlcov",
                    "*.key", "*.pem", "*.whl", "*.zip", "*.tar.gz", "*.tgz", "cdk.context.json",
                    "**/__pycache__", "**/*.pyc", "node_modules",
                    "cdk.out/*",
                    "infrastructure/cdk.out/*",
                    "infrastructure/*",
                    ".git/*",
                    ".hypothesis/*",
                    ".kiro/*",
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
            role=multi_account_lambda_role,
            timeout=Duration.minutes(10),
            memory_size=1024,
            environment={
                "COLLECT_ALLOCATION_TAGS": "true",
                "EXTERNAL_ID": self.node.try_get_context("cross_account_external_id") or os.environ.get("EXTERNAL_ID", ""),
                "ORGANIZATIONS_TABLE": organizations_table.table_name,
                "ACCOUNTS_TABLE": accounts_table.table_name,
                "MULTI_ACCOUNT_COSTS_TABLE": multi_account_costs_table.table_name,
                "ALLOCATION_RULES_TABLE": allocation_rules_table.table_name,
                "BUDGETS_TABLE": budgets_table.table_name,
                "BUSINESS_METRICS_TABLE": business_metrics_table.table_name,
                "ORGANIZATION_POLICIES_TABLE": organization_policies_table.table_name,
                "CROSS_ACCOUNT_ROLE_NAME": "CostGuardCrossAccountRole",
                "MAX_PARALLEL_ACCOUNTS": "10",  # Configurable: Number of accounts processed in parallel (default: 10)
                "ORG_CACHE_TTL_HOURS": str(org_sync_hours * 6),  # Cache TTL = 6x sync frequency (default: 24 hours)
                "LOG_LEVEL": "INFO",
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # =====================================================================
        # CloudWatch Log Groups
        # =====================================================================

        # Log group for multi-account cost collector
        cost_collector_log_group = logs.LogGroup(
            self, "CostCollectorLogGroup",
            log_group_name=f"/aws/lambda/{multi_account_cost_collector.function_name}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Log group for multi-account API handler
        api_handler_log_group = logs.LogGroup(
            self, "APIHandlerLogGroup",
            log_group_name=f"/aws/lambda/{multi_account_api_handler.function_name}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Log group for multi-account main handler
        main_handler_log_group = logs.LogGroup(
            self, "MainHandlerLogGroup",
            log_group_name=f"/aws/lambda/{multi_account_handler.function_name}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # =====================================================================
        # API Gateway Extensions
        # =====================================================================

        # Create new API Gateway for multi-account endpoints
        multi_account_api = apigateway.RestApi(
            self, "MultiAccountAPI",
            rest_api_name="CostGuard-MultiAccountAPI",
            description="REST API for CostGuard Multi-Account Cost Management",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
            ),
        )

        # Lambda integration for multi-account API
        multi_account_integration = apigateway.LambdaIntegration(multi_account_api_handler)

        # Create /api resource
        api_resource = multi_account_api.root.add_resource("api")

        # Organizations endpoints
        organizations_resource = api_resource.add_resource("organizations")
        organizations_resource.add_method("GET", multi_account_integration)

        org_accounts_resource = organizations_resource.add_resource("{org_id}").add_resource("accounts")
        org_accounts_resource.add_method("GET", multi_account_integration)

        # Costs endpoints
        costs_resource = api_resource.add_resource("costs")
        
        consolidated_costs = costs_resource.add_resource("consolidated")
        consolidated_costs.add_method("GET", multi_account_integration)

        costs_by_account = costs_resource.add_resource("by-account")
        costs_by_account.add_method("GET", multi_account_integration)

        account_costs = costs_resource.add_resource("account").add_resource("{account_id}")
        account_costs.add_method("GET", multi_account_integration)

        # Scoped showback/chargeback reporting
        reports_resource = api_resource.add_resource("reports")
        reports_resource.add_resource("showback").add_method("GET", multi_account_integration)
        reports_resource.add_resource("chargeback").add_method("GET", multi_account_integration)

        forecasts_resource = api_resource.add_resource("forecasts")
        forecasts_resource.add_resource("organization").add_method("GET", multi_account_integration)
        forecasts_resource.add_resource("account").add_resource("{account_id}").add_method("GET", multi_account_integration)
        api_resource.add_resource("organization-advisor").add_resource("query").add_method("POST", multi_account_integration)

        policies_resource = api_resource.add_resource("organization-policies")
        policies_resource.add_resource("effective").add_resource("{account_id}").add_method("GET", multi_account_integration)
        policy_item = policies_resource.add_resource("{scope}").add_resource("{entity_id}")
        policy_item.add_method("GET", multi_account_integration)
        policy_item.add_method("PUT", multi_account_integration)

        business_metric_item = api_resource.add_resource("business-metrics").add_resource("{account_id}")
        business_metric_item.add_method("PUT", multi_account_integration)
        business_metric_item.add_method("GET", multi_account_integration)
        api_resource.add_resource("unit-economics").add_method("GET", multi_account_integration)

        api_resource.add_resource("commitments").add_resource("analytics").add_method("GET", multi_account_integration)

        # Allocation endpoints
        allocation_resource = api_resource.add_resource("allocation")
        
        allocation_by_tag = allocation_resource.add_resource("by-tag")
        allocation_by_tag.add_method("GET", multi_account_integration)

        unallocated_costs = allocation_resource.add_resource("unallocated")
        unallocated_costs.add_method("GET", multi_account_integration)

        allocation_rules = allocation_resource.add_resource("rules")
        allocation_rules.add_method("GET", multi_account_integration)
        allocation_rules.add_method("POST", multi_account_integration)

        # Budget endpoints
        budgets_resource = api_resource.add_resource("budgets")
        
        budget_hierarchy = budgets_resource.add_resource("hierarchy")
        budget_hierarchy.add_method("GET", multi_account_integration)

        org_budget = budgets_resource.add_resource("organization")
        org_budget.add_method("POST", multi_account_integration)

        ou_budget = budgets_resource.add_resource("ou").add_resource("{ou_id}")
        ou_budget.add_method("POST", multi_account_integration)

        # =====================================================================
        # EventBridge Rules
        # =====================================================================

        # Daily cost collection rule
        daily_cost_collection_rule = events.Rule(
            self, "DailyCostCollectionRule",
            rule_name="costguard-daily-cost-collection",
            description="Trigger multi-account cost collection daily at 6 AM UTC",
            schedule=events.Schedule.cron(minute="0", hour="6"),
        )

        daily_cost_collection_rule.add_target(
            targets.LambdaFunction(
                multi_account_cost_collector,
                event=events.RuleTargetInput.from_object({
                    "type": "daily-collection",
                    "source": "eventbridge-scheduler",
                }),
            )
        )

        # Organization discovery refresh rule
        # Uses org_sync_hours defined above (configurable via CDK context)
        org_discovery_rule = events.Rule(
            self, "OrganizationDiscoveryRule",
            rule_name="costguard-organization-discovery",
            description=f"Refresh organization structure every {org_sync_hours} hours",
            schedule=events.Schedule.rate(Duration.hours(org_sync_hours)),
        )

        org_discovery_rule.add_target(
            targets.LambdaFunction(
                multi_account_handler,
                event=events.RuleTargetInput.from_object({
                    "operation": "discover_organization",
                    "source": "eventbridge-scheduler",
                }),
            )
        )

        # =====================================================================
        # CloudWatch Alarms
        # =====================================================================

        # Cost collection failure rate alarm
        cost_collection_failure_alarm = cloudwatch.Alarm(
            self, "CostCollectionFailureAlarm",
            alarm_name="CostGuard-CostCollectionFailureRate",
            alarm_description="Alert when cost collection failure rate exceeds 10%",
            metric=multi_account_cost_collector.metric_errors(
                period=Duration.minutes(15),
                statistic="Sum",
            ),
            threshold=1,  # More than 1 error in 15 minutes
            evaluation_periods=2,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )

        # API response time alarm
        api_response_time_alarm = cloudwatch.Alarm(
            self, "APIResponseTimeAlarm",
            alarm_name="CostGuard-APIResponseTime",
            alarm_description="Alert when API response time exceeds 5 seconds",
            metric=multi_account_api_handler.metric_duration(
                period=Duration.minutes(5),
                statistic="Average",
            ),
            threshold=5000,  # 5 seconds in milliseconds
            evaluation_periods=3,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )

        # Lambda errors alarm
        lambda_errors_alarm = cloudwatch.Alarm(
            self, "LambdaErrorsAlarm",
            alarm_name="CostGuard-LambdaErrors",
            alarm_description="Alert when Lambda errors exceed 5 per hour",
            metric=cloudwatch.MathExpression(
                expression="e1 + e2 + e3",
                using_metrics={
                    "e1": multi_account_cost_collector.metric_errors(period=Duration.hours(1)),
                    "e2": multi_account_api_handler.metric_errors(period=Duration.hours(1)),
                    "e3": multi_account_handler.metric_errors(period=Duration.hours(1)),
                },
            ),
            threshold=5,
            evaluation_periods=1,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )

        # DynamoDB throttling alarm
        dynamodb_throttle_alarm = cloudwatch.Alarm(
            self, "DynamoDBThrottleAlarm",
            alarm_name="CostGuard-DynamoDBThrottling",
            alarm_description="Alert when DynamoDB throttling occurs",
            metric=cloudwatch.Metric(
                namespace="CostGuard/MultiAccount",
                metric_name="DynamoDB.Throttles",
                statistic="Sum",
                period=Duration.minutes(5),
            ),
            threshold=0,  # Any throttling is concerning
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )

        # =====================================================================
        # SNS Topics for Notifications
        # =====================================================================

        multi_account_notifications_topic = sns.Topic(
            self, "MultiAccountNotificationsTopic",
            topic_name="costguard-multi-account-notifications",
            display_name="CostGuard Multi-Account Notifications",
        )

        # Subscribe alarms to SNS topic
        cost_collection_failure_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(multi_account_notifications_topic)
        )
        api_response_time_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(multi_account_notifications_topic)
        )
        lambda_errors_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(multi_account_notifications_topic)
        )
        dynamodb_throttle_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(multi_account_notifications_topic)
        )
        lambda_errors_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(multi_account_notifications_topic)
        )

        # Grant SNS publish permissions to Lambda functions
        multi_account_notifications_topic.grant_publish(multi_account_lambda_role)

        # =====================================================================
        # Outputs
        # =====================================================================

        CfnOutput(
            self, "MultiAccountAPIEndpoint",
            value=multi_account_api.url,
            description="Multi-Account API Gateway endpoint",
        )

        CfnOutput(
            self, "CostCollectorFunctionName",
            value=multi_account_cost_collector.function_name,
            description="Multi-Account Cost Collector Lambda function name",
        )

        CfnOutput(
            self, "APIHandlerFunctionName",
            value=multi_account_api_handler.function_name,
            description="Multi-Account API Handler Lambda function name",
        )

        CfnOutput(
            self, "MainHandlerFunctionName",
            value=multi_account_handler.function_name,
            description="Multi-Account Main Handler Lambda function name",
        )

        CfnOutput(
            self, "NotificationsTopicArn",
            value=multi_account_notifications_topic.topic_arn,
            description="SNS topic for multi-account notifications",
        )

        CfnOutput(
            self, "OrganizationsTableName",
            value=organizations_table.table_name,
            description="Organizations DynamoDB table name",
        )

        CfnOutput(
            self, "AccountsTableName",
            value=accounts_table.table_name,
            description="Accounts DynamoDB table name",
        )

        CfnOutput(
            self, "MultiAccountCostsTableName",
            value=multi_account_costs_table.table_name,
            description="Multi-Account Costs DynamoDB table name",
        )

        CfnOutput(
            self, "AllocationRulesTableName",
            value=allocation_rules_table.table_name,
            description="Allocation Rules DynamoDB table name",
        )

        CfnOutput(
            self, "BudgetsTableName",
            value=budgets_table.table_name,
            description="Budgets DynamoDB table name",
        )