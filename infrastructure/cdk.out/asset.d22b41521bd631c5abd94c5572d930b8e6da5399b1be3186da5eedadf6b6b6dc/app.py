#!/usr/bin/env python3
"""
CDK App for CostGuard Infrastructure

This app creates the complete CostGuard infrastructure stack including:
- Phase 1-4: Single-account infrastructure (DynamoDB, Lambda, API Gateway, SNS, EventBridge, IAM)
- Phase 5: Multi-account infrastructure (additional tables, Lambda functions, cross-account roles)
- Phase 6: AI/ML workload cost management (GPU tracking, SageMaker, Bedrock cost optimization)
"""

import aws_cdk as cdk
from cdk_stack import CostGuardStack
from multi_account_stack import MultiAccountStack
from aiml_stack import AIMLStack


app = cdk.App()

# Deploy Phase 1-4 infrastructure (existing single-account stack)
costguard_stack = CostGuardStack(
    app, "CostGuardStack",
    description="CostGuard - AWS Cost Management and Automated Prevention System (Phases 1-4)",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1",
    ),
)

# Deploy Phase 5 infrastructure (multi-account stack)
multi_account_stack = MultiAccountStack(
    app, "CostGuardMultiAccountStack",
    description="CostGuard - Multi-Account Cost Management System (Phase 5)",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1",
    ),
)

# Deploy Phase 6 infrastructure (AI/ML stack)
aiml_stack = AIMLStack(
    app, "CostGuardAIMLStack",
    description="CostGuard - AI/ML Workload Cost Management System (Phase 6)",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1",
    ),
)

# Add dependencies to ensure proper deployment order
multi_account_stack.add_dependency(costguard_stack)
aiml_stack.add_dependency(costguard_stack)  # Phase 6 depends on Phase 1-4
aiml_stack.add_dependency(multi_account_stack)  # Phase 6 uses multi-account tables

app.synth()
