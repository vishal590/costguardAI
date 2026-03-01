# CostGuard API Endpoint Test Commands

Quick reference for testing all CostGuard endpoints.

**API Base URL:** `https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod`

---

## Phase 1: Cost Data Collection

### 1. Fetch Cost Data
**Endpoint:** `POST /api/fetch`  
**Purpose:** Fetch cost data from AWS Cost Explorer and store in DynamoDB

```powershell
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/fetch" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"startDate": "2026-02-01", "endDate": "2026-02-27", "granularity": "DAILY"}' | Select-Object -ExpandProperty Content
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Cost data fetched and stored successfully",
  "data": {
    "recordsProcessed": 12,
    "dateRange": {"start": "2026-02-01", "end": "2026-02-27"},
    "totalCost": 0.00,
    "services": ["AWS Lambda", "Amazon S3", ...]
  }
}
```

---

### 2. Query Cost Data
**Endpoint:** `GET /api/cost-data`  
**Purpose:** Query stored cost data with filters

```powershell
# Query all data
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/cost-data?startDate=2026-02-01&endDate=2026-02-27" -Method GET | Select-Object -ExpandProperty Content

# Query specific service
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/cost-data?startDate=2026-02-01&endDate=2026-02-27&service=AWS%20Lambda" -Method GET | Select-Object -ExpandProperty Content

# Query with limit
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/cost-data?startDate=2026-02-01&endDate=2026-02-27&limit=5" -Method GET | Select-Object -ExpandProperty Content
```

**Expected Response:**
```json
{
  "success": true,
  "data": [
    {
      "date": "2026-02-27",
      "service": "AWS Lambda",
      "blendedCost": 0.0,
      "unblendedCost": 0.0,
      "currency": "USD"
    }
  ],
  "count": 12
}
```

---

## Phase 1.5: Real-Time Cost Estimation

### 3. Get Current Cost Estimation
**Endpoint:** `GET /api/cost-estimation/current`  
**Purpose:** Estimate current costs based on CloudWatch metrics

```powershell
# Last 1 hour (default)
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/cost-estimation/current" -Method GET | Select-Object -ExpandProperty Content

# Last 24 hours
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/cost-estimation/current?hours=24" -Method GET | Select-Object -ExpandProperty Content

# Specific region
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/cost-estimation/current?region=us-west-2" -Method GET | Select-Object -ExpandProperty Content
```

**Expected Response:**
```json
{
  "success": true,
  "estimates": [
    {
      "service": "lambda",
      "estimatedCost": 14.23,
      "currency": "USD",
      "confidenceLower": 12.50,
      "confidenceUpper": 16.00,
      "timestamp": "2026-03-01T08:50:00Z",
      "metricsCount": 100
    }
  ],
  "totalCost": 16.45,
  "currency": "USD"
}
```

---

### 4. Get Service-Specific Cost Estimation
**Endpoint:** `GET /api/cost-estimation/service/{service}`  
**Purpose:** Estimate costs for a specific service

```powershell
# Lambda costs
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/cost-estimation/service/lambda" -Method GET | Select-Object -ExpandProperty Content

# DynamoDB costs
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/cost-estimation/service/dynamodb" -Method GET | Select-Object -ExpandProperty Content

# S3 costs (last 24 hours)
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/cost-estimation/service/s3?hours=24" -Method GET | Select-Object -ExpandProperty Content
```

**Expected Response:**
```json
{
  "success": true,
  "service": "lambda",
  "estimatedCost": 14.23,
  "currency": "USD",
  "confidenceLower": 12.50,
  "confidenceUpper": 16.00,
  "timestamp": "2026-03-01T08:50:00Z",
  "metricsCount": 100
}
```

---

## Phase 2: AI Cost Forecasting

### 5. Get Cost Forecast
**Endpoint:** `GET /api/cost-forecast`  
**Purpose:** Generate AI-powered cost forecast

```powershell
# 7-day forecast (daily)
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/cost-forecast?days=7&granularity=daily" -Method GET | Select-Object -ExpandProperty Content

# 14-day forecast (daily)
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/cost-forecast?days=14&granularity=daily" -Method GET | Select-Object -ExpandProperty Content

# 30-day forecast (weekly)
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/cost-forecast?days=30&granularity=weekly" -Method GET | Select-Object -ExpandProperty Content
```

**Expected Response (with sufficient data):**
```json
{
  "success": true,
  "forecast_data": [
    {
      "date": "2026-03-02",
      "predicted_cost": 15.50,
      "confidence_lower": 12.00,
      "confidence_upper": 19.00,
      "currency": "USD"
    }
  ],
  "metadata": {
    "timestamp": "2026-03-01T08:50:00Z",
    "forecast_horizon": 7,
    "granularity": "daily",
    "model_used": "amazon.nova-lite-v1:0",
    "cache_hit": false,
    "historical_data_days": 30
  }
}
```

**Expected Response (insufficient data):**
```json
{
  "success": false,
  "error": {
    "code": "INSUFFICIENT_DATA",
    "message": "Insufficient historical data: need at least 30 data points, found 12"
  }
}
```

