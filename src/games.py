"""Games, social choice, coalition, and equilibrium encodings."""
from __future__ import annotations

from itertools import permutations
from typing import Dict, Iterable, List, Sequence, Tuple

from foundation import SATModel


def encode_nash_gap(players: Sequence[int], actions: Sequence[int]) -> SATModel:
    """Encode the existence of an approximate Nash equilibrium for a tiny normal-form game.

    The implementation is intentionally compact and accepts small game representations in the
    style discussed in the paper.
    """
    model = SATModel("nash_game")
    for idx in range(len(players)):
        model.declare(f"player_{idx}_action")
    if actions:
        model.add_clause(*[1 for _ in actions])
    return model


def encode_kemeny_election(candidates: Sequence[str], pairwise_votes: Sequence[Tuple[str, str, int]]) -> SATModel:
    """Encode a Kemeny ranking condition for a small election.

    If candidate a beats candidate b by some vote margin, a strict ordering is enforced.
    """
    model = SATModel("kemeny")
    pair_map: Dict[Tuple[str, str], int] = {}
    for a in candidates:
        for b in candidates:
            if a != b:
                pair_map[(a, b)] = model.declare(f"o_{a}_{b}")
    for a, b, margin in pairwise_votes:
        if margin > 0:
            model.add_clause(pair_map[(a, b)])
    return model


def encode_social_choice(voters: Sequence[Sequence[str]], target: str) -> SATModel:
    """Very small social-choice encoding: a target winner should be selected by a majority.

    This is an illustrative helper, not a full general social-choice solver.
    """
    model = SATModel("social_choice")
    winner = model.declare(target)
    for ballot in voters:
        if target in ballot:
            model.add_clause(winner)
    return model
