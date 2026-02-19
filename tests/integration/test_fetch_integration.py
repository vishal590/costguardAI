"""
Integration tests for POST /api/cost-data/fetch endpoint

These tests verify the end-to-end flow of fetching cost data from Cost Explorer
and storing it in DynamoDB.

Requirements: 1.1, 3.5, 6.1, 8.1, 8.2
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from moto import mock_aws
import boto3

from src.lambda_handler import handler
from src.utils.types import CostRecord


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
                    {
                        "Keys": ["Amazon Simple Storage Service"],
                        "Metrics": {
                            "BlendedCost": {"Amount": "45.67", "Unit": "USD"},
                            "UnblendedCost": {"Amount": "45.67", "Unit": "USD"},
                        },
                    },
                ],
            },
            {
                "TimePeriod": {"Start": "2025-02-01", "End": "2025-02-28"},
                "Groups": [
                    {
                        "Keys": ["Amazon Elastic Compute Cloud - Compute"],
                        "Metrics": {
                            "BlendedCost": {"Amount": "134.56", "Unit": "USD"},
                            "UnblendedCost": {"Amount": "134.56", "Unit": "USD"},
                        },
                    },
                    {
                        "Keys": ["Amazon Simple Storage Service"],
                        "Metrics": {
                            "BlendedCost": {"Amount": "56.78", "Unit": "USD"},
                            "UnblendedCost": {"Amount": "56.78", "Unit": "USD"},
                        },
                    },
                ],
            },
        ]
    }


class TestFetchIntegration:
    """Integration tests for fetch endpoint"""

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data"})
    @patch("src.services.cost_explorer.boto3.client")
    def test_fetch_stores_data_in_dynamodb(
        self, mock_ce_client, dynamodb_table, mock_cost_explorer_response
    ):
        """
        Test that fetch endpoint successfully fetches data from Cost Explorer
        and stores it in DynamoDB

        Requirements: 1.1, 3.5, 6.1
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
                    "endDate": "2025-02-28",
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
        assert body["data"]["recordsProcessed"] == 4
        assert body["data"]["dateRange"]["start"] == "2025-01-01"
        assert body["data"]["dateRange"]["end"] == "2025-02-28"
        assert body["data"]["totalCost"] == 360.46  # Sum of all costs

        # Verify data was stored in DynamoDB
        items = list(dynamodb_table.scan()["Items"])
        assert len(items) == 4

        # Verify record structure
        for item in items:
            assert "pk" in item
            assert "sk" in item
            assert "date" in item
            assert "service" in item
            assert "blendedCost" in item
            assert "unblendedCost" in item
            assert "currency" in item
            assert "timestamp" in item

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data"})
    @patch("src.services.cost_explorer.boto3.client")
    def test_fetch_with_default_parameters(
        self, mock_ce_client, dynamodb_table, mock_cost_explorer_response
    ):
        """
        Test fetch endpoint with default parameters (no body)

        Requirements: 1.1, 6.1
        """
        # Setup Cost Explorer mock
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = mock_cost_explorer_response
        mock_ce_client.return_value = mock_ce

        # Create Lambda event with no body
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
        assert body["data"]["recordsProcessed"] == 4

        # Verify Cost Explorer was called with default parameters
        call_args = mock_ce.get_cost_and_usage.call_args
        assert call_args is not None
        assert call_args[1]["Granularity"] == "MONTHLY"

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data"})
    @patch("src.services.cost_explorer.boto3.client")
    def test_fetch_response_contains_correct_summary(
        self, mock_ce_client, dynamodb_table, mock_cost_explorer_response
    ):
        """
        Test that fetch response contains complete summary information

        Requirements: 8.1, 8.2
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
                    "endDate": "2025-02-28",
                    "granularity": "MONTHLY",
                }
            ),
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify response structure
        assert response["statusCode"] == 200
        body = json.loads(response["body"])

        # Verify summary contains all required fields
        assert "success" in body
        assert body["success"] is True
        assert "message" in body
        assert "data" in body

        data = body["data"]
        assert "recordsProcessed" in data
        assert "dateRange" in data
        assert "start" in data["dateRange"]
        assert "end" in data["dateRange"]
        assert "totalCost" in data
        assert "services" in data

        # Verify services list
        assert len(data["services"]) == 2
        assert "Amazon Elastic Compute Cloud - Compute" in data["services"]
        assert "Amazon Simple Storage Service" in data["services"]

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data"})
    @patch("src.services.cost_explorer.boto3.client")
    def test_fetch_handles_empty_response(self, mock_ce_client, dynamodb_table):
        """
        Test fetch endpoint handles empty Cost Explorer response

        Requirements: 1.1, 8.1
        """
        # Setup Cost Explorer mock with empty response
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = {"ResultsByTime": []}
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

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["data"]["recordsProcessed"] == 0
        assert body["data"]["totalCost"] == 0.0
        assert len(body["data"]["services"]) == 0

        # Verify no data was stored in DynamoDB
        items = list(dynamodb_table.scan()["Items"])
        assert len(items) == 0

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data"})
    @patch("src.services.cost_explorer.boto3.client")
    def test_fetch_handles_cost_explorer_error(self, mock_ce_client, dynamodb_table):
        """
        Test fetch endpoint handles Cost Explorer API errors

        Requirements: 1.1, 8.4
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

        # Verify error response
        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["success"] is False
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]
