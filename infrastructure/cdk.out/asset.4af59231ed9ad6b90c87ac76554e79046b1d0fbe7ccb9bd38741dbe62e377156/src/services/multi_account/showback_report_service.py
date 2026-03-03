"""
Showback Report Service

Generates showback reports for teams, projects, and environments.
Showback provides cost visibility without actual billing.
"""
import logging
import csv
from io import StringIO
from decimal import Decimal
from typing import List, Dict, Optional
from dataclasses import dataclass

from .models import AllocationResult
from .cost_allocation_engine import CostAllocationEngine


logger = logging.getLogger(__name__)


@dataclass
class ShowbackReport:
    """Showback report data"""
    entity_type: str  # "team", "project", "environment"
    entity_name: str
    start_date: str
    end_date: str
    total_cost: Decimal
    cost_breakdown: Dict[str, Decimal]  # service -> cost
    cost_trend: Dict[str, Decimal]  # date -> cost


class ShowbackReportService:
    """
    Generates showback reports for cost visibility.
    
    Showback reports show teams their AWS costs without actual billing.
    """
    
    def __init__(self, allocation_engine: Optional[CostAllocationEngine] = None):
        """
        Initialize the Showback Report Service.
        
        Args:
            allocation_engine: Cost allocation engine
        """
        self.allocation_engine = allocation_engine or CostAllocationEngine()
    
    def generate_showback_report(
        self,
        entity_type: str,
        entity_name: str,
        account_ids: List[str],
        start_date: str,
        end_date: str
    ) -> ShowbackReport:
        """
        Generate showback report for a team, project, or environment.
        
        Args:
            entity_type: Type of entity ("team", "project", "environment")
            entity_name: Name of the entity
            account_ids: List of account IDs to include
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            ShowbackReport with cost breakdown and trends
            
        Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6
        """
        logger.info(
            f"Generating showback report for {entity_type} '{entity_name}' "
            f"from {start_date} to {end_date}"
        )
        
        # Map entity type to tag key
        tag_key_map = {
            "team": "Team",
            "project": "Project",
            "environment": "Environment"
        }
        
        tag_key = tag_key_map.get(entity_type.lower())
        if not tag_key:
            raise ValueError(f"Invalid entity_type: {entity_type}")
        
        total_cost = Decimal("0")
        cost_breakdown: Dict[str, Decimal] = {}
        cost_trend: Dict[str, Decimal] = {}
        
        # Aggregate costs across all accounts
        for account_id in account_ids:
            # Get allocation result for this account
            result = self.allocation_engine.allocate_by_tags(
                account_id=account_id,
                start_date=start_date,
                end_date=end_date,
                tag_keys=[tag_key]
            )
            
            # Filter allocations for this entity
            entity_tag = f"{tag_key}:{entity_name}"
            if entity_tag in result.allocations_by_category:
                entity_cost = result.allocations_by_category[entity_tag]
                total_cost += entity_cost
                
                # Get service breakdown (from cost repository)
                cost_data = self.allocation_engine.cost_repository.get_cost_data(
                    account_id, start_date
                )
                
                if cost_data and 'costs_by_service' in cost_data:
                    for service, cost in cost_data['costs_by_service'].items():
                        cost_decimal = Decimal(str(cost))
                        cost_breakdown[service] = cost_breakdown.get(
                            service, Decimal("0")
                        ) + cost_decimal
                
                # Get daily trend
                if cost_data and 'costs_by_day' in cost_data:
                    for date, cost in cost_data['costs_by_day'].items():
                        cost_decimal = Decimal(str(cost))
                        cost_trend[date] = cost_trend.get(
                            date, Decimal("0")
                        ) + cost_decimal
        
        report = ShowbackReport(
            entity_type=entity_type,
            entity_name=entity_name,
            start_date=start_date,
            end_date=end_date,
            total_cost=total_cost,
            cost_breakdown=cost_breakdown,
            cost_trend=cost_trend
        )
        
        logger.info(
            f"Generated showback report for {entity_type} '{entity_name}': "
            f"${total_cost} across {len(account_ids)} accounts"
        )
        
        return report
    
    def export_to_csv(self, report: ShowbackReport) -> str:
        """
        Export showback report to CSV format.
        
        Args:
            report: Showback report
            
        Returns:
            CSV string
            
        Validates: Requirements 9.7
        """
        logger.info(
            f"Exporting showback report for {report.entity_type} "
            f"'{report.entity_name}' to CSV"
        )
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            f"Showback Report - {report.entity_type.title()}: {report.entity_name}"
        ])
        writer.writerow([f"Period: {report.start_date} to {report.end_date}"])
        writer.writerow([f"Total Cost: ${report.total_cost}"])
        writer.writerow([])
        
        # Cost breakdown by service
        writer.writerow(["Cost Breakdown by Service"])
        writer.writerow(["Service", "Cost"])
        for service, cost in sorted(
            report.cost_breakdown.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            writer.writerow([service, f"${cost}"])
        
        writer.writerow([])
        
        # Cost trend by date
        writer.writerow(["Cost Trend by Date"])
        writer.writerow(["Date", "Cost"])
        for date, cost in sorted(report.cost_trend.items()):
            writer.writerow([date, f"${cost}"])
        
        csv_content = output.getvalue()
        output.close()
        
        logger.info(f"Exported showback report to CSV ({len(csv_content)} bytes)")
        
        return csv_content
