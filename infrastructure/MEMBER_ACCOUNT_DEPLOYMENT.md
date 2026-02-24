# CostGuard Multi-Account Member Account Deployment Guide

This guide explains how to deploy the necessary IAM roles in member accounts to enable CostGuard Multi-Account Cost Management (Phase 5).

## Overview

CostGuard Multi-Account requires a cross-account IAM role in each member account to collect cost data and metadata. This role allows the management account to assume roles in member accounts securely.

## Deployment Options

### Option 1: Individual Account Deployment (Recommended for Small Organizations)

Deploy the CloudFormation template individually in each member account.

#### Prerequisites
- AWS CLI configured with appropriate permissions
- Access to each member account
- Management account ID

#### Steps

1. **Get the Management Account ID**
   ```bash
   # Run this in your CostGuard management account
   aws sts get-caller-identity --query Account --output text
   ```

2. **Generate External ID**
   ```bash
   # Generate a unique external ID for security
   EXTERNAL_ID="CostGuard-$(date +%s)-$(openssl rand -hex 8)"
   echo "External ID: $EXTERNAL_ID"
   ```

3. **Deploy to Each Member Account**
   ```bash
   # Switch to member account (replace with actual account ID)
   aws sts assume-role --role-arn "arn:aws:iam::MEMBER-ACCOUNT-ID:role/OrganizationAccountAccessRole" --role-session-name "CostGuardDeployment"
   
   # Deploy the CloudFormation stack
   aws cloudformation create-stack \
     --stack-name "CostGuard-CrossAccount-Role" \
     --template-body file://member_account_role_template.yaml \
     --parameters ParameterKey=ManagementAccountId,ParameterValue=MANAGEMENT-ACCOUNT-ID \
                  ParameterKey=ExternalId,ParameterValue=$EXTERNAL_ID \
     --capabilities CAPABILITY_NAMED_IAM \
     --region us-east-1
   ```

4. **Verify Deployment**
   ```bash
   # Check stack status
   aws cloudformation describe-stacks --stack-name "CostGuard-CrossAccount-Role" --query 'Stacks[0].StackStatus'
   
   # Get role ARN
   aws cloudformation describe-stacks --stack-name "CostGuard-CrossAccount-Role" --query 'Stacks[0].Outputs[?OutputKey==`RoleArn`].OutputValue' --output text
   ```

### Option 2: StackSet Deployment (Recommended for Large Organizations)

Deploy using AWS CloudFormation StackSets to automatically deploy across all organization accounts.

#### Prerequisites
- AWS Organizations enabled
- StackSet administration permissions in management account
- Trusted access enabled for CloudFormation StackSets

#### Steps

1. **Enable StackSet Trusted Access**
   ```bash
   # Run in management account
   aws organizations enable-aws-service-access --service-principal stacksets.cloudformation.amazonaws.com
   ```

2. **Create StackSet**
   ```bash
   # Create the StackSet
   aws cloudformation create-stack-set \
     --stack-set-name "CostGuard-CrossAccount-Roles" \
     --template-body file://stackset_template.yaml \
     --parameters ParameterKey=ManagementAccountId,ParameterValue=$(aws sts get-caller-identity --query Account --output text) \
                  ParameterKey=ExternalIdPrefix,ParameterValue="CostGuard-$(date +%s)-" \
     --capabilities CAPABILITY_NAMED_IAM \
     --description "CostGuard Multi-Account cross-account roles for all organization accounts"
   ```

3. **Deploy to Organization**
   ```bash
   # Deploy to all accounts in the organization
   aws cloudformation create-stack-instances \
     --stack-set-name "CostGuard-CrossAccount-Roles" \
     --deployment-targets OrganizationalUnitIds=r-xxxx \
     --regions us-east-1 \
     --operation-preferences RegionConcurrencyType=PARALLEL,MaxConcurrentPercentage=100
   ```

4. **Monitor Deployment**
   ```bash
   # Check deployment status
   aws cloudformation list-stack-instances --stack-set-name "CostGuard-CrossAccount-Roles"
   ```

## Verification

### Test Role Assumption

After deployment, test that the management account can assume the role:

```bash
# Run from management account
MEMBER_ACCOUNT_ID="123456789012"  # Replace with actual member account ID
EXTERNAL_ID="your-external-id"    # Replace with actual external ID

aws sts assume-role \
  --role-arn "arn:aws:iam::$MEMBER_ACCOUNT_ID:role/CostGuardCrossAccountRole" \
  --role-session-name "CostGuardTest" \
  --external-id "$EXTERNAL_ID"
```

### Test Cost Data Access

```bash
# Test Cost Explorer access (using assumed role credentials)
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-02 \
  --granularity DAILY \
  --metrics BlendedCost
```

## Security Considerations

### External ID Management
- Use unique external IDs for each account
- Store external IDs securely (e.g., AWS Systems Manager Parameter Store)
- Rotate external IDs periodically

### Role Permissions
- The role has read-only permissions for cost and resource data
- No write permissions are granted
- Session duration is limited to 1 hour

### Monitoring
- Enable CloudTrail logging for role assumptions
- Monitor for unusual access patterns
- Set up alerts for failed role assumptions

## Troubleshooting

### Common Issues

1. **Role Assumption Fails**
   - Verify external ID matches
   - Check trust policy configuration
   - Ensure management account ID is correct

2. **Permission Denied Errors**
   - Verify IAM policies are attached correctly
   - Check if Cost Explorer is enabled in the account
   - Ensure required services are available in the region

3. **StackSet Deployment Fails**
   - Verify trusted access is enabled
   - Check organizational unit IDs
   - Ensure sufficient permissions in target accounts

### Support

For additional support:
1. Check CloudFormation stack events for detailed error messages
2. Review CloudTrail logs for API call failures
3. Verify AWS service quotas and limits
4. Contact AWS support if needed

## Cleanup

To remove the cross-account roles:

### Individual Account Cleanup
```bash
# Delete stack from each member account
aws cloudformation delete-stack --stack-name "CostGuard-CrossAccount-Role"
```

### StackSet Cleanup
```bash
# Delete all stack instances
aws cloudformation delete-stack-instances \
  --stack-set-name "CostGuard-CrossAccount-Roles" \
  --deployment-targets OrganizationalUnitIds=r-xxxx \
  --regions us-east-1 \
  --retain-stacks false

# Delete the StackSet
aws cloudformation delete-stack-set --stack-set-name "CostGuard-CrossAccount-Roles"
```

## Next Steps

After successful deployment:
1. Configure CostGuard Multi-Account system with account IDs and external IDs
2. Run initial organization discovery
3. Set up cost collection schedules
4. Configure cost allocation rules
5. Set up organization-wide budgets and alerts