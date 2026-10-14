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

import os
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
    aws_apigateway as apigateway,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_logs as logs,
    CfnOutput,
    CfnParameter,
    ArnFormat,
    aws_scheduler as scheduler,
    aws_secretsmanager as secretsmanager,
    aws_sqs as sqs,
    aws_ssm as ssm,
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
                source=["costguard.autonomous", "costguard.autonomous.api",
                        "costguard.autonomous.demo", "costguard.autonomous.scheduler",
                        "costguard.autonomous.spotmanager", "costguard.autonomous.safetyguard",
                        "costguard.autonomous.learningengine", "costguard.autonomous.rightsizer",
                        "costguard.autonomous.circuitbreaker", "costguard.autonomous.executor"],
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
            code=lambda_.Code.from_asset(os.path.join(os.path.dirname(__file__), "..", "src"), exclude=["**/__pycache__", "**/*.pyc"]),
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
            code=lambda_.Code.from_asset(os.path.join(os.path.dirname(__file__), "..", "src"), exclude=["**/__pycache__", "**/*.pyc"]),
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
            code=lambda_.Code.from_asset(os.path.join(os.path.dirname(__file__), "..", "src"), exclude=["**/__pycache__", "**/*.pyc"]),
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
            code=lambda_.Code.from_asset(os.path.join(os.path.dirname(__file__), "..", "src"), exclude=["**/__pycache__", "**/*.pyc"]),
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
            code=lambda_.Code.from_asset(os.path.join(os.path.dirname(__file__), "..", "src"), exclude=["**/__pycache__", "**/*.pyc"]),
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

        # Resource execution stays disabled until deployment explicitly opts in.
        enable_execution = CfnParameter(self, "EnableAutonomousExecution", type="String",
            default="false", allowed_values=["true", "false"],
            description="Enable approved EC2 changes; defaults to analysis and approval only")
        schedule_group = scheduler.CfnScheduleGroup(self, "ExecutionScheduleGroup",
                                                    name="costguard-autonomous")
        schedule_role = iam.Role(self, "ExecutionScheduleRole",
            assumed_by=iam.ServicePrincipal("scheduler.amazonaws.com", conditions={
                "StringEquals": {"aws:SourceAccount": self.account},
                "ArnEquals": {"aws:SourceArn": schedule_group.attr_arn}}))
        executor_role = iam.Role(self, "ActionExecutorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")])
        action_history_table.grant_read_write_data(executor_role)
        migration_rollbacks_table.grant_read_write_data(executor_role)
        autonomous_event_bus.grant_put_events_to(executor_role)
        executor_role.add_to_policy(iam.PolicyStatement(actions=["ce:GetCostAndUsage"], resources=["*"]))
        executor_role.add_to_policy(iam.PolicyStatement(
            actions=["ec2:DescribeInstances", "ec2:DescribeLaunchTemplates", "ec2:DescribeLaunchTemplateVersions",
                     "ec2:RunInstances", "ec2:CreateTags", "ec2:StartInstances", "ec2:StopInstances",
                     "ec2:TerminateInstances", "ec2:ModifyInstanceAttribute"], resources=["*"],
            conditions={"StringEquals": {"aws:RequestedRegion": self.region}}))
        executor_role.add_to_policy(iam.PolicyStatement(actions=["scheduler:CreateSchedule", "scheduler:DeleteSchedule"],
            resources=[self.format_arn(service="scheduler", resource="schedule",
                                      resource_name="costguard-autonomous/cg-*")]))
        executor_role.add_to_policy(iam.PolicyStatement(actions=["iam:PassRole"],
            resources=[schedule_role.role_arn], conditions={"StringEquals": {"iam:PassedToService": "scheduler.amazonaws.com"}}))
        execution_dlq = sqs.Queue(self, "AutonomousExecutionDLQ", retention_period=Duration.days(14))
        execution_dlq.grant_send_messages(schedule_role)
        training_role = iam.Role(self, "TrainingInstanceRole", assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")])
        training_role.add_to_policy(iam.PolicyStatement(actions=["s3:GetObject", "s3:PutObject"],
            resources=[checkpoints_bucket.arn_for_objects("training/*")]))
        training_profile = iam.CfnInstanceProfile(self, "TrainingInstanceProfile", roles=[training_role.role_name])
        training_document = ssm.CfnDocument(self, "TrainingResumeDocument", document_type="Command",
            content={"schemaVersion": "2.2", "description": "Run the installed CostGuard reference SGD worker",
                "parameters": {"request": {"type": "String", "allowedPattern": "^[A-Za-z0-9+/=]+$"},
                    "timeout": {"type": "String", "allowedPattern": "^[0-9]{1,3}$"}},
                "mainSteps": [{"action": "aws:runShellScript", "name": "train", "inputs": {
                    "timeoutSeconds": "{{ timeout }}", "runCommand": [
                        'PYTHONPATH=/opt/costguard/src /opt/costguard/venv/bin/python -m autonomous.training_worker --request-base64 "{{ request }}"']}}]})
        executor_role.add_to_policy(iam.PolicyStatement(actions=["iam:PassRole"], resources=[training_role.role_arn],
            conditions={"StringEquals": {"iam:PassedToService": "ec2.amazonaws.com"}}))
        executor_role.add_to_policy(iam.PolicyStatement(actions=["ssm:SendCommand"],
            resources=[self.format_arn(service="ssm", resource="document", resource_name=training_document.ref),
                       self.format_arn(service="ec2", resource="instance", resource_name="*")]))
        executor_role.add_to_policy(iam.PolicyStatement(actions=["ssm:DescribeInstanceInformation", "ssm:GetCommandInvocation", "ssm:CancelCommand"], resources=["*"]))
        checkpoints_bucket.grant_read(executor_role, "training/*")
        CfnOutput(self, "TrainingInstanceProfileArn", value=training_profile.attr_arn)
        CfnOutput(self, "TrainingDocumentName", value=training_document.ref)

        executor_arn = self.format_arn(service="lambda", resource="function", resource_name="CostGuard-Action-Executor",
                                       arn_format=ArnFormat.COLON_RESOURCE_NAME)
        action_executor_lambda = lambda_.Function(self, "ActionExecutorFunction",
            function_name="CostGuard-Action-Executor", runtime=lambda_.Runtime.PYTHON_3_11,
            handler="autonomous.action_executor.handler", code=lambda_.Code.from_asset(os.path.join(os.path.dirname(__file__), "..", "src"), exclude=["**/__pycache__", "**/*.pyc"]),
            role=executor_role, timeout=Duration.minutes(15), memory_size=512,
            dead_letter_queue=execution_dlq,
            environment={**common_env, "EXECUTION_ENABLED": enable_execution.value_as_string,
                         "DRY_RUN_MODE": "false", "MIGRATION_ROLLBACKS_TABLE": migration_rollbacks_table.table_name,
                         "SCHEDULE_GROUP": "costguard-autonomous", "EXECUTOR_ARN": executor_arn,
                         "SCHEDULE_ROLE_ARN": schedule_role.role_arn, "SCHEDULE_DLQ_ARN": execution_dlq.queue_arn,
                         "FREE_TIER_BUDGET_LIMIT": "5", "CHECKPOINT_BUCKET": checkpoints_bucket.bucket_name,
                         "TRAINING_DOCUMENT": training_document.ref,
                         "TRAINING_INSTANCE_PROFILE_ARN": training_profile.attr_arn},
            description="Executes approved reversible EC2 operations and resource rollback")
        action_executor_lambda.grant_invoke(schedule_role)
        approval_secret = secretsmanager.Secret(self, "AutonomousApprovalSecret",
            description="HMAC key for autonomous approval requests")
        approval_secret.grant_read(safety_guard_lambda)
        safety_guard_lambda.add_environment("APPROVAL_SECRET_ARN", approval_secret.secret_arn)

        recommendation_rule = events.Rule(self, "ScheduleRecommendationRule",
            rule_name="costguard-schedule-recommendation-approval", event_bus=autonomous_event_bus,
            event_pattern=events.EventPattern(source=["costguard.autonomous.scheduler"], detail_type=["ScheduleRecommendation"]))
        recommendation_rule.add_target(targets.LambdaFunction(safety_guard_lambda))
        executor_rule = events.Rule(self, "ApprovedExecutionRule",
            rule_name="costguard-approved-action-execution", event_bus=autonomous_event_bus,
            event_pattern=events.EventPattern(source=["costguard.autonomous.safetyguard"],
                                             detail_type=["ExecuteAction", "ExecuteRollback"]))
        executor_rule.add_target(targets.LambdaFunction(action_executor_lambda, dead_letter_queue=execution_dlq))
        CfnOutput(self, "ActionExecutorArn", value=action_executor_lambda.function_arn)

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
                source=["costguard.autonomous", "costguard.autonomous.spotmanager",
                        "costguard.autonomous.rightsizer", "costguard.autonomous.executor"],
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
                source=["costguard.autonomous", "costguard.autonomous.spotmanager", "costguard.autonomous.rightsizer"],
                detail_type=["ActionRequest"],
            ),
            description="Trigger Safety Guard on ActionRequest events",
        )
        safety_guard_rule.add_target(targets.LambdaFunction(safety_guard_lambda))

        # API decisions and rollbacks are handled by Safety Guard. Keep this rule
        # separate so worker-emitted approval events cannot loop back into it.
        safety_guard_api_rule = events.Rule(
            self, "SafetyGuardAPIRule",
            rule_name="costguard-safety-guard-api-requests",
            event_bus=autonomous_event_bus,
            event_pattern=events.EventPattern(
                source=["costguard.autonomous.api"],
                detail_type=["ActionApproved", "ActionRejected", "RollbackRequested"],
            ),
            description="Validate API approval decisions and process rollback requests",
        )
        safety_guard_api_rule.add_target(targets.LambdaFunction(safety_guard_lambda))

        # Spot Manager - Event-driven trigger (SpotInterruptionDetected events)
        spot_manager_rule = events.Rule(
            self, "SpotManagerRule",
            rule_name="costguard-spot-manager-interruption",
            event_bus=autonomous_event_bus,
            event_pattern=events.EventPattern(
                source=["costguard.autonomous", "costguard.autonomous.demo"],
                detail_type=["SpotInterruptionDetected"],
            ),
            description="Trigger Spot Manager on spot interruption warnings",
        )
        spot_manager_rule.add_target(targets.LambdaFunction(spot_manager_lambda))

        # =====================================================================
 (REST API for demo, action-history, approve, etc.)
        # =====================================================================

        api_lambda_role = iam.Role(
            self, "AutonomousAPILambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
            description="IAM role for Autonomous API Lambda",
        )
        action_history_table.grant_read_write_data(api_lambda_role)
        autonomous_event_bus.grant_put_events_to(api_lambda_role)
        gpu_scheduler_lambda.grant_invoke(api_lambda_role)
        learning_engine_lambda.grant_invoke(api_lambda_role)

        project_root = os.path.join(os.path.dirname(__file__), "..")
        autonomous_api_handler = lambda_.Function(
            self, "AutonomousAPIHandler",
            function_name="CostGuard-Autonomous-API",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="src.autonomous_handler.handler",
            code=lambda_.Code.from_asset(
                project_root,
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
                    "*.py[cod]",
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
                    "*$py.class",
                ],
            ),
            role=api_lambda_role,
            timeout=Duration.seconds(29),
            memory_size=256,
            environment={
                "BACKEND_API_KEY": self.node.try_get_context("bff_autonomous_key") or os.environ.get("BFF_AUTONOMOUS_API_KEY", ""),
                "BACKEND_ACCOUNT_ID": Stack.of(self).account,
                "ALLOW_DIRECT_API_KEYS": self.node.try_get_context("allow_direct_api_keys") or "false",
                "ACTION_HISTORY_TABLE": action_history_table.table_name,
                "EVENT_BUS_NAME": autonomous_event_bus.event_bus_name,
                "GPU_SCHEDULER_FUNCTION": gpu_scheduler_lambda.function_name,
                "LEARNING_ENGINE_FUNCTION": learning_engine_lambda.function_name,
                "DEMO_MODE": "true",
                "CHECKPOINTS_BUCKET": checkpoints_bucket.bucket_name,
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # =====================================================================
        # API Gateway for Autonomous (Phase 6 Extension)
        # =====================================================================

        autonomous_api = apigateway.RestApi(
            self, "AutonomousAPI",
            rest_api_name="CostGuard-AutonomousAPI",
            description="REST API for CostGuard Autonomous Action Loops (Phase 6 Extension)",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "X-API-Key", "Authorization"],
            ),
        )
        autonomous_integration = apigateway.LambdaIntegration(
            autonomous_api_handler,
            allow_test_invoke=False,
            timeout=Duration.seconds(29),
        )
        api_resource = autonomous_api.root.add_resource("api")
        autonomous_resource = api_resource.add_resource("autonomous")

        # OPTIONS (CORS preflight) must not require API key so browser preflight succeeds.
        self._disable_api_key_on_options(api_resource)
        self._disable_api_key_on_options(autonomous_resource)

        schedule_analysis_res = autonomous_resource.add_resource("schedule-analysis")
        schedule_analysis_res.add_method("POST", autonomous_integration)
        self._disable_api_key_on_options(schedule_analysis_res)

        action_history_res = autonomous_resource.add_resource("action-history")
        action_history_res.add_method("GET", autonomous_integration)
        self._disable_api_key_on_options(action_history_res)

        approve_action_res = autonomous_resource.add_resource("approve-action")
        approve_action_res.add_method("POST", autonomous_integration)
        self._disable_api_key_on_options(approve_action_res)

        rollback_res = autonomous_resource.add_resource("rollback")
        rollback_res.add_method("POST", autonomous_integration)
        self._disable_api_key_on_options(rollback_res)

        confidence_scores_res = autonomous_resource.add_resource("confidence-scores")
        confidence_scores_res.add_method("GET", autonomous_integration)
        self._disable_api_key_on_options(confidence_scores_res)

        demo_status_res = autonomous_resource.add_resource("demo-status")
        demo_status_res.add_method("GET", autonomous_integration)
        self._disable_api_key_on_options(demo_status_res)

        demo_resource = autonomous_resource.add_resource("demo")
        self._disable_api_key_on_options(demo_resource)

        demo_start_res = demo_resource.add_resource("start")
        demo_start_res.add_method("POST", autonomous_integration)
        self._disable_api_key_on_options(demo_start_res)

        demo_reset_res = demo_resource.add_resource("reset")
        demo_reset_res.add_method("POST", autonomous_integration)
        self._disable_api_key_on_options(demo_reset_res)

        demo_trigger_res = demo_resource.add_resource("trigger-interruption")
        demo_trigger_res.add_method("POST", autonomous_integration)
        self._disable_api_key_on_options(demo_trigger_res)

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

        CfnOutput(
            self, "AutonomousAPIUrl",
            value=autonomous_api.url,
            description="Phase 6 Extension Autonomous API base URL (set VITE_AUTONOMOUS_API_BASE_URL in frontend)",
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

    def _disable_api_key_on_options(self, resource: apigateway.Resource) -> None:
        """Set ApiKeyRequired=false on the OPTIONS method so CORS preflight succeeds without x-api-key."""
        for child in resource.node.children:
            if isinstance(child, apigateway.Method) and getattr(child, "http_method", None) == "OPTIONS":
                cfn = child.node.default_child
                if cfn is not None:
                    cfn.add_property_override("ApiKeyRequired", False)
                break
