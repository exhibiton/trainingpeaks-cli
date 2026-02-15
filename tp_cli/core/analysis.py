"""Analysis logic for weekly, zone, and pattern reports."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from tp_cli.core.classify import classify_zone
from tp_cli.core.constants import DEFAULT_ZONE_THRESHOLDS, SPORT_MAP, SPORT_NAME_BY_ID


def _workout_date(value: str) -> datetime:
    return datetime.strptime(value[:10], "%Y-%m-%d")


def get_week_key(date_str: str) -> str:
    dt = _workout_date(date_str)
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def get_week_start(date_str: str) -> datetime:
    dt = _workout_date(date_str)
    return dt - timedelta(days=dt.weekday())


def _classification_type(workout: Dict[str, Any]) -> str:
    return str(workout.get("classification", {}).get("type") or "other")


def classify_week(total_distance: float, total_sessions: int, has_race: bool, delta_pct: Optional[float]) -> str:
    """Classify weekly pattern label."""
    if has_race:
        return "race"
    if total_sessions <= 2 and total_distance < 20000:
        return "off"
    if delta_pct is None:
        return "start"
    if delta_pct < -25:
        return "recovery"
    if delta_pct > 15:
        return "build"
    return "maintenance"


def build_weekly_analysis(
    workouts: Iterable[Dict[str, Any]],
    sport_filter: str = "all",
) -> Dict[str, Any]:
    """Aggregate workouts into weekly report JSON payload."""
    weeks: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "week": "",
            "start_date": "",
            "end_date": "",
            "by_sport": {
                "swim": {
                    "distance": 0.0,
                    "sessions": 0,
                    "tss": 0.0,
                    "by_type": defaultdict(float),
                    "quality_workouts": [],
                },
                "bike": {
                    "distance": 0.0,
                    "sessions": 0,
                    "tss": 0.0,
                    "by_type": defaultdict(float),
                    "quality_workouts": [],
                },
                "run": {
                    "distance": 0.0,
                    "sessions": 0,
                    "tss": 0.0,
                    "by_type": defaultdict(float),
                    "quality_workouts": [],
                },
            },
            "strength_sessions": 0,
            "rest_days": 0,
            "total_distance": 0.0,
            "total_tss": 0.0,
            "total_sessions": 0,
            "pattern": "",
        }
    )

    for workout in workouts:
        day = workout.get("workoutDay")
        if not day:
            continue

        sport_id = workout.get("workoutTypeValueId")
        sport = SPORT_MAP.get(sport_id)
        if sport_filter != "all" and sport != sport_filter:
            continue

        week_key = get_week_key(day)
        week_start = get_week_start(day)
        week_end = week_start + timedelta(days=6)
        week_bucket = weeks[week_key]
        week_bucket["week"] = week_key
        week_bucket["start_date"] = week_start.strftime("%Y-%m-%d")
        week_bucket["end_date"] = week_end.strftime("%Y-%m-%d")

        if sport_id == 9:
            week_bucket["strength_sessions"] += 1
            continue
        if sport_id == 7:
            week_bucket["rest_days"] += 1
            continue
        if sport not in {"swim", "bike", "run"}:
            continue

        workout_type = _classification_type(workout)
        distance = float(workout.get("distance") or workout.get("distancePlanned") or 0.0)
        tss = float(workout.get("tssActual") or workout.get("tssPlanned") or 0.0)

        sport_data = week_bucket["by_sport"][sport]
        sport_data["distance"] += distance
        sport_data["sessions"] += 1
        sport_data["tss"] += tss
        sport_data["by_type"][workout_type] += distance

        week_bucket["total_distance"] += distance
        week_bucket["total_tss"] += tss
        week_bucket["total_sessions"] += 1

        if workout_type in {"lt1", "lt2", "vo2", "race", "test", "sprint"}:
            sport_data["quality_workouts"].append(
                {
                    "date": str(day)[:10],
                    "type": workout_type,
                    "title": workout.get("title", "Untitled"),
                    "distance": distance,
                    "tss": tss,
                }
            )

    ordered = [weeks[key] for key in sorted(weeks.keys())]
    previous_total: Optional[float] = None
    for row in ordered:
        total = float(row["total_distance"])
        delta = None
        if previous_total and previous_total > 0:
            delta = (total - previous_total) / previous_total * 100

        has_race = any(
            quality["type"] == "race"
            for sport in ("swim", "bike", "run")
            for quality in row["by_sport"][sport]["quality_workouts"]
        )
        row["pattern"] = classify_week(
            total_distance=total,
            total_sessions=int(row["total_sessions"]),
            has_race=has_race,
            delta_pct=delta,
        )
        previous_total = total

        # Convert by_type defaultdicts to summary objects.
        for sport in ("swim", "bike", "run"):
            sport_data = row["by_sport"][sport]
            distance_total = float(sport_data["distance"]) or 0.0
            converted = {}
            for workout_type, dist in sorted(
                sport_data["by_type"].items(), key=lambda item: item[1], reverse=True
            ):
                converted[workout_type] = {
                    "distance": dist,
                    "pct": (dist / distance_total * 100) if distance_total else 0,
                }
            sport_data["by_type"] = converted

    summary = {
        "total_weeks": len(ordered),
        "avg_weekly_distance": (
            sum(float(item["total_distance"]) for item in ordered) / len(ordered)
            if ordered
            else 0
        ),
        "avg_weekly_tss": (
            sum(float(item["total_tss"]) for item in ordered) / len(ordered)
            if ordered
            else 0
        ),
    }

    return {"weeks": ordered, "summary": summary}


def weekly_to_markdown(report: Dict[str, Any]) -> str:
    """Render weekly analysis payload to markdown."""
    lines: List[str] = ["# Weekly Training Analysis", ""]
    weeks = report.get("weeks", [])
    summary = report.get("summary", {})

    lines.append(f"**Total weeks:** {summary.get('total_weeks', 0)}")
    lines.append(
        f"**Average weekly distance:** {summary.get('avg_weekly_distance', 0) / 1000:.1f} km"
    )
    lines.append(f"**Average weekly TSS:** {summary.get('avg_weekly_tss', 0):.1f}")
    lines.append("")

    for week in weeks:
        lines.append(
            f"## {week['week']} ({week['start_date']} to {week['end_date']})"
        )
        lines.append(f"**Pattern:** {week['pattern']}")
        lines.append(
            f"**Total:** {week['total_distance'] / 1000:.1f} km | {week['total_tss']:.0f} TSS | {week['total_sessions']} sessions"
        )
        lines.append("")

        for sport in ("swim", "bike", "run"):
            sport_data = week["by_sport"][sport]
            if sport_data["sessions"] == 0:
                continue
            lines.append(
                f"### {SPORT_NAME_BY_ID[{'swim': 1, 'bike': 2, 'run': 3}[sport]]}: "
                f"{sport_data['distance'] / 1000:.1f} km | {sport_data['sessions']} sessions | {sport_data['tss']:.0f} TSS"
            )
            if sport_data["by_type"]:
                parts = []
                for t, metrics in sport_data["by_type"].items():
                    parts.append(f"{t}: {metrics['distance'] / 1000:.1f}km ({metrics['pct']:.0f}%)")
                lines.append(f"- Distribution: {' | '.join(parts)}")
            for quality in sport_data["quality_workouts"]:
                lines.append(
                    f"- **{quality['type'].upper()}** {quality['date']}: {quality['title']} "
                    f"({quality['distance'] / 1000:.1f}km, {quality['tss']:.0f} TSS)"
                )
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def _step_distance_raw(step: Dict[str, Any], threshold_speed: float) -> Tuple[float, float]:
    length = step.get("length", {})
    unit = length.get("unit")
    value = float(length.get("value") or 0)

    targets = step.get("targets", [{}])
    target = targets[0] if targets else {}
    min_value = float(target.get("minValue") or 0)
    max_value = float(target.get("maxValue") or min_value)
    pct = (min_value + max_value) / 2 if max_value > min_value else min_value

    if unit == "meter":
        return value, pct
    if unit == "second":
        speed = threshold_speed * (pct / 100.0) if pct > 0 else threshold_speed * 0.7
        return value * speed, pct
    return 0.0, pct


def parse_workout_zones(
    workout: Dict[str, Any],
    threshold_speed: float = 4.0,
    thresholds: Dict[str, float] = DEFAULT_ZONE_THRESHOLDS,
) -> Tuple[Dict[str, float], float]:
    """Parse workout structure and return zone-distance map and total distance."""
    structure = workout.get("structure")
    if not structure:
        distance = float(workout.get("distance") or 0)
        return {"easy": distance, "lt1": 0.0, "lt2": 0.0, "vo2": 0.0}, distance

    if isinstance(structure, str):
        try:
            structure = json.loads(structure)
        except Exception:
            distance = float(workout.get("distance") or 0)
            return {"easy": distance, "lt1": 0.0, "lt2": 0.0, "vo2": 0.0}, distance

    metric = structure.get("primaryIntensityMetric", "")
    if metric not in {"percentOfThresholdPace", "percentOfFtp", "percentOfThresholdHr"}:
        distance = float(workout.get("distance") or 0)
        return {"easy": distance, "lt1": 0.0, "lt2": 0.0, "vo2": 0.0}, distance

    zones = {"easy": 0.0, "lt1": 0.0, "lt2": 0.0, "vo2": 0.0}
    for block in structure.get("structure", []):
        block_type = block.get("type", "step")
        rep_count = int(block.get("length", {}).get("value", 1) if block_type == "repetition" else 1)

        for step in block.get("steps", []):
            raw_distance, pct = _step_distance_raw(step, threshold_speed)
            zone = classify_zone(
                pct=pct,
                block_type=block_type,
                intensity_class=str(step.get("intensityClass", "active")),
                thresholds=thresholds,
            )
            zones[zone] += raw_distance * rep_count

    raw_total = sum(zones.values())
    actual_distance = float(workout.get("distance") or 0)

    if raw_total > 0 and actual_distance > 0:
        scale = actual_distance / raw_total
        zones = {k: v * scale for k, v in zones.items()}
        return zones, actual_distance

    if actual_distance > 0 and raw_total == 0:
        return {"easy": actual_distance, "lt1": 0.0, "lt2": 0.0, "vo2": 0.0}, actual_distance

    return zones, raw_total


def analyze_zones(
    workouts: Iterable[Dict[str, Any]],
    sport: str,
    group_by: str = "week",
    thresholds: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Generate zone distribution summary."""
    effective_thresholds = thresholds or DEFAULT_ZONE_THRESHOLDS
    filtered = [
        workout
        for workout in workouts
        if SPORT_MAP.get(workout.get("workoutTypeValueId")) == sport
    ]
    filtered.sort(key=lambda item: str(item.get("workoutDay", "")))

    total = 0.0
    zone_totals = {"easy": 0.0, "lt1": 0.0, "lt2": 0.0, "vo2": 0.0}
    sessions = {"easy": 0, "lt1": 0, "lt2": 0, "vo2": 0}
    by_period: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"easy": 0.0, "lt1": 0.0, "lt2": 0.0, "vo2": 0.0, "total": 0.0}
    )

    for workout in filtered:
        day = str(workout.get("workoutDay") or "")[:10]
        if not day:
            continue

        zones, dist = parse_workout_zones(workout, thresholds=effective_thresholds)
        total += dist
        for key, value in zones.items():
            zone_totals[key] += value
            if value > 0:
                sessions[key] += 1

        dt = datetime.strptime(day, "%Y-%m-%d")
        period = dt.strftime("%Y-%m") if group_by == "month" else get_week_key(day)
        for key, value in zones.items():
            by_period[period][key] += value
        by_period[period]["total"] += dist

    distribution = {}
    for key in ("easy", "lt1", "lt2", "vo2"):
        pct = (zone_totals[key] / total * 100) if total else 0
        distribution[key] = {
            "distance": zone_totals[key],
            "pct": pct,
            "sessions": sessions[key],
        }

    period_list = []
    for period in sorted(by_period.keys()):
        row = {"period": period, "total_distance": by_period[period]["total"]}
        for key in ("easy", "lt1", "lt2", "vo2"):
            value = by_period[period][key]
            row[key] = {
                "distance": value,
                "pct": (value / by_period[period]["total"] * 100)
                if by_period[period]["total"]
                else 0,
            }
        period_list.append(row)

    start = str(filtered[0].get("workoutDay", ""))[:10] if filtered else None
    end = str(filtered[-1].get("workoutDay", ""))[:10] if filtered else None

    return {
        "period": {"start": start, "end": end},
        "sport": sport,
        "total_distance": total,
        "zone_distribution": distribution,
        "by_period": period_list,
    }


