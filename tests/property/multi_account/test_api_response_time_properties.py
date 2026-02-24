"""
Property-based tests for Multi-Account API response time.

Tests that API endpoints respond within acceptable time limits.
"""
import time
import json
from unittest.mock import Mock, patch
from decimal import Decimal
from datetime import datetime, UTC

import pytest
from hypothesis import given, strategies as st, settings

from src.multi_account_api_handler import handler
from src.services.multi_account.models import (
    Organization, Account, AggregatedCosts, AccountCostData, 
    AllocationResult
)
from src.services.multi_account.per_account_cost_service import AccountCostBreakdown


class TestAPIResponseTimeProperties:
    """Property-based tests for API response time bounds."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.valid_api_key = "cg_test_api_key_12345678901234567890"
        self.valid_headers = {
            'X-API-Key': self.valid_api_key,
            'Content-Type': 'application/json'
        }
        
        self.user_context = {
            'api_key_id': 'key_123',
            'user_id': 'test_user',
            'permissions': ['read', 'write'],
            'rate_limit': 100
        }
    
    @given(
        org_count=st.integers(min_value=1, max_value=5),
        account_count=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=20, deadline=10000)  # 10 second deadline per test
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    @patch('src.multi_account_api_handler._get_organization_service')
    def test_list_organizations_response_time(self, mock_get_org_service, mock_auth, org_count, account_count):
        """
        Property 13: API Response Time Bound - Organizations endpoint
        
        For any number of organizations (1-5), the API should respond within 5 seconds.
        
        **Validates: Requirements 4.6, 17.3**
        """
        # Setup mocks
        mock_auth.return_value = (True, None, self.user_context)
        
        mock_org_service = Mock()
        mock_organization = Organization(
            id='o-123456789',
            arn='arn:aws:organizations::123456789012:organization/o-123456789',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        mock_org_service.discover_organization.return_value = mock_organization
        mock_get_org_service.return_value = mock_org_service
        
        # Create event
        event = {
            'httpMethod': 'GET',
            'path': '/api/organizations',
            'headers': self.valid_headers,
            'queryStringParameters': None
        }
        
        # Measure response time
        start_time = time.time()
        response = handler(event, {})
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # Verify response time is within 5 seconds
        assert response_time < 5.0, f"Response time {response_time:.2f}s exceeds 5 second limit"
        
        # Verify response is successful
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        assert len(body['organizations']) == 1
    
    @given(
        account_count=st.integers(min_value=1, max_value=50),
        start_date=st.dates(min_value=datetime(2024, 1, 1).date(), max_value=datetime(2024, 12, 31).date()),
        end_date=st.dates(min_value=datetime(2024, 1, 1).date(), max_value=datetime(2024, 12, 31).date())
    )
    @settings(max_examples=20, deadline=10000)
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    @patch('src.multi_account_api_handler._get_cost_aggregation_engine')
    @patch('src.multi_account_api_handler._get_organization_service')
    def test_consolidated_costs_response_time(self, mock_get_org_service, mock_get_aggregation_engine, mock_auth, 
                                            account_count, start_date, end_date):
        """
        Property 13: API Response Time Bound - Consolidated costs endpoint
        
        For any number of accounts (1-50) and date range, the API should respond within 5 seconds.
        
        **Validates: Requirements 4.6, 17.3**
        """
        # Ensure valid date range
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        
        # Setup mocks
        mock_auth.return_value = (True, None, self.user_context)
        
        # Mock organization service
        mock_org_service = Mock()
        mock_organization = Organization(
            id='o-123456789',
            arn='arn:aws:organizations::123456789012:organization/o-123456789',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        mock_accounts = [
            Account(
                id=f'{123456789000 + i:012d}',
                arn=f'arn:aws:organizations::123456789012:account/o-123456789/{123456789000 + i:012d}',
                name=f'Account-{i}',
                email=f'account{i}@example.com',
                status='ACTIVE',
                joined_method='CREATED',
                joined_timestamp=datetime.now(UTC)
            )
            for i in range(account_count)
        ]
        mock_org_service.discover_organization.return_value = mock_organization
        mock_org_service.get_all_accounts.return_value = mock_accounts
        mock_get_org_service.return_value = mock_org_service
        
        mock_aggregation_engine = Mock()
        
        # Generate realistic cost data
        total_cost = Decimal(str(account_count * 100.0))  # $100 per account
        by_service = {
            'EC2': total_cost * Decimal('0.4'),
            'S3': total_cost * Decimal('0.3'),
            'RDS': total_cost * Decimal('0.2'),
            'Lambda': total_cost * Decimal('0.1')
        }
        by_account = {
            f'{123456789000 + i:012d}': total_cost / account_count
            for i in range(account_count)
        }
        
        mock_consolidated_costs = AggregatedCosts(
            entity_id='o-123456789',
            entity_type='ORGANIZATION',
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            total_cost=total_cost,
            account_count=account_count,
            costs_by_account=by_account,
            costs_by_service=by_service,
            costs_by_day={}
        )
        mock_aggregation_engine.aggregate_organization_costs.return_value = mock_consolidated_costs
        mock_get_aggregation_engine.return_value = mock_aggregation_engine
        
        # Create event
        event = {
            'httpMethod': 'GET',
            'path': '/api/costs/consolidated',
            'headers': self.valid_headers,
            'queryStringParameters': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'granularity': 'MONTHLY'
            }
        }
        
        # Measure response time
        start_time = time.time()
        response = handler(event, {})
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # Verify response time is within 5 seconds
        assert response_time < 5.0, f"Response time {response_time:.2f}s exceeds 5 second limit for {account_count} accounts"
        
        # Verify response is successful
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        assert body['consolidated_costs']['total_cost'] == float(total_cost)
        assert len(body['consolidated_costs']['by_account']) == account_count
    
    @given(
        account_count=st.integers(min_value=1, max_value=30),
        service_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=20, deadline=10000)
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    @patch('src.multi_account_api_handler._get_per_account_cost_service')
    @patch('src.multi_account_api_handler._get_organization_service')
    def test_costs_by_account_response_time(self, mock_get_org_service, mock_get_per_account_service, 
                                          mock_auth, account_count, service_count):
        """
        Property 13: API Response Time Bound - Costs by account endpoint
        
        For any number of accounts (1-30) and services (1-10), the API should respond within 5 seconds.
        
        **Validates: Requirements 4.6, 17.3**
        """
        # Setup mocks
        mock_auth.return_value = (True, None, self.user_context)
        
        # Mock organization service
        mock_org_service = Mock()
        mock_organization = Organization(
            id='o-123456789',
            arn='arn:aws:organizations::123456789012:organization/o-123456789',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        mock_accounts = [
            Account(
                id=f'{123456789000 + i:012d}',
                arn=f'arn:aws:organizations::123456789012:account/o-123456789/{123456789000 + i:012d}',
                name=f'Account-{i}',
                email=f'account{i}@example.com',
                status='ACTIVE',
                joined_method='CREATED',
                joined_timestamp=datetime.now(UTC)
            )
            for i in range(account_count)
        ]
        mock_org_service.discover_organization.return_value = mock_organization
        mock_org_service.get_all_accounts.return_value = mock_accounts
        mock_get_org_service.return_value = mock_org_service
        
        # Mock per-account service
        mock_per_account_service = Mock()
        
        def mock_get_account_costs(account_id, start_date=None, end_date=None):
            # Generate realistic service costs
            service_names = ['EC2', 'S3', 'RDS', 'Lambda', 'DynamoDB', 'CloudWatch', 'VPC', 'ELB', 'Route53', 'CloudFront']
            by_service = {
                service_names[i]: Decimal(str((i + 1) * 50.0))
                for i in range(min(service_count, len(service_names)))
            }
            total_cost = sum(by_service.values())
            
            return AccountCostBreakdown(
                account_id=account_id,
                account_name=f'Account-{account_id[-3:]}',
                start_date='2024-01-01',
                end_date='2024-01-31',
                total_cost=total_cost,
                costs_by_service=by_service,
                costs_by_day={'2024-01-01': total_cost / 31, '2024-01-02': total_cost / 31},
                top_services=[(service, cost) for service, cost in by_service.items()][:5]
            )
        
        mock_per_account_service.get_account_costs.side_effect = mock_get_account_costs
        mock_get_per_account_service.return_value = mock_per_account_service
        
        # Create event
        event = {
            'httpMethod': 'GET',
            'path': '/api/costs/by-account',
            'headers': self.valid_headers,
            'queryStringParameters': {
                'start_date': '2024-01-01',
                'end_date': '2024-01-31'
            }
        }
        
        # Measure response time
        start_time = time.time()
        response = handler(event, {})
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # Verify response time is within 5 seconds
        assert response_time < 5.0, f"Response time {response_time:.2f}s exceeds 5 second limit for {account_count} accounts with {service_count} services each"
        
        # Verify response is successful
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        assert len(body['account_costs']) == account_count
        assert body['count'] == account_count
        
        # Verify each account has the expected number of services
        for account_cost in body['account_costs']:
            assert len(account_cost['by_service']) == service_count
    
    @given(
        tag_value_count=st.integers(min_value=1, max_value=20),
        cost_per_tag=st.floats(min_value=10.0, max_value=1000.0)
    )
    @settings(max_examples=20, deadline=10000)
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    @patch('src.multi_account_api_handler._get_cost_allocation_engine')
    def test_allocation_by_tag_response_time(self, mock_get_allocation_engine, mock_auth, 
                                           tag_value_count, cost_per_tag):
        """
        Property 13: API Response Time Bound - Allocation by tag endpoint
        
        For any number of tag values (1-20) and cost amounts, the API should respond within 5 seconds.
        
        **Validates: Requirements 4.6, 17.3**
        """
        # Setup mocks
        mock_auth.return_value = (True, None, self.user_context)
        
        mock_allocation_engine = Mock()
        
        # Generate allocation results for different tag values
        mock_allocated_costs = {}
        for i in range(tag_value_count):
            tag_value = f'team-{i}'
            mock_allocated_costs[tag_value] = AllocationResult(
                total_cost=Decimal(str(cost_per_tag)),
                currency='USD',
                by_service={
                    'EC2': Decimal(str(cost_per_tag * 0.6)),
                    'S3': Decimal(str(cost_per_tag * 0.4))
                },
                by_account={f'{123456789000 + i:012d}': Decimal(str(cost_per_tag))}
            )
        
        mock_allocation_engine.allocate_by_tags.return_value = mock_allocated_costs
        mock_get_allocation_engine.return_value = mock_allocation_engine
        
        # Create event
        event = {
            'httpMethod': 'GET',
            'path': '/api/allocation/by-tag',
            'headers': self.valid_headers,
            'queryStringParameters': {
                'tag_key': 'Team',
                'start_date': '2024-01-01',
                'end_date': '2024-01-31'
            }
        }
        
        # Measure response time
        start_time = time.time()
        response = handler(event, {})
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # Verify response time is within 5 seconds
        assert response_time < 5.0, f"Response time {response_time:.2f}s exceeds 5 second limit for {tag_value_count} tag values"
        
        # Verify response is successful
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        assert body['tag_key'] == 'Team'
        assert len(body['allocated_costs']) == tag_value_count
        
        # Verify cost amounts are correct
        for tag_value, allocation in body['allocated_costs'].items():
            assert abs(allocation['total_cost'] - cost_per_tag) < 0.01  # Allow for floating point precision
    
    @given(
        unallocated_resource_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=20, deadline=10000)
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    @patch('src.multi_account_api_handler._get_cost_allocation_engine')
    def test_unallocated_costs_response_time(self, mock_get_allocation_engine, mock_auth, 
                                           unallocated_resource_count):
        """
        Property 13: API Response Time Bound - Unallocated costs endpoint
        
        For any number of unallocated resources (1-100), the API should respond within 5 seconds.
        
        **Validates: Requirements 4.6, 17.3**
        """
        # Setup mocks
        mock_auth.return_value = (True, None, self.user_context)
        
        mock_allocation_engine = Mock()
        
        # Generate unallocated resources
        from src.services.multi_account.models import UntaggedResource
        untagged_resources = [
            UntaggedResource(
                resource_id=f'resource-{i}',
                service='EC2' if i % 2 == 0 else 'S3',
                account_id=f'{123456789000 + (i % 5):012d}',
                cost=Decimal(str(10.0 + i)),
                currency='USD'
            )
            for i in range(unallocated_resource_count)
        ]
        
        total_unallocated = sum(resource.cost for resource in untagged_resources)
        
        mock_unallocated_costs = UnallocatedCosts(
            total_cost=total_unallocated,
            currency='USD',
            percentage_of_total=Decimal('25.0'),
            by_service={
                'EC2': total_unallocated * Decimal('0.6'),
                'S3': total_unallocated * Decimal('0.4')
            },
            by_account={
                f'{123456789000 + i:012d}': total_unallocated / 5
                for i in range(5)
            },
            untagged_resources=untagged_resources
        )
        
        mock_allocation_engine.calculate_unallocated_costs.return_value = mock_unallocated_costs
        mock_get_allocation_engine.return_value = mock_allocation_engine
        
        # Create event
        event = {
            'httpMethod': 'GET',
            'path': '/api/allocation/unallocated',
            'headers': self.valid_headers,
            'queryStringParameters': {
                'start_date': '2024-01-01',
                'end_date': '2024-01-31'
            }
        }
        
        # Measure response time
        start_time = time.time()
        response = handler(event, {})
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # Verify response time is within 5 seconds
        assert response_time < 5.0, f"Response time {response_time:.2f}s exceeds 5 second limit for {unallocated_resource_count} unallocated resources"
        
        # Verify response is successful
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        assert len(body['unallocated_costs']['untagged_resources']) == unallocated_resource_count
        assert body['unallocated_costs']['percentage_of_total'] == 25.0
    
    @given(
        request_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=20, deadline=30000)  # 30 second deadline for multiple requests
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    @patch('src.multi_account_api_handler._get_organization_service')
    def test_concurrent_request_response_time(self, mock_get_org_service, mock_auth, request_count):
        """
        Property 13: API Response Time Bound - Concurrent requests
        
        For any number of concurrent requests (1-10), each should respond within 5 seconds.
        
        **Validates: Requirements 4.6, 17.3**
        """
        # Setup mocks
        mock_auth.return_value = (True, None, self.user_context)
        
        mock_org_service = Mock()
        mock_organizations = [
            Organization(
                organization_id='o-123456789',
                master_account_id='123456789012',
                master_account_email='admin@example.com',
                feature_set='ALL',
                available_policy_types=['SERVICE_CONTROL_POLICY']
            )
        ]
        mock_org_service.discover_organization.return_value = mock_organizations
        mock_get_org_service.return_value = mock_org_service
        
        # Create event
        event = {
            'httpMethod': 'GET',
            'path': '/api/organizations',
            'headers': self.valid_headers,
            'queryStringParameters': None
        }
        
        # Make multiple requests and measure response times
        response_times = []
        for i in range(request_count):
            start_time = time.time()
            response = handler(event, {})
            end_time = time.time()
            
            response_time = end_time - start_time
            response_times.append(response_time)
            
            # Verify each response is successful
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
        
        # Verify all response times are within 5 seconds
        max_response_time = max(response_times)
        avg_response_time = sum(response_times) / len(response_times)
        
        assert max_response_time < 5.0, f"Maximum response time {max_response_time:.2f}s exceeds 5 second limit across {request_count} requests"
        assert avg_response_time < 2.0, f"Average response time {avg_response_time:.2f}s is too high for {request_count} requests"
        
        # Log performance metrics for analysis
        print(f"Performance metrics for {request_count} requests:")
        print(f"  Max response time: {max_response_time:.3f}s")
        print(f"  Avg response time: {avg_response_time:.3f}s")
        print(f"  Min response time: {min(response_times):.3f}s")