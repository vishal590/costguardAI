"""
Validation utilities for input parameters.
"""
from typing import Set

# Valid granularity values
VALID_GRANULARITIES: Set[str] = {'DAILY', 'MONTHLY', 'HOURLY'}


def validate_granularity(granularity: str) -> bool:
    """
    Validate granularity is DAILY, MONTHLY, or HOURLY.
    
    Args:
        granularity: Granularity value to validate
        
    Returns:
        True if valid, False otherwise
    """
    return granularity in VALID_GRANULARITIES


# ============================================================================
# Phase 1.5 Validation Functions
# ============================================================================

# Valid service names for Phase 1.5
VALID_SERVICES: Set[str] = {'ec2', 'lambda', 'dynamodb', 's3', 'rds'}


def validate_service_name(service: str) -> bool:
    """
    Validate service name is one of the supported services.
    
    Args:
        service: Service name to validate
        
    Returns:
        True if valid, False otherwise
    """
    return service.lower() in VALID_SERVICES


def validate_metric_value(value: float) -> bool:
    """
    Validate metric value is non-negative.
    
    Args:
        value: Metric value to validate
        
    Returns:
        True if valid (non-negative), False otherwise
    """
    return value >= 0


def validate_pricing_value(price: float) -> bool:
    """
    Validate pricing value is positive.
    
    Args:
        price: Price value to validate
        
    Returns:
        True if valid (positive), False otherwise
    """
    return price > 0


def validate_time_range(start_time: str, end_time: str) -> bool:
    """
    Validate time range is valid (start before end).
    
    Args:
        start_time: Start time (ISO format string)
        end_time: End time (ISO format string)
        
    Returns:
        True if valid, False otherwise
    """
    try:
        from datetime import datetime
        start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        return start < end
    except (ValueError, AttributeError):
        return False


# ============================================================================
# Phase 2: AI Cost Forecasting Validation Functions
# ============================================================================

# Valid forecast horizons (days)
VALID_FORECAST_DAYS: Set[int] = {7, 14, 30}

# Valid forecast granularities
VALID_FORECAST_GRANULARITIES: Set[str] = {'daily', 'weekly'}


def validate_forecast_days(days: int) -> bool:
    """
    Validate forecast horizon is 7, 14, or 30 days.
    
    Args:
        days: Number of days to forecast
        
    Returns:
        True if valid, False otherwise
    """
    return days in VALID_FORECAST_DAYS


def validate_forecast_granularity(granularity: str) -> bool:
    """
    Validate forecast granularity is 'daily' or 'weekly'.
    
    Args:
        granularity: Granularity value to validate
        
    Returns:
        True if valid, False otherwise
    """
    return granularity.lower() in VALID_FORECAST_GRANULARITIES


def validate_confidence_interval(lower: float, predicted: float, upper: float) -> bool:
    """
    Validate confidence interval bounds are correctly ordered.
    
    Args:
        lower: Lower bound
        predicted: Predicted value
        upper: Upper bound
        
    Returns:
        True if lower <= predicted <= upper, False otherwise
    """
    return lower <= predicted <= upper


def validate_forecast_data_point(data_point: dict) -> bool:
    """
    Validate forecast data point has all required fields.
    
    Args:
        data_point: Dictionary with forecast data
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = {'date', 'predicted_cost', 'confidence_lower', 'confidence_upper', 'currency'}
    return all(field in data_point for field in required_fields)


# ============================================================================
# Phase 3: Automated Cost Prevention Validation Functions
# ============================================================================

# Valid AWS services for Phase 3
VALID_PREVENTION_SERVICES: Set[str] = {
    'ec2', 'rds', 'lambda', 's3', 'dynamodb', 'ebs',
    'elasticache', 'redshift', 'ecs', 'eks',
    'nat_gateway', 'elastic_ip', 'elb',
    'sns', 'sqs', 'apigateway', 'stepfunctions',
    'glue', 'sagemaker', 'cloudfront'
}

# Valid threshold types
VALID_THRESHOLD_TYPES: Set[str] = {'warning', 'action'}

# Valid action types
VALID_ACTION_TYPES: Set[str] = {'stop', 'terminate', 'limit_concurrency', 'snapshot_delete', 'switch_billing', 'delete'}


def validate_prevention_service(service: str) -> bool:
    """
    Validate service is supported for prevention.
    
    Args:
        service: Service name to validate
        
    Returns:
        True if valid, False otherwise
    """
    return service.lower() in VALID_PREVENTION_SERVICES


def validate_threshold_type(threshold_type: str) -> bool:
    """
    Validate threshold type is 'warning' or 'action'.
    
    Args:
        threshold_type: Threshold type to validate
        
    Returns:
        True if valid, False otherwise
    """
    return threshold_type.lower() in VALID_THRESHOLD_TYPES


def validate_action_type(action: str) -> bool:
    """
    Validate action type is supported.
    
    Args:
        action: Action type to validate
        
    Returns:
        True if valid, False otherwise
    """
    return action.lower() in VALID_ACTION_TYPES


def validate_budget_utilization(utilization: float) -> bool:
    """
    Validate budget utilization is non-negative.
    
    Args:
        utilization: Utilization percentage (0-100+)
        
    Returns:
        True if valid, False otherwise
    """
    return utilization >= 0.0


def validate_idle_duration(duration_minutes: int) -> bool:
    """
    Validate idle duration is positive.
    
    Args:
        duration_minutes: Duration in minutes
        
    Returns:
        True if valid (positive), False otherwise
    """
    return duration_minutes > 0


def validate_confidence_score(confidence: float) -> bool:
    """
    Validate confidence score is between 0.0 and 1.0.
    
    Args:
        confidence: Confidence score
        
    Returns:
        True if valid (0.0 to 1.0), False otherwise
    """
    return 0.0 <= confidence <= 1.0


def validate_resource_tags(tags: dict) -> bool:
    """
    Validate resource tags dictionary.
    
    Args:
        tags: Dictionary of tags
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(tags, dict):
        return False
    
    # All keys and values should be strings
    return all(isinstance(k, str) and isinstance(v, str) for k, v in tags.items())


