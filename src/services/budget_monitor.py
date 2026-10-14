"""
Budget Monitor for tracking AWS Budgets and detecting threshold breaches.

This module monitors AWS Budgets continuously and detects when spending
approaches warning (80%) or action (90%) thresholds.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, UTC
import logging
import math

logger = logging.getLogger(__name__)


class BudgetDataUnavailable(RuntimeError):
    """Budget coverage cannot be established from current data."""


class BudgetMonitor:
    """Monitor AWS Budgets and detect threshold breaches."""
    
    def __init__(self, budgets_client, cost_estimator):
        """
        Initialize budget monitor.
        
        Args:
            budgets_client: boto3 Budgets client
            cost_estimator: CostEstimator instance for fallback
        """
        self.budgets_client = budgets_client
        self.cost_estimator = cost_estimator
        self.warning_threshold = 0.80  # 80%
        self.action_threshold = 0.90   # 90%
        
    def poll_budgets(self) -> List[Any]:
        """
        Poll all budgets and return threshold events.
        
        Returns:
            List of ThresholdEvent objects
        """
        logger.info("Polling AWS Budgets")
        threshold_events = []
        
        try:
            request = {'AccountId': self._get_account_id()}
            seen = set()
            while True:
                response = self.budgets_client.describe_budgets(**request)
                for budget in response.get('Budgets', []):
                    if not budget.get('BudgetType'): raise BudgetDataUnavailable('Budget type is unavailable')
                    if budget['BudgetType'] != 'COST': continue
                    threshold_event = self.check_thresholds(self._create_budget_status(budget))
                    if threshold_event: threshold_events.append(threshold_event)
                token = response.get('NextToken')
                if not token: break
                if token in seen: raise BudgetDataUnavailable('Repeated budget page token')
                seen.add(token)
                request['NextToken'] = token
        except Exception as e:
            logger.error('Budget monitoring unavailable: %s', type(e).__name__)
            # A partial poll cannot justify a successful prevention cycle.
            raise BudgetDataUnavailable('Budget data is unavailable; no fallback limit or zero spending was invented') from e

        return threshold_events
    
    def check_thresholds(self, budget_status) -> Optional[Any]:
        """
        Check if budget has crossed warning or action thresholds.
        
        Args:
            budget_status: BudgetStatus object
            
        Returns:
            ThresholdEvent if threshold crossed, None otherwise
        """
        # Convert utilization_percent (0-100) to decimal (0.0-1.0) for comparison
        utilization = budget_status.utilization_percent / 100.0
        
        if utilization >= self.action_threshold:
            logger.warning(f"Budget {budget_status.budget_name} at {budget_status.utilization_percent:.1f}% - ACTION threshold")
            return self._create_threshold_event(budget_status, "action")
        elif utilization >= self.warning_threshold:
            logger.info(f"Budget {budget_status.budget_name} at {budget_status.utilization_percent:.1f}% - WARNING threshold")
            return self._create_threshold_event(budget_status, "warning")
        
        return None
    
    def calculate_utilization(self, budget: Dict[str, Any]) -> float:
        """
        Calculate current budget utilization percentage.
        
        Args:
            budget: Budget dict from AWS API
            
        Returns:
            Utilization percentage (0.0 to 1.0+)
        """
        limit = float(budget['BudgetLimit']['Amount'])
        
        # Use forecasted spend if available, otherwise actual spend
        calculated_spend = budget.get('CalculatedSpend', {})
        forecasted = calculated_spend.get('ForecastedSpend')
        actual = calculated_spend.get('ActualSpend')
        
        if forecasted:
            spend = float(forecasted['Amount'])
        elif actual:
            spend = float(actual['Amount'])
        else:
            raise BudgetDataUnavailable('Calculated spending is unavailable')
        
        if not math.isfinite(limit) or limit <= 0 or not math.isfinite(spend):
            raise BudgetDataUnavailable('Budget limit or spending is invalid')
        return spend / limit
    
    def _create_budget_status(self, budget: Dict[str, Any]):
        """Create BudgetStatus from AWS budget dict."""
        from ..utils.types import BudgetStatus
        
        limit = float(budget['BudgetLimit']['Amount'])
        currency = budget['BudgetLimit']['Unit']
        
        calculated_spend = budget.get('CalculatedSpend', {})
        if 'ActualSpend' not in calculated_spend:
            raise BudgetDataUnavailable('Actual spending is unavailable')
        actual_spend = float(calculated_spend['ActualSpend']['Amount'])
        forecasted = calculated_spend.get('ForecastedSpend')
        forecasted_spend = float(forecasted['Amount']) if forecasted else None
        if calculated_spend['ActualSpend'].get('Unit') != currency or (forecasted and forecasted.get('Unit') != currency):
            raise BudgetDataUnavailable('Budget and spending units differ')
        
        if not math.isfinite(actual_spend) or (forecasted_spend is not None and not math.isfinite(forecasted_spend)):
            raise BudgetDataUnavailable("Calculated spending is invalid")
        utilization = self.calculate_utilization(budget)
        
        time_period = budget.get('TimePeriod', {})
        period_str = f"{time_period.get('Start', '')} to {time_period.get('End', '')}"
        
        return BudgetStatus(
            budget_name=budget['BudgetName'],
            limit=limit,
            actual_spend=actual_spend,
            forecasted_spend=forecasted_spend,
            utilization_percent=utilization * 100,
            currency=currency,
            time_period=period_str
        )
    
    def _create_threshold_event(self, budget_status, threshold_type: str):
        """Create ThresholdEvent from budget status."""
        from ..utils.types import ThresholdEvent
        
        return ThresholdEvent(
            budget_name=budget_status.budget_name,
            threshold_type=threshold_type,
            utilization_percent=budget_status.utilization_percent,
            timestamp=datetime.now(UTC).isoformat(),
            budget_status=budget_status
        )
    
    def _get_account_id(self) -> str:
        """Get AWS account ID from STS."""
        import boto3
        sts = boto3.client('sts')
        return sts.get_caller_identity()['Account']
    
    def _get_fallback_budget_status(self):
        """An estimator alone cannot establish a configured budget limit or MTD spend."""
        raise BudgetDataUnavailable("No verified fallback budget data is configured")
