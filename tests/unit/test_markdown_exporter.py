from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from tp_cli.exporters.markdown import generate_indexes, workout_to_markdown, write_workout_markdown


def _workout(title: str = 'Tempo "Run"') -> Dict[str, Any]:
    return {
        "workoutId": 101,
        "workoutDay": "2026-02-14T00:00:00",
        "workoutTypeValueId": 3,
        "title": title,
        "description": "Main set work",
        "distance": 10000,
        "totalTime": 1.0,
        "tssPlanned": 80,
        "workoutComments": [{"comment": "Nail pacing"}],
        "structure": {
            "primaryIntensityMetric": "percentOfThresholdPace",
            "structure": [
                {
                    "type": "step",
                    "length": {"value": 1, "unit": "repetition"},
                    "steps": [
                        {
                            "name": "Main",
                            "length": {"value": 1200, "unit": "second"},
                            "targets": [{"minValue": 90, "unit": "percentOfThresholdPace"}],
                            "intensityClass": "active",
                        }
                    ],
                }
            ],
        },
        "classification": {"type": "lt1"},
    }


def test_workout_to_markdown_contains_frontmatter_and_sections() -> None:
    output = workout_to_markdown(_workout(), "lt1")
    assert output.startswith("---\n")
    assert 'title: "Tempo \\"Run\\""' in output
    assert 'sport: "run"' in output
    assert "## Structured Workout" in output
    assert "Nail pacing" in output


def test_workout_to_markdown_falls_back_for_missing_fields() -> None:
    minimal = {"workoutDay": "2026-02-14", "workoutTypeValueId": 2, "title": "Bike", "classification": {}}
    output = workout_to_markdown(minimal, "other")
    assert "No description" in output
    assert "No notes" in output


def test_write_workout_markdown_creates_expected_file(tmp_path: Path) -> None:
    workout = _workout()
    path = write_workout_markdown(tmp_path, workout, "lt1", rewrite=False)
    assert path.exists()
    assert path.name.startswith("2026-02-14-tempo-run")
    assert "run/lt1" in str(path)


def test_write_workout_markdown_skips_overwrite_when_rewrite_false(tmp_path: Path) -> None:
    workout = _workout("Steady Run")
    path = write_workout_markdown(tmp_path, workout, "easy", rewrite=False)
    path.write_text("ORIGINAL")
    second = write_workout_markdown(tmp_path, workout, "easy", rewrite=False)
    assert second == path
    assert path.read_text() == "ORIGINAL"


def test_generate_indexes_writes_top_level_and_sport_indexes(tmp_path: Path) -> None:
    workouts: List[Dict[str, Any]] = [_workout("Run A"), _workout("Run B")]
    generate_indexes(tmp_path, workouts)
    top = tmp_path / "INDEX.md"
    run_index = tmp_path / "run" / "INDEX.md"
    assert top.exists()
    assert run_index.exists()
    assert "All Workouts" in top.read_text()
    assert "Run Workouts" in run_index.read_text()
