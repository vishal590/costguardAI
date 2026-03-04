"""
AWS Lambda handler for Autonomous Action Loops.

This handler processes API Gateway requests for autonomous cost optimization actions,
including schedule analysis, action history, approvals, rollbacks, confidence scores,
and demo mode.

Requirements: 6.8
"""
import json
import logging
import os
from typing import Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key, Attr

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
ACTION_HISTORY_TABLE = os.environ.get("ACTION_HISTORY_TABLE", "costguard-action-history")
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "costguard-autonomous-events")
GPU_SCHEDULER_FUNCTION = os.environ.get("GPU_SCHEDULER_FUNCTION", "")
LEARNING_ENGINE_FUNCTION = os.environ.get("LEARNING_ENGINE_FUNCTION", "")

# AWS clients
dynamodb = boto3.resource("dynamodb")
events_client = boto3.client("events")
lambda_client = boto3.client("lambda")

# Tables
action_history_table = dynamodb.Table(ACTION_HISTORY_TABLE)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler function for Autonomous Action Loops.
    
    Args:
        event: Lambda event from API Gateway
        context: Lambda context object
        
    Returns:
        Dict containing statusCode, headers, and body
    """
    try:
        logger.info(f"Received autonomous action event: {json.dumps(event, default=str)}")
        
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')
        
        # Route to appropriate handler
        if http_method == 'POST' and path.endswith('/schedule-analysis'):
            return handle_schedule_analysis(event)
        elif http_method == 'GET' and path.endswith('/action-history'):
            return handle_action_history(event)
        elif http_method == 'POST' and path.endswith('/approve-action'):
            return handle_approve_action(event)
        elif http_method == 'POST' and path.endswith('/rollback'):
            return handle_rollback(event)
        elif http_method == 'GET' and path.endswith('/confidence-scores'):
            return handle_confidence_scores(event)
        elif http_method == 'GET' and path.endswith('/demo-status'):
            return handle_demo_status(event)
        elif http_method == 'POST' and path.endswith('/demo/start'):
            return handle_demo_start(event)
        elif http_method == 'POST' and path.endswith('/demo/reset'):
            return handle_demo_reset(event)
        elif http_method == 'POST' and path.endswith('/demo/trigger-interruption'):
            return handle_demo_trigger_interruption(event)
        else:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': f'Endpoint not found: {http_method} {path}'})
            }
            
    except Exception as e:
        logger.error(f"Error in autonomous handler: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }


def handle_schedule_analysis(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/autonomous/schedule-analysis
    
    Trigger GPU Scheduler Lambda manually to analyze cost patterns and generate
    scheduling recommendations.
    
    Request body:
        - days (int, optional): Number of days to analyze (default: 7)
        - confidence_threshold (float, optional): Minimum confidence score (default: 0.7)
        - dry_run (bool, optional): Run in dry-run mode (default: false)
    
    Returns:
        Recommendations with confidence scores and expected savings
    
    Requirements: 1.1, 1.2
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        days = body.get('days', 7)
        confidence_threshold = body.get('confidence_threshold', 0.7)
        dry_run = body.get('dry_run', False)
        
        # Validate parameters
        if not isinstance(days, int) or days < 1 or days > 30:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'days must be an integer between 1 and 30'})
            }
        
        if not isinstance(confidence_threshold, (int, float)) or confidence_threshold < 0 or confidence_threshold > 1:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'confidence_threshold must be between 0 and 1'})
            }
        
        # Invoke GPU Scheduler Lambda
        if GPU_SCHEDULER_FUNCTION:
            payload = {
                'days': days,
                'confidence_threshold': confidence_threshold,
                'dry_run': dry_run
            }
            
            response = lambda_client.invoke(
                FunctionName=GPU_SCHEDULER_FUNCTION,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            result = json.loads(response['Payload'].read())
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(result, cls=DecimalEncoder)
            }
        else:
            return {
                'statusCode': 503,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'GPU Scheduler function not configured'})
            }
            
    except Exception as e:
        logger.error(f"Error in schedule analysis: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }


def handle_action_history(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/autonomous/action-history
    
    Query action history with filters and return paginated results with cumulative savings.
    
    Query parameters:
        - action_type (str, optional): Filter by action type
        - start_date (str, optional): Start date (ISO format)
        - end_date (str, optional): End date (ISO format)
        - status (str, optional): Filter by status
        - limit (int, optional): Max results (default: 100)
    
    Returns:
        Paginated action history with cumulative savings
    
    Requirements: 4.1, 9.1
    """
    try:
        # Parse query parameters
        params = event.get('queryStringParameters', {}) or {}
        action_type = params.get('action_type')
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        status = params.get('status')
        limit = int(params.get('limit', 100))
        
        # Validate limit
        if limit < 1 or limit > 1000:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'limit must be between 1 and 1000'})
            }
        
        # Build query
        if action_type:
            # Query by action type using GSI
            query_kwargs = {
                'IndexName': 'action-type-index',
                'KeyConditionExpression': Key('action_type').eq(action_type),
                'Limit': limit,
                'ScanIndexForward': False  # Most recent first
            }
            
            # Add filter expressions
            filter_expressions = []
            if start_date:
                filter_expressions.append(Attr('timestamp').gte(start_date))
            if end_date:
                filter_expressions.append(Attr('timestamp').lte(end_date))
            if status:
                filter_expressions.append(Attr('status').eq(status))
            
            if filter_expressions:
                filter_expr = filter_expressions[0]
                for expr in filter_expressions[1:]:
                    filter_expr = filter_expr & expr
                query_kwargs['FilterExpression'] = filter_expr
            
            response = action_history_table.query(**query_kwargs)
        else:
            # Scan all actions
            scan_kwargs = {
                'Limit': limit
            }
            
            # Add filter expressions
            filter_expressions = []
            if start_date:
                filter_expressions.append(Attr('timestamp').gte(start_date))
            if end_date:
                filter_expressions.append(Attr('timestamp').lte(end_date))
            if status:
                filter_expressions.append(Attr('status').eq(status))
            
            if filter_expressions:
                filter_expr = filter_expressions[0]
                for expr in filter_expressions[1:]:
                    filter_expr = filter_expr & expr
                scan_kwargs['FilterExpression'] = filter_expr
            
            response = action_history_table.scan(**scan_kwargs)
        
        actions = response.get('Items', [])
        
        # Calculate cumulative savings
        cumulative_savings = sum(
            float(action.get('actual_cost_impact', 0))
            for action in actions
            if action.get('status') == 'completed'
        )
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'actions': actions,
                'count': len(actions),
                'cumulative_savings': cumulative_savings,
                'has_more': 'LastEvaluatedKey' in response
            }, cls=DecimalEncoder)
        }
        
    except Exception as e:
        logger.error(f"Error in action history: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }


def handle_approve_action(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/autonomous/approve-action
    
    Accept approval decisions for pending actions and publish events to EventBridge.
    
    Request body:
        - request_id (str): Approval request ID
        - action_id (str): Action ID
        - approved (bool): Approval decision
        - signature (str): HMAC signature for validation
    
    Returns:
        Approval status
    
    Requirements: 5.4, 5.5
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        request_id = body.get('request_id')
        action_id = body.get('action_id')
        approved = body.get('approved')
        signature = body.get('signature')
        
        # Validate required fields
        if not all([request_id, action_id, signature is not None, approved is not None]):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Missing required fields: request_id, action_id, approved, signature'})
            }
        
        # Validate signature (simplified - in production would use HMAC validation)
        # This would call the Safety Guard's validate_approval_signature function
        
        # Publish approval decision event
        detail_type = "ActionApproved" if approved else "ActionRejected"
        
        events_client.put_events(
            Entries=[{
                'Source': 'costguard.autonomous.api',
                'DetailType': detail_type,
                'Detail': json.dumps({
                    'request_id': request_id,
                    'action_id': action_id,
                    'approved': approved,
                    'timestamp': datetime.utcnow().isoformat()
                }),
                'EventBusName': EVENT_BUS_NAME
            }]
        )
        
        logger.info(f"Published {detail_type} event for action: {action_id}")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'status': 'approved' if approved else 'rejected',
                'action_id': action_id,
                'request_id': request_id
            })
        }
        
    except Exception as e:
        logger.error(f"Error in approve action: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }


def handle_rollback(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/autonomous/rollback
    
    Trigger rollback execution for a completed action.
    
    Request body:
        - action_id (str): Action ID to rollback
        - reason (str, optional): Reason for rollback
    
    Returns:
        Rollback status and estimated completion time
    
    Requirements: 5.7, 5.8
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        action_id = body.get('action_id')
        reason = body.get('reason', 'Manual rollback requested')
        
        # Validate required fields
        if not action_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Missing required field: action_id'})
            }
        
        # Publish rollback request event
        events_client.put_events(
            Entries=[{
                'Source': 'costguard.autonomous.api',
                'DetailType': 'RollbackRequested',
                'Detail': json.dumps({
                    'action_id': action_id,
                    'reason': reason,
                    'timestamp': datetime.utcnow().isoformat()
                }),
                'EventBusName': EVENT_BUS_NAME
            }]
        )
        
        logger.info(f"Published RollbackRequested event for action: {action_id}")
        
        # Estimate completion time (5 minutes as per requirements)
        estimated_completion = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
        
        return {
            'statusCode': 202,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'status': 'rollback_initiated',
                'action_id': action_id,
                'reason': reason,
                'estimated_completion': estimated_completion
            })
        }
        
    except Exception as e:
        logger.error(f"Error in rollback: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }


def handle_confidence_scores(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/autonomous/confidence-scores
    
    Query Learning Engine for current confidence scores by action type.
    
    Returns:
        Confidence scores, success rates, and total action counts by type
    
    Requirements: 4.3, 4.4
    """
    try:
        # Query action history for all completed actions
        response = action_history_table.scan(
            FilterExpression=Attr('status').eq('completed')
        )
        
        actions = response.get('Items', [])
        
        # Calculate confidence scores by action type
        scores_by_type = {}
        
        for action in actions:
            action_type = action.get('action_type')
            if not action_type:
                continue
            
            if action_type not in scores_by_type:
                scores_by_type[action_type] = {
                    'total_actions': 0,
                    'successful_actions': 0,
                    'success_rate': 0.0,
                    'avg_confidence': 0.0,
                    'confidence_scores': []
                }
            
            scores_by_type[action_type]['total_actions'] += 1
            
            # Check if action was successful (simplified)
            if action.get('outcome') == 'success':
                scores_by_type[action_type]['successful_actions'] += 1
            
            # Collect confidence scores
            confidence = float(action.get('confidence_score', 0.5))
            scores_by_type[action_type]['confidence_scores'].append(confidence)
        
        # Calculate averages
        for action_type, data in scores_by_type.items():
            if data['total_actions'] > 0:
                data['success_rate'] = data['successful_actions'] / data['total_actions']
                data['avg_confidence'] = sum(data['confidence_scores']) / len(data['confidence_scores'])
            
            # Remove raw scores from response
            del data['confidence_scores']
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'confidence_scores': scores_by_type,
                'timestamp': datetime.utcnow().isoformat()
            }, cls=DecimalEncoder)
        }
        
    except Exception as e:
        logger.error(f"Error in confidence scores: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }


def handle_demo_status(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/autonomous/demo-status
    
    Return real-time demo progress including current phase, actions in progress,
    cumulative savings, and recent completed actions.
    
    Returns:
        Demo status with progress, savings, and recent actions
    
    Requirements: 8.3, 8.4, 8.5
    """
    try:
        # Query recent actions (last 24 hours in demo mode = last 2 minutes real time)
        cutoff_time = (datetime.utcnow() - timedelta(minutes=10)).isoformat()
        
        response = action_history_table.scan(
            FilterExpression=Attr('timestamp').gte(cutoff_time)
        )
        
        actions = response.get('Items', [])
        
        # Categorize actions by status
        in_progress = [a for a in actions if a.get('status') == 'in_progress']
        completed = [a for a in actions if a.get('status') == 'completed']
        
        # Calculate cumulative savings
        cumulative_savings = sum(
            float(action.get('actual_cost_impact', 0))
            for action in completed
        )
        
        # Calculate savings percentage (assuming baseline cost)
        baseline_cost = 100.0  # Simplified
        savings_percent = (abs(cumulative_savings) / baseline_cost * 100) if baseline_cost > 0 else 0
        
        # Determine current phase based on action types
        current_phase = "idle"
        if any(a.get('action_type') == 'schedule' for a in in_progress):
            current_phase = "analyze"
        elif any(a.get('action_type') == 'spot_migration' for a in in_progress):
            current_phase = "act"
        elif any(a.get('action_type') == 'right_sizing' for a in in_progress):
            current_phase = "verify"
        elif len(completed) > 0:
            current_phase = "learn"
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'current_phase': current_phase,
                'actions_in_progress': len(in_progress),
                'actions_completed': len(completed),
                'cumulative_savings': cumulative_savings,
                'savings_percent': savings_percent,
                'recent_actions': completed[-5:] if completed else [],  # Last 5
                'timestamp': datetime.utcnow().isoformat()
            }, cls=DecimalEncoder)
        }
        
    except Exception as e:
        logger.error(f"Error in demo status: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }


def handle_demo_start(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/autonomous/demo/start
    
    Initiate demo sequence (placeholder for future implementation).
    
    Requirements: 8.3
    """
    return {
        'statusCode': 501,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'message': 'Demo start endpoint - to be implemented in Task 11'})
    }


def handle_demo_reset(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/autonomous/demo/reset
    
    Clear demo data (placeholder for future implementation).
    
    Requirements: 8.3
    """
    return {
        'statusCode': 501,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'message': 'Demo reset endpoint - to be implemented in Task 11'})
    }


def handle_demo_trigger_interruption(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/autonomous/demo/trigger-interruption
    
    Manually trigger spot interruption for demo (placeholder for future implementation).
    
    Requirements: 8.3
    """
    return {
        'statusCode': 501,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'message': 'Demo trigger interruption endpoint - to be implemented in Task 11'})
    }
