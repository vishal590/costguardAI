"""
Budget Monitor for tracking AWS Budgets and detecting threshold breaches.

This module monitors AWS Budgets continuously and detects when spending
approaches warning (80%) or action (90%) thresholds.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, UTC
import logging

logger = logging.getLogger(__name__)


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
            # Get all budgets for the account
            response = self.budgets_client.describe_budgets(
                AccountId=self._get_account_id()
            )
            
            for budget in response.get('Budgets', []):
                budget_status = self._create_budget_status(budget)
                threshold_event = self.check_thresholds(budget_status)
                
                if threshold_event:
                    threshold_events.append(threshold_event)
                    
        except Exception as e:
            logger.error(f"Failed to poll budgets: {e}")
            # Fall back to cost estimates
            budget_status = self._get_fallback_budget_status()
            threshold_event = self.check_thresholds(budget_status)
            if threshold_event:
                threshold_events.append(threshold_event)
        
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
            spend = 0.0
        
        return spend / limit if limit > 0 else 0.0
    
    def _create_budget_status(self, budget: Dict[str, Any]):
        """Create BudgetStatus from AWS budget dict."""
        from ..utils.types import BudgetStatus
        
        limit = float(budget['BudgetLimit']['Amount'])
        currency = budget['BudgetLimit']['Unit']
        
        calculated_spend = budget.get('CalculatedSpend', {})
        actual_spend = float(calculated_spend.get('ActualSpend', {}).get('Amount', 0))
        forecasted_spend = float(calculated_spend.get('ForecastedSpend', {}).get('Amount', 0))
        
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
        """Get budget status using cost estimator as fallback."""
        from ..utils.types import BudgetStatus
        
        logger.info("Using cost estimator as fallback for budget status")
        
        # This would use the cost estimator to get current spend
        # For now, return a placeholder
        return BudgetStatus(
            budget_name="fallback-budget",
            limit=1000.0,
            actual_spend=0.0,
            forecasted_spend=0.0,
            utilization_percent=0.0,
            currency="USD",
            time_period="current"
        )
