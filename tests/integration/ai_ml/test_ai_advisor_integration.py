"""
Integration tests for AI Advisor Integration.

Tests the integration between Phase 6 (AI/ML Workload Costs) and
Phase 4 (AI Advisor), verifying that GPU cost context is properly
provided and optimization recommendations are generated.

Requirements: IR-2.4
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

from src.services.ai_ml.ai_advisor_integration import AIAdvisorIntegration
from src.services.ai_ml.gpu_cost_tracker import GPUCostTracker, GPUCostData
from src.services.ai_ml.workload_classifier import WorkloadClassifier, WorkloadClassification
from src.services.ai_ml.idle_detector import IdleGPUDetector, IdleGPU
from src.services.ai_ml.spot_instance_recommender import SpotInstanceRecommender, SpotRecommendation
from src.services.ai_ml.sagemaker_cost_tracker import SageMakerCostTracker, EndpointMetrics
from src.services.ai_ml.bedrock_cost_tracker import BedrockCostTracker, BedrockCosts, ModelRecommendation


class TestAIAdvisorIntegration:
    """Test AI Advisor integration functionality."""
    
    @pytest.fixture
    def mock_dynamodb(self):
        """Create mock DynamoDB client."""
        return Mock()
    
    @pytest.fixture
    def mock_gpu_cost_tracker(self):
        """Create mock GPU cost tracker."""
        tracker = Mock(spec=GPUCostTracker)
        
        # Mock GPU costs
        tracker.collect_gpu_costs.return_value = [
            GPUCostData(
                date=datetime(2024, 1, 15),
                instance_id='i-training-001',
                instance_type='p3.2xlarge',
                workload_type='training',
                cost=100.0,
                gpu_hours=10.0,
                cost_per_gpu_hour=10.0,
                utilization=85.0,
                classification_confidence=0.95
            ),
            GPUCostData(
                date=datetime(2024, 1, 15),
                instance_id='i-inference-001',
                instance_type='g4dn.xlarge',
                workload_type='inference',
                cost=50.0,
                gpu_hours=10.0,
                cost_per_gpu_hour=5.0,
                utilization=45.0,
                classification_confidence=0.90
            ),
            GPUCostData(
                date=datetime(2024, 1, 15),
                instance_id='i-idle-001',
                instance_type='p3.2xlarge',
                workload_type='idle',
                cost=30.0,
                gpu_hours=10.0,
                cost_per_gpu_hour=3.0,
                utilization=5.0,
                classification_confidence=0.98
            )
        ]
        
        return tracker
    
    @pytest.fixture
    def mock_workload_classifier(self):
        """Create mock workload classifier."""
        classifier = Mock(spec=WorkloadClassifier)
        
        classifier.classify_workload.return_value = WorkloadClassification(
            instance_id='i-training-001',
            workload_type='training',
            confidence=0.95,
            classification_method='cloudwatch-metrics',
            gpu_utilization_avg=85.0,
            gpu_utilization_pattern=[80.0, 85.0, 90.0, 85.0, 80.0],
            timestamp=datetime.now().isoformat()
        )
        
        return classifier
    
    @pytest.fixture
    def mock_idle_detector(self):
        """Create mock idle GPU detector."""
        detector = Mock(spec=IdleGPUDetector)
        
        detector.identify_idle_gpus.return_value = [
            IdleGPU(
                instance_id='i-idle-001',
                instance_type='p3.2xlarge',
                utilization=5.0,
                idle_hours=240.0,
                wasted_cost=720.0,
                cost_per_hour=3.0,
                first_idle_time=datetime(2024, 1, 5).isoformat(),
                last_check_time=datetime(2024, 1, 15).isoformat(),
                recommendation='Stop or terminate this idle GPU instance'
            )
        ]
        
        return detector
    
    @pytest.fixture
    def mock_spot_recommender(self):
        """Create mock spot instance recommender."""
        recommender = Mock(spec=SpotInstanceRecommender)
        
        recommender.recommend_spot_instances.return_value = [
            SpotRecommendation(
                workload_id='i-training-001',
                current_instance='p3.2xlarge',
                current_cost=3.06,
                recommended_spot_instance='p3.2xlarge',
                spot_cost=0.92,
                savings=2.14,
                savings_percent=70.0,
                interruption_risk=0.05,
                suitable=True,
                reason='Training workload suitable for spot instances'
            )
        ]
        
        return recommender
    
    @pytest.fixture
    def mock_sagemaker_tracker(self):
        """Create mock SageMaker cost tracker."""
        tracker = Mock(spec=SageMakerCostTracker)
        
        tracker.identify_idle_endpoints.return_value = [
            EndpointMetrics(
                endpoint_name='idle-endpoint-1',
                instance_type='ml.m5.xlarge',
                instance_count=1,
                requests_per_hour=2.0,
                avg_latency_ms=50.0,
                cost_per_hour=0.23,
                is_idle=True
            )
        ]
        
        return tracker
    
    @pytest.fixture
    def mock_bedrock_tracker(self):
        """Create mock Bedrock cost tracker."""
        tracker = Mock(spec=BedrockCostTracker)
        
        tracker.track_bedrock_costs.return_value = [
            BedrockCosts(
                date=datetime(2024, 1, 15),
                model_id='anthropic.claude-v2',
                invocations=1000,
                input_tokens=50000,
                output_tokens=25000,
                total_cost=15.0,
                cost_per_invocation=0.015
            )
        ]
        
        tracker.recommend_cost_optimized_models.return_value = [
            ModelRecommendation(
                current_model='anthropic.claude-v2',
                recommended_model='anthropic.claude-instant-v1',
                current_cost_per_1k_tokens=0.20,
                recommended_cost_per_1k_tokens=0.08,
                savings_percent=60.0,
                reason='Similar performance for most use cases at lower cost'
            )
        ]
        
        return tracker
    
    @pytest.fixture
    def integration(
        self,
        mock_gpu_cost_tracker,
        mock_workload_classifier,
        mock_idle_detector,
        mock_spot_recommender,
        mock_sagemaker_tracker,
        mock_bedrock_tracker
    ):
        """Create AI Advisor integration instance."""
        return AIAdvisorIntegration(
            gpu_cost_tracker=mock_gpu_cost_tracker,
            workload_classifier=mock_workload_classifier,
            idle_detector=mock_idle_detector,
            spot_recommender=mock_spot_recommender,
            sagemaker_tracker=mock_sagemaker_tracker,
            bedrock_tracker=mock_bedrock_tracker
        )
    
    def test_get_gpu_cost_context(self, integration):
        """Test getting GPU cost context for AI Advisor."""
        # Get context
        context = integration.get_gpu_cost_context(
            start_date='2024-01-01',
            end_date='2024-01-31',
            include_recommendations=True
        )
        
        # Verify context structure
        assert 'period' in context
        assert context['period']['start_date'] == '2024-01-01'
        assert context['period']['end_date'] == '2024-01-31'
        
        assert 'gpu_costs' in context
        assert 'by_workload' in context['gpu_costs']
        assert 'by_instance_type' in context['gpu_costs']
        
        assert 'workload_distribution' in context
        assert 'idle_gpus' in context
        assert 'optimization_opportunities' in context
        assert 'summary' in context
        
        # Verify cost breakdown
        costs_by_workload = context['gpu_costs']['by_workload']
        assert costs_by_workload['training'] == 100.0
        assert costs_by_workload['inference'] == 50.0
        assert costs_by_workload['idle'] == 30.0
        assert costs_by_workload['total'] == 180.0
        
        # Verify workload distribution
        distribution = context['workload_distribution']
        assert 'training_percent' in distribution
        assert 'inference_percent' in distribution
        assert 'idle_percent' in distribution
        
        # Verify idle GPUs
        assert len(context['idle_gpus']) == 1
        assert context['idle_gpus'][0]['instance_id'] == 'i-idle-001'
        assert context['idle_gpus'][0]['wasted_cost'] == 720.0
        
        # Verify summary
        summary = context['summary']
        assert summary['total_gpu_cost'] == 180.0
        assert summary['idle_gpu_count'] == 1
        assert summary['total_wasted_cost'] == 720.0
    
    def test_get_gpu_cost_context_without_recommendations(self, integration):
        """Test getting GPU cost context without recommendations."""
        context = integration.get_gpu_cost_context(
            start_date='2024-01-01',
            end_date='2024-01-31',
            include_recommendations=False
        )
        
        # Verify recommendations are empty
        assert context['optimization_opportunities'] == []
    
    def test_get_gpu_optimization_recommendations(self, integration):
        """Test generating GPU optimization recommendations."""
        recommendations = integration.get_gpu_optimization_recommendations(
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
        
        # Verify recommendations structure
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        
        # Check for idle GPU recommendation
        idle_rec = next((r for r in recommendations if r['type'] == 'idle_gpu'), None)
        assert idle_rec is not None
        assert idle_rec['priority'] in ['high', 'medium', 'low']
        assert idle_rec['potential_savings'] > 0
        assert 'description' in idle_rec
        assert 'action_items' in idle_rec
        
        # Check for spot instance recommendation
        spot_rec = next((r for r in recommendations if r['type'] == 'spot_instance'), None)
        assert spot_rec is not None
        assert spot_rec['potential_savings'] > 0
        
        # Verify recommendations are sorted by savings
        if len(recommendations) > 1:
            for i in range(len(recommendations) - 1):
                assert recommendations[i]['potential_savings'] >= recommendations[i + 1]['potential_savings']
    
    def test_get_sagemaker_recommendations(self, integration):
        """Test SageMaker idle endpoint recommendations."""
        recommendations = integration.get_gpu_optimization_recommendations(
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
        
        # Check for SageMaker recommendation
        sagemaker_rec = next(
            (r for r in recommendations if r['type'] == 'sagemaker_idle_endpoint'),
            None
        )
        assert sagemaker_rec is not None
        assert sagemaker_rec['potential_savings'] > 0
        assert 'idle-endpoint-1' in str(sagemaker_rec['action_items'])
    
    def test_get_bedrock_recommendations(self, integration):
        """Test Bedrock model optimization recommendations."""
        recommendations = integration.get_gpu_optimization_recommendations(
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
        
        # Check for Bedrock recommendation
        bedrock_rec = next(
            (r for r in recommendations if r['type'] == 'bedrock_model_optimization'),
            None
        )
        assert bedrock_rec is not None
        assert bedrock_rec['potential_savings'] > 0
        assert 'claude-instant' in bedrock_rec['description'].lower()
    
    def test_explain_workload_classification(self, integration):
        """Test workload classification explanation."""
        explanation = integration.explain_workload_classification(
            instance_id='i-training-001',
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
        
        # Verify explanation structure
        assert explanation['instance_id'] == 'i-training-001'
        assert explanation['classification'] == 'training'
        assert explanation['confidence'] == 0.95
        assert 'explanation' in explanation
        assert 'metrics' in explanation
        assert 'recommendations' in explanation
        
        # Verify explanation content
        assert 'training workload' in explanation['explanation'].lower()
        assert '95%' in explanation['explanation']
        
        # Verify metrics
        metrics = explanation['metrics']
        assert metrics['avg_utilization'] == 85.0
        assert metrics['classification_method'] == 'cloudwatch-metrics'
        
        # Verify recommendations
        assert len(explanation['recommendations']) > 0
        assert any('spot' in rec.lower() for rec in explanation['recommendations'])
    
    def test_explain_idle_workload(self, integration, mock_workload_classifier):
        """Test explanation for idle workload."""
        # Mock idle classification
        mock_workload_classifier.classify_workload.return_value = WorkloadClassification(
            instance_id='i-idle-001',
            workload_type='idle',
            confidence=0.98,
            classification_method='cloudwatch-metrics',
            gpu_utilization_avg=5.0,
            gpu_utilization_pattern=[5.0, 4.0, 6.0, 5.0, 5.0],
            timestamp=datetime.now().isoformat()
        )
        
        explanation = integration.explain_workload_classification(
            instance_id='i-idle-001',
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
        
        # Verify idle-specific content
        assert explanation['classification'] == 'idle'
        assert 'idle' in explanation['explanation'].lower()
        assert any('stop' in rec.lower() or 'terminate' in rec.lower() 
                  for rec in explanation['recommendations'])
    
    def test_explain_inference_workload(self, integration, mock_workload_classifier):
        """Test explanation for inference workload."""
        # Mock inference classification
        mock_workload_classifier.classify_workload.return_value = WorkloadClassification(
            instance_id='i-inference-001',
            workload_type='inference',
            confidence=0.90,
            classification_method='cloudwatch-metrics',
            gpu_utilization_avg=45.0,
            gpu_utilization_pattern=[40.0, 50.0, 45.0, 48.0, 42.0],
            timestamp=datetime.now().isoformat()
        )
        
        explanation = integration.explain_workload_classification(
            instance_id='i-inference-001',
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
        
        # Verify inference-specific content
        assert explanation['classification'] == 'inference'
        assert 'inference workload' in explanation['explanation'].lower()
        assert any('scale' in rec.lower() or 'auto-scaling' in rec.lower() 
                  for rec in explanation['recommendations'])
    
    def test_explain_manual_classification(self, integration, mock_workload_classifier):
        """Test explanation for manual classification."""
        # Mock manual classification
        mock_workload_classifier.classify_workload.return_value = WorkloadClassification(
            instance_id='i-manual-001',
            workload_type='training',
            confidence=1.0,
            classification_method='manual-tag',
            gpu_utilization_avg=75.0,
            gpu_utilization_pattern=[],
            timestamp=datetime.now().isoformat()
        )
        
        explanation = integration.explain_workload_classification(
            instance_id='i-manual-001',
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
        
        # Verify manual classification is mentioned
        assert 'manual' in explanation['explanation'].lower()
        assert 'tag' in explanation['explanation'].lower()
    
    def test_error_handling_in_context(self, integration, mock_gpu_cost_tracker):
        """Test error handling when getting context."""
        # Mock error
        mock_gpu_cost_tracker.collect_gpu_costs.side_effect = Exception("API error")
        
        context = integration.get_gpu_cost_context(
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
        
        # Verify error is captured
        assert 'error' in context
        assert 'API error' in context['error']
    
    def test_error_handling_in_recommendations(self, integration, mock_idle_detector):
        """Test error handling when generating recommendations."""
        # Mock error
        mock_idle_detector.identify_idle_gpus.side_effect = Exception("Detection error")
        
        recommendations = integration.get_gpu_optimization_recommendations(
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
        
        # Should return empty list on error
        assert isinstance(recommendations, list)
    
    def test_error_handling_in_explanation(self, integration, mock_workload_classifier):
        """Test error handling when explaining classification."""
        # Mock error
        mock_workload_classifier.classify_workload.side_effect = Exception("Classification error")
        
        explanation = integration.explain_workload_classification(
            instance_id='i-error-001',
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
        
        # Verify error is captured
        assert 'error' in explanation
        assert 'Classification error' in explanation['error']
    
    def test_integration_without_optional_trackers(
        self,
        mock_gpu_cost_tracker,
        mock_workload_classifier,
        mock_idle_detector,
        mock_spot_recommender
    ):
        """Test integration works without optional SageMaker and Bedrock trackers."""
        integration = AIAdvisorIntegration(
            gpu_cost_tracker=mock_gpu_cost_tracker,
            workload_classifier=mock_workload_classifier,
            idle_detector=mock_idle_detector,
            spot_recommender=mock_spot_recommender,
            sagemaker_tracker=None,
            bedrock_tracker=None
        )
        
        # Should still work
        context = integration.get_gpu_cost_context(
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
        
        assert 'gpu_costs' in context
        assert 'summary' in context
        
        recommendations = integration.get_gpu_optimization_recommendations(
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
        
        # Should have GPU recommendations but not SageMaker/Bedrock
        assert len(recommendations) > 0
        assert not any(r['type'] == 'sagemaker_idle_endpoint' for r in recommendations)
        assert not any(r['type'] == 'bedrock_model_optimization' for r in recommendations)
