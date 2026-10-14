"""Opaque filter-bound cursors for cost-history keyset pages (not snapshots)."""
import base64
import hashlib
import json
from datetime import datetime


def _scope(filters):
    return hashlib.sha256(json.dumps(filters, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def encode_cursor(record, filters):
    value = {'v': 1, 'filters': _scope(filters), 'date': record.date, 'service': record.service}
    return base64.urlsafe_b64encode(json.dumps(value, separators=(',', ':')).encode()).decode()


def decode_cursor(token, filters):
    try:
        if not isinstance(token, str) or not 1 <= len(token) <= 2048: raise ValueError()
        value = json.loads(base64.b64decode(token, altchars=b'-_', validate=True))
        if value.get('v') != 1 or value.get('filters') != _scope(filters): raise ValueError()
        moment, service = value['date'], value['service']
        if not isinstance(moment, str) or len(moment) > 40: raise ValueError()
        datetime.fromisoformat(moment.replace('Z', '+00:00'))
        if not isinstance(service, str) or not 1 <= len(service) <= 256: raise ValueError()
        return moment, service
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError('Invalid cost-history cursor; start a new page for the selected filters') from None
