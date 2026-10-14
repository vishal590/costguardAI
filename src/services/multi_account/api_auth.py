"""
API Authentication and Rate Limiting for Multi-Account Cost Management.

This module provides API key authentication and rate limiting functionality.
"""
import json
import logging
import hashlib
import secrets
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, UTC
from decimal import Decimal

import boto3
from urllib.parse import urlencode
from ..access_control import AccessDenied, validate_grant, authorize_request, verify_delegation
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class APIAuthenticator:
    """
    Handles API key authentication for multi-account endpoints.
    
    Requirements: 16.10, 17.6
    """
    
    def __init__(self, dynamodb_client, api_keys_table: str = 'costguard-api-keys'):
        """
        Initialize API authenticator.
        
        Args:
            dynamodb_client: DynamoDB client
            api_keys_table: Name of API keys table
        """
        self.dynamodb = dynamodb_client
        self.api_keys_table = api_keys_table
    
    def authenticate_request(self, event: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Authenticate API request using API key.
        
        Args:
            event: Lambda event from API Gateway
            
        Returns:
            Tuple of (is_authenticated, error_message, user_context)
            
        Requirements: 16.10
        """
        try:
            # Extract API key from headers (case-insensitive; API Gateway may normalize casing)
            headers = event.get('headers', {}) or {}
            headers_lower = {k.lower(): v for k, v in headers.items()}
            api_key = headers_lower.get('x-api-key')
            if isinstance(api_key, list):
                api_key = api_key[0] if api_key else None

            if not api_key:
                return False, 'API key is required', None
            
            # Validate API key format
            if len(api_key) < 32:
                return False, 'Invalid API key format', None
            
            # Look up API key in DynamoDB
            try:
                response = self.dynamodb.get_item(
                    TableName=self.api_keys_table,
                    Key={'api_key': {'S': api_key}}, ConsistentRead=True
                )
                
                if 'Item' not in response:
                    logger.warning(f"Invalid API key attempted: {api_key[:8]}...")
                    return False, 'Invalid API key', None
                
                item = response['Item']
                
                # Check if API key is active
                if not item.get('is_active', {}).get('BOOL', False):
                    return False, 'API key is disabled', None
                
                # Check expiration
                expires_at = item.get('expires_at', {}).get('S')
                if expires_at:
                    expiry_date = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    if datetime.now(UTC) > expiry_date:
                        return False, 'API key has expired', None
                
                # Extract user context
                user_context = {
                    'api_key_id': item.get('api_key_id', {}).get('S'),
                    'user_id': item.get('user_id', {}).get('S'),
                    'permissions': item.get('permissions', {}).get('SS', []),
                    'rate_limit': int(item.get('rate_limit', {}).get('N', '100')),
                    'role': item.get('role', {}).get('S', 'operator' if 'write' in item.get('permissions', {}).get('SS', []) else 'viewer'),
                    'organizations': item.get('organizations', {}).get('SS', []),
                    'accounts': item.get('accounts', {}).get('SS', []),
                    'is_bff_gateway': item.get('is_bff_gateway', {}).get('BOOL', False)
                }
                
                if user_context['is_bff_gateway']:
                    multiple = event.get('multiValueQueryStringParameters') or {}
                    single = event.get('queryStringParameters') or {}
                    pairs = [(key, '' if value is None else value) for key, values in multiple.items() for value in values]
                    pairs.extend((key, '' if value is None else value) for key, value in single.items() if key not in multiple)
                    query = event.get('rawQueryString') if isinstance(event.get('rawQueryString'), str) else urlencode(pairs)
                    delegation = verify_delegation(api_key, headers_lower, event.get('httpMethod', 'GET'), event.get('path', ''), query, event.get('body'))
                    grant = delegation['grant']
                    for kind in ('organizations', 'accounts'):
                        key_scope = user_context[kind]
                        if '*' not in key_scope and any(value not in key_scope for value in grant[kind]):
                            raise AccessDenied('Delegated scope exceeds backend key scope')
                    if {'viewer': 0, 'operator': 1, 'admin': 2}[grant['role']] > {'viewer': 0, 'operator': 1, 'admin': 2}.get(user_context['role'], -1):
                        raise AccessDenied('Delegated role exceeds backend key role')
                    user_context.update(grant)
                    user_context['user_id'] = delegation['subject']
                validate_grant(user_context)
                params = {'query': event.get('queryStringParameters') or {}, 'body': json.loads(event.get('body') or '{}')}
                authorize_request(user_context, event.get('httpMethod', 'GET'), event.get('path', ''), params)
                logger.info(f"API key authenticated: {user_context['user_id']}")
                return True, None, user_context
                
            except AccessDenied as e:
                return False, 'Access denied: ' + str(e), None
            except ClientError as e:
                logger.error(f"Error validating API key: {str(e)}")
                return False, 'Authentication service unavailable', None
        
        except Exception as e:
            logger.error(f"Error in authenticate_request: {str(e)}")
            return False, 'Authentication error', None
    
    def create_api_key(self, user_id: str, permissions: list = None, rate_limit: int = 100, 
                      expires_days: int = 365, *, role: str = "viewer", organizations=None, accounts=None, is_bff_gateway: bool = False) -> Dict[str, Any]:
        """
        Create a new API key for a user.
        
        Args:
            user_id: User identifier
            permissions: List of permissions
            rate_limit: Requests per minute limit
            expires_days: Days until expiration
            
        Returns:
            Dict containing API key details
        """
        try:
            grant = validate_grant({"role": role, "organizations": organizations or [], "accounts": accounts or []})
            # Generate API key
            api_key = self._generate_api_key(user_id)
            api_key_id = f"key_{int(time.time())}"
            
            # Calculate expiration
            expires_at = datetime.now(UTC) + timedelta(days=expires_days)
            
            # Store in DynamoDB
            self.dynamodb.put_item(
                TableName=self.api_keys_table,
                Item={
                    'role': {'S': grant['role']},
                    'organizations': {'SS': grant['organizations']},
                    'accounts': {'SS': grant['accounts']},
                    'is_bff_gateway': {'BOOL': is_bff_gateway},
                    'api_key': {'S': api_key},
                    'api_key_id': {'S': api_key_id},
                    'user_id': {'S': user_id},
                    'permissions': {'SS': permissions or ['read']},
                    'rate_limit': {'N': str(rate_limit)},
                    'is_active': {'BOOL': True},
                    'created_at': {'S': datetime.now(UTC).isoformat()},
                    'expires_at': {'S': expires_at.isoformat()}
                }
            )
            
            logger.info(f"Created API key for user {user_id}: {api_key_id}")
            
            return {
                'api_key': api_key,
                'api_key_id': api_key_id,
                'user_id': user_id,
                'permissions': permissions or ['read'],
                'rate_limit': rate_limit,
                'expires_at': expires_at.isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error creating API key: {str(e)}")
            raise
    
    def _generate_api_key(self, user_id: str) -> str:
        """Use OS-backed randomness rather than user/time-derived key material."""
        return 'cg_' + secrets.token_urlsafe(32)


class RateLimiter:
    """
    Implements rate limiting for API requests.
    
    Requirements: 17.6
    """
    
    def __init__(self, dynamodb_client, rate_limit_table: str = 'costguard-rate-limits'):
        """
        Initialize rate limiter.
        
        Args:
            dynamodb_client: DynamoDB client
            rate_limit_table: Name of rate limits table
        """
        self.dynamodb = dynamodb_client
        self.rate_limit_table = rate_limit_table
    
    def check_rate_limit(self, user_id: str, rate_limit: int = 100) -> Tuple[bool, Optional[str]]:
        """
        Check if user has exceeded rate limit.
        
        Args:
            user_id: User identifier
            rate_limit: Requests per minute limit
            
        Returns:
            Tuple of (is_allowed, error_message)
            
        Requirements: 17.6
        """
        try:
            window_start = datetime.now(UTC).replace(second=0, microsecond=0)
            window_key = f"{user_id}:{window_start.isoformat()}"
            self.dynamodb.update_item(TableName=self.rate_limit_table,
                Key={'window_key': {'S': window_key}},
                UpdateExpression='SET user_id = :user, window_start = :start, #ttl = :ttl ADD request_count :one',
                ConditionExpression='attribute_not_exists(request_count) OR request_count < :limit',
                ExpressionAttributeNames={'#ttl': 'ttl'},
                ExpressionAttributeValues={':user': {'S': user_id}, ':start': {'S': window_start.isoformat()},
                    ':ttl': {'N': str(int((window_start+timedelta(minutes=5)).timestamp()))}, ':one': {'N': '1'}, ':limit': {'N': str(rate_limit)}})
            return True, None
        except ClientError as exc:
            if exc.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return False, f'Rate limit exceeded. Maximum {rate_limit} requests per minute.'
            return False, 'Rate limiting service unavailable'
        except Exception:
            return False, 'Rate limiting service unavailable'


def authenticate_and_authorize(event: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Authenticate and authorize API request.
    
    Args:
        event: Lambda event from API Gateway
        
    Returns:
        Tuple of (is_authorized, error_message, user_context)
        
    Requirements: 16.10, 17.6
    """
    try:
        # Initialize services
        from ..dynamodb import get_dynamodb_client
        dynamodb_client = get_dynamodb_client()
        
        authenticator = APIAuthenticator(dynamodb_client)
        rate_limiter = RateLimiter(dynamodb_client)
        
        # Authenticate request
        is_authenticated, auth_error, user_context = authenticator.authenticate_request(event)
        
        if not is_authenticated:
            return False, auth_error, None
        
        # Check rate limit
        rate_limit = user_context.get('rate_limit', 100)
        is_allowed, rate_error = rate_limiter.check_rate_limit(
            user_context['user_id'], 
            rate_limit
        )
        
        if not is_allowed:
            return False, rate_error, user_context
        
        # Check permissions (basic implementation)
        path = event.get('path', '')
        method = event.get('httpMethod', 'GET')
        permissions = user_context.get('permissions', [])
        
        # Simple permission check
        if method in ['POST', 'PUT', 'PATCH', 'DELETE'] and not (method == 'POST' and path == '/api/organization-advisor/query') and 'write' not in permissions:
            return False, 'Insufficient permissions for write operations', user_context
        
        if (method in ['GET', 'HEAD'] or (method == 'POST' and path == '/api/organization-advisor/query')) and 'read' not in permissions:
            return False, 'Insufficient permissions for read operations', user_context
        return True, None, user_context
    
    except Exception as e:
        logger.error(f"Error in authenticate_and_authorize: {str(e)}")
        return False, 'Authentication service error', None


def create_auth_error_response(status_code: int, message: str) -> Dict[str, Any]:
    """
    Create authentication error response.
    
    Args:
        status_code: HTTP status code
        message: Error message
        
    Returns:
        Response dict with status code and error body
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            **({'WWW-Authenticate': 'API-Key'} if status_code == 401 else {})
        },
        'body': json.dumps({
            'success': False,
            'error': {
                'code': {401: 'AUTHENTICATION_FAILED', 403: 'ACCESS_DENIED', 429: 'RATE_LIMIT_EXCEEDED', 503: 'ACCESS_SERVICE_UNAVAILABLE'}.get(status_code, 'ACCESS_ERROR'),
                'message': message
            }
        })
    }