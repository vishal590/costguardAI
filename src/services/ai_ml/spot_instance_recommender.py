"""Scoped EC2 rate-reference observations, without suitability/risk/savings inference."""
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from typing import Optional, List
import json
import math
import re
import boto3
from .error_handler import AIMLError
from ..time_values import parse_utc_timestamp


class SpotQuoteUnavailable(AIMLError):
    pass


@dataclass
class SpotRecommendation:
    workload_id: str
    current_instance: str
    current_cost: Optional[float]
    recommended_spot_instance: Optional[str]
    spot_cost: Optional[float]
    savings: Optional[float]
    savings_percent: Optional[float]
    interruption_risk: Optional[float]
    suitable: Optional[bool]
    reason: str


@dataclass
class SpotSavings:
    current_instance: str
    spot_instance: str
    on_demand_price: Optional[float] = None
    spot_price: Optional[float] = None
    savings_per_hour: Optional[float] = None
    savings_percent: Optional[float] = None
    estimated_monthly_savings: Optional[float] = None
    status: str = 'unavailable_without_matched_AZ_profile_and_workload'


@dataclass
class WhatIfScenario:
    scenario_name: str
    workload_id: str
    instance_type: str
    spot_usage_percent: float
    estimated_savings: Optional[float]
    estimated_interruptions: Optional[int]
    recommendation: str


