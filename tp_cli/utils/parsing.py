"""Parsing helpers for workout payload conversion."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import yaml

from tp_cli.core.constants import SPORT_ID_BY_NAME


def parse_length(value: str) -> Tuple[int, str]:
    """Parse time/distance string to (value, unit)."""
    raw = value.strip()
    if raw.endswith("km"):
        return int(float(raw[:-2]) * 1000), "meter"
    if raw.endswith("m"):
        return int(float(raw[:-1])), "meter"

    parts = raw.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1]), "second"
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]), "second"

    return int(raw), "second"


def parse_duration(value: str) -> int:
    """Parse duration string into seconds."""
    parsed, _ = parse_length(value)
    return parsed


def parse_target(value: Optional[str]) -> Optional[int]:
    """Parse target like '72% TP' into integer percent."""
    if not value:
        return None
    match = re.match(r"(\d+)", value)
    return int(match.group(1)) if match else None


def simple_to_tp_structure(
    steps: Sequence[Dict[str, Any]],
    intensity_metric: str = "percentOfThresholdPace",
) -> Dict[str, Any]:
    """Convert simple step DSL into TP structure payload."""
    blocks: List[Dict[str, Any]] = []
    warmup_steps: List[Dict[str, Any]] = []

    for step in steps:
        step_type = step["type"]

        if step_type == "warmup":
            dur_value, dur_unit = parse_length(step["duration"])
            warmup_steps.append(
                {
                    "name": step.get("name", ""),
                    "length": {"value": dur_value, "unit": dur_unit},
                    "targets": ([{"minValue": parse_target(step.get("target"))}] if step.get("target") else []),
                    "intensityClass": "warmUp" if not warmup_steps else "active",
                    "openDuration": False,
                }
            )
            continue

        if step_type == "interval":
            on_value, on_unit = parse_length(step["on"])
            off_value, off_unit = parse_length(step["off"])

            on_targets: List[Dict[str, Any]] = []
            on_target = step.get("on_target")
            if on_target:
                range_match = re.match(r"(\d+)-(\d+)", on_target)
                if range_match:
                    on_targets = [
                        {
                            "minValue": int(range_match.group(1)),
                            "maxValue": int(range_match.group(2)),
                        }
                    ]
                else:
                    parsed = parse_target(on_target)
                    if parsed is not None:
                        on_targets = [{"minValue": parsed}]

            if warmup_steps:
                blocks.append(
                    {
                        "type": "rampUp",
                        "length": {"value": 1, "unit": "repetition"},
                        "steps": warmup_steps,
                    }
                )
                warmup_steps = []

            blocks.append(
                {
                    "type": "repetition",
                    "length": {"value": step.get("reps", 1), "unit": "repetition"},
                    "steps": [
                        {
                            "name": step.get("on_name", step.get("name", "")),
                            "length": {"value": on_value, "unit": on_unit},
                            "targets": on_targets,
                            "intensityClass": "active",
                            "openDuration": False,
                        },
                        {
                            "name": step.get("off_name", "Easy"),
                            "length": {"value": off_value, "unit": off_unit},
                            "targets": ([{"minValue": parse_target(step.get("off_target"))}] if step.get("off_target") else []),
                            "intensityClass": "rest",
                            "openDuration": False,
                        },
                    ],
                }
            )
            continue

        if warmup_steps:
            blocks.append(
                {
                    "type": "rampUp",
                    "length": {"value": 1, "unit": "repetition"},
                    "steps": warmup_steps,
                }
            )
            warmup_steps = []

        if step_type == "cooldown":
            blocks.append(
                {
                    "type": "step",
                    "length": {"value": 1, "unit": "repetition"},
                    "steps": [
                        {
                            "name": step.get("name", "Cool Down"),
                            "length": {"value": parse_duration(step["duration"]), "unit": "second"},
                            "targets": ([{"minValue": parse_target(step.get("target"))}] if step.get("target") else []),
                            "intensityClass": "coolDown",
                            "openDuration": False,
                        }
                    ],
                }
            )
            continue

        if step_type == "steady":
            blocks.append(
                {
                    "type": "step",
                    "length": {"value": 1, "unit": "repetition"},
                    "steps": [
                        {
                            "name": step.get("name", ""),
                            "length": {"value": parse_duration(step["duration"]), "unit": "second"},
                            "targets": ([{"minValue": parse_target(step.get("target"))}] if step.get("target") else []),
                            "intensityClass": "active",
                            "openDuration": False,
                        }
                    ],
                }
            )

    if warmup_steps:
        blocks.append(
            {
                "type": "rampUp",
                "length": {"value": 1, "unit": "repetition"},
                "steps": warmup_steps,
            }
        )

    return {
        "primaryIntensityMetric": intensity_metric,
        "structure": blocks,
    }


def load_workout_input(file_path: Optional[Path], read_stdin: bool, stdin_text: str = "") -> List[Dict[str, Any]]:
    """Load workout object(s) from file or stdin text."""
    raw_data: Any
    if file_path:
        text = file_path.read_text()
        if file_path.suffix.lower() in {".yaml", ".yml"}:
            raw_data = yaml.safe_load(text)
        else:
            raw_data = json.loads(text)
    elif read_stdin:
        text = stdin_text.strip()
        if not text:
            return []
        try:
            raw_data = json.loads(text)
        except json.JSONDecodeError:
            raw_data = yaml.safe_load(text)
    else:
        return []

    if isinstance(raw_data, dict):
        return [raw_data]
    if isinstance(raw_data, list):
        return [item for item in raw_data if isinstance(item, dict)]
    return []


def build_basic_workout(
    date: str,
    sport: str,
    title: str,
    description: str = "",
) -> Dict[str, Any]:
    """Build simple workout payload from CLI flags."""
    if sport.lower() not in SPORT_ID_BY_NAME:
        raise ValueError(f"Unsupported sport: {sport}")
    return {
        "date": date,
        "sport": sport.lower(),
        "title": title,
        "description": description,
    }
