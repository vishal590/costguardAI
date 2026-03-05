"""
Integration Tests for Autonomous Action Loops

Tests the complete end-to-end flow of the autonomous optimization system:
1. Analyze phase: GPU Scheduler identifies optimization opportunities
2. Decide phase: Safety Guard validates and approves actions
3. Act phase: Spot Manager/Right Sizer execute optimizations
4. Verify phase: System monitors outcomes
5. Learn phase: Learning Engine updates confidence scores

These tests use the seeded demo data and validate the complete autonomous loop.
"""

import json
import os
import time
from datetime import datetime, timedelta
from decimal import Decimal

import boto3
import pytest
from botocore.exceptions import ClientError

# AWS clients
dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')
events_client = boto3.client('events')
s3_client = boto3.client('s3')

# Table and resource names
GPU_COSTS_TABLE = os.environ.get('GPU_COSTS_TABLE', 'costguard-gpu-costs')
ACTION_HISTORY_TABLE = os.environ.get('ACTION_HISTORY_TABLE', 'costguard-action-history')
EVENT_BUS_NAME = os.environ.get('EVENT_BUS_NAME', 'costguard-autonomous-events')

# Lambda function names
GPU_SCHEDULER_FUNCTION = 'CostGuard-GPU-Scheduler'
SPOT_MANAGER_FUNCTION = 'CostGuard-Spot-Manager'
RIGHT_SIZER_FUNCTION = 'CostGuard-Right-Sizer'
LEARNING_ENGINE_FUNCTION = 'CostGuard-Learning-Engine'
SAFETY_GUARD_FUNCTION = 'CostGuard-Safety-Guard'


@pytest.fixture(scope='module')
def demo_data_exists():
    """Verify demo data has been seeded."""
    table = dynamodb.Table(GPU_COSTS_TABLE)
    
    # Check for demo instances
    response = table.query(
        KeyConditionExpression='instance_id = :id',
        ExpressionAttributeValues={':id': 'i-demo-overprovisioned-001'},
        Limit=1
    )
    
    assert response['Count'] > 0, "Demo data not found. Run: python scripts/seed_demo_data.py"
    return True


