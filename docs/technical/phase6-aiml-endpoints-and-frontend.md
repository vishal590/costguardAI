# Phase 6 AI/ML: Backend Endpoints vs Frontend Integration

**Purpose:** Checklist of all Phase 6 (AI/ML workload) backend endpoints and whether each is integrated in the frontend.

**Backend:** `src/ai_ml_handler.py` (AIML stack Lambda).  
**Frontend:** `client-aws-ideas` — `src/store/apiSlice.js` (API hooks), `src/pages/AIMLPage.jsx` (Phase 6 AI/ML page).

**Phase 6 has 18 GET and 2 POST endpoints.** The 2 POST endpoints are:
- **POST /api/ai-ml/gpu-prevention** — run prevention cycle for idle GPUs (body: start_date, end_date, threshold, dry_run).
- **POST /api/ai-ml/workload-classification** — manual override for workload type (body: instance_id, workload_type, reason).

Both are integrated in existing tabs: GPU prevention in the Idle GPUs tab; Set workload type in the GPU costs tab. (No longer separate tabs; **“GPU prevention (POST)”** and tab **“Set workload type (POST)”**.

---

## Backend endpoints (Phase 6 only; not Extension)

| # | Method | Endpoint | Backend handler | API hook (apiSlice) | UI (AIMLPage) |
|---|--------|----------|------------------|---------------------|---------------|
| 1 | GET | `/api/ai-ml/gpu-costs` | `handle_gpu_costs` | `getGPUCosts` | ✅ GPU costs tab |
| 2 | GET | `/api/ai-ml/gpu-utilization` | `handle_gpu_utilization` | — | — (backend returns 501 Not Implemented) |
| 3 | GET | `/api/ai-ml/idle-gpus` | `handle_idle_gpus` | `getIdleGPUs` | ✅ Idle GPUs tab |
| 4 | POST | `/api/ai-ml/gpu-prevention` | `handle_gpu_prevention` | `runGPUPrevention` | ✅ Idle GPUs tab (button) |
| 5 | GET | `/api/ai-ml/gpu-cost-savings` | `handle_gpu_cost_savings` | `getGPUCostSavings` | ❌ No tab |
| 6 | GET | `/api/ai-ml/workload-classification` | `handle_get_workload_classification` | `getWorkloadClassification` | ❌ No tab |
| 7 | POST | `/api/ai-ml/workload-classification` | `handle_post_workload_classification` | `setWorkloadClassification` | ✅ GPU costs tab (form) |
| 8 | GET | `/api/ai-ml/cost-per-inference` | `handle_cost_per_inference` | `getCostPerInference` | ✅ Cost per inference tab |
| 9 | GET | `/api/ai-ml/inference-trends` | `handle_inference_trends` | `getInferenceTrends` | ❌ No tab |
| 10 | GET | `/api/ai-ml/cost-per-training` | `handle_cost_per_training` | `getCostPerTraining` | ❌ No tab |
| 11 | GET | `/api/ai-ml/training-comparison` | `handle_training_comparison` | `getTrainingComparison` | ❌ No tab |
| 12 | GET | `/api/ai-ml/spot-recommendations` | `handle_spot_recommendations` | `getSpotRecommendations` | ✅ Spot recommendations tab |
| 13 | GET | `/api/ai-ml/spot-savings` | `handle_spot_savings` | `getSpotSavings` | ❌ No tab |
| 14 | GET | `/api/ai-ml/sagemaker-costs` | `handle_sagemaker_costs` | `getSageMakerCosts` | ✅ SageMaker costs tab |
| 15 | GET | `/api/ai-ml/sagemaker-idle-endpoints` | `handle_sagemaker_idle_endpoints` | `getSageMakerIdleEndpoints` | ❌ No tab |
| 16 | GET | `/api/ai-ml/bedrock-costs` | `handle_bedrock_costs` | `getBedrockCosts` | ✅ Bedrock costs tab |
| 17 | GET | `/api/ai-ml/bedrock-cost-per-invocation` | `handle_bedrock_cost_per_invocation` | `getBedrockCostPerInvocation` | ❌ No tab |
| 18 | GET | `/api/ai-ml/multi-account/gpu-costs` | `handle_multi_account_gpu_costs` | `getMultiAccountGPUCosts` | ❌ No tab |
| 19 | GET | `/api/ai-ml/multi-account/gpu-utilization` | `handle_multi_account_gpu_utilization` | `getMultiAccountGPUUtilization` | ❌ No tab |
| 20 | GET | `/api/ai-ml/multi-account/top-gpu-accounts` | `handle_multi_account_top_gpu_accounts` | `getMultiAccountTopGPUAccounts` | ❌ No tab |

---

## Summary

- **Backend:** 20 endpoints (19 implemented; 1 returns 501: `gpu-utilization`).
- **API hooks (apiSlice):** All 20 endpoints have a corresponding hook (gpu-utilization returns 501; hook can be added for consistency if desired).
- **UI (AIMLPage):** 6 tabs: GPU costs (table + set workload form), Idle GPUs (table + run prevention button), Spot recommendations, Cost per inference, SageMaker costs, Bedrock costs. The remaining GET endpoints have apiSlice hooks but no tab yet (API-only from frontend).

---

## Optional next steps (frontend)

- **Extra tabs:** GPU cost savings, Spot savings, Inference trends, Cost per training, Training comparison, SageMaker idle endpoints, Bedrock cost per invocation, Multi-account GPU / top accounts (all hooks already in apiSlice).
- **multi-account/gpu-utilization:** Hook `getMultiAccountGPUUtilization` is in apiSlice; add a tab if multi-account GPU UI is needed.
