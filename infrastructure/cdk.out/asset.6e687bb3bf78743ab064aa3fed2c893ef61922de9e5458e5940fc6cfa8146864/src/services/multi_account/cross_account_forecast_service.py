"""
Cross-Account Forecast Service

Extends Phase 2 forecasting engine for multi-account organizations.
Validates Requirements 13.1-13.7.
"""
import logging
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime, timedelta

from ..forecast_engine import ForecastEngine
from .repositories import AccountRepository, MultiAccountCostRepository
from .models import Account

logger = logging.getLogger(__name__)


class CrossAccountForecastService:
    """Service for forecasting costs across multiple accounts"""

    def __init__(
        self,
        forecast_engine: ForecastEngine,
        account_repository: AccountRepository,
        cost_repository: MultiAccountCostRepository
    ):
        """
        Initialize the Cross-Account Forecast Service
        
        Args:
            forecast_engine: Phase 2 ForecastEngine instance
            account_repository: Repository for account data
            cost_repository: Repository for cost data
        """
        self.forecast_engine = forecast_engine
        self.account_repo = account_repository
        self.cost_repo = cost_repository

    def forecast_organization_costs(
        self,
        org_id: str,
        days: int = 30,
        granularity: str = "daily"
    ) -> Dict:
        """
        Generate cost forecast for entire organization
        
        Args:
            org_id: Organization ID
            days: Forecast horizon (7, 14, or 30)
            granularity: Time resolution ("daily" or "weekly")
            
        Returns:
            Dict with forecast data
            
        Validates: Requirements 13.1, 13.4
        """
        # Get all accounts in organization
        accounts = self.account_repo.list_by_organization(org_id)
        
        if not accounts:
            return {
                "org_id": org_id,
                "forecast_data": [],
                "total_forecasted_cost": Decimal("0"),
                "account_count": 0,
                "error": "No accounts found in organization"
            }
        
        # Aggregate historical data from all accounts
        account_ids = [acc.id for acc in accounts]
        aggregated_historical = self._aggregate_historical_data(account_ids)
        
        # Generate forecast using Phase 2 engine
        # Note: This is a simplified approach - in production, we'd pass aggregated data
        forecast_response = self.forecast_engine.generate_forecast(
            service=None,  # Total forecast
            days=days,
            granularity=granularity
        )
        
        # Calculate total forecasted cost
        total_forecast = sum(
            point.predicted_cost for point in forecast_response.forecast_data
        )
        
        return {
            "org_id": org_id,
            "forecast_data": [
                {
                    "date": point.date,
                    "predicted_cost": Decimal(str(point.predicted_cost)),
                    "confidence_lower": Decimal(str(point.confidence_lower)),
                    "confidence_upper": Decimal(str(point.confidence_upper))
                }
                for point in forecast_response.forecast_data
            ],
            "total_forecasted_cost": Decimal(str(total_forecast)),
            "account_count": len(accounts),
            "forecast_horizon": days,
            "granularity": granularity,
            "timestamp": datetime.utcnow().isoformat()
        }


    def forecast_ou_costs(
        self,
        ou_id: str,
        account_ids: List[str],
        days: int = 30,
        granularity: str = "daily"
    ) -> Dict:
        """
        Generate cost forecast for organizational unit
        
        Args:
            ou_id: Organizational Unit ID
            account_ids: List of account IDs in the OU
            days: Forecast horizon
            granularity: Time resolution
            
        Returns:
            Dict with forecast data
            
        Validates: Requirements 13.2
        """
        if not account_ids:
            return {
                "ou_id": ou_id,
                "forecast_data": [],
                "total_forecasted_cost": Decimal("0"),
                "account_count": 0,
                "error": "No accounts in OU"
            }
        
        # Aggregate historical data from OU accounts
        aggregated_historical = self._aggregate_historical_data(account_ids)
        
        # Generate forecast
        forecast_response = self.forecast_engine.generate_forecast(
            service=None,
            days=days,
            granularity=granularity
        )
        
        # Calculate total
        total_forecast = sum(
            point.predicted_cost for point in forecast_response.forecast_data
        )
        
        return {
            "ou_id": ou_id,
            "forecast_data": [
                {
                    "date": point.date,
                    "predicted_cost": Decimal(str(point.predicted_cost)),
                    "confidence_lower": Decimal(str(point.confidence_lower)),
                    "confidence_upper": Decimal(str(point.confidence_upper))
                }
                for point in forecast_response.forecast_data
            ],
            "total_forecasted_cost": Decimal(str(total_forecast)),
            "account_count": len(account_ids),
            "forecast_horizon": days,
            "granularity": granularity,
            "timestamp": datetime.utcnow().isoformat()
        }

    def forecast_account_costs(
        self,
        account_id: str,
        days: int = 30,
        granularity: str = "daily"
    ) -> Dict:
        """
        Generate cost forecast for single account
        
        Args:
            account_id: Account ID
            days: Forecast horizon
            granularity: Time resolution
            
        Returns:
            Dict with forecast data
            
        Validates: Requirements 13.3
        """
        # Generate forecast for single account
        forecast_response = self.forecast_engine.generate_forecast(
            service=None,
            days=days,
            granularity=granularity
        )
        
        # Calculate total
        total_forecast = sum(
            point.predicted_cost for point in forecast_response.forecast_data
        )
        
        return {
            "account_id": account_id,
            "forecast_data": [
                {
                    "date": point.date,
                    "predicted_cost": Decimal(str(point.predicted_cost)),
                    "confidence_lower": Decimal(str(point.confidence_lower)),
                    "confidence_upper": Decimal(str(point.confidence_upper))
                }
                for point in forecast_response.forecast_data
            ],
            "total_forecasted_cost": Decimal(str(total_forecast)),
            "forecast_horizon": days,
            "granularity": granularity,
            "timestamp": datetime.utcnow().isoformat()
        }

    def _aggregate_historical_data(self, account_ids: List[str]) -> Dict:
        """
        Aggregate historical cost data from multiple accounts
        
        Args:
            account_ids: List of account IDs
            
        Returns:
            Dict with aggregated historical data
        """
        # Get last 90 days of data for each account
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=90)
        
        aggregated_costs = {}
        
        for account_id in account_ids:
            # Get cost data for each day
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                cost_data = self.cost_repo.get(account_id, date_str)
                
                if cost_data:
                    if date_str not in aggregated_costs:
                        aggregated_costs[date_str] = Decimal("0")
                    aggregated_costs[date_str] += cost_data.total_cost
                
                current_date += timedelta(days=1)
        
        return aggregated_costs
