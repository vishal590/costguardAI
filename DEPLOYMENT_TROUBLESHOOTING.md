# CostGuard Deployment Troubleshooting Guide

**Last Updated:** February 27, 2026  
**Purpose:** Document all deployment issues encountered and their solutions for future reference

---

## Table of Contents

1. [CDK Recursive Symlink Issue](#1-cdk-recursive-symlink-issue)
2. [CDK Bootstrap Required](#2-cdk-bootstrap-required)
3. [PowerShell curl Alias Issue](#3-powershell-curl-alias-issue)
4. [Lambda Runtime Errors](#4-lambda-runtime-errors)
5. [IAM User vs Root User](#5-iam-user-vs-root-user)
6. [AWS Region Selection](#6-aws-region-selection)
7. [CDK Lock File Issues](#7-cdk-lock-file-issues)

---

## 1. CDK Recursive Symlink Issue

### Problem

**Symptom:**
- `cdk synth` or `cdk deploy` appears to succeed but nothing deploys
- CloudFormation shows 0 stacks
- Attempting to delete `cdk.out` directory fails with "path too long" errors
- Error message: `Could not find a part of the path` with extremely long nested paths

**Root Cause:**
CDK was bundling the entire parent directory (including `infrastructure/`, `.git/`, `cdk.out/`, etc.) into the Lambda asset. This created a recursive symlink loop where:
```
cdk.out/asset.../infrastructure/cdk.out/asset.../infrastructure/cdk.out/...
```
This loop continued infinitely, creating paths longer than Windows' 260-character limit.

### Solution

**Step 1: Delete the corrupted `cdk.out` directory**

Close VS Code completely, then manually delete the folder in File Explorer, or run:
```powershell
cd G:\projects\aws-ideas\infrastructure
Remove-Item -Recurse -Force -Path cdk.out -ErrorAction SilentlyContinue
```

**Step 2: Fix the Lambda asset bundling in `infrastructure/cdk_stack.py`**

Change this:
```python
code=lambda_.Code.from_asset("../"),  # BAD: Includes everything
```

To this:
```python
code=lambda_.Code.from_asset(
    "../",
    exclude=[
        "infrastructure/*",      # Exclude CDK infrastructure code
        "cdk.out/*",            # Exclude CDK output directory
        ".git/*",               # Exclude git repository
        ".hypothesis/*",        # Exclude hypothesis test data
        "tests/*",              # Exclude test files
        "docs/*",               # Exclude documentation
        "scripts/*",            # Exclude scripts
        "*.md",                 # Exclude markdown files
        ".coverage",            # Exclude coverage reports
        ".pytest_cache/*",      # Exclude pytest cache
        "__pycache__/*",        # Exclude Python cache
        "*.pyc",                # Exclude compiled Python files
        ".venv/*",              # Exclude virtual environment
        "venv/*",               # Exclude virtual environment
    ]
),
```

**Step 3: Verify the fix**
```powershell
cd infrastructure
cdk synth  # Should complete successfully without creating recursive directories
```

### Prevention

Always exclude non-essential directories when bundling Lambda assets. Only include:
- `src/` - Application source code
- `requirements.txt` - Python dependencies (if using layers)
- Any other runtime-required files

---

## 2. CDK Bootstrap Required

### Problem

**Symptom:**
```
CostGuardStack: SSM parameter /cdk-bootstrap/hnb659fds/version not found. 
Has the environment been bootstrapped? Please run 'cdk bootstrap'
```

**Root Cause:**
CDK requires a one-time bootstrap process to create necessary AWS resources (S3 bucket for assets, IAM roles, etc.) in your AWS account.

### Solution

Run bootstrap once per account/region combination:
```powershell
cd infrastructure
cdk bootstrap aws://456041708434/us-east-1
```

Replace `456041708434` with your AWS account ID and `us-east-1` with your region.

**What it creates:**
- S3 bucket: `cdk-hnb659fds-assets-456041708434-us-east-1`
- IAM roles: `cdk-hnb659fds-deploy-role-*`, `cdk-hnb659fds-file-publishing-role-*`, etc.
- SSM parameter: `/cdk-bootstrap/hnb659fds/version`
- ECR repository: `cdk-hnb659fds-container-assets-456041708434-us-east-1`

**Time:** ~1-2 minutes

### Prevention

Always bootstrap before first CDK deployment in a new account/region.

---

## 3. PowerShell curl Alias Issue

### Problem

**Symptom:**
```powershell
curl -X GET "https://api.example.com/endpoint"
# Error: A parameter cannot be found that matches parameter name 'X'
```

**Root Cause:**
In PowerShell, `curl` is an alias for `Invoke-WebRequest`, which has different syntax than the Unix `curl` command.

### Solution

**Option 1: Use Invoke-WebRequest (Recommended)**
```powershell
Invoke-WebRequest -Uri "https://api.example.com/endpoint" -Method GET | Select-Object -ExpandProperty Content
```

**Option 2: Use Invoke-RestMethod (for JSON APIs)**
```powershell
Invoke-RestMethod -Uri "https://api.example.com/endpoint" -Method GET
```

**Option 3: Install real curl**
```powershell
# Install via Chocolatey
choco install curl

# Or download from https://curl.se/windows/
```

### Prevention

Use `Invoke-WebRequest` or `Invoke-RestMethod` in PowerShell scripts instead of `curl`.

---

## 4. Lambda Runtime Errors

### Problem

**Symptom:**
API returns 500 error with message like:
```json
{
  "success": false,
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "'NoneType' object has no attribute 'protected_tags'",
    "details": {"error_type": "AttributeError"}
  }
}
```

**Root Cause:**
Lambda code is trying to access AWS resources or data that doesn't exist yet (e.g., empty DynamoDB tables, missing environment variables, uninitialized services).

### Solution

**Step 1: Check CloudWatch Logs**
```powershell
aws logs tail /aws/lambda/CostGuardLambda --follow
```

**Step 2: Verify Environment Variables**
```powershell
aws lambda get-function-configuration --function-name CostGuardLambda --query 'Environment.Variables'
```

**Step 3: Test with data**
For Phase 1, fetch some cost data first:
```powershell
Invoke-WebRequest -Uri "https://YOUR-API-URL/prod/api/fetch" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"start_date": "2026-02-01", "end_date": "2026-02-27", "granularity": "DAILY"}'
```

**Step 4: Enable Bedrock Access (for Phase 2)**
1. Go to AWS Console → Bedrock → Model access
2. Enable: `amazon.nova-lite-v1:0`
3. Wait for approval (usually instant)

### Prevention

- Add proper error handling in Lambda code for missing data
- Initialize services gracefully with fallbacks
- Test endpoints in order (Phase 1 → 1.5 → 2 → 3)

---

## 5. IAM User vs Root User

### Problem

**Confusion:**
Should we use root user or IAM user for deployment?

**Answer:**
Always use IAM user with `AdministratorAccess` policy. NEVER use root user.

### Solution

**Create IAM User (One-time setup):**

1. Go to AWS Console → IAM → Users → Create user
2. User name: `costguard-deployer`
3. Uncheck "Provide user access to the AWS Management Console" (CLI-only)
4. Attach policy: `AdministratorAccess`
5. Create access key → CLI
6. Save Access Key ID and Secret Access Key

**Configure AWS CLI:**
```powershell
aws configure
# AWS Access Key ID: [paste your key]
# AWS Secret Access Key: [paste your secret]
# Default region name: us-east-1
# Default output format: json
```

**Verify:**
```powershell
aws sts get-caller-identity
# Should show: "Arn": "arn:aws:iam::456041708434:user/costguard-deployer"
```

### Why Not Root User?

- Security best practice: Root user should only be used for account-level tasks
- Root user has unrestricted access (dangerous if credentials leak)
- IAM user can be easily rotated, disabled, or deleted
- IAM user access can be audited via CloudTrail

### Prevention

Always create dedicated IAM users for deployments. Never share root credentials.

---

## 6. AWS Region Selection

### Problem

**Question:**
Which AWS region should we use? User is in India, but us-east-1 is cheaper.

### Solution

**Recommendation: us-east-1 (US East - N. Virginia)**

**Reasons:**
1. **Cost:** Cheapest region for most services
2. **Free Tier:** Best free tier coverage
3. **Service Availability:** All AWS services available first in us-east-1
4. **Latency:** For backend APIs, latency is less critical than for user-facing apps
5. **Cost Explorer API:** Only available in us-east-1

**Cost Comparison (Monthly):**
- us-east-1: ~$2.51/month
- ap-south-1 (Mumbai): ~$3.50/month (+39% more expensive)

**When to use ap-south-1:**
- User-facing frontend with strict latency requirements
- Data residency requirements (Indian data must stay in India)
- Compliance requirements

**For CostGuard:**
Since it's a backend API for cost management, use us-east-1 for cost optimization.

### Prevention

Choose region based on:
1. Cost (us-east-1 is usually cheapest)
2. Latency requirements (user-facing apps)
3. Data residency/compliance requirements
4. Service availability

---

## 7. CDK Lock File Issues

### Problem

**Symptom:**
- CDK commands hang or appear stuck
- Error: "Another CLI (PID=XXXX) is currently synthing to cdk.out"
- Commands return success but don't actually execute

**Root Cause:**
Background CDK processes or VS Code extensions holding locks on `cdk.out` directory.

### Solution

**Step 1: Close VS Code completely**
```powershell
# Close all VS Code windows
# Wait 10 seconds
```

**Step 2: Kill any CDK processes**
```powershell
# Find CDK processes
Get-Process | Where-Object {$_.ProcessName -like "*cdk*" -or $_.ProcessName -like "*node*"}

# Kill them
Stop-Process -Name "node" -Force -ErrorAction SilentlyContinue
```

**Step 3: Delete cdk.out directory**
```powershell
cd infrastructure
Remove-Item -Recurse -Force cdk.out -ErrorAction SilentlyContinue
```

**Step 4: Reopen VS Code and try again**
```powershell
cd infrastructure
cdk synth
```

### Prevention

- Close VS Code before running CDK commands in external terminal
- Don't run multiple CDK commands simultaneously
- Use `--output` flag to specify different output directories for parallel operations

---

## Common Deployment Checklist

Use this checklist for future deployments:

### Prerequisites
- [ ] Node.js installed (v18+)
- [ ] AWS CLI installed and configured
- [ ] AWS CDK installed globally (`npm install -g aws-cdk`)
- [ ] Python virtual environment activated
- [ ] CDK dependencies installed (`pip install -r infrastructure/requirements.txt`)

### AWS Setup
- [ ] IAM user created with `AdministratorAccess`
- [ ] AWS CLI configured with IAM user credentials
- [ ] Verified with `aws sts get-caller-identity`
- [ ] Region selected (us-east-1 recommended)

### CDK Setup
- [ ] CDK bootstrapped (`cdk bootstrap aws://ACCOUNT-ID/REGION`)
- [ ] `cdk.out` directory deleted if exists
- [ ] No background CDK processes running
- [ ] VS Code closed (if running CDK in external terminal)

### Deployment
- [ ] `cdk synth` runs successfully
- [ ] `cdk deploy --require-approval never` completes
- [ ] CloudFormation stack shows `CREATE_COMPLETE`
- [ ] API Gateway endpoint accessible
- [ ] Lambda function deployed
- [ ] DynamoDB tables created

### Post-Deployment
- [ ] Test API endpoints
- [ ] Check CloudWatch Logs for errors
- [ ] Subscribe to SNS topics
- [ ] Enable Bedrock model access (for Phase 2)
- [ ] Monitor costs after 24 hours

---

## Quick Reference Commands

### CDK Commands
```powershell
# Synthesize CloudFormation template
cdk synth

# Deploy stack
cdk deploy --require-approval never

# Destroy stack (WARNING: deletes all resources)
cdk destroy

# Show differences between deployed and local
cdk diff

# List all stacks
cdk list
```

### AWS CLI Commands
```powershell
# Verify identity
aws sts get-caller-identity

# List CloudFormation stacks
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE

# Describe stack
aws cloudformation describe-stacks --stack-name CostGuardStack

# View Lambda logs
aws logs tail /aws/lambda/CostGuardLambda --follow

# List DynamoDB tables
aws dynamodb list-tables

# Check costs
aws ce get-cost-and-usage \
  --time-period Start=2026-02-27,End=2026-02-28 \
  --granularity DAILY \
  --metrics UnblendedCost \
  --group-by Type=SERVICE
```

### Testing Commands
```powershell
# Test API endpoint (PowerShell)
Invoke-WebRequest -Uri "https://YOUR-API-URL/prod/api/prevention/status" -Method GET | Select-Object -ExpandProperty Content

# Test with POST data
Invoke-WebRequest -Uri "https://YOUR-API-URL/prod/api/fetch" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"start_date": "2026-02-01", "end_date": "2026-02-27", "granularity": "DAILY"}' | Select-Object -ExpandProperty Content
```

---

## Contact & Support

If you encounter issues not covered in this guide:

1. Check CloudWatch Logs: `aws logs tail /aws/lambda/CostGuardLambda --follow`
2. Review CDK output for error messages
3. Check AWS Console → CloudFormation for stack events
4. Verify IAM permissions are correct
5. Ensure all prerequisites are installed

---

**Document Version:** 1.0  
**Last Deployment:** February 27, 2026  
**Stack Name:** CostGuardStack  
**Region:** us-east-1  
**Account:** 456041708434
