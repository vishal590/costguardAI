# CDK Deployment Quick Reference

**Last Updated:** March 2, 2026  
**Purpose:** Quick solutions for common CDK deployment issues

**Tags:** `quick-reference` `cdk` `deployment` `errors` `fixes` `cheat-sheet` `troubleshooting`

**Related Documents:**
- [Full Troubleshooting Guide](./DEPLOYMENT_TROUBLESHOOTING.md) - Complete issue database
- [Phase 5 Success Report](../PHASE5_DEPLOYMENT_SUCCESS.md) - Latest deployment
- [Phase 5 Troubleshooting](../PHASE5_DEPLOYMENT_TROUBLESHOOTING.md) - Phase 5 specific
- [CDK Output Directory Fix](../CDK_OUTPUT_DIRECTORY_FIX.md) - Output configuration
- [Deployment README](./README.md) - Documentation hub

**Keywords for Search:** CDK quick fixes, common errors, deployment commands, troubleshooting cheat sheet, error solutions, CDK commands, verification commands, pre-deployment checklist

---

## 🚨 Common Errors & Quick Fixes

### Error: `AttributeError: module 'aws_cdk.aws_cloudwatch' has no attribute 'SnsAction'`

**Phase:** Phase 5 (Multi-Account)  
**Severity:** Critical (deployment blocker)  
**Tags:** `python-import` `cloudwatch-actions` `phase-5`

**Quick Fix:**
```python
# Add this import
from aws_cdk import aws_cloudwatch_actions as cloudwatch_actions

# Change this:
cloudwatch.SnsAction(topic)

# To this:
cloudwatch_actions.SnsAction(topic)
```

**File:** `infrastructure/multi_account_stack.py`

---

### Error: `cdk.out` folder in wrong location

**Phase:** All phases  
**Severity:** Medium (best practice)  
**Tags:** `working-directory` `cdk-output` `infrastructure-folder`

**Quick Fix:**
```powershell
# Always run from infrastructure directory
cd infrastructure
cdk deploy --require-approval never
```

**Cleanup if needed:**
```powershell
.\cleanup_cdk_out.ps1
```

---

### Error: `Another CLI (PID=XXXX) is currently synthing to cdk.out`

**Phase:** All phases  
**Severity:** Medium (blocks deployment)  
**Tags:** `process-lock` `node-process` `cdk-lock`

**Quick Fix:**
```powershell
# Kill node processes
Stop-Process -Name "node" -Force -ErrorAction SilentlyContinue

# Delete cdk.out
.\cleanup_cdk_out.ps1

# Try again
cd infrastructure
cdk deploy
```

---

### Error: Path too long / Recursive symlink

**Phase:** Phase 1-4 (historical)  
**Severity:** High (if encountered)  
**Tags:** `recursive-symlink` `lambda-assets` `path-too-long`

**Quick Fix:**
Ensure Lambda `from_asset()` has proper exclusions:
```python
code=lambda_.Code.from_asset(
    ".",
    exclude=[
        "cdk.out/*",
        "infrastructure/cdk.out/*",
        "infrastructure/*",
        ".git/*",
        ".hypothesis/*",
        ".kiro/*",
        "tests/*",
        "docs/*",
        "scripts/*",
        "*.md",
        ".coverage",
        ".pytest_cache/*",
        "__pycache__/*",
        "*.pyc",
        ".venv/*",
        "venv/*",
    ]
)
```

---

### Error: `SSM parameter /cdk-bootstrap/hnb659fds/version not found`

**Phase:** All phases (first deployment)  
**Severity:** Blocker (one-time setup)  
**Tags:** `cdk-bootstrap` `first-time-setup` `ssm-parameter`

**Quick Fix:**
```powershell
cd infrastructure
cdk bootstrap aws://ACCOUNT-ID/REGION
```

---

## ✅ Correct Deployment Process

### Phase 1-4 (CostGuardStack)
```powershell
cd infrastructure
cdk deploy CostGuardStack --require-approval never
```

### Phase 5 (CostGuardMultiAccountStack)
```powershell
cd infrastructure
cdk deploy CostGuardMultiAccountStack --require-approval never
```

### Deploy Both Stacks
```powershell
cd infrastructure
cdk deploy --all --require-approval never
```

---

## 📋 Pre-Deployment Checklist

- [ ] Virtual environment activated (`venv` or `.venv`)
- [ ] In `infrastructure/` directory
- [ ] No `cdk.out` folder in root
- [ ] No background CDK processes running
- [ ] AWS credentials configured
- [ ] CDK bootstrapped in target account/region

---

## 🔍 Verification Commands

### Check Stack Status
```powershell
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE
```

### Check Lambda Functions
```powershell
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `CostGuard`)].FunctionName'
```

### Check DynamoDB Tables
```powershell
aws dynamodb list-tables --query 'TableNames[?starts_with(@, `costguard`)]'
```

### Check API Gateway
```powershell
aws apigateway get-rest-apis --query 'items[?name==`CostGuardAPI` || name==`CostGuard-MultiAccountAPI`].[name,id]'
```

---

## 🛠️ Useful CDK Commands

```powershell
# Synthesize CloudFormation template (no deployment)
cdk synth

# Show differences between deployed and local
cdk diff

# List all stacks
cdk list

# Destroy stack (WARNING: deletes all resources)
cdk destroy CostGuardMultiAccountStack

# Deploy with verbose output
cdk deploy --verbose

# Deploy specific stack
cdk deploy CostGuardStack
```

---

## 📁 File Structure

```
aws-ideas/
├── infrastructure/
│   ├── app.py                    # CDK app entry point
│   ├── cdk_stack.py              # Phases 1-4 stack
│   ├── multi_account_stack.py    # Phase 5 stack
│   ├── cdk.json                  # CDK configuration
│   └── cdk.out/                  # Output directory (created here)
├── src/                          # Lambda source code
├── tests/                        # Test files
├── docs/                         # Documentation
├── .cdkignore                    # CDK ignore patterns
└── cleanup_cdk_out.ps1           # Cleanup script
```

---

## 🔗 Related Documentation

- [Full Deployment Troubleshooting Guide](./DEPLOYMENT_TROUBLESHOOTING.md)
- [Phase 5 Deployment Success Report](../PHASE5_DEPLOYMENT_SUCCESS.md)
- [Phase 5 Deployment Troubleshooting](../PHASE5_DEPLOYMENT_TROUBLESHOOTING.md)
- [CDK Output Directory Fix](../CDK_OUTPUT_DIRECTORY_FIX.md)

---

## 💡 Pro Tips

1. **Always run CDK from `infrastructure/` directory**
2. **Use `cleanup_cdk_out.ps1` if things get messy**
3. **Check CloudWatch Logs immediately after deployment**
4. **Test API endpoints right after deployment**
5. **Subscribe to SNS topics for alarm notifications**
6. **Monitor costs in AWS Cost Explorer after 24 hours**

---

**Quick Help:** If stuck, search error message in [DEPLOYMENT_TROUBLESHOOTING.md](./DEPLOYMENT_TROUBLESHOOTING.md)
