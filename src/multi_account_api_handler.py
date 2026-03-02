"""
AWS Lambda handler for Multi-Account Cost Management API.

This handler processes API Gateway requests for multi-account cost operations.
"""
import json
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime, UTC
from decimal import Decimal

from .services.multi_account.organization_discovery import OrganizationDiscoveryService
from .services.multi_account.cost_aggregation_engine import CostAggregationEngine
from .services.multi_account.per_account_cost_service import PerAccountCostService
from .services.multi_account.cost_allocation_engine import CostAllocationEngine
from .services.multi_account.allocation_rules_engine import AllocationRulesEngine
from .services.multi_account.organization_budget_service import OrganizationBudgetService
from .services.multi_account.repositories import (
    OrganizationRepository,
    AccountRepository,
    MultiAccountCostRepository,
    AllocationRuleRepository,
    BudgetRepository
)
from .services.multi_account.api_auth import authenticate_and_authorize, create_auth_error_response
from .services.multi_account.cloudwatch_metrics import get_metrics_service
from .services.dynamodb import get_dynamodb_client
from .utils.error_handler import format_error
from .utils.date_utils import validate_date_format, validate_date_range

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler function for Multi-Account Cost Management API.
    
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
    start_time = time.time()
    metrics_service = get_metrics_service()
    endpoint = event.get('path', 'unknown')
    
    try:
        # Log incoming event
        logger.info(f"Received multi-account API event: {json.dumps(event)}")
        
        # Authenticate and authorize request
        is_authorized, auth_error, user_context = authenticate_and_authorize(event)
        
        if not is_authorized:
            logger.warning(f"Authentication failed: {auth_error}")
            status_code = 401 if 'key' in auth_error.lower() or 'authentication' in auth_error.lower() else 429
            return create_auth_error_response(status_code, auth_error)
        
        logger.info(f"Request authenticated for user: {user_context['user_id']}")
        
        # Extract HTTP method and path
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')
        
        # Route to appropriate handler
        # Organization endpoints
        if http_method == 'GET' and path.endswith('/organizations'):
            response = handle_list_organizations(event)
        elif http_method == 'GET' and '/organizations/' in path and path.endswith('/accounts'):
            response = handle_list_accounts(event)
        
        # Cost endpoints
        elif http_method == 'GET' and path.endswith('/costs/consolidated'):
            response = handle_consolidated_costs(event)
        elif http_method == 'GET' and path.endswith('/costs/by-account'):
            response = handle_costs_by_account(event)
        elif http_method == 'GET' and '/costs/account/' in path:
            response = handle_account_costs(event)
        
        # Allocation endpoints
        elif http_method == 'GET' and path.endswith('/allocation/by-tag'):
            response = handle_allocation_by_tag(event)
        elif http_method == 'GET' and path.endswith('/allocation/unallocated'):
            response = handle_unallocated_costs(event)
        elif http_method == 'POST' and path.endswith('/allocation/rules'):
            response = handle_create_allocation_rule(event)
        
        # Budget endpoints
        elif http_method == 'GET' and path.endswith('/budgets/hierarchy'):
            response = handle_budget_hierarchy(event)
        elif http_method == 'POST' and path.endswith('/budgets/organization'):
            response = handle_create_organization_budget(event)
        elif http_method == 'POST' and '/budgets/ou/' in path:
            response = handle_create_ou_budget(event)
        
        else:
            response = create_error_response(
                400,
                'INVALID_REQUEST',
                f'Unsupported method {http_method} or path {path}'
            )
        
        # Record response time metric
        duration_ms = (time.time() - start_time) * 1000
        metrics_service.record_api_response_time(endpoint, duration_ms)
        
        return response
    
    except Exception as e:
        logger.error(f"Unhandled exception in multi-account API: {str(e)}", exc_info=True)
        
        # Record error and response time
        duration_ms = (time.time() - start_time) * 1000
        metrics_service.record_api_response_time(endpoint, duration_ms)
        metrics_service.record_lambda_error('MultiAccountAPIHandler', type(e).__name__)
        
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_list_organizations(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/organizations request to list all organizations.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
        
    Requirements: 16.1
    """
    try:
        logger.info("Listing organizations")
        
        # Initialize services
        org_service = _get_organization_service()
        
        # Get organizations
        organization = org_service.discover_organization()
        
        # Format response
        response_data = {
            'success': True,
            'organizations': [
                {
                    'organization_id': organization.id,
                    'master_account_id': organization.master_account_id,
                    'master_account_arn': organization.arn,
                    'feature_set': organization.feature_set
                }
            ],
            'count': 1
        }
        
        logger.info(f"Listed 1 organization")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        logger.error(f"Error in handle_list_organizations: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_list_accounts(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/organizations/{org_id}/accounts request to list accounts.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
        
    Requirements: 16.2
    """
    try:
        # Extract organization ID from path
        path = event.get('path', '')
        path_parts = path.split('/')
        
        org_id = None
        for i, part in enumerate(path_parts):
            if part == 'organizations' and i + 1 < len(path_parts):
                org_id = path_parts[i + 1]
                break
        
        if not org_id:
            return create_error_response(
                400,
                'MISSING_PARAMETER',
                'Organization ID is required in path'
            )
        
        logger.info(f"Listing accounts for organization: {org_id}")
        
        # Initialize services
        org_service = _get_organization_service()
        
        # Get accounts
        accounts = org_service.get_all_accounts(org_id)
        
        # Format response
        response_data = {
            'success': True,
            'organization_id': org_id,
            'accounts': [
                {
                    'account_id': acc.id,
                    'account_name': acc.name,
                    'email': acc.email,
                    'status': acc.status,
                    'joined_method': acc.joined_method,
                    'joined_timestamp': acc.joined_timestamp.isoformat() if acc.joined_timestamp else None
                }
                for acc in accounts
            ],
            'count': len(accounts)
        }
        
        logger.info(f"Listed {len(accounts)} accounts for organization {org_id}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        logger.error(f"Error in handle_list_accounts: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_consolidated_costs(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/costs/consolidated request to get consolidated costs.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
        
    Requirements: 16.3
    """
    try:
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')
        granularity = query_params.get('granularity', 'MONTHLY')
        
        # Validate date parameters
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
        
        if start_date and end_date and not validate_date_range(start_date, end_date):
            return create_error_response(
                400,
                'INVALID_DATE_RANGE',
                f'Start date {start_date} must be before or equal to end date {end_date}'
            )
        
        logger.info(f"Getting consolidated costs: start={start_date}, end={end_date}, granularity={granularity}")
        
        # Initialize services
        org_service = _get_organization_service()
        aggregation_engine = _get_cost_aggregation_engine()
        
        # Get organization and accounts
        organization = org_service.discover_organization()
        accounts = org_service.get_all_accounts(organization.id)
        account_ids = [acc.id for acc in accounts]
        
        # Get consolidated costs
        consolidated_costs = aggregation_engine.aggregate_organization_costs(
            org_id=organization.id,
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date
        )
        
        # Format response
        response_data = {
            'success': True,
            'consolidated_costs': {
                'total_cost': float(consolidated_costs.total_cost),
                'currency': 'USD',
                'period_start': consolidated_costs.start_date,
                'period_end': consolidated_costs.end_date,
                'granularity': granularity,
                'by_service': {
                    service: float(cost) 
                    for service, cost in consolidated_costs.costs_by_service.items()
                },
                'by_account': {
                    account: float(cost) 
                    for account, cost in consolidated_costs.costs_by_account.items()
                },
                'by_time_period': [
                    {
                        'period': period,
                        'cost': float(cost),
                        'currency': 'USD'
                    }
                    for period, cost in consolidated_costs.costs_by_day.items()
                ]
            },
            'timestamp': datetime.now(UTC).isoformat()
        }
        
        logger.info(f"Retrieved consolidated costs: ${float(consolidated_costs.total_cost):.2f}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        logger.error(f"Error in handle_consolidated_costs: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_costs_by_account(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/costs/by-account request to get per-account costs.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
        
    Requirements: 16.4
    """
    try:
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')
        
        logger.info(f"Getting costs by account: start={start_date}, end={end_date}")
        
        # Initialize services
        per_account_service = _get_per_account_cost_service()
        
        # Get all accounts first
        org_service = _get_organization_service()
        organization = org_service.discover_organization()
        accounts = org_service.get_all_accounts(organization.id)
        
        # Get costs for each account
        account_costs = []
        for account in accounts:
            costs = per_account_service.get_account_costs(
                account_id=account.id,
                start_date=start_date,
                end_date=end_date
            )
            
            account_costs.append({
                'account_id': account.id,
                'account_name': account.name,
                'total_cost': float(costs.total_cost),
                'currency': 'USD',
                'by_service': {
                    service: float(cost) 
                    for service, cost in costs.costs_by_service.items()
                },
                'period_start': costs.start_date,
                'period_end': costs.end_date
            })
        
        # Format response
        response_data = {
            'success': True,
            'account_costs': account_costs,
            'count': len(account_costs),
            'timestamp': datetime.now(UTC).isoformat()
        }
        
        logger.info(f"Retrieved costs for {len(account_costs)} accounts")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        logger.error(f"Error in handle_costs_by_account: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_account_costs(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/costs/account/{account_id} request to get costs for specific account.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
        
    Requirements: 16.5
    """
    try:
        # Extract account ID from path
        path = event.get('path', '')
        path_parts = path.split('/')
        
        account_id = None
        for i, part in enumerate(path_parts):
            if part == 'account' and i + 1 < len(path_parts):
                account_id = path_parts[i + 1]
                break
        
        if not account_id:
            return create_error_response(
                400,
                'MISSING_PARAMETER',
                'Account ID is required in path'
            )
        
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')
        
        logger.info(f"Getting costs for account {account_id}: start={start_date}, end={end_date}")
        
        # Initialize services
        per_account_service = _get_per_account_cost_service()
        
        # Get account costs
        costs = per_account_service.get_account_costs(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Format response
        response_data = {
            'success': True,
            'account_id': account_id,
            'costs': {
                'total_cost': float(costs.total_cost),
                'currency': 'USD',
                'period_start': costs.start_date,
                'period_end': costs.end_date,
                'by_service': {
                    service: float(cost) 
                    for service, cost in costs.costs_by_service.items()
                },
                'by_time_period': [
                    {
                        'period': period,
                        'cost': float(cost),
                        'currency': 'USD'
                    }
                    for period, cost in costs.costs_by_day.items()
                ]
            },
            'timestamp': datetime.now(UTC).isoformat()
        }
        
        logger.info(f"Retrieved costs for account {account_id}: ${float(costs.total_cost):.2f}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        logger.error(f"Error in handle_account_costs: {str(e)}", exc_info=True)
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


def _get_organization_service() -> OrganizationDiscoveryService:
    """Initialize and return OrganizationDiscoveryService."""
    dynamodb_client = get_dynamodb_client()
    
    return OrganizationDiscoveryService(
        dynamodb_client=dynamodb_client,
        organizations_client=None  # Will be initialized internally
    )


def _get_cost_aggregation_engine() -> CostAggregationEngine:
    """Initialize and return CostAggregationEngine."""
    dynamodb_client = get_dynamodb_client()
    cost_repo = MultiAccountCostRepository(dynamodb_client, 'costguard-multi-account-costs')
    account_repo = AccountRepository(dynamodb_client, 'costguard-accounts')
    org_repo = OrganizationRepository(dynamodb_client, 'costguard-organizations')
    
    return CostAggregationEngine(
        cost_repository=cost_repo,
        account_repository=account_repo,
        org_repository=org_repo
    )


def _get_per_account_cost_service() -> PerAccountCostService:
    """Initialize and return PerAccountCostService."""
    dynamodb_client = get_dynamodb_client()
    cost_repo = MultiAccountCostRepository(dynamodb_client, 'costguard-multi-account-costs')
    account_repo = AccountRepository(dynamodb_client, 'costguard-accounts')
    
    return PerAccountCostService(
        cost_repository=cost_repo,
        account_repository=account_repo
    )


def _get_cost_allocation_engine() -> CostAllocationEngine:
    """Initialize and return CostAllocationEngine."""
    dynamodb_client = get_dynamodb_client()
    cost_repo = MultiAccountCostRepository(dynamodb_client, 'costguard-multi-account-costs')
    rule_repo = AllocationRuleRepository(dynamodb_client, 'costguard-allocation-rules')
    
    return CostAllocationEngine(
        cost_repository=cost_repo,
        rule_repository=rule_repo
    )


def _get_allocation_rules_engine() -> AllocationRulesEngine:
    """Initialize and return AllocationRulesEngine."""
    dynamodb_client = get_dynamodb_client()
    rule_repo = AllocationRuleRepository(dynamodb_client, 'costguard-allocation-rules')
    
    return AllocationRulesEngine(rule_repository=rule_repo)


def _get_organization_budget_service() -> OrganizationBudgetService:
    """Initialize and return OrganizationBudgetService."""
    dynamodb_client = get_dynamodb_client()
    budget_repo = BudgetRepository(dynamodb_client, 'costguard-budgets')
    account_repo = AccountRepository(dynamodb_client, 'costguard-accounts')
    cost_repo = MultiAccountCostRepository(dynamodb_client, 'costguard-multi-account-costs')
    
    return OrganizationBudgetService(
        budget_repository=budget_repo,
        account_repository=account_repo,
        cost_repository=cost_repo
    )


def handle_allocation_by_tag(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/allocation/by-tag request to get allocated costs by tag.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
        
    Requirements: 16.6
    """
    try:
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        tag_key = query_params.get('tag_key', 'Team')
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')
        
        logger.info(f"Getting allocation by tag {tag_key}: start={start_date}, end={end_date}")
        
        # Initialize services
        allocation_engine = _get_cost_allocation_engine()
        org_service = _get_organization_service()
        
        # Get organization and accounts
        organization = org_service.discover_organization()
        accounts = org_service.get_all_accounts(organization.id)
        account_ids = [acc.id for acc in accounts]
        
        # Get allocated costs by team (using Team tag as example)
        if tag_key == 'Team':
            team_costs = allocation_engine.get_allocation_by_team(
                org_id=organization.id,
                account_ids=account_ids,
                start_date=start_date,
                end_date=end_date
            )
            allocated_costs = {
                team: {
                    'total_cost': float(cost),
                    'currency': 'USD',
                    'by_service': {},  # Simplified for now
                    'by_account': {}   # Simplified for now
                }
                for team, cost in team_costs.items()
            }
        else:
            # For other tags, return empty for now
            allocated_costs = {}
        
        # Format response
        response_data = {
            'success': True,
            'tag_key': tag_key,
            'allocated_costs': allocated_costs,
            'period_start': start_date,
            'period_end': end_date,
            'timestamp': datetime.now(UTC).isoformat()
        }
        
        logger.info(f"Retrieved allocation by tag {tag_key}: {len(allocated_costs)} values")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        logger.error(f"Error in handle_allocation_by_tag: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_unallocated_costs(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/allocation/unallocated request to get unallocated costs.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
        
    Requirements: 16.7
    """
    try:
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')
        
        logger.info(f"Getting unallocated costs: start={start_date}, end={end_date}")
        
        # Initialize services
        allocation_engine = _get_cost_allocation_engine()
        org_service = _get_organization_service()
        
        # Get organization to get account IDs
        organization = org_service.discover_organization()
        accounts = org_service.get_all_accounts(organization.id)
        
        # Calculate unallocated costs for all accounts
        # For now, use first account as example (should aggregate across all accounts)
        account_id = accounts[0].id if accounts else None
        
        if not account_id:
            return create_error_response(
                404,
                'NO_ACCOUNTS',
                'No accounts found in organization'
            )
        
        # Get unallocated costs
        unallocated_costs = allocation_engine.calculate_unallocated_costs(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Format response
        response_data = {
            'success': True,
            'unallocated_costs': {
                'total_cost': float(unallocated_costs.total_cost),
                'currency': unallocated_costs.currency,
                'percentage_of_total': float(unallocated_costs.percentage_of_total),
                'by_service': {
                    service: float(cost) 
                    for service, cost in unallocated_costs.by_service.items()
                },
                'by_account': {
                    account: float(cost) 
                    for account, cost in unallocated_costs.by_account.items()
                },
                'untagged_resources': [
                    {
                        'resource_id': resource.resource_id,
                        'service': resource.service,
                        'account_id': resource.account_id,
                        'cost': float(resource.cost),
                        'currency': resource.currency
                    }
                    for resource in unallocated_costs.untagged_resources
                ]
            },
            'period_start': start_date,
            'period_end': end_date,
            'timestamp': datetime.now(UTC).isoformat()
        }
        
        logger.info(f"Retrieved unallocated costs: ${float(unallocated_costs.total_cost):.2f} ({float(unallocated_costs.percentage_of_total):.1f}%)")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        logger.error(f"Error in handle_unallocated_costs: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_create_allocation_rule(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/allocation/rules request to create allocation rules.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
        
    Requirements: 16.8
    """
    try:
        # Parse request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            params = json.loads(body) if body else {}
        else:
            params = body
        
        rule_name = params.get('rule_name')
        rule_type = params.get('rule_type')
        conditions = params.get('conditions', {})
        allocation_target = params.get('allocation_target')
        priority = params.get('priority', 100)
        
        if not rule_name:
            return create_error_response(
                400,
                'MISSING_PARAMETER',
                'rule_name is required'
            )
        
        if not rule_type:
            return create_error_response(
                400,
                'MISSING_PARAMETER',
                'rule_type is required'
            )
        
        if not allocation_target:
            return create_error_response(
                400,
                'MISSING_PARAMETER',
                'allocation_target is required'
            )
        
        logger.info(f"Creating allocation rule: {rule_name} (type: {rule_type})")
        
        # Initialize services
        rules_engine = _get_allocation_rules_engine()
        org_service = _get_organization_service()
        
        # Get organization ID
        organization = org_service.discover_organization()
        
        # Create allocation rule
        rule = rules_engine.create_rule(
            org_id=organization.id,
            name=rule_name,
            priority=priority,
            rule_type=rule_type,
            conditions=conditions,
            allocation_target=allocation_target
        )
        
        # Format response
        response_data = {
            'success': True,
            'rule': {
                'rule_id': rule.rule_id,
                'rule_name': rule.name,
                'rule_type': rule.rule_type,
                'conditions': rule.conditions,
                'allocation_target': rule.allocation_target,
                'priority': rule.priority
            },
            'message': 'Allocation rule created successfully'
        }
        
        logger.info(f"Created allocation rule: {rule.rule_id}")
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        logger.error(f"Error in handle_create_allocation_rule: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_budget_hierarchy(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/budgets/hierarchy request to get budget hierarchy.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
        
    Requirements: 16.9
    """
    try:
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        date = query_params.get('date', datetime.now(UTC).strftime('%Y-%m-%d'))
        
        logger.info(f"Getting budget hierarchy for date: {date}")
        
        # Initialize services
        budget_service = _get_organization_budget_service()
        org_service = _get_organization_service()
        
        # Get organization ID
        organization = org_service.discover_organization()
        
        # Get budget hierarchy
        hierarchy = budget_service.get_budget_hierarchy(
            org_id=organization.id,
            date=date
        )
        
        # Format response
        response_data = {
            'success': True,
            'budget_hierarchy': {
                'organization': {
                    'budget_id': hierarchy.organization_budget.budget_id if hierarchy.organization_budget else None,
                    'budget_name': hierarchy.organization_budget.budget_name if hierarchy.organization_budget else None,
                    'budget_limit': float(hierarchy.organization_budget.budget_limit) if hierarchy.organization_budget else None,
                    'actual_spend': float(hierarchy.organization_budget.actual_spend) if hierarchy.organization_budget else None,
                    'forecasted_spend': float(hierarchy.organization_budget.forecasted_spend) if hierarchy.organization_budget else None,
                    'utilization_percentage': float(hierarchy.organization_budget.utilization_percentage) if hierarchy.organization_budget else None,
                    'currency': hierarchy.organization_budget.currency if hierarchy.organization_budget else 'USD'
                },
                'organizational_units': [
                    {
                        'ou_id': ou_budget.ou_id,
                        'ou_name': ou_budget.ou_name,
                        'budget_id': ou_budget.budget_id,
                        'budget_name': ou_budget.budget_name,
                        'budget_limit': float(ou_budget.budget_limit),
                        'actual_spend': float(ou_budget.actual_spend),
                        'forecasted_spend': float(ou_budget.forecasted_spend),
                        'utilization_percentage': float(ou_budget.utilization_percentage),
                        'currency': ou_budget.currency,
                        'accounts': [
                            {
                                'account_id': acc_budget.account_id,
                                'account_name': acc_budget.account_name,
                                'budget_id': acc_budget.budget_id,
                                'budget_name': acc_budget.budget_name,
                                'budget_limit': float(acc_budget.budget_limit),
                                'actual_spend': float(acc_budget.actual_spend),
                                'forecasted_spend': float(acc_budget.forecasted_spend),
                                'utilization_percentage': float(acc_budget.utilization_percentage),
                                'currency': acc_budget.currency
                            }
                            for acc_budget in ou_budget.account_budgets
                        ]
                    }
                    for ou_budget in hierarchy.ou_budgets
                ]
            },
            'timestamp': datetime.now(UTC).isoformat()
        }
        
        logger.info(f"Retrieved budget hierarchy: {len(hierarchy.ou_budgets)} OUs")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        logger.error(f"Error in handle_budget_hierarchy: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_create_organization_budget(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/budgets/organization request to create organization budget.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
        
    Requirements: 16.9
    """
    try:
        # Parse request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            params = json.loads(body) if body else {}
        else:
            params = body
        
        budget_name = params.get('budget_name')
        budget_limit = params.get('budget_limit')
        time_unit = params.get('time_unit', 'MONTHLY')
        currency = params.get('currency', 'USD')
        
        if not budget_name:
            return create_error_response(
                400,
                'MISSING_PARAMETER',
                'budget_name is required'
            )
        
        if not budget_limit:
            return create_error_response(
                400,
                'MISSING_PARAMETER',
                'budget_limit is required'
            )
        
        try:
            budget_limit = float(budget_limit)
        except (ValueError, TypeError):
            return create_error_response(
                400,
                'INVALID_PARAMETER',
                'budget_limit must be a number'
            )
        
        logger.info(f"Creating organization budget: {budget_name} (${budget_limit})")
        
        # Initialize services
        budget_service = _get_organization_budget_service()
        org_service = _get_organization_service()
        
        # Get organization ID
        organization = org_service.discover_organization()
        
        # Create organization budget
        budget_id = budget_service.create_organization_budget(
            org_id=organization.id,
            budget_amount=Decimal(str(budget_limit)),
            period=time_unit
        )
        
        # Format response
        response_data = {
            'success': True,
            'budget': {
                'budget_id': budget_id,
                'budget_name': budget_name,
                'budget_limit': float(budget_limit),
                'time_unit': time_unit,
                'currency': currency,
                'created_at': datetime.now(UTC).isoformat(),
                'is_active': True
            },
            'message': 'Organization budget created successfully'
        }
        
        logger.info(f"Created organization budget: {budget.budget_id}")
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        logger.error(f"Error in handle_create_organization_budget: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_create_ou_budget(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/budgets/ou/{ou_id} request to create OU budget.
    
    Args:
        event: Lambda event
        
    Returns:
        Response dict with status code and body
        
    Requirements: 16.9
    """
    try:
        # Extract OU ID from path
        path = event.get('path', '')
        path_parts = path.split('/')
        
        ou_id = None
        for i, part in enumerate(path_parts):
            if part == 'ou' and i + 1 < len(path_parts):
                ou_id = path_parts[i + 1]
                break
        
        if not ou_id:
            return create_error_response(
                400,
                'MISSING_PARAMETER',
                'OU ID is required in path'
            )
        
        # Parse request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            params = json.loads(body) if body else {}
        else:
            params = body
        
        budget_name = params.get('budget_name')
        budget_limit = params.get('budget_limit')
        time_unit = params.get('time_unit', 'MONTHLY')
        currency = params.get('currency', 'USD')
        
        if not budget_name:
            return create_error_response(
                400,
                'MISSING_PARAMETER',
                'budget_name is required'
            )
        
        if not budget_limit:
            return create_error_response(
                400,
                'MISSING_PARAMETER',
                'budget_limit is required'
            )
        
        try:
            budget_limit = float(budget_limit)
        except (ValueError, TypeError):
            return create_error_response(
                400,
                'INVALID_PARAMETER',
                'budget_limit must be a number'
            )
        
        logger.info(f"Creating OU budget for {ou_id}: {budget_name} (${budget_limit})")
        
        # Initialize services
        budget_service = _get_organization_budget_service()
        
        # Create OU budget
        budget_id = budget_service.create_ou_budget(
            ou_id=ou_id,
            budget_amount=Decimal(str(budget_limit)),
            period=time_unit
        )
        
        # Format response
        response_data = {
            'success': True,
            'budget': {
                'budget_id': budget_id,
                'budget_name': budget_name,
                'ou_id': ou_id,
                'budget_limit': float(budget_limit),
                'time_unit': time_unit,
                'currency': currency,
                'created_at': datetime.now(UTC).isoformat(),
                'is_active': True
            },
            'message': f'OU budget created successfully for {ou_id}'
        }
        
        logger.info(f"Created OU budget: {budget_id}")
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        logger.error(f"Error in handle_create_ou_budget: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )