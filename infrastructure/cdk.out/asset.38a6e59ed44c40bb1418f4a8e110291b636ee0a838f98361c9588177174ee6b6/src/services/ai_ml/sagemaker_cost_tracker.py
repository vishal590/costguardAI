"""
SageMaker Cost Tracker Service

Tracks SageMaker training job costs, inference endpoint costs, and notebook instance costs.
Identifies idle endpoints and recommends cost-optimized instance types.

Requirements: FR-6.1, FR-6.2, FR-6.3, FR-6.4, FR-6.5, FR-6.6
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import boto3
from decimal import Decimal
from botocore.exceptions import ClientError

from .error_handler import (
    retry_with_exponential_backoff,
    handle_cost_explorer_error,
    handle_sagemaker_error,
    handle_pricing_error,
    validate_minimum_data,
    AIMLError,
    DataNotFoundError
)


@dataclass
class JobCost:
    """Cost breakdown for a SageMaker job"""
    job_name: str
    job_type: str  # "training", "inference", "notebook"
    instance_type: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_hours: float
    compute_cost: float
    storage_cost: float
    data_transfer_cost: float
    total_cost: float


@dataclass
class SageMakerCosts:
    """Aggregated SageMaker costs"""
    date: datetime
    training_costs: float
    inference_costs: float
    notebook_costs: float
    total_cost: float
    job_breakdown: List[JobCost]


@dataclass
class EndpointMetrics:
    """Metrics for a SageMaker endpoint"""
    endpoint_name: str
    instance_type: str
    instance_count: int
    requests_per_hour: float
    avg_latency_ms: float
    cost_per_hour: float
    is_idle: bool


@dataclass
class InstanceRecommendation:
    """Instance type recommendation"""
    current_instance: str
    recommended_instance: str
    current_cost_per_hour: float
    recommended_cost_per_hour: float
    savings_per_hour: float
    savings_percent: float
    reason: str


class SageMakerCostTracker:
    """
    Tracks SageMaker costs for training jobs, inference endpoints, and notebooks.
    
    Responsibilities:
    - Track SageMaker training and inference costs
    - Identify idle endpoints
    - Recommend cost-optimized instances
    """
    
    def __init__(self, cost_explorer_client=None, sagemaker_client=None, 
                 cloudwatch_client=None, pricing_client=None, cache_manager=None):
        """Initialize SageMaker cost tracker with AWS clients"""
        self.cost_explorer = cost_explorer_client or boto3.client('ce')
        self.sagemaker = sagemaker_client or boto3.client('sagemaker')
        self.cloudwatch = cloudwatch_client or boto3.client('cloudwatch')
        self.pricing = pricing_client or boto3.client('pricing', region_name='us-east-1')
        self.cache_manager = cache_manager
    
    @retry_with_exponential_backoff(max_retries=3)
    def track_sagemaker_costs(self, start_date: datetime, end_date: datetime) -> SageMakerCosts:
        """
        Track SageMaker costs by job type.
        
        Args:
            start_date: Start date for cost tracking
            end_date: End date for cost tracking
            
        Returns:
            SageMakerCosts with breakdown by job type
            
        Requirements: FR-6.1, FR-6.2, FR-6.3, FR-6.4
        """
        # Try to get cached data first
        cache_data = None
        if self.cache_manager:
            cache_key = f"sagemaker_costs_{start_date.strftime('%Y-%m-%d')}_{end_date.strftime('%Y-%m-%d')}"
            cache_data = self.cache_manager.get(cache_key)
            if cache_data:
                return cache_data
        
        try:
            # Get all SageMaker costs from Cost Explorer
            response = self.cost_explorer.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Granularity='DAILY',
                Metrics=['UnblendedCost'],
                Filter={
                    'Dimensions': {
                        'Key': 'SERVICE',
                        'Values': ['Amazon SageMaker']
                    }
                },
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'}
                ]
            )
        except ClientError as e:
            # Handle Cost Explorer errors with fallback to cached data
            error_result = handle_cost_explorer_error(e, cache_data)
            if 'data' in error_result:
                return error_result['data']
            raise
        
        # Parse costs by job type
        training_costs = 0.0
        inference_costs = 0.0
        notebook_costs = 0.0
        job_breakdown = []
        
        for result in response.get('ResultsByTime', []):
            for group in result.get('Groups', []):
                usage_type = group['Keys'][0]
                cost = float(group['Metrics']['UnblendedCost']['Amount'])
                
                # Classify by usage type
                if 'Training' in usage_type or 'TrainingJob' in usage_type:
                    training_costs += cost
                elif 'Hosting' in usage_type or 'Endpoint' in usage_type:
                    inference_costs += cost
                elif 'Notebook' in usage_type:
                    notebook_costs += cost
        
        # Get detailed job breakdown
        job_breakdown = self._get_job_breakdown(start_date, end_date)
        
        return SageMakerCosts(
            date=start_date,
            training_costs=training_costs,
            inference_costs=inference_costs,
            notebook_costs=notebook_costs,
            total_cost=training_costs + inference_costs + notebook_costs,
            job_breakdown=job_breakdown
        )
    
    @retry_with_exponential_backoff(max_retries=3)
    def get_training_job_costs(self, job_name: str) -> JobCost:
        """
        Get costs for a specific training job.
        
        Args:
            job_name: SageMaker training job name
            
        Returns:
            JobCost with detailed cost breakdown
            
        Requirements: FR-6.1
        """
        try:
            # Get training job details
            response = self.sagemaker.describe_training_job(TrainingJobName=job_name)
        except ClientError as e:
            # Handle SageMaker errors
            error_result = handle_sagemaker_error(e)
            if isinstance(error_result, dict) and 'data' in error_result:
                return error_result['data']
            raise
        
        instance_type = response['ResourceConfig']['InstanceType']
        instance_count = response['ResourceConfig']['InstanceCount']
        start_time = response['TrainingStartTime']
        end_time = response.get('TrainingEndTime')
        
        # Calculate duration
        if end_time:
            duration = (end_time - start_time).total_seconds() / 3600
        else:
            duration = (datetime.now() - start_time).total_seconds() / 3600
        
        # Get instance pricing
        cost_per_hour = self._get_instance_price(instance_type, 'training')
        compute_cost = cost_per_hour * instance_count * duration
        
        # Estimate storage and data transfer costs (typically 5-10% of compute)
        storage_cost = compute_cost * 0.05
        data_transfer_cost = compute_cost * 0.03
        
        return JobCost(
            job_name=job_name,
            job_type='training',
            instance_type=instance_type,
            start_time=start_time,
            end_time=end_time,
            duration_hours=duration,
            compute_cost=compute_cost,
            storage_cost=storage_cost,
            data_transfer_cost=data_transfer_cost,
            total_cost=compute_cost + storage_cost + data_transfer_cost
        )
    
    @retry_with_exponential_backoff(max_retries=3)
    def get_endpoint_costs(self, endpoint_name: str, start_date: datetime, 
                          end_date: datetime) -> JobCost:
        """
        Get costs for a specific inference endpoint.
        
        Args:
            endpoint_name: SageMaker endpoint name
            start_date: Start date for cost calculation
            end_date: End date for cost calculation
            
        Returns:
            JobCost with detailed cost breakdown
            
        Requirements: FR-6.2
        """
        try:
            # Get endpoint details
            response = self.sagemaker.describe_endpoint(EndpointName=endpoint_name)
            endpoint_config = self.sagemaker.describe_endpoint_config(
                EndpointConfigName=response['EndpointConfigName']
            )
        except ClientError as e:
            # Handle SageMaker errors
            error_result = handle_sagemaker_error(e)
            if isinstance(error_result, dict) and 'data' in error_result:
                return error_result['data']
            raise
        
        # Get instance details from first production variant
        variant = endpoint_config['ProductionVariants'][0]
        instance_type = variant['InstanceType']
        instance_count = variant['InitialInstanceCount']
        
        # Calculate duration
        duration = (end_date - start_date).total_seconds() / 3600
        
        # Get instance pricing
        cost_per_hour = self._get_instance_price(instance_type, 'hosting')
        compute_cost = cost_per_hour * instance_count * duration
        
        # Estimate storage and data transfer costs
        storage_cost = compute_cost * 0.02
        data_transfer_cost = compute_cost * 0.05
        
        return JobCost(
            job_name=endpoint_name,
            job_type='inference',
            instance_type=instance_type,
            start_time=start_date,
            end_time=end_date,
            duration_hours=duration,
            compute_cost=compute_cost,
            storage_cost=storage_cost,
            data_transfer_cost=data_transfer_cost,
            total_cost=compute_cost + storage_cost + data_transfer_cost
        )
    
    def identify_idle_endpoints(self, threshold: int = 10) -> List[EndpointMetrics]:
        """
        Identify endpoints with <threshold requests/hour.
        
        Args:
            threshold: Minimum requests per hour (default: 10)
            
        Returns:
            List of idle endpoint metrics
            
        Requirements: FR-6.6
        """
        idle_endpoints = []
        
        # List all endpoints
        paginator = self.sagemaker.get_paginator('list_endpoints')
        for page in paginator.paginate(StatusEquals='InService'):
            for endpoint in page['Endpoints']:
                endpoint_name = endpoint['EndpointName']
                
                # Get endpoint metrics
                metrics = self._get_endpoint_metrics(endpoint_name)
                
                if metrics.requests_per_hour < threshold:
                    metrics.is_idle = True
                    idle_endpoints.append(metrics)
        
        return idle_endpoints
    
    def recommend_instance_types(self, job_type: str, current_instance: str, 
                                 workload_characteristics: Optional[Dict] = None) -> List[InstanceRecommendation]:
        """
        Recommend cost-optimized instance types.
        
        Args:
            job_type: "training" or "inference"
            current_instance: Current instance type (e.g., "ml.p3.2xlarge")
            workload_characteristics: Optional workload info (memory, compute requirements)
            
        Returns:
            List of instance recommendations sorted by savings
            
        Requirements: FR-6.5
        """
        recommendations = []
        
        # Get current instance price
        current_price = self._get_instance_price(current_instance, job_type)
        
        # Define alternative instances based on job type
        if job_type == 'training':
            alternatives = self._get_training_alternatives(current_instance)
        else:
            alternatives = self._get_inference_alternatives(current_instance)
        
        # Calculate savings for each alternative
        for alt_instance in alternatives:
            alt_price = self._get_instance_price(alt_instance, job_type)
            
            if alt_price < current_price:
                savings = current_price - alt_price
                savings_percent = (savings / current_price) * 100
                
                reason = self._get_recommendation_reason(
                    current_instance, alt_instance, job_type
                )
                
                recommendations.append(InstanceRecommendation(
                    current_instance=current_instance,
                    recommended_instance=alt_instance,
                    current_cost_per_hour=current_price,
                    recommended_cost_per_hour=alt_price,
                    savings_per_hour=savings,
                    savings_percent=savings_percent,
                    reason=reason
                ))
        
        # Sort by savings (highest first)
        recommendations.sort(key=lambda x: x.savings_per_hour, reverse=True)
        
        return recommendations
    
    def _get_job_breakdown(self, start_date: datetime, end_date: datetime) -> List[JobCost]:
        """Get detailed breakdown of all jobs in date range"""
        job_breakdown = []
        
        # Get training jobs
        try:
            paginator = self.sagemaker.get_paginator('list_training_jobs')
            for page in paginator.paginate(
                CreationTimeAfter=start_date,
                CreationTimeBefore=end_date
            ):
                for job in page['TrainingJobSummaries']:
                    try:
                        job_cost = self.get_training_job_costs(job['TrainingJobName'])
                        job_breakdown.append(job_cost)
                    except Exception:
                        # Skip jobs we can't get details for
                        pass
        except Exception:
            # If listing fails, continue without training jobs
            pass
        
        return job_breakdown
    
    def _get_endpoint_metrics(self, endpoint_name: str) -> EndpointMetrics:
        """Get CloudWatch metrics for an endpoint"""
        # Get endpoint details
        response = self.sagemaker.describe_endpoint(EndpointName=endpoint_name)
        endpoint_config = self.sagemaker.describe_endpoint_config(
            EndpointConfigName=response['EndpointConfigName']
        )
        
        variant = endpoint_config['ProductionVariants'][0]
        instance_type = variant['InstanceType']
        instance_count = variant['InitialInstanceCount']
        
        # Get invocation metrics from CloudWatch
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=1)
        
        try:
            invocations_response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/SageMaker',
                MetricName='Invocations',
                Dimensions=[
                    {'Name': 'EndpointName', 'Value': endpoint_name},
                    {'Name': 'VariantName', 'Value': variant['VariantName']}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Sum']
            )
            
            requests_per_hour = 0.0
            if invocations_response['Datapoints']:
                requests_per_hour = invocations_response['Datapoints'][0]['Sum']
        except Exception:
            requests_per_hour = 0.0
        
        # Get latency metrics
        try:
            latency_response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/SageMaker',
                MetricName='ModelLatency',
                Dimensions=[
                    {'Name': 'EndpointName', 'Value': endpoint_name},
                    {'Name': 'VariantName', 'Value': variant['VariantName']}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Average']
            )
            
            avg_latency_ms = 0.0
            if latency_response['Datapoints']:
                avg_latency_ms = latency_response['Datapoints'][0]['Average']
        except Exception:
            avg_latency_ms = 0.0
        
        # Get instance pricing
        cost_per_hour = self._get_instance_price(instance_type, 'hosting') * instance_count
        
        return EndpointMetrics(
            endpoint_name=endpoint_name,
            instance_type=instance_type,
            instance_count=instance_count,
            requests_per_hour=requests_per_hour,
            avg_latency_ms=avg_latency_ms,
            cost_per_hour=cost_per_hour,
            is_idle=False
        )
    
    def _get_instance_price(self, instance_type: str, job_type: str) -> float:
        """
        Get hourly price for a SageMaker instance type.
        
        Args:
            instance_type: Instance type (e.g., "ml.p3.2xlarge")
            job_type: "training" or "hosting"
            
        Returns:
            Hourly price in USD
        """
        # Map job type to SageMaker usage type
        usage_type_map = {
            'training': 'TrainingJob',
            'hosting': 'Hosting'
        }
        
        try:
            # Query AWS Pricing API
            response = self.pricing.get_products(
                ServiceCode='AmazonSageMaker',
                Filters=[
                    {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                    {'Type': 'TERM_MATCH', 'Field': 'usagetype', 'Value': usage_type_map.get(job_type, 'TrainingJob')}
                ],
                MaxResults=1
            )
            
            if response['PriceList']:
                import json
                price_data = json.loads(response['PriceList'][0])
                on_demand = price_data['terms']['OnDemand']
                price_dimensions = list(on_demand.values())[0]['priceDimensions']
                price_per_hour = float(list(price_dimensions.values())[0]['pricePerUnit']['USD'])
                return price_per_hour
        except ClientError as e:
            # Handle pricing API errors with fallback
            estimated_price = self._get_estimated_price(instance_type, job_type)
            error_result = handle_pricing_error(e, estimated_price)
            if 'price' in error_result:
                return error_result['price']
        except Exception:
            pass
        
        # Fallback to estimated prices if API fails
        return self._get_estimated_price(instance_type, job_type)
    
    def _get_estimated_price(self, instance_type: str, job_type: str) -> float:
        """Fallback estimated prices for common instance types"""
        # Estimated prices (USD per hour) - training prices
        training_prices = {
            'ml.m5.large': 0.115,
            'ml.m5.xlarge': 0.23,
            'ml.m5.2xlarge': 0.46,
            'ml.p3.2xlarge': 3.825,
            'ml.p3.8xlarge': 14.688,
            'ml.p3.16xlarge': 28.152,
            'ml.p4d.24xlarge': 37.688,
            'ml.g4dn.xlarge': 0.736,
            'ml.g4dn.2xlarge': 1.052,
            'ml.g5.xlarge': 1.408,
            'ml.g5.2xlarge': 1.515,
        }
        
        # Hosting prices are typically 20% higher
        if job_type == 'hosting':
            base_price = training_prices.get(instance_type, 1.0)
            return base_price * 1.2
        
        return training_prices.get(instance_type, 1.0)
    
    def _get_training_alternatives(self, current_instance: str) -> List[str]:
        """Get alternative instance types for training"""
        # Map instance families to alternatives
        if 'p3' in current_instance:
            return ['ml.g4dn.xlarge', 'ml.g5.xlarge']
        elif 'p4' in current_instance:
            return ['ml.p3.8xlarge', 'ml.g5.2xlarge']
        elif 'g4dn' in current_instance:
            return ['ml.m5.xlarge', 'ml.m5.2xlarge']
        elif 'g5' in current_instance:
            return ['ml.g4dn.xlarge', 'ml.m5.2xlarge']
        else:
            return ['ml.m5.xlarge', 'ml.g4dn.xlarge']
    
    def _get_inference_alternatives(self, current_instance: str) -> List[str]:
        """Get alternative instance types for inference"""
        # For inference, recommend smaller instances
        if 'p3' in current_instance or 'p4' in current_instance:
            return ['ml.g4dn.xlarge', 'ml.m5.xlarge']
        elif 'g4dn' in current_instance or 'g5' in current_instance:
            return ['ml.m5.large', 'ml.m5.xlarge']
        else:
            return ['ml.m5.large', 'ml.t3.medium']
    
    def _get_recommendation_reason(self, current: str, recommended: str, job_type: str) -> str:
        """Generate explanation for recommendation"""
        if 'p3' in current or 'p4' in current:
            if 'g4dn' in recommended or 'g5' in recommended:
                return "G-series instances offer better price/performance for most workloads"
            elif 'm5' in recommended:
                return "CPU instances sufficient for inference workloads"
        elif 'g4dn' in current or 'g5' in current:
            if 'm5' in recommended:
                return "CPU instances more cost-effective for low GPU utilization"
        
        return "Lower-cost alternative with similar performance"
