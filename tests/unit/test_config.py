from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from tp_cli.core.config import (
    ConfigError,
    _deep_merge,
    default_config_path,
    default_data_dir,
    expand_path,
    load_config,
    resolve_cookie_store,
    resolve_output_dir,
    save_config,
)


def test_deep_merge_nested_dicts() -> None:
    base = {"a": {"b": 1, "c": 2}, "x": 3}
    override = {"a": {"b": 9}, "y": 4}
    merged = _deep_merge(base, override)
    assert merged == {"a": {"b": 9, "c": 2}, "x": 3, "y": 4}
    assert base["a"]["b"] == 1


def test_expand_path_expands_home_and_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TP_TMP_PATH", str(tmp_path))
    expanded = expand_path("$TP_TMP_PATH/config.toml")
    assert expanded == (tmp_path / "config.toml").resolve()


def test_default_config_path_uses_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "custom.toml"
    monkeypatch.setenv("TP_CONFIG_FILE", str(path))
    assert default_config_path() == path.resolve()


def test_default_data_dir_uses_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "tp-data"
    monkeypatch.setenv("TP_DATA_DIR", str(path))
    assert default_data_dir() == path.resolve()


def test_load_config_missing_file_returns_defaults(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "missing.toml")
    assert cfg["api"]["max_retries"] == 3
    assert cfg["auth"]["cookie_store"].endswith("cookies.json")
    assert cfg["cache"]["directory"].endswith("cache")


def test_load_config_from_json(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api": {"max_retries": 9}, "defaults": {"date_range": "last-7-days"}}))
    cfg = load_config(path)
    assert cfg["api"]["max_retries"] == 9
    assert cfg["defaults"]["date_range"] == "last-7-days"


def test_load_config_from_toml(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        """
[api]
max_retries = 5

[defaults]
output_format = "json"
""".strip()
        + "\n"
    )
    cfg = load_config(path)
    assert cfg["api"]["max_retries"] == 5
    assert cfg["defaults"]["output_format"] == "json"


def test_load_config_invalid_json_raises(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{broken")
    with pytest.raises(ConfigError):
        load_config(path)


def test_load_config_invalid_toml_raises(tmp_path: Path) -> None:
    path = tmp_path / "broken.toml"
    path.write_text("[api\nmax_retries = 3")
    with pytest.raises(ConfigError):
        load_config(path)


def test_load_config_legacy_json_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    default_path = tmp_path / "missing.toml"
    legacy_path = tmp_path / "legacy.json"
    legacy_path.write_text(json.dumps({"api": {"timeout_seconds": 99}}))

    monkeypatch.setattr("tp_cli.core.config.default_config_path", lambda: default_path)
    monkeypatch.setattr("tp_cli.core.config.legacy_config_path", lambda: legacy_path)

    cfg = load_config()
    assert cfg["api"]["timeout_seconds"] == 99


def test_save_config_json(tmp_path: Path) -> None:
    payload: Dict[str, Any] = {"api": {"max_retries": 7}}
    path = save_config(payload, tmp_path / "config.json")
    assert path.exists()
    assert json.loads(path.read_text())["api"]["max_retries"] == 7


def test_save_config_toml_and_reload(tmp_path: Path) -> None:
    payload: Dict[str, Any] = {"api": {"max_retries": 7}, "defaults": {"sports": ["run", "bike"]}}
    path = save_config(payload, tmp_path / "config.toml")
    assert path.exists()
    cfg = load_config(path)
    assert cfg["api"]["max_retries"] == 7
    assert cfg["defaults"]["sports"] == ["run", "bike"]


def test_resolve_cookie_store_env_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cookie_path = tmp_path / "cookies.json"
    monkeypatch.setenv("TP_COOKIE_STORE", str(cookie_path))
    resolved = resolve_cookie_store({"auth": {"cookie_store": "/nope"}})
    assert resolved == cookie_path.resolve()


def test_resolve_cookie_store_default_uses_data_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("TP_COOKIE_STORE", raising=False)
    monkeypatch.setenv("TP_DATA_DIR", str(tmp_path / "xdg"))
    resolved = resolve_cookie_store({"auth": {}})
    assert resolved == (tmp_path / "xdg" / "cookies.json").resolve()


def test_resolve_output_dir_prefers_explicit(tmp_path: Path) -> None:
    explicit = tmp_path / "exports"
    cfg = {"export": {"default_directory": "/tmp/ignored"}}
    assert resolve_output_dir(cfg, explicit=explicit) == explicit.resolve()


def test_resolve_output_dir_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TP_OUTPUT_DIR", str(tmp_path / "from-env"))
    cfg = {"export": {"default_directory": "/tmp/ignored"}}
    assert resolve_output_dir(cfg) == (tmp_path / "from-env").resolve()
