"""
Bedrock Advisor Client for AI-powered cost analysis.

This module interfaces with Amazon Bedrock Nova Lite to:
1. Construct prompts with query + context + history
2. Invoke Bedrock API
3. Parse AI responses
4. Handle retries and errors
"""

from typing import List, Callable, Any, Optional
import json
import time
import logging

from ..utils.types import CostContext, ConversationTurn, AdvisorResponse, Recommendation

logger = logging.getLogger(__name__)


class BedrockAdvisorClient:
    """Interface with Amazon Bedrock for AI responses."""
    
    def __init__(
        self,
        bedrock_client=None,
        model_id: str = "amazon.nova-lite-v1:0",
        max_retries: int = 3
    ):
        """
        Initialize Bedrock client.
        
        Args:
            bedrock_client: AWS Bedrock Runtime client
            model_id: Bedrock model identifier
            max_retries: Maximum retry attempts
        """
        self.bedrock_client = bedrock_client
        self.model_id = model_id
        self.max_retries = max_retries
        
        logger.info(f"BedrockAdvisorClient initialized with model {model_id}")
    
    def invoke_advisor(
        self,
        query: str,
        context: CostContext,
        conversation_history: List[ConversationTurn]
    ) -> str:
        """
        Invoke Bedrock Nova Lite with query and context.
        
        Args:
            query: User's natural language query
            context: Cost data context
            conversation_history: Previous conversation turns
            
        Returns:
            AI-generated response text
        """
        logger.info("Invoking Bedrock advisor")
        
        # Build prompt
        prompt = self.build_prompt(query, context, conversation_history)
        
        # Invoke Bedrock with retry
        response = self.retry_with_backoff(
            lambda: self._invoke_bedrock(prompt)
        )
        
        return response
    
    def build_prompt(
        self,
        query: str,
        context: CostContext,
        history: List[ConversationTurn]
    ) -> str:
        """
        Construct prompt for Bedrock.
        
        Args:
            query: User's query
            context: Cost data context
            history: Conversation history
            
        Returns:
            Formatted prompt string
        """
        prompt_parts = []
        
        # System instruction
        prompt_parts.append(
            "You are an AWS cost optimization advisor. Analyze the provided cost data "
            "and answer the user's question with clear, actionable insights. "
            "Format your response in markdown with bullet points and tables where appropriate."
        )
        
        # Add conversation history
        if history:
            prompt_parts.append("\n## Previous Conversation:")
            for turn in history[-3:]:  # Last 3 turns
                prompt_parts.append(f"\nUser: {turn.query}")
                prompt_parts.append(f"Assistant: {turn.response[:200]}...")  # Truncate
        
        # Add cost context
        prompt_parts.append("\n## Cost Data:")
        
        # Historical costs
        if context.historical_costs:
            prompt_parts.append("\n### Historical Costs:")
            for service, costs in list(context.historical_costs.items())[:5]:  # Limit to 5 services
                total_cost = sum(c.get('blended_cost', 0) for c in costs)
                prompt_parts.append(f"- {service}: ${total_cost:.2f}")
        
        # Forecast data
        if context.forecast_data:
            prompt_parts.append("\n### Forecast Data:")
            for service, forecasts in list(context.forecast_data.items())[:3]:
                if forecasts:
                    avg_forecast = sum(f.get('predicted_cost', 0) for f in forecasts) / len(forecasts)
                    prompt_parts.append(f"- {service}: ${avg_forecast:.2f}/day (predicted)")
        
        # Prevention actions
        if context.prevention_actions:
            total_savings = sum(a.get('estimated_savings', 0) for a in context.prevention_actions)
            prompt_parts.append(f"\n### Prevention Actions: {len(context.prevention_actions)} actions, ${total_savings:.2f} saved")
        
        # Budget status
        if context.current_budget:
            budget = context.current_budget
            prompt_parts.append(
                f"\n### Budget: ${budget.actual_spend:.2f} / ${budget.limit:.2f} "
                f"({budget.utilization_percent:.1f}% used)"
            )
        
        # User query
        prompt_parts.append(f"\n## User Question:\n{query}")
        
        # Response instruction
        prompt_parts.append(
            "\n## Instructions:\n"
            "Provide a clear, concise answer (max 500 words). "
            "Use markdown formatting. Highlight important numbers. "
            "If recommending actions, explain why and estimate savings."
        )
        
        prompt = "\n".join(prompt_parts)
        
        # Ensure prompt is under 1000 tokens (~4000 characters)
        if len(prompt) > 4000:
            prompt = prompt[:4000] + "\n[Context truncated for length]"
        
        logger.debug(f"Built prompt with {len(prompt)} characters")
        return prompt
    
    def parse_response(self, response: str) -> AdvisorResponse:
        """
        Parse Bedrock response and extract structured data.
        
        Args:
            response: Raw response from Bedrock
            
        Returns:
            Structured AdvisorResponse
        """
        # Extract recommendations (basic pattern matching)
        recommendations = self._extract_recommendations(response)
        
        # Extract cost data (basic pattern matching)
        cost_data = self._extract_cost_data(response)
        
        # Estimate confidence (placeholder)
        confidence = 0.8
        
        return AdvisorResponse(
            response_text=response,
            recommendations=recommendations,
            cost_data=cost_data,
            confidence=confidence,
            cached=False
        )
    
    def retry_with_backoff(
        self,
        func: Callable,
        max_retries: Optional[int] = None
    ) -> Any:
        """
        Retry Bedrock calls with exponential backoff.
        
        Args:
            func: Function to retry
            max_retries: Maximum retry attempts (uses self.max_retries if None)
            
        Returns:
            Function result
            
        Raises:
            Exception: If all retries fail
        """
        max_retries = max_retries or self.max_retries
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                
                # Check if retryable
                if not self._is_retryable_error(e):
                    raise
                
                if attempt < max_retries - 1:
                    delay = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(f"Bedrock call failed, retrying in {delay}s: {e}")
                    time.sleep(delay)
        
        # All retries failed
        logger.error(f"All {max_retries} retries failed")
        raise last_exception
    
    def _invoke_bedrock(self, prompt: str) -> str:
        """
        Invoke Bedrock API.
        
        Args:
            prompt: Formatted prompt
            
        Returns:
            AI response text
        """
        if not self.bedrock_client:
            logger.warning("No Bedrock client, returning mock response")
            return "I apologize, but I'm unable to access the AI service at this time."
        
        try:
            # Prepare request body
            request_body = {
                "prompt": prompt,
                "max_tokens": 1000,
                "temperature": 0.7,
                "top_p": 0.9
            }
            
            # Invoke model
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            
            # Extract text (format varies by model)
            if 'completion' in response_body:
                return response_body['completion']
            elif 'output' in response_body:
                return response_body['output']
            else:
                logger.error(f"Unexpected response format: {response_body.keys()}")
                return "I received an unexpected response format from the AI service."
            
        except Exception as e:
            logger.error(f"Bedrock invocation failed: {e}")
            raise
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Check if error is retryable.
        
        Args:
            error: Exception to check
            
        Returns:
            True if retryable
        """
        error_str = str(error).lower()
        
        # Retryable errors
        retryable_patterns = [
            'throttling',
            'rate limit',
            'service unavailable',
            'timeout',
            '503',
            '429'
        ]
        
        return any(pattern in error_str for pattern in retryable_patterns)
    
    def _extract_recommendations(self, response: str) -> List[Recommendation]:
        """
        Extract recommendations from response text.
        
        Args:
            response: AI response text
            
        Returns:
            List of Recommendation objects
        """
        recommendations = []
        
        # Look for recommendation patterns (basic implementation)
        lines = response.split('\n')
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Look for recommendation indicators
            if any(word in line_lower for word in ['recommend', 'suggest', 'should', 'consider']):
                # Extract action (simplified)
                action = line.strip('- *#').strip()
                
                # Look for savings estimate in nearby lines
                estimated_savings = 0.0
                for nearby_line in lines[max(0, i-2):min(len(lines), i+3)]:
                    if '$' in nearby_line:
                        # Extract dollar amount (simplified)
                        import re
                        amounts = re.findall(r'\$(\d+(?:\.\d+)?)', nearby_line)
                        if amounts:
                            estimated_savings = float(amounts[0])
                            break
                
                recommendations.append(Recommendation(
                    action=action,
                    rationale="Based on cost analysis",
                    estimated_savings=estimated_savings,
                    priority=3,  # Default priority
                    safe=True  # Assume safe unless specified
                ))
        
        return recommendations[:5]  # Limit to 5 recommendations
    
    def _extract_cost_data(self, response: str) -> dict:
        """
        Extract structured cost data from response.
        
        Args:
            response: AI response text
            
        Returns:
            Dictionary of cost data
        """
        import re
        
        cost_data = {}
        
        # Extract dollar amounts
        amounts = re.findall(r'\$(\d+(?:\.\d+)?)', response)
        if amounts:
            cost_data['mentioned_costs'] = [float(a) for a in amounts]
        
        # Extract percentages
        percentages = re.findall(r'(\d+(?:\.\d+)?)\s*%', response)
        if percentages:
            cost_data['mentioned_percentages'] = [float(p) for p in percentages]
        
        return cost_data
