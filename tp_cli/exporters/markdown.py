"""Markdown workout export functionality."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List

from tp_cli.core.constants import SPORT_MAP, SPORT_NAME_BY_ID, TYPE_LABELS
from tp_cli.utils.formatting import format_distance, format_duration, format_steps
from tp_cli.utils.text import slugify


def workout_to_markdown(workout: Dict[str, Any], workout_type: str) -> str:
    """Convert a workout object to markdown with frontmatter."""
    title = workout.get("title") or "Untitled"
    date = str((workout.get("workoutDay") or "")[:10])
    sport_id = workout.get("workoutTypeValueId")
    sport_name = SPORT_NAME_BY_ID.get(sport_id, str(sport_id))

    duration = workout.get("totalTime") or workout.get("totalTimePlanned")
    distance = workout.get("distance") or workout.get("distancePlanned")
    tss = workout.get("tssActual") or workout.get("tssPlanned")

    description = workout.get("description") or workout.get("coachComments") or ""
    comments = workout.get("workoutComments") or []
    note_lines: List[str] = []
    for comment in comments:
        if isinstance(comment, dict):
            note_lines.append(comment.get("comment") or comment.get("text") or "")
        elif isinstance(comment, str):
            note_lines.append(comment)
    notes = "\n".join([line for line in note_lines if line])

    structure = workout.get("structure")
    steps_data = None
    primary_metric = ""
    if isinstance(structure, dict):
        steps_data = structure.get("structure") or structure.get("steps")
        primary_metric = structure.get("primaryIntensityMetric", "")
    elif isinstance(structure, list):
        steps_data = structure

    extras: List[str] = []
    if workout.get("normalizedPowerActual"):
        extras.append(f"- **NP:** {float(workout['normalizedPowerActual']):.0f}W")
    if workout.get("powerAverage"):
        extras.append(f"- **Avg Power:** {workout['powerAverage']}W")
    if workout.get("heartRateAverage"):
        extras.append(f"- **Avg HR:** {workout['heartRateAverage']} bpm")
    if workout.get("cadenceAverage"):
        extras.append(f"- **Avg Cadence:** {workout['cadenceAverage']}")
    if workout.get("elevationGain"):
        extras.append(f"- **Elevation:** {float(workout['elevationGain']):.0f}m")
    if workout.get("if"):
        extras.append(f"- **IF:** {float(workout['if']):.2f}")
    extras_text = "\n".join(extras)

    title_yaml = title.replace('"', '\\"')
    tss_text = f"{float(tss):.1f}" if tss is not None else "null"

    return (
        f"---\n"
        f"title: \"{title_yaml}\"\n"
        f"date: \"{date}\"\n"
        f"sport: \"{sport_name.lower()}\"\n"
        f"type: \"{workout_type}\"\n"
        f"duration: \"{format_duration(duration)}\"\n"
        f"distance: \"{format_distance(distance)}\"\n"
        f"tss: {tss_text}\n"
        f"workoutId: {workout.get('workoutId', '')}\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"- **Date:** {date}\n"
        f"- **Sport:** {sport_name}\n"
        f"- **Type:** {TYPE_LABELS.get(workout_type, workout_type)}\n"
        f"- **Duration:** {format_duration(duration)}\n"
        f"- **Distance:** {format_distance(distance)}\n"
        f"- **TSS:** {tss_text if tss_text != 'null' else 'N/A'}\n"
        f"{extras_text}\n\n"
        f"## Description\n"
        f"{description or 'No description'}\n\n"
        f"## Structured Workout\n"
        f"{format_steps(steps_data, primary_metric)}\n\n"
        f"## Notes\n"
        f"{notes or 'No notes'}\n"
    )


def write_workout_markdown(
    output_dir: Path,
    workout: Dict[str, Any],
    workout_type: str,
    rewrite: bool = False,
) -> Path:
    """Write one workout markdown file and return output path."""
    sport_key = SPORT_MAP.get(workout.get("workoutTypeValueId"), "other")
    date = str((workout.get("workoutDay") or "unknown")[:10])
    slug = slugify(str(workout.get("title") or "untitled"))
    filename = f"{date}-{slug}.md"

    out_dir = output_dir / sport_key / workout_type
    out_path = out_dir / filename

    if out_path.exists() and not rewrite:
        return out_path

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(workout_to_markdown(workout, workout_type))
    return out_path


def generate_indexes(output_dir: Path, workouts: Iterable[Dict[str, Any]]) -> None:
    """Generate top-level and per-sport index markdown files."""
    rows: List[Dict[str, Any]] = []
    for workout in workouts:
        sport_id = workout.get("workoutTypeValueId")
        sport_key = SPORT_MAP.get(sport_id, "other")
        sport_name = SPORT_NAME_BY_ID.get(sport_id, "?")
        workout_type = workout.get("classification", {}).get("type") or "other"
        date = str((workout.get("workoutDay") or "")[:10])
        title = str(workout.get("title") or "Untitled")
        filename = f"{date}-{slugify(title)}.md"

        rows.append(
            {
                "date": date,
                "sport": sport_name,
                "sport_key": sport_key,
                "type": workout_type,
                "title": title,
                "duration": format_duration(workout.get("totalTime") or workout.get("totalTimePlanned")),
                "distance": format_distance(workout.get("distance") or workout.get("distancePlanned")),
                "tss": (
                    f"{float(workout.get('tssActual') or workout.get('tssPlanned')):.1f}"
                    if (workout.get("tssActual") or workout.get("tssPlanned")) is not None
                    else "-"
                ),
                "path": f"{sport_key}/{workout_type}/{filename}",
            }
        )

    rows.sort(key=lambda row: row["date"], reverse=True)

    def _write_index(path: Path, title: str, data: List[Dict[str, Any]], trim_sport: bool = False) -> None:
        lines = [f"# {title}", "", f"_{len(data)} workouts_", "", "| Date | Sport | Type | Title | Duration | Distance | TSS |", "|------|-------|------|-------|----------|----------|-----|"]
        for row in data:
            rel_path = row["path"]
            if trim_sport:
                rel_path = "/".join(rel_path.split("/")[1:])
            link = f"[{row['title']}]({rel_path})"
            lines.append(
                f"| {row['date']} | {row['sport']} | {row['type']} | {link} | {row['duration']} | {row['distance']} | {row['tss']} |"
            )
        lines.append("")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines))

    _write_index(output_dir / "INDEX.md", "All Workouts", rows)
    for sport_key, sport_name in (("swim", "Swim"), ("bike", "Bike"), ("run", "Run")):
        sport_rows = [row for row in rows if row["sport_key"] == sport_key]
        if sport_rows:
            _write_index(output_dir / sport_key / "INDEX.md", f"{sport_name} Workouts", sport_rows, trim_sport=True)
