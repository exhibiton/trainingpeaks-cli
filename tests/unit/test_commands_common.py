from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

import pytest
import typer
from rich.console import Console

from tp_cli.commands.common import authenticate, fetch_workouts_in_chunks, get_state
from tp_cli.core.state import CLIState


@dataclass
class FakeContext:
    obj: Any


def _state(config: Dict[str, Any] | None = None) -> CLIState:
    return CLIState(
        json_output=False,
        plain_output=True,
        verbose=False,
        quiet=False,
        config_path=Path("/tmp/config.toml"),
        config=config or {"api": {"rate_limit_delay": 0.0, "max_retries": 5, "timeout_seconds": 12}},
        console=Console(record=True),
    )


def test_get_state_returns_cli_state() -> None:
    state = _state()
    assert get_state(FakeContext(obj=state)) is state


def test_get_state_raises_on_invalid_obj() -> None:
    with pytest.raises(typer.Exit):
        get_state(FakeContext(obj={"not": "state"}))


def test_authenticate_uses_configured_api_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _state()
    seen: Dict[str, Any] = {}

    class FakeAuth:
        def __init__(self, config: Dict[str, Any]) -> None:
            seen["auth_config"] = config

        def login(self, force: bool = False):
            seen["force"] = force
            return "token-1", {"sid": "x"}

    class FakeAPI:
        def __init__(self, token: str, rate_limit_delay: float, max_retries: int, timeout_seconds: int) -> None:
            seen["token"] = token
            seen["rate_limit_delay"] = rate_limit_delay
            seen["max_retries"] = max_retries
            seen["timeout_seconds"] = timeout_seconds

        def get_user_id(self) -> str:
            return "42"

    monkeypatch.setattr("tp_cli.commands.common.TrainingPeaksAuth", FakeAuth)
    monkeypatch.setattr("tp_cli.commands.common.TrainingPeaksAPI", FakeAPI)

    token, api, user_id = authenticate(state, force=True)
    assert token == "token-1"
    assert user_id == "42"
    assert seen["rate_limit_delay"] == 0.0
    assert seen["max_retries"] == 5
    assert seen["timeout_seconds"] == 12


class DummyAPI:
    def __init__(self, payloads: List[List[Dict[str, Any]]]) -> None:
        self.payloads = list(payloads)
        self.calls: List[tuple[str, str, str]] = []

    def get_workouts(self, user_id: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        self.calls.append((user_id, start_date, end_date))
        return self.payloads.pop(0)


def test_fetch_workouts_in_chunks_collects_classification(monkeypatch: pytest.MonkeyPatch) -> None:
    workouts_1 = [
        {
            "workoutId": "a",
            "workoutDay": "2026-02-10T00:00:00",
            "workoutTypeValueId": 3,
            "tssPlanned": 70,
            "title": "Run LT2",
        }
    ]
    workouts_2 = [
        {
            "workoutId": "b",
            "workoutDay": "2026-02-11T00:00:00",
            "workoutTypeValueId": 2,
            "tssPlanned": 50,
            "title": "Bike Easy",
        }
    ]
    api = DummyAPI([workouts_1, workouts_2])

    monkeypatch.setattr(
        "tp_cli.commands.common.chunk_date_range",
        lambda start, end, chunk_days: [
            (date(2026, 2, 1), date(2026, 2, 5)),
            (date(2026, 2, 6), date(2026, 2, 14)),
        ],
    )
    monkeypatch.setattr("tp_cli.commands.common.classification_rules_from_config", lambda cfg: {})
    monkeypatch.setattr(
        "tp_cli.commands.common.classify_with_metadata",
        lambda workout, method, rules: type(
            "Meta",
            (),
            {"type": "lt2" if "LT2" in workout["title"] else "easy", "method": "auto", "confidence": 0.8, "reasoning": "rule"},
        )(),
    )

    rows = fetch_workouts_in_chunks(
        api=api,
        user_id="42",
        start=date(2026, 2, 1),
        end=date(2026, 2, 14),
        config={},
    )
    assert len(rows) == 2
    assert rows[0]["workoutId"] == "b"
    assert rows[1]["classification"]["type"] == "lt2"
    assert len(api.calls) == 2


def test_fetch_workouts_in_chunks_filters_sport_type_and_tss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = [
        {
            "workoutId": "a",
            "workoutDay": "2026-02-10T00:00:00",
            "workoutTypeValueId": 3,
            "tssPlanned": 30,
            "title": "Run Easy",
        },
        {
            "workoutId": "b",
            "workoutDay": "2026-02-11T00:00:00",
            "workoutTypeValueId": 2,
            "tssPlanned": 90,
            "title": "Bike LT2",
        },
    ]
    api = DummyAPI([payload])

    monkeypatch.setattr(
        "tp_cli.commands.common.chunk_date_range",
        lambda start, end, chunk_days: [(date(2026, 2, 1), date(2026, 2, 14))],
    )
    monkeypatch.setattr("tp_cli.commands.common.classification_rules_from_config", lambda cfg: {})
    monkeypatch.setattr(
        "tp_cli.commands.common.classify_with_metadata",
        lambda workout, method, rules: type(
            "Meta",
            (),
            {
                "type": "easy" if workout["workoutId"] == "a" else "lt2",
                "method": "auto",
                "confidence": 0.8,
                "reasoning": "rule",
            },
        )(),
    )

    rows = fetch_workouts_in_chunks(
        api=api,
        user_id="42",
        start=date(2026, 2, 1),
        end=date(2026, 2, 14),
        sport_filter="bike",
        type_filter="lt2",
        min_tss=80,
        max_tss=100,
        config={},
    )
    assert [row["workoutId"] for row in rows] == ["b"]
