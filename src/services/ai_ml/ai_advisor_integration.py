"""
AI Advisor Integration for GPU Cost Management.

This module extends Phase 4 AI Advisor to provide GPU-specific cost insights:
1. GPU cost context for AI Advisor queries
2. GPU optimization recommendations
3. Natural language explanations of workload classifications
4. GPU-specific cost analysis and insights

Requirements: IR-2.4
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from .gpu_cost_tracker import GPUCostTracker
from .workload_classifier import WorkloadClassifier
from .idle_detector import IdleGPUDetector
from .spot_instance_recommender import SpotInstanceRecommender
from .sagemaker_cost_tracker import SageMakerCostTracker
from .bedrock_cost_tracker import BedrockCostTracker

logger = logging.getLogger(__name__)


class AIAdvisorIntegration:
    """
    Extends AI Advisor with GPU cost management capabilities.
    
    Provides GPU-specific context, recommendations, and insights for
    the AI Advisor to answer GPU cost questions and provide optimization
    recommendations.
    """
    
    def __init__(
        self,
        gpu_cost_tracker: GPUCostTracker,
        workload_classifier: WorkloadClassifier,
        idle_detector: IdleGPUDetector,
        spot_recommender: SpotInstanceRecommender,
        sagemaker_tracker: Optional[SageMakerCostTracker] = None,
        bedrock_tracker: Optional[BedrockCostTracker] = None
    ):
        """
        Initialize AI Advisor integration.
        
        Args:
            gpu_cost_tracker: GPU cost tracking service
            workload_classifier: Workload classification service
            idle_detector: Idle GPU detection service
            spot_recommender: Spot instance recommendation service
            sagemaker_tracker: Optional SageMaker cost tracking service
            bedrock_tracker: Optional Bedrock cost tracking service
        """
        self.gpu_cost_tracker = gpu_cost_tracker
        self.workload_classifier = workload_classifier
        self.idle_detector = idle_detector
        self.spot_recommender = spot_recommender
        self.sagemaker_tracker = sagemaker_tracker
        self.bedrock_tracker = bedrock_tracker
        self.last_recommendation_report = None
        
        logger.info("AIAdvisorIntegration initialized")
    
    def get_gpu_cost_context(
        self,
        start_date: str,
        end_date: str,
        include_recommendations: bool = True
    ) -> Dict[str, Any]:
        """
        Get comprehensive GPU cost context for AI Advisor.
        
        This provides all GPU-related cost data that the AI Advisor
        can use to answer questions about GPU costs, workloads, and
        optimization opportunities.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            include_recommendations: Whether to include optimization recommendations
            
        Returns:
            Dictionary containing GPU cost context with:
            - gpu_costs: GPU cost breakdown by workload type
            - workload_distribution: Distribution of training/inference/idle workloads
            - idle_gpus: List of idle GPU instances
            - optimization_opportunities: List of optimization recommendations
            - cost_trends: GPU cost trends over time
        """
        logger.info(f"Getting GPU cost context for {start_date} to {end_date}")
        
        context = {
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'gpu_costs': {},
            'workload_distribution': {},
            'idle_gpus': [],
            'optimization_opportunities': [],
            'cost_trends': {},
            'summary': {}, 'data_contract': 'gpu_advisor_context_v2',
            'workload_identity_verified': False, 'resource_actions': 0
        }
        
        try:
            # Get GPU costs
            gpu_costs = self.gpu_cost_tracker.collect_gpu_costs(
                start_date, end_date
            )
            
            observed_total = self.gpu_cost_tracker.last_observation_report.get('observed_total')
            costs_by_instance_type = {}
            for row in gpu_costs:
                costs_by_instance_type[row.instance_type] = costs_by_instance_type.get(row.instance_type, 0.0)+row.cost
            context['gpu_costs'] = {'by_workload': {'training': None, 'inference': None, 'idle': None,
                'unknown': observed_total, 'total': observed_total}, 'by_instance_type': costs_by_instance_type,
                'total_gpu_hours': None, 'data_quality': self.gpu_cost_tracker.last_observation_report}
            context['workload_distribution'] = {'status': 'unavailable', 'reason': 'Type-level costs do not establish workload or device-hour attribution'}

            # Get idle GPUs
            idle_gpus = self.idle_detector.identify_idle_gpus(
                start_date, end_date, threshold=10.0
            )
            
            context['gpu_observation_report'] = self.idle_detector.last_observation_report
            context['idle_gpus'] = [
                {
                    'instance_id': gpu.instance_id,
                    'instance_type': gpu.instance_type,
                    'idle_hours': gpu.idle_hours,
                    'wasted_cost': gpu.wasted_cost,
                    'utilization': gpu.utilization,
                    'recommendation': gpu.recommendation
                }
                for gpu in idle_gpus
            ]
            
            # Get optimization recommendations if requested
            if include_recommendations:
                context['optimization_opportunities'] = self._get_optimization_recommendations(
                    gpu_costs, idle_gpus
                )
            
            # Generate summary
            context['summary'] = self._generate_summary(context)
            
            logger.info(f"Generated GPU cost context with {len(gpu_costs)} cost entries")
            return context
            
        except Exception as e:
            logger.error(f"Error getting GPU cost context: {e}", exc_info=True)
            raise RuntimeError('GPU advisor observations are unavailable') from e
    
    def get_gpu_optimization_recommendations(
        self,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        Generate GPU optimization recommendations for AI Advisor.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of optimization recommendations with:
            - type: Type of recommendation (idle_gpu, spot_instance, etc.)
            - priority: Priority level (high, medium, low)
            - potential_savings: Unavailable; no verified monetary attribution
            - description: Natural language description
            - action_items: Specific actions to take
        """
        logger.info(f"Generating GPU optimization recommendations for {start_date} to {end_date}")
        
        recommendations = []
        self.last_recommendation_report = {'data_contract': 'ai_ml_advisor_review_v2',
            'status': 'reading', 'sources': {}, 'monetary_savings_status': 'unavailable',
            'workload_inactivity_verified': False, 'resource_actions': 0}
        sources = self.last_recommendation_report['sources']
        try:
            idle_gpus = self.idle_detector.identify_idle_gpus(start_date, end_date, threshold=10.0)
            sources['gpu'] = {'status': 'observed', 'observation_report': self.idle_detector.last_observation_report}
            if idle_gpus:
                recommendations.append({'type': 'gpu_low_usage_review', 'priority': 'medium',
                    'potential_savings': None, 'observation_report': self.idle_detector.last_observation_report,
                    'description': f'{len(idle_gpus)} GPU instances matched configured rules in a bounded window. Inactivity and savings are unverified.',
                    'action_items': [f'Review workload requirements for {gpu.instance_id}' for gpu in idle_gpus[:3]],
                    'affected_instances': len(idle_gpus), 'workload_inactivity_verified': False})
            if self.sagemaker_tracker:
                endpoints = self.sagemaker_tracker.identify_idle_endpoints(threshold=10)
                sources['sagemaker'] = {'status': 'observed', 'observation_report': self.sagemaker_tracker.last_idle_report,
                    'window_scope': 'adapter_current_recent_window_not_requested_billing_dates'}
                if endpoints:
                    recommendations.append({'type': 'sagemaker_low_usage_review', 'priority': 'medium',
                        'potential_savings': None, 'observation_report': self.sagemaker_tracker.last_idle_report,
                        'description': f'{len(endpoints)} endpoints matched bounded fully observed low-invocation rules; workload inactivity and savings are unverified.',
                        'action_items': [f'Review workload requirements for endpoint {ep.endpoint_name}' for ep in endpoints[:3]],
                        'affected_instances': len(endpoints), 'workload_inactivity_verified': False})
            else:
                sources['sagemaker'] = {'status': 'not_configured'}
            if self.bedrock_tracker:
                self.bedrock_tracker.track_bedrock_costs(datetime.strptime(start_date, '%Y-%m-%d'), datetime.strptime(end_date, '%Y-%m-%d'))
                sources['bedrock'] = {'status': 'observed', 'cost_observations': self.bedrock_tracker.last_cost_report,
                    'model_recommendations_status': 'unavailable_without_verified_attribution_and_quality_comparison'}
            else:
                sources['bedrock'] = {'status': 'not_configured'}
            self.last_recommendation_report.update({'status': 'observed', 'recommendations': recommendations,
                'selection_scope': 'bounded_configured_evidence_not_complete_inventory'})
            return recommendations
        except Exception as error:
            # Preserve completed source provenance, but never report a failed review as no opportunities.
            self.last_recommendation_report.update({'status': 'unavailable', 'recommendations': None,
                'reason': 'One or more configured observation sources could not be read'})
            raise RuntimeError('AI/ML advisor review observations are unavailable') from error

    def explain_workload_classification(
        self,
        instance_id: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        Provide natural language explanation of workload classification.
        
        Args:
            instance_id: EC2 instance ID
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            Dictionary containing:
            - classification: Workload type (training, inference, idle)
            - confidence: Unavailable; declarations are not calibrated identity estimates
            - explanation: Natural language explanation
            - metrics: Supporting metrics
            - recommendations: Specific recommendations for this workload
        """
        logger.info(f"Explaining workload classification for {instance_id}")
        
        try:
            # Get classification
            classification = self.workload_classifier.classify_workload(
                instance_id, start_date, end_date
            )
            
            # Generate natural language explanation
            explanation = self._generate_classification_explanation(classification)
            
            # Get recommendations based on classification
            recommendations = self._get_workload_recommendations(
                instance_id, classification
            )
            
            return {
                'instance_id': instance_id,
                'classification': classification.workload_type,
                'data_contract': 'classification_explanation_v2',
                'confidence': None, 'confidence_method': 'unavailable',
                'workload_identity_verified': False, 'manual_label': classification.manual_label,
                'utilization_pattern_label': classification.utilization_pattern_label,
                'data_quality': classification.data_quality,
                'explanation': explanation,
                'metrics': {
                    'avg_utilization': classification.gpu_utilization_avg,
                    'classification_method': classification.classification_method,
                    'timestamp': classification.timestamp
                },
                'recommendations': recommendations
            }
            
        except Exception as e:
            logger.error(f"Error explaining workload classification: {e}", exc_info=True)
            raise RuntimeError('Workload declaration or GPU evidence is unavailable') from e

    def _get_optimization_recommendations(
        self,
        gpu_costs: List[Any],
        idle_gpus: List[Any]
    ) -> List[Dict[str, Any]]:
        """Generate optimization recommendations from GPU cost data."""
        recommendations = []
        
        if idle_gpus:
            recommendations.append({'type': 'gpu_low_usage_review', 'priority': 'medium', 'savings': None,
                'description': f'Review {len(idle_gpus)} observed GPU rule matches; workload inactivity and monetary savings are unverified.'})

        # No fixed spot discount is inferred from aggregate observed charges.

        return recommendations
    
    def _generate_summary(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary of GPU cost context."""
        gpu_costs = context.get('gpu_costs', {})
        idle_gpus = context.get('idle_gpus', [])
        
        total_cost = gpu_costs.get('by_workload', {}).get('total')
        idle_cost = gpu_costs.get('by_workload', {}).get('idle')
        
        values = [item.get('potential_savings', item.get('savings')) for item in context.get('optimization_opportunities', [])]
        complete = bool(values) and all(value is not None for value in values)
        optimization_potential = sum(values) if complete else None
        observed_opportunity = sum(value for value in values if value is not None) if any(value is not None for value in values) else None
        return {
            'total_gpu_cost': total_cost,
            'idle_gpu_count': len(idle_gpus),
            'total_wasted_cost': None, 'gpu_monetary_status': 'unavailable',
            'idle_cost_percent': None,
            'optimization_potential': optimization_potential,
            'optimization_potential_complete': complete, 'observed_partial_opportunity': observed_opportunity
        }
    
    def _generate_classification_explanation(self, classification: Any) -> str:
        label = classification.workload_type
        source = classification.classification_method
        pattern = classification.utilization_pattern_label
        return (f'Declared workload label: {label}; source: {source}. GPU pattern observation: {pattern}. '
                'Labels are operator assertions and utilization does not establish training/inference identity. '
                'No calibrated confidence or workload inactivity guarantee is available.')

    def _get_workload_recommendations(self, instance_id: str, classification: Any) -> List[str]:
        return ['Review the declared label and its source before using it for allocation or capacity decisions.',
                'GPU patterns and declared labels do not authorize resource changes or establish monetary savings.']
