from src.backends import DpllBackend
from src.markets import (
    Repacking,
    coloring_to_repacking,
    cycles_up_to,
    encode_repacking,
    is_feasible_repacking,
    kidney_bids,
    solve_kidney,
    solve_repacking,
)


def test_repacking_encoding_has_constraints():
    repacking = Repacking(
        domains={"a": [0, 1], "b": [0, 1]},
        forbidden={("a", 0, "b", 0)},
    )
    cnf, variables = encode_repacking(repacking)
    assert variables
    assert cnf.clauses


def test_cycle_exchange_finds_simple_cycles():
    cycles = cycles_up_to(3, [(0, 1), (1, 0), (1, 2), (2, 1)], 3)
    assert cycles == [(0, 1), (1, 2)]


def test_repacking_feasibility_solver_and_coloring_reduction():
    repacking = coloring_to_repacking(2, [(0, 1)], 2)
    assert is_feasible_repacking(repacking, {0: 1, 1: 2})
    assert not is_feasible_repacking(repacking, {0: 1})
    assert not is_feasible_repacking(repacking, {0: 1, 1: 1})
    model = solve_repacking(repacking, DpllBackend())
    assert model is not None
    assert is_feasible_repacking(repacking, model)
    impossible = Repacking({"empty": []})
    assert solve_repacking(impossible, DpllBackend()) is None


def test_kidney_cycle_weights_and_optimal_exchange():
    arcs = [(0, 1), (1, 0), (1, 2), (2, 1)]
    bids, cycles = kidney_bids(
        3, arcs, 2, {(0, 1): 3, (1, 0): 2, (1, 2): 1, (2, 1): 1}
    )
    assert cycles == [(0, 1), (1, 2)]
    assert [bid.price for bid in bids] == [5, 2]
    result = solve_kidney(3, arcs, 2, DpllBackend())
    assert result.value == 2
    assert len(result.cycles) == 1
