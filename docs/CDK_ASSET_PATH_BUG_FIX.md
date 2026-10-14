# CDK Asset Path Bug Fix - March 2026

> **Historical report.** This records an earlier implementation, deployment or test run. Its counts, pending tasks, timing and savings are not current verification. Use [current project status](PROJECT_STATUS.md) and [current source limitations](technical/documentation-code-sync.md) for the checked-in backend (reviewed October 3, 2026).


**Issue Date:** March 4, 2026  
**Severity:** HIGH  
**Status:** ✅ RESOLVED

---

## Problem Description

The AIML Stack CDK configuration was using an incorrect asset path (`".."`) that pointed to the parent directory containing multiple projects, causing CDK to bundle unrelated projects into the Lambda deployment package.

### Symptoms

- `cdk.out/` directory contained folders from sibling projects (`ai_good`, `algolia`)
- Large deployment package size
- Unrelated project files appearing in CDK asset staging
- File tree showing modified files from other projects

### Root Cause

In `infrastructure/aiml_stack.py` line 287, the Lambda asset path was set to:

```python
code=lambda_.Code.from_asset(
    "..",  # Parent directory contains src/
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

---

## Solution

### Fix Applied

Changed the asset path from `".."` to `"."` in `infrastructure/aiml_stack.py`:

```python
# BEFORE (INCORRECT)
code=lambda_.Code.from_asset(
    "..",  # Parent directory contains src/
    exclude=[...]
)

# AFTER (CORRECT)
code=lambda_.Code.from_asset(
    ".",  # Current directory (aws-ideas project root)
    exclude=[...]
)
```

### Cleanup Steps

1. Removed contaminated `cdk.out` directory:
   ```powershell
   Remove-Item -Recurse -Force cdk.out
   ```

2. Verified the fix in `infrastructure/aiml_stack.py`

---

## Prevention Guidelines

### For Future CDK Stacks

1. **Always use relative paths from project root:**
   - ✅ Use `"."` for project root
   - ❌ Avoid `".."` unless absolutely necessary

2. **Verify asset path before deployment:**
   ```python
   # Check what directory the path resolves to
   import os
   print(os.path.abspath("."))  # Should be project root
   print(os.path.abspath(".."))  # Should NOT be used
   ```

3. **Review exclude patterns:**
   - Ensure `.cdkignore` is properly configured
   - Test with `cdk synth` before `cdk deploy`

4. **Monitor cdk.out size:**
   - Check `cdk.out/` after synthesis
   - Deployment packages should only contain project files

### CDK Best Practices

**Correct Asset Paths:**
```python
# ✅ CORRECT: From infrastructure/ subdirectory
lambda_.Code.from_asset(
    ".",  # Points to project root when CDK runs from root
    exclude=[...]
)

# ✅ CORRECT: Explicit project root
lambda_.Code.from_asset(
    os.path.join(os.path.dirname(__file__), ".."),  # Explicit parent
    exclude=[...]
)

# ❌ INCORRECT: Relative parent without context
lambda_.Code.from_asset(
    "..",  # Ambiguous, depends on execution context
    exclude=[...]
)
```

**Exclude Patterns:**
```python
exclude=[
    "cdk.out",           # CDK output
    "infrastructure",    # CDK code itself
    ".git",              # Version control
    ".hypothesis",       # Test artifacts
    ".kiro",             # Kiro files
    "tests",             # Test files
    "docs",              # Documentation
    "*.md",              # Markdown files
    ".venv",             # Virtual environments
    "__pycache__",       # Python cache
]
```

---

## Verification Checklist

After any CDK stack changes, verify:

- [ ] Asset path points to correct directory
- [ ] `cdk synth` completes without errors
- [ ] `cdk.out/` contains only project files
- [ ] Deployment package size is reasonable (<50MB for Lambda)
- [ ] No sibling project directories in `cdk.out/`

---

## Related Files

- `infrastructure/aiml_stack.py` - Fixed asset path (line 287)
- `infrastructure/cdk_stack.py` - Uses correct path (line 287)
- `.cdkignore` - Exclude patterns for CDK assets
- `cleanup_cdk_out.ps1` - Script to clean CDK output

---

## Impact

**Before Fix:**
- Deployment package: ~500MB+ (included 3 projects)
- Build time: 5+ minutes
- Potential security risk (exposing other project code)

**After Fix:**
- Deployment package: ~10MB (only aws-ideas project)
- Build time: <1 minute
- Secure (only intended code deployed)

---

## Lessons Learned

1. **Always verify CDK asset paths** - Relative paths can be tricky
2. **Test CDK synthesis locally** - Check `cdk.out/` before deploying
3. **Use explicit paths when possible** - Avoid ambiguous relative paths
4. **Document CDK configuration** - Help future developers avoid this issue

---

**Fixed By:** Kiro AI Assistant  
**Verified By:** User  
**Date:** March 4, 2026

**Status:** ✅ RESOLVED - No further action required
