"""Cortex stage names. Not a second store."""
from __future__ import annotations

from enum import Enum


class Stage(Enum):
    CAPTURED = "Captured"
    MATERIALIZED = "Materialized"
    STABILIZED = "Stabilized"
    DEPRECATED = "Deprecated"
