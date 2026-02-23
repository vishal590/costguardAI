"""
Unit tests for InsightGenerator.
"""
import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import Mock

from src.services.insight_generator import InsightGenerator
from src.utils.types import Insight


class TestInsightGeneratorInitialization:
    """Tests for InsightGenerator initialization."""
    
    def test_insight_generator_initialization(self):
        """Test InsightGenerator initializes correctly."""
        generator = InsightGenerator()
        assert generator is not None
        assert generator.cost_explorer_client is None
        assert generator.dynamodb_client is None
    
    def test_insight_generator_with_clients(self):
        """Test InsightGenerator with clients."""
        cost_explorer_mock = Mock()
        dynamodb_mock = Mock()
        
        generator = InsightGenerator(
            cost_explorer_client=cost_explorer_mock,
            dynamodb_client=dynamodb_mock
        )
        
        assert generator.cost_explorer_client == cost_explorer_mock
        assert generator.dynamodb_client == dynamodb_mock


class TestDailySummaryGeneration:
    """Tests for daily summary generation."""
    
    def test_generate_daily_summary_no_client(self):
        """Test daily summary without Cost Explorer client."""
        generator = InsightGenerator()
        
        result = generator.generate_daily_summary("user123")
        
        assert result is None
    
    def test_generate_daily_summary_success(self):
        """Test successful daily summary generation."""
        cost_explorer_mock = Mock()
        
        # Mock yesterday's cost
        cost_explorer_mock.get_cost_and_usage.return_value = {
            'ResultsByTime': [
                {
                    'Total': {
                        'BlendedCost': {
                            'Amount': '25.50'
                        }
                    }
                }
            ]
        }
        
        generator = InsightGenerator(cost_explorer_client=cost_explorer_mock)
        
        result = generator.generate_daily_summary("user123")
        
        assert result is not None
        assert isinstance(result, Insight)
        assert result.insight_type == "summary"
        assert result.title == "Daily Cost Summary"
        assert "$25.50" in result.description
    
    def test_generate_daily_summary_cost_increase(self):
        """Test daily summary with cost increase."""
        cost_explorer_mock = Mock()
        
        # Mock responses: yesterday higher than average
        def mock_get_cost(TimePeriod, **kwargs):
            if TimePeriod['End'] == datetime.now(UTC).strftime('%Y-%m-%d'):
                # Yesterday's cost
                return {
                    'ResultsByTime': [
                        {'Total': {'BlendedCost': {'Amount': '50.00'}}}
                    ]
                }
            else:
                # Week's costs (lower average)
                return {
                    'ResultsByTime': [
                        {'Total': {'BlendedCost': {'Amount': '30.00'}}}
                        for _ in range(7)
                    ]
                }
        
        cost_explorer_mock.get_cost_and_usage.side_effect = mock_get_cost
        
        generator = InsightGenerator(cost_explorer_client=cost_explorer_mock)
        
        result = generator.generate_daily_summary("user123")
        
        assert result is not None
        assert result.severity == "warning"
        assert "higher" in result.description.lower()
    
    def test_generate_daily_summary_cost_decrease(self):
        """Test daily summary with cost decrease."""
        cost_explorer_mock = Mock()
        
        # Mock responses: yesterday lower than average
        def mock_get_cost(TimePeriod, **kwargs):
            if TimePeriod['End'] == datetime.now(UTC).strftime('%Y-%m-%d'):
                # Yesterday's cost
                return {
                    'ResultsByTime': [
                        {'Total': {'BlendedCost': {'Amount': '20.00'}}}
                    ]
                }
            else:
                # Week's costs (higher average)
                return {
                    'ResultsByTime': [
                        {'Total': {'BlendedCost': {'Amount': '40.00'}}}
                        for _ in range(7)
                    ]
                }
        
        cost_explorer_mock.get_cost_and_usage.side_effect = mock_get_cost
        
        generator = InsightGenerator(cost_explorer_client=cost_explorer_mock)
        
        result = generator.generate_daily_summary("user123")
        
        assert result is not None
        assert result.severity == "info"
        assert "lower" in result.description.lower()
    
    def test_generate_daily_summary_no_data(self):
        """Test daily summary with no data."""
        cost_explorer_mock = Mock()
        cost_explorer_mock.get_cost_and_usage.return_value = {}
        
        generator = InsightGenerator(cost_explorer_client=cost_explorer_mock)
        
        result = generator.generate_daily_summary("user123")
        
        assert result is None
    
    def test_generate_daily_summary_api_error(self):
        """Test daily summary with API error."""
        cost_explorer_mock = Mock()
        cost_explorer_mock.get_cost_and_usage.side_effect = Exception("API Error")
        
        generator = InsightGenerator(cost_explorer_client=cost_explorer_mock)
        
        result = generator.generate_daily_summary("user123")
        
        assert result is None


