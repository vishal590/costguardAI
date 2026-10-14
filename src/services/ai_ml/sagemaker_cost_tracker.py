"""
SageMaker Cost Tracker Service

Tracks SageMaker training job costs, inference endpoint costs, and notebook instance costs.
Identifies idle endpoints and recommends cost-optimized instance types.

Requirements: FR-6.1, FR-6.2, FR-6.3, FR-6.4, FR-6.5, FR-6.6
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
import math
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
    instance_type: Optional[str]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    duration_hours: Optional[float]
    compute_cost: Optional[float]
    storage_cost: Optional[float]
    data_transfer_cost: Optional[float]
    total_cost: Optional[float]

    cost_status: str = "unavailable"
    cost_basis: str = "resource_metadata_without_verified_billing_profile"


@dataclass
class SageMakerCosts:
    """Aggregated SageMaker costs"""
    date: datetime
    training_costs: Optional[float]
    inference_costs: Optional[float]
    notebook_costs: Optional[float]
    total_cost: Optional[float]
    job_breakdown: List[JobCost]

    unclassified_costs: Optional[float] = None
    currency: Optional[str] = None
    data_quality: Dict = field(default_factory=dict)


@dataclass
class EndpointMetrics:
    """Observed endpoint evidence; unavailable values are never zero-filled."""
    endpoint_name: str
    instance_type: Optional[str]
    instance_count: Optional[int]
    requests_per_hour: Optional[float]
    avg_latency_ms: Optional[float]
    cost_per_hour: Optional[float]
    is_idle: bool
    observation_status: str = 'unavailable'
    reason: Optional[str] = None
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    cost_status: str = 'unavailable'
    latency_basis: str = 'unavailable'
    cost_scope: str = 'unavailable'
    pricing_provenance: Optional[Dict] = None


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


class SageMakerDataUnavailable(AIMLError):
    """Provider cost observations do not satisfy the reporting contract."""


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
        self._compute_rates = {}
    
    @retry_with_exponential_backoff(max_retries=3)
    def track_sagemaker_costs(self, start_date: datetime, end_date: datetime) -> SageMakerCosts:
        """Aggregate all observed USD usage categories over a bounded exclusive period."""
        start, end = start_date.date(), end_date.date()
        days = (end-start).days
        if not 1 <= days <= 31 or end > datetime.now(UTC).date():
            raise ValueError('SageMaker costs require 1-31 completed daily dates with an exclusive end')
        expected = {(start+timedelta(days=offset)).isoformat() for offset in range(days)}
        request = {'TimePeriod': {'Start': start.isoformat(), 'End': end.isoformat()},
                   'Granularity': 'DAILY', 'Metrics': ['UnblendedCost'],
                   'Filter': {'Dimensions': {'Key': 'SERVICE', 'Values': ['Amazon SageMaker']}},
                   'GroupBy': [{'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'}]}
        rows, flags, seen = {}, {}, set()
        try:
            while True:
                response = self.cost_explorer.get_cost_and_usage(**request)
                for period in response.get('ResultsByTime', []):
                    day = period['TimePeriod']['Start']
                    if day not in expected or period['TimePeriod']['End'] != (datetime.fromisoformat(day).date()+timedelta(days=1)).isoformat():
                        raise ValueError('Unexpected daily provider period')
                    flag = period.get('Estimated')
                    flag = flag if isinstance(flag, bool) else None
                    if day not in flags: flags[day] = flag
                    elif flags[day] is True or flag is True: flags[day] = True
                    elif flags[day] is None or flag is None: flags[day] = None
                    for group in period.get('Groups', []):
                        keys = group.get('Keys')
                        if not isinstance(keys, list) or len(keys) != 1 or not isinstance(keys[0], str) or not keys[0]:
                            raise ValueError('Invalid usage type')
                        metric = group['Metrics']['UnblendedCost']
                        if metric.get('Unit') != 'USD' or isinstance(metric.get('Amount'), bool): raise ValueError('Unsupported cost observation unit')
                        amount = Decimal(str(metric['Amount']))
                        if not amount.is_finite() or not math.isfinite(float(amount)): raise ValueError('Invalid cost amount')
                        identity = (day, keys[0])
                        if identity in rows and rows[identity] != amount: raise ValueError('Conflicting duplicate cost observations')
                        rows[identity] = amount
                token = response.get('NextPageToken')
                if not token: break
                if token in seen: raise ValueError('Repeated cost page token')
                seen.add(token)
                request['NextPageToken'] = token
        except Exception as error:
            raise SageMakerDataUnavailable('SageMaker provider cost observations are unavailable') from error
        categories = {'training': [], 'inference': [], 'notebook': [], 'unclassified': []}
        for (_, usage), amount in rows.items():
            category = 'training' if 'Training' in usage else 'inference' if 'Hosting' in usage or 'Endpoint' in usage else 'notebook' if 'Notebook' in usage else 'unclassified'
            categories[category].append(amount)
        def observed_sum(values):
            if not values: return None
            total = float(sum(values, Decimal('0')))
            if not math.isfinite(total): raise SageMakerDataUnavailable('Cost total is unavailable')
            return total
        observed_dates = {day for day, _ in rows}
        quality = {'status': 'observed' if rows else 'no_observations', 'metric': 'UnblendedCost',
            'granularity': 'DAILY', 'missing_dates': sorted(expected-observed_dates),
            'complete_date_coverage': expected == observed_dates, 'invoice_coverage_verified': False,
            'estimated_dates': sorted(day for day in observed_dates if flags.get(day) is True),
            'unknown_estimate_dates': sorted(day for day in observed_dates if flags.get(day) is None),
            'category_method': 'usage_type_name_heuristic_with_unclassified_residual',
            'job_breakdown_scope': 'jobs_created_in_requested_window_not_attributed_billing',
            'observed_at': datetime.now(UTC).isoformat()}
        breakdown = self._get_job_breakdown(start_date, end_date)
        quality['job_metadata'] = self.last_job_breakdown_report
        return SageMakerCosts(start_date, observed_sum(categories['training']), observed_sum(categories['inference']),
            observed_sum(categories['notebook']), observed_sum(list(rows.values())),
            breakdown, observed_sum(categories['unclassified']),
            'USD' if rows else None, quality)

    @retry_with_exponential_backoff(max_retries=3)
    def get_training_job_costs(self, job_name: str) -> JobCost:
        """Observe job metadata without inventing attributable billing charges."""
        from ..time_values import parse_utc_timestamp
        response = self.sagemaker.describe_training_job(TrainingJobName=job_name)
        resource = response.get('ResourceConfig', {})
        start = parse_utc_timestamp(response['TrainingStartTime']) if response.get('TrainingStartTime') else None
        end = parse_utc_timestamp(response['TrainingEndTime']) if response.get('TrainingEndTime') else None
        now = datetime.now(UTC)
        duration = None
        if start is not None and start <= (end or now) <= now:
            duration = ((end or now)-start).total_seconds()/3600.0
        instance_type = None if resource.get('InstanceGroups') else resource.get('InstanceType')
        return JobCost(job_name, 'training', instance_type, start, end, duration, None, None, None, None)

    @retry_with_exponential_backoff(max_retries=3)
    def get_endpoint_costs(self, endpoint_name: str, start_date: datetime, end_date: datetime) -> JobCost:
        """Return requested-period metadata; current capacity cannot reconstruct past charges."""
        if end_date <= start_date: raise ValueError('Endpoint period must have a positive duration')
        response = self.sagemaker.describe_endpoint(EndpointName=endpoint_name)
        config = self.sagemaker.describe_endpoint_config(EndpointConfigName=response['EndpointConfigName'])
        variants = config.get('ProductionVariants', [])
        instance_type = variants[0].get('InstanceType') if len(variants) == 1 else None
        return JobCost(endpoint_name, 'inference', instance_type, start_date, end_date,
                       (end_date-start_date).total_seconds()/3600.0, None, None, None, None)

    def identify_idle_endpoints(self, threshold: int = 10) -> List[EndpointMetrics]:
        """Return bounded fully observed low-invocation review candidates."""
        if isinstance(threshold, bool) or not isinstance(threshold, int) or not 0 <= threshold <= 1000000:
            raise ValueError('Threshold must be an integer from 0 to 1000000')
        candidates, seen = [], set()
        self._compute_rates = {}
        report = {'observed_endpoint_count': 0, 'unavailable_evidence_count': 0,
                  'unavailable_examples': [], 'inventory_completeness': 'unverified',
                  'method': 'observed_single_variant_hour', 'workload_inactivity_verified': False,
                  'endpoint_detail_limit': 20, 'list_page_limit': 5, 'list_pages_read': 0,
                  'has_more': False, 'duplicate_list_observations': 0}
        self.last_idle_report = report
        try:
            paginator = self.sagemaker.get_paginator('list_endpoints')
            for page in paginator.paginate(StatusEquals='InService', PaginationConfig={'PageSize': 100}):
                report['list_pages_read'] += 1
                for endpoint in page['Endpoints']:
                    name = endpoint['EndpointName']
                    if name in seen:
                        report['duplicate_list_observations'] += 1
                        continue
                    if report['observed_endpoint_count'] >= report['endpoint_detail_limit']:
                        report['has_more'] = True
                        return candidates
                    seen.add(name)
                    metrics = self._get_endpoint_metrics(name)
                    report['observed_endpoint_count'] += 1
                    if metrics.observation_status != 'available':
                        report['unavailable_evidence_count'] += 1
                        if len(report['unavailable_examples']) < 20:
                            report['unavailable_examples'].append({'endpoint_name': metrics.endpoint_name, 'reason': metrics.reason})
                    elif metrics.requests_per_hour < threshold:
                        metrics.is_idle = True
                        self._attach_compute_component(metrics)
                        candidates.append(metrics)
                if report['list_pages_read'] >= report['list_page_limit'] and page.get('NextToken'):
                    report['has_more'] = True
                    return candidates
        except Exception as error:
            raise SageMakerDataUnavailable('SageMaker endpoint listing is unavailable') from error
        finally:
            report['unavailable_examples_truncated'] = report['unavailable_evidence_count'] > len(report['unavailable_examples'])
        return candidates

    def _attach_compute_component(self, metrics):
        from .sagemaker_pricing import lookup_compute_rate
        region = self.sagemaker.meta.region_name
        key = (region, metrics.instance_type)
        if key not in self._compute_rates:
            self._compute_rates[key] = lookup_compute_rate(self.pricing, region, metrics.instance_type, 'hosting')
        rate = self._compute_rates[key]
        if rate is not None:
            component = float(rate.hourly_usd)*metrics.instance_count
            if math.isfinite(component) and component >= 0:
                metrics.cost_per_hour = component
                metrics.cost_status = 'partial_compute_component'
                metrics.cost_scope = rate.scope
                metrics.pricing_provenance = rate.provenance()

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
        # Product rates alone do not establish workload/hardware compatibility.
        compatible = (workload_characteristics or {}).get('compatible_instance_types')
        if not isinstance(compatible, list) or not compatible or any(not isinstance(item, str) for item in compatible): return []
        # Get current instance price
        current_price = self._get_instance_price(current_instance, job_type)
        if current_price is None: return []
        
        # Define alternative instances based on job type
        if job_type == 'training':
            alternatives = self._get_training_alternatives(current_instance)
        else:
            alternatives = self._get_inference_alternatives(current_instance)
        
        # Calculate savings for each alternative
        for alt_instance in alternatives:
            if alt_instance not in compatible: continue
            alt_price = self._get_instance_price(alt_instance, job_type)
            
            if alt_price is not None and alt_price < current_price:
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
        """Bound detail reads independently of provider cost aggregation."""
        rows, seen = [], set()
        report = {'scope': 'jobs_created_in_requested_window', 'detail_attempt_limit': 50,
                  'attempted_jobs': 0, 'omitted_jobs': 0, 'duplicate_list_observations': 0,
                  'list_page_limit': 5, 'list_pages_read': 0,
                  'omission_examples': [], 'listing_status': 'observed', 'has_more': False,
                  'billing_attribution_verified': False}
        self.last_job_breakdown_report = report
        try:
            paginator = self.sagemaker.get_paginator('list_training_jobs')
            for page in paginator.paginate(CreationTimeAfter=start_date, CreationTimeBefore=end_date,
                                           PaginationConfig={'PageSize': 100}):
                report['list_pages_read'] += 1
                for job in page['TrainingJobSummaries']:
                    name = job['TrainingJobName']
                    if name in seen:
                        report['duplicate_list_observations'] += 1
                        continue
                    if report['attempted_jobs'] >= report['detail_attempt_limit']:
                        report['has_more'] = True
                        report['listing_status'] = 'bounded_selection'
                        return rows
                    seen.add(name)
                    report['attempted_jobs'] += 1
                    try:
                        rows.append(self.get_training_job_costs(name))
                    except Exception:
                        report['omitted_jobs'] += 1
                        if len(report['omission_examples']) < 20:
                            report['omission_examples'].append({'job_name': name, 'reason': 'Job metadata unavailable'})
                if report['list_pages_read'] >= report['list_page_limit'] and page.get('NextToken'):
                    report['has_more'] = True
                    report['listing_status'] = 'bounded_selection'
                    return rows
        except Exception:
            report['listing_status'] = 'unavailable_or_partial'
            report['has_more'] = None
        finally:
            report['returned_rows'] = len(rows)
            report['omission_examples_truncated'] = report['omitted_jobs'] > len(report['omission_examples'])
        return rows

    def _get_endpoint_metrics(self, endpoint_name: str) -> EndpointMetrics:
        """Observe one supported real-time variant over a complete dated hour."""
        from ..time_values import parse_utc_timestamp
        result = EndpointMetrics(endpoint_name, None, None, None, None, None, False)
        try:
            if self.sagemaker.meta.region_name != self.cloudwatch.meta.region_name:
                raise ValueError('Resource and metric regions differ')
            endpoint = self.sagemaker.describe_endpoint(EndpointName=endpoint_name)
            config = self.sagemaker.describe_endpoint_config(EndpointConfigName=endpoint['EndpointConfigName'])
            variants, live = config.get('ProductionVariants', []), endpoint.get('ProductionVariants', [])
            if (endpoint.get('EndpointStatus') != 'InService' or len(variants) != 1 or len(live) != 1
                    or config.get('AsyncInferenceConfig') or config.get('ShadowProductionVariants')):
                raise ValueError('Unsupported endpoint profile; only one real-time production variant is covered')
            variant, current = variants[0], live[0]
            if (variant.get('ServerlessConfig') or variant.get('InstancePools') or current.get('InstancePools')
                    or not variant.get('InstanceType') or variant.get('VariantName') != current.get('VariantName')):
                raise ValueError('Unsupported or mismatched endpoint variant')
            count = current.get('CurrentInstanceCount')
            if isinstance(count, bool) or not isinstance(count, int) or count <= 0: raise ValueError('Current instance count is unavailable')
            result.instance_type, result.instance_count = variant['InstanceType'], count
            end_epoch = int(datetime.now(UTC).timestamp())//300*300-300
            start_epoch = end_epoch-3600
            start, end = datetime.fromtimestamp(start_epoch, UTC), datetime.fromtimestamp(end_epoch, UTC)
            dimensions = [{'Name': 'EndpointName', 'Value': endpoint_name}, {'Name': 'VariantName', 'Value': variant['VariantName']}]
            response = self.cloudwatch.get_metric_statistics(Namespace='AWS/SageMaker', MetricName='Invocations',
                Dimensions=dimensions, StartTime=start, EndTime=end, Period=300, Statistics=['Sum', 'SampleCount'])
            points = {}
            for point in response.get('Datapoints', []):
                stamp = int(parse_utc_timestamp(point['Timestamp']).timestamp())
                value, samples = float(point['Sum']), float(point['SampleCount'])
                if not math.isfinite(value) or value < 0 or not math.isfinite(samples) or samples <= 0: raise ValueError('Invalid invocation evidence')
                if stamp in points and points[stamp] != value: raise ValueError('Conflicting invocation buckets')
                points[stamp] = value
            if set(points) != set(range(start_epoch, end_epoch, 300)): raise ValueError('Incomplete invocation buckets; missing metrics are not zero requests')
            result.requests_per_hour = sum(points.values())
            if not math.isfinite(result.requests_per_hour): raise ValueError('Invalid invocation total')
            result.window_start, result.window_end = start.isoformat(), end.isoformat()
            result.observation_status = 'available'
            result.reason = 'Observed invocation threshold is a review signal, not verified workload inactivity'
            try:
                latency = self.cloudwatch.get_metric_statistics(Namespace='AWS/SageMaker', MetricName='ModelLatency',
                    Dimensions=dimensions, StartTime=start, EndTime=end, Period=300,
                    Statistics=['Average', 'SampleCount'], Unit='Microseconds')
                weighted, samples = 0.0, 0.0
                for point in latency.get('Datapoints', []):
                    stamp = parse_utc_timestamp(point['Timestamp'])
                    value, amount = float(point['Average']), float(point['SampleCount'])
                    if not start <= stamp < end or not math.isfinite(value) or value < 0 or not math.isfinite(amount) or amount <= 0: raise ValueError('Invalid latency sample')
                    weighted += value*amount
                    samples += amount
                if samples > 0 and math.isfinite(weighted) and math.isfinite(samples):
                    result.avg_latency_ms = weighted/samples/1000.0
                    result.latency_basis = 'sample_weighted_observed_microseconds_to_ms'
            except Exception:
                pass  # Latency absence does not establish zero latency or invocation coverage.
            return result
        except ValueError as error:
            result.reason = str(error)
        except Exception:
            result.reason = 'Endpoint evidence could not be retrieved'
        return result

    def _get_instance_price(self, instance_type: str, job_type: str) -> Optional[float]:
        """Return a strictly matched regional on-demand compute rate, without fallback."""
        from .sagemaker_pricing import lookup_compute_rate
        rate = lookup_compute_rate(self.pricing, self.sagemaker.meta.region_name, instance_type, 'hosting' if job_type == 'inference' else job_type)
        return float(rate.hourly_usd) if rate is not None else None

    def _get_estimated_price(self, instance_type: str, job_type: str) -> Optional[float]:
        """Unknown profiles have no monetary fallback."""
        return None

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
