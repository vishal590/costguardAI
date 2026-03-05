"""
AWS X-Ray Tracing Utility for Autonomous Action Loops

Provides X-Ray tracing instrumentation for Lambda functions to enable
distributed tracing and performance monitoring.

Usage:
    from autonomous.utils.xray_tracing import trace_subsegment
    
    @trace_subsegment('analyze_cost_patterns')
    def analyze_cost_patterns(days: int):
        # Function implementation
        pass

Requirements: 9.9, 12.5
"""

import functools
import os
from typing import Any, Callable, Dict, Optional

# Check if X-Ray is available
try:
    from aws_xray_sdk.core import xray_recorder
    from aws_xray_sdk.core import patch_all
    XRAY_AVAILABLE = True
except ImportError:
    XRAY_AVAILABLE = False
    print("WARNING: aws-xray-sdk not installed, tracing disabled")

# Patch AWS SDK clients for automatic tracing
if XRAY_AVAILABLE:
    patch_all()


def trace_subsegment(name: str, metadata: Optional[Dict[str, Any]] = None):
    """
    Decorator to trace a function as an X-Ray subsegment.
    
    Args:
        name: Name of the subsegment
        metadata: Optional metadata to attach to the subsegment
        
    Returns:
        Decorated function with X-Ray tracing
        
    Example:
        @trace_subsegment('checkpoint_save', {'operation': 'save'})
        def save_checkpoint(instance_id: str, training_state: Dict):
            # Implementation
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not XRAY_AVAILABLE:
                # X-Ray not available, just call function
                return func(*args, **kwargs)
            
            # Create subsegment
            subsegment = xray_recorder.begin_subsegment(name)
            
            try:
                # Add metadata if provided
                if metadata:
                    for key, value in metadata.items():
                        subsegment.put_metadata(key, value)
                
                # Add function arguments as annotations (for filtering)
                subsegment.put_annotation('function', func.__name__)
                
                # Execute function
                result = func(*args, **kwargs)
                
                # Mark as successful
                subsegment.put_annotation('status', 'success')
                
                return result
                
            except Exception as e:
                # Mark as failed and add error info
                subsegment.put_annotation('status', 'error')
                subsegment.put_metadata('error', str(e))
                raise
                
            finally:
                # End subsegment
                xray_recorder.end_subsegment()
        
        return wrapper
    return decorator


def add_trace_metadata(key: str, value: Any) -> None:
    """
    Add metadata to the current X-Ray segment.
    
    Args:
        key: Metadata key
        value: Metadata value
    """
    if not XRAY_AVAILABLE:
        return
    
    try:
        segment = xray_recorder.current_segment()
        if segment:
            segment.put_metadata(key, value)
    except Exception as e:
        print(f"WARNING: Failed to add X-Ray metadata: {e}")


def add_trace_annotation(key: str, value: str) -> None:
    """
    Add annotation to the current X-Ray segment.
    
    Annotations are indexed and can be used for filtering traces.
    
    Args:
        key: Annotation key
        value: Annotation value (must be string, number, or boolean)
    """
    if not XRAY_AVAILABLE:
        return
    
    try:
        segment = xray_recorder.current_segment()
        if segment:
            segment.put_annotation(key, value)
    except Exception as e:
        print(f"WARNING: Failed to add X-Ray annotation: {e}")


def trace_cost_analysis(days: int, record_count: int) -> None:
    """
    Add cost analysis tracing metadata.
    
    Args:
        days: Number of days analyzed
        record_count: Number of records processed
    """
    add_trace_annotation('analysis_days', str(days))
    add_trace_metadata('record_count', record_count)


def trace_checkpoint_operation(checkpoint_id: str, size_bytes: int, duration_ms: float) -> None:
    """
    Add checkpoint operation tracing metadata.
    
    Args:
        checkpoint_id: Checkpoint ID
        size_bytes: Checkpoint size in bytes
        duration_ms: Operation duration in milliseconds
    """
    add_trace_annotation('checkpoint_id', checkpoint_id)
    add_trace_metadata('checkpoint_size_bytes', size_bytes)
    add_trace_metadata('duration_ms', duration_ms)


def trace_migration_workflow(
    instance_id: str,
    instance_type: str,
    migration_mode: str,
    success: bool
) -> None:
    """
    Add migration workflow tracing metadata.
    
    Args:
        instance_id: Instance ID
        instance_type: Instance type
        migration_mode: Migration mode (spot/ondemand)
        success: Whether migration succeeded
    """
    add_trace_annotation('instance_id', instance_id)
    add_trace_annotation('instance_type', instance_type)
    add_trace_annotation('migration_mode', migration_mode)
    add_trace_annotation('migration_success', str(success))


def trace_action_outcome(
    action_type: str,
    action_id: str,
    success: bool,
    cost_impact: float,
    confidence_score: float
) -> None:
    """
    Add action outcome tracing metadata.
    
    Args:
        action_type: Type of action
        action_id: Action ID
        success: Whether action succeeded
        cost_impact: Cost impact in dollars
        confidence_score: Confidence score (0.0-1.0)
    """
    add_trace_annotation('action_type', action_type)
    add_trace_annotation('action_id', action_id)
    add_trace_annotation('action_success', str(success))
    add_trace_metadata('cost_impact', cost_impact)
    add_trace_metadata('confidence_score', confidence_score)


# Context manager for manual subsegment creation
class XRaySubsegment:
    """
    Context manager for creating X-Ray subsegments.
    
    Example:
        with XRaySubsegment('database_query') as subsegment:
            # Perform database query
            results = query_database()
            subsegment.add_metadata('result_count', len(results))
    """
    
    def __init__(self, name: str):
        self.name = name
        self.subsegment = None
    
    def __enter__(self):
        if XRAY_AVAILABLE:
            self.subsegment = xray_recorder.begin_subsegment(self.name)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if XRAY_AVAILABLE and self.subsegment:
            if exc_type:
                # Add error information
                self.subsegment.put_annotation('status', 'error')
                self.subsegment.put_metadata('error_type', exc_type.__name__)
                self.subsegment.put_metadata('error_message', str(exc_val))
            else:
                self.subsegment.put_annotation('status', 'success')
            
            xray_recorder.end_subsegment()
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to this subsegment."""
        if self.subsegment:
            self.subsegment.put_metadata(key, value)
    
    def add_annotation(self, key: str, value: str) -> None:
        """Add annotation to this subsegment."""
        if self.subsegment:
            self.subsegment.put_annotation(key, value)

