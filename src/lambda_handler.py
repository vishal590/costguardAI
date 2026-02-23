"""
AWS Lambda handler for Cost Data Pipeline.

This handler processes API Gateway requests to fetch and query AWS cost data.
"""
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, UTC

from .services.cost_explorer import fetch_cost_data, CostExplorerParams
from .services.dynamodb import store_cost_data, query_cost_data, get_dynamodb_client
from .services.cloudwatch_collector import CloudWatchMetricsCollector
from .services.pricing_manager import PricingManager
from .services.cost_estimator import CostEstimator
from .services.forecast_engine import ForecastEngine
from .services.bedrock_client import BedrockClient
from .services.historical_data import HistoricalDataRetriever
from .services.forecast_cache import ForecastCacheManager
from .services.prevention_engine import PreventionEngine
from .services.budget_monitor import BudgetMonitor
from .services.resource_manager import ResourceManager
from .services.idle_detector import IdleDetector
from .services.safety_guard import SafetyGuard
from .services.action_executor import ActionExecutor
from .services.approval_manager import ApprovalManager
from .services.rollback_manager import RollbackManager
from .services.notification_service import NotificationService
from .services.eventbridge_scheduler import EventBridgeScheduler
from .services.advisor_engine import AdvisorEngine
from .services.query_processor import QueryProcessor
from .services.context_manager import ContextManager
from .services.bedrock_advisor_client import BedrockAdvisorClient
from .services.response_formatter import ResponseFormatter
from .services.advisor_cache_manager import AdvisorCacheManager
from .services.insight_generator import InsightGenerator
from .utils.types import QueryParams, ErrorResponse, EstimationResponse, InsufficientDataError, BedrockAPIError, BedrockRateLimitError
from .utils.error_handler import format_error
from .utils.validation import (
    validate_granularity, 
    validate_service_name,
    validate_forecast_days,
    validate_forecast_granularity
)
from .utils.date_utils import (
    validate_date_format,
    validate_date_range,
    calculate_default_date_range
)
from .utils.helpers import calculate_cost_summary

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler function for Cost Data Pipeline.
    
    Args:
        event: Lambda event from API Gateway containing:
            - httpMethod: 'GET' or 'POST'
            - path: Request path
            - queryStringParameters: Optional query parameters
            - body: Optional request body (JSON string)
        context: Lambda context object
        
    Returns:
        Dict containing:
            - statusCode: HTTP status code
            - headers: Response headers
            - body: JSON string response
    """
    try:
        # Log incoming event
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Check if this is an EventBridge scheduled event
        if event.get('source') == 'aws.events' or event.get('type') == 'budget-monitoring':
            return handle_eventbridge_event(event)
        
        # Extract HTTP method and path
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')
        
        # Route to appropriate handler
        # Phase 1 endpoints
        if http_method == 'POST' and '/fetch' in path:
            return handle_fetch(event)
        elif http_method == 'GET' and path.endswith('/cost-data'):
            return handle_query(event)
        # Phase 1.5 endpoints
        elif http_method == 'GET' and path.endswith('/cost-estimation/current'):
            return handle_estimation_current(event)
        elif http_method == 'GET' and '/cost-estimation/service/' in path:
            return handle_estimation_service(event)
        # Phase 2 endpoints
        elif http_method == 'GET' and path.endswith('/cost-forecast'):
            return handle_forecast_request(event)
        elif http_method == 'GET' and '/cost-forecast/service/' in path:
            return handle_forecast_service_request(event)
        # Phase 3 endpoints
        elif http_method == 'GET' and path.endswith('/prevention/status'):
            return handle_prevention_status(event)
        elif http_method == 'POST' and path.endswith('/prevention/enable'):
            return handle_prevention_enable(event)
        elif http_method == 'POST' and path.endswith('/prevention/disable'):
            return handle_prevention_disable(event)
        elif http_method == 'GET' and path.endswith('/prevention/resources'):
            return handle_prevention_resources(event)
        elif http_method == 'POST' and path.endswith('/prevention/rollback'):
            return handle_prevention_rollback(event)
        elif http_method == 'GET' and path.endswith('/prevention/history'):
            return handle_prevention_history(event)
        # Phase 4 endpoints
        elif http_method == 'POST' and path.endswith('/advisor/query'):
            return handle_advisor_query(event)
        elif http_method == 'GET' and path.endswith('/advisor/history'):
            return handle_advisor_history(event)
        elif http_method == 'DELETE' and path.endswith('/advisor/history'):
            return handle_advisor_clear_history(event)
        elif http_method == 'GET' and path.endswith('/advisor/suggestions'):
            return handle_advisor_suggestions(event)
        else:
            return create_error_response(
                400,
                'INVALID_REQUEST',
                f'Unsupported method {http_method} or path {path}'
            )
    
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_fetch(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /fetch request to fetch and store cost data.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
    """
    try:
        # Parse request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            params = json.loads(body) if body else {}
        else:
            params = body
        
        # Extract and validate parameters
        start_date = params.get('startDate')
        end_date = params.get('endDate')
        granularity = params.get('granularity', 'MONTHLY')
        
        # Use defaults if not provided
        if not start_date or not end_date:
            start_date, end_date = calculate_default_date_range()
            logger.info(f"Using default date range: {start_date} to {end_date}")
        
        # Validate date formats
        if not validate_date_format(start_date):
            return create_error_response(
                400,
                'INVALID_DATE_FORMAT',
                f'Invalid start date format: {start_date}. Expected YYYY-MM-DD'
            )
        
        if not validate_date_format(end_date):
            return create_error_response(
                400,
                'INVALID_DATE_FORMAT',
                f'Invalid end date format: {end_date}. Expected YYYY-MM-DD'
            )
        
        # Validate date range
        if not validate_date_range(start_date, end_date):
            return create_error_response(
                400,
                'INVALID_DATE_RANGE',
                f'Start date {start_date} must be before or equal to end date {end_date}'
            )
        
        # Validate granularity
        if not validate_granularity(granularity):
            return create_error_response(
                400,
                'INVALID_GRANULARITY',
                f'Invalid granularity: {granularity}. Must be DAILY, MONTHLY, or HOURLY'
            )
        
        logger.info(f"Fetching cost data: {start_date} to {end_date}, granularity: {granularity}")
        
        # Fetch cost data from Cost Explorer
        cost_explorer_params = CostExplorerParams(start_date, end_date, granularity)
        records = fetch_cost_data(cost_explorer_params)
        
        logger.info(f"Fetched {len(records)} cost records")
        
        # Store in DynamoDB
        if records:
            store_cost_data(records)
            logger.info(f"Stored {len(records)} records in DynamoDB")
        
        # Calculate summary
        summary = calculate_cost_summary(records)
        
        # Build response
        response_data = {
            'success': True,
            'message': 'Cost data fetched and stored successfully',
            'data': {
                'recordsProcessed': summary['recordCount'],
                'dateRange': {
                    'start': start_date,
                    'end': end_date
                },
                'totalCost': summary['totalCost'],
                'services': list(set(r.service for r in records))
            }
        }
        
        logger.info(f"Fetch completed successfully: {summary['recordCount']} records, ${summary['totalCost']:.2f} total")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        logger.error(f"Error in handle_fetch: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_query(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /cost-data request to query stored cost data.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
    """
    try:
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        
        start_date = query_params.get('startDate')
        end_date = query_params.get('endDate')
        service = query_params.get('service')
        limit_str = query_params.get('limit', '100')
        
        # Validate and parse limit
        try:
            limit = int(limit_str)
        except ValueError:
            return create_error_response(
                400,
                'INVALID_PARAMETER',
                f'Invalid limit: {limit_str}. Must be an integer'
            )
        
        # Validate date formats if provided
        if start_date and not validate_date_format(start_date):
            return create_error_response(
                400,
                'INVALID_DATE_FORMAT',
                f'Invalid start date format: {start_date}. Expected YYYY-MM-DD'
            )
        
        if end_date and not validate_date_format(end_date):
            return create_error_response(
                400,
                'INVALID_DATE_FORMAT',
                f'Invalid end date format: {end_date}. Expected YYYY-MM-DD'
            )
        
        # Validate date range if both provided
        if start_date and end_date and not validate_date_range(start_date, end_date):
            return create_error_response(
                400,
                'INVALID_DATE_RANGE',
                f'Start date {start_date} must be before or equal to end date {end_date}'
            )
        
        logger.info(f"Querying cost data: start={start_date}, end={end_date}, service={service}, limit={limit}")
        
        # Query DynamoDB
        params = QueryParams(
            start_date=start_date,
            end_date=end_date,
            service=service,
            limit=limit
        )
        
        records = query_cost_data(params)
        
        logger.info(f"Query returned {len(records)} records")
        
        # Convert records to response format
        data = [
            {
                'date': record.date,
                'service': record.service,
                'blendedCost': record.blended_cost,
                'unblendedCost': record.unblended_cost,
                'currency': record.currency
            }
            for record in records
        ]
        
        response_data = {
            'success': True,
            'data': data,
            'count': len(data)
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        logger.error(f"Error in handle_query: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def create_error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response.
    
    Args:
        status_code: HTTP status code
        error_code: Application error code
        message: Error message
        details: Optional additional details
        
    Returns:
        Response dict with status code and error body
    """
    error_body = {
        'success': False,
        'error': {
            'code': error_code,
            'message': message
        }
    }
    
    if details:
        error_body['error']['details'] = details
    
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(error_body)
    }



