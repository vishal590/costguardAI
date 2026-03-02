"""
DynamoDB Repository Classes for Multi-Account Cost Management

Provides data access layer for multi-account tables.
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime
from decimal import Decimal
import boto3
from botocore.exceptions import ClientError

from .models import (
    Organization,
    Account,
    AccountCostData,
    AllocationRule,
    AggregatedCosts,
)

logger = logging.getLogger(__name__)


class OrganizationRepository:
    """Repository for organizations table"""

    def __init__(self, dynamodb_client=None, table_name=None):
        """
        Initialize the Organization Repository
        
        Args:
            dynamodb_client: Optional DynamoDB client (for testing)
            table_name: Optional table name (defaults to 'organizations')
        """
        self.dynamodb = dynamodb_client or boto3.client('dynamodb')
        self.table_name = table_name or 'organizations'

    def save(self, organization: Organization, ttl: int) -> None:
        """
        Save organization to DynamoDB
        
        Args:
            organization: Organization to save
            ttl: TTL timestamp for cache expiration
        """
        try:
            self.dynamodb.put_item(
                TableName=self.table_name,
                Item={
                    'org_id': {'S': organization.id},
                    'arn': {'S': organization.arn},
                    'master_account_id': {'S': organization.master_account_id},
                    'feature_set': {'S': organization.feature_set},
                    'last_updated': {'N': str(int(datetime.utcnow().timestamp()))},
                    'ttl': {'N': str(ttl)}
                }
            )
            logger.debug(f"Saved organization: {organization.id}")
        except ClientError as e:
            logger.error(f"Failed to save organization: {e}")
            raise

    def get(self, org_id: str) -> Optional[Organization]:
        """
        Get organization by ID
        
        Args:
            org_id: Organization ID
            
        Returns:
            Organization if found, None otherwise
        """
        try:
            response = self.dynamodb.get_item(
                TableName=self.table_name,
                Key={'org_id': {'S': org_id}}
            )
            
            if 'Item' not in response:
                return None
            
            item = response['Item']
            return Organization(
                id=item['org_id']['S'],
                arn=item['arn']['S'],
                master_account_id=item['master_account_id']['S'],
                feature_set=item['feature_set']['S']
            )
        except ClientError as e:
            logger.error(f"Failed to get organization: {e}")
            raise


class AccountRepository:
    """Repository for accounts table"""

    def __init__(self, dynamodb_client=None, table_name=None):
        """
        Initialize the Account Repository
        
        Args:
            dynamodb_client: Optional DynamoDB client (for testing)
            table_name: Optional table name (defaults to 'accounts')
        """
        self.dynamodb = dynamodb_client or boto3.client('dynamodb')
        self.table_name = table_name or 'accounts'

    def save(self, account: Account, org_id: str) -> None:
        """
        Save account to DynamoDB
        
        Args:
            account: Account to save
            org_id: Organization ID
        """
        try:
            self.dynamodb.put_item(
                TableName=self.table_name,
                Item={
                    'account_id': {'S': account.id},
                    'org_id': {'S': org_id},
                    'name': {'S': account.name},
                    'email': {'S': account.email},
                    'status': {'S': account.status},
                    'last_collection': {'N': '0'},
                    'collection_status': {'S': 'PENDING'}
                }
            )
            logger.debug(f"Saved account: {account.id}")
        except ClientError as e:
            logger.error(f"Failed to save account: {e}")
            raise

    def get(self, account_id: str) -> Optional[Account]:
        """
        Get account by ID
        
        Args:
            account_id: Account ID
            
        Returns:
            Account if found, None otherwise
        """
        try:
            response = self.dynamodb.get_item(
                TableName=self.table_name,
                Key={'account_id': {'S': account_id}}
            )
            
            if 'Item' not in response:
                return None
            
            item = response['Item']
            return Account(
                id=item['account_id']['S'],
                arn='',  # Not stored in table
                name=item['name']['S'],
                email=item['email']['S'],
                status=item['status']['S'],
                joined_method='',  # Not stored in table
                joined_timestamp=datetime.utcnow()  # Not stored in table
            )
        except ClientError as e:
            logger.error(f"Failed to get account: {e}")
            raise

    def list_by_organization(self, org_id: str) -> List[Account]:
        """
        List all accounts in an organization
        
        Args:
            org_id: Organization ID
            
        Returns:
            List of accounts
        """
        try:
            response = self.dynamodb.query(
                TableName=self.table_name,
                IndexName='org_id-index',
                KeyConditionExpression='org_id = :org_id',
                ExpressionAttributeValues={
                    ':org_id': {'S': org_id}
                }
            )
            
            accounts = []
            for item in response.get('Items', []):
                account = Account(
                    id=item['account_id']['S'],
                    arn='',
                    name=item['name']['S'],
                    email=item['email']['S'],
                    status=item['status']['S'],
                    joined_method='',
                    joined_timestamp=datetime.utcnow()
                )
                accounts.append(account)
            
            return accounts
        except ClientError as e:
            logger.error(f"Failed to list accounts: {e}")
            raise


class MultiAccountCostRepository:
    """Repository for multi_account_costs table"""

    def __init__(self, dynamodb_client=None, table_name=None):
        """
        Initialize the Multi-Account Cost Repository
        
        Args:
            dynamodb_client: Optional DynamoDB client (for testing)
            table_name: Optional table name (defaults to 'multi_account_costs')
        """
        self.dynamodb = dynamodb_client or boto3.client('dynamodb')
        self.table_name = table_name or 'multi_account_costs'

    def save(self, cost_data: AccountCostData) -> None:
        """
        Save account cost data to DynamoDB
        
        Args:
            cost_data: Account cost data to save
        """
        try:
            # Convert costs_by_service to DynamoDB format
            costs_by_service_item = {
                service: {'N': str(cost)}
                for service, cost in cost_data.costs_by_service.items()
            }
            
            # Convert costs_by_day to DynamoDB format
            costs_by_day_item = {
                day: {'N': str(cost)}
                for day, cost in cost_data.costs_by_day.items()
            }
            
            self.dynamodb.put_item(
                TableName=self.table_name,
                Item={
                    'account_id': {'S': cost_data.account_id},
                    'date': {'S': cost_data.start_date},
                    'total_cost': {'N': str(cost_data.total_cost)},
                    'costs_by_service': {'M': costs_by_service_item},
                    'costs_by_day': {'M': costs_by_day_item},
                    'collection_timestamp': {'N': str(int(cost_data.collection_timestamp.timestamp()))}
                }
            )
            logger.debug(f"Saved cost data for account: {cost_data.account_id}")
        except ClientError as e:
            logger.error(f"Failed to save cost data: {e}")
            raise

    def get(self, account_id: str, date: str) -> Optional[AccountCostData]:
        """
        Get cost data for an account on a specific date
        
        Args:
            account_id: Account ID
            date: Date in YYYY-MM-DD format
            
        Returns:
            AccountCostData if found, None otherwise
        """
        try:
            response = self.dynamodb.get_item(
                TableName=self.table_name,
                Key={
                    'account_id': {'S': account_id},
                    'date': {'S': date}
                }
            )
            
            if 'Item' not in response:
                return None
            
            item = response['Item']
            
            # Convert costs_by_service from DynamoDB format
            costs_by_service = {
                service: Decimal(cost['N'])
                for service, cost in item.get('costs_by_service', {}).get('M', {}).items()
            }
            
            # Convert costs_by_day from DynamoDB format
            costs_by_day = {
                day: Decimal(cost['N'])
                for day, cost in item.get('costs_by_day', {}).get('M', {}).items()
            }
            
            return AccountCostData(
                account_id=item['account_id']['S'],
                start_date=item['date']['S'],
                end_date=item['date']['S'],
                total_cost=Decimal(item['total_cost']['N']),
                costs_by_service=costs_by_service,
                costs_by_day=costs_by_day,
                collection_timestamp=datetime.fromtimestamp(int(item['collection_timestamp']['N'])),
                status='SUCCESS'
            )
        except ClientError as e:
            logger.error(f"Failed to get cost data: {e}")
            raise
    
    def get_cost_data(self, account_id: str, date: str) -> Optional[AccountCostData]:
        """
        Alias for get() method for backward compatibility.
        
        Args:
            account_id: Account ID
            date: Date in YYYY-MM-DD format
            
        Returns:
            AccountCostData if found, None otherwise
        """
        return self.get(account_id, date)

    def list_by_date(self, date: str) -> List[AccountCostData]:
        """
        List all account costs for a specific date
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            List of account cost data
        """
        try:
            response = self.dynamodb.query(
                TableName=self.table_name,
                IndexName='date-index',
                KeyConditionExpression='#date = :date',
                ExpressionAttributeNames={
                    '#date': 'date'
                },
                ExpressionAttributeValues={
                    ':date': {'S': date}
                }
            )
            
            cost_data_list = []
            for item in response.get('Items', []):
                costs_by_service = {
                    service: Decimal(cost['N'])
                    for service, cost in item.get('costs_by_service', {}).get('M', {}).items()
                }
                
                costs_by_day = {
                    day: Decimal(cost['N'])
                    for day, cost in item.get('costs_by_day', {}).get('M', {}).items()
                }
                
                cost_data = AccountCostData(
                    account_id=item['account_id']['S'],
                    start_date=item['date']['S'],
                    end_date=item['date']['S'],
                    total_cost=Decimal(item['total_cost']['N']),
                    costs_by_service=costs_by_service,
                    costs_by_day=costs_by_day,
                    collection_timestamp=datetime.fromtimestamp(int(item['collection_timestamp']['N'])),
                    status='SUCCESS'
                )
                cost_data_list.append(cost_data)
            
            return cost_data_list
        except ClientError as e:
            logger.error(f"Failed to list cost data by date: {e}")
            raise


class AllocationRuleRepository:
    """Repository for allocation_rules table"""

    def __init__(self, dynamodb_client=None, table_name=None):
        """
        Initialize the Allocation Rule Repository
        
        Args:
            dynamodb_client: Optional DynamoDB client (for testing)
            table_name: Optional table name (defaults to 'allocation_rules')
        """
        self.dynamodb = dynamodb_client or boto3.client('dynamodb')
        self.table_name = table_name or 'allocation_rules'

    def save(self, rule: AllocationRule, org_id: str) -> None:
        """
        Save allocation rule to DynamoDB
        
        Args:
            rule: Allocation rule to save
            org_id: Organization ID
        """
        try:
            # Convert conditions dict to DynamoDB format
            conditions_item = {
                key: {'S': str(value)}
                for key, value in rule.conditions.items()
            }
            
            self.dynamodb.put_item(
                TableName=self.table_name,
                Item={
                    'rule_id': {'S': rule.rule_id},
                    'org_id': {'S': org_id},
                    'name': {'S': rule.name},
                    'priority': {'N': str(rule.priority)},
                    'rule_type': {'S': rule.rule_type},
                    'conditions': {'M': conditions_item},
                    'allocation_target': {'S': rule.allocation_target},
                    'created_at': {'N': str(int(datetime.utcnow().timestamp()))},
                    'updated_at': {'N': str(int(datetime.utcnow().timestamp()))}
                }
            )
            logger.debug(f"Saved allocation rule: {rule.rule_id}")
        except ClientError as e:
            logger.error(f"Failed to save allocation rule: {e}")
            raise

    def list_by_organization(self, org_id: str) -> List[AllocationRule]:
        """
        List all allocation rules for an organization (sorted by priority)
        
        Args:
            org_id: Organization ID
            
        Returns:
            List of allocation rules sorted by priority
        """
        try:
            response = self.dynamodb.query(
                TableName=self.table_name,
                IndexName='org_id-index',
                KeyConditionExpression='org_id = :org_id',
                ExpressionAttributeValues={
                    ':org_id': {'S': org_id}
                },
                ScanIndexForward=True  # Sort by priority ascending
            )
            
            rules = []
            for item in response.get('Items', []):
                conditions = {
                    key: value['S']
                    for key, value in item.get('conditions', {}).get('M', {}).items()
                }
                
                rule = AllocationRule(
                    rule_id=item['rule_id']['S'],
                    name=item['name']['S'],
                    priority=int(item['priority']['N']),
                    rule_type=item['rule_type']['S'],
                    conditions=conditions,
                    allocation_target=item['allocation_target']['S']
                )
                rules.append(rule)
            
            return rules
        except ClientError as e:
            logger.error(f"Failed to list allocation rules: {e}")
            raise


class BudgetRepository:
    """Repository for budgets table"""

    def __init__(self, dynamodb_client=None, table_name=None):
        """
        Initialize the Budget Repository
        
        Args:
            dynamodb_client: Optional DynamoDB client (for testing)
            table_name: Optional table name (defaults to 'budgets')
        """
        self.dynamodb = dynamodb_client or boto3.client('dynamodb')
        self.table_name = table_name or 'budgets'

    def save(self, budget_id: str, entity_id: str, entity_type: str, 
             budget_amount: Decimal, period: str) -> None:
        """
        Save budget to DynamoDB
        
        Args:
            budget_id: Budget ID
            entity_id: Entity ID (org/OU/account)
            entity_type: Entity type (ORGANIZATION/OU/ACCOUNT)
            budget_amount: Budget amount
            period: Budget period (MONTHLY/QUARTERLY/ANNUAL)
        """
        try:
            self.dynamodb.put_item(
                TableName=self.table_name,
                Item={
                    'budget_id': {'S': budget_id},
                    'entity_id': {'S': entity_id},
                    'entity_type': {'S': entity_type},
                    'budget_amount': {'N': str(budget_amount)},
                    'period': {'S': period},
                    'current_spend': {'N': '0'},
                    'utilization_percentage': {'N': '0'},
                    'last_updated': {'N': str(int(datetime.utcnow().timestamp()))}
                }
            )
            logger.debug(f"Saved budget: {budget_id}")
        except ClientError as e:
            logger.error(f"Failed to save budget: {e}")
            raise

    def get(self, budget_id: str) -> Optional[Dict]:
        """
        Get budget by ID
        
        Args:
            budget_id: Budget ID
            
        Returns:
            Budget dict if found, None otherwise
        """
        try:
            response = self.dynamodb.get_item(
                TableName=self.table_name,
                Key={'budget_id': {'S': budget_id}}
            )
            
            if 'Item' not in response:
                return None
            
            item = response['Item']
            return {
                'budget_id': item['budget_id']['S'],
                'entity_id': item['entity_id']['S'],
                'entity_type': item['entity_type']['S'],
                'budget_amount': Decimal(item['budget_amount']['N']),
                'period': item['period']['S'],
                'current_spend': Decimal(item['current_spend']['N']),
                'utilization_percentage': float(item['utilization_percentage']['N'])
            }
        except ClientError as e:
            logger.error(f"Failed to get budget: {e}")
            raise

    def list_by_entity(self, entity_id: str, entity_type: str) -> List[Dict]:
        """
        List all budgets for an entity
        
        Args:
            entity_id: Entity ID
            entity_type: Entity type
            
        Returns:
            List of budgets
        """
        try:
            response = self.dynamodb.query(
                TableName=self.table_name,
                IndexName='entity_id-index',
                KeyConditionExpression='entity_id = :entity_id AND entity_type = :entity_type',
                ExpressionAttributeValues={
                    ':entity_id': {'S': entity_id},
                    ':entity_type': {'S': entity_type}
                }
            )
            
            budgets = []
            for item in response.get('Items', []):
                budget = {
                    'budget_id': item['budget_id']['S'],
                    'entity_id': item['entity_id']['S'],
                    'entity_type': item['entity_type']['S'],
                    'budget_amount': Decimal(item['budget_amount']['N']),
                    'period': item['period']['S'],
                    'current_spend': Decimal(item['current_spend']['N']),
                    'utilization_percentage': float(item['utilization_percentage']['N'])
                }
                budgets.append(budget)
            
            return budgets
        except ClientError as e:
            logger.error(f"Failed to list budgets: {e}")
            raise
