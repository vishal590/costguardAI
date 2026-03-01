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
from datetime import datetime, timedelta
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
            'summary': {}
        }
        
        try:
            # Get GPU costs
            gpu_costs = self.gpu_cost_tracker.collect_gpu_costs(
                start_date, end_date
            )
            
            # Calculate cost breakdown by workload type
            costs_by_workload = {
                'training': 0.0,
                'inference': 0.0,
                'idle': 0.0,
                'total': 0.0
            }
            
            costs_by_instance_type = {}
            gpu_hours_by_workload = {
                'training': 0.0,
                'inference': 0.0,
                'idle': 0.0
            }
            
            for cost in gpu_costs:
                workload = cost.workload_type
                costs_by_workload[workload] += cost.cost
                costs_by_workload['total'] += cost.cost
                gpu_hours_by_workload[workload] += cost.gpu_hours
                
                if cost.instance_type not in costs_by_instance_type:
                    costs_by_instance_type[cost.instance_type] = 0.0
                costs_by_instance_type[cost.instance_type] += cost.cost
            
            context['gpu_costs'] = {
                'by_workload': costs_by_workload,
                'by_instance_type': costs_by_instance_type,
                'total_gpu_hours': sum(gpu_hours_by_workload.values())
            }
            
            # Calculate workload distribution
            total_hours = sum(gpu_hours_by_workload.values())
            if total_hours > 0:
                context['workload_distribution'] = {
                    'training_percent': (gpu_hours_by_workload['training'] / total_hours) * 100,
                    'inference_percent': (gpu_hours_by_workload['inference'] / total_hours) * 100,
                    'idle_percent': (gpu_hours_by_workload['idle'] / total_hours) * 100
                }
            
            # Get idle GPUs
            idle_gpus = self.idle_detector.identify_idle_gpus(
                start_date, end_date, threshold=10.0
            )
            
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
            context['error'] = str(e)
            return context
    
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
            - potential_savings: Estimated cost savings
            - description: Natural language description
            - action_items: Specific actions to take
        """
        logger.info(f"Generating GPU optimization recommendations for {start_date} to {end_date}")
        
        recommendations = []
        
        try:
            # Get idle GPUs
            idle_gpus = self.idle_detector.identify_idle_gpus(
                start_date, end_date, threshold=10.0
            )
            
            if idle_gpus:
                total_wasted = sum(gpu.wasted_cost for gpu in idle_gpus)
                
                recommendations.append({
                    'type': 'idle_gpu',
                    'priority': 'high' if total_wasted > 100 else 'medium',
                    'potential_savings': total_wasted,
                    'description': f"Found {len(idle_gpus)} idle GPU instances wasting ${total_wasted:.2f}. "
                                 f"These GPUs have utilization below 10% and should be stopped or terminated.",
                    'action_items': [
                        f"Stop or terminate {gpu.instance_id} ({gpu.instance_type}) - saving ${gpu.wasted_cost:.2f}"
                        for gpu in idle_gpus[:3]  # Top 3
                    ],
                    'affected_instances': len(idle_gpus)
                })
            
            # Get spot instance recommendations for training workloads
            gpu_costs = self.gpu_cost_tracker.collect_gpu_costs(
                start_date, end_date, workload_type='training'
            )
            
            if gpu_costs:
                # Get spot recommendations for training instances
                total_spot_savings = 0.0
                spot_suitable_count = 0
                
                for cost in gpu_costs:
                    try:
                        spot_recs = self.spot_recommender.recommend_spot_instances(
                            cost.instance_id
                        )
                        
                        for rec in spot_recs:
                            if rec.suitable:
                                total_spot_savings += rec.savings
                                spot_suitable_count += 1
                    except Exception as e:
                        logger.debug(f"Could not get spot recommendation for {cost.instance_id}: {e}")
                
                if spot_suitable_count > 0:
                    recommendations.append({
                        'type': 'spot_instance',
                        'priority': 'high' if total_spot_savings > 500 else 'medium',
                        'potential_savings': total_spot_savings,
                        'description': f"Found {spot_suitable_count} training workloads that could use spot instances, "
                                     f"saving up to ${total_spot_savings:.2f} (up to 70% discount).",
                        'action_items': [
                            "Review training workloads for spot instance compatibility",
                            "Implement checkpointing for fault tolerance",
                            "Switch suitable training jobs to spot instances"
                        ],
                        'affected_instances': spot_suitable_count
                    })
            
            # Get SageMaker recommendations if available
            if self.sagemaker_tracker:
                try:
                    idle_endpoints = self.sagemaker_tracker.identify_idle_endpoints(threshold=10)
                    
                    if idle_endpoints:
                        total_endpoint_waste = sum(ep.cost_per_hour * 24 * 30 for ep in idle_endpoints)
                        
                        recommendations.append({
                            'type': 'sagemaker_idle_endpoint',
                            'priority': 'high' if total_endpoint_waste > 200 else 'medium',
                            'potential_savings': total_endpoint_waste,
                            'description': f"Found {len(idle_endpoints)} idle SageMaker endpoints with <10 requests/hour, "
                                         f"wasting approximately ${total_endpoint_waste:.2f}/month.",
                            'action_items': [
                                f"Scale down or delete endpoint {ep.endpoint_name} - saving ${ep.cost_per_hour * 24 * 30:.2f}/month"
                                for ep in idle_endpoints[:3]  # Top 3
                            ],
                            'affected_instances': len(idle_endpoints)
                        })
                except Exception as e:
                    logger.debug(f"Could not get SageMaker recommendations: {e}")
            
            # Get Bedrock recommendations if available
            if self.bedrock_tracker:
                try:
                    # Get Bedrock costs for the period
                    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                    
                    bedrock_costs = self.bedrock_tracker.track_bedrock_costs(
                        start_dt, end_dt
                    )
                    
                    for costs in bedrock_costs:
                        if costs.invocations > 100:  # Only recommend for significant usage
                            usage_pattern = {
                                'avg_input_tokens': costs.input_tokens / costs.invocations,
                                'avg_output_tokens': costs.output_tokens / costs.invocations
                            }
                            
                            model_recs = self.bedrock_tracker.recommend_cost_optimized_models(
                                costs.model_id, usage_pattern
                            )
                            
                            if model_recs:
                                best_rec = model_recs[0]
                                monthly_savings = costs.total_cost * (best_rec.savings_percent / 100.0) * 30
                                
                                if monthly_savings > 50:  # Only recommend if significant savings
                                    recommendations.append({
                                        'type': 'bedrock_model_optimization',
                                        'priority': 'medium',
                                        'potential_savings': monthly_savings,
                                        'description': f"Consider switching from {costs.model_id} to {best_rec.recommended_model} "
                                                     f"for {best_rec.savings_percent:.1f}% cost savings.",
                                        'action_items': [
                                            f"Evaluate {best_rec.recommended_model} for your use case",
                                            "Test model performance and quality",
                                            f"Switch to save approximately ${monthly_savings:.2f}/month"
                                        ],
                                        'affected_models': 1
                                    })
                except Exception as e:
                    logger.debug(f"Could not get Bedrock recommendations: {e}")
            
            # Sort by potential savings (highest first)
            recommendations.sort(key=lambda x: x['potential_savings'], reverse=True)
            
            logger.info(f"Generated {len(recommendations)} optimization recommendations")
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating optimization recommendations: {e}", exc_info=True)
            return []
    
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
            - confidence: Confidence score (0-1)
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
                'confidence': classification.confidence,
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
            return {
                'instance_id': instance_id,
                'error': str(e),
                'explanation': f"Unable to classify workload for {instance_id}: {str(e)}"
            }
    
    def _get_optimization_recommendations(
        self,
        gpu_costs: List[Any],
        idle_gpus: List[Any]
    ) -> List[Dict[str, Any]]:
        """Generate optimization recommendations from GPU cost data."""
        recommendations = []
        
        # Idle GPU recommendations
        if idle_gpus:
            total_wasted = sum(gpu.wasted_cost for gpu in idle_gpus)
            recommendations.append({
                'type': 'idle_gpu',
                'priority': 'high',
                'savings': total_wasted,
                'description': f"Stop {len(idle_gpus)} idle GPU instances to save ${total_wasted:.2f}"
            })
        
        # Spot instance recommendations for training workloads
        training_costs = [c for c in gpu_costs if c.workload_type == 'training']
        if training_costs:
            estimated_spot_savings = sum(c.cost * 0.7 for c in training_costs)  # Up to 70% savings
            recommendations.append({
                'type': 'spot_instance',
                'priority': 'medium',
                'savings': estimated_spot_savings,
                'description': f"Use spot instances for training to save up to ${estimated_spot_savings:.2f}"
            })
        
        return recommendations
    
    def _generate_summary(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary of GPU cost context."""
        gpu_costs = context.get('gpu_costs', {})
        idle_gpus = context.get('idle_gpus', [])
        
        total_cost = gpu_costs.get('by_workload', {}).get('total', 0.0)
        idle_cost = gpu_costs.get('by_workload', {}).get('idle', 0.0)
        
        # Calculate optimization potential from recommendations
        optimization_potential = 0.0
        for rec in context.get('optimization_opportunities', []):
            # Handle both 'potential_savings' and 'savings' keys
            optimization_potential += rec.get('potential_savings', rec.get('savings', 0.0))
        
        return {
            'total_gpu_cost': total_cost,
            'idle_gpu_count': len(idle_gpus),
            'total_wasted_cost': sum(gpu['wasted_cost'] for gpu in idle_gpus),
            'idle_cost_percent': (idle_cost / total_cost * 100) if total_cost > 0 else 0,
            'optimization_potential': optimization_potential
        }
    
    def _generate_classification_explanation(self, classification: Any) -> str:
        """Generate natural language explanation of workload classification."""
        workload_type = classification.workload_type
        confidence = classification.confidence
        avg_util = classification.gpu_utilization_avg
        method = classification.classification_method
        
        # Base explanation
        if workload_type == 'training':
            explanation = (
                f"This GPU instance is classified as a **training workload** with "
                f"{confidence*100:.0f}% confidence. "
                f"The average GPU utilization is {avg_util:.1f}%, which indicates "
                f"sustained high GPU usage typical of model training."
            )
        elif workload_type == 'inference':
            explanation = (
                f"This GPU instance is classified as an **inference workload** with "
                f"{confidence*100:.0f}% confidence. "
                f"The average GPU utilization is {avg_util:.1f}%, with frequent spikes "
                f"typical of serving inference requests."
            )
        else:  # idle
            explanation = (
                f"This GPU instance is classified as **idle** with "
                f"{confidence*100:.0f}% confidence. "
                f"The average GPU utilization is only {avg_util:.1f}%, indicating "
                f"the GPU is not being actively used."
            )
        
        # Add method information
        if method == 'manual-tag':
            explanation += " This classification was set manually via EC2 tags."
        else:
            explanation += " This classification was determined automatically from CloudWatch GPU metrics."
        
        return explanation
    
    def _get_workload_recommendations(
        self,
        instance_id: str,
        classification: Any
    ) -> List[str]:
        """Get recommendations based on workload classification."""
        recommendations = []
        
        if classification.workload_type == 'idle':
            recommendations.append(
                f"Consider stopping or terminating this idle GPU instance to save costs"
            )
            recommendations.append(
                f"If needed occasionally, use auto-scaling to start/stop on demand"
            )
        
        elif classification.workload_type == 'training':
            recommendations.append(
                f"Consider using spot instances for training to save up to 70% on costs"
            )
            recommendations.append(
                f"Implement checkpointing to handle potential spot interruptions"
            )
        
        elif classification.workload_type == 'inference':
            recommendations.append(
                f"Monitor request patterns and scale down during low-traffic periods"
            )
            recommendations.append(
                f"Consider using auto-scaling based on request volume"
            )
        
        return recommendations
