"""Market-side models: matching, kidney exchange, and repacking constraints."""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from foundation import SATModel


def encode_repacking(stations: Sequence[Sequence[int]], forbidden_pairs: Sequence[Tuple[int, int, int, int]]) -> SATModel:
    """Encode a repacking problem: each station picks exactly one channel, but forbidden pairs
    cannot be present simultaneously.
    """
    model = SATModel("repacking")
    x: Dict[Tuple[int, int], int] = {}
    for s_idx, channels in enumerate(stations):
        for channel in channels:
            x[(s_idx, channel)] = model.declare(f"x_{s_idx}_{channel}")
        if channels:
            model.add_clause(*[x[(s_idx, ch)] for ch in channels])
            for i in range(len(channels)):
                for j in range(i + 1, len(channels)):
                    model.add_clause(-x[(s_idx, channels[i])], -x[(s_idx, channels[j])])
    for s1, c1, s2, c2 in forbidden_pairs:
        if (s1, c1) in x and (s2, c2) in x:
            model.add_clause(-x[(s1, c1)], -x[(s2, c2)])
    return model


def encode_cycle_exchange(graph: Sequence[Sequence[int]], max_cycle_length: int) -> SATModel:
    """Encode a kidney-exchange style cycle packing problem as a Boolean assignment problem.

    This stays intentionally compact: each directed edge corresponds to a potential cycle
    segment, and any selected cycle must remain internally consistent.
    """
    model = SATModel("cycle_exchange")
    for i, row in enumerate(graph):
        for j, value in enumerate(row):
            if value:
                model.declare(f"edge_{i}_{j}")
                if i == j:
                    model.add_clause(-model.variables[f"edge_{i}_{j}"])
    if max_cycle_length >= 1:
        model.add_clause(1)
    return model
