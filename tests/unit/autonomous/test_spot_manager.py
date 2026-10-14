"""
Unit Tests for Spot Manager

Tests individual functions and edge cases for the Spot Manager Lambda.
Covers checkpoint save/restore, spot interruption handling, on-demand fallback,
cost calculation, and approval workflow.
"""

import hashlib
import json
import os
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, Mock, call

import pytest

# Import Spot Manager functions
from autonomous.spot_manager import (
    TrainingCheckpoint,
    save_checkpoint,
    verify_checkpoint_integrity,
    restore_from_checkpoint,
    select_most_recent_checkpoint,
    acquire_replacement_instance,
    check_spot_availability,
    request_ondemand_approval,
    track_spot_cost,
    track_ondemand_cost,
    calculate_total_training_cost,
    handler,
)


# ============================================================================
# TrainingCheckpoint Tests
# ============================================================================

class TestTrainingCheckpoint:
    """Test TrainingCheckpoint class."""
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        training_state = {
            "training_job_id": "job_123",
            "epoch": 5,
            "step": 1000,
            "loss": 0.25,
            "model_name": "resnet50",
        }
        
        checkpoint = TrainingCheckpoint(
            checkpoint_id="ckpt_20240115_020000_resnet50",
            instance_id="i-1234567890abcdef0",
            training_job_id="job_123",
            s3_location="s3://costguard-training-checkpoints/job_123/checkpoint_epoch_5.json",
            training_state=training_state,
            checkpoint_size_bytes=1024,
        )
        
        result = checkpoint.to_dict()
        
        assert result["checkpoint_id"] == "ckpt_20240115_020000_resnet50"
        assert result["instance_id"] == "i-1234567890abcdef0"
        assert result["training_job_id"] == "job_123"
        assert result["s3_location"] == "s3://costguard-training-checkpoints/job_123/checkpoint_epoch_5.json"
        assert result["checkpoint_size_bytes"] == 1024
        assert result["integrity_verified"] is False
        assert result["training_state"] == training_state
        assert result["created_by"] == "spot_manager"
        assert result["restored_count"] == 0
    
    def test_checkpoint_creation_sets_timestamp(self):
        """Test that checkpoint creation sets created_at timestamp."""
        checkpoint = TrainingCheckpoint(
            checkpoint_id="ckpt_test",
            instance_id="i-test",
            training_job_id="job_test",
            s3_location="s3://bucket/key",
            training_state={},
        )
        
        assert isinstance(checkpoint.created_at, datetime)
        assert checkpoint.created_at <= datetime.utcnow()


# ============================================================================
# Checkpoint Save/Restore Tests
# ============================================================================

