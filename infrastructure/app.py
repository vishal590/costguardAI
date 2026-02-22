#!/usr/bin/env python3
"""
CDK App for CostGuard Infrastructure

This app creates the complete CostGuard infrastructure stack including:
- DynamoDB tables
- Lambda function
- API Gateway
- SNS topics
- EventBridge schedule
- IAM roles and permissions
"""

import aws_cdk as cdk
from cdk_stack import CostGuardStack


app = cdk.App()

CostGuardStack(
    app, "CostGuardStack",
    description="CostGuard - AWS Cost Management and Automated Prevention System",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1",
    ),
)

app.synth()
