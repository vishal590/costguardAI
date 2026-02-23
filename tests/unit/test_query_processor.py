"""
Unit tests for QueryProcessor.
"""
import pytest
from datetime import datetime, timedelta, UTC
from src.services.query_processor import QueryProcessor
from src.utils.types import QueryIntent


class TestQueryProcessorInitialization:
    """Tests for QueryProcessor initialization."""
    
    def test_query_processor_initialization(self):
        """Test QueryProcessor initializes correctly."""
        processor = QueryProcessor()
        assert processor is not None
        assert hasattr(processor, 'INTENT_KEYWORDS')
        assert hasattr(processor, 'SERVICE_MAPPINGS')


class TestTimeRangeExtraction:
    """Tests for time range extraction."""
    
    def test_extract_last_7_days(self):
        """Test extracting 'last 7 days'."""
        processor = QueryProcessor()
        start, end = processor.extract_time_range("what were my costs last 7 days")
        
        assert isinstance(start, datetime)
        assert isinstance(end, datetime)
        assert start < end
        # Should be approximately 7 days apart
        delta = end - start
        assert 6.9 <= delta.days <= 7.1
    
    def test_extract_last_30_days(self):
        """Test extracting 'last 30 days'."""
        processor = QueryProcessor()
        start, end = processor.extract_time_range("show me costs for last 30 days")
        
        delta = end - start
        assert 29.9 <= delta.days <= 30.1
    
    def test_extract_last_week(self):
        """Test extracting 'last week'."""
        processor = QueryProcessor()
        start, end = processor.extract_time_range("last week costs")
        
        delta = end - start
        assert 6.9 <= delta.days <= 7.1
    
    def test_extract_last_month(self):
        """Test extracting 'last month'."""
        processor = QueryProcessor()
        start, end = processor.extract_time_range("last month spending")
        
        delta = end - start
        assert 29.9 <= delta.days <= 30.1
    
    def test_extract_this_week(self):
        """Test extracting 'this week'."""
        processor = QueryProcessor()
        start, end = processor.extract_time_range("this week costs")
        
        # Start should be at beginning of current week
        assert start.weekday() == 0  # Monday
        assert end >= start  # Can be equal if called at exact start of week
    
    def test_extract_this_month(self):
        """Test extracting 'this month'."""
        processor = QueryProcessor()
        start, end = processor.extract_time_range("this month spending")
        
        # Start should be first day of current month
        assert start.day == 1
        assert start.hour == 0
        assert end > start
    
    def test_extract_yesterday(self):
        """Test extracting 'yesterday'."""
        processor = QueryProcessor()
        start, end = processor.extract_time_range("yesterday costs")
        
        # Should be approximately 1 day (23h 59m 59s)
        delta = end - start
        assert delta.total_seconds() >= 86399  # At least 23:59:59
    
    def test_extract_today(self):
        """Test extracting 'today'."""
        processor = QueryProcessor()
        start, end = processor.extract_time_range("today costs")
        
        # Start should be beginning of today
        assert start.hour == 0
        assert start.minute == 0
        assert end > start
    
    def test_default_time_range(self):
        """Test default time range when no time specified."""
        processor = QueryProcessor()
        start, end = processor.extract_time_range("what are my costs")
        
        # Default should be last 7 days
        delta = end - start
        assert 6.9 <= delta.days <= 7.1


