"""
Integration tests for Phase 1 compatibility

These tests verify that Phase 1 endpoints continue to work correctly after
Phase 1.5 changes. This ensures backward compatibility.

Requirements: 5.4
Feature: near-realtime-cost-estimation, Task 12.2: Phase 1 Compatibility
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from moto import mock_aws
import boto3
from decimal import Decimal

from src.lambda_handler import handler


@pytest.fixture
def dynamodb_table():
    """Create a mock DynamoDB table for testing"""
    with mock_aws():
        # Create DynamoDB resource
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        # Create table
        table = dynamodb.create_table(
            TableName="costguard-cost-data",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Wait for table to be created
        table.meta.client.get_waiter("table_exists").wait(
            TableName="costguard-cost-data"
        )

        yield table


@pytest.fixture
def dynamodb_table_with_data():
    """Create a mock DynamoDB table with test data"""
    with mock_aws():
        # Create DynamoDB resource
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        # Create table
        table = dynamodb.create_table(
            TableName="costguard-cost-data",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Wait for table to be created
        table.meta.client.get_waiter("table_exists").wait(
            TableName="costguard-cost-data"
        )

        # Insert test data
        test_data = [
            {
                "pk": "COST#2025-01",
                "sk": "SERVICE#amazon-elastic-compute-cloud-compute",
                "date": "2025-01-01",
                "service": "Amazon Elastic Compute Cloud - Compute",
                "blendedCost": Decimal("123.45"),
                "unblendedCost": Decimal("123.45"),
                "currency": "USD",
                "unit": "USD",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            {
                "pk": "COST#2025-01",
                "sk": "SERVICE#amazon-simple-storage-service",
                "date": "2025-01-01",
                "service": "Amazon Simple Storage Service",
                "blendedCost": Decimal("45.67"),
                "unblendedCost": Decimal("45.67"),
                "currency": "USD",
                "unit": "USD",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        ]

        # Batch write test data
        with table.batch_writer() as batch:
            for item in test_data:
                batch.put_item(Item=item)

        yield table


@pytest.fixture
def mock_cost_explorer_response():
    """Mock Cost Explorer API response"""
    return {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2025-01-01", "End": "2025-01-31"},
                "Groups": [
                    {
                        "Keys": ["Amazon Elastic Compute Cloud - Compute"],
                        "Metrics": {
                            "BlendedCost": {"Amount": "123.45", "Unit": "USD"},
                            "UnblendedCost": {"Amount": "123.45", "Unit": "USD"},
                        },
                    },
                ],
            },
        ]
    }


class TestPhase1Compatibility:
    """Test Phase 1 endpoints continue to work after Phase 1.5 changes"""

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.services.cost_explorer.boto3.client")
    def test_fetch_endpoint_still_works(
        self, mock_ce_client, dynamodb_table, mock_cost_explorer_response
    ):
        """
        Test that Phase 1 /api/cost-data/fetch endpoint still works correctly

        Requirements: 5.4
        """
        # Setup Cost Explorer mock
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = mock_cost_explorer_response
        mock_ce_client.return_value = mock_ce

        # Create Lambda event for Phase 1 fetch endpoint
        event = {
            "httpMethod": "POST",
            "path": "/api/cost-data/fetch",
            "body": json.dumps(
                {
                    "startDate": "2025-01-01",
                    "endDate": "2025-01-31",
                    "granularity": "MONTHLY",
                }
            ),
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert "data" in body
        assert body["data"]["recordsProcessed"] == 1
        assert body["data"]["totalCost"] == 123.45

        # Verify Cost Explorer was called
        assert mock_ce.get_cost_and_usage.called

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_query_endpoint_still_works(self, dynamodb_table_with_data):
        """
        Test that Phase 1 /api/cost-data endpoint still works correctly

        Requirements: 5.4
        """
        # Create Lambda event for Phase 1 query endpoint
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "2025-01-01",
                "endDate": "2025-01-31",
            },
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert "data" in body
        assert body["count"] == 2
        assert len(body["data"]) == 2

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.services.cost_explorer.boto3.client")
    def test_fetch_response_format_unchanged(
        self, mock_ce_client, dynamodb_table, mock_cost_explorer_response
    ):
        """
        Test that Phase 1 fetch response format is unchanged

        Requirements: 5.4
        """
        # Setup Cost Explorer mock
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = mock_cost_explorer_response
        mock_ce_client.return_value = mock_ce

        # Create Lambda event
        event = {
            "httpMethod": "POST",
            "path": "/api/cost-data/fetch",
            "body": json.dumps(
                {
                    "startDate": "2025-01-01",
                    "endDate": "2025-01-31",
                    "granularity": "MONTHLY",
                }
            ),
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify response structure matches Phase 1 format
        assert response["statusCode"] == 200
        body = json.loads(response["body"])

        # Verify all Phase 1 fields are present
        assert "success" in body
        assert "message" in body
        assert "data" in body

        data = body["data"]
        assert "recordsProcessed" in data
        assert "dateRange" in data
        assert "start" in data["dateRange"]
        assert "end" in data["dateRange"]
        assert "totalCost" in data
        assert "services" in data

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_query_response_format_unchanged(self, dynamodb_table_with_data):
        """
        Test that Phase 1 query response format is unchanged

        Requirements: 5.4
        """
        # Create Lambda event
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "2025-01-01",
                "endDate": "2025-01-31",
            },
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify response structure matches Phase 1 format
        assert response["statusCode"] == 200
        body = json.loads(response["body"])

        # Verify all Phase 1 fields are present
        assert "success" in body
        assert "data" in body
        assert "count" in body

        # Verify each record has Phase 1 fields
        for record in body["data"]:
            assert "date" in record
            assert "service" in record
            assert "blendedCost" in record
            assert "unblendedCost" in record
            assert "currency" in record

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.services.cost_explorer.boto3.client")
    def test_fetch_error_handling_unchanged(self, mock_ce_client, dynamodb_table):
        """
        Test that Phase 1 fetch error handling is unchanged

        Requirements: 5.4
        """
        # Setup Cost Explorer mock to raise error
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.side_effect = Exception("Cost Explorer API error")
        mock_ce_client.return_value = mock_ce

        # Create Lambda event
        event = {
            "httpMethod": "POST",
            "path": "/api/cost-data/fetch",
            "body": json.dumps(
                {
                    "startDate": "2025-01-01",
                    "endDate": "2025-01-31",
                    "granularity": "MONTHLY",
                }
            ),
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify error response format matches Phase 1
        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["success"] is False
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_query_error_handling_unchanged(self, dynamodb_table_with_data):
        """
        Test that Phase 1 query error handling is unchanged

        Requirements: 5.4
        """
        # Create Lambda event with invalid date format
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "invalid-date",
            },
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify error response format matches Phase 1
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["success"] is False
        assert "error" in body

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.services.cost_explorer.boto3.client")
    def test_fetch_with_default_parameters_unchanged(
        self, mock_ce_client, dynamodb_table, mock_cost_explorer_response
    ):
        """
        Test that Phase 1 fetch with default parameters still works

        Requirements: 5.4
        """
        # Setup Cost Explorer mock
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = mock_cost_explorer_response
        mock_ce_client.return_value = mock_ce

        # Create Lambda event with no body (use defaults)
        event = {
            "httpMethod": "POST",
            "path": "/api/cost-data/fetch",
            "body": json.dumps({}),
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["data"]["recordsProcessed"] == 1

        # Verify Cost Explorer was called with default parameters
        call_args = mock_ce.get_cost_and_usage.call_args
        assert call_args is not None
        assert call_args[1]["Granularity"] == "MONTHLY"

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_query_with_no_filters_unchanged(self, dynamodb_table_with_data):
        """
        Test that Phase 1 query with no filters still works
        
        Note: Phase 1 requires at least a startDate to query data.
        Without it, returns empty results (expected behavior).

        Requirements: 5.4
        """
        # Create Lambda event with no query parameters
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": None,
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify response - Phase 1 returns empty when no startDate provided
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["count"] == 0
        assert len(body["data"]) == 0

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_query_with_service_filter_unchanged(self, dynamodb_table_with_data):
        """
        Test that Phase 1 query with service filter still works

        Requirements: 5.4
        """
        # Create Lambda event with service filter
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "2025-01-01",
                "endDate": "2025-01-31",
                "service": "Amazon Simple Storage Service",
            },
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["count"] == 1

        # Verify service filter was applied
        for record in body["data"]:
            assert record["service"] == "Amazon Simple Storage Service"

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_query_with_limit_unchanged(self, dynamodb_table_with_data):
        """
        Test that Phase 1 query with limit still works

        Requirements: 5.4
        """
        # Create Lambda event with limit
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "2025-01-01",
                "endDate": "2025-01-31",
                "limit": "1",
            },
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["count"] == 1
        assert len(body["data"]) == 1
