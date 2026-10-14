"""
DynamoDB Repository Classes for Multi-Account Cost Management

Provides data access layer for multi-account tables.
"""
import logging
import os
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

def _query_all(client, **request):
    items = []
    while True:
        response = client.query(**request)
        items.extend(response.get('Items', []))
        cursor = response.get('LastEvaluatedKey')
        if not cursor: return {'Items': items}
        request['ExclusiveStartKey'] = cursor



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
        self.table_name = table_name or os.environ.get('ORGANIZATIONS_TABLE', 'costguard-organizations')

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
        self.table_name = table_name or os.environ.get('ACCOUNTS_TABLE', 'costguard-accounts')

    def save(self, account: Account, org_id: str) -> None:
        """
        Save account to DynamoDB
        
        Args:
            account: Account to save
            org_id: Organization ID
        """
        try:
            fields = {'org_id': {'S': org_id}, 'name': {'S': account.name}, 'email': {'S': account.email},
                'status': {'S': account.state}, 'state': {'S': account.state}, 'arn': {'S': account.arn},
                'joined_method': {'S': account.joined_method}}
            if account.joined_timestamp: fields['joined_timestamp'] = {'S': account.joined_timestamp.isoformat()}
            names = {'#field'+str(index): name for index, name in enumerate(fields)}
            values = {':value'+str(index): value for index, value in enumerate(fields.values())}
            assignments = [alias+' = :value'+alias[len('#field'):] for alias in names]
            values.update({':zero': {'N': '0'}, ':pending': {'S': 'PENDING'}})
            assignments.extend(['last_collection = if_not_exists(last_collection, :zero)', 'collection_status = if_not_exists(collection_status, :pending)'])
            self.dynamodb.update_item(TableName=self.table_name, Key={'account_id': {'S': account.id}},
                UpdateExpression='SET '+', '.join(assignments), ExpressionAttributeNames=names, ExpressionAttributeValues=values)
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
                arn=item.get('arn', {}).get('S', ''),
                name=item['name']['S'],
                email=item['email']['S'],
                status=item.get('state', item.get('status', {'S': 'UNKNOWN'}))['S'],
                joined_method=item.get('joined_method', {}).get('S', ''),
                joined_timestamp=datetime.fromisoformat(item['joined_timestamp']['S']) if 'joined_timestamp' in item else None
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
            response = _query_all(self.dynamodb,
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
                    arn=item.get('arn', {}).get('S', ''),
                    name=item['name']['S'],
                    email=item['email']['S'],
                    status=item.get('state', item.get('status', {'S': 'UNKNOWN'}))['S'],
                    joined_method=item.get('joined_method', {}).get('S', ''),
                    joined_timestamp=datetime.fromisoformat(item['joined_timestamp']['S']) if 'joined_timestamp' in item else None
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
        self.table_name = table_name or os.environ.get('MULTI_ACCOUNT_COSTS_TABLE', 'costguard-multi-account-costs')

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
                    'date': {'S': str(cost_data.start_date)},
                    'end_date': {'S': str(cost_data.end_date)},
                    **({'costs_by_tag_service': {'M': {tag: {'M': {service: {'N': str(cost)} for service, cost in services.items()}} for tag, services in cost_data.costs_by_tag_service.items()}}} if getattr(cost_data, 'costs_by_tag_service', None) is not None else {}),
                    'total_cost': {'N': str(cost_data.total_cost)},
                    'is_estimated': {'BOOL': cost_data.is_estimated} if cost_data.is_estimated is not None else {'NULL': True},
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
                status='SUCCESS', is_estimated=item.get('is_estimated', {}).get('BOOL'),
                costs_by_tag_service={tag: {service: Decimal(cost['N']) for service, cost in value['M'].items()} for tag, value in item['costs_by_tag_service']['M'].items()} if 'costs_by_tag_service' in item else None
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

    def get_period(self, account_id, start_date, end_date):
        """Aggregate observed daily records, retaining missing-date coverage."""
        from datetime import date, timedelta
        first, last = date.fromisoformat(start_date), date.fromisoformat(end_date)
        if last < first or (last-first).days > 365: raise ValueError('Select at most 366 ordered days')
        records = self.list_range(account_id, start_date, end_date)
        if not records: raise ValueError('No observed daily cost data for the selected account and period')
        services, days = {}, {}
        for record in records:
            days[record.start_date] = record.total_cost
            for service, amount in record.costs_by_service.items(): services[service] = services.get(service, Decimal('0')) + amount
        expected = {(first+timedelta(days=index)).isoformat() for index in range((last-first).days+1)}
        missing = sorted(expected-set(days))
        return {'total_cost': sum(days.values(), Decimal('0')), 'costs_by_service': services, 'costs_by_day': days,
                'complete': not missing, 'missing_dates': missing}

    def list_range(self, account_id, start_date, end_date):
        """Query complete daily history for one account without N individual reads."""
        from boto3.dynamodb.types import TypeDeserializer
        decoder = TypeDeserializer()
        request = dict(TableName=self.table_name, KeyConditionExpression='account_id = :account AND #day BETWEEN :start AND :end',
            ExpressionAttributeNames={'#day': 'date'}, ExpressionAttributeValues={':account': {'S': account_id}, ':start': {'S': start_date}, ':end': {'S': end_date}})
        records = []
        while True:
            response = self.dynamodb.query(**request)
            for encoded in response.get('Items', []):
                item = {key: decoder.deserialize(value) for key, value in encoded.items()}
                if item.get('end_date', item['date']) != item['date'] or (item.get('costs_by_day') and set(item['costs_by_day']) != {item['date']}):
                    continue  # Legacy period aggregates cannot represent a measured daily record.
                records.append(AccountCostData(account_id=item['account_id'], start_date=item['date'], end_date=item['date'],
                    total_cost=Decimal(item['total_cost']), costs_by_service=item.get('costs_by_service', {}), costs_by_day=item.get('costs_by_day', {}),
                    collection_timestamp=datetime.fromtimestamp(int(item['collection_timestamp'])), status='SUCCESS', costs_by_tag_service=item.get('costs_by_tag_service'), is_estimated=item.get('is_estimated')))
            if not response.get('LastEvaluatedKey'): break
            request['ExclusiveStartKey'] = response['LastEvaluatedKey']
        return records

    def list_by_date(self, date: str) -> List[AccountCostData]:
        """
        List all account costs for a specific date
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            List of account cost data
        """
        try:
            response = _query_all(self.dynamodb,
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
        self.table_name = table_name or os.environ.get('ALLOCATION_RULES_TABLE', 'costguard-allocation-rules')

    def save(self, rule: AllocationRule, org_id: str) -> None:
        """
        Save allocation rule to DynamoDB
        
        Args:
            rule: Allocation rule to save
            org_id: Organization ID
        """
        try:
            # Convert conditions dict to DynamoDB format
            from boto3.dynamodb.types import TypeSerializer
            serializer = TypeSerializer()
            conditions_item = {key: serializer.serialize(Decimal(str(value)) if type(value) is float else value)
                               for key, value in rule.conditions.items()}
            
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
            response = _query_all(self.dynamodb,
                TableName=self.table_name,
                IndexName='org_id-priority-index',
                KeyConditionExpression='org_id = :org_id',
                ExpressionAttributeValues={
                    ':org_id': {'S': org_id}
                },
                ScanIndexForward=True  # Sort by priority ascending
            )
            
            rules = []
            for item in response.get('Items', []):
                from boto3.dynamodb.types import TypeDeserializer
                deserializer = TypeDeserializer()
                conditions = {key: deserializer.deserialize(value) for key, value in item.get('conditions', {}).get('M', {}).items()}
                if item['rule_type']['S'] == 'PERCENTAGE' and isinstance(conditions.get('percentage'), str):
                    conditions['percentage'] = Decimal(conditions['percentage'])
                
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
        self.table_name = table_name or os.environ.get('BUDGETS_TABLE', 'costguard-budgets')

    def save(self, budget_id: str, entity_id: str, entity_type: str, 
             budget_amount: Decimal, period: str, budget_name: str = None, currency: str = "USD") -> None:
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
                    'budget_name': {'S': budget_name or budget_id},
                    'currency': {'S': currency},
                    'current_spend': {'NULL': True},
                    'utilization_percentage': {'NULL': True},
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
                'budget_name': item.get('budget_name', {}).get('S', item['budget_id']['S']),
                'currency': item.get('currency', {}).get('S', 'USD'),
                'current_spend': Decimal(item['current_spend']['N']) if 'N' in item.get('current_spend', {}) else None,
                'utilization_percentage': float(item['utilization_percentage']['N']) if 'N' in item.get('utilization_percentage', {}) else None
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
            response = _query_all(self.dynamodb,
                TableName=self.table_name,
                IndexName='entity_id-type-index',
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
                    'budget_name': item.get('budget_name', {}).get('S', item['budget_id']['S']),
                    'currency': item.get('currency', {}).get('S', 'USD'),
                    'current_spend': Decimal(item['current_spend']['N']) if 'N' in item.get('current_spend', {}) else None,
                    'utilization_percentage': float(item['utilization_percentage']['N']) if 'N' in item.get('utilization_percentage', {}) else None
                }
                budgets.append(budget)
            
            return budgets
        except ClientError as e:
            logger.error(f"Failed to list budgets: {e}")
            raise
