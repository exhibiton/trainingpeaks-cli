"""Workout classification utilities."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from tp_cli.core.constants import DEFAULT_ZONE_THRESHOLDS, TYPE_RULES
from tp_cli.core.models import WorkoutClassification

_PRIORITY_KEYWORD_TYPES = {"race", "test", "strength", "long", "sprint"}
_EASY_CLASSES = {"warmup", "cooldown", "rest", "recovery"}


def _normalized_text(workout: Dict[str, Any]) -> str:
    return " ".join(
        [
            str(workout.get("title") or ""),
            str(workout.get("description") or ""),
            str(workout.get("coachComments") or ""),
            str(workout.get("userTags") or ""),
        ]
    ).lower()


def _classify_by_keywords(
    workout: Dict[str, Any],
    rules: Sequence[Tuple[str, Sequence[str]]],
) -> str:
    text = _normalized_text(workout)
    for workout_type, keywords in rules:
        if any(keyword in text for keyword in keywords):
            return workout_type
    return "other"


def _parse_structure_value(raw: Any) -> Optional[Any]:
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return None
    return raw


def _normalize_blocks(raw_blocks: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_blocks, list):
        return []

    dict_blocks = [block for block in raw_blocks if isinstance(block, dict)]
    if not dict_blocks:
        return []

    # `structuredSteps` payloads can be a direct list of step objects.
    if all("steps" not in block for block in dict_blocks):
        return [
            {
                "type": "step",
                "length": {"value": 1, "unit": "repetition"},
                "steps": dict_blocks,
            }
        ]
    return dict_blocks


def _extract_structure(workout: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    metric = str(workout.get("primaryIntensityMetric") or "")

    # Prefer explicit structured step payload when present.
    for key in ("structuredSteps", "structuredWorkout", "structure"):
        parsed = _parse_structure_value(workout.get(key))
        if parsed is None:
            continue

        if isinstance(parsed, dict):
            metric = str(parsed.get("primaryIntensityMetric") or metric)
            blocks = parsed.get("structure") or parsed.get("steps")
            normalized = _normalize_blocks(blocks)
            if normalized:
                return normalized, metric
            continue

        normalized = _normalize_blocks(parsed)
        if normalized:
            return normalized, metric

    return [], metric


def _as_percent(value: Any) -> float:
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return 0.0
    if pct <= 0:
        return 0.0
    return pct * 100.0 if pct <= 2.0 else pct


def _step_intensity_pct(step: Dict[str, Any]) -> float:
    targets = step.get("targets")
    if not isinstance(targets, list) or not targets:
        return 0.0

    target = targets[0]
    if not isinstance(target, dict):
        return 0.0

    min_pct = _as_percent(target.get("minValue"))
    max_pct = _as_percent(target.get("maxValue"))
    if min_pct > 0 and max_pct > 0:
        return (min_pct + max_pct) / 2.0
    if min_pct > 0:
        return min_pct
    if max_pct > 0:
        return max_pct
    return _as_percent(target.get("value"))


def _length_to_seconds(length: Dict[str, Any]) -> float:
    unit = str(length.get("unit") or "").lower()
    try:
        value = float(length.get("value") or 0)
    except (TypeError, ValueError):
        return 0.0
    if value <= 0:
        return 0.0

    if unit == "second":
        return value
    if unit == "minute":
        return value * 60.0
    if unit == "hour":
        return value * 3600.0
    if unit == "meter":
        return value / 4.0
    if unit == "kilometer":
        return value * 250.0
    return 0.0


def classify_zone(
    pct: float,
    block_type: str,
    intensity_class: str,
    thresholds: Dict[str, float] = DEFAULT_ZONE_THRESHOLDS,
) -> str:
    """Classify an interval into easy/lt1/lt2/vo2 using configured thresholds."""
    block_type_norm = block_type.strip().lower()
    if block_type_norm == "rampup":
        return "easy"

    if intensity_class.strip().lower() in _EASY_CLASSES:
        return "easy"

    if pct <= thresholds["easy_max"]:
        return "easy"
    if pct <= thresholds["lt1_max"]:
        return "lt1"
    if pct <= thresholds["lt2_max"]:
        return "lt2"
    return "vo2"


def _classify_from_structure(workout: Dict[str, Any]) -> Optional[str]:
    blocks, _ = _extract_structure(workout)
    if not blocks:
        return None

    zone_loads: Dict[str, float] = {"easy": 0.0, "lt1": 0.0, "lt2": 0.0, "vo2": 0.0}
    zone_counts: Dict[str, int] = {"easy": 0, "lt1": 0, "lt2": 0, "vo2": 0}
    has_intensity_targets = False
    max_pct = 0.0

    for block in blocks:
        block_type = str(block.get("type") or "step")
        rep_count = 1
        if block_type.strip().lower() == "repetition":
            try:
                rep_count = int(float(block.get("length", {}).get("value") or 1))
            except (TypeError, ValueError):
                rep_count = 1

        steps_raw = block.get("steps")
        if isinstance(steps_raw, list):
            steps = [step for step in steps_raw if isinstance(step, dict)]
        else:
            steps = []

        for step in steps:
            pct = _step_intensity_pct(step)
            if pct > 0:
                has_intensity_targets = True
                max_pct = max(max_pct, pct)

            zone = classify_zone(
                pct=pct,
                block_type=block_type,
                intensity_class=str(step.get("intensityClass") or "active"),
            )
            load = _length_to_seconds(step.get("length", {})) * max(rep_count, 1)
            if load <= 0 and pct > 0:
                load = 30.0

            zone_loads[zone] += load
            if pct > 0:
                zone_counts[zone] += 1

    if not has_intensity_targets:
        return None

    vo2_load = zone_loads["vo2"]
    hard_load = zone_loads["lt2"] + vo2_load
    lt1_load = zone_loads["lt1"]

    if vo2_load >= 180 or (zone_counts["vo2"] >= 2 and max_pct > 105):
        return "vo2"
    if hard_load >= 180 or (zone_counts["lt2"] + zone_counts["vo2"]) >= 2:
        return "lt2"
    if lt1_load >= 300 or zone_counts["lt1"] >= 2:
        return "lt1"
    return "easy"


def _classify_with_source(
    workout: Dict[str, Any],
    rules: Sequence[Tuple[str, Sequence[str]]],
) -> Tuple[str, str]:
    keyword_label = _classify_by_keywords(workout, rules)
    if keyword_label in _PRIORITY_KEYWORD_TYPES:
        return keyword_label, "keyword"

    structure_label = _classify_from_structure(workout)
    if structure_label:
        return structure_label, "structure"

    return keyword_label, "keyword"


def classify_workout(
    workout: Dict[str, Any],
    rules: Sequence[Tuple[str, Sequence[str]]] = TYPE_RULES,
) -> str:
    """Classify workout with structure-first intensity logic + keyword fallback."""
    label, _ = _classify_with_source(workout, rules)
    return label


def classify_with_metadata(
    workout: Dict[str, Any],
    method: str = "auto",
    rules: Sequence[Tuple[str, Sequence[str]]] = TYPE_RULES,
) -> WorkoutClassification:
    """Return classification with method and confidence metadata."""
    label, source = _classify_with_source(workout, rules)

    if method == "ai":
        # AI classification is intentionally not invoked automatically yet.
        return WorkoutClassification(
            type=label,
            method="auto",
            confidence=0.6,
            reasoning="AI classification not configured; fell back to rules",
        )

    confidence = 0.97 if source == "structure" else 0.95 if label != "other" else 0.6
    reasoning = (
        "classified from structured workout intensity targets"
        if source == "structure"
        else None
    )
    return WorkoutClassification(
        type=label,
        method="auto",
        confidence=confidence,
        reasoning=reasoning,
    )


def classification_rules_from_config(config: Dict[str, Any]) -> List[Tuple[str, List[str]]]:
    """Build rules from config if provided, otherwise defaults."""
    configured = config.get("classification", {}).get("rules", {})
    if not isinstance(configured, dict) or not configured:
        return [(k, list(v)) for k, v in TYPE_RULES]

    rules: List[Tuple[str, List[str]]] = []
    for key, value in configured.items():
        if isinstance(value, Iterable):
            rules.append((str(key), [str(item).lower() for item in value]))
    return rules or [(k, list(v)) for k, v in TYPE_RULES]
