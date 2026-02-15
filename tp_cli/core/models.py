"""Lightweight data models used across commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class WorkoutClassification:
    """Classification metadata for a workout."""

    type: str
    method: str = "auto"
    confidence: float = 0.9
    reasoning: Optional[str] = None
