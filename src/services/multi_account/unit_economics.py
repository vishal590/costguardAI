"""Unit economics with operator-supplied measurement provenance and complete coverage."""
from datetime import date, timedelta, datetime, UTC
from decimal import Decimal
import hashlib
import json
import os
import boto3
from .report_data import AllocationDataUnavailable


class UnitEconomics:
    def __init__(self, cost_repository):
        self.cost_repository = cost_repository
        self.table = boto3.resource('dynamodb').Table(os.environ.get('BUSINESS_METRICS_TABLE', 'costguard-business-metrics'))

    def key(self, account_id, metric_type, metric_name):
        if metric_type not in ('customer', 'transaction', 'feature') or not isinstance(metric_name, str) or not 1 <= len(metric_name.strip()) <= 128:
            raise ValueError('Supply a supported metric type and name')
        return account_id + ':' + hashlib.sha256(json.dumps([metric_type, metric_name]).encode()).hexdigest()

    def put(self, account_id, body, subject):
        key = self.key(account_id, body.get('metric_type'), body.get('metric_name'))
        day = body.get('date', '')
        if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day: raise ValueError('Use YYYY-MM-DD')
        if type(body.get('quantity')) not in (int, float): raise ValueError('Quantity must be a finite nonnegative number')
        quantity = Decimal(str(body['quantity']))
        if not quantity.is_finite() or quantity < 0: raise ValueError('Quantity must be a finite nonnegative number')
        from boto3.dynamodb.types import DYNAMODB_CONTEXT
        from decimal import DecimalException
        try: DYNAMODB_CONTEXT.create_decimal(quantity)
        except DecimalException as exc: raise ValueError('Quantity exceeds supported storage precision/range') from exc
        unit, source = body.get('unit_name'), body.get('source_reference')
        if not isinstance(unit, str) or not 1 <= len(unit.strip()) <= 64 or not isinstance(source, str) or not 1 <= len(source.strip()) <= 512:
            raise ValueError('Supply unit_name and source_reference')
        version = body.get('expected_version')
        if type(version) is not int or version < 0: raise ValueError('Supply a non-negative expected_version')
        item = dict(metric_key=key, date=day, account_id=account_id, metric_type=body['metric_type'], metric_name=body['metric_name'],
                    quantity=quantity, unit_name=unit, source_reference=source, submitted_by=subject, version=version+1, updated_at=datetime.now(UTC).isoformat())
        request = dict(Item=item, ConditionExpression='attribute_not_exists(metric_key)' if version == 0 else '#version = :expected')
        if version: request.update(ExpressionAttributeNames={'#version': 'version'}, ExpressionAttributeValues={':expected': version})
        self.table.put_item(**request)
        return item

    def volumes(self, account, kind, name, start, end):
        from boto3.dynamodb.conditions import Key
        request = {'KeyConditionExpression': Key('metric_key').eq(self.key(account, kind, name)) & Key('date').between(start, end), 'ConsistentRead': True}
        records = {}
        while True:
            response = self.table.query(**request)
            records.update({item['date']: item for item in response.get('Items', [])})
            if not response.get('LastEvaluatedKey'): break
            request['ExclusiveStartKey'] = response['LastEvaluatedKey']
        return records

    def calculate(self, accounts, params):
        start, end = date.fromisoformat(params['start_date']), date.fromisoformat(params['end_date'])
        if end < start or (end-start).days > 30: raise ValueError('Select at most 31 ordered calendar days')
        kind, name = params['metric_type'], params['metric_name']
        allocation_type, allocation_name = params.get('allocation_type'), params.get('allocation_name')
        mapping = {'team': 'Team', 'project': 'Project', 'environment': 'Environment'}
        if allocation_type not in mapping or not isinstance(allocation_name, str) or not 1 <= len(allocation_name) <= 256:
            raise ValueError('Supply a supported allocation type and name')
        category = mapping[allocation_type] + ':' + allocation_name
        total, quantity, missing_costs, missing_volumes, units, sources = Decimal('0'), Decimal('0'), [], [], set(), []
        observed_cost_records = 0
        estimated, unknown_estimate = [], []
        for account in accounts:
            records = {record.start_date: record for record in self.cost_repository.list_range(account, start.isoformat(), end.isoformat())}
            volumes = self.volumes(account, kind, name, start.isoformat(), end.isoformat())
            day = start
            while day <= end:
                stamp = day.isoformat()
                record, volume = records.get(stamp), volumes.get(stamp)
                if record is None or record.costs_by_tag_service is None: missing_costs.append({'account_id': account, 'date': stamp})
                else:
                    total += sum(record.costs_by_tag_service.get(category, {}).values(), Decimal('0'))
                    observed_cost_records += 1
                    if record.is_estimated is True: estimated.append({'account_id': account, 'date': stamp})
                    if record.is_estimated is None: unknown_estimate.append({'account_id': account, 'date': stamp})
                if volume is None: missing_volumes.append({'account_id': account, 'date': stamp})
                else:
                    quantity += volume['quantity']
                    units.add(volume['unit_name'])
                    sources.append({'account_id': account, 'date': stamp, 'source_reference': volume['source_reference'], 'version': volume['version']})
                day += timedelta(days=1)
        complete = not missing_costs and not missing_volumes and len(units) == 1
        reason = 'Incomplete daily cost or business-volume coverage' if missing_costs or missing_volumes else 'Business units differ' if len(units) != 1 else 'Zero denominator' if quantity == 0 else None
        return {'accounts': accounts, 'metric_type': kind, 'metric_name': name, 'allocation_type': allocation_type, 'allocation_name': allocation_name,
            'start_date': start.isoformat(), 'end_date': end.isoformat(), 'observed_cost': total if observed_cost_records else None, 'observed_quantity': quantity if sources else None, 'currency': 'USD',
            'unit_name': next(iter(units)) if len(units)==1 else None, 'unit_cost': total/quantity if complete and quantity > 0 else None,
            'complete': complete, 'reason': reason, 'missing_costs': missing_costs, 'missing_volumes': missing_volumes,
            'quantity_source': 'operator_provided', 'source_records': sources,
            'estimated_cost_observations': estimated, 'unknown_estimate_cost_observations': unknown_estimate}
