from __future__ import annotations

import requests
import pytest

from tp_cli.core.api import APIError, TrainingPeaksAPI


class _MockResponse:
    def __init__(
        self,
        status_code: int = 200,
        payload: dict[str, object] | None = None,
        text: str = '{"ok":true}',
    ) -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {"ok": True}
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError("request failed", response=self)

    def json(self) -> dict[str, object]:
        return self._payload


def test_api_retries_then_succeeds(monkeypatch) -> None:
    attempts = {"count": 0}

    def fake_request(*args, **kwargs):  # type: ignore[no-untyped-def]
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise requests.Timeout("timeout")
        return _MockResponse(payload={"user": {"userId": 42}}, text='{"user":{"userId":42}}')

    monkeypatch.setattr("tp_cli.core.api.requests.request", fake_request)
    monkeypatch.setattr("tp_cli.core.api.time.sleep", lambda _: None)

    api = TrainingPeaksAPI(token="token", rate_limit_delay=0, max_retries=3)
    response = api.get("/users/v3/user")

    assert response["user"]["userId"] == 42
    assert attempts["count"] == 2


def test_api_retries_on_server_error(monkeypatch) -> None:
    attempts = {"count": 0}

    def fake_request(*args, **kwargs):  # type: ignore[no-untyped-def]
        attempts["count"] += 1
        if attempts["count"] == 1:
            return _MockResponse(status_code=500, payload={"error": "temporary"}, text="temporary")
        return _MockResponse(payload={"ok": True})

    monkeypatch.setattr("tp_cli.core.api.requests.request", fake_request)
    monkeypatch.setattr("tp_cli.core.api.time.sleep", lambda _: None)

    api = TrainingPeaksAPI(token="token", rate_limit_delay=0, max_retries=3)
    response = api.get("/status")

    assert response["ok"] is True
    assert attempts["count"] == 2


def test_api_raises_after_max_retries(monkeypatch) -> None:
    def fake_request(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise requests.ConnectionError("network down")

    monkeypatch.setattr("tp_cli.core.api.requests.request", fake_request)
    monkeypatch.setattr("tp_cli.core.api.time.sleep", lambda _: None)

    api = TrainingPeaksAPI(token="token", rate_limit_delay=0, max_retries=2)
    with pytest.raises(APIError, match="API request failed for GET /users/v3/user"):
        api.get("/users/v3/user")


def test_api_headers_include_bearer_and_content_type() -> None:
    api = TrainingPeaksAPI(token="abc123")
    assert api._headers == {
        "Authorization": "Bearer abc123",
        "Content-Type": "application/json",
    }


def test_api_empty_response_text_returns_empty_object(monkeypatch) -> None:
    monkeypatch.setattr(
        "tp_cli.core.api.requests.request",
        lambda *args, **kwargs: _MockResponse(payload={}, text=""),
    )
    api = TrainingPeaksAPI(token="token", rate_limit_delay=0)
    assert api.delete("/empty") == {}


def test_api_get_post_delete_delegate_to_request(monkeypatch) -> None:
    calls = []

    def fake_request(self, method, path, params=None, json_data=None):  # type: ignore[no-untyped-def]
        calls.append((method, path, params, json_data))
        return {"ok": True}

    monkeypatch.setattr(TrainingPeaksAPI, "_request", fake_request)

    api = TrainingPeaksAPI(token="token", rate_limit_delay=0)
    assert api.get("/g", params={"x": 1}) == {"ok": True}
    assert api.post("/p", {"a": 2}) == {"ok": True}
    assert api.delete("/d") == {"ok": True}
    assert calls == [
        ("GET", "/g", {"x": 1}, None),
        ("POST", "/p", None, {"a": 2}),
        ("DELETE", "/d", None, None),
    ]


def test_api_specialized_methods_use_expected_paths(monkeypatch) -> None:
    get_calls = []
    post_calls = []
    delete_calls = []

    def fake_get(self, path, params=None):  # type: ignore[no-untyped-def]
        get_calls.append((path, params))
        if path == "/users/v3/user":
            return {"user": {"userId": 42}}
        return {"ok": True}

    def fake_post(self, path, payload):  # type: ignore[no-untyped-def]
        post_calls.append((path, payload))
        return {"workoutId": 7}

    def fake_delete(self, path):  # type: ignore[no-untyped-def]
        delete_calls.append(path)
        return {"deleted": True}

    monkeypatch.setattr(TrainingPeaksAPI, "get", fake_get)
    monkeypatch.setattr(TrainingPeaksAPI, "post", fake_post)
    monkeypatch.setattr(TrainingPeaksAPI, "delete", fake_delete)

    api = TrainingPeaksAPI(token="token", rate_limit_delay=0)
    assert api.get_user()["user"]["userId"] == 42
    assert api.get_user_id() == "42"
    api.get_workouts("1", "2026-01-01", "2026-01-31")
    api.get_workout("1", "99")
    api.create_workout("1", {"title": "Run"})
    api.delete_workout("1", "99")
    api.get_athlete_settings("1")

    assert ("/fitness/v6/athletes/1/workouts/2026-01-01/2026-01-31", None) in get_calls
    assert ("/fitness/v1/athletes/1/workouts/99", None) in get_calls
    assert ("/fitness/v1/athletes/1/settings", None) in get_calls
    assert post_calls == [("/fitness/v6/athletes/1/workouts", {"title": "Run"})]
    assert delete_calls == ["/fitness/v6/athletes/1/workouts/99"]
