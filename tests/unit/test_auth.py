from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any, Dict, List

import pytest

from tp_cli.core.auth import API_BASE, AuthError, TrainingPeaksAuth


def _auth_config(use_1password: bool = True) -> Dict[str, Any]:
    return {
        "auth": {
            "use_1password": use_1password,
            "op_vault": "Vault",
            "op_cookie_document": "tp-cookies",
            "op_username_ref": "op://vault/item/username",
            "op_password_ref": "op://vault/item/password",
        }
    }


class DummyRunResult:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class DummyGetResponse:
    def __init__(self, status_code: int, payload: Dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("http")


def test_op_read_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=tmp_path / "cookies.json")
    monkeypatch.setattr(
        "tp_cli.core.auth.subprocess.run",
        lambda *_, **__: DummyRunResult(returncode=0, stdout="value\n"),
    )
    assert auth._op_read("op://x/y") == "value"


def test_op_read_failure_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=tmp_path / "cookies.json")
    monkeypatch.setattr(
        "tp_cli.core.auth.subprocess.run",
        lambda *_, **__: DummyRunResult(returncode=1, stderr="not found"),
    )
    with pytest.raises(AuthError):
        auth._op_read("op://missing")


def test_load_op_cookies_disabled(tmp_path: Path) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(use_1password=False), cookie_file=tmp_path / "c.json")
    assert auth._load_op_cookies() is None


def test_load_op_cookies_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=tmp_path / "c.json")
    cookies = [{"name": "sid", "value": "abc"}]
    monkeypatch.setattr(
        "tp_cli.core.auth.subprocess.run",
        lambda *_, **__: DummyRunResult(returncode=0, stdout=json.dumps(cookies)),
    )
    assert auth._load_op_cookies() == cookies


def test_load_op_cookies_invalid_json_returns_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=tmp_path / "c.json")
    monkeypatch.setattr(
        "tp_cli.core.auth.subprocess.run",
        lambda *_, **__: DummyRunResult(returncode=0, stdout="not json"),
    )
    assert auth._load_op_cookies() is None


def test_save_op_cookies_disabled_does_not_call_subprocess(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(use_1password=False), cookie_file=tmp_path / "c.json")
    called = {"value": False}

    def fake_run(*_: Any, **__: Any) -> DummyRunResult:
        called["value"] = True
        return DummyRunResult(returncode=0)

    monkeypatch.setattr("tp_cli.core.auth.subprocess.run", fake_run)
    auth._save_op_cookies([{"name": "sid", "value": "x"}])
    assert called["value"] is False


def test_cookies_to_jar_handles_alternate_keys(tmp_path: Path) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=tmp_path / "c.json")
    jar = auth._cookies_to_jar(
        [{"name": "a", "value": "1"}, {"Name": "b", "Value": "2"}, {"bad": "row"}]
    )
    assert jar == {"a": "1", "b": "2"}


def test_try_token_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=tmp_path / "c.json")
    monkeypatch.setattr(
        "tp_cli.core.auth.requests.get",
        lambda url, cookies, timeout: DummyGetResponse(
            200,
            {"success": True, "token": {"access_token": "tok-1"}},
        ),
    )
    assert auth._try_token({"sid": "x"}) == "tok-1"


def test_try_token_non_200_returns_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=tmp_path / "c.json")
    monkeypatch.setattr(
        "tp_cli.core.auth.requests.get",
        lambda url, cookies, timeout: DummyGetResponse(401, {}),
    )
    assert auth._try_token({"sid": "x"}) is None


def test_load_local_cookies_missing_returns_none(tmp_path: Path) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=tmp_path / "missing.json")
    assert auth._load_local_cookies() is None


def test_load_local_cookies_reads_list(tmp_path: Path) -> None:
    cookie_file = tmp_path / "cookies.json"
    cookie_file.write_text(json.dumps([{"name": "sid", "value": "123"}]))
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=cookie_file)
    assert auth._load_local_cookies() == [{"name": "sid", "value": "123"}]


