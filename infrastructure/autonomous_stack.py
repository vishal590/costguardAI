"""
AWS CDK Infrastructure Stack for Autonomous Action Loops

This CDK stack extends the AI/ML Workload Cost Management (Phase 6) with
autonomous capabilities that close the loop from analysis to automated optimization.

Includes:
- DynamoDB tables for action history, training checkpoints, and rollback points
- EventBridge custom event bus for autonomous action orchestration
- S3 bucket for training checkpoints
- SNS topics for approval workflows and alerts
- Lambda functions for autonomous capabilities (added in subsequent tasks)

Requirements: Autonomous Action Loops requirements (1-12)
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    aws_lambda as lambda_,
    aws_s3 as s3,
    aws_sns as sns,
    aws_iam as iam,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    CfnOutput,
)
from constructs import Construct


class AutonomousStack(Stack):
    """
    CDK Stack for Autonomous Action Loops.
    
    Extends the existing AI/ML infrastructure with autonomous optimization capabilities.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # =====================================================================
        # DynamoDB Tables for Autonomous Actions
        # =====================================================================

        # Action history table - stores all autonomous actions and outcomes
        action_history_table = dynamodb.Table(
            self, "ActionHistoryTable",
            table_name="costguard-action-history",
            partition_key=dynamodb.Attribute(
                name="action_id",
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

        # GSI for querying by action type
        action_history_table.add_global_secondary_index(
            index_name="action-type-index",
            partition_key=dynamodb.Attribute(
                name="action_type",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # GSI for querying by status
        action_history_table.add_global_secondary_index(
            index_name="status-index",
            partition_key=dynamodb.Attribute(
                name="status",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Training checkpoints table - stores checkpoint metadata
        training_checkpoints_table = dynamodb.Table(
            self, "TrainingCheckpointsTable",
            table_name="costguard-training-checkpoints",
            partition_key=dynamodb.Attribute(
                name="checkpoint_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            time_to_live_attribute="ttl",
            point_in_time_recovery=False,  # Free tier constraint
        )

        # GSI for querying by training job
        training_checkpoints_table.add_global_secondary_index(
            index_name="training-job-index",
            partition_key=dynamodb.Attribute(
                name="training_job_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Migration rollbacks table - stores rollback points for migrations
        migration_rollbacks_table = dynamodb.Table(
            self, "MigrationRollbacksTable",
            table_name="costguard-migration-rollbacks",
            partition_key=dynamodb.Attribute(
                name="rollback_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            time_to_live_attribute="ttl",
            point_in_time_recovery=False,  # Free tier constraint
        )

        # =====================================================================
        # EventBridge Custom Event Bus
        # =====================================================================

        # Custom event bus for autonomous action orchestration
        autonomous_event_bus = events.EventBus(
            self, "AutonomousEventBus",
            event_bus_name="costguard-autonomous-events",
        )

        # Event archive for debugging (7-day retention)
        events.Archive(
            self, "AutonomousEventArchive",
            archive_name="costguard-autonomous-events-archive",
            source_event_bus=autonomous_event_bus,
            description="Archive of autonomous action events for debugging",
            retention=Duration.days(7),
            event_pattern=events.EventPattern(
                source=["costguard.autonomous"],
            ),
        )

        # =====================================================================
        # S3 Bucket for Training Checkpoints
        # =====================================================================

        # S3 bucket for storing training checkpoints
        checkpoints_bucket = s3.Bucket(
            self, "CheckpointsBucket",
            bucket_name=f"costguard-training-checkpoints-{self.account}-{self.region}",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteOldCheckpoints",
                    enabled=True,
                    expiration=Duration.days(7),
                    noncurrent_version_expiration=Duration.days(1),
                )
            ],
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        # =====================================================================
        # SNS Topics for Notifications
        # =====================================================================

        # SNS topic for approval requests
        approvals_topic = sns.Topic(
            self, "ApprovalsTopic",
            topic_name="costguard-autonomous-approvals",
            display_name="CostGuard Autonomous Action Approvals",
        )

        # SNS topic for error alerts
        alerts_topic = sns.Topic(
            self, "AlertsTopic",
            topic_name="costguard-autonomous-alerts",
            display_name="CostGuard Autonomous Action Alerts",
        )

        # =====================================================================
        # CloudWatch Dashboards
        # =====================================================================

        # Create main autonomous actions dashboard
        dashboard = cloudwatch.Dashboard(
            self, "AutonomousDashboard",
            dashboard_name="CostGuard-Autonomous-Actions",
        )

        # Metric namespace
        metric_namespace = "CostGuard/AIML"

        # Action Success Rate widget
        success_rate_widget = cloudwatch.GraphWidget(
            title="Action Success Rates",
            left=[
                cloudwatch.Metric(
                    namespace=metric_namespace,
                    metric_name="ActionSuccessRate",
                    dimensions_map={"ActionType": "schedule"},
                    statistic="Average",
                    label="GPU Scheduling",
                    period=Duration.minutes(5),
                ),
                cloudwatch.Metric(
                    namespace=metric_namespace,
                    metric_name="ActionSuccessRate",
                    dimensions_map={"ActionType": "spot_migration"},
                    statistic="Average",
                    label="Spot Migration",
                    period=Duration.minutes(5),
                ),
                cloudwatch.Metric(
                    namespace=metric_namespace,
                    metric_name="ActionSuccessRate",
                    dimensions_map={"ActionType": "right_sizing"},
                    statistic="Average",
                    label="Right Sizing",
                    period=Duration.minutes(5),
                ),
            ],
            width=12,
            height=6,
        )

        # Confidence Score widget
        confidence_widget = cloudwatch.GraphWidget(
            title="Average Confidence Score",
            left=[
                cloudwatch.Metric(
                    namespace=metric_namespace,
                    metric_name="ConfidenceScore",
                    statistic="Average",
                    label="Confidence",
                    period=Duration.minutes(5),
                ),
            ],
            width=12,
            height=6,
        )

        # Cumulative Savings widget
        savings_widget = cloudwatch.GraphWidget(
            title="Cumulative Cost Savings",
            left=[
                cloudwatch.Metric(
                    namespace=metric_namespace,
                    metric_name="CumulativeSavings",
                    statistic="Maximum",
                    label="Total Savings ($)",
                    period=Duration.hours(1),
                ),
            ],
            width=12,
            height=6,
        )

        # Active Actions widget
        active_actions_widget = cloudwatch.SingleValueWidget(
            title="Active Actions",
            metrics=[
                cloudwatch.Metric(
                    namespace=metric_namespace,
                    metric_name="ActiveActions",
                    statistic="Sum",
                    label="In Progress",
                    period=Duration.minutes(5),
                ),
            ],
            width=6,
            height=6,
        )

        # Budget Utilization widget
        budget_widget = cloudwatch.GaugeWidget(
            title="Free Tier Budget Utilization",
            metrics=[
                cloudwatch.Metric(
                    namespace=metric_namespace,
                    metric_name="BudgetUtilization",
                    statistic="Average",
                    label="Budget %",
                    period=Duration.minutes(5),
                ),
            ],
            left_y_axis=cloudwatch.YAxisProps(
                min=0,
                max=100,
            ),
            width=6,
            height=6,
        )

        # Add widgets to dashboard
        dashboard.add_widgets(success_rate_widget, confidence_widget)
        dashboard.add_widgets(savings_widget, active_actions_widget, budget_widget)

        # =====================================================================
        # CloudWatch Alarms
        # =====================================================================

        # Alarm for low success rate (<70%)
        low_success_alarm = cloudwatch.Alarm(
            self, "LowSuccessRateAlarm",
            alarm_name="CostGuard-Autonomous-LowSuccessRate",
            alarm_description="Triggered when action success rate falls below 70%",
            metric=cloudwatch.Metric(
                namespace=metric_namespace,
                metric_name="ActionSuccessRate",
                statistic="Average",
                period=Duration.minutes(15),
            ),
            threshold=70,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )

        # Add SNS action to alarm
        low_success_alarm.add_alarm_action(cw_actions.SnsAction(alerts_topic))

        # Alarm for budget exceeded (>90%)
        budget_alarm = cloudwatch.Alarm(
            self, "BudgetExceededAlarm",
            alarm_name="CostGuard-Autonomous-BudgetExceeded",
            alarm_description="Triggered when Free Tier budget utilization exceeds 90%",
            metric=cloudwatch.Metric(
                namespace=metric_namespace,
                metric_name="BudgetUtilization",
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=90,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )

        # Add SNS action to alarm
        budget_alarm.add_alarm_action(cw_actions.SnsAction(alerts_topic))

        # Alarm for low confidence (<0.7)
        low_confidence_alarm = cloudwatch.Alarm(
            self, "LowConfidenceAlarm",
            alarm_name="CostGuard-Autonomous-LowConfidence",
            alarm_description="Triggered when average confidence score falls below 0.7",
            metric=cloudwatch.Metric(
                namespace=metric_namespace,
                metric_name="ConfidenceScore",
                statistic="Average",
                period=Duration.minutes(15),
            ),
            threshold=0.7,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )

        # Add SNS action to alarm
        low_confidence_alarm.add_alarm_action(cw_actions.SnsAction(alerts_topic))

        # =====================================================================
        # Outputs
        # =====================================================================

        CfnOutput(
            self, "ActionHistoryTableName",
            value=action_history_table.table_name,
            description="Action History DynamoDB table name",
        )

        CfnOutput(
            self, "TrainingCheckpointsTableName",
            value=training_checkpoints_table.table_name,
            description="Training Checkpoints DynamoDB table name",
        )

        CfnOutput(
            self, "MigrationRollbacksTableName",
            value=migration_rollbacks_table.table_name,
            description="Migration Rollbacks DynamoDB table name",
        )

        CfnOutput(
            self, "AutonomousEventBusName",
            value=autonomous_event_bus.event_bus_name,
            description="Autonomous Event Bus name",
        )

        CfnOutput(
            self, "AutonomousEventBusArn",
            value=autonomous_event_bus.event_bus_arn,
            description="Autonomous Event Bus ARN",
        )

        CfnOutput(
            self, "CheckpointsBucketName",
            value=checkpoints_bucket.bucket_name,
            description="Training Checkpoints S3 bucket name",
        )

        CfnOutput(
            self, "CheckpointsBucketArn",
            value=checkpoints_bucket.bucket_arn,
            description="Training Checkpoints S3 bucket ARN",
        )

        CfnOutput(
            self, "ApprovalsTopicArn",
            value=approvals_topic.topic_arn,
            description="SNS topic for approval requests",
        )

        CfnOutput(
            self, "AlertsTopicArn",
            value=alerts_topic.topic_arn,
            description="SNS topic for error alerts",
        )

        CfnOutput(
            self, "DashboardName",
            value=dashboard.dashboard_name,
            description="CloudWatch Dashboard name",
        )

        CfnOutput(
            self, "LowSuccessAlarmName",
            value=low_success_alarm.alarm_name,
            description="CloudWatch Alarm for low success rate",
        )

        CfnOutput(
            self, "BudgetAlarmName",
            value=budget_alarm.alarm_name,
            description="CloudWatch Alarm for budget exceeded",
        )

        CfnOutput(
            self, "LowConfidenceAlarmName",
            value=low_confidence_alarm.alarm_name,
            description="CloudWatch Alarm for low confidence",
        )

        # =====================================================================
        # IAM Roles for Lambda Functions (Least-Privilege)
        # =====================================================================

        # GPU Scheduler Role
        gpu_scheduler_role = iam.Role(
            self, "GPUSchedulerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="IAM role for GPU Scheduler Lambda with least-privilege permissions",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
        )

        # GPU Scheduler permissions
        gpu_scheduler_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["dynamodb:Query", "dynamodb:GetItem"],
            resources=[
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/costguard-gpu-costs",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/costguard-gpu-costs/index/*",
            ],
        ))

        gpu_scheduler_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["dynamodb:PutItem"],
            resources=[action_history_table.table_arn],
        ))

        gpu_scheduler_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["events:PutEvents"],
            resources=[autonomous_event_bus.event_bus_arn],
        ))

        gpu_scheduler_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["ec2:DescribeSpotPriceHistory"],
            resources=["*"],
        ))

        # Spot Manager Role
        spot_manager_role = iam.Role(
            self, "SpotManagerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="IAM role for Spot Manager Lambda with least-privilege permissions",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
        )

        # Spot Manager permissions
        spot_manager_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["dynamodb:Query", "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"],
            resources=[
                action_history_table.table_arn,
                training_checkpoints_table.table_arn,
                f"{training_checkpoints_table.table_arn}/index/*",
            ],
        ))

        spot_manager_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
            resources=[f"{checkpoints_bucket.bucket_arn}/*"],
        ))

        spot_manager_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["s3:ListBucket"],
            resources=[checkpoints_bucket.bucket_arn],
        ))

        spot_manager_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ec2:RunInstances",
                "ec2:TerminateInstances",
                "ec2:DescribeInstances",
                "ec2:DescribeInstanceStatus",
            ],
            resources=["*"],
            conditions={
                "StringEquals": {
                    "aws:RequestedRegion": ["us-east-1", "us-west-2"],
                },
            },
        ))

        spot_manager_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["events:PutEvents"],
            resources=[autonomous_event_bus.event_bus_arn],
        ))

        # Right Sizer Role
        right_sizer_role = iam.Role(
            self, "RightSizerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="IAM role for Right Sizer Lambda with least-privilege permissions",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
        )

        # Right Sizer permissions
        right_sizer_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["dynamodb:Query", "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"],
            resources=[
                action_history_table.table_arn,
                f"{action_history_table.table_arn}/index/*",
                migration_rollbacks_table.table_arn,
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/costguard-gpu-costs",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/costguard-workload-classifications",
            ],
        ))

        right_sizer_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ec2:RunInstances",
                "ec2:TerminateInstances",
                "ec2:DescribeInstances",
                "ec2:DescribeInstanceTypes",
                "ec2:ModifyInstanceAttribute",
            ],
            resources=["*"],
        ))

        right_sizer_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["events:PutEvents"],
            resources=[autonomous_event_bus.event_bus_arn],
        ))

        # Learning Engine Role
        learning_engine_role = iam.Role(
            self, "LearningEngineRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="IAM role for Learning Engine Lambda with least-privilege permissions",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
        )

        # Learning Engine permissions
        learning_engine_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["dynamodb:Query", "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Scan"],
            resources=[
                action_history_table.table_arn,
                f"{action_history_table.table_arn}/index/*",
            ],
        ))

        learning_engine_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["events:PutEvents"],
            resources=[autonomous_event_bus.event_bus_arn],
        ))

        learning_engine_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["sns:Publish"],
            resources=[alerts_topic.topic_arn],
        ))

        # Safety Guard Role
        safety_guard_role = iam.Role(
            self, "SafetyGuardRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="IAM role for Safety Guard Lambda with least-privilege permissions",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
        )

        # Safety Guard permissions
        safety_guard_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["dynamodb:Query", "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"],
            resources=[
                action_history_table.table_arn,
                f"{action_history_table.table_arn}/index/*",
            ],
        ))

        safety_guard_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["sns:Publish"],
            resources=[approvals_topic.topic_arn, alerts_topic.topic_arn],
        ))

        safety_guard_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["events:PutEvents"],
            resources=[autonomous_event_bus.event_bus_arn],
        ))

        safety_guard_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["ce:GetCostAndUsage"],
            resources=["*"],
        ))

        safety_guard_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["cloudwatch:GetMetricStatistics"],
            resources=["*"],
        ))

        # =====================================================================
        # Outputs for IAM Roles
        # =====================================================================

        CfnOutput(
            self, "GPUSchedulerRoleArn",
            value=gpu_scheduler_role.role_arn,
            description="IAM role ARN for GPU Scheduler Lambda",
        )

        CfnOutput(
            self, "SpotManagerRoleArn",
            value=spot_manager_role.role_arn,
            description="IAM role ARN for Spot Manager Lambda",
        )

        CfnOutput(
            self, "RightSizerRoleArn",
            value=right_sizer_role.role_arn,
            description="IAM role ARN for Right Sizer Lambda",
        )

        CfnOutput(
            self, "LearningEngineRoleArn",
            value=learning_engine_role.role_arn,
            description="IAM role ARN for Learning Engine Lambda",
        )

        CfnOutput(
            self, "SafetyGuardRoleArn",
            value=safety_guard_role.role_arn,
            description="IAM role ARN for Safety Guard Lambda",
        )

        # =====================================================================
        # Lambda Functions
        # =====================================================================

        # Common environment variables for all Lambda functions
        common_env = {
            "ACTION_HISTORY_TABLE": action_history_table.table_name,
            "EVENT_BUS_NAME": autonomous_event_bus.event_bus_name,
            "DRY_RUN_MODE": "false",
            "DEMO_MODE": "false",
        }

        # GPU Scheduler Lambda
        gpu_scheduler_lambda = lambda_.Function(
            self, "GPUSchedulerFunction",
            function_name="CostGuard-GPU-Scheduler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="autonomous.gpu_scheduler.handler",
            code=lambda_.Code.from_asset("../src"),
            role=gpu_scheduler_role,
            timeout=Duration.minutes(5),
            memory_size=512,
            environment={
                **common_env,
                "GPU_COSTS_TABLE": "costguard-gpu-costs",
                "CONFIDENCE_THRESHOLD": "0.8",
                "MIN_COST_SAVINGS_PERCENT": "20",
            },
            tracing=lambda_.Tracing.ACTIVE,
            description="Analyzes GPU cost patterns and schedules training jobs during optimization windows",
        )

        # Spot Manager Lambda
        spot_manager_lambda = lambda_.Function(
            self, "SpotManagerFunction",
            function_name="CostGuard-Spot-Manager",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="autonomous.spot_manager.handler",
            code=lambda_.Code.from_asset("../src"),
            role=spot_manager_role,
            timeout=Duration.minutes(15),
            memory_size=1024,
            environment={
                **common_env,
                "CHECKPOINT_BUCKET": checkpoints_bucket.bucket_name,
                "TRAINING_CHECKPOINTS_TABLE": training_checkpoints_table.table_name,
                "SPOT_TIMEOUT_SECONDS": "300",
                "CHECKPOINT_TIMEOUT_SECONDS": "30",
                "APPROVAL_REQUIRED_FOR_ONDEMAND": "true",
            },
            tracing=lambda_.Tracing.ACTIVE,
            description="Handles spot instance interruptions with automatic checkpoint save/restore",
        )

        # Right Sizer Lambda
        right_sizer_lambda = lambda_.Function(
            self, "RightSizerFunction",
            function_name="CostGuard-Right-Sizer",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="autonomous.right_sizer.handler",
            code=lambda_.Code.from_asset("../src"),
            role=right_sizer_role,
            timeout=Duration.minutes(10),
            memory_size=512,
            environment={
                **common_env,
                "GPU_COSTS_TABLE": "costguard-gpu-costs",
                "MIGRATION_ROLLBACKS_TABLE": migration_rollbacks_table.table_name,
                "UTILIZATION_THRESHOLD": "0.60",
                "DEGRADATION_THRESHOLD": "0.15",
            },
            tracing=lambda_.Tracing.ACTIVE,
            description="Analyzes GPU utilization and recommends right-sizing opportunities",
        )

        # Learning Engine Lambda
        learning_engine_lambda = lambda_.Function(
            self, "LearningEngineFunction",
            function_name="CostGuard-Learning-Engine",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="autonomous.learning_engine.handler",
            code=lambda_.Code.from_asset("../src"),
            role=learning_engine_role,
            timeout=Duration.minutes(5),
            memory_size=512,
            environment={
                **common_env,
                "MIN_ACTIONS_FOR_LEARNING": "30",
                "SUCCESS_RATE_THRESHOLD": "0.7",
                "LEARNING_MODE_ENABLED": "true",
            },
            tracing=lambda_.Tracing.ACTIVE,
            description="Tracks action outcomes and improves recommendations over time",
        )

        # Safety Guard Lambda
        safety_guard_lambda = lambda_.Function(
            self, "SafetyGuardFunction",
            function_name="CostGuard-Safety-Guard",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="autonomous.safety_guard.handler",
            code=lambda_.Code.from_asset("../src"),
            role=safety_guard_role,
            timeout=Duration.minutes(15),
            memory_size=256,
            environment={
                **common_env,
                "APPROVAL_SNS_TOPIC": approvals_topic.topic_arn,
                "APPROVAL_TIMEOUT_MINUTES": "15",
                "FREE_TIER_BUDGET_LIMIT": "5.0",
                "APPROVAL_REQUIRED_ACTIONS": "migration,ondemand_fallback",
                "APPROVAL_SECRET_KEY": "change-this-in-production",
            },
            tracing=lambda_.Tracing.ACTIVE,
            description="Validates and controls autonomous actions to prevent costly mistakes",
        )

        # =====================================================================
        # EventBridge Rules for Lambda Triggers
        # =====================================================================

        # GPU Scheduler - Hourly scheduled trigger
        gpu_scheduler_rule = events.Rule(
            self, "GPUSchedulerRule",
            rule_name="costguard-gpu-scheduler-hourly",
            schedule=events.Schedule.rate(Duration.hours(1)),
            description="Trigger GPU Scheduler hourly to analyze cost patterns",
        )
        gpu_scheduler_rule.add_target(targets.LambdaFunction(gpu_scheduler_lambda))

        # Right Sizer - Daily scheduled trigger (2 AM UTC)
        right_sizer_rule = events.Rule(
            self, "RightSizerRule",
            rule_name="costguard-right-sizer-daily",
            schedule=events.Schedule.cron(hour="2", minute="0"),
            description="Trigger Right Sizer daily at 2 AM UTC",
        )
        right_sizer_rule.add_target(targets.LambdaFunction(right_sizer_lambda))

        # Learning Engine - Daily scheduled trigger (3 AM UTC)
        learning_engine_schedule_rule = events.Rule(
            self, "LearningEngineScheduleRule",
            rule_name="costguard-learning-engine-daily",
            schedule=events.Schedule.cron(hour="3", minute="0"),
            description="Trigger Learning Engine daily at 3 AM UTC for batch analysis",
        )
        learning_engine_schedule_rule.add_target(targets.LambdaFunction(learning_engine_lambda))

        # Learning Engine - Event-driven trigger (ActionCompleted events)
        learning_engine_event_rule = events.Rule(
            self, "LearningEngineEventRule",
            rule_name="costguard-learning-engine-action-completed",
            event_bus=autonomous_event_bus,
            event_pattern=events.EventPattern(
                source=["costguard.autonomous"],
                detail_type=["ActionCompleted"],
            ),
            description="Trigger Learning Engine on ActionCompleted events",
        )
        learning_engine_event_rule.add_target(targets.LambdaFunction(learning_engine_lambda))

        # Safety Guard - Event-driven trigger (ActionRequest events)
        safety_guard_rule = events.Rule(
            self, "SafetyGuardRule",
            rule_name="costguard-safety-guard-action-request",
            event_bus=autonomous_event_bus,
            event_pattern=events.EventPattern(
                source=["costguard.autonomous"],
                detail_type=["ActionRequest"],
            ),
            description="Trigger Safety Guard on ActionRequest events",
        )
        safety_guard_rule.add_target(targets.LambdaFunction(safety_guard_lambda))

        # Spot Manager - Event-driven trigger (SpotInterruptionDetected events)
        spot_manager_rule = events.Rule(
            self, "SpotManagerRule",
            rule_name="costguard-spot-manager-interruption",
            event_bus=autonomous_event_bus,
            event_pattern=events.EventPattern(
                source=["costguard.autonomous"],
                detail_type=["SpotInterruptionDetected"],
            ),
            description="Trigger Spot Manager on spot interruption warnings",
        )
        spot_manager_rule.add_target(targets.LambdaFunction(spot_manager_lambda))

        # =====================================================================
        # Lambda Function Outputs
        # =====================================================================

        CfnOutput(
            self, "GPUSchedulerFunctionArn",
            value=gpu_scheduler_lambda.function_arn,
            description="GPU Scheduler Lambda function ARN",
        )

        CfnOutput(
            self, "SpotManagerFunctionArn",
            value=spot_manager_lambda.function_arn,
            description="Spot Manager Lambda function ARN",
        )

        CfnOutput(
            self, "RightSizerFunctionArn",
            value=right_sizer_lambda.function_arn,
            description="Right Sizer Lambda function ARN",
        )

        CfnOutput(
            self, "LearningEngineFunctionArn",
            value=learning_engine_lambda.function_arn,
            description="Learning Engine Lambda function ARN",
        )

        CfnOutput(
            self, "SafetyGuardFunctionArn",
            value=safety_guard_lambda.function_arn,
            description="Safety Guard Lambda function ARN",
        )

        # Store references for use by Lambda functions in subsequent tasks
        self.action_history_table = action_history_table
        self.training_checkpoints_table = training_checkpoints_table
        self.migration_rollbacks_table = migration_rollbacks_table
        self.autonomous_event_bus = autonomous_event_bus
        self.checkpoints_bucket = checkpoints_bucket
        self.approvals_topic = approvals_topic
        self.alerts_topic = alerts_topic
        self.dashboard = dashboard
        self.gpu_scheduler_role = gpu_scheduler_role
        self.spot_manager_role = spot_manager_role
        self.right_sizer_role = right_sizer_role
        self.learning_engine_role = learning_engine_role
        self.safety_guard_role = safety_guard_role
        self.gpu_scheduler_lambda = gpu_scheduler_lambda
        self.spot_manager_lambda = spot_manager_lambda
        self.right_sizer_lambda = right_sizer_lambda
        self.learning_engine_lambda = learning_engine_lambda
        self.safety_guard_lambda = safety_guard_lambda
