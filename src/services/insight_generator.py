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
        dynamodb_client=None,
        resource_manager=None,
        idle_detector=None,
        budget_monitor=None,
        budgets_client=None,
        pricing_manager=None
    ):
        """
        Initialize insight generator.
        
        Args:
            cost_explorer_client: AWS Cost Explorer client
            dynamodb_client: DynamoDB client for forecast/prevention data
            resource_manager: ResourceManager instance for Phase 3 integration
            idle_detector: IdleDetector instance for Phase 3 integration
            budget_monitor: BudgetMonitor instance for budget data
            budgets_client: AWS Budgets client for budget queries
            pricing_manager: PricingManager instance for savings estimation (optional)
        """
        self.cost_explorer_client = cost_explorer_client
        self.dynamodb_client = dynamodb_client
        self.resource_manager = resource_manager
        self.idle_detector = idle_detector
        self.budget_monitor = budget_monitor
        self.budgets_client = budgets_client
        self.pricing_manager = pricing_manager
        
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
        Suggest cost optimization opportunities based on Phase 3 idle detection.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of optimization Insights
        """
        logger.info("Generating optimization suggestions from Phase 3 idle detection")
        
        suggestions = []
        
        # Integrate with Phase 3 idle detection
        if not self.resource_manager or not self.idle_detector:
            logger.warning("Phase 3 components not available, returning empty suggestions")
            return []
        
        try:
            # Get resources from inventory
            resources = self.resource_manager.discover_resources(
                ["ec2", "rds", "lambda", "ebs", "dynamodb", "nat_gateway"]
            )
            
            idle_resources_by_service = {}
            total_estimated_savings = 0.0
            
            # Check each resource for idle status
            for resource in resources:
                try:
                    metadata = self.resource_manager.get_resource_metadata(resource)
                    idle_status = self.idle_detector.is_resource_idle(resource, metadata)
                    
                    if idle_status.is_idle and idle_status.idle_duration >= 7 * 24 * 60:  # At least 7 days
                        service = resource.service
                        if service not in idle_resources_by_service:
                            idle_resources_by_service[service] = []
                        
                        # Estimate monthly savings using real pricing
                        estimated_monthly_savings = self._estimate_resource_savings(resource)
                        total_estimated_savings += estimated_monthly_savings
                        
                        idle_resources_by_service[service].append({
                            'resource_id': resource.resource_id,
                            'idle_duration_days': idle_status.idle_duration / (24 * 60),
                            'estimated_savings': estimated_monthly_savings
                        })
                        
                except Exception as e:
                    logger.debug(f"Failed to check idle status for {resource.resource_id}: {e}")
                    continue
            
            # Create insights grouped by service
            for service, idle_resources in idle_resources_by_service.items():
                if not idle_resources:  # Skip empty lists
                    continue
                    
                count = len(idle_resources)
                service_savings = sum(r['estimated_savings'] for r in idle_resources)
                avg_duration = sum(r['idle_duration_days'] for r in idle_resources) / count if count > 0 else 0.0
                
                resource_list = ", ".join([r['resource_id'] for r in idle_resources[:5]])  # Show first 5
                if count > 5:
                    resource_list += f" and {count - 5} more"
                
                suggestions.append(Insight(
                    insight_type="optimization",
                    title=f"Idle {service.upper()} Resources Detected",
                    description=f"{count} {service} resources have been idle for {avg_duration:.1f} days on average. "
                               f"Resources: {resource_list}. Estimated savings: ${service_savings:.2f}/month if stopped.",
                    severity="info" if count < 5 else "warning",
                    action_required=count >= 5,
                    related_services=[service],
                    estimated_impact=service_savings
                ))
            
            if suggestions:
                logger.info(f"Generated {len(suggestions)} optimization suggestions for {sum(len(r) for r in idle_resources_by_service.values())} idle resources")
            else:
                logger.info("No idle resources found for optimization suggestions")
                
        except Exception as e:
            logger.error(f"Error generating optimization suggestions: {e}")
            # Return empty list on error rather than placeholder
        
        return suggestions
    
    def check_forecast_alerts(self, user_id: str) -> List[Insight]:
        """
        Check forecasts for budget overrun predictions using real budget data.
        
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
            if not forecast_items:
                return []
            
            total_forecast = sum(
                float(item.get('predicted_cost', {}).get('N', 0))
                for item in forecast_items
            )
            
            # Get real budget data from AWS Budgets or Phase 3
            budget_limits = []
            
            # Try Phase 3 BudgetMonitor first
            if self.budget_monitor:
                try:
                    threshold_events = self.budget_monitor.poll_budgets()
                    for event in threshold_events:
                        budget_status = event.budget_status
                        budget_limits.append({
                            'name': budget_status.budget_name,
                            'limit': budget_status.limit,
                            'currency': budget_status.currency
                        })
                except Exception as e:
                    logger.debug(f"Failed to get budgets from BudgetMonitor: {e}")
            
            # Fallback to AWS Budgets API
            if not budget_limits and self.budgets_client:
                try:
                    import boto3
                    sts = boto3.client('sts')
                    account_id = sts.get_caller_identity()['Account']
                    
                    budgets_response = self.budgets_client.describe_budgets(AccountId=account_id)
                    for budget in budgets_response.get('Budgets', []):
                        limit = float(budget['BudgetLimit']['Amount'])
                        currency = budget['BudgetLimit']['Unit']
                        budget_limits.append({
                            'name': budget['BudgetName'],
                            'limit': limit,
                            'currency': currency
                        })
                except Exception as e:
                    logger.debug(f"Failed to get budgets from AWS Budgets API: {e}")
            
            # Check forecast against each budget
            for budget in budget_limits:
                budget_limit = budget['limit']
                budget_name = budget['name']
                currency = budget.get('currency', 'USD')
                
                # Convert forecast to monthly (30-day forecast assumed to be monthly)
                monthly_forecast = total_forecast
                
                if monthly_forecast > budget_limit:
                    overage = monthly_forecast - budget_limit
                    overage_percent = (overage / budget_limit * 100) if budget_limit > 0 else 0
                    
                    alerts.append(Insight(
                        insight_type="forecast_alert",
                        title=f"Budget Overrun Predicted: {budget_name}",
                        description=f"Forecasted costs (${monthly_forecast:.2f} {currency}) exceed budget "
                                   f"(${budget_limit:.2f} {currency}) by ${overage:.2f} ({overage_percent:.1f}%).",
                        severity="critical" if overage_percent > 20 else "warning",
                        action_required=True,
                        related_services=[],
                        estimated_impact=overage
                    ))
            
            # If no budgets found, log warning but don't create alert
            if not budget_limits:
                logger.warning("No budgets found - cannot check forecast overruns. Configure AWS Budgets or Phase 3 budget monitoring.")
            
            logger.info(f"Generated {len(alerts)} forecast alerts")
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking forecast alerts: {e}")
            return []
    
    def _estimate_resource_savings(self, resource) -> float:
        """
        Estimate monthly savings from stopping/optimizing resource using real pricing.
        
        Args:
            resource: Resource object with service, region, resource_id
            
        Returns:
            Estimated monthly savings in USD
        """
        try:
            # Initialize PricingManager if not provided
            if not self.pricing_manager:
                from ..pricing_manager import PricingManager
                import os
                region = resource.region if hasattr(resource, 'region') else os.environ.get('AWS_REGION', 'us-east-1')
                self.pricing_manager = PricingManager(region=region)
            
            region = resource.region if hasattr(resource, 'region') else 'us-east-1'
            
            # Service-specific pricing logic (similar to action_executor)
            if resource.service == 'ec2':
                return self._estimate_ec2_savings(resource, region)
            elif resource.service == 'rds':
                return self._estimate_rds_savings(resource, region)
            elif resource.service == 'lambda':
                return self._estimate_lambda_savings(resource, region)
            elif resource.service == 'dynamodb':
                return self._estimate_dynamodb_savings(resource, region)
            elif resource.service == 'ebs':
                return self._estimate_ebs_savings(resource, region)
            elif resource.service == 'nat_gateway':
                return self._estimate_nat_gateway_savings(resource, region)
            else:
                # Fallback for unknown services
                logger.debug(f"Unknown service for savings estimation: {resource.service}")
                return self._estimate_default_savings(resource)
                
        except Exception as e:
            logger.warning(f"Error estimating savings for {resource.resource_id}: {e}")
            # Fallback to default
            return self._estimate_default_savings(resource)
    
    def _estimate_ec2_savings(self, resource, region: str) -> float:
        """Estimate EC2 instance savings."""
        try:
            import boto3
            
            # Get EC2 client from resource_manager or create new
            ec2 = None
            if self.resource_manager and hasattr(self.resource_manager, 'clients'):
                ec2 = self.resource_manager.clients.get('ec2')
            
            if not ec2:
                ec2 = boto3.client('ec2', region_name=region)
            
            # Get instance type
            response = ec2.describe_instances(InstanceIds=[resource.resource_id])
            if not response.get('Reservations'):
                return self._estimate_default_savings(resource)
            
            instance = response['Reservations'][0]['Instances'][0]
            instance_type = instance.get('InstanceType', 't3.micro')
            
            # Get pricing for instance type
            pricing_data = self.pricing_manager.get_pricing_data('ec2', region)
            hourly_price = pricing_data.prices.get(instance_type)
            
            if hourly_price:
                monthly_savings = float(hourly_price) * 24 * 30
                logger.debug(f"EC2 savings estimate: ${monthly_savings:.2f}/month for {instance_type}")
                return monthly_savings
            else:
                logger.debug(f"Pricing not found for instance type: {instance_type}")
                return self._estimate_default_savings(resource)
                
        except Exception as e:
            logger.debug(f"Error estimating EC2 savings: {e}")
            return self._estimate_default_savings(resource)
    
    def _estimate_rds_savings(self, resource, region: str) -> float:
        """Estimate RDS instance savings."""
        try:
            import boto3
            
            rds = None
            if self.resource_manager and hasattr(self.resource_manager, 'clients'):
                rds = self.resource_manager.clients.get('rds')
            
            if not rds:
                rds = boto3.client('rds', region_name=region)
            
            # Get DB instance class
            response = rds.describe_db_instances(DBInstanceIdentifier=resource.resource_id)
            if not response.get('DBInstances'):
                return self._estimate_default_savings(resource)
            
            db_instance = response['DBInstances'][0]
            instance_class = db_instance.get('DBInstanceClass', 'db.t3.micro')
            
            # Get pricing for instance class
            pricing_data = self.pricing_manager.get_pricing_data('rds', region)
            hourly_price = pricing_data.prices.get(instance_class)
            
            if hourly_price:
                monthly_savings = float(hourly_price) * 24 * 30
                logger.debug(f"RDS savings estimate: ${monthly_savings:.2f}/month for {instance_class}")
                return monthly_savings
            else:
                logger.debug(f"Pricing not found for DB instance class: {instance_class}")
                return self._estimate_default_savings(resource)
                
        except Exception as e:
            logger.debug(f"Error estimating RDS savings: {e}")
            return self._estimate_default_savings(resource)
    
    def _estimate_lambda_savings(self, resource, region: str) -> float:
        """Estimate Lambda savings (complex - uses average pricing)."""
        # Lambda pricing is per-request and per-GB-second
        # Use default for now, could be enhanced with CloudWatch metrics
        return self._estimate_default_savings(resource)
    
    def _estimate_dynamodb_savings(self, resource, region: str) -> float:
        """Estimate DynamoDB savings (switching to on-demand)."""
        # DynamoDB on-demand vs provisioned savings
        # Use default for now, could be enhanced with table metadata
        return self._estimate_default_savings(resource)
    
    def _estimate_ebs_savings(self, resource, region: str) -> float:
        """Estimate EBS volume savings."""
        # EBS pricing depends on volume type and size
        # Use default for now, could be enhanced with volume metadata
        return self._estimate_default_savings(resource)
    
    def _estimate_nat_gateway_savings(self, resource, region: str) -> float:
        """Estimate NAT Gateway savings (fixed hourly pricing)."""
        # NAT Gateway: $0.045/hour
        hourly_price = 0.045
        monthly_savings = hourly_price * 24 * 30  # ~$32.40/month
        logger.debug(f"NAT Gateway savings estimate: ${monthly_savings:.2f}/month")
        return monthly_savings
    
    def _estimate_default_savings(self, resource) -> float:
        """Default savings estimation fallback."""
        # Conservative default: $0.10/hour = $72/month
        default_hourly = 0.10
        monthly_savings = default_hourly * 24 * 30
        logger.debug(f"Using default savings estimate for {resource.service}: ${monthly_savings:.2f}/month")
        return monthly_savings