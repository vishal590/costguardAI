"""
AWS Lambda handler for AI/ML Workload Cost Management (Phase 6).

This handler processes API Gateway requests for GPU cost tracking, workload classification,
cost-per-inference calculations, and ML optimization recommendations.
"""
import json
from .services.request_json import RequestBodyError, prepare_json_body
from .services.access_control import AccessDenied, BackendAuthenticationError, BackendConfigurationError, authorize_stack_request, advisor_identity
import logging
from typing import Dict, Any
from datetime import datetime, timedelta, UTC

from src.services.ai_ml.gpu_cost_tracker import GPUCostTracker, GPUCostDataUnavailable, GPUWorkloadAttributionUnavailable
from src.services.ai_ml.workload_classifier import WorkloadClassifier, WorkloadClassification, ClassificationStoreUnavailable, ClassificationConflict
from src.services.ai_ml.idle_detector import IdleGPUDetector
from src.services.ai_ml.cost_per_inference_calculator import CostPerInferenceCalculator
from src.services.ai_ml.cost_per_training_calculator import CostPerTrainingCalculator
from src.services.ai_ml.spot_instance_recommender import SpotInstanceRecommender
from src.services.ai_ml.sagemaker_cost_tracker import SageMakerCostTracker, SageMakerDataUnavailable
from src.services.ai_ml.bedrock_cost_tracker import BedrockCostTracker, BedrockAttributionUnavailable
from src.services.ai_ml.observed_service_costs import CostObservationUnavailable
from src.services.ai_ml.ai_ml_cache_manager import AIMLCacheManager
from src.services.ai_ml.prevention_integration import GPUPreventionIntegration, GPUActionHistoryUnavailable
from src.services.dynamodb import get_dynamodb_client
from src.utils.error_handler import format_error
from src.utils.date_utils import validate_date_format, validate_date_range

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global cache manager instance (reused across Lambda invocations)
_cache_manager = None


