"""
Spot Instance Recommender for AI/ML workloads.

This module identifies training workloads suitable for spot instances,
calculates potential savings, assesses interruption risk, and generates
what-if scenarios for cost optimization.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import boto3
from decimal import Decimal
from botocore.exceptions import ClientError

from .error_handler import (
    retry_with_exponential_backoff,
    handle_pricing_error,
    AIMLError,
    DataNotFoundError
)


@dataclass
class SpotRecommendation:
    """Spot instance recommendation with savings and risk assessment."""
    workload_id: str
    current_instance: str
    current_cost: float
    recommended_spot_instance: str
    spot_cost: float
    savings: float
    savings_percent: float
    interruption_risk: float  # 0-1
    suitable: bool
    reason: str


@dataclass
class SpotSavings:
    """Spot instance savings calculation."""
    current_instance: str
    spot_instance: str
    on_demand_price: float
    spot_price: float
    savings_per_hour: float
    savings_percent: float
    estimated_monthly_savings: float


@dataclass
class WhatIfScenario:
    """What-if scenario for spot instance usage."""
    scenario_name: str
    workload_id: str
    instance_type: str
    spot_usage_percent: float  # 0-100
    estimated_savings: float
    estimated_interruptions: int
    recommendation: str


class SpotInstanceRecommender:
    """Recommends spot instances for training workloads."""
    
    def __init__(self, region: str = 'us-east-1', pricing_client=None, ec2_client=None, cloudwatch_client=None):
        """Initialize spot instance recommender."""
        self.region = region
        self.ec2_client = ec2_client or boto3.client('ec2', region_name=region)
        self.pricing_client = pricing_client or boto3.client('pricing', region_name='us-east-1')
        self.cloudwatch_client = cloudwatch_client or boto3.client('cloudwatch', region_name=region)
        
        # Spot suitability criteria
        self.min_training_duration = 1.0  # hours
        self.max_interruption_tolerance = 0.15  # 15%
        
    def recommend_spot_instances(self, workload_id: str) -> List[SpotRecommendation]:
        """
        Recommend spot instances for a training workload.
        
        Args:
            workload_id: ID of the workload (instance ID or job ID)
            
        Returns:
            List of spot instance recommendations
        """
        # Get workload metadata
        workload_metadata = self._get_workload_metadata(workload_id)
        
        if not workload_metadata:
            return []
        
        current_instance = workload_metadata.get('instance_type')
        workload_type = workload_metadata.get('workload_type')
        
        # Check if workload is suitable for spot
        is_suitable, reason = self._is_spot_suitable(workload_metadata)
        
        if not is_suitable:
            return [SpotRecommendation(
                workload_id=workload_id,
                current_instance=current_instance,
                current_cost=0.0,
                recommended_spot_instance=current_instance,
                spot_cost=0.0,
                savings=0.0,
                savings_percent=0.0,
                interruption_risk=0.0,
                suitable=False,
                reason=reason
            )]
        
        # Get current instance pricing
        on_demand_price = self._get_on_demand_price(current_instance)
        
        # Get spot pricing for current instance type
        spot_price = self._get_spot_price(current_instance)
        
        # Calculate savings
        savings_per_hour = on_demand_price - spot_price
        savings_percent = (savings_per_hour / on_demand_price * 100) if on_demand_price > 0 else 0
        
        # Get interruption risk
        interruption_risk = self._get_interruption_risk(current_instance)
        
        # Calculate current cost (estimate based on typical training duration)
        training_hours = workload_metadata.get('duration_hours', 24.0)
        current_cost = on_demand_price * training_hours
        spot_cost = spot_price * training_hours
        total_savings = current_cost - spot_cost
        
        return [SpotRecommendation(
            workload_id=workload_id,
            current_instance=current_instance,
            current_cost=current_cost,
            recommended_spot_instance=current_instance,
            spot_cost=spot_cost,
            savings=total_savings,
            savings_percent=savings_percent,
            interruption_risk=interruption_risk,
            suitable=True,
            reason=f"Training workload suitable for spot instances. Estimated savings: ${total_savings:.2f} ({savings_percent:.1f}%)"
        )]
    
    def identify_spot_suitable_workloads(self) -> List[str]:
        """
        Identify training workloads suitable for spot instances.
        
        Returns:
            List of workload IDs suitable for spot instances
        """
        suitable_workloads = []
        
        # Query EC2 instances with training classification
        try:
            response = self.ec2_client.describe_instances(
                Filters=[
                    {'Name': 'instance-state-name', 'Values': ['running']},
                    {'Name': 'tag:WorkloadType', 'Values': ['training']}
                ]
            )
            
            for reservation in response.get('Reservations', []):
                for instance in reservation.get('Instances', []):
                    instance_id = instance['InstanceId']
                    instance_type = instance['InstanceType']
                    
                    # Check if GPU instance
                    if self._is_gpu_instance(instance_type):
                        # Get workload metadata
                        metadata = self._get_workload_metadata(instance_id)
                        is_suitable, _ = self._is_spot_suitable(metadata)
                        
                        if is_suitable:
                            suitable_workloads.append(instance_id)
        
        except Exception as e:
            print(f"Error identifying spot suitable workloads: {e}")
        
        return suitable_workloads
    
    def calculate_spot_savings(self, current_instance: str, spot_instance: str) -> SpotSavings:
        """
        Calculate potential savings from switching to spot instances.
        
        Args:
            current_instance: Current instance type
            spot_instance: Spot instance type (usually same as current)
            
        Returns:
            Spot savings calculation
        """
        # Get pricing
        on_demand_price = self._get_on_demand_price(current_instance)
        spot_price = self._get_spot_price(spot_instance)
        
        # Calculate savings
        savings_per_hour = on_demand_price - spot_price
        savings_percent = (savings_per_hour / on_demand_price * 100) if on_demand_price > 0 else 0
        
        # Estimate monthly savings (assume 24/7 usage)
        hours_per_month = 730  # average
        estimated_monthly_savings = savings_per_hour * hours_per_month
        
        return SpotSavings(
            current_instance=current_instance,
            spot_instance=spot_instance,
            on_demand_price=on_demand_price,
            spot_price=spot_price,
            savings_per_hour=savings_per_hour,
            savings_percent=savings_percent,
            estimated_monthly_savings=estimated_monthly_savings
        )
    
    def get_spot_interruption_risk(self, instance_type: str, az: Optional[str] = None) -> float:
        """
        Get spot instance interruption risk from historical data.
        
        Args:
            instance_type: EC2 instance type
            az: Availability zone (optional)
            
        Returns:
            Interruption risk (0-1, where 0 is no risk and 1 is high risk)
        """
        return self._get_interruption_risk(instance_type, az)
    
    def generate_what_if_scenarios(self, workload_id: str) -> List[WhatIfScenario]:
        """
        Generate what-if scenarios for spot instance usage.
        
        Args:
            workload_id: ID of the workload
            
        Returns:
            List of what-if scenarios
        """
        scenarios = []
        
        # Get workload metadata
        metadata = self._get_workload_metadata(workload_id)
        if not metadata:
            return scenarios
        
        instance_type = metadata.get('instance_type')
        training_hours = metadata.get('duration_hours', 24.0)
        
        # Get pricing
        on_demand_price = self._get_on_demand_price(instance_type)
        spot_price = self._get_spot_price(instance_type)
        interruption_risk = self._get_interruption_risk(instance_type)
        
        # Scenario 1: 100% spot usage
        savings_100 = (on_demand_price - spot_price) * training_hours
        interruptions_100 = int(training_hours * interruption_risk)
        scenarios.append(WhatIfScenario(
            scenario_name="100% Spot Usage",
            workload_id=workload_id,
            instance_type=instance_type,
            spot_usage_percent=100.0,
            estimated_savings=savings_100,
            estimated_interruptions=interruptions_100,
            recommendation="Maximum savings but higher interruption risk"
        ))
        
        # Scenario 2: 50% spot, 50% on-demand
        savings_50 = savings_100 * 0.5
        interruptions_50 = interruptions_100 // 2
        scenarios.append(WhatIfScenario(
            scenario_name="50% Spot, 50% On-Demand",
            workload_id=workload_id,
            instance_type=instance_type,
            spot_usage_percent=50.0,
            estimated_savings=savings_50,
            estimated_interruptions=interruptions_50,
            recommendation="Balanced approach with moderate savings and lower risk"
        ))
        
        # Scenario 3: 0% spot (current state)
        scenarios.append(WhatIfScenario(
            scenario_name="0% Spot (Current)",
            workload_id=workload_id,
            instance_type=instance_type,
            spot_usage_percent=0.0,
            estimated_savings=0.0,
            estimated_interruptions=0,
            recommendation="No savings but no interruption risk"
        ))
        
        return scenarios
    
    def _get_workload_metadata(self, workload_id: str) -> Dict[str, Any]:
        """Get workload metadata from EC2 or SageMaker."""
        try:
            # Try EC2 first
            response = self.ec2_client.describe_instances(InstanceIds=[workload_id])
            
            if response['Reservations']:
                instance = response['Reservations'][0]['Instances'][0]
                
                # Get workload type from tags
                workload_type = 'unknown'
                for tag in instance.get('Tags', []):
                    if tag['Key'] == 'WorkloadType':
                        workload_type = tag['Value']
                        break
                
                # Estimate duration from launch time
                launch_time = instance.get('LaunchTime')
                if launch_time:
                    duration = datetime.now(launch_time.tzinfo) - launch_time
                    duration_hours = duration.total_seconds() / 3600
                else:
                    duration_hours = 24.0  # default
                
                return {
                    'instance_type': instance['InstanceType'],
                    'workload_type': workload_type,
                    'duration_hours': duration_hours,
                    'state': instance['State']['Name']
                }
        
        except Exception as e:
            print(f"Error getting workload metadata: {e}")
        
        return {}
    
    def _is_spot_suitable(self, metadata: Dict[str, Any]) -> tuple[bool, str]:
        """Check if workload is suitable for spot instances."""
        workload_type = metadata.get('workload_type', 'unknown')
        duration_hours = metadata.get('duration_hours', 0)
        
        # Only training workloads are suitable
        if workload_type != 'training':
            return False, f"Workload type '{workload_type}' not suitable for spot instances (only training workloads)"
        
        # Must run for minimum duration
        if duration_hours < self.min_training_duration:
            return False, f"Training duration too short ({duration_hours:.1f}h < {self.min_training_duration}h)"
        
        return True, "Workload suitable for spot instances"
    
    def _is_gpu_instance(self, instance_type: str) -> bool:
        """Check if instance type is a GPU instance."""
        gpu_families = ['p3', 'p4', 'p4d', 'p5', 'g4', 'g5', 'g6']
        return any(instance_type.startswith(family) for family in gpu_families)
    
    def _get_on_demand_price(self, instance_type: str) -> float:
        """Get on-demand price for instance type using Pricing API."""
        try:
            # Query AWS Pricing API for on-demand pricing
            response = self.pricing_client.get_products(
                ServiceCode='AmazonEC2',
                Filters=[
                    {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                    {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                    {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                    {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
                    {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'}
                ],
                MaxResults=1
            )
            
            if response.get('PriceList'):
                import json
                price_data = json.loads(response['PriceList'][0])
                
                # Extract on-demand price from pricing structure
                terms = price_data.get('terms', {}).get('OnDemand', {})
                for term_key, term_value in terms.items():
                    price_dimensions = term_value.get('priceDimensions', {})
                    for dim_key, dim_value in price_dimensions.items():
                        price_per_unit = dim_value.get('pricePerUnit', {}).get('USD', '0')
                        return float(price_per_unit)
        
        except Exception as e:
            # Fallback to simplified pricing if API call fails
            pricing_map = {
                'p3.2xlarge': 3.06,
                'p3.8xlarge': 12.24,
                'p3.16xlarge': 24.48,
                'p4d.24xlarge': 32.77,
                'p5.48xlarge': 98.32,
                'g4dn.xlarge': 0.526,
                'g4dn.2xlarge': 0.752,
                'g4dn.4xlarge': 1.204,
                'g4dn.8xlarge': 2.176,
                'g5.xlarge': 1.006,
                'g5.2xlarge': 1.212,
                'g5.4xlarge': 1.624,
                'g5.8xlarge': 2.448,
            }
            return pricing_map.get(instance_type, 1.0)
        
        # Default fallback
        return 1.0
    
    @retry_with_exponential_backoff(max_retries=3)
    def _get_spot_price(self, instance_type: str) -> float:
        """Get current spot price for instance type."""
        try:
            response = self.ec2_client.describe_spot_price_history(
                InstanceTypes=[instance_type],
                MaxResults=1,
                ProductDescriptions=['Linux/UNIX']
            )
            
            if response['SpotPriceHistory']:
                return float(response['SpotPriceHistory'][0]['SpotPrice'])
        
        except ClientError as e:
            # Handle pricing errors with fallback
            on_demand_price = self._get_on_demand_price(instance_type)
            estimated_spot_price = on_demand_price * 0.3
            error_result = handle_pricing_error(e, estimated_spot_price)
            if 'price' in error_result:
                return error_result['price']
        except Exception as e:
            print(f"Error getting spot price: {e}")
        
        # Fallback: estimate 70% discount
        on_demand_price = self._get_on_demand_price(instance_type)
        return on_demand_price * 0.3
    
    def _get_interruption_risk(self, instance_type: str, az: Optional[str] = None) -> float:
        """Get interruption risk for spot instance using historical data."""
        try:
            # Query CloudWatch for spot interruption history
            # Use SpotInstanceInterruption metric if available
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=30)  # Last 30 days
            
            try:
                response = self.cloudwatch_client.get_metric_statistics(
                    Namespace='AWS/EC2Spot',
                    MetricName='SpotInstanceInterruption',
                    Dimensions=[
                        {'Name': 'InstanceType', 'Value': instance_type}
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400,  # Daily
                    Statistics=['Sum']
                )
                
                # Calculate interruption rate from historical data
                total_interruptions = sum(float(dp['Sum']) for dp in response.get('Datapoints', []))
                total_days = len(response.get('Datapoints', []))
                
                if total_days > 0:
                    # Estimate risk as interruptions per day
                    daily_risk = total_interruptions / total_days
                    # Normalize to 0-1 range (assuming max 1 interruption per day = 100% risk)
                    risk = min(daily_risk, 1.0)
                    return risk
                    
            except Exception:
                # Fallback to instance family-based risk assessment
                pass
        
        except Exception:
            pass
        
        # Fallback: Use instance family-based risk assessment
        # GPU instances typically have lower interruption rates
        risk_map = {
            'p3': 0.05,   # 5% risk
            'p4': 0.08,   # 8% risk
            'p5': 0.10,   # 10% risk
            'g4': 0.12,   # 12% risk
            'g5': 0.10,   # 10% risk
            'g6': 0.15,   # 15% risk
        }
        
        for family, risk in risk_map.items():
            if instance_type.startswith(family):
                return risk
        
        return 0.20  # default 20% risk
