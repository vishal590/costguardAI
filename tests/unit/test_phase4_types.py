"""
Unit tests for Phase 4 (AI Cost Advisor) data models and types.
"""
import pytest
from datetime import datetime, UTC
from src.utils.types import (
    QueryIntent,
    CostContext,
    ConversationTurn,
    AdvisorResponse,
    Recommendation,
    Insight,
    BudgetStatus
)


class TestQueryIntent:
    """Tests for QueryIntent dataclass."""
    
    def test_query_intent_cost_analysis(self):
        """Test creating a cost analysis query intent."""
        intent = QueryIntent(
            intent_type="cost_analysis",
            services=["ec2", "s3"],
            time_range=(datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 31, tzinfo=UTC)),
            accounts=["123456789012"],
            entities={"instance_ids": ["i-1234567890abcdef0"]}
        )
        
        assert intent.intent_type == "cost_analysis"
        assert len(intent.services) == 2
        assert "ec2" in intent.services
        assert len(intent.accounts) == 1
        assert "instance_ids" in intent.entities
    
    def test_query_intent_optimization(self):
        """Test creating an optimization query intent."""
        intent = QueryIntent(
            intent_type="optimization",
            services=["lambda", "dynamodb"],
            time_range=(datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 7, tzinfo=UTC)),
            accounts=[],
            entities={}
        )
        
        assert intent.intent_type == "optimization"
        assert len(intent.services) == 2
        assert intent.accounts == []
        assert intent.entities == {}
    
    def test_query_intent_forecast(self):
        """Test creating a forecast query intent."""
        intent = QueryIntent(
            intent_type="forecast",
            services=[],
            time_range=(datetime(2024, 2, 1, tzinfo=UTC), datetime(2024, 2, 29, tzinfo=UTC)),
            accounts=["123456789012"],
            entities={}
        )
        
        assert intent.intent_type == "forecast"
        assert intent.services == []


class TestCostContext:
    """Tests for CostContext dataclass."""
    
    def test_cost_context_with_all_data(self):
        """Test creating CostContext with all data sources."""
        budget = BudgetStatus(
            budget_name="test-budget",
            limit=1000.0,
            actual_spend=800.0,
            forecasted_spend=850.0,
            utilization_percent=85.0,
            currency="USD",
            time_period="2024-01"
        )
        
        context = CostContext(
            historical_costs={
                "ec2": [{"date": "2024-01-01", "blended_cost": 50.0}],
                "s3": [{"date": "2024-01-01", "blended_cost": 10.0}]
            },
            forecast_data={
                "ec2": [{"date": "2024-02-01", "predicted_cost": 55.0}]
            },
            prevention_actions=[
                {"resource_id": "i-test", "action": "stop", "estimated_savings": 72.0}
            ],
            current_budget=budget,
            anomalies=[{"service": "ec2", "spike_percent": 50.0}]
        )
        
        assert len(context.historical_costs) == 2
        assert context.forecast_data is not None
        assert len(context.prevention_actions) == 1
        assert context.current_budget.budget_name == "test-budget"
        assert len(context.anomalies) == 1
    
    def test_cost_context_minimal(self):
        """Test creating CostContext with minimal data."""
        context = CostContext(
            historical_costs={},
            forecast_data=None,
            prevention_actions=[],
            current_budget=None,
            anomalies=[]
        )
        
        assert context.historical_costs == {}
        assert context.forecast_data is None
        assert context.prevention_actions == []
        assert context.current_budget is None
        assert context.anomalies == []
    
    def test_cost_context_with_multiple_services(self):
        """Test CostContext with multiple services."""
        context = CostContext(
            historical_costs={
                "ec2": [{"date": "2024-01-01", "blended_cost": 50.0}],
                "s3": [{"date": "2024-01-01", "blended_cost": 10.0}],
                "lambda": [{"date": "2024-01-01", "blended_cost": 5.0}],
                "dynamodb": [{"date": "2024-01-01", "blended_cost": 8.0}],
                "rds": [{"date": "2024-01-01", "blended_cost": 100.0}]
            },
            forecast_data=None,
            prevention_actions=[],
            current_budget=None,
            anomalies=[]
        )
        
        assert len(context.historical_costs) == 5
        assert "rds" in context.historical_costs


