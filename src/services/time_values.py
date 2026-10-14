"""Explicit UTC audit timestamps and inclusive calendar-date query boundaries."""
from datetime import datetime, date, time, timedelta, UTC
from decimal import Decimal, InvalidOperation


def parse_utc_timestamp(value):
    try:
        if isinstance(value, bool) or value is None: raise ValueError()
        try: numeric = Decimal(str(value))
        except InvalidOperation:
            moment = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        else:
            if not numeric.is_finite(): raise ValueError()
            moment = datetime.fromtimestamp(float(numeric), UTC)
        if moment.tzinfo is None: raise ValueError()
        return moment.astimezone(UTC)
    except (ValueError, TypeError, OverflowError, InvalidOperation):
        raise ValueError('Use finite UNIX seconds or an ISO timestamp with timezone') from None


def history_boundary(value, end=False):
    if isinstance(value, str) and len(value) == 10 and value[4] == '-' and value[7] == '-':
        day = date.fromisoformat(value)
        if day.isoformat() != value: raise ValueError('Use YYYY-MM-DD')
        moment = datetime.combine(day, time.min, UTC)
        return moment+timedelta(days=1)-timedelta(microseconds=1) if end else moment
    return parse_utc_timestamp(value)
