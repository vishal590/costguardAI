# Deployment Documentation Index

**Quick Navigation:** All deployment-related documentation in one place

---

## 📋 Quick Start

**New to deployment?** Start here:
1. Read [DEPLOYMENT_PLAN.md](./DEPLOYMENT_PLAN.md) - Complete deployment guide
2. Follow the prerequisites checklist
3. Run deployment commands
4. If issues occur, check [DEPLOYMENT_TROUBLESHOOTING.md](./DEPLOYMENT_TROUBLESHOOTING.md)

---

## 📚 Documentation Files

### 1. DEPLOYMENT_STATUS.md
**Purpose:** Current deployment status and details  
**When to use:** Check if system is deployed, get API endpoint, see what's live  
**Key info:**
- Deployment status (✅ DEPLOYED)
- API Gateway endpoint
- Resources created
- Next steps

[View DEPLOYMENT_STATUS.md](./DEPLOYMENT_STATUS.md)

---

### 2. DEPLOYMENT_PLAN.md
**Purpose:** Complete phase-by-phase deployment guide  
**When to use:** Planning or executing deployment  
**Key info:**
- Prerequisites setup
- Phase 1-6 deployment steps
- Validation commands
- Cost estimates per phase
- Timeline estimates

[View DEPLOYMENT_PLAN.md](./DEPLOYMENT_PLAN.md)

---

### 3. DEPLOYMENT_TROUBLESHOOTING.md ⭐ IMPORTANT
**Purpose:** Solutions to all deployment issues  
**When to use:** When deployment fails or encounters errors  
**Key info:**
- CDK recursive symlink issue (CRITICAL)
- CDK bootstrap requirements
- PowerShell curl alias issues
- Lambda runtime errors
- IAM user vs root user
- AWS region selection
- Quick reference commands

[View DEPLOYMENT_TROUBLESHOOTING.md](./DEPLOYMENT_TROUBLESHOOTING.md)

---

### 4. DEPLOYMENT_SUMMARY.md
**Purpose:** Quick summary of what was deployed  
**When to use:** Quick reference for deployment details  
**Key info:**
- Resources created
- Issues encountered and fixed
- Documentation updates
- Key learnings
- Next steps

[View DEPLOYMENT_SUMMARY.md](./DEPLOYMENT_SUMMARY.md)

---

### 5. COST_MONITORING_GUIDE.md
**Purpose:** Cost tracking and monitoring after deployment  
**When to use:** Monitor costs, set up alerts, track spending  
**Key info:**
- Cost monitoring commands
- Expected costs per phase
- Cost optimization tips
- Budget alerts setup

[View COST_MONITORING_GUIDE.md](./COST_MONITORING_GUIDE.md)

---

## 🚨 Common Issues & Quick Fixes

