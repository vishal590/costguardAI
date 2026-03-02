# CostGuard Deployment Documentation Index

**Last Updated:** March 2, 2026  
**Purpose:** Comprehensive index of all deployment documentation with semantic search support

**Tags:** `documentation-index` `semantic-search` `cross-reference` `navigation` `deployment` `troubleshooting`

---

## 📖 Document Categories

### Quick Reference & Cheat Sheets
- **[CDK Quick Reference](./CDK_QUICK_REFERENCE.md)** - Fast solutions for common errors
  - Tags: `quick-reference` `errors` `fixes` `cheat-sheet`
  - Use when: You need immediate solution to a known error
  - Search terms: error messages, CDK commands, verification steps

### Deployment Guides
- **[Deployment README](./README.md)** - Central documentation hub
  - Tags: `documentation-hub` `navigation` `overview`
  - Use when: Starting point for all deployment documentation
  - Search terms: deployment overview, documentation structure

- **[Phase 5 Success Report](../PHASE5_DEPLOYMENT_SUCCESS.md)** - Latest deployment details
  - Tags: `phase-5` `success-report` `production-ready` `multi-account`
  - Use when: Understanding what was deployed in Phase 5
  - Search terms: Phase 5 resources, API endpoints, verification steps

### Troubleshooting Guides
- **[Deployment Troubleshooting Guide](./DEPLOYMENT_TROUBLESHOOTING.md)** - Complete issue database
  - Tags: `troubleshooting` `all-issues` `historical` `solutions`
  - Use when: Encountering deployment issues across any phase
  - Search terms: error messages, symptoms, issue numbers

- **[Phase 5 Troubleshooting](../PHASE5_DEPLOYMENT_TROUBLESHOOTING.md)** - Phase 5 specific timeline
  - Tags: `phase-5` `troubleshooting` `timeline` `root-cause`
  - Use when: Understanding Phase 5 deployment journey
  - Search terms: Phase 5 issues, Python import error, deployment timeline

### Configuration & Best Practices
- **[CDK Output Directory Fix](../CDK_OUTPUT_DIRECTORY_FIX.md)** - Output directory configuration
  - Tags: `cdk-output` `best-practices` `configuration` `working-directory`
  - Use when: Setting up correct CDK output location
  - Search terms: cdk.out location, working directory, cleanup

---

## 🔍 Search by Error Message

| Error Message | Primary Document | Section | Tags |
|---------------|------------------|---------|------|
| `AttributeError: ... 'SnsAction'` | [Quick Reference](./CDK_QUICK_REFERENCE.md) | Python Import Error | `python-import` `cloudwatch-actions` `phase-5` |
| `path too long` / `recursive symlink` | [Troubleshooting](./DEPLOYMENT_TROUBLESHOOTING.md) | Issue 1 | `recursive-symlink` `lambda-assets` `windows` |
| `Another CLI is currently synthing` | [Quick Reference](./CDK_QUICK_REFERENCE.md) | Process Lock | `process-lock` `node-process` `cdk-lock` |
| `SSM parameter not found` | [Troubleshooting](./DEPLOYMENT_TROUBLESHOOTING.md) | Issue 2 | `cdk-bootstrap` `first-time-setup` |
| `'NoneType' object has no attribute` | [Troubleshooting](./DEPLOYMENT_TROUBLESHOOTING.md) | Issue 2 (SafetyGuard) | `safetyguard` `python-error` `lambda-crash` |
| `key element does not match schema` | [Troubleshooting](./DEPLOYMENT_TROUBLESHOOTING.md) | Issue 3 | `dynamodb` `schema-mismatch` `validation` |
| `cdk.out in wrong location` | [CDK Output Fix](../CDK_OUTPUT_DIRECTORY_FIX.md) | Solution | `cdk-output` `working-directory` |

---

## 🎯 Search by Symptom

| Symptom | Primary Document | Solution | Tags |
|---------|------------------|----------|------|
| CDK deployment fails | [Quick Reference](./CDK_QUICK_REFERENCE.md) | Pre-deployment checklist | `deployment` `checklist` |
| Can't delete `cdk.out` | [CDK Output Fix](../CDK_OUTPUT_DIRECTORY_FIX.md) | Cleanup procedure | `cleanup` `recursive-symlink` |
| Lambda crashes on startup | [Troubleshooting](./DEPLOYMENT_TROUBLESHOOTING.md) | Issue 2 (SafetyGuard) | `lambda` `runtime-error` |
| API returns 500 error | [Troubleshooting](./DEPLOYMENT_TROUBLESHOOTING.md) | Issue 4 (Lambda Runtime) | `api-gateway` `500-error` |
| Cost data won't save | [Troubleshooting](./DEPLOYMENT_TROUBLESHOOTING.md) | Issue 3 (DynamoDB) | `dynamodb` `data-storage` |
| Wrong output directory | [CDK Output Fix](../CDK_OUTPUT_DIRECTORY_FIX.md) | Best practices | `working-directory` `cdk-output` |

---

## 📊 Search by Phase

### Phase 1-4 (Single Account)
- **Issues:** Recursive symlink (prevented), SafetyGuard config, DynamoDB schema
- **Documents:** [Troubleshooting Guide](./DEPLOYMENT_TROUBLESHOOTING.md) (Issues 1-3)
- **Tags:** `phase-1` `phase-2` `phase-3` `phase-4` `single-account`

### Phase 5 (Multi-Account)
- **Issues:** Python import error (actual blocker)
- **Documents:** 
  - [Phase 5 Success](../PHASE5_DEPLOYMENT_SUCCESS.md) - What was deployed
  - [Phase 5 Troubleshooting](../PHASE5_DEPLOYMENT_TROUBLESHOOTING.md) - Timeline
  - [Troubleshooting Guide](./DEPLOYMENT_TROUBLESHOOTING.md) (Issue 4, 8)
