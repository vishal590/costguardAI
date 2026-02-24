"""
Unit tests for Per-Account Cost Service
"""
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, MagicMock

from src.services.multi_account.per_account_cost_service import (
    PerAccountCostService,
    AccountCostBreakdown,
    AccountComparison,
    CostAnomaly
)


@pytest.fixture
def mock_cost_repository():
    """Mock cost repository"""
    return Mock()


@pytest.fixture
def mock_account_repository():
    """Mock account repository"""
    return Mock()


@pytest.fixture
def service(mock_cost_repository, mock_account_repository):
    """Create service instance with mocked dependencies"""
    return PerAccountCostService(
        cost_repository=mock_cost_repository,
        account_repository=mock_account_repository
    )


def test_get_account_costs_success(service, mock_cost_repository, mock_account_repository):
    """Test successful account cost retrieval"""
    # Given: Mock cost data
    mock_cost_repository.get_cost_data.return_value = {
        'costs_by_service': {
            'EC2': 100.50,
            'S3': 50.25,
            'RDS': 75.00
        },
        'costs_by_day': {
            '2026-02-01': 75.25,
            '2026-02-02': 75.25,
            '2026-02-03': 75.25
        }
    }
    mock_account_repository.get_account.return_value = {
        'name': 'Production Account'
    }
    
    # When: Getting account costs
    result = service.get_account_costs(
        account_id='123456789012',
        start_date='2026-02-01',
        end_date='2026-02-03'
    )
    
    # Then: Should return correct breakdown
    assert result.account_id == '123456789012'
    assert result.account_name == 'Production Account'
    assert result.total_cost == Decimal('225.75')
    assert len(result.costs_by_service) == 3
    assert result.costs_by_service['EC2'] == Decimal('100.50')
    assert len(result.top_services) == 3
    assert result.top_services[0] == ('EC2', Decimal('100.50'))


def test_get_account_costs_no_data(service, mock_cost_repository, mock_account_repository):
    """Test account cost retrieval with no data"""
    # Given: No cost data
    mock_cost_repository.get_cost_data.return_value = None
    mock_account_repository.get_account.return_value = {
        'name': 'Empty Account'
    }
    
    # When: Getting account costs
    result = service.get_account_costs(
        account_id='999999999999',
        start_date='2026-02-01',
        end_date='2026-02-03'
    )
    
    # Then: Should return empty breakdown
    assert result.account_id == '999999999999'
    assert result.total_cost == Decimal('0')
    assert len(result.costs_by_service) == 0
    assert len(result.top_services) == 0


def test_get_account_costs_top_services_limit(service, mock_cost_repository, mock_account_repository):
    """Test top services limit"""
    # Given: Mock cost data with many services
    mock_cost_repository.get_cost_data.return_value = {
        'costs_by_service': {
            'EC2': 100.00,
            'S3': 90.00,
            'RDS': 80.00,
            'Lambda': 70.00,
            'DynamoDB': 60.00,
            'CloudWatch': 50.00
        },
        'costs_by_day': {}
    }
    mock_account_repository.get_account.return_value = {'name': 'Test'}
    
    # When: Getting account costs with limit of 3
    result = service.get_account_costs(
        account_id='123456789012',
        start_date='2026-02-01',
        end_date='2026-02-03',
        top_services_limit=3
    )
    
    # Then: Should return only top 3 services
    assert len(result.top_services) == 3
    assert result.top_services[0][0] == 'EC2'
    assert result.top_services[1][0] == 'S3'
    assert result.top_services[2][0] == 'RDS'


