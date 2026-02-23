"""
Insight Generator for proactive cost insights.

This module generates proactive insights:
1. Daily cost summaries
2. Anomaly detection
3. Optimization suggestions
4. Forecast alerts
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, UTC
import logging

from ..utils.types import Insight

logger = logging.getLogger(__name__)


class InsightGenerator:
    """Generate proactive cost insights."""
    
    def __init__(
        self,
        cost_explorer_client=None,
        dynamodb_client=None
    ):
        """
        Initialize insight generator.
        
        Args:
            cost_explorer_client: AWS Cost Explorer client
            dynamodb_client: DynamoDB client for forecast/prevention data
        """
        self.cost_explorer_client = cost_explorer_client
        self.dynamodb_client = dynamodb_client
        
        logger.info("InsightGenerator initialized")
    
    def generate_daily_summary(self, user_id: str) -> Optional[Insight]:
        """
        Generate daily cost summary.
        
        Args:
            user_id: User identifier
            
        Returns:
            Daily summary Insight or None
        """
        if not self.cost_explorer_client:
            logger.warning("No Cost Explorer client, cannot generate summary")
            return None
        
        try:
            # Get yesterday's costs
            yesterday = datetime.now(UTC) - timedelta(days=1)
            yesterday_str = yesterday.strftime('%Y-%m-%d')
            today_str = datetime.now(UTC).strftime('%Y-%m-%d')
            
            response = self.cost_explorer_client.get_cost_and_usage(
                TimePeriod={
                    'Start': yesterday_str,
                    'End': today_str
                },
                Granularity='DAILY',
                Metrics=['BlendedCost']
            )
            
            if not response.get('ResultsByTime'):
                return None
            
            yesterday_cost = float(
                response['ResultsByTime'][0]['Total']['BlendedCost']['Amount']
            )
            
            # Compare to 7-day average (simplified)
            week_ago = yesterday - timedelta(days=7)
            week_response = self.cost_explorer_client.get_cost_and_usage(
                TimePeriod={
                    'Start': week_ago.strftime('%Y-%m-%d'),
                    'End': yesterday_str
                },
                Granularity='DAILY',
                Metrics=['BlendedCost']
            )
            
            week_costs = [
                float(day['Total']['BlendedCost']['Amount'])
                for day in week_response.get('ResultsByTime', [])
            ]
            
            avg_cost = sum(week_costs) / len(week_costs) if week_costs else yesterday_cost
            
            # Determine severity
            diff_percent = ((yesterday_cost - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0
            
            if diff_percent > 20:
                severity = "warning"
                description = f"Yesterday's cost (${yesterday_cost:.2f}) was {diff_percent:.1f}% higher than your 7-day average (${avg_cost:.2f})."
            elif diff_percent < -20:
                severity = "info"
                description = f"Good news! Yesterday's cost (${yesterday_cost:.2f}) was {abs(diff_percent):.1f}% lower than your 7-day average (${avg_cost:.2f})."
            else:
                severity = "info"
                description = f"Yesterday's cost was ${yesterday_cost:.2f}, consistent with your 7-day average (${avg_cost:.2f})."
            
            return Insight(
                insight_type="summary",
                title="Daily Cost Summary",
                description=description,
                severity=severity,
                action_required=False,
                related_services=[],
                estimated_impact=yesterday_cost
            )
            
        except Exception as e:
            logger.error(f"Error generating daily summary: {e}")
            return None
    
    def detect_anomalies(self, user_id: str) -> List[Insight]:
        """
        Detect cost anomalies and generate alerts.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of anomaly Insights
        """
        if not self.cost_explorer_client:
            logger.warning("No Cost Explorer client, cannot detect anomalies")
            return []
        
        try:
            # Get last 30 days of costs by service
            end_date = datetime.now(UTC)
            start_date = end_date - timedelta(days=30)
            
            response = self.cost_explorer_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Granularity='DAILY',
                Metrics=['BlendedCost'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'}
                ]
            )
            
            anomalies = []
            
            # Simplified anomaly detection: look for sudden spikes
            service_costs: Dict[str, List[float]] = {}
            
            for result in response.get('ResultsByTime', []):
                for group in result.get('Groups', []):
                    service = group['Keys'][0]
                    cost = float(group['Metrics']['BlendedCost']['Amount'])
                    
                    if service not in service_costs:
                        service_costs[service] = []
                    service_costs[service].append(cost)
            
            # Check each service for anomalies
            for service, costs in service_costs.items():
                if len(costs) < 7:
                    continue
                
                # Compare last day to previous week average
                last_day_cost = costs[-1]
                prev_week_avg = sum(costs[-8:-1]) / 7
                
                if prev_week_avg == 0:
                    continue
                
                spike_percent = ((last_day_cost - prev_week_avg) / prev_week_avg * 100)
                
                if spike_percent > 50:  # 50% spike
                    anomalies.append(Insight(
                        insight_type="anomaly",
                        title=f"Cost Spike Detected: {service}",
                        description=f"{service} costs increased by {spike_percent:.1f}% (${last_day_cost:.2f} vs ${prev_week_avg:.2f} average).",
                        severity="warning",
                        action_required=True,
                        related_services=[service],
                        estimated_impact=last_day_cost - prev_week_avg
                    ))
            
            logger.info(f"Detected {len(anomalies)} anomalies")
            return anomalies
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
            return []
    
    def suggest_optimizations(self, user_id: str) -> List[Insight]:
        """
        Suggest cost optimization opportunities.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of optimization Insights
        """
        # Placeholder: would integrate with Phase 3 idle detection
        logger.info("Generating optimization suggestions")
        
        suggestions = []
        
        # Example suggestion (would be data-driven in production)
        suggestions.append(Insight(
            insight_type="optimization",
            title="Idle Resources Detected",
            description="3 EC2 instances have been idle for >7 days. Consider stopping or terminating them to save ~$50/month.",
            severity="info",
            action_required=False,
            related_services=["ec2"],
            estimated_impact=50.0
        ))
        
        return suggestions
    
    def check_forecast_alerts(self, user_id: str) -> List[Insight]:
        """
        Check forecasts for budget overrun predictions.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of forecast alert Insights
        """
        if not self.dynamodb_client:
            logger.warning("No DynamoDB client, cannot check forecasts")
            return []
        
        try:
            # Query forecast data from Phase 2
            table_name = "cost-forecasts"
            
            # Get total forecast for next 30 days
            response = self.dynamodb_client.query(
                TableName=table_name,
                KeyConditionExpression="service = :svc",
                ExpressionAttributeValues={
                    ":svc": {"S": "total"}
                },
                Limit=30
            )
            
            alerts = []
            
            # Calculate forecasted monthly cost
            forecast_items = response.get('Items', [])
            if forecast_items:
                total_forecast = sum(
                    float(item.get('predicted_cost', {}).get('N', 0))
                    for item in forecast_items
                )
                
                # Check against budget (placeholder: $100/month)
                budget_limit = 100.0
                
                if total_forecast > budget_limit:
                    overage = total_forecast - budget_limit
                    alerts.append(Insight(
                        insight_type="forecast_alert",
                        title="Budget Overrun Predicted",
                        description=f"Forecasted costs (${total_forecast:.2f}) exceed budget (${budget_limit:.2f}) by ${overage:.2f}.",
                        severity="critical",
                        action_required=True,
                        related_services=[],
                        estimated_impact=overage
                    ))
            
            logger.info(f"Generated {len(alerts)} forecast alerts")
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking forecast alerts: {e}")
            return []
