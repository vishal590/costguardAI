"""Idempotent authentication bootstrap. Default prints a plan; --apply makes AWS changes.

Supply a principal JSON file with user_id, role, organizations, accounts,
permissions, rate_limit and optional is_bff_gateway. Key values stay in a private
local key file and DynamoDB; stdout contains no credentials.
"""
import argparse
from datetime import datetime, timedelta, UTC
import hashlib
import json
from pathlib import Path
import secrets

from src.services.access_control import validate_grant

TABLES = {'costguard-api-keys': 'api_key', 'costguard-rate-limits': 'window_key'}


def bootstrap(client, principal, key_file, rotate_from=None):
    for table, key in TABLES.items():
        try:
            response = client.describe_table(TableName=table)
            schema = response['Table']['KeySchema']
            if schema != [{'AttributeName': key, 'KeyType': 'HASH'}]: raise ValueError('Unexpected key schema for ' + table)
        except client.exceptions.ResourceNotFoundException:
            client.create_table(TableName=table, KeySchema=[{'AttributeName': key, 'KeyType': 'HASH'}],
                                AttributeDefinitions=[{'AttributeName': key, 'AttributeType': 'S'}], BillingMode='PAY_PER_REQUEST')
            client.get_waiter('table_exists').wait(TableName=table)
    ttl = client.describe_time_to_live(TableName='costguard-rate-limits')['TimeToLiveDescription']
    if ttl.get('TimeToLiveStatus') == 'DISABLED': client.update_time_to_live(TableName='costguard-rate-limits', TimeToLiveSpecification={'Enabled': True, 'AttributeName': 'ttl'})
    elif ttl.get('AttributeName') != 'ttl': raise ValueError('Unexpected rate-limit TTL attribute')
    grant = validate_grant(principal)
    key_file = Path(key_file)
    if key_file.exists():
        key = key_file.read_text().strip()
    else:
        key = secrets.token_urlsafe(32)
        key_file.parent.mkdir(parents=True, exist_ok=True)
        with key_file.open('x') as output: output.write(key)
        key_file.chmod(0o600)
    if len(key) < 32: raise ValueError('Key must contain at least 32 characters')
    existing = client.get_item(TableName='costguard-api-keys', Key={'api_key': {'S': key}}, ConsistentRead=True).get('Item', {})
    fingerprint = hashlib.sha256(key.encode()).hexdigest()
    item = {'api_key': {'S': key}, 'api_key_id': {'S': 'key_' + fingerprint[:20]}, 'user_id': {'S': principal['user_id']},
        'role': {'S': grant['role']}, 'organizations': {'SS': grant['organizations']}, 'accounts': {'SS': grant['accounts']},
        'permissions': {'SS': principal.get('permissions', ['read'])}, 'rate_limit': {'N': str(principal.get('rate_limit', 100))},
        'is_bff_gateway': {'BOOL': principal.get('is_bff_gateway', False)}, 'is_active': {'BOOL': True},
        'created_at': existing.get('created_at', {'S': datetime.now(UTC).isoformat()}),
        'expires_at': existing.get('expires_at', {'S': (datetime.now(UTC)+timedelta(days=365)).isoformat()})}
    if existing != item: client.put_item(TableName='costguard-api-keys', Item=item)
    if rotate_from:
        prior = Path(rotate_from).read_text().strip()
        if prior == key: raise ValueError('Rotation requires a different new key file')
        client.update_item(TableName='costguard-api-keys', Key={'api_key': {'S': prior}},
            UpdateExpression='SET is_active = :disabled', ExpressionAttributeValues={':disabled': {'BOOL': False}},
            ConditionExpression='attribute_exists(api_key)')
    return {'configured': True, 'key_fingerprint': fingerprint[:12], 'key_file': str(key_file), 'rotated': bool(rotate_from)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--principal', type=Path, required=True)
    parser.add_argument('--key-file', type=Path, required=True)
    parser.add_argument('--rotate-from-key-file', type=Path)
    parser.add_argument('--region', default='us-east-1')
    parser.add_argument('--profile')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    principal = json.loads(args.principal.read_text())
    validate_grant(principal)
    if not isinstance(principal.get('user_id'), str) or not principal['user_id']: raise ValueError('Supply user_id')
    permissions = principal.get('permissions', ['read'])
    if not isinstance(permissions, list) or not permissions or not set(permissions).issubset({'read', 'write'}): raise ValueError('Supply nonempty read/write key permissions')
    if type(principal.get('rate_limit', 100)) is not int or not 1 <= principal.get('rate_limit', 100) <= 10000: raise ValueError('Invalid rate limit')
    if type(principal.get('is_bff_gateway', False)) is not bool: raise ValueError('Invalid gateway flag')
    if args.apply:
        import boto3
        result = bootstrap(boto3.Session(profile_name=args.profile, region_name=args.region).client('dynamodb'), principal, args.key_file, args.rotate_from_key_file)
    else:
        result = {'applied': False, 'tables': TABLES, 'principal': principal['user_id'], 'role': principal['role'],
                  'organizations': principal['organizations'], 'accounts': principal['accounts'], 'region': args.region,
                  'key_file': str(args.key_file), 'rotation_requested': bool(args.rotate_from_key_file), 'aws_calls': 0}
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
