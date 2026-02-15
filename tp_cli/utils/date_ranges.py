"""Date range parsing and chunking helpers."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Generator, Optional, Tuple

import typer

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_date(value: Optional[str]) -> Optional[str]:
    """Typer callback that validates YYYY-MM-DD format for date options."""
    if value is None:
        return value
    if not _DATE_RE.match(value):
        raise typer.BadParameter(
            f"Invalid date '{value}'. Expected format: YYYY-MM-DD (e.g. 2026-01-15)"
        )
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise typer.BadParameter(
            f"Invalid date '{value}'. Expected format: YYYY-MM-DD (e.g. 2026-01-15)"
        )
    return value


def parse_date(value: str) -> date:
    """Parse YYYY-MM-DD date string."""
    return datetime.strptime(value, "%Y-%m-%d").date()


def resolve_date_range(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    last_days: Optional[int] = None,
    last_weeks: Optional[int] = None,
    last_months: Optional[int] = None,
    this_week: bool = False,
    last_week: bool = False,
    this_month: bool = False,
    this_year: bool = False,
    all_time: bool = False,
    today: Optional[date] = None,
) -> Tuple[date, date]:
    """Resolve CLI date flags into concrete start/end dates."""
    now = today or date.today()

    if start_date and end_date:
        return parse_date(start_date), parse_date(end_date)
    if start_date and not end_date:
        return parse_date(start_date), now
    if end_date and not start_date:
        return date(2000, 1, 1), parse_date(end_date)

    if last_days:
        return now - timedelta(days=max(last_days - 1, 0)), now
    if last_weeks:
        days = max(last_weeks * 7 - 1, 0)
        return now - timedelta(days=days), now
    if last_months:
        days = max(last_months * 30 - 1, 0)
        return now - timedelta(days=days), now

    if this_week:
        start = now - timedelta(days=now.weekday())
        return start, start + timedelta(days=6)

    if last_week:
        this_week_start = now - timedelta(days=now.weekday())
        start = this_week_start - timedelta(days=7)
        return start, start + timedelta(days=6)

    if this_month:
        start = date(now.year, now.month, 1)
        if now.month == 12:
            month_end = date(now.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(now.year, now.month + 1, 1) - timedelta(days=1)
        return start, month_end

    if this_year:
        return date(now.year, 1, 1), date(now.year, 12, 31)

    if all_time:
        return date(2000, 1, 1), now

    # Default: last 30 days.
    return now - timedelta(days=29), now


def chunk_date_range(
    start: date,
    end: date,
    chunk_days: int = 90,
) -> Generator[Tuple[date, date], None, None]:
    """Yield inclusive date chunks from start..end."""
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), end)
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(days=1)