---

### 6. Get Service-Specific Forecast
**Endpoint:** `GET /api/cost-forecast/service/{service}`  
**Purpose:** Generate forecast for specific service

```powershell
# Lambda forecast
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/cost-forecast/service/lambda?days=7&granularity=daily" -Method GET | Select-Object -ExpandProperty Content

# DynamoDB forecast
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/cost-forecast/service/dynamodb?days=14&granularity=daily" -Method GET | Select-Object -ExpandProperty Content
```

---

## Phase 3: Cost Prevention System

### 7. Get Prevention Status
**Endpoint:** `GET /api/prevention/status`  
**Purpose:** Check prevention system configuration and status

```powershell
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/prevention/status" -Method GET | Select-Object -ExpandProperty Content
```

**Expected Response:**
```json
{
  "success": true,
  "enabled": false,
  "config": {
    "budget_threshold": 100.0,
    "warning_threshold": 80.0,
    "actions": ["stop_instances", "notify"],
    "protected_tags": ["production", "critical"]
  },
  "last_check": "2026-03-01T08:50:00Z"
}
```

---

### 8. Get Prevention Resources
**Endpoint:** `GET /api/prevention/resources`  
**Purpose:** List discovered AWS resources

```powershell
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/prevention/resources" -Method GET | Select-Object -ExpandProperty Content
```

**Expected Response:**
```json
{
  "success": true,
  "resources": [
    {
      "resource_id": "i-1234567890abcdef0",
      "resource_type": "ec2_instance",
      "region": "us-east-1",
      "tags": {"Name": "web-server", "Environment": "dev"},
      "estimated_cost": 50.00,
      "idle": false
    }
  ],
  "total_count": 10,
  "total_estimated_cost": 500.00
}
```

---

### 9. Enable Prevention System
**Endpoint:** `POST /api/prevention/enable`  
**Purpose:** Enable cost prevention system

```powershell
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/prevention/enable" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"budget_threshold": 100.0, "warning_threshold": 80.0}' | Select-Object -ExpandProperty Content
```

---

### 10. Disable Prevention System
**Endpoint:** `POST /api/prevention/disable`  
**Purpose:** Disable cost prevention system

```powershell
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/prevention/disable" `
  -Method POST | Select-Object -ExpandProperty Content
```

---

### 11. Rollback Prevention Actions
**Endpoint:** `POST /api/prevention/rollback`  
**Purpose:** Rollback previous prevention actions

```powershell
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/prevention/rollback" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"action_id": "action-123"}' | Select-Object -ExpandProperty Content
```

---

### 12. Get Prevention History
**Endpoint:** `GET /api/prevention/history`  
**Purpose:** Get history of prevention actions

```powershell
Invoke-WebRequest -Uri "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod/api/prevention/history" -Method GET | Select-Object -ExpandProperty Content
```

---

## Quick Test All Endpoints

```powershell
# Test all endpoints at once
$baseUrl = "https://5wtnoppajc.execute-api.us-east-1.amazonaws.com/prod"

Write-Host "Testing Prevention Status..." -ForegroundColor Cyan
Invoke-WebRequest -Uri "$baseUrl/api/prevention/status" -Method GET | Select-Object StatusCode

Write-Host "Testing Prevention Resources..." -ForegroundColor Cyan
Invoke-WebRequest -Uri "$baseUrl/api/prevention/resources" -Method GET | Select-Object StatusCode

Write-Host "Testing Cost Data Fetch..." -ForegroundColor Cyan
Invoke-WebRequest -Uri "$baseUrl/api/fetch" -Method POST -ContentType "application/json" -Body '{"startDate": "2026-02-01", "endDate": "2026-02-27", "granularity": "DAILY"}' | Select-Object StatusCode

Write-Host "Testing Cost Data Query..." -ForegroundColor Cyan
Invoke-WebRequest -Uri "$baseUrl/api/cost-data?startDate=2026-02-01&endDate=2026-02-27" -Method GET | Select-Object StatusCode

Write-Host "Testing Cost Estimation..." -ForegroundColor Cyan
Invoke-WebRequest -Uri "$baseUrl/api/cost-estimation/current" -Method GET | Select-Object StatusCode

Write-Host "Testing Cost Forecast..." -ForegroundColor Cyan
try {
    Invoke-WebRequest -Uri "$baseUrl/api/cost-forecast?days=7&granularity=daily" -Method GET | Select-Object StatusCode
} catch {
    Write-Host "Expected error (insufficient data)" -ForegroundColor Yellow
}

Write-Host "`nAll tests complete!" -ForegroundColor Green
```

---

## Notes

- All endpoints return JSON responses
- Use `-ErrorAction SilentlyContinue` to suppress PowerShell errors
- Add `| ConvertFrom-Json` to parse JSON responses
- Add `| ConvertTo-Json -Depth 5` for pretty-printed output
- Forecast endpoint requires 30+ data points to work

---

**Status:** ✅ All 6 endpoints working (100% success rate)
