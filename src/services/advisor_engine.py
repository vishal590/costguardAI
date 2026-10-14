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
            
            # Conversation state is part of cache identity: context changes must
            # not reuse an answer generated before a new turn or history deletion.
            import hashlib
            import json
            revision = self._session_revision(session_id)
            conversation_history = self._get_conversation_history(session_id, revision)
            history_fingerprint = hashlib.sha256((revision + json.dumps([
                {'query': turn.query, 'response': turn.response, 'timestamp': turn.timestamp.isoformat()}
                for turn in conversation_history], sort_keys=True)).encode()).hexdigest()
            # Step 2: Check owner/session/conversation-state cache.
            cache_key = hashlib.sha256(json.dumps(["advisor-context-v4-evidence-metadata", user_id, session_id, revision, history_fingerprint, self._generate_cache_key(query, intent)]).encode()).hexdigest()
            cached_response = self.cache_manager.get_cached_response(cache_key)
            
            if cached_response:
                logger.info("Returning cached response")
                cached_response.cached = True
                self._store_conversation_turn(session_id, query, cached_response.response_text, None, revision)
                return cached_response
            
            # Step 3: Retrieve context
            context = self.context_manager.get_cost_context(intent)
            logger.debug(f"Retrieved context with {len(context.historical_costs)} services")
            
            # Step 4: Use the same conversation snapshot as cache identity
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
            formatted_response.cost_data["data_quality"] = context.data_quality
            
            # Persist the turn before exposing a cache entry.
            # Step 7: Store conversation turn
            self._store_conversation_turn(
                session_id=session_id,
                query=query,
                response=formatted_response.response_text,
                context=context, revision=revision
            )
            
            self.cache_manager.store_response(cache_key, formatted_response)
            logger.info("Query processed successfully")
            return formatted_response
            
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            err_str = str(e).lower()
            if "throttl" in err_str or "too many tokens" in err_str or "rate" in err_str and "limit" in err_str:
                response_text = (
                    "I’m temporarily limited by my daily usage quota, so I can’t answer right now. "
                    "You can try again later (quotas reset daily), or your administrator can request a higher "
                    "Bedrock quota in AWS Service Quotas (Amazon Bedrock → On-demand inference tokens per day)."
                )
            else:
                response_text = "The advisor could not complete this request. Please try again later."
            return AdvisorResponse(
                response_text=response_text,
                recommendations=[],
                cost_data={},
                confidence=None,
                cached=False, status="unavailable"
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
            raise RuntimeError("Conversation storage is unavailable")
        
        try:
            table_name = "advisor-conversation-history"
            
            self._session_revision(session_id)  # Initialize/refresh a live generation before incrementing.
            state = self.dynamodb_client.update_item(TableName=table_name,
                Key={'session_id': {'S': session_id}, 'timestamp': {'N': '0'}},
                UpdateExpression='SET record_kind = :kind, #ttl = :ttl ADD #revision :one',
                ExpressionAttributeNames={'#ttl': 'ttl', '#revision': 'revision'}, ReturnValues='ALL_NEW',
                ExpressionAttributeValues={':kind': {'S': 'session_state'}, ':ttl': {'N': str(int(datetime.now().timestamp())+90*86400)}, ':one': {'N': '1'}})
            current_revision = int(state['Attributes']['revision']['N'])
            request = {'TableName': table_name, 'KeyConditionExpression': 'session_id = :sid',
                       'ExpressionAttributeValues': {':sid': {'S': session_id}}}
            while True:
                response = self.dynamodb_client.query(**request)
                for item in response.get('Items', []):
                    if item.get('record_kind', {}).get('S') == 'session_state' or int(item.get('revision', {}).get('N', '0')) >= current_revision: continue
                    self.dynamodb_client.delete_item(TableName=table_name,
                        Key={'session_id': {'S': session_id}, 'timestamp': item['timestamp']})
                if not response.get('LastEvaluatedKey'): break
                request['ExclusiveStartKey'] = response['LastEvaluatedKey']

            logger.info(f"Cleared conversation history for session {session_id}")
            
        except Exception as e:
            logger.error("Conversation deletion failed: %s", type(e).__name__)
            raise
    
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
    
    def _get_conversation_history(self, session_id: str, revision=None) -> List[ConversationTurn]:
        """Read the latest ten unexpired turns, traversing filtered pages."""
        if not self.dynamodb_client: raise RuntimeError('Conversation storage is unavailable')
        revision = self._session_revision(session_id) if revision is None else revision
        request = {
            'TableName': 'advisor-conversation-history',
            'KeyConditionExpression': 'session_id = :sid AND #time > :zero',
            'ExpressionAttributeNames': {'#time': 'timestamp', '#revision': 'revision', '#expiry': 'ttl'},
            'FilterExpression': '#expiry > :now AND (' + ('attribute_not_exists(#revision) OR #revision = :revision' if revision == '0' else '#revision = :revision') + ')',
            'ExpressionAttributeValues': {':sid': {'S': session_id}, ':zero': {'N': '0'},
                ':revision': {'N': revision}, ':now': {'N': str(int(datetime.now(UTC).timestamp()))}},
            'ScanIndexForward': False, 'Limit': 10, 'ConsistentRead': True
        }
        turns = []
        while True:
            response = self.dynamodb_client.query(**request)
            for item in response.get('Items', []):
                if item.get('record_kind', {}).get('S') == 'session_state': continue
                turns.append(ConversationTurn(query=item.get('query', {}).get('S', ''),
                    response=item.get('response', {}).get('S', ''),
                    timestamp=datetime.fromisoformat(item['timestamp_iso']['S']), context_used=None))
            cursor = response.get('LastEvaluatedKey')
            if len(turns) >= 10 or not cursor: break
            request['ExclusiveStartKey'] = cursor
        return list(reversed(turns[:10]))

    def _store_conversation_turn(
        self,
        session_id: str,
        query: str,
        response: str,
        context: CostContext,
        revision=None
    ) -> None:
        """Store conversation turn in DynamoDB."""
        if not self.dynamodb_client:
            raise RuntimeError("Conversation storage is unavailable")
        
        try:
            table_name = "advisor-conversation-history"
            timestamp = datetime.now(UTC)
            
            item = {
                "session_id": {"S": session_id},
                "timestamp": {"N": str(timestamp.timestamp())},
                "timestamp_iso": {"S": timestamp.isoformat()},
                "query": {"S": query},
                "response": {"S": response},
                "ttl": {"N": str(int((timestamp.timestamp()) + 86400))}  # 24 hour TTL
            }
            
            revision = self._session_revision(session_id) if revision is None else revision
            item['revision'] = {'N': revision}
            self.dynamodb_client.transact_write_items(TransactItems=[
                {'ConditionCheck': {'TableName': table_name,
                    'Key': {'session_id': {'S': session_id}, 'timestamp': {'N': '0'}},
                    'ConditionExpression': '#revision = :revision AND #expiry > :now AND record_kind = :kind',
                    'ExpressionAttributeNames': {'#revision': 'revision', '#expiry': 'ttl'},
                    'ExpressionAttributeValues': {':revision': {'N': revision}, ':now': {'N': str(int(timestamp.timestamp()))}, ':kind': {'S': 'session_state'}}}},
                {'Put': {'TableName': table_name, 'Item': item, 'ConditionExpression': 'attribute_not_exists(session_id)'}}])

            logger.debug(f"Stored conversation turn for session {session_id}")
            
        except Exception as e:
            logger.error("Conversation history persistence failed: %s", type(e).__name__)
            raise

    def _session_revision(self, session_id):
        """Initialize and renew a generation; expired state never reuses an old revision."""
        if not self.dynamodb_client: raise RuntimeError('Conversation storage is unavailable')
        import time
        from botocore.exceptions import ClientError
        key = {'session_id': {'S': session_id}, 'timestamp': {'N': '0'}}
        for _ in range(3):
            now = int(datetime.now(UTC).timestamp())
            state = self.dynamodb_client.get_item(TableName='advisor-conversation-history', Key=key, ConsistentRead=True).get('Item')
            try:
                if not state:
                    revision = str(time.time_ns())
                    self.dynamodb_client.put_item(TableName='advisor-conversation-history',
                        Item={**key, 'record_kind': {'S': 'session_state'}, 'revision': {'N': revision}, 'ttl': {'N': str(now+90*86400)}},
                        ConditionExpression='attribute_not_exists(session_id)')
                else:
                    observed = state['revision']['N']
                    expiry = int(state.get('ttl', {}).get('N', '0'))
                    revision = observed if expiry > now else str(max(int(observed)+1, time.time_ns()))
                    self.dynamodb_client.update_item(TableName='advisor-conversation-history', Key=key,
                        UpdateExpression='SET #revision = :new, #expiry = :expiry',
                        ConditionExpression='#revision = :observed AND record_kind = :kind',
                        ExpressionAttributeNames={'#revision': 'revision', '#expiry': 'ttl'},
                        ExpressionAttributeValues={':new': {'N': revision}, ':observed': {'N': observed},
                            ':kind': {'S': 'session_state'}, ':expiry': {'N': str(now+90*86400)}})
                return revision
            except ClientError as error:
                if error.response.get('Error', {}).get('Code') != 'ConditionalCheckFailedException': raise
        raise RuntimeError('Conversation changed concurrently; retry the request')