def test_compare_accounts_success(service, mock_cost_repository, mock_account_repository):
    """Test successful account comparison"""
    # Given: Mock cost data for two accounts
    def get_cost_data_side_effect(account_id, start_date):
        if account_id == '111111111111':
            return {
                'costs_by_service': {'EC2': 200.00, 'S3': 100.00},
                'costs_by_day': {}
            }
        elif account_id == '222222222222':
            return {
                'costs_by_service': {'EC2': 100.00, 'S3': 50.00},
                'costs_by_day': {}
            }
        return None
    
    mock_cost_repository.get_cost_data.side_effect = get_cost_data_side_effect
    
    def get_account_side_effect(account_id):
        if account_id == '111111111111':
            return {'name': 'Account 1'}
        elif account_id == '222222222222':
            return {'name': 'Account 2'}
        return None
    
    mock_account_repository.get_account.side_effect = get_account_side_effect
    
    # When: Comparing accounts
    result = service.compare_accounts(
        account1_id='111111111111',
        account2_id='222222222222',
        start_date='2026-02-01',
        end_date='2026-02-03'
    )
    
    # Then: Should return correct comparison
    assert result.account1_id == '111111111111'
    assert result.account2_id == '222222222222'
    assert result.account1_cost == Decimal('300.00')
    assert result.account2_cost == Decimal('150.00')
    assert result.cost_difference == Decimal('150.00')
    assert result.percentage_difference == 100.0
    assert result.service_differences['EC2'] == Decimal('100.00')
    assert result.service_differences['S3'] == Decimal('50.00')


def test_compare_accounts_zero_cost(service, mock_cost_repository, mock_account_repository):
    """Test account comparison with zero cost"""
    # Given: One account with zero cost
    def get_cost_data_side_effect(account_id, start_date):
        if account_id == '111111111111':
            return {
                'costs_by_service': {'EC2': 100.00},
                'costs_by_day': {}
            }
        elif account_id == '222222222222':
            return None
        return None
    
    mock_cost_repository.get_cost_data.side_effect = get_cost_data_side_effect
    mock_account_repository.get_account.return_value = {'name': 'Test'}
    
    # When: Comparing accounts
    result = service.compare_accounts(
        account1_id='111111111111',
        account2_id='222222222222',
        start_date='2026-02-01',
        end_date='2026-02-03'
    )
    
    # Then: Should handle zero cost correctly
    assert result.account1_cost == Decimal('100.00')
    assert result.account2_cost == Decimal('0')
    assert result.percentage_difference == 100.0


def test_compare_accounts_different_services(service, mock_cost_repository, mock_account_repository):
    """Test account comparison with different services"""
    # Given: Accounts with different services
    def get_cost_data_side_effect(account_id, start_date):
        if account_id == '111111111111':
            return {
                'costs_by_service': {'EC2': 100.00, 'S3': 50.00},
                'costs_by_day': {}
            }
        elif account_id == '222222222222':
            return {
                'costs_by_service': {'RDS': 75.00, 'Lambda': 25.00},
                'costs_by_day': {}
            }
        return None
    
    mock_cost_repository.get_cost_data.side_effect = get_cost_data_side_effect
    mock_account_repository.get_account.return_value = {'name': 'Test'}
    
    # When: Comparing accounts
    result = service.compare_accounts(
        account1_id='111111111111',
        account2_id='222222222222',
        start_date='2026-02-01',
        end_date='2026-02-03'
    )
    
    # Then: Should include all services
    assert len(result.service_differences) == 4
    assert result.service_differences['EC2'] == Decimal('100.00')
    assert result.service_differences['S3'] == Decimal('50.00')
    assert result.service_differences['RDS'] == Decimal('-75.00')
    assert result.service_differences['Lambda'] == Decimal('-25.00')


def test_detect_anomalies_anomalous(service, mock_cost_repository, mock_account_repository):
    """Test anomaly detection with anomalous increase"""
    # Given: Mock cost data showing 100% increase
    call_count = [0]
    
    def get_cost_data_side_effect(account_id, start_date):
        call_count[0] += 1
        if call_count[0] == 1:  # Current period
            return {
                'costs_by_service': {'EC2': 200.00},
                'costs_by_day': {}
            }
        else:  # Previous period
            return {
                'costs_by_service': {'EC2': 100.00},
                'costs_by_day': {}
            }
    
    mock_cost_repository.get_cost_data.side_effect = get_cost_data_side_effect
    mock_account_repository.get_account.return_value = {'name': 'Anomalous Account'}
    
    # When: Detecting anomalies with 50% threshold
    result = service.detect_anomalies(
        account_id='123456789012',
        current_start_date='2026-02-08',
        current_end_date='2026-02-14',
        threshold_percentage=50.0
    )
    
    # Then: Should detect anomaly
    assert result.account_id == '123456789012'
    assert result.is_anomalous is True
    assert result.current_period_cost == Decimal('200.00')
    assert result.previous_period_cost == Decimal('100.00')
    assert result.increase_amount == Decimal('100.00')
    assert result.increase_percentage == 100.0
    assert result.threshold_percentage == 50.0


