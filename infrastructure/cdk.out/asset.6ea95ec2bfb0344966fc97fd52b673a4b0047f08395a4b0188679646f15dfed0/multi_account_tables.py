"""
DynamoDB Table Definitions for Multi-Account Cost Management (Phase 5)

This module defines the DynamoDB table infrastructure for managing costs
across multiple AWS accounts within an AWS Organization.

Phase 5 Requirements:
- Organizations table: Cache organization structure
- Accounts table: Store account metadata with GSI for org queries
- Multi-account costs table: Store cost data by account with date GSI
- Allocation rules table: Store cost allocation rules
- Budgets table: Store organization/OU/account budgets
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
)
from constructs import Construct


class OrganizationsTable(Construct):
    """DynamoDB table for caching organization structure"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create DynamoDB table for organizations
        self.table = dynamodb.Table(
            self,
            "OrganizationsTable",
            table_name="organizations",
            partition_key=dynamodb.Attribute(
                name="org_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,  # On-demand billing
            time_to_live_attribute="ttl",  # Enable TTL for 24-hour cache expiration
            removal_policy=RemovalPolicy.RETAIN,  # Retain table on stack deletion
            point_in_time_recovery=False,  # Disabled for Free Tier
        )


class AccountsTable(Construct):
    """DynamoDB table for storing account metadata"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create DynamoDB table for accounts
        self.table = dynamodb.Table(
            self,
            "AccountsTable",
            table_name="accounts",
            partition_key=dynamodb.Attribute(
                name="account_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,  # On-demand billing
            removal_policy=RemovalPolicy.RETAIN,  # Retain table on stack deletion
            point_in_time_recovery=False,  # Disabled for Free Tier
        )

        # Add GSI for querying accounts by organization
        self.table.add_global_secondary_index(
            index_name="org_id-index",
            partition_key=dynamodb.Attribute(
                name="org_id", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )


class MultiAccountCostsTable(Construct):
    """DynamoDB table for storing cost data by account"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create DynamoDB table for multi-account costs
        self.table = dynamodb.Table(
            self,
            "MultiAccountCostsTable",
            table_name="multi_account_costs",
            partition_key=dynamodb.Attribute(
                name="account_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="date", type=dynamodb.AttributeType.STRING  # YYYY-MM-DD format
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,  # On-demand billing
            removal_policy=RemovalPolicy.RETAIN,  # Retain table on stack deletion
            point_in_time_recovery=False,  # Disabled for Free Tier
        )

        # Add GSI for querying costs by date across accounts
        self.table.add_global_secondary_index(
            index_name="date-index",
            partition_key=dynamodb.Attribute(
                name="date", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )


class AllocationRulesTable(Construct):
    """DynamoDB table for storing cost allocation rules"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create DynamoDB table for allocation rules
        self.table = dynamodb.Table(
            self,
            "AllocationRulesTable",
            table_name="allocation_rules",
            partition_key=dynamodb.Attribute(
                name="rule_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,  # On-demand billing
            removal_policy=RemovalPolicy.RETAIN,  # Retain table on stack deletion
            point_in_time_recovery=False,  # Disabled for Free Tier
        )

        # Add GSI for querying rules by organization
        self.table.add_global_secondary_index(
            index_name="org_id-index",
            partition_key=dynamodb.Attribute(
                name="org_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="priority", type=dynamodb.AttributeType.NUMBER
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )


class BudgetsTable(Construct):
    """DynamoDB table for storing organization/OU/account budgets"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create DynamoDB table for budgets
        self.table = dynamodb.Table(
            self,
            "BudgetsTable",
            table_name="budgets",
            partition_key=dynamodb.Attribute(
                name="budget_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,  # On-demand billing
            removal_policy=RemovalPolicy.RETAIN,  # Retain table on stack deletion
            point_in_time_recovery=False,  # Disabled for Free Tier
        )

        # Add GSI for querying budgets by entity (org/OU/account)
        self.table.add_global_secondary_index(
            index_name="entity_id-index",
            partition_key=dynamodb.Attribute(
                name="entity_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="entity_type", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )


class MultiAccountStack(Stack):
    """CDK Stack for Multi-Account Cost Management DynamoDB tables"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create DynamoDB table for organizations
        self.organizations_table = OrganizationsTable(
            self, "OrganizationsTableConstruct"
        )

        # Create DynamoDB table for accounts
        self.accounts_table = AccountsTable(self, "AccountsTableConstruct")

        # Create DynamoDB table for multi-account costs
        self.multi_account_costs_table = MultiAccountCostsTable(
            self, "MultiAccountCostsTableConstruct"
        )

        # Create DynamoDB table for allocation rules
        self.allocation_rules_table = AllocationRulesTable(
            self, "AllocationRulesTableConstruct"
        )

        # Create DynamoDB table for budgets
        self.budgets_table = BudgetsTable(self, "BudgetsTableConstruct")
