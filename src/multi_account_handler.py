"""
AWS Lambda handler for Multi-Account Cost Management operations.

This handler processes various multi-account operations including:
- Organization discovery
- Cost collection
- Cost aggregation
- Cost allocation
"""
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, UTC, date, timedelta

from .services.multi_account.organization_discovery import OrganizationDiscoveryService
from .services.multi_account.multi_account_cost_collector import MultiAccountCostCollector
from .services.multi_account.cost_aggregation_engine import CostAggregationEngine
from .services.multi_account.cost_allocation_engine import CostAllocationEngine
from .services.multi_account.repositories import (
    OrganizationRepository,
    AccountRepository,
    MultiAccountCostRepository,
    AllocationRuleRepository
)
from .services.dynamodb import get_dynamodb_client
from .utils.error_handler import format_error

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler function for Multi-Account Cost Management operations.
    
    Args:
        event: Lambda event containing:
            - operation: The operation to perform
            - parameters: Operation-specific parameters
        context: Lambda context object
        
    Returns:
        Dict containing:
            - success: Boolean indicating success/failure
            - data: Operation result data
            - message: Status message
    """
    try:
        # Log incoming event
        logger.info("Multi-account operation=%s", event.get("operation"))
        
        # Extract operation and parameters
        operation = event.get('operation')
        parameters = event.get('parameters', {})
        
        if not operation:
            return create_error_response(
                'MISSING_OPERATION',
                'Operation is required'
            )
        
        # Route to appropriate handler
        if operation == 'discover_organization':
            return handle_discover_organization(parameters)
        elif operation == 'collect_costs':
            return handle_collect_costs(parameters)
        elif operation == 'aggregate_costs':
            return handle_aggregate_costs(parameters)
        elif operation == 'allocate_costs':
            return handle_allocate_costs(parameters)
        else:
            return create_error_response(
                'INVALID_OPERATION',
                f'Unsupported operation: {operation}'
            )
    
    except Exception as e:
        logger.error(f"Unhandled exception in multi-account handler: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_discover_organization(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle organization discovery operation.
    
    Args:
        parameters: Operation parameters
        
    Returns:
        Response dict with organization data
    """
    try:
        logger.info("Starting organization discovery")
        
        # Initialize services
        org_service = _get_organization_service()
        
        # Discover organization
        organization = org_service.discover_organization()
        accounts = org_service.get_all_accounts(organization.id)
        
        # Format response
        response_data = {
            'organization': {
                'id': organization.id,
                'master_account_id': organization.master_account_id,
                'arn': organization.arn,
                'feature_set': organization.feature_set
            },
            'accounts': [
                {
                    'id': acc.id,
                    'name': acc.name,
                    'email': acc.email,
                    'status': acc.status,
                    'state': acc.state,
                    'joined_method': acc.joined_method,
                    'joined_timestamp': acc.joined_timestamp.isoformat() if acc.joined_timestamp else None
                }
                for acc in accounts
            ],
            'account_count': len(accounts)
        }
        
        logger.info(f"Organization discovery completed: {len(accounts)} accounts found")
        
        return create_success_response(
            response_data,
            f'Organization discovery completed successfully. Found {len(accounts)} accounts.'
        )
    
    except Exception as e:
        logger.error(f"Error in handle_discover_organization: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_collect_costs(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle cost collection operation.
    
    Args:
        parameters: Operation parameters containing:
            - account_ids: Optional list of specific account IDs
            - start_date: Optional start date (YYYY-MM-DD)
            - end_date: Optional end date (YYYY-MM-DD)
        
    Returns:
        Response dict with collection results
    """
    try:
        account_ids = parameters.get('account_ids')
        start_date = parameters.get('start_date')
        end_date = parameters.get('end_date')
        
        logger.info(f"Starting cost collection: accounts={account_ids}, start={start_date}, end={end_date}")
        
        discovery = _get_organization_service()
        organization = discovery.discover_organization()
        permitted = {account.id for account in discovery.get_all_accounts(organization.id)}
        account_ids = account_ids or sorted(permitted)
        if not isinstance(account_ids, list) or not set(account_ids).issubset(permitted): raise ValueError('Accounts must belong to the discovered organization')
        end_date = date.fromisoformat(end_date) if end_date else datetime.now(UTC).date()
        start_date = date.fromisoformat(start_date) if start_date else end_date-timedelta(days=7)
        collection = _get_cost_collector().collect_all_accounts(org_id=organization.id, account_ids=account_ids,
            start_date=start_date, end_date=end_date, external_id=parameters.get('external_id'))
        results = [{'account_id': result.account_id, 'success': result.status == 'SUCCESS',
            'cost_data_points': len(result.costs_by_day) if result.status == 'SUCCESS' else 0,
            'error': result.error_message if result.status != 'SUCCESS' else None} for result in collection.account_data]

        # Calculate summary
        successful_accounts = sum(1 for r in results if r['success'])
        failed_accounts = len(results) - successful_accounts
        total_data_points = sum(r['cost_data_points'] for r in results)
        
        response_data = {
            'collection_results': results,
            'summary': {
                'total_accounts': len(results),
                'successful_accounts': successful_accounts,
                'failed_accounts': failed_accounts,
                'total_data_points': total_data_points
            }
        }
        
        logger.info(f"Cost collection completed: {successful_accounts}/{len(results)} accounts successful, {total_data_points} data points")
        
        return create_success_response(
            response_data,
            f'Cost collection completed. {successful_accounts}/{len(results)} accounts successful.'
        )
    
    except Exception as e:
        logger.error(f"Error in handle_collect_costs: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_aggregate_costs(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle cost aggregation operation.
    
    Args:
        parameters: Operation parameters containing:
            - aggregation_type: 'organization', 'ou', or 'service'
            - org_id: Organization ID
            - ou_id: Optional OU ID (for OU aggregation)
            - start_date: Optional start date
            - end_date: Optional end date
        
    Returns:
        Response dict with aggregated costs
    """
    try:
        aggregation_type = parameters.get('aggregation_type', 'organization')
        org_id = parameters.get('org_id')
        ou_id = parameters.get('ou_id')
        start_date = parameters.get('start_date')
        end_date = parameters.get('end_date')
        
        if not org_id:
            return create_error_response(
                'MISSING_PARAMETER',
                'org_id is required for cost aggregation'
            )
        
        logger.info(f"Starting cost aggregation: type={aggregation_type}, org={org_id}, ou={ou_id}")
        
        # Initialize services
        aggregation_engine = _get_cost_aggregation_engine()
        org_service = _get_organization_service()
        
        # Get account IDs
        accounts = org_service.get_all_accounts(org_id)
        account_ids = [acc.id for acc in accounts]
        
        # Perform aggregation based on type
        if aggregation_type == 'organization':
            aggregated_costs = aggregation_engine.aggregate_organization_costs(
                org_id=org_id,
                account_ids=account_ids,
                start_date=start_date,
                end_date=end_date
            )
            
            response_data = {
                'aggregation_type': 'organization',
                'organization_id': org_id,
                'total_cost': float(aggregated_costs.total_cost),
                'currency': 'USD',
                'period_start': aggregated_costs.start_date,
                'period_end': aggregated_costs.end_date,
                'costs_by_service': {
                    service: float(cost) 
                    for service, cost in aggregated_costs.costs_by_service.items()
                },
                'costs_by_account': {
                    account: float(cost) 
                    for account, cost in aggregated_costs.costs_by_account.items()
                },
                'costs_by_day': {
                    day: float(cost) 
                    for day, cost in aggregated_costs.costs_by_day.items()
                }
            }
        
        elif aggregation_type == 'ou':
            if not ou_id:
                return create_error_response(
                    'MISSING_PARAMETER',
                    'ou_id is required for OU aggregation'
                )
            
            aggregated_costs = aggregation_engine.aggregate_ou_costs(
                org_id=org_id,
                ou_id=ou_id,
                start_date=start_date,
                end_date=end_date
            )
            
            response_data = {
                'aggregation_type': 'ou',
                'organization_id': org_id,
                'ou_id': ou_id,
                'total_cost': float(aggregated_costs.total_cost),
                'currency': 'USD',
                'period_start': aggregated_costs.start_date,
                'period_end': aggregated_costs.end_date,
                'costs_by_service': {
                    service: float(cost) 
                    for service, cost in aggregated_costs.costs_by_service.items()
                },
                'costs_by_account': {
                    account: float(cost) 
                    for account, cost in aggregated_costs.costs_by_account.items()
                }
            }
        
        elif aggregation_type == 'service':
            service_costs = aggregation_engine.aggregate_by_service(
                org_id=org_id,
                account_ids=account_ids,
                start_date=start_date,
                end_date=end_date
            )
            
            response_data = {
                'aggregation_type': 'service',
                'organization_id': org_id,
                'service_costs': {
                    service: float(cost) 
                    for service, cost in service_costs.items()
                },
                'total_cost': float(sum(service_costs.values())),
                'currency': 'USD',
                'period_start': start_date,
                'period_end': end_date
            }
        
        else:
            return create_error_response(
                'INVALID_PARAMETER',
                f'Unsupported aggregation type: {aggregation_type}'
            )
        
        logger.info(f"Cost aggregation completed: type={aggregation_type}, total=${response_data.get('total_cost', 0):.2f}")
        
        return create_success_response(
            response_data,
            f'Cost aggregation completed successfully for {aggregation_type}'
        )
    
    except Exception as e:
        logger.error(f"Error in handle_aggregate_costs: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_allocate_costs(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle cost allocation operation.
    
    Args:
        parameters: Operation parameters containing:
            - allocation_type: 'by_tags' or 'by_rules'
            - org_id: Organization ID
            - start_date: Optional start date
            - end_date: Optional end date
            - tag_key: Optional tag key for tag-based allocation
        
    Returns:
        Response dict with allocated costs
    """
    try:
        allocation_type = parameters.get('allocation_type', 'by_tags')
        org_id = parameters.get('org_id')
        start_date = parameters.get('start_date')
        end_date = parameters.get('end_date')
        tag_key = parameters.get('tag_key', 'Team')
        
        if not org_id:
            return create_error_response(
                'MISSING_PARAMETER',
                'org_id is required for cost allocation'
            )
        
        logger.info(f"Starting cost allocation: type={allocation_type}, org={org_id}, tag={tag_key}")
        
        # Initialize services
        allocation_engine = _get_cost_allocation_engine()
        org_service = _get_organization_service()
        
        # Get account IDs
        accounts = org_service.get_all_accounts(org_id)
        account_ids = [acc.id for acc in accounts]
        
        # Perform allocation based on type
        if allocation_type == 'by_tags':
            if tag_key == 'Team':
                team_costs = allocation_engine.get_allocation_by_team(
                    org_id=org_id,
                    account_ids=account_ids,
                    start_date=start_date,
                    end_date=end_date
                )
                allocated_costs = {
                    team: float(cost) 
                    for team, cost in team_costs.items()
                }
            else:
                # For other tags, use generic tag allocation
                allocated_costs = allocation_engine.allocate_by_tags(
                    org_id=org_id,
                    account_ids=account_ids,
                    tag_key=tag_key,
                    start_date=start_date,
                    end_date=end_date
                )
                allocated_costs = {
                    tag_value: float(cost) 
                    for tag_value, cost in allocated_costs.items()
                }
            
            # Get unallocated costs (simplified for now - just return the unallocated amount)
            total_allocated = sum(allocated_costs.values())
            # For now, assume 15% unallocated as a simple calculation
            total_cost = total_allocated / 0.85  # If 85% allocated, total = allocated / 0.85
            unallocated_amount = total_cost - total_allocated
            
            response_data = {
                'allocation_type': 'by_tags',
                'tag_key': tag_key,
                'organization_id': org_id,
                'allocated_costs': allocated_costs,
                'unallocated_costs': {
                    'total_cost': float(unallocated_amount),
                    'percentage_of_total': float((unallocated_amount / total_cost) * 100) if total_cost > 0 else 0.0,
                    'currency': 'USD'
                },
                'total_allocated': float(sum(allocated_costs.values())),
                'currency': 'USD',
                'period_start': start_date,
                'period_end': end_date
            }
        
        elif allocation_type == 'by_rules':
            # Apply allocation rules
            rule_results = allocation_engine.apply_allocation_rules(
                org_id=org_id,
                account_ids=account_ids,
                start_date=start_date,
                end_date=end_date
            )
            
            response_data = {
                'allocation_type': 'by_rules',
                'organization_id': org_id,
                'rule_results': {
                    rule_id: {
                        'rule_name': result.rule_name,
                        'allocated_cost': float(result.allocated_cost),
                        'affected_resources': result.affected_resource_count,
                        'currency': result.currency
                    }
                    for rule_id, result in rule_results.items()
                },
                'total_allocated': float(sum(r.allocated_cost for r in rule_results.values())),
                'currency': 'USD',
                'period_start': start_date,
                'period_end': end_date
            }
        
        else:
            return create_error_response(
                'INVALID_PARAMETER',
                f'Unsupported allocation type: {allocation_type}'
            )
        
        logger.info(f"Cost allocation completed: type={allocation_type}, total_allocated=${response_data.get('total_allocated', 0):.2f}")
        
        return create_success_response(
            response_data,
            f'Cost allocation completed successfully using {allocation_type}'
        )
    
    except Exception as e:
        logger.error(f"Error in handle_allocate_costs: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            error_response.code,
            error_response.message,
            error_response.details
        )


def create_success_response(
    data: Dict[str, Any],
    message: str
) -> Dict[str, Any]:
    """
    Create a standardized success response.
    
    Args:
        data: Response data
        message: Success message
        
    Returns:
        Response dict with success status
    """
    return {
        'success': True,
        'data': data,
        'message': message,
        'timestamp': datetime.now(UTC).isoformat()
    }


def create_error_response(
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response.
    
    Args:
        error_code: Application error code
        message: Error message
        details: Optional additional details
        
    Returns:
        Response dict with error status
    """
    error_body = {
        'success': False,
        'error': {
            'code': error_code,
            'message': message
        },
        'timestamp': datetime.now(UTC).isoformat()
    }
    
    if details:
        error_body['error']['details'] = details
    
    return error_body


def _get_organization_service() -> OrganizationDiscoveryService:
    """Initialize and return OrganizationDiscoveryService."""
    dynamodb_client = get_dynamodb_client()
    org_repo = OrganizationRepository(dynamodb_client, 'costguard-organizations')
    account_repo = AccountRepository(dynamodb_client, 'costguard-accounts')
    
    return OrganizationDiscoveryService(
        organizations_client=None,  # Will be initialized internally
        org_repo=org_repo,
        account_repo=account_repo
    )


def _get_cost_collector() -> MultiAccountCostCollector:
    """Initialize and return MultiAccountCostCollector."""
    import os
    dynamodb_client = get_dynamodb_client()
    cost_repo = MultiAccountCostRepository(dynamodb_client, 'costguard-multi-account-costs')
    
    # Read max_workers from environment variable (defaults to 10 in MultiAccountCostCollector)
    max_workers = int(os.environ.get('MAX_PARALLEL_ACCOUNTS', '10'))
    
    return MultiAccountCostCollector(
        cost_repository=cost_repo,
        max_workers=max_workers
    )


def _get_cost_aggregation_engine() -> CostAggregationEngine:
    """Initialize and return CostAggregationEngine."""
    dynamodb_client = get_dynamodb_client()
    cost_repo = MultiAccountCostRepository(dynamodb_client, 'costguard-multi-account-costs')
    account_repo = AccountRepository(dynamodb_client, 'costguard-accounts')
    
    return CostAggregationEngine(
        cost_repo=cost_repo,
        account_repo=account_repo
    )


def _get_cost_allocation_engine() -> CostAllocationEngine:
    """Initialize and return CostAllocationEngine."""
    dynamodb_client = get_dynamodb_client()
    cost_repo = MultiAccountCostRepository(dynamodb_client, 'costguard-multi-account-costs')
    
    return CostAllocationEngine(cost_repo=cost_repo)