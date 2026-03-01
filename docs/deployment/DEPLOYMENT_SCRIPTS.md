# CostGuard Deployment Scripts

This document describes the deployment and rollback scripts for CostGuard Multi-Account Cost Management.

## Overview

Two main scripts are provided for managing CostGuard infrastructure:

1. **deploy.sh** - Deploys CostGuard infrastructure
2. **rollback.sh** - Rolls back CostGuard infrastructure

Both scripts support dry-run mode, flexible configuration, and comprehensive verification.

---

## deploy.sh - Deployment Script

### Purpose

Deploys the complete CostGuard infrastructure including:
- Phase 1-4: Single-account infrastructure (existing)
- Phase 5: Multi-account infrastructure (new)
- Cross-account roles deployment
- Organization discovery initialization
- Deployment verification

### Basic Usage

```bash
# Deploy everything with default settings
./deploy.sh

# Deploy to specific region
./deploy.sh --region us-west-2

# Deploy with AWS profile
./deploy.sh --profile production

# Deploy only multi-account components
./deploy.sh --skip-single-account

# Dry run to see what would be deployed
./deploy.sh --dry-run
```

### Options

| Option | Description |
|--------|-------------|
| `--region REGION` | AWS region (default: us-east-1) |
| `--profile PROFILE` | AWS profile to use |
| `--skip-single-account` | Skip Phase 1-4 deployment |
| `--skip-multi-account` | Skip Phase 5 deployment |
| `--skip-cross-account` | Skip cross-account roles deployment |
| `--skip-verification` | Skip deployment verification |
| `--dry-run` | Show what would be deployed without deploying |
| `--help` | Show help message |

### Prerequisites

Before running the deployment script, ensure you have:

1. **AWS CLI** - Configured with appropriate permissions
2. **CDK CLI** - Install with `npm install -g aws-cdk`
3. **Python 3.11+** - With required dependencies installed
4. **Organization Admin Permissions** - For cross-account setup

### Deployment Steps

The script performs the following steps:

1. **Check Prerequisites** - Validates AWS CLI, CDK, Python, and credentials
2. **Bootstrap CDK** - Bootstraps CDK in the target region if needed
3. **Deploy Single-Account** - Deploys Phase 1-4 infrastructure (optional)
4. **Deploy Multi-Account** - Deploys Phase 5 infrastructure
5. **Deploy Cross-Account Roles** - Deploys roles to member accounts using StackSets
6. **Initialize Organization Discovery** - Triggers organization discovery Lambda
7. **Verify Deployment** - Runs infrastructure tests to verify deployment

### Examples

#### Deploy Everything

```bash
./deploy.sh
```

#### Deploy Only Multi-Account Components

```bash
./deploy.sh --skip-single-account
```

#### Deploy to Production with Profile

```bash
./deploy.sh --region us-west-2 --profile production
```

#### Dry Run

```bash
./deploy.sh --dry-run
```

This shows what would be deployed without making any changes.

### Verification

The script automatically verifies deployment by:
- Checking DynamoDB tables are active
- Verifying Lambda functions are deployed
- Testing API Gateway endpoints
- Confirming EventBridge rules are enabled
- Validating CloudWatch alarms are created

### Troubleshooting

If deployment fails:

1. **Check AWS Credentials** - Ensure credentials are valid
2. **Check Permissions** - Verify you have necessary IAM permissions
3. **Check CDK Bootstrap** - Ensure CDK is bootstrapped in the region
4. **Check Logs** - Review CloudFormation stack events for errors
5. **Run Verification** - Run `python infrastructure/deploy_multi_account.py --test-only`

---

## rollback.sh - Rollback Script

### Purpose

Rolls back CostGuard infrastructure deployment including:
- Phase 5: Multi-account infrastructure rollback
- Phase 1-4: Single-account infrastructure rollback (optional)
- Cross-account roles cleanup
- Deployment verification

### Basic Usage

```bash
# Rollback multi-account stack only (default)
./rollback.sh

# Rollback everything
./rollback.sh --rollback-all

# Rollback but keep data
./rollback.sh --keep-data

# Dry run to see what would be rolled back
./rollback.sh --dry-run
```

### Options

| Option | Description |
|--------|-------------|
| `--region REGION` | AWS region (default: us-east-1) |
| `--profile PROFILE` | AWS profile to use |
| `--rollback-all` | Rollback both single and multi-account stacks |
| `--rollback-single` | Rollback only single-account stack |
| `--rollback-multi` | Rollback only multi-account stack [default] |
| `--keep-data` | Keep DynamoDB tables (don't delete data) |
| `--skip-cross-account` | Skip cross-account roles cleanup |
| `--skip-verification` | Skip rollback verification |
| `--dry-run` | Show what would be rolled back without doing it |
| `--help` | Show help message |

### ⚠️ WARNING

**This script will delete AWS resources!**

Make sure you have backups of any important data before proceeding.

### Rollback Steps

The script performs the following steps:

1. **Check Prerequisites** - Validates AWS CLI, CDK, and credentials
2. **Confirm Rollback** - Asks for user confirmation (unless dry-run)
3. **Backup DynamoDB Tables** - Backs up tables if `--keep-data` is specified
4. **Delete Cross-Account Roles** - Removes roles from member accounts
5. **Rollback Multi-Account Stack** - Destroys Phase 5 infrastructure
6. **Rollback Single-Account Stack** - Destroys Phase 1-4 infrastructure (optional)
7. **Verify Rollback** - Confirms resources are deleted

### Examples

#### Rollback Multi-Account Only

```bash
./rollback.sh
```

#### Rollback Everything

```bash
./rollback.sh --rollback-all
```

#### Rollback with Data Backup

```bash
./rollback.sh --keep-data
```

This creates backups of all DynamoDB tables before rollback.

#### Dry Run

```bash
./rollback.sh --dry-run
```

This shows what would be rolled back without making any changes.

### Data Backup

When using `--keep-data`, the script:
1. Creates a timestamped backup directory: `./dynamodb-backups-YYYYMMDD-HHMMSS/`
2. Exports all DynamoDB tables to JSON files
3. Saves backups before proceeding with rollback

**Note:** DynamoDB tables with `RemovalPolicy.RETAIN` will not be deleted even without `--keep-data`.

### Verification

The script automatically verifies rollback by:
- Checking CloudFormation stacks are deleted
- Verifying Lambda functions are removed
- Confirming DynamoDB tables are deleted (unless retained)
- Validating cross-account roles are cleaned up

### Manual Cleanup

Some resources may require manual deletion:
- **DynamoDB tables** - If RemovalPolicy is RETAIN
- **CloudWatch Log Groups** - May persist after stack deletion
- **S3 buckets** - If any were created
- **Cross-account roles** - In member accounts (if not using StackSets)

---

## Common Workflows

### Initial Deployment

```bash
# 1. Deploy everything
./deploy.sh

# 2. Configure SNS subscriptions
# (Subscribe to costguard-multi-account-notifications topic)

# 3. Set up cross-account roles in member accounts
# (Follow instructions in infrastructure/MEMBER_ACCOUNT_DEPLOYMENT.md)

# 4. Test multi-account cost collection
# (Invoke CostGuard-MultiAccountCostCollector Lambda)
```

### Update Deployment

```bash
# 1. Make code changes
# 2. Deploy updates
./deploy.sh

# 3. Verify updates
python infrastructure/deploy_multi_account.py --test-only
```

### Complete Rollback

```bash
# 1. Backup data (optional)
./rollback.sh --keep-data

# 2. Rollback everything
./rollback.sh --rollback-all

# 3. Verify rollback
# (Check AWS Console to confirm resources are deleted)
```

### Partial Rollback

```bash
# Rollback only multi-account components
./rollback.sh --rollback-multi

# Keep single-account infrastructure intact
```

---

## Environment Variables

Both scripts respect the following environment variables:

- `AWS_PROFILE` - AWS profile to use (can also use `--profile`)
- `AWS_DEFAULT_REGION` - AWS region (can also use `--region`)

Example:

```bash
export AWS_PROFILE=production
export AWS_DEFAULT_REGION=us-west-2
./deploy.sh
```

---

## Exit Codes

Both scripts use standard exit codes:

- `0` - Success
- `1` - Error (check logs for details)

---

## Logging

Both scripts provide colored output:
- 🔵 **INFO** - Informational messages
- 🟢 **SUCCESS** - Successful operations
- 🟡 **WARNING** - Warnings (non-fatal)
- 🔴 **ERROR** - Errors (fatal)

---

## Support

For issues or questions:

1. Check the troubleshooting section above
2. Review CloudFormation stack events in AWS Console
3. Check Lambda function logs in CloudWatch
4. Review documentation:
   - `infrastructure/MEMBER_ACCOUNT_DEPLOYMENT.md`
   - `infrastructure/CROSS_ACCOUNT_SETUP.md`
   - `docs/API_EXAMPLES.md`

---

## Related Documentation

- [Member Account Deployment](infrastructure/MEMBER_ACCOUNT_DEPLOYMENT.md)
- [Cross-Account Setup](infrastructure/CROSS_ACCOUNT_SETUP.md)
- [API Examples](docs/API_EXAMPLES.md)
- [Deployment Checklist](DEPLOYMENT_CHECKLIST.md)

---

**Last Updated:** February 2026