class SpotInstanceRecommender:
    def __init__(self, region=None, pricing_client=None, ec2_client=None, cloudwatch_client=None):
        self.ec2_client = ec2_client or boto3.client('ec2', **({'region_name': region} if region else {}))
        self.region = self.ec2_client.meta.region_name
        if region is not None and region != self.region: raise ValueError('EC2 client region does not match requested region')
        self.pricing_client = pricing_client or boto3.client('pricing', region_name='us-east-1')
        self.cloudwatch_client = cloudwatch_client
        self.last_quote_report = None

    def recommend_spot_instances(self, workload_id) -> List[SpotRecommendation]:
        self.observe_instance_quotes(workload_id)
        return []  # Price references alone do not establish a workload recommendation.

    def observe_instance_quotes(self, workload_id):
        if not isinstance(workload_id, str) or not re.fullmatch(r'i-(?:[a-f0-9]{8}|[a-f0-9]{17})', workload_id):
            raise ValueError('Supply an EC2 instance ID; SageMaker/job-to-EC2 price mapping is not supported')
        response = self.ec2_client.describe_instances(InstanceIds=[workload_id])
        matches = [instance for reservation in response.get('Reservations', []) for instance in reservation.get('Instances', []) if instance.get('InstanceId') == workload_id]
        if len(matches) != 1: raise SpotQuoteUnavailable('Selected instance metadata is unavailable')
        instance = matches[0]
        placement = instance.get('Placement', {})
        kind, az = instance.get('InstanceType'), placement.get('AvailabilityZone')
        report = {'data_contract': 'spot_quote_observations_v2', 'workload_id': workload_id,
            'instance_type': kind, 'region': self.region, 'availability_zone': az,
            'observed_lifecycle': instance.get('InstanceLifecycle') or 'standard',
            'observed_state': instance.get('State', {}).get('Name'), 'observed_at': datetime.now(UTC).isoformat(),
            'status': 'unavailable', 'recommendations': [], 'suitable': None, 'interruption_risk': None,
            'current_billed_cost': None, 'realized_savings': None, 'estimated_monthly_savings': None,
            'on_demand_reference_usd_per_hour': None, 'spot_quote_usd_per_hour': None,
            'quoted_rate_difference_usd_per_hour': None, 'quoted_rate_difference_percent': None,
            'quote_profile': 'Linux_shared_on_demand_reference_vs_same_type_AZ_spot',
            'capacity_available_verified': False, 'workload_compatibility_verified': False,
            'future_price_verified': False}
        self.last_quote_report = report
        if (instance.get('PlatformDetails') != 'Linux/UNIX' or placement.get('Tenancy') != 'default'
                or not isinstance(kind, str) or not kind or not isinstance(az, str) or not az):
            report['reason'] = 'Instance profile is not covered by the Linux/shared quote adapter'
            return report
        reference = self._on_demand_reference(kind)
        quote = self._spot_quote(kind, az)
        if reference is not None:
            report['on_demand_reference_usd_per_hour'] = reference['price']
            report['on_demand_provenance'] = reference
        if quote is not None:
            report['spot_quote_usd_per_hour'] = quote['price']
            report['spot_provenance'] = quote
        if reference is not None and quote is not None:
            difference = reference['price']-quote['price']
            report['quoted_rate_difference_usd_per_hour'] = difference
            report['quoted_rate_difference_percent'] = difference/reference['price']*100.0
            report['status'] = 'observed_quote_comparison'
        elif reference is not None or quote is not None:
            report['status'] = 'partial_quote_observation'
        report['reason'] = 'Reference quotes do not establish billed cost, interruption probability, suitability or realized savings'
        return report

    def _on_demand_reference(self, instance_type):
        attributes = {'regionCode': self.region, 'instanceType': instance_type, 'operatingSystem': 'Linux',
                      'tenancy': 'Shared', 'preInstalledSw': 'NA', 'capacitystatus': 'Used', 'operation': 'RunInstances'}
        request = {'ServiceCode': 'AmazonEC2', 'MaxResults': 100,
            'Filters': [{'Type': 'TERM_MATCH', 'Field': key, 'Value': value} for key, value in attributes.items()]}
        matches, seen = {}, set()
        try:
            for page_number in range(20):
                response = self.pricing_client.get_products(**request)
                for encoded in response.get('PriceList', []):
                    item = json.loads(encoded) if isinstance(encoded, str) else encoded
                    product = item['product']
                    attrs = product['attributes']
                    if product.get('productFamily') != 'Compute Instance' or any(attrs.get(key) != value for key, value in attributes.items()): continue
                    rates = []
                    for term in item.get('terms', {}).get('OnDemand', {}).values():
                        if term.get('offerTermCode') != 'JRTCKXETXF' or term.get('termAttributes'): continue
                        if parse_utc_timestamp(term['effectiveDate']) > datetime.now(UTC): continue
                        for dimension in term.get('priceDimensions', {}).values():
                            if (dimension.get('unit') != 'Hrs' or dimension.get('beginRange') != '0' or dimension.get('endRange') != 'Inf'
                                    or dimension.get('appliesTo') or set(dimension.get('pricePerUnit', {})) != {'USD'}): continue
                            rate = Decimal(dimension['pricePerUnit']['USD'])
                            if not rate.is_finite() or rate <= 0 or not math.isfinite(float(rate)): return None
                            rates.append(float(rate))
                    if len(rates) != 1: return None
                    sku = product['sku']
                    if sku in matches and matches[sku] != rates[0]: return None
                    matches[sku] = rates[0]
                token = response.get('NextToken')
                if not token: break
                if token in seen: return None
                seen.add(token)
                request['NextToken'] = token
            else: return None
            if len(matches) != 1: return None
            sku, price = next(iter(matches.items()))
            return {'price': price, 'sku': sku, 'region': self.region, 'source': 'aws_pricing', 'unit': 'Hrs',
                    'currency': 'USD', 'scope': 'undiscounted_compute_reference_only', 'queried_at': datetime.now(UTC).isoformat()}
        except Exception: return None

    def _spot_quote(self, instance_type, az):
        end = datetime.now(UTC)
        request = {'InstanceTypes': [instance_type], 'AvailabilityZone': az,
            'ProductDescriptions': ['Linux/UNIX'], 'StartTime': end-timedelta(days=1), 'EndTime': end, 'MaxResults': 100}
        seen, points = set(), {}
        try:
            for page_number in range(20):
                response = self.ec2_client.describe_spot_price_history(**request)
                for point in response.get('SpotPriceHistory', []):
                    if point.get('InstanceType') != instance_type or point.get('AvailabilityZone') != az or point.get('ProductDescription') != 'Linux/UNIX': continue
                    stamp = parse_utc_timestamp(point['Timestamp'])
                    price = Decimal(point['SpotPrice'])
                    if stamp > end or not price.is_finite() or price <= 0 or not math.isfinite(float(price)): return None
                    if stamp in points and points[stamp] != price: return None
                    points[stamp] = price
                token = response.get('NextToken')
                if not token: break
                if token in seen: return None
                seen.add(token)
                request['NextToken'] = token
            else: return None
            if not points: return None
            stamp = max(points)
            return {'price': float(points[stamp]), 'price_change_time': stamp.isoformat(), 'queried_at': end.isoformat(),
                'region': self.region, 'availability_zone': az, 'instance_type': instance_type,
                'product': 'Linux/UNIX', 'source': 'ec2_spot_price_history', 'currency': 'USD', 'unit': 'Hrs',
                'scope': 'matching_AZ_type_effective_historical_quote_not_capacity_guarantee'}
        except Exception: return None

    def identify_spot_suitable_workloads(self): return []
    def calculate_spot_savings(self, current_instance, spot_instance): return SpotSavings(current_instance, spot_instance)
    def get_spot_interruption_risk(self, instance_type, az=None): return None
    def generate_what_if_scenarios(self, workload_id): return []
    def _get_workload_metadata(self, workload_id):
        return self.observe_instance_quotes(workload_id)
    def _is_spot_suitable(self, metadata): return None, 'Workload interruption tolerance and compatibility are unverified'
    def _is_gpu_instance(self, instance_type): return isinstance(instance_type, str) and re.fullmatch(r'[gp][0-9][a-z0-9-]*\.[a-z0-9]+', instance_type) is not None
    def _get_on_demand_price(self, instance_type):
        reference = self._on_demand_reference(instance_type)
        return reference['price'] if reference else None
    def _get_spot_price(self, instance_type): return None  # An explicit AZ is required.
    def _get_interruption_risk(self, instance_type, az=None): return None