def test_detect_anomalies_not_anomalous(service, mock_cost_repository, mock_account_repository):
    """Test anomaly detection with normal increase"""
    # Given: Mock cost data showing 25% increase
    call_count = [0]
    
    def get_cost_data_side_effect(account_id, start_date):
        call_count[0] += 1
        if call_count[0] == 1:  # Current period
            return {
                'costs_by_service': {'EC2': 125.00},
                'costs_by_day': {}
            }
        else:  # Previous period
            return {
                'costs_by_service': {'EC2': 100.00},
                'costs_by_day': {}
            }
    
    mock_cost_repository.get_cost_data.side_effect = get_cost_data_side_effect
    mock_account_repository.get_account.return_value = {'name': 'Normal Account'}
    
    # When: Detecting anomalies with 50% threshold
    result = service.detect_anomalies(
        account_id='123456789012',
        current_start_date='2026-02-08',
        current_end_date='2026-02-14',
        threshold_percentage=50.0
    )
    
    # Then: Should not detect anomaly
    assert result.is_anomalous is False
    assert result.increase_percentage == 25.0


def test_detect_anomalies_decrease(service, mock_cost_repository, mock_account_repository):
    """Test anomaly detection with cost decrease"""
    # Given: Mock cost data showing decrease
    call_count = [0]
    
    def get_cost_data_side_effect(account_id, start_date):
        call_count[0] += 1
        if call_count[0] == 1:  # Current period
            return {
                'costs_by_service': {'EC2': 50.00},
                'costs_by_day': {}
            }
        else:  # Previous period
            return {
                'costs_by_service': {'EC2': 100.00},
                'costs_by_day': {}
            }
    
    mock_cost_repository.get_cost_data.side_effect = get_cost_data_side_effect
    mock_account_repository.get_account.return_value = {'name': 'Decreased Account'}
    
    # When: Detecting anomalies
    result = service.detect_anomalies(
        account_id='123456789012',
        current_start_date='2026-02-08',
        current_end_date='2026-02-14',
        threshold_percentage=50.0
    )
    
    # Then: Should not detect anomaly (decrease)
    assert result.is_anomalous is False
    assert result.increase_amount == Decimal('-50.00')
    assert result.increase_percentage == -50.0


def test_detect_anomalies_zero_previous_cost(service, mock_cost_repository, mock_account_repository):
    """Test anomaly detection with zero previous cost"""
    # Given: Mock cost data with zero previous cost
    call_count = [0]
    
    def get_cost_data_side_effect(account_id, start_date):
        call_count[0] += 1
        if call_count[0] == 1:  # Current period
            return {
                'costs_by_service': {'EC2': 100.00},
                'costs_by_day': {}
            }
        else:  # Previous period
            return None
    
    mock_cost_repository.get_cost_data.side_effect = get_cost_data_side_effect
    mock_account_repository.get_account.return_value = {'name': 'New Account'}
    
    # When: Detecting anomalies
    result = service.detect_anomalies(
        account_id='123456789012',
        current_start_date='2026-02-08',
        current_end_date='2026-02-14',
        threshold_percentage=50.0
    )
    
    # Then: Should handle zero previous cost
    assert result.previous_period_cost == Decimal('0')
    assert result.increase_percentage == 100.0
    assert result.is_anomalous is True


def test_get_account_name_success(service, mock_account_repository):
    """Test getting account name successfully"""
    # Given: Mock account data
    mock_account_repository.get_account.return_value = {
        'name': 'Production Account'
    }
    
    # When: Getting account name
    result = service._get_account_name('123456789012')
    
    # Then: Should return account name
    assert result == 'Production Account'


def test_get_account_name_fallback(service, mock_account_repository):
    """Test getting account name with fallback"""
    # Given: No account data
    mock_account_repository.get_account.return_value = None
    
    # When: Getting account name
    result = service._get_account_name('123456789012')
    
    # Then: Should return account ID
    assert result == '123456789012'


def test_get_account_name_error(service, mock_account_repository):
    """Test getting account name with error"""
    # Given: Repository raises exception
    mock_account_repository.get_account.side_effect = Exception("Repository error")
    
    # When: Getting account name
    result = service._get_account_name('123456789012')
    
    # Then: Should return account ID
    assert result == '123456789012'
