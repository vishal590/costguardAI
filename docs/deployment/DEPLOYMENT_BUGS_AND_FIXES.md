# CostGuard Deployment Issues and Fixes - Complete Reference

**Last Updated:** March 3, 2026  
**Purpose:** Comprehensive troubleshooting guide for all deployment issues encountered from Phase 1 to Phase 6

---

## Table of Contents

1. [Phase 1-4 Issues](#phase-1-4-issues)
2. [Phase 5 Issues](#phase-5-issues)
3. [Phase 6 Issues](#phase-6-issues)
4. [Common Patterns](#common-patterns)
5. [Quick Reference](#quick-reference)

---

## Phase 1-4 Issues

### Issue 1.1: CDK Bootstrap Not Configured

**Symptom:**
```
Error: This stack uses assets, so the toolkit stack must be deployed to the environment
```

**Root Cause:**
- CDK toolkit (bootstrap stack) not deployed in the AWS account/region
- Required for deploying stacks with assets (Lambda code, etc.)

**Solution:**
```bash
cd infrastructure
cdk bootstrap
```

**Prevention:**
- Always run `cdk bootstrap` before first deployment in a new account/region
- Check if `CDKToolkit` stack exists: `aws cloudformation list-stacks`

---

### Issue 1.2: Lambda Package Size Warnings

**Symptom:**
- Deployment succeeds but Lambda package is large (>50MB)
- Slow deployment times

**Root Cause:**
- Including unnecessary files in Lambda package (tests, docs, .git, etc.)

**Solution:**
Update `infrastructure/cdk_stack.py` exclusions:
```python
code=lambda_.Code.from_asset(
    ".",
    exclude=[
        "cdk.out",
        "infrastructure",
        ".git",
        ".hypothesis",
        ".kiro",
        "tests",
        "docs",
        "scripts",
        "*.md",
        ".coverage",
        ".pytest_cache",
        "__pycache__",
        "*.pyc",
        ".venv",
        "venv",
    ]
)
```

**Prevention:**
- Use directory names without wildcards for better matching
- Test package size before deployment: `cdk synth --quiet`

---

### Issue 1.3: DynamoDB Table Already Exists

**Symptom:**
```
Resource of type 'AWS::DynamoDB::Table' with identifier 'costguard-cost-data' already exists
```

**Root Cause:**
- Table from previous deployment still exists
- `RemovalPolicy.RETAIN` prevents automatic deletion

**Solution:**
```bash
# Option 1: Delete table manually
aws dynamodb delete-table --table-name costguard-cost-data

# Option 2: Import existing table into stack
cdk import CostGuardStack
```

**Prevention:**
- Use `RemovalPolicy.DESTROY` for development environments
- Document table retention policy in deployment guide

---

## Phase 5 Issues

### Issue 5.1: CDK Output Directory Accumulation

**Symptom:**
- `cdk.out` directory grows to several GB
- Deployment becomes slow
- "File size is greater than 2 GiB" error

**Root Cause:**
- CDK doesn't clean up old assets from `cdk.out`
- Multiple deployments accumulate asset files

**Solution:**
```bash
# Clean cdk.out directory
cd infrastructure
Remove-Item -Path cdk.out -Recurse -Force

# Or use cleanup script
.\cleanup_cdk_out.ps1
```

**Prevention:**
- Clean `cdk.out` before major deployments
- Add cleanup to deployment scripts
- See: `docs/CDK_OUTPUT_DIRECTORY_FIX.md`

---

### Issue 5.2: API Authentication Tables Missing

**Symptom:**
```
ResourceNotFoundException: Requested resource not found: Table: costguard-api-keys
```

**Root Cause:**
- API authentication tables (`costguard-api-keys`, `costguard-rate-limits`) not created
- These tables are created separately by `setup_api_auth.py`, not by CDK

**Solution:**
```bash
# Create authentication tables
python setup_api_auth.py
```

**Prevention:**
- Run `setup_api_auth.py` after Phase 5 deployment
- Document in deployment guide
- See: `docs/PHASE5_AUTHENTICATION_FIX_REPORT.md`

---

### Issue 5.3: Method Signature Mismatches

**Symptom:**
```
TypeError: get_organization_structure() missing 1 required positional argument: 'org_id'
```

**Root Cause:**
- Service layer methods had incorrect signatures
- Handler was calling methods with wrong parameters

**Solution:**
Update method signatures in service layer to match handler expectations:
```python
# Before
def get_organization_structure(self, org_id: str) -> Dict[str, Any]:

# After
def get_organization_structure(self) -> Dict[str, Any]:
```

**Prevention:**
- Write integration tests that test handler → service layer calls
- Use type hints and mypy for static type checking
- See: `docs/PHASE5_METHOD_SIGNATURE_FIXES.md`

---

### Issue 5.4: Cross-Account Role Not Created

**Symptom:**
```
AccessDenied: User is not authorized to perform: sts:AssumeRole on resource: arn:aws:iam::*:role/CostGuardCrossAccountRole
```

**Root Cause:**
- Cross-account role `CostGuardCrossAccountRole` not created in member accounts
- Required for multi-account cost collection

**Solution:**
Create role in each member account:
```bash
# Use CloudFormation StackSet or manually create in each account
aws cloudformation create-stack \
  --stack-name CostGuardCrossAccountRole \
  --template-body file://cross-account-role.yaml \
  --capabilities CAPABILITY_NAMED_IAM
```

**Prevention:**
- Document cross-account setup in deployment guide
- Provide CloudFormation template for cross-account role
- See: `docs/PHASE5_DEPLOYMENT_TROUBLESHOOTING.md`

---

## Phase 6 Issues

### Issue 6.1: Lambda Package Size Exceeded (CRITICAL)

**Symptom:**
```
Unzipped size must be smaller than 262144000 bytes (Service: Lambda, Status Code: 400)
```

**Root Cause:**
- Phase 6 infrastructure was added to existing `CostGuardStack` (Phases 1-4)
- Combined Lambda package exceeded AWS's 250MB limit
- `CostGuardStack` already had ~200MB of code

**Solution:**
Create separate stack for Phase 6 (following Phase 5 pattern):

1. **Create new stack file:** `infrastructure/aiml_stack.py`
```python
class AIMLStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        # Phase 6 infrastructure only
```

2. **Update app.py:**
```python
from aiml_stack import AIMLStack

aiml_stack = AIMLStack(
    app, "CostGuardAIMLStack",
    description="CostGuard - AI/ML Workload Cost Management System (Phase 6)",
)
aiml_stack.add_dependency(costguard_stack)
aiml_stack.add_dependency(multi_account_stack)
```

3. **Remove Phase 6 from cdk_stack.py:**
- Remove Phase 6 DynamoDB tables
- Remove Phase 6 API endpoints
- Remove Phase 6 IAM permissions

4. **Deploy only Phase 6:**
```bash
cd infrastructure
cdk deploy CostGuardAIMLStack --exclusively --require-approval never
```

**Prevention:**
- Use separate stacks for large features (>50MB of code)
- Monitor Lambda package sizes during development
- Follow the pattern: 1 stack per major phase
- See: `docs/PHASE6_SEPARATE_STACK_ARCHITECTURE.md`

---

### Issue 6.2: CDK File Size Error (2GB Limit)

**Symptom:**
```
RangeError [ERR_FS_FILE_TOO_LARGE]: File size (2948076183) is greater than 2 GiB
```

**Root Cause:**
- `venv` directory (378MB) was being included in Lambda package
- CDK exclusions used wildcards (`venv/*`) which didn't match properly
- Combined with accumulated `cdk.out` assets, exceeded Node.js file size limit

**Solution:**

1. **Fix CDK exclusions (remove wildcards):**
```python
code=lambda_.Code.from_asset(
    "..",
    exclude=[
        "cdk.out",      # Not "cdk.out/*"
        "infrastructure",
        ".git",
        "venv",         # Not "venv/*"
        ".venv",
        "tests",
        "docs",
        # ... other exclusions
    ]
)
```

2. **Clean cdk.out directory:**
```bash
cd infrastructure
Remove-Item -Path cdk.out -Recurse -Force
```

3. **Deploy with --exclusively flag:**
```bash
cdk deploy CostGuardAIMLStack --exclusively --require-approval never
```

**Prevention:**
- Use directory names without wildcards in exclusions
- Clean `cdk.out` before deployments
- Use `--exclusively` flag to avoid rebuilding dependency stacks
- See: `docs/PHASE6_DEPLOYMENT_ATTEMPT.md`

---

### Issue 6.3: Partial Deployment Rollback

**Symptom:**
- DynamoDB tables created successfully
- Lambda deployment failed
- Tables automatically deleted during rollback

**Root Cause:**
- CloudFormation rolls back entire stack on any failure
- `RemovalPolicy.RETAIN` doesn't prevent rollback deletion

**Solution:**
- Fix the root cause (Lambda package size)
- Redeploy the entire stack
- Tables will be recreated

**Prevention:**
- Test deployments in development environment first
- Use `cdk diff` to preview changes before deployment
- Monitor deployment progress in CloudFormation console

---

## Common Patterns

### Pattern 1: Stack Architecture

**Best Practice:**
```
Project Structure:
├── CostGuardStack (Phases 1-4) - Single account features
├── CostGuardMultiAccountStack (Phase 5) - Multi-account features
└── CostGuardAIMLStack (Phase 6) - AI/ML features
```

**Why:**
- Keeps Lambda packages small (<50MB each)
- Enables independent deployment
- Reduces blast radius of changes
- Follows AWS best practices

---

### Pattern 2: CDK Exclusions

**Best Practice:**
```python
exclude=[
    "cdk.out",          # Not "cdk.out/*"
    "infrastructure",   # Not "infrastructure/*"
    ".git",
    ".venv",
    "venv",
    "tests",
    "docs",
    "__pycache__",
    "*.pyc",
]
```

**Why:**
- Directory names without wildcards match better
- Prevents accidental inclusion of large directories
- Reduces Lambda package size

---

### Pattern 3: Deployment Order

**Best Practice:**
```bash
# 1. Bootstrap (first time only)
cdk bootstrap

# 2. Deploy base stack
cdk deploy CostGuardStack

# 3. Deploy Phase 5
cdk deploy CostGuardMultiAccountStack

# 4. Setup authentication
python setup_api_auth.py

# 5. Deploy Phase 6
cdk deploy CostGuardAIMLStack --exclusively
```

**Why:**
- Ensures dependencies are met
- Prevents deployment failures
- Enables rollback at each step

---

### Pattern 4: Troubleshooting Workflow

**Best Practice:**
```bash
# 1. Check stack status
aws cloudformation describe-stacks --stack-name <StackName>

# 2. Check for stuck stacks
aws cloudformation list-stacks --stack-status-filter CREATE_IN_PROGRESS UPDATE_IN_PROGRESS

# 3. Clean cdk.out if needed
Remove-Item -Path cdk.out -Recurse -Force

# 4. Preview changes
cdk diff <StackName>

# 5. Deploy with verbose output
cdk deploy <StackName> --require-approval never --verbose
```

---

## Quick Reference

### Lambda Package Size Issues

| Symptom | Root Cause | Solution |
|---------|-----------|----------|
| Package > 250MB | Too much code in one stack | Create separate stack |
| Package > 50MB | Including unnecessary files | Fix CDK exclusions |
| File > 2GB error | `venv` included + large `cdk.out` | Fix exclusions + clean `cdk.out` |

### Deployment Failures

| Symptom | Root Cause | Solution |
|---------|-----------|----------|
| Stack stuck IN_PROGRESS | Previous deployment interrupted | Wait or delete stack |
| Table already exists | Previous deployment retained table | Delete table or import |
| Role not found | Cross-account role not created | Create role in member accounts |
| API keys table missing | Authentication not setup | Run `setup_api_auth.py` |

### CDK Issues

| Symptom | Root Cause | Solution |
|---------|-----------|----------|
| Bootstrap required | CDK not initialized | Run `cdk bootstrap` |
| cdk.out too large | Old assets accumulated | Clean `cdk.out` directory |
| Dependency error | Wrong deployment order | Deploy stacks in order |

---

## Deployment Checklist

### Before Deployment

- [ ] Clean `cdk.out` directory
- [ ] Run `cdk diff` to preview changes
- [ ] Check Lambda package size (`cdk synth --quiet`)
- [ ] Verify no stacks are stuck IN_PROGRESS
- [ ] Ensure CDK is bootstrapped

### During Deployment

- [ ] Monitor CloudFormation console
- [ ] Watch for errors in terminal output
- [ ] Check Lambda package size in logs
- [ ] Verify resources are being created

### After Deployment

- [ ] Verify stack status is CREATE_COMPLETE or UPDATE_COMPLETE
- [ ] Test API endpoints
- [ ] Check CloudWatch logs for errors
- [ ] Run authentication setup if needed (Phase 5)
- [ ] Update documentation

---

## Emergency Procedures

### Stack Stuck in IN_PROGRESS

```bash
# Check status
aws cloudformation describe-stacks --stack-name <StackName>

# If truly stuck (>30 minutes), delete and redeploy
aws cloudformation delete-stack --stack-name <StackName>

# Wait for deletion
aws cloudformation wait stack-delete-complete --stack-name <StackName>

# Redeploy
cdk deploy <StackName>
```

### Rollback Failed Deployment

```bash
# Check what failed
aws cloudformation describe-stack-events --stack-name <StackName> --max-items 20

# Delete stack
cdk destroy <StackName>

# Fix issue
# ... make code changes ...

# Redeploy
cdk deploy <StackName>
```

### Lambda Package Too Large

```bash
# Option 1: Create separate stack (recommended)
# See Issue 6.1 above

# Option 2: Use Lambda Layers
# Move large dependencies to layers

# Option 3: Use container images
# Package Lambda as Docker container (up to 10GB)
```

---

## Contact and Support

### Documentation References

- **Phase 5 Issues:** `docs/PHASE5_DEPLOYMENT_TROUBLESHOOTING.md`
- **Phase 6 Issues:** `docs/PHASE6_DEPLOYMENT_ATTEMPT.md`
- **CDK Issues:** `docs/CDK_OUTPUT_DIRECTORY_FIX.md`
- **Architecture:** `docs/PHASE6_SEPARATE_STACK_ARCHITECTURE.md`

### Useful Commands

```bash
# List all stacks
aws cloudformation list-stacks

# Describe specific stack
aws cloudformation describe-stacks --stack-name <StackName>

# Get stack outputs
aws cloudformation describe-stacks --stack-name <StackName> --query 'Stacks[0].Outputs'

# List DynamoDB tables
aws dynamodb list-tables

# Check Lambda function
aws lambda get-function --function-name <FunctionName>

# View CloudWatch logs
aws logs tail /aws/lambda/<FunctionName> --follow
```

---

**Last Updated:** March 3, 2026  
**Version:** 1.0  
**Maintainer:** CostGuard Development Team


---

## Issue 7: CDK Asset Path Including Sibling Projects (March 4, 2026)

**Severity:** HIGH  
**Status:** ✅ RESOLVED  
**Affected:** Phase 6 AIML Stack

### Symptom

- `cdk.out/` directory contained folders from sibling projects (`ai_good`, `algolia`)
- Large deployment package size (~500MB+)
- Unrelated project files appearing in CDK asset staging
- File tree showing modified files from other projects outside aws-ideas

### Root Cause

In `infrastructure/aiml_stack.py` line 287, the Lambda asset path was incorrectly set to `".."`:

```python
code=lambda_.Code.from_asset(
    "..",  # WRONG - Points to parent directory G:\projects\
    exclude=[...]
)
```

This caused CDK to go UP one level from `infrastructure/` to the parent `projects/` directory, bundling ALL sibling projects.

**Directory Structure:**
```
G:\projects\
├── ai_good/          ← Incorrectly included
├── algolia/          ← Incorrectly included
└── aws-ideas/        ← Current project
    └── infrastructure/
        └── aiml_stack.py (using ".." went to G:\projects\)
```

### Solution

**Step 1: Fix the asset path**

Changed from `".."` to `"."` in `infrastructure/aiml_stack.py`:

```python
# CORRECT
code=lambda_.Code.from_asset(
    ".",  # Points to aws-ideas project root
    exclude=[...]
)
```

**Step 2: Clean up contaminated cdk.out**

```powershell
Remove-Item -Recurse -Force cdk.out
```

### Prevention

1. **Always use `"."` for project root** in CDK asset paths
2. **Verify `cdk.out/` after synthesis** - should only contain project files
3. **Check deployment package size** - should be <50MB for Lambda
4. **Review CDK asset paths** before deployment

### Verification

After fix:
- ✅ Deployment package: ~10MB (only aws-ideas project)
- ✅ No sibling project directories in `cdk.out/`
- ✅ Build time: <1 minute

### Related Documentation

- [CDK_ASSET_PATH_BUG_FIX.md](./CDK_ASSET_PATH_BUG_FIX.md) - Detailed analysis and prevention guidelines
- `infrastructure/aiml_stack.py` - Fixed file (line 287)
- `.cdkignore` - Exclude patterns for CDK assets

---