class TestServiceExtraction:
    """Tests for service name extraction."""
    
    def test_extract_ec2(self):
        """Test extracting EC2 service."""
        processor = QueryProcessor()
        services = processor.extract_services("what are my ec2 costs")
        
        assert 'ec2' in services
    
    def test_extract_ec2_instance(self):
        """Test extracting EC2 via 'instance' keyword."""
        processor = QueryProcessor()
        services = processor.extract_services("how much do my instances cost")
        
        assert 'ec2' in services
    
    def test_extract_lambda(self):
        """Test extracting Lambda service."""
        processor = QueryProcessor()
        services = processor.extract_services("lambda function costs")
        
        assert 'lambda' in services
    
    def test_extract_s3(self):
        """Test extracting S3 service."""
        processor = QueryProcessor()
        services = processor.extract_services("s3 storage costs")
        
        assert 's3' in services
    
    def test_extract_s3_bucket(self):
        """Test extracting S3 via 'bucket' keyword."""
        processor = QueryProcessor()
        services = processor.extract_services("how much do my buckets cost")
        
        assert 's3' in services
    
    def test_extract_dynamodb(self):
        """Test extracting DynamoDB service."""
        processor = QueryProcessor()
        services = processor.extract_services("dynamodb costs")
        
        assert 'dynamodb' in services
    
    def test_extract_rds(self):
        """Test extracting RDS service."""
        processor = QueryProcessor()
        services = processor.extract_services("rds database costs")
        
        assert 'rds' in services
    
    def test_extract_multiple_services(self):
        """Test extracting multiple services."""
        processor = QueryProcessor()
        services = processor.extract_services("ec2 and s3 costs")
        
        assert 'ec2' in services
        assert 's3' in services
        assert len(services) == 2
    
    def test_extract_no_services(self):
        """Test when no services mentioned."""
        processor = QueryProcessor()
        services = processor.extract_services("what are my total costs")
        
        assert services == []


class TestServiceNormalization:
    """Tests for service name normalization."""
    
    def test_normalize_ec2(self):
        """Test normalizing 'ec2'."""
        processor = QueryProcessor()
        normalized = processor.normalize_service_names(['ec2'])
        
        assert normalized == ['ec2']
    
    def test_normalize_instance_to_ec2(self):
        """Test normalizing 'instance' to 'ec2'."""
        processor = QueryProcessor()
        normalized = processor.normalize_service_names(['instance'])
        
        assert 'ec2' in normalized
    
    def test_normalize_storage_to_s3(self):
        """Test normalizing 'storage' to 's3'."""
        processor = QueryProcessor()
        normalized = processor.normalize_service_names(['storage'])
        
        assert 's3' in normalized
    
    def test_normalize_function_to_lambda(self):
        """Test normalizing 'function' to 'lambda'."""
        processor = QueryProcessor()
        normalized = processor.normalize_service_names(['function'])
        
        assert 'lambda' in normalized
    
    def test_normalize_multiple_services(self):
        """Test normalizing multiple services."""
        processor = QueryProcessor()
        normalized = processor.normalize_service_names(['ec2', 'storage', 'function'])
        
        assert 'ec2' in normalized
        assert 's3' in normalized
        assert 'lambda' in normalized
    
    def test_normalize_duplicate_services(self):
        """Test normalizing removes duplicates."""
        processor = QueryProcessor()
        normalized = processor.normalize_service_names(['ec2', 'instance'])
        
        # Both should map to ec2, but only one should be in result
        assert normalized.count('ec2') == 1


class TestIntentClassification:
    """Tests for intent classification."""
    
    def test_classify_cost_analysis(self):
        """Test classifying cost analysis intent."""
        processor = QueryProcessor()
        intent = processor._classify_intent("what are my costs")
        
        assert intent == 'cost_analysis'
    
    def test_classify_optimization(self):
        """Test classifying optimization intent."""
        processor = QueryProcessor()
        intent = processor._classify_intent("how can i save money and optimize")
        
        assert intent == 'optimization'
    
    def test_classify_trend_analysis(self):
        """Test classifying trend analysis intent."""
        processor = QueryProcessor()
        intent = processor._classify_intent("show me trends and patterns")
        
        assert intent == 'trend_analysis'
    
    def test_classify_forecast(self):
        """Test classifying forecast intent."""
        processor = QueryProcessor()
        intent = processor._classify_intent("predict my future costs")
        
        assert intent == 'forecast'
    
    def test_classify_prevention(self):
        """Test classifying prevention intent."""
        processor = QueryProcessor()
        intent = processor._classify_intent("stop idle resources")
        
        assert intent == 'prevention'
    
    def test_classify_default_intent(self):
        """Test default intent when no keywords match."""
        processor = QueryProcessor()
        intent = processor._classify_intent("hello")
        
        assert intent == 'cost_analysis'  # Default