def test_save_local_cookies_writes_json(tmp_path: Path) -> None:
    cookie_file = tmp_path / "cookies" / "cookies.json"
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=cookie_file)
    auth._save_local_cookies([{"name": "sid", "value": "123"}])
    parsed = json.loads(cookie_file.read_text())
    assert parsed[0]["name"] == "sid"


def test_resolve_credentials_from_explicit_values(tmp_path: Path) -> None:
    auth = TrainingPeaksAuth(
        config=_auth_config(),
        username="u1",
        password="p1",
        cookie_file=tmp_path / "cookies.json",
    )
    assert auth._resolve_credentials() == ("u1", "p1")


def test_resolve_credentials_from_1password(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=tmp_path / "cookies.json")
    monkeypatch.setattr(
        auth,
        "_op_read",
        lambda ref: "u1" if ref.endswith("username") else "p1",
    )
    assert auth._resolve_credentials() == ("u1", "p1")


def test_resolve_credentials_missing_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=tmp_path / "cookies.json")
    monkeypatch.setattr(auth, "_op_read", lambda _: (_ for _ in ()).throw(AuthError("missing")))
    with pytest.raises(AuthError):
        auth._resolve_credentials()


def test_login_uses_op_cookies_first(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=tmp_path / "cookies.json")
    cookies = [{"name": "sid", "value": "abc"}]
    saved: List[List[Dict[str, Any]]] = []

    monkeypatch.setattr(auth, "_load_op_cookies", lambda: cookies)
    monkeypatch.setattr(auth, "_load_local_cookies", lambda: None)
    monkeypatch.setattr(auth, "_try_token", lambda jar: "token-1")
    monkeypatch.setattr(auth, "_save_local_cookies", lambda items: saved.append(items))
    monkeypatch.setattr(auth, "login_playwright", lambda: (_ for _ in ()).throw(RuntimeError("no")))

    token, jar = auth.login()
    assert token == "token-1"
    assert jar == {"sid": "abc"}
    assert saved == [cookies]


def test_login_uses_cached_local_cookies(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=tmp_path / "cookies.json")
    cookies = [{"name": "sid", "value": "abc"}]

    monkeypatch.setattr(auth, "_load_op_cookies", lambda: None)
    monkeypatch.setattr(auth, "_load_local_cookies", lambda: cookies)
    monkeypatch.setattr(auth, "_try_token", lambda jar: "token-2")
    token, jar = auth.login()

    assert token == "token-2"
    assert jar == {"sid": "abc"}


def test_login_force_uses_playwright(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=tmp_path / "cookies.json")
    cookies = [{"name": "sid", "value": "fresh"}]
    saved_op: List[List[Dict[str, Any]]] = []

    monkeypatch.setattr(auth, "login_playwright", lambda: cookies)
    monkeypatch.setattr(auth, "_try_token", lambda jar: "token-3")
    monkeypatch.setattr(auth, "_save_op_cookies", lambda items: saved_op.append(items))
    token, jar = auth.login(force=True)

    assert token == "token-3"
    assert jar == {"sid": "fresh"}
    assert saved_op == [cookies]


def test_login_raises_when_exchange_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=tmp_path / "cookies.json")
    monkeypatch.setattr(auth, "_load_op_cookies", lambda: None)
    monkeypatch.setattr(auth, "_load_local_cookies", lambda: None)
    monkeypatch.setattr(auth, "login_playwright", lambda: [{"name": "sid", "value": "fresh"}])
    monkeypatch.setattr(auth, "_try_token", lambda jar: None)
    with pytest.raises(AuthError):
        auth.login()


def test_logout_removes_cookie_file(tmp_path: Path) -> None:
    cookie_file = tmp_path / "cookies.json"
    cookie_file.write_text("[]")
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=cookie_file)
    assert auth.logout() is True
    assert not cookie_file.exists()


