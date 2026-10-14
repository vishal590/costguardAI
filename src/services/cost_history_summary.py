"""Aggregate observed stored DAILY rows without manufacturing missing-day zeros."""
from datetime import date, timedelta


def summarize_daily_history(records, start, end):
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if last < first or (last-first).days > 30: raise ValueError('Select at most 31 ordered daily dates')
    currencies = {record.currency for record in records}
    if len(currencies) > 1: raise ValueError('Stored records use mixed currencies; no combined summary is available')
    by_date, by_service = {}, {}
    for record in records:
        by_date.setdefault(record.date, []).append(record)
        by_service[record.service] = by_service.get(record.service, 0.0)+record.blended_cost
    days = []
    for index in range((last-first).days+1):
        stamp = (first+timedelta(days=index)).isoformat()
        observations = by_date.get(stamp, [])
        days.append({'date': stamp, 'observed_cost': sum(record.blended_cost for record in observations) if observations else None,
            'record_count': len(observations),
            'is_estimated': True if any(record.is_estimated is True for record in observations) else None if not observations or any(record.is_estimated is None for record in observations) else False})
    return {'success': True, 'scope': 'stored_daily_records', 'cost_metric': 'BlendedCost',
        'currency': next(iter(currencies)) if currencies else None,
        'observed_total': sum(record.blended_cost for record in records) if records else None,
        'record_count': len(records), 'by_service': by_service, 'daily': days,
        'missing_dates': [point['date'] for point in days if point['observed_cost'] is None],
        'complete_date_coverage': all(point['observed_cost'] is not None for point in days),
        'invoice_coverage_verified': False, 'period_start': start, 'period_end': end}
