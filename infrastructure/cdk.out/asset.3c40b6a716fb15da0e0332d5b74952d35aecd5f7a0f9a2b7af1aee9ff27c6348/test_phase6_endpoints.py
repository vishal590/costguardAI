"""
Phase 6 AI/ML Endpoint Testing Script

Tests all Phase 6 endpoints against the deployed CostGuardAIMLStack.
API Endpoint: https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/
"""

import requests
import json
from datetime import datetime, timedelta

# API Configuration
BASE_URL = "https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml"
HEADERS = {"Content-Type": "application/json"}

# Test results tracking
results = {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "errors": []
}

def test_endpoint(method, path, data=None, expected_status=200, description=""):
    """Test a single endpoint"""
    global results
    results["total"] += 1
    
    url = f"{BASE_URL}{path}"
    print(f"\n{'='*80}")
    print(f"Test: {description}")
    print(f"Method: {method} {path}")
    
    try:
        if method == "GET":
            response = requests.get(url, headers=HEADERS)
        elif method == "POST":
            response = requests.post(url, headers=HEADERS, json=data)
        elif method == "PUT":
            response = requests.put(url, headers=HEADERS, json=data)
        elif method == "DELETE":
            response = requests.delete(url, headers=HEADERS)
        
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)[:500]}")
        
        if response.status_code == expected_status:
            print("✅ PASSED")
            results["passed"] += 1
            return True
        else:
            print(f"❌ FAILED - Expected {expected_status}, got {response.status_code}")
            results["failed"] += 1
            results["errors"].append({
                "endpoint": path,
                "expected": expected_status,
                "actual": response.status_code,
                "response": response.text[:200]
            })
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        results["failed"] += 1
        results["errors"].append({
            "endpoint": path,
            "error": str(e)
        })
        return False

def run_tests():
    """Run all Phase 6 endpoint tests"""
    
    print("="*80)
    print("PHASE 6 AI/ML ENDPOINT TESTING")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Started: {datetime.now().isoformat()}")
    
    # 1. GPU Cost Tracking Endpoints
    print("\n" + "="*80)
    print("CATEGORY: GPU Cost Tracking")
    print("="*80)
    
    test_endpoint("GET", "/gpu-costs",
                  description="Get GPU costs")
    
    test_endpoint("GET", "/gpu-utilization",
                  description="Get GPU utilization")
    
    test_endpoint("GET", "/idle-gpus",
                  description="Get idle GPUs")
    
    test_endpoint("POST", "/gpu-prevention",
                  data={"action": "enable", "dry_run": True},
                  description="GPU prevention action")
    
    test_endpoint("GET", "/gpu-cost-savings",
                  description="Get GPU cost savings")
    
    # 2. Workload Classification Endpoints
    print("\n" + "="*80)
    print("CATEGORY: Workload Classification")
    print("="*80)
    
    test_endpoint("GET", "/workload-classification",
                  description="Get workload classifications")
    
    test_endpoint("POST", "/workload-classification",
                  data={
                      "instance_id": "i-1234567890abcdef0",
                      "workload_type": "training",
                      "model_name": "test-model"
                  },
                  description="Create workload classification")
    
    # 3. Cost Per Inference Endpoints
    print("\n" + "="*80)
    print("CATEGORY: Cost Per Inference")
    print("="*80)
    
    test_endpoint("GET", "/cost-per-inference",
                  description="Get cost per inference")
    
    test_endpoint("GET", "/inference-trends",
                  description="Get inference trends")
    
    # 4. Cost Per Training Endpoints
    print("\n" + "="*80)
    print("CATEGORY: Cost Per Training")
    print("="*80)
    
    test_endpoint("GET", "/cost-per-training",
                  description="Get cost per training")
    
    test_endpoint("GET", "/training-comparison",
                  description="Get training comparison")
    
    # 5. Spot Instance Recommendations
    print("\n" + "="*80)
    print("CATEGORY: Spot Instance Recommendations")
    print("="*80)
    
    test_endpoint("GET", "/spot-recommendations",
                  description="Get spot instance recommendations")
    
    test_endpoint("GET", "/spot-savings",
                  description="Get spot savings")
    
    # 6. SageMaker Cost Tracking
    print("\n" + "="*80)
    print("CATEGORY: SageMaker Cost Tracking")
    print("="*80)
    
    test_endpoint("GET", "/sagemaker-costs",
                  description="Get SageMaker costs")
    
    test_endpoint("GET", "/sagemaker-idle-endpoints",
                  description="Get SageMaker idle endpoints")
    
    # 7. Bedrock Cost Tracking
    print("\n" + "="*80)
    print("CATEGORY: Bedrock Cost Tracking")
    print("="*80)
    
    test_endpoint("GET", "/bedrock-costs",
                  description="Get Bedrock costs")
    
    test_endpoint("GET", "/bedrock-cost-per-invocation",
                  description="Get Bedrock cost per invocation")
    
    # 8. Multi-Account GPU Costs
    print("\n" + "="*80)
    print("CATEGORY: Multi-Account GPU Costs")
    print("="*80)
    
    test_endpoint("GET", "/multi-account/gpu-costs",
                  description="Get multi-account GPU costs")
    
    test_endpoint("GET", "/multi-account/gpu-utilization",
                  description="Get multi-account GPU utilization")
    
    test_endpoint("GET", "/multi-account/top-gpu-accounts",
                  description="Get top GPU accounts")
    
    # Print Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {results['total']}")
    print(f"Passed: {results['passed']} ✅")
    print(f"Failed: {results['failed']} ❌")
    print(f"Success Rate: {(results['passed']/results['total']*100):.1f}%")
    
    if results["errors"]:
        print("\n" + "="*80)
        print("ERRORS")
        print("="*80)
        for error in results["errors"]:
            print(f"\nEndpoint: {error.get('endpoint', 'Unknown')}")
            if 'error' in error:
                print(f"Error: {error['error']}")
            else:
                print(f"Expected: {error.get('expected')}, Got: {error.get('actual')}")
                print(f"Response: {error.get('response', '')[:200]}")
    
    print(f"\nCompleted: {datetime.now().isoformat()}")
    
    return results["failed"] == 0

if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
