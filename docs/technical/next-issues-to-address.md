# Next Issues to Address

**Date:** March 2026  
**Status:** 📋 **PENDING REVIEW**

---

## ✅ Recently Fixed Issues

All 3 critical issues from external code review have been fixed:
1. ✅ Phase 3: Savings Estimation - Real pricing API integration
2. ✅ Phase 4: Account ID - STS get_caller_identity
3. ✅ Phase 6 Extension: Fallback Pricing - Documentation improved

---

## 🔍 Remaining Issues Found in Codebase

### 🟡 MEDIUM Priority

#### 1. Phase 6: DynamoDB Storage for Workload Classifications
**File:** `src/services/ai_ml/workload_classifier.py:332`
```python
# TODO: Implement DynamoDB storage
pass
```
**Impact:** Workload classifications are not persisted  
**Fix:** Implement DynamoDB storage for classification results  
**Complexity:** 🟡 MEDIUM

---

#### 2. Phase 6: Pricing API Integration for Idle Detector
**File:** `src/services/ai_ml/idle_detector.py:466`
```python
# TODO: Implement Pricing API integration
# For now, use approximate costs for common GPU instances
```
**Impact:** Idle cost calculations use approximate pricing  
**Fix:** Integrate Pricing API for accurate GPU instance pricing  
**Complexity:** 🟡 MEDIUM

---

#### 3. Phase 3: Resource Manager Placeholder Methods
**File:** `src/services/resource_manager.py:1061, 1066, 1071`
```python
# Placeholder - would query CloudWatch
return {}

# Placeholder - would use pricing data
return 0.0

# Placeholder - would analyze metrics
return datetime.now(UTC).isoformat()
```
**Impact:** Resource metrics and cost calculations not fully implemented  
**Fix:** Implement CloudWatch queries and pricing integration  
**Complexity:** 🟡 MEDIUM

---

### 🟢 LOW Priority

#### 4. Phase 1.5: Cost Estimator Placeholder for Unsupported Services
**File:** `src/services/cost_estimator.py:402`
```python
value=Decimal('1'),  # Placeholder for unsupported services
```
**Impact:** Unsupported services get $1 placeholder value  
**Fix:** Better handling/documentation for unsupported services  
**Complexity:** 🟢 LOW

---

#### 5. Phase 4: Anomaly Detection Placeholder
**File:** `src/services/context_manager.py:84`
```python
# Detect anomalies (placeholder)
anomalies = []
```
**Impact:** Anomaly detection not implemented  
**Fix:** Implement anomaly detection logic  
**Complexity:** 🟡 MEDIUM (but low priority)

---

## 📊 Priority Recommendation

### Immediate Next Steps (if needed):
1. **Phase 6: DynamoDB Storage** - If workload classification persistence is needed
2. **Phase 6: Idle Detector Pricing** - If accurate idle cost tracking is critical
3. **Phase 3: Resource Manager** - If resource metrics are needed for prevention

### Lower Priority:
4. **Cost Estimator Placeholder** - Minor issue, mainly documentation
5. **Anomaly Detection** - Feature enhancement, not critical

---

## 🎯 Decision Needed

**Question:** Which issue should we address next?

**Options:**
- A) Phase 6 DynamoDB storage (workload classification persistence)
- B) Phase 6 Idle detector pricing (accurate cost calculations)
- C) Phase 3 Resource manager placeholders (complete resource metrics)
- D) Review and prioritize based on user requirements
- E) Something else (specify)

---

**Note:** All critical issues from the external review have been fixed. These remaining items are enhancements or incomplete features that may or may not be needed depending on requirements.