class TestAnomalyDetection:
    """Tests for anomaly detection."""
    
    def test_detect_anomalies_no_client(self):
        """Test anomaly detection without Cost Explorer client."""
        generator = InsightGenerator()
        
        result = generator.detect_anomalies("user123")
        
        assert result == []
    
    def test_detect_anomalies_no_anomalies(self):
        """Test anomaly detection with no anomalies."""
        cost_explorer_mock = Mock()
        
        # Mock stable costs
        cost_explorer_mock.get_cost_and_usage.return_value = {
            'ResultsByTime': [
                {
                    'Groups': [
                        {
                            'Keys': ['ec2'],
                            'Metrics': {'BlendedCost': {'Amount': '25.00'}}
                        }
                    ]
                }
                for _ in range(30)
            ]
        }
        
        generator = InsightGenerator(cost_explorer_client=cost_explorer_mock)
        
        result = generator.detect_anomalies("user123")
        
        assert result == []
    
    def test_detect_anomalies_with_spike(self):
        """Test anomaly detection with cost spike."""
        cost_explorer_mock = Mock()
        
        # Mock costs with spike on last day
        results = []
        for i in range(30):
            if i < 29:
                # Normal costs
                results.append({
                    'Groups': [
                        {
                            'Keys': ['ec2'],
                            'Metrics': {'BlendedCost': {'Amount': '20.00'}}
                        }
                    ]
                })
            else:
                # Spike on last day (100% increase)
                results.append({
                    'Groups': [
                        {
                            'Keys': ['ec2'],
                            'Metrics': {'BlendedCost': {'Amount': '40.00'}}
                        }
                    ]
                })
        
        cost_explorer_mock.get_cost_and_usage.return_value = {
            'ResultsByTime': results
        }
        
        generator = InsightGenerator(cost_explorer_client=cost_explorer_mock)
        
        result = generator.detect_anomalies("user123")
        
        assert len(result) > 0
        assert result[0].insight_type == "anomaly"
        assert result[0].severity == "warning"
        assert result[0].action_required is True
        assert "ec2" in result[0].related_services
    
    def test_detect_anomalies_multiple_services(self):
        """Test anomaly detection across multiple services."""
        cost_explorer_mock = Mock()
        
        # Mock costs with spikes in multiple services
        results = []
        for i in range(30):
            if i < 29:
                results.append({
                    'Groups': [
                        {'Keys': ['ec2'], 'Metrics': {'BlendedCost': {'Amount': '20.00'}}},
                        {'Keys': ['s3'], 'Metrics': {'BlendedCost': {'Amount': '10.00'}}}
                    ]
                })
            else:
                # Spikes on last day
                results.append({
                    'Groups': [
                        {'Keys': ['ec2'], 'Metrics': {'BlendedCost': {'Amount': '50.00'}}},
                        {'Keys': ['s3'], 'Metrics': {'BlendedCost': {'Amount': '30.00'}}}
                    ]
                })
        
        cost_explorer_mock.get_cost_and_usage.return_value = {
            'ResultsByTime': results
        }
        
        generator = InsightGenerator(cost_explorer_client=cost_explorer_mock)
        
        result = generator.detect_anomalies("user123")
        
        # Should detect anomalies in both services
        assert len(result) >= 2
        services = [insight.related_services[0] for insight in result]
        assert 'ec2' in services
        assert 's3' in services
    
    def test_detect_anomalies_insufficient_data(self):
        """Test anomaly detection with insufficient data."""
        cost_explorer_mock = Mock()
        
        # Mock only 5 days of data (need 7+)
        cost_explorer_mock.get_cost_and_usage.return_value = {
            'ResultsByTime': [
                {
                    'Groups': [
                        {'Keys': ['ec2'], 'Metrics': {'BlendedCost': {'Amount': '20.00'}}}
                    ]
                }
                for _ in range(5)
            ]
        }
        
        generator = InsightGenerator(cost_explorer_client=cost_explorer_mock)
        
        result = generator.detect_anomalies("user123")
        
        assert result == []
    
    def test_detect_anomalies_api_error(self):
        """Test anomaly detection with API error."""
        cost_explorer_mock = Mock()
        cost_explorer_mock.get_cost_and_usage.side_effect = Exception("API Error")
        
        generator = InsightGenerator(cost_explorer_client=cost_explorer_mock)
        
        result = generator.detect_anomalies("user123")
        
        assert result == []


