"""Welfare models and information constraints used in the economics section of the paper."""
from __future__ import annotations

from typing import Sequence


def welfare_gain(alpha: float, avg_gap: float) -> float:
    """Compute the relative welfare gain formula from the paper's simplified model."""
    if alpha * avg_gap >= 1.0:
        return float("inf")
    return (alpha * avg_gap) / (1.0 - alpha * avg_gap)


def aggregate_welfare(values: Sequence[Sequence[int]]) -> int:
    """Aggregate individual utility vectors into a total social welfare score."""
    if not values:
        return 0
    return sum(sum(v) for v in values)


def communication_need(num_goods: int) -> int:
    """Return the exponential lower bound in the communication example of the paper."""
    return 2 ** max(num_goods, 0)
