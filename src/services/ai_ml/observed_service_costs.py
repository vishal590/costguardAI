"""Bounded provider service/usage-type observations, without guessed model attribution."""
from datetime import datetime, timedelta, UTC
from decimal import Decimal
import math


class CostObservationUnavailable(RuntimeError):
    pass


def observe_service_costs(client, service, start_date, end_date):
    start, end = start_date.date(), end_date.date()
    days = (end-start).days
    if not 1 <= days <= 31 or end > datetime.now(UTC).date():
        raise ValueError('Use 1-31 completed daily dates with an exclusive end')
    expected = {(start+timedelta(days=offset)).isoformat() for offset in range(days)}
    request = {'TimePeriod': {'Start': start.isoformat(), 'End': end.isoformat()}, 'Granularity': 'DAILY',
        'Metrics': ['UnblendedCost'], 'Filter': {'Dimensions': {'Key': 'SERVICE', 'Values': [service]}},
        'GroupBy': [{'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'}]}
    rows, flags, seen = {}, {}, set()
    try:
        for page_number in range(100):
            response = client.get_cost_and_usage(**request)
            for period in response.get('ResultsByTime', []):
                day = period['TimePeriod']['Start']
                if day not in expected or period['TimePeriod']['End'] != (datetime.fromisoformat(day).date()+timedelta(days=1)).isoformat():
                    raise ValueError('Unexpected provider period')
                flag = period.get('Estimated')
                flag = flag if isinstance(flag, bool) else None
                if day not in flags: flags[day] = flag
                elif flags[day] is True or flag is True: flags[day] = True
                elif flags[day] is None or flag is None: flags[day] = None
                for group in period.get('Groups', []):
                    keys = group.get('Keys')
                    if not isinstance(keys, list) or len(keys) != 1 or not isinstance(keys[0], str) or not keys[0] or len(keys[0]) > 2048:
                        raise ValueError('Invalid usage type')
                    metric = group['Metrics']['UnblendedCost']
                    if metric.get('Unit') != 'USD' or isinstance(metric.get('Amount'), bool): raise ValueError('Unsupported amount/unit')
                    amount = Decimal(str(metric['Amount']))
                    if not amount.is_finite() or not math.isfinite(float(amount)): raise ValueError('Invalid amount')
                    identity = (day, keys[0])
                    if identity in rows and rows[identity] != amount: raise ValueError('Conflicting provider observations')
                    rows[identity] = amount
                    if len(rows) > 50000: raise ValueError('Provider observation limit exceeded')
            token = response.get('NextPageToken')
            if not token: break
            if token in seen: raise ValueError('Repeated provider token')
            seen.add(token)
            request['NextPageToken'] = token
        else: raise ValueError('Provider page limit exceeded')
        grouped = {}
        for (_, usage), amount in rows.items(): grouped[usage] = grouped.get(usage, Decimal('0'))+amount
        def total(values):
            if not values: return None
            amount = float(sum(values, Decimal('0')))
            if not math.isfinite(amount): raise ValueError('Invalid aggregate')
            return amount
        ordered = sorted(grouped.items(), key=lambda item: (-item[1], item[0]))
        selected = ordered[:100]
        dates = {day for day, _ in rows}
        return {'start_date': start.isoformat(), 'end_date': end.isoformat(), 'service_filter': service,
            'result_scope': 'observed_service_usage_costs', 'currency': 'USD' if rows else None,
            'total_cost': total(list(rows.values())), 'usage_type_count': len(grouped),
            'usage_types': [{'usage_type': usage, 'observed_cost': float(amount)} for usage, amount in selected],
            'usage_types_has_more': len(ordered) > len(selected), 'usage_type_row_limit': 100,
            'listed_usage_cost': total([amount for _, amount in selected]),
            'unlisted_usage_cost': total([amount for _, amount in ordered[100:]]),
            'data_quality': {'status': 'observed' if rows else 'no_observations', 'metric': 'UnblendedCost',
                'granularity': 'DAILY', 'missing_dates': sorted(expected-dates), 'complete_date_coverage': expected == dates,
                'estimated_dates': sorted(day for day in dates if flags.get(day) is True),
                'unknown_estimate_dates': sorted(day for day in dates if flags.get(day) is None),
                'invoice_coverage_verified': False, 'observed_at': datetime.now(UTC).isoformat()}}
    except Exception as error:
        raise CostObservationUnavailable('Provider service cost observations are unavailable') from error
