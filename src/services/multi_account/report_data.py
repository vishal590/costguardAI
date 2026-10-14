"""Measured daily entity/service allocations and safe CSV cells."""
import csv
from datetime import date, timedelta


class AllocationDataUnavailable(ValueError):
    pass


def entity_rows(repository, account_ids, category, start, end, observations=None):
    for account_id in account_ids:
        records = {record.start_date: record for record in repository.list_range(account_id, start, end)}
        day = date.fromisoformat(start)
        while day <= date.fromisoformat(end):
            data = records.get(day.isoformat())
            if data is None or getattr(data, "costs_by_tag_service", None) is None:
                raise AllocationDataUnavailable("Daily tag/service data is unavailable; collect allocation tags for the selected period")
            if observations is not None:
                observations.append({'account_id': account_id, 'date': day.isoformat(), 'is_estimated': data.is_estimated})
            for service, cost in data.costs_by_tag_service.get(category, {}).items():
                yield account_id, day.isoformat(), service, cost
            day += timedelta(days=1)


def safe_writer(output):
    writer = csv.writer(output)
    class SafeWriter:
        def writerow(self, values):
            writer.writerow(["'" + value if isinstance(value, str) and (value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n"))) else value for value in values])
    return SafeWriter()
