"""
Chargeback Report Service

Generates chargeback reports for internal billing.
Chargeback includes detailed line items for actual billing.
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
class ChargebackLineItem:
    """Individual line item in chargeback report"""
    account_id: str
    account_name: str
    service: str
    cost: Decimal
    date: str


@dataclass
class ChargebackReport:
    """Chargeback report data"""
    entity_type: str  # "team", "project"
    entity_name: str
    start_date: str
    end_date: str
    total_charges: Decimal
    line_items: List[ChargebackLineItem]
    summary_by_account: Dict[str, Decimal]  # account_id -> total_cost
    summary_by_service: Dict[str, Decimal]  # service -> total_cost
    estimated_observations: Optional[List[Dict]] = None
    unknown_estimate_observations: Optional[List[Dict]] = None


class ChargebackReportService:
    """
    Generates chargeback reports for internal billing.
    
    Chargeback reports include detailed line items for charging teams.
    """
    
    def __init__(self, allocation_engine: Optional[CostAllocationEngine] = None):
        """
        Initialize the Chargeback Report Service.
        
        Args:
            allocation_engine: Cost allocation engine
        """
        self.allocation_engine = allocation_engine or CostAllocationEngine()
    
    def generate_chargeback_report(
        self,
        entity_type: str,
        entity_name: str,
        account_ids: List[str],
        account_names: Dict[str, str],
        start_date: str,
        end_date: str
    ) -> ChargebackReport:
        """
        Generate chargeback report for a team or project.
        
        Args:
            entity_type: Type of entity ("team", "project")
            entity_name: Name of the entity
            account_ids: List of account IDs to include
            account_names: Mapping of account_id to account_name
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            ChargebackReport with detailed line items
            
        Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5
        """
        logger.info(
            f"Generating chargeback report for {entity_type} '{entity_name}' "
            f"from {start_date} to {end_date}"
        )
        
        # Map entity type to tag key
        tag_key_map = {
            "team": "Team",
            "project": "Project"
        }
        
        tag_key = tag_key_map.get(entity_type.lower())
        if not tag_key:
            raise ValueError(f"Invalid entity_type: {entity_type}")
        
        line_items: List[ChargebackLineItem] = []
        summary_by_account: Dict[str, Decimal] = {}
        summary_by_service: Dict[str, Decimal] = {}
        total_charges = Decimal("0")
        
        observations = []
        category = tag_key + ':' + entity_name
        for account_id, day, service, cost in entity_rows(self.allocation_engine.cost_repository, account_ids, category, start_date, end_date, observations=observations):
            line_items.append(ChargebackLineItem(account_id, account_names.get(account_id, account_id), service, cost, day))
            summary_by_account[account_id] = summary_by_account.get(account_id, Decimal('0')) + cost
            summary_by_service[service] = summary_by_service.get(service, Decimal('0')) + cost
            total_charges += cost
        report = ChargebackReport(
            entity_type=entity_type,
            entity_name=entity_name,
            start_date=start_date,
            end_date=end_date,
            total_charges=total_charges,
            line_items=line_items,
            summary_by_account=summary_by_account,
            summary_by_service=summary_by_service,
            estimated_observations=[item for item in observations if item['is_estimated'] is True],
            unknown_estimate_observations=[item for item in observations if item['is_estimated'] is None]
        )
        
        logger.info(
            f"Generated chargeback report for {entity_type} '{entity_name}': "
            f"${total_charges} across {len(account_ids)} accounts, "
            f"{len(line_items)} line items"
        )
        
        return report
    
    def export_to_csv(self, report: ChargebackReport) -> str:
        """
        Export chargeback report to CSV format.
        
        Args:
            report: Chargeback report
            
        Returns:
            CSV string
            
        Validates: Requirements 10.6
        """
        logger.info(
            f"Exporting chargeback report for {report.entity_type} "
            f"'{report.entity_name}' to CSV"
        )
        
        output = StringIO()
        writer = safe_writer(output)
        
        # Header
        writer.writerow([
            f"Chargeback Report - {report.entity_type.title()}: {report.entity_name}"
        ])
        writer.writerow([f"Period: {report.start_date} to {report.end_date}"])
        writer.writerow(["Provider estimated account/day observations", len(report.estimated_observations) if report.estimated_observations is not None else "Unknown"])
        writer.writerow(["Unknown provider estimate account/day observations", len(report.unknown_estimate_observations) if report.unknown_estimate_observations is not None else "Unknown"])
        writer.writerow(["Provider cost observations can change; this is not a verified invoice."])
        writer.writerow([f"Total Charges: ${report.total_charges}"])
        writer.writerow([])
        
        # Line items
        writer.writerow(["Line Items"])
        writer.writerow(["Account ID", "Account Name", "Service", "Date", "Cost"])
        for item in sorted(report.line_items, key=lambda x: x.cost, reverse=True):
            writer.writerow([
                item.account_id,
                item.account_name,
                item.service,
                item.date,
                f"${item.cost}"
            ])
        
        writer.writerow([])
        
        # Summary by account
        writer.writerow(["Summary by Account"])
        writer.writerow(["Account ID", "Total Cost"])
        for account_id, cost in sorted(
            report.summary_by_account.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            writer.writerow([account_id, f"${cost}"])
        
        writer.writerow([])
        
        # Summary by service
        writer.writerow(["Summary by Service"])
        writer.writerow(["Service", "Total Cost"])
        for service, cost in sorted(
            report.summary_by_service.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            writer.writerow([service, f"${cost}"])
        
        csv_content = output.getvalue()
        output.close()
        
        logger.info(f"Exported chargeback report to CSV ({len(csv_content)} bytes)")
        
        return csv_content
    
    def export_to_pdf(self, report: ChargebackReport) -> str:
        """PDF is unavailable; never label plain text as a PDF artifact."""
        raise NotImplementedError("PDF export is not supported. Use export_to_csv instead.")
