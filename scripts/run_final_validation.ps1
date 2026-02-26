# Phase 6 Final Validation Script
# Runs comprehensive test suite and generates validation report

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Phase 6 Final Validation Checkpoint" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$results = @{}
$totalTests = 0
$totalPassed = 0
$totalFailed = 0

# Function to run tests and capture results
function Run-TestSuite {
    param(
        [string]$Name,
        [string]$Path
    )
    
    Write-Host "Running $Name..." -ForegroundColor Yellow
    $output = pytest $Path --no-cov -q --tb=no 2>&1 | Out-String
    
    # Parse results
    if ($output -match "(\d+) passed") {
        $passed = [int]$Matches[1]
    } else {
        $passed = 0
    }
    
    if ($output -match "(\d+) failed") {
        $failed = [int]$Matches[1]
    } else {
        $failed = 0
    }
    
    $script:totalTests += ($passed + $failed)
    $script:totalPassed += $passed
    $script:totalFailed += $failed
    
    $results[$Name] = @{
        Passed = $passed
        Failed = $failed
        Total = $passed + $failed
    }
    
    Write-Host "  ✓ $passed passed, $failed failed" -ForegroundColor $(if ($failed -eq 0) { "Green" } else { "Red" })
    Write-Host ""
}

# Run test suites
Write-Host "1. Unit Tests" -ForegroundColor Cyan
Write-Host "-------------" -ForegroundColor Cyan
Run-TestSuite "AI/ML Unit Tests" "tests/unit/ai_ml/"
Run-TestSuite "Core Unit Tests" "tests/unit/test_*.py"
Run-TestSuite "Multi-Account Unit Tests" "tests/unit/multi_account/"

Write-Host "2. Integration Tests" -ForegroundColor Cyan
Write-Host "--------------------" -ForegroundColor Cyan
Run-TestSuite "AI/ML Handler Integration" "tests/integration/test_ai_ml_handler.py"
Run-TestSuite "AI/ML Integration Tests" "tests/integration/ai_ml/"
Run-TestSuite "Backward Compatibility" "tests/integration/test_backward_compatibility.py"
Run-TestSuite "Phase 1 Compatibility" "tests/integration/test_phase1_compatibility.py"

Write-Host "3. API Endpoint Tests" -ForegroundColor Cyan
Write-Host "---------------------" -ForegroundColor Cyan
Run-TestSuite "GPU Prevention API" "tests/integration/test_gpu_prevention_api.py"
Run-TestSuite "Idle GPU API" "tests/integration/test_idle_gpu_api.py"
Run-TestSuite "Workload Classification API" "tests/integration/test_workload_classification_integration.py"
Run-TestSuite "Spot Recommendations API" "tests/integration/test_spot_recommendations_api.py"
Run-TestSuite "SageMaker Tracking API" "tests/integration/test_sagemaker_tracking_api.py"
Run-TestSuite "Bedrock Tracking API" "tests/integration/test_bedrock_tracking_api.py"
Run-TestSuite "Cost Per Inference API" "tests/integration/test_cost_per_inference_api.py"
Run-TestSuite "Cost Per Training API" "tests/integration/test_cost_per_training_api.py"

# Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Validation Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Total Tests: $totalTests" -ForegroundColor White
Write-Host "Passed: $totalPassed" -ForegroundColor Green
Write-Host "Failed: $totalFailed" -ForegroundColor $(if ($totalFailed -eq 0) { "Green" } else { "Red" })
Write-Host ""

if ($totalFailed -eq 0) {
    Write-Host "✓ All tests passed!" -ForegroundColor Green
} else {
    Write-Host "✗ Some tests failed. Review output above." -ForegroundColor Red
}

Write-Host ""
Write-Host "Detailed Results:" -ForegroundColor Cyan
Write-Host "-----------------" -ForegroundColor Cyan
foreach ($key in $results.Keys | Sort-Object) {
    $r = $results[$key]
    $status = if ($r.Failed -eq 0) { "✓" } else { "✗" }
    $color = if ($r.Failed -eq 0) { "Green" } else { "Red" }
    Write-Host "$status $key : $($r.Passed)/$($r.Total) passed" -ForegroundColor $color
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
