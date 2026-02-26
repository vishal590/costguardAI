"""
AWS Lambda handler for AI/ML Workload Cost Management (Phase 6).

This handler processes API Gateway requests for GPU cost tracking, workload classification,
cost-per-inference calculations, and ML optimization recommendations.
"""
import json
import logging
from typing import Dict, Any
from datetime import datetime, timedelta, UTC

from src.services.ai_ml.gpu_cost_tracker import GPUCostTracker
from src.services.ai_ml.workload_classifier import WorkloadClassifier, WorkloadClassification
from src.services.ai_ml.idle_detector import IdleGPUDetector
from src.services.ai_ml.cost_per_inference_calculator import CostPerInferenceCalculator
from src.services.ai_ml.cost_per_training_calculator import CostPerTrainingCalculator
from src.services.ai_ml.spot_instance_recommender import SpotInstanceRecommender
from src.services.ai_ml.sagemaker_cost_tracker import SageMakerCostTracker
from src.services.ai_ml.bedrock_cost_tracker import BedrockCostTracker
from src.services.ai_ml.ai_ml_cache_manager import AIMLCacheManager
from src.services.ai_ml.prevention_integration import GPUPreventionIntegration
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
        logger.info(f"Received AI/ML event: {json.dumps(event)}")
        
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')
        
        # Route to appropriate handler
        if http_method == 'GET' and path.endswith('/gpu-costs'):
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
        elif http_method == 'GET' and path.endswith('/multi-account/gpu-costs'):
            return handle_multi_account_gpu_costs(event)
        elif http_method == 'GET' and path.endswith('/multi-account/gpu-utilization'):
            return handle_multi_account_gpu_utilization(event)
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
    """
    Handle GET /api/ai-ml/gpu-costs request.
    
    Requirements: API-1.1, FR-1.1, FR-1.3, FR-1.6, NFR-5.2
    """
    try:
        query_params = event.get('queryStringParameters') or {}
        
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')
        workload_type = query_params.get('workload_type')
        instance_type = query_params.get('instance_type')
        
        # Validate dates
        if not start_date or not end_date:
            return create_error_response(400, 'MISSING_PARAMETER', 'start_date and end_date are required')
        
        if not validate_date_format(start_date) or not validate_date_format(end_date):
            return create_error_response(400, 'INVALID_DATE_FORMAT', 'Dates must be in YYYY-MM-DD format')
        
        if not validate_date_range(start_date, end_date):
            return create_error_response(400, 'INVALID_DATE_RANGE', 'start_date must be before end_date')
        
        # Check cache first
        cache_manager = get_cache_manager()
        cached_data = cache_manager.get_cached_data(
            'gpu_costs',
            start_date=start_date,
            end_date=end_date,
            workload_type=workload_type or 'all',
            instance_type=instance_type or 'all'
        )
        
        if cached_data:
            logger.info("Returning cached GPU costs data")
            return create_success_response(cached_data)
        
        # Initialize tracker
        dynamodb = get_dynamodb_client()
        tracker = GPUCostTracker(dynamodb)
        
        # Collect GPU costs
        gpu_costs = tracker.collect_gpu_costs(start_date, end_date, workload_type, instance_type)
        
        response_data = {
            'gpu_costs': [cost.to_dict() for cost in gpu_costs],
            'total_cost': sum(cost.cost for cost in gpu_costs),
            'total_gpu_hours': sum(cost.gpu_hours for cost in gpu_costs),
            'average_cost_per_gpu_hour': sum(cost.cost for cost in gpu_costs) / sum(cost.gpu_hours for cost in gpu_costs) if gpu_costs else 0
        }
        
        # Cache the response
        cache_manager.store_data(
            response_data,
            'gpu_costs',
            start_date=start_date,
            end_date=end_date,
            workload_type=workload_type or 'all',
            instance_type=instance_type or 'all'
        )
        
        return create_success_response(response_data)
    
    except Exception as e:
        logger.error(f"Error handling GPU costs request: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(500, error_response.code, error_response.message, error_response.details)


def handle_gpu_utilization(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GET /api/ai-ml/gpu-utilization request. Requirements: API-1.2"""
    return create_error_response(501, 'NOT_IMPLEMENTED', 'GPU utilization endpoint not yet implemented')


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
        dynamodb = get_dynamodb_client()
        detector = IdleGPUDetector(dynamodb)
        
        # Identify idle GPUs
        idle_gpus = detector.identify_idle_gpus(start_date, end_date, threshold)
        
        # Calculate totals
        total_wasted_cost = sum(gpu.wasted_cost for gpu in idle_gpus)
        total_idle_hours = sum(gpu.idle_hours for gpu in idle_gpus)
        
        return create_success_response({
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
    
    except Exception as e:
        logger.error(f"Error handling idle GPUs request: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(500, error_response.code, error_response.message, error_response.details)


def handle_get_workload_classification(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/ai-ml/workload-classification request.
    
    Query parameters:
    - instance_id (required): EC2 instance ID
    - start_date (required): Start date in YYYY-MM-DD format
    - end_date (required): End date in YYYY-MM-DD format
    
    Requirements: API-2.1, FR-2.1, FR-2.2, FR-2.4
    """
    try:
        query_params = event.get('queryStringParameters') or {}
        
        instance_id = query_params.get('instance_id')
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')
        
        # Validate required parameters
        if not instance_id:
            return create_error_response(400, 'MISSING_PARAMETER', 'instance_id is required')
        
        if not start_date or not end_date:
            return create_error_response(400, 'MISSING_PARAMETER', 'start_date and end_date are required')
        
        # Validate dates
        if not validate_date_format(start_date) or not validate_date_format(end_date):
            return create_error_response(400, 'INVALID_DATE_FORMAT', 'Dates must be in YYYY-MM-DD format')
        
        if not validate_date_range(start_date, end_date):
            return create_error_response(400, 'INVALID_DATE_RANGE', 'start_date must be before end_date')
        
        # Initialize classifier
        dynamodb = get_dynamodb_client()
        classifier = WorkloadClassifier(dynamodb)
        
        # Classify workload
        classification = classifier.classify_workload(instance_id, start_date, end_date)
        
        return create_success_response({
            'classification': classification.to_dict()
        })
    
    except Exception as e:
        logger.error(f"Error handling workload classification request: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(500, error_response.code, error_response.message, error_response.details)


def handle_post_workload_classification(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/ai-ml/workload-classification request (manual override).
    
    Request body:
    - instance_id (required): EC2 instance ID
    - workload_type (required): "training", "inference", or "idle"
    - reason (optional): Reason for manual classification
    
    Requirements: API-2.2, FR-2.3, FR-2.5
    """
    try:
        # Parse request body
        try:
            body = json.loads(event.get('body', '{}'))
        except json.JSONDecodeError:
            return create_error_response(400, 'INVALID_JSON', 'Request body must be valid JSON')
        
        instance_id = body.get('instance_id')
        workload_type = body.get('workload_type')
        reason = body.get('reason', 'Manual classification via API')
        
        # Validate required parameters
        if not instance_id:
            return create_error_response(400, 'MISSING_PARAMETER', 'instance_id is required')
        
        if not workload_type:
            return create_error_response(400, 'MISSING_PARAMETER', 'workload_type is required')
        
        # Validate workload type
        valid_types = ['training', 'inference', 'idle']
        if workload_type not in valid_types:
            return create_error_response(
                400,
                'INVALID_WORKLOAD_TYPE',
                f'workload_type must be one of: {", ".join(valid_types)}'
            )
        
        # Initialize classifier
        dynamodb = get_dynamodb_client()
        classifier = WorkloadClassifier(dynamodb)
        
        # Create manual classification
        classification = WorkloadClassification(
            instance_id=instance_id,
            workload_type=workload_type,
            confidence=1.0,
            classification_method="manual-tag",
            gpu_utilization_avg=0.0,
            gpu_utilization_pattern=[],
            timestamp=datetime.now(UTC).isoformat()
        )
        
        # Store manual classification
        classifier.store_classification(instance_id, classification)
        
        return create_success_response({
            'classification': classification.to_dict(),
            'message': f'Manual classification set to {workload_type} for instance {instance_id}'
        })
    
    except Exception as e:
        logger.error(f"Error handling manual workload classification request: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(500, error_response.code, error_response.message, error_response.details)


def handle_cost_per_inference(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/ai-ml/cost-per-inference request.
    
    Query parameters:
    - start_date (required): Start date in YYYY-MM-DD format
    - end_date (required): End date in YYYY-MM-DD format
    - model (optional): Model name filter
    - endpoint (optional): Endpoint identifier filter
    
    Requirements: API-3.1, FR-3.1, FR-3.4, NFR-5.2
    """
    try:
        query_params = event.get('queryStringParameters') or {}
        
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')
        model = query_params.get('model', 'default-model')
        endpoint = query_params.get('endpoint', 'default-endpoint')
        
        # Validate required parameters
        if not start_date or not end_date:
            return create_error_response(400, 'MISSING_PARAMETER', 'start_date and end_date are required')
        
        # Validate dates
        if not validate_date_format(start_date) or not validate_date_format(end_date):
            return create_error_response(400, 'INVALID_DATE_FORMAT', 'Dates must be in YYYY-MM-DD format')
        
        if not validate_date_range(start_date, end_date):
            return create_error_response(400, 'INVALID_DATE_RANGE', 'start_date must be before end_date')
        
        # Check cache first
        cache_manager = get_cache_manager()
        cached_data = cache_manager.get_cached_data(
            'cost_per_inference',
            start_date=start_date,
            end_date=end_date,
            model=model,
            endpoint=endpoint
        )
        
        if cached_data:
            logger.info("Returning cached cost-per-inference data")
            return create_success_response(cached_data)
        
        # Parse dates
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Initialize calculator
        calculator = CostPerInferenceCalculator()
        
        # Calculate cost per inference
        result = calculator.calculate_cost_per_inference(model, endpoint, start_dt, end_dt)
        
        response_data = {
            'model': result.model,
            'endpoint': result.endpoint,
            'date_range': {
                'start_date': start_date,
                'end_date': end_date
            },
            'total_requests': result.total_requests,
            'total_cost': result.total_cost,
            'cost_per_inference': result.cost_per_inference,
            'cost_breakdown': {
                'compute_cost': result.compute_cost,
                'api_cost': result.api_cost,
                'data_transfer_cost': result.data_transfer_cost
            }
        }
        
        # Cache the response
        cache_manager.store_data(
            response_data,
            'cost_per_inference',
            start_date=start_date,
            end_date=end_date,
            model=model,
            endpoint=endpoint
        )
        
        return create_success_response(response_data)
    
    except Exception as e:
        logger.error(f"Error handling cost-per-inference request: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(500, error_response.code, error_response.message, error_response.details)


def handle_inference_trends(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/ai-ml/inference-trends request.
    
    Query parameters:
    - model (required): Model name
    - endpoint (optional): Endpoint identifier (default: 'default-endpoint')
    - days (optional): Number of days to track (default: 30, max: 90)
    
    Requirements: API-3.2, FR-3.5
    """
    try:
        query_params = event.get('queryStringParameters') or {}
        
        model = query_params.get('model')
        endpoint = query_params.get('endpoint', 'default-endpoint')
        days_str = query_params.get('days', '30')
        
        # Validate required parameters
        if not model:
            return create_error_response(400, 'MISSING_PARAMETER', 'model is required')
        
        # Validate days
        try:
            days = int(days_str)
            if days < 1 or days > 90:
                return create_error_response(400, 'INVALID_DAYS', 'days must be between 1 and 90')
        except ValueError:
            return create_error_response(400, 'INVALID_DAYS', 'days must be a valid integer')
        
        # Initialize calculator
        calculator = CostPerInferenceCalculator()
        
        # Track cost trends
        trends = calculator.track_cost_trends(model, endpoint, days)
        
        return create_success_response({
            'model': model,
            'endpoint': endpoint,
            'days': days,
            'trends': [
                {
                    'date': trend.date.strftime('%Y-%m-%d'),
                    'cost_per_inference': trend.cost_per_inference,
                    'total_requests': trend.total_requests,
                    'total_cost': trend.total_cost
                }
                for trend in trends
            ]
        })
    
    except Exception as e:
        logger.error(f"Error handling inference trends request: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(500, error_response.code, error_response.message, error_response.details)


def handle_cost_per_training(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/ai-ml/cost-per-training request.
    
    Query parameters:
    - job_id (required): Training job identifier
    
    Requirements: API-4.1, FR-4.1, FR-4.3, NFR-5.2
    """
    try:
        query_params = event.get('queryStringParameters') or {}
        
        job_id = query_params.get('job_id')
        
        # Validate required parameters
        if not job_id:
            return create_error_response(400, 'MISSING_PARAMETER', 'job_id is required')
        
        # Check cache first
        cache_manager = get_cache_manager()
        cached_data = cache_manager.get_cached_data(
            'cost_per_training',
            job_id=job_id
        )
        
        if cached_data:
            logger.info("Returning cached cost-per-training data")
            return create_success_response(cached_data)
        
        # Initialize calculator
        calculator = CostPerTrainingCalculator()
        
        # Calculate cost per training
        result = calculator.calculate_cost_per_training(job_id)
        
        response_data = {
            'job_id': result.job_id,
            'model': result.model,
            'dataset': result.dataset,
            'date': result.date.strftime('%Y-%m-%d'),
            'training_hours': result.training_hours,
            'total_cost': result.total_cost,
            'cost_per_hour': result.cost_per_hour,
            'instance_type': result.instance_type,
            'cost_breakdown': {
                'compute_cost': result.compute_cost,
                'storage_cost': result.storage_cost,
                'data_transfer_cost': result.data_transfer_cost
            }
        }
        
        # Cache the response
        cache_manager.store_data(
            response_data,
            'cost_per_training',
            job_id=job_id
        )
        
        return create_success_response(response_data)
    
    except ValueError as e:
        logger.error(f"Training job not found: {str(e)}")
        return create_error_response(404, 'JOB_NOT_FOUND', str(e))
    except Exception as e:
        logger.error(f"Error handling cost-per-training request: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(500, error_response.code, error_response.message, error_response.details)


def handle_training_comparison(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/ai-ml/training-comparison request.
    
    Query parameters:
    - model (required): Model name
    - instance_types (required): Comma-separated list of instance types
    - baseline_instance (optional): Baseline instance for savings calculation
    
    Requirements: API-4.2, FR-4.6
    """
    try:
        query_params = event.get('queryStringParameters') or {}
        
        model = query_params.get('model')
        instance_types_str = query_params.get('instance_types')
        baseline_instance = query_params.get('baseline_instance')
        
        # Validate required parameters
        if not model:
            return create_error_response(400, 'MISSING_PARAMETER', 'model is required')
        
        if not instance_types_str:
            return create_error_response(400, 'MISSING_PARAMETER', 'instance_types is required')
        
        # Parse instance types
        instance_types = [t.strip() for t in instance_types_str.split(',')]
        
        if len(instance_types) < 1:
            return create_error_response(400, 'INVALID_PARAMETER', 'At least one instance type is required')
        
        # Initialize calculator
        calculator = CostPerTrainingCalculator()
        
        # Compare instance types
        comparisons = calculator.compare_instance_types(model, instance_types, baseline_instance)
        
        return create_success_response({
            'model': model,
            'baseline_instance': baseline_instance or instance_types[0],
            'comparisons': [
                {
                    'instance_type': comp.instance_type,
                    'estimated_duration_hours': comp.estimated_duration_hours,
                    'estimated_cost': comp.estimated_cost,
                    'cost_per_hour': comp.cost_per_hour,
                    'savings_vs_baseline': comp.savings_vs_baseline,
                    'savings_percent': comp.savings_percent
                }
                for comp in comparisons
            ]
        })
    
    except Exception as e:
        logger.error(f"Error handling training comparison request: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(500, error_response.code, error_response.message, error_response.details)


def handle_spot_recommendations(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/ai-ml/spot-recommendations request.
    
    Query parameters:
    - workload_id (required): Workload identifier (instance ID or job ID)
    - include_scenarios (optional): Include what-if scenarios (default: false)
    
    Requirements: API-5.1, FR-5.1, FR-5.2, FR-5.4, FR-5.5
    """
    try:
        query_params = event.get('queryStringParameters') or {}
        
        workload_id = query_params.get('workload_id')
        include_scenarios_str = query_params.get('include_scenarios', 'false')
        
        # Validate required parameters
        if not workload_id:
            return create_error_response(400, 'MISSING_PARAMETER', 'workload_id is required')
        
        # Parse include_scenarios
        include_scenarios = include_scenarios_str.lower() in ['true', '1', 'yes']
        
        # Initialize recommender
        recommender = SpotInstanceRecommender()
        
        # Get spot recommendations
        recommendations = recommender.recommend_spot_instances(workload_id)
        
        # Build response
        response_data = {
            'workload_id': workload_id,
            'recommendations': [
                {
                    'current_instance': rec.current_instance,
                    'recommended_spot_instance': rec.recommended_spot_instance,
                    'suitable': rec.suitable,
                    'reason': rec.reason,
                    'current_cost': rec.current_cost,
                    'spot_cost': rec.spot_cost,
                    'savings': rec.savings,
                    'savings_percent': rec.savings_percent,
                    'interruption_risk': rec.interruption_risk
                }
                for rec in recommendations
            ]
        }
        
        # Add what-if scenarios if requested
        if include_scenarios and recommendations and recommendations[0].suitable:
            scenarios = recommender.generate_what_if_scenarios(workload_id)
            response_data['what_if_scenarios'] = [
                {
                    'scenario_name': scenario.scenario_name,
                    'instance_type': scenario.instance_type,
                    'spot_usage_percent': scenario.spot_usage_percent,
                    'estimated_savings': scenario.estimated_savings,
                    'estimated_interruptions': scenario.estimated_interruptions,
                    'recommendation': scenario.recommendation
                }
                for scenario in scenarios
            ]
        
        return create_success_response(response_data)
    
    except Exception as e:
        logger.error(f"Error handling spot recommendations request: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(500, error_response.code, error_response.message, error_response.details)


def handle_spot_savings(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/ai-ml/spot-savings request.
    
    Query parameters:
    - current_instance (required): Current instance type
    - spot_instance (optional): Spot instance type (defaults to same as current)
    
    Requirements: API-5.2, FR-5.2
    """
    try:
        query_params = event.get('queryStringParameters') or {}
        
        current_instance = query_params.get('current_instance')
        spot_instance = query_params.get('spot_instance')
        
        # Validate required parameters
        if not current_instance:
            return create_error_response(400, 'MISSING_PARAMETER', 'current_instance is required')
        
        # Default spot instance to current instance
        if not spot_instance:
            spot_instance = current_instance
        
        # Initialize recommender
        recommender = SpotInstanceRecommender()
        
        # Calculate spot savings
        savings = recommender.calculate_spot_savings(current_instance, spot_instance)
        
        return create_success_response({
            'current_instance': savings.current_instance,
            'spot_instance': savings.spot_instance,
            'pricing': {
                'on_demand_price': savings.on_demand_price,
                'spot_price': savings.spot_price
            },
            'savings': {
                'savings_per_hour': savings.savings_per_hour,
                'savings_percent': savings.savings_percent,
                'estimated_monthly_savings': savings.estimated_monthly_savings
            },
            'interruption_risk': recommender.get_spot_interruption_risk(spot_instance)
        })
    
    except Exception as e:
        logger.error(f"Error handling spot savings request: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(500, error_response.code, error_response.message, error_response.details)


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
        
        if cached_data:
            logger.info("Returning cached SageMaker costs data")
            return create_success_response(cached_data)
        
        # Track SageMaker costs
        tracker = SageMakerCostTracker()
        costs = tracker.track_sagemaker_costs(start_date, end_date)
        
        # Build response
        response_data = {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
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
                'start_time': job.start_time.isoformat(),
                'end_time': job.end_time.isoformat() if job.end_time else None,
                'duration_hours': job.duration_hours,
                'compute_cost': job.compute_cost,
                'storage_cost': job.storage_cost,
                'data_transfer_cost': job.data_transfer_cost,
                'total_cost': job.total_cost
            }
            
            # Filter by job_type if specified
            if not job_type or job.job_type == job_type:
                response_data['job_breakdown'].append(job_data)
        
        # If filtering by job_type, recalculate totals
        if job_type:
            if job_type == 'training':
                response_data['total_cost'] = costs.training_costs
                response_data['inference_costs'] = 0
                response_data['notebook_costs'] = 0
            elif job_type == 'inference':
                response_data['total_cost'] = costs.inference_costs
                response_data['training_costs'] = 0
                response_data['notebook_costs'] = 0
            elif job_type == 'notebook':
                response_data['total_cost'] = costs.notebook_costs
                response_data['training_costs'] = 0
                response_data['inference_costs'] = 0
        
        # Cache the response
        cache_manager.store_data(
            response_data,
            'sagemaker_costs',
            start_date=params['start_date'],
            end_date=params['end_date'],
            job_type=job_type or 'all'
        )
        
        return create_success_response(response_data)
    
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
            'threshold': threshold,
            'idle_endpoint_count': len(idle_endpoints),
            'idle_endpoints': []
        }
        
        for endpoint in idle_endpoints:
            endpoint_data = {
                'endpoint_name': endpoint.endpoint_name,
                'instance_type': endpoint.instance_type,
                'instance_count': endpoint.instance_count,
                'requests_per_hour': endpoint.requests_per_hour,
                'avg_latency_ms': endpoint.avg_latency_ms,
                'cost_per_hour': endpoint.cost_per_hour,
                'is_idle': endpoint.is_idle,
                'recommendation': f'Consider scaling down or deleting this endpoint. Current cost: ${endpoint.cost_per_hour:.2f}/hour'
            }
            response_data['idle_endpoints'].append(endpoint_data)
        
        # Calculate total wasted cost
        total_wasted_cost_per_hour = sum(e.cost_per_hour for e in idle_endpoints)
        response_data['total_wasted_cost_per_hour'] = total_wasted_cost_per_hour
        response_data['estimated_monthly_waste'] = total_wasted_cost_per_hour * 24 * 30
        
        return create_success_response(response_data)
    
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
    """
    Handle GET /api/ai-ml/bedrock-costs request.
    
    Query Parameters:
    - start_date (required): Start date (YYYY-MM-DD)
    - end_date (required): End date (YYYY-MM-DD)
    - model (optional): Filter by model ID
    
    Requirements: API-7.1, NFR-5.2
    """
    try:
        # Extract query parameters
        params = event.get('queryStringParameters', {}) or {}
        
        # Validate required parameters
        if 'start_date' not in params or 'end_date' not in params:
            return create_error_response(
                400,
                'MISSING_PARAMETERS',
                'start_date and end_date are required'
            )
        
        # Parse dates
        start_date = datetime.strptime(params['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(params['end_date'], '%Y-%m-%d')
        
        # Validate date range
        if start_date > end_date:
            return create_error_response(
                400,
                'INVALID_DATE_RANGE',
                'start_date must be before or equal to end_date'
            )
        
        if end_date > datetime.now():
            return create_error_response(
                400,
                'INVALID_DATE_RANGE',
                'end_date cannot be in the future'
            )
        
        # Get optional model filter
        model_id = params.get('model')
        
        # Check cache first
        cache_manager = get_cache_manager()
        cached_data = cache_manager.get_cached_data(
            'bedrock_costs',
            start_date=params['start_date'],
            end_date=params['end_date'],
            model=model_id or 'all'
        )
        
        if cached_data:
            logger.info("Returning cached Bedrock costs data")
            return create_success_response(cached_data)
        
        # Track Bedrock costs
        tracker = BedrockCostTracker()
        bedrock_costs = tracker.track_bedrock_costs(start_date, end_date, model_id)
        
        # Build response
        response_data = {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'model_filter': model_id,
            'total_models': len(bedrock_costs),
            'models': []
        }
        
        total_cost = 0.0
        total_invocations = 0
        total_input_tokens = 0
        total_output_tokens = 0
        
        for costs in bedrock_costs:
            model_data = {
                'model_id': costs.model_id,
                'invocations': costs.invocations,
                'input_tokens': costs.input_tokens,
                'output_tokens': costs.output_tokens,
                'total_tokens': costs.input_tokens + costs.output_tokens,
                'total_cost': costs.total_cost,
                'cost_per_invocation': costs.cost_per_invocation,
                'cost_per_1k_tokens': (
                    (costs.total_cost / ((costs.input_tokens + costs.output_tokens) / 1000.0))
                    if (costs.input_tokens + costs.output_tokens) > 0 else 0.0
                )
            }
            response_data['models'].append(model_data)
            
            total_cost += costs.total_cost
            total_invocations += costs.invocations
            total_input_tokens += costs.input_tokens
            total_output_tokens += costs.output_tokens
        
        # Add totals
        response_data['totals'] = {
            'total_cost': total_cost,
            'total_invocations': total_invocations,
            'total_input_tokens': total_input_tokens,
            'total_output_tokens': total_output_tokens,
            'total_tokens': total_input_tokens + total_output_tokens,
            'avg_cost_per_invocation': (
                total_cost / total_invocations if total_invocations > 0 else 0.0
            )
        }
        
        # Cache the response
        cache_manager.store_data(
            response_data,
            'bedrock_costs',
            start_date=params['start_date'],
            end_date=params['end_date'],
            model=model_id or 'all'
        )
        
        return create_success_response(response_data)
    
    except ValueError as e:
        return create_error_response(
            400,
            'INVALID_PARAMETER',
            f'Invalid date format. Use YYYY-MM-DD: {str(e)}'
        )
    except Exception as e:
        logger.error(f"Error in handle_bedrock_costs: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_bedrock_cost_per_invocation(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/ai-ml/bedrock-cost-per-invocation request.
    
    Query Parameters:
    - start_date (required): Start date (YYYY-MM-DD)
    - end_date (required): End date (YYYY-MM-DD)
    - model (required): Model ID
    
    Requirements: API-7.2
    """
    try:
        # Extract query parameters
        params = event.get('queryStringParameters', {}) or {}
        
        # Validate required parameters
        if 'start_date' not in params or 'end_date' not in params or 'model' not in params:
            return create_error_response(
                400,
                'MISSING_PARAMETERS',
                'start_date, end_date, and model are required'
            )
        
        # Parse dates
        start_date = datetime.strptime(params['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(params['end_date'], '%Y-%m-%d')
        model_id = params['model']
        
        # Validate date range
        if start_date > end_date:
            return create_error_response(
                400,
                'INVALID_DATE_RANGE',
                'start_date must be before or equal to end_date'
            )
        
        if end_date > datetime.now():
            return create_error_response(
                400,
                'INVALID_DATE_RANGE',
                'end_date cannot be in the future'
            )
        
        # Calculate cost per invocation
        tracker = BedrockCostTracker()
        cost_per_invocation = tracker.calculate_cost_per_invocation(
            model_id, start_date, end_date
        )
        
        # Get detailed token usage
        token_usage = tracker.track_token_usage(model_id, start_date, end_date)
        
        # Get model costs for additional details
        bedrock_costs = tracker.track_bedrock_costs(start_date, end_date, model_id)
        
        if not bedrock_costs:
            return create_error_response(
                404,
                'NO_DATA',
                f'No cost data found for model {model_id} in the specified date range'
            )
        
        costs = bedrock_costs[0]
        
        # Build response
        response_data = {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'model_id': model_id,
            'cost_per_invocation': cost_per_invocation,
            'total_invocations': costs.invocations,
            'total_cost': costs.total_cost,
            'token_usage': {
                'input_tokens': token_usage['input_tokens'],
                'output_tokens': token_usage['output_tokens'],
                'total_tokens': token_usage['total_tokens'],
                'avg_input_tokens_per_invocation': (
                    token_usage['input_tokens'] / costs.invocations 
                    if costs.invocations > 0 else 0
                ),
                'avg_output_tokens_per_invocation': (
                    token_usage['output_tokens'] / costs.invocations 
                    if costs.invocations > 0 else 0
                )
            },
            'cost_breakdown': {
                'cost_per_1k_input_tokens': (
                    costs.total_cost / (costs.input_tokens / 1000.0)
                    if costs.input_tokens > 0 else 0.0
                ),
                'cost_per_1k_output_tokens': (
                    costs.total_cost / (costs.output_tokens / 1000.0)
                    if costs.output_tokens > 0 else 0.0
                ),
                'cost_per_1k_tokens': (
                    costs.total_cost / ((costs.input_tokens + costs.output_tokens) / 1000.0)
                    if (costs.input_tokens + costs.output_tokens) > 0 else 0.0
                )
            }
        }
        
        # Get model recommendations
        usage_pattern = {
            'avg_input_tokens': token_usage['input_tokens'] / costs.invocations if costs.invocations > 0 else 0,
            'avg_output_tokens': token_usage['output_tokens'] / costs.invocations if costs.invocations > 0 else 0
        }
        recommendations = tracker.recommend_cost_optimized_models(model_id, usage_pattern)
        
        if recommendations:
            response_data['recommendations'] = []
            for rec in recommendations[:3]:  # Top 3 recommendations
                response_data['recommendations'].append({
                    'recommended_model': rec.recommended_model,
                    'current_cost_per_1k_tokens': rec.current_cost_per_1k_tokens,
                    'recommended_cost_per_1k_tokens': rec.recommended_cost_per_1k_tokens,
                    'savings_percent': rec.savings_percent,
                    'estimated_monthly_savings': (
                        costs.total_cost * (rec.savings_percent / 100.0) * 30
                    ),
                    'reason': rec.reason
                })
        
        return create_success_response(response_data)
    
    except ValueError as e:
        return create_error_response(
            400,
            'INVALID_PARAMETER',
            f'Invalid date format. Use YYYY-MM-DD: {str(e)}'
        )
    except Exception as e:
        logger.error(f"Error in handle_bedrock_cost_per_invocation: {str(e)}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


def handle_gpu_prevention(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/ai-ml/gpu-prevention request.
    
    Run prevention cycle for idle GPU instances.
    
    Request body:
        {
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "threshold": 10.0,
            "dry_run": true
        }
    
    Response:
        {
            "success": true,
            "idle_gpus_found": 5,
            "actions_planned": 3,
            "actions_executed": 0,
            "total_savings": 1500.00,
            "dry_run": true
        }
    
    Requirements: IR-2.3
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        start_date = body.get('start_date')
        end_date = body.get('end_date')
        threshold = float(body.get('threshold', 10.0))
        dry_run = body.get('dry_run', True)
        
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
        
        logger.info(f"Running GPU prevention cycle: {start_date} to {end_date}, threshold={threshold}, dry_run={dry_run}")
        
        # Run prevention cycle
        result = integration.run_gpu_prevention_cycle(
            start_date=start_date,
            end_date=end_date,
            threshold=threshold,
            dry_run=dry_run
        )
        
        return create_success_response(result)
        
    except ValueError as e:
        logger.error(f"Invalid parameter in GPU prevention request: {e}")
        return create_error_response(
            400,
            'INVALID_PARAMETER',
            str(e)
        )
    except Exception as e:
        logger.error(f"Error in GPU prevention handler: {e}", exc_info=True)
        error_response = format_error(e)
        return create_error_response(
            500,
            error_response.code,
            error_response.message,
            error_response.details
        )


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
        
        return create_success_response(result)
        
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
            'total_gpu_cost': float(result.total_gpu_cost),
            'account_count': result.account_count,
            'costs_by_account': {k: float(v) for k, v in result.costs_by_account.items()},
            'costs_by_workload_type': {k: float(v) for k, v in result.costs_by_workload_type.items()},
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
