"""
AWS Lambda handler for Cost Data Pipeline.

This handler processes API Gateway requests to fetch and query AWS cost data.
"""
import json
from .services.request_json import RequestBodyError, prepare_json_body
from .services.access_control import AccessDenied, BackendAuthenticationError, BackendConfigurationError, authorize_stack_request, advisor_identity
import logging
import os
import threading
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
from .services.prevention_engine import PreventionEngine, PreventionConfigurationUnavailable, PreventionConfigurationConflict
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
from .utils.helpers import calculate_cost_summary, cost_explorer_service_to_short

# API Gateway integration timeout is 29s; forecast/advisor run in a thread and return before this.
FORECAST_THREAD_TIMEOUT = 28.0

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
        logger.info("Request method=%s path=%s", event.get("httpMethod"), event.get("path"))
        
        # Check if this is an EventBridge scheduled event
        if event.get('source') == 'aws.events' or event.get('type') == 'budget-monitoring':
            return handle_eventbridge_event(event)
        
        try:
            authorize_stack_request(event)
        except RequestBodyError as exc:
            return create_error_response(400, 'INVALID_REQUEST_BODY', str(exc))
        except BackendConfigurationError:
            return create_error_response(503, 'BACKEND_AUTHENTICATION_UNAVAILABLE', 'Backend access is not configured')
        except BackendAuthenticationError:
            return create_error_response(401, 'BACKEND_AUTHENTICATION_FAILED', 'Invalid backend access key')
        except AccessDenied as exc:
            return create_error_response(403, "ACCESS_DENIED", str(exc))

        # Extract HTTP method and path
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')
        
        # Route to appropriate handler
        # Phase 1 endpoints
        if http_method == 'POST' and '/fetch' in path:
            return handle_fetch(event)
        elif http_method == 'GET' and path.endswith('/cost-data/summary'):
            return handle_cost_history_summary(event)
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
        elif http_method == 'POST' and path.endswith('/prevention/config'):
            return handle_prevention_config(event)
        elif http_method == 'POST' and path.endswith('/prevention/enable'):
            return handle_prevention_enable(event)
        elif http_method == 'POST' and path.endswith('/prevention/disable'):
            return handle_prevention_disable(event)
        elif http_method == 'GET' and path.endswith('/prevention/resource'):
            return handle_prevention_resource(event)
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
        # Phase 5: Multi-account stub (full API in MultiAccountStack; stub returns empty data when using main API URL)
        elif http_method == 'GET' and ('/organizations' in path or path.endswith('/costs/consolidated') or path.endswith('/costs/by-account')):
            return handle_multi_account_stub(event)
        # Phase 6 Autonomous API is in AutonomousStack (separate API URL). Not handled by main Lambda.
        # Phase 6: AI/ML workload cost management endpoints
        elif '/ai-ml/' in path:
            # Delegate all AI/ML endpoints to the AI/ML handler
            from .ai_ml_handler import handler as aiml_handler
            return aiml_handler(event, context)
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
        granularity = params.get('granularity', 'DAILY')
        
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
        
        span = (datetime.fromisoformat(end_date)-datetime.fromisoformat(start_date)).days
        maximum = 14 if granularity == 'HOURLY' else 366 if granularity == 'MONTHLY' else 31
        if not 1 <= span <= maximum:
            return create_error_response(400, 'INVALID_DATE_RANGE', f'Choose 1-{maximum} days; fetch end dates are exclusive')
        if datetime.fromisoformat(end_date).date() > datetime.now(UTC).date():
            return create_error_response(400, 'INVALID_DATE_RANGE', 'Fetch end date cannot be later than today UTC')
        if granularity == 'HOURLY' and datetime.fromisoformat(start_date).date() < datetime.now(UTC).date()-timedelta(days=14):
            return create_error_response(400, 'INVALID_DATE_RANGE', 'Hourly collection supports the recent 14-day provider window')

        logger.info(f"Fetching cost data: {start_date} to {end_date}, granularity: {granularity}")
        
        # Fetch cost data from Cost Explorer
        cost_explorer_params = CostExplorerParams(start_date, end_date, granularity)
        records = fetch_cost_data(cost_explorer_params)
        
        logger.info(f"Fetched {len(records)} cost records")
        
        currencies = {record.currency for record in records}
        if len(currencies) > 1:
            return create_error_response(503, 'INCONSISTENT_CURRENCY', 'Cost data uses inconsistent currencies; no combined total is available')
        # Store in DynamoDB
        if records:
            table_name = os.environ.get('COST_DATA_TABLE', 'costguard-cost-data')
            # Invalidate before and after the batch so an in-flight forecast
            # cannot populate the post-refresh generation with older input.
            import boto3
            refresh_cache = ForecastCacheManager(boto3.client('dynamodb'), table_name=os.environ.get('FORECAST_CACHE_TABLE', 'costguard-forecast-cache'))
            refresh_cache.invalidate_all()
            try:
                store_cost_data(records, table_name=table_name)
            finally:
                refresh_cache.invalidate_all()
            logger.info(f"Stored {len(records)} records in DynamoDB")
        
        # Calculate summary
        summary = calculate_cost_summary(records)
        
        # Build response
        response_data = {
            'success': True,
            'message': 'Cost data fetched and stored successfully' if records else 'No observed service cost records were returned',
            'data': {
                'recordsProcessed': summary['recordCount'],
                'dateRange': {
                    'start': start_date,
                    'end': end_date
                },
                'totalCost': summary['totalCost'] if records else None,
                'currency': next(iter(currencies)) if currencies else None,
                'observationStatus': 'observed' if records else 'no_observations',
                'granularity': granularity,
                'estimatedRecords': sum(record.is_estimated is True for record in records),
                'unknownEstimateRecords': sum(record.is_estimated is None for record in records),
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


def handle_cost_history_summary(event):
    """Summarize selected stored daily rows independently of history page limits."""
    from .services.cost_history_summary import summarize_daily_history
    params = event.get('queryStringParameters') or {}
    start, end = params.get('startDate'), params.get('endDate')
    if not validate_date_format(start or '') or not validate_date_format(end or '') or not validate_date_range(start, end):
        return create_error_response(400, 'INVALID_DATE_RANGE', 'Supply ordered YYYY-MM-DD startDate and endDate')
    if (datetime.fromisoformat(end)-datetime.fromisoformat(start)).days > 30:
        return create_error_response(400, 'INVALID_DATE_RANGE', 'Daily summaries support at most 31 dates')
    try:
        records = query_cost_data(QueryParams(start_date=start, end_date=end, service=params.get('service'), granularity='DAILY'),
            table_name=os.environ.get('COST_DATA_TABLE', 'costguard-cost-data'))
        result = summarize_daily_history(records, start, end)
        return {'statusCode': 200, 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}, 'body': json.dumps(result)}
    except ValueError as error: return create_error_response(422, 'COST_SUMMARY_UNAVAILABLE', str(error))
    except Exception as error:
        logger.warning('Daily summary unavailable: %s', type(error).__name__)
        return create_error_response(503, 'COST_SUMMARY_UNAVAILABLE', 'Observed daily history could not be loaded')


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
        granularity = query_params.get('granularity', 'DAILY')
        if granularity not in ('DAILY', 'MONTHLY', 'HOURLY', 'UNKNOWN'):
            return create_error_response(400, 'INVALID_GRANULARITY', 'Choose DAILY, MONTHLY, HOURLY or UNKNOWN legacy records')
        limit_str = query_params.get('limit', '100')
        
        # Validate and parse limit
        try:
            limit = int(limit_str)
        except (ValueError, TypeError):
            return create_error_response(
                400,
                'INVALID_PARAMETER',
                f'Invalid limit: {limit_str}. Must be an integer'
            )
        
        if not 1 <= limit <= 1000:
            return create_error_response(400, 'INVALID_PARAMETER', 'Limit must be between 1 and 1000')

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
        
        # HTTP history always has bounded monthly-partition reads. The service
        # utility retains its explicit undated scan fallback for internal callers.
        end_date = end_date or datetime.now(UTC).date().isoformat()
        start_date = start_date or (datetime.fromisoformat(end_date).date()-timedelta(days=30)).isoformat()
        maximum_days = 31 if granularity == 'HOURLY' else 366
        if (datetime.fromisoformat(end_date)-datetime.fromisoformat(start_date)).days >= maximum_days:
            return create_error_response(400, 'INVALID_DATE_RANGE', f'Choose at most {maximum_days} inclusive dates for this granularity')

        # Validate date range if both provided
        if start_date and end_date and not validate_date_range(start_date, end_date):
            return create_error_response(
                400,
                'INVALID_DATE_RANGE',
                f'Start date {start_date} must be before or equal to end date {end_date}'
            )
        
        logger.info(f"Querying cost data: start={start_date}, end={end_date}, service={service}, limit={limit}")
        
        from .services.cost_history_cursor import decode_cursor, encode_cursor
        filters = {'start': start_date, 'end': end_date, 'service': service, 'granularity': granularity}
        try:
            before_date, before_service = decode_cursor(query_params['cursor'], filters) if query_params.get('cursor') else (None, None)
        except ValueError as error:
            return create_error_response(400, 'INVALID_CURSOR', str(error))
        # Query DynamoDB
        params = QueryParams(
            start_date=start_date,
            end_date=end_date,
            service=service,
            limit=limit + 1,
            granularity=granularity, before_date=before_date, before_service=before_service
        )
        table_name = os.environ.get('COST_DATA_TABLE', 'costguard-cost-data')
        records = query_cost_data(params, table_name=table_name)
        
        has_more = len(records) > limit
        records = records[:limit]
        logger.info(f'Query returned {len(records)} records; truncated={has_more}')
        
        # Convert records to response format (normalize service to short name for consistent display with Phase 2)
        data = [
            {
                'date': record.date,
                'service': cost_explorer_service_to_short(record.service),
                'blendedCost': record.blended_cost,
                'unblendedCost': record.unblended_cost,
                'currency': record.currency,
                'granularity': record.granularity,
                'period_end': record.period_end, 'is_estimated': record.is_estimated
            }
            for record in records
        ]
        
        response_data = {
            'success': True,
            'data': data,
            'count': len(data),
            'granularity': granularity,
            'has_more': has_more,
            'result_scope': 'page_records',
            'next_cursor': encode_cursor(records[-1], filters) if has_more and records else None,
            'pagination_consistency': 'live_keyset_not_snapshot',
            'legacy_period_unknown': granularity == 'UNKNOWN'
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


def handle_autonomous_demo_stub(event: Dict[str, Any]) -> Dict[str, Any]:
    """Expose missing autonomous routing without claiming an action was accepted."""
    return create_error_response(
        503, 'AUTONOMOUS_BACKEND_UNAVAILABLE',
        'Autonomous optimization is unavailable. No request was accepted; contact your administrator.'
    )


def handle_multi_account_stub(event: Dict[str, Any]) -> Dict[str, Any]:
    """Expose missing multi-account routing without manufacturing empty results."""
    return create_error_response(
        503, 'MULTI_ACCOUNT_BACKEND_UNAVAILABLE',
        'Organization data is unavailable. Contact your administrator.'
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
        region = query_params.get('region') or os.environ.get('AWS_REGION', 'us-east-1')
        metrics_collector = CloudWatchMetricsCollector(region=region)
        pricing_manager = PricingManager()
        cost_estimator = CostEstimator()
        
        requested_services = ['ec2', 'lambda', 'dynamodb', 's3', 'rds']
        # Collect service-specific metrics (returns original metric objects)
        all_service_metrics = metrics_collector.collect_service_metrics(
            services=requested_services,
            start_time=start_time,
            end_time=end_time
        )
        
        # Calculate estimates for each service using service-specific methods
        estimates = []
        total_cost = 0.0
        
        missing_metric_services = []
        for service in requested_services:
            service_metrics = all_service_metrics.get(service)
            if not service_metrics:
                from .utils.types import CostEstimate
                missing_metric_services.append(service)
                estimates.append(CostEstimate(service=service, estimated_cost=None, currency='USD',
                    confidence_lower=None, confidence_upper=None, timestamp=datetime.now(UTC),
                    period_start=start_time, period_end=end_time, metrics_count=0, status='unavailable',
                    reason='No observed metrics were returned; this does not establish zero cost'))
                continue
            
            # Get pricing data
            pricing_data = pricing_manager.get_pricing_data(service, region)
            
            # Calculate estimate using service-specific method
            estimate = cost_estimator.estimate_cost_with_service_method(
                service=service,
                service_metrics=service_metrics,
                pricing_data=pricing_data,
                start_time=start_time,
                end_time=end_time
            )
            estimates.append(estimate)
            total_cost += float(estimate.estimated_cost) if estimate.estimated_cost is not None else 0.0
        
        logger.info(f"Estimation completed: {len(estimates)} services, ${total_cost:.2f} total")
        
        # Build response
        response_data = {
            'success': True,
            'estimates': [
                {
                    'service': est.service,
                    'status': est.status, 'pricingSource': est.pricing_source, 'pricingProfile': est.pricing_profile, 'reason': est.reason, 'rangeMethod': est.range_method, 'coveredComponents': est.covered_components, 'missingComponents': est.missing_components,
                    'estimatedCost': float(est.estimated_cost) if est.estimated_cost is not None else None,
                    'currency': est.currency,
                    'confidenceLower': float(est.confidence_lower) if est.confidence_lower is not None else None,
                    'confidenceUpper': float(est.confidence_upper) if est.confidence_upper is not None else None,
                    'timestamp': est.timestamp.isoformat(),
                    'periodStart': est.period_start.isoformat(),
                    'periodEnd': est.period_end.isoformat(),
                    'metricsCount': est.metrics_count
                }
                for est in estimates
            ],
            'totalCost': total_cost if any(est.estimated_cost is not None for est in estimates) else None,
            'complete': bool(estimates) and all(est.status == 'estimated' for est in estimates),
            'missingMetricServices': missing_metric_services,
            'coverageScope': 'selected_service_metric_profiles',
            'region': region,
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
        region = query_params.get('region') or os.environ.get('AWS_REGION', 'us-east-1')
        metrics_collector = CloudWatchMetricsCollector(region=region)
        pricing_manager = PricingManager()
        cost_estimator = CostEstimator()
        
        # Collect service-specific metrics for specified service
        all_service_metrics = metrics_collector.collect_service_metrics(
            services=[service],
            start_time=start_time,
            end_time=end_time
        )
        
        service_metrics = all_service_metrics.get(service, [])
        
        if not service_metrics:
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
                    'estimatedCost': None,
                    'status': 'unavailable',
                    'complete': False,
                    'reason': 'No observed metrics were returned; this does not establish zero cost',
                    'region': region,
                    'currency': 'USD',
                    'message': 'No metrics found for the specified time range'
                })
            }
        
        # Get pricing data
        pricing_data = pricing_manager.get_pricing_data(service, region)
        
        # Calculate estimate using service-specific method
        estimate = cost_estimator.estimate_cost_with_service_method(
            service=service,
            service_metrics=service_metrics,
            pricing_data=pricing_data,
            start_time=start_time,
            end_time=end_time
        )
        
        logger.info("Estimation service=%s status=%s", service, estimate.status)
        
        # Build response
        response_data = {
            'success': True,
            'service': estimate.service,
            'complete': estimate.status == 'estimated',
            'coverageScope': 'selected_service_metric_profiles',
            'status': estimate.status, 'pricingSource': estimate.pricing_source, 'pricingProfile': estimate.pricing_profile, 'reason': estimate.reason, 'rangeMethod': estimate.range_method, 'coveredComponents': estimate.covered_components, 'missingComponents': estimate.missing_components,
            'estimatedCost': float(estimate.estimated_cost) if estimate.estimated_cost is not None else None,
            'currency': estimate.currency,
            'confidenceLower': float(estimate.confidence_lower) if estimate.confidence_lower is not None else None,
            'confidenceUpper': float(estimate.confidence_upper) if estimate.confidence_upper is not None else None,
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

        # Run forecast with timeout so we return 200 + message before API Gateway 29s limit (avoid 504)
        forecast_result = [None]
        forecast_error = [None]

        def run_forecast():
            try:
                import boto3
                dynamodb_resource = boto3.resource('dynamodb')
                dynamodb_client = boto3.client('dynamodb')
                bedrock_client = BedrockClient()
                cost_data_table = os.environ.get('COST_DATA_TABLE', 'costguard-cost-data')
                historical_data_retriever = HistoricalDataRetriever(dynamodb_resource, table_name=cost_data_table)
                cache_manager = ForecastCacheManager(dynamodb_client, table_name=os.environ.get('FORECAST_CACHE_TABLE', 'costguard-forecast-cache'))
                forecast_engine = ForecastEngine(
                    bedrock_client=bedrock_client,
                    historical_data_retriever=historical_data_retriever,
                    cache_manager=cache_manager
                )
                forecast_response = forecast_engine.generate_forecast(
                    service=None,
                    days=days,
                    granularity=granularity
                )
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
                        'historical_data_days': forecast_response.metadata.historical_data_days,
                        'range_method': forecast_response.metadata.range_method,
                        'observed_history_days': forecast_response.metadata.observed_history_days,
                        'missing_history_dates': forecast_response.metadata.missing_history_dates,
                        'history_method': forecast_response.metadata.history_method,
                        'cost_metric': forecast_response.metadata.cost_metric,
                        'forecast_start_date': forecast_response.metadata.forecast_start_date,
                        'estimated_dates': forecast_response.metadata.estimated_dates, 'unknown_estimate_dates': forecast_response.metadata.unknown_estimate_dates
                    }
                }
                forecast_result[0] = response_data
            except Exception as e:
                forecast_error[0] = e

        thread = threading.Thread(target=run_forecast, daemon=True)
        thread.start()
        thread.join(timeout=FORECAST_THREAD_TIMEOUT)
        if thread.is_alive():
            logger.warning("Forecast request timed out after %.0fs", FORECAST_THREAD_TIMEOUT)
            response_data = {
                'success': False,
                'forecast_data': [],
                'metadata': {
                    'timestamp': datetime.now(UTC).isoformat(),
                    'forecast_horizon': days,
                    'granularity': granularity,
                    'model_used': None,
                    'service': None,
                    'services_included': None,
                    'cache_hit': False,
                    'historical_data_days': None
                },
                'error': 'timeout',
                'message': (
                    'Forecast is taking longer than expected (API limit). '
                    'Try fewer days (e.g. 7 or 14), or try again in a moment. Cached forecasts return instantly.'
                )
            }
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps(response_data)
            }
        if forecast_error[0] is not None:
            raise forecast_error[0]
        response_data = forecast_result[0]
        if response_data is None:
            raise RuntimeError("Forecast completed but no result returned")

        logger.info(f"Forecast generated successfully: {len(response_data['forecast_data'])} data points, cache_hit={response_data['metadata']['cache_hit']}")

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

        # Run forecast with timeout so we return 200 + message before API Gateway 29s limit (avoid 504)
        forecast_result = [None]
        forecast_error = [None]

        def run_forecast_service():
            try:
                import boto3
                dynamodb_resource = boto3.resource('dynamodb')
                dynamodb_client = boto3.client('dynamodb')
                bedrock_client = BedrockClient()
                cost_data_table = os.environ.get('COST_DATA_TABLE', 'costguard-cost-data')
                historical_data_retriever = HistoricalDataRetriever(dynamodb_resource, table_name=cost_data_table)
                cache_manager = ForecastCacheManager(dynamodb_client, table_name=os.environ.get('FORECAST_CACHE_TABLE', 'costguard-forecast-cache'))
                forecast_engine = ForecastEngine(
                    bedrock_client=bedrock_client,
                    historical_data_retriever=historical_data_retriever,
                    cache_manager=cache_manager
                )
                forecast_response = forecast_engine.generate_forecast(
                    service=service,
                    days=days,
                    granularity=granularity
                )
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
                        'historical_data_days': forecast_response.metadata.historical_data_days,
                        'range_method': forecast_response.metadata.range_method,
                        'observed_history_days': forecast_response.metadata.observed_history_days,
                        'missing_history_dates': forecast_response.metadata.missing_history_dates,
                        'history_method': forecast_response.metadata.history_method,
                        'cost_metric': forecast_response.metadata.cost_metric,
                        'forecast_start_date': forecast_response.metadata.forecast_start_date,
                        'estimated_dates': forecast_response.metadata.estimated_dates, 'unknown_estimate_dates': forecast_response.metadata.unknown_estimate_dates
                    }
                }
                forecast_result[0] = response_data
            except Exception as e:
                forecast_error[0] = e

        thread = threading.Thread(target=run_forecast_service, daemon=True)
        thread.start()
        thread.join(timeout=FORECAST_THREAD_TIMEOUT)
        if thread.is_alive():
            logger.warning("Forecast service request timed out after %.0fs", FORECAST_THREAD_TIMEOUT)
            response_data = {
                'success': False,
                'forecast_data': [],
                'metadata': {
                    'timestamp': datetime.now(UTC).isoformat(),
                    'forecast_horizon': days,
                    'granularity': granularity,
                    'model_used': None,
                    'service': service,
                    'services_included': None,
                    'cache_hit': False,
                    'historical_data_days': None
                },
                'error': 'timeout',
                'message': (
                    'Forecast is taking longer than expected (API limit). '
                    'Try fewer days (e.g. 7 or 14), or try again in a moment. Cached forecasts return instantly.'
                )
            }
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps(response_data)
            }
        if forecast_error[0] is not None:
            raise forecast_error[0]
        response_data = forecast_result[0]
        if response_data is None:
            raise RuntimeError("Forecast completed but no result returned")

        logger.info(f"Forecast generated successfully for {service}: {len(response_data['forecast_data'])} data points, cache_hit={response_data['metadata']['cache_hit']}")

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
    
    except PreventionConfigurationConflict as e:
        return create_error_response(409, 'PREVENTION_CONFIG_CONFLICT', str(e))
    except PreventionConfigurationUnavailable as e:
        return create_error_response(503, 'PREVENTION_CONFIG_UNAVAILABLE', str(e))
    except Exception as e:
        logger.error(f"Error in handle_prevention_status: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_prevention_config(event: Dict[str, Any]) -> Dict[str, Any]:
    """Save administrator-owned monitoring settings without enabling execution."""
    try:
        body = prepare_json_body(event)
        allowed = {'expected_version', 'budget_thresholds', 'enabled_services'}
        if set(body)-allowed or not ({'budget_thresholds', 'enabled_services'} & set(body)):
            raise ValueError('Supply thresholds and/or enabled_services with expected_version only')
        expected = body.get('expected_version')
        if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
            raise ValueError('expected_version must be a nonnegative integer from current status')
        if 'budget_thresholds' in body:
            thresholds = body['budget_thresholds']
            if not isinstance(thresholds, dict) or not thresholds or set(thresholds)-{'warning', 'action'}:
                raise ValueError('budget_thresholds supports warning and action only')
        engine = _get_prevention_engine()
        if expected != engine.config_version:
            raise PreventionConfigurationConflict('Monitoring configuration changed; refresh before retrying')
        engine.update_config({key: value for key, value in body.items() if key != 'expected_version'})
        return {'statusCode': 200, 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'success': True, 'message': 'Monitoring settings saved', 'status': engine.get_status()})}
    except PreventionConfigurationConflict as error:
        return create_error_response(409, 'PREVENTION_CONFIG_CONFLICT', str(error))
    except PreventionConfigurationUnavailable as error:
        return create_error_response(503, 'PREVENTION_CONFIG_UNAVAILABLE', str(error))
    except ValueError as error:
        return create_error_response(400, 'INVALID_PARAMETER', str(error))
    except Exception as error:
        logger.error('Monitoring settings save failed: %s', type(error).__name__)
        return create_error_response(500, 'MONITORING_CONFIG_ERROR', 'Monitoring settings could not be saved')


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
    
    except PreventionConfigurationConflict as e:
        return create_error_response(409, 'PREVENTION_CONFIG_CONFLICT', str(e))
    except PreventionConfigurationUnavailable as e:
        return create_error_response(503, 'PREVENTION_CONFIG_UNAVAILABLE', str(e))
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
    
    except PreventionConfigurationConflict as e:
        return create_error_response(409, 'PREVENTION_CONFIG_CONFLICT', str(e))
    except PreventionConfigurationUnavailable as e:
        return create_error_response(503, 'PREVENTION_CONFIG_UNAVAILABLE', str(e))
    except Exception as e:
        logger.error(f"Error in handle_prevention_disable: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_prevention_resource(event: Dict[str, Any]) -> Dict[str, Any]:
    """Direct scoped metadata read; no inventory persistence or resource operation."""
    try:
        from dataclasses import asdict
        from .services.request_query import single_valued_query
        params = single_valued_query(event, {'service', 'resource_id'}, maximum_value_length=128)
        service, identifier = params.get('service'), params.get('resource_id')
        ResourceManager.validate_inspection(service, identifier)
        engine = _get_prevention_engine()
        if service not in engine.config.get('enabled_services', []):
            return create_error_response(400, 'SERVICE_NOT_CONFIGURED', 'This service is not enabled for resource discovery')
        resource = engine.resource_manager.inspect_resource(service, identifier)
        body = json.dumps({'success': True, 'data_contract': 'resource_inspection_observations_v2',
            'resource': asdict(resource), 'observed_at': datetime.now(UTC).isoformat(),
            'applied_selection': {'service': service, 'resource_id': identifier},
            'data_quality': {'scope': 'one_direct_metadata_observation_not_inventory_or_eligibility',
                'account_scope_basis': 'configured_backend_account_not_independently_verified',
                'resource_membership_in_budget_verified': False, 'idle_evidence_included': False,
                'protected_tag_coverage_verified': False, 'monetary_cost': None,
                'action_eligibility': None, 'inventory_persistence_performed': False, 'resource_actions': 0}})
        if len(body.encode('utf-8')) > 256*1024:
            return create_error_response(413, 'INSPECTION_TOO_LARGE', 'Resource metadata exceeds the inspection response limit')
        return {'statusCode': 200, 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}, 'body': body}
    except ValueError as error:
        return create_error_response(400, 'INVALID_PARAMETER', str(error))
    except Exception as error:
        logger.warning('Resource inspection unavailable: %s', type(error).__name__)
        return create_error_response(503, 'RESOURCE_INSPECTION_UNAVAILABLE', 'The resource could not be observed in the configured account and SDK region')


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
        if not isinstance(query_params, dict) or set(query_params)-{'service', 'state'}:
            raise ValueError('Resource query supports service and state only')
        multiple = event.get('multiValueQueryStringParameters') or {}
        if any(not isinstance(values, list) or len(values) != 1 for values in multiple.values()):
            raise ValueError('Resource filters must occur once')
        if set(multiple)-{'service', 'state'}: raise ValueError('Unsupported resource query parameter')
        for name, values in multiple.items():
            query_params.setdefault(name, values[0])
        service = query_params.get('service')
        state = query_params.get('state')
        
        logger.info(f"Getting prevention resources: service={service}, state={state}")
        
        # Initialize prevention engine
        prevention_engine = _get_prevention_engine()
        
        # Build filters
        filters = {}
        if 'service' in query_params:
            filters['service'] = service
        if 'state' in query_params:
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
                'creation_date': r.creation_date, 'properties': r.properties
            }
            for r in resources
        ]
        
        response_data = {
            'success': True, 'resources': resources_data, 'count': len(resources_data),
            'result_scope': 'observed_inventory', 'inventory_completeness': 'unverified',
            'discovery_report': prevention_engine.resource_manager.last_discovery_report,
            'applied_filters': filters,
            'requested_service_configured': service in prevention_engine.config.get('enabled_services', []) if service is not None else None,
            'idle_evidence_included': False, 'active_idle_services': ['ec2', 'rds', 'lambda'],
            'coverage_note': 'Discovery failures can omit resources. A listed resource has not been classified as idle.'
        }
        response_body = json.dumps(response_data)
        if len(response_body.encode('utf-8')) > 2*1024*1024:
            return create_error_response(413, 'RESOURCE_LIST_TOO_LARGE', 'Resource inventory exceeds the response limit; narrow discovery configuration.')
        logger.info(f"Retrieved {len(resources)} resources")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': response_body
        }
    
    except ValueError as error:
        return create_error_response(400, 'INVALID_PARAMETER', str(error))
    except PreventionConfigurationConflict as e:
        return create_error_response(409, 'PREVENTION_CONFIG_CONFLICT', str(e))
    except PreventionConfigurationUnavailable as e:
        return create_error_response(503, 'PREVENTION_CONFIG_UNAVAILABLE', str(e))
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
            'statusCode': 202 if result['success'] else 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': result['success'],
                'action_id': result.get('action_id'),
                'resource_id': result.get('resource_id'),
                'status': result.get('status', 'failed'),
                'verification_status': result.get('verification_status', 'unverified'),
                'target_state': result.get('target_state'),
                'restored_state': None,
                'message': result.get('message'),
                'error': result.get('error')
            })
        }
    
    except PreventionConfigurationConflict as e:
        return create_error_response(409, 'PREVENTION_CONFIG_CONFLICT', str(e))
    except PreventionConfigurationUnavailable as e:
        return create_error_response(503, 'PREVENTION_CONFIG_UNAVAILABLE', str(e))
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
        from .services.request_query import single_valued_query
        query_params = single_valued_query(event, {'start_date', 'end_date', 'limit', 'cursor'})
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')
        limit_str = query_params.get('limit', '100')
        
        try:
            limit = int(limit_str)
        except (ValueError, TypeError):
            return create_error_response(
                400,
                'INVALID_PARAMETER',
                f'Invalid limit: {limit_str}. Must be an integer'
            )
        
        if not 1 <= limit <= 1000:
            return create_error_response(400, 'INVALID_PARAMETER', 'Limit must be 1-1000')

        logger.info(f"Getting prevention history: start={start_date}, end={end_date}, limit={limit}")

        from .services.prevention_history_cursor import decode_cursor, encode_cursor
        filters = {'start_date': start_date, 'end_date': end_date, 'limit': limit,
            'subject': (event.get('_principal') or {}).get('subject'),
            'account': os.environ.get('BACKEND_ACCOUNT_ID')}
        scan_start_key = decode_cursor(query_params['cursor'], filters) if query_params.get('cursor') else None
        prevention_engine = _get_prevention_engine()
        quality = {}
        history = prevention_engine.get_action_history(
            start_date=start_date,
            end_date=end_date,
            limit=limit, report=quality, scan_start_key=scan_start_key
        )

        next_key = quality.pop('next_scan_key', None)
        next_cursor = encode_cursor(next_key, filters) if next_key else None
        has_more = next_cursor is not None
        body = json.dumps({'success': True, 'history': history, 'count': len(history),
            'has_more': has_more, 'scope': 'bounded_audit_record_selection',
            'data_contract': 'prevention_history_observations_v2', 'data_quality': quality,
            'next_cursor': next_cursor, 'pagination_scope': 'scan_pages_not_snapshot_or_global_time_order'})
        if len(body.encode('utf-8')) > 2*1024*1024:
            return create_error_response(413, 'HISTORY_TOO_LARGE', 'Reduce the limit or narrow history dates')
        logger.info(f"Retrieved {len(history)} history records")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': body
        }
    
    except ValueError as error:
        return create_error_response(400, 'INVALID_PARAMETER', str(error))
    except PreventionConfigurationConflict as e:
        return create_error_response(409, 'PREVENTION_CONFIG_CONFLICT', str(e))
    except PreventionConfigurationUnavailable as e:
        return create_error_response(503, 'PREVENTION_CONFIG_UNAVAILABLE', str(e))
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
        user_id, session_id = advisor_identity(event, params.get('session_id', 'default'))
        
        if not query:
            return create_error_response(
                400,
                'MISSING_PARAMETER',
                'query is required'
            )
        
        if not isinstance(query, str) or not query.strip() or len(query) > 2000:
            return create_error_response(400, 'INVALID_PARAMETER', 'query must contain 1-2000 characters')

        logger.info(f"Processing advisor query: user={user_id}, session={session_id}")

        # Run advisor with timeout so we return 200 + message before API Gateway 29s limit (avoid 504)
        advisor_result = [None]
        advisor_error = [None]

        def run_advisor():
            try:
                advisor_engine = _get_advisor_engine()
                advisor_result[0] = advisor_engine.process_query(query, user_id, session_id)
            except Exception as e:
                advisor_error[0] = e

        thread = threading.Thread(target=run_advisor, daemon=True)
        thread.start()
        thread.join(timeout=25.0)
        if thread.is_alive():
            logger.warning("Advisor query timed out after 25s")
            return create_error_response(504, 'ADVISOR_TIMEOUT',
                'The advisor did not complete before the response deadline. Try again later. No durable background job was created.')
        if advisor_error[0] is not None:
            raise advisor_error[0]
        response = advisor_result[0]
        if response is None or getattr(response, 'status', 'available') == 'unavailable':
            return create_error_response(503, 'ADVISOR_UNAVAILABLE',
                'The advisor could not complete this request. Please try again later.')
        response_text = response.response_text
        if not isinstance(response_text, str) or not response_text.strip():
            return create_error_response(503, 'ADVISOR_UNAVAILABLE', 'The advisor returned no answer. Please try again later.')
        recommendations = getattr(response, 'recommendations', []) or []
        cost_data = getattr(response, 'cost_data', {}) or {}
        raw_confidence = getattr(response, 'confidence', None)
        confidence = float(raw_confidence) if raw_confidence is not None else None
        cached = getattr(response, 'cached', False)

        # Format response (never echo request params; always return advisor answer shape)
        response_data = {
            'success': True,
            'query': query,
            'response': response_text,
            'recommendations': [
                {
                    'action': getattr(rec, 'action', ''),
                    'rationale': getattr(rec, 'rationale', ''),
                    'estimated_savings': None, 'monetary_basis': 'unavailable_unverified_advice',
                    'priority': None, 'ranking_basis': 'unavailable',
                    'safe': None, 'safety_basis': 'unavailable_unverified_advice'
                }
                for rec in recommendations
            ],
            'cost_data': cost_data,
            'confidence': confidence,
            'confidence_method': 'unavailable',
            'cached': cached
        }

        logger.info(f"Query processed successfully: cached={cached}, recommendations={len(recommendations)}")

        # Never return a body that looks like the request (query/user_id/session_id only)
        if 'success' not in response_data or 'response' not in response_data:
            logger.error("Advisor response_data missing success/response")
            return create_error_response(
                500, 'INTERNAL_ERROR', 'Advisor response was malformed.', None
            )
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
        client_session_id = query_params.get('session_id', 'default')
        _, session_id = advisor_identity(event, client_session_id)
        
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
        # Parse query parameters (DELETE uses query params, not body)
        query_params = event.get('queryStringParameters') or {}
        client_session_id = query_params.get('session_id', 'default')
        _, session_id = advisor_identity(event, client_session_id)
        
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
                'session_id': client_session_id
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
        user_id, _ = advisor_identity(event)
        
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
                    'estimated_impact': float(insight.estimated_impact) if insight.estimated_impact is not None else None,
                    'method': insight.method, 'data_quality': insight.data_quality
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
    import boto3
    
    # Initialize DynamoDB client
    dynamodb_client = get_dynamodb_client()
    
    # Initialize Bedrock Runtime client
    bedrock_runtime_client = boto3.client('bedrock-runtime')
    
    # Initialize Phase 3 components for InsightGenerator integration
    # Create AWS clients for Phase 3
    aws_clients = {
        'ec2': boto3.client('ec2'),
        'rds': boto3.client('rds'),
        'lambda': boto3.client('lambda'),
        's3': boto3.client('s3'),
        'dynamodb': boto3.client('dynamodb'),
        'cloudwatch': boto3.client('cloudwatch'),
        'budgets': boto3.client('budgets')
    }
    
    resource_manager = ResourceManager(
        aws_clients=aws_clients,
        dynamodb_client=dynamodb_client
    )
    
    idle_detector = IdleDetector(
        cloudwatch_client=aws_clients.get('cloudwatch')
    )
    
    budget_monitor = BudgetMonitor(
        budgets_client=aws_clients.get('budgets'),
        cost_estimator=None  # Could pass CostEstimator if needed
    )
    
    # Initialize Phase 4 components
    query_processor = QueryProcessor()
    context_manager = ContextManager(
        cost_explorer_client=None,
        dynamodb_client=dynamodb_client
    )
    advisor_model_id = os.environ.get("ADVISOR_MODEL_ID", "amazon.nova-lite-v1:0")
    bedrock_advisor_client = BedrockAdvisorClient(
        bedrock_client=bedrock_runtime_client,
        model_id=advisor_model_id,
    )
    response_formatter = ResponseFormatter()
    cache_manager = AdvisorCacheManager(
        dynamodb_client=dynamodb_client
    )
    insight_generator = InsightGenerator(
        cost_explorer_client=None,
        dynamodb_client=dynamodb_client,
        resource_manager=resource_manager,
        idle_detector=idle_detector,
        budget_monitor=budget_monitor,
        budgets_client=aws_clients.get('budgets')
    )
    
    # Create advisor engine
    advisor_engine = AdvisorEngine(
        query_processor=query_processor,
        context_manager=context_manager,
        bedrock_client=bedrock_advisor_client,
        response_formatter=response_formatter,
        cache_manager=cache_manager,
        insight_generator=insight_generator,
        dynamodb_client=dynamodb_client
    )
    
    return advisor_engine


