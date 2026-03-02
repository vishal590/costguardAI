# Semantic Search Guide for CostGuard Documentation

**Last Updated:** March 2, 2026  
**Purpose:** Guide for using semantic search features in CostGuard documentation

**Tags:** `semantic-search` `documentation` `search-guide` `ai-optimization` `discoverability`

---

## Overview

All CostGuard deployment documentation now includes semantic search metadata to help both humans and AI (Kiro) quickly find relevant information.

---

## Search Methods

### 1. Search by Error Message

**Best for:** Exact error text from terminal or logs

**How to use:**
1. Copy the error message
2. Search in [Quick Issue Finder](./DEPLOYMENT_TROUBLESHOOTING.md#quick-issue-finder)
3. Or use [Documentation Index](./DOCUMENTATION_INDEX.md#-search-by-error-message)

**Example:**
```
Error: AttributeError: module 'aws_cdk.aws_cloudwatch' has no attribute 'SnsAction'
→ Search: "SnsAction"
→ Found in: Quick Reference, Issue 4
```

---

### 2. Search by Symptom

**Best for:** Describing what's wrong without exact error

**How to use:**
1. Identify the symptom (e.g., "deployment fails", "can't delete folder")
2. Check [Search by Symptom](./DOCUMENTATION_INDEX.md#-search-by-symptom) table
3. Follow link to solution

**Example:**
```
Symptom: "Can't delete cdk.out folder"
→ Found in: CDK Output Directory Fix
→ Solution: Use cleanup_cdk_out.ps1 script
```

---

### 3. Search by Tag

**Best for:** Finding related issues or documentation

**Available tag categories:**

#### Deployment Tags
- `deployment` - General deployment topics
- `cdk` - AWS CDK specific
- `cloudformation` - CloudFormation stacks
- `troubleshooting` - Problem solving
- `quick-reference` - Fast solutions

#### Error Type Tags
- `python-import` - Python import errors
- `recursive-symlink` - Symlink loop issues
- `process-lock` - Process locking issues
- `schema-mismatch` - Database schema issues
- `runtime-error` - Lambda runtime errors

#### Severity Tags
- `critical` - Deployment blockers
- `high` - Major issues
- `medium` - Moderate issues
- `low` - Minor issues
- `best-practice` - Recommendations

#### Phase Tags
- `phase-1` - Cost data collection
- `phase-2` - AI advisor
- `phase-3` - Prevention system
- `phase-4` - Anomaly detection
- `phase-5` - Multi-account

#### Component Tags
- `lambda` - Lambda functions
- `dynamodb` - DynamoDB tables
- `api-gateway` - API Gateway
- `cloudwatch` - CloudWatch monitoring
- `iam` - IAM roles/permissions

**How to use:**
1. Identify relevant tags
2. Search in [Search by Tag](./DOCUMENTATION_INDEX.md#-search-by-tag)
3. Find all related documents

**Example:**
```
Tag: "phase-5" + "critical"
→ Found: Python import error (Issue 4)
→ Related: Phase 5 Success Report, Phase 5 Troubleshooting
```

---

### 4. Search by Phase

**Best for:** Phase-specific issues or documentation

**How to use:**
1. Identify which phase you're working on
2. Check [Search by Phase](./DOCUMENTATION_INDEX.md#-search-by-phase)
3. Review phase-specific documents

**Example:**
```
Phase: Phase 5 (Multi-Account)
→ Documents: Phase 5 Success, Phase 5 Troubleshooting
→ Issues: Python import error (actual blocker)
→ Tags: phase-5, multi-account, aws-organizations
```

---

### 5. Search by Keywords

**Best for:** Full-text search across documentation

**Available in every document header:**
- Error-specific keywords
- Technology keywords
- Solution keywords

**Example:**
```
Keyword: "CloudWatch actions"
→ Found in: Phase 5 Success Report
→ Related: Python import error, SnsAction fix
```

---

## For AI/Kiro: Automated Search

### Context Gathering Strategy

1. **Start with error message** - Exact match in Quick Issue Finder
2. **Check tags** - Find related issues and documents
3. **Follow cross-references** - Understand dependencies
4. **Review phase context** - Get phase-specific information

### Search Priority

```
1. Exact error message match (highest priority)
   ↓
2. Symptom-based search
   ↓
3. Tag-based semantic search
   ↓
4. Cross-reference following
   ↓
5. Keyword full-text search (lowest priority)
```

### Example AI Search Flow

```
User: "CDK deployment fails with SnsAction error"

Step 1: Extract error term → "SnsAction"
Step 2: Search Quick Issue Finder → Found in Quick Reference
Step 3: Check tags → python-import, cloudwatch-actions, phase-5
Step 4: Get related docs → Phase 5 Success, Issue 4
Step 5: Follow cross-references → No dependencies
Step 6: Return solution → Add aws_cloudwatch_actions import
```

---

## Document Structure

Every enhanced document now includes:

### Header Metadata
```markdown
**Tags:** `tag1` `tag2` `tag3`
**Related Documents:** [Doc1](link) [Doc2](link)
**Keywords for Search:** keyword1, keyword2, keyword3
```

### Issue Metadata (in Troubleshooting docs)
```markdown
**Phases Affected:** Phase X
**Severity:** Critical/High/Medium/Low
**Tags:** `tag1` `tag2`
**Related Issues:** [Issue Y](#issue-y)
**Related Docs:** [Doc](link)
```

---

## Quick Reference Table

| Need | Use This | Location |
|------|----------|----------|
| Fast error fix | Quick Reference | [CDK_QUICK_REFERENCE.md](./CDK_QUICK_REFERENCE.md) |
| Comprehensive search | Documentation Index | [DOCUMENTATION_INDEX.md](./DOCUMENTATION_INDEX.md) |
| Detailed issue info | Troubleshooting Guide | [DEPLOYMENT_TROUBLESHOOTING.md](./DEPLOYMENT_TROUBLESHOOTING.md) |
| Phase 5 specific | Phase 5 docs | [PHASE5_DEPLOYMENT_SUCCESS.md](../PHASE5_DEPLOYMENT_SUCCESS.md) |
| Configuration help | CDK Output Fix | [CDK_OUTPUT_DIRECTORY_FIX.md](../CDK_OUTPUT_DIRECTORY_FIX.md) |
| Overview | Deployment README | [README.md](./README.md) |

---

## Benefits

### For Humans
✅ Faster problem resolution  
✅ Better understanding of relationships  
✅ Clear navigation paths  
✅ Multiple search methods

### For AI (Kiro)
✅ Semantic search capability  
✅ Context gathering from tags  
✅ Pattern matching from keywords  
✅ Automated issue resolution

---

## Examples

### Example 1: New Developer
**Goal:** Understand deployment structure

**Search path:**
1. Start: [Deployment README](./README.md)
2. Overview: [Documentation Index](./DOCUMENTATION_INDEX.md)
3. Commands: [Quick Reference](./CDK_QUICK_REFERENCE.md)
4. Bookmark: [Troubleshooting Guide](./DEPLOYMENT_TROUBLESHOOTING.md)

### Example 2: Troubleshooting Error
**Goal:** Fix "SnsAction" error

**Search path:**
1. Copy error message
2. Search: [Quick Issue Finder](./DEPLOYMENT_TROUBLESHOOTING.md#quick-issue-finder)
3. Found: Issue 4 - Python Import Error
4. Solution: Add `aws_cloudwatch_actions` import

### Example 3: Understanding Phase 5
**Goal:** Learn what was deployed

**Search path:**
1. Tag search: `phase-5`
2. Found: [Phase 5 Success Report](../PHASE5_DEPLOYMENT_SUCCESS.md)
3. Related: [Phase 5 Troubleshooting](../PHASE5_DEPLOYMENT_TROUBLESHOOTING.md)
4. Context: 105 resources, 3 Lambda functions, 5 DynamoDB tables

---

## Maintenance

### Adding New Issues
When documenting new issues, include:
- [ ] Tags (deployment, error type, severity, phase, component)
- [ ] Related Issues section
- [ ] Related Docs section
- [ ] Keywords in header
- [ ] Entry in Quick Issue Finder
- [ ] Entry in Documentation Index

### Updating Existing Docs
When updating documentation:
- [ ] Update "Last Updated" date
- [ ] Add new tags if applicable
- [ ] Update cross-references
- [ ] Update Documentation Index
- [ ] Log change in DOCUMENTATION_UPDATE_LOG.md

---

**Maintained by:** Kiro AI Assistant  
**For questions:** Start with [Documentation Index](./DOCUMENTATION_INDEX.md)
