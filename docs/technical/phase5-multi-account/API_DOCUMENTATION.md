# Multi-Account API Documentation

Complete API reference for CostGuard Multi-Account Cost Management (Phase 5).

**Base URL**: `https://{api-id}.execute-api.{region}.amazonaws.com/prod/api`

**Version**: 1.0.0  
**Last Updated**: February 2026

---

## Table of Contents

- [Authentication](#authentication)
- [Rate Limiting](#rate-limiting)
- [Error Handling](#error-handling)
- [Organizations API](#organizations-api)
- [Costs API](#costs-api)
- [Allocation API](#allocation-api)
- [Budgets API](#budgets-api)
- [Response Formats](#response-formats)
- [Code Examples](#code-examples)

---

## Authentication

All API requests require an API key in the request headers.

### API Key Header

```http
x-api-key: YOUR_API_KEY
```

### Example Request

```bash
curl -H "x-api-key: YOUR_API_KEY" \
  https://api.costguard.example.com/api/organizations
```

### Obtaining an API Key

The multi-account API validates keys against the **DynamoDB** table `costguard-api-keys`, not API Gateway. After deploying CostGuardMultiAccountStack, run in the backend repo (aws-ideas):

```bash
python setup_api_auth.py
```

This creates the `costguard-api-keys` and `costguard-rate-limits` tables (if needed) and prints a test API key. Use that value in the `X-API-Key` header or as `VITE_MULTI_ACCOUNT_API_KEY` in the frontend. See `docs/deployment/DEPLOYMENT_BUGS_AND_FIXES.md` (Issue 5.2).

---

## Rate Limiting

- **Rate Limit**: 100 requests per minute per API key
- **Burst Limit**: 200 requests
- **Throttling**: Returns `429 Too Many Requests` when exceeded

### Rate Limit Headers

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

---

## Error Handling

### Error Response Format

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field": "Additional context"
    }
  }
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Missing or invalid API key |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

### Common Error Codes

- `INVALID_PARAMETERS`: Request parameters are invalid
- `RESOURCE_NOT_FOUND`: Requested resource doesn't exist
- `UNAUTHORIZED`: API key is missing or invalid
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `INTERNAL_ERROR`: Server error

---

## Organizations API

### List Organizations

Get all organizations accessible to the API key.

**Endpoint**: `GET /api/organizations`

**Response**:
```json
{
  "organizations": [
    {
      "id": "o-abc123xyz",
      "arn": "arn:aws:organizations::123456789012:organization/o-abc123xyz",
      "master_account_id": "123456789012",
      "feature_set": "ALL",
      "account_count": 15
    }
  ]
}
```

**Example**:
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  https://api.costguard.example.com/api/organizations
```

---

### List Accounts in Organization

Get all accounts in a specific organization.

**Endpoint**: `GET /api/organizations/{org_id}/accounts`

**Path Parameters**:
- `org_id` (required): Organization ID

**Query Parameters**:
- `status` (optional): Filter by account status (`ACTIVE`, `SUSPENDED`)
- `ou_id` (optional): Filter by organizational unit

**Response**:
```json
{
  "organization_id": "o-abc123xyz",
  "accounts": [
    {
      "id": "123456789012",
      "name": "Production Account",
      "email": "prod@example.com",
      "status": "ACTIVE",
      "ou_id": "ou-xyz-12345678",
      "ou_name": "Production",
      "joined_timestamp": "2024-01-15T10:30:00Z"
    },
    {
      "id": "234567890123",
      "name": "Development Account",
      "email": "dev@example.com",
      "status": "ACTIVE",
      "ou_id": "ou-xyz-87654321",
      "ou_name": "Development",
      "joined_timestamp": "2024-02-20T14:45:00Z"
    }
  ],
  "total_count": 2
}
```

**Example**:
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://api.costguard.example.com/api/organizations/o-abc123xyz/accounts?status=ACTIVE"
```

---

## Costs API

### Get Consolidated Costs

Get aggregated costs across all accounts in the organization.

**Endpoint**: `GET /api/costs/consolidated`

**Query Parameters**:
- `start_date` (required): Start date (YYYY-MM-DD)
- `end_date` (required): End date (YYYY-MM-DD)
- `granularity` (optional): `DAILY`, `WEEKLY`, `MONTHLY` (default: `DAILY`)
- `group_by` (optional): `SERVICE`, `ACCOUNT`, `OU` (default: `ACCOUNT`)

**Response**:
```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-01-31",
  "granularity": "DAILY",
  "total_cost": 15234.56,
  "currency": "USD",
  "costs_by_day": {
    "2026-01-01": 492.15,
    "2026-01-02": 498.32,
    "...": "..."
  },
  "costs_by_account": {
    "123456789012": 8500.00,
    "234567890123": 4234.56,
    "345678901234": 2500.00
  },
  "costs_by_service": {
    "EC2": 6000.00,
    "S3": 3000.00,
    "RDS": 2500.00,
    "Lambda": 1500.00,
    "Other": 2234.56
  }
}
```

**Example**:
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://api.costguard.example.com/api/costs/consolidated?start_date=2026-01-01&end_date=2026-01-31&granularity=DAILY"
```

---

### Get Costs by Account

Get per-account cost breakdown.

**Endpoint**: `GET /api/costs/by-account`

**Query Parameters**:
- `start_date` (required): Start date (YYYY-MM-DD)
- `end_date` (required): End date (YYYY-MM-DD)
- `account_ids` (optional): Comma-separated account IDs
- `top_n` (optional): Return top N spending accounts (default: all)

**Response**:
```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-01-31",
  "accounts": [
    {
      "account_id": "123456789012",
      "account_name": "Production Account",
      "total_cost": 8500.00,
      "percentage_of_total": 55.8,
      "costs_by_service": {
        "EC2": 4000.00,
        "S3": 2000.00,
        "RDS": 1500.00,
        "Lambda": 1000.00
      },
      "trend": {
        "previous_period": 7800.00,
        "change_percentage": 8.97,
        "change_amount": 700.00
      }
    },
    {
      "account_id": "234567890123",
      "account_name": "Development Account",
      "total_cost": 4234.56,
      "percentage_of_total": 27.8,
      "costs_by_service": {
        "EC2": 2000.00,
        "S3": 1000.00,
        "Lambda": 500.00,
        "Other": 734.56
      },
      "trend": {
        "previous_period": 4100.00,
        "change_percentage": 3.28,
        "change_amount": 134.56
      }
    }
  ],
  "total_cost": 15234.56
}
```

**Example**:
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://api.costguard.example.com/api/costs/by-account?start_date=2026-01-01&end_date=2026-01-31&top_n=5"
```

---

### Get Account Costs

Get detailed costs for a specific account.

**Endpoint**: `GET /api/costs/account/{account_id}`

**Path Parameters**:
- `account_id` (required): AWS account ID

**Query Parameters**:
- `start_date` (required): Start date (YYYY-MM-DD)
- `end_date` (required): End date (YYYY-MM-DD)
- `granularity` (optional): `DAILY`, `WEEKLY`, `MONTHLY` (default: `DAILY`)

**Response**:
```json
{
  "account_id": "123456789012",
  "account_name": "Production Account",
  "start_date": "2026-01-01",
  "end_date": "2026-01-31",
  "total_cost": 8500.00,
  "currency": "USD",
  "costs_by_day": {
    "2026-01-01": 274.19,
    "2026-01-02": 278.45,
    "...": "..."
  },
  "costs_by_service": {
    "EC2": {
      "cost": 4000.00,
      "percentage": 47.06,
      "trend": {
        "previous_period": 3800.00,
        "change_percentage": 5.26
      }
    },
    "S3": {
      "cost": 2000.00,
      "percentage": 23.53,
      "trend": {
        "previous_period": 1900.00,
        "change_percentage": 5.26
      }
    }
  },
  "top_resources": [
    {
      "resource_id": "i-0123456789abcdef0",
      "service": "EC2",
      "cost": 1200.00,
      "tags": {
        "Name": "prod-web-server-1",
        "Team": "Engineering",
        "Environment": "Production"
      }
    }
  ]
}
```

**Example**:
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://api.costguard.example.com/api/costs/account/123456789012?start_date=2026-01-01&end_date=2026-01-31"
```

---

## Allocation API

### Get Allocated Costs by Tag

Get costs allocated by a specific tag key.

**Endpoint**: `GET /api/allocation/by-tag`

**Query Parameters**:
- `tag_key` (required): Tag key (e.g., `Team`, `Project`, `Environment`)
- `start_date` (required): Start date (YYYY-MM-DD)
- `end_date` (required): End date (YYYY-MM-DD)
- `account_ids` (optional): Comma-separated account IDs

**Response**:
```json
{
  "tag_key": "Team",
  "start_date": "2026-01-01",
  "end_date": "2026-01-31",
  "total_allocated": 12500.00,
  "total_unallocated": 2734.56,
  "allocation_percentage": 82.05,
  "allocations": [
    {
      "tag_value": "Engineering",
      "cost": 7500.00,
      "percentage": 60.00,
      "account_breakdown": {
        "123456789012": 5000.00,
        "234567890123": 2500.00
      }
    },
    {
      "tag_value": "Marketing",
      "cost": 3000.00,
      "percentage": 24.00,
      "account_breakdown": {
        "123456789012": 2000.00,
        "345678901234": 1000.00
      }
    },
    {
      "tag_value": "Operations",
      "cost": 2000.00,
      "percentage": 16.00,
      "account_breakdown": {
        "123456789012": 1500.00,
        "234567890123": 500.00
      }
    }
  ]
}
```

**Example**:
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://api.costguard.example.com/api/allocation/by-tag?tag_key=Team&start_date=2026-01-01&end_date=2026-01-31"
```

---

### Get Unallocated Costs

Get costs that cannot be allocated to any team/project.

**Endpoint**: `GET /api/allocation/unallocated`

**Query Parameters**:
- `start_date` (required): Start date (YYYY-MM-DD)
- `end_date` (required): End date (YYYY-MM-DD)
- `account_ids` (optional): Comma-separated account IDs

**Response**:
```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-01-31",
  "total_cost": 15234.56,
  "unallocated_cost": 2734.56,
  "unallocated_percentage": 17.95,
  "unallocated_by_account": {
    "123456789012": 1500.00,
    "234567890123": 734.56,
    "345678901234": 500.00
  },
  "unallocated_by_service": {
    "EC2": 1000.00,
    "S3": 800.00,
    "RDS": 500.00,
    "Other": 434.56
  },
  "top_untagged_resources": [
    {
      "resource_id": "i-untagged-instance",
      "service": "EC2",
      "cost": 500.00,
      "account_id": "123456789012"
    }
  ]
}
```

**Example**:
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://api.costguard.example.com/api/allocation/unallocated?start_date=2026-01-01&end_date=2026-01-31"
```

---

### Create Allocation Rule

Create a custom cost allocation rule.

**Endpoint**: `POST /api/allocation/rules`

**Request Body**:
```json
{
  "name": "Split VPC Costs 50/50",
  "priority": 10,
  "rule_type": "PERCENTAGE",
  "conditions": {
    "service": "VPC"
  },
  "allocations": [
    {
      "target": "Team-A",
      "percentage": 50
    },
    {
      "target": "Team-B",
      "percentage": 50
    }
  ]
}
```

**Response**:
```json
{
  "rule_id": "rule-abc123xyz",
  "name": "Split VPC Costs 50/50",
  "priority": 10,
  "rule_type": "PERCENTAGE",
  "status": "ACTIVE",
  "created_at": "2026-02-24T10:30:00Z"
}
```

**Example**:
```bash
curl -X POST \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Split VPC Costs 50/50",
    "priority": 10,
    "rule_type": "PERCENTAGE",
    "conditions": {"service": "VPC"},
    "allocations": [
      {"target": "Team-A", "percentage": 50},
      {"target": "Team-B", "percentage": 50}
    ]
  }' \
  https://api.costguard.example.com/api/allocation/rules
```

---

## Budgets API

### Get Budget Hierarchy

Get the complete budget hierarchy (organization → OU → account).

**Endpoint**: `GET /api/budgets/hierarchy`

**Response**:
```json
{
  "organization": {
    "budget_id": "budget-org-123",
    "budget_amount": 50000.00,
    "current_spend": 42500.00,
    "utilization_percentage": 85.00,
    "period": "MONTHLY",
    "status": "WARNING"
  },
  "organizational_units": [
    {
      "ou_id": "ou-xyz-12345678",
      "ou_name": "Production",
      "budget_id": "budget-ou-456",
      "budget_amount": 30000.00,
      "current_spend": 25000.00,
      "utilization_percentage": 83.33,
      "period": "MONTHLY",
      "status": "WARNING",
      "accounts": [
        {
          "account_id": "123456789012",
          "account_name": "Production Account",
          "budget_id": "budget-acc-789",
          "budget_amount": 15000.00,
          "current_spend": 12500.00,
          "utilization_percentage": 83.33,
          "period": "MONTHLY",
          "status": "WARNING"
        }
      ]
    }
  ]
}
```

**Example**:
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  https://api.costguard.example.com/api/budgets/hierarchy
```

---

### Create Organization Budget

Create a budget at the organization level.

**Endpoint**: `POST /api/budgets/organization`

**Request Body**:
```json
{
  "budget_amount": 50000.00,
  "period": "MONTHLY",
  "alert_thresholds": [80, 100],
  "notification_email": "finance@example.com"
}
```

**Response**:
```json
{
  "budget_id": "budget-org-123",
  "entity_type": "ORGANIZATION",
  "budget_amount": 50000.00,
  "period": "MONTHLY",
  "alert_thresholds": [80, 100],
  "status": "ACTIVE",
  "created_at": "2026-02-24T10:30:00Z"
}
```

**Example**:
```bash
curl -X POST \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "budget_amount": 50000.00,
    "period": "MONTHLY",
    "alert_thresholds": [80, 100],
    "notification_email": "finance@example.com"
  }' \
  https://api.costguard.example.com/api/budgets/organization
```

---

### Create OU Budget

Create a budget for an organizational unit.

**Endpoint**: `POST /api/budgets/ou/{ou_id}`

**Path Parameters**:
- `ou_id` (required): Organizational unit ID

**Request Body**:
```json
{
  "budget_amount": 30000.00,
  "period": "MONTHLY",
  "alert_thresholds": [80, 100]
}
```

**Response**:
```json
{
  "budget_id": "budget-ou-456",
  "entity_id": "ou-xyz-12345678",
  "entity_type": "OU",
  "budget_amount": 30000.00,
  "period": "MONTHLY",
  "alert_thresholds": [80, 100],
  "status": "ACTIVE",
  "created_at": "2026-02-24T10:30:00Z"
}
```

**Example**:
```bash
curl -X POST \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "budget_amount": 30000.00,
    "period": "MONTHLY",
    "alert_thresholds": [80, 100]
  }' \
  https://api.costguard.example.com/api/budgets/ou/ou-xyz-12345678
```

---

## Response Formats

### Pagination

For endpoints that return large datasets, pagination is supported:

**Query Parameters**:
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Items per page (default: 50, max: 100)

**Response**:
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_items": 150,
    "total_pages": 3,
    "has_next": true,
    "has_previous": false
  }
}
```

### Date Formats

All dates use ISO 8601 format:
- Date: `YYYY-MM-DD` (e.g., `2026-01-31`)
- DateTime: `YYYY-MM-DDTHH:MM:SSZ` (e.g., `2026-01-31T23:59:59Z`)

### Currency

All monetary values are in USD unless otherwise specified.

---

## Code Examples

### Python

```python
import requests

API_KEY = "YOUR_API_KEY"
BASE_URL = "https://api.costguard.example.com/api"

headers = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json"
}

# Get consolidated costs
response = requests.get(
    f"{BASE_URL}/costs/consolidated",
    headers=headers,
    params={
        "start_date": "2026-01-01",
        "end_date": "2026-01-31",
        "granularity": "DAILY"
    }
)

costs = response.json()
print(f"Total cost: ${costs['total_cost']:.2f}")
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

const API_KEY = 'YOUR_API_KEY';
const BASE_URL = 'https://api.costguard.example.com/api';

const headers = {
  'x-api-key': API_KEY,
  'Content-Type': 'application/json'
};

// Get costs by account
axios.get(`${BASE_URL}/costs/by-account`, {
  headers: headers,
  params: {
    start_date: '2026-01-01',
    end_date: '2026-01-31',
    top_n: 5
  }
})
.then(response => {
  const accounts = response.data.accounts;
  accounts.forEach(account => {
    console.log(`${account.account_name}: $${account.total_cost}`);
  });
})
.catch(error => {
  console.error('Error:', error.response.data);
});
```

### cURL

```bash
# Get allocated costs by team
curl -H "x-api-key: YOUR_API_KEY" \
  "https://api.costguard.example.com/api/allocation/by-tag?tag_key=Team&start_date=2026-01-01&end_date=2026-01-31" \
  | jq '.allocations[] | {team: .tag_value, cost: .cost}'
```

### AWS CLI (Lambda Invoke)

```bash
# Invoke multi-account handler directly
aws lambda invoke \
  --function-name CostGuard-MultiAccountHandler \
  --payload '{"operation": "get_consolidated_costs", "start_date": "2026-01-01", "end_date": "2026-01-31"}' \
  response.json

cat response.json | jq '.total_cost'
```

---

## Related Documentation

- [Phase 5 README](README.md)
- [Cross-Account Setup](../../../infrastructure/CROSS_ACCOUNT_SETUP.md)
- [Deployment Scripts](../../../DEPLOYMENT_SCRIPTS.md)

---

**Version**: 1.0.0  
**Last Updated**: February 2026  
**Status**: ✅ Production Ready
