"""Runtime state container for CLI context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from rich.console import Console


@dataclass
class CLIState:
    """CLI runtime options and loaded configuration."""

    json_output: bool
    plain_output: bool
    verbose: bool
    quiet: bool
    config_path: Path
    config: Dict[str, Any]
    console: Console
