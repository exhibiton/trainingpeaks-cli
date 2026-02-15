"""Workout fetch/get commands."""

from __future__ import annotations

from collections import Counter
from contextlib import nullcontext
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

import typer
from rich.table import Table

from tp_cli.commands.common import (
    authenticate,
    fetch_workouts_in_chunks,
    get_state,
    print_json_payload,
)
from tp_cli.core.classify import classify_with_metadata
from tp_cli.core.config import resolve_output_dir
from tp_cli.core.constants import SPORT_MAP, SPORT_NAME_BY_ID
from tp_cli.exporters.json_export import write_json
from tp_cli.exporters.markdown import generate_indexes, workout_to_markdown, write_workout_markdown
from tp_cli.utils.date_ranges import resolve_date_range, validate_date
from tp_cli.utils.formatting import format_distance, format_duration


def _summary(workouts: list[Dict[str, Any]], start: date, end: date) -> Dict[str, Any]:
    by_sport = Counter()
    by_type = Counter()
    for workout in workouts:
        sport = SPORT_MAP.get(workout.get("workoutTypeValueId"), "other")
        by_sport[sport] += 1
        by_type[workout.get("classification", {}).get("type", "other")] += 1

    return {
        "total": len(workouts),
        "by_sport": dict(by_sport),
        "by_type": dict(by_type),
        "date_range": {
            "start": start.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
        },
    }


