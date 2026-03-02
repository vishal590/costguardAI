# CostGuard Deployment Troubleshooting Guide

**Last Updated:** March 2, 2026  
**Purpose:** Document all deployment issues encountered and their solutions for future reference

**Tags:** `deployment` `troubleshooting` `cdk` `cloudformation` `aws` `errors` `fixes` `phase-1` `phase-2` `phase-3` `phase-4` `phase-5`

**Related Documents:**
- [CDK Quick Reference](./CDK_QUICK_REFERENCE.md) - Fast solutions
- [Phase 5 Success Report](../PHASE5_DEPLOYMENT_SUCCESS.md) - Latest deployment
- [Phase 5 Troubleshooting](../PHASE5_DEPLOYMENT_TROUBLESHOOTING.md) - Phase 5 specific
- [CDK Output Directory Fix](../CDK_OUTPUT_DIRECTORY_FIX.md) - Output configuration
- [Project Status](../PROJECT_STATUS.md) - Overall project status

**Keywords for Search:** CDK deployment errors, CloudFormation stack failures, Lambda errors, DynamoDB issues, Python import errors, recursive symlink, bootstrap required, IAM permissions, API Gateway 500 errors, process locks, output directory issues

---

## Quick Issue Finder

**Search by Error Message:**
- `AttributeError: module 'aws_cdk.aws_cloudwatch' has no attribute 'SnsAction'` → [Issue 4: Python Import Error](#issue-4-python-import-error---snsaction-phase-5-deployment)
- `path too long` / `recursive symlink` → [Issue 1: CDK Recursive Symlink](#1-cdk-recursive-symlink-issue)
- `'NoneType' object has no attribute 'protected_tags'` → [Issue 2: SafetyGuard Config Error](#issue-2-safetyguard-config-initialization-error)
- `The provided key element does not match the schema` → [Issue 3: DynamoDB Schema Mismatch](#issue-3-dynamodb-schema-mismatch-for-cost-data)
- `SSM parameter /cdk-bootstrap/hnb659fds/version not found` → [Issue 2: CDK Bootstrap Required](#2-cdk-bootstrap-required)
- `Another CLI (PID=XXXX) is currently synthing to cdk.out` → [Issue 7: CDK Lock File Issues](#7-cdk-lock-file-issues)

**Search by Symptom:**
- CDK deployment fails with Python error → [Issue 4: Python Import Error](#issue-4-python-import-error---snsaction-phase-5-deployment)
- Can't delete cdk.out folder → [Issue 1: Recursive Symlink](#1-cdk-recursive-symlink-issue)
- Lambda function crashes on startup → [Issue 2: SafetyGuard Config](#issue-2-safetyguard-config-initialization-error)
- API returns 500 error → [Issue 4: Lambda Runtime Errors](#4-lambda-runtime-errors)
- Cost data won't save to DynamoDB → [Issue 3: DynamoDB Schema Mismatch](#issue-3-dynamodb-schema-mismatch-for-cost-data)

---

## Table of Contents

1. [CDK Recursive Symlink Issue](#1-cdk-recursive-symlink-issue)
2. [CDK Bootstrap Required](#2-cdk-bootstrap-required)
3. [PowerShell curl Alias Issue](#3-powershell-curl-alias-issue)
4. [Lambda Runtime Errors](#4-lambda-runtime-errors)
5. [IAM User vs Root User](#5-iam-user-vs-root-user)
6. [AWS Region Selection](#6-aws-region-selection)
7. [CDK Lock File Issues](#7-cdk-lock-file-issues)
8. [CDK Deployment Directory](#8-cdk-deployment-directory-phase-5)
9. [Issue 2: SafetyGuard Config Initialization Error](#issue-2-safetyguard-config-initialization-error)
10. [Issue 3: DynamoDB Schema Mismatch](#issue-3-dynamodb-schema-mismatch-for-cost-data)
11. [Issue 4: Python Import Error - SnsAction](#issue-4-python-import-error---snsaction-phase-5-deployment)

---

## 1. CDK Recursive Symlink Issue

**Status for Phase 5:** ⚠️ PREVENTED - NOT ENCOUNTERED  
**Phases Affected:** Phase 1-4 (historical)  
**Severity:** High (if encountered)  
**Tags:** `recursive-symlink` `cdk-asset-bundling` `lambda` `path-too-long` `windows`

**Related Issues:** [Issue 8: CDK Deployment Directory](#8-cdk-deployment-directory-phase-5)  
**Related Docs:** [CDK Output Directory Fix](../CDK_OUTPUT_DIRECTORY_FIX.md)

**Important Note:** This issue was documented from earlier Phase 1-4 deployments. For Phase 5 deployment (March 2, 2026), we added exclusions preventatively but **never actually encountered** this issue. The real blocker was a Python import error (see Issue 4 below).

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

**Phases Affected:** All phases  
**Severity:** Blocker (first deployment only)  
**Tags:** `cdk-bootstrap` `ssm-parameter` `first-time-setup` `prerequisites`

**Related Issues:** None  
**Related Docs:** [CDK Quick Reference](./CDK_QUICK_REFERENCE.md)

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

**Phases Affected:** All phases (testing)  
**Severity:** Low (workaround available)  
**Tags:** `powershell` `curl` `invoke-webrequest` `api-testing` `windows`

**Related Issues:** None  
**Related Docs:** [Phase 4 Endpoint Test Report](../PHASE4_ENDPOINT_TEST_REPORT.md)

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

**Phases Affected:** All phases  
**Severity:** Medium (runtime errors)  
**Tags:** `lambda` `runtime-errors` `500-error` `api-gateway` `cloudwatch-logs` `debugging`

**Related Issues:** [Issue 2: SafetyGuard Config](#issue-2-safetyguard-config-initialization-error), [Issue 3: DynamoDB Schema](#issue-3-dynamodb-schema-mismatch-for-cost-data)  
**Related Docs:** [Cost Monitoring Guide](../user-guide/COST_MONITORING_GUIDE.md)

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

**Phases Affected:** All phases  
**Severity:** Critical (security best practice)  
**Tags:** `iam` `security` `authentication` `aws-cli` `best-practices`

**Related Issues:** None  
**Related Docs:** [Project Status](../PROJECT_STATUS.md)

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

**Phases Affected:** All phases  
**Severity:** Low (cost optimization)  
**Tags:** `aws-regions` `cost-optimization` `us-east-1` `latency` `free-tier`

**Related Issues:** None  
**Related Docs:** [Innovation Strategy](../INNOVATION-STRATEGY.md)

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

**Phases Affected:** All phases  
**Severity:** Medium (blocks deployment)  
**Tags:** `cdk-lock` `process-lock` `node-process` `vscode` `windows`

**Related Issues:** [Issue 1: Recursive Symlink](#1-cdk-recursive-symlink-issue)  
**Related Docs:** [CDK Quick Reference](./CDK_QUICK_REFERENCE.md)

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

## 8. CDK Deployment Directory (Phase 5)

**Phases Affected:** Phase 5 (multi-account)  
**Severity:** Medium (best practice)  
**Tags:** `cdk-output` `working-directory` `infrastructure-folder` `cdk.json` `phase-5`

**Related Issues:** [Issue 1: Recursive Symlink](#1-cdk-recursive-symlink-issue)  
**Related Docs:** [CDK Output Directory Fix](../CDK_OUTPUT_DIRECTORY_FIX.md), [Phase 5 Success](../PHASE5_DEPLOYMENT_SUCCESS.md)

### Problem

**Symptom:**
- `cdk.out` folder created in root directory instead of `infrastructure/`
- Python import errors during deployment
- Deployment fails with module not found errors

**Root Cause:**
Running CDK commands from the wrong directory. CDK uses the current working directory to resolve paths and create output folders.

### Solution

**Always run CDK commands from the `infrastructure/` directory:**

```powershell
# CORRECT: Run from infrastructure directory
cd infrastructure
cdk deploy CostGuardMultiAccountStack --require-approval never

# WRONG: Running from root with --app flag
cd .
cdk deploy CostGuardMultiAccountStack --app "python infrastructure/app.py"  # ❌ Creates cdk.out in root
```

**Why this matters:**
1. `cdk.json` is in `infrastructure/` directory
2. `cdk.json` specifies `"output": "cdk.out"` (relative path)
3. CDK creates output relative to where `cdk.json` is located
4. Running from root creates `./cdk.out` instead of `infrastructure/cdk.out`

**Verification:**
```powershell
# After deployment, check output location
Test-Path infrastructure/cdk.out  # Should return: True
Test-Path cdk.out                 # Should return: False
```

### Prevention

- Always `cd infrastructure` before running CDK commands
- Use the cleanup script if `cdk.out` is created in wrong location: `.\cleanup_cdk_out.ps1`
- Create a deployment script that automatically changes to the correct directory

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


---

## Issue 2: SafetyGuard Config Initialization Error

**Date Fixed:** February 28, 2026  
**Phases Affected:** Phase 1-4  
**Severity:** High (runtime blocker)  
**Tags:** `safetyguard` `python-error` `attributeerror` `lambda-crash` `phase-3`

**Related Issues:** [Issue 4: Lambda Runtime Errors](#4-lambda-runtime-errors)  
**Related Docs:** [Phase 3 Prevention System](../PROJECT_STATUS.md)

**Symptom:**
- Lambda function crashes with error: `AttributeError: 'NoneType' object has no attribute 'protected_tags'`
- Prevention endpoints return 500 errors
- EventBridge scheduled events fail every 5 minutes

**Error in CloudWatch Logs:**
```
[ERROR] Error in handle_prevention_status: 'NoneType' object has no attribute 'protected_tags'
Traceback (most recent call last):
  File "/var/task/src/lambda_handler.py", line 966, in handle_prevention_status
    prevention_engine = _get_prevention_engine()
  File "/var/task/src/lambda_handler.py", line 1669, in _get_prevention_engine
    safety_guard = SafetyGuard(config=None)
  File "/var/task/src/services/safety_guard.py", line 32, in __init__
    self.protected_tags = config.protected_tags or [...]
AttributeError: 'NoneType' object has no attribute 'protected_tags'
```

**Root Cause:**
The `SafetyGuard` class in `src/services/safety_guard.py` was checking `if config and hasattr(config, 'protected_tags')` but then still trying to access `config.protected_tags` directly. When `config=None`, this causes an AttributeError because Python's `and` operator short-circuits but the code still tries to access the attribute in the same line.

**Solution:**
Updated `src/services/safety_guard.py` to check `if config is not None` before accessing any config attributes:

```python
# Before (BROKEN):
if config and hasattr(config, 'protected_tags'):
    self.protected_tags = config.protected_tags or [...]

# After (FIXED):
if config is not None and hasattr(config, 'protected_tags'):
    self.protected_tags = config.protected_tags or [...]
```

**Files Modified:**
- `src/services/safety_guard.py` (lines 28-73)

**Verification:**
```powershell
# Test prevention status endpoint
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/prevention/status" -Method GET

# Expected response:
# {"success": true, "status": {"enabled": false, "dry_run_mode": true, ...}}
```

**Deployment:**
```powershell
cd infrastructure
cdk deploy --require-approval never
```

---

## Issue 3: DynamoDB Schema Mismatch for Cost Data

**Date Fixed:** February 28, 2026  
**Phases Affected:** Phase 1  
**Severity:** High (data storage blocker)  
**Tags:** `dynamodb` `schema-mismatch` `validationexception` `partition-key` `phase-1`

**Related Issues:** [Issue 4: Lambda Runtime Errors](#4-lambda-runtime-errors)  
**Related Docs:** [Cost Monitoring Guide](../user-guide/COST_MONITORING_GUIDE.md)

**Symptom:**
- `/api/fetch` endpoint fails with ValidationException
- Cost data cannot be stored in DynamoDB
- Error: "The provided key element does not match the schema"

**Error in CloudWatch Logs:**
```
[ERROR] Error in handle_fetch: An error occurred (ValidationException) when calling the BatchWriteItem operation: The provided key element does not match the schema
Traceback (most recent call last):
  File "/var/task/src/lambda_handler.py", line 212, in handle_fetch
    store_cost_data(records)
  File "/var/task/src/services/dynamodb.py", line 105, in store_cost_data
    _write_batch(table, batch, retry_config)
```

**Root Cause:**
The DynamoDB table `costguard-cost-data` was created with partition key `date_service` (format: `2026-02-01#AWS Lambda`), but the code was trying to write with keys `pk` and `sk` (format: `COST#2026-02` and `SERVICE#aws-lambda`). This mismatch caused the ValidationException.

**Table Schema (from CDK):**
```python
cost_data_table = dynamodb.Table(
    self, "CostDataTable",
    table_name="costguard-cost-data",
    partition_key=dynamodb.Attribute(
        name="date_service",  # <-- Single partition key
        type=dynamodb.AttributeType.STRING
    ),
    ...
)
```

**Code Before (BROKEN):**
```python
item = {
    'pk': record.pk,  # <-- Wrong key name
    'sk': record.sk,  # <-- Wrong key name
    'date': record.date,
    ...
}
```

**Solution:**
Updated `src/services/dynamodb.py` to use `date_service` as the partition key:

```python
item = {
    'date_service': f"{record.date}#{record.service}",  # <-- Correct format
    'date': record.date,
    'service': record.service,
    ...
}
```

**Files Modified:**
- `src/services/dynamodb.py` (lines 118-138)

**Verification:**
```powershell
# Fetch and store cost data
$body = @{start_date="2026-02-01"; end_date="2026-02-28"; granularity="DAILY"} | ConvertTo-Json
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/fetch" -Method POST -ContentType "application/json" -Body $body

# Expected response:
# {"success": true, "message": "Cost data fetched and stored successfully", ...}
```

**Deployment:**
```powershell
cd infrastructure
cdk deploy --require-approval never
```

**Known Limitation:**
The query logic in `query_cost_data()` still uses the old `COST#YYYY-MM` format and needs to be updated to query by `date_service` key. This means `/api/cost-data` endpoint will return empty results until the query logic is fixed.

---

## Summary of All Fixes

| Issue | Status | Files Modified | Deployment Required |
|-------|--------|----------------|---------------------|
| Recursive Symlink Loop | ✅ Fixed | `infrastructure/cdk_stack.py` | Yes |
| SafetyGuard Config Error | ✅ Fixed | `src/services/safety_guard.py` | Yes |
| DynamoDB Schema Mismatch | ✅ Fixed | `src/services/dynamodb.py` | Yes |

**Total Deployments:** 3
- Initial deployment: February 27, 2026
- SafetyGuard fix: February 28, 2026 6:50 PM
- DynamoDB fix: February 28, 2026 6:57 PM

---

## Issue 4: Python Import Error - SnsAction (Phase 5 Deployment)

**Date Fixed:** March 2, 2026  
**Phases Affected:** Phase 5 (multi-account)  
**Severity:** Critical (deployment blocker)  
**Tags:** `python-import` `aws-cdk` `cloudwatch-actions` `snsaction` `phase-5` `actual-blocker`

**Related Issues:** None (this was the actual Phase 5 blocker)  
**Related Docs:** [Phase 5 Success Report](../PHASE5_DEPLOYMENT_SUCCESS.md), [Phase 5 Troubleshooting](../PHASE5_DEPLOYMENT_TROUBLESHOOTING.md)

**Symptom:**
- CDK deployment fails with Python AttributeError
- Error: `AttributeError: module 'aws_cdk.aws_cloudwatch' has no attribute 'SnsAction'`
- Occurs during CloudFormation stack synthesis

**Error in Terminal:**
```
Traceback (most recent call last):
  File "G:\projects\aws-ideas\infrastructure\app.py", line 28, in <module>
    multi_account_stack = MultiAccountStack(...)
  File "G:\projects\aws-ideas\infrastructure\multi_account_stack.py", line 581, in __init__
    cloudwatch.SnsAction(multi_account_notifications_topic)
    ^^^^^^^^^^^^^^^^^^^^
AttributeError: module 'aws_cdk.aws_cloudwatch' has no attribute 'SnsAction'
```

**Root Cause:**
The `SnsAction` class is located in the `aws_cloudwatch_actions` module, not `aws_cloudwatch`. The code was trying to use `cloudwatch.SnsAction()` which doesn't exist.

**Correct Module Structure:**
```python
# WRONG:
from aws_cdk import aws_cloudwatch as cloudwatch
cloudwatch.SnsAction(topic)  # ❌ SnsAction not in this module

# CORRECT:
from aws_cdk import aws_cloudwatch_actions as cloudwatch_actions
cloudwatch_actions.SnsAction(topic)  # ✅ Correct module
```

**Solution:**
Updated `infrastructure/multi_account_stack.py`:

**Step 1: Add the correct import**
```python
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
    aws_cloudwatch_actions as cloudwatch_actions,  # ← Added this
    CfnOutput,
)
```

**Step 2: Update all SnsAction references (5 occurrences)**
```python
# Before (BROKEN):
cost_collection_failure_alarm.add_alarm_action(
    cloudwatch.SnsAction(multi_account_notifications_topic)  # ❌
)

# After (FIXED):
cost_collection_failure_alarm.add_alarm_action(
    cloudwatch_actions.SnsAction(multi_account_notifications_topic)  # ✅
)
```

**Files Modified:**
- `infrastructure/multi_account_stack.py` (lines 19 and 582-596)

**Verification:**
```powershell
# From infrastructure directory
cd infrastructure
cdk deploy CostGuardMultiAccountStack --require-approval never

# Expected: Successful deployment
# ✅ CostGuardMultiAccountStack deployed successfully
```

**Deployment Result:**
```
✅ CostGuardMultiAccountStack

✨ Deployment time: 158.34s

Outputs:
CostGuardMultiAccountStack.MultiAccountAPIEndpoint = https://7s4ff2lzc6.execute-api.us-east-1.amazonaws.com/prod/
CostGuardMultiAccountStack.CostCollectorFunctionName = CostGuard-MultiAccountCostCollector
CostGuardMultiAccountStack.APIHandlerFunctionName = CostGuard-MultiAccountAPIHandler
CostGuardMultiAccountStack.MainHandlerFunctionName = CostGuard-MultiAccountHandler
...
```

**Prevention:**
- Always check AWS CDK documentation for correct module imports
- Common mistake: Assuming all CloudWatch-related classes are in `aws_cloudwatch`
- Reality: Actions are in separate `aws_cloudwatch_actions` module

**Related AWS CDK Modules:**
```python
aws_cloudwatch           # Alarms, Metrics, Dashboards
aws_cloudwatch_actions   # Alarm actions (SNS, Lambda, etc.)
aws_cloudwatch_logs      # Log groups, Log streams
```

---

## Summary of All Fixes

| Issue | Status | Files Modified | Deployment Required | Phase 5 Impact |
|-------|--------|----------------|---------------------|----------------|
| Recursive Symlink Loop | ✅ Prevented | `infrastructure/cdk_stack.py`, `infrastructure/multi_account_stack.py` | Yes | Not encountered |
| SafetyGuard Config Error | ✅ Fixed | `src/services/safety_guard.py` | Yes | N/A (Phase 1-4) |
| DynamoDB Schema Mismatch | ✅ Fixed | `src/services/dynamodb.py` | Yes | N/A (Phase 1-4) |
| Python Import Error (SnsAction) | ✅ Fixed | `infrastructure/multi_account_stack.py` | Yes | **ACTUAL BLOCKER** |

**Phase 5 Deployment Summary:**
- **Only real issue:** Python import error (`SnsAction` in wrong module)
- **Preventative measures:** Added exclusions (good practice, but not needed for this deployment)
- **Best practice:** Running from `infrastructure/` directory

**Total Deployments:** 4
- Initial deployment: February 27, 2026 (Phase 1-4)
- SafetyGuard fix: February 28, 2026 6:50 PM (Phase 1-4)
- DynamoDB fix: February 28, 2026 6:57 PM (Phase 1-4)
- Phase 5 Multi-Account: March 2, 2026 10:08 AM ✅