def _day_intensity(types: Iterable[str]) -> str:
    order = {"vo2": 4, "lt2": 3, "lt1": 2, "easy": 1, "other": 0}
    values = list(types)
    if not values:
        return "rest"
    return max(values, key=lambda item: order.get(item, 0))


def analyze_patterns(
    workouts: Iterable[Dict[str, Any]],
    multi_sport: bool = False,
    injury_risk: bool = False,
    coach_analysis: bool = False,
) -> Dict[str, Any]:
    """Detect same-day, day-after, and weekly hard-load patterns."""
    rows = [w for w in workouts if SPORT_MAP.get(w.get("workoutTypeValueId")) in {"run", "bike"}]
    rows.sort(key=lambda item: str(item.get("workoutDay", "")))

    run_by_date: Dict[str, List[str]] = defaultdict(list)
    bike_by_date: Dict[str, List[str]] = defaultdict(list)
    all_dates: set[str] = set()

    for workout in rows:
        day = str(workout.get("workoutDay", ""))[:10]
        if not day:
            continue
        all_dates.add(day)
        workout_type = _classification_type(workout)
        sport = SPORT_MAP.get(workout.get("workoutTypeValueId"))
        if sport == "run":
            run_by_date[day].append(workout_type)
        elif sport == "bike":
            bike_by_date[day].append(workout_type)

    ordered_dates = sorted(all_dates)
    combinations: Counter[Tuple[str, str]] = Counter()
    day_after: Dict[str, Counter[str]] = defaultdict(Counter)

    for day in ordered_dates:
        run_intensity = _day_intensity(run_by_date.get(day, []))
        bike_intensity = _day_intensity(bike_by_date.get(day, []))
        combinations[(run_intensity, bike_intensity)] += 1

        if run_intensity in {"lt2", "vo2"} or bike_intensity in {"lt2", "vo2"}:
            next_day = (
                datetime.strptime(day, "%Y-%m-%d") + timedelta(days=1)
            ).strftime("%Y-%m-%d")
            next_combo = (
                _day_intensity(run_by_date.get(next_day, [])),
                _day_intensity(bike_by_date.get(next_day, [])),
            )
            key = f"run={run_intensity},bike={bike_intensity}"
            day_after[key][f"run={next_combo[0]},bike={next_combo[1]}"] += 1

    weekly: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"run_lt2": 0, "bike_lt2": 0, "run_vo2": 0, "total_hard": 0}
    )
    for day in ordered_dates:
        dt = datetime.strptime(day, "%Y-%m-%d")
        week_key = f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
        run_intensity = _day_intensity(run_by_date.get(day, []))
        bike_intensity = _day_intensity(bike_by_date.get(day, []))

        if run_intensity == "lt2":
            weekly[week_key]["run_lt2"] += 1
        if run_intensity == "vo2":
            weekly[week_key]["run_vo2"] += 1
        if bike_intensity == "lt2":
            weekly[week_key]["bike_lt2"] += 1
        if run_intensity in {"lt2", "vo2"}:
            weekly[week_key]["total_hard"] += 1
        if bike_intensity in {"lt2", "vo2"}:
            weekly[week_key]["total_hard"] += 1

    risk_factors: List[Dict[str, Any]] = []
    if injury_risk:
        week_keys = sorted(weekly.keys())
        for idx in range(1, len(week_keys)):
            prev_key = week_keys[idx - 1]
            curr_key = week_keys[idx]
            prev_val = weekly[prev_key]["total_hard"]
            curr_val = weekly[curr_key]["total_hard"]
            if prev_val > 0:
                increase = (curr_val - prev_val) / prev_val * 100
                if increase >= 40:
                    risk_factors.append(
                        {
                            "type": "hard_session_spike",
                            "week": curr_key,
                            "increase_pct": round(increase, 1),
                            "severity": "high" if increase >= 60 else "medium",
                            "recommendation": "Consider a recovery week or reducing intensity density",
                        }
                    )

    payload: Dict[str, Any] = {
        "date_range": {
            "start": ordered_dates[0] if ordered_dates else None,
            "end": ordered_dates[-1] if ordered_dates else None,
        },
        "same_day_combinations": [
            {"run": run, "bike": bike, "count": count}
            for (run, bike), count in combinations.most_common()
        ],
        "day_after_patterns": {
            key: [{"next_day": next_day, "count": count} for next_day, count in counter.items()]
            for key, counter in sorted(day_after.items())
        },
        "weekly_load": [{"week": week, **weekly[week]} for week in sorted(weekly.keys())],
    }

    if multi_sport:
        payload["hard_day_correlation"] = {
            "same_day_both_hard": sum(
                count
                for (run, bike), count in combinations.items()
                if run in {"lt2", "vo2"} and bike in {"lt2", "vo2"}
            ),
            "hard_run_easy_bike": sum(
                count
                for (run, bike), count in combinations.items()
                if run in {"lt2", "vo2"} and bike in {"easy", "rest", "other"}
            ),
            "hard_bike_easy_run": sum(
                count
                for (run, bike), count in combinations.items()
                if bike in {"lt2", "vo2"} and run in {"easy", "rest", "other"}
            ),
        }

    if injury_risk:
        payload["risk_factors"] = risk_factors

    if coach_analysis:
        payload["coach_analysis"] = {
            "note": "Coach analysis requires additional coach metadata in workout comments.",
            "supported": True,
        }

    return payload
