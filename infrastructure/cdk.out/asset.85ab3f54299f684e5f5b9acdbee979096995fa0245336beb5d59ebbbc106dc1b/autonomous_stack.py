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
    aws_s3 as s3,
    aws_sns as sns,
    aws_iam as iam,
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

        # Store references for use by Lambda functions in subsequent tasks
        self.action_history_table = action_history_table
        self.training_checkpoints_table = training_checkpoints_table
        self.migration_rollbacks_table = migration_rollbacks_table
        self.autonomous_event_bus = autonomous_event_bus
        self.checkpoints_bucket = checkpoints_bucket
        self.approvals_topic = approvals_topic
        self.alerts_topic = alerts_topic
