"""
Organization Discovery Service

Discovers and maps AWS Organizations structure including accounts and OUs.
"""
import logging
import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError

from .models import Organization, Account, OrganizationalUnit, OUHierarchy

logger = logging.getLogger(__name__)


class OrganizationDiscoveryService:
    """
    Service for discovering AWS Organizations structure
    
    Responsibilities:
    - Discover organization structure from AWS Organizations API
    - Map organization hierarchy (Management → OUs → Member Accounts)
    - Cache organization structure in DynamoDB
    - Refresh organization structure periodically
    """
    
    def __init__(self, dynamodb_client=None, organizations_client=None, cache_ttl_hours=None):
        """
        Initialize the Organization Discovery Service
        
        Args:
            dynamodb_client: Optional DynamoDB client (for testing)
            organizations_client: Optional Organizations client (for testing)
            cache_ttl_hours: Optional cache TTL in hours. If None, reads from ORG_CACHE_TTL_HOURS
                            environment variable (default: 24)
        """
        self.dynamodb = dynamodb_client or boto3.client('dynamodb')
        self.organizations = organizations_client or boto3.client('organizations')
        
        # Read cache TTL from environment variable if not provided
        if cache_ttl_hours is None:
            cache_ttl_hours = int(os.environ.get('ORG_CACHE_TTL_HOURS', '24'))
        
        self.cache_ttl_hours = cache_ttl_hours
        logger.info(f"Initialized OrganizationDiscoveryService with cache_ttl_hours={self.cache_ttl_hours}")
        
    def discover_organization(self) -> Organization:
        """
        Discover organization structure from AWS Organizations API
        
        Returns:
            Organization: The discovered organization
            
        Raises:
            ClientError: If Organizations API call fails
        """
        try:
            logger.info("Discovering organization structure")
            response = self.organizations.describe_organization()
            
            org_data = response['Organization']
            organization = Organization(
                id=org_data['Id'],
                arn=org_data['Arn'],
                master_account_id=org_data['MasterAccountId'],
                feature_set=org_data['FeatureSet']
            )
            
            logger.info(f"Discovered organization: {organization.id}")
            
            # Cache the organization structure
            self._cache_organization(organization)
            
            return organization
            
        except ClientError as e:
            logger.error(f"Failed to discover organization: {e}")
            raise
    
    def get_all_accounts(self, org_id: str) -> List[Account]:
        """
        Get all accounts in the organization
        
        Args:
            org_id: Organization ID
            
        Returns:
            List[Account]: List of all accounts in the organization
            
        Raises:
            ClientError: If Organizations API call fails
        """
        try:
            logger.info(f"Retrieving all accounts for organization: {org_id}")
            accounts = []
            paginator = self.organizations.get_paginator('list_accounts')
            
            for page in paginator.paginate():
                for account_data in page['Accounts']:
                    account = Account(
                        id=account_data['Id'],
                        arn=account_data['Arn'],
                        name=account_data['Name'],
                        email=account_data['Email'],
                        status=account_data.get('State') or account_data.get('Status') or 'UNKNOWN',
                        joined_method=account_data['JoinedMethod'],
                        joined_timestamp=account_data['JoinedTimestamp']
                    )
                    accounts.append(account)
            
            logger.info(f"Found {len(accounts)} accounts in organization")
            
            # Cache account metadata
            self._cache_accounts(org_id, accounts)
            
            return accounts
            
        except ClientError as e:
            logger.error(f"Failed to retrieve accounts: {e}")
            raise
    
    def get_ou_hierarchy(self, org_id: str) -> OUHierarchy:
        """
        Get organizational unit hierarchy
        
        Args:
            org_id: Organization ID
            
        Returns:
            OUHierarchy: The OU hierarchy structure
            
        Raises:
            ClientError: If Organizations API call fails
        """
        try:
            logger.info(f"Retrieving OU hierarchy for organization: {org_id}")
            
            # Get root
            roots_response = self.organizations.list_roots()
            root_id = roots_response['Roots'][0]['Id']
            
            # Recursively get all OUs
            ous = []
            accounts_by_ou = {}
            self._discover_ous_recursive(root_id, None, ous, accounts_by_ou)
            
            hierarchy = OUHierarchy(
                root_id=root_id,
                ous=ous,
                accounts_by_ou=accounts_by_ou
            )
            
            logger.info(f"Discovered {len(ous)} OUs in hierarchy")
            
            return hierarchy
            
        except ClientError as e:
            logger.error(f"Failed to retrieve OU hierarchy: {e}")
            raise
    
    def refresh_organization_cache(self, org_id: str) -> None:
        """
        Refresh cached organization structure
        
        Args:
            org_id: Organization ID
        """
        logger.info(f"Refreshing organization cache for: {org_id}")
        
        # Rediscover organization
        organization = self.discover_organization()
        
        # Refresh accounts
        accounts = self.get_all_accounts(org_id)
        
        # Refresh OU hierarchy
        hierarchy = self.get_ou_hierarchy(org_id)
        
        logger.info(f"Organization cache refreshed: {len(accounts)} accounts, {len(hierarchy.ous)} OUs")
    
    def _discover_ous_recursive(
        self,
        parent_id: str,
        parent_ou_id: Optional[str],
        ous: List[OrganizationalUnit],
        accounts_by_ou: Dict[str, List[str]]
    ) -> None:
        """
        Recursively discover OUs and their accounts
        
        Args:
            parent_id: Parent ID (root or OU)
            parent_ou_id: Parent OU ID (None for root)
            ous: List to accumulate OUs
            accounts_by_ou: Dict to accumulate accounts by OU
        """
        try:
            # List OUs under this parent
            ou_paginator = self.organizations.get_paginator('list_organizational_units_for_parent')
            for page in ou_paginator.paginate(ParentId=parent_id):
                for ou_data in page['OrganizationalUnits']:
                    ou = OrganizationalUnit(
                        id=ou_data['Id'],
                        arn=ou_data['Arn'],
                        name=ou_data['Name'],
                        parent_id=parent_ou_id
                    )
                    ous.append(ou)
                    
                    # Get accounts in this OU
                    account_ids = []
                    account_paginator = self.organizations.get_paginator('list_accounts_for_parent')
                    for acc_page in account_paginator.paginate(ParentId=ou.id):
                        for account_data in acc_page['Accounts']:
                            account_ids.append(account_data['Id'])
                    
                    accounts_by_ou[ou.id] = account_ids
                    
                    # Recursively discover child OUs
                    self._discover_ous_recursive(ou.id, ou.id, ous, accounts_by_ou)
                    
        except ClientError as e:
            logger.error(f"Failed to discover OUs for parent {parent_id}: {e}")
            raise
    
    def _cache_organization(self, organization: Organization) -> None:
        """
        Cache organization structure in DynamoDB
        
        Args:
            organization: Organization to cache
        """
        try:
            ttl = int((datetime.utcnow() + timedelta(hours=self.cache_ttl_hours)).timestamp())
            
            self.dynamodb.put_item(
                TableName=os.environ.get('ORGANIZATIONS_TABLE', 'costguard-organizations'),
                Item={
                    'org_id': {'S': organization.id},
                    'arn': {'S': organization.arn},
                    'master_account_id': {'S': organization.master_account_id},
                    'feature_set': {'S': organization.feature_set},
                    'last_updated': {'N': str(int(datetime.utcnow().timestamp()))},
                    'ttl': {'N': str(ttl)}
                }
            )
            logger.debug(f"Cached organization: {organization.id}")
            
        except ClientError as e:
            logger.warning(f"Failed to cache organization: {e}")
            # Don't raise - caching is optional
    
    def _cache_accounts(self, org_id: str, accounts: List[Account]) -> None:
        """
        Cache account metadata in DynamoDB
        
        Args:
            org_id: Organization ID
            accounts: List of accounts to cache
        """
        try:
            from .repositories import AccountRepository
            repository = AccountRepository(self.dynamodb, os.environ.get('ACCOUNTS_TABLE', 'costguard-accounts'))
            for account in accounts:
                repository.save(account, org_id)
            logger.debug(f"Cached {len(accounts)} accounts")
            
        except ClientError as e:
            logger.warning(f"Failed to cache accounts: {e}")
            # Don't raise - caching is optional
