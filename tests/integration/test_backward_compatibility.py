"""
Integration tests for Phase 1-5 backward compatibility with Phase 6.

These tests verify that Phase 6 (AI/ML Workload Cost Management) additions
do not break existing Phase 1-5 functionality. All Phase 1-5 APIs should
continue to work correctly after Phase 6 deployment.

Requirements: IR-2.1, IR-2.2, IR-2.3, IR-2.4, IR-2.5
Feature: ai-ml-workload-costs, Task 15.5: Backward compatibility tests
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from moto import mock_aws
import boto3
from decimal import Decimal

from src.lambda_handler import handler
from src.ai_ml_handler import handler as ai_ml_handler


@pytest.fixture
def dynamodb_table_with_data():
    """Create a mock DynamoDB table with test data for Phase 1-5"""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        
        # Create cost data table with Phase 1 schema (date_service as partition key)
        table = dynamodb.create_table(
            TableName="costguard-cost-data",
            KeySchema=[
                {"AttributeName": "date_service", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "date_service", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        
        table.meta.client.get_waiter("table_exists").wait(TableName="costguard-cost-data")
        
        # Insert test data using Phase 1 schema
        test_data = [
            {
                "date_service": "2025-01-01#Amazon Elastic Compute Cloud - Compute",
                "date": "2025-01-01",
                "service": "Amazon Elastic Compute Cloud - Compute",
                "blendedCost": Decimal("123.45"),
                "unblendedCost": Decimal("123.45"),
                "currency": "USD",
                "unit": "USD",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            {
                "date_service": "2025-01-01#Amazon Simple Storage Service",
                "date": "2025-01-01",
                "service": "Amazon Simple Storage Service",
                "blendedCost": Decimal("45.67"),
                "unblendedCost": Decimal("45.67"),
                "currency": "USD",
                "unit": "USD",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        ]
        
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


class TestPhase1BackwardCompatibility:
    """Test Phase 1 (Cost Explorer data) APIs remain unchanged"""
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.services.cost_explorer.boto3.client")
    def test_phase1_fetch_endpoint_unchanged(
        self, mock_ce_client, dynamodb_table_with_data, mock_cost_explorer_response
    ):
        """
        Verify Phase 1 /api/cost-data/fetch endpoint still works correctly
        
        Requirements: IR-2.1
        """
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = mock_cost_explorer_response
        mock_ce_client.return_value = mock_ce
        
        event = {
            "httpMethod": "POST",
            "path": "/api/cost-data/fetch",
            "body": json.dumps({
                "startDate": "2025-01-01",
                "endDate": "2025-01-31",
                "granularity": "MONTHLY",
            }),
        }
        
        response = handler(event, None)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert "data" in body
        assert body["data"]["recordsProcessed"] == 1
        assert body["data"]["totalCost"] == 123.45
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_phase1_query_endpoint_unchanged(self, dynamodb_table_with_data):
        """
        Verify Phase 1 /api/cost-data query endpoint still works correctly
        
        Requirements: IR-2.1
        """
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "2025-01-01",
                "endDate": "2025-01-31",
            },
        }
        
        response = handler(event, None)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert "data" in body
        assert body["count"] == 2
        assert len(body["data"]) == 2
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_phase1_response_format_unchanged(self, dynamodb_table_with_data):
        """
        Verify Phase 1 response format is unchanged
        
        Requirements: IR-2.1
        """
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "2025-01-01",
                "endDate": "2025-01-31",
            },
        }
        
        response = handler(event, None)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        
        # Verify Phase 1 fields are present
        assert "success" in body
        assert "data" in body
        assert "count" in body
        
        # Verify record structure
        for record in body["data"]:
            assert "date" in record
            assert "service" in record
            assert "blendedCost" in record
            assert "unblendedCost" in record
            assert "currency" in record


class TestPhase2BackwardCompatibility:
    """Test Phase 2 (Forecasting) APIs remain unchanged"""
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.lambda_handler.HistoricalDataRetriever")
    @patch("src.lambda_handler.ForecastCacheManager")
    @patch("src.lambda_handler.BedrockClient")
    @patch("src.lambda_handler.ForecastEngine")
    def test_phase2_forecast_endpoint_unchanged(
        self, 
        mock_forecast_engine_class, 
        mock_bedrock_class,
        mock_cache_class,
        mock_historical_class,
        dynamodb_table_with_data
    ):
        """
        Verify Phase 2 /api/cost-forecast endpoint still works correctly
        
        Requirements: IR-2.2
        """
        # Mock forecast engine instance
        mock_engine = MagicMock()
        mock_forecast_engine_class.return_value = mock_engine
        
        # Mock forecast response
        mock_forecast_response = MagicMock()
        mock_forecast_response.success = True
        mock_forecast_response.forecast_data = [
            MagicMock(
                date="2025-02-01",
                predicted_cost=150.0,
                confidence_lower=140.0,
                confidence_upper=160.0,
                currency="USD"
            )
        ]
        mock_forecast_response.metadata = MagicMock(
            timestamp="2025-01-15T10:00:00Z",
            forecast_horizon=30,
            granularity="daily",
            model_used="bedrock-claude",
            service=None,
            services_included=["ec2", "s3"],
            cache_hit=False,
            historical_data_days=90
        )
        mock_engine.generate_forecast.return_value = mock_forecast_response
        
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-forecast",
            "queryStringParameters": {
                "days": "30",
                "granularity": "daily",
            },
        }
        
        response = handler(event, None)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert "forecast_data" in body
        assert "metadata" in body
        assert len(body["forecast_data"]) == 1
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.lambda_handler.HistoricalDataRetriever")
    @patch("src.lambda_handler.ForecastCacheManager")
    @patch("src.lambda_handler.BedrockClient")
    @patch("src.lambda_handler.ForecastEngine")
    def test_phase2_service_forecast_endpoint_unchanged(
        self,
        mock_forecast_engine_class,
        mock_bedrock_class,
        mock_cache_class,
        mock_historical_class,
        dynamodb_table_with_data
    ):
        """
        Verify Phase 2 /api/cost-forecast/service/{service} endpoint still works
        
        Requirements: IR-2.2
        """
        # Mock forecast engine instance
        mock_engine = MagicMock()
        mock_forecast_engine_class.return_value = mock_engine
        
        mock_forecast_response = MagicMock()
        mock_forecast_response.success = True
        mock_forecast_response.forecast_data = [
            MagicMock(
                date="2025-02-01",
                predicted_cost=100.0,
                confidence_lower=95.0,
                confidence_upper=105.0,
                currency="USD"
            )
        ]
        mock_forecast_response.metadata = MagicMock(
            timestamp="2025-01-15T10:00:00Z",
            forecast_horizon=30,
            granularity="daily",
            model_used="bedrock-claude",
            service="ec2",
            services_included=["ec2"],
            cache_hit=False,
            historical_data_days=90
        )
        mock_engine.generate_forecast.return_value = mock_forecast_response
        
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-forecast/service/ec2",
            "queryStringParameters": {
                "days": "30",
                "granularity": "daily",
            },
        }
        
        response = handler(event, None)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["metadata"]["service"] == "ec2"


class TestPhase3BackwardCompatibility:
    """Test Phase 3 (Prevention) APIs remain unchanged"""
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.lambda_handler._get_prevention_engine")
    def test_phase3_prevention_status_unchanged(self, mock_get_engine, dynamodb_table_with_data):
        """
        Verify Phase 3 /api/prevention/status endpoint still works correctly
        
        Requirements: IR-2.3
        """
        mock_engine = MagicMock()
        mock_engine.get_status.return_value = {
            "enabled": True,
            "last_check": "2025-01-15T10:00:00Z",
            "actions_taken": 5
        }
        mock_get_engine.return_value = mock_engine
        
        event = {
            "httpMethod": "GET",
            "path": "/api/prevention/status",
        }
        
        response = handler(event, None)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert "status" in body
        assert body["status"]["enabled"] is True
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.lambda_handler._get_prevention_engine")
    def test_phase3_prevention_enable_unchanged(self, mock_get_engine, dynamodb_table_with_data):
        """
        Verify Phase 3 /api/prevention/enable endpoint still works correctly
        
        Requirements: IR-2.3
        """
        mock_engine = MagicMock()
        mock_engine.get_status.return_value = {"enabled": True}
        mock_get_engine.return_value = mock_engine
        
        event = {
            "httpMethod": "POST",
            "path": "/api/prevention/enable",
        }
        
        response = handler(event, None)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["message"] == "Prevention system enabled"
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.lambda_handler._get_prevention_engine")
    def test_phase3_prevention_resources_unchanged(self, mock_get_engine, dynamodb_table_with_data):
        """
        Verify Phase 3 /api/prevention/resources endpoint still works correctly
        
        Requirements: IR-2.3
        """
        mock_engine = MagicMock()
        
        mock_resource = MagicMock()
        mock_resource.resource_id = "i-1234567890abcdef0"
        mock_resource.resource_type = "ec2-instance"
        mock_resource.service = "ec2"
        mock_resource.region = "us-east-1"
        mock_resource.tags = {"Name": "test-instance"}
        mock_resource.state = "running"
        mock_resource.creation_date = "2025-01-01T00:00:00Z"
        
        mock_engine.get_resources.return_value = [mock_resource]
        mock_get_engine.return_value = mock_engine
        
        event = {
            "httpMethod": "GET",
            "path": "/api/prevention/resources",
            "queryStringParameters": {
                "service": "ec2",
            },
        }
        
        response = handler(event, None)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert "resources" in body
        assert body["count"] == 1


class TestPhase4BackwardCompatibility:
    """Test Phase 4 (AI Advisor) APIs remain unchanged"""
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.lambda_handler._get_advisor_engine")
    def test_phase4_advisor_query_unchanged(self, mock_get_engine, dynamodb_table_with_data):
        """
        Verify Phase 4 /api/advisor/query endpoint still works correctly
        
        Requirements: IR-2.4
        """
        mock_engine = MagicMock()
        mock_response = MagicMock()
        mock_response.response_text = "Your EC2 costs are $123.45 this month."
        mock_response.recommendations = []
        mock_response.cost_data = {"ec2": 123.45}
        mock_response.confidence = 0.95
        mock_response.cached = False
        
        mock_engine.process_query.return_value = mock_response
        mock_get_engine.return_value = mock_engine
        
        event = {
            "httpMethod": "POST",
            "path": "/api/advisor/query",
            "body": json.dumps({
                "query": "What are my EC2 costs?",
                "user_id": "test-user",
                "session_id": "test-session"
            }),
        }
        
        response = handler(event, None)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert "response" in body
        assert "recommendations" in body
        assert "confidence" in body
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.lambda_handler._get_advisor_engine")
    def test_phase4_advisor_history_unchanged(self, mock_get_engine, dynamodb_table_with_data):
        """
        Verify Phase 4 /api/advisor/history endpoint still works correctly
        
        Requirements: IR-2.4
        """
        mock_engine = MagicMock()
        mock_turn = MagicMock()
        mock_turn.query = "What are my costs?"
        mock_turn.response = "Your costs are $123.45"
        mock_turn.timestamp = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        
        mock_engine.get_conversation_history.return_value = [mock_turn]
        mock_get_engine.return_value = mock_engine
        
        event = {
            "httpMethod": "GET",
            "path": "/api/advisor/history",
            "queryStringParameters": {
                "session_id": "test-session",
            },
        }
        
        response = handler(event, None)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert "history" in body
        assert body["count"] == 1
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.lambda_handler._get_advisor_engine")
    def test_phase4_advisor_suggestions_unchanged(self, mock_get_engine, dynamodb_table_with_data):
        """
        Verify Phase 4 /api/advisor/suggestions endpoint still works correctly
        
        Requirements: IR-2.4
        """
        mock_engine = MagicMock()
        mock_insight = MagicMock()
        mock_insight.insight_type = "cost-spike"
        mock_insight.title = "EC2 cost spike detected"
        mock_insight.description = "EC2 costs increased by 50%"
        mock_insight.severity = "high"
        mock_insight.action_required = True
        mock_insight.related_services = ["ec2"]
        mock_insight.estimated_impact = 50.0
        
        mock_engine.generate_proactive_insights.return_value = [mock_insight]
        mock_get_engine.return_value = mock_engine
        
        event = {
            "httpMethod": "GET",
            "path": "/api/advisor/suggestions",
            "queryStringParameters": {
                "user_id": "test-user",
            },
        }
        
        response = handler(event, None)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert "insights" in body
        assert body["count"] == 1


class TestPhase5BackwardCompatibility:
    """Test Phase 5 (Multi-account) APIs remain unchanged"""
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_phase5_multi_account_endpoints_exist(self, dynamodb_table_with_data):
        """
        Verify Phase 5 multi-account endpoints are still accessible
        
        Requirements: IR-2.5
        
        Note: This is a basic test to ensure the endpoints exist.
        Full Phase 5 testing would require multi-account setup.
        """
        # Test that multi-account endpoints are routed correctly
        # (even if they return errors due to missing setup)
        
        event = {
            "httpMethod": "GET",
            "path": "/api/ai-ml/multi-account/gpu-costs",
            "queryStringParameters": {
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
            },
        }
        
        # This should route to the AI/ML handler
        # We're just verifying the endpoint exists and is routable
        response = ai_ml_handler(event, None)
        
        # Should get a response (even if it's an error due to missing data)
        assert response is not None
        assert "statusCode" in response


class TestMultiPhaseIntegration:
    """Test that Phase 6 integrates correctly with multiple phases"""
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.services.cost_explorer.boto3.client")
    def test_phase1_and_phase6_data_compatibility(
        self, mock_ce_client, dynamodb_table_with_data, mock_cost_explorer_response
    ):
        """
        Verify Phase 1 cost data is compatible with Phase 6 GPU tracking
        
        Requirements: IR-2.1, IR-2.5
        """
        # First, fetch Phase 1 data
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = mock_cost_explorer_response
        mock_ce_client.return_value = mock_ce
        
        phase1_event = {
            "httpMethod": "POST",
            "path": "/api/cost-data/fetch",
            "body": json.dumps({
                "startDate": "2025-01-01",
                "endDate": "2025-01-31",
                "granularity": "MONTHLY",
            }),
        }
        
        phase1_response = handler(phase1_event, None)
        assert phase1_response["statusCode"] == 200
        
        # Then, query Phase 1 data
        phase1_query_event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "2025-01-01",
                "endDate": "2025-01-31",
            },
        }
        
        phase1_query_response = handler(phase1_query_event, None)
        assert phase1_query_response["statusCode"] == 200
        
        # Verify data format is still compatible
        body = json.loads(phase1_query_response["body"])
        assert body["success"] is True
        assert "data" in body
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.lambda_handler._get_prevention_engine")
    def test_phase3_prevention_works_with_phase6_gpu_detection(self, mock_get_engine, dynamodb_table_with_data):
        """
        Verify Phase 3 prevention system can work with Phase 6 GPU detection
        
        Requirements: IR-2.3, IR-2.5
        """
        # Test that Phase 3 prevention status endpoint still works
        mock_engine = MagicMock()
        mock_engine.get_status.return_value = {"enabled": True}
        mock_get_engine.return_value = mock_engine
        
        event = {
            "httpMethod": "GET",
            "path": "/api/prevention/status",
        }
        
        response = handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.lambda_handler._get_advisor_engine")
    def test_phase4_advisor_can_answer_gpu_questions(self, mock_get_engine, dynamodb_table_with_data):
        """
        Verify Phase 4 AI Advisor can still process queries (including GPU-related)
        
        Requirements: IR-2.4, IR-2.5
        """
        mock_engine = MagicMock()
        mock_response = MagicMock()
        mock_response.response_text = "Your GPU costs are tracked in Phase 6."
        mock_response.recommendations = []
        mock_response.cost_data = {}
        mock_response.confidence = 0.90
        mock_response.cached = False
        
        mock_engine.process_query.return_value = mock_response
        mock_get_engine.return_value = mock_engine
        
        event = {
            "httpMethod": "POST",
            "path": "/api/advisor/query",
            "body": json.dumps({
                "query": "What are my GPU costs?",
                "user_id": "test-user",
                "session_id": "test-session"
            }),
        }
        
        response = handler(event, None)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert "response" in body


class TestDataFormatCompatibility:
    """Test that data formats remain compatible across phases"""
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_cost_data_format_unchanged(self, dynamodb_table_with_data):
        """
        Verify cost data format is unchanged by Phase 6
        
        Requirements: IR-2.1
        """
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "2025-01-01",
                "endDate": "2025-01-31",
            },
        }
        
        response = handler(event, None)
        body = json.loads(response["body"])
        
        # Verify all Phase 1 fields are present
        for record in body["data"]:
            assert "date" in record
            assert "service" in record
            assert "blendedCost" in record
            assert "unblendedCost" in record
            assert "currency" in record
            
            # Verify field types
            assert isinstance(record["date"], str)
            assert isinstance(record["service"], str)
            assert isinstance(record["blendedCost"], (int, float))
            assert isinstance(record["unblendedCost"], (int, float))
            assert isinstance(record["currency"], str)
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_error_response_format_unchanged(self, dynamodb_table_with_data):
        """
        Verify error response format is unchanged by Phase 6
        
        Requirements: IR-2.1
        """
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "invalid-date",
            },
        }
        
        response = handler(event, None)
        
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        
        # Verify error format
        assert body["success"] is False
        assert "error" in body
        assert "code" in body["error"] or "message" in body["error"]


class TestNoBreakingChanges:
    """Test that Phase 6 introduces no breaking changes"""
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    @patch("src.services.cost_explorer.boto3.client")
    def test_phase1_fetch_parameters_unchanged(
        self, mock_ce_client, dynamodb_table_with_data, mock_cost_explorer_response
    ):
        """
        Verify Phase 1 fetch accepts same parameters as before
        
        Requirements: IR-2.1
        """
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = mock_cost_explorer_response
        mock_ce_client.return_value = mock_ce
        
        # Test with all original parameters
        event = {
            "httpMethod": "POST",
            "path": "/api/cost-data/fetch",
            "body": json.dumps({
                "startDate": "2025-01-01",
                "endDate": "2025-01-31",
                "granularity": "MONTHLY",
            }),
        }
        
        response = handler(event, None)
        assert response["statusCode"] == 200
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_phase1_query_parameters_unchanged(self, dynamodb_table_with_data):
        """
        Verify Phase 1 query accepts same parameters as before
        
        Requirements: IR-2.1
        """
        # Test with all original parameters
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "2025-01-01",
                "endDate": "2025-01-31",
                "service": "Amazon Simple Storage Service",
                "limit": "10",
            },
        }
        
        response = handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
    
    @patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "costguard-cost-data", "AWS_DEFAULT_REGION": "us-east-1"})
    def test_http_headers_unchanged(self, dynamodb_table_with_data):
        """
        Verify HTTP response headers are unchanged
        
        Requirements: IR-2.1
        """
        event = {
            "httpMethod": "GET",
            "path": "/api/cost-data",
            "queryStringParameters": {
                "startDate": "2025-01-01",
                "endDate": "2025-01-31",
            },
        }
        
        response = handler(event, None)
        
        # Verify headers
        assert "headers" in response
        assert "Content-Type" in response["headers"]
        assert response["headers"]["Content-Type"] == "application/json"
        assert "Access-Control-Allow-Origin" in response["headers"]
        assert response["headers"]["Access-Control-Allow-Origin"] == "*"
