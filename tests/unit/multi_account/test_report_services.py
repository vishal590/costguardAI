"""
Unit tests for Showback and Chargeback Report Services
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, MagicMock
from datetime import datetime

from src.services.multi_account.showback_report_service import (
    ShowbackReportService,
    ShowbackReport
)
from src.services.multi_account.chargeback_report_service import (
    ChargebackReportService,
    ChargebackReport,
    ChargebackLineItem
)
from src.services.multi_account.models import AllocationResult


class TestShowbackReportService:
    """Test suite for ShowbackReportService"""
    
    @pytest.fixture
    def mock_allocation_engine(self):
        """Create mock allocation engine"""
        engine = Mock()
        engine.cost_repository = Mock()
        return engine
    
    @pytest.fixture
    def service(self, mock_allocation_engine):
        """Create ShowbackReportService with mock engine"""
        return ShowbackReportService(allocation_engine=mock_allocation_engine)
    
    def test_generate_showback_report_team(self, service, mock_allocation_engine):
        """Test generating showback report for a team"""
        # Given: Team allocation data
        account_ids = ["111111111111", "222222222222"]
        entity_type = "team"
        entity_name = "Engineering"
        start_date = "2026-02-01"
        end_date = "2026-02-28"
        
        # Mock allocation result
        mock_allocation_engine.allocate_by_tags.return_value = AllocationResult(
            total_cost=Decimal("1000"),
            allocated_cost=Decimal("800"),
            unallocated_cost=Decimal("200"),
            allocation_percentage=80.0,
            allocations_by_category={
                "Team:Engineering": Decimal("800")
            }
        )
        
        # Mock cost data
        mock_allocation_engine.cost_repository.get_cost_data.return_value = {
            'costs_by_service': {
                'EC2': Decimal("500"),
                'S3': Decimal("300")
            },
            'costs_by_day': {
                '2026-02-01': Decimal("400"),
                '2026-02-02': Decimal("400")
            }
        }
        
        # When: Generating report
        report = service.generate_showback_report(
            entity_type=entity_type,
            entity_name=entity_name,
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date
        )
        
        # Then: Report should be generated
        assert report.entity_type == entity_type
        assert report.entity_name == entity_name
        assert report.start_date == start_date
        assert report.end_date == end_date
        assert report.total_cost == Decimal("1600")  # 800 * 2 accounts
        assert 'EC2' in report.cost_breakdown
        assert 'S3' in report.cost_breakdown
        assert len(report.cost_trend) > 0
    
    def test_generate_showback_report_project(self, service, mock_allocation_engine):
        """Test generating showback report for a project"""
        # Given: Project allocation data
        account_ids = ["111111111111"]
        entity_type = "project"
        entity_name = "WebApp"
        start_date = "2026-02-01"
        end_date = "2026-02-28"
        
        # Mock allocation result
        mock_allocation_engine.allocate_by_tags.return_value = AllocationResult(
            total_cost=Decimal("500"),
            allocated_cost=Decimal("400"),
            unallocated_cost=Decimal("100"),
            allocation_percentage=80.0,
            allocations_by_category={
                "Project:WebApp": Decimal("400")
            }
        )
        
        # Mock cost data
        mock_allocation_engine.cost_repository.get_cost_data.return_value = {
            'costs_by_service': {
                'Lambda': Decimal("200"),
                'DynamoDB': Decimal("200")
            },
            'costs_by_day': {
                '2026-02-01': Decimal("400")
            }
        }
        
        # When: Generating report
        report = service.generate_showback_report(
            entity_type=entity_type,
            entity_name=entity_name,
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date
        )
        
        # Then: Report should be generated
        assert report.entity_type == entity_type
        assert report.entity_name == entity_name
        assert report.total_cost == Decimal("400")
        assert 'Lambda' in report.cost_breakdown
        assert 'DynamoDB' in report.cost_breakdown
    
    def test_generate_showback_report_environment(self, service, mock_allocation_engine):
        """Test generating showback report for an environment"""
        # Given: Environment allocation data
        account_ids = ["111111111111"]
        entity_type = "environment"
        entity_name = "Production"
        start_date = "2026-02-01"
        end_date = "2026-02-28"
        
        # Mock allocation result
        mock_allocation_engine.allocate_by_tags.return_value = AllocationResult(
            total_cost=Decimal("2000"),
            allocated_cost=Decimal("1800"),
            unallocated_cost=Decimal("200"),
            allocation_percentage=90.0,
            allocations_by_category={
                "Environment:Production": Decimal("1800")
            }
        )
        
        # Mock cost data
        mock_allocation_engine.cost_repository.get_cost_data.return_value = {
            'costs_by_service': {
                'RDS': Decimal("1000"),
                'EC2': Decimal("800")
            },
            'costs_by_day': {
                '2026-02-01': Decimal("1800")
            }
        }
        
        # When: Generating report
        report = service.generate_showback_report(
            entity_type=entity_type,
            entity_name=entity_name,
            account_ids=account_ids,
            start_date=start_date,
            end_date=end_date
        )
        
        # Then: Report should be generated
        assert report.entity_type == entity_type
        assert report.entity_name == entity_name
        assert report.total_cost == Decimal("1800")
    
    def test_generate_showback_report_invalid_entity_type(
        self, service, mock_allocation_engine
    ):
        """Test generating report with invalid entity type"""
        # Given: Invalid entity type
        entity_type = "invalid"
        
        # When/Then: Should raise ValueError
        with pytest.raises(ValueError, match="Invalid entity_type"):
            service.generate_showback_report(
                entity_type=entity_type,
                entity_name="Test",
                account_ids=["111111111111"],
                start_date="2026-02-01",
                end_date="2026-02-28"
            )
    
    def test_export_to_csv(self, service):
        """Test exporting showback report to CSV"""
        # Given: Showback report
        report = ShowbackReport(
            entity_type="team",
            entity_name="Engineering",
            start_date="2026-02-01",
            end_date="2026-02-28",
            total_cost=Decimal("1000"),
            cost_breakdown={
                'EC2': Decimal("600"),
                'S3': Decimal("400")
            },
            cost_trend={
                '2026-02-01': Decimal("500"),
                '2026-02-02': Decimal("500")
            }
        )
        
        # When: Exporting to CSV
        csv_content = service.export_to_csv(report)
        
        # Then: CSV should contain report data
        assert "Showback Report" in csv_content
        assert "Engineering" in csv_content
        assert "2026-02-01" in csv_content
        assert "2026-02-28" in csv_content
        assert "$1000" in csv_content
        assert "EC2" in csv_content
        assert "S3" in csv_content
        assert "Cost Breakdown by Service" in csv_content
        assert "Cost Trend by Date" in csv_content


class TestChargebackReportService:
    """Test suite for ChargebackReportService"""
    
    @pytest.fixture
    def mock_allocation_engine(self):
        """Create mock allocation engine"""
        engine = Mock()
        engine.cost_repository = Mock()
        return engine
    
    @pytest.fixture
    def service(self, mock_allocation_engine):
        """Create ChargebackReportService with mock engine"""
        return ChargebackReportService(allocation_engine=mock_allocation_engine)
    
    def test_generate_chargeback_report_team(self, service, mock_allocation_engine):
        """Test generating chargeback report for a team"""
        # Given: Team allocation data
        account_ids = ["111111111111", "222222222222"]
        account_names = {
            "111111111111": "prod-account",
            "222222222222": "dev-account"
        }
        entity_type = "team"
        entity_name = "Engineering"
        start_date = "2026-02-01"
        end_date = "2026-02-28"
        
        # Mock allocation result
        mock_allocation_engine.allocate_by_tags.return_value = AllocationResult(
            total_cost=Decimal("1000"),
            allocated_cost=Decimal("800"),
            unallocated_cost=Decimal("200"),
            allocation_percentage=80.0,
            allocations_by_category={
                "Team:Engineering": Decimal("800")
            }
        )
        
        # Mock cost data
        mock_allocation_engine.cost_repository.get_cost_data.return_value = {
            'costs_by_service': {
                'EC2': Decimal("500"),
                'S3': Decimal("300")
            }
        }
        
        # When: Generating report
        report = service.generate_chargeback_report(
            entity_type=entity_type,
            entity_name=entity_name,
            account_ids=account_ids,
            account_names=account_names,
            start_date=start_date,
            end_date=end_date
        )
        
        # Then: Report should be generated
        assert report.entity_type == entity_type
        assert report.entity_name == entity_name
        assert report.start_date == start_date
        assert report.end_date == end_date
        assert report.total_charges == Decimal("1600")  # 800 * 2 accounts
        assert len(report.line_items) == 4  # 2 services * 2 accounts
        assert len(report.summary_by_account) == 2
        assert len(report.summary_by_service) == 2
    
    def test_generate_chargeback_report_project(self, service, mock_allocation_engine):
        """Test generating chargeback report for a project"""
        # Given: Project allocation data
        account_ids = ["111111111111"]
        account_names = {"111111111111": "webapp-account"}
        entity_type = "project"
        entity_name = "WebApp"
        start_date = "2026-02-01"
        end_date = "2026-02-28"
        
        # Mock allocation result
        mock_allocation_engine.allocate_by_tags.return_value = AllocationResult(
            total_cost=Decimal("500"),
            allocated_cost=Decimal("400"),
            unallocated_cost=Decimal("100"),
            allocation_percentage=80.0,
            allocations_by_category={
                "Project:WebApp": Decimal("400")
            }
        )
        
        # Mock cost data
        mock_allocation_engine.cost_repository.get_cost_data.return_value = {
            'costs_by_service': {
                'Lambda': Decimal("200"),
                'DynamoDB': Decimal("200")
            }
        }
        
        # When: Generating report
        report = service.generate_chargeback_report(
            entity_type=entity_type,
            entity_name=entity_name,
            account_ids=account_ids,
            account_names=account_names,
            start_date=start_date,
            end_date=end_date
        )
        
        # Then: Report should be generated
        assert report.entity_type == entity_type
        assert report.entity_name == entity_name
        assert report.total_charges == Decimal("400")
        assert len(report.line_items) == 2  # 2 services
        assert "111111111111" in report.summary_by_account
        assert 'Lambda' in report.summary_by_service
        assert 'DynamoDB' in report.summary_by_service
    
    def test_generate_chargeback_report_line_items(
        self, service, mock_allocation_engine
    ):
        """Test chargeback report line items contain correct data"""
        # Given: Allocation data
        account_ids = ["111111111111"]
        account_names = {"111111111111": "test-account"}
        
        # Mock allocation result
        mock_allocation_engine.allocate_by_tags.return_value = AllocationResult(
            total_cost=Decimal("300"),
            allocated_cost=Decimal("300"),
            unallocated_cost=Decimal("0"),
            allocation_percentage=100.0,
            allocations_by_category={
                "Team:DevOps": Decimal("300")
            }
        )
        
        # Mock cost data
        mock_allocation_engine.cost_repository.get_cost_data.return_value = {
            'costs_by_service': {
                'EC2': Decimal("200"),
                'S3': Decimal("100")
            }
        }
        
        # When: Generating report
        report = service.generate_chargeback_report(
            entity_type="team",
            entity_name="DevOps",
            account_ids=account_ids,
            account_names=account_names,
            start_date="2026-02-01",
            end_date="2026-02-28"
        )
        
        # Then: Line items should have correct structure
        assert len(report.line_items) == 2
        
        ec2_item = next(item for item in report.line_items if item.service == 'EC2')
        assert ec2_item.account_id == "111111111111"
        assert ec2_item.account_name == "test-account"
        assert ec2_item.cost == Decimal("200")
        assert ec2_item.date == "2026-02-01"
        
        s3_item = next(item for item in report.line_items if item.service == 'S3')
        assert s3_item.cost == Decimal("100")
    
    def test_generate_chargeback_report_invalid_entity_type(
        self, service, mock_allocation_engine
    ):
        """Test generating report with invalid entity type"""
        # Given: Invalid entity type
        entity_type = "invalid"
        
        # When/Then: Should raise ValueError
        with pytest.raises(ValueError, match="Invalid entity_type"):
            service.generate_chargeback_report(
                entity_type=entity_type,
                entity_name="Test",
                account_ids=["111111111111"],
                account_names={"111111111111": "test"},
                start_date="2026-02-01",
                end_date="2026-02-28"
            )
    
    def test_export_to_csv(self, service):
        """Test exporting chargeback report to CSV"""
        # Given: Chargeback report
        line_items = [
            ChargebackLineItem(
                account_id="111111111111",
                account_name="prod-account",
                service="EC2",
                cost=Decimal("600"),
                date="2026-02-01"
            ),
            ChargebackLineItem(
                account_id="111111111111",
                account_name="prod-account",
                service="S3",
                cost=Decimal("400"),
                date="2026-02-01"
            )
        ]
        
        report = ChargebackReport(
            entity_type="team",
            entity_name="Engineering",
            start_date="2026-02-01",
            end_date="2026-02-28",
            total_charges=Decimal("1000"),
            line_items=line_items,
            summary_by_account={"111111111111": Decimal("1000")},
            summary_by_service={"EC2": Decimal("600"), "S3": Decimal("400")}
        )
        
        # When: Exporting to CSV
        csv_content = service.export_to_csv(report)
        
        # Then: CSV should contain report data
        assert "Chargeback Report" in csv_content
        assert "Engineering" in csv_content
        assert "2026-02-01" in csv_content
        assert "2026-02-28" in csv_content
        assert "$1000" in csv_content
        assert "prod-account" in csv_content
        assert "EC2" in csv_content
        assert "S3" in csv_content
        assert "Line Items" in csv_content
        assert "Summary by Account" in csv_content
        assert "Summary by Service" in csv_content
    
    def test_export_to_pdf(self, service):
        """Test exporting chargeback report to PDF (placeholder)"""
        # Given: Chargeback report
        line_items = [
            ChargebackLineItem(
                account_id="111111111111",
                account_name="prod-account",
                service="EC2",
                cost=Decimal("600"),
                date="2026-02-01"
            )
        ]
        
        report = ChargebackReport(
            entity_type="team",
            entity_name="Engineering",
            start_date="2026-02-01",
            end_date="2026-02-28",
            total_charges=Decimal("600"),
            line_items=line_items,
            summary_by_account={"111111111111": Decimal("600")},
            summary_by_service={"EC2": Decimal("600")}
        )
        
        # When: Exporting to PDF
        pdf_content = service.export_to_pdf(report)
        
        # Then: PDF should contain report data (placeholder format)
        assert "CHARGEBACK REPORT" in pdf_content
        assert "Engineering" in pdf_content
        assert "2026-02-01" in pdf_content
        assert "$600" in pdf_content
        assert "prod-account" in pdf_content
        assert "EC2" in pdf_content