### Issue 1: CDK Recursive Symlink
**Symptom:** `cdk deploy` hangs or fails with "path too long" errors  
**Fix:** See [DEPLOYMENT_TROUBLESHOOTING.md#1-cdk-recursive-symlink-issue](./DEPLOYMENT_TROUBLESHOOTING.md#1-cdk-recursive-symlink-issue)

### Issue 2: CDK Bootstrap Required
**Symptom:** "SSM parameter /cdk-bootstrap/hnb659fds/version not found"  
**Fix:** Run `cdk bootstrap aws://ACCOUNT-ID/us-east-1`

### Issue 3: PowerShell curl Error
**Symptom:** "A parameter cannot be found that matches parameter name 'X'"  
**Fix:** Use `Invoke-WebRequest` instead of `curl` in PowerShell

### Issue 4: Lambda Runtime Error
**Symptom:** API returns 500 error with "NoneType" or "AttributeError"  
**Fix:** Check CloudWatch Logs, verify environment variables, enable Bedrock access

---

## 📊 Deployment Checklist

Use this checklist for deployment:

### Prerequisites
- [ ] Node.js installed (v18+)
- [ ] AWS CLI installed and configured
- [ ] AWS CDK installed globally
- [ ] Python virtual environment activated
- [ ] CDK dependencies installed

### AWS Setup
- [ ] IAM user created with `AdministratorAccess`
- [ ] AWS CLI configured with IAM user credentials
- [ ] Verified with `aws sts get-caller-identity`
- [ ] Region selected (us-east-1 recommended)

### CDK Setup
- [ ] CDK bootstrapped
- [ ] `cdk.out` directory deleted if exists
- [ ] No background CDK processes running

### Deployment
- [ ] `cdk synth` runs successfully
- [ ] `cdk deploy` completes
- [ ] CloudFormation stack shows `CREATE_COMPLETE`
- [ ] API Gateway endpoint accessible

### Post-Deployment
- [ ] Test API endpoints
- [ ] Check CloudWatch Logs
- [ ] Subscribe to SNS topics
- [ ] Enable Bedrock model access
- [ ] Monitor costs after 24 hours

---

## 🔧 Quick Reference Commands

### CDK Commands
```powershell
# Synthesize CloudFormation template
cdk synth

# Deploy stack
cdk deploy --require-approval never

# Destroy stack (WARNING: deletes all resources)
cdk destroy

# Show differences
cdk diff
```

### AWS CLI Commands
```powershell
# Verify identity
aws sts get-caller-identity

# List stacks
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE

# View Lambda logs
aws logs tail /aws/lambda/CostGuardLambda --follow

# Check costs
aws ce get-cost-and-usage \
  --time-period Start=2026-02-27,End=2026-02-28 \
  --granularity DAILY \
  --metrics UnblendedCost \
  --group-by Type=SERVICE
```

### Testing Commands (PowerShell)
```powershell
# Test API endpoint
Invoke-WebRequest -Uri "https://YOUR-API-URL/prod/api/prevention/status" -Method GET | Select-Object -ExpandProperty Content

# Test with POST data
Invoke-WebRequest -Uri "https://YOUR-API-URL/prod/api/fetch" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"start_date": "2026-02-01", "end_date": "2026-02-27", "granularity": "DAILY"}' | Select-Object -ExpandProperty Content
```

---

## 📈 Deployment Timeline

| Phase | Time Estimate | Status |
|-------|---------------|--------|
| Prerequisites | 30 min | ✅ Complete |
| Phase 1 | 2 hours | ✅ Deployed |
| Phase 1.5 | 1 hour | ✅ Deployed |
| Phase 2 | 2 hours | ✅ Deployed |
| Phase 3 | 3 hours | ✅ Deployed |
| Phase 4 | 2 hours | ⏸️ Code Ready |
| Phase 5 | 2 hours | ⏸️ Code Ready |
| Phase 6 | 2 hours | ⏸️ Code Ready |

**Total Time (Phase 1-3):** ~32 minutes (including troubleshooting)  
**Total Time (All Phases):** ~14.5 hours estimated

---

## 💰 Cost Summary

| Phase | Monthly Cost | Status |
|-------|--------------|--------|
| Phase 1 | ~$1.00 | ✅ Deployed |
| Phase 1.5 | ~$0.01 | ✅ Deployed |
| Phase 2 | ~$0.50 | ✅ Deployed |
| Phase 3 | ~$0.00 | ✅ Deployed |
| Phase 4 | ~$0.50 | ⏸️ Not Deployed |
| Phase 5 | ~$0.00 | ⏸️ Not Deployed |
| Phase 6 | ~$0.50 | ⏸️ Not Deployed |

**Current Monthly Cost:** ~$1.51/month  
**Full System Cost:** ~$2.51/month

---

## 🎯 Current Status

**Deployment Date:** February 27, 2026  
**Stack Name:** CostGuardStack  
**Status:** ✅ CREATE_COMPLETE  
**Region:** us-east-1  
**Account:** 456041708434  
**API Endpoint:** `https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/`

**Phases Deployed:** 1, 1.5, 2, 3  
**Phases Pending:** 4, 5, 6

---

## 📞 Need Help?

1. Check [DEPLOYMENT_TROUBLESHOOTING.md](./DEPLOYMENT_TROUBLESHOOTING.md) for common issues
2. Review CloudWatch Logs: `aws logs tail /aws/lambda/CostGuardLambda --follow`
3. Check CloudFormation events in AWS Console
4. Verify IAM permissions are correct
5. Ensure all prerequisites are installed

---

## 📝 Related Documentation

- [README.md](./README.md) - Project overview
- [docs/INDEX.md](./docs/INDEX.md) - Master documentation index
- [docs/PROJECT_STATUS.md](./docs/PROJECT_STATUS.md) - Overall project status
- [TEST_SUMMARY.md](./TEST_SUMMARY.md) - Test coverage and results

---

**Last Updated:** February 27, 2026  
**Version:** 1.0
