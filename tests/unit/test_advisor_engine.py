"""
Unit tests for AdvisorEngine.
"""
import pytest
from datetime import datetime, UTC
from unittest.mock import Mock, MagicMock

from src.services.advisor_engine import AdvisorEngine
from src.utils.types import (
    QueryIntent, CostContext, ConversationTurn,
    AdvisorResponse, Recommendation, Insight
)


class TestAdvisorEngineInitialization:
    """Tests for AdvisorEngine initialization."""
    
    def test_advisor_engine_initialization(self):
        """Test AdvisorEngine initializes correctly."""
        query_processor = Mock()
        context_manager = Mock()
        bedrock_client = Mock()
        response_formatter = Mock()
        cache_manager = Mock()
        insight_generator = Mock()
        
        engine = AdvisorEngine(
            query_processor=query_processor,
            context_manager=context_manager,
            bedrock_client=bedrock_client,
            response_formatter=response_formatter,
            cache_manager=cache_manager,
            insight_generator=insight_generator
        )
        
        assert engine is not None
        assert engine.query_processor == query_processor
        assert engine.context_manager == context_manager
        assert engine.bedrock_client == bedrock_client
        assert engine.response_formatter == response_formatter
        assert engine.cache_manager == cache_manager
        assert engine.insight_generator == insight_generator


class TestQueryProcessing:
    """Tests for query processing workflow."""
    
    def test_process_query_cache_hit(self):
        """Test query processing with cache hit."""
        # Setup mocks
        query_processor = Mock()
        context_manager = Mock()
        bedrock_client = Mock()
        response_formatter = Mock()
        cache_manager = Mock()
        insight_generator = Mock()
        
        # Mock query parsing
        intent = QueryIntent(
            intent_type="cost_analysis",
            services=["ec2"],
            time_range=(datetime.now(UTC), datetime.now(UTC)),
            accounts=[],
            entities={}
        )
        query_processor.parse_query.return_value = intent
        
        # Mock cache hit
        cached_response = AdvisorResponse(
            response_text="Cached response",
            recommendations=[],
            cost_data={},
            confidence=0.9,
            cached=False
        )
        cache_manager.get_cached_response.return_value = cached_response
        
        engine = AdvisorEngine(
            query_processor=query_processor,
            context_manager=context_manager,
            bedrock_client=bedrock_client,
            response_formatter=response_formatter,
            cache_manager=cache_manager,
            insight_generator=insight_generator
        )
        
        result = engine.process_query("What are my EC2 costs?", "user123", "session456")
        
        assert result is not None
        assert result.cached is True
        assert result.response_text == "Cached response"
        
        # Bedrock should not be called on cache hit
        bedrock_client.invoke_advisor.assert_not_called()
    
    def test_process_query_cache_miss(self):
        """Test query processing with cache miss."""
        # Setup mocks
        query_processor = Mock()
        context_manager = Mock()
        bedrock_client = Mock()
        response_formatter = Mock()
        cache_manager = Mock()
        insight_generator = Mock()
        dynamodb_client = Mock()
        
        # Mock query parsing
        intent = QueryIntent(
            intent_type="cost_analysis",
            services=["ec2"],
            time_range=(datetime.now(UTC), datetime.now(UTC)),
            accounts=[],
            entities={}
        )
        query_processor.parse_query.return_value = intent
        
        # Mock cache miss
        cache_manager.get_cached_response.return_value = None
        
        # Mock context retrieval
        context = CostContext(
            historical_costs={"ec2": [{"blended_cost": 25.50}]},
            forecast_data=None,
            prevention_actions=[],
            current_budget=None,
            anomalies=[]
        )
        context_manager.get_cost_context.return_value = context
        
        # Mock Bedrock response
        bedrock_client.invoke_advisor.return_value = "Your EC2 costs are $25.50"
        
        # Mock response formatting
        formatted_response = AdvisorResponse(
            response_text="Your EC2 costs are **$25.50**",
            recommendations=[],
            cost_data={},
            confidence=0.8,
            cached=False
        )
        response_formatter.format_response.return_value = formatted_response
        
        # Mock DynamoDB for conversation history
        dynamodb_client.query.return_value = {"Items": []}
        dynamodb_client.put_item.return_value = {}
        
        engine = AdvisorEngine(
            query_processor=query_processor,
            context_manager=context_manager,
            bedrock_client=bedrock_client,
            response_formatter=response_formatter,
            cache_manager=cache_manager,
            insight_generator=insight_generator,
            dynamodb_client=dynamodb_client
        )
        
        result = engine.process_query("What are my EC2 costs?", "user123", "session456")
        
        assert result is not None
        assert result.cached is False
        assert "EC2" in result.response_text or "ec2" in result.response_text.lower()
        
        # Verify workflow
        query_processor.parse_query.assert_called_once()
        context_manager.get_cost_context.assert_called_once()
        bedrock_client.invoke_advisor.assert_called_once()
        response_formatter.format_response.assert_called_once()
        cache_manager.store_response.assert_called_once()
    
    def test_process_query_with_error(self):
        """Test query processing with error."""
        query_processor = Mock()
        context_manager = Mock()
        bedrock_client = Mock()
        response_formatter = Mock()
        cache_manager = Mock()
        insight_generator = Mock()
        
        # Mock error in query parsing
        query_processor.parse_query.side_effect = Exception("Parse error")
        
        engine = AdvisorEngine(
            query_processor=query_processor,
            context_manager=context_manager,
            bedrock_client=bedrock_client,
            response_formatter=response_formatter,
            cache_manager=cache_manager,
            insight_generator=insight_generator
        )
        
        result = engine.process_query("Invalid query", "user123", "session456")
        
        assert result is not None
        assert "error" in result.response_text.lower()
        assert result.confidence == 0.0


