import json

import pytest

from src.auctions import (
    Bid,
    auction_subgraph_instance,
    compatibility_graph,
    conflicting_pairs,
    encode_wdp,
    independent_set_to_wdp,
    is_feasible,
    max_revenue_via_clique,
    revenue,
    revenue_at_least_via_subgraph,
    solve_wdp,
    twin_graph,
    vcg,
    wdp_problem,
)
from src.backends import DpllBackend


def test_wdp_encoding_has_variables_and_clauses():
    bids = [
        Bid(frozenset({0, 1}), 3),
        Bid(frozenset({1, 2}), 2),
        Bid(frozenset({2}), 1),
    ]
    formula = encode_wdp(bids, 3)
    assert formula.num_vars > 0
    assert formula.clauses


def test_solve_wdp_finds_highest_revenue_winners():
    bids = [
        Bid(frozenset({0, 1}), 3),
        Bid(frozenset({1, 2}), 2),
        Bid(frozenset({2}), 1),
    ]
    result = solve_wdp(bids, DpllBackend())
    assert result.revenue == 4
    assert result.winners == [0, 2]


def test_vcg_payments_are_non_negative():
    bids = [
        Bid(frozenset({0}), 1, agent=0),
        Bid(frozenset({1}), 1, agent=1),
        Bid(frozenset({0, 1}), 2, agent=2),
    ]
    result = vcg(bids, DpllBackend())
    assert result.welfare >= 0
    assert all(payment >= 0 for payment in result.payments.values())


def test_bid_validation_conflicts_revenue_and_reduction_graphs():
    with pytest.raises(ValueError, match="nichtnegativ"):
        Bid(frozenset(), -1)
    bids = [
        Bid(frozenset({0}), 2, agent=4),
        Bid(frozenset({1}), 3, agent=4),
        Bid(frozenset({0, 2}), 1, agent=5),
    ]
    assert conflicting_pairs(bids) == [(0, 2)]
    assert conflicting_pairs(bids, xor_agents=True) == [(0, 1), (0, 2)]
    assert is_feasible(bids, [0, 1])
    assert not is_feasible(bids, [0, 2])
    assert revenue(bids, [0, 1]) == 5

    graph = compatibility_graph(bids)
    assert graph.has_edge(0, 1)
    twin, owners = twin_graph(bids)
    assert owners == [0, 0, 1, 1, 1, 2]
    assert twin.num_edges > 0
    assert max_revenue_via_clique(bids) == 5
    assert revenue_at_least_via_subgraph(
        [Bid(frozenset({i}), 1) for i in range(3)], 2
    )
    encoded = json.loads(auction_subgraph_instance(bids, 2))
    assert set(encoded) == {"G", "H"}


def test_wdp_bound_and_independent_set_encoding():
    bids = independent_set_to_wdp(3, [(0, 1), (1, 2)])
    assert len(bids) == 3
    problem, word = wdp_problem(bids)
    assert problem.objectives[0] == word
    assert solve_wdp(bids, DpllBackend()).revenue == 2
    assert not encode_wdp(bids, 4).clauses == []


def test_vcg_requires_agent_ids():
    with pytest.raises(ValueError, match="Agenten"):
        vcg([Bid(frozenset({0}), 1)], DpllBackend())
