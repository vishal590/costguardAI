"""
Property-based tests for QueryProcessor.

Feature: ai-cost-advisor
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta, UTC

from src.services.query_processor import QueryProcessor
from src.utils.types import QueryIntent


# Feature: ai-cost-advisor, Property 1: Query Intent Extraction Consistency
@given(
    service=st.sampled_from(['ec2', 'lambda', 's3', 'dynamodb', 'rds']),
    time_phrase=st.sampled_from(['last week', 'last month', 'yesterday', 'today'])
)
@settings(max_examples=100)
def test_query_intent_extraction_consistency(service, time_phrase):
    """
    Property 1: Query Intent Extraction Consistency
    For any natural language query containing time references and service names,
    parsing the query should consistently extract the same intent, time range,
    and services regardless of phrasing variations.
    
    Validates: Requirements 1.1, 1.3, 1.4
    """
    processor = QueryProcessor()
    
    # Create query with service and time phrase
    query1 = f"what are my {service} costs {time_phrase}"
    query2 = f"show me {service} spending {time_phrase}"
    query3 = f"{service} costs for {time_phrase}"
    
    # Parse all variations
    intent1 = processor.parse_query(query1)
    intent2 = processor.parse_query(query2)
    intent3 = processor.parse_query(query3)
    
    # All should extract the same service
    assert service in intent1.services, f"Service {service} not found in query1"
    assert service in intent2.services, f"Service {service} not found in query2"
    assert service in intent3.services, f"Service {service} not found in query3"
    
    # All should have the same intent type (cost_analysis for these queries)
    assert intent1.intent_type == intent2.intent_type == intent3.intent_type
    
    # Time ranges should be similar (within reasonable bounds)
    # We can't guarantee exact equality due to timing, but they should be close
    delta1 = intent1.time_range[1] - intent1.time_range[0]
    delta2 = intent2.time_range[1] - intent2.time_range[0]
    delta3 = intent3.time_range[1] - intent3.time_range[0]
    
    # All deltas should be similar (within 1 second)
    assert abs((delta1 - delta2).total_seconds()) < 1
    assert abs((delta2 - delta3).total_seconds()) < 1


# Feature: ai-cost-advisor, Property 9: Time Range Interpretation
@given(days=st.integers(min_value=1, max_value=365))
@settings(max_examples=100)
def test_time_range_interpretation_consistency(days):
    """
    Property 9: Time Range Interpretation
    For any relative time reference (e.g., "last N days"), the system should
    consistently map it to the correct absolute date range based on current date.
    
    Validates: Requirements 1.3
    """
    processor = QueryProcessor()
    
    query = f"costs for last {days} days"
    start, end = processor.extract_time_range(query)
    
    # Verify start and end are datetime objects
    assert isinstance(start, datetime)
    assert isinstance(end, datetime)
    
    # Verify start is before end
    assert start < end
    
    # Verify the time range is approximately N days
    delta = end - start
    expected_seconds = days * 86400  # days * seconds per day
    actual_seconds = delta.total_seconds()
    
    # Allow 1% tolerance for timing differences
    tolerance = expected_seconds * 0.01
    assert abs(actual_seconds - expected_seconds) < tolerance, \
        f"Expected ~{expected_seconds}s, got {actual_seconds}s"


# Feature: ai-cost-advisor, Property 10: Service Name Normalization
@given(
    service_alias=st.sampled_from([
        'instance', 'instances', 'compute', 'vm',  # EC2 aliases
        'function', 'functions', 'serverless',  # Lambda aliases
        'storage', 'bucket', 'buckets',  # S3 aliases
        'nosql',  # DynamoDB specific
        'relational', 'mysql', 'postgres'  # RDS specific
    ])
)
@settings(max_examples=100)
def test_service_name_normalization_consistency(service_alias):
    """
    Property 10: Service Name Normalization
    For any common service name or alias, the system should consistently
    map it to the correct AWS service identifier.
    
    Validates: Requirements 1.4
    """
    processor = QueryProcessor()
    
    # Extract services from query with alias
    query = f"what are my {service_alias} costs"
    services = processor.extract_services(query)
    
    # Should extract at least one service
    assert len(services) > 0, f"No services extracted from alias: {service_alias}"
    
    # Normalize the alias directly
    normalized = processor.normalize_service_names([service_alias])
    
    # Should normalize to a valid AWS service
    valid_services = {'ec2', 'lambda', 's3', 'dynamodb', 'rds'}
    assert len(normalized) > 0, f"Normalization failed for: {service_alias}"
    assert all(s in valid_services for s in normalized), \
        f"Normalized to invalid service: {normalized}"
    
    # Extracting from query should match normalization
    # Note: Some aliases like "database" may match multiple services
    assert set(services) == set(normalized), \
        f"Extraction {services} doesn't match normalization {normalized}"


# Additional property: Intent classification is deterministic
@given(query_text=st.text(min_size=5, max_size=100))
@settings(max_examples=100)
def test_intent_classification_deterministic(query_text):
    """
    Property: Intent classification is deterministic
    For any query text, parsing it multiple times should always
    produce the same intent classification.
    
    Validates: Requirements 1.1
    """
    processor = QueryProcessor()
    
    # Parse the same query multiple times
    intent1 = processor.parse_query(query_text)
    intent2 = processor.parse_query(query_text)
    intent3 = processor.parse_query(query_text)
    
    # All should produce the same intent type
    assert intent1.intent_type == intent2.intent_type == intent3.intent_type
    
    # All should extract the same services
    assert intent1.services == intent2.services == intent3.services
    
    # All should extract the same accounts
    assert intent1.accounts == intent2.accounts == intent3.accounts
    
    # All should extract the same entities
    assert intent1.entities == intent2.entities == intent3.entities


# Property: Service extraction is idempotent
@given(
    services=st.lists(
        st.sampled_from(['ec2', 'lambda', 's3', 'dynamodb', 'rds']),
        min_size=1,
        max_size=5,
        unique=True
    )
)
@settings(max_examples=100)
def test_service_extraction_idempotent(services):
    """
    Property: Service extraction is idempotent
    For any list of services, normalizing them multiple times
    should always produce the same result.
    
    Validates: Requirements 1.4
    """
    processor = QueryProcessor()
    
    # Normalize multiple times
    normalized1 = processor.normalize_service_names(services)
    normalized2 = processor.normalize_service_names(normalized1)
    normalized3 = processor.normalize_service_names(normalized2)
    
    # All should be identical
    assert normalized1 == normalized2 == normalized3
    
    # Result should contain only valid services
    valid_services = {'ec2', 'lambda', 's3', 'dynamodb', 'rds'}
    assert all(s in valid_services for s in normalized1)


# Property: Time range extraction always returns valid ranges
@given(query_text=st.text(min_size=1, max_size=200))
@settings(max_examples=100)
def test_time_range_always_valid(query_text):
    """
    Property: Time range extraction always returns valid ranges
    For any query text, the extracted time range should always
    have start before end and both should be valid datetime objects.
    
    Validates: Requirements 1.3
    """
    processor = QueryProcessor()
    
    start, end = processor.extract_time_range(query_text.lower())
    
    # Both should be datetime objects
    assert isinstance(start, datetime)
    assert isinstance(end, datetime)
    
    # Start should be before or equal to end
    assert start <= end
    
    # Both should have timezone info (UTC)
    assert start.tzinfo is not None
    assert end.tzinfo is not None
    
    # Time range should be reasonable (not more than 1 year)
    delta = end - start
    assert delta.days <= 365


# Property: Account ID extraction only finds valid 12-digit IDs
@given(text=st.text(min_size=1, max_size=200))
@settings(max_examples=100)
def test_account_extraction_valid_format(text):
    """
    Property: Account ID extraction only finds valid 12-digit IDs
    For any text, extracted account IDs should always be exactly 12 digits.
    
    Validates: Requirements 1.1
    """
    processor = QueryProcessor()
    
    accounts = processor._extract_accounts(text.lower())
    
    # All extracted accounts should be 12 digits
    for account in accounts:
        assert len(account) == 12, f"Account {account} is not 12 digits"
        assert account.isdigit(), f"Account {account} contains non-digits"


# Property: Entity extraction never raises exceptions
@given(query_text=st.text(min_size=1, max_size=200))
@settings(max_examples=100)
def test_entity_extraction_never_fails(query_text):
    """
    Property: Entity extraction never raises exceptions
    For any query text, entity extraction should always complete
    without raising exceptions, even for malformed input.
    
    Validates: Requirements 1.1
    """
    processor = QueryProcessor()
    
    # Should not raise any exceptions
    try:
        entities = processor._extract_entities(query_text.lower())
        
        # Result should be a dictionary
        assert isinstance(entities, dict)
        
        # If instance_ids present, should be a list
        if 'instance_ids' in entities:
            assert isinstance(entities['instance_ids'], list)
        
        # If function_names present, should be a list
        if 'function_names' in entities:
            assert isinstance(entities['function_names'], list)
            
    except Exception as e:
        pytest.fail(f"Entity extraction raised exception: {e}")
