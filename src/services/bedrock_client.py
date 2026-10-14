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
import math
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
            "schemaVersion": "messages-v1",
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ],
            "inferenceConfig": {
                "maxTokens": min(4096, max(1024, forecast_horizon * 100)),  # Bound output while allowing complete horizons
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
            range_method=forecast_data['range_method'],
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

Forecast starts on {historical_data.forecast_start_date or (datetime.now(UTC).date()+timedelta(days=1)).isoformat()} (UTC). Missing history dates were not observed; do not treat them as zero.

Task:
1. Analyze the time series pattern (trend, seasonality, anomalies)
2. Return exactly {forecast_horizon} predictions for consecutive future days in order
3. Provide lower and upper uncertainty estimates; do not claim statistical calibration

Requirements:
- All predicted costs must be non-negative
- Confidence intervals must be realistic (lower ≤ prediction ≤ upper)
- Consider weekly patterns (weekday vs weekend usage)
- Account for any visible trends in the data

Output Format (JSON only, no explanation):
{{
  "forecasts": [
    {{
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
            blocks = response.get('output', {}).get('message', {}).get('content') if isinstance(response.get('output'), dict) else None
            if blocks is None: blocks = response.get('content')
            if not isinstance(blocks, list): raise BedrockInvalidResponseError('No response text blocks')
            text = ''.join(block['text'] for block in blocks if isinstance(block, dict) and isinstance(block.get('text'), str))
            if not text.strip(): raise BedrockInvalidResponseError('No forecast text in response')
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
            if not isinstance(forecasts, list) or len(forecasts) != forecast_horizon:
                raise BedrockInvalidResponseError('Model must return exactly the requested number of forecast points')
            predictions, confidence_lower, confidence_upper, dates = [], [], [], []
            forecast_start = datetime.fromisoformat(historical_data.forecast_start_date).date() if historical_data.forecast_start_date else datetime.now(UTC).date()+timedelta(days=1)
            used_heuristic = False
            for index, point in enumerate(forecasts):
                if not isinstance(point, dict) or 'predicted_cost' not in point or isinstance(point['predicted_cost'], bool):
                    raise BedrockInvalidResponseError('Missing or invalid predicted_cost')
                pred = float(point['predicted_cost'])
                if not math.isfinite(pred) or pred < 0: raise BedrockInvalidResponseError('Predicted cost must be finite and nonnegative')
                missing_bounds = 'confidence_lower' not in point or 'confidence_upper' not in point
                used_heuristic = used_heuristic or missing_bounds
                if isinstance(point.get('confidence_lower'), bool) or isinstance(point.get('confidence_upper'), bool):
                    raise BedrockInvalidResponseError('Invalid forecast range')
                lower = float(point.get('confidence_lower', pred*0.8))
                upper = float(point.get('confidence_upper', pred*1.2))
                if not math.isfinite(lower) or not math.isfinite(upper) or not 0 <= lower <= pred <= upper:
                    raise BedrockInvalidResponseError('Forecast bounds must be finite, nonnegative and ordered')
                predictions.append(pred); confidence_lower.append(lower); confidence_upper.append(upper)
                dates.append((forecast_start+timedelta(days=index)).isoformat())
            return {
                'predictions': predictions,
                'confidence_lower': confidence_lower,
                'confidence_upper': confidence_upper,
                'dates': dates,
                'range_method': 'includes_heuristic_20pct' if used_heuristic else 'model_provided_uncalibrated'
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
