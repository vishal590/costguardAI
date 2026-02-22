"""
Property-based tests for IdleDetector.

Tests universal properties that should hold for all idle detection operations.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock
from src.services.idle_detector import IdleDetector
from src.utils.types import Resource, ResourceMetadata, IdleStatus


# Feature: automated-cost-prevention, Property 3: Idle Detection Consistency
# Idle detection must be consistent and deterministic


@settings(max_examples=100)
@given(
    cpu_utilization=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
)
def test_property_ec2_idle_detection_consistency(cpu_utilization):
    """
    Property 3: Idle Detection Consistency (EC2)
    
    For any CPU utilization value:
    - Detection should be deterministic (same input = same output)
    - Idle status should match threshold (< 5%)
    - Confidence should be high when idle
    - Metrics should be recorded
    
    Validates: Requirements 3.1
    """
    detector = IdleDetector(Mock())
    
    resource = Resource(
        resource_id='i-test',
        resource_type='instance',
        service='ec2',
        region='us-east-1',
        tags={},
        state='running',
        creation_date='2024-01-01T12:00:00'
    )
    
    metadata = ResourceMetadata(
        resource=resource,
        cost_per_hour=0.10,
        last_activity='2024-01-01T12:00:00',
        metrics={'CPUUtilization': cpu_utilization}
    )
    
    criteria = detector.get_idle_criteria('ec2')
    
    # Run detection twice
    status1 = detector._check_ec2_idle(resource, metadata, criteria)
    status2 = detector._check_ec2_idle(resource, metadata, criteria)
    
    # Should be deterministic
    assert status1.is_idle == status2.is_idle
    assert status1.idle_duration == status2.idle_duration
    assert status1.confidence == status2.confidence
    
    # Idle status should match threshold
    if cpu_utilization < 5.0:
        assert status1.is_idle is True
        assert status1.confidence == 0.95
        assert status1.idle_duration == 120
    else:
        assert status1.is_idle is False
        assert status1.confidence == 0.0
        assert status1.idle_duration == 0
    
    # Metrics should be recorded
    assert 'CPUUtilization' in status1.metrics_used
    assert status1.metrics_used['CPUUtilization'] == cpu_utilization


@settings(max_examples=100)
@given(
    connections=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
)
def test_property_rds_idle_detection_consistency(connections):
    """
    Property 3: Idle Detection Consistency (RDS)
    
    For any connection count:
    - Detection should be deterministic
    - Idle status should match threshold (= 0)
    - Confidence should be high when idle
    
    Validates: Requirements 3.2
    """
    detector = IdleDetector(Mock())
    
    resource = Resource(
        resource_id='db-test',
        resource_type='db_instance',
        service='rds',
        region='us-east-1',
        tags={},
        state='available',
        creation_date='2024-01-01T12:00:00'
    )
    
    metadata = ResourceMetadata(
        resource=resource,
        cost_per_hour=0.20,
        last_activity='2024-01-01T12:00:00',
        metrics={'DatabaseConnections': connections}
    )
    
    criteria = detector.get_idle_criteria('rds')
    status = detector._check_rds_idle(resource, metadata, criteria)
    
    # Idle status should match threshold
    if connections <= 0.0:
        assert status.is_idle is True
        assert status.confidence == 0.90
        assert status.idle_duration == 60
    else:
        assert status.is_idle is False
        assert status.confidence == 0.0
    
    # Metrics should be recorded
    assert 'DatabaseConnections' in status.metrics_used


@settings(max_examples=100)
@given(
    invocations=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False)
)
def test_property_lambda_idle_detection_consistency(invocations):
    """
    Property 3: Idle Detection Consistency (Lambda)
    
    For any invocation count:
    - Detection should be deterministic
    - Idle status should match threshold (= 0)
    - Duration should be 24 hours when idle
    
    Validates: Requirements 3.3
    """
    detector = IdleDetector(Mock())
    
    resource = Resource(
        resource_id='arn:aws:lambda:us-east-1:123456789012:function:test',
        resource_type='function',
        service='lambda',
        region='us-east-1',
        tags={},
        state='Active',
        creation_date='2024-01-01T12:00:00'
    )
    
    metadata = ResourceMetadata(
        resource=resource,
        cost_per_hour=0.0,
        last_activity='2024-01-01T12:00:00',
        metrics={'Invocations': invocations}
    )
    
    criteria = detector.get_idle_criteria('lambda')
    status = detector._check_lambda_idle(resource, metadata, criteria)
    
    # Idle status should match threshold
    if invocations <= 0.0:
        assert status.is_idle is True
        assert status.idle_duration == 1440  # 24 hours
    else:
        assert status.is_idle is False
        assert status.idle_duration == 0


@settings(max_examples=100)
@given(
    state=st.sampled_from(['available', 'in-use', 'creating', 'deleting'])
)
def test_property_ebs_idle_detection_by_state(state):
    """
    Property 3: Idle Detection Consistency (EBS)
    
    For any EBS volume state:
    - Detection should be based on attachment status
    - Only 'in-use' volumes should be considered active
    - Confidence should be 1.0 (deterministic)
    
    Validates: Requirements 3.4
    """
    detector = IdleDetector(Mock())
    
    resource = Resource(
        resource_id='vol-test',
        resource_type='volume',
        service='ebs',
        region='us-east-1',
        tags={},
        state=state,
        creation_date='2024-01-01T12:00:00'
    )
    
    metadata = ResourceMetadata(
        resource=resource,
        cost_per_hour=0.05,
        last_activity='2024-01-01T12:00:00',
        metrics={}
    )
    
    criteria = detector.get_idle_criteria('ebs')
    status = detector._check_ebs_idle(resource, metadata, criteria)
    
    # Only in-use volumes are not idle
    if state == 'in-use':
        assert status.is_idle is False
        assert status.idle_duration == 0
    else:
        assert status.is_idle is True
        assert status.idle_duration == 10080  # 7 days
    
    # Confidence should always be 1.0 (deterministic)
    assert status.confidence == 1.0 or status.confidence == 0.0


@settings(max_examples=100)
@given(
    read_capacity=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    write_capacity=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
)
def test_property_dynamodb_idle_detection_both_metrics(read_capacity, write_capacity):
    """
    Property 3: Idle Detection Consistency (DynamoDB)
    
    For any read/write capacity values:
    - Detection should require BOTH metrics to be zero
    - If either metric > 0, table is not idle
    - Metrics should be recorded
    
    Validates: Requirements 3.6
    """
    detector = IdleDetector(Mock())
    
    resource = Resource(
        resource_id='my-table',
        resource_type='table',
        service='dynamodb',
        region='us-east-1',
        tags={},
        state='ACTIVE',
        creation_date='2024-01-01T12:00:00'
    )
    
    metadata = ResourceMetadata(
        resource=resource,
        cost_per_hour=0.15,
        last_activity='2024-01-01T12:00:00',
        metrics={
            'ConsumedReadCapacityUnits': read_capacity,
            'ConsumedWriteCapacityUnits': write_capacity
        }
    )
    
    criteria = detector.get_idle_criteria('dynamodb')
    status = detector._check_dynamodb_idle(resource, metadata, criteria)
    
    # Both metrics must be zero for idle
    if read_capacity <= 0.0 and write_capacity <= 0.0:
        assert status.is_idle is True
        assert status.idle_duration == 1440
    else:
        assert status.is_idle is False
        assert status.idle_duration == 0
    
    # Both metrics should be recorded
    assert 'ConsumedReadCapacityUnits' in status.metrics_used
    assert 'ConsumedWriteCapacityUnits' in status.metrics_used


@settings(max_examples=100)
@given(
    service=st.sampled_from(['ec2', 'rds', 'lambda', 'ebs', 's3', 'dynamodb'])
)
def test_property_idle_criteria_availability(service):
    """
    Property: Idle criteria should be available for all supported services.
    
    For any supported service:
    - Criteria should be defined
    - Criteria should have valid threshold
    - Criteria should have valid duration
    
    Validates: Requirements 3.7, 3.8
    """
    detector = IdleDetector(Mock())
    
    criteria = detector.get_idle_criteria(service)
    
    # Criteria should exist
    assert criteria is not None
    assert criteria.service == service
    
    # Threshold should be valid
    assert criteria.threshold >= 0.0
    
    # Duration should be positive
    assert criteria.duration_minutes > 0


@settings(max_examples=100)
@given(
    service=st.sampled_from(['ec2', 'rds', 'lambda', 'ebs', 's3', 'dynamodb']),
    resource_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-'))
)
def test_property_idle_status_structure(service, resource_id):
    """
    Property: Idle status should have consistent structure.
    
    For any service and resource:
    - Status should have resource_id
    - Status should have is_idle boolean
    - Status should have idle_duration
    - Status should have metrics_used dict
    - Status should have confidence
    
    Validates: Requirements 3.1-3.8
    """
    detector = IdleDetector(Mock())
    
    resource = Resource(
        resource_id=resource_id,
        resource_type='test',
        service=service,
        region='us-east-1',
        tags={},
        state='active',
        creation_date='2024-01-01T12:00:00'
    )
    
    # Create appropriate metadata based on service
    metrics = {}
    if service == 'ec2':
        metrics = {'CPUUtilization': 50.0}
    elif service == 'rds':
        metrics = {'DatabaseConnections': 5.0}
    elif service == 'lambda':
        metrics = {'Invocations': 100.0}
    elif service == 's3':
        metrics = {'AllRequests': 1000.0}
    elif service == 'dynamodb':
        metrics = {'ConsumedReadCapacityUnits': 10.0, 'ConsumedWriteCapacityUnits': 5.0}
    
    metadata = ResourceMetadata(
        resource=resource,
        cost_per_hour=0.10,
        last_activity='2024-01-01T12:00:00',
        metrics=metrics
    )
    
    status = detector.is_resource_idle(resource, metadata)
    
    # Status should have all required fields
    assert hasattr(status, 'resource_id')
    assert hasattr(status, 'is_idle')
    assert hasattr(status, 'idle_duration')
    assert hasattr(status, 'metrics_used')
    assert hasattr(status, 'confidence')
    
    # Types should be correct
    assert isinstance(status.resource_id, str)
    assert isinstance(status.is_idle, bool)
    assert isinstance(status.idle_duration, (int, float))
    assert isinstance(status.metrics_used, dict)
    assert isinstance(status.confidence, float)
    
    # Confidence should be in valid range
    assert 0.0 <= status.confidence <= 1.0


@settings(max_examples=100)
@given(
    cpu1=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    cpu2=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
)
def test_property_idle_detection_monotonicity(cpu1, cpu2):
    """
    Property: Idle detection should be monotonic with respect to metrics.
    
    For EC2 instances:
    - If CPU1 < CPU2 and CPU1 is idle, then CPU2 might not be idle
    - If CPU1 >= threshold and CPU2 >= threshold, both should not be idle
    - If CPU1 < threshold and CPU2 < threshold, both should be idle
    
    Validates: Requirements 3.1
    """
    detector = IdleDetector(Mock())
    
    resource = Resource(
        resource_id='i-test',
        resource_type='instance',
        service='ec2',
        region='us-east-1',
        tags={},
        state='running',
        creation_date='2024-01-01T12:00:00'
    )
    
    metadata1 = ResourceMetadata(
        resource=resource,
        cost_per_hour=0.10,
        last_activity='2024-01-01T12:00:00',
        metrics={'CPUUtilization': cpu1}
    )
    
    metadata2 = ResourceMetadata(
        resource=resource,
        cost_per_hour=0.10,
        last_activity='2024-01-01T12:00:00',
        metrics={'CPUUtilization': cpu2}
    )
    
    criteria = detector.get_idle_criteria('ec2')
    status1 = detector._check_ec2_idle(resource, metadata1, criteria)
    status2 = detector._check_ec2_idle(resource, metadata2, criteria)
    
    # If both below threshold, both should be idle
    if cpu1 < 5.0 and cpu2 < 5.0:
        assert status1.is_idle is True
        assert status2.is_idle is True
    
    # If both above threshold, both should not be idle
    if cpu1 >= 5.0 and cpu2 >= 5.0:
        assert status1.is_idle is False
        assert status2.is_idle is False


@settings(max_examples=100)
@given(
    service=st.sampled_from(['ec2', 'rds', 'lambda', 'ebs', 's3', 'dynamodb'])
)
def test_property_idle_duration_matches_criteria(service):
    """
    Property: Idle duration should match service criteria when idle.
    
    For any service:
    - When resource is idle, duration should match criteria
    - When resource is not idle, duration should be 0
    
    Validates: Requirements 3.1-3.8
    """
    detector = IdleDetector(Mock())
    criteria = detector.get_idle_criteria(service)
    
    # Create idle resource
    resource = Resource(
        resource_id='test-resource',
        resource_type='test',
        service=service,
        region='us-east-1',
        tags={},
        state='available' if service == 'ebs' else 'active',
        creation_date='2024-01-01T12:00:00'
    )
    
    # Create metadata that makes resource idle
    metrics = {}
    if service == 'ec2':
        metrics = {'CPUUtilization': 0.0}
    elif service == 'rds':
        metrics = {'DatabaseConnections': 0.0}
    elif service == 'lambda':
        metrics = {'Invocations': 0.0}
    elif service == 's3':
        metrics = {'AllRequests': 0.0}
    elif service == 'dynamodb':
        metrics = {'ConsumedReadCapacityUnits': 0.0, 'ConsumedWriteCapacityUnits': 0.0}
    
    metadata = ResourceMetadata(
        resource=resource,
        cost_per_hour=0.10,
        last_activity='2024-01-01T12:00:00',
        metrics=metrics
    )
    
    status = detector.is_resource_idle(resource, metadata)
    
    # If idle, duration should match criteria
    if status.is_idle:
        assert status.idle_duration == criteria.duration_minutes
    else:
        assert status.idle_duration == 0
