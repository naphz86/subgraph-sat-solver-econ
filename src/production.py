"""Production, scheduling, and configuration constraints encoded as SAT formulas."""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from foundation import SATModel


def encode_job_schedule(jobs: Sequence[Tuple[int, int, int]], horizon: int) -> SATModel:
    """Encode a simple single-machine scheduling instance with release times and deadlines.

    Each job j gets a start time s_j in [r_j, d_j-p_j]. Variables z_{j,t} indicate that job j
    starts at time t. The formula requires one start time per job and no overlap.
    """
    model = SATModel("job_schedule")
    z: Dict[Tuple[int, int], int] = {}
    for j, (release, deadline, duration) in enumerate(jobs):
        for t in range(release, deadline - duration + 1):
            z[(j, t)] = model.declare(f"z_{j}_{t}")
        if not z:
            continue
        model.add_clause(*[z[(j, t)] for t in range(release, deadline - duration + 1)])
        for t1 in range(release, deadline - duration + 1):
            for t2 in range(t1 + 1, deadline - duration + 1):
                if abs(t2 - t1) < duration:
                    model.add_clause(-z[(j, t1)], -z[(j, t2)])
    return model


def encode_product_configuration(options: Sequence[str], incompatibilities: Sequence[Tuple[str, str]]) -> SATModel:
    """Encode option compatibility checks for product configuration.

    The model marks impossible options and checks which options remain feasible.
    """
    model = SATModel("product_configuration")
    var_map = {option: model.declare(option) for option in options}
    for a, b in incompatibilities:
        if a in var_map and b in var_map:
            model.add_clause(-var_map[a], -var_map[b])
    return model
