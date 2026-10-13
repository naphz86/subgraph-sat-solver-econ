from src.backends import DpllBackend
import pytest

from src.backends import BackendError, DecisionOnlyBackend
from src.cnf import Cnf
from src.foundation import (
    Problem,
    clique_graph_node_bound,
    decide_via_sat,
    find_model,
    find_witness,
    lower_bound_decision,
    maximize,
    minimize,
    new_problem,
    opt_call_bound,
    opt_formula_size_bound,
    s3_time_bound,
    selfreduce,
    three_cnf_size_bounds,
    tseitin_size_bound,
)


def test_problem_checks_constraints_and_objectives():
    problem = Problem(2)
    problem.cnf.add_clause(-problem.x[0], problem.x[1])
    problem.add_objective(problem.cb.weighted_sum(problem.x, [1, 2]))
    assert problem.check([False, False]) == (True, [0])
    assert problem.check([True, False]) == (False, [1])


def test_maximize_finds_best_feasible_decision():
    problem = Problem(2)
    problem.cnf.add_clause(-problem.x[0], -problem.x[1])
    objective = problem.cb.weighted_sum(problem.x, [1, 2])
    result = maximize(problem, objective, DpllBackend())
    assert result.feasible
    assert result.value == 2
    assert result.x == [False, True]


def test_problem_copy_bounds_minimization_and_infeasibility():
    problem = new_problem(2)
    word = problem.cb.weighted_sum(problem.x, [1, 2])
    problem.add_objective(word)
    copied = problem.copy()
    assert copied.x == problem.x
    assert lower_bound_decision(problem, word, 2, DpllBackend())
    assert minimize(problem, word, DpllBackend()).value == 0
    impossible = Problem(1)
    impossible.cnf.add_clause()
    assert not maximize(impossible, [False], DpllBackend()).feasible


def test_self_reduction_witness_search_and_sat_encoding():
    cnf = Cnf(2, [(1, 2)])
    decision_only = DecisionOnlyBackend(DpllBackend())
    assert selfreduce(cnf, decision_only) == {1: False, 2: True}
    assert decision_only.calls > 0
    assert find_model(cnf, DpllBackend()) is not None
    assert find_model(Cnf(1, [(1,), (-1,)]), DpllBackend()) is None
    assert find_witness(
        lambda prefix: "10".startswith(prefix),
        lambda candidate: candidate == "10",
        2,
    ) == "10"
    assert find_witness(lambda _prefix: False, lambda _candidate: False, 3) is None
    with pytest.raises(BackendError, match="inkonsistent"):
        find_witness(lambda _prefix: True, lambda _candidate: False, 0)
    assert decide_via_sat("sat", lambda _value: cnf, DpllBackend())


def test_size_and_call_bound_helpers():
    assert three_cnf_size_bounds(7) == (7, 21)
    assert clique_graph_node_bound(7) == 21
    assert s3_time_bound(2, 0.5) == 108
    assert tseitin_size_bound(3) == 36
    assert opt_call_bound(4, 5) == 11
    assert opt_formula_size_bound(4, 5) == 110
