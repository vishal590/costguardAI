"""Consistent strict JSON-object requests for HTTP handlers and delegation."""
import base64
import binascii
import json
import math


class RequestBodyError(ValueError):
    pass


def _constant(value):
    raise RequestBodyError('Non-finite JSON numbers are unsupported')


def _number(value):
    parsed = float(value)
    if not math.isfinite(parsed): raise RequestBodyError('Non-finite JSON numbers are unsupported')
    return parsed


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise RequestBodyError('Duplicate JSON object keys are unsupported')
        result[key] = value
    return result


def prepare_json_body(event):
    """Validate an object and normalize base64/dict inputs without changing text bytes."""
    try:
        original = event.get('body')
        raw = json.dumps(original, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode() if isinstance(original, dict) else b'' if original is None else original
        if isinstance(raw, str): raw = raw.encode('utf-8')
        if not isinstance(raw, bytes): raise RequestBodyError('Request body must be a JSON object')
        if event.get('isBase64Encoded'): raw = base64.b64decode(raw, validate=True)
        text = raw.decode('utf-8')
        parsed = json.loads(text, parse_constant=_constant, parse_float=_number, object_pairs_hook=_object) if raw else {}
        if not isinstance(parsed, dict): raise RequestBodyError('Request body must be a JSON object')
        if event.get('isBase64Encoded') or isinstance(original, (dict, bytes)):
            event['body'] = text
            event['isBase64Encoded'] = False
        return parsed
    except RequestBodyError:
        raise
    except (ValueError, TypeError, UnicodeError, binascii.Error, RecursionError):
        raise RequestBodyError('Request body must be valid UTF-8 JSON with one object') from None
