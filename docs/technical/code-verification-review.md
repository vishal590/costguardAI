# Code Verification Issues - Detailed Review & Fix Plan

> **Historical report.** This records an earlier implementation, deployment or test run. Its counts, pending tasks, timing and savings are not current verification. Use [current project status](../PROJECT_STATUS.md) and [current source limitations](documentation-code-sync.md) for the checked-in backend (reviewed October 3, 2026).

**Date:** March 2026  
**Status:** 🔍 **REVIEW COMPLETE**  
**Reviewer:** Internal Review

---

## Issue #1: Phase 3 - Placeholder Savings Estimation

### Current Code
**File:** `src/services/action_executor.py:255-259`
```python
def _estimate_savings(self, resource) -> float:
    """Estimate monthly savings from stopping resource."""
    # Placeholder - would use actual pricing data
    # Assume $0.10/hour as default
    return 0.10 * 24 * 30  # $72/month
```

### Analysis
- **Severity:** 🟡 MEDIUM
- **Impact:** Savings estimates shown to users are inaccurate
- **Context:**
  - Resource object has: `service`, `region`, `resource_id`, `resource_type`
  - `PricingManager` is available in codebase and used elsewhere
  - Pricing API supports: EC2, Lambda, RDS, DynamoDB, S3
  - Different services need different pricing logic:
    - **EC2:** Instance type pricing (need to get instance type from resource_id or EC2 API)
    - **RDS:** DB instance class pricing
    - **Lambda:** Per-request and per-GB-second pricing (complex)
    - **DynamoDB:** On-demand vs provisioned pricing
    - **EBS:** Volume pricing by type and size
    - **NAT Gateway:** Fixed hourly pricing

### Proposed Fix
1. **Add PricingManager to ActionExecutor:**
   - Initialize `PricingManager` in `__init__` or pass as parameter
   - Use existing `PricingManager.get_pricing_data()` method

2. **Service-Specific Pricing Logic:**
   - **EC2:** Get instance type from EC2 API, then get pricing
   - **RDS:** Get DB instance class from RDS API, then get pricing
   - **Lambda:** Use average pricing or get from CloudWatch metrics
   - **DynamoDB:** Get table billing mode, calculate on-demand savings
   - **EBS:** Get volume type and size, calculate storage cost
   - **NAT Gateway:** Fixed $0.045/hour pricing

3. **Fallback Strategy:**
   - If pricing API fails, use service-specific defaults
   - Log warning when using fallback
   - Document fallback behavior

### Complexity: 🟡 MEDIUM
- Requires service-specific logic
- May need additional AWS API calls (EC2/RDS describe)
- Fallback handling needed

---

## Issue #2: Phase 4 - Hardcoded Account ID

### Current Code
**File:** `src/services/context_manager.py:278`
```python
response = self.budgets_client.describe_budgets(
    AccountId='123456789012',  # Placeholder
    MaxResults=1
)
```

### Analysis
- **Severity:** 🔴 HIGH
- **Impact:** Budget status retrieval will fail for real accounts
- **Context:**
  - `ContextManager` doesn't have STS client
  - Other code uses `sts.get_caller_identity()['Account']` (see `budget_monitor.py:150-154`)
  - Budgets API requires account ID
  - This is a simple fix

### Proposed Fix
1. **Add STS Client:**
   - Add `sts_client` parameter to `__init__` (optional, default to boto3.client('sts'))
   - Or add method `_get_account_id()` that uses STS

2. **Update `_get_budget_status`:**
   ```python
   account_id = self._get_account_id()
   response = self.budgets_client.describe_budgets(
       AccountId=account_id,
       MaxResults=1
   )
   ```

3. **Error Handling:**
   - If STS fails, return None (budget status unavailable)
   - Log error for debugging

### Complexity: 🟢 LOW
- Simple STS call
- Already used elsewhere in codebase
- Minimal risk

---

## Issue #3: Phase 6 Extension - Fallback Pricing Documentation

### Current Code
**File:** `src/autonomous/spot_manager.py:460, 485`
```python
except Exception as e:
    print(f"ERROR: Failed to track spot cost: {e}")
    # Fallback to simplified pricing
    spot_price_per_hour = Decimal("0.294")
    return spot_price_per_hour * Decimal(str(duration_hours))
```

### Analysis
- **Severity:** 🟡 MEDIUM (Documentation issue, not code bug)
- **Impact:** Documentation claims "real pricing" but fallback exists
- **Context:**
  - Code **does** try to use real pricing first (lines 442-456)
  - Fallback is intentional and appropriate (exception handling)
  - Fallback values are reasonable (g4dn.xlarge pricing)
  - Issue is that documentation doesn't mention fallback behavior

### Proposed Fix
1. **Update Function Docstrings:**
   - Document that fallback pricing is used when API calls fail
   - Specify which instance type the fallback pricing represents
   - Note that fallback is a last resort

2. **Add Logging:**
   - Change `print()` to proper logging
   - Log when fallback pricing is used (WARNING level)

3. **Update Documentation:**
   - Phase 6 Extension docs should mention fallback behavior
   - Clarify that "real pricing" means "attempts real pricing, falls back if needed"

### Complexity: 🟢 LOW
- Documentation updates only
- Minor code improvements (logging)

---

## Summary & Recommendations

### Priority Order
1. **🔴 HIGH:** Issue #2 (Account ID) - Quick fix, high impact
2. **🟡 MEDIUM:** Issue #1 (Savings Estimation) - More complex, but important
3. **🟡 MEDIUM:** Issue #3 (Fallback Documentation) - Documentation only

### Implementation Strategy
1. **Quick Win:** Fix Issue #2 first (15 minutes)
2. **Medium Effort:** Fix Issue #1 (1-2 hours, service-specific logic)
3. **Documentation:** Update Issue #3 (30 minutes)

### Testing Requirements
- **Issue #1:** Test each service type (EC2, RDS, Lambda, etc.)
- **Issue #2:** Test with real account ID, test STS failure case
- **Issue #3:** Verify documentation accuracy

---

## Next Steps

1. ✅ Review complete
2. ⏳ Await approval to proceed with fixes
3. ⏳ Implement fixes in priority order
4. ⏳ Update documentation
5. ⏳ Run tests
6. ⏳ Commit and push

---

**Note:** All fixes are straightforward and low-risk. Issue #1 requires the most work but is well-scoped.
