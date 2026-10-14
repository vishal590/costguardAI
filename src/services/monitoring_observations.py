"""Bounded stored monitoring observations; missing fields remain unavailable."""
import json
import math
from datetime import datetime, timedelta, UTC
from .time_values import parse_utc_timestamp


def _bounded(value, depth=0):
    if depth > 12: raise ValueError('Monitoring observation is too deeply nested')
    if value is None or isinstance(value, bool): return
    if isinstance(value, (int, float)):
        if not math.isfinite(value): raise ValueError('Non-finite observation number')
    elif isinstance(value, str):
        if len(value) > 4096: raise ValueError('Observation text exceeds limit')
    elif isinstance(value, list):
        if len(value) > 100: raise ValueError('Observation list exceeds limit')
        for child in value: _bounded(child, depth+1)
    elif isinstance(value, dict):
        if len(value) > 100 or any(not isinstance(key, str) or len(key) > 256 for key in value): raise ValueError('Invalid observation map')
        for child in value.values(): _bounded(child, depth+1)
    else: raise ValueError('Unsupported observation value')


def _text(value, maximum=4096):
    if not isinstance(value, str) or not value or len(value) > maximum: raise ValueError('Invalid observation text')


def _count(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0: raise ValueError('Invalid observation count')


def _date(value):
    if not isinstance(value, str): raise ValueError('Observation time must be explicit text')
    moment = parse_utc_timestamp(value)
    if moment > datetime.now(UTC)+timedelta(minutes=5): raise ValueError('Observation time is in the future')
    return moment


def _examples(value, maximum, text_fields):
    if not isinstance(value, list) or len(value) > maximum: raise ValueError('Observation examples exceed limit')
    for item in value:
        if not isinstance(item, dict): raise ValueError('Observation example must be an object')
        for field in text_fields: _text(item.get(field))


def _inventory_persistence(report):
    if not isinstance(report, dict) or type(report.get('schema_version')) is not int or report['schema_version'] != 2:
        raise ValueError('Unknown inventory persistence report')
    statuses = {'not_configured', 'account_scope_not_configured', 'partial_or_unavailable',
        'observations_persisted', 'newer_observations_retained'}
    if report.get('status') not in statuses: raise ValueError('Invalid inventory persistence status')
    for field in ('requested_rows', 'attempted_rows', 'stored_rows', 'failed_rows', 'superseded_rows'):
        _count(report.get(field))
    if (report['attempted_rows'] > report['requested_rows']
            or report['stored_rows']+report['failed_rows']+report['superseded_rows'] != report['attempted_rows']):
        raise ValueError('Inconsistent inventory persistence counters')
    if report.get('snapshot_complete') is not False or report.get('legacy_rows_migrated') is not False:
        raise ValueError('Unsupported inventory completeness claim')
    if report.get('account_scope_basis') != 'configured_backend_account_not_independently_verified':
        raise ValueError('Unsupported inventory account scope')
    _examples(report.get('failure_examples'), 20, ('resource_id', 'service', 'region', 'reason'))
    if len(report['failure_examples']) > report['failed_rows']:
        raise ValueError('Inconsistent inventory failure examples')
    expected_truncation = report['failed_rows'] > len(report['failure_examples'])
    if not isinstance(report.get('failure_examples_truncated'), bool) or report['failure_examples_truncated'] != expected_truncation:
        raise ValueError('Invalid inventory example omission flag')
    status = report['status']
    if status in ('not_configured', 'account_scope_not_configured'):
        if report['attempted_rows'] != 0: raise ValueError('Unconfigured inventory attempted writes')
    else:
        if report['attempted_rows'] != report['requested_rows']: raise ValueError('Unreported inventory write omission')
        if _date(report.get('completed_at')) < _date(report.get('observed_at')):
            raise ValueError('Inventory persistence completion precedes observation')
        if status == 'partial_or_unavailable' and not report['failed_rows']:
            raise ValueError('Invalid failed inventory status')
        if status != 'partial_or_unavailable' and report['failed_rows']:
            raise ValueError('Unreported inventory failure')
        if (status == 'newer_observations_retained') != (report['superseded_rows'] > 0) and status != 'partial_or_unavailable':
            raise ValueError('Inconsistent superseded inventory status')


def _listing_reports(reports):
    if not isinstance(reports, list) or len(reports) > 50: raise ValueError('Invalid listing reports')
    for report in reports:
        if not isinstance(report, dict): raise ValueError('Invalid listing report')
        _text(report.get('service'), 128); _text(report.get('operation'), 128)
        for field in ('page_limit', 'item_limit', 'pages_read', 'listed_items_seen', 'retained_items'):
            _count(report.get(field))
        if (report['page_limit'] != 5 or report['item_limit'] != 100 or report['pages_read'] > 5
                or report['retained_items'] > min(100, report['listed_items_seen'])):
            raise ValueError('Inconsistent listing bounds')
        if not isinstance(report.get('bound_reached'), bool) or not isinstance(report.get('provider_listing_exhausted'), bool):
            raise ValueError('Invalid listing flags')
        status = report.get('status')
        if status not in ('bounded_selection', 'observed_provider_pages', 'unavailable_or_partial'):
            raise ValueError('Invalid listing status')
        if status == 'bounded_selection' and not report['bound_reached']:
            raise ValueError('Unreported listing bound')
        if status == 'observed_provider_pages' and (report['bound_reached'] or not report['provider_listing_exhausted']):
            raise ValueError('Unsupported listing exhaustion claim')


def _report(report):
    if not isinstance(report, dict): raise ValueError('Discovery report must be an object')
    if 'inventory_persistence' in report: _inventory_persistence(report['inventory_persistence'])
    if 'listing_reports' in report: _listing_reports(report['listing_reports'])
    for field in ('requested_services',):
        if field in report:
            if not isinstance(report[field], list) or len(report[field]) > 22: raise ValueError('Invalid requested services')
            for service in report[field]: _text(service, 64)
    for field in ('reported_issue_count', 'raw_observation_count', 'unique_observed_resources', 'duplicate_observation_count', 'conflicting_resource_count'):
        if field in report: _count(report[field])
    if 'service_results' in report:
        _examples(report['service_results'], 22, ('service',))
        for item in report['service_results']:
            for field in ('observed_resources', 'reported_issue_count'):
                if field in item: _count(item[field])
            if 'requested_services' in item:
                if not isinstance(item['requested_services'], list) or len(item['requested_services']) > 22: raise ValueError('Invalid adapter scope')
                for service in item['requested_services']: _text(service, 64)
    if 'issue_examples' in report: _examples(report['issue_examples'], 50, ('service', 'category'))
    for field in ('started_at', 'completed_at'):
        if field in report: _date(report[field])


def validate_summary(summary):
    if not isinstance(summary, dict): raise ValueError('Cycle summary must be an object')
    _bounded(summary)
    if len(json.dumps(summary, allow_nan=False).encode()) > 192*1024: raise ValueError('Cycle summary exceeds limit')
    if 'completed_at' in summary: _date(summary['completed_at'])
    for field in ('discovered_resources', 'low_usage_rule_matches', 'planned_review_candidates', 'triggering_budget_count', 'action_requests_accepted'):
        if field in summary: _count(summary[field])
    for field in ('evidence_counts', 'unavailable_evidence_reasons'):
        if field in summary:
            if not isinstance(summary[field], dict) or len(summary[field]) > 50: raise ValueError('Invalid evidence counters')
            for value in summary[field].values(): _count(value)
    if 'candidate_examples' in summary: _examples(summary['candidate_examples'], 20, ('resource_id', 'resource_type', 'action', 'reason'))
    if 'unavailable_evidence_examples' in summary: _examples(summary['unavailable_evidence_examples'], 20, ('resource_id', 'service', 'region', 'reason'))
    if 'triggering_budget_examples' in summary:
        if not isinstance(summary['triggering_budget_examples'], list) or len(summary['triggering_budget_examples']) > 20: raise ValueError('Invalid budget examples')
        for name in summary['triggering_budget_examples']: _text(name, 256)
    if 'discovery_report' in summary: _report(summary['discovery_report'])
    for field in ('discovery_performed', 'candidate_examples_truncated', 'triggering_budget_examples_truncated', 'unavailable_evidence_examples_truncated'):
        if field in summary and not isinstance(summary[field], bool): raise ValueError('Invalid summary flag')
    return summary


def validate_outcome(outcome):
    if not isinstance(outcome, dict): raise ValueError('Cycle outcome must be an object')
    _bounded(outcome)
    if outcome.get('status') not in ('success', 'failed', 'skipped'): raise ValueError('Unknown cycle status')
    if _date(outcome.get('started_at')) > _date(outcome.get('completed_at')): raise ValueError('Reversed cycle times')
    if outcome.get('summary') is not None: validate_summary(outcome['summary'])
    for field in ('reason', 'error_code'):
        if outcome.get(field) is not None: _text(outcome[field], 256)
    if len(json.dumps(outcome, allow_nan=False).encode()) > 224*1024: raise ValueError('Cycle outcome exceeds limit')
    return outcome