class TestOptimizationSuggestions:
    """Tests for optimization suggestions."""
    
    def test_suggest_optimizations(self):
        """Test optimization suggestion generation."""
        generator = InsightGenerator()
        
        result = generator.suggest_optimizations("user123")
        
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(insight, Insight) for insight in result)
        assert all(insight.insight_type == "optimization" for insight in result)
    
    def test_suggest_optimizations_structure(self):
        """Test optimization suggestion structure."""
        generator = InsightGenerator()
        
        result = generator.suggest_optimizations("user123")
        
        for insight in result:
            assert insight.title is not None
            assert insight.description is not None
            assert insight.severity in ["info", "warning", "critical"]
            assert isinstance(insight.action_required, bool)
            assert isinstance(insight.related_services, list)


class TestForecastAlerts:
    """Tests for forecast alerts."""
    
    def test_check_forecast_alerts_no_client(self):
        """Test forecast alerts without DynamoDB client."""
        generator = InsightGenerator()
        
        result = generator.check_forecast_alerts("user123")
        
        assert result == []
    
    def test_check_forecast_alerts_no_overrun(self):
        """Test forecast alerts with no budget overrun."""
        dynamodb_mock = Mock()
        
        # Mock forecast data under budget
        dynamodb_mock.query.return_value = {
            'Items': [
                {'predicted_cost': {'N': '2.50'}}
                for _ in range(30)
            ]
        }
        
        generator = InsightGenerator(dynamodb_client=dynamodb_mock)
        
        result = generator.check_forecast_alerts("user123")
        
        # Total forecast: 30 * 2.50 = 75, under 100 budget
        assert result == []
    
    def test_check_forecast_alerts_with_overrun(self):
        """Test forecast alerts with budget overrun."""
        dynamodb_mock = Mock()
        
        # Mock forecast data over budget
        dynamodb_mock.query.return_value = {
            'Items': [
                {'predicted_cost': {'N': '5.00'}}
                for _ in range(30)
            ]
        }
        
        generator = InsightGenerator(dynamodb_client=dynamodb_mock)
        
        result = generator.check_forecast_alerts("user123")
        
        # Total forecast: 30 * 5.00 = 150, over 100 budget
        assert len(result) > 0
        assert result[0].insight_type == "forecast_alert"
        assert result[0].severity == "critical"
        assert result[0].action_required is True
        assert "$150" in result[0].description or "150" in result[0].description
    
    def test_check_forecast_alerts_no_data(self):
        """Test forecast alerts with no forecast data."""
        dynamodb_mock = Mock()
        dynamodb_mock.query.return_value = {'Items': []}
        
        generator = InsightGenerator(dynamodb_client=dynamodb_mock)
        
        result = generator.check_forecast_alerts("user123")
        
        assert result == []
    
    def test_check_forecast_alerts_api_error(self):
        """Test forecast alerts with API error."""
        dynamodb_mock = Mock()
        dynamodb_mock.query.side_effect = Exception("DynamoDB Error")
        
        generator = InsightGenerator(dynamodb_client=dynamodb_mock)
        
        result = generator.check_forecast_alerts("user123")
        
        assert result == []


class TestInsightGeneratorIntegration:
    """Integration tests for InsightGenerator."""
    
    def test_generate_all_insights(self):
        """Test generating all types of insights."""
        cost_explorer_mock = Mock()
        dynamodb_mock = Mock()
        
        # Mock Cost Explorer responses
        cost_explorer_mock.get_cost_and_usage.return_value = {
            'ResultsByTime': [
                {'Total': {'BlendedCost': {'Amount': '25.00'}}}
            ]
        }
        
        # Mock DynamoDB responses
        dynamodb_mock.query.return_value = {
            'Items': [
                {'predicted_cost': {'N': '5.00'}}
                for _ in range(30)
            ]
        }
        
        generator = InsightGenerator(
            cost_explorer_client=cost_explorer_mock,
            dynamodb_client=dynamodb_mock
        )
        
        # Generate all insight types
        summary = generator.generate_daily_summary("user123")
        anomalies = generator.detect_anomalies("user123")
        optimizations = generator.suggest_optimizations("user123")
        forecasts = generator.check_forecast_alerts("user123")
        
        # Verify all types generated
        assert summary is not None
        assert isinstance(anomalies, list)
        assert isinstance(optimizations, list)
        assert isinstance(forecasts, list)
    
    def test_insight_types_distinct(self):
        """Test that different insight types are distinct."""
        generator = InsightGenerator()
        
        optimizations = generator.suggest_optimizations("user123")
        
        # Verify insight types
        assert all(opt.insight_type == "optimization" for opt in optimizations)
