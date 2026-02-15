"""Configuration loading and persistence."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # Python 3.9-3.10
    import tomli as tomllib  # type: ignore[no-redef]


class ConfigError(RuntimeError):
    """Raised when config file parsing fails."""


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def expand_path(path_str: str) -> Path:
    """Expand user/env vars and return absolute path."""
    return Path(os.path.expandvars(path_str)).expanduser().resolve()


def default_data_dir() -> Path:
    """Resolve XDG-style data directory with env override."""
    raw = os.getenv("TP_DATA_DIR", "~/.local/share/tp")
    return expand_path(raw)


def default_config_path() -> Path:
    """Get default config file path."""
    raw = os.getenv("TP_CONFIG_FILE", "~/.config/tp/config.toml")
    return expand_path(raw)


def legacy_config_path() -> Path:
    """Get legacy JSON config file location."""
    return expand_path("~/.tp-cli/config.json")


def _default_config() -> Dict[str, Any]:
    data_dir = default_data_dir()
    return {
        "auth": {
            "username": None,
            "cookie_store": str(data_dir / "cookies.json"),
            "use_1password": False,
            "op_vault": "",
            "op_cookie_document": "",
            "op_username_ref": "",
            "op_password_ref": "",
        },
        "defaults": {
            "output_format": "pretty",
            "date_range": "last-30-days",
            "sports": ["swim", "bike", "run"],
        },
        "classification": {
            "method": "auto",
            "rules": {},
            "ai": {
                "enabled": False,
                "model": "gpt-4",
                "api_key_env": "OPENAI_API_KEY",
            },
        },
        "cache": {
            "enabled": True,
            "directory": str(data_dir / "cache"),
            "raw_responses": False,
        },
        "export": {
            "default_directory": "./workouts",
            "include_index": True,
            "markdown_frontmatter": True,
        },
        "zones": {
            "easy_max": 75,
            "lt1_max": 93,
            "lt2_max": 100,
        },
        "api": {
            "rate_limit_delay": 1.0,
            "max_retries": 3,
            "timeout_seconds": 30,
        },
    }


DEFAULT_CONFIG: Dict[str, Any] = _default_config()


def _read_config(path: Path) -> Dict[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text()
    try:
        if suffix in {".toml", ""}:
            loaded = tomllib.loads(text)
        else:
            loaded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in config file {path}: {exc}") from exc
    except Exception as exc:
        if suffix in {".toml", ""}:
            raise ConfigError(f"Invalid TOML in config file {path}: {exc}") from exc
        raise ConfigError(f"Failed to parse config file {path}: {exc}") from exc

    if not isinstance(loaded, dict):
        raise ConfigError(f"Config file {path} must contain an object/table at the root")
    return loaded


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load configuration from disk, merged with defaults."""
    cfg_path = path or default_config_path()
    cfg = _default_config()

    source: Optional[Path] = None
    if cfg_path.exists():
        source = cfg_path
    elif path is None:
        legacy = legacy_config_path()
        if legacy.exists():
            source = legacy

    if source:
        loaded = _read_config(source)
        cfg = _deep_merge(cfg, loaded)

    return cfg


def _toml_literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        items = ", ".join(_toml_literal(item) for item in value if item is not None)
        return f"[{items}]"
    raise TypeError(f"Unsupported TOML value type: {type(value)!r}")


def _dict_to_toml(data: Dict[str, Any], prefix: Optional[str] = None) -> str:
    lines = []
    plain_keys = []
    nested_keys = []

    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, dict):
            nested_keys.append((key, value))
        else:
            plain_keys.append((key, value))

    if prefix is not None:
        lines.append(f"[{prefix}]")

    for key, value in plain_keys:
        lines.append(f"{key} = {_toml_literal(value)}")

    if plain_keys and nested_keys:
        lines.append("")

    for index, (key, value) in enumerate(nested_keys):
        table_name = key if prefix is None else f"{prefix}.{key}"
        lines.append(_dict_to_toml(value, prefix=table_name))
        if index != len(nested_keys) - 1:
            lines.append("")

    return "\n".join(lines)


def save_config(config: Dict[str, Any], path: Optional[Path] = None) -> Path:
    """Save configuration to disk as TOML (default) or JSON."""
    cfg_path = path or default_config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)

    if cfg_path.suffix.lower() == ".json":
        cfg_path.write_text(json.dumps(config, indent=2) + "\n")
        return cfg_path

    cfg_path.write_text(_dict_to_toml(config).strip() + "\n")
    return cfg_path


def resolve_cookie_store(config: Dict[str, Any]) -> Path:
    """Resolve cookie file path from env/config."""
    raw = os.getenv("TP_COOKIE_STORE") or config.get("auth", {}).get("cookie_store")
    if not raw:
        raw = str(default_data_dir() / "cookies.json")
    return expand_path(raw)


def resolve_output_dir(config: Dict[str, Any], explicit: Optional[Path] = None) -> Path:
    """Resolve output directory with CLI override first."""
    if explicit is not None:
        return explicit.expanduser().resolve()
    raw = os.getenv("TP_OUTPUT_DIR") or config.get("export", {}).get(
        "default_directory",
        "./workouts",
    )
    return expand_path(raw)
