#!/usr/bin/env python3
"""
Setup API Authentication for Phase 5 Testing

This script creates the API keys table and generates a test API key.
"""
import boto3
import hashlib
import time
from datetime import datetime, timedelta, UTC

# Initialize AWS clients
dynamodb = boto3.client('dynamodb', region_name='us-east-1')

API_KEYS_TABLE = 'costguard-api-keys'
RATE_LIMITS_TABLE = 'costguard-rate-limits'


def create_api_keys_table():
    """Create API keys DynamoDB table."""
    try:
        print(f"Creating table: {API_KEYS_TABLE}")
        
        dynamodb.create_table(
            TableName=API_KEYS_TABLE,
            KeySchema=[
                {'AttributeName': 'api_key', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'api_key', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST',
            Tags=[
                {'Key': 'Project', 'Value': 'CostGuard'},
                {'Key': 'Phase', 'Value': 'Phase5'}
            ]
        )
        
        # Wait for table to be created
        waiter = dynamodb.get_waiter('table_exists')
        waiter.wait(TableName=API_KEYS_TABLE)
        
        print(f"✅ Table {API_KEYS_TABLE} created successfully")
        return True
    
    except dynamodb.exceptions.ResourceInUseException:
        print(f"ℹ️  Table {API_KEYS_TABLE} already exists")
        return True
    
    except Exception as e:
        print(f"❌ Error creating table: {str(e)}")
        return False


def create_rate_limits_table():
    """Create rate limits DynamoDB table."""
    try:
        print(f"Creating table: {RATE_LIMITS_TABLE}")
        
        dynamodb.create_table(
            TableName=RATE_LIMITS_TABLE,
            KeySchema=[
                {'AttributeName': 'window_key', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'window_key', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST',
            Tags=[
                {'Key': 'Project', 'Value': 'CostGuard'},
                {'Key': 'Phase', 'Value': 'Phase5'}
            ]
        )
        
        # Wait for table to be created
        waiter = dynamodb.get_waiter('table_exists')
        waiter.wait(TableName=RATE_LIMITS_TABLE)
        
        # Enable TTL after table is created
        try:
            dynamodb.update_time_to_live(
                TableName=RATE_LIMITS_TABLE,
                TimeToLiveSpecification={
                    'Enabled': True,
                    'AttributeName': 'ttl'
                }
            )
            print(f"✅ TTL enabled on {RATE_LIMITS_TABLE}")
        except Exception as e:
            print(f"⚠️  Could not enable TTL: {str(e)}")
        
        print(f"✅ Table {RATE_LIMITS_TABLE} created successfully")
        return True
    
    except dynamodb.exceptions.ResourceInUseException:
        print(f"ℹ️  Table {RATE_LIMITS_TABLE} already exists")
        return True
    
    except Exception as e:
        print(f"❌ Error creating table: {str(e)}")
        return False


def generate_api_key(user_id: str) -> str:
    """Generate a secure API key."""
    timestamp = str(int(time.time() * 1000000))
    unique_string = f"{user_id}:{timestamp}:{hash(user_id + timestamp)}"
    api_key = hashlib.sha256(unique_string.encode()).hexdigest()
    return f"cg_{api_key[:32]}"


def create_test_api_key():
    """Create a test API key for Phase 5 testing."""
    try:
        user_id = 'test-user'
        api_key = generate_api_key(user_id)
        api_key_id = f"key_{int(time.time())}"
        expires_at = datetime.now(UTC) + timedelta(days=365)
        
        print(f"\nCreating test API key for user: {user_id}")
        
        dynamodb.put_item(
            TableName=API_KEYS_TABLE,
            Item={
                'api_key': {'S': api_key},
                'api_key_id': {'S': api_key_id},
                'user_id': {'S': user_id},
                'permissions': {'SS': ['read', 'write']},
                'rate_limit': {'N': '1000'},
                'is_active': {'BOOL': True},
                'created_at': {'S': datetime.now(UTC).isoformat()},
                'expires_at': {'S': expires_at.isoformat()}
            }
        )
        
        print(f"✅ Test API key created successfully")
        print(f"\n{'='*80}")
        print(f"API KEY DETAILS")
        print(f"{'='*80}")
        print(f"API Key: {api_key}")
        print(f"API Key ID: {api_key_id}")
        print(f"User ID: {user_id}")
        print(f"Permissions: read, write")
        print(f"Rate Limit: 1000 requests/minute")
        print(f"Expires: {expires_at.strftime('%Y-%m-%d')}")
        print(f"{'='*80}")
        print(f"\nUse this API key for testing:")
        print(f"  -H 'x-api-key: {api_key}'")
        print(f"{'='*80}\n")
        
        return api_key
    
    except Exception as e:
        print(f"❌ Error creating test API key: {str(e)}")
        return None


def main():
    """Setup API authentication infrastructure."""
    print("=" * 80)
    print("Phase 5 API Authentication Setup")
    print("=" * 80)
    print()
    
    # Create tables
    if not create_api_keys_table():
        print("❌ Failed to create API keys table")
        return
    
    if not create_rate_limits_table():
        print("❌ Failed to create rate limits table")
        return
    
    # Create test API key
    api_key = create_test_api_key()
    
    if api_key:
        print("✅ API authentication setup complete!")
        print("\nYou can now test Phase 5 endpoints with the generated API key.")
    else:
        print("❌ Failed to create test API key")


if __name__ == '__main__':
    main()
