"""
AI Advisor Engine for conversational cost analysis.

This module orchestrates the AI advisor functionality by:
1. Processing natural language queries
2. Managing conversation context
3. Coordinating data retrieval and AI invocation
4. Generating proactive insights
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, UTC
import logging
from dataclasses import asdict

from ..utils.types import (
    QueryIntent, CostContext, ConversationTurn,
    AdvisorResponse, Recommendation, Insight
)

logger = logging.getLogger(__name__)


class AdvisorEngine:
    """Main orchestrator for AI advisor functionality."""
    
    def __init__(
        self,
        query_processor,
        context_manager,
        bedrock_client,
        response_formatter,
        cache_manager,
        insight_generator,
        dynamodb_client=None
    ):
        """
        Initialize advisor engine with all components.
        
        Args:
            query_processor: QueryProcessor instance
            context_manager: ContextManager instance
            bedrock_client: BedrockAdvisorClient instance
            response_formatter: ResponseFormatter instance
            cache_manager: AdvisorCacheManager instance
            insight_generator: InsightGenerator instance
            dynamodb_client: DynamoDB client for conversation history
        """
        self.query_processor = query_processor
        self.context_manager = context_manager
        self.bedrock_client = bedrock_client
        self.response_formatter = response_formatter
        self.cache_manager = cache_manager
        self.insight_generator = insight_generator
        self.dynamodb_client = dynamodb_client
        
        logger.info("AdvisorEngine initialized")
    
    def process_query(
        self,
        query: str,
        user_id: str,
        session_id: str
    ) -> AdvisorResponse:
        """
        Process a natural language query and return AI-generated response.
        
        Args:
            query: Natural language query from user
            user_id: User identifier
            session_id: Conversation session identifier
            
        Returns:
            AdvisorResponse with formatted response and recommendations
        """
        logger.info(f"Processing query for user {user_id}, session {session_id}")
        
        try:
            # Step 1: Parse query to extract intent
            intent = self.query_processor.parse_query(query)
            logger.debug(f"Query intent: {intent.intent_type}")
            
            # Step 2: Check cache
            cache_key = self._generate_cache_key(query, intent)
            cached_response = self.cache_manager.get_cached_response(cache_key)
            
            if cached_response:
                logger.info("Returning cached response")
                cached_response.cached = True
                return cached_response
            
            # Step 3: Retrieve context
            context = self.context_manager.get_cost_context(intent)
            logger.debug(f"Retrieved context with {len(context.historical_costs)} services")
            
            # Step 4: Get conversation history
            conversation_history = self._get_conversation_history(session_id)
            logger.debug(f"Retrieved {len(conversation_history)} conversation turns")
            
            # Step 5: Invoke Bedrock
            raw_response = self.bedrock_client.invoke_advisor(
                query=query,
                context=context,
                conversation_history=conversation_history
            )
            
            # Step 6: Format response
            formatted_response = self.response_formatter.format_response(
                raw_response=raw_response,
                context=context
            )
            formatted_response.cached = False
            
            # Step 7: Store in cache
            self.cache_manager.store_response(cache_key, formatted_response)
            
            # Step 8: Store conversation turn
            self._store_conversation_turn(
                session_id=session_id,
                query=query,
                response=formatted_response.response_text,
                context=context
            )
            
            logger.info("Query processed successfully")
            return formatted_response
            
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            # Return error response
            return AdvisorResponse(
                response_text=f"I apologize, but I encountered an error processing your query: {str(e)}",
                recommendations=[],
                cost_data={},
                confidence=0.0,
                cached=False
            )
    
    def get_conversation_history(self, session_id: str) -> List[ConversationTurn]:
        """
        Retrieve conversation history for a session.
        
        Args:
            session_id: Conversation session identifier
            
        Returns:
            List of conversation turns
        """
        return self._get_conversation_history(session_id)
    
    def clear_conversation_history(self, session_id: str) -> None:
        """
        Clear conversation history for a session.
        
        Args:
            session_id: Conversation session identifier
        """
        if not self.dynamodb_client:
            logger.warning("No DynamoDB client, cannot clear history")
            return
        
        try:
            table_name = "advisor-conversation-history"
            
            # Query all items for this session
            response = self.dynamodb_client.query(
                TableName=table_name,
                KeyConditionExpression="session_id = :sid",
                ExpressionAttributeValues={
                    ":sid": {"S": session_id}
                }
            )
            
            # Delete each item
            for item in response.get("Items", []):
                self.dynamodb_client.delete_item(
                    TableName=table_name,
                    Key={
                        "session_id": {"S": session_id},
                        "timestamp": item["timestamp"]
                    }
                )
            
            logger.info(f"Cleared conversation history for session {session_id}")
            
        except Exception as e:
            logger.error(f"Error clearing conversation history: {e}")
    
    def generate_proactive_insights(self, user_id: str) -> List[Insight]:
        """
        Generate proactive cost insights for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of insights
        """
        logger.info(f"Generating proactive insights for user {user_id}")
        
        try:
            insights = []
            
            # Generate daily summary
            daily_summary = self.insight_generator.generate_daily_summary(user_id)
            if daily_summary:
                insights.append(daily_summary)
            
            # Detect anomalies
            anomalies = self.insight_generator.detect_anomalies(user_id)
            insights.extend(anomalies)
            
            # Suggest optimizations
            optimizations = self.insight_generator.suggest_optimizations(user_id)
            insights.extend(optimizations)
            
            # Check forecast alerts
            forecast_alerts = self.insight_generator.check_forecast_alerts(user_id)
            insights.extend(forecast_alerts)
            
            logger.info(f"Generated {len(insights)} insights")
            return insights
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}", exc_info=True)
            return []
    
    def _generate_cache_key(self, query: str, intent: QueryIntent) -> str:
        """Generate cache key from query and intent."""
        import hashlib
        
        # Create a string representation of the query intent
        key_parts = [
            query.lower().strip(),
            intent.intent_type,
            ",".join(sorted(intent.services)),
            intent.time_range[0].isoformat() if intent.time_range else "",
            intent.time_range[1].isoformat() if intent.time_range else ""
        ]
        
        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    def _get_conversation_history(self, session_id: str) -> List[ConversationTurn]:
        """Retrieve conversation history from DynamoDB."""
        if not self.dynamodb_client:
            logger.warning("No DynamoDB client, returning empty history")
            return []
        
        try:
            table_name = "advisor-conversation-history"
            
            response = self.dynamodb_client.query(
                TableName=table_name,
                KeyConditionExpression="session_id = :sid",
                ExpressionAttributeValues={
                    ":sid": {"S": session_id}
                },
                Limit=10,  # Last 10 turns
                ScanIndexForward=False  # Most recent first
            )
            
            turns = []
            for item in response.get("Items", []):
                turn = ConversationTurn(
                    query=item.get("query", {}).get("S", ""),
                    response=item.get("response", {}).get("S", ""),
                    timestamp=datetime.fromisoformat(item.get("timestamp_iso", {}).get("S", "")),
                    context_used=None  # Don't load full context for history
                )
                turns.append(turn)
            
            # Reverse to get chronological order
            turns.reverse()
            
            return turns
            
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}")
            return []
    
    def _store_conversation_turn(
        self,
        session_id: str,
        query: str,
        response: str,
        context: CostContext
    ) -> None:
        """Store conversation turn in DynamoDB."""
        if not self.dynamodb_client:
            logger.warning("No DynamoDB client, cannot store conversation")
            return
        
        try:
            table_name = "advisor-conversation-history"
            timestamp = datetime.now(UTC)
            
            item = {
                "session_id": {"S": session_id},
                "timestamp": {"N": str(int(timestamp.timestamp()))},
                "timestamp_iso": {"S": timestamp.isoformat()},
                "query": {"S": query},
                "response": {"S": response},
                "ttl": {"N": str(int((timestamp.timestamp()) + 86400))}  # 24 hour TTL
            }
            
            self.dynamodb_client.put_item(
                TableName=table_name,
                Item=item
            )
            
            logger.debug(f"Stored conversation turn for session {session_id}")
            
        except Exception as e:
            logger.error(f"Error storing conversation turn: {e}")
