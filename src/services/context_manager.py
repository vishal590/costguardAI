"""
Context Manager for retrieving cost data context.

This module retrieves relevant cost data for queries:
1. Historical cost data from Cost Explorer
2. Forecast data from Phase 2
3. Prevention actions from Phase 3
4. Budget status
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

from ..utils.types import QueryIntent, CostContext, BudgetStatus

logger = logging.getLogger(__name__)


class ContextManager:
    """Retrieve relevant cost data for queries."""
    
    def __init__(
        self,
        cost_explorer_client=None,
        dynamodb_client=None,
        budgets_client=None,
        sts_client=None
    ):
        """
        Initialize context manager.
        
        Args:
            cost_explorer_client: AWS Cost Explorer client
            dynamodb_client: DynamoDB client for Phase 2/3 data
            budgets_client: AWS Budgets client
            sts_client: AWS STS client (optional, defaults to boto3.client('sts'))
        """
        self.cost_explorer_client = cost_explorer_client
        self.dynamodb_client = dynamodb_client
        self.budgets_client = budgets_client
        self.sts_client = sts_client
        
        logger.info("ContextManager initialized")
    
    def get_cost_context(self, intent: QueryIntent) -> CostContext:
        """
        Retrieve relevant cost data based on query intent.
        
        Args:
            intent: Parsed query intent
            
        Returns:
            CostContext with relevant data
        """
        logger.info(f"Retrieving context for intent: {intent.intent_type}")
        
        # Retrieve historical costs
        historical_costs = self.get_historical_costs(
            services=intent.services,
            start_date=intent.time_range[0],
            end_date=intent.time_range[1]
        )
        
        # Retrieve forecast data if relevant
        forecast_data = None
        if intent.intent_type in ['forecast', 'trend_analysis']:
            forecast_data = self.get_forecast_data(
                services=intent.services,
                days=30
            )
        
        # Retrieve prevention actions if relevant
        prevention_actions = []
        if intent.intent_type in ['prevention', 'optimization']:
            prevention_actions = self.get_prevention_actions(
                start_date=intent.time_range[0],
                end_date=intent.time_range[1]
            )
        
        # Retrieve budget status
        current_budget = self._get_budget_status()
        
        # Detect anomalies in cost data
        anomalies = self._detect_anomalies(historical_costs)
        
        return CostContext(
            historical_costs=historical_costs,
            forecast_data=forecast_data,
            prevention_actions=prevention_actions,
            current_budget=current_budget,
            anomalies=anomalies
        )
    
    def get_historical_costs(
        self,
        services: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch historical cost data from Cost Explorer.
        
        Args:
            services: List of AWS service identifiers
            start_date: Start date for cost data
            end_date: End date for cost data
            
        Returns:
            Dictionary mapping service to list of cost data points
        """
        if not self.cost_explorer_client:
            logger.warning("No Cost Explorer client, returning empty data")
            return {}
        
        try:
            costs_by_service = {}
            
            # Format dates for Cost Explorer API
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            
            # Query Cost Explorer
            response = self.cost_explorer_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_str,
                    'End': end_str
                },
                Granularity='DAILY',
                Metrics=['BlendedCost', 'UnblendedCost'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'}
                ]
            )
            
            # Process results
            for result in response.get('ResultsByTime', []):
                date = result['TimePeriod']['Start']
                
                for group in result.get('Groups', []):
                    service = group['Keys'][0]
                    
                    # Filter by requested services if specified
                    if services and service.lower() not in services:
                        continue
                    
                    cost_data = {
                        'date': date,
                        'blended_cost': float(group['Metrics']['BlendedCost']['Amount']),
                        'unblended_cost': float(group['Metrics']['UnblendedCost']['Amount']),
                        'currency': group['Metrics']['BlendedCost']['Unit']
                    }
                    
                    if service not in costs_by_service:
                        costs_by_service[service] = []
                    
                    costs_by_service[service].append(cost_data)
            
            logger.debug(f"Retrieved historical costs for {len(costs_by_service)} services")
            return costs_by_service
            
        except Exception as e:
            logger.error(f"Error retrieving historical costs: {e}")
            return {}
    
    def get_forecast_data(
        self,
        services: List[str],
        days: int = 30
    ) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """
        Fetch forecast data from Phase 2 DynamoDB table.
        
        Args:
            services: List of AWS service identifiers
            days: Number of days to forecast
            
        Returns:
            Dictionary mapping service to list of forecast points
        """
        if not self.dynamodb_client:
            logger.warning("No DynamoDB client, cannot fetch forecasts")
            return None
        
        try:
            table_name = "cost-forecasts"
            forecasts_by_service = {}
            
            # Query forecasts for each service
            for service in services:
                response = self.dynamodb_client.query(
                    TableName=table_name,
                    KeyConditionExpression="service = :svc",
                    ExpressionAttributeValues={
                        ":svc": {"S": service}
                    },
                    Limit=days
                )
                
                forecast_points = []
                for item in response.get('Items', []):
                    forecast_points.append({
                        'date': item.get('date', {}).get('S', ''),
                        'predicted_cost': float(item.get('predicted_cost', {}).get('N', 0)),
                        'confidence_lower': float(item.get('confidence_lower', {}).get('N', 0)),
                        'confidence_upper': float(item.get('confidence_upper', {}).get('N', 0))
                    })
                
                if forecast_points:
                    forecasts_by_service[service] = forecast_points
            
            logger.debug(f"Retrieved forecasts for {len(forecasts_by_service)} services")
            return forecasts_by_service if forecasts_by_service else None
            
        except Exception as e:
            logger.error(f"Error retrieving forecast data: {e}")
            return None
    
    def get_prevention_actions(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Fetch prevention actions from Phase 3 DynamoDB table.
        
        Args:
            start_date: Start date for action history
            end_date: End date for action history
            
        Returns:
            List of prevention actions
        """
        if not self.dynamodb_client:
            logger.warning("No DynamoDB client, cannot fetch prevention actions")
            return []
        
        try:
            table_name = "prevention-actions"
            
            # Query actions within date range
            response = self.dynamodb_client.scan(
                TableName=table_name,
                FilterExpression="timestamp BETWEEN :start AND :end",
                ExpressionAttributeValues={
                    ":start": {"S": start_date.isoformat()},
                    ":end": {"S": end_date.isoformat()}
                }
            )
            
            actions = []
            for item in response.get('Items', []):
                actions.append({
                    'resource_id': item.get('resource_id', {}).get('S', ''),
                    'action': item.get('action', {}).get('S', ''),
                    'timestamp': item.get('timestamp', {}).get('S', ''),
                    'estimated_savings': float(item.get('estimated_savings', {}).get('N', 0)),
                    'success': item.get('success', {}).get('BOOL', False)
                })
            
            logger.debug(f"Retrieved {len(actions)} prevention actions")
            return actions
            
        except Exception as e:
            logger.error(f"Error retrieving prevention actions: {e}")
            return []
    
    def _detect_anomalies(self, historical_costs: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Detect anomalies in historical cost data.
        
        Uses statistical analysis to identify unusual cost spikes or drops.
        
        Args:
            historical_costs: Dictionary of service names to cost data lists
            
        Returns:
            List of anomaly dictionaries with service, date, and description
        """
        anomalies = []
        
        try:
            import statistics
            
            for service, cost_data in historical_costs.items():
                if not cost_data or len(cost_data) < 3:
                    # Need at least 3 data points for anomaly detection
                    continue
                
                # Extract cost values
                costs = []
                for item in cost_data:
                    if isinstance(item, dict):
                        cost = item.get('cost') or item.get('amount') or item.get('unblended_cost', 0)
                        if isinstance(cost, (int, float)):
                            costs.append(float(cost))
                
                if len(costs) < 3:
                    continue
                
                # Calculate mean and standard deviation
                mean_cost = statistics.mean(costs)
                if len(costs) > 1:
                    stdev_cost = statistics.stdev(costs)
                else:
                    stdev_cost = 0
                
                # Define anomaly threshold (2 standard deviations)
                threshold = 2 * stdev_cost if stdev_cost > 0 else mean_cost * 0.5
                
                # Check each data point for anomalies
                for i, item in enumerate(cost_data):
                    if isinstance(item, dict):
                        cost = item.get('cost') or item.get('amount') or item.get('unblended_cost', 0)
                        if isinstance(cost, (int, float)):
                            cost_value = float(cost)
                            
                            # Detect spike (cost significantly higher than mean)
                            if cost_value > mean_cost + threshold:
                                anomalies.append({
                                    'service': service,
                                    'date': item.get('date') or item.get('time_period', {}).get('start', 'unknown'),
                                    'cost': cost_value,
                                    'expected_range': f"${mean_cost - threshold:.2f} - ${mean_cost + threshold:.2f}",
                                    'type': 'spike',
                                    'severity': 'high' if cost_value > mean_cost + (3 * stdev_cost) else 'medium',
                                    'description': f"Cost spike detected: ${cost_value:.2f} (expected: ${mean_cost:.2f} ± ${threshold:.2f})"
                                })
                            
                            # Detect drop (cost significantly lower than mean) - less critical
                            elif cost_value < mean_cost - threshold and mean_cost > 0:
                                anomalies.append({
                                    'service': service,
                                    'date': item.get('date') or item.get('time_period', {}).get('start', 'unknown'),
                                    'cost': cost_value,
                                    'expected_range': f"${mean_cost - threshold:.2f} - ${mean_cost + threshold:.2f}",
                                    'type': 'drop',
                                    'severity': 'low',
                                    'description': f"Cost drop detected: ${cost_value:.2f} (expected: ${mean_cost:.2f} ± ${threshold:.2f})"
                                })
            
            if anomalies:
                logger.info(f"Detected {len(anomalies)} cost anomalies")
            
        except Exception as e:
            logger.warning(f"Error detecting anomalies: {e}")
            # Return empty list on error rather than failing
        
        return anomalies
    
    def _get_account_id(self) -> Optional[str]:
        """
        Get AWS account ID from STS.
        
        Returns:
            Account ID string or None if unavailable
        """
        try:
            if not self.sts_client:
                import boto3
                sts = boto3.client('sts')
            else:
                sts = self.sts_client
            
            identity = sts.get_caller_identity()
            return identity.get('Account')
        except Exception as e:
            logger.error(f"Error retrieving account ID: {e}")
            return None
    
    def _get_budget_status(self) -> Optional[BudgetStatus]:
        """
        Retrieve current budget status.
        
        Returns:
            BudgetStatus or None if unavailable
        """
        if not self.budgets_client:
            return None
        
        try:
            # Get account ID from STS
            account_id = self._get_account_id()
            if not account_id:
                logger.warning("Unable to retrieve account ID, cannot fetch budget status")
                return None
            
            # Get first budget (simplified)
            response = self.budgets_client.describe_budgets(
                AccountId=account_id,
                MaxResults=1
            )
            
            if not response.get('Budgets'):
                return None
            
            budget = response['Budgets'][0]
            
            return BudgetStatus(
                budget_name=budget['BudgetName'],
                limit=float(budget['BudgetLimit']['Amount']),
                actual_spend=float(budget.get('CalculatedSpend', {}).get('ActualSpend', {}).get('Amount', 0)),
                forecasted_spend=float(budget.get('CalculatedSpend', {}).get('ForecastedSpend', {}).get('Amount', 0)),
                utilization_percent=0.0,  # Calculate from actual/limit
                currency=budget['BudgetLimit']['Unit'],
                time_period=budget['TimePeriod']['Start']
            )
            
        except Exception as e:
            logger.error(f"Error retrieving budget status: {e}")
            return None
