"""Text helpers."""

from __future__ import annotations

import re


def slugify(value: str, max_len: int = 50) -> str:
    """Generate filesystem-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        slug = "untitled"
    return slug[:max_len]
