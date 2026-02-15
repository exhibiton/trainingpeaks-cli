"""Formatting helpers used by exports and console output."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from tp_cli.core.constants import INTENSITY_CLASS_LABELS, INTENSITY_METRIC_LABELS


def format_duration(hours: Optional[float]) -> str:
    """Format duration from hours to H:MM:SS or M:SS."""
    if not hours:
        return "N/A"
    total_seconds = int(float(hours) * 3600)
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_distance(meters: Optional[float]) -> str:
    """Format meters as kilometers."""
    if not meters:
        return "N/A"
    return f"{float(meters) / 1000:.1f} km"


def format_length_human(length: Optional[Dict[str, Any]]) -> str:
    """Format step length payload into readable text."""
    if not length:
        return ""

    value = length.get("value", "")
    unit = length.get("unit", "")

    if unit == "second":
        seconds = int(value)
        if seconds >= 3600:
            h, rem = divmod(seconds, 3600)
            m, s = divmod(rem, 60)
            return f"{h}h{m:02d}m" if s == 0 else f"{h}:{m:02d}:{s:02d}"
        if seconds >= 60:
            m, s = divmod(seconds, 60)
            return f"{m}min" if s == 0 else f"{m}min {s}sec"
        return f"{seconds}sec"

    if unit == "minute":
        return f"{value}min"
    if unit == "meter":
        meters = int(value)
        return f"{meters / 1000:.1f}km" if meters >= 1000 else f"{meters}m"
    if unit == "kilometer":
        return f"{value}km"
    if unit == "repetition":
        return f"{value}x" if int(value) > 1 else ""

    return f"{value} {unit}".strip()


def format_target_human(target: Dict[str, Any], metric_label: str) -> str:
    """Format target range for a workout step."""
    unit = target.get("unit", "")
    min_value = target.get("minValue")
    max_value = target.get("maxValue")

    if min_value is None and max_value is None:
        return ""

    if min_value is not None and max_value is not None:
        range_text = str(min_value) if min_value == max_value else f"{min_value}-{max_value}"
    elif min_value is not None:
        range_text = f"{min_value}+"
    else:
        range_text = f"<{max_value}"

    label = INTENSITY_METRIC_LABELS.get(unit, "") or metric_label
    return f"{range_text}{label}" if label else range_text


def _format_single_step(step: Dict[str, Any], metric_label: str) -> str:
    """Format one workout step line."""
    name = step.get("name", "")
    length = format_length_human(step.get("length"))
    intensity = step.get("intensityClass", "")
    targets = [format_target_human(t, metric_label) for t in step.get("targets", [])]
    targets = [target for target in targets if target]

    parts: List[str] = []
    if length:
        parts.append(length)

    at_parts: List[str] = []
    if name:
        at_parts.append(name)
    if targets:
        at_parts.append(f"({', '.join(targets)})")
    if at_parts:
        parts.append("@ " + " ".join(at_parts))

    intensity_label = INTENSITY_CLASS_LABELS.get(intensity, "")
    if intensity_label and intensity not in ("active",):
        parts.append(f"[{intensity_label}]")

    return " ".join(parts) if parts else "(step)"


def format_steps(steps: Optional[List[Dict[str, Any]]], primary_metric: str = "", indent: int = 0) -> str:
    """Format structured workout steps into readable markdown-style lines."""
    if not steps:
        return "No structured workout data"

    metric_label = INTENSITY_METRIC_LABELS.get(primary_metric, "")
    prefix = "    " * indent
    lines: List[str] = []

    for idx, block in enumerate(steps, 1):
        block_type = block.get("type", "step")
        block_len = block.get("length", {})
        child_steps = block.get("steps", [])
        reps = block_len.get("value", 1) if block_len.get("unit") == "repetition" else None

        if block_type == "repetition" and reps and reps > 1 and child_steps:
            parts = [_format_single_step(step, metric_label) for step in child_steps]
            lines.append(f"{prefix}{idx}. **{reps}x** [{' / '.join(parts)}]")
            continue

        if block_type == "rampUp" and child_steps:
            lines.append(f"{prefix}{idx}. **Warm-up ramp:**")
            for step in child_steps:
                lines.append(f"{prefix}   - {_format_single_step(step, metric_label)}")
            continue

        if child_steps:
            for step in child_steps:
                label = INTENSITY_CLASS_LABELS.get(step.get("intensityClass", ""), "")
                desc = _format_single_step(step, metric_label)
                if label:
                    lines.append(f"{prefix}{idx}. **{label}:** {desc}")
                else:
                    lines.append(f"{prefix}{idx}. {desc}")
        else:
            label = INTENSITY_CLASS_LABELS.get(block.get("intensityClass", ""), "")
            desc = _format_single_step(block, metric_label)
            if label:
                lines.append(f"{prefix}{idx}. **{label}:** {desc}")
            else:
                lines.append(f"{prefix}{idx}. {desc}")

    return "\n".join(lines)