def _get_prevention_engine() -> PreventionEngine:
    """
    Initialize and return a PreventionEngine instance.
    
    Returns:
        Configured PreventionEngine instance
    """
    import boto3
    from .utils.types import NotificationConfig
    dynamodb_client = get_dynamodb_client()
    region = os.environ.get('AWS_REGION', 'us-east-1')
    clients = {service: boto3.client(service, region_name=region) for service in ('budgets', 'cloudwatch', 'ec2', 'rds', 'lambda', 'sns')}


    budget_monitor = BudgetMonitor(
        budgets_client=clients['budgets'],
        cost_estimator=None
    )

    resource_manager = ResourceManager(
        aws_clients={},
        dynamodb_client=dynamodb_client
    )

    idle_detector = IdleDetector(
        cloudwatch_client=clients['cloudwatch']
    )

    safety_guard = SafetyGuard(
        config=None
    )

    action_executor = ActionExecutor(
        aws_clients={key: clients[key] for key in ("ec2", "rds", "lambda")},
        audit_logger=None
    )

    approval_manager = ApprovalManager(
        sns_client=None,
        dynamodb_client=dynamodb_client
    )

    # Pass empty dict; RollbackManager creates EC2/RDS/Lambda clients only when execute_rollback runs
    rollback_manager = RollbackManager(
        aws_clients={},
        dynamodb_client=dynamodb_client
    )

    notification_service = NotificationService(
        sns_client=clients["sns"],
        config=NotificationConfig(warning_topic_arn=os.environ.get("SNS_TOPIC_WARNINGS"), action_topic_arn=os.environ.get("SNS_TOPIC_ACTIONS"), error_topic_arn=os.environ.get("SNS_TOPIC_ERRORS"))
    )

    prevention_engine = PreventionEngine(
        budget_monitor=budget_monitor,
        resource_manager=resource_manager,
        idle_detector=idle_detector,
        safety_guard=safety_guard,
        action_executor=action_executor,
        approval_manager=approval_manager,
        rollback_manager=rollback_manager,
        notification_service=notification_service,
        dynamodb_client=dynamodb_client
    )

    return prevention_engine
