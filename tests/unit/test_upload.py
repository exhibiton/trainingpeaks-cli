from __future__ import annotations

import json
from typing import Any, Dict

from tp_cli.core.upload import (
    calc_time_and_distance,
    convert_workout,
    fetch_threshold_speed,
    get_existing_workouts,
    label_run_steps,
    speed_pct_to_pace,
    workout_exists,
)


class DummyAPI:
    def __init__(self, settings: Dict[str, Any] | None = None, workouts: Any = None) -> None:
        self._settings = settings or {}
        self._workouts = workouts

    def get_athlete_settings(self, user_id: str) -> Dict[str, Any]:
        return self._settings

    def get_workouts(self, user_id: str, start_date: str, end_date: str) -> Any:
        return self._workouts


def test_speed_pct_to_pace_basic() -> None:
    assert speed_pct_to_pace(100, 4.0) == "4:10"
    assert speed_pct_to_pace(80, 4.0) == "5:12"


def test_speed_pct_to_pace_non_positive_speed() -> None:
    assert speed_pct_to_pace(0, 4.0) == "?"
    assert speed_pct_to_pace(90, 0.0) == "?"


def test_label_run_steps_with_range_target() -> None:
    structure = {
        "structure": [
            {
                "steps": [
                    {"targets": [{"minValue": 94, "maxValue": 100}], "name": ""},
                    {"targets": [{"minValue": 72}], "name": ""},
                ]
            }
        ]
    }
    label_run_steps(structure, threshold_speed=4.0)
    assert structure["structure"][0]["steps"][0]["name"].startswith("Pace ")
    assert structure["structure"][0]["steps"][1]["name"].startswith("Pace ")


def test_calc_time_and_distance_with_steady_and_intervals() -> None:
    steps = [
        {"type": "warmup", "duration": "10:00", "target": "70% TP"},
        {"type": "steady", "duration": "5km", "target": "80% TP"},
        {
            "type": "interval",
            "reps": 2,
            "on": "1:00",
            "off": "30",
            "on_target": "100% TP",
            "off_target": "70% TP",
        },
    ]
    seconds, meters = calc_time_and_distance(steps, threshold_speed=4.0)
    assert seconds == 2343
    assert meters == 7328


def test_calc_time_and_distance_with_distance_recovery() -> None:
    steps = [
        {
            "type": "interval",
            "reps": 1,
            "on": "400m",
            "off": "200m",
            "on_target": "95% TP",
            "off_target": "70% TP",
        }
    ]
    seconds, meters = calc_time_and_distance(steps, threshold_speed=4.0)
    assert meters == 600
    assert seconds > 0


def test_convert_workout_from_steps_for_run_labels_paces() -> None:
    workout = {
        "date": "2026-02-14",
        "sport": "run",
        "title": "Intervals",
        "description": "Test workout",
        "steps": [
            {"type": "warmup", "duration": "10:00", "target": "72% TP"},
            {"type": "interval", "reps": 2, "on": "3:00", "on_target": "94-100% TP", "off": "2:00"},
            {"type": "cooldown", "duration": "10:00"},
        ],
    }
    payload = convert_workout(workout, user_id="42", threshold_speed=4.0)
    assert payload["athleteId"] == "42"
    assert payload["workoutTypeValueId"] == 3
    struct = json.loads(payload["structure"])
    assert struct["primaryIntensityMetric"] == "percentOfThresholdPace"
    names = [step["name"] for block in struct["structure"] for step in block["steps"]]
    assert any(name.startswith("Pace ") for name in names if name)


def test_convert_workout_from_dict_structure() -> None:
    structure = {"primaryIntensityMetric": "percentOfThresholdPace", "structure": []}
    workout = {
        "date": "2026-02-14",
        "sport": "run",
        "title": "Existing Structure",
        "structure": structure,
    }
    payload = convert_workout(workout, user_id="42")
    assert json.loads(payload["structure"]) == structure


def test_convert_workout_bike_uses_ftp_metric() -> None:
    workout = {
        "date": "2026-02-14",
        "sport": "bike",
        "title": "Bike Session",
        "steps": [{"type": "steady", "duration": "30:00", "target": "80% FTP"}],
    }
    payload = convert_workout(workout, user_id="42", threshold_speed=4.0)
    struct = json.loads(payload["structure"])
    assert struct["primaryIntensityMetric"] == "percentOfFtp"
    assert payload["workoutTypeValueId"] == 2


def test_fetch_threshold_speed_found() -> None:
    api = DummyAPI(
        settings={
            "speedZones": [
                {"workoutTypeId": 2, "threshold": 7},
                {"workoutTypeId": 3, "threshold": 4.2},
            ]
        }
    )
    assert fetch_threshold_speed(api, "42") == 4.2


def test_fetch_threshold_speed_default_when_missing() -> None:
    api = DummyAPI(settings={"speedZones": [{"workoutTypeId": 2, "threshold": 7}]})
    assert fetch_threshold_speed(api, "42") == 4.0


def test_get_existing_workouts_handles_non_list() -> None:
    api = DummyAPI(workouts={"not": "a list"})
    assert get_existing_workouts(api, "42", "2026-02-14") == []


def test_workout_exists_case_insensitive_title_match() -> None:
    api = DummyAPI(workouts=[{"title": " Tempo Run "}])
    assert workout_exists(api, "42", "2026-02-14", "tempo run")


def test_workout_exists_false_when_not_present() -> None:
    api = DummyAPI(workouts=[{"title": "Bike"}])
    assert not workout_exists(api, "42", "2026-02-14", "Run")
