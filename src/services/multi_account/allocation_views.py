"""Measured single-dimension allocation across explicitly selected accounts."""
from datetime import date, timedelta
from decimal import Decimal
from .report_data import AllocationDataUnavailable


def allocation_view(repository, accounts, start, end, tag_key):
    if tag_key not in ('Team', 'Project', 'Environment'): raise ValueError('Choose Team, Project or Environment')
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if not accounts or len(accounts) > 25 or last < first or (last-first).days > 30:
        raise ValueError('Select 1-25 accounts and at most 31 ordered days')
    expected = {(first+timedelta(days=index)).isoformat() for index in range((last-first).days+1)}
    groups, remaining_service, remaining_account = {}, {}, {}
    total, allocated = Decimal('0'), Decimal('0')
    estimated, unknown_estimate = [], []
    for account_id in accounts:
        records = {record.start_date: record for record in repository.list_range(account_id, start, end)}
        if set(records) != expected or any(record.costs_by_tag_service is None for record in records.values()):
            raise AllocationDataUnavailable('Complete daily tag/service coverage is unavailable for selected accounts and dates')
        for record in records.values():
            total += record.total_cost
            if record.is_estimated is True: estimated.append({'account_id': account_id, 'date': record.start_date})
            if record.is_estimated is None: unknown_estimate.append({'account_id': account_id, 'date': record.start_date})
            tagged_by_service, account_allocated = {}, Decimal('0')
            for category, services in record.costs_by_tag_service.items():
                if not category.startswith(tag_key+':'): continue
                name = category.split(':', 1)[1]
                if not name: continue
                row = groups.setdefault(name, {'total_cost': Decimal('0'), 'currency': 'USD', 'by_service': {}, 'by_account': {}})
                for service, cost in services.items():
                    row['total_cost'] += cost
                    row['by_service'][service] = row['by_service'].get(service, Decimal('0'))+cost
                    row['by_account'][account_id] = row['by_account'].get(account_id, Decimal('0'))+cost
                    tagged_by_service[service] = tagged_by_service.get(service, Decimal('0'))+cost
                    allocated += cost
                    account_allocated += cost
            remaining_account[account_id] = remaining_account.get(account_id, Decimal('0'))+record.total_cost-account_allocated
            for service in set(record.costs_by_service) | set(tagged_by_service):
                remaining_service[service] = remaining_service.get(service, Decimal('0'))+record.costs_by_service.get(service, Decimal('0'))-tagged_by_service.get(service, Decimal('0'))
    def numbers(value):
        if isinstance(value, Decimal): return float(value)
        if isinstance(value, dict): return {key: numbers(item) for key, item in value.items()}
        return value
    return numbers({'allocated_costs': groups,
        'unallocated_costs': {'total_cost': total-allocated, 'currency': 'USD',
            'percentage_of_total': (total-allocated)/total*100 if total else None,
            'by_service': remaining_service, 'by_account': remaining_account,
            'untagged_resources': [], 'resource_detail_available': False},
        'total_observed_cost': total, 'complete': True, 'account_ids': accounts,
        'tag_key': tag_key, 'period_start': start, 'period_end': end,
        'estimated_observations': estimated, 'unknown_estimate_observations': unknown_estimate,
        'allocation_method': 'observed_single_tag_dimension', 'rules_applied': False})