def fetch_command(
    ctx: typer.Context,
    start_date: Optional[str] = typer.Option(None, help="Start date (YYYY-MM-DD)", callback=validate_date),
    end_date: Optional[str] = typer.Option(None, help="End date (YYYY-MM-DD)", callback=validate_date),
    last_days: Optional[int] = typer.Option(None, help="Fetch last N days"),
    last_weeks: Optional[int] = typer.Option(None, help="Fetch last N weeks"),
    last_months: Optional[int] = typer.Option(None, help="Fetch last N months"),
    this_week: bool = typer.Option(False, help="Fetch this week"),
    last_week: bool = typer.Option(False, help="Fetch previous week"),
    this_month: bool = typer.Option(False, help="Fetch this month"),
    this_year: bool = typer.Option(False, help="Fetch this year"),
    all_time: bool = typer.Option(False, "--all", help="Fetch all available workouts"),
    sport: str = typer.Option("all", help="Filter by sport: swim|bike|run|all"),
    workout_type: Optional[str] = typer.Option(None, "--type", help="Filter by workout type"),
    min_tss: Optional[float] = typer.Option(None, help="Minimum TSS"),
    max_tss: Optional[float] = typer.Option(None, help="Maximum TSS"),
    output_dir: Optional[Path] = typer.Option(None, help="Output directory for exports"),
    export_format: str = typer.Option("both", "--format", help="Export format: json|markdown|both"),
    raw: bool = typer.Option(False, help="Also save raw API responses"),
    no_index: bool = typer.Option(False, help="Do not generate markdown indexes"),
    classify: str = typer.Option("auto", help="Classification method: auto|ai"),
    ai_model: Optional[str] = typer.Option(None, help="Reserved for AI classification"),
    ai_api_key: Optional[str] = typer.Option(None, help="Reserved for AI classification"),
    rewrite: bool = typer.Option(False, help="Rewrite existing markdown files"),
) -> None:
    """Fetch workouts and export them to disk and/or JSON output."""
    del ai_model, ai_api_key
    state = get_state(ctx)

    start, end = resolve_date_range(
        start_date=start_date,
        end_date=end_date,
        last_days=last_days,
        last_weeks=last_weeks,
        last_months=last_months,
        this_week=this_week,
        last_week=last_week,
        this_month=this_month,
        this_year=this_year,
        all_time=all_time,
    )

    if sport not in {"swim", "bike", "run", "all"}:
        raise typer.BadParameter("sport must be one of: swim, bike, run, all")
    if export_format not in {"json", "markdown", "both"}:
        raise typer.BadParameter("--format must be one of: json, markdown, both")

    _, api, user_id = authenticate(state)

    status_ctx = (
        state.console.status(
            f"Fetching workouts from {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}..."
        )
        if not state.plain_output
        else nullcontext()
    )
    with status_ctx:
        workouts = fetch_workouts_in_chunks(
            api=api,
            user_id=user_id,
            start=start,
            end=end,
            sport_filter=sport,
            type_filter=workout_type,
            min_tss=min_tss,
            max_tss=max_tss,
            classify_method=classify,
            config=state.config,
        )

    out_dir = resolve_output_dir(state.config, explicit=output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if raw:
        write_json(out_dir / "raw" / "all_workouts.json", workouts)

    markdown_written = 0
    json_path: Optional[Path] = None

    if export_format in {"json", "both"}:
        json_payload = {"workouts": workouts, "summary": _summary(workouts, start, end)}
        json_path = write_json(out_dir / "workouts.json", json_payload)

    if export_format in {"markdown", "both"}:
        for workout in workouts:
            workout_type_value = workout.get("classification", {}).get("type", "other")
            path = write_workout_markdown(out_dir, workout, workout_type_value, rewrite=rewrite)
            if path.exists():
                markdown_written += 1
        if not no_index:
            generate_indexes(out_dir, workouts)

    payload = {
        "workouts": workouts,
        "summary": _summary(workouts, start, end),
        "exports": {
            "output_dir": str(out_dir),
            "json_file": str(json_path) if json_path else None,
            "markdown_files": markdown_written if export_format in {"markdown", "both"} else 0,
        },
    }

    if state.json_output:
        print_json_payload(state, payload)
        return

    if state.plain_output:
        typer.echo("date\tsport\ttype\ttitle\tduration\tdistance\ttss")
        for workout in workouts:
            sport_label = SPORT_NAME_BY_ID.get(workout.get("workoutTypeValueId"), "?")
            tss_value = workout.get("tssActual") or workout.get("tssPlanned")
            tss_text = f"{float(tss_value):.1f}" if tss_value is not None else "-"
            typer.echo(
                "\t".join(
                    [
                        str((workout.get("workoutDay") or "")[:10]),
                        sport_label,
                        workout.get("classification", {}).get("type", "other"),
                        str(workout.get("title") or "Untitled"),
                        format_duration(workout.get("totalTime") or workout.get("totalTimePlanned")),
                        format_distance(workout.get("distance") or workout.get("distancePlanned")),
                        tss_text,
                    ]
                )
            )
        typer.echo(f"total\t{len(workouts)}")
        typer.echo(f"output_dir\t{out_dir}")
        return

    table = Table(title=f"Workouts ({len(workouts)} total)")
    table.add_column("Date")
    table.add_column("Sport")
    table.add_column("Type")
    table.add_column("Title")
    table.add_column("Duration")
    table.add_column("Distance")
    table.add_column("TSS")

    for workout in workouts[:30]:
        sport_label = SPORT_NAME_BY_ID.get(workout.get("workoutTypeValueId"), "?")
        tss_value = workout.get("tssActual") or workout.get("tssPlanned")
        table.add_row(
            str((workout.get("workoutDay") or "")[:10]),
            sport_label,
            workout.get("classification", {}).get("type", "other"),
            str(workout.get("title") or "Untitled"),
            format_duration(workout.get("totalTime") or workout.get("totalTimePlanned")),
            format_distance(workout.get("distance") or workout.get("distancePlanned")),
            f"{float(tss_value):.1f}" if tss_value is not None else "-",
        )

    state.console.print(table)
    state.console.print(
        f"Fetched {len(workouts)} workouts from {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
    )
    state.console.print(f"Exported to: {out_dir}")


def get_command(
    ctx: typer.Context,
    workout_id: str = typer.Argument(..., help="Workout ID"),
    output_format: str = typer.Option("json", "--format", help="Output format: json|markdown|raw"),
) -> None:
    """Fetch a single workout by ID."""
    state = get_state(ctx)

    if output_format not in {"json", "markdown", "raw"}:
        raise typer.BadParameter("--format must be one of: json, markdown, raw")

    _, api, user_id = authenticate(state)
    workout = api.get_workout(user_id=user_id, workout_id=workout_id)

    classification = classify_with_metadata(workout)
    workout["classification"] = {
        "type": classification.type,
        "method": classification.method,
        "confidence": classification.confidence,
        "reasoning": classification.reasoning,
    }

    if state.json_output:
        print_json_payload(state, workout)
        return

    if state.plain_output:
        for key in ("workoutDay", "title", "description", "distance", "totalTime", "tssPlanned"):
            typer.echo(f"{key}\t{workout.get(key)}")
        typer.echo(f"classification\t{classification.type}")
        return

    if output_format == "markdown":
        state.console.print(workout_to_markdown(workout, classification.type))
        return

    if output_format in {"json", "raw"}:
        print_json_payload(state, workout)
        return

    table = Table(title=f"Workout {workout_id}")
    table.add_column("Field")
    table.add_column("Value")
    for key in ("workoutDay", "title", "description", "distance", "totalTime", "tssPlanned"):
        table.add_row(key, str(workout.get(key)))
    table.add_row("classification", classification.type)
    state.console.print(table)
