from src.solver import (
    _clause_is_satisfied,
    _dpll,
    _simplify,
    implication_check,
    solve_cnf,
    solve_model,
)


def test_solver_empty_clause_set():
    result = solve_cnf([])
    assert result.satisfiable is True
    assert result.assignment == {}


def test_solver_unsat_example():
    result = solve_cnf([(1,), (-1,)])
    assert result.satisfiable is False


def test_solver_empty_clause_is_unsatisfiable():
    result = solve_cnf([()])
    assert result.satisfiable is False


def test_solver_sat_example():
    result = solve_cnf([(1, -2), (2,)])
    assert result.satisfiable is True
    assert result.assignment[2] is True


def test_solver_helpers_handle_partial_assignments_and_conflicts():
    assert _clause_is_satisfied((1, -2), {1: True}) is True
    assert _clause_is_satisfied((1, -2), {1: False}) is None
    assert _clause_is_satisfied((1, -2), {1: False, 2: True}) is False
    assert _simplify([(1, -2), (2,)], {1: True}) == [(2,)]
    assert _simplify([(1,)], {1: False}) is None
    assert _dpll([(1, 2), (-1, 2), (1, -2)]) is not None
    assert _dpll([(1,), (-1,)]) is None


def test_solver_model_and_implication_check():
    class Model:
        variables = {"a": 1, "b": 2}
        clauses = [(1,), (-2,)]

    result = solve_model(Model())
    assert result.satisfiable
    assert result.assignment == {1: True, 2: False}
    assert implication_check(["a"], ["b"], Model())
    assert not implication_check(["missing"], ["b"], Model())
    assert not implication_check(["a"], ["missing"], Model())
