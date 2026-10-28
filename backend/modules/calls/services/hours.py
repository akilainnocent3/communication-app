"""Office hours: whether a moment is after hours for an office, in that office's own time zone.

`OfficeHours.week` maps ISO weekday ("1" = Monday … "7" = Sunday) to a list of ["HH:MM", "HH:MM"] opening ranges;
a missing or empty day is closed. `holidays` lists closed dates (YYYY-MM-DD, local to the office). An office without
hours configured falls back to DEFAULT_WEEK (Monday–Friday 08:00–17:00, Saturday 08:00–13:00, Africa/Dar_es_Salaam).
"""

from __future__ import annotations

import re
import zoneinfo
from datetime import datetime, time

from ..models import OfficeHours

DEFAULT_TZ = "Africa/Dar_es_Salaam"
DEFAULT_WEEK = {"1": [["08:00", "17:00"]], "2": [["08:00", "17:00"]], "3": [["08:00", "17:00"]], "4": [["08:00", "17:00"]],
                "5": [["08:00", "17:00"]], "6": [["08:00", "13:00"]], "7": []}
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$|^24:00$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class HoursError(ValueError):
    pass


def _parse(value: str) -> time:
    if value == "24:00":
        return time.max
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def zone(name: str) -> zoneinfo.ZoneInfo:
    try:
        return zoneinfo.ZoneInfo(name or DEFAULT_TZ)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return zoneinfo.ZoneInfo(DEFAULT_TZ)


def clean_week(week: dict) -> dict:
    """Validate and normalise an admin-supplied week. Raises HoursError with a friendly message."""
    result = {}
    for day in map(str, range(1, 8)):
        ranges = (week or {}).get(day) or (week or {}).get(int(day)) or []
        clean = []
        for item in ranges[:4]:
            if not isinstance(item, (list, tuple)) or len(item) != 2 or not all(isinstance(v, str) and _HHMM.match(v) for v in item):
                raise HoursError("Use opening hours like 08:00–17:00.")
            if _parse(item[0]) >= _parse(item[1]):
                raise HoursError("An opening range must end after it starts.")
            clean.append([item[0], item[1]])
        result[day] = sorted(clean)
    return result


def clean_holidays(holidays: list) -> list[str]:
    days = sorted({str(d) for d in holidays or [] if _DATE.match(str(d))})
    if len(days) > 200:
        raise HoursError("At most 200 holidays.")
    return days


def hours_for(office_id) -> tuple[dict, list, str]:
    row = OfficeHours.objects.filter(office_id=office_id).first() if office_id else None
    if row is None:
        return DEFAULT_WEEK, [], DEFAULT_TZ
    return row.week or {}, row.holidays or [], row.timezone or DEFAULT_TZ


def is_open(at: datetime, week: dict, holidays: list, tz_name: str) -> bool:
    local = at.astimezone(zone(tz_name))
    if local.date().isoformat() in set(holidays):
        return False
    now = local.time()
    for start, end in week.get(str(local.isoweekday()), []):
        if _parse(start) <= now < _parse(end) or (end == "24:00" and now >= _parse(start)):
            return True
    return False


def is_after_hours(at: datetime, office_id) -> bool:
    week, holidays, tz_name = hours_for(office_id)
    return not is_open(at, week, holidays, tz_name)
