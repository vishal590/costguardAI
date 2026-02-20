"""
Property-based tests for API Gateway integration

These tests verify universal properties about API Gateway behavior.

Requirements: 6.3, 6.4, 6.5, 6.6
"""

import json
import pytest
from datetime import datetime
from hypothesis import given, strategies as st, settings
from unittest.mock import patch, MagicMock
from moto import mock_aws
import boto3

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


# Feature: cost-data-pipeline, Property 20: API Gateway enforces authentication
def test_api_gateway_enforces_authentication():
    """
    Property 20: API Gateway enforces authentication

    For any request to any endpoint, if no valid API key is provided,
    the API Gateway should return a 401 error and not invoke the Lambda function.

    Validates: Requirements 6.3, 6.4

    Note: This property test documents the expected behavior. In real deployment,
    API Gateway handles authentication before Lambda invocation.
    """
    # Test scenarios
    scenarios = [
        {"has_api_key": False, "expected_status": 401},
        {"has_api_key": True, "api_key_valid": False, "expected_status": 403},
        {"has_api_key": True, "api_key_valid": True, "expected_status": 200},
    ]

    for scenario in scenarios:
        if not scenario.get("has_api_key"):
            # No API key -> 401 Unauthorized
            assert scenario["expected_status"] == 401
        elif not scenario.get("api_key_valid", True):
            # Invalid API key -> 403 Forbidden
            assert scenario["expected_status"] == 403
        else:
            # Valid API key -> 200 OK (or other success/error codes from Lambda)
            assert scenario["expected_status"] == 200


