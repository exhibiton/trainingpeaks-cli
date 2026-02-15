from datetime import date

import pytest
import typer

from tp_cli.utils.date_ranges import chunk_date_range, resolve_date_range, validate_date


def test_resolve_last_days() -> None:
    start, end = resolve_date_range(last_days=7, today=date(2026, 2, 14))
    assert start.isoformat() == "2026-02-08"
    assert end.isoformat() == "2026-02-14"


def test_resolve_this_week() -> None:
    start, end = resolve_date_range(this_week=True, today=date(2026, 2, 14))
    assert start.isoformat() == "2026-02-09"
    assert end.isoformat() == "2026-02-15"


def test_chunk_date_range() -> None:
    chunks = list(chunk_date_range(date(2026, 1, 1), date(2026, 4, 15), chunk_days=90))
    assert chunks[0][0].isoformat() == "2026-01-01"
    assert chunks[0][1].isoformat() == "2026-03-31"
    assert chunks[1][0].isoformat() == "2026-04-01"
    assert chunks[1][1].isoformat() == "2026-04-15"


def test_resolve_with_explicit_start_end() -> None:
    start, end = resolve_date_range(start_date="2026-01-02", end_date="2026-01-03")
    assert start.isoformat() == "2026-01-02"
    assert end.isoformat() == "2026-01-03"


def test_resolve_with_start_only() -> None:
    start, end = resolve_date_range(start_date="2026-02-01", today=date(2026, 2, 14))
    assert start.isoformat() == "2026-02-01"
    assert end.isoformat() == "2026-02-14"


def test_resolve_with_end_only() -> None:
    start, end = resolve_date_range(end_date="2026-02-14")
    assert start.isoformat() == "2000-01-01"
    assert end.isoformat() == "2026-02-14"


def test_resolve_last_weeks() -> None:
    start, end = resolve_date_range(last_weeks=2, today=date(2026, 2, 14))
    assert start.isoformat() == "2026-02-01"
    assert end.isoformat() == "2026-02-14"


def test_resolve_last_months() -> None:
    start, end = resolve_date_range(last_months=2, today=date(2026, 2, 14))
    assert start.isoformat() == "2025-12-17"
    assert end.isoformat() == "2026-02-14"


def test_resolve_last_week() -> None:
    start, end = resolve_date_range(last_week=True, today=date(2026, 2, 14))
    assert start.isoformat() == "2026-02-02"
    assert end.isoformat() == "2026-02-08"


def test_resolve_this_month() -> None:
    start, end = resolve_date_range(this_month=True, today=date(2026, 2, 14))
    assert start.isoformat() == "2026-02-01"
    assert end.isoformat() == "2026-02-28"


def test_resolve_this_month_december_rollover() -> None:
    start, end = resolve_date_range(this_month=True, today=date(2026, 12, 12))
    assert start.isoformat() == "2026-12-01"
    assert end.isoformat() == "2026-12-31"


def test_resolve_this_year_and_all_time() -> None:
    start, end = resolve_date_range(this_year=True, today=date(2026, 2, 14))
    assert start.isoformat() == "2026-01-01"
    assert end.isoformat() == "2026-12-31"

    start2, end2 = resolve_date_range(all_time=True, today=date(2026, 2, 14))
    assert start2.isoformat() == "2000-01-01"
    assert end2.isoformat() == "2026-02-14"


def test_resolve_default_last_30_days() -> None:
    start, end = resolve_date_range(today=date(2026, 2, 14))
    assert start.isoformat() == "2026-01-16"
    assert end.isoformat() == "2026-02-14"


def test_validate_date_valid() -> None:
    assert validate_date("2026-01-15") == "2026-01-15"
    assert validate_date(None) is None


def test_validate_date_bad_format() -> None:
    with pytest.raises(typer.BadParameter, match="Invalid date"):
        validate_date("01-15-2026")


def test_validate_date_bad_day() -> None:
    with pytest.raises(typer.BadParameter, match="Invalid date"):
        validate_date("2026-02-30")


def test_validate_date_not_a_date() -> None:
    with pytest.raises(typer.BadParameter, match="Invalid date"):
        validate_date("not-a-date")