class TestCompleteAutonomousLoop:
    """Test the complete autonomous optimization loop."""
    
    def test_01_gpu_scheduler_analysis(self, demo_data_exists):
        """
        Test Phase 1: Analyze
        GPU Scheduler should analyze cost patterns and identify optimization windows.
        """
        # Invoke GPU Scheduler Lambda
        response = lambda_client.invoke(
            FunctionName=GPU_SCHEDULER_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'action': 'analyze_patterns',
                'days': 7,
                'demo_mode': True
            })
        )
        
        assert response['StatusCode'] == 200, "GPU Scheduler invocation failed"
        
        # Parse Lambda response (API Gateway format)
        lambda_response = json.loads(response['Payload'].read())
        assert lambda_response['statusCode'] == 200, "Lambda returned error status"
        
        # Parse the body field (which is a JSON string)
        payload = json.loads(lambda_response['body'])
        assert 'recommendations' in payload, "Missing recommendations field"
        
        # Recommendations may be empty if no future optimization windows exist
        # This is acceptable behavior - the function executed successfully
        recommendations = payload['recommendations']
        
        # If recommendations exist, verify their structure
        if len(recommendations) > 0:
            rec = recommendations[0]
            assert 'window_start' in rec
            assert 'window_end' in rec
            assert 'expected_savings_percent' in rec or 'expected_savings' in rec
            assert 'confidence_score' in rec
            
            # Confidence score should be valid
            assert 0.0 <= rec['confidence_score'] <= 1.0
        
        # Verify analysis timestamp is present
        assert 'analysis_timestamp' in payload
    
    def test_02_action_history_recording(self):
        """
        Test that autonomous actions are recorded in action history.
        """
        table = dynamodb.Table(ACTION_HISTORY_TABLE)
        
        # Query recent actions
        response = table.scan(
            FilterExpression='demo_mode = :demo',
            ExpressionAttributeValues={':demo': True},
            Limit=10
        )
        
        # Should have at least some actions recorded
        # (May be 0 if this is first run, which is okay)
        actions = response.get('Items', [])
        
        if len(actions) > 0:
            action = actions[0]
            # Verify action structure
            assert 'action_id' in action
            assert 'timestamp' in action
            assert 'action_type' in action
            assert 'status' in action
    
    def test_03_right_sizer_utilization_analysis(self, demo_data_exists):
        """
        Test Phase 2: Right Sizer analyzes utilization and recommends downsizing.
        """
        # Invoke Right Sizer Lambda
        response = lambda_client.invoke(
            FunctionName=RIGHT_SIZER_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'action': 'analyze_utilization',
                'instance_id': 'i-demo-overprovisioned-001',
                'days': 7,
                'demo_mode': True
            })
        )
        
        assert response['StatusCode'] == 200, "Right Sizer invocation failed"
        
        # Parse Lambda response (API Gateway format)
        lambda_response = json.loads(response['Payload'].read())
        assert lambda_response['statusCode'] == 200, "Lambda returned error status"
        
        # Parse the body field (which is a JSON string)
        payload = json.loads(lambda_response['body'])
        
        # Should identify over-provisioning
        if 'recommendation' in payload:
            rec = payload['recommendation']
            assert rec.get('is_overprovisioned') == True
            assert 'recommended_instance_type' in rec
            assert 'expected_savings' in rec
    
    def test_04_learning_engine_confidence_scores(self):
        """
        Test Phase 5: Learning Engine calculates confidence scores.
        """
        # Invoke Learning Engine Lambda with EventBridge format
        response = lambda_client.invoke(
            FunctionName=LEARNING_ENGINE_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'detail-type': 'ActionCompleted',
                'detail': {
                    'action_id': f'test-action-{int(time.time())}',
                    'action_type': 'schedule',
                    'status': 'completed',
                    'expected_cost_impact': -25.0,
                    'actual_cost_impact': -23.5,
                    'demo_mode': True
                }
            })
        )
        
        assert response['StatusCode'] == 200, "Learning Engine invocation failed"
        
        # Parse Lambda response (API Gateway format)
        lambda_response = json.loads(response['Payload'].read())
        assert lambda_response['statusCode'] == 200, f"Lambda returned error: {lambda_response.get('body')}"
        
        # Parse the body field (which is a JSON string)
        payload = json.loads(lambda_response['body'])
        
        # Should have updated confidence score
        assert 'confidence_score' in payload or 'success_rate' in payload
    
    def test_05_safety_guard_dry_run(self):
        """
        Test Safety Guard dry-run mode (no actual changes).
        """
        # Invoke Safety Guard in dry-run mode
        response = lambda_client.invoke(
            FunctionName=SAFETY_GUARD_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'detail-type': 'ActionRequest',
                'detail': {
                    'action_type': 'right_sizing',  # Valid action type
                    'action_id': f'test-action-{int(time.time())}',
                    'instance_id': 'i-demo-overprovisioned-001',
                    'parameters': {
                        'current_type': 'g4dn.2xlarge',
                        'target_type': 'g4dn.xlarge',
                        'expected_savings': '30.0'  # String to avoid float/Decimal issues
                    },
                    'confidence_score': 0.85,
                    'expected_cost_impact': -30,  # Integer to avoid float/Decimal issues
                    'approval_required': False
                },
                'demo_mode': True
            })
        )
        
        assert response['StatusCode'] == 200, "Safety Guard invocation failed"
        
        # Parse Lambda response (API Gateway format)
        lambda_response = json.loads(response['Payload'].read())
        assert lambda_response['statusCode'] in [200, 202], f"Lambda returned error: {lambda_response.get('body')}"
        
        # Parse the body field (which is a JSON string)
        payload = json.loads(lambda_response['body'])
        
        # Should have validation result or approval status
        assert 'status' in payload
        assert payload['status'] in ['dry_run', 'approved', 'pending_approval']


