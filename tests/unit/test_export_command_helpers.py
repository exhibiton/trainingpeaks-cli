from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from tp_cli.commands.export import _ics_escape, _write_csv, _write_ical, _write_tcx


def _sample_rows() -> List[Dict[str, object]]:
    return [
        {
            "workoutId": "123",
            "workoutDay": "2026-02-14T00:00:00",
            "workoutTypeValueId": 3,
            "title": "Run, Tempo",
            "description": "Line1\nLine2",
            "distance": 10000,
            "totalTime": 1.0,
            "tssPlanned": 70,
            "classification": {"type": "lt1"},
        }
    ]


def test_ics_escape_special_characters() -> None:
    escaped = _ics_escape("a\\b;c,d\ne")
    assert escaped == "a\\\\b\\;c\\,d\\ne"


def test_write_csv_creates_file_with_header(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    _write_csv(path, _sample_rows())
    text = path.read_text()
    assert "workoutId,workoutDay,sport,title,description,distance,totalTime,tssPlanned,classification" in text
    assert "123,2026-02-14,run" in text


def test_write_ical_creates_valid_calendar(tmp_path: Path) -> None:
    path = tmp_path / "training.ics"
    _write_ical(path, _sample_rows())
    text = path.read_text()
    assert "BEGIN:VCALENDAR" in text
    assert "BEGIN:VEVENT" in text
    assert "SUMMARY:Run\\, Tempo" in text
    assert "END:VCALENDAR" in text


def test_write_tcx_writes_one_file_per_workout(tmp_path: Path) -> None:
    output_dir = tmp_path / "tcx"
    count = _write_tcx(output_dir, _sample_rows())
    assert count == 1
    files = list(output_dir.glob("*.tcx"))
    assert len(files) == 1
    assert "<TrainingCenterDatabase>" in files[0].read_text()


def test_write_tcx_skips_rows_without_workout_id(tmp_path: Path) -> None:
    output_dir = tmp_path / "tcx"
    count = _write_tcx(
        output_dir,
        [
            {
                "workoutDay": "2026-02-14T00:00:00",
                "workoutTypeValueId": 3,
                "title": "Run",
            }
        ],
    )
    assert count == 0
