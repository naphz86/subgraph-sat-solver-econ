"""Economic decision utilities, ranking, and welfare functions."""
from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Sequence, Set, Tuple


def utility_rank(preferences: Sequence[Sequence[int]]) -> Dict[int, int]:
    """Return a utility index from a complete preference ranking.

    If a >= b is interpreted as a preferred or tied to b, the rank is based on the count of
    alternatives that are at least as good.
    """
    result: Dict[int, int] = {}
    for idx, alt in enumerate(preferences):
        result[idx] = len([other for other in preferences if alt == other or alt >= other])
    return result


def lexicographic_optimize(values: Sequence[Sequence[int]]) -> List[int]:
    """Return a lexicographic maximum index from a set of value vectors."""
    if not values:
        return []
    best = list(values[0])
    best_idx = 0
    for idx, vector in enumerate(values[1:], start=1):
        if tuple(vector) > tuple(best):
            best = list(vector)
            best_idx = idx
    return [best_idx]


def pareto_front(values: Sequence[Sequence[int]]) -> List[Tuple[int, ...]]:
    """Compute a simple Pareto front for a finite set of value vectors."""
    front: List[Tuple[int, ...]] = []
    for vector in values:
        dominated = False
        for other in values:
            if other == vector:
                continue
            if all(o >= v for o, v in zip(other, vector)) and any(o > v for o, v in zip(other, vector)):
                dominated = True
                break
        if not dominated:
            front.append(tuple(vector))
    return front


def social_welfare(values: Sequence[Sequence[int]], aggregator: Callable[[Sequence[int]], int] = sum) -> int:
    """Aggregate individual values into a social welfare score."""
    return aggregator(values[0]) if len(values) == 1 else aggregator([sum(v) for v in zip(*values)])


def welfare_gain(alpha: float, avg_gap: float) -> float:
    """Compute the welfare gain used in the paper's simplified example formula."""
    return (alpha * avg_gap) / (1.0 - alpha * avg_gap)
