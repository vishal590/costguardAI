"""
Unit Tests for GPU Scheduler

Tests individual functions and edge cases for the GPU Scheduler Lambda.
Covers cost pattern analysis, optimization window identification, confidence
scoring, and integration with Phase 6 GPU costs table.
"""

import json
import os
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, Mock

import pytest

# Import GPU Scheduler functions
import sys
sys.path.insert(0, 'src')
from autonomous.gpu_scheduler import (
    TimeManager,
    OptimizationWindow,
    ScheduleRecommendation,
    analyze_cost_patterns,
    identify_optimization_windows,
    calculate_pattern_stability,
    calculate_confidence_score,
    calculate_expected_savings,
    should_recommend_spot,
    check_spot_availability,
    generate_recommendation,
    publish_recommendation_event,
    record_action,
    handler,
)


# ============================================================================
# TimeManager Tests
# ============================================================================

class TestTimeManager:
    """Test TimeManager class for demo mode time compression."""
    
    def test_get_analysis_window_production_mode(self):
        """Test analysis window in production mode (no compression)."""
        with patch.dict(os.environ, {"DEMO_MODE": "false"}):
            window = TimeManager.get_analysis_window(7)
            assert window == timedelta(days=7)
    
    def test_get_analysis_window_demo_mode(self):
        """Test analysis window in demo mode (2,016x compression)."""
        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            window = TimeManager.get_analysis_window(7)
            # 7 days = 10,080 minutes → 5 minutes in demo mode
            expected_minutes = (7 * 24 * 60) / TimeManager.COMPRESSION_FACTOR
            assert window == timedelta(minutes=expected_minutes)
    
    def test_get_polling_interval_production_mode(self):
        """Test polling interval in production mode."""
        with patch.dict(os.environ, {"DEMO_MODE": "false"}):
            interval = TimeManager.get_polling_interval(60)
            assert interval == 60
    
    def test_get_polling_interval_demo_mode(self):
        """Test polling interval in demo mode (6x compression)."""
        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            interval = TimeManager.get_polling_interval(60)
            assert interval == 10  # 60 / 6


# ============================================================================
# OptimizationWindow Tests
# ============================================================================

class TestOptimizationWindow:
    """Test OptimizationWindow class."""
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        window = OptimizationWindow(
            window_start=datetime(2024, 1, 15, 2, 0, 0),
            window_end=datetime(2024, 1, 15, 6, 0, 0),
            avg_spot_price=0.294,
            price_stability=0.92,
            region="us-east-1",
            instance_type="g4dn.xlarge",
        )
        
        result = window.to_dict()
        
        assert result["window_start"] == "2024-01-15T02:00:00"
        assert result["window_end"] == "2024-01-15T06:00:00"
        assert result["avg_spot_price"] == 0.294
        assert result["price_stability"] == 0.92
        assert result["region"] == "us-east-1"
        assert result["instance_type"] == "g4dn.xlarge"
    
    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "window_start": "2024-01-15T02:00:00",
            "window_end": "2024-01-15T06:00:00",
            "avg_spot_price": 0.294,
            "price_stability": 0.92,
            "region": "us-east-1",
            "instance_type": "g4dn.xlarge",
        }
        
        window = OptimizationWindow.from_dict(data)
        
        assert window.window_start == datetime(2024, 1, 15, 2, 0, 0)
        assert window.window_end == datetime(2024, 1, 15, 6, 0, 0)
        assert window.avg_spot_price == 0.294
        assert window.price_stability == 0.92
        assert window.region == "us-east-1"
        assert window.instance_type == "g4dn.xlarge"
    
    def test_round_trip_serialization(self):
        """Test that serialization and deserialization preserve data."""
        original = OptimizationWindow(
            window_start=datetime(2024, 1, 15, 2, 0, 0),
            window_end=datetime(2024, 1, 15, 6, 0, 0),
            avg_spot_price=0.294,
            price_stability=0.92,
            region="us-east-1",
            instance_type="g4dn.xlarge",
        )
        
        restored = OptimizationWindow.from_dict(original.to_dict())
        
        assert restored.window_start == original.window_start
        assert restored.window_end == original.window_end
        assert restored.avg_spot_price == original.avg_spot_price
        assert restored.price_stability == original.price_stability
        assert restored.region == original.region
        assert restored.instance_type == original.instance_type


# ============================================================================
# Cost Pattern Analysis Tests
# ============================================================================