def handle_estimation_current(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /cost-estimation/current request to estimate current costs for all services.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
    """
    try:
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        
        # Extract time range parameters (default to last hour)
        hours_str = query_params.get('hours', '1')
        try:
            hours = int(hours_str)
        except ValueError:
            return create_error_response(
                400,
                'INVALID_PARAMETER',
                f'Invalid hours: {hours_str}. Must be an integer'
            )
        
        # Validate time range (1 hour to 7 days)
        if hours < 1 or hours > 168:
            return create_error_response(
                400,
                'INVALID_TIME_RANGE',
                f'Invalid time range: {hours} hours. Must be between 1 and 168 (7 days)'
            )
        
        # Calculate time range
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(hours=hours)
        
        logger.info(f"Estimating costs for all services: {start_time} to {end_time}")
        
        # Initialize services
        metrics_collector = CloudWatchMetricsCollector()
        pricing_manager = PricingManager()
        cost_estimator = CostEstimator()
        
        # Collect metrics for all services
        all_metrics = metrics_collector.collect_metrics(
            services=['ec2', 'lambda', 'dynamodb', 's3', 'rds'],
            start_time=start_time,
            end_time=end_time
        )
        
        # Calculate estimates for each service
        estimates = []
        total_cost = 0.0
        
        for service, metrics in all_metrics.items():
            if not metrics:
                continue
            
            # Get pricing data
            region = query_params.get('region', 'us-east-1')
            pricing_data = pricing_manager.get_pricing_data(service, region)
            
            # Calculate estimate
            estimate = cost_estimator.estimate_cost(service, metrics, pricing_data)
            estimates.append(estimate)
            total_cost += float(estimate.estimated_cost)
        
        logger.info(f"Estimation completed: {len(estimates)} services, ${total_cost:.2f} total")
        
        # Build response
        response_data = {
            'success': True,
            'estimates': [
                {
                    'service': est.service,
                    'estimatedCost': float(est.estimated_cost),
                    'currency': est.currency,
                    'confidenceLower': float(est.confidence_lower),
                    'confidenceUpper': float(est.confidence_upper),
                    'timestamp': est.timestamp.isoformat(),
                    'periodStart': est.period_start.isoformat(),
                    'periodEnd': est.period_end.isoformat(),
                    'metricsCount': est.metrics_count
                }
                for est in estimates
            ],
            'totalCost': total_cost,
            'currency': 'USD',
            'timestamp': datetime.now(UTC).isoformat(),
            'period': f'{hours} hours'
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        logger.error(f"Error in handle_estimation_current: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_estimation_service(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /cost-estimation/service/{service} request to estimate costs for a specific service.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
    """
    try:
        # Extract service name from path
        path = event.get('path', '')
        path_parts = path.split('/')
        
        # Find service name in path
        service = None
        for i, part in enumerate(path_parts):
            if part == 'service' and i + 1 < len(path_parts):
                service = path_parts[i + 1]
                break
        
        if not service:
            return create_error_response(
                400,
                'MISSING_SERVICE',
                'Service name is required in path'
            )
        
        # Validate service name
        if not validate_service_name(service):
            return create_error_response(
                400,
                'INVALID_SERVICE',
                f'Invalid service name: {service}. Must be one of: ec2, lambda, dynamodb, s3, rds'
            )
        
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        
        # Extract time range parameters (default to last hour)
        hours_str = query_params.get('hours', '1')
        try:
            hours = int(hours_str)
        except ValueError:
            return create_error_response(
                400,
                'INVALID_PARAMETER',
                f'Invalid hours: {hours_str}. Must be an integer'
            )
        
        # Validate time range (1 hour to 7 days)
        if hours < 1 or hours > 168:
            return create_error_response(
                400,
                'INVALID_TIME_RANGE',
                f'Invalid time range: {hours} hours. Must be between 1 and 168 (7 days)'
            )
        
        # Calculate time range
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(hours=hours)
        
        logger.info(f"Estimating costs for {service}: {start_time} to {end_time}")
        
        # Initialize services
        metrics_collector = CloudWatchMetricsCollector()
        pricing_manager = PricingManager()
        cost_estimator = CostEstimator()
        
        # Collect metrics for specified service
        all_metrics = metrics_collector.collect_metrics(
            services=[service],
            start_time=start_time,
            end_time=end_time
        )
        
        metrics = all_metrics.get(service, [])
        
        if not metrics:
            logger.info(f"No metrics found for {service}")
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': True,
                    'service': service,
                    'estimatedCost': 0.0,
                    'currency': 'USD',
                    'message': 'No metrics found for the specified time range'
                })
            }
        
        # Get pricing data
        region = query_params.get('region', 'us-east-1')
        pricing_data = pricing_manager.get_pricing_data(service, region)
        
        # Calculate estimate
        estimate = cost_estimator.estimate_cost(service, metrics, pricing_data)
        
        logger.info(f"Estimation completed for {service}: ${float(estimate.estimated_cost):.2f}")
        
        # Build response
        response_data = {
            'success': True,
            'service': estimate.service,
            'estimatedCost': float(estimate.estimated_cost),
            'currency': estimate.currency,
            'confidenceLower': float(estimate.confidence_lower),
            'confidenceUpper': float(estimate.confidence_upper),
            'timestamp': estimate.timestamp.isoformat(),
            'periodStart': estimate.period_start.isoformat(),
            'periodEnd': estimate.period_end.isoformat(),
            'metricsCount': estimate.metrics_count
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        logger.error(f"Error in handle_estimation_service: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


# ============================================================================
# Phase 2: AI Cost Forecasting Handlers
# ============================================================================

def handle_forecast_request(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/cost-forecast request for total cost forecast.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
    """
    try:
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        days = query_params.get('days', '30')
        granularity = query_params.get('granularity', 'daily')
        
        # Convert days to int
        try:
            days = int(days)
        except ValueError:
            return create_error_response(
                400,
                'INVALID_PARAMETER',
                f'Invalid days parameter: {days}. Must be an integer (7, 14, or 30)'
            )
        
        # Validate parameters
        if not validate_forecast_days(days):
            return create_error_response(
                400,
                'INVALID_PARAMETER',
                f'Invalid days value: {days}. Must be 7, 14, or 30'
            )
        
        if not validate_forecast_granularity(granularity):
            return create_error_response(
                400,
                'INVALID_PARAMETER',
                f'Invalid granularity: {granularity}. Must be "daily" or "weekly"'
            )
        
        logger.info(f"Generating forecast: days={days}, granularity={granularity}")
        
        # Initialize Phase 2 services
        dynamodb_client = get_dynamodb_client()
        bedrock_client = BedrockClient()
        historical_data_retriever = HistoricalDataRetriever(dynamodb_client)
        cache_manager = ForecastCacheManager(dynamodb_client, table_name='costguard-forecast-cache')
        forecast_engine = ForecastEngine(
            bedrock_client=bedrock_client,
            historical_data_retriever=historical_data_retriever,
            cache_manager=cache_manager
        )
        
        # Generate forecast
        forecast_response = forecast_engine.generate_forecast(
            service=None,
            days=days,
            granularity=granularity
        )
        
        # Format response
        response_data = {
            'success': forecast_response.success,
            'forecast_data': [
                {
                    'date': point.date,
                    'predicted_cost': float(point.predicted_cost),
                    'confidence_lower': float(point.confidence_lower),
                    'confidence_upper': float(point.confidence_upper),
                    'currency': point.currency
                }
                for point in forecast_response.forecast_data
            ],
            'metadata': {
                'timestamp': forecast_response.metadata.timestamp,
                'forecast_horizon': forecast_response.metadata.forecast_horizon,
                'granularity': forecast_response.metadata.granularity,
                'model_used': forecast_response.metadata.model_used,
                'service': forecast_response.metadata.service,
                'services_included': forecast_response.metadata.services_included,
                'cache_hit': forecast_response.metadata.cache_hit,
                'historical_data_days': forecast_response.metadata.historical_data_days
            }
        }
        
        logger.info(f"Forecast generated successfully: {len(forecast_response.forecast_data)} data points, cache_hit={forecast_response.metadata.cache_hit}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except InsufficientDataError as e:
        logger.warning(f"Insufficient data for forecast: {str(e)}")
        return create_error_response(
            400,
            'INSUFFICIENT_DATA',
            str(e)
        )
    
    except BedrockRateLimitError as e:
        logger.warning(f"Bedrock rate limit exceeded: {str(e)}")
        return create_error_response(
            429,
            'RATE_LIMIT_EXCEEDED',
            'Bedrock API rate limit exceeded. Please try again later.',
            {'retry_after': '60'}
        )
    
    except BedrockAPIError as e:
        logger.error(f"Bedrock API error: {str(e)}")
        return create_error_response(
            503,
            'SERVICE_UNAVAILABLE',
            'Bedrock API is currently unavailable. Please try again later.',
            {'retry_after': '30'}
        )
    
    except Exception as e:
        logger.error(f"Error in handle_forecast_request: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_forecast_service_request(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/cost-forecast/service/{service} request for service-specific forecast.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
    """
    try:
        # Parse service name from path
        path = event.get('path', '')
        # Extract service from path like /api/cost-forecast/service/lambda
        path_parts = path.split('/')
        service = None
        for i, part in enumerate(path_parts):
            if part == 'service' and i + 1 < len(path_parts):
                service = path_parts[i + 1]
                break
        
        if not service:
            return create_error_response(
                400,
                'INVALID_REQUEST',
                'Service name not found in path'
            )
        
        # Validate service name
        if not validate_service_name(service):
            return create_error_response(
                400,
                'INVALID_SERVICE',
                f'Invalid service name: {service}. Must be one of: ec2, lambda, dynamodb, s3, rds'
            )
        
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        days = query_params.get('days', '30')
        granularity = query_params.get('granularity', 'daily')
        
        # Convert days to int
        try:
            days = int(days)
        except ValueError:
            return create_error_response(
                400,
                'INVALID_PARAMETER',
                f'Invalid days parameter: {days}. Must be an integer (7, 14, or 30)'
            )
        
        # Validate parameters
        if not validate_forecast_days(days):
            return create_error_response(
                400,
                'INVALID_PARAMETER',
                f'Invalid days value: {days}. Must be 7, 14, or 30'
            )
        
        if not validate_forecast_granularity(granularity):
            return create_error_response(
                400,
                'INVALID_PARAMETER',
                f'Invalid granularity: {granularity}. Must be "daily" or "weekly"'
            )
        
        logger.info(f"Generating forecast for service {service}: days={days}, granularity={granularity}")
        
        # Initialize Phase 2 services
        dynamodb_client = get_dynamodb_client()
        bedrock_client = BedrockClient()
        historical_data_retriever = HistoricalDataRetriever(dynamodb_client)
        cache_manager = ForecastCacheManager(dynamodb_client, table_name='costguard-forecast-cache')
        forecast_engine = ForecastEngine(
            bedrock_client=bedrock_client,
            historical_data_retriever=historical_data_retriever,
            cache_manager=cache_manager
        )
        
        # Generate forecast for specific service
        forecast_response = forecast_engine.generate_forecast(
            service=service,
            days=days,
            granularity=granularity
        )
        
        # Format response
        response_data = {
            'success': forecast_response.success,
            'forecast_data': [
                {
                    'date': point.date,
                    'predicted_cost': float(point.predicted_cost),
                    'confidence_lower': float(point.confidence_lower),
                    'confidence_upper': float(point.confidence_upper),
                    'currency': point.currency
                }
                for point in forecast_response.forecast_data
            ],
            'metadata': {
                'timestamp': forecast_response.metadata.timestamp,
                'forecast_horizon': forecast_response.metadata.forecast_horizon,
                'granularity': forecast_response.metadata.granularity,
                'model_used': forecast_response.metadata.model_used,
                'service': forecast_response.metadata.service,
                'services_included': forecast_response.metadata.services_included,
                'cache_hit': forecast_response.metadata.cache_hit,
                'historical_data_days': forecast_response.metadata.historical_data_days
            }
        }
        
        logger.info(f"Forecast generated successfully for {service}: {len(forecast_response.forecast_data)} data points, cache_hit={forecast_response.metadata.cache_hit}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except InsufficientDataError as e:
        logger.warning(f"Insufficient data for forecast: {str(e)}")
        return create_error_response(
            400,
            'INSUFFICIENT_DATA',
            str(e)
        )
    
    except BedrockRateLimitError as e:
        logger.warning(f"Bedrock rate limit exceeded: {str(e)}")
        return create_error_response(
            429,
            'RATE_LIMIT_EXCEEDED',
            'Bedrock API rate limit exceeded. Please try again later.',
            {'retry_after': '60'}
        )
    
    except BedrockAPIError as e:
        logger.error(f"Bedrock API error: {str(e)}")
        return create_error_response(
            503,
            'SERVICE_UNAVAILABLE',
            'Bedrock API is currently unavailable. Please try again later.',
            {'retry_after': '30'}
        )
    
    except Exception as e:
        logger.error(f"Error in handle_forecast_service_request: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


# ============================================================================
# Phase 3: Automated Cost Prevention Handlers
# ============================================================================

def handle_prevention_status(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/prevention/status request to get prevention system status.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
    """
    try:
        logger.info("Getting prevention system status")
        
        # Initialize prevention engine
        prevention_engine = _get_prevention_engine()
        
        # Get status
        status = prevention_engine.get_status()
        
        logger.info(f"Prevention status retrieved: enabled={status.get('enabled')}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'status': status
            })
        }
    
    except Exception as e:
        logger.error(f"Error in handle_prevention_status: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_prevention_enable(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/prevention/enable request to enable prevention system.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
    """
    try:
        logger.info("Enabling prevention system")
        
        # Initialize prevention engine
        prevention_engine = _get_prevention_engine()
        
        # Enable prevention
        prevention_engine.enable()
        
        logger.info("Prevention system enabled successfully")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'message': 'Prevention system enabled',
                'status': prevention_engine.get_status()
            })
        }
    
    except Exception as e:
        logger.error(f"Error in handle_prevention_enable: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_prevention_disable(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/prevention/disable request to disable prevention system.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
    """
    try:
        logger.info("Disabling prevention system")
        
        # Initialize prevention engine
        prevention_engine = _get_prevention_engine()
        
        # Disable prevention
        prevention_engine.disable()
        
        logger.info("Prevention system disabled successfully")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'message': 'Prevention system disabled',
                'status': prevention_engine.get_status()
            })
        }
    
    except Exception as e:
        logger.error(f"Error in handle_prevention_disable: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_prevention_resources(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/prevention/resources request to list managed resources.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
    """
    try:
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        service = query_params.get('service')
        state = query_params.get('state')
        
        logger.info(f"Getting prevention resources: service={service}, state={state}")
        
        # Initialize prevention engine
        prevention_engine = _get_prevention_engine()
        
        # Build filters
        filters = {}
        if service:
            filters['service'] = service
        if state:
            filters['state'] = state
        
        # Get resources
        resources = prevention_engine.get_resources(filters=filters if filters else None)
        
        # Format response
        resources_data = [
            {
                'resource_id': r.resource_id,
                'resource_type': r.resource_type,
                'service': r.service,
                'region': r.region,
                'tags': r.tags,
                'state': r.state,
                'creation_date': r.creation_date
            }
            for r in resources
        ]
        
        logger.info(f"Retrieved {len(resources)} resources")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'resources': resources_data,
                'count': len(resources_data)
            })
        }
    
    except Exception as e:
        logger.error(f"Error in handle_prevention_resources: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_prevention_rollback(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/prevention/rollback request to rollback an action.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
    """
    try:
        # Parse request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            params = json.loads(body) if body else {}
        else:
            params = body
        
        action_id = params.get('action_id')
        
        if not action_id:
            return create_error_response(
                400,
                'MISSING_PARAMETER',
                'action_id is required'
            )
        
        logger.info(f"Rolling back action: {action_id}")
        
        # Initialize prevention engine
        prevention_engine = _get_prevention_engine()
        
        # Execute rollback
        result = prevention_engine.execute_rollback(action_id)
        
        if result['success']:
            logger.info(f"Rollback successful for action {action_id}")
        else:
            logger.warning(f"Rollback failed for action {action_id}: {result.get('error')}")
        
        return {
            'statusCode': 200 if result['success'] else 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': result['success'],
                'action_id': result.get('action_id'),
                'resource_id': result.get('resource_id'),
                'message': result.get('message'),
                'error': result.get('error')
            })
        }
    
    except Exception as e:
        logger.error(f"Error in handle_prevention_rollback: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_prevention_history(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/prevention/history request to get action history.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
    """
    try:
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')
        limit_str = query_params.get('limit', '100')
        
        try:
            limit = int(limit_str)
        except ValueError:
            return create_error_response(
                400,
                'INVALID_PARAMETER',
                f'Invalid limit: {limit_str}. Must be an integer'
            )
        
        logger.info(f"Getting prevention history: start={start_date}, end={end_date}, limit={limit}")
        
        # Initialize prevention engine
        prevention_engine = _get_prevention_engine()
        
        # Get history (this would query the audit table)
        # For now, return a placeholder response
        history = []
        
        logger.info(f"Retrieved {len(history)} history records")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'history': history,
                'count': len(history)
            })
        }
    
    except Exception as e:
        logger.error(f"Error in handle_prevention_history: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_eventbridge_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle EventBridge scheduled event for budget monitoring.
    
    Args:
        event: EventBridge event
        
    Returns:
        Response dict with status code and body
        
    Requirements:
    - 1.1: Trigger budget monitoring every 5 minutes
    """
    try:
        logger.info("Processing EventBridge scheduled event")
        
        # Initialize prevention engine
        prevention_engine = _get_prevention_engine()
        
        # Initialize EventBridge scheduler
        scheduler = EventBridgeScheduler(prevention_engine)
        
        # Handle the scheduled event
        result = scheduler.handle_scheduled_event(event)
        
        if result['success']:
            logger.info(f"EventBridge event processed successfully: {result}")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'success': True,
                    'message': 'Budget monitoring completed',
                    'result': result
                })
            }
        else:
            logger.error(f"EventBridge event processing failed: {result}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'success': False,
                    'error': result.get('error', 'Unknown error')
                })
            }
    
    except Exception as e:
        logger.error(f"Error in handle_eventbridge_event: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )




# ============================================================================
# Phase 4: AI Cost Advisor Handlers
# ============================================================================

def handle_advisor_query(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/advisor/query request to process natural language queries.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
    """
    try:
        # Parse request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            params = json.loads(body) if body else {}
        else:
            params = body
        
        query = params.get('query')
        user_id = params.get('user_id', 'default')
        session_id = params.get('session_id', 'default')
        
        if not query:
            return create_error_response(
                400,
                'MISSING_PARAMETER',
                'query is required'
            )
        
        logger.info(f"Processing advisor query: user={user_id}, session={session_id}")
        
        # Initialize advisor engine
        advisor_engine = _get_advisor_engine()
        
        # Process query
        response = advisor_engine.process_query(query, user_id, session_id)
        
        # Format response
        response_data = {
            'success': True,
            'response': response.response_text,
            'recommendations': [
                {
                    'action': rec.action,
                    'rationale': rec.rationale,
                    'estimated_savings': float(rec.estimated_savings),
                    'priority': rec.priority,
                    'safe': rec.safe
                }
                for rec in response.recommendations
            ],
            'cost_data': response.cost_data,
            'confidence': float(response.confidence),
            'cached': response.cached
        }
        
        logger.info(f"Query processed successfully: cached={response.cached}, recommendations={len(response.recommendations)}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        logger.error(f"Error in handle_advisor_query: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_advisor_history(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/advisor/history request to retrieve conversation history.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
    """
    try:
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        session_id = query_params.get('session_id', 'default')
        
        logger.info(f"Retrieving conversation history: session={session_id}")
        
        # Initialize advisor engine
        advisor_engine = _get_advisor_engine()
        
        # Get conversation history
        history = advisor_engine.get_conversation_history(session_id)
        
        # Format response
        response_data = {
            'success': True,
            'history': [
                {
                    'query': turn.query,
                    'response': turn.response,
                    'timestamp': turn.timestamp.isoformat()
                }
                for turn in history
            ],
            'count': len(history)
        }
        
        logger.info(f"Retrieved {len(history)} conversation turns")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        logger.error(f"Error in handle_advisor_history: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_advisor_clear_history(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle DELETE /api/advisor/history request to clear conversation history.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
    """
    try:
        # Parse request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            params = json.loads(body) if body else {}
        else:
            params = body
        
        session_id = params.get('session_id', 'default')
        
        logger.info(f"Clearing conversation history: session={session_id}")
        
        # Initialize advisor engine
        advisor_engine = _get_advisor_engine()
        
        # Clear conversation history
        advisor_engine.clear_conversation_history(session_id)
        
        logger.info(f"Conversation history cleared for session {session_id}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'message': 'Conversation history cleared',
                'session_id': session_id
            })
        }
    
    except Exception as e:
        logger.error(f"Error in handle_advisor_clear_history: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_advisor_suggestions(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/advisor/suggestions request to get proactive insights.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
    """
    try:
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        user_id = query_params.get('user_id', 'default')
        
        logger.info(f"Generating proactive insights: user={user_id}")
        
        # Initialize advisor engine
        advisor_engine = _get_advisor_engine()
        
        # Generate proactive insights
        insights = advisor_engine.generate_proactive_insights(user_id)
        
        # Format response
        response_data = {
            'success': True,
            'insights': [
                {
                    'insight_type': insight.insight_type,
                    'title': insight.title,
                    'description': insight.description,
                    'severity': insight.severity,
                    'action_required': insight.action_required,
                    'related_services': insight.related_services,
                    'estimated_impact': float(insight.estimated_impact) if insight.estimated_impact else None
                }
                for insight in insights
            ],
            'count': len(insights)
        }
        
        logger.info(f"Generated {len(insights)} proactive insights")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        logger.error(f"Error in handle_advisor_suggestions: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def _get_advisor_engine() -> AdvisorEngine:
    """
    Initialize and return an AdvisorEngine instance.
    
    Returns:
        Configured AdvisorEngine instance
    """
    # Initialize DynamoDB client
    dynamodb_client = get_dynamodb_client()
    
    # Initialize Phase 4 components
    query_processor = QueryProcessor()
    context_manager = ContextManager(
        cost_explorer_client=None,
        dynamodb_client=dynamodb_client
    )
    bedrock_advisor_client = BedrockAdvisorClient(
        bedrock_client=None
    )
    response_formatter = ResponseFormatter()
    cache_manager = AdvisorCacheManager(
        dynamodb_client=dynamodb_client,
        table_name='costguard-advisor-cache'
    )
    insight_generator = InsightGenerator(
        cost_explorer_client=None,
        dynamodb_client=dynamodb_client
    )
    
    # Create advisor engine
    advisor_engine = AdvisorEngine(
        query_processor=query_processor,
        context_manager=context_manager,
        bedrock_client=bedrock_advisor_client,
        response_formatter=response_formatter,
        cache_manager=cache_manager,
        insight_generator=insight_generator,
        dynamodb_client=dynamodb_client,
        conversation_table_name='costguard-advisor-conversation-history'
    )
    
    return advisor_engine


def _get_prevention_engine() -> PreventionEngine:
    """
    Initialize and return a PreventionEngine instance.
    
    Returns:
        Configured PreventionEngine instance
    """
    # Initialize all required components
    # Note: In production, these would use actual AWS clients
    # For now, we'll use None and let the engine handle initialization
    
    budget_monitor = BudgetMonitor(
        budgets_client=None,
        cost_estimator=None
    )
    
    resource_manager = ResourceManager(
        aws_clients={},
        dynamodb_client=None
    )
    
    idle_detector = IdleDetector(
        cloudwatch_client=None
    )
    
    safety_guard = SafetyGuard(
        config=None
    )
    
    action_executor = ActionExecutor(
        aws_clients={},
        audit_logger=None
    )
    
    approval_manager = ApprovalManager(
        sns_client=None,
        dynamodb_client=None
    )
    
    rollback_manager = RollbackManager(
        aws_clients={},
        dynamodb_client=None
    )
    
    notification_service = NotificationService(
        sns_client=None,
        config=None
    )
    
    # Create prevention engine
    prevention_engine = PreventionEngine(
        budget_monitor=budget_monitor,
        resource_manager=resource_manager,
        idle_detector=idle_detector,
        safety_guard=safety_guard,
        action_executor=action_executor,
        approval_manager=approval_manager,
        rollback_manager=rollback_manager,
        notification_service=notification_service
    )
    
    return prevention_engine
