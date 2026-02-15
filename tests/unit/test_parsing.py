import json
from pathlib import Path

import pytest

from tp_cli.utils.parsing import (
    build_basic_workout,
    load_workout_input,
    parse_length,
    parse_target,
    simple_to_tp_structure,
)


def test_parse_length_duration() -> None:
    assert parse_length("15:00") == (900, "second")
    assert parse_length("1:05:00") == (3900, "second")


def test_parse_length_distance() -> None:
    assert parse_length("5km") == (5000, "meter")
    assert parse_length("400m") == (400, "meter")
    assert parse_length("1.5km") == (1500, "meter")
    assert parse_length("250.9m") == (250, "meter")


def test_parse_length_hh_mm_ss_and_mm_ss() -> None:
    assert parse_length("00:45") == (45, "second")
    assert parse_length("2:03:04") == (7384, "second")


def test_parse_length_plain_seconds() -> None:
    assert parse_length("90") == (90, "second")


def test_parse_target() -> None:
    assert parse_target("72% TP") == 72
    assert parse_target("94-104% TP") == 94
    assert parse_target(None) is None
    assert parse_target("no target") is None


def test_simple_interval_conversion() -> None:
    steps = [
        {
            "type": "interval",
            "reps": 4,
            "on": "8:00",
            "on_target": "94-104% TP",
            "off": "2:00",
            "off_target": "72% TP",
        }
    ]
    structure = simple_to_tp_structure(steps)
    assert structure["primaryIntensityMetric"] == "percentOfThresholdPace"
    assert len(structure["structure"]) == 1
    block = structure["structure"][0]
    assert block["type"] == "repetition"
    assert block["length"]["value"] == 4


def test_simple_to_tp_structure_warmup_intervals_cooldown() -> None:
    steps = [
        {"type": "warmup", "duration": "10:00", "target": "70% TP"},
        {
            "type": "interval",
            "reps": 3,
            "on": "3:00",
            "on_target": "94-100% TP",
            "off": "2:00",
            "off_target": "70% TP",
        },
        {"type": "cooldown", "duration": "8:00"},
    ]
    structure = simple_to_tp_structure(steps)
    blocks = structure["structure"]
    assert len(blocks) == 3
    assert blocks[0]["type"] == "rampUp"
    assert blocks[1]["type"] == "repetition"
    assert blocks[1]["length"]["value"] == 3
    assert blocks[2]["type"] == "step"
    assert blocks[2]["steps"][0]["intensityClass"] == "coolDown"


def test_simple_to_tp_structure_steady_step() -> None:
    steps = [{"type": "steady", "duration": "30:00", "target": "80% TP", "name": "Steady"}]
    structure = simple_to_tp_structure(steps)
    block = structure["structure"][0]
    assert block["type"] == "step"
    assert block["steps"][0]["name"] == "Steady"
    assert block["steps"][0]["length"]["unit"] == "second"


def test_load_workout_input_from_yaml_file(tmp_path) -> None:
    yaml_path = tmp_path / "workout.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                "date: 2026-02-14",
                "sport: run",
                "title: Easy Run",
            ]
        )
    )
    workouts = load_workout_input(file_path=yaml_path, read_stdin=False)
    assert len(workouts) == 1
    assert workouts[0]["sport"] == "run"


def test_load_workout_input_from_json_file(tmp_path: Path) -> None:
    json_path = tmp_path / "workout.json"
    json_path.write_text(
        json.dumps({"date": "2026-02-14", "sport": "bike", "title": "Ride"}) + "\n"
    )
    workouts = load_workout_input(file_path=json_path, read_stdin=False)
    assert workouts[0]["sport"] == "bike"


def test_load_workout_input_from_stdin_json() -> None:
    payload = '{"date":"2026-02-14","sport":"run","title":"Run"}'
    workouts = load_workout_input(file_path=None, read_stdin=True, stdin_text=payload)
    assert len(workouts) == 1
    assert workouts[0]["title"] == "Run"


def test_load_workout_input_from_stdin_yaml() -> None:
    payload = "date: 2026-02-14\nsport: swim\ntitle: Swim Session\n"
    workouts = load_workout_input(file_path=None, read_stdin=True, stdin_text=payload)
    assert len(workouts) == 1
    assert workouts[0]["sport"] == "swim"


def test_load_workout_input_empty_stdin_returns_empty() -> None:
    assert load_workout_input(file_path=None, read_stdin=True, stdin_text="   ") == []


def test_load_workout_input_filters_non_dict_items(tmp_path: Path) -> None:
    json_path = tmp_path / "workouts.json"
    json_path.write_text(json.dumps([{"title": "A"}, "not-a-dict", 42]))
    workouts = load_workout_input(file_path=json_path, read_stdin=False)
    assert workouts == [{"title": "A"}]


def test_build_basic_workout_success() -> None:
    workout = build_basic_workout("2026-02-14", "run", "Easy Run", "desc")
    assert workout["sport"] == "run"
    assert workout["title"] == "Easy Run"


def test_build_basic_workout_invalid_sport_raises() -> None:
    with pytest.raises(ValueError):
        build_basic_workout("2026-02-14", "ski", "Session")
