"""
API Authentication and Rate Limiting for Multi-Account Cost Management.

This module provides API key authentication and rate limiting functionality.
"""
import json
import logging
import hashlib
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, UTC
from decimal import Decimal

import boto3
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
                    Key={'api_key': {'S': api_key}}
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
                    'rate_limit': int(item.get('rate_limit', {}).get('N', '100'))
                }
                
                logger.info(f"API key authenticated: {user_context['user_id']}")
                return True, None, user_context
                
            except ClientError as e:
                logger.error(f"Error validating API key: {str(e)}")
                return False, 'Authentication service unavailable', None
        
        except Exception as e:
            logger.error(f"Error in authenticate_request: {str(e)}")
            return False, 'Authentication error', None
    
    def create_api_key(self, user_id: str, permissions: list = None, rate_limit: int = 100, 
                      expires_days: int = 365) -> Dict[str, Any]:
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
            # Generate API key
            api_key = self._generate_api_key(user_id)
            api_key_id = f"key_{int(time.time())}"
            
            # Calculate expiration
            expires_at = datetime.now(UTC) + timedelta(days=expires_days)
            
            # Store in DynamoDB
            self.dynamodb.put_item(
                TableName=self.api_keys_table,
                Item={
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
        """
        Generate a secure API key.
        
        Args:
            user_id: User identifier
            
        Returns:
            Generated API key
        """
        # Create a unique string combining user_id, timestamp, and a random component
        timestamp = str(int(time.time() * 1000000))  # microsecond precision
        unique_string = f"{user_id}:{timestamp}:{hash(user_id + timestamp)}"
        
        # Hash to create API key
        api_key = hashlib.sha256(unique_string.encode()).hexdigest()
        
        return f"cg_{api_key[:32]}"  # CostGuard prefix + 32 chars


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
            current_time = datetime.now(UTC)
            window_start = current_time.replace(second=0, microsecond=0)  # Start of current minute
            window_key = f"{user_id}:{window_start.isoformat()}"
            
            # Get current request count for this minute
            try:
                response = self.dynamodb.get_item(
                    TableName=self.rate_limit_table,
                    Key={'window_key': {'S': window_key}}
                )
                
                current_count = 0
                if 'Item' in response:
                    current_count = int(response['Item'].get('request_count', {}).get('N', '0'))
                
                # Check if limit exceeded
                if current_count >= rate_limit:
                    logger.warning(f"Rate limit exceeded for user {user_id}: {current_count}/{rate_limit}")
                    return False, f'Rate limit exceeded. Maximum {rate_limit} requests per minute.'
                
                # Increment counter
                self.dynamodb.put_item(
                    TableName=self.rate_limit_table,
                    Item={
                        'window_key': {'S': window_key},
                        'user_id': {'S': user_id},
                        'request_count': {'N': str(current_count + 1)},
                        'window_start': {'S': window_start.isoformat()},
                        'ttl': {'N': str(int((window_start + timedelta(minutes=5)).timestamp()))}  # 5 min TTL
                    }
                )
                
                logger.debug(f"Rate limit check passed for user {user_id}: {current_count + 1}/{rate_limit}")
                return True, None
                
            except ClientError as e:
                logger.error(f"Error checking rate limit: {str(e)}")
                # Allow request if rate limiting service is unavailable
                return True, None
        
        except Exception as e:
            logger.error(f"Error in check_rate_limit: {str(e)}")
            # Allow request if rate limiting service is unavailable
            return True, None


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
        if method in ['POST', 'PUT', 'DELETE'] and 'write' not in permissions:
            return False, 'Insufficient permissions for write operations', user_context
        
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
            'WWW-Authenticate': 'API-Key'
        },
        'body': json.dumps({
            'success': False,
            'error': {
                'code': 'AUTHENTICATION_FAILED' if status_code == 401 else 'RATE_LIMIT_EXCEEDED',
                'message': message
            }
        })
    }