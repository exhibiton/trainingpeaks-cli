from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple

from tp_cli.__main__ import app
from tp_cli.core.auth import AuthError


class FakeAPI:
    def __init__(self, workout: Dict[str, Any] | None = None) -> None:
        self.workout = workout or {}

    def get_workout(self, user_id: str, workout_id: str) -> Dict[str, Any]:
        return dict(self.workout or {"workoutId": workout_id, "workoutDay": "2026-02-14", "title": "Run"})


def _sample_workouts() -> List[Dict[str, Any]]:
    return [
        {
            "workoutId": "101",
            "workoutDay": "2026-02-14T00:00:00",
            "workoutTypeValueId": 3,
            "title": "Run",
            "distance": 10000,
            "totalTime": 1.0,
            "tssPlanned": 70,
            "classification": {"type": "easy"},
        }
    ]


def test_global_json_plain_conflict(runner) -> None:
    result = runner.invoke(app, ["--json", "--plain", "fetch"])
    assert result.exit_code == 2
    assert "--json" in result.stdout
    assert "--plain" in result.stdout


def test_fetch_command_json_output(monkeypatch, runner, tmp_path: Path) -> None:
    monkeypatch.setattr("tp_cli.commands.fetch.resolve_date_range", lambda **_: (date(2026, 2, 14), date(2026, 2, 14)))
    monkeypatch.setattr("tp_cli.commands.fetch.authenticate", lambda state: ("tok", FakeAPI(), "42"))
    monkeypatch.setattr("tp_cli.commands.fetch.fetch_workouts_in_chunks", lambda **_: _sample_workouts())
    monkeypatch.setattr("tp_cli.commands.fetch.resolve_output_dir", lambda config, explicit=None: tmp_path)

    result = runner.invoke(app, ["--json", "fetch", "--last-days", "1", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["total"] == 1
    assert payload["workouts"][0]["workoutId"] == "101"


def test_fetch_command_plain_output(monkeypatch, runner, tmp_path: Path) -> None:
    monkeypatch.setattr("tp_cli.commands.fetch.resolve_date_range", lambda **_: (date(2026, 2, 14), date(2026, 2, 14)))
    monkeypatch.setattr("tp_cli.commands.fetch.authenticate", lambda state: ("tok", FakeAPI(), "42"))
    monkeypatch.setattr("tp_cli.commands.fetch.fetch_workouts_in_chunks", lambda **_: _sample_workouts())
    monkeypatch.setattr("tp_cli.commands.fetch.resolve_output_dir", lambda config, explicit=None: tmp_path)

    result = runner.invoke(app, ["fetch", "--last-days", "1", "--format", "json"])
    assert result.exit_code == 0
    assert "Fetched 1 workouts" in result.stdout
    assert "Exported to:" in result.stdout
    assert tmp_path.name in result.stdout


def test_get_command_global_json_overrides_markdown(monkeypatch, runner) -> None:
    workout = {
        "workoutId": "abc",
        "workoutDay": "2026-02-14T00:00:00",
        "workoutTypeValueId": 3,
        "title": "Run",
    }
    monkeypatch.setattr("tp_cli.commands.fetch.authenticate", lambda state: ("tok", FakeAPI(workout), "42"))

    result = runner.invoke(app, ["--json", "get", "abc", "--format", "markdown"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["workoutId"] == "abc"


def test_export_plain_output(monkeypatch, runner, tmp_path: Path) -> None:
    monkeypatch.setattr("tp_cli.commands.export.resolve_date_range", lambda **_: (date(2026, 2, 14), date(2026, 2, 14)))
    monkeypatch.setattr("tp_cli.commands.export.authenticate", lambda state: ("tok", FakeAPI(), "42"))
    monkeypatch.setattr("tp_cli.commands.export.fetch_workouts_in_chunks", lambda **_: _sample_workouts())
    monkeypatch.setattr("tp_cli.commands.export.resolve_output_dir", lambda config, explicit=None: tmp_path)

    result = runner.invoke(app, ["export", "--format", "csv", "--last-days", "1"])
    assert result.exit_code == 0
    assert "Exported 1 workouts as csv" in result.stdout


def test_export_json_output(monkeypatch, runner, tmp_path: Path) -> None:
    monkeypatch.setattr("tp_cli.commands.export.resolve_date_range", lambda **_: (date(2026, 2, 14), date(2026, 2, 14)))
    monkeypatch.setattr("tp_cli.commands.export.authenticate", lambda state: ("tok", FakeAPI(), "42"))
    monkeypatch.setattr("tp_cli.commands.export.fetch_workouts_in_chunks", lambda **_: _sample_workouts())
    monkeypatch.setattr("tp_cli.commands.export.resolve_output_dir", lambda config, explicit=None: tmp_path)

    result = runner.invoke(app, ["--json", "export", "--format", "csv", "--last-days", "1"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "exported"
    assert payload["format"] == "csv"


def test_export_fit_plain_error(monkeypatch, runner, tmp_path: Path) -> None:
    monkeypatch.setattr("tp_cli.commands.export.resolve_date_range", lambda **_: (date(2026, 2, 14), date(2026, 2, 14)))
    monkeypatch.setattr("tp_cli.commands.export.authenticate", lambda state: ("tok", FakeAPI(), "42"))
    monkeypatch.setattr("tp_cli.commands.export.fetch_workouts_in_chunks", lambda **_: _sample_workouts())
    monkeypatch.setattr("tp_cli.commands.export.resolve_output_dir", lambda config, explicit=None: tmp_path)

    result = runner.invoke(app, ["export", "--format", "fit", "--last-days", "1"])
    assert result.exit_code == 1
    assert "FIT export is not implemented" in result.stdout


def test_analyze_zones_plain_output(monkeypatch, runner) -> None:
    monkeypatch.setattr("tp_cli.commands.analyze.resolve_date_range", lambda **_: (date(2026, 2, 14), date(2026, 2, 14)))
    monkeypatch.setattr("tp_cli.commands.analyze.authenticate", lambda state: ("tok", FakeAPI(), "42"))
    monkeypatch.setattr("tp_cli.commands.analyze.fetch_workouts_in_chunks", lambda **_: _sample_workouts())

    result = runner.invoke(app, ["analyze", "zones", "--last-days", "1", "--sport", "run"])
    assert result.exit_code == 0
    assert "Zone analysis for run" in result.stdout


def test_analyze_weekly_plain_output(monkeypatch, runner) -> None:
    monkeypatch.setattr("tp_cli.commands.analyze.resolve_date_range", lambda **_: (date(2026, 2, 14), date(2026, 2, 14)))
    monkeypatch.setattr("tp_cli.commands.analyze.authenticate", lambda state: ("tok", FakeAPI(), "42"))
    monkeypatch.setattr("tp_cli.commands.analyze.fetch_workouts_in_chunks", lambda **_: _sample_workouts())

    result = runner.invoke(app, ["analyze", "weekly", "--last-days", "1"])
    assert result.exit_code == 0
    assert "Weekly Training Analysis" in result.stdout


def test_analyze_zones_json_output(monkeypatch, runner) -> None:
    monkeypatch.setattr("tp_cli.commands.analyze.resolve_date_range", lambda **_: (date(2026, 2, 14), date(2026, 2, 14)))
    monkeypatch.setattr("tp_cli.commands.analyze.authenticate", lambda state: ("tok", FakeAPI(), "42"))
    monkeypatch.setattr("tp_cli.commands.analyze.fetch_workouts_in_chunks", lambda **_: _sample_workouts())

    result = runner.invoke(app, ["--json", "analyze", "zones", "--last-days", "1", "--sport", "run"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["sport"] == "run"


def test_analyze_patterns_plain_output(monkeypatch, runner) -> None:
    monkeypatch.setattr("tp_cli.commands.analyze.resolve_date_range", lambda **_: (date(2026, 2, 14), date(2026, 2, 14)))
    monkeypatch.setattr("tp_cli.commands.analyze.authenticate", lambda state: ("tok", FakeAPI(), "42"))
    monkeypatch.setattr("tp_cli.commands.analyze.fetch_workouts_in_chunks", lambda **_: _sample_workouts())

    result = runner.invoke(app, ["analyze", "patterns", "--last-days", "1"])
    assert result.exit_code == 0
    assert "Patterns from" in result.stdout


def test_upload_json_dry_run(monkeypatch, runner) -> None:
    result = runner.invoke(
        app,
        [
            "--json",
            "upload",
            "--date",
            "2026-02-14",
            "--sport",
            "run",
            "--title",
            "Easy Run",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["results"][0]["status"] == "dry-run"


def test_upload_plain_dry_run_output(runner) -> None:
    result = runner.invoke(
        app,
        [
            "upload",
            "--date",
            "2026-02-14",
            "--sport",
            "run",
            "--title",
            "Easy Run",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "Processed 1 workout(s)" in result.stdout


def test_delete_plain_force_output(monkeypatch, runner) -> None:
    class DeleteAPI:
        def __init__(self) -> None:
            self.deleted: List[Tuple[str, str]] = []

        def delete_workout(self, user_id: str, workout_id: str) -> None:
            self.deleted.append((user_id, workout_id))

    api = DeleteAPI()
    monkeypatch.setattr("tp_cli.commands.upload.authenticate", lambda state: ("tok", api, "42"))

    result = runner.invoke(app, ["delete", "abc", "--force"])
    assert result.exit_code == 0
    assert "Deleted workout abc" in result.stdout
    assert api.deleted == [("42", "abc")]


def test_login_and_logout_json(monkeypatch, runner) -> None:
    class FakeAuth:
        def __init__(self, config: Dict[str, Any], username: str | None = None, password: str | None = None) -> None:
            pass

        def login(self, force: bool = False) -> Tuple[str, Dict[str, str]]:
            return "token", {"sid": "cookie"}

        def get_user_info(self, token: str) -> Dict[str, Any]:
            return {"user": {"userId": 42, "username": "athlete", "email": "a@example.com"}}

        def logout(self) -> bool:
            return True

    monkeypatch.setattr("tp_cli.commands.auth.TrainingPeaksAuth", FakeAuth)

    login_result = runner.invoke(app, ["--json", "login"])
    assert login_result.exit_code == 0
    login_payload = json.loads(login_result.stdout)
    assert login_payload["status"] == "success"

    logout_result = runner.invoke(app, ["--json", "logout"])
    assert logout_result.exit_code == 0
    logout_payload = json.loads(logout_result.stdout)
    assert logout_payload["logged_out"] is True


def test_login_plain_error(monkeypatch, runner) -> None:
    class FailingAuth:
        def __init__(self, config: Dict[str, Any], username: str | None = None, password: str | None = None) -> None:
            pass

        def login(self, force: bool = False):
            raise AuthError("bad credentials")

    monkeypatch.setattr("tp_cli.commands.auth.TrainingPeaksAuth", FailingAuth)
    result = runner.invoke(app, ["login"])
    assert result.exit_code == 1
    assert "Login failed: bad credentials" in result.stdout