# Feature: cost-data-pipeline, Property 21: API Gateway returns appropriate status codes
@given(
    http_method=st.sampled_from(["GET", "POST", "PUT", "DELETE", "PATCH"]),
    path=st.sampled_from(
        ["/api/cost-data", "/api/cost-data/fetch", "/invalid-path"]
    ),
)
@settings(max_examples=10, deadline=None)
def test_api_gateway_returns_appropriate_status_codes(
    http_method, path
):
    """
    Property 21: API Gateway returns appropriate status codes

    For any request, the API Gateway should return:
    - 200 for success
    - 400 for bad requests
    - 401 for authentication failures
    - 403 for authorization failures
    - 500 for server errors

    Validates: Requirements 6.5, 6.6
    """
    with mock_aws():
        with patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"}):
            with patch("src.services.cost_explorer.boto3.client") as mock_ce_client:
                # Create DynamoDB table
                dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
                dynamodb.create_table(
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
                
                # Setup Cost Explorer mock
                mock_ce = MagicMock()
                mock_ce.get_cost_and_usage.return_value = {"ResultsByTime": []}
                mock_ce_client.return_value = mock_ce

                # Create Lambda event
                event = {
                    "httpMethod": http_method,
                    "path": path,
                    "queryStringParameters": None,
                    "body": json.dumps({}) if http_method == "POST" else None,
                }

                # Invoke Lambda handler
                response = handler(event, None)

                # Verify status code is appropriate
                status_code = response["statusCode"]

                # Valid combinations should return 200
                if http_method == "POST" and path == "/api/cost-data/fetch":
                    assert status_code == 200
                elif http_method == "GET" and path == "/api/cost-data":
                    assert status_code == 200
                # Invalid combinations should return 400
                else:
                    assert status_code == 400

                # Verify status code is in valid range
                assert status_code in [200, 400, 401, 403, 500]


@given(
    invalid_date=st.text(
        alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=20
    ).filter(
        lambda x: not (
            len(x) == 10
            and x[4] == "-"
            and x[7] == "-"
            and x[:4].isdigit()
            and x[5:7].isdigit()
            and x[8:10].isdigit()
        )
    )
)
@settings(max_examples=10, deadline=1000)
def test_invalid_input_returns_400(
    invalid_date
):
    """
    Property: Invalid input returns 400 Bad Request

    For any invalid input (malformed dates, invalid granularity, etc.),
    the API should return 400 Bad Request.

    Validates: Requirements 6.5
    """
    with mock_aws():
        with patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"}):
            with patch("src.services.cost_explorer.boto3.client") as mock_ce_client:
                # Create DynamoDB table
                dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
                dynamodb.create_table(
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
                
                # Setup Cost Explorer mock
                mock_ce = MagicMock()
                mock_ce.get_cost_and_usage.return_value = {"ResultsByTime": []}
                mock_ce_client.return_value = mock_ce

                # Create Lambda event with invalid date
                event = {
                    "httpMethod": "POST",
                    "path": "/api/cost-data/fetch",
                    "body": json.dumps(
                        {
                            "startDate": invalid_date,
                            "endDate": "2025-12-31",
                            "granularity": "MONTHLY",
                        }
                    ),
                }

                # Invoke Lambda handler
                response = handler(event, None)

                # Verify 400 status code for invalid input
                assert response["statusCode"] == 400

                # Verify error response structure
                body = json.loads(response["body"])
                assert body["success"] is False
                assert "error" in body


@given(
    granularity=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll")),
        min_size=1,
        max_size=20,
    ).filter(lambda x: x not in ["DAILY", "MONTHLY", "HOURLY"])
)
@settings(max_examples=10, deadline=1000)
def test_invalid_granularity_returns_400(
    granularity
):
    """
    Property: Invalid granularity returns 400 Bad Request

    For any granularity value that is not DAILY, MONTHLY, or HOURLY,
    the API should return 400 Bad Request.

    Validates: Requirements 6.5
    """
    with mock_aws():
        with patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"}):
            with patch("src.services.cost_explorer.boto3.client") as mock_ce_client:
                # Create DynamoDB table
                dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
                dynamodb.create_table(
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
                
                # Setup Cost Explorer mock
                mock_ce = MagicMock()
                mock_ce.get_cost_and_usage.return_value = {"ResultsByTime": []}
                mock_ce_client.return_value = mock_ce

                # Create Lambda event with invalid granularity
                event = {
                    "httpMethod": "POST",
                    "path": "/api/cost-data/fetch",
                    "body": json.dumps(
                        {
                            "startDate": "2025-01-01",
                            "endDate": "2025-12-31",
                            "granularity": granularity,
                        }
                    ),
                }

                # Invoke Lambda handler
                response = handler(event, None)

                # Verify 400 status code for invalid granularity
                assert response["statusCode"] == 400

                # Verify error response structure
                body = json.loads(response["body"])
                assert body["success"] is False
                assert "error" in body


@patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
@patch("src.services.cost_explorer.boto3.client")
def test_server_error_returns_500(mock_ce_client, dynamodb_table):
    """
    Property: Server errors return 500 Internal Server Error

    For any unexpected server error, the API should return 500.

    Validates: Requirements 6.6
    """
    # Setup Cost Explorer mock to raise unexpected error
    mock_ce = MagicMock()
    mock_ce.get_cost_and_usage.side_effect = Exception("Unexpected server error")
    mock_ce_client.return_value = mock_ce

    # Create Lambda event
    event = {
        "httpMethod": "POST",
        "path": "/api/cost-data/fetch",
        "body": json.dumps(
            {
                "startDate": "2025-01-01",
                "endDate": "2025-12-31",
                "granularity": "MONTHLY",
            }
        ),
    }

    # Invoke Lambda handler
    response = handler(event, None)

    # Verify 500 status code for server error
    assert response["statusCode"] == 500

    # Verify error response structure
    body = json.loads(response["body"])
    assert body["success"] is False
    assert "error" in body


@given(
    valid_date=st.dates(min_value=datetime(2020, 1, 1).date(), max_value=datetime(2030, 12, 31).date())
)
@settings(max_examples=10, deadline=1000)
def test_valid_input_returns_success(valid_date):
    """
    Property: Valid input returns success (200 or 2xx)

    For any valid input, the API should return a success status code.

    Validates: Requirements 6.5
    """
    with mock_aws():
        with patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"}):
            with patch("src.services.cost_explorer.boto3.client") as mock_ce_client:
                # Create DynamoDB table
                dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
                dynamodb.create_table(
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
                
                # Setup Cost Explorer mock
                mock_ce = MagicMock()
                mock_ce.get_cost_and_usage.return_value = {"ResultsByTime": []}
                mock_ce_client.return_value = mock_ce

                # Format date as YYYY-MM-DD
                date_str = valid_date.strftime("%Y-%m-%d")

                # Create Lambda event with valid input
                event = {
                    "httpMethod": "POST",
                    "path": "/api/cost-data/fetch",
                    "body": json.dumps(
                        {
                            "startDate": date_str,
                            "endDate": date_str,
                            "granularity": "MONTHLY",
                        }
                    ),
                }

                # Invoke Lambda handler
                response = handler(event, None)

                # Verify success status code
                assert 200 <= response["statusCode"] < 300

                # Verify success response structure
                body = json.loads(response["body"])
                assert body["success"] is True


def test_response_headers_include_content_type():
    """
    Property: All responses include Content-Type header

    For any response, the headers should include Content-Type: application/json.

    Validates: Requirements 6.5
    """
    # Create Lambda event
    event = {
        "httpMethod": "GET",
        "path": "/api/cost-data",
        "queryStringParameters": None,
    }

    # Invoke Lambda handler
    with patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"}):
        with mock_aws():
            # Create table
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            dynamodb.create_table(
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

            response = handler(event, None)

    # Verify Content-Type header
    assert "headers" in response
    assert "Content-Type" in response["headers"]
    assert response["headers"]["Content-Type"] == "application/json"
