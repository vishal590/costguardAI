"""
Bedrock Client for AI model interactions.

This module handles all Amazon Bedrock API interactions including:
1. Model invocation (Nova Lite/Micro)
2. Prompt building for time series forecasting
3. Response parsing
4. Retry logic with exponential backoff
"""

from typing import Dict, List, Optional
import boto3
import json
import time
from datetime import datetime, UTC, timedelta
from src.utils.types import (
    ProcessedData,
    BedrockResponse,
    ForecastDataPoint,
    BedrockAPIError,
    BedrockRateLimitError,
    BedrockInvalidResponseError
)


class BedrockClient:
    """Handles all Bedrock API interactions."""
    
    def __init__(self, model_id: str = "amazon.nova-lite-v1:0", region: str = "us-east-1"):
        """
        Initialize Bedrock runtime client.
        
        Args:
            model_id: Bedrock model ID (nova-lite or nova-micro)
            region: AWS region for Bedrock
        """
        self.client = boto3.client('bedrock-runtime', region_name=region)
        self.model_id = model_id
        
    def invoke_forecast(
        self,
        historical_data: ProcessedData,
        forecast_horizon: int,
        confidence_level: float = 0.95
    ) -> BedrockResponse:
        """
        Invoke Bedrock model for cost forecasting.
        
        Args:
            historical_data: Preprocessed historical cost data
            forecast_horizon: Number of days to forecast
            confidence_level: Confidence level for intervals (default 0.95)
            
        Returns:
            BedrockResponse with predictions and confidence intervals
            
        Raises:
            BedrockAPIError: API call failed
            BedrockRateLimitError: Rate limit exceeded
            BedrockInvalidResponseError: Invalid JSON response
        """
        # Build prompt
        prompt = self.build_prompt(historical_data, forecast_horizon, confidence_level)
        
        # Prepare request body
        request_body = {
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "inferenceConfig": {
                "maxTokens": 1024,  # Enough for 30-day forecast JSON; lower helps stay under API Gateway 29s
                "temperature": 0.1,  # Low temperature for consistent predictions
                "topP": 0.9
            }
        }
        
        # Invoke with retry logic
        start_time = time.time()
        response = self.retry_with_backoff(
            lambda: self._invoke_model(request_body),
            max_retries=3
        )
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Parse response
        forecast_data = self.parse_response(response, historical_data, forecast_horizon)
        
        return BedrockResponse(
            predictions=forecast_data['predictions'],
            confidence_lower=forecast_data['confidence_lower'],
            confidence_upper=forecast_data['confidence_upper'],
            dates=forecast_data['dates'],
            model_id=self.model_id,
            latency_ms=latency_ms
        )
    
    def _invoke_model(self, request_body: Dict) -> Dict:
        """
        Internal method to invoke Bedrock model.
        
        Args:
            request_body: Request payload for Bedrock
            
        Returns:
            Parsed response from Bedrock
            
        Raises:
            BedrockAPIError: API call failed
            BedrockRateLimitError: Rate limit exceeded
        """
        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(request_body)
            )
            
            # Parse response body
            response_body = json.loads(response['body'].read())
            return response_body
            
        except Exception as e:
            # Check exception type by name to handle boto3 exceptions
            exception_name = type(e).__name__
            
            if exception_name == 'ThrottlingException':
                raise BedrockRateLimitError(f"Bedrock rate limit exceeded: {str(e)}")
            elif exception_name == 'ModelTimeoutException':
                raise BedrockAPIError(f"Bedrock model timeout: {str(e)}")
            elif exception_name == 'ServiceUnavailableException':
                raise BedrockAPIError(f"Bedrock service unavailable: {str(e)}")
            else:
                raise BedrockAPIError(f"Bedrock API error: {str(e)}")
        
    def build_prompt(
        self,
        historical_data: ProcessedData,
        forecast_horizon: int,
        confidence_level: float = 0.95
    ) -> str:
        """
        Build prompt for time series forecasting.
        
        Args:
            historical_data: Preprocessed historical cost data
            forecast_horizon: Number of days to forecast
            confidence_level: Confidence level for intervals
            
        Returns:
            Formatted prompt string for Bedrock
        """
        # Format historical data as JSON
        data_points = [
            {"date": date, "cost": cost}
            for date, cost in zip(historical_data.timestamps, historical_data.costs)
        ]
        
        # Build prompt with clear instructions
        prompt = f"""You are a time series forecasting expert. Analyze the following historical AWS cost data and generate a {forecast_horizon}-day forecast.

Historical Cost Data ({historical_data.total_days} days):
{json.dumps(data_points, indent=2)}

Task:
1. Analyze the time series pattern (trend, seasonality, anomalies)
2. Generate predictions for the next {forecast_horizon} days
3. Calculate {int(confidence_level * 100)}% confidence intervals (upper and lower bounds)

Requirements:
- All predicted costs must be non-negative
- Confidence intervals must be realistic (lower ≤ prediction ≤ upper)
- Consider weekly patterns (weekday vs weekend usage)
- Account for any visible trends in the data

Output Format (JSON only, no explanation):
{{
  "forecasts": [
    {{
      "date": "YYYY-MM-DD",
      "predicted_cost": <float>,
      "confidence_lower": <float>,
      "confidence_upper": <float>
    }},
    ...
  ]
}}

Generate the forecast now:"""
        
        return prompt
        
    def parse_response(
        self,
        response: Dict,
        historical_data: ProcessedData,
        forecast_horizon: int
    ) -> Dict[str, List]:
        """
        Parse Bedrock JSON response into forecast data points.
        
        Args:
            response: Raw response from Bedrock
            historical_data: Original historical data (for date calculation)
            forecast_horizon: Number of days forecasted
            
        Returns:
            Dict with predictions, confidence_lower, confidence_upper, dates
            
        Raises:
            BedrockInvalidResponseError: Invalid JSON response
        """
        try:
            # Extract content from response
            if 'content' in response and len(response['content']) > 0:
                content = response['content'][0]
                if 'text' in content:
                    text = content['text']
                else:
                    raise BedrockInvalidResponseError("No text in response content")
            else:
                raise BedrockInvalidResponseError("No content in response")
            
            # Parse JSON from text
            # Handle potential markdown code blocks
            text = text.strip()
            if text.startswith('```json'):
                text = text[7:]
            if text.startswith('```'):
                text = text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()
            
            forecast_data = json.loads(text)
            
            # Validate structure
            if 'forecasts' not in forecast_data:
                raise BedrockInvalidResponseError("Missing 'forecasts' key in response")
            
            forecasts = forecast_data['forecasts']
            
            if len(forecasts) != forecast_horizon:
                # If Bedrock returned different number, adjust or raise error
                # For now, we'll take what we got and pad/truncate if needed
                pass
            
            # Extract data
            predictions = []
            confidence_lower = []
            confidence_upper = []
            dates = []
            
            # Calculate forecast start date (day after last historical date)
            last_date = datetime.fromisoformat(historical_data.timestamps[-1]).date()
            
            for i, forecast in enumerate(forecasts[:forecast_horizon]):
                # Calculate date
                forecast_date = last_date + timedelta(days=i + 1)
                dates.append(forecast_date.isoformat())
                
                # Extract values with validation
                pred = float(forecast.get('predicted_cost', 0))
                # Fallback: If Bedrock doesn't provide confidence intervals, use ±20% ranges
                # Note: This is NOT a true 95% confidence interval, just a simple range
                lower = float(forecast.get('confidence_lower', pred * 0.8))
                upper = float(forecast.get('confidence_upper', pred * 1.2))
                
                # Ensure non-negative
                pred = max(0, pred)
                lower = max(0, lower)
                upper = max(0, upper)
                
                # Ensure proper ordering
                if lower > pred:
                    lower = pred * 0.9
                if upper < pred:
                    upper = pred * 1.1
                
                predictions.append(pred)
                confidence_lower.append(lower)
                confidence_upper.append(upper)
            
            # If we got fewer forecasts than requested, pad with last value
            while len(predictions) < forecast_horizon:
                last_date = datetime.fromisoformat(dates[-1]).date()
                next_date = last_date + timedelta(days=1)
                dates.append(next_date.isoformat())
                predictions.append(predictions[-1] if predictions else 0)
                confidence_lower.append(confidence_lower[-1] if confidence_lower else 0)
                confidence_upper.append(confidence_upper[-1] if confidence_upper else 0)
            
            return {
                'predictions': predictions,
                'confidence_lower': confidence_lower,
                'confidence_upper': confidence_upper,
                'dates': dates
            }
            
        except json.JSONDecodeError as e:
            raise BedrockInvalidResponseError(f"Invalid JSON in Bedrock response: {str(e)}")
        except KeyError as e:
            raise BedrockInvalidResponseError(f"Missing required field in response: {str(e)}")
        except Exception as e:
            raise BedrockInvalidResponseError(f"Error parsing Bedrock response: {str(e)}")
        
    def retry_with_backoff(self, func, max_retries: int = 3):
        """
        Retry function with exponential backoff.
        
        Args:
            func: Function to retry
            max_retries: Maximum number of retries
            
        Returns:
            Result from successful function call
            
        Raises:
            BedrockRateLimitError: Rate limit exceeded after all retries
            BedrockAPIError: API error after all retries
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return func()
            except BedrockRateLimitError as e:
                last_exception = e
                if attempt < max_retries:
                    # Exponential backoff: 1s, 2s, 4s
                    delay = 2 ** attempt
                    time.sleep(delay)
                    continue
                else:
                    raise
            except BedrockAPIError as e:
                # Don't retry non-rate-limit API errors
                raise
        
        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        raise BedrockAPIError("Retry logic failed unexpectedly")
