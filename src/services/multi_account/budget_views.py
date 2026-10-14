"""Measured organization budget views; configured limits never imply observed spend."""
from datetime import date, datetime, timedelta, UTC
from decimal import Decimal
from .models import EntityType


def _period_start(day, period):
    month = 1 if period == 'ANNUAL' else ((day.month-1)//3)*3+1 if period == 'QUARTERLY' else day.month
    return day.replace(month=month, day=1)


def build_budget_hierarchy(discovery, repository, costs, org_id, as_of):
    day = date.fromisoformat(as_of)
    if day > datetime.now(UTC).date(): raise ValueError('Budget observation date cannot be in the future')
    accounts = {account.id: account for account in discovery.get_all_accounts(org_id)}
    hierarchy = discovery.get_ou_hierarchy(org_id)
    reads = {}

    def summary(entity_id, entity_type, account_ids):
        budgets = repository.list_by_entity(entity_id, entity_type)
        rows = []
        for budget in budgets:
            period = budget['period']
            if period not in ('MONTHLY', 'QUARTERLY', 'ANNUAL'):
                rows.append({'budget_id': budget['budget_id'], 'status': 'UNSUPPORTED_PERIOD', 'actual_spend': None})
                continue
            start = _period_start(day, period).isoformat()
            expected = {(date.fromisoformat(start)+timedelta(days=index)).isoformat() for index in range((day-date.fromisoformat(start)).days+1)}
            observed, missing, observed_accounts = Decimal('0'), {}, 0
            estimated, unknown_estimate = [], []
            for account_id in account_ids:
                key = (account_id, start, as_of)
                if key not in reads: reads[key] = costs.list_range(account_id, start, as_of)
                records = reads[key]
                dates = {record.start_date for record in records}
                missing[account_id] = sorted(expected-dates)
                observed += sum((record.total_cost for record in records), Decimal('0'))
                observed_accounts += bool(records)
                estimated.extend({'account_id': account_id, 'date': record.start_date} for record in records if record.is_estimated is True)
                unknown_estimate.extend({'account_id': account_id, 'date': record.start_date} for record in records if record.is_estimated is None)
            limit = budget['budget_amount']
            complete = bool(account_ids) and not any(missing.values())
            currency = budget.get('currency', 'USD')
            supported = currency == 'USD' and limit.is_finite() and limit > 0
            total = float(observed) if complete and supported else None
            utilization = float(observed/limit*100) if total is not None else None
            rows.append({'budget_id': budget['budget_id'], 'budget_name': budget.get('budget_name'),
                'budget_limit': float(limit) if limit.is_finite() else None, 'currency': currency,
                'time_unit': period, 'period_start': start, 'as_of': as_of,
                'actual_spend': total, 'observed_spend': float(observed) if observed_accounts else None,
                'forecasted_spend': None, 'utilization_percentage': utilization,
                'complete': complete and supported, 'missing_dates_by_account': missing,
                'estimated_observations': estimated, 'unknown_estimate_observations': unknown_estimate,
                'status': ('EXCEEDED' if utilization >= 100 else 'WARNING' if utilization >= 80 else 'OK') if utilization is not None else 'DATA_UNAVAILABLE'})
        if len(rows) == 1: return rows[0]
        return {'budget_id': None, 'budget_limit': None, 'actual_spend': None, 'forecasted_spend': None,
            'utilization_percentage': None, 'complete': False,
            'status': 'MULTIPLE_BUDGETS' if rows else 'NO_BUDGET', 'budgets': rows}

    children = {}
    for ou in hierarchy.ous: children.setdefault(ou.parent_id, []).append(ou.id)
    def ou_accounts(ou_id):
        selected = set(hierarchy.accounts_by_ou.get(ou_id, [])) & set(accounts)
        for child in children.get(ou_id, []): selected.update(ou_accounts(child))
        return sorted(selected)
    assigned = {account_id for members in hierarchy.accounts_by_ou.values() for account_id in members}
    def account_row(account_id):
        return {'account_id': account_id, 'account_name': accounts[account_id].name,
            **summary(account_id, EntityType.ACCOUNT.value, [account_id])}
    return {'organization': summary(org_id, EntityType.ORGANIZATION.value, sorted(accounts)),
        'organizational_units': [{'ou_id': ou.id, 'ou_name': ou.name, 'parent_id': ou.parent_id,
            **summary(ou.id, EntityType.OU.value, ou_accounts(ou.id)),
            'accounts': [account_row(account_id) for account_id in hierarchy.accounts_by_ou.get(ou.id, []) if account_id in accounts]}
            for ou in hierarchy.ous],
        'accounts': [account_row(account_id) for account_id in sorted(set(accounts)-assigned)],
        'as_of': as_of, 'source': 'configured_limits_and_observed_daily_costs',
        'forecast_status': 'unavailable', 'execution_enabled': False}
