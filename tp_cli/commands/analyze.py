"""Training analysis commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from tp_cli.commands.common import (
    authenticate,
    fetch_workouts_in_chunks,
    get_state,
    print_json_payload,
)
from tp_cli.core.analysis import (
    analyze_patterns,
    analyze_zones,
    build_weekly_analysis,
    weekly_to_markdown,
)
from tp_cli.utils.date_ranges import resolve_date_range, validate_date

app = typer.Typer(help="Training analysis commands")


def _fetch_for_analysis(
    ctx: typer.Context,
    start_date: Optional[str],
    end_date: Optional[str],
    last_days: Optional[int],
    last_weeks: Optional[int],
    this_year: bool,
    sport: str = "all",
):
    state = get_state(ctx)
    start, end = resolve_date_range(
        start_date=start_date,
        end_date=end_date,
        last_days=last_days,
        last_weeks=last_weeks,
        this_year=this_year,
    )

    _, api, user_id = authenticate(state)
    workouts = fetch_workouts_in_chunks(
        api=api,
        user_id=user_id,
        start=start,
        end=end,
        sport_filter=sport,
        classify_method="auto",
        config=state.config,
    )
    return state, workouts


@app.command("weekly")
def weekly_command(
    ctx: typer.Context,
    start_date: Optional[str] = typer.Option(None, help="Start date YYYY-MM-DD", callback=validate_date),
    end_date: Optional[str] = typer.Option(None, help="End date YYYY-MM-DD", callback=validate_date),
    last_weeks: Optional[int] = typer.Option(None, help="Analyze last N weeks"),
    last_days: Optional[int] = typer.Option(None, help="Analyze last N days"),
    this_year: bool = typer.Option(False, help="Analyze this year"),
    sport: str = typer.Option("all", help="Filter by sport"),
    output_file: Optional[Path] = typer.Option(None, help="Write result to file"),
    output_format: str = typer.Option("markdown", "--format", help="Output format: markdown|json"),
) -> None:
    """Generate weekly training analysis."""
    state, workouts = _fetch_for_analysis(
        ctx, start_date, end_date, last_days, last_weeks, this_year, sport=sport
    )

    report = build_weekly_analysis(workouts, sport_filter=sport)

    if state.json_output or output_format == "json":
        if output_file:
            output_file.write_text(json.dumps(report, indent=2) + "\n")
        print_json_payload(state, report)
        return

    markdown = weekly_to_markdown(report)
    if output_file:
        output_file.write_text(markdown)
    state.console.print(markdown)


@app.command("zones")
def zones_command(
    ctx: typer.Context,
    start_date: Optional[str] = typer.Option(None, help="Start date YYYY-MM-DD", callback=validate_date),
    end_date: Optional[str] = typer.Option(None, help="End date YYYY-MM-DD", callback=validate_date),
    last_weeks: Optional[int] = typer.Option(None, help="Analyze last N weeks"),
    last_days: Optional[int] = typer.Option(None, help="Analyze last N days"),
    this_year: bool = typer.Option(False, help="Analyze this year"),
    sport: str = typer.Option("run", help="Sport: swim|bike|run"),
    group_by: str = typer.Option("week", help="Group by week|month"),
    easy_max: Optional[float] = typer.Option(None, help="Easy zone upper bound (% of threshold, default: 75)"),
    lt1_max: Optional[float] = typer.Option(None, help="LT1 zone upper bound (% of threshold, default: 93)"),
    lt2_max: Optional[float] = typer.Option(None, help="LT2 zone upper bound (% of threshold, default: 100)"),
    output_file: Optional[Path] = typer.Option(None, help="Write result to file"),
) -> None:
    """Analyze zone distribution from structured workouts."""
    if sport not in {"swim", "bike", "run"}:
        raise typer.BadParameter("sport must be one of swim|bike|run")
    if group_by not in {"week", "month"}:
        raise typer.BadParameter("group-by must be week or month")

    state, workouts = _fetch_for_analysis(
        ctx, start_date, end_date, last_days, last_weeks, this_year, sport="all"
    )

    # Build zone thresholds: CLI flags > config > defaults
    from tp_cli.core.constants import DEFAULT_ZONE_THRESHOLDS
    config_zones = state.config.get("zones", {})
    thresholds = {
        "easy_max": easy_max if easy_max is not None else config_zones.get("easy_max", DEFAULT_ZONE_THRESHOLDS["easy_max"]),
        "lt1_max": lt1_max if lt1_max is not None else config_zones.get("lt1_max", DEFAULT_ZONE_THRESHOLDS["lt1_max"]),
        "lt2_max": lt2_max if lt2_max is not None else config_zones.get("lt2_max", DEFAULT_ZONE_THRESHOLDS["lt2_max"]),
    }
    report = analyze_zones(workouts, sport=sport, group_by=group_by, thresholds=thresholds)

    if output_file:
        output_file.write_text(json.dumps(report, indent=2) + "\n")

    if state.json_output:
        print_json_payload(state, report)
        return

    state.console.print(f"Zone analysis for {sport}")
    state.console.print(
        f"Range: {report['period']['start']} to {report['period']['end']} "
        f"({report['total_distance'] / 1000:.1f} km)"
    )
    for zone in ("easy", "lt1", "lt2", "vo2"):
        zone_row = report["zone_distribution"][zone]
        state.console.print(
            f"{zone.upper():4s}  {zone_row['distance'] / 1000:.1f} km  "
            f"{zone_row['pct']:.1f}%  sessions={zone_row['sessions']}"
        )


@app.command("patterns")
def patterns_command(
    ctx: typer.Context,
    start_date: Optional[str] = typer.Option(None, help="Start date YYYY-MM-DD", callback=validate_date),
    end_date: Optional[str] = typer.Option(None, help="End date YYYY-MM-DD", callback=validate_date),
    last_weeks: Optional[int] = typer.Option(None, help="Analyze last N weeks"),
    last_days: Optional[int] = typer.Option(None, help="Analyze last N days"),
    this_year: bool = typer.Option(False, help="Analyze this year"),
    coach_analysis: bool = typer.Option(False, help="Include coach-based notes"),
    multi_sport: bool = typer.Option(False, help="Analyze run-bike interactions"),
    injury_risk: bool = typer.Option(False, help="Highlight risk spikes"),
) -> None:
    """Identify training patterns and correlations."""
    state, workouts = _fetch_for_analysis(
        ctx, start_date, end_date, last_days, last_weeks, this_year, sport="all"
    )

    report = analyze_patterns(
        workouts,
        multi_sport=multi_sport,
        injury_risk=injury_risk,
        coach_analysis=coach_analysis,
    )

    if state.json_output:
        print_json_payload(state, report)
        return

    state.console.print(
        f"Patterns from {report['date_range']['start']} to {report['date_range']['end']}"
    )
    state.console.print("Same-day run/bike intensity combinations:")
    for row in report.get("same_day_combinations", [])[:10]:
        state.console.print(f"- run={row['run']} bike={row['bike']}: {row['count']}")

    if report.get("risk_factors"):
        state.console.print("Risk factors:")
        for factor in report["risk_factors"]:
            state.console.print(
                f"- {factor['week']}: {factor['type']} "
                f"(+{factor['increase_pct']}%, {factor['severity']})"
            )