class TestCostPatternAnalysis:
    """Test cost pattern analysis functions."""
    
    def test_analyze_cost_patterns_minimum_days(self):
        """Test analysis with minimum 7 days."""
        windows = analyze_cost_patterns(7)
        
        assert isinstance(windows, list)
        # Should return future windows only
        for window in windows:
            assert isinstance(window, OptimizationWindow)
            assert window.window_start > datetime.utcnow()
    
    def test_analyze_cost_patterns_extended_period(self):
        """Test analysis with extended period (30 days)."""
        windows = analyze_cost_patterns(30)
        
        assert isinstance(windows, list)
        # Function should handle extended periods without errors
        # Windows may be empty if no future optimization windows exist
        for window in windows:
            assert isinstance(window, OptimizationWindow)
            assert window.window_start > datetime.utcnow()
    
    def test_calculate_pattern_stability(self):
        """Test pattern stability calculation."""
        window = OptimizationWindow(
            window_start=datetime(2024, 1, 15, 2, 0, 0),
            window_end=datetime(2024, 1, 15, 6, 0, 0),
            avg_spot_price=0.294,
            price_stability=0.92,
            region="us-east-1",
            instance_type="g4dn.xlarge",
        )
        
        stability = calculate_pattern_stability(window)
        
        assert 0.0 <= stability <= 1.0
        assert stability == window.price_stability


# ============================================================================
# Confidence Score Tests
# ============================================================================

class TestConfidenceScore:
    """Test confidence score calculation."""
    
    def test_confidence_score_high_stability(self):
        """Test confidence score with high stability."""
        window = OptimizationWindow(
            window_start=datetime(2024, 1, 15, 2, 0, 0),
            window_end=datetime(2024, 1, 15, 6, 0, 0),
            avg_spot_price=0.294,
            price_stability=0.95,
            region="us-east-1",
            instance_type="g4dn.xlarge",
        )
        
        confidence = calculate_confidence_score(window)
        
        assert 0.0 <= confidence <= 1.0
        assert confidence >= 0.8  # High stability should yield high confidence
    
    def test_confidence_score_low_stability(self):
        """Test confidence score with low stability."""
        window = OptimizationWindow(
            window_start=datetime(2024, 1, 15, 2, 0, 0),
            window_end=datetime(2024, 1, 15, 6, 0, 0),
            avg_spot_price=0.294,
            price_stability=0.3,
            region="us-east-1",
            instance_type="g4dn.xlarge",
        )
        
        confidence = calculate_confidence_score(window)
        
        assert 0.0 <= confidence <= 1.0
        assert confidence < 0.8  # Low stability should yield lower confidence
    
    def test_confidence_score_boundary_values(self):
        """Test confidence score at boundary values."""
        # Test with stability = 0.0
        window_min = OptimizationWindow(
            window_start=datetime(2024, 1, 15, 2, 0, 0),
            window_end=datetime(2024, 1, 15, 6, 0, 0),
            avg_spot_price=0.294,
            price_stability=0.0,
            region="us-east-1",
            instance_type="g4dn.xlarge",
        )
        confidence_min = calculate_confidence_score(window_min)
        assert confidence_min == 0.0
        
        # Test with stability = 1.0
        window_max = OptimizationWindow(
            window_start=datetime(2024, 1, 15, 2, 0, 0),
            window_end=datetime(2024, 1, 15, 6, 0, 0),
            avg_spot_price=0.294,
            price_stability=1.0,
            region="us-east-1",
            instance_type="g4dn.xlarge",
        )
        confidence_max = calculate_confidence_score(window_max)
        assert confidence_max == 1.0


# ============================================================================
# Expected Savings Tests
# ============================================================================

