"""Forecast explicit account histories; never substitute the main account's data."""
from decimal import Decimal
from .scoped_analytics import forecast_accounts, ScopedHistory


class CrossAccountForecastService:
    def __init__(self, forecast_engine, account_repository, cost_repository):
        self.forecast_engine = forecast_engine
        self.account_repo = account_repository
        self.cost_repo = cost_repository

    def _forecast(self, account_ids, days, granularity, identity):
        if not account_ids:
            return {**identity, 'forecast_data': [], 'total_forecasted_cost': None, 'account_count': 0,
                    'error': 'No permitted accounts selected', 'coverage': {'complete_history': False}}
        result = forecast_accounts(self.cost_repo, sorted(set(account_ids)), self.forecast_engine.bedrock_client, days, granularity)
        return {**identity, 'forecast_data': result['forecast']['forecast_data'],
                'total_forecasted_cost': Decimal(str(result['total_forecasted_cost'])),
                'account_count': len(set(account_ids)), 'forecast_horizon': days, 'granularity': granularity,
                'timestamp': result['forecast']['metadata']['timestamp'], 'coverage': result['coverage']}

    def forecast_organization_costs(self, org_id, days=30, granularity='daily', account_ids=None):
        members = {account.id for account in self.account_repo.list_by_organization(org_id)}
        selected = sorted(members) if account_ids is None else account_ids
        if not set(selected).issubset(members): raise ValueError('Accounts must belong to the selected organization')
        return self._forecast(selected, days, granularity, {'org_id': org_id})

    def forecast_ou_costs(self, ou_id, account_ids, days=30, granularity='daily'):
        # The calling service must supply the authorized OU membership selection.
        return self._forecast(account_ids, days, granularity, {'ou_id': ou_id})

    def forecast_account_costs(self, account_id, days=30, granularity='daily'):
        return self._forecast([account_id], days, granularity, {'account_id': account_id})

    def _aggregate_historical_data(self, account_ids):
        history = ScopedHistory(self.cost_repo, account_ids)
        data = history.get_historical_data()
        return {'costs_by_day': dict(zip(data.timestamps, map(lambda value: Decimal(str(value)), data.costs))),
                'total_cost': sum((Decimal(str(value)) for value in data.costs), Decimal('0')),
                'account_count': len(account_ids), 'coverage': history.coverage}