def get_cache_manager():
    """Get or create cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        dynamodb = get_dynamodb_client()
        _cache_manager = AIMLCacheManager(dynamodb)
    return _cache_manager


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler function for AI/ML Workload Cost Management.
    
    Args:
        event: Lambda event from API Gateway
        context: Lambda context object
        
    Returns:
        Dict containing statusCode, headers, and body
    """
    try:
        logger.info("AI/ML request method=%s path=%s", event.get("httpMethod"), event.get("path"))
        
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
        
        # Match specific multi-account paths before generic GPU suffixes.
        if http_method == 'GET' and path.endswith('/multi-account/gpu-costs'):
            return handle_multi_account_gpu_costs(event)
        elif http_method == 'GET' and path.endswith('/multi-account/gpu-utilization'):
            return handle_multi_account_gpu_utilization(event)
        elif http_method == 'GET' and path.endswith('/gpu-costs'):
            return handle_gpu_costs(event)
        elif http_method == 'GET' and path.endswith('/gpu-utilization'):
            return handle_gpu_utilization(event)
        elif http_method == 'GET' and path.endswith('/idle-gpus'):
            return handle_idle_gpus(event)
        elif http_method == 'POST' and path.endswith('/gpu-prevention'):
            return handle_gpu_prevention(event)
        elif http_method == 'GET' and path.endswith('/gpu-cost-savings'):
            return handle_gpu_cost_savings(event)
        elif http_method == 'GET' and path.endswith('/workload-classification'):
            return handle_get_workload_classification(event)
        elif http_method == 'POST' and path.endswith('/workload-classification'):
            return handle_post_workload_classification(event)
        elif http_method == 'GET' and path.endswith('/cost-per-inference'):
            return handle_cost_per_inference(event)
        elif http_method == 'GET' and path.endswith('/inference-trends'):
            return handle_inference_trends(event)
        elif http_method == 'GET' and path.endswith('/cost-per-training'):
            return handle_cost_per_training(event)
        elif http_method == 'GET' and path.endswith('/training-comparison'):
            return handle_training_comparison(event)
        elif http_method == 'GET' and path.endswith('/spot-recommendations'):
            return handle_spot_recommendations(event)
        elif http_method == 'GET' and path.endswith('/spot-savings'):
            return handle_spot_savings(event)
        elif http_method == 'GET' and path.endswith('/sagemaker-costs'):
            return handle_sagemaker_costs(event)
        elif http_method == 'GET' and path.endswith('/sagemaker-idle-endpoints'):
            return handle_sagemaker_idle_endpoints(event)
        elif http_method == 'GET' and path.endswith('/bedrock-costs'):
            return handle_bedrock_costs(event)
        elif http_method == 'GET' and path.endswith('/bedrock-cost-per-invocation'):
            return handle_bedrock_cost_per_invocation(event)
        elif http_method == 'GET' and path.endswith('/multi-account/top-gpu-accounts'):
            return handle_multi_account_top_gpu_accounts(event)
        else:
            return create_error_response(
                400,
                'INVALID_REQUEST',
                f'Unsupported method {http_method} or path {path}'
            )
    
    except Exception as e:
        logger.error(f"Unhandled exception in AI/ML handler: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_gpu_costs(event: Dict[str, Any]) -> Dict[str, Any]:
    """Return observed type/usage aggregates without resource or GPU-hour attribution."""
    try:
        params = event.get('queryStringParameters') or {}
        if not params.get('start_date') or not params.get('end_date'): raise ValueError('start_date and end_date are required')
        start = datetime.strptime(params['start_date'], '%Y-%m-%d')
        end = datetime.strptime(params['end_date'], '%Y-%m-%d')
        if not 1 <= (end-start).days <= 31 or end.date() > datetime.now(UTC).date(): raise ValueError('Use 1-31 completed daily dates with an exclusive end')
        workload, instance_type = params.get('workload_type'), params.get('instance_type')
        if workload not in (None, 'unknown', 'training', 'inference', 'idle'): raise ValueError('Unknown workload filter')
        if workload not in (None, 'unknown'):
            return create_error_response(422, 'GPU_WORKLOAD_ATTRIBUTION_UNAVAILABLE', 'Type-level billing does not establish workload attribution')
        tracker = GPUCostTracker(None)
        rows = tracker.collect_gpu_costs(params['start_date'], params['end_date'], workload, instance_type)
        result = {'data_contract': 'gpu_cost_observations_v2', 'result_scope': 'observed_instance_type_usage_costs',
            'start_date': params['start_date'], 'end_date': params['end_date'],
            'gpu_costs': [row.to_dict() for row in rows], 'data_quality': tracker.last_observation_report,
            'total_cost': tracker.last_observation_report['observed_total'], 'currency': tracker.last_observation_report['currency'],
            'total_gpu_hours': None, 'average_cost_per_gpu_hour': None,
            'total_instance_hours': sum(row.instance_hours for row in rows) if rows and all(row.instance_hours is not None for row in rows) else None}
        if len(json.dumps(result).encode('utf-8')) > 2*1024*1024:
            return create_error_response(413, 'GPU_COST_REPORT_TOO_LARGE', 'Narrow dates or instance type for the observed report')
        return create_success_response(result)
    except GPUWorkloadAttributionUnavailable:
        return create_error_response(422, 'GPU_WORKLOAD_ATTRIBUTION_UNAVAILABLE', 'Workload-attributed billing is unavailable')
    except ValueError as error:
        return create_error_response(400, 'INVALID_PARAMETER', str(error))
    except Exception as error:
        logger.error('GPU provider costs unavailable: %s', type(error).__name__)
        return create_error_response(503, 'GPU_COST_DATA_UNAVAILABLE', 'GPU-family cost observations are unavailable')


def handle_gpu_utilization(event: Dict[str, Any]) -> Dict[str, Any]:
    """Read bounded configured GPU evidence, without CPU substitution."""
    try:
        params = event.get('queryStringParameters') or {}
        if not all(isinstance(params.get(key), str) and params[key] for key in ('start_date', 'end_date')):
            raise ValueError('start_date and end_date are required')
        if set(params)-{'start_date', 'end_date', 'instance_id', 'instance_type'}: raise ValueError('Unsupported GPU utilization filter')
        filters = {key: params[key] for key in ('instance_id', 'instance_type') if key in params}
        detector = IdleGPUDetector(None)
        rows = detector.observe_utilization(params['start_date'], params['end_date'], **filters)
        return create_success_response({'data_contract': 'gpu_utilization_observed_v2',
            'result_scope': 'bounded_configured_gpu_metric_observations', 'utilization': rows,
            'observation_report': detector.last_observation_report, 'applied_filters': filters,
            'start_date': params['start_date'], 'end_date': params['end_date'],
            'workload_inactivity_verified': False})
    except ValueError as error:
        return create_error_response(400, 'INVALID_PARAMETER', str(error))
    except Exception as error:
        logger.error('GPU utilization observations unavailable: %s', type(error).__name__)
        return create_error_response(503, 'GPU_EVIDENCE_UNAVAILABLE', 'GPU utilization observations are unavailable')


def handle_idle_gpus(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/ai-ml/idle-gpus request.
    
    Query parameters:
    - start_date (required): Start date in YYYY-MM-DD format
    - end_date (required): End date in YYYY-MM-DD format
    - threshold (optional): Utilization threshold percentage (default: 10%)
    
    Requirements: API-1.3, FR-1.5
    """
    try:
        query_params = event.get('queryStringParameters') or {}
        
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')
        threshold_str = query_params.get('threshold', '10.0')
        
        # Validate required parameters
        if not start_date or not end_date:
            return create_error_response(400, 'MISSING_PARAMETER', 'start_date and end_date are required')
        
        # Validate dates
        if not validate_date_format(start_date) or not validate_date_format(end_date):
            return create_error_response(400, 'INVALID_DATE_FORMAT', 'Dates must be in YYYY-MM-DD format')
        
        if not validate_date_range(start_date, end_date):
            return create_error_response(400, 'INVALID_DATE_RANGE', 'start_date must be before end_date')
        
        # Validate threshold
        try:
            threshold = float(threshold_str)
            if threshold < 0 or threshold > 100:
                return create_error_response(400, 'INVALID_THRESHOLD', 'threshold must be between 0 and 100')
        except ValueError:
            return create_error_response(400, 'INVALID_THRESHOLD', 'threshold must be a valid number')
        
        # Initialize detector
        detector = IdleGPUDetector(None)
        
        # Identify idle GPUs
        idle_gpus = detector.identify_idle_gpus(start_date, end_date, threshold)
        
        # Calculate totals
        total_wasted_cost = None
        total_idle_hours = sum(gpu.idle_hours for gpu in idle_gpus) if idle_gpus else None
        
        return create_success_response({
            'data_contract': 'gpu_low_usage_observed_v2',
            'result_scope': 'bounded_configured_gpu_metric_observations',
            'observation_report': detector.last_observation_report,
            'workload_inactivity_verified': False,
            'idle_gpus': [gpu.to_dict() for gpu in idle_gpus],
            'count': len(idle_gpus),
            'total_wasted_cost': total_wasted_cost,
            'total_idle_hours': total_idle_hours,
            'threshold': threshold,
            'date_range': {
                'start_date': start_date,
                'end_date': end_date
            }
        })
    
    except ValueError as error:
        return create_error_response(400, 'INVALID_PARAMETER', str(error))
    except Exception as e:
        logger.error(f"Error handling idle GPUs request: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(503, 'GPU_EVIDENCE_UNAVAILABLE', 'GPU observations could not be read')


def _classification_query(event):
    """Reject ambiguous declaration/assessment selections before any source reads."""
    from .services.request_query import single_valued_query
    params = single_valued_query(event, {'instance_id', 'mode', 'start_date', 'end_date', 'before_version'}, maximum_value_length=128)
    WorkloadClassifier._identity(params.get('instance_id'))
    mode = params.get('mode', 'assessment')
    if mode in ('manual_only', 'history'):
        if 'start_date' in params or 'end_date' in params:
            raise ValueError('Declaration/history modes omit metric date parameters')
        if mode == 'manual_only' and 'before_version' in params:
            raise ValueError('before_version is supported only for history')
        if 'before_version' in params:
            value = params['before_version']
            if not value.isascii() or not value.isdigit() or not 1 <= int(value) <= 2**53-1:
                raise ValueError('before_version must be a positive safe integer')
    elif mode == 'assessment':
        if 'before_version' in params: raise ValueError('before_version is supported only for history')
        if not params.get('start_date') or not params.get('end_date'):
            raise ValueError('Assessment requires start_date and end_date')
        IdleGPUDetector(None)._window(params['start_date'], params['end_date'])
    else:
        raise ValueError('mode must be manual_only, history or assessment')
    return params


def handle_get_workload_classification(event: Dict[str, Any]) -> Dict[str, Any]:
    """Read declared labels independently from uncalibrated GPU metric patterns."""
    try:
        params = _classification_query(event)
        mode = params.get('mode', 'assessment')
        classifier = WorkloadClassifier(get_dynamodb_client())
        if mode == 'history':
            before = int(params['before_version']) if 'before_version' in params else None
            return create_success_response({'data_contract': 'workload_label_history_v2',
                'history': classifier.read_label_history(params['instance_id'], before)})
        if mode == 'manual_only':
            return create_success_response({'data_contract': 'workload_label_observations_v2',
                'manual_label': classifier.read_manual_label(params['instance_id'])})
        if mode != 'assessment' or not params.get('start_date') or not params.get('end_date'):
            raise ValueError('Assessment requires start_date/end_date; manual_only needs instance_id only')
        classification = classifier.classify_workload(params['instance_id'], params['start_date'], params['end_date'])
        return create_success_response({'data_contract': 'classification_observations_v2', 'classification': classification.to_dict()})
    except ValueError as error:
        return create_error_response(400, 'INVALID_PARAMETER', str(error))
    except Exception as error:
        logger.error('Classification observations unavailable: %s', type(error).__name__)
        return create_error_response(503, 'CLASSIFICATION_UNAVAILABLE', 'Declared labels or classification evidence are unavailable')


def handle_post_workload_classification(event: Dict[str, Any]) -> Dict[str, Any]:
    """Persist an operator-declared label only after a versioned durable write."""
    try:
        body = prepare_json_body(event)
        if set(body)-{'instance_id', 'workload_type', 'reason', 'expected_version', 'operation'}: raise ValueError('Unsupported manual-label field')
        classifier = WorkloadClassifier(get_dynamodb_client())
        actor = (event.get('_principal') or {}).get('subject')
        operation = body.get('operation', 'set')
        if operation == 'clear':
            if 'workload_type' in body: raise ValueError('Clear must omit workload_type')
            manual = classifier.clear_manual_label(body.get('instance_id'), body.get('expected_version'), actor, body.get('reason', ''))
        elif operation == 'set':
            manual = classifier.save_manual_label(body.get('instance_id'), body.get('workload_type'),
                body.get('expected_version'), actor, body.get('reason', ''))
        else:
            raise ValueError('operation must be set or clear')
        committed_version = body['expected_version']+1
        return create_success_response({'data_contract': 'workload_label_observations_v2', 'manual_label': manual,
            'write_observation': {'committed_version': committed_version, 'operation': operation,
                'readback_at_committed_version': manual['version'] == committed_version},
            'message': 'Application declaration updated; workload identity remains unverified'})
    except ClassificationConflict as error:
        return create_error_response(409, 'CLASSIFICATION_CONFLICT', str(error))
    except ValueError as error:
        return create_error_response(400, 'INVALID_PARAMETER', str(error))
    except Exception as error:
        logger.error('Manual workload label save unavailable: %s', type(error).__name__)
        return create_error_response(503, 'CLASSIFICATION_STORE_UNAVAILABLE', 'Manual workload label could not be read or saved')


def handle_cost_per_inference(event: Dict[str, Any]) -> Dict[str, Any]:
    """Read one explicitly selected counter with unavailable attributed money."""
    try:
        params = event.get('queryStringParameters') or {}
        if not all(params.get(key) for key in ('start_date', 'end_date', 'source', 'endpoint')):
            raise ValueError('start_date, end_date, source and endpoint are required')
        start = datetime.strptime(params['start_date'], '%Y-%m-%d')
        end = datetime.strptime(params['end_date'], '%Y-%m-%d')
        calculator = CostPerInferenceCalculator()
        result = calculator.calculate_cost_per_inference(params.get('model'), params['endpoint'], start, end,
            source=params['source'], variant=params.get('variant'), stage=params.get('stage'))
        return create_success_response({'data_contract': 'inference_counter_observations_v2',
            'model': result.model, 'model_label_verified': False, 'endpoint': result.endpoint, 'source': result.source,
            'start_date': start.date().isoformat(), 'end_date': end.date().isoformat(),
            'total_requests': result.total_requests, 'total_cost': None, 'cost_per_inference': None,
            'cost_attribution_status': 'unavailable', 'threshold_exceeded': None,
            'cost_breakdown': {'compute_cost': None, 'api_cost': None, 'data_transfer_cost': None},
            'data_quality': result.data_quality})
    except ValueError as error:
        return create_error_response(400, 'INVALID_PARAMETER', str(error))
    except Exception as error:
        logger.error('Inference counter unavailable: %s', type(error).__name__)
        return create_error_response(503, 'INFERENCE_COUNTER_UNAVAILABLE', 'Selected inference telemetry is unavailable')


def handle_inference_trends(event: Dict[str, Any]) -> Dict[str, Any]:
    """Completed-day selected-counter observations; missing days/costs remain null."""
    try:
        params = event.get('queryStringParameters') or {}
        if not params.get('endpoint') or not params.get('source'): raise ValueError('source and endpoint are required')
        days = int(params.get('days', '30'))
        calculator = CostPerInferenceCalculator()
        trends = calculator.track_cost_trends(params.get('model'), params['endpoint'], days,
            source=params['source'], variant=params.get('variant'), stage=params.get('stage'))
        return create_success_response({'data_contract': 'inference_counter_trends_v2',
            'source': params['source'], 'endpoint': params['endpoint'], 'cost_attribution_status': 'unavailable',
            'trends': [{'date': row.date.date().isoformat(), 'total_requests': row.total_requests,
                        'total_cost': None, 'cost_per_inference': None, 'observation_status': row.observation_status} for row in trends],
            'data_quality': calculator.last_counter_observation})
    except ValueError as error:
        return create_error_response(400, 'INVALID_PARAMETER', str(error))
    except Exception as error:
        logger.error('Inference counter trend unavailable: %s', type(error).__name__)
        return create_error_response(503, 'INFERENCE_COUNTER_UNAVAILABLE', 'Selected counter trend is unavailable')


def handle_cost_per_training(event: Dict[str, Any]) -> Dict[str, Any]:
    """Observe one explicit training/resource source without attributing account charges."""
    try:
        params = event.get('queryStringParameters') or {}
        if not params.get('job_id') or not params.get('source'): raise ValueError('job_id and source are required')
        result = CostPerTrainingCalculator().calculate_cost_per_training(params['job_id'], source=params['source'])
        return create_success_response({'data_contract': 'training_metadata_observed_v2',
            'result_scope': 'resource_or_job_metadata_without_billed_cost_join', 'job_id': result.job_id,
            'model': result.model, 'dataset': result.dataset, 'date': result.date.isoformat() if result.date else None,
            'instance_type': result.instance_type, 'training_hours': result.training_hours,
            'total_cost': None, 'cost_per_hour': None, 'cost_attribution_status': 'unavailable',
            'cost_breakdown': {'compute_cost': None, 'storage_cost': None, 'data_transfer_cost': None},
            'metadata': result.metadata})
    except ValueError as error:
        return create_error_response(400, 'INVALID_PARAMETER', str(error))
    except Exception as error:
        logger.error('Training metadata unavailable: %s', type(error).__name__)
        return create_error_response(503, 'TRAINING_METADATA_UNAVAILABLE', 'Training/resource metadata is unavailable')


def handle_training_comparison(event: Dict[str, Any]) -> Dict[str, Any]:
    """Explain unavailable benchmark comparisons without fabricated speed/rate estimates."""
    try:
        params = event.get('queryStringParameters') or {}
        if not params.get('model') or not params.get('instance_types'): raise ValueError('model and instance_types are required')
        selected = [item.strip() for item in params['instance_types'].split(',')]
        calculator = CostPerTrainingCalculator()
        comparisons = calculator.compare_instance_types(params['model'], selected, params.get('baseline_instance'))
        return create_success_response({'data_contract': 'training_comparison_scope_v2', 'comparisons': comparisons,
            'comparison_status': 'unavailable', 'data_quality': calculator.last_comparison_report})
    except ValueError as error:
        return create_error_response(400, 'INVALID_PARAMETER', str(error))
    except Exception as error:
        logger.error('Training comparison unavailable: %s', type(error).__name__)
        return create_error_response(503, 'TRAINING_COMPARISON_UNAVAILABLE', 'Training comparison is unavailable')


def handle_spot_recommendations(event: Dict[str, Any]) -> Dict[str, Any]:
    """Observe matched EC2 reference quotes without suitability/savings defaults."""
    try:
        params = event.get('queryStringParameters') or {}
        if not params.get('workload_id'): raise ValueError('workload_id must identify one EC2 instance')
        include = params.get('include_scenarios', 'false')
        if include not in ('true', 'false'): raise ValueError('include_scenarios must be true or false')
        result = SpotInstanceRecommender().observe_instance_quotes(params['workload_id'])
        if include == 'true':
            result['scenarios'] = []
            result['scenario_status'] = 'unavailable_without_explicit_usage_interruption_and_compatibility_evidence'
        return create_success_response(result)
    except ValueError as error:
        return create_error_response(400, 'INVALID_PARAMETER', str(error))
    except Exception as error:
        logger.error('Spot quote observations unavailable: %s', type(error).__name__)
        return create_error_response(503, 'SPOT_QUOTE_UNAVAILABLE', 'Selected instance quote observations are unavailable')


def handle_spot_savings(event: Dict[str, Any]) -> Dict[str, Any]:
    """Instance-type names alone do not establish a scoped savings comparison."""
    params = event.get('queryStringParameters') or {}
    if not params.get('current_instance'): return create_error_response(400, 'MISSING_PARAMETER', 'current_instance is required')
    return create_success_response({'data_contract': 'spot_savings_scope_v2', 'status': 'unavailable',
        'current_instance': params['current_instance'], 'spot_instance': params.get('spot_instance'),
        'savings_per_hour': None, 'savings_percent': None, 'estimated_monthly_savings': None,
        'interruption_risk': None, 'reason': 'Use explicit EC2 instance quote observations; types alone do not establish AZ/profile/workload suitability'})


def handle_sagemaker_costs(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/ai-ml/sagemaker-costs request.
    
    Query Parameters:
    - start_date (required): Start date (YYYY-MM-DD)
    - end_date (required): End date (YYYY-MM-DD)
    - job_type (optional): Filter by job type (training, inference, notebook)
    
    Requirements: API-6.1, FR-6.1, FR-6.2, FR-6.3, FR-6.4, NFR-5.2
    """
    try:
        params = event.get('queryStringParameters', {}) or {}
        
        # Validate required parameters
        if 'start_date' not in params or 'end_date' not in params:
            return create_error_response(
                400,
                'MISSING_PARAMETER',
                'start_date and end_date are required'
            )
        
        # Parse and validate dates
        try:
            start_date = datetime.strptime(params['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(params['end_date'], '%Y-%m-%d')
        except ValueError as e:
            return create_error_response(
                400,
                'INVALID_DATE_FORMAT',
                f'Invalid date format. Use YYYY-MM-DD: {str(e)}'
            )
        
        # Validate date range (start must be before end)
        if start_date >= end_date:
            return create_error_response(
                400,
                'INVALID_DATE_RANGE',
                'start_date must be before end_date'
            )
        
        if (end_date-start_date).days > 31 or end_date.date() > datetime.now(UTC).date():
            return create_error_response(400, 'INVALID_DATE_RANGE', 'Use at most 31 completed daily dates with an exclusive end')

        # Get optional job_type filter
        job_type = params.get('job_type')
        if job_type and job_type not in ['training', 'inference', 'notebook']:
            return create_error_response(
                400,
                'INVALID_JOB_TYPE',
                'job_type must be one of: training, inference, notebook'
            )
        
        # Check cache first
        cache_manager = get_cache_manager()
        cached_data = cache_manager.get_cached_data(
            'sagemaker_costs',
            start_date=params['start_date'],
            end_date=params['end_date'],
            job_type=job_type or 'all'
        )
        
        if isinstance(cached_data, dict) and cached_data.get('data_contract') == 'sagemaker_observed_v2' and len(json.dumps(cached_data, default=str).encode('utf-8')) <= 2*1024*1024:
            logger.info("Returning cached SageMaker costs data")
            return create_success_response(cached_data)
        
        # Track SageMaker costs
        tracker = SageMakerCostTracker()
        costs = tracker.track_sagemaker_costs(start_date, end_date)
        
        # Build response
        response_data = {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'data_contract': 'sagemaker_observed_v2', 'result_scope': 'observed_provider_costs',
            'currency': costs.currency, 'unclassified_costs': costs.unclassified_costs,
            'data_quality': costs.data_quality,
            'training_costs': costs.training_costs,
            'inference_costs': costs.inference_costs,
            'notebook_costs': costs.notebook_costs,
            'total_cost': costs.total_cost,
            'job_breakdown': []
        }
        
        # Add job breakdown
        for job in costs.job_breakdown:
            job_data = {
                'job_name': job.job_name,
                'job_type': job.job_type,
                'instance_type': job.instance_type,
                'start_time': job.start_time.isoformat() if job.start_time else None,
                'end_time': job.end_time.isoformat() if job.end_time else None,
                'duration_hours': job.duration_hours,
                'compute_cost': job.compute_cost,
                'storage_cost': job.storage_cost,
                'data_transfer_cost': job.data_transfer_cost,
                'total_cost': job.total_cost, 'cost_status': job.cost_status, 'cost_basis': job.cost_basis
            }
            
            # Filter by job_type if specified
            if not job_type or job.job_type == job_type:
                response_data['job_breakdown'].append(job_data)
        
        # If filtering by job_type, recalculate totals
        if job_type:
            response_data['result_scope'] = 'observed_selected_job_category'
            response_data['overall_observed_total'] = costs.total_cost
            response_data['unclassified_costs'] = None
            if job_type == 'training':
                response_data['total_cost'] = costs.training_costs
                response_data['inference_costs'] = None
                response_data['notebook_costs'] = None
            elif job_type == 'inference':
                response_data['total_cost'] = costs.inference_costs
                response_data['training_costs'] = None
                response_data['notebook_costs'] = None
            elif job_type == 'notebook':
                response_data['total_cost'] = costs.notebook_costs
                response_data['training_costs'] = None
                response_data['inference_costs'] = None
        
        if len(json.dumps(response_data, default=str).encode('utf-8')) > 2*1024*1024:
            return create_error_response(413, 'SAGEMAKER_REPORT_TOO_LARGE', 'SageMaker report exceeds the response limit')
        # Cache the response
        cache_manager.store_data(
            response_data,
            'sagemaker_costs',
            start_date=params['start_date'],
            end_date=params['end_date'],
            job_type=job_type or 'all'
        )
        
        return create_success_response(response_data)
    
    except SageMakerDataUnavailable:
        return create_error_response(503, 'SAGEMAKER_DATA_UNAVAILABLE', 'SageMaker provider cost observations are unavailable')
    except ValueError as error:
        return create_error_response(400, 'INVALID_DATE_RANGE', str(error))
    except Exception as e:
        logger.error(f"Error in handle_sagemaker_costs: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_sagemaker_idle_endpoints(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/ai-ml/sagemaker-idle-endpoints request.
    
    Query Parameters:
    - threshold (optional): Minimum requests per hour (default: 10)
    
    Requirements: API-6.2, FR-6.6
    """
    try:
        params = event.get('queryStringParameters', {}) or {}
        
        # Get threshold parameter (default: 10)
        threshold = int(params.get('threshold', 10))
        
        if threshold < 0:
            return create_error_response(
                400,
                'INVALID_THRESHOLD',
                'threshold must be non-negative'
            )
        
        # Identify idle endpoints
        tracker = SageMakerCostTracker()
        idle_endpoints = tracker.identify_idle_endpoints(threshold)
        
        # Build response
        response_data = {
            'threshold': threshold, 'result_scope': 'bounded_observed_low_usage_candidates',
            'idle_endpoint_count': len(idle_endpoints),
            'idle_endpoints': [],
            'observation_report': tracker.last_idle_report,
            'workload_inactivity_verified': False, 'savings_status': 'unavailable'
        }
        
        for endpoint in idle_endpoints:
            endpoint_data = {
                'endpoint_name': endpoint.endpoint_name,
                'instance_type': endpoint.instance_type,
                'instance_count': endpoint.instance_count,
                'requests_per_hour': endpoint.requests_per_hour,
                'avg_latency_ms': endpoint.avg_latency_ms,
                'cost_status': endpoint.cost_status, 'cost_scope': endpoint.cost_scope,
                'pricing_provenance': endpoint.pricing_provenance,
                'cost_per_hour': endpoint.cost_per_hour,
                'is_idle': endpoint.is_idle,
                'observation_status': endpoint.observation_status, 'window_start': endpoint.window_start,
                'window_end': endpoint.window_end, 'latency_basis': endpoint.latency_basis,
                'recommendation': 'Review workload requirements before changing capacity; observed low usage does not establish safe removal.'
            }
            response_data['idle_endpoints'].append(endpoint_data)
        
        # Calculate total wasted cost
        total_wasted_cost_per_hour = None  # No verified billing-profile rate is available for this evidence adapter.
        response_data['total_wasted_cost_per_hour'] = total_wasted_cost_per_hour
        response_data['estimated_monthly_waste'] = None
        
        if len(json.dumps(response_data).encode('utf-8')) > 2*1024*1024:
            return create_error_response(413, 'SAGEMAKER_EVIDENCE_TOO_LARGE', 'Endpoint evidence exceeds the response limit')
        return create_success_response(response_data)
    
    except SageMakerDataUnavailable:
        return create_error_response(503, 'SAGEMAKER_EVIDENCE_UNAVAILABLE', 'Endpoint listing is unavailable')
    except ValueError as e:
        return create_error_response(
            400,
            'INVALID_PARAMETER',
            f'Invalid threshold value: {str(e)}'
        )
    except Exception as e:
        logger.error(f"Error in handle_sagemaker_idle_endpoints: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_bedrock_costs(event: Dict[str, Any]) -> Dict[str, Any]:
    """Return observed service/usage-type charges without guessed model/token joins."""
    try:
        params = event.get('queryStringParameters') or {}
        if not params.get('start_date') or not params.get('end_date'):
            raise ValueError('start_date and end_date are required')
        start = datetime.strptime(params['start_date'], '%Y-%m-%d')
        end = datetime.strptime(params['end_date'], '%Y-%m-%d')
        if not 1 <= (end-start).days <= 31 or end.date() > datetime.now(UTC).date():
            raise ValueError('Use 1-31 completed daily dates with an exclusive end')
        if params.get('model_id'):
            return create_error_response(422, 'MODEL_COST_ATTRIBUTION_UNAVAILABLE', 'Usage-type charges are not verified model-attributed costs')
        cache = get_cache_manager()
        cached = cache.get_cached_data('bedrock_costs', start_date=params['start_date'], end_date=params['end_date'], model_id='all')
        if isinstance(cached, dict) and cached.get('data_contract') == 'bedrock_observed_v2' and len(json.dumps(cached, default=str).encode()) <= 2*1024*1024:
            return create_success_response(cached)
        tracker = BedrockCostTracker()
        tracker.track_bedrock_costs(start, end)
        result = tracker.last_cost_report
        if len(json.dumps(result).encode()) > 2*1024*1024:
            return create_error_response(413, 'BEDROCK_REPORT_TOO_LARGE', 'Observed Bedrock report exceeds the response limit')
        cache.store_data(result, 'bedrock_costs', start_date=params['start_date'], end_date=params['end_date'], model_id='all')
        return create_success_response(result)
    except ValueError as error:
        return create_error_response(400, 'INVALID_DATE_RANGE', str(error))
    except (CostObservationUnavailable, BedrockAttributionUnavailable):
        return create_error_response(503, 'BEDROCK_DATA_UNAVAILABLE', 'Observed Bedrock charges are unavailable')
    except Exception as error:
        logger.error('Bedrock report unavailable: %s', type(error).__name__)
        return create_error_response(503, 'BEDROCK_DATA_UNAVAILABLE', 'Observed Bedrock charges are unavailable')


def handle_bedrock_cost_per_invocation(event: Dict[str, Any]) -> Dict[str, Any]:
    """Expose measured runtime usage separately from unavailable cost attribution."""
    try:
        params = event.get('queryStringParameters') or {}
        if not all(params.get(key) for key in ('start_date', 'end_date', 'model')):
            raise ValueError('start_date, end_date and model are required')
        start = datetime.strptime(params['start_date'], '%Y-%m-%d')
        end = datetime.strptime(params['end_date'], '%Y-%m-%d')
        tracker = BedrockCostTracker()
        usage = tracker.track_token_usage(params['model'], start, end)
        result = {'data_contract': 'bedrock_usage_observed_v2', 'model_id': params['model'],
            'start_date': start.date().isoformat(), 'end_date': end.date().isoformat(),
            'invocations': usage['invocations'], 'input_tokens': usage['input_tokens'],
            'output_tokens': usage['output_tokens'], 'total_tokens': usage['total_tokens'],
            'total_cost': None, 'cost_per_invocation': None,
            'cost_attribution_status': 'unavailable', 'data_quality': usage,
            'cost_breakdown': {'cost_per_1k_input_tokens': None, 'cost_per_1k_output_tokens': None, 'cost_per_1k_tokens': None},
            'recommendations': []}
        return create_success_response(result)
    except ValueError as error:
        return create_error_response(400, 'INVALID_PARAMETER', str(error))
    except Exception as error:
        logger.error('Bedrock runtime usage unavailable: %s', type(error).__name__)
        return create_error_response(503, 'BEDROCK_USAGE_UNAVAILABLE', 'Runtime usage observations are unavailable')


def handle_gpu_prevention(event: Dict[str, Any]) -> Dict[str, Any]:
    """Run a read-only GPU review preview, never simulated resource execution."""
    try:
        body = prepare_json_body(event)
        if set(body)-{'start_date', 'end_date', 'threshold', 'dry_run'}:
            raise ValueError('Unsupported GPU preview field')
        if not all(isinstance(body.get(key), str) and body[key] for key in ('start_date', 'end_date')):
            raise ValueError('start_date and end_date are required')
        dry_run = body.get('dry_run', True)
        if not isinstance(dry_run, bool): raise ValueError('dry_run must be boolean')
        if not dry_run:
            return create_error_response(409, 'GPU_EXECUTION_UNAVAILABLE', 'Only read-only GPU review previews are supported')
        detector = IdleGPUDetector(None)
        integration = GPUPreventionIntegration(detector, None, None)
        result = integration.run_gpu_prevention_cycle(body['start_date'], body['end_date'], body.get('threshold', 10.0), True)
        return create_success_response(result)
    except ValueError as error:
        return create_error_response(400, 'INVALID_PARAMETER', str(error))
    except Exception as error:
        logger.error('GPU preview unavailable: %s', type(error).__name__)
        return create_error_response(503, 'GPU_PREVIEW_UNAVAILABLE', 'GPU review preview is unavailable')


def handle_gpu_cost_savings(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/ai-ml/gpu-cost-savings request.
    
    Get GPU cost savings from prevention actions.
    
    Query parameters:
        - start_date: Start date (YYYY-MM-DD)
        - end_date: End date (YYYY-MM-DD)
    
    Response:
        {
            "period_start": "2024-01-01",
            "period_end": "2024-01-31",
            "total_savings": 5000.00,
            "actions_count": 10,
            "instances_stopped": 7,
            "instances_terminated": 3,
            "avg_idle_hours": 48.5,
            "breakdown_by_instance_type": {
                "p3.2xlarge": 1500.00,
                "g4dn.xlarge": 500.00,
                "g5.2xlarge": 3000.00
            }
        }
    
    Requirements: IR-2.3
    """
    try:
        # Parse query parameters
        params = event.get('queryStringParameters', {}) or {}
        
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        
        # Validate required parameters
        if not start_date or not end_date:
            return create_error_response(
                400,
                'MISSING_PARAMETERS',
                'start_date and end_date are required'
            )
        
        # Validate date formats
        if not validate_date_format(start_date) or not validate_date_format(end_date):
            return create_error_response(
                400,
                'INVALID_DATE_FORMAT',
                'Dates must be in YYYY-MM-DD format'
            )
        
        # Validate date range
        if not validate_date_range(start_date, end_date):
            return create_error_response(
                400,
                'INVALID_DATE_RANGE',
                'end_date must be after start_date'
            )
        
        # Initialize components
        dynamodb = get_dynamodb_client()
        idle_gpu_detector = IdleGPUDetector(dynamodb)
        
        # Note: prevention_engine would be the Phase 3 PreventionEngine instance
        # For now, we pass None as it's optional for the integration to work
        prevention_engine = None
        
        # Initialize prevention integration
        integration = GPUPreventionIntegration(
            idle_gpu_detector=idle_gpu_detector,
            prevention_engine=prevention_engine,
            dynamodb_client=dynamodb
        )
        
        logger.info(f"Retrieving GPU cost savings: {start_date} to {end_date}")
        
        # Get cost savings
        savings = integration.get_gpu_cost_savings(
            start_date=start_date,
            end_date=end_date
        )
        
        # Convert to dictionary for JSON response
        result = savings.to_dict()
        
        if len(json.dumps(result).encode('utf-8')) > 2*1024*1024:
            return create_error_response(413, 'GPU_HISTORY_TOO_LARGE', 'Reduce the requested GPU history period')
        return create_success_response(result)
        
    except ValueError as error:
        return create_error_response(400, 'INVALID_DATE_RANGE', str(error))
    except GPUActionHistoryUnavailable:
        return create_error_response(503, 'GPU_HISTORY_UNAVAILABLE', 'Historical GPU action storage is unavailable or not configured')
    except Exception as e:
        logger.error(f"Error in GPU cost savings handler: {e}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def create_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a successful API Gateway response."""
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(data)
    }


def create_error_response(status_code: int, error_code: str, message: str, details: Dict[str, Any] = None) -> Dict[str, Any]:
    """Create an error API Gateway response."""
    body = {
        'error': {
            'code': error_code,
            'message': message
        }
    }
    if details:
        body['error']['details'] = details
    
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(body)
    }


# Multi-Account GPU Cost Handlers

def handle_multi_account_gpu_costs(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/ai-ml/multi-account/gpu-costs
    
    Collect and aggregate GPU costs across multiple accounts in an organization.
    
    Query Parameters:
        - org_id: Organization ID (required)
        - account_ids: Comma-separated list of account IDs (required)
        - start_date: Start date in YYYY-MM-DD format (required)
        - end_date: End date in YYYY-MM-DD format (required)
        - role_name: Cross-account role name (optional, default: CostGuardCollectorRole)
        - external_id: External ID for role assumption (optional)
    """
    try:
        from src.services.ai_ml.multi_account_gpu_integration import MultiAccountGPUIntegration
        from datetime import datetime
        
        params = event.get('queryStringParameters', {}) or {}
        
        # Validate required parameters
        org_id = params.get('org_id')
        account_ids_str = params.get('account_ids')
        start_date_str = params.get('start_date')
        end_date_str = params.get('end_date')
        
        if not all([org_id, account_ids_str, start_date_str, end_date_str]):
            return create_error_response(
                400,
                'MISSING_PARAMETERS',
                'Required parameters: org_id, account_ids, start_date, end_date'
            )
        
        # Parse account IDs
        account_ids = [aid.strip() for aid in account_ids_str.split(',')]
        
        # Validate dates
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError as e:
            return create_error_response(
                400,
                'INVALID_DATE_FORMAT',
                f'Dates must be in YYYY-MM-DD format: {str(e)}'
            )
        
        # Optional parameters
        role_name = params.get('role_name', 'CostGuardCollectorRole')
        external_id = params.get('external_id')
        
        # Collect multi-account GPU costs
        integration = MultiAccountGPUIntegration()
        result = integration.collect_gpu_costs_all_accounts(
            org_id=org_id,
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date,
            role_name=role_name,
            external_id=external_id
        )
        
        # Format response
        response_data = {
            'org_id': result.org_id,
            'start_date': result.start_date.isoformat(),
            'end_date': result.end_date.isoformat(),
            'data_contract': 'gpu_multi_cost_observations_v2',
            'total_gpu_cost': float(result.total_gpu_cost) if result.total_gpu_cost is not None else None,
            'observed_partial_cost': float(result.observed_partial_cost) if result.observed_partial_cost is not None else None,
            'account_data_quality': result.account_data_quality, 'result_scope': result.result_scope,
            'account_count': result.account_count,
            'costs_by_account': {k: float(v) if v is not None else None for k, v in result.costs_by_account.items()},
            'costs_by_workload_type': {k: float(v) if v is not None else None for k, v in result.costs_by_workload_type.items()},
            'costs_by_instance_type': {k: float(v) for k, v in result.costs_by_instance_type.items()},
            'gpu_hours_by_account': result.gpu_hours_by_account,
            'utilization_by_account': result.utilization_by_account
        }
        
        return create_success_response(response_data)
        
    except Exception as e:
        logger.error(f"Error collecting multi-account GPU costs: {str(e)}", exc_info=True)
        return create_error_response(
            500,
            'INTERNAL_ERROR',
            f'Failed to collect multi-account GPU costs: {str(e)}'
        )


def handle_multi_account_gpu_utilization(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/ai-ml/multi-account/gpu-utilization
    
    Get organization-wide GPU utilization metrics.
    
    Query Parameters:
        - org_id: Organization ID (required)
        - account_ids: Comma-separated list of account IDs (required)
        - start_date: Start date in YYYY-MM-DD format (required)
        - end_date: End date in YYYY-MM-DD format (required)
    """
    try:
        from src.services.ai_ml.multi_account_gpu_integration import MultiAccountGPUIntegration
        from datetime import datetime
        
        params = event.get('queryStringParameters', {}) or {}
        
        # Validate required parameters
        org_id = params.get('org_id')
        account_ids_str = params.get('account_ids')
        start_date_str = params.get('start_date')
        end_date_str = params.get('end_date')
        
        if not all([org_id, account_ids_str, start_date_str, end_date_str]):
            return create_error_response(
                400,
                'MISSING_PARAMETERS',
                'Required parameters: org_id, account_ids, start_date, end_date'
            )
        
        # Parse account IDs
        account_ids = [aid.strip() for aid in account_ids_str.split(',')]
        
        # Validate dates
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError as e:
            return create_error_response(
                400,
                'INVALID_DATE_FORMAT',
                f'Dates must be in YYYY-MM-DD format: {str(e)}'
            )
        
        # Get organization GPU utilization
        integration = MultiAccountGPUIntegration()
        result = integration.get_organization_gpu_utilization(
            org_id=org_id,
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date
        )
        
        return create_success_response(result)
        
    except Exception as e:
        logger.error(f"Error getting organization GPU utilization: {str(e)}", exc_info=True)
        return create_error_response(
            500,
            'INTERNAL_ERROR',
            f'Failed to get organization GPU utilization: {str(e)}'
        )


def handle_multi_account_top_gpu_accounts(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/ai-ml/multi-account/top-gpu-accounts
    
    Get top GPU spending accounts in organization.
    
    Query Parameters:
        - org_id: Organization ID (required)
        - account_ids: Comma-separated list of account IDs (required)
        - start_date: Start date in YYYY-MM-DD format (required)
        - end_date: End date in YYYY-MM-DD format (required)
        - limit: Number of top accounts to return (optional, default: 5)
    """
    try:
        from src.services.ai_ml.multi_account_gpu_integration import MultiAccountGPUIntegration
        from datetime import datetime
        
        params = event.get('queryStringParameters', {}) or {}
        
        # Validate required parameters
        org_id = params.get('org_id')
        account_ids_str = params.get('account_ids')
        start_date_str = params.get('start_date')
        end_date_str = params.get('end_date')
        
        if not all([org_id, account_ids_str, start_date_str, end_date_str]):
            return create_error_response(
                400,
                'MISSING_PARAMETERS',
                'Required parameters: org_id, account_ids, start_date, end_date'
            )
        
        # Parse account IDs
        account_ids = [aid.strip() for aid in account_ids_str.split(',')]
        
        # Validate dates
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError as e:
            return create_error_response(
                400,
                'INVALID_DATE_FORMAT',
                f'Dates must be in YYYY-MM-DD format: {str(e)}'
            )
        
        # Optional limit parameter
        limit = int(params.get('limit', 5))
        
        # Get top GPU spending accounts
        integration = MultiAccountGPUIntegration()
        result = integration.get_top_gpu_spending_accounts(
            org_id=org_id,
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        return create_success_response({'top_accounts': result})
        
    except Exception as e:
        logger.error(f"Error getting top GPU spending accounts: {str(e)}", exc_info=True)
        return create_error_response(
            500,
            'INTERNAL_ERROR',
            f'Failed to get top GPU spending accounts: {str(e)}'
        )