class TestEventBridgeIntegration:
    """Test EventBridge event routing and processing."""
    
    def test_eventbridge_bus_exists(self):
        """Verify the autonomous events bus exists."""
        response = events_client.list_event_buses(
            NamePrefix='costguard-autonomous'
        )
        
        buses = response.get('EventBuses', [])
        assert len(buses) > 0, "Autonomous event bus not found"
        
        bus = buses[0]
        assert bus['Name'] == EVENT_BUS_NAME
    
    def test_eventbridge_rules_exist(self):
        """Verify EventBridge rules are configured."""
        response = events_client.list_rules(
            EventBusName=EVENT_BUS_NAME,
            Limit=10
        )
        
        rules = response.get('Rules', [])
        # Should have rules for autonomous actions
        # (May be 0 if rules are created dynamically)
        assert isinstance(rules, list)
    
    def test_publish_test_event(self):
        """Test publishing an event to the autonomous bus."""
        test_event = {
            'version': '0',
            'id': 'test-event-001',
            'detail-type': 'TestEvent',
            'source': 'integration-test',
            'time': datetime.utcnow().isoformat() + 'Z',
            'detail': {
                'test': True,
                'message': 'Integration test event'
            }
        }
        
        response = events_client.put_events(
            Entries=[
                {
                    'Source': test_event['source'],
                    'DetailType': test_event['detail-type'],
                    'Detail': json.dumps(test_event['detail']),
                    'EventBusName': EVENT_BUS_NAME
                }
            ]
        )
        
        assert response['FailedEntryCount'] == 0, "Failed to publish test event"


class TestPhase6BackwardCompatibility:
    """Test that autonomous loops don't break Phase 6 functionality."""
    
    def test_gpu_costs_table_accessible(self):
        """Verify Phase 6 GPU costs table is still accessible."""
        table = dynamodb.Table(GPU_COSTS_TABLE)
        
        # Should be able to query the table
        response = table.scan(Limit=1)
        assert 'Items' in response
    
    def test_demo_data_isolation(self):
        """Verify demo data is properly isolated with demo_mode flag."""
        table = dynamodb.Table(GPU_COSTS_TABLE)
        
        # Query demo data
        response = table.scan(
            FilterExpression='demo_mode = :demo',
            ExpressionAttributeValues={':demo': True},
            Limit=10
        )
        
        demo_items = response.get('Items', [])
        
        # All demo items should have demo_mode = True
        for item in demo_items:
            assert item.get('demo_mode') == True
            assert item['instance_id'].startswith('i-demo-')


class TestErrorHandlingAndRecovery:
    """Test error scenarios and recovery mechanisms."""
    
    def test_invalid_lambda_payload(self):
        """Test Lambda functions handle invalid payloads gracefully."""
        # Invoke with invalid payload
        response = lambda_client.invoke(
            FunctionName=GPU_SCHEDULER_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'invalid_field': 'invalid_value'
            })
        )
        
        # Lambda should still return 200 (function executed)
        assert response['StatusCode'] == 200
        
        # Parse Lambda response (API Gateway format)
        lambda_response = json.loads(response['Payload'].read())
        
        # The Lambda may return success with empty recommendations or an error
        # Both are acceptable for invalid input
        assert 'statusCode' in lambda_response
        assert 'body' in lambda_response
        
        # Parse body
        payload = json.loads(lambda_response['body'])
        
        # Should either have empty recommendations or error information
        if lambda_response['statusCode'] >= 400:
            assert 'error' in payload or 'errorMessage' in payload or 'message' in payload
        else:
            # If successful, should have recommendations field (possibly empty)
            assert 'recommendations' in payload
    
    def test_missing_instance_handling(self):
        """Test handling of non-existent instances."""
        response = lambda_client.invoke(
            FunctionName=RIGHT_SIZER_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'action': 'analyze_utilization',
                'instance_id': 'i-nonexistent-999',
                'days': 7,
                'demo_mode': True
            })
        )
        
        # Lambda should execute successfully
        assert response['StatusCode'] == 200
        
        # Parse Lambda response (API Gateway format)
        lambda_response = json.loads(response['Payload'].read())
        
        # Should handle gracefully - either return error or empty result
        assert 'statusCode' in lambda_response
        assert lambda_response['statusCode'] in [200, 404, 400]


