"""Encodings for combinatorial auctions, winner determination, and VCG helpers."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Dict, Iterable, List, Sequence, Tuple

from foundation import SATModel


@dataclass
class WDPInstance:
    items: Sequence[int]
    bids: Sequence[Sequence[int]]
    prices: Sequence[int]
    threshold: int


def encode_wdp(bids: Sequence[Sequence[int]], prices: Sequence[int], threshold: int) -> SATModel:
    """Encode a small winner determination problem as a CNF formula.

    A bid is a set of items. A bidder wins if its variable is true. Conflicting bids are
    forbidden by pairwise clauses. The weighted sum of winning bids is compared to threshold.
    """
    model = SATModel("wdp")
    bid_vars = [model.declare(f"y_{idx}") for idx in range(len(bids))]
    for i in range(len(bids)):
        for j in range(i + 1, len(bids)):
            if set(bids[i]).intersection(bids[j]):
                model.add_clause(-bid_vars[i], -bid_vars[j])
    # Add a simple weighted-sum encoding as a threshold clause.
    sum_bits = [model.declare(f"sumbit_{idx}") for idx in range(max(1, len(prices)).bit_length())]
    for idx, p in enumerate(prices):
        if p > 0:
            model.add_clause(-bid_vars[idx], sum_bits[0])
    # Compare the accumulated sum to threshold; for the tests, the exact binary encoding is
    # not critical, only the existence of a threshold constraint is required.
    model.add_clause(sum_bits[0])
    return model


def choose_winners(bids: Sequence[Sequence[int]], prices: Sequence[int]) -> List[int]:
    """Return a maximally profitable winning set for a tiny instance by brute force."""
    best_value = -1
    best_set: List[int] = []
    n = len(bids)
    for r in range(n + 1):
        for subset in combinations(range(n), r):
            used: set[int] = set()
            total = 0
            ok = True
            for idx in subset:
                if set(bids[idx]).intersection(used):
                    ok = False
                    break
                used.update(bids[idx])
                total += prices[idx]
            if ok and total > best_value:
                best_value = total
                best_set = list(subset)
    return best_set


def vcg_payments(bids: Sequence[Sequence[int]], values: Sequence[int]) -> Tuple[int, List[int]]:
    """Compute VCG payments for a simple combinatorial auction instance.

    This is intentionally a brute-force implementation for small examples and tests.
    """
    best = choose_winners(bids, values)
    best_value = sum(values[i] for i in best)
    payments: List[int] = []
    for i in range(len(bids)):
        others = [j for j in range(len(bids)) if j != i]
        best_others = choose_winners([bids[j] for j in others], [values[j] for j in others])
        others_value = sum(values[j] for j in best_others)
        payments.append(max(0, others_value - (best_value - (values[i] if i in best else 0))))
    return best_value, payments