class TestEntityExtraction:
    """Tests for entity extraction."""
    
    def test_extract_instance_id(self):
        """Test extracting EC2 instance ID."""
        processor = QueryProcessor()
        entities = processor._extract_entities("costs for i-1234567890abcdef0")
        
        assert 'instance_ids' in entities
        assert 'i-1234567890abcdef0' in entities['instance_ids']
    
    def test_extract_multiple_instance_ids(self):
        """Test extracting multiple instance IDs."""
        processor = QueryProcessor()
        entities = processor._extract_entities("costs for i-1234567890abcdef0 and i-abcdef1234567890a")
        
        assert 'instance_ids' in entities
        assert len(entities['instance_ids']) == 2
    
    def test_extract_function_name(self):
        """Test extracting Lambda function name."""
        processor = QueryProcessor()
        entities = processor._extract_entities("costs for function my-function")
        
        assert 'function_names' in entities
        assert 'my-function' in entities['function_names']
    
    def test_extract_no_entities(self):
        """Test when no entities present."""
        processor = QueryProcessor()
        entities = processor._extract_entities("what are my costs")
        
        assert entities == {}


class TestAccountExtraction:
    """Tests for AWS account ID extraction."""
    
    def test_extract_account_id(self):
        """Test extracting 12-digit account ID."""
        processor = QueryProcessor()
        accounts = processor._extract_accounts("costs for account 123456789012")
        
        assert '123456789012' in accounts
    
    def test_extract_multiple_accounts(self):
        """Test extracting multiple account IDs."""
        processor = QueryProcessor()
        accounts = processor._extract_accounts("costs for 123456789012 and 987654321098")
        
        assert len(accounts) == 2
        assert '123456789012' in accounts
        assert '987654321098' in accounts
    
    def test_extract_no_accounts(self):
        """Test when no account IDs present."""
        processor = QueryProcessor()
        accounts = processor._extract_accounts("what are my costs")
        
        assert accounts == []


class TestParseQuery:
    """Tests for complete query parsing."""
    
    def test_parse_simple_cost_query(self):
        """Test parsing simple cost query."""
        processor = QueryProcessor()
        intent = processor.parse_query("What were my EC2 costs last month?")
        
        assert intent.intent_type == 'cost_analysis'
        assert 'ec2' in intent.services
        assert intent.time_range is not None
    
    def test_parse_optimization_query(self):
        """Test parsing optimization query."""
        processor = QueryProcessor()
        intent = processor.parse_query("How can I save money on Lambda?")
        
        assert intent.intent_type == 'optimization'
        assert 'lambda' in intent.services
    
    def test_parse_forecast_query(self):
        """Test parsing forecast query."""
        processor = QueryProcessor()
        intent = processor.parse_query("Forecast and predict my future S3 spending")
        
        assert intent.intent_type == 'forecast'
        assert 's3' in intent.services
    
    def test_parse_query_with_instance_id(self):
        """Test parsing query with instance ID."""
        processor = QueryProcessor()
        intent = processor.parse_query("What are the costs for i-1234567890abcdef0?")
        
        assert 'instance_ids' in intent.entities
        assert 'i-1234567890abcdef0' in intent.entities['instance_ids']
    
    def test_parse_query_with_account(self):
        """Test parsing query with account ID."""
        processor = QueryProcessor()
        intent = processor.parse_query("Show costs for account 123456789012")
        
        assert '123456789012' in intent.accounts
    
    def test_parse_complex_query(self):
        """Test parsing complex query with multiple elements."""
        processor = QueryProcessor()
        intent = processor.parse_query(
            "What were my EC2 and S3 costs last 30 days for account 123456789012?"
        )
        
        assert intent.intent_type == 'cost_analysis'
        assert 'ec2' in intent.services
        assert 's3' in intent.services
        assert '123456789012' in intent.accounts
        assert intent.time_range is not None