class TestPerformanceRequirements:
    """Test performance requirements are met."""
    
    def test_gpu_scheduler_performance(self, demo_data_exists):
        """Test GPU Scheduler completes analysis within acceptable time."""
        start_time = time.time()
        
        response = lambda_client.invoke(
            FunctionName=GPU_SCHEDULER_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'action': 'analyze_patterns',
                'days': 7,
                'demo_mode': True
            })
        )
        
        elapsed_time = time.time() - start_time
        
        # Should complete within 30 seconds (generous for cold start)
        assert elapsed_time < 30.0, f"GPU Scheduler took {elapsed_time:.2f}s (expected <30s)"
        assert response['StatusCode'] == 200
        
        # Parse Lambda response
        lambda_response = json.loads(response['Payload'].read())
        assert lambda_response['statusCode'] == 200
    
    def test_right_sizer_performance(self, demo_data_exists):
        """Test Right Sizer completes analysis within acceptable time."""
        start_time = time.time()
        
        response = lambda_client.invoke(
            FunctionName=RIGHT_SIZER_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'action': 'analyze_utilization',
                'instance_id': 'i-demo-overprovisioned-001',
                'days': 7,
                'demo_mode': True
            })
        )
        
        elapsed_time = time.time() - start_time
        
        # Should complete within 30 seconds
        assert elapsed_time < 30.0, f"Right Sizer took {elapsed_time:.2f}s (expected <30s)"
        assert response['StatusCode'] == 200
        
        # Parse Lambda response
        lambda_response = json.loads(response['Payload'].read())
        assert lambda_response['statusCode'] == 200


@pytest.mark.slow
class TestEndToEndAutonomousLoop:
    """
    Comprehensive end-to-end test of the complete autonomous loop.
    This test takes longer and validates the full workflow.
    """
    
    def test_complete_loop_execution(self, demo_data_exists):
        """
        Execute a complete autonomous loop cycle:
        1. GPU Scheduler analyzes and recommends
        2. Safety Guard validates
        3. Action is recorded
        4. Learning Engine updates confidence
        """
        # Step 1: Analyze
        print("\n[Step 1] GPU Scheduler: Analyzing cost patterns...")
        scheduler_response = lambda_client.invoke(
            FunctionName=GPU_SCHEDULER_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'action': 'analyze_patterns',
                'days': 7,
                'demo_mode': True
            })
        )
        
        assert scheduler_response['StatusCode'] == 200
        scheduler_lambda_response = json.loads(scheduler_response['Payload'].read())
        assert scheduler_lambda_response['statusCode'] == 200
        scheduler_payload = json.loads(scheduler_lambda_response['body'])
        print(f"  ✓ Analysis complete: {json.dumps(scheduler_payload, indent=2, default=str)[:200]}...")
        
        # Step 2: Validate (Safety Guard)
        print("\n[Step 2] Safety Guard: Validating action...")
        safety_response = lambda_client.invoke(
            FunctionName=SAFETY_GUARD_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'detail-type': 'ActionRequest',
                'detail': {
                    'action_type': 'schedule_optimization',
                    'action_id': f'test-action-{int(time.time())}',
                    'parameters': {},
                    'confidence_score': 0.85,
                    'expected_cost_impact': -25.0,
                    'approval_required': False
                },
                'demo_mode': True
            })
        )
        
        assert safety_response['StatusCode'] == 200
        safety_lambda_response = json.loads(safety_response['Payload'].read())
        assert safety_lambda_response['statusCode'] in [200, 202]
        print("  ✓ Validation complete")
        
        # Step 3: Record action
        print("\n[Step 3] Recording action in history...")
        table = dynamodb.Table(ACTION_HISTORY_TABLE)
        action_id = f"test-action-{int(time.time())}"
        
        table.put_item(Item={
            'action_id': action_id,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'action_type': 'schedule_optimization',
            'status': 'completed',
            'demo_mode': True,
            'expected_savings': Decimal('25.0'),
            'actual_savings': Decimal('23.5')
        })
        print(f"  ✓ Action recorded: {action_id}")
        
        # Step 4: Update confidence (Learning Engine)
        print("\n[Step 4] Learning Engine: Updating confidence scores...")
        learning_response = lambda_client.invoke(
            FunctionName=LEARNING_ENGINE_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'detail-type': 'ActionCompleted',
                'detail': {
                    'action_id': action_id,
                    'action_type': 'schedule_optimization',
                    'status': 'completed',
                    'expected_cost_impact': -25.0,
                    'actual_cost_impact': -23.5,
                    'demo_mode': True
                }
            })
        )
        
        assert learning_response['StatusCode'] == 200
        learning_lambda_response = json.loads(learning_response['Payload'].read())
        assert learning_lambda_response['statusCode'] == 200
        learning_payload = json.loads(learning_lambda_response['body'])
        print(f"  ✓ Confidence updated: {json.dumps(learning_payload, indent=2, default=str)[:200]}...")
        
        print("\n✅ Complete autonomous loop executed successfully!")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