class TestCheckpointSaveRestore:
    """Test checkpoint save and restore functions."""
    
    @patch('autonomous.spot_manager.s3_client')
    @patch('autonomous.spot_manager.training_checkpoints_table')
    def test_save_checkpoint_success(self, mock_table, mock_s3):
        """Test successful checkpoint save."""
        training_state = {
            "training_job_id": "job_123",
            "epoch": 5,
            "step": 1000,
            "loss": 0.25,
            "model_name": "resnet50",
        }
        
        # Mock S3 operations
        mock_s3.put_object.return_value = {}
        mock_s3.get_object.return_value = {
            'Body': Mock(read=lambda: json.dumps(training_state, default=str).encode('utf-8'))
        }
        
        # Mock DynamoDB operations
        mock_table.put_item.return_value = {}
        
        # Save checkpoint
        checkpoint_id = save_checkpoint("i-test123", training_state)
        
        # Verify checkpoint ID format
        assert checkpoint_id.startswith("ckpt_")
        assert "resnet50" in checkpoint_id
        
        # Verify S3 put_object was called
        mock_s3.put_object.assert_called_once()
        call_args = mock_s3.put_object.call_args
        assert call_args[1]["Bucket"] == "costguard-training-checkpoints"
        assert "job_123" in call_args[1]["Key"]
        
        # Verify DynamoDB put_item was called
        mock_table.put_item.assert_called_once()
    
    @patch('autonomous.spot_manager.s3_client')
    def test_save_checkpoint_timeout_warning(self, mock_s3):
        """Test checkpoint save timeout warning."""
        import time
        
        # Mock S3 to simulate slow upload
        def slow_put_object(*args, **kwargs):
            time.sleep(0.1)  # Simulate delay
            return {}
        
        mock_s3.put_object.side_effect = slow_put_object
        mock_s3.get_object.return_value = {
            'Body': Mock(read=lambda: b'{}')
        }
        
        with patch('autonomous.spot_manager.training_checkpoints_table'):
            with patch('autonomous.spot_manager.CHECKPOINT_TIMEOUT_SECONDS', 0.05):
                # This should log a warning but still succeed
                checkpoint_id = save_checkpoint("i-test", {"training_job_id": "job_test"})
                assert checkpoint_id is not None
    
    @patch('autonomous.spot_manager.s3_client')
    def test_save_checkpoint_failure(self, mock_s3):
        """Test checkpoint save failure handling."""
        mock_s3.put_object.side_effect = Exception("S3 error")
        
        with pytest.raises(Exception) as exc_info:
            save_checkpoint("i-test", {"training_job_id": "job_test"})
        
        assert "S3 error" in str(exc_info.value)
    
    @patch('autonomous.spot_manager.s3_client')
    def test_verify_checkpoint_integrity_success(self, mock_s3):
        """Test successful checkpoint integrity verification."""
        checkpoint_data = b'{"test": "data"}'
        
        mock_s3.get_object.return_value = {
            'Body': Mock(read=lambda: checkpoint_data)
        }
        
        result = verify_checkpoint_integrity("ckpt_test", "test/key", checkpoint_data)
        
        assert result is True
        mock_s3.get_object.assert_called_once()
    
    @patch('autonomous.spot_manager.s3_client')
    def test_verify_checkpoint_integrity_failure(self, mock_s3):
        """Test checkpoint integrity verification failure."""
        original_data = b'{"test": "data"}'
        corrupted_data = b'{"test": "corrupted"}'
        
        mock_s3.get_object.return_value = {
            'Body': Mock(read=lambda: corrupted_data)
        }
        
        result = verify_checkpoint_integrity("ckpt_test", "test/key", original_data)
        
        assert result is False
    
    @patch('autonomous.spot_manager.s3_client')
    def test_verify_checkpoint_integrity_exception(self, mock_s3):
        """Test checkpoint integrity verification with exception."""
        mock_s3.get_object.side_effect = Exception("S3 error")
        
        result = verify_checkpoint_integrity("ckpt_test", "test/key", b"data")
        
        assert result is False
    
    @patch('autonomous.spot_manager.s3_client')
    @patch('autonomous.spot_manager.training_checkpoints_table')
    def test_metadata_only_checkpoint_cannot_claim_training_restore(self, mock_table, mock_s3):
        """Progress metadata does not prove model restoration."""
        training_state = {
            "training_job_id": "job_123",
            "epoch": 5,
            "step": 1000,
            "loss": 0.25,
            "model_name": "resnet50",
        }
        
        # Mock DynamoDB query
        mock_table.query.return_value = {
            "Items": [{
                "checkpoint_id": "ckpt_test",
                "created_at": "2024-01-15T02:00:00",
                "s3_location": "s3://costguard-training-checkpoints/job_123/checkpoint.json",
                "integrity_verified": True,
            }]
        }
        
        # Mock S3 get_object
        mock_s3.get_object.return_value = {
            'Body': Mock(read=lambda: json.dumps(training_state).encode('utf-8'))
        }
        
        # Mock DynamoDB update
        mock_table.update_item.return_value = {}
        
        # Restore checkpoint
        result = restore_from_checkpoint("ckpt_test", "i-new123")
        
        assert result is False
        mock_table.query.assert_not_called()
        mock_s3.get_object.assert_not_called()
        mock_table.update_item.assert_not_called()
    
    @patch('autonomous.spot_manager.training_checkpoints_table')
    def test_restore_from_checkpoint_not_found(self, mock_table):
        """Test checkpoint restoration when checkpoint not found."""
        mock_table.query.return_value = {"Items": []}
        
        result = restore_from_checkpoint("ckpt_nonexistent", "i-new123")
        
        assert result is False
    
    @patch('autonomous.spot_manager.training_checkpoints_table')
    def test_restore_from_checkpoint_not_verified(self, mock_table):
        """Test checkpoint restoration when integrity not verified."""
        mock_table.query.return_value = {
            "Items": [{
                "checkpoint_id": "ckpt_test",
                "created_at": "2024-01-15T02:00:00",
                "s3_location": "s3://bucket/key",
                "integrity_verified": False,
            }]
        }
        
        result = restore_from_checkpoint("ckpt_test", "i-new123")
        
        assert result is False
    
    @patch('autonomous.spot_manager.training_checkpoints_table')
    def test_select_most_recent_checkpoint_success(self, mock_table):
        """Test selecting most recent checkpoint."""
        mock_table.query.return_value = {
            "Items": [
                {
                    "checkpoint_id": "ckpt_newest",
                    "created_at": "2024-01-15T03:00:00",
                    "integrity_verified": True,
                },
                {
                    "checkpoint_id": "ckpt_older",
                    "created_at": "2024-01-15T02:00:00",
                    "integrity_verified": True,
                },
            ]
        }
        
        checkpoint_id = select_most_recent_checkpoint("job_123")
        
        assert checkpoint_id == "ckpt_newest"
        mock_table.query.assert_called_once()
    
    @patch('autonomous.spot_manager.training_checkpoints_table')
    def test_select_most_recent_checkpoint_skip_unverified(self, mock_table):
        """Test that unverified checkpoints are skipped."""
        mock_table.query.return_value = {
            "Items": [
                {
                    "checkpoint_id": "ckpt_newest_unverified",
                    "created_at": "2024-01-15T03:00:00",
                    "integrity_verified": False,
                },
                {
                    "checkpoint_id": "ckpt_older_verified",
                    "created_at": "2024-01-15T02:00:00",
                    "integrity_verified": True,
                },
            ]
        }
        
        checkpoint_id = select_most_recent_checkpoint("job_123")
        
        assert checkpoint_id == "ckpt_older_verified"
    
    @patch('autonomous.spot_manager.training_checkpoints_table')
    def test_select_most_recent_checkpoint_none_found(self, mock_table):
        """Test when no verified checkpoints found."""
        mock_table.query.return_value = {"Items": []}
        
        checkpoint_id = select_most_recent_checkpoint("job_123")
        
        assert checkpoint_id is None


