"""Workout upload conversion and idempotency logic."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from tp_cli.core.api import TrainingPeaksAPI
from tp_cli.core.constants import SPORT_ID_BY_NAME
from tp_cli.utils.parsing import parse_length, simple_to_tp_structure


def fetch_threshold_speed(api: TrainingPeaksAPI, user_id: str) -> float:
    """Fetch run threshold speed from athlete settings."""
    settings = api.get_athlete_settings(user_id)
    for zone in settings.get("speedZones", []):
        if zone.get("workoutTypeId") == 3 and zone.get("threshold"):
            return float(zone["threshold"])
    return 4.0


def speed_pct_to_pace(pct: float, threshold_speed: float) -> str:
    """Convert % threshold speed to min:sec/km string."""
    speed = threshold_speed * (pct / 100.0)
    if speed <= 0:
        return "?"
    seconds_per_km = 1000.0 / speed
    minutes = int(seconds_per_km // 60)
    seconds = int(round(seconds_per_km % 60))
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d}"


def label_run_steps(structure_dict: Dict[str, Any], threshold_speed: float) -> None:
    """Apply Garmin-friendly pace labels to run steps in-place."""
    for block in structure_dict.get("structure", []):
        for step in block.get("steps", []):
            targets = step.get("targets", [])
            if not targets:
                continue
            target = targets[0]
            min_value = target.get("minValue")
            max_value = target.get("maxValue")
            if min_value is not None and max_value is not None:
                fast = speed_pct_to_pace(float(max_value), threshold_speed)
                slow = speed_pct_to_pace(float(min_value), threshold_speed)
                step["name"] = f"Pace {fast}-{slow}"
            elif min_value is not None:
                step["name"] = f"Pace {speed_pct_to_pace(float(min_value), threshold_speed)}"


def _pct_to_speed(target_str: Optional[str], threshold_speed: float) -> float:
    if not target_str:
        return threshold_speed * 0.72
    range_match = re.match(r"(\d+)-(\d+)", target_str)
    if range_match:
        mid = (int(range_match.group(1)) + int(range_match.group(2))) / 2.0
        return threshold_speed * (mid / 100.0)
    single_match = re.match(r"(\d+)", target_str)
    if single_match:
        return threshold_speed * (int(single_match.group(1)) / 100.0)
    return threshold_speed * 0.72


def calc_time_and_distance(
    steps: Sequence[Dict[str, Any]],
    threshold_speed: float,
) -> Tuple[int, int]:
    """Estimate total seconds and meters from simple steps payload."""
    total_seconds = 0.0
    total_meters = 0.0

    for step in steps:
        step_type = step.get("type")

        if step_type in ("warmup", "steady", "cooldown"):
            dur_value, dur_unit = parse_length(str(step["duration"]))
            speed = _pct_to_speed(step.get("target"), threshold_speed)
            if dur_unit == "second":
                total_seconds += dur_value
                total_meters += dur_value * speed
            else:
                total_meters += dur_value
                total_seconds += dur_value / speed if speed > 0 else 0
            continue

        if step_type == "interval":
            reps = int(step.get("reps", 1))
            on_value, on_unit = parse_length(str(step["on"]))
            off_value, off_unit = parse_length(str(step["off"]))
            on_speed = _pct_to_speed(step.get("on_target"), threshold_speed)
            off_speed = _pct_to_speed(step.get("off_target"), threshold_speed)

            for _ in range(reps):
                if on_unit == "second":
                    total_seconds += on_value
                    total_meters += on_value * on_speed
                else:
                    total_meters += on_value
                    total_seconds += on_value / on_speed if on_speed > 0 else 0

                if off_unit == "second":
                    total_seconds += off_value
                    total_meters += off_value * off_speed
                else:
                    total_meters += off_value
                    total_seconds += off_value / off_speed if off_speed > 0 else 0

    # Use half-up rounding for predictable workout totals.
    return int(total_seconds + 0.5), int(total_meters + 0.5)


def convert_workout(
    workout: Dict[str, Any],
    user_id: str,
    threshold_speed: Optional[float] = None,
) -> Dict[str, Any]:
    """Convert workout file object to TrainingPeaks API payload."""
    sport = str(workout.get("sport", "run")).lower()
    sport_id = SPORT_ID_BY_NAME.get(sport, 3)
    date_text = f"{workout['date']}T00:00:00"

    calc_seconds: Optional[int] = None
    calc_meters: Optional[int] = None
    if "steps" in workout and threshold_speed:
        calc_seconds, calc_meters = calc_time_and_distance(workout["steps"], threshold_speed)

    payload: Dict[str, Any] = {
        "athleteId": user_id,
        "workoutDay": date_text,
        "workoutTypeValueId": sport_id,
        "title": workout["title"],
        "description": workout.get("description", ""),
        "totalTimePlanned": workout.get("totalTimePlanned")
        or (round(calc_seconds / 3600, 4) if calc_seconds else None),
        "distancePlanned": workout.get("distancePlanned") or calc_meters,
        "tssPlanned": workout.get("tssPlanned"),
    }

    struct: Optional[Dict[str, Any]]
    if "structure" in workout:
        if isinstance(workout["structure"], dict):
            struct = workout["structure"]
        else:
            struct = json.loads(str(workout["structure"]))
    elif "steps" in workout:
        metric = "percentOfFtp" if sport == "bike" else "percentOfThresholdPace"
        struct = simple_to_tp_structure(workout["steps"], intensity_metric=metric)
    else:
        struct = None

    if struct and sport == "run" and threshold_speed:
        label_run_steps(struct, threshold_speed)

    payload["structure"] = json.dumps(struct) if struct else None
    return payload


def get_existing_workouts(api: TrainingPeaksAPI, user_id: str, date_str: str) -> List[Dict[str, Any]]:
    """Fetch workouts on a given date."""
    data = api.get_workouts(user_id, start_date=date_str, end_date=date_str)
    return data if isinstance(data, list) else []


def workout_exists(api: TrainingPeaksAPI, user_id: str, date_str: str, title: str) -> bool:
    """Check if workout with identical title exists on date."""
    existing = get_existing_workouts(api, user_id, date_str)
    normalized = title.strip().lower()
    return any(str(item.get("title", "")).strip().lower() == normalized for item in existing)