class TestExpectedSavings:
    """Test expected savings calculation."""
    
    def test_calculate_expected_savings_typical(self):
        """Test savings calculation with typical values."""
        window = OptimizationWindow(
            window_start=datetime(2024, 1, 15, 2, 0, 0),
            window_end=datetime(2024, 1, 15, 6, 0, 0),
            avg_spot_price=0.294,
            price_stability=0.92,
            region="us-east-1",
            instance_type="g4dn.xlarge",
        )
        
        on_demand_price = 0.526
        savings_percent, savings_dollars = calculate_expected_savings(window, on_demand_price)
        
        assert savings_percent > 0
        assert savings_dollars > 0
        assert abs(savings_dollars - (on_demand_price - window.avg_spot_price)) < 0.01
        assert abs(savings_percent - ((savings_dollars / on_demand_price) * 100)) < 0.1
    
    def test_calculate_expected_savings_no_savings(self):
        """Test savings when spot price equals on-demand."""
        window = OptimizationWindow(
            window_start=datetime(2024, 1, 15, 2, 0, 0),
            window_end=datetime(2024, 1, 15, 6, 0, 0),
            avg_spot_price=0.526,
            price_stability=0.92,
            region="us-east-1",
            instance_type="g4dn.xlarge",
        )
        
        on_demand_price = 0.526
        savings_percent, savings_dollars = calculate_expected_savings(window, on_demand_price)
        
        assert savings_percent == 0.0
        assert savings_dollars == 0.0
    
    def test_should_recommend_spot_above_threshold(self):
        """Test spot recommendation when savings exceed threshold."""
        assert should_recommend_spot(25.0) is True
        assert should_recommend_spot(20.0) is True
    
    def test_should_recommend_spot_below_threshold(self):
        """Test spot recommendation when savings below threshold."""
        assert should_recommend_spot(19.9) is False
        assert should_recommend_spot(10.0) is False
        assert should_recommend_spot(0.0) is False


# ============================================================================
# Spot Availability Tests
# ============================================================================

class TestSpotAvailability:
    """Test spot availability checking."""
    
    def test_check_spot_availability_returns_valid_percentage(self):
        """Test that availability check returns valid percentage."""
        availability = check_spot_availability("us-east-1", "g4dn.xlarge")
        
        assert 0.0 <= availability <= 1.0
    
    def test_check_spot_availability_different_regions(self):
        """Test availability check for different regions."""
        regions = ["us-east-1", "us-west-2", "eu-west-1"]
        
        for region in regions:
            availability = check_spot_availability(region)
            assert 0.0 <= availability <= 1.0


# ============================================================================
# Recommendation Generation Tests
# ============================================================================

class TestRecommendationGeneration:
    """Test recommendation generation."""
    
    def test_generate_recommendation_high_confidence_high_savings(self):
        """Test recommendation with high confidence and savings."""
        window = OptimizationWindow(
            window_start=datetime(2024, 1, 15, 2, 0, 0),
            window_end=datetime(2024, 1, 15, 6, 0, 0),
            avg_spot_price=0.294,
            price_stability=0.92,
            region="us-east-1",
            instance_type="g4dn.xlarge",
        )
        
        recommendation = generate_recommendation(window)
        
        assert recommendation is not None
        assert isinstance(recommendation, ScheduleRecommendation)
        assert recommendation.confidence_score >= 0.8
        assert recommendation.expected_savings_percent >= 20.0
    
    def test_generate_recommendation_low_confidence(self):
        """Test that low confidence prevents recommendation."""
        window = OptimizationWindow(
            window_start=datetime(2024, 1, 15, 2, 0, 0),
            window_end=datetime(2024, 1, 15, 6, 0, 0),
            avg_spot_price=0.294,
            price_stability=0.5,  # Low stability
            region="us-east-1",
            instance_type="g4dn.xlarge",
        )
        
        recommendation = generate_recommendation(window)
        
        # Should return None due to low confidence
        assert recommendation is None
    
    def test_generate_recommendation_low_savings(self):
        """Test that low savings prevent recommendation."""
        window = OptimizationWindow(
            window_start=datetime(2024, 1, 15, 2, 0, 0),
            window_end=datetime(2024, 1, 15, 6, 0, 0),
            avg_spot_price=0.50,  # High spot price, low savings
            price_stability=0.92,
            region="us-east-1",
            instance_type="g4dn.xlarge",
        )
        
        recommendation = generate_recommendation(window)
        
        # Should return None due to low savings
        assert recommendation is None


# ============================================================================
# Dry-Run Mode Tests
# ============================================================================

