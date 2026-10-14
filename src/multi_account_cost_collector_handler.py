"""
Multi-Account Cost Collector Lambda Handler

This Lambda function is triggered daily by EventBridge to collect cost data
from all accounts in the AWS Organization.
"""
import json
import logging
import os
from datetime import date, timedelta
from typing import Dict, Any

from src.services.multi_account.organization_discovery import OrganizationDiscoveryService
from src.services.multi_account.multi_account_cost_collector import MultiAccountCostCollector

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for multi-account cost collection.
    
    Triggered daily by EventBridge to:
    1. Discover all accounts in the organization
    2. Collect cost data from each account in parallel
    3. Store results in DynamoDB
    
    Args:
        event: EventBridge event (scheduled event)
        context: Lambda context
        
    Returns:
        Response with collection summary
    """
    try:
        logger.info("Starting multi-account cost collection")
        logger.info("Cost collection invocation received")
        
        # Get configuration from environment variables
        org_id = os.environ.get('ORGANIZATION_ID')
        external_id = os.environ.get('EXTERNAL_ID')
        days_to_collect = int(os.environ.get('DAYS_TO_COLLECT', '7'))
        
        if not org_id:
            org_id = OrganizationDiscoveryService().discover_organization().id
        
        # Calculate date range
        end_date = date.today()
        start_date = end_date - timedelta(days=days_to_collect)
        
        logger.info(f"Collecting costs from {start_date} to {end_date}")
        
        # Discover organization accounts
        logger.info("Discovering organization accounts")
        discovery_service = OrganizationDiscoveryService()
        
        try:
            org_data = discovery_service.discover_organization()
            if org_data.id != org_id: raise ValueError('Configured organization differs from discovered organization')
            account_ids = [acc.id for acc in discovery_service.get_all_accounts(org_id)]
            
            logger.info(f"Found {len(account_ids)} accounts in organization")
            
        except Exception as e:
            logger.error(f"Failed to discover organization: {e}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Failed to discover organization',
                    'message': str(e)
                })
            }
        
        # Collect costs from all accounts
        logger.info(f"Starting cost collection for {len(account_ids)} accounts")
        
        # Read max_workers from environment variable (defaults to 10 in MultiAccountCostCollector)
        max_workers = int(os.environ.get('MAX_PARALLEL_ACCOUNTS', '10'))
        logger.info(f"Using max_workers={max_workers} for parallel collection")
        
        collector = MultiAccountCostCollector(max_workers=max_workers)
        
        try:
            result = collector.collect_all_accounts(
                org_id=org_id,
                account_ids=account_ids,
                start_date=start_date,
                end_date=end_date
            )
            
            # Log summary
            logger.info(
                f"Cost collection completed: "
                f"{result.successful}/{result.total_accounts} successful, "
                f"{result.failed} failed, "
                f"duration: {result.collection_duration:.2f}s"
            )
            
            if result.failed > 0:
                logger.warning(f"Failed accounts: {result.failed_accounts}")
            
            # Calculate total costs
            total_cost = sum(
                data.total_cost 
                for data in result.account_data 
                if data.status == 'SUCCESS'
            )
            
            # Return success response
            response = {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Cost collection completed',
                    'summary': {
                        'total_accounts': result.total_accounts,
                        'successful': result.successful,
                        'failed': result.failed,
                        'failed_accounts': result.failed_accounts,
                        'collection_duration_seconds': round(result.collection_duration, 2),
                        'total_cost': float(total_cost),
                        'date_range': {
                            'start': start_date.isoformat(),
                            'end': end_date.isoformat()
                        }
                    }
                })
            }
            
            # If more than 20% of accounts failed, return warning status
            if result.failed > 0 and (result.failed / result.total_accounts) > 0.2:
                logger.warning(
                    f"High failure rate: {result.failed}/{result.total_accounts} "
                    f"({result.failed / result.total_accounts * 100:.1f}%)"
                )
                response['statusCode'] = 207  # Multi-Status
            
            return response
            
        except Exception as e:
            logger.error(f"Cost collection failed: {e}", exc_info=True)
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Cost collection failed',
                    'message': str(e)
                })
            }
    
    except Exception as e:
        logger.error(f"Lambda handler failed: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Lambda handler failed',
                'message': str(e)
            })
        }


def manual_trigger_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler for manual triggers with custom parameters.
    
    Allows manual invocation with custom date ranges and account lists.
    
    Event format:
    {
        "org_id": "o-1234567890",
        "account_ids": ["123456789012", "234567890123"],  # Optional
        "start_date": "2024-01-01",  # Optional
        "end_date": "2024-01-31",  # Optional
        "external_id": "custom-external-id"  # Optional
    }
    
    Args:
        event: Manual trigger event with parameters
        context: Lambda context
        
    Returns:
        Response with collection summary
    """
    try:
        logger.info("Manual trigger received")
        logger.info("Cost collection invocation received")
        
        # Parse event parameters
        org_id = event.get('org_id') or os.environ.get('ORGANIZATION_ID')
        external_id = event.get('external_id') or os.environ.get('EXTERNAL_ID')
        
        if not org_id:
            org_id = OrganizationDiscoveryService().discover_organization().id
        
        # Parse date range
        if 'start_date' in event and 'end_date' in event:
            start_date = date.fromisoformat(event['start_date'])
            end_date = date.fromisoformat(event['end_date'])
        else:
            # Default to last 7 days
            end_date = date.today()
            start_date = end_date - timedelta(days=7)
        
        # Validate explicit selections against the actual organization as well.
        selected_organization = OrganizationDiscoveryService()
        actual_org = selected_organization.discover_organization()
        if actual_org.id != org_id: raise ValueError('Configured organization differs from discovered organization')
        permitted = {account.id for account in selected_organization.get_all_accounts(org_id)}
        # Get account IDs
        if 'account_ids' in event:
            account_ids = event['account_ids']
            if not isinstance(account_ids, list) or not account_ids or not set(account_ids).issubset(permitted): raise ValueError('Select accounts in the discovered organization')
            logger.info(f"Using provided account IDs: {len(account_ids)} accounts")
        else:
            # Discover accounts
            logger.info("Discovering organization accounts")
            discovery_service = OrganizationDiscoveryService()
            org_data = discovery_service.discover_organization()
            if org_data.id != org_id: raise ValueError('Configured organization differs from discovered organization')
            account_ids = [acc.id for acc in discovery_service.get_all_accounts(org_id)]
            logger.info(f"Discovered {len(account_ids)} accounts")
        
        # Collect costs
        logger.info(f"Collecting costs from {start_date} to {end_date}")
        
        # Read max_workers from environment variable (defaults to 10 in MultiAccountCostCollector)
        max_workers = int(os.environ.get('MAX_PARALLEL_ACCOUNTS', '10'))
        logger.info(f"Using max_workers={max_workers} for parallel collection")
        
        collector = MultiAccountCostCollector(max_workers=max_workers)
        
        result = collector.collect_all_accounts(
            org_id=org_id,
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date, external_id=external_id
        )
        
        # Log summary
        logger.info(
            f"Manual collection completed: "
            f"{result.successful}/{result.total_accounts} successful, "
            f"{result.failed} failed"
        )
        
        # Calculate total costs
        total_cost = sum(
            data.total_cost 
            for data in result.account_data 
            if data.status == 'SUCCESS'
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Manual cost collection completed',
                'summary': {
                    'total_accounts': result.total_accounts,
                    'successful': result.successful,
                    'failed': result.failed,
                    'failed_accounts': result.failed_accounts,
                    'collection_duration_seconds': round(result.collection_duration, 2),
                    'total_cost': float(total_cost),
                    'date_range': {
                        'start': start_date.isoformat(),
                        'end': end_date.isoformat()
                    }
                }
            })
        }
        
    except Exception as e:
        logger.error(f"Manual trigger failed: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Manual trigger failed',
                'message': str(e)
            })
        }
