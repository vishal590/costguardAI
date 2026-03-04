#!/usr/bin/env python3
"""
Demo Data Seeding Script for Autonomous Action Loops

This script generates 7 days of synthetic GPU cost data to demonstrate
the autonomous optimization capabilities in a compressed timeframe.

Features:
- Diurnal spot price patterns (low 2-6 AM, high 9-5 PM)
- Over-provisioned instance (g4dn.2xlarge with 55% utilization)
- Well-utilized instance (g4dn.xlarge with 85% utilization)
- Initial training checkpoint for spot interruption demo
- Realistic cost and utilization patterns

Usage:
    python scripts/seed_demo_data.py [--reset]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List

import boto3
from botocore.exceptions import ClientError

# AWS clients
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

# Table and bucket names
GPU_COSTS_TABLE = os.environ.get('GPU_COSTS_TABLE', 'costguard-gpu-costs')
CHECKPOINTS_BUCKET = os.environ.get('CHECKPOINTS_BUCKET', 
                                     f'costguard-training-checkpoints-{boto3.client("sts").get_caller_identity()["Account"]}-us-east-1')

# Demo instance configurations
DEMO_INSTANCES = {
    'over_provisioned': {
        'instance_id': 'i-demo-overprovisioned-001',
        'instance_type': 'g4dn.2xlarge',
        'region': 'us-east-1',
        'avg_utilization': 0.55,  # 55% - over-provisioned
        'hourly_cost': Decimal('0.752'),  # On-demand price
        'workload_type': 'inference',
    },
    'well_utilized': {
        'instance_id': 'i-demo-wellutilized-002',
        'instance_type': 'g4dn.xlarge',
        'region': 'us-east-1',
        'avg_utilization': 0.85,  # 85% - well-utilized
        'hourly_cost': Decimal('0.526'),  # On-demand price
        'workload_type': 'training',
    },
}


def generate_spot_price_pattern(hour: int) -> float:
    """
    Generate realistic diurnal spot price pattern.
    
    Low prices: 2-6 AM (0.3-0.4x on-demand)
    High prices: 9 AM - 5 PM (0.7-0.9x on-demand)
    Medium prices: Other times (0.5-0.6x on-demand)
    """
    if 2 <= hour < 6:
        # Early morning - lowest prices
        return 0.35 + (hour - 2) * 0.0125  # 0.35 to 0.40
    elif 9 <= hour < 17:
        # Business hours - highest prices
        return 0.70 + (hour - 9) * 0.025  # 0.70 to 0.90
    elif 6 <= hour < 9:
        # Morning ramp-up
        return 0.40 + (hour - 6) * 0.10  # 0.40 to 0.70
    elif 17 <= hour < 20:
        # Evening ramp-down
        return 0.90 - (hour - 17) * 0.10  # 0.90 to 0.60
    else:
        # Night - medium prices
        return 0.50


def generate_utilization_pattern(base_utilization: float, hour: int, day: int) -> float:
    """
    Generate realistic utilization pattern with daily and weekly variations.
    """
    # Daily pattern: lower at night, higher during day
    daily_factor = 1.0
    if 0 <= hour < 6:
        daily_factor = 0.7  # Lower utilization at night
    elif 9 <= hour < 17:
        daily_factor = 1.1  # Higher during business hours
    
    # Weekly pattern: slightly lower on weekends
    weekly_factor = 0.9 if day % 7 in [5, 6] else 1.0
    
    # Add some randomness (±10%)
    import random
    random_factor = 0.9 + random.random() * 0.2
    
    utilization = base_utilization * daily_factor * weekly_factor * random_factor
    return min(1.0, max(0.1, utilization))  # Clamp between 10% and 100%


def seed_gpu_cost_data(days: int = 7, reset: bool = False):
    """
    Seed GPU cost data for demo instances.
    
    Args:
        days: Number of days of historical data to generate
        reset: If True, delete existing demo data first
    """
    table = dynamodb.Table(GPU_COSTS_TABLE)
    
    if reset:
        print(f"Resetting demo data in {GPU_COSTS_TABLE}...")
        # Delete existing demo data
        for instance_config in DEMO_INSTANCES.values():
            instance_id = instance_config['instance_id']
            try:
                # Query and delete all items for this instance
                response = table.query(
                    KeyConditionExpression='instance_id = :id',
                    ExpressionAttributeValues={':id': instance_id}
                )
                with table.batch_writer() as batch:
                    for item in response.get('Items', []):
                        batch.delete_item(Key={
                            'instance_id': item['instance_id'],
                            'timestamp': item['timestamp']
                        })
                print(f"  Deleted existing data for {instance_id}")
            except ClientError as e:
                print(f"  Warning: Could not delete data for {instance_id}: {e}")
    
    print(f"\nSeeding {days} days of GPU cost data...")
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)
    
    total_records = 0
    
    for instance_name, config in DEMO_INSTANCES.items():
        print(f"\n  Seeding data for {instance_name} ({config['instance_id']})...")
        
        current_time = start_time
        records = []
        
        while current_time <= end_time:
            hour = current_time.hour
            day = (current_time - start_time).days
            
            # Generate spot price multiplier
            spot_multiplier = generate_spot_price_pattern(hour)
            spot_price = float(config['hourly_cost']) * spot_multiplier
            
            # Generate utilization
            utilization = generate_utilization_pattern(
                config['avg_utilization'], hour, day
            )
            
            # Calculate costs
            actual_cost = spot_price  # Using spot pricing
            on_demand_cost = float(config['hourly_cost'])
            
            # Create record
            record = {
                'instance_id': config['instance_id'],
                'timestamp': current_time.isoformat() + 'Z',
                'instance_type': config['instance_type'],
                'region': config['region'],
                'gpu_utilization': Decimal(str(round(utilization, 4))),
                'cost_per_hour': Decimal(str(round(actual_cost, 6))),
                'on_demand_cost': Decimal(str(round(on_demand_cost, 6))),
                'spot_price': Decimal(str(round(spot_price, 6))),
                'workload_type': config['workload_type'],
                'is_spot': True,
                'demo_mode': True,
            }
            
            records.append(record)
            
            # Batch write every 25 records
            if len(records) >= 25:
                with table.batch_writer() as batch:
                    for r in records:
                        batch.put_item(Item=r)
                total_records += len(records)
                records = []
            
            # Move to next hour
            current_time += timedelta(hours=1)
        
        # Write remaining records
        if records:
            with table.batch_writer() as batch:
                for r in records:
                    batch.put_item(Item=r)
            total_records += len(records)
        
        print(f"    Seeded {days * 24} hourly records")
    
    print(f"\n✅ Successfully seeded {total_records} total records")


def create_initial_checkpoint():
    """
    Create an initial training checkpoint for spot interruption demo.
    """
    print("\nCreating initial training checkpoint...")
    
    checkpoint_data = {
        'training_job_id': 'demo-training-job-001',
        'instance_id': DEMO_INSTANCES['well_utilized']['instance_id'],
        'epoch': 5,
        'step': 1000,
        'loss': 0.234,
        'accuracy': 0.876,
        'model_state': 'base64_encoded_model_weights_placeholder',
        'optimizer_state': 'base64_encoded_optimizer_state_placeholder',
        'created_at': datetime.utcnow().isoformat() + 'Z',
    }
    
    checkpoint_id = 'demo-checkpoint-initial-001'
    checkpoint_key = f'checkpoints/{checkpoint_id}.json'
    
    try:
        s3.put_object(
            Bucket=CHECKPOINTS_BUCKET,
            Key=checkpoint_key,
            Body=json.dumps(checkpoint_data, indent=2),
            ContentType='application/json',
        )
        print(f"  ✅ Created checkpoint: s3://{CHECKPOINTS_BUCKET}/{checkpoint_key}")
    except ClientError as e:
        print(f"  ⚠️  Warning: Could not create checkpoint: {e}")


def print_summary():
    """Print summary of seeded data."""
    print("\n" + "="*60)
    print("DEMO DATA SUMMARY")
    print("="*60)
    
    for instance_name, config in DEMO_INSTANCES.items():
        print(f"\n{instance_name.upper().replace('_', ' ')}:")
        print(f"  Instance ID: {config['instance_id']}")
        print(f"  Instance Type: {config['instance_type']}")
        print(f"  Avg Utilization: {config['avg_utilization']*100:.0f}%")
        print(f"  Hourly Cost: ${config['hourly_cost']}")
        print(f"  Workload: {config['workload_type']}")
    
    print("\nSPOT PRICE PATTERNS:")
    print("  2-6 AM: Low (35-40% of on-demand)")
    print("  9 AM-5 PM: High (70-90% of on-demand)")
    print("  Other times: Medium (50-60% of on-demand)")
    
    print("\nEXPECTED OPTIMIZATIONS:")
    print("  1. GPU Scheduler: Recommend scheduling during 2-6 AM window")
    print("  2. Spot Manager: Handle interruptions with checkpointing")
    print("  3. Right Sizer: Recommend downsizing over-provisioned instance")
    print("  4. Learning Engine: Build confidence from successful actions")
    
    print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(
        description='Seed demo data for Autonomous Action Loops'
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Delete existing demo data before seeding'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days of historical data to generate (default: 7)'
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("AUTONOMOUS ACTION LOOPS - DEMO DATA SEEDING")
    print("="*60)
    
    try:
        # Seed GPU cost data
        seed_gpu_cost_data(days=args.days, reset=args.reset)
        
        # Create initial checkpoint
        create_initial_checkpoint()
        
        # Print summary
        print_summary()
        
        print("\n✅ Demo data seeding complete!")
        print("\nNext steps:")
        print("  1. Start demo: POST /api/autonomous/demo/start")
        print("  2. Monitor progress: GET /api/autonomous/demo-status")
        print("  3. View results: GET /api/autonomous/action-history")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error seeding demo data: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
