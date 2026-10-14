"""Versioned policy configuration; saving does not execute prevention actions."""
import os
from datetime import datetime, UTC
import boto3

ALLOWED = {'budget_limit', 'warning_percent', 'action_percent', 'excluded_resources', 'dry_run_mode', 'enabled'}


class PolicyStore:
    def __init__(self):
        self.table = boto3.resource('dynamodb').Table(os.environ.get('ORGANIZATION_POLICIES_TABLE', 'costguard-organization-policies'))

    def get(self, org_id, scope, entity_id):
        return self.table.get_item(Key={'scope_key': f'{org_id}:{scope}:{entity_id}'}, ConsistentRead=True).get('Item')

    def save(self, org_id, scope, entity_id, config, expected_version):
        if not isinstance(config, dict) or set(config)-ALLOWED: raise ValueError('Unknown policy configuration field')
        if type(expected_version) is not int or expected_version < 0: raise ValueError('Supply a non-negative expected_version')
        if config.get('enabled', False) is not False or config.get('dry_run_mode', True) is not True:
            raise ValueError('Policy preparation requires enabled=false and dry_run_mode=true')
        for key in ('budget_limit', 'warning_percent', 'action_percent'):
            if key in config and (type(config[key]) not in (int, float) or not 0 < config[key] <= (100 if key.endswith('percent') else 1000000000)):
                raise ValueError('Invalid ' + key)
        if config.get('warning_percent', 80) >= config.get('action_percent', 90): raise ValueError('Warning threshold must precede action threshold')
        excluded = config.get('excluded_resources', [])
        if not isinstance(excluded, list) or len(excluded)>100 or any(not isinstance(value, str) or not 1 <= len(value) <= 256 for value in excluded): raise ValueError('Supply at most 100 excluded resource IDs')
        from decimal import Decimal
        import json
        from boto3.dynamodb.types import DYNAMODB_CONTEXT
        from decimal import DecimalException
        for key in ("budget_limit", "warning_percent", "action_percent"):
            if key in config:
                try: DYNAMODB_CONTEXT.create_decimal(Decimal(str(config[key])))
                except DecimalException as exc: raise ValueError("Policy number exceeds supported storage precision/range") from exc
        normalized = json.loads(json.dumps({**config, 'enabled': False, 'dry_run_mode': True}), parse_float=Decimal)
        item = {'scope_key': f'{org_id}:{scope}:{entity_id}', 'organization_id': org_id, 'scope': scope,
                'entity_id': entity_id, 'config': normalized, 'version': expected_version+1, 'updated_at': datetime.now(UTC).isoformat()}
        request = {'Item': item, 'ConditionExpression': 'attribute_not_exists(scope_key)' if expected_version == 0 else '#version = :expected'}
        if expected_version:
            request.update(ExpressionAttributeNames={'#version': 'version'}, ExpressionAttributeValues={':expected': expected_version})
        self.table.put_item(**request)
        return item

    def effective(self, org_id, account_id, ou_ids):
        config, sources = {'enabled': False, 'dry_run_mode': True}, []
        for scope, entity in [('organization', org_id), *[('ou', ou_id) for ou_id in ou_ids], ('account', account_id)]:
            policy = self.get(org_id, scope, entity)
            if policy:
                config.update(policy['config'])
                sources.append({'scope': scope, 'entity_id': entity, 'version': policy['version']})
        return {'account_id': account_id, 'configuration': config, 'sources': sources, 'execution_enabled': False,
                'note': 'Configuration preview only; no policy was applied to resources'}