# ============================================================================
# Spot Instance Replacement Tests
# ============================================================================

class TestSpotInstanceReplacement:
    """Test spot instance replacement functions."""
    
    @patch('autonomous.spot_manager.events_client')
    @patch('autonomous.spot_manager.check_spot_availability', return_value=True)
    def test_acquire_replacement_instance_spot_success(self, availability, events):
        events.put_events.return_value = {"FailedEntryCount": 0}
        instance_id, mode = acquire_replacement_instance("us-east-1", "g4dn.xlarge", "job-1", parameters={"launch_template_id": "lt-test", "launch_template_version": "1", "max_runtime_minutes": 10, "max_hourly_cost": "0.1", "region": "us-east-1"})
        assert instance_id is None and mode == "pending_approval"
        payload = json.loads(events.put_events.call_args.kwargs["Entries"][0]["Detail"])
        assert payload["action_type"] == "spot_migration"
        assert payload["approval_required"] is True

    @patch('autonomous.spot_manager.events_client')
    @patch('autonomous.spot_manager.check_spot_availability', return_value=False)
    def test_acquire_replacement_instance_ondemand_fallback(self, availability, events):
        events.put_events.return_value = {"FailedEntryCount": 0}
        instance_id, mode = acquire_replacement_instance("us-east-1", "g4dn.xlarge", "job-1", parameters={"launch_template_id": "lt-test", "launch_template_version": "1", "max_runtime_minutes": 10, "max_hourly_cost": "0.1", "region": "us-east-1"})
        assert instance_id is None and mode == "pending_approval"
        payload = json.loads(events.put_events.call_args.kwargs["Entries"][0]["Detail"])
        assert payload["action_type"] == "ondemand_fallback"

    @patch('autonomous.spot_manager.events_client')
    @patch('autonomous.spot_manager.check_spot_availability', return_value=False)
    def test_acquire_replacement_instance_approval_denied(self, availability, events):
        instance_id, mode = acquire_replacement_instance("us-east-1", "g4dn.xlarge", "job-1")
        assert instance_id is None and mode == "failed"
        events.put_events.assert_not_called()
    
    def test_check_spot_availability_returns_boolean(self):
        """Test that spot availability check returns boolean."""
        result = check_spot_availability("us-east-1", "g4dn.xlarge")
        
        assert isinstance(result, bool)
    
    @patch('autonomous.spot_manager.events_client')
    def test_request_ondemand_approval_success(self, events):
        events.put_events.return_value = {"FailedEntryCount": 0}
        result = request_ondemand_approval("job-1", "g4dn.xlarge", "us-east-1", parameters={"launch_template_id": "lt-test", "launch_template_version": "1", "max_runtime_minutes": 10, "max_hourly_cost": "0.1", "region": "us-east-1"})
        assert isinstance(result, str) and result.startswith("req_")
        payload = json.loads(events.put_events.call_args.kwargs["Entries"][0]["Detail"])
        assert payload["action_id"] and payload["parameters"]["training_job_id"] == "job-1"
    
    @patch('autonomous.spot_manager.events_client')
    def test_request_ondemand_approval_failure(self, events):
        events.put_events.return_value = {"FailedEntryCount": 1}
        with pytest.raises(RuntimeError):
            request_ondemand_approval("job-1", "g4dn.xlarge", "us-east-1", parameters={"launch_template_id": "lt-test", "launch_template_version": "1", "max_runtime_minutes": 10, "max_hourly_cost": "0.1", "region": "us-east-1"})


