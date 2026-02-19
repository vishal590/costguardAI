"""
AWS Lambda handler for Cost Data Pipeline.

This handler processes API Gateway requests to fetch and query AWS cost data.
"""
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from .services.cost_explorer import fetch_cost_data, CostExplorerParams
from .services.dynamodb import store_cost_data, query_cost_data
from .utils.types import QueryParams, ErrorResponse
from .utils.error_handler import format_error
from .utils.validation import validate_granularity
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
        
        # Extract HTTP method and path
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')
        
        # Route to appropriate handler
        if http_method == 'POST' and '/fetch' in path:
            return handle_fetch(event)
        elif http_method == 'GET' and path.endswith('/cost-data'):
            return handle_query(event)
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
