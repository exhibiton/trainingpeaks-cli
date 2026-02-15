"""Shared command helpers."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import typer

from tp_cli.core.api import TrainingPeaksAPI
from tp_cli.core.auth import TrainingPeaksAuth
from tp_cli.core.classify import classification_rules_from_config, classify_with_metadata
from tp_cli.core.constants import SPORT_MAP
from tp_cli.core.state import CLIState
from tp_cli.utils.date_ranges import chunk_date_range


def get_state(ctx: typer.Context) -> CLIState:
    """Extract validated CLI state from Typer context."""
    state = ctx.obj
    if not isinstance(state, CLIState):
        raise typer.Exit(code=2)
    return state


def authenticate(state: CLIState, force: bool = False) -> Tuple[str, TrainingPeaksAPI, str]:
    """Login and return (token, api_client, user_id)."""
    auth = TrainingPeaksAuth(config=state.config)
    token, _ = auth.login(force=force)

    api_cfg = state.config.get("api", {})
    api = TrainingPeaksAPI(
        token=token,
        rate_limit_delay=float(api_cfg.get("rate_limit_delay", 1.0)),
        max_retries=int(api_cfg.get("max_retries", 3)),
        timeout_seconds=int(api_cfg.get("timeout_seconds", 30)),
    )
    user_id = api.get_user_id()
    return token, api, user_id


def print_json_payload(state: CLIState, payload: Any) -> None:
    """Print JSON payload with plain-mode fallback for piping."""
    if state.plain_output:
        typer.echo(json.dumps(payload, separators=(",", ":")))
        return
    state.console.print_json(data=payload)


def fetch_workouts_in_chunks(
    api: TrainingPeaksAPI,
    user_id: str,
    start: date,
    end: date,
    sport_filter: str = "all",
    type_filter: Optional[str] = None,
    min_tss: Optional[float] = None,
    max_tss: Optional[float] = None,
    classify_method: str = "auto",
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Fetch workouts over date chunks and apply filters/classification."""
    all_workouts: List[Dict[str, Any]] = []
    rules = classification_rules_from_config(config or {})

    for chunk_start, chunk_end in chunk_date_range(start, end, chunk_days=90):
        payload = api.get_workouts(
            user_id=user_id,
            start_date=chunk_start.strftime("%Y-%m-%d"),
            end_date=chunk_end.strftime("%Y-%m-%d"),
        )
        if isinstance(payload, list):
            all_workouts.extend(payload)

    filtered: List[Dict[str, Any]] = []
    for workout in all_workouts:
        sport_id = workout.get("workoutTypeValueId")
        sport_key = SPORT_MAP.get(sport_id)
        if sport_filter != "all" and sport_key != sport_filter:
            continue

        classification = classify_with_metadata(workout, method=classify_method, rules=rules)
        workout["classification"] = {
            "type": classification.type,
            "method": classification.method,
            "confidence": classification.confidence,
            "reasoning": classification.reasoning,
        }

        if type_filter and classification.type != type_filter:
            continue

        tss = workout.get("tssActual") or workout.get("tssPlanned")
        if min_tss is not None and (tss is None or float(tss) < min_tss):
            continue
        if max_tss is not None and (tss is None or float(tss) > max_tss):
            continue

        filtered.append(workout)

    filtered.sort(key=lambda item: str(item.get("workoutDay", "")), reverse=True)
    return filtered
