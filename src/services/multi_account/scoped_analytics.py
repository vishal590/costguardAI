"""Cross-account analytics built only from explicit permitted daily records."""
from dataclasses import asdict
from datetime import date, timedelta, datetime, UTC
from decimal import Decimal
from ...utils.types import ProcessedData, InsufficientDataError
from ..forecast_engine import ForecastEngine


class NoSharedCache:
    def get_cached_forecast(self, *args): return None
    def store_forecast(self, *args): pass


class ScopedHistory:
    def __init__(self, repository, account_ids, end=None):
        self.repository, self.account_ids = repository, account_ids
        self.end = end or datetime.now(UTC).date() - timedelta(days=1)
        self.coverage = {}

    def get_historical_data(self, service=None, days_back=30):
        start = self.end - timedelta(days=days_back-1)
        by_account, missing = {}, {}
        expected = {(start + timedelta(days=index)).isoformat() for index in range(days_back)}
        for account_id in self.account_ids:
            records = self.repository.list_range(account_id, start.isoformat(), self.end.isoformat())
            by_account[account_id] = {record.start_date: record for record in records}
            missing[account_id] = sorted(expected - set(by_account[account_id]))
        complete_days = sorted(set.intersection(*(set(records) for records in by_account.values()))) if by_account else []
        self.coverage = {'missing_dates_by_account': missing, 'complete_history': all(not dates for dates in missing.values()),
                         'observed_days': len(complete_days), 'expected_days': days_back}
        if len(complete_days) < 7: raise InsufficientDataError('At least 7 shared observed days are required for the selected accounts')
        costs = [float(sum((records[day].costs_by_service.get(service, Decimal('0')) if service else records[day].total_cost for records in by_account.values()), Decimal('0'))) for day in complete_days]
        return ProcessedData(timestamps=complete_days, costs=costs, service=service, total_days=len(complete_days),
            observed_days=len(complete_days), missing_dates=sorted(expected-set(complete_days)), history_method='observed_only', cost_metric='UnblendedCost',
            estimated_dates=[day for day in complete_days if any(records[day].is_estimated is True for records in by_account.values())],
            unknown_estimate_dates=[day for day in complete_days if any(records[day].is_estimated is None for records in by_account.values())])


def forecast_accounts(repository, account_ids, bedrock_client, days=30, granularity='daily'):
    history = ScopedHistory(repository, account_ids)
    engine = ForecastEngine(bedrock_client, history, NoSharedCache())
    forecast = engine.generate_forecast(days=days, granularity=granularity)
    return {'success': True, 'accounts': account_ids, 'forecast': asdict(forecast), 'coverage': history.coverage,
            'total_forecasted_cost': sum(point.predicted_cost for point in forecast.forecast_data)}


def observed_context(repository, account_ids, start, end):
    expected = {(date.fromisoformat(start) + timedelta(days=index)).isoformat() for index in range((date.fromisoformat(end)-date.fromisoformat(start)).days+1)}
    totals, services, missing = {}, {}, {}
    estimated, unknown_estimate = [], []
    for account_id in account_ids:
        records = repository.list_range(account_id, start, end)
        missing[account_id] = sorted(expected - {record.start_date for record in records})
        totals[account_id] = sum((record.total_cost for record in records), Decimal('0')) if records else None
        for record in records:
            if record.is_estimated is True: estimated.append({'account_id': account_id, 'date': record.start_date})
            if record.is_estimated is None: unknown_estimate.append({'account_id': account_id, 'date': record.start_date})
            for service, cost in record.costs_by_service.items(): services[service] = services.get(service, Decimal('0')) + cost
    total = sum((value for value in totals.values() if value is not None), Decimal('0')) if any(value is not None for value in totals.values()) else None
    return {'accounts': account_ids, 'start_date': start, 'end_date': end, 'total_cost': total, 'costs_by_account': totals,
            'costs_by_service': services, 'missing_dates_by_account': missing, 'complete': all(not dates for dates in missing.values()), 'estimated_observations': estimated, 'unknown_estimate_observations': unknown_estimate}