class TestConversationManagement:
    """Tests for conversation management."""
    
    def test_get_conversation_history_no_client(self):
        """Test getting conversation history without DynamoDB client."""
        query_processor = Mock()
        context_manager = Mock()
        bedrock_client = Mock()
        response_formatter = Mock()
        cache_manager = Mock()
        insight_generator = Mock()
        
        engine = AdvisorEngine(
            query_processor=query_processor,
            context_manager=context_manager,
            bedrock_client=bedrock_client,
            response_formatter=response_formatter,
            cache_manager=cache_manager,
            insight_generator=insight_generator
        )
        
        result = engine.get_conversation_history("session456")
        
        assert result == []
    
    def test_get_conversation_history_success(self):
        """Test successful conversation history retrieval."""
        query_processor = Mock()
        context_manager = Mock()
        bedrock_client = Mock()
        response_formatter = Mock()
        cache_manager = Mock()
        insight_generator = Mock()
        dynamodb_client = Mock()
        
        # Mock DynamoDB response
        now = datetime.now(UTC)
        dynamodb_client.query.return_value = {
            "Items": [
                {
                    "query": {"S": "What are my costs?"},
                    "response": {"S": "Your costs are $25.50"},
                    "timestamp_iso": {"S": now.isoformat()}
                }
            ]
        }
        
        engine = AdvisorEngine(
            query_processor=query_processor,
            context_manager=context_manager,
            bedrock_client=bedrock_client,
            response_formatter=response_formatter,
            cache_manager=cache_manager,
            insight_generator=insight_generator,
            dynamodb_client=dynamodb_client
        )
        
        result = engine.get_conversation_history("session456")
        
        assert len(result) == 1
        assert isinstance(result[0], ConversationTurn)
        assert result[0].query == "What are my costs?"
        assert result[0].response == "Your costs are $25.50"
    
    def test_clear_conversation_history_no_client(self):
        """Test clearing conversation history without DynamoDB client."""
        query_processor = Mock()
        context_manager = Mock()
        bedrock_client = Mock()
        response_formatter = Mock()
        cache_manager = Mock()
        insight_generator = Mock()
        
        engine = AdvisorEngine(
            query_processor=query_processor,
            context_manager=context_manager,
            bedrock_client=bedrock_client,
            response_formatter=response_formatter,
            cache_manager=cache_manager,
            insight_generator=insight_generator
        )
        
        # Should not raise error
        engine.clear_conversation_history("session456")
    
    def test_clear_conversation_history_success(self):
        """Test successful conversation history clearing."""
        query_processor = Mock()
        context_manager = Mock()
        bedrock_client = Mock()
        response_formatter = Mock()
        cache_manager = Mock()
        insight_generator = Mock()
        dynamodb_client = Mock()
        
        # Mock DynamoDB responses
        dynamodb_client.query.return_value = {
            "Items": [
                {
                    "session_id": {"S": "session456"},
                    "timestamp": {"N": "1234567890"}
                },
                {
                    "session_id": {"S": "session456"},
                    "timestamp": {"N": "1234567891"}
                }
            ]
        }
        
        engine = AdvisorEngine(
            query_processor=query_processor,
            context_manager=context_manager,
            bedrock_client=bedrock_client,
            response_formatter=response_formatter,
            cache_manager=cache_manager,
            insight_generator=insight_generator,
            dynamodb_client=dynamodb_client
        )
        
        engine.clear_conversation_history("session456")
        
        # Should delete both items
        assert dynamodb_client.delete_item.call_count == 2


class TestProactiveInsights:
    """Tests for proactive insight generation."""
    
    def test_generate_proactive_insights(self):
        """Test proactive insight generation."""
        query_processor = Mock()
        context_manager = Mock()
        bedrock_client = Mock()
        response_formatter = Mock()
        cache_manager = Mock()
        insight_generator = Mock()
        
        # Mock insight generation
        daily_summary = Insight(
            insight_type="summary",
            title="Daily Summary",
            description="Yesterday's costs were $25.50",
            severity="info",
            action_required=False,
            related_services=[],
            estimated_impact=25.50
        )
        
        anomaly = Insight(
            insight_type="anomaly",
            title="Cost Spike",
            description="EC2 costs spiked by 50%",
            severity="warning",
            action_required=True,
            related_services=["ec2"],
            estimated_impact=10.00
        )
        
        insight_generator.generate_daily_summary.return_value = daily_summary
        insight_generator.detect_anomalies.return_value = [anomaly]
        insight_generator.suggest_optimizations.return_value = []
        insight_generator.check_forecast_alerts.return_value = []
        
        engine = AdvisorEngine(
            query_processor=query_processor,
            context_manager=context_manager,
            bedrock_client=bedrock_client,
            response_formatter=response_formatter,
            cache_manager=cache_manager,
            insight_generator=insight_generator
        )
        
        result = engine.generate_proactive_insights("user123")
        
        assert len(result) == 2
        assert result[0].insight_type == "summary"
        assert result[1].insight_type == "anomaly"
    
    def test_generate_proactive_insights_with_error(self):
        """Test proactive insight generation with error."""
        query_processor = Mock()
        context_manager = Mock()
        bedrock_client = Mock()
        response_formatter = Mock()
        cache_manager = Mock()
        insight_generator = Mock()
        
        # Mock error
        insight_generator.generate_daily_summary.side_effect = Exception("Error")
        
        engine = AdvisorEngine(
            query_processor=query_processor,
            context_manager=context_manager,
            bedrock_client=bedrock_client,
            response_formatter=response_formatter,
            cache_manager=cache_manager,
            insight_generator=insight_generator
        )
        
        result = engine.generate_proactive_insights("user123")
        
        assert result == []


