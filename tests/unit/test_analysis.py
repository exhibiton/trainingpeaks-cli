from __future__ import annotations

from typing import Any, Dict, List

import pytest

from tp_cli.core.analysis import (
    analyze_patterns,
    analyze_zones,
    build_weekly_analysis,
    classify_week,
    classify_zone,
    get_week_key,
    get_week_start,
    parse_workout_zones,
)


def _workout(
    day: str,
    sport_id: int,
    distance: float,
    tss: float,
    workout_type: str,
    title: str = "Session",
) -> Dict[str, Any]:
    return {
        "workoutDay": f"{day}T00:00:00",
        "workoutTypeValueId": sport_id,
        "distance": distance,
        "tssPlanned": tss,
        "title": title,
        "classification": {"type": workout_type},
    }


def test_get_week_key_and_start() -> None:
    assert get_week_key("2026-02-14T00:00:00") == "2026-W07"
    assert get_week_start("2026-02-14T00:00:00").strftime("%Y-%m-%d") == "2026-02-09"


@pytest.mark.parametrize(
    ("total_distance", "total_sessions", "has_race", "delta_pct", "expected"),
    [
        (10000, 3, True, 10, "race"),
        (10000, 2, False, 0, "off"),
        (30000, 5, False, None, "start"),
        (30000, 5, False, -30, "recovery"),
        (30000, 5, False, 20, "build"),
        (30000, 5, False, 3, "maintenance"),
    ],
)
def test_classify_week_cases(
    total_distance: float,
    total_sessions: int,
    has_race: bool,
    delta_pct: float | None,
    expected: str,
) -> None:
    assert classify_week(total_distance, total_sessions, has_race, delta_pct) == expected


def test_build_weekly_analysis_aggregates_and_classifies() -> None:
    workouts = [
        _workout("2026-02-10", 3, 10000, 70, "lt2", "Run LT2"),
        _workout("2026-02-11", 2, 40000, 90, "easy", "Bike"),
        _workout("2026-02-12", 1, 2500, 35, "easy", "Swim"),
        _workout("2026-02-13", 9, 0, 0, "strength", "Strength"),
        _workout("2026-02-14", 7, 0, 0, "other", "Rest"),
    ]
    report = build_weekly_analysis(workouts)
    assert report["summary"]["total_weeks"] == 1
    week = report["weeks"][0]
    assert week["total_sessions"] == 3
    assert week["strength_sessions"] == 1
    assert week["rest_days"] == 1
    assert week["by_sport"]["run"]["sessions"] == 1
    assert week["by_sport"]["run"]["quality_workouts"][0]["type"] == "lt2"


def test_build_weekly_analysis_applies_sport_filter() -> None:
    workouts = [
        _workout("2026-02-10", 3, 10000, 70, "lt2"),
        _workout("2026-02-11", 2, 40000, 90, "easy"),
    ]
    report = build_weekly_analysis(workouts, sport_filter="run")
    week = report["weeks"][0]
    assert week["total_sessions"] == 1
    assert week["by_sport"]["run"]["sessions"] == 1
    assert week["by_sport"]["bike"]["sessions"] == 0


def test_classify_zone_threshold_boundaries() -> None:
    # Default thresholds: easy_max=75, lt1_max=93, lt2_max=100
    assert classify_zone(75, "step", "active") == "easy"
    assert classify_zone(76, "step", "active") == "lt1"
    assert classify_zone(93, "step", "active") == "lt1"
    assert classify_zone(94, "step", "active") == "lt2"
    assert classify_zone(100, "step", "active") == "lt2"
    assert classify_zone(101, "step", "active") == "vo2"


def test_classify_zone_custom_thresholds() -> None:
    custom = {"easy_max": 78, "lt1_max": 93, "lt2_max": 108}
    assert classify_zone(78, "step", "active", thresholds=custom) == "easy"
    assert classify_zone(79, "step", "active", thresholds=custom) == "lt1"
    assert classify_zone(108, "step", "active", thresholds=custom) == "lt2"
    assert classify_zone(109, "step", "active", thresholds=custom) == "vo2"


def test_classify_zone_rest_and_rampup_forces_easy() -> None:
    assert classify_zone(110, "rampUp", "active") == "easy"
    assert classify_zone(110, "step", "rest") == "easy"


def test_parse_workout_zones_without_structure_falls_back_to_easy() -> None:
    workout = {"distance": 12345}
    zones, total = parse_workout_zones(workout)
    assert total == 12345
    assert zones == {"easy": 12345, "lt1": 0.0, "lt2": 0.0, "vo2": 0.0}


def test_parse_workout_zones_with_structure_and_scaling() -> None:
    workout = {
        "distance": 2720,
        "structure": {
            "primaryIntensityMetric": "percentOfThresholdPace",
            "structure": [
                {
                    "type": "repetition",
                    "length": {"value": 2, "unit": "repetition"},
                    "steps": [
                        {
                            "length": {"value": 100, "unit": "second"},
                            "targets": [{"minValue": 100}],
                            "intensityClass": "active",
                        },
                        {
                            "length": {"value": 100, "unit": "second"},
                            "targets": [{"minValue": 70}],
                            "intensityClass": "rest",
                        },
                    ],
                }
            ],
        },
    }
    zones, total = parse_workout_zones(workout, threshold_speed=4.0)
    assert total == 2720
    assert round(zones["lt2"], 1) == 1600.0
    assert round(zones["easy"], 1) == 1120.0


def test_analyze_zones_weekly_distribution() -> None:
    workouts: List[Dict[str, Any]] = [
        {
            "workoutDay": "2026-02-10T00:00:00",
            "workoutTypeValueId": 3,
            "distance": 10000,
            "structure": None,
        },
        {
            "workoutDay": "2026-02-17T00:00:00",
            "workoutTypeValueId": 3,
            "distance": 5000,
            "structure": None,
        },
        {
            "workoutDay": "2026-02-11T00:00:00",
            "workoutTypeValueId": 2,
            "distance": 20000,
            "structure": None,
        },
    ]
    report = analyze_zones(workouts, sport="run", group_by="week")
    assert report["sport"] == "run"
    assert report["total_distance"] == 15000
    assert len(report["by_period"]) == 2
    assert report["zone_distribution"]["easy"]["pct"] == 100.0


def test_analyze_zones_month_grouping() -> None:
    workouts = [
        {
            "workoutDay": "2026-01-10T00:00:00",
            "workoutTypeValueId": 3,
            "distance": 10000,
            "structure": None,
        },
        {
            "workoutDay": "2026-02-10T00:00:00",
            "workoutTypeValueId": 3,
            "distance": 10000,
            "structure": None,
        },
    ]
    report = analyze_zones(workouts, sport="run", group_by="month")
    assert [row["period"] for row in report["by_period"]] == ["2026-01", "2026-02"]


def test_analyze_patterns_builds_correlation_and_risk() -> None:
    workouts = [
        _workout("2026-02-02", 3, 10000, 70, "lt2"),
        _workout("2026-02-03", 2, 20000, 80, "easy"),
        _workout("2026-02-10", 3, 10000, 70, "vo2"),
        _workout("2026-02-11", 2, 20000, 80, "lt2"),
        _workout("2026-02-12", 3, 10000, 70, "lt2"),
    ]
    report = analyze_patterns(workouts, multi_sport=True, injury_risk=True, coach_analysis=True)
    assert report["date_range"]["start"] == "2026-02-02"
    assert "hard_day_correlation" in report
    assert "weekly_load" in report
    assert "coach_analysis" in report
