"""
Showback Report Service

Generates showback reports for teams, projects, and environments.
Showback provides cost visibility without actual billing.
"""
import logging
from .report_data import entity_rows, safe_writer
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
    estimated_observations: Optional[List[Dict]] = None
    unknown_estimate_observations: Optional[List[Dict]] = None


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
        
        observations = []
        category = tag_key + ':' + entity_name
        for account_id, day, service, cost in entity_rows(self.allocation_engine.cost_repository, account_ids, category, start_date, end_date, observations=observations):
            total_cost += cost
            cost_breakdown[service] = cost_breakdown.get(service, Decimal('0')) + cost
            cost_trend[day] = cost_trend.get(day, Decimal('0')) + cost
        report = ShowbackReport(
            entity_type=entity_type,
            entity_name=entity_name,
            start_date=start_date,
            end_date=end_date,
            total_cost=total_cost,
            cost_breakdown=cost_breakdown,
            cost_trend=cost_trend,
            estimated_observations=[item for item in observations if item['is_estimated'] is True],
            unknown_estimate_observations=[item for item in observations if item['is_estimated'] is None]
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
        writer = safe_writer(output)
        
        # Header
        writer.writerow([
            f"Showback Report - {report.entity_type.title()}: {report.entity_name}"
        ])
        writer.writerow([f"Period: {report.start_date} to {report.end_date}"])
        writer.writerow(["Provider estimated account/day observations", len(report.estimated_observations) if report.estimated_observations is not None else "Unknown"])
        writer.writerow(["Unknown provider estimate account/day observations", len(report.unknown_estimate_observations) if report.unknown_estimate_observations is not None else "Unknown"])
        writer.writerow(["Provider cost observations can change; this is not a verified invoice."])
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