def test_logout_when_no_cookie_file(tmp_path: Path) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=tmp_path / "none.json")
    assert auth.logout() is False


def test_get_user_info(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=tmp_path / "cookies.json")
    seen: Dict[str, Any] = {}

    def fake_get(url: str, headers: Dict[str, str], timeout: int) -> DummyGetResponse:
        seen["url"] = url
        seen["auth"] = headers["Authorization"]
        return DummyGetResponse(200, {"user": {"userId": 7}})

    monkeypatch.setattr("tp_cli.core.auth.requests.get", fake_get)
    payload = auth.get_user_info("token-7")
    assert payload["user"]["userId"] == 7
    assert seen["url"] == f"{API_BASE}/users/v3/user"
    assert seen["auth"] == "Bearer token-7"


def test_login_playwright_flow_mocked(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=tmp_path / "cookies.json")
    monkeypatch.setattr(auth, "_resolve_credentials", lambda: ("user", "pass"))

    class FakeNav:
        def __enter__(self) -> None:
            return None

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

    class FakePage:
        def goto(self, *args: Any, **kwargs: Any) -> None:
            return None

        def fill(self, *args: Any, **kwargs: Any) -> None:
            return None

        def press(self, *args: Any, **kwargs: Any) -> None:
            return None

        def expect_navigation(self, *args: Any, **kwargs: Any) -> FakeNav:
            return FakeNav()

    class FakeContext:
        def new_page(self) -> FakePage:
            return FakePage()

        def cookies(self) -> List[Dict[str, Any]]:
            return [{"name": "sid", "value": "cookie"}]

    class FakeBrowser:
        def new_context(self, **kwargs: Any) -> FakeContext:
            return FakeContext()

        def close(self) -> None:
            return None

    class FakeChromium:
        def launch(self, **kwargs: Any) -> FakeBrowser:
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakePlaywrightContext:
        def __enter__(self) -> FakePlaywright:
            return FakePlaywright()

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

    module = types.SimpleNamespace(sync_playwright=lambda: FakePlaywrightContext())
    monkeypatch.setitem(sys.modules, "playwright.sync_api", module)
    monkeypatch.setattr("tp_cli.core.auth.time.sleep", lambda _: None)

    cookies = auth.login_playwright()
    assert cookies == [{"name": "sid", "value": "cookie"}]
    assert json.loads(auth.cookie_file.read_text())[0]["name"] == "sid"


def test_login_playwright_raises_when_no_cookies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    auth = TrainingPeaksAuth(config=_auth_config(), cookie_file=tmp_path / "cookies.json")
    monkeypatch.setattr(auth, "_resolve_credentials", lambda: ("user", "pass"))

    class FakeNav:
        def __enter__(self) -> None:
            return None

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

    class FakePage:
        def goto(self, *args: Any, **kwargs: Any) -> None:
            return None

        def fill(self, *args: Any, **kwargs: Any) -> None:
            return None

        def press(self, *args: Any, **kwargs: Any) -> None:
            return None

        def expect_navigation(self, *args: Any, **kwargs: Any) -> FakeNav:
            return FakeNav()

    class FakeContext:
        def new_page(self) -> FakePage:
            return FakePage()

        def cookies(self) -> List[Dict[str, Any]]:
            return []

    class FakeBrowser:
        def new_context(self, **kwargs: Any) -> FakeContext:
            return FakeContext()

        def close(self) -> None:
            return None

    class FakeChromium:
        def launch(self, **kwargs: Any) -> FakeBrowser:
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakePlaywrightContext:
        def __enter__(self) -> FakePlaywright:
            return FakePlaywright()

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

    module = types.SimpleNamespace(sync_playwright=lambda: FakePlaywrightContext())
    monkeypatch.setitem(sys.modules, "playwright.sync_api", module)
    monkeypatch.setattr("tp_cli.core.auth.time.sleep", lambda _: None)

    with pytest.raises(AuthError):
        auth.login_playwright()
