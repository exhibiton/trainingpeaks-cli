"""Threshold pace/speed/power commands."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import typer

from tp_cli.commands.common import authenticate, get_state, print_json_payload

app = typer.Typer(help="Get and set threshold pace/speed/power")

SPORT_BY_WORKOUT_TYPE = {1: "swim", 2: "bike", 3: "run"}
WORKOUT_TYPE_BY_SPORT = {"swim": 1, "bike": 2, "run": 3}
SPORT_LABEL = {"swim": "Swim", "bike": "Bike", "run": "Run"}
SPORT_ORDER = {"run": 0, "bike": 1, "swim": 2}
PACE_DISTANCE_METERS = {"run": 1000.0, "swim": 100.0, "bike": 1000.0}
PACE_UNIT = {"run": "min/km", "swim": "sec/100m", "bike": "min/km"}

# Power zone sport mapping (workoutTypeId 0 = default/bike)
POWER_SPORT_BY_WORKOUT_TYPE = {0: "bike"}
POWER_WORKOUT_TYPE_BY_SPORT = {"bike": 0}


def _normalize_sport(sport: Optional[str]) -> Optional[str]:
    if sport is None:
        return None
    normalized = sport.strip().lower()
    if normalized not in WORKOUT_TYPE_BY_SPORT:
        raise typer.BadParameter("sport must be one of: run, swim, bike")
    return normalized


def _normalize_speed_zones(settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = settings.get("speedZones", [])
    if not isinstance(raw, list):
        return []
    return [zone for zone in raw if isinstance(zone, dict)]


def _normalize_power_zones(settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = settings.get("powerZones", [])
    if not isinstance(raw, list):
        return []
    return [zone for zone in raw if isinstance(zone, dict)]


def _parse_pace_seconds(value: str) -> int:
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ValueError("invalid pace")
    minutes_text, seconds_text = parts
    if not minutes_text.isdigit() or not seconds_text.isdigit() or len(seconds_text) != 2:
        raise ValueError("invalid pace")
    minutes = int(minutes_text)
    seconds = int(seconds_text)
    if seconds >= 60:
        raise ValueError("invalid pace")
    total_seconds = (minutes * 60) + seconds
    if total_seconds <= 0:
        raise ValueError("invalid pace")
    return total_seconds


def _pace_seconds_to_speed_ms(total_seconds: int, sport: str) -> float:
    return PACE_DISTANCE_METERS[sport] / float(total_seconds)


def _speed_ms_to_pace(speed_ms: float, sport: str) -> str:
    if speed_ms <= 0:
        return "?"
    seconds_per_unit = PACE_DISTANCE_METERS[sport] / speed_ms
    rounded = int(seconds_per_unit + 0.5)
    minutes, seconds = divmod(rounded, 60)
    return f"{minutes}:{seconds:02d}"


def _find_speed_zone(speed_zones: List[Dict[str, Any]], workout_type_id: int) -> Optional[Dict[str, Any]]:
    for zone in speed_zones:
        if zone.get("workoutTypeId") == workout_type_id:
            return zone
    return None


def _find_power_zone(power_zones: List[Dict[str, Any]], workout_type_id: int) -> Optional[Dict[str, Any]]:
    for zone in power_zones:
        if zone.get("workoutTypeId") == workout_type_id:
            return zone
    return None


def _format_zone(sport: str, threshold_ms: float) -> Dict[str, Any]:
    return {
        "sport": sport,
        "threshold_ms": float(f"{threshold_ms:.4f}"),
        "threshold_pace": _speed_ms_to_pace(threshold_ms, sport),
        "unit": PACE_UNIT[sport],
    }


def _format_power_zone(sport: str, threshold_watts: float) -> Dict[str, Any]:
    return {
        "sport": sport,
        "threshold_watts": int(threshold_watts),
        "unit": "W",
    }


def _format_rich_pace(zone: Dict[str, Any]) -> str:
    pace = str(zone["threshold_pace"])
    sport = str(zone["sport"])
    if sport == "swim":
        return f"{pace}/100m"
    return f"{pace}/km"


def _error_and_exit(state: Any, message: str, code: int = 1) -> None:
    if state.json_output:
        print_json_payload(state, {"status": "error", "message": message})
    elif state.plain_output:
        typer.echo(f"error\t{message}")
    else:
        state.console.print(message)
    raise typer.Exit(code=code)


@app.command("get")
def get_threshold_command(
    ctx: typer.Context,
    sport: Optional[str] = typer.Option(None, "--sport", help="Sport: run|swim|bike"),
) -> None:
    """Get current threshold pace/speed/power."""
    state = get_state(ctx)
    sport_filter = _normalize_sport(sport)

    _, api, user_id = authenticate(state)
    settings = api.get_athlete_settings(user_id)
    speed_zones = _normalize_speed_zones(settings)
    power_zones = _normalize_power_zones(settings)

    rows: List[Dict[str, Any]] = []

    # Speed/pace thresholds
    for zone in speed_zones:
        workout_type_id = zone.get("workoutTypeId")
        sport_name = SPORT_BY_WORKOUT_TYPE.get(workout_type_id)
        if sport_name is None:
            continue
        if sport_filter is not None and sport_filter != sport_name:
            continue
        threshold_raw = zone.get("threshold")
        if threshold_raw is None:
            continue
        try:
            threshold_ms = float(threshold_raw)
        except (TypeError, ValueError):
            continue
        rows.append(_format_zone(sport_name, threshold_ms))

    # Power thresholds
    for zone in power_zones:
        workout_type_id = zone.get("workoutTypeId")
        sport_name = POWER_SPORT_BY_WORKOUT_TYPE.get(workout_type_id)
        if sport_name is None:
            continue
        if sport_filter is not None and sport_filter != sport_name:
            continue
        threshold_raw = zone.get("threshold")
        if threshold_raw is None:
            continue
        try:
            threshold_watts = float(threshold_raw)
        except (TypeError, ValueError):
            continue
        rows.append(_format_power_zone(sport_name, threshold_watts))

    rows.sort(key=lambda row: SPORT_ORDER.get(str(row["sport"]), 99))

    if not rows:
        if sport_filter is not None:
            _error_and_exit(state, f"No {sport_filter} threshold configured")
        _error_and_exit(state, "No thresholds configured")

    if state.json_output:
        print_json_payload(state, rows[0] if len(rows) == 1 else rows)
        return

    if state.plain_output:
        for row in rows:
            if "threshold_watts" in row:
                typer.echo(f"{row['sport']}\t{row['threshold_watts']}\tW")
            else:
                typer.echo(
                    f"{row['sport']}\t{row['threshold_ms']:.4f}\t{row['threshold_pace']}\t{row['unit']}"
                )
        return

    for row in rows:
        if "threshold_watts" in row:
            state.console.print(
                f"{SPORT_LABEL[str(row['sport'])]} FTP: {row['threshold_watts']}W"
            )
        else:
            state.console.print(
                f"{SPORT_LABEL[str(row['sport'])]}: {_format_rich_pace(row)} ({row['threshold_ms']:.2f} m/s)"
            )


@app.command("set")
def set_threshold_command(
    ctx: typer.Context,
    value: str = typer.Argument(..., help="Threshold: pace M:SS (run/swim) or watts (bike)"),
    sport: str = typer.Option("run", "--sport", help="Sport: run|swim|bike"),
) -> None:
    """Set threshold pace/speed/power."""
    state = get_state(ctx)
    selected_sport = _normalize_sport(sport)
    if selected_sport is None:
        raise typer.BadParameter("sport must be one of: run, swim, bike")

    _, api, user_id = authenticate(state)
    settings = api.get_athlete_settings(user_id)

    try:
        current_user_id = int(user_id)
    except ValueError:
        _error_and_exit(state, f"Invalid user id returned by API: {user_id}")

    # Bike power threshold
    if selected_sport == "bike" and ":" not in value:
        try:
            new_watts = int(value)
        except ValueError:
            raise typer.BadParameter("Expected integer watts for bike, e.g. 267")
        if new_watts <= 0:
            raise typer.BadParameter("Watts must be positive")

        power_zones = _normalize_power_zones(settings)
        target_zone = _find_power_zone(power_zones, POWER_WORKOUT_TYPE_BY_SPORT["bike"])
        if target_zone is None:
            _error_and_exit(state, "No bike power zone configured")

        old_watts = int(float(target_zone.get("threshold", 0)))

        payload: List[Dict[str, Any]] = []
        for zone in power_zones:
            zone_payload = dict(zone)
            workout_type_id = zone_payload.get("workoutTypeId")
            if workout_type_id == POWER_WORKOUT_TYPE_BY_SPORT["bike"]:
                zone_payload["threshold"] = new_watts
            zone_payload["currentUserId"] = current_user_id
            payload.append(zone_payload)

        api.put_powerzones(user_id=user_id, payload=payload)

        # Verify
        verified_settings = api.get_athlete_settings(user_id)
        verified_power_zones = _normalize_power_zones(verified_settings)
        verified_zone = _find_power_zone(verified_power_zones, POWER_WORKOUT_TYPE_BY_SPORT["bike"])
        if verified_zone is None:
            _error_and_exit(state, "Unable to verify updated bike power threshold")

        verified_watts = int(float(verified_zone["threshold"]))

        result = {
            "status": "updated",
            "sport": "bike",
            "previous": _format_power_zone("bike", old_watts),
            "current": _format_power_zone("bike", verified_watts),
        }

        if state.json_output:
            print_json_payload(state, result)
            return
        if state.plain_output:
            typer.echo("status\tupdated")
            typer.echo("sport\tbike")
            typer.echo(f"previous_watts\t{old_watts}")
            typer.echo(f"current_watts\t{verified_watts}")
            typer.echo("unit\tW")
            return
        state.console.print(f"Bike FTP updated: {old_watts}W → {verified_watts}W")
        return

    # Speed/pace threshold (run, swim, or bike pace)
    try:
        pace_seconds = _parse_pace_seconds(value)
    except ValueError as exc:
        raise typer.BadParameter("Expected format: M:SS, e.g. 4:25") from exc

    new_threshold_ms = _pace_seconds_to_speed_ms(pace_seconds, selected_sport)

    speed_zones = _normalize_speed_zones(settings)
    target_workout_type_id = WORKOUT_TYPE_BY_SPORT[selected_sport]
    target_zone = _find_speed_zone(speed_zones, target_workout_type_id)
    if target_zone is None:
        _error_and_exit(state, f"No {selected_sport} speed zone configured")

    old_threshold_raw = target_zone.get("threshold")
    old_threshold_ms = float(old_threshold_raw) if old_threshold_raw is not None else 0.0

    payload_speed: List[Dict[str, Any]] = []
    for zone in speed_zones:
        zone_payload = dict(zone)
        workout_type_id = zone_payload.get("workoutTypeId")
        if workout_type_id == target_workout_type_id or (
            selected_sport == "run" and workout_type_id == 0
        ):
            zone_payload["threshold"] = new_threshold_ms
        zone_payload["currentUserId"] = current_user_id
        payload_speed.append(zone_payload)

    api.put_speedzones(user_id=user_id, payload=payload_speed)

    verified_settings = api.get_athlete_settings(user_id)
    verified_speed_zones = _normalize_speed_zones(verified_settings)
    verified_zone = _find_speed_zone(verified_speed_zones, target_workout_type_id)
    if verified_zone is None or verified_zone.get("threshold") is None:
        _error_and_exit(state, f"Unable to verify updated {selected_sport} threshold")

    verified_threshold_ms = float(verified_zone["threshold"])

    previous = _format_zone(selected_sport, old_threshold_ms)
    current = _format_zone(selected_sport, verified_threshold_ms)
    result = {
        "status": "updated",
        "sport": selected_sport,
        "previous": previous,
        "current": current,
    }

    if state.json_output:
        print_json_payload(state, result)
        return

    if state.plain_output:
        typer.echo("status\tupdated")
        typer.echo(f"sport\t{selected_sport}")
        typer.echo(f"previous_pace\t{previous['threshold_pace']}")
        typer.echo(f"current_pace\t{current['threshold_pace']}")
        typer.echo(f"threshold_ms\t{current['threshold_ms']:.4f}")
        typer.echo(f"unit\t{current['unit']}")
        return

    state.console.print(
        f"{SPORT_LABEL[selected_sport]} threshold updated: "
        f"{_format_rich_pace(previous)} → {_format_rich_pace(current)} "
        f"({current['threshold_ms']:.2f} m/s)"
    )
