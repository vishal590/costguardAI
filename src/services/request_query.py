"""Strict single-valued HTTP query selections without silent duplicate collapse."""
from urllib.parse import parse_qsl


def single_valued_query(event, allowed, maximum_value_length=2048):
    single, multiple = event.get('queryStringParameters') or {}, event.get('multiValueQueryStringParameters') or {}
    if not isinstance(single, dict) or not isinstance(multiple, dict): raise ValueError('Invalid query parameter representation')
    params = dict(single)
    for name, values in multiple.items():
        if not isinstance(values, list) or len(values) != 1: raise ValueError('Repeated query parameters are unsupported')
        if name in params and params[name] != values[0]: raise ValueError('Conflicting query parameter representations')
        params[name] = values[0]
    raw = event.get('rawQueryString')
    if raw is not None:
        if not isinstance(raw, str): raise ValueError('Invalid query string')
        parsed = {}
        for name, value in parse_qsl(raw, keep_blank_values=True, max_num_fields=16):
            if name in parsed: raise ValueError('Repeated query parameters are unsupported')
            parsed[name] = value
        if params and parsed != params: raise ValueError('Conflicting query parameter representations')
        params = parsed
    if set(params)-set(allowed): raise ValueError('Unsupported query parameter')
    if any(not isinstance(value, str) or not value or len(value) > maximum_value_length for value in params.values()):
        raise ValueError('Query values must be nonempty bounded text')
    return params
