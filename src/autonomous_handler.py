"""
AWS Lambda handler for Autonomous Action Loops.

This handler processes API Gateway requests for autonomous cost optimization actions,
including schedule analysis, action history, approvals, rollbacks, confidence scores,
and demo mode.

Requirements: 6.8
"""
import json
from .services.request_json import RequestBodyError
from .services.access_control import AccessDenied, BackendAuthenticationError, BackendConfigurationError, authorize_stack_request, advisor_identity
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

# CORS headers for browser requests (API Gateway only adds them to OPTIONS; Lambda must add to GET/POST)
CORS_HEADERS = {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}


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
        logger.info("Request method=%s path=%s", event.get("httpMethod"), event.get("path"))
        
        try:
            authorize_stack_request(event)
        except RequestBodyError as exc:
            return {'statusCode': 400, 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}, 'body': json.dumps({'error': str(exc), 'code': 'INVALID_REQUEST_BODY'})}
        except BackendConfigurationError:
            return {'statusCode': 503, 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}, 'body': json.dumps({'error': 'Backend access is not configured', 'code': 'BACKEND_AUTHENTICATION_UNAVAILABLE'})}
        except BackendAuthenticationError:
            return {'statusCode': 401, 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}, 'body': json.dumps({'error': 'Invalid backend access key', 'code': 'BACKEND_AUTHENTICATION_FAILED'})}
        except AccessDenied as exc:
            return {'statusCode': 403, 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}, 'body': json.dumps({'error': str(exc)})}
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
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': f'Endpoint not found: {http_method} {path}'})
            }
            
    except Exception as e:
        logger.error(f"Error in autonomous handler: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
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
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': 'days must be an integer between 1 and 30'})
            }
        
        if not isinstance(confidence_threshold, (int, float)) or confidence_threshold < 0 or confidence_threshold > 1:
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': 'confidence_threshold must be between 0 and 1'})
            }
        
        if not isinstance(dry_run, bool) or (body.get("workload") is not None and not isinstance(body["workload"], dict)):
            return {"statusCode": 400, "headers": CORS_HEADERS,
                    "body": json.dumps({"error": "dry_run must be boolean and workload must be an object"})}

        # Invoke GPU Scheduler Lambda
        if GPU_SCHEDULER_FUNCTION:
            payload = {
                'days': days,
                'confidence_threshold': confidence_threshold,
                'dry_run': dry_run,
                'workload': body.get('workload')
            }
            
            response = lambda_client.invoke(
                FunctionName=GPU_SCHEDULER_FUNCTION,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            result = json.loads(response['Payload'].read())
            if response.get('FunctionError'):
                return {'statusCode': 500, 'headers': CORS_HEADERS,
                        'body': json.dumps({'error': 'GPU Scheduler failed'})}
            result_status = result.get('statusCode', 200) if isinstance(result, dict) else 200
            # GPU Scheduler may return API Gateway shape; unwrap so client gets payload only
            if isinstance(result, dict) and 'body' in result and 'statusCode' in result:
                body_content = result['body']
                if isinstance(body_content, str):
                    body_content = json.loads(body_content)
                result = body_content
            
            return {
                'statusCode': result_status,
                'headers': CORS_HEADERS,
                'body': json.dumps(result, cls=DecimalEncoder)
            }
        else:
            return {
                'statusCode': 503,
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': 'GPU Scheduler function not configured'})
            }
            
    except Exception as e:
        logger.error(f"Error in schedule analysis: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
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
        action_id = params.get('action_id')
        action_type = params.get('action_type')
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        status = params.get('status')
        limit = int(params.get('limit', 100))
        
        # Validate limit
        if limit < 1 or limit > 1000:
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': 'limit must be between 1 and 1000'})
            }
        
        # Build query
        if action_id:
            query_kwargs = {'KeyConditionExpression': Key('action_id').eq(action_id),
                            'Limit': limit, 'ScanIndexForward': False, 'ConsistentRead': True}
            filters = []
            for field, value, comparison in [('action_type', action_type, 'eq'), ('status', status, 'eq'),
                                              ('timestamp', start_date, 'gte'), ('timestamp', end_date, 'lte')]:
                if value:
                    filters.append(getattr(Attr(field), comparison)(value))
            if filters:
                expression = filters[0]
                for extra in filters[1:]:
                    expression = expression & extra
                query_kwargs['FilterExpression'] = expression
            response = action_history_table.query(**query_kwargs)
        elif action_type:
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
            'headers': CORS_HEADERS,
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
            'headers': CORS_HEADERS,
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
        if not (isinstance(request_id, str) and request_id.strip()
                and isinstance(action_id, str) and action_id.strip()
                and isinstance(signature, str) and signature.strip()
                and isinstance(approved, bool)):
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': 'request_id, action_id and signature must be non-empty strings; approved must be a boolean'})
            }
        
        # Safety Guard validates the signature against the stored, unexpired
        # request before applying this asynchronous decision.
        
        # Publish approval decision event
        detail_type = "ActionApproved" if approved else "ActionRejected"
        
        response = events_client.put_events(
            Entries=[{
                'Source': 'costguard.autonomous.api',
                'DetailType': detail_type,
                'Detail': json.dumps({
                    'request_id': request_id,
                    'action_id': action_id,
                    'approved': approved,
                    'signature': signature,
                    'submitted_by': event.get('_principal', {}).get('subject'),
                    'timestamp': datetime.utcnow().isoformat()
                }),
                'EventBusName': EVENT_BUS_NAME
            }]
        )
        
        if response.get('FailedEntryCount', 0):
            raise RuntimeError("EventBridge failed to accept the approval decision")

        logger.info(f"Published {detail_type} event for action: {action_id}")
        
        return {
            'statusCode': 202,
            'headers': CORS_HEADERS,
            'body': json.dumps({
                'status': 'approval_submitted',
                'approved': approved,
                'action_id': action_id,
                'request_id': request_id
            })
        }
        
    except Exception as e:
        logger.error(f"Error in approve action: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
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
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': 'Missing required field: action_id'})
            }
        
        # Publish rollback request event
        response = events_client.put_events(
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
        
        if response.get('FailedEntryCount', 0):
            raise RuntimeError("EventBridge failed to accept the rollback request")

        logger.info(f"Published RollbackRequested event for action: {action_id}")
        
        # Estimate completion time (5 minutes as per requirements)
        estimated_completion = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
        
        return {
            'statusCode': 202,
            'headers': CORS_HEADERS,
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
            'headers': CORS_HEADERS,
            'body': json.dumps({'error': str(e)})
        }


def handle_confidence_scores(event: Dict[str, Any]) -> Dict[str, Any]:
    """Observe bounded stored action outcomes; heuristic scores are not calibrated confidence."""
    import math
    from datetime import UTC
    try:
        from .services.request_query import single_valued_query
        single_valued_query(event, set())
        fields = ('action_id', 'timestamp', 'action_type', 'status', 'success', 'outcome',
                  'confidence_score', 'ttl', 'demo', 'demo_mode')
        names = {f'#projection{index}': name for index, name in enumerate(fields)}
        names.update({'#parameters': 'parameters', '#demo': 'demo', '#demo_mode': 'demo_mode'})
        request = {'FilterExpression': Attr('status').eq('completed'), 'Limit': 100,
            'ProjectionExpression': ', '.join(f'#projection{index}' for index in range(len(fields)))+', #parameters.#demo, #parameters.#demo_mode',
            'ExpressionAttributeNames': names}
        quality = {'scan_page_limit': 10, 'scan_page_size': 100, 'pages_read': 0,
            'returned_completed_rows': 0, 'invalid_rows': 0, 'expired_rows': 0,
            'unknown_retention_rows': 0, 'duplicate_rows': 0, 'conflicting_identities': 0,
            'scanned_rows': 0, 'has_more_stored_rows': None, 'complete_history_verified': False,
            'execution_verified': False, 'calibrated_confidence_available': False,
            'scope': 'bounded_completed_record_observations_not_production_success_or_calibration'}
        now = datetime.now(UTC)
        records, conflicts, seen = {}, set(), set()
        for _ in range(10):
            response = action_history_table.scan(**request)
            quality['pages_read'] += 1
            scanned = response.get('ScannedCount')
            if quality['scanned_rows'] is not None:
                quality['scanned_rows'] = quality['scanned_rows']+scanned if type(scanned) is int and scanned >= 0 else None
            rows = response.get('Items', [])
            if not isinstance(rows, list): raise RuntimeError('Invalid action observation page')
            quality['returned_completed_rows'] += len(rows)
            for row in rows:
                if not isinstance(row, dict) or row.get('status') != 'completed':
                    quality['invalid_rows'] += 1; continue
                identifier, timestamp, kind = (row.get(key) for key in ('action_id', 'timestamp', 'action_type'))
                if any(not isinstance(value, str) or not value or len(value) > maximum
                        for value, maximum in ((identifier, 256), (timestamp, 64), (kind, 128))):
                    quality['invalid_rows'] += 1; continue
                ttl = row.get('ttl')
                try:
                    expiry = float(ttl) if ttl is not None and not isinstance(ttl, bool) else None
                    if expiry is not None and not math.isfinite(expiry): expiry = None
                except (TypeError, ValueError, OverflowError): expiry = None
                if expiry is not None and expiry <= now.timestamp():
                    quality['expired_rows'] += 1; continue
                if expiry is None: quality['unknown_retention_rows'] += 1
                if 'success' in row:
                    outcome = row['success'] if isinstance(row['success'], bool) else None
                else:
                    outcome = True if row.get('outcome') == 'success' else False if row.get('outcome') in ('failed', 'failure') else None
                raw_score = row.get('confidence_score')
                try:
                    score = float(raw_score) if raw_score is not None and not isinstance(raw_score, bool) else None
                    if score is not None and (not math.isfinite(score) or not 0 <= score <= 1): score = None
                except (TypeError, ValueError, OverflowError): score = None
                parameters = row.get('parameters') if isinstance(row.get('parameters'), dict) else {}
                raw_flags = (row.get('demo'), row.get('demo_mode'), parameters.get('demo'), parameters.get('demo_mode'))
                declared_flags = [value for value in raw_flags if isinstance(value, bool)]
                invalid_scope = any(value is not None and not isinstance(value, bool) for value in raw_flags)
                scope = 'unknown_or_conflicting' if invalid_scope else 'declared_demo' if declared_flags and all(declared_flags) else 'declared_non_demo' if declared_flags and not any(declared_flags) else 'unknown_or_conflicting'
                key = (identifier, timestamp)
                observed = {'action_type': kind, 'outcome': outcome, 'recorded_score': score, 'declared_scope': scope}
                if key in conflicts: continue
                if key in records:
                    quality['duplicate_rows'] += 1
                    if records[key] != observed:
                        conflicts.add(key); del records[key]
                    continue
                records[key] = observed
            cursor = response.get('LastEvaluatedKey')
            quality['has_more_stored_rows'] = bool(cursor)
            if not cursor: break
            fingerprint = json.dumps(cursor, sort_keys=True, cls=DecimalEncoder)
            if fingerprint in seen: raise RuntimeError('Repeated action observation scan cursor')
            seen.add(fingerprint); request['ExclusiveStartKey'] = cursor
        quality['conflicting_identities'] = len(conflicts)
        quality['retained_unique_records'] = len(records)
        quality['status'] = 'bounded_selection' if quality['has_more_stored_rows'] else 'observed_scan_pages'
        scores = {}
        for row in records.values():
            kind = row['action_type']
            data = scores.setdefault(kind, {'total_actions': 0, 'successful_actions': 0, 'failed_actions': 0,
                'unknown_outcome_actions': 0, 'known_outcome_actions': 0, 'success_rate': None,
                'avg_confidence': None, 'confidence_method': 'unavailable',
                'recorded_score_average': None, 'recorded_score_count': 0, 'missing_or_invalid_score_count': 0,
                'recorded_score_basis': 'unverified_recorded_heuristic',
                'declared_scope_counts': {'declared_demo': 0, 'declared_non_demo': 0, 'unknown_or_conflicting': 0},
                'execution_verified': False, '_score_sum': 0.0})
            data['total_actions'] += 1
            data['declared_scope_counts'][row['declared_scope']] += 1
            if row['outcome'] is None: data['unknown_outcome_actions'] += 1
            else:
                data['known_outcome_actions'] += 1
                data['successful_actions' if row['outcome'] else 'failed_actions'] += 1
            if row['recorded_score'] is None: data['missing_or_invalid_score_count'] += 1
            else:
                data['recorded_score_count'] += 1; data['_score_sum'] += row['recorded_score']
        for data in scores.values():
            if data['known_outcome_actions']: data['success_rate'] = data['successful_actions']/data['known_outcome_actions']
            if data['recorded_score_count']: data['recorded_score_average'] = data['_score_sum']/data['recorded_score_count']
            del data['_score_sum']
        return {'statusCode': 200, 'headers': CORS_HEADERS, 'body': json.dumps({
            'data_contract': 'autonomous_action_observations_v2', 'confidence_scores': scores,
            'data_quality': quality, 'timestamp': datetime.now(UTC).isoformat()}, cls=DecimalEncoder, allow_nan=False)}
    except ValueError as error:
        return {'statusCode': 400, 'headers': CORS_HEADERS, 'body': json.dumps({'error': str(error), 'code': 'INVALID_PARAMETER'})}
    except Exception as error:
        logger.warning('Autonomous action observations unavailable: %s', type(error).__name__)
        return {'statusCode': 503, 'headers': CORS_HEADERS,
            'body': json.dumps({'error': 'Stored autonomous action observations are unavailable', 'code': 'ACTION_OBSERVATIONS_UNAVAILABLE'})}


def handle_demo_status(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/autonomous/demo-status
    
    Return real-time demo progress including current phase, actions in progress,
    cumulative savings, and recent completed actions with detailed phase tracking.
    
    Returns:
        Demo status with progress, savings, and recent actions
    
    Requirements: 8.3, 8.4, 8.5, 8.7
    """
    try:
        # Query recent actions (last 24 hours in demo mode = last 10 minutes real time)
        cutoff_time = (datetime.utcnow() - timedelta(minutes=15)).isoformat()
        
        response = action_history_table.scan(
            FilterExpression=Attr('timestamp').gte(cutoff_time) & Attr('demo_mode').eq(True)
        )
        
        actions = response.get('Items', [])
        
        # Categorize actions by status
        in_progress = [a for a in actions if a.get('status') == 'in_progress']
        completed = [a for a in actions if a.get('status') == 'completed']
        failed = [a for a in actions if a.get('status') == 'failed']
        
        # Calculate cumulative savings from completed actions
        cumulative_savings = Decimal('0')
        for action in completed:
            cost_impact = action.get('actual_cost_impact', 0)
            if isinstance(cost_impact, (int, float, Decimal)):
                cumulative_savings += Decimal(str(cost_impact))
        
        # Calculate baseline cost (sum of original costs before optimization)
        baseline_cost = Decimal('100.0')  # Default baseline
        for action in completed:
            baseline = action.get('baseline_cost', 0)
            if isinstance(baseline, (int, float, Decimal)) and baseline > 0:
                baseline_cost += Decimal(str(baseline))
        
        # Calculate savings percentage
        savings_percent = float((abs(cumulative_savings) / baseline_cost * 100)) if baseline_cost > 0 else 0.0
        
        # Determine current phase and progress based on action types and timestamps
        demo_phases = ['analyze', 'decide', 'act', 'verify', 'learn']
        current_phase = 'idle'
        phase_progress = 0.0
        estimated_completion = None
        
        # Find demo start action
        demo_start = next((a for a in actions if a.get('action_type') == 'demo_start'), None)
        
        if demo_start:
            start_time = datetime.fromisoformat(demo_start['timestamp'].replace('Z', ''))
            elapsed_minutes = (datetime.utcnow() - start_time).total_seconds() / 60
            
            # Calculate overall progress (10-minute demo)
            overall_progress = min(100.0, (elapsed_minutes / 10.0) * 100)
            
            # Determine phase based on elapsed time
            if elapsed_minutes < 2:
                current_phase = 'analyze'
                phase_progress = (elapsed_minutes / 2.0) * 100
            elif elapsed_minutes < 3:
                current_phase = 'decide'
                phase_progress = ((elapsed_minutes - 2) / 1.0) * 100
            elif elapsed_minutes < 7:
                current_phase = 'act'
                phase_progress = ((elapsed_minutes - 3) / 4.0) * 100
            elif elapsed_minutes < 9:
                current_phase = 'verify'
                phase_progress = ((elapsed_minutes - 7) / 2.0) * 100
            elif elapsed_minutes < 10:
                current_phase = 'learn'
                phase_progress = ((elapsed_minutes - 9) / 1.0) * 100
            else:
                current_phase = 'completed'
                phase_progress = 100.0
            
            # Estimate completion time
            remaining_minutes = max(0, 10 - elapsed_minutes)
            estimated_completion = (datetime.utcnow() + timedelta(minutes=remaining_minutes)).isoformat() + 'Z'
            
            # When phase is completed, don't show stale in-progress actions (demo_start is never updated to completed in DB)
            if current_phase == 'completed':
                cutoff_recent = (datetime.utcnow() - timedelta(minutes=10)).isoformat() + 'Z'
                in_progress = [a for a in in_progress if (a.get('timestamp') or '') >= cutoff_recent]
        else:
            overall_progress = 0.0
        
        # Get actions in progress with details
        actions_in_progress_details = []
        for action in in_progress:
            actions_in_progress_details.append({
                'action_id': action.get('action_id'),
                'action_type': action.get('action_type'),
                'started_at': action.get('timestamp'),
                'current_step': action.get('current_step', 'processing'),
                'progress': action.get('progress', 0)
            })
        
        # Get recent completed actions with outcomes
        recent_completed = sorted(
            completed,
            key=lambda x: x.get('timestamp', ''),
            reverse=True
        )[:5]
        
        recent_actions_summary = []
        for action in recent_completed:
            recent_actions_summary.append({
                'action_id': action.get('action_id'),
                'action_type': action.get('action_type'),
                'completed_at': action.get('timestamp'),
                'cost_impact': float(action.get('actual_cost_impact', 0)),
                'outcome': action.get('outcome', 'success')
            })
        
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': json.dumps({
                'demo_mode': True,
                'current_phase': current_phase,
                'phase_progress_percent': round(phase_progress, 1),
                'overall_progress_percent': round(overall_progress, 1) if demo_start else 0.0,
                'estimated_completion': estimated_completion,
                'phases': demo_phases,
                'actions': {
                    'in_progress': len(in_progress),
                    'completed': len(completed),
                    'failed': len(failed),
                    'total': len(actions)
                },
                'actions_in_progress_details': actions_in_progress_details,
                'cumulative_savings': float(cumulative_savings),
                'savings_percent': round(savings_percent, 2),
                'recent_completed_actions': recent_actions_summary,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }, cls=DecimalEncoder)
        }
        
    except Exception as e:
        logger.error(f"Error in demo status: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
            'body': json.dumps({'error': str(e)})
        }


def handle_demo_start(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/autonomous/demo/start
    
    Initiate demo sequence by triggering the GPU Scheduler Lambda
    to analyze cost patterns and generate recommendations.
    
    Requirements: 8.3
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        # Validate demo mode is enabled
        if not os.environ.get('DEMO_MODE', 'false').lower() == 'true':
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({
                    'error': 'Demo mode is not enabled',
                    'message': 'Set DEMO_MODE=true environment variable to enable demo mode'
                })
            }
        
        # Trigger GPU Scheduler Lambda to start analysis
        lambda_client = boto3.client('lambda')
        gpu_scheduler_function = os.environ.get('GPU_SCHEDULER_FUNCTION', 'CostGuardGPUScheduler')
        
        # Invoke GPU Scheduler asynchronously
        response = lambda_client.invoke(
            FunctionName=gpu_scheduler_function,
            InvocationType='Event',  # Asynchronous invocation
            Payload=json.dumps({
                'demo_mode': True,
                'trigger': 'demo_start'
            })
        )
        
        # Record demo start in action history
        action_history_table.put_item(
            Item={
                'action_id': f'demo-start-{datetime.utcnow().isoformat()}',
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'action_type': 'demo_start',
                'status': 'in_progress',
                'parameters': {
                    'demo_mode': True,
                    'started_at': datetime.utcnow().isoformat() + 'Z'
                },
                'demo_mode': True
            }
        )
        
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': json.dumps({
                'message': 'Demo sequence initiated',
                'demo_mode': True,
                'estimated_duration_minutes': 10,
                'phases': ['analyze', 'decide', 'act', 'verify', 'learn'],
                'next_steps': [
                    'Monitor progress: GET /api/autonomous/demo-status',
                    'View actions: GET /api/autonomous/action-history?action_type=demo'
                ]
            }, cls=DecimalEncoder)
        }
        
    except Exception as e:
        logger.error(f"Error starting demo: {str(e)}")
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
            'body': json.dumps({'error': f'Failed to start demo: {str(e)}'})
        }


def handle_demo_reset(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/autonomous/demo/reset
    
    Clear demo data from all tables and reset demo state.
    
    Requirements: 8.3
    """
    try:
        # Validate demo mode is enabled
        if not os.environ.get('DEMO_MODE', 'false').lower() == 'true':
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({
                    'error': 'Demo mode is not enabled',
                    'message': 'Set DEMO_MODE=true environment variable to enable demo mode'
                })
            }
        
        deleted_counts = {}
        
        # Delete demo data from action history table
        try:
            response = action_history_table.scan(
                FilterExpression=Attr('demo_mode').eq(True)
            )
            with action_history_table.batch_writer() as batch:
                for item in response.get('Items', []):
                    batch.delete_item(Key={
                        'action_id': item['action_id'],
                        'timestamp': item['timestamp']
                    })
            deleted_counts['action_history'] = len(response.get('Items', []))
        except Exception as e:
            logger.warning(f"Error deleting action history: {e}")
            deleted_counts['action_history'] = 0
        
        # Delete demo checkpoints from S3
        try:
            s3_client = boto3.client('s3')
            checkpoints_bucket = os.environ.get('CHECKPOINTS_BUCKET')
            if checkpoints_bucket:
                response = s3_client.list_objects_v2(
                    Bucket=checkpoints_bucket,
                    Prefix='checkpoints/demo-'
                )
                objects_to_delete = [{'Key': obj['Key']} for obj in response.get('Contents', [])]
                if objects_to_delete:
                    s3_client.delete_objects(
                        Bucket=checkpoints_bucket,
                        Delete={'Objects': objects_to_delete}
                    )
                deleted_counts['checkpoints'] = len(objects_to_delete)
            else:
                deleted_counts['checkpoints'] = 0
        except Exception as e:
            logger.warning(f"Error deleting checkpoints: {e}")
            deleted_counts['checkpoints'] = 0
        
        # Delete demo data from GPU costs table (optional - may want to keep for re-running demo)
        # Commented out to preserve seeded demo data
        # try:
        #     gpu_costs_table = dynamodb.Table(os.environ.get('GPU_COSTS_TABLE', 'costguard-gpu-costs'))
        #     response = gpu_costs_table.scan(
        #         FilterExpression=Attr('demo_mode').eq(True)
        #     )
        #     with gpu_costs_table.batch_writer() as batch:
        #         for item in response.get('Items', []):
        #             batch.delete_item(Key={
        #                 'instance_id': item['instance_id'],
        #                 'timestamp': item['timestamp']
        #             })
        #     deleted_counts['gpu_costs'] = len(response.get('Items', []))
        # except Exception as e:
        #     logger.warning(f"Error deleting GPU costs: {e}")
        #     deleted_counts['gpu_costs'] = 0
        
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': json.dumps({
                'message': 'Demo data reset successfully',
                'deleted_counts': deleted_counts,
                'note': 'Seeded GPU cost data preserved for re-running demo'
            }, cls=DecimalEncoder)
        }
        
    except Exception as e:
        logger.error(f"Error resetting demo: {str(e)}")
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
            'body': json.dumps({'error': f'Failed to reset demo: {str(e)}'})
        }


