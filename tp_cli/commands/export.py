"""Export workouts to external formats."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional

import typer

from tp_cli.commands.common import (
    authenticate,
    fetch_workouts_in_chunks,
    get_state,
    print_json_payload,
)
from tp_cli.core.config import resolve_output_dir
from tp_cli.core.constants import SPORT_MAP
from tp_cli.utils.date_ranges import resolve_date_range, validate_date


def _ics_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _write_csv(path: Path, workouts: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "workoutId",
        "workoutDay",
        "sport",
        "title",
        "description",
        "distance",
        "totalTime",
        "tssPlanned",
        "classification",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for workout in workouts:
            writer.writerow(
                {
                    "workoutId": workout.get("workoutId"),
                    "workoutDay": str(workout.get("workoutDay", ""))[:10],
                    "sport": SPORT_MAP.get(workout.get("workoutTypeValueId"), "other"),
                    "title": workout.get("title"),
                    "description": workout.get("description"),
                    "distance": workout.get("distance") or workout.get("distancePlanned"),
                    "totalTime": workout.get("totalTime") or workout.get("totalTimePlanned"),
                    "tssPlanned": workout.get("tssPlanned"),
                    "classification": workout.get("classification", {}).get("type"),
                }
            )


def _write_ical(path: Path, workouts: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//trainingpeaks-cli//EN"]
    for workout in workouts:
        day = str(workout.get("workoutDay", ""))[:10].replace("-", "")
        if not day:
            continue
        wid = workout.get("workoutId") or f"unknown-{day}"
        title = _ics_escape(str(workout.get("title") or "Workout"))
        description = _ics_escape(str(workout.get("description") or ""))
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{wid}@trainingpeaks-cli",
                f"DTSTART;VALUE=DATE:{day}",
                f"SUMMARY:{title}",
                f"DESCRIPTION:{description}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    path.write_text("\n".join(lines) + "\n")


def _write_tcx(output_dir: Path, workouts: List[Dict[str, object]]) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for workout in workouts:
        workout_id = workout.get("workoutId")
        if not workout_id:
            continue
        day = str(workout.get("workoutDay", ""))[:10]
        sport = SPORT_MAP.get(workout.get("workoutTypeValueId"), "other")
        title = str(workout.get("title") or "Workout")
        file_path = output_dir / f"{day}-{workout_id}.tcx"
        sport_label = "Running" if sport == "run" else "Biking" if sport == "bike" else "Other"
        file_path.write_text(
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<TrainingCenterDatabase>\n"
            "  <Workouts>\n"
            f"    <Workout Sport=\"{sport_label}\">\n"
            f"      <Name>{title}</Name>\n"
            "    </Workout>\n"
            "  </Workouts>\n"
            "</TrainingCenterDatabase>\n"
        )
        count += 1
    return count


def export_command(
    ctx: typer.Context,
    start_date: Optional[str] = typer.Option(None, help="Start date YYYY-MM-DD", callback=validate_date),
    end_date: Optional[str] = typer.Option(None, help="End date YYYY-MM-DD", callback=validate_date),
    last_days: Optional[int] = typer.Option(None, help="Export last N days"),
    last_weeks: Optional[int] = typer.Option(None, help="Export last N weeks"),
    this_month: bool = typer.Option(False, help="Export this month"),
    this_year: bool = typer.Option(False, help="Export this year"),
    output_format: str = typer.Option(
        "csv",
        "--format",
        help="Export format: csv|ical|tcx (minimal/placeholder)|fit (not yet implemented)",
    ),
    output_dir: Optional[Path] = typer.Option(None, help="Output directory"),
    output_file: Optional[Path] = typer.Option(None, help="Single output file (csv/ical)"),
    sport: str = typer.Option("all", help="Filter sport"),
    workout_type: Optional[str] = typer.Option(None, "--type", help="Filter workout type"),
) -> None:
    """Export workouts in CSV, iCal, or simple TCX format."""
    state = get_state(ctx)

    if output_format not in {"tcx", "fit", "ical", "csv"}:
        raise typer.BadParameter("--format must be tcx|fit|ical|csv")

    if output_format == "tcx":
        typer.echo(
            "Warning: TCX export is minimal/placeholder — files contain metadata only, "
            "no lap/track data.",
            err=True,
        )

    start, end = resolve_date_range(
        start_date=start_date,
        end_date=end_date,
        last_days=last_days,
        last_weeks=last_weeks,
        this_month=this_month,
        this_year=this_year,
    )

    _, api, user_id = authenticate(state)
    workouts = fetch_workouts_in_chunks(
        api=api,
        user_id=user_id,
        start=start,
        end=end,
        sport_filter=sport,
        type_filter=workout_type,
        classify_method="auto",
        config=state.config,
    )

    out_dir = resolve_output_dir(state.config, explicit=output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    result: Dict[str, object]

    if output_format == "csv":
        path = output_file or (out_dir / "workouts.csv")
        _write_csv(path, workouts)
        result = {"status": "exported", "format": "csv", "path": str(path), "count": len(workouts)}
    elif output_format == "ical":
        path = output_file or (out_dir / "training.ics")
        _write_ical(path, workouts)
        result = {"status": "exported", "format": "ical", "path": str(path), "count": len(workouts)}
    elif output_format == "tcx":
        tcx_dir = out_dir / "tcx"
        count = _write_tcx(tcx_dir, workouts)
        result = {"status": "exported", "format": "tcx", "path": str(tcx_dir), "count": count}
    else:
        result = {
            "status": "error",
            "format": "fit",
            "message": "FIT export is not implemented yet in this phase.",
        }

    if state.json_output:
        print_json_payload(state, result)
        return

    if state.plain_output:
        for key in ("status", "format", "path", "count", "message"):
            if key in result and result[key] is not None:
                typer.echo(f"{key}\t{result[key]}")
        return

    if result.get("status") == "error":
        state.console.print(str(result.get("message", "Export failed")))
        raise typer.Exit(code=1)

    state.console.print(
        f"Exported {result.get('count', 0)} workouts as {result.get('format')} "
        f"to {result.get('path')}"
    )
