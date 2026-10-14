"""
Cost Estimator for Phase 1.5.

This module calculates cost estimates based on metrics and pricing data.
"""
from typing import List, Tuple, Any
from decimal import Decimal
from datetime import datetime, timezone
import math

from src.utils.types import (
    MetricDataPoint,
    EC2Metrics,
    LambdaMetrics,
    DynamoDBMetrics,
    S3Metrics,
    RDSMetrics,
    PricingData,
    CostEstimate,
    EC2Pricing,
    LambdaPricing,
    DynamoDBPricing,
    S3Pricing,
    RDSPricing
)


class CostEstimator:
    """Calculates cost estimates based on metrics and pricing data."""
    
    def __init__(self):
        """Initialize cost estimator."""
        pass
    
    def estimate_cost(
        self,
        service: str,
        metrics: List[MetricDataPoint],
        pricing_data: PricingData
    ) -> CostEstimate:
        """
        Estimate cost for a service based on metrics and pricing.
        
        Args:
            service: Service name
            metrics: List of metric data points
            pricing_data: Pricing information
            
        Returns:
            Cost estimate with confidence interval
        """
        now = datetime.now(timezone.utc)
        return self._unavailable(service, metrics, pricing_data, now, now,
            'Generic metric values do not establish monetary cost; use a supported service-specific estimator')

    def estimate_ec2_cost(
        self,
        metrics: List[EC2Metrics],
        pricing: EC2Pricing
    ) -> Decimal:
        """
        Estimate EC2 costs.
        
        Args:
            metrics: EC2 metrics
            pricing: EC2 pricing data
            
        Returns:
            Estimated cost
        """
        if not metrics:
            return Decimal('0')
        
        total_cost = Decimal('0')
        
        for metric in metrics:
            # Calculate instance cost (running hours * price per hour)
            instance_price = pricing.instance_prices.get(
                metric.instance_type,
                Decimal('0.0116')  # Default to t2.micro price
            )
            instance_cost = metric.running_hours * instance_price
            
            # Calculate data transfer cost (network out in GB * price per GB)
            # Convert bytes to GB
            network_out_gb = metric.network_out / Decimal('1073741824')  # 1024^3
            data_transfer_cost = network_out_gb * pricing.data_transfer_out
            
            total_cost += instance_cost + data_transfer_cost
        
        return total_cost
    
    def estimate_lambda_cost(
        self,
        metrics: List[LambdaMetrics],
        pricing: LambdaPricing
    ) -> Decimal:
        """
        Estimate Lambda costs.
        
        Args:
            metrics: Lambda metrics
            pricing: Lambda pricing data
            
        Returns:
            Estimated cost
        """
        if not metrics:
            return Decimal('0')
        
        total_cost = Decimal('0')
        
        for metric in metrics:
            # Calculate request cost
            request_cost = Decimal(str(metric.invocations)) * pricing.price_per_request
            
            # Calculate duration cost (GB-seconds)
            # Duration is in milliseconds, convert to seconds
            duration_seconds = metric.duration_ms / Decimal('1000')
            # Memory is in MB, convert to GB
            memory_gb = Decimal(str(metric.memory_mb)) / Decimal('1024')
            # GB-seconds = invocations * duration_seconds * memory_gb
            gb_seconds = Decimal(str(metric.invocations)) * duration_seconds * memory_gb
            duration_cost = gb_seconds * pricing.price_per_gb_second
            
            total_cost += request_cost + duration_cost
        
        return total_cost
    
    def estimate_dynamodb_cost(
        self,
        metrics: List[DynamoDBMetrics],
        pricing: DynamoDBPricing
    ) -> Decimal:
        """
        Estimate DynamoDB costs.
        
        Args:
            metrics: DynamoDB metrics
            pricing: DynamoDB pricing data
            
        Returns:
            Estimated cost
        """
        if not metrics:
            return Decimal('0')
        
        total_cost = Decimal('0')
        
        for metric in metrics:
            # Calculate read cost
            read_cost = metric.consumed_read_capacity * pricing.price_per_read_unit
            
            # Calculate write cost
            write_cost = metric.consumed_write_capacity * pricing.price_per_write_unit
            
            total_cost += read_cost + write_cost
        
        return total_cost
    
    def estimate_s3_cost(
        self,
        metrics: List[S3Metrics],
        pricing: S3Pricing
    ) -> Decimal:
        """
        Estimate S3 costs.
        
        Args:
            metrics: S3 metrics
            pricing: S3 pricing data
            
        Returns:
            Estimated cost
        """
        if not metrics:
            return Decimal('0')
        
        total_cost = Decimal('0')
        
        for metric in metrics:
            # Calculate storage cost (size in GB * price per GB)
            storage_gb = metric.bucket_size_bytes / Decimal('1073741824')  # Convert bytes to GB
            storage_cost = storage_gb * pricing.price_per_gb_storage
            
            # Calculate request costs
            get_request_cost = Decimal(str(metric.get_requests)) * pricing.price_per_get_request
            put_request_cost = Decimal(str(metric.put_requests)) * pricing.price_per_put_request
            
            total_cost += storage_cost + get_request_cost + put_request_cost
        
        return total_cost
    
    def estimate_rds_cost(
        self,
        metrics: List[RDSMetrics],
        pricing: RDSPricing
    ) -> Decimal:
        """
        Estimate RDS costs.
        
        Args:
            metrics: RDS metrics
            pricing: RDS pricing data
            
        Returns:
            Estimated cost
        """
        if not metrics:
            return Decimal('0')
        
        total_cost = Decimal('0')
        
        for metric in metrics:
            # Calculate instance cost (running hours * price per hour)
            instance_price = pricing.instance_prices.get(
                metric.instance_type,
                Decimal('0.017')  # Default to db.t3.micro price
            )
            instance_cost = metric.running_hours * instance_price
            
            # Calculate storage cost
            storage_cost = metric.storage_gb * pricing.storage_price_per_gb
            
            # Calculate IOPS cost (average IOPS * price)
            avg_iops = (metric.read_iops + metric.write_iops) / Decimal('2')
            iops_cost = avg_iops * pricing.iops_price
            
            total_cost += instance_cost + storage_cost + iops_cost
        
        return total_cost
    
    def calculate_confidence_interval(
        self,
        estimate: Decimal,
        metrics_count: int
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate confidence interval for estimate.
        
        Args:
            estimate: Cost estimate
            metrics_count: Number of metrics used
            
        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        if metrics_count == 0:
            return (Decimal('0'), Decimal('0'))
        
        # Calculate confidence interval based on sample size
        # More metrics = tighter confidence interval
        # Using a simple percentage-based approach
        
        # Base confidence margin: 10% for large samples, up to 30% for small samples
        if metrics_count >= 100:
            margin_percent = Decimal('0.10')  # 10%
        elif metrics_count >= 50:
            margin_percent = Decimal('0.15')  # 15%
        elif metrics_count >= 10:
            margin_percent = Decimal('0.20')  # 20%
        else:
            margin_percent = Decimal('0.30')  # 30%
        
        margin = estimate * margin_percent
        
        lower_bound = max(Decimal('0'), estimate - margin)
        upper_bound = estimate + margin
        
        return (lower_bound, upper_bound)
    
    def calculate_total_estimate(
        self,
        estimates: List[CostEstimate]
    ) -> Decimal:
        """
        Calculate total cost across all services.
        
        Args:
            estimates: List of cost estimates
            
        Returns:
            Total estimated cost
        """
        if not estimates:
            return Decimal('0')
        
        available = [est.estimated_cost for est in estimates if est.estimated_cost is not None]
        if not available: return None
        total = sum(available)
        return total
    
    def estimate_cost_with_service_method(
        self,
        service: str,
        service_metrics: Any,
        pricing_data: PricingData,
        start_time: datetime,
        end_time: datetime
    ) -> CostEstimate:
        """
        Estimate cost using service-specific methods.
        
        Args:
            service: Service name (ec2, lambda, dynamodb, s3, rds)
            service_metrics: Service-specific metrics (EC2Metrics, LambdaMetrics, etc.)
            pricing_data: Generic pricing data
            start_time: Period start time
            end_time: Period end time
            
        Returns:
            Cost estimate with confidence interval
        """
        from src.utils.types import EC2Metrics, LambdaMetrics, DynamoDBMetrics, S3Metrics, RDSMetrics
        
        partial_storage = service == 's3' and isinstance(service_metrics, list) and bool(service_metrics) and all(getattr(metric, 'billing_profile', '') == 'storage_only_missing_requests' for metric in service_metrics)
        profiles = {'ec2': 'linux_shared_ondemand', 'lambda': 'x86_lambda', 'dynamodb': 'standard_ondemand', 's3': 'standard_with_requests', 'rds': 'postgres_singleaz_gp2'}
        if not partial_storage and (not isinstance(service_metrics, list) or not service_metrics or any(getattr(metric, 'billing_profile', 'unknown') != profiles.get(service) for metric in service_metrics)):
            return self._unavailable(service, service_metrics, pricing_data, start_time, end_time, 'S3 request usage is not collected' if service == 's3' else 'Observed billing profile or required usage components are not supported')
        required = {'lambda': ('request', 'gb_second'), 'dynamodb': ('read_unit', 'write_unit'), 's3': ('storage_gb', 'get_request', 'put_request'), 'rds': ('storage_gb',)}
        if partial_storage: required['s3'] = ('storage_gb',)
        try:
            if any(not Decimal(str(value)).is_finite() or Decimal(str(value)) < 0 for value in pricing_data.prices.values()):
                return self._unavailable(service, service_metrics, pricing_data, start_time, end_time, 'Pricing contains invalid nonnegative rates')
        except Exception:
            return self._unavailable(service, service_metrics, pricing_data, start_time, end_time, 'Pricing rate shape is unsupported')
        if pricing_data.source != 'aws_pricing' or any(key not in pricing_data.prices for key in required.get(service, ())):
            return self._unavailable(service, service_metrics, pricing_data, start_time, end_time, 'Verified regional pricing is incomplete or unavailable')
        if service in ('ec2', 'rds') and any(getattr(metric, 'instance_type', None) not in pricing_data.prices for metric in service_metrics):
            return self._unavailable(service, service_metrics, pricing_data, start_time, end_time, 'Instance profile has no unambiguous regional price')
        if service == 'ec2' and any(metric.network_out > 0 for metric in service_metrics) and 'data_transfer_out' not in pricing_data.prices:
            return self._unavailable(service, service_metrics, pricing_data, start_time, end_time, 'Transfer pricing is unavailable for the collected network usage')
        estimated_cost = Decimal('0')
        metrics_count = 0
        
        if service == 'ec2' and isinstance(service_metrics, list) and len(service_metrics) > 0 and isinstance(service_metrics[0], EC2Metrics):
            # Convert PricingData to EC2Pricing
            ec2_pricing = EC2Pricing(
                instance_prices={k: v for k, v in pricing_data.prices.items() if not k.startswith('data_transfer')},
                data_transfer_out=pricing_data.prices.get('data_transfer_out', Decimal('0')),
                currency=pricing_data.currency
            )
            estimated_cost = self.estimate_ec2_cost(service_metrics, ec2_pricing)
            metrics_count = len(service_metrics)
            
        elif service == 'lambda' and isinstance(service_metrics, list) and len(service_metrics) > 0 and isinstance(service_metrics[0], LambdaMetrics):
            # Convert PricingData to LambdaPricing
            lambda_pricing = LambdaPricing(
                price_per_request=pricing_data.prices['request'],
                price_per_gb_second=pricing_data.prices['gb_second'],
                currency=pricing_data.currency
            )
            estimated_cost = self.estimate_lambda_cost(service_metrics, lambda_pricing)
            metrics_count = len(service_metrics)
            
        elif service == 'dynamodb' and isinstance(service_metrics, list) and len(service_metrics) > 0 and isinstance(service_metrics[0], DynamoDBMetrics):
            # Convert PricingData to DynamoDBPricing
            dynamodb_pricing = DynamoDBPricing(
                price_per_read_unit=pricing_data.prices['read_unit'],
                price_per_write_unit=pricing_data.prices['write_unit'],
                currency=pricing_data.currency
            )
            estimated_cost = self.estimate_dynamodb_cost(service_metrics, dynamodb_pricing)
            metrics_count = len(service_metrics)
            
        elif service == 's3' and isinstance(service_metrics, list) and len(service_metrics) > 0 and isinstance(service_metrics[0], S3Metrics):
            # Convert PricingData to S3Pricing
            s3_pricing = S3Pricing(
                price_per_gb_storage=pricing_data.prices['storage_gb'] * Decimal(str((end_time-start_time).total_seconds())) / Decimal('2628000'),
                price_per_get_request=pricing_data.prices.get('get_request', Decimal('0')),
                price_per_put_request=pricing_data.prices.get('put_request', Decimal('0')),
                currency=pricing_data.currency
            )
            if partial_storage:
                estimated_cost = sum((metric.bucket_size_bytes / Decimal('1073741824') * s3_pricing.price_per_gb_storage for metric in service_metrics), Decimal('0'))
            else:
                estimated_cost = self.estimate_s3_cost(service_metrics, s3_pricing)
            metrics_count = len(service_metrics)
            
        elif service == 'rds' and isinstance(service_metrics, list) and len(service_metrics) > 0 and isinstance(service_metrics[0], RDSMetrics):
            # Convert PricingData to RDSPricing
            rds_pricing = RDSPricing(
                instance_prices={k: v for k, v in pricing_data.prices.items() if k.startswith('db.')},
                storage_price_per_gb=pricing_data.prices['storage_gb'] * Decimal(str((end_time-start_time).total_seconds())) / Decimal('2628000'),
                iops_price=Decimal('0'),  # General-purpose storage profile does not bill observed I/O as provisioned IOPS,
                currency=pricing_data.currency
            )
            estimated_cost = self.estimate_rds_cost(service_metrics, rds_pricing)
            metrics_count = len(service_metrics)
        else:
            return self._unavailable(service, service_metrics, pricing_data, start_time, end_time, 'Unsupported service or metric shape')

        if not estimated_cost.is_finite() or estimated_cost < 0:
            return self._unavailable(service, service_metrics, pricing_data, start_time, end_time, 'Collected usage did not produce a finite nonnegative estimate')
        # Calculate confidence interval
        lower, upper = self.calculate_confidence_interval(estimated_cost, metrics_count)
        
        # Create estimate
        now = datetime.now(timezone.utc)
        estimate = CostEstimate(
            service=service,
            estimated_cost=estimated_cost,
            currency=pricing_data.currency,
            confidence_lower=lower,
            confidence_upper=upper,
            timestamp=now,
            period_start=start_time,
            period_end=end_time,
            metrics_count=metrics_count, pricing_source=pricing_data.source, pricing_profile=pricing_data.pricing_profile, range_method="heuristic_resource_count",
            status="partial" if partial_storage else "estimated",
            covered_components=["standard_storage"] if partial_storage else ["supported_profile_usage"],
            missing_components=["get_requests", "put_requests", "other_storage_classes_and_charges"] if partial_storage else None,
            reason="Standard storage only; request usage and other storage charges are excluded" if partial_storage else None
        )
        
        return estimate
    def _unavailable(self, service, metrics, pricing, start, end, reason):
        return CostEstimate(service=service, estimated_cost=None, currency=pricing.currency,
            confidence_lower=None, confidence_upper=None, timestamp=datetime.now(timezone.utc),
            period_start=start, period_end=end, metrics_count=len(metrics) if isinstance(metrics, list) else 0,
            status='unavailable', pricing_source=pricing.source, pricing_profile=pricing.pricing_profile, reason=reason)
