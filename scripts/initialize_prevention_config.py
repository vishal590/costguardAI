#!/usr/bin/env python3
"""
Initialize Prevention Configuration in DynamoDB

This script creates the default prevention configuration in DynamoDB
that the Lambda function expects.
"""

import boto3
import json
from datetime import datetime

# DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('costguard-prevention-config')

# Default prevention configuration
default_config = {
    'config_key': 'default',
    'prevention_enabled': False,  # Disabled by default for safety
    'dry_run_mode': True,  # Dry run by default
    'approval_required': True,  # Require approval by default
    'warning_threshold_percent': 80,
    'action_threshold_percent': 90,
    'protected_tags': [
        {'key': 'Environment', 'value': 'production'},
        {'key': 'Critical', 'value': 'true'},
        {'key': 'DoNotStop', 'value': 'true'}
    ],
    'whitelisted_resources': [],
    'budget_poll_interval_minutes': 5,
    'resource_refresh_interval_minutes': 15,
    'approval_timeout_minutes': 30,
    'rollback_window_hours': 24,
    'created_at': datetime.utcnow().isoformat(),
    'updated_at': datetime.utcnow().isoformat()
}

print("Initializing prevention configuration...")
print(f"Config: {json.dumps(default_config, indent=2)}")

try:
    # Put the default configuration
    table.put_item(Item=default_config)
    print("\n✅ Successfully initialized prevention configuration!")
    print("\nConfiguration details:")
    print(f"  - Prevention enabled: {default_config['prevention_enabled']}")
    print(f"  - Dry run mode: {default_config['dry_run_mode']}")
    print(f"  - Approval required: {default_config['approval_required']}")
    print(f"  - Warning threshold: {default_config['warning_threshold_percent']}%")
    print(f"  - Action threshold: {default_config['action_threshold_percent']}%")
    print(f"  - Protected tags: {len(default_config['protected_tags'])} tags")
    
except Exception as e:
    print(f"\n❌ Error initializing configuration: {e}")
    exit(1)
