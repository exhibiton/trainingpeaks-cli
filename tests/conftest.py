from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest
from typer.testing import CliRunner


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def sample_workout_run() -> Dict[str, Any]:
    return {
        "workoutId": "w-run-1",
        "workoutDay": "2026-02-10T00:00:00",
        "workoutTypeValueId": 3,
        "title": "Tempo Run",
        "description": "Steady quality run",
        "distance": 10000,
        "totalTime": 1.0,
        "tssPlanned": 70,
        "classification": {"type": "lt1"},
    }


@pytest.fixture()
def sample_workout_bike() -> Dict[str, Any]:
    return {
        "workoutId": "w-bike-1",
        "workoutDay": "2026-02-11T00:00:00",
        "workoutTypeValueId": 2,
        "title": "Bike Intervals",
        "description": "Threshold reps",
        "distance": 40000,
        "totalTime": 1.5,
        "tssPlanned": 95,
        "classification": {"type": "lt2"},
    }


@pytest.fixture()
def sample_workout_swim() -> Dict[str, Any]:
    return {
        "workoutId": "w-swim-1",
        "workoutDay": "2026-02-12T00:00:00",
        "workoutTypeValueId": 1,
        "title": "Easy Swim",
        "description": "Technique focused",
        "distance": 2500,
        "totalTime": 0.75,
        "tssPlanned": 35,
        "classification": {"type": "easy"},
    }


@pytest.fixture()
def sample_workouts(
    sample_workout_run: Dict[str, Any],
    sample_workout_bike: Dict[str, Any],
    sample_workout_swim: Dict[str, Any],
) -> List[Dict[str, Any]]:
    return [sample_workout_run, sample_workout_bike, sample_workout_swim]


@pytest.fixture()
def sample_tp_structure() -> Dict[str, Any]:
    return {
        "primaryIntensityMetric": "percentOfThresholdPace",
        "structure": [
            {
                "type": "rampUp",
                "length": {"value": 1, "unit": "repetition"},
                "steps": [
                    {
                        "name": "Warmup",
                        "length": {"value": 600, "unit": "second"},
                        "targets": [{"minValue": 70}],
                        "intensityClass": "warmUp",
                        "openDuration": False,
                    }
                ],
            },
            {
                "type": "repetition",
                "length": {"value": 4, "unit": "repetition"},
                "steps": [
                    {
                        "name": "On",
                        "length": {"value": 300, "unit": "second"},
                        "targets": [{"minValue": 94, "maxValue": 100}],
                        "intensityClass": "active",
                        "openDuration": False,
                    },
                    {
                        "name": "Off",
                        "length": {"value": 120, "unit": "second"},
                        "targets": [{"minValue": 70}],
                        "intensityClass": "rest",
                        "openDuration": False,
                    },
                ],
            },
        ],
    }


@pytest.fixture()
def mock_user_response() -> Dict[str, Any]:
    return {"user": {"userId": 1234, "username": "athlete", "email": "a@example.com"}}


@pytest.fixture()
def write_temp_json(tmp_path: Path):
    def _write(name: str, payload: Any) -> Path:
        path = tmp_path / name
        path.write_text(json.dumps(payload, indent=2) + "\n")
        return path

    return _write


@pytest.fixture()
def write_temp_toml(tmp_path: Path):
    def _write(name: str, content: str) -> Path:
        path = tmp_path / name
        path.write_text(content.strip() + "\n")
        return path

    return _write
