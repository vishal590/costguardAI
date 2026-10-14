"""Read-only, account-filtered commitment utilization and coverage evidence."""
from datetime import date, timedelta, datetime, UTC
from decimal import Decimal
import boto3
from botocore.exceptions import ClientError


def analyze_commitments(accounts, start, end, client=None):
    client = client or boto3.client('ce')
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if last < first or (last-first).days > 30: raise ValueError('Select at most 31 ordered calendar days')
    period = {'Start': first.isoformat(), 'End': (last+timedelta(days=1)).isoformat()}
    selection = {'Dimensions': {'Key': 'LINKED_ACCOUNT', 'Values': accounts}}
    sections = {}
    operations = [('reservation_utilization', 'get_reservation_utilization', 'UtilizationsByTime', 'NextPageToken'),
        ('reservation_coverage', 'get_reservation_coverage', 'CoveragesByTime', 'NextPageToken'),
        ('savings_plans_utilization', 'get_savings_plans_utilization', 'SavingsPlansUtilizationsByTime', None),
        ('savings_plans_coverage', 'get_savings_plans_coverage', 'SavingsPlansCoverages', 'NextToken'),
        ('savings_plans_inventory', 'get_savings_plans_utilization_details', 'SavingsPlansUtilizationDetails', 'NextToken')]
    for label, operation, field, token_name in operations:
        request = {'TimePeriod': period, 'Filter': selection}
        if operation != 'get_savings_plans_utilization_details': request['Granularity'] = 'DAILY'
        if operation == 'get_reservation_utilization':
            request.pop('Granularity')
            request['GroupBy'] = [{'Type': 'DIMENSION', 'Key': 'SUBSCRIPTION_ID'}]
        records, total, seen = [], None, set()
        try:
            while True:
                page = getattr(client, operation)(**request)
                records.extend(page.get(field, []))
                if total is None: total = page.get('Total')
                token = page.get(token_name) if token_name else None
                if not token: break
                if token in seen: raise ValueError('Repeated commitment page token')
                seen.add(token)
                request[token_name] = token
            sections[label] = {'status': 'available', 'records': records, 'total': total}
        except ClientError as exc:
            sections[label] = {'status': 'unavailable', 'error_code': exc.response['Error']['Code'], 'records': None, 'total': None}
    ri = sections['reservation_utilization'].get('total') or {}
    sp = (sections['savings_plans_utilization'].get('total') or {}).get('Utilization') or {}
    def money(value):
        try:
            amount = Decimal(value)
            return amount if amount.is_finite() and amount >= 0 else None
        except Exception: return None
    unused_ri = [money(ri.get(name)) for name in ('UnusedRecurringFee', 'UnusedAmortizedUpfrontFee')]
    unused = {'ri_unused_fees': sum(unused_ri) if all(value is not None for value in unused_ri) else None,
              'savings_plans_unused_commitment': money(sp.get('UnusedCommitment'))}
    return {'accounts': accounts, 'start_date': start, 'end_date': end, 'retrieved_at': datetime.now(UTC).isoformat(),
            'source': 'aws_cost_explorer', 'sections': sections, 'unused_cost_indicators': unused,
            'complete': all(section['status']=='available' for section in sections.values()),
            'recommendations': [{'type': 'review_unused_commitments', 'message': 'Review workload coverage for the observed unused commitments before considering additional commitments.'}] if any(value is not None and value > 0 for value in unused.values()) else [], 'note': 'Historical utilization, coverage and unused-cost indicators only. No commitments are purchased or modified. Cost Explorer may lag billing.'}
