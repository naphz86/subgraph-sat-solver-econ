from solver import solve_cnf


def test_solver_empty_clause_set():
    result = solve_cnf([])
    assert result.satisfiable is True
    assert result.assignment == {}


def test_solver_unsat_example():
    result = solve_cnf([(1,), (-1,)])
    assert result.satisfiable is False


def test_solver_sat_example():
    result = solve_cnf([(1, -2), (2,)])
    assert result.satisfiable is True
    assert result.assignment[2] is True