def validate_safety_config(config: dict) -> bool:
    """
    Validate safety configuration.
    
    Args:
        config: Safety configuration dictionary
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = {'protected_tags', 'whitelist_ids', 'minimum_idle_minutes', 'dry_run_mode'}
    
    if not all(field in config for field in required_fields):
        return False
    
    # Validate types
    if not isinstance(config['protected_tags'], list):
        return False
    if not isinstance(config['whitelist_ids'], list):
        return False
    if not isinstance(config['minimum_idle_minutes'], dict):
        return False
    if not isinstance(config['dry_run_mode'], bool):
        return False
    
    return True


def validate_approval_timeout(timeout_minutes: int) -> bool:
    """
    Validate approval timeout is reasonable (1-60 minutes).
    
    Args:
        timeout_minutes: Timeout in minutes
        
    Returns:
        True if valid, False otherwise
    """
    return 1 <= timeout_minutes <= 60


def validate_rollback_window(hours: int) -> bool:
    """
    Validate rollback window is reasonable (1-72 hours).
    
    Args:
        hours: Rollback window in hours
        
    Returns:
        True if valid, False otherwise
    """
    return 1 <= hours <= 72


# ============================================================================
# Phase 4: AI Cost Advisor Validation Functions
# ============================================================================

# Valid intent types
VALID_INTENT_TYPES: Set[str] = {
    'cost_analysis', 'optimization', 'trend_analysis', 'forecast', 'prevention'
}

# Valid insight types
VALID_INSIGHT_TYPES: Set[str] = {
    'summary', 'anomaly', 'optimization', 'forecast_alert'
}

# Valid severity levels
VALID_SEVERITY_LEVELS: Set[str] = {'info', 'warning', 'critical'}


def validate_intent_type(intent_type: str) -> bool:
    """
    Validate query intent type.
    
    Args:
        intent_type: Intent type to validate
        
    Returns:
        True if valid, False otherwise
    """
    return intent_type.lower() in VALID_INTENT_TYPES


def validate_query_length(query: str, max_length: int = 500) -> bool:
    """
    Validate query length is within limits.
    
    Args:
        query: Query string
        max_length: Maximum allowed length
        
    Returns:
        True if valid, False otherwise
    """
    return 0 < len(query) <= max_length


def validate_session_id(session_id: str) -> bool:
    """
    Validate session ID format.
    
    Args:
        session_id: Session identifier
        
    Returns:
        True if valid, False otherwise
    """
    # Basic validation: non-empty string, reasonable length
    return isinstance(session_id, str) and 1 <= len(session_id) <= 128


def validate_cache_ttl(ttl_hours: int) -> bool:
    """
    Validate cache TTL is reasonable (1-168 hours / 1 week).
    
    Args:
        ttl_hours: TTL in hours
        
    Returns:
        True if valid, False otherwise
    """
    return 1 <= ttl_hours <= 168


def validate_insight_type(insight_type: str) -> bool:
    """
    Validate insight type.
    
    Args:
        insight_type: Insight type to validate
        
    Returns:
        True if valid, False otherwise
    """
    return insight_type.lower() in VALID_INSIGHT_TYPES


def validate_severity_level(severity: str) -> bool:
    """
    Validate severity level.
    
    Args:
        severity: Severity level to validate
        
    Returns:
        True if valid, False otherwise
    """
    return severity.lower() in VALID_SEVERITY_LEVELS


def validate_recommendation_priority(priority: int) -> bool:
    """
    Validate recommendation priority (1-5).
    
    Args:
        priority: Priority value
        
    Returns:
        True if valid, False otherwise
    """
    return 1 <= priority <= 5


def validate_ai_confidence(confidence: float) -> bool:
    """
    Validate AI confidence score (0.0-1.0).
    
    Args:
        confidence: Confidence score
        
    Returns:
        True if valid, False otherwise
    """
    return 0.0 <= confidence <= 1.0


def validate_response_length(response: str, max_words: int = 500) -> bool:
    """
    Validate response length is within limits.
    
    Args:
        response: Response text
        max_words: Maximum word count
        
    Returns:
        True if valid, False otherwise
    """
    word_count = len(response.split())
    return 0 < word_count <= max_words


def validate_conversation_history_size(history: list, max_turns: int = 10) -> bool:
    """
    Validate conversation history size.
    
    Args:
        history: List of conversation turns
        max_turns: Maximum allowed turns
        
    Returns:
        True if valid, False otherwise
    """
    return 0 <= len(history) <= max_turns
