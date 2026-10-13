from src.backends import DpllBackend
from src.circuits import CircuitBuilder
from src.decision import (
    cegar_robust,
    expected_utility_word,
    lexicographic,
    maximin,
    maximize_expected_utility,
    maximize_welfare,
    minimax_regret,
    pareto_front,
    rational_choice,
    utility_from_preference,
    welfare_word,
)
from src.foundation import Problem
import pytest
from fractions import Fraction


def test_utility_from_preference_counts_weakly_preferred_items():
    result = utility_from_preference([0, 1, 2], lambda a, b: a >= b)
    assert result == {0: 1, 1: 2, 2: 3}


def test_lexicographic_optimization_maximizes_objectives_in_order():
    problem = Problem(2)
    first = problem.cb.weighted_sum(problem.x, [1, 0])
    second = problem.cb.weighted_sum(problem.x, [0, 1])
    result = lexicographic(problem, [first, second], DpllBackend())
    assert result.feasible
    assert result.values == [1, 1]


def test_pareto_front_contains_non_dominated_vectors():
    problem = Problem(2)
    problem.cnf.add_clause(-problem.x[0], -problem.x[1])
    result = pareto_front(problem, [[problem.x[0]], [problem.x[1]]], DpllBackend())
    assert set(result.front) == {(1, 0), (0, 1)}


def test_utilitarian_welfare_word_sums_utilities():
    cb = CircuitBuilder()
    x, y = cb.inputs(2)
    total = welfare_word(cb, [[x], [y]], "utilitarian")
    values = cb.evaluate({x: True, y: True})
    assert cb.word_value(total, values) == 2


def test_choice_and_welfare_variants():
    problem = Problem(2)
    problem.cnf.add_clause(-problem.x[0], -problem.x[1])
    u1 = problem.cb.weighted_sum(problem.x, [2, 1])
    u2 = problem.cb.weighted_sum(problem.x, [0, 2])
    problem.add_objective(u1)
    assert rational_choice(problem, 0, DpllBackend()).value == 2
    assert maximize_welfare(problem, [[problem.x[0]], [problem.x[1]]],
                            "egalitarian", DpllBackend()).value == 0
    nash = maximize_welfare(problem, [u1, u2], "nash", DpllBackend())
    assert nash.feasible
    with pytest.raises(ValueError, match="mindestens"):
        welfare_word(CircuitBuilder(), [], "utilitarian")
    with pytest.raises(ValueError, match="unbekannte"):
        welfare_word(CircuitBuilder(), [[1]], "unknown")


def test_expected_utility_and_maximin_decisions():
    problem = Problem(1)
    x = problem.x[0]
    utilities = [[x], [problem.cb.neg(x)]]
    expected = expected_utility_word(
        problem.cb, utilities, [Fraction(1, 2), Fraction(1, 2)]
    )
    assert problem.cb.word_value(expected, problem.cb.evaluate({x: True})) == 1
    result = maximize_expected_utility(
        problem, utilities, [Fraction(1, 2), Fraction(1, 2)], DpllBackend()
    )
    assert result.feasible
    assert maximin(problem, utilities, DpllBackend()).value == 0
    with pytest.raises(ValueError, match="gleich viele"):
        expected_utility_word(problem.cb, utilities[:1], [Fraction(1, 2), Fraction(1, 2)])
    with pytest.raises(ValueError, match="Wahrscheinlichkeiten"):
        expected_utility_word(problem.cb, utilities, [Fraction(1, 3), Fraction(1, 3)])


def test_minimax_regret_and_cegar_robustness():
    problem = Problem(1)
    x = problem.x[0]
    regret = minimax_regret(problem, [[x], [problem.cb.neg(x)]], DpllBackend())
    assert regret.feasible
    assert regret.regret == 1
    robust = cegar_robust(
        1,
        1,
        lambda cb, decisions, scenarios: cb.or_(
            cb.neg(decisions[0]), scenarios[0]
        ),
        DpllBackend(),
    )
    assert robust.robust
    assert robust.a == [False]
    impossible = cegar_robust(
        1,
        1,
        lambda cb, decisions, scenarios: cb.neg(
            cb.xor_(decisions[0], scenarios[0])
        ),
        DpllBackend(),
    )
    assert not impossible.robust
