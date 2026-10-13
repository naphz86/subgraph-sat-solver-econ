from src.backends import DpllBackend
from src.cnf import Cnf
import pytest

from src.production import (
    Configurator,
    Job,
    feasible_schedule,
    is_valid_schedule,
    optimal_schedule,
    schedule_problem,
    set_cover_to_ufl,
    solve_ufl,
    ufl_cost,
    ufl_problem,
)


def test_job_schedule_encoding_has_at_least_one_choice():
    jobs = [Job(0, 3, 2), Job(1, 4, 2)]
    problem, starts = schedule_problem(jobs)
    assert starts
    assert problem.cnf.clauses
    assert is_valid_schedule(jobs, {0: 0, 1: 2})
    assert not is_valid_schedule(jobs, {0: 0, 1: 1})
    assert not is_valid_schedule(jobs, {0: 0})
    model = feasible_schedule(jobs, DpllBackend())
    assert model is not None
    optimal = optimal_schedule(jobs, DpllBackend())
    assert optimal is not None
    assert is_valid_schedule(jobs, optimal.starts)


def test_job_validation_and_infeasible_windows():
    with pytest.raises(ValueError, match="Bearbeitungsdauer"):
        Job(0, 3, 0)
    with pytest.raises(ValueError, match="nichtnegativ"):
        Job(-1, 3, 1)
    with pytest.raises(ValueError, match="nichtnegativ"):
        Job(0, 3, 1, -1)
    impossible = [Job(0, 1, 2)]
    problem, _ = schedule_problem(impossible)
    assert problem.cnf.clauses == [()]
    assert feasible_schedule(impossible, DpllBackend()) is None
    assert optimal_schedule(impossible, DpllBackend()) is None


def test_product_configuration_encoding_has_conflict_clauses():
    formula = Cnf.from_dimacs("p cnf 3 1\n-1 -2 0\n")
    configurator = Configurator(formula)
    assert configurator.is_realizable([1], DpllBackend())
    assert not configurator.is_realizable([1, 2], DpllBackend())


def test_configurator_classification_and_minimum_violation():
    formula = Cnf(3, [(1,), (-2,)])
    configurator = Configurator(formula)
    assert configurator.classify(DpllBackend()) == {
        1: "mandatory",
        2: "never",
        3: "optional",
    }
    result = configurator.min_violation([([1], 2), ([2], 3)], DpllBackend())
    assert result is not None
    assert result[0] == 3
    assert Configurator(Cnf(1, [(1,), (-1,)])).min_violation([], DpllBackend()) is None


def test_ufl_encoding_solver_and_set_cover_reduction():
    costs, assignment_costs = set_cover_to_ufl(
        3, [{0, 1}, {1, 2}], 2
    )
    assert costs == [1, 1]
    assert assignment_costs == [[0, 0, 3], [3, 0, 0]]
    problem, factories, assignments = ufl_problem([3, 4], [[1, 5], [4, 2]])
    assert len(factories) == 2
    assert len(assignments) == 2
    result = solve_ufl([3, 4], [[1, 5], [4, 2]], DpllBackend())
    assert result is not None
    assert result.cost == ufl_cost([3, 4], [[1, 5], [4, 2]],
                                   result.open_facilities, result.assignment)
    empty_result = solve_ufl([], [], DpllBackend())
    assert empty_result is not None
    assert empty_result.cost == 0
    with pytest.raises(ValueError, match="Matrix"):
        ufl_problem([1], [[1], [2]])