# ============================================================================
# Cost Tracking Tests
# ============================================================================

class TestCostTracking:
    """Test cost tracking functions."""
    
    def test_track_spot_cost_typical(self):
        """Test spot cost tracking with typical values."""
        cost = track_spot_cost("i-test123", 1.0)
        
        assert isinstance(cost, Decimal)
        assert cost > 0
        # g4dn.xlarge spot ~$0.294/hour
        assert cost == Decimal("0.294")
    
    def test_track_spot_cost_zero_duration(self):
        """Test spot cost with zero duration."""
        cost = track_spot_cost("i-test123", 0.0)
        
        assert cost == Decimal("0")
    
    def test_track_spot_cost_fractional_hours(self):
        """Test spot cost with fractional hours."""
        cost = track_spot_cost("i-test123", 0.5)
        
        expected = Decimal("0.294") * Decimal("0.5")
        assert cost == expected
    
    def test_track_ondemand_cost_typical(self):
        """Test on-demand cost tracking with typical values."""
        cost = track_ondemand_cost("i-test123", 1.0)
        
        assert isinstance(cost, Decimal)
        assert cost > 0
        # g4dn.xlarge on-demand $0.526/hour
        assert cost == Decimal("0.526")
    
    def test_track_ondemand_cost_zero_duration(self):
        """Test on-demand cost with zero duration."""
        cost = track_ondemand_cost("i-test123", 0.0)
        
        assert cost == Decimal("0")
    
    def test_ondemand_more_expensive_than_spot(self):
        """Test that on-demand is more expensive than spot."""
        spot_cost = track_spot_cost("i-test", 1.0)
        ondemand_cost = track_ondemand_cost("i-test", 1.0)
        
        assert ondemand_cost > spot_cost
    
    @patch('autonomous.spot_manager.action_history_table')
    def test_calculate_total_training_cost_success(self, mock_table):
        """Test total training cost calculation."""
        mock_table.query.return_value = {
            "Items": [
                {
                    "action_id": "act_1",
                    "parameters": {
                        "training_job_id": "job_123",
                        "spot_cost": 1.5,
                        "ondemand_cost": 0.0,
                    }
                },
                {
                    "action_id": "act_2",
                    "parameters": {
                        "training_job_id": "job_123",
                        "spot_cost": 0.5,
                        "ondemand_cost": 2.0,
                    }
                },
            ]
        }
        
        costs = calculate_total_training_cost("job_123")
        
        assert costs["spot_cost"] == Decimal("2.0")
        assert costs["ondemand_cost"] == Decimal("2.0")
        assert costs["total_cost"] == Decimal("4.0")
    
    @patch('autonomous.spot_manager.action_history_table')
    def test_calculate_total_training_cost_no_actions(self, mock_table):
        """Test total cost calculation with no actions."""
        mock_table.query.return_value = {"Items": []}
        
        costs = calculate_total_training_cost("job_123")
        
        assert costs["spot_cost"] == Decimal("0")
        assert costs["ondemand_cost"] == Decimal("0")
        assert costs["total_cost"] == Decimal("0")
    
    @patch('autonomous.spot_manager.action_history_table')
    def test_calculate_total_training_cost_exception(self, mock_table):
        """Test total cost calculation with exception."""
        mock_table.query.side_effect = Exception("DynamoDB error")
        
        costs = calculate_total_training_cost("job_123")
        
        # Should return zeros on error
        assert costs["spot_cost"] == Decimal("0")
        assert costs["ondemand_cost"] == Decimal("0")
        assert costs["total_cost"] == Decimal("0")


# ============================================================================
# Lambda Handler Tests
# ============================================================================