class TestCacheKeyGeneration:
    """Tests for cache key generation."""
    
    def test_generate_cache_key_consistent(self):
        """Test cache key generation is consistent."""
        query_processor = Mock()
        context_manager = Mock()
        bedrock_client = Mock()
        response_formatter = Mock()
        cache_manager = Mock()
        insight_generator = Mock()
        
        engine = AdvisorEngine(
            query_processor=query_processor,
            context_manager=context_manager,
            bedrock_client=bedrock_client,
            response_formatter=response_formatter,
            cache_manager=cache_manager,
            insight_generator=insight_generator
        )
        
        intent = QueryIntent(
            intent_type="cost_analysis",
            services=["ec2", "s3"],
            time_range=(datetime(2026, 2, 1, tzinfo=UTC), datetime(2026, 2, 28, tzinfo=UTC)),
            accounts=[],
            entities={}
        )
        
        key1 = engine._generate_cache_key("What are my costs?", intent)
        key2 = engine._generate_cache_key("What are my costs?", intent)
        
        assert key1 == key2
    
    def test_generate_cache_key_different_queries(self):
        """Test cache key generation for different queries."""
        query_processor = Mock()
        context_manager = Mock()
        bedrock_client = Mock()
        response_formatter = Mock()
        cache_manager = Mock()
        insight_generator = Mock()
        
        engine = AdvisorEngine(
            query_processor=query_processor,
            context_manager=context_manager,
            bedrock_client=bedrock_client,
            response_formatter=response_formatter,
            cache_manager=cache_manager,
            insight_generator=insight_generator
        )
        
        intent = QueryIntent(
            intent_type="cost_analysis",
            services=["ec2"],
            time_range=(datetime(2026, 2, 1, tzinfo=UTC), datetime(2026, 2, 28, tzinfo=UTC)),
            accounts=[],
            entities={}
        )
        
        key1 = engine._generate_cache_key("What are my EC2 costs?", intent)
        key2 = engine._generate_cache_key("What are my S3 costs?", intent)
        
        assert key1 != key2


class TestAdvisorEngineIntegration:
    """Integration tests for AdvisorEngine."""
    
    def test_complete_query_workflow(self):
        """Test complete query processing workflow."""
        # Setup all mocks
        query_processor = Mock()
        context_manager = Mock()
        bedrock_client = Mock()
        response_formatter = Mock()
        cache_manager = Mock()
        insight_generator = Mock()
        dynamodb_client = Mock()
        
        # Configure mocks for complete workflow
        intent = QueryIntent(
            intent_type="cost_analysis",
            services=["ec2"],
            time_range=(datetime.now(UTC), datetime.now(UTC)),
            accounts=[],
            entities={}
        )
        query_processor.parse_query.return_value = intent
        
        cache_manager.get_cached_response.return_value = None
        
        context = CostContext(
            historical_costs={"ec2": [{"blended_cost": 25.50}]},
            forecast_data=None,
            prevention_actions=[],
            current_budget=None,
            anomalies=[]
        )
        context_manager.get_cost_context.return_value = context
        
        dynamodb_client.query.return_value = {"Items": []}
        dynamodb_client.put_item.return_value = {}
        
        bedrock_client.invoke_advisor.return_value = "Your EC2 costs are $25.50"
        
        formatted_response = AdvisorResponse(
            response_text="Your EC2 costs are **$25.50**",
            recommendations=[],
            cost_data={},
            confidence=0.8,
            cached=False
        )
        response_formatter.format_response.return_value = formatted_response
        
        engine = AdvisorEngine(
            query_processor=query_processor,
            context_manager=context_manager,
            bedrock_client=bedrock_client,
            response_formatter=response_formatter,
            cache_manager=cache_manager,
            insight_generator=insight_generator,
            dynamodb_client=dynamodb_client
        )
        
        # Execute workflow
        result = engine.process_query("What are my EC2 costs?", "user123", "session456")
        
        # Verify all steps executed
        assert result is not None
        assert result.cached is False
        query_processor.parse_query.assert_called_once()
        cache_manager.get_cached_response.assert_called_once()
        context_manager.get_cost_context.assert_called_once()
        bedrock_client.invoke_advisor.assert_called_once()
        response_formatter.format_response.assert_called_once()
        cache_manager.store_response.assert_called_once()
        dynamodb_client.put_item.assert_called_once()
