"""
Unit tests for Idle GPU Detector.

Tests idle GPU identification, idle time calculation, wasted cost calculation,
and alert generation.

Requirements: FR-1.5
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from src.services.ai_ml.idle_detector import IdleGPUDetector, IdleGPU, IdleGPUAlert
from decimal import Decimal


class TestIdleGPUDetector:
    """Unit tests for IdleGPUDetector."""
    
    @patch('src.services.pricing_manager.PricingManager')
    def test_identify_idle_gpus_with_low_utilization(self, mock_pricing_manager_class):
        """
        Test identification of idle GPUs with low utilization.
        Requirements: FR-1.5
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # Mock PricingManager
        mock_pricing_manager = Mock()
        mock_pricing_data = Mock()
        mock_pricing_data.prices = {'p3.2xlarge': Decimal('3.06')}
        mock_pricing_manager.get_pricing_data.return_value = mock_pricing_data
        mock_pricing_manager_class.return_value = mock_pricing_manager
        detector.pricing_manager = mock_pricing_manager
        
        # Mock GPU instances
        detector._get_gpu_instances = Mock(return_value=[
            {'instance_id': 'i-idle-123', 'instance_type': 'p3.2xlarge'}
        ])
        
        # Mock low utilization (idle)
        detector._get_gpu_utilization = Mock(return_value=[5.0, 3.0, 7.0, 4.0, 6.0])
        
        # Execute
        idle_gpus = detector.identify_idle_gpus('2026-02-01', '2026-02-24', threshold=10.0)
        
        # Verify
        assert len(idle_gpus) == 1
        assert idle_gpus[0].instance_id == 'i-idle-123'
        assert idle_gpus[0].utilization < 10.0
        assert idle_gpus[0].idle_hours > 0
        assert idle_gpus[0].wasted_cost > 0
    
    def test_identify_idle_gpus_with_high_utilization(self):
        """
        Test that high utilization GPUs are not identified as idle.
        Requirements: FR-1.5
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # Mock GPU instances
        detector._get_gpu_instances = Mock(return_value=[
            {'instance_id': 'i-active-456', 'instance_type': 'p3.2xlarge'}
        ])
        
        # Mock high utilization (not idle)
        detector._get_gpu_utilization = Mock(return_value=[85.0, 87.0, 84.0, 86.0, 85.5])
        
        # Execute
        idle_gpus = detector.identify_idle_gpus('2026-02-01', '2026-02-24', threshold=10.0)
        
        # Verify
        assert len(idle_gpus) == 0
    
    def test_calculate_idle_time(self):
        """
        Test idle time calculation.
        Requirements: FR-1.5
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # Mock utilization data (50% idle, 50% active)
        detector._get_gpu_utilization = Mock(return_value=[5.0, 15.0, 5.0, 15.0])
        
        # Execute
        idle_hours = detector.calculate_idle_time(
            'i-test-123',
            '2026-02-01T00:00:00',
            '2026-02-01T04:00:00',  # 4 hours total
            threshold=10.0
        )
        
        # Verify (50% of 4 hours = 2 hours)
        assert idle_hours == pytest.approx(2.0, rel=0.1)
    
    @patch('src.services.pricing_manager.PricingManager')
    def test_calculate_wasted_cost(self, mock_pricing_manager_class):
        """
        Test wasted cost calculation.
        Requirements: FR-1.5
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # Mock PricingManager
        mock_pricing_manager = Mock()
        mock_pricing_data = Mock()
        mock_pricing_data.prices = {'p3.2xlarge': Decimal('3.06')}
        mock_pricing_manager.get_pricing_data.return_value = mock_pricing_data
        mock_pricing_manager_class.return_value = mock_pricing_manager
        detector.pricing_manager = mock_pricing_manager
        
        # Mock utilization data (all idle)
        detector._get_gpu_utilization = Mock(return_value=[5.0, 3.0, 7.0, 4.0])
        
        # Execute
        wasted_cost = detector.calculate_wasted_cost(
            'i-test-123',
            'p3.2xlarge',  # $3.06/hour
            '2026-02-01T00:00:00',
            '2026-02-01T10:00:00',  # 10 hours total
            threshold=10.0
        )
        
        # Verify (10 hours * $3.06/hour = $30.60)
        assert wasted_cost == pytest.approx(30.6, rel=0.1)
    
    def test_generate_idle_alerts_low_severity(self):
        """
        Test alert generation with low severity.
        Requirements: FR-1.5
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # Mock idle GPU with low wasted cost
        detector.identify_idle_gpus = Mock(return_value=[
            IdleGPU(
                instance_id='i-idle-123',
                instance_type='g4dn.xlarge',
                utilization=5.0,
                idle_hours=10.0,
                wasted_cost=5.26,  # $5.26 (low severity)
                cost_per_hour=0.526,
                first_idle_time='2026-02-01',
                last_check_time='2026-02-24',
                recommendation='REVIEW: GPU utilization is low.'
            )
        ])
        
        # Execute
        alerts = detector.generate_idle_alerts('2026-02-01', '2026-02-24')
        
        # Verify
        assert len(alerts) == 1
        assert alerts[0].severity == 'low'
        assert 'i-idle-123' in alerts[0].message
    
    def test_generate_idle_alerts_critical_severity(self):
        """
        Test alert generation with critical severity.
        Requirements: FR-1.5
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # Mock idle GPU with high wasted cost
        detector.identify_idle_gpus = Mock(return_value=[
            IdleGPU(
                instance_id='i-idle-999',
                instance_type='p5.48xlarge',
                utilization=2.0,
                idle_hours=100.0,
                wasted_cost=9832.0,  # $9,832 (critical severity)
                cost_per_hour=98.32,
                first_idle_time='2026-02-01',
                last_check_time='2026-02-24',
                recommendation='STOP: GPU is nearly unused.'
            )
        ])
        
        # Execute
        alerts = detector.generate_idle_alerts('2026-02-01', '2026-02-24')
        
        # Verify
        assert len(alerts) == 1
        assert alerts[0].severity == 'critical'
        assert 'CRITICAL ALERT' in alerts[0].message
        assert '$9832.00' in alerts[0].message
    
    def test_determine_severity_thresholds(self):
        """
        Test severity determination based on wasted cost thresholds.
        Requirements: FR-1.5
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # Test all severity levels
        # Thresholds: low < $10, medium >= $50, high >= $100, critical >= $500
        assert detector._determine_severity(5.0) == 'low'      # < $10
        assert detector._determine_severity(25.0) == 'low'     # < $50
        assert detector._determine_severity(75.0) == 'medium'  # >= $50, < $100
        assert detector._determine_severity(150.0) == 'high'   # >= $100, < $500
        assert detector._determine_severity(600.0) == 'critical'  # >= $500
    
    def test_generate_recommendation_nearly_unused(self):
        """
        Test recommendation generation for nearly unused GPU.
        Requirements: FR-1.5
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # Execute
        recommendation = detector._generate_recommendation(
            avg_utilization=3.0,
            idle_hours=100.0,
            wasted_cost=300.0
        )
        
        # Verify
        assert 'STOP' in recommendation
        assert 'nearly unused' in recommendation
    
    def test_generate_recommendation_idle_high_cost(self):
        """
        Test recommendation generation for idle GPU with high wasted cost.
        Requirements: FR-1.5
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # Execute
        recommendation = detector._generate_recommendation(
            avg_utilization=8.0,
            idle_hours=50.0,
            wasted_cost=150.0
        )
        
        # Verify
        assert 'STOP' in recommendation
        assert 'wasting significant cost' in recommendation
    
    def test_generate_recommendation_borderline(self):
        """
        Test recommendation generation for borderline utilization.
        Requirements: FR-1.5
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # Execute
        recommendation = detector._generate_recommendation(
            avg_utilization=12.0,
            idle_hours=10.0,
            wasted_cost=30.0
        )
        
        # Verify
        assert 'MONITOR' in recommendation
    
    def test_calculate_idle_hours_all_idle(self):
        """
        Test idle hours calculation when all data points are idle.
        Requirements: FR-1.5
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # All data points below threshold
        utilization_data = [5.0, 3.0, 7.0, 4.0, 6.0]
        
        # Execute
        idle_hours = detector._calculate_idle_hours(
            utilization_data,
            threshold=10.0,
            start_date='2026-02-01T00:00:00',
            end_date='2026-02-01T10:00:00'  # 10 hours
        )
        
        # Verify (100% idle = 10 hours)
        assert idle_hours == pytest.approx(10.0, rel=0.01)
    
    def test_calculate_idle_hours_none_idle(self):
        """
        Test idle hours calculation when no data points are idle.
        Requirements: FR-1.5
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # All data points above threshold
        utilization_data = [85.0, 87.0, 84.0, 86.0, 85.5]
        
        # Execute
        idle_hours = detector._calculate_idle_hours(
            utilization_data,
            threshold=10.0,
            start_date='2026-02-01T00:00:00',
            end_date='2026-02-01T10:00:00'  # 10 hours
        )
        
        # Verify (0% idle = 0 hours)
        assert idle_hours == pytest.approx(0.0, rel=0.01)
    
    @patch('src.services.pricing_manager.PricingManager')
    def test_get_instance_cost_per_hour_known_types(self, mock_pricing_manager_class):
        """
        Test cost per hour retrieval for known instance types.
        Requirements: FR-1.5
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # Mock PricingManager
        mock_pricing_manager = Mock()
        mock_pricing_data = Mock()
        mock_pricing_data.prices = {
            'p3.2xlarge': Decimal('3.06'),
            'p4d.24xlarge': Decimal('32.77'),
            'p5.48xlarge': Decimal('98.32'),
            'g4dn.xlarge': Decimal('0.526'),
            'g5.xlarge': Decimal('1.006')
        }
        mock_pricing_manager.get_pricing_data.return_value = mock_pricing_data
        mock_pricing_manager_class.return_value = mock_pricing_manager
        detector.pricing_manager = mock_pricing_manager
        
        # Test known instance types
        assert detector._get_instance_cost_per_hour('p3.2xlarge') == 3.06
        assert detector._get_instance_cost_per_hour('p4d.24xlarge') == 32.77
        assert detector._get_instance_cost_per_hour('p5.48xlarge') == 98.32
        assert detector._get_instance_cost_per_hour('g4dn.xlarge') == 0.526
        assert detector._get_instance_cost_per_hour('g5.xlarge') == 1.006
    
    @patch('src.services.pricing_manager.PricingManager')
    def test_get_instance_cost_per_hour_unknown_type(self, mock_pricing_manager_class):
        """
        Test cost per hour retrieval for unknown instance types.
        Requirements: FR-1.5
        """
        # Setup
        mock_dynamodb = Mock()
        detector = IdleGPUDetector(mock_dynamodb)
        
        # Mock PricingManager to return empty prices (simulating unknown type)
        mock_pricing_manager = Mock()
        mock_pricing_data = Mock()
        mock_pricing_data.prices = {}  # Empty - unknown type
        mock_pricing_manager.get_pricing_data.return_value = mock_pricing_data
        mock_pricing_manager_class.return_value = mock_pricing_manager
        detector.pricing_manager = mock_pricing_manager
        
        # Mock boto3 pricing client to raise exception (simulating API failure)
        with patch('boto3.client') as mock_boto3:
            mock_pricing_client = Mock()
            mock_pricing_client.get_products.side_effect = Exception("API error")
            mock_boto3.return_value = mock_pricing_client
            
            # Test unknown instance type (should return default fallback)
            assert detector._get_instance_cost_per_hour('unknown.type') == 5.0
