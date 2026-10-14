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
    
    def _daily_totals(self, start, end):
        """Read explicit USD daily totals with paging and provider provenance."""
        import math
        request = {'TimePeriod': {'Start': start, 'End': end}, 'Granularity': 'DAILY', 'Metrics': ['BlendedCost']}
        totals, seen = {}, set()
        while True:
            response = self.cost_explorer_client.get_cost_and_usage(**request)
            for result in response.get('ResultsByTime', []):
                stamp = result['TimePeriod']['Start']
                metric = result['Total']['BlendedCost']
                value = float(metric['Amount'])
                if metric.get('Unit') != 'USD' or not math.isfinite(value): raise ValueError('Daily USD observations unavailable')
                point = {'cost': value, 'is_estimated': result.get('Estimated') if type(result.get('Estimated')) is bool else None}
                if stamp in totals and totals[stamp] != point: raise ValueError('Conflicting daily totals')
                totals[stamp] = point
            token = response.get('NextPageToken')
            if not token: return totals
            if token in seen: raise ValueError('Repeated daily total page token')
            seen.add(token)
            request['NextPageToken'] = token

    def generate_daily_summary(self, user_id: str) -> Optional[Insight]:
        if not self.cost_explorer_client: return None
        try:
            today = datetime.now(UTC).date()
            first = today-timedelta(days=8)
            expected = [(first+timedelta(days=index)).isoformat() for index in range(8)]
            totals = self._daily_totals(first.isoformat(), today.isoformat())
            if set(totals) != set(expected): return None
            yesterday = totals[expected[-1]]['cost']
            baseline = sum(totals[stamp]['cost'] for stamp in expected[:-1])/7
            change = (yesterday-baseline)/baseline*100 if baseline > 0 else None
            if change is None:
                comparison = f'The prior seven observed dates average {baseline:.2f} USD; a percentage comparison is unavailable for a nonpositive baseline.'
            else:
                comparison = f'The prior seven observed dates average {baseline:.2f} USD; the change is {change:+.1f}%.'
            estimated = [stamp for stamp in expected if totals[stamp]['is_estimated'] is True]
            unknown = [stamp for stamp in expected if totals[stamp]['is_estimated'] is None]
            return Insight(insight_type='summary', title='Observed Daily Cost Summary',
                description=f'Observed cost for {expected[-1]}: {yesterday:.2f} USD. {comparison} Provider estimates can change.',
                severity='warning' if change is not None and change > 20 else 'info', action_required=False,
                related_services=[], estimated_impact=None, method='observed_7_day_comparison',
                data_quality={'cost_metric': 'BlendedCost', 'baseline_dates': expected[:-1], 'estimated_dates': estimated, 'unknown_estimate_dates': unknown})
        except Exception as error:
            logger.warning('Daily comparison unavailable: %s', type(error).__name__)
            return None

    def detect_anomalies(self, user_id: str) -> List[Insight]:
        """Flag observed increases using eight dated points; no probability claim."""
        if not self.cost_explorer_client: return []
        try:
            from .cost_explorer import CostExplorerParams, fetch_cost_data
            today = datetime.now(UTC).date()
            first = today-timedelta(days=8)
            dates = [(first+timedelta(days=index)).isoformat() for index in range(8)]
            records = fetch_cost_data(CostExplorerParams(first.isoformat(), today.isoformat(), 'DAILY'), self.cost_explorer_client)
            grouped = {}
            for record in records:
                if record.currency != 'USD': raise ValueError('USD observations required')
                grouped.setdefault(record.service, {})[record.date] = record
            insights = []
            for service, observations in grouped.items():
                if set(observations) != set(dates): continue
                baseline = sum(observations[stamp].blended_cost for stamp in dates[:-1])/7
                current = observations[dates[-1]].blended_cost
                if baseline <= 0: continue
                percent = (current-baseline)/baseline*100
                if percent <= 50: continue
                insights.append(Insight(insight_type='anomaly', title=f'Observed Cost Increase: {service}',
                    description=f'{service} cost for {dates[-1]} is {current:.2f} USD versus {baseline:.2f} USD across the seven preceding observed dates ({percent:.1f}% increase). This is a comparison heuristic, not a calibrated anomaly probability.',
                    severity='warning', action_required=True, related_services=[service], estimated_impact=current-baseline,
                    method='observed_7_day_comparison', data_quality={'cost_metric': 'BlendedCost', 'baseline_dates': dates[:-1],
                        'estimated_dates': [stamp for stamp in dates if observations[stamp].is_estimated is True],
                        'unknown_estimate_dates': [stamp for stamp in dates if observations[stamp].is_estimated is None]}))
            return insights
        except Exception as error:
            logger.warning('Observed increase insights unavailable: %s', type(error).__name__)
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
                    metadata = None  # Use the dedicated observed-window adapter.
                    idle_status = self.idle_detector.is_resource_idle(resource, metadata)
                    
                    if idle_status.is_idle and idle_status.observation_status == 'rule_matched':
                        service = resource.service
                        if service not in idle_resources_by_service:
                            idle_resources_by_service[service] = []
                        
                        # Estimate monthly savings using real pricing
                        estimated_monthly_savings = self._estimate_resource_savings(resource)
                        if estimated_monthly_savings is not None: total_estimated_savings += estimated_monthly_savings
                        
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
                values = [resource['estimated_savings'] for resource in idle_resources]
                service_savings = sum(values) if all(value is not None for value in values) else None
                opportunity = f'Potential compute-only cost at 730 hours: ${service_savings:.2f}/month; savings are not verified.' if service_savings is not None else 'Monetary savings are unavailable; review rates and retained charges.'
                avg_duration = sum(r['idle_duration_days'] for r in idle_resources) / count if count > 0 else 0.0
                
                resource_list = ", ".join([r['resource_id'] for r in idle_resources[:5]])  # Show first 5
                if count > 5:
                    resource_list += f" and {count - 5} more"
                
                suggestions.append(Insight(
                    insight_type="optimization",
                    title=f"Low-Usage {service.upper()} Resources Observed",
                    description=f"{count} {service} resources matched low-usage rules over {avg_duration*24:.1f} observed hours on average; workload inactivity is not verified. "
                               f"Resources: {resource_list}. {opportunity}",
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
        """Use AWS Budgets' own matching-period projection, not a rolling-model sum."""
        if not self.budgets_client: return []
        try:
            from .budget_monitor import BudgetMonitor
            monitor = BudgetMonitor(self.budgets_client, None)
            request = {'AccountId': monitor._get_account_id()}
            alerts, seen = [], set()
            while True:
                response = self.budgets_client.describe_budgets(**request)
                for budget in response.get('Budgets', []):
                    if budget.get('BudgetType') != 'COST' or budget.get('BudgetLimit', {}).get('Unit') != 'USD': continue
                    status = monitor._create_budget_status(budget)
                    if status.forecasted_spend is None or status.forecasted_spend <= status.limit: continue
                    overage = status.forecasted_spend-status.limit
                    reset_unit = budget.get('TimeUnit') or 'reported'
                    alerts.append(Insight(insight_type='forecast_alert',
                        title=f'Provider Budget Projection: {status.budget_name}',
                        description=f'AWS Budgets projects {status.forecasted_spend:.2f} USD against a {status.limit:.2f} USD limit for its {reset_unit} reset period. Projected overage: {overage:.2f} USD. This provider projection can change.',
                        severity='critical' if overage/status.limit > 0.2 else 'warning',
                        action_required=True, related_services=[], estimated_impact=overage))
                token = response.get('NextToken')
                if not token: return alerts
                if token in seen: raise ValueError('Repeated budget page token')
                seen.add(token)
                request['NextToken'] = token
        except Exception as error:
            logger.warning('Budget projection insights unavailable: %s', type(error).__name__)
            return []

    def _estimate_resource_savings(self, resource) -> Optional[float]:
        """Estimate supported compute opportunity without fabricated default savings."""
        if resource.service != 'ec2': return None
        try:
            if not self.pricing_manager:
                from .pricing_manager import PricingManager
                self.pricing_manager = PricingManager(region=resource.region)
            return self._estimate_ec2_savings(resource, resource.region)
        except Exception as error:
            logger.debug('Resource opportunity unavailable: %s', type(error).__name__)
            return None

    def _estimate_ec2_savings(self, resource, region: str) -> float:
        """Estimate EC2 instance savings."""
        try:
            import boto3
            
            # Get EC2 client from resource_manager or create new
            ec2 = None
            if self.resource_manager and hasattr(self.resource_manager, 'clients'):
                ec2 = self.resource_manager.clients.get('ec2')
            
            if ec2 is not None and getattr(getattr(ec2, 'meta', None), 'region_name', None) != region: return None
            if not ec2:
                ec2 = boto3.client('ec2', region_name=region)
            
            # Get instance type
            response = ec2.describe_instances(InstanceIds=[resource.resource_id])
            if not response.get('Reservations'):
                return self._estimate_default_savings(resource)
            
            instance = response['Reservations'][0]['Instances'][0]
            if instance.get('PlatformDetails') != 'Linux/UNIX' or instance.get('Placement', {}).get('Tenancy') != 'default' or instance.get('InstanceLifecycle'):
                return None
            instance_type = instance.get('InstanceType')
            
            # Get pricing for instance type
            pricing_data = self.pricing_manager.get_pricing_data('ec2', region)
            if pricing_data.source != 'aws_pricing' or pricing_data.currency != 'USD': return None
            hourly_price = pricing_data.prices.get(instance_type)
            
            if hourly_price is not None and hourly_price.is_finite() and hourly_price >= 0:
                monthly_savings = float(hourly_price) * 730
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
    
    def _estimate_default_savings(self, resource) -> Optional[float]:
        """Missing observed pricing cannot establish a monetary opportunity."""
        return None