class TestLambdaHandler:
    """Test Lambda handler function."""
    
    @patch('autonomous.spot_manager.acquire_replacement_instance', return_value=(None, "pending_approval"))
    @patch('autonomous.spot_manager.save_checkpoint', return_value="checkpoint-1")
    def test_handler_spot_interruption_success(self, save, acquire):
        event = {"id": "event-1", "region": "us-east-1", "detail": {"instance_id": "i-old", "training_job_id": "job-1", "parameters": {"launch_template_id": "lt-test", "launch_template_version": "1", "max_runtime_minutes": 10, "max_hourly_cost": "0.1", "region": "us-east-1"}, "training_state": {"epoch": 5}}}
        with patch.dict(os.environ, {"DRY_RUN_MODE": "false"}):
            response = handler(event, None)
        assert response["statusCode"] == 202
        body = json.loads(response["body"])
        assert body["status"] == "pending_approval" and "new_instance_id" not in body
        assert body["checkpoint_id"] == "checkpoint-1"
        save.assert_called_once()
    
    @patch('autonomous.spot_manager.acquire_replacement_instance')
    @patch('autonomous.spot_manager.save_checkpoint', side_effect=RuntimeError("Checkpoint unavailable"))
    def test_handler_checkpoint_save_failure(self, save, acquire):
        event = {"region": "us-east-1", "detail": {"instance_id": "i-old", "training_job_id": "job-1", "parameters": {"launch_template_id": "lt-test", "launch_template_version": "1", "max_runtime_minutes": 10, "max_hourly_cost": "0.1", "region": "us-east-1"}, "training_state": {"epoch": 5}}}
        with patch.dict(os.environ, {"DRY_RUN_MODE": "false"}), pytest.raises(RuntimeError):
            handler(event, None)
        acquire.assert_not_called()

    @patch('autonomous.spot_manager.acquire_replacement_instance', return_value=(None, "failed"))
    def test_handler_instance_acquisition_failure(self, acquire):
        event = {"region": "us-east-1", "detail": {"instance_id": "i-old", "training_job_id": "job-1", "parameters": {"launch_template_id": "lt-test", "launch_template_version": "1", "max_runtime_minutes": 10, "max_hourly_cost": "0.1", "region": "us-east-1"}}}
        with patch.dict(os.environ, {"DRY_RUN_MODE": "false"}):
            response = handler(event, None)
        assert response["statusCode"] == 400
        assert json.loads(response["body"])["status"] == "failed"
    
    @patch('autonomous.spot_manager.restore_from_checkpoint')
    @patch('autonomous.spot_manager.acquire_replacement_instance')
    def test_handler_restore_failure(self, acquire, restore):
        event = {"region": "us-east-1", "detail": {"instance_id": "i-old", "training_job_id": "job-1"}}
        with patch.dict(os.environ, {"DRY_RUN_MODE": "false"}):
            assert handler(event, None)["statusCode"] == 400
        acquire.assert_not_called()
        restore.assert_not_called()
    
    @patch('autonomous.spot_manager.acquire_replacement_instance')
    def test_handler_ondemand_fallback(self, acquire):
        event = {"region": "us-east-1", "detail": {"instance_id": "i-old", "training_job_id": "job-1", "parameters": {"launch_template_id": "lt-test", "launch_template_version": "1", "max_runtime_minutes": 10, "max_hourly_cost": "0.1", "region": "us-east-1"}}}
        with patch.dict(os.environ, {"DRY_RUN_MODE": "true"}):
            response = handler(event, None)
        assert json.loads(response["body"])["status"] == "dry_run"
        acquire.assert_not_called()


# ============================================================================
# Edge Cases and Error Handling Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_track_cost_with_large_duration(self):
        """Test cost tracking with large duration."""
        cost = track_spot_cost("i-test", 720.0)  # 30 days
        
        assert cost > 0
        assert isinstance(cost, Decimal)
    
    def test_track_cost_precision(self):
        """Test that cost calculations maintain precision."""
        cost1 = track_spot_cost("i-test", 0.1)
        cost2 = track_spot_cost("i-test", 0.2)
        cost3 = track_spot_cost("i-test", 0.3)
        
        # Should maintain precision with Decimal
        assert cost1 + cost2 == cost3
    
    @patch('autonomous.spot_manager.training_checkpoints_table')
    def test_select_checkpoint_with_exception(self, mock_table):
        """Test checkpoint selection with exception."""
        mock_table.query.side_effect = Exception("DynamoDB error")
        
        checkpoint_id = select_most_recent_checkpoint("job_test")
        
        assert checkpoint_id is None
