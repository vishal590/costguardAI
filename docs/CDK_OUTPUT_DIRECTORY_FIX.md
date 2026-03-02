# CDK Output Directory Configuration Fix

**Issue:** CDK creates `cdk.out` folder in the root directory instead of inside `infrastructure/` folder, causing deployment issues and clutter.

**Date:** March 2, 2026  
**Status:** Fixed

**Tags:** `cdk-output` `working-directory` `infrastructure-folder` `cdk.json` `best-practices` `windows`

**Related Documents:**
- [Phase 5 Deployment Troubleshooting](./PHASE5_DEPLOYMENT_TROUBLESHOOTING.md) - Phase 5 issues
- [Deployment Troubleshooting Guide](./deployment/DEPLOYMENT_TROUBLESHOOTING.md) - All issues
- [Phase 5 Success Report](./PHASE5_DEPLOYMENT_SUCCESS.md) - Latest deployment
- [CDK Quick Reference](./deployment/CDK_QUICK_REFERENCE.md) - Quick solutions

**Keywords for Search:** CDK output directory, cdk.out location, infrastructure folder, working directory, deployment best practices, cleanup script, recursive symlink prevention

---

## Problem Summary

When running CDK commands from the root directory with `--app "python infrastructure/app.py"`, CDK creates the `cdk.out` folder in the current working directory (root) instead of inside the `infrastructure/` folder. This causes:

1. Clutter in the root directory
2. Potential recursive symlink issues if not properly excluded
3. Inconsistent deployment artifacts location

---

## Root Cause

CDK determines the output directory based on:
1. The `--output` CLI flag (if provided)
2. The `output` field in `cdk.json` (relative to where `cdk.json` is located)
3. Default: `cdk.out` in the current working directory

When running `cdk deploy --app "python infrastructure/app.py"` from the root directory, CDK uses the root as the working directory, creating `cdk.out` there.

---

## Solution

### 1. Configure CDK Output Directory

The `infrastructure/cdk.json` file now includes an explicit `output` configuration:

```json
{
  "app": "python app.py",
  "output": "cdk.out",
  "watch": { ... }
}
```

Since `cdk.json` is located in `infrastructure/`, this creates `infrastructure/cdk.out`.

### 2. Run CDK Commands from Infrastructure Directory

Always run CDK commands from the `infrastructure/` directory:

```powershell
# Correct approach
cd infrastructure
cdk deploy --require-approval never

# Or from root with explicit working directory
cd infrastructure ; cdk deploy --require-approval never ; cd ..
```

### 3. Updated Cleanup Script

The `cleanup_cdk_out.ps1` script now checks both root and infrastructure directories:

```powershell
# Searches in both locations
$searchPaths = @(".", "infrastructure")
```

This ensures any `cdk.out*` folders are cleaned up regardless of where they were created.

### 4. Lambda Asset Exclusions

All Lambda functions in `multi_account_stack.py` already exclude the following directories to prevent recursive symlinks:

```python
exclude=[
    "infrastructure/*",
    ".git/*",
    ".hypothesis/*",
    ".kiro/*",          # Prevents spec files from being included
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
```

The `.kiro/*` exclusion is critical to prevent recursive loops with spec files.

---

## Deployment Best Practices

### Option 1: Deploy from Infrastructure Directory (Recommended)

```powershell
# Navigate to infrastructure directory
cd infrastructure

# Bootstrap (first time only)
cdk bootstrap

# Deploy
cdk deploy CostGuardMultiAccountStack --require-approval never

# Output will be in infrastructure/cdk.out
```

### Option 2: Deploy from Root with Explicit Output

```powershell
# From root directory
cdk deploy CostGuardMultiAccountStack \
  --app "python infrastructure/app.py" \
  --output infrastructure/cdk.out \
  --require-approval never
```

### Option 3: Use Deployment Script

The `deploy.ps1` script automatically handles this:

```powershell
# From root directory
.\deploy.ps1
```

The script:
1. Changes to `infrastructure/` directory
2. Runs `cdk deploy`
3. Creates `infrastructure/cdk.out`

---

## Cleanup Procedure

If `cdk.out` folders are created in the wrong location or become corrupted:

### Automated Cleanup

```powershell
# Run the cleanup script
.\cleanup_cdk_out.ps1
```

This script:
- Searches both root and infrastructure directories
- Uses `robocopy` to empty directories (handles recursive symlinks)
- Removes the folders using PowerShell or CMD

### Manual Cleanup

If the script fails:

```powershell
# Close VS Code completely first

# Method 1: Using robocopy
$emptyDir = "$env:TEMP\empty_temp_dir"
New-Item -ItemType Directory -Path $emptyDir -Force
robocopy $emptyDir cdk.out /MIR /R:0 /W:0
Remove-Item -Recurse -Force cdk.out

# Method 2: Using CMD
cmd /c "rmdir /s /q cdk.out"

# Method 3: File Explorer
# Navigate to the folder in File Explorer and delete manually
```

---

## Verification

After deployment, verify the output directory location:

```powershell
# Check if cdk.out exists in infrastructure directory
Test-Path infrastructure/cdk.out
# Should return: True

# Check if cdk.out exists in root directory
Test-Path cdk.out
# Should return: False

# List cdk.out contents
Get-ChildItem infrastructure/cdk.out
```

---

## Troubleshooting

### Issue: `cdk.out` still created in root

**Solution:** Ensure you're running CDK commands from the `infrastructure/` directory:

```powershell
cd infrastructure
cdk deploy
```

### Issue: "Another CLI is currently synthing to cdk.out"

**Solution:** Kill locked processes and delete `cdk.out`:

```powershell
# Kill node processes
Stop-Process -Name "node" -Force -ErrorAction SilentlyContinue

# Run cleanup script
.\cleanup_cdk_out.ps1

# Try deployment again
cd infrastructure
cdk deploy
```

### Issue: Recursive symlink loop in `cdk.out`

**Solution:** This should be prevented by the exclusions in `multi_account_stack.py`. If it still occurs:

1. Verify `.kiro/*` is in the exclusions list
2. Run cleanup script
3. Ensure you're not including the `infrastructure/` directory in Lambda assets

```python
# Correct (in multi_account_stack.py)
code=lambda_.Code.from_asset(
    ".",  # Root directory
    exclude=[
        "infrastructure/*",  # Exclude infrastructure folder
        ".kiro/*",          # Exclude spec files
        # ... other exclusions
    ]
)
```

---

## Summary of Changes

| File | Change | Purpose |
|------|--------|---------|
| `infrastructure/cdk.json` | Added `"output": "cdk.out"` | Explicitly set output directory relative to cdk.json location |
| `cleanup_cdk_out.ps1` | Search both root and infrastructure directories | Clean up cdk.out folders regardless of location |
| `infrastructure/multi_account_stack.py` | Already includes `.kiro/*` exclusion | Prevent recursive symlinks with spec files |

---

## References

- [CDK Output Directory Documentation](https://docs.aws.amazon.com/cdk/v2/guide/cli.html#cli-output)
- [Phase 5 Deployment Troubleshooting](./PHASE5_DEPLOYMENT_TROUBLESHOOTING.md)
- [Deployment Troubleshooting Guide](./deployment/DEPLOYMENT_TROUBLESHOOTING.md)

---

**Last Updated:** March 2, 2026  
**Status:** Resolved
