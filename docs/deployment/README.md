# CostGuard Deployment Documentation

**Last Updated:** March 2, 2026

**Tags:** `deployment` `documentation` `cdk` `cloudformation` `troubleshooting` `quick-reference` `phase-1` `phase-2` `phase-3` `phase-4` `phase-5`

**Purpose:** Central hub for all CostGuard deployment documentation, troubleshooting guides, and quick references.

**Keywords for Search:** deployment documentation, CDK deployment, CloudFormation stacks, troubleshooting guide, quick reference, deployment checklist, AWS infrastructure, multi-account deployment

This directory contains comprehensive deployment documentation for CostGuard AWS infrastructure.

---

## 📚 Documentation Index

### 🎉 What's New
- **[What's New](./WHATS_NEW.md)** - Latest documentation improvements ✨
  - Semantic search support
  - Cross-reference network
  - AI optimization
  - Quick start guide

### Quick Start
- **[CDK Quick Reference](./CDK_QUICK_REFERENCE.md)** - Fast solutions for common issues ⚡
  - Error messages with instant fixes
  - Pre-deployment checklist
  - Useful commands

- **[Documentation Index](./DOCUMENTATION_INDEX.md)** - Comprehensive search & navigation 🔍
  - Search by error message, symptom, phase, or tag
  - Cross-reference map between issues
  - AI/Kiro search optimization guide
  - Learning paths for developers

- **[Semantic Search Guide](./SEMANTIC_SEARCH_GUIDE.md)** - How to use search features 📖
  - 5 search methods explained
  - Tag categories and usage
  - AI/Kiro automated search strategy
  - Real-world examples

- **[Enhancements Summary](./ENHANCEMENTS_SUMMARY.md)** - What's new in documentation 🎉
  - All enhancements listed
  - How to use new features
  - Benefits and impact metrics
  - Quick start guide

- **[Documentation Structure](./DOCUMENTATION_STRUCTURE.md)** - Visual guide to docs 📊
  - File structure and navigation map
  - Use case navigation paths
  - Search strategy by user type
  - Learning paths and pro tips

### Deployment Guides
- **[Phase 5 Deployment Success](../PHASE5_DEPLOYMENT_SUCCESS.md)** - Latest deployment report ✅
  - What was deployed
  - API endpoints
  - Verification steps
  - Next steps

### Troubleshooting
- **[Deployment Troubleshooting Guide](./DEPLOYMENT_TROUBLESHOOTING.md)** - Complete issue database 🔧
  - All historical issues and solutions
  - Searchable by error message
  - Step-by-step fixes
  
- **[Phase 5 Deployment Troubleshooting](../PHASE5_DEPLOYMENT_TROUBLESHOOTING.md)** - Phase 5 specific issues
  - Timeline of deployment attempts
  - Root cause analysis
  - Final solution

- **[CDK Output Directory Fix](../CDK_OUTPUT_DIRECTORY_FIX.md)** - Output directory configuration
  - Why `cdk.out` location matters
  - How to fix it
  - Prevention strategies

---

## 🚀 Quick Deployment

### Prerequisites
```powershell
# 1. Activate virtual environment
.\venv\Scripts\Activate.ps1

# 2. Navigate to infrastructure directory
cd infrastructure

# 3. Ensure CDK is bootstrapped (first time only)
cdk bootstrap aws://ACCOUNT-ID/us-east-1
```

### Deploy Phase 1-4 (Single Account)
```powershell
cd infrastructure
cdk deploy CostGuardStack --require-approval never
```

### Deploy Phase 5 (Multi-Account)
```powershell
cd infrastructure
cdk deploy CostGuardMultiAccountStack --require-approval never
```

### Deploy All Stacks
```powershell
cd infrastructure
cdk deploy --all --require-approval never
```

---

## 🔍 Find Solutions Fast

### By Error Message
Search in [CDK Quick Reference](./CDK_QUICK_REFERENCE.md) or [Deployment Troubleshooting](./DEPLOYMENT_TROUBLESHOOTING.md):

| Error Message | Document | Section |
|---------------|----------|---------|
| `AttributeError: ... 'SnsAction'` | Quick Reference | Python Import Error |
| `path too long` / `recursive symlink` | Troubleshooting | Issue 1 |
| `Another CLI is currently synthing` | Quick Reference | Process Lock |
| `SSM parameter not found` | Troubleshooting | Issue 2 |
| `'NoneType' object has no attribute` | Troubleshooting | Issue 2 |
| `key element does not match schema` | Troubleshooting | Issue 3 |

### By Symptom
| Symptom | Solution |
|---------|----------|
| CDK deployment fails | Check [Quick Reference](./CDK_QUICK_REFERENCE.md) |
| Can't delete `cdk.out` | Run `.\cleanup_cdk_out.ps1` |
| Lambda crashes on startup | See [Troubleshooting Issue 2](./DEPLOYMENT_TROUBLESHOOTING.md#issue-2-safetyguard-config-initialization-error) |
| API returns 500 error | See [Troubleshooting Issue 4](./DEPLOYMENT_TROUBLESHOOTING.md#4-lambda-runtime-errors) |
| Wrong output directory | See [CDK Output Directory Fix](../CDK_OUTPUT_DIRECTORY_FIX.md) |

---

## 📊 Current Deployment Status

### CloudFormation Stacks
| Stack Name | Status | Resources | Phase |
|------------|--------|-----------|-------|
| CostGuardStack | UPDATE_COMPLETE | ~50 | 1-4 |
| CostGuardMultiAccountStack | CREATE_COMPLETE | 105 | 5 |
| CDKToolkit | CREATE_COMPLETE | ~10 | Bootstrap |

### API Endpoints
- **Phase 1-4 API:** `https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/`
- **Phase 5 API:** `https://7s4ff2lzc6.execute-api.us-east-1.amazonaws.com/prod/`

### Last Deployment
- **Date:** March 2, 2026 10:08 AM
- **Duration:** 158.34 seconds
- **Status:** ✅ SUCCESS

---

## 🛠️ Common Tasks

### Update Existing Stack
```powershell
cd infrastructure
cdk deploy CostGuardStack --require-approval never
```

### View Stack Differences
```powershell
cd infrastructure
cdk diff CostGuardStack
```

### Delete Stack (Careful!)
```powershell
cd infrastructure
cdk destroy CostGuardMultiAccountStack
```

### Clean Up Output Directory
```powershell
.\cleanup_cdk_out.ps1
```

### View CloudWatch Logs
```powershell
# Phase 1-4 Lambda
aws logs tail /aws/lambda/CostGuardLambda --follow

# Phase 5 Cost Collector
aws logs tail /aws/lambda/CostGuard-MultiAccountCostCollector --follow

# Phase 5 API Handler
aws logs tail /aws/lambda/CostGuard-MultiAccountAPIHandler --follow
```

---

## 📖 Additional Resources

### AWS Documentation
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [AWS CloudFormation Documentation](https://docs.aws.amazon.com/cloudformation/)
- [AWS Organizations Documentation](https://docs.aws.amazon.com/organizations/)
- [AWS Cost Explorer API](https://docs.aws.amazon.com/cost-management/latest/APIReference/)

### Project Documentation
- [Project Status](../PROJECT_STATUS.md)
- [Cost Monitoring Guide](../user-guide/COST_MONITORING_GUIDE.md)
- [Innovation Strategy](../INNOVATION-STRATEGY.md)

---

## 💬 Getting Help

1. **Check Documentation Index first:** [DOCUMENTATION_INDEX.md](./DOCUMENTATION_INDEX.md) - Comprehensive search
2. **Check Quick Reference:** [CDK_QUICK_REFERENCE.md](./CDK_QUICK_REFERENCE.md) - Fast solutions
3. **Search error message:** Use Ctrl+F in [DEPLOYMENT_TROUBLESHOOTING.md](./DEPLOYMENT_TROUBLESHOOTING.md)
4. **Check CloudWatch Logs:** Look for detailed error messages
5. **Review recent changes:** Check git history for what changed

**Pro Tip:** Use tags and keywords in the Documentation Index for semantic search!

---

## 🎯 Best Practices

1. ✅ Always run CDK from `infrastructure/` directory
2. ✅ Use `cleanup_cdk_out.ps1` if output directory gets corrupted
3. ✅ Check CloudWatch Logs immediately after deployment
4. ✅ Test API endpoints right after deployment
5. ✅ Subscribe to SNS topics for alarm notifications
6. ✅ Monitor costs in AWS Cost Explorer after 24 hours
7. ✅ Keep documentation updated with new issues and solutions

---

**Need immediate help?** Start with [CDK Quick Reference](./CDK_QUICK_REFERENCE.md) for fast solutions! ⚡