def handle_demo_trigger_interruption(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/autonomous/demo/trigger-interruption
    
    Manually trigger spot interruption for demo by publishing a
    SpotInterruptionDetected event to EventBridge.
    
    Requirements: 8.3
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        instance_id = body.get('instance_id')
        parameters = body.get('parameters')
        training_job_id = body.get('training_job_id')
        
        # Validate demo mode is enabled
        if not os.environ.get('DEMO_MODE', 'false').lower() == 'true':
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({
                    'error': 'Demo mode is not enabled',
                    'message': 'Set DEMO_MODE=true environment variable to enable demo mode'
                })
            }
        
        if not (isinstance(instance_id, str) and instance_id.strip()
                and isinstance(training_job_id, str) and training_job_id.strip()
                and isinstance(parameters, dict)):
            return {'statusCode': 400, 'headers': CORS_HEADERS,
                    'body': json.dumps({'error': 'instance_id, training_job_id and parameters are required'})}
        from autonomous.action_executor import validate_parameters
        try:
            validate_parameters('ondemand_fallback', dict(parameters, training_job_id=training_job_id))
        except (ValueError, KeyError, TypeError) as error:
            return {'statusCode': 400, 'headers': CORS_HEADERS, 'body': json.dumps({'error': str(error)})}

        # Publish SpotInterruptionDetected event to EventBridge
        event_bus_name = os.environ.get('EVENT_BUS_NAME', 'costguard-autonomous-events')
        
        interruption_event = {
            'Source': 'costguard.autonomous.demo',
            'DetailType': 'SpotInterruptionDetected',
            'Detail': json.dumps({
                'instance_id': instance_id,
                'instance_type': body.get('instance_type', 'g4dn.xlarge'),
                'region': parameters['region'],
                'interruption_time': (datetime.utcnow() + timedelta(minutes=2)).isoformat() + 'Z',
                'training_job_id': training_job_id,
                'parameters': parameters,
                'demo_mode': True,
                'triggered_manually': True
            }),
            'EventBusName': event_bus_name
        }
        
        response = events_client.put_events(Entries=[interruption_event])
        
        # Check for failures
        if response.get('FailedEntryCount', 0) > 0:
            return {
                'statusCode': 500,
                'headers': CORS_HEADERS,
                'body': json.dumps({
                    'error': 'Failed to publish interruption event',
                    'details': response.get('Entries', [])
                })
            }
        
        # Record trigger in action history
        action_history_table.put_item(
            Item={
                'action_id': f'demo-interruption-{datetime.utcnow().isoformat()}',
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'action_type': 'demo_trigger_interruption',
                'status': 'submitted',
                'parameters': {
                    'instance_id': instance_id,
                    'triggered_at': datetime.utcnow().isoformat() + 'Z'
                },
                'demo_mode': True
            }
        )
        
        return {
            'statusCode': 202,
            'headers': CORS_HEADERS,
            'body': json.dumps({
                'message': 'Interruption request submitted for approval',
                'status': 'interruption_submitted',
                'instance_id': instance_id,
                'interruption_time': (datetime.utcnow() + timedelta(minutes=2)).isoformat() + 'Z',
                'training_job_id': training_job_id
            }, cls=DecimalEncoder)
        }
        
    except Exception as e:
        logger.error(f"Error triggering interruption: {str(e)}")
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
            'body': json.dumps({'error': f'Failed to trigger interruption: {str(e)}'})
        }