class TestConversationTurn:
    """Tests for ConversationTurn dataclass."""
    
    def test_conversation_turn_creation(self):
        """Test creating a ConversationTurn."""
        context = CostContext(
            historical_costs={"ec2": [{"date": "2024-01-01", "blended_cost": 50.0}]},
            forecast_data=None,
            prevention_actions=[],
            current_budget=None,
            anomalies=[]
        )
        
        turn = ConversationTurn(
            query="What were my EC2 costs last month?",
            response="Your EC2 costs last month were $50.00.",
            timestamp=datetime.now(UTC),
            context_used=context
        )
        
        assert turn.query == "What were my EC2 costs last month?"
        assert "EC2 costs" in turn.response
        assert turn.context_used is not None
        assert isinstance(turn.timestamp, datetime)
    
    def test_conversation_turn_without_context(self):
        """Test ConversationTurn without context."""
        turn = ConversationTurn(
            query="Hello",
            response="Hi! How can I help you with your AWS costs?",
            timestamp=datetime.now(UTC),
            context_used=None
        )
        
        assert turn.context_used is None


class TestAdvisorResponse:
    """Tests for AdvisorResponse dataclass."""
    
    def test_advisor_response_with_recommendations(self):
        """Test AdvisorResponse with recommendations."""
        recommendations = [
            Recommendation(
                action="Stop idle EC2 instance i-test",
                rationale="Instance has been idle for 7 days",
                estimated_savings=72.0,
                priority=4,
                safe=True
            )
        ]
        
        response = AdvisorResponse(
            response_text="Your EC2 costs can be reduced by stopping idle instances.",
            recommendations=recommendations,
            cost_data={"total_cost": 150.0, "ec2_cost": 100.0},
            confidence=0.85,
            cached=False
        )
        
        assert "EC2 costs" in response.response_text
        assert len(response.recommendations) == 1
        assert response.cost_data["total_cost"] == 150.0
        assert response.confidence == 0.85
        assert response.cached is False
    
    def test_advisor_response_cached(self):
        """Test cached AdvisorResponse."""
        response = AdvisorResponse(
            response_text="Cached response",
            recommendations=[],
            cost_data={},
            confidence=0.9,
            cached=True
        )
        
        assert response.cached is True
    
    def test_advisor_response_no_recommendations(self):
        """Test AdvisorResponse without recommendations."""
        response = AdvisorResponse(
            response_text="Your costs are optimized.",
            recommendations=[],
            cost_data={"total_cost": 50.0},
            confidence=0.95,
            cached=False
        )
        
        assert len(response.recommendations) == 0
        assert response.confidence == 0.95


class TestRecommendation:
    """Tests for Recommendation dataclass."""
    
    def test_recommendation_high_priority(self):
        """Test high priority recommendation."""
        rec = Recommendation(
            action="Stop idle EC2 instance i-1234567890abcdef0",
            rationale="Instance has been idle for 14 days with <5% CPU utilization",
            estimated_savings=144.0,
            priority=5,
            safe=True
        )
        
        assert rec.priority == 5
        assert rec.estimated_savings == 144.0
        assert rec.safe is True
    
    def test_recommendation_low_priority(self):
        """Test low priority recommendation."""
        rec = Recommendation(
            action="Consider switching to Reserved Instances",
            rationale="You could save 30% with 1-year commitment",
            estimated_savings=50.0,
            priority=2,
            safe=True
        )
        
        assert rec.priority == 2
        assert rec.estimated_savings == 50.0
    
    def test_recommendation_unsafe(self):
        """Test unsafe recommendation (blocked by safety guards)."""
        rec = Recommendation(
            action="Terminate production database",
            rationale="Database appears idle",
            estimated_savings=500.0,
            priority=1,
            safe=False
        )
        
        assert rec.safe is False
        assert rec.priority == 1
    
    def test_recommendation_zero_savings(self):
        """Test recommendation with zero savings."""
        rec = Recommendation(
            action="Enable cost allocation tags",
            rationale="Better cost tracking and reporting",
            estimated_savings=0.0,
            priority=3,
            safe=True
        )
        
        assert rec.estimated_savings == 0.0