- **Tags:** `phase-5` `multi-account` `aws-organizations`

---

## 🏷️ Search by Tag

### Deployment Tags
- `deployment` - General deployment topics
- `cdk` - AWS CDK specific
- `cloudformation` - CloudFormation stacks
- `troubleshooting` - Problem solving
- `quick-reference` - Fast solutions

### Error Type Tags
- `python-import` - Python import errors
- `recursive-symlink` - Symlink loop issues
- `process-lock` - Process locking issues
- `schema-mismatch` - Database schema issues
- `runtime-error` - Lambda runtime errors

### Severity Tags
- `critical` - Deployment blockers
- `high` - Major issues
- `medium` - Moderate issues
- `low` - Minor issues
- `best-practice` - Recommendations

### Phase Tags
- `phase-1` - Cost data collection
- `phase-2` - AI advisor
- `phase-3` - Prevention system
- `phase-4` - Anomaly detection
- `phase-5` - Multi-account

### Component Tags
- `lambda` - Lambda functions
- `dynamodb` - DynamoDB tables
- `api-gateway` - API Gateway
- `cloudwatch` - CloudWatch monitoring
- `iam` - IAM roles/permissions

---

## 🔗 Cross-Reference Map

### Issue Dependencies
```
Issue 1 (Recursive Symlink)
  ├─→ Related to: Issue 8 (Deployment Directory)
  └─→ Prevented by: Lambda asset exclusions

Issue 2 (SafetyGuard Config)
  └─→ Related to: Issue 4 (Lambda Runtime Errors)

Issue 3 (DynamoDB Schema)
  └─→ Related to: Issue 4 (Lambda Runtime Errors)

Issue 4 (Python Import - Phase 5)
  ├─→ Actual blocker for Phase 5
  └─→ No dependencies

Issue 8 (Deployment Directory)
  └─→ Related to: Issue 1 (Recursive Symlink)
```

### Document Flow
```
Start Here
  └─→ Deployment README
      ├─→ Quick Reference (for fast solutions)
      ├─→ Troubleshooting Guide (for detailed issues)
      ├─→ Phase 5 Success (for latest deployment)
      └─→ CDK Output Fix (for configuration)
```

---

## 💡 AI/Kiro Search Optimization

### For Error Resolution
1. **Search by exact error message** in Quick Issue Finder sections
2. **Search by tags** for related issues
3. **Follow cross-references** for dependent issues
4. **Check phase-specific** documents for context

### For Understanding Deployment
1. **Start with README** for overview
2. **Read Success Report** for what's deployed
3. **Review Troubleshooting** for lessons learned
4. **Check Best Practices** for configuration

### For Preventative Measures
1. **Review Pre-deployment Checklist** in Quick Reference
2. **Study Preventative Measures** in Phase 5 Success
3. **Understand Root Causes** in Troubleshooting Guide
4. **Follow Best Practices** in CDK Output Fix

---

## 📝 Document Metadata Summary

| Document | Lines | Issues Covered | Last Updated | Status |
|----------|-------|----------------|--------------|--------|
| [Troubleshooting Guide](./DEPLOYMENT_TROUBLESHOOTING.md) | ~800 | 11 issues | 2026-03-02 | Complete |
| [Quick Reference](./CDK_QUICK_REFERENCE.md) | ~200 | 5 errors | 2026-03-02 | Complete |
| [Phase 5 Success](../PHASE5_DEPLOYMENT_SUCCESS.md) | ~400 | 3 issues | 2026-03-02 | Complete |
| [Phase 5 Troubleshooting](../PHASE5_DEPLOYMENT_TROUBLESHOOTING.md) | ~300 | Timeline | 2026-03-02 | Resolved |
| [CDK Output Fix](../CDK_OUTPUT_DIRECTORY_FIX.md) | ~250 | 1 config | 2026-03-02 | Complete |
| [Deployment README](./README.md) | ~200 | Overview | 2026-03-02 | Complete |

---

## 🎓 Learning Path

### For New Developers
1. Read [Deployment README](./README.md) - Understand structure
2. Review [Quick Reference](./CDK_QUICK_REFERENCE.md) - Learn common commands
3. Study [Phase 5 Success](../PHASE5_DEPLOYMENT_SUCCESS.md) - See what's deployed
4. Bookmark [Troubleshooting Guide](./DEPLOYMENT_TROUBLESHOOTING.md) - For when issues arise

### For Troubleshooting
1. Check [Quick Reference](./CDK_QUICK_REFERENCE.md) - Fast solutions
2. Search [Troubleshooting Guide](./DEPLOYMENT_TROUBLESHOOTING.md) - Detailed fixes
3. Review [Phase 5 Troubleshooting](../PHASE5_DEPLOYMENT_TROUBLESHOOTING.md) - Recent issues
4. Consult [CDK Output Fix](../CDK_OUTPUT_DIRECTORY_FIX.md) - Configuration issues

### For AI/Kiro
1. **Semantic search** using tags and keywords
2. **Cross-reference** using Related Documents sections
3. **Context gathering** from multiple related documents
4. **Pattern matching** using error messages and symptoms

---

## 🔄 Update History

| Date | Document | Change | Reason |
|------|----------|--------|--------|
| 2026-03-02 | All docs | Added semantic search metadata | Improve discoverability |
| 2026-03-02 | Troubleshooting | Added tags and cross-references | Better navigation |
| 2026-03-02 | Quick Reference | Added phase/severity metadata | Context clarity |
| 2026-03-02 | Phase 5 docs | Marked as resolved | Deployment complete |

---

**Maintained by:** Kiro AI Assistant  
**For questions:** Search this index or start with [Deployment README](./README.md)
