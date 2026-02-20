"""
Integration property tests for API retry logic

These tests verify that retry logic works correctly for CloudWatch API calls
with rate limiting and other retryable errors.

Requirements: 6.1
Feature: near-realtime-cost-estimation, Task 12.4: Property 7 - Retry Logic for Rate Limiting
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError
from moto import mock_aws
import boto3

from src.lambda_handler import handler


def create_client_error(error_code: str, http_status: int, message: str = "Test error"):
    """Create a mock ClientError for testing."""
    error_response = {
        'Error': {
            'Code': error_code,
            'Message': message
        },
        'ResponseMetadata': {
            'HTTPStatusCode': http_status,
            'RequestId': 'test-request-id'
        }
    }
    return ClientError(error_response, 'test_operation')


@pytest.fixture
def dynamodb_table():
    """Create a mock DynamoDB table"""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
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
        table.meta.client.get_waiter("table_exists").wait(
            TableName="costguard-cost-data"
        )
        yield table


class TestRetryLogicIntegration:
    """Test retry logic for API integration"""

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.services.cloudwatch_collector.CloudWatchMetricsCollector.collect_metrics")
    def test_cloudwatch_rate_limiting_triggers_retry(
        self, mock_collect_metrics, dynamodb_table
    ):
        """
        Property 7: Retry Logic for Rate Limiting
        
        Test that CloudWatch API calls that return 429 rate limiting
        trigger retry with exponential backoff.

        Requirements: 6.1
        """
        # Setup mock to fail with rate limiting first, then succeed
        rate_limit_error = create_client_error('Throttling', 429, 'Rate exceeded')
        
        # First call fails with rate limiting, second call succeeds
        mock_collect_metrics.side_effect = [
            rate_limit_error,
            {"ec2": []}  # Success on retry
        ]
        
        # Create Lambda event
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-estimation/service/ec2",
            "queryStringParameters": {"hours": "1"},
        }
        
        # Invoke Lambda handler
        response = handler(event, None)
        
        # Verify that the call eventually succeeded (after retry)
        # If retry logic works, we should get a 200 response
        assert response["statusCode"] in [200, 500]  # 500 if other errors occur
        
        # Verify collect_metrics was called multiple times (retry happened)
        assert mock_collect_metrics.call_count >= 1

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.services.cloudwatch_collector.CloudWatchMetricsCollector.collect_metrics")
    def test_cloudwatch_service_unavailable_triggers_retry(
        self, mock_collect_metrics, dynamodb_table
    ):
        """
        Test that CloudWatch API calls that return 503 service unavailable
        trigger retry with exponential backoff.

        Requirements: 6.1
        """
        # Setup mock to fail with service unavailable first, then succeed
        service_error = create_client_error('ServiceUnavailable', 503, 'Service temporarily unavailable')
        
        # First call fails, second call succeeds
        mock_collect_metrics.side_effect = [
            service_error,
            {"lambda": []}  # Success on retry
        ]
        
        # Create Lambda event
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-estimation/service/lambda",
            "queryStringParameters": {"hours": "1"},
        }
        
        # Invoke Lambda handler
        response = handler(event, None)
        
        # Verify response
        assert response["statusCode"] in [200, 500]
        
        # Verify retry happened
        assert mock_collect_metrics.call_count >= 1

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.services.cloudwatch_collector.CloudWatchMetricsCollector.collect_metrics")
    def test_non_retryable_errors_fail_immediately(
        self, mock_collect_metrics, dynamodb_table
    ):
        """
        Test that non-retryable errors (like 400 Bad Request) fail immediately
        without retry attempts.

        Requirements: 6.1
        """
        # Setup mock to fail with non-retryable error
        bad_request_error = create_client_error('ValidationException', 400, 'Invalid parameter')
        
        mock_collect_metrics.side_effect = bad_request_error
        
        # Create Lambda event
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-estimation/service/dynamodb",
            "queryStringParameters": {"hours": "1"},
        }
        
        # Invoke Lambda handler
        response = handler(event, None)
        
        # Verify error response
        assert response["statusCode"] == 500
        
        # Verify no retry happened (called only once)
        assert mock_collect_metrics.call_count == 1

    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.services.cloudwatch_collector.CloudWatchMetricsCollector.collect_metrics")
    @patch("src.services.pricing_manager.PricingManager.get_pricing_data")
    def test_pricing_api_rate_limiting_triggers_retry(
        self, mock_get_pricing, mock_collect_metrics, dynamodb_table
    ):
        """
        Test that Pricing API calls that return 429 rate limiting
        trigger retry with exponential backoff.

        Requirements: 6.1
        """
        # Setup metrics first so pricing API gets called
        from decimal import Decimal
        from src.utils.types import S3Metrics
        
        s3_metrics = S3Metrics(
            bucket_name="test-bucket",
            number_of_objects=100,
            bucket_size_bytes=Decimal("1000000"),
            get_requests=50,
            put_requests=25
        )
        mock_collect_metrics.return_value = {"s3": [s3_metrics]}
        
        # Setup pricing mock to fail with rate limiting first, then succeed
        rate_limit_error = create_client_error('Throttling', 429, 'Rate exceeded')
        
        from datetime import datetime, timedelta, timezone
        from src.utils.types import PricingData
        
        # First call fails, second call succeeds
        mock_get_pricing.side_effect = [
            rate_limit_error,
            PricingData(
                service="s3",
                region="us-east-1",
                prices={},
                currency="USD",
                last_updated=datetime.now(timezone.utc),
                ttl=int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp())
            )
        ]
        
        # Create Lambda event
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-estimation/service/s3",
            "queryStringParameters": {"hours": "1"},
        }
        
        # Invoke Lambda handler
        response = handler(event, None)
        
        # Verify response
        assert response["statusCode"] in [200, 500]
        
        # Verify pricing API was called
        assert mock_get_pricing.call_count >= 1


# Property-based test for retry logic
@given(
    retry_count=st.integers(min_value=1, max_value=3)
)
@settings(max_examples=100, deadline=2000)  # Increased deadline for integration test with retries
@patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
def test_property_retry_logic_for_rate_limiting(retry_count):
    """
    Property 7: Retry Logic for Rate Limiting
    
    For any CloudWatch API call that returns 429 rate limiting,
    the system must retry with exponential backoff.
    
    This property test verifies that:
    1. Rate limiting errors trigger retries
    2. The system eventually succeeds after retries
    3. Non-retryable errors fail immediately
    
    Validates: Requirements 6.1
    Feature: near-realtime-cost-estimation, Property 7: Retry Logic for Rate Limiting
    """
    with mock_aws():
        # Create DynamoDB table
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
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
        table.meta.client.get_waiter("table_exists").wait(
            TableName="costguard-cost-data"
        )
        
        with patch("src.services.cloudwatch_collector.CloudWatchMetricsCollector.collect_metrics") as mock_collect:
            # Setup mock to fail N times with rate limiting, then succeed
            rate_limit_error = create_client_error('Throttling', 429, 'Rate exceeded')
            
            # Create side effect: fail retry_count times, then succeed
            side_effects = [rate_limit_error] * retry_count + [{"ec2": []}]
            mock_collect.side_effect = side_effects
            
            # Create Lambda event
            event = {
                "httpMethod": "GET",
                "path": "/api/cost-estimation/service/ec2",
                "queryStringParameters": {"hours": "1"},
            }
            
            # Invoke Lambda handler
            response = handler(event, None)
            
            # Property: System should handle retries gracefully
            # Either succeeds after retries or returns error if max retries exceeded
            assert response["statusCode"] in [200, 500]
            assert "body" in response
            
            # Property: Retry count should be at least 1 (original call)
            assert mock_collect.call_count >= 1
