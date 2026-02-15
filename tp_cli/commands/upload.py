"""Workout upload and delete commands."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer

from tp_cli.commands.common import authenticate, get_state, print_json_payload
from tp_cli.core.upload import convert_workout, fetch_threshold_speed, workout_exists
from tp_cli.utils.parsing import build_basic_workout, load_workout_input


def upload_command(
    ctx: typer.Context,
    file: Optional[Path] = typer.Option(None, help="JSON/YAML file with workout(s)"),
    stdin: bool = typer.Option(False, "--stdin", help="Read workout data from stdin"),
    date: Optional[str] = typer.Option(None, help="Workout date YYYY-MM-DD"),
    sport: Optional[str] = typer.Option(None, help="Sport: swim|bike|run"),
    title: Optional[str] = typer.Option(None, help="Workout title"),
    description: str = typer.Option("", help="Workout description"),
    force: bool = typer.Option(False, help="Upload even if duplicate exists"),
    dry_run: bool = typer.Option(False, help="Show payloads without uploading"),
) -> None:
    """Upload workout definitions to TrainingPeaks."""
    state = get_state(ctx)

    stdin_text = sys.stdin.read() if stdin else ""
    workouts = load_workout_input(file_path=file, read_stdin=stdin, stdin_text=stdin_text)

    if not workouts and date and sport and title:
        workouts = [build_basic_workout(date=date, sport=sport, title=title, description=description)]

    if not workouts:
        raise typer.BadParameter(
            "Provide --file, --stdin, or --date/--sport/--title for quick creation"
        )

    threshold_speed = 4.0
    api = None
    user_id = ""

    if not dry_run:
        _, api, user_id = authenticate(state)
        threshold_speed = fetch_threshold_speed(api, user_id)

    results: List[Dict[str, Any]] = []

    for workout in workouts:
        payload = convert_workout(workout, user_id=user_id or "preview", threshold_speed=threshold_speed)

        if dry_run:
            results.append({"status": "dry-run", "payload": payload})
            continue

        if api is None:
            raise RuntimeError("Authenticated API client is unavailable")
        if not force and workout_exists(api, user_id, workout["date"], payload["title"]):
            results.append(
                {
                    "status": "skipped",
                    "date": workout["date"],
                    "title": payload["title"],
                    "reason": "already_exists",
                }
            )
            continue

        response = api.create_workout(user_id, payload)
        workout_id = response.get("workoutId") if isinstance(response, dict) else None
        results.append(
            {
                "status": "created",
                "date": workout["date"],
                "title": payload["title"],
                "workoutId": workout_id,
                "url": (
                    f"https://app.trainingpeaks.com/workout/{workout_id}"
                    if workout_id
                    else None
                ),
            }
        )

    if state.json_output:
        print_json_payload(state, {"results": results})
        return

    if state.plain_output:
        typer.echo(f"processed\t{len(results)}")
        for item in results:
            typer.echo(json.dumps(item, separators=(",", ":")))
        return

    state.console.print(f"Processed {len(results)} workout(s)")
    for item in results:
        state.console.print(json.dumps(item, indent=2 if dry_run else None))


def delete_command(
    ctx: typer.Context,
    workout_id: str = typer.Argument(..., help="Workout ID"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompt"),
) -> None:
    """Delete workout by ID."""
    state = get_state(ctx)

    if not force:
        confirmed = typer.confirm(f"Delete workout {workout_id}?", default=False)
        if not confirmed:
            raise typer.Exit(code=0)

    _, api, user_id = authenticate(state)
    api.delete_workout(user_id, workout_id)

    payload = {"status": "deleted", "workoutId": workout_id}
    if state.json_output:
        print_json_payload(state, payload)
        return

    if state.plain_output:
        typer.echo("status\tdeleted")
        typer.echo(f"workout_id\t{workout_id}")
        return

    state.console.print(f"Deleted workout {workout_id}")
