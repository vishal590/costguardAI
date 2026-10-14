"""Opaque selection-bound audit scan continuations, not authorization or snapshot tokens."""
import base64
import hashlib
import json


def _scope(filters):
    return hashlib.sha256(json.dumps(filters, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _key(value):
    if not isinstance(value, dict) or set(value) != {'action_id'}: raise ValueError('Invalid audit cursor key')
    encoded = value['action_id']
    if not isinstance(encoded, dict) or set(encoded) != {'S'}: raise ValueError('Invalid audit cursor key')
    action_id = encoded['S']
    if not isinstance(action_id, str) or not 1 <= len(action_id) <= 256: raise ValueError('Invalid audit cursor key')
    return {'action_id': {'S': action_id}}


def encode_cursor(key, filters):
    value = {'v': 1, 'scope': _scope(filters), 'key': _key(key)}
    return base64.urlsafe_b64encode(json.dumps(value, separators=(',', ':')).encode()).decode()


def decode_cursor(token, filters):
    try:
        if not isinstance(token, str) or not 1 <= len(token) <= 2048: raise ValueError()
        value = json.loads(base64.b64decode(token, altchars=b'-_', validate=True))
        if not isinstance(value, dict) or set(value) != {'v', 'scope', 'key'} or type(value['v']) is not int or value['v'] != 1 or value['scope'] != _scope(filters):
            raise ValueError()
        return _key(value['key'])
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
        raise ValueError('Invalid audit continuation; restart the selection with the current dates and limit') from None