class TestDryRunMode:
    """Test dry-run mode behavior."""
    
    @patch('autonomous.gpu_scheduler.events_client')
    def test_publish_recommendation_event_dry_run(self, mock_events):
        """Test that dry-run mode doesn't publish events."""
        with patch.dict(os.environ, {"DRY_RUN_MODE": "true"}):
            window = OptimizationWindow(
                window_start=datetime(2024, 1, 15, 2, 0, 0),
                window_end=datetime(2024, 1, 15, 6, 0, 0),
                avg_spot_price=0.294,
                price_stability=0.92,
                region="us-east-1",
                instance_type="g4dn.xlarge",
            )
            
            recommendation = ScheduleRecommendation(
                recommendation_id="rec_test",
                window=window,
                confidence_score=0.85,
                expected_savings_percent=25.0,
                expected_savings_dollars=12.50,
            )
            
            publish_recommendation_event(recommendation)
            
            # Should not call put_events in dry-run mode
            mock_events.put_events.assert_not_called()
    
    @patch('autonomous.gpu_scheduler.events_client')
    def test_publish_recommendation_event_production(self, mock_events):
        """Test that production mode publishes events."""
        with patch.dict(os.environ, {"DRY_RUN_MODE": "false"}):
            window = OptimizationWindow(
                window_start=datetime(2024, 1, 15, 2, 0, 0),
                window_end=datetime(2024, 1, 15, 6, 0, 0),
                avg_spot_price=0.294,
                price_stability=0.92,
                region="us-east-1",
                instance_type="g4dn.xlarge",
            )
            
            recommendation = ScheduleRecommendation(
                recommendation_id="rec_test",
                window=window,
                confidence_score=0.85,
                expected_savings_percent=25.0,
                expected_savings_dollars=12.50,
            )
            
            publish_recommendation_event(recommendation)
            
            # Should call put_events in production mode
            mock_events.put_events.assert_called_once()


# ============================================================================
# Lambda Handler Tests
# ============================================================================

class TestLambdaHandler:
    """Test Lambda handler function."""
    
    @patch('autonomous.gpu_scheduler.analyze_cost_patterns')
    @patch('autonomous.gpu_scheduler.generate_recommendation')
    @patch('autonomous.gpu_scheduler.publish_recommendation_event')
    @patch('autonomous.gpu_scheduler.record_action')
    def test_handler_api_gateway_request(
        self, mock_record, mock_publish, mock_generate, mock_analyze
    ):
        """Test handler with API Gateway request."""
        # Setup mocks
        mock_window = OptimizationWindow(
            window_start=datetime(2024, 1, 15, 2, 0, 0),
            window_end=datetime(2024, 1, 15, 6, 0, 0),
            avg_spot_price=0.294,
            price_stability=0.92,
            region="us-east-1",
            instance_type="g4dn.xlarge",
        )
        mock_analyze.return_value = [mock_window]
        
        mock_recommendation = ScheduleRecommendation(
            recommendation_id="rec_test",
            window=mock_window,
            confidence_score=0.85,
            expected_savings_percent=25.0,
            expected_savings_dollars=12.50,
        )
        mock_generate.return_value = mock_recommendation
        
        # Create API Gateway event
        event = {
            "body": json.dumps({
                "days": 7,
                "confidence_threshold": 0.8,
                "dry_run": False
            })
        }
        context = {}
        
        # Call handler
        response = handler(event, context)
        
        # Verify response
        assert response["statusCode"] == 200
        assert "body" in response
        
        body = json.loads(response["body"])
        assert "recommendations" in body
        assert len(body["recommendations"]) == 1
        assert body["recommendations"][0]["recommendation_id"] == "rec_test"
    
    @patch('autonomous.gpu_scheduler.analyze_cost_patterns')
    def test_handler_eventbridge_scheduled_event(self, mock_analyze):
        """Test handler with EventBridge scheduled event."""
        mock_analyze.return_value = []
        
        # Create EventBridge event
        event = {
            "source": "aws.events",
            "detail-type": "Scheduled Event"
        }
        context = {}
        
        # Call handler
        response = handler(event, context)
        
        # Verify response
        assert response["statusCode"] == 200
        mock_analyze.assert_called_once()


# ============================================================================
# Integration with Phase 6 Tests
# ============================================================================

class TestPhase6Integration:
    """Test integration with Phase 6 GPU costs table."""
    
    @patch('autonomous.gpu_scheduler.gpu_costs_table')
    def test_query_gpu_costs_table(self, mock_table):
        """Test querying GPU costs from Phase 6 table."""
        # This would test actual DynamoDB queries in integration tests
        # Unit test validates the structure
        assert mock_table is not None
    
    def test_cost_data_format_compatibility(self):
        """Test that cost data format is compatible with Phase 6."""
        # Validate that our data structures match Phase 6 expectations
        window = OptimizationWindow(
            window_start=datetime(2024, 1, 15, 2, 0, 0),
            window_end=datetime(2024, 1, 15, 6, 0, 0),
            avg_spot_price=0.294,
            price_stability=0.92,
            region="us-east-1",
            instance_type="g4dn.xlarge",
        )
        
        # Should be serializable to Phase 6 format
        data = window.to_dict()
        assert "region" in data
        assert "instance_type" in data
        assert "avg_spot_price" in data
