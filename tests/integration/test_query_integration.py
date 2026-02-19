"""
Integration tests for GET /api/cost-data endpoint

These tests verify the end-to-end flow of querying cost data from DynamoDB.

Requirements: 6.2, 7.1, 7.2, 7.3, 7.4, 8.3
"""

import json
import pytest
from unittest.mock import patch
from datetime import datetime, timezone
from moto import mock_aws
import boto3
from decimal import Decimal

from src.lambda_handler import handler


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
            {
                "pk": "COST#2025-02",
                "sk": "SERVICE#amazon-elastic-compute-cloud-compute",
                "date": "2025-02-01",
                "service": "Amazon Elastic Compute Cloud - Compute",
                "blendedCost": Decimal("134.56"),
                "unblendedCost": Decimal("134.56"),
                "currency": "USD",
                "unit": "USD",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            {
                "pk": "COST#2025-02",
                "sk": "SERVICE#amazon-simple-storage-service",
                "date": "2025-02-01",
                "service": "Amazon Simple Storage Service",
                "blendedCost": Decimal("56.78"),
                "unblendedCost": Decimal("56.78"),
                "currency": "USD",
                "unit": "USD",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            {
                "pk": "COST#2025-03",
                "sk": "SERVICE#aws-lambda",
                "date": "2025-03-01",
                "service": "AWS Lambda",
                "blendedCost": Decimal("12.34"),
                "unblendedCost": Decimal("12.34"),
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


class TestQueryIntegration:
    """Integration tests for query endpoint"""

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_query_returns_all_data(self, dynamodb_table_with_data):
        """
        Test query endpoint returns all data when no filters are provided

        Requirements: 6.2, 7.1
        """
        # Create Lambda event with start date to enable querying
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "2025-01-01",
                "endDate": "2025-12-31",
            },
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert "data" in body
        assert "count" in body
        assert body["count"] == 5
        assert len(body["data"]) == 5

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_query_with_date_range_filter(self, dynamodb_table_with_data):
        """
        Test query endpoint filters by date range

        Requirements: 7.2, 7.3
        """
        # Create Lambda event with date range filter
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "2025-01-01",
                "endDate": "2025-02-28",
            },
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["count"] == 4  # Only Jan and Feb records

        # Verify all returned records are within date range
        for record in body["data"]:
            date = record["date"]
            assert date >= "2025-01-01"
            assert date <= "2025-02-28"

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_query_with_service_filter(self, dynamodb_table_with_data):
        """
        Test query endpoint filters by service

        Requirements: 7.3
        """
        # Create Lambda event with service filter and date range
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "2025-01-01",
                "endDate": "2025-12-31",
                "service": "Amazon Simple Storage Service",
            },
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["count"] == 2  # Only S3 records

        # Verify all returned records are for the specified service
        for record in body["data"]:
            assert record["service"] == "Amazon Simple Storage Service"

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_query_with_limit(self, dynamodb_table_with_data):
        """
        Test query endpoint respects limit parameter

        Requirements: 7.4
        """
        # Create Lambda event with limit and date range
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "2025-01-01",
                "endDate": "2025-12-31",
                "limit": "2",
            },
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["count"] == 2
        assert len(body["data"]) == 2

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_query_with_multiple_filters(self, dynamodb_table_with_data):
        """
        Test query endpoint with multiple filters combined

        Requirements: 7.1, 7.2, 7.3, 7.4
        """
        # Create Lambda event with multiple filters (date range and limit)
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "2025-01-01",
                "endDate": "2025-02-28",
                "limit": "3",
            },
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["count"] == 3  # Limited to 3 records from Jan-Feb (4 total available)
        assert len(body["data"]) == 3

        # Verify date filter was applied
        for record in body["data"]:
            assert record["date"] >= "2025-01-01"
            assert record["date"] <= "2025-02-28"

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_query_response_contains_required_fields(self, dynamodb_table_with_data):
        """
        Test query response contains all required fields

        Requirements: 8.3
        """
        # Create Lambda event
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": None,
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify response structure
        assert response["statusCode"] == 200
        body = json.loads(response["body"])

        # Verify top-level structure
        assert "success" in body
        assert body["success"] is True
        assert "data" in body
        assert "count" in body

        # Verify each record has required fields
        for record in body["data"]:
            assert "date" in record
            assert "service" in record
            assert "blendedCost" in record
            assert "unblendedCost" in record
            assert "currency" in record

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_query_with_no_results(self, dynamodb_table_with_data):
        """
        Test query endpoint returns empty array when no data matches filters

        Requirements: 7.1, 8.3
        """
        # Create Lambda event with filters that match no data
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "2030-01-01",
                "endDate": "2030-12-31",
            },
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["count"] == 0
        assert len(body["data"]) == 0

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_query_handles_invalid_date_format(self, dynamodb_table_with_data):
        """
        Test query endpoint handles invalid date format

        Requirements: 7.1
        """
        # Create Lambda event with invalid date format
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "01-01-2025",  # Invalid format
            },
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify error response
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["success"] is False
        assert "error" in body

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_query_handles_invalid_date_range(self, dynamodb_table_with_data):
        """
        Test query endpoint handles invalid date range (start after end)

        Requirements: 7.1
        """
        # Create Lambda event with invalid date range
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "2025-12-31",
                "endDate": "2025-01-01",  # End before start
            },
        }

        # Invoke Lambda handler
        response = handler(event, None)

        # Verify error response
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["success"] is False
        assert "error" in body
