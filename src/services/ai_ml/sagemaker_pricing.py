"""Strict regional on-demand compute component lookup, without billing/savings inference."""
from dataclasses import dataclass
from datetime import datetime, UTC
from decimal import Decimal
import json
import math
import re
from ..time_values import parse_utc_timestamp


@dataclass(frozen=True)
class SageMakerComputeRate:
    hourly_usd: Decimal
    instance_type: str
    region: str
    component: str
    sku: str
    queried_at: str
    source: str = 'aws_pricing'
    scope: str = 'on_demand_compute_component_only'

    def provenance(self):
        return {'source': self.source, 'scope': self.scope, 'region': self.region,
                'instance_type': self.instance_type, 'component': self.component,
                'sku': self.sku, 'currency': 'USD', 'unit': 'Hrs', 'queried_at': self.queried_at}


def lookup_compute_rate(client, region, instance_type, job_type):
    """Return one exact unambiguous matching SKU or None; never choose the first product."""
    component = {'training': 'Training', 'hosting': 'Hosting'}.get(job_type)
    if (component is None or not isinstance(region, str) or not re.fullmatch(r'[a-z]{2}(?:-[a-z]+)+-\d+', region)
            or not isinstance(instance_type, str) or not re.fullmatch(r'ml\.[a-z0-9-]+\.[a-z0-9]+', instance_type)):
        return None
    usage_kind = 'Train' if component == 'Training' else 'Host'
    request = {'ServiceCode': 'AmazonSageMaker', 'MaxResults': 100,
               'Filters': [{'Type': 'TERM_MATCH', 'Field': key, 'Value': value} for key, value in
                   [('regionCode', region), ('instanceName', instance_type), ('component', component), ('operation', 'RunInstance')]]}
    seen, matches = set(), {}
    try:
        for page_number in range(20):
            response = client.get_products(**request)
            for encoded in response.get('PriceList', []):
                item = json.loads(encoded) if isinstance(encoded, str) else encoded
                product, terms = item['product'], item['terms']
                attrs = product['attributes']
                if (product.get('productFamily') != 'ML Instance' or attrs.get('servicecode') != 'AmazonSageMaker'
                        or attrs.get('regionCode') != region or attrs.get('locationType') != 'AWS Region'
                        or attrs.get('instanceName') != instance_type or attrs.get('instanceType') != f'{instance_type}-{component}'
                        or attrs.get('component') != component or attrs.get('operation') != 'RunInstance'):
                    continue
                usage = attrs.get('usagetype', '')
                if usage != f'{usage_kind}:{instance_type}' and not usage.endswith(f'-{usage_kind}:{instance_type}'):
                    continue
                rates = []
                for term in terms.get('OnDemand', {}).values():
                    if term.get('offerTermCode') != 'JRTCKXETXF' or term.get('termAttributes'):
                        continue
                    if parse_utc_timestamp(term['effectiveDate']) > datetime.now(UTC): continue
                    for dimension in term.get('priceDimensions', {}).values():
                        if (dimension.get('unit') != 'Hrs' or dimension.get('beginRange') != '0'
                                or dimension.get('endRange') != 'Inf' or dimension.get('appliesTo')
                                or set(dimension.get('pricePerUnit', {})) != {'USD'}):
                            continue
                        rate = Decimal(dimension['pricePerUnit']['USD'])
                        if not rate.is_finite() or rate <= 0 or not math.isfinite(float(rate)): return None
                        rates.append(rate)
                if len(rates) != 1: return None
                sku = product['sku']
                if sku in matches and matches[sku] != rates[0]: return None
                matches[sku] = rates[0]
            token = response.get('NextToken')
            if not token: break
            if token in seen: return None
            seen.add(token)
            request['NextToken'] = token
        else:
            return None
        if len(matches) != 1: return None
        sku, rate = next(iter(matches.items()))
        return SageMakerComputeRate(rate, instance_type, region, component, sku, datetime.now(UTC).isoformat())
    except Exception:
        return None