class TestInsight:
    """Tests for Insight dataclass."""
    
    def test_insight_daily_summary(self):
        """Test daily summary insight."""
        insight = Insight(
            insight_type="summary",
            title="Daily Cost Summary",
            description="Yesterday's cost was $50.00, consistent with your 7-day average.",
            severity="info",
            action_required=False,
            related_services=[],
            estimated_impact=50.0
        )
        
        assert insight.insight_type == "summary"
        assert insight.severity == "info"
        assert insight.action_required is False
        assert insight.estimated_impact == 50.0
    
    def test_insight_anomaly_warning(self):
        """Test anomaly warning insight."""
        insight = Insight(
            insight_type="anomaly",
            title="Cost Spike Detected: EC2",
            description="EC2 costs increased by 75% compared to last week.",
            severity="warning",
            action_required=True,
            related_services=["ec2"],
            estimated_impact=100.0
        )
        
        assert insight.insight_type == "anomaly"
        assert insight.severity == "warning"
        assert insight.action_required is True
        assert "ec2" in insight.related_services
    
    def test_insight_optimization(self):
        """Test optimization insight."""
        insight = Insight(
            insight_type="optimization",
            title="Idle Resources Detected",
            description="3 EC2 instances have been idle for >7 days.",
            severity="info",
            action_required=False,
            related_services=["ec2"],
            estimated_impact=216.0
        )
        
        assert insight.insight_type == "optimization"
        assert insight.estimated_impact == 216.0
    
    def test_insight_forecast_alert_critical(self):
        """Test critical forecast alert."""
        insight = Insight(
            insight_type="forecast_alert",
            title="Budget Overrun Predicted",
            description="Forecasted costs exceed budget by $200.",
            severity="critical",
            action_required=True,
            related_services=[],
            estimated_impact=200.0
        )
        
        assert insight.insight_type == "forecast_alert"
        assert insight.severity == "critical"
        assert insight.action_required is True
    
    def test_insight_no_impact(self):
        """Test insight without estimated impact."""
        insight = Insight(
            insight_type="summary",
            title="Cost Tracking Enabled",
            description="Cost allocation tags are now active.",
            severity="info",
            action_required=False,
            related_services=[],
            estimated_impact=None
        )
        
        assert insight.estimated_impact is None


class TestDataModelConversions:
    """Tests for data model conversions and type compatibility."""
    
    def test_query_intent_to_dict(self):
        """Test converting QueryIntent to dictionary."""
        intent = QueryIntent(
            intent_type="cost_analysis",
            services=["ec2"],
            time_range=(datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 31, tzinfo=UTC)),
            accounts=[],
            entities={}
        )
        
        # Verify all fields are accessible
        assert hasattr(intent, 'intent_type')
        assert hasattr(intent, 'services')
        assert hasattr(intent, 'time_range')
        assert hasattr(intent, 'accounts')
        assert hasattr(intent, 'entities')
    
    def test_advisor_response_with_nested_objects(self):
        """Test AdvisorResponse with nested Recommendation objects."""
        recommendations = [
            Recommendation(
                action="Action 1",
                rationale="Reason 1",
                estimated_savings=50.0,
                priority=3,
                safe=True
            ),
            Recommendation(
                action="Action 2",
                rationale="Reason 2",
                estimated_savings=100.0,
                priority=4,
                safe=True
            )
        ]
        
        response = AdvisorResponse(
            response_text="Test response",
            recommendations=recommendations,
            cost_data={},
            confidence=0.8,
            cached=False
        )
        
        assert len(response.recommendations) == 2
        assert response.recommendations[0].estimated_savings == 50.0
        assert response.recommendations[1].priority == 4
