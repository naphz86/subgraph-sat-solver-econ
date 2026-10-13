from fractions import Fraction

from src.backends import DpllBackend
import pytest

from src.games import (
    NormalFormGame,
    _solve_linear,
    borda_winner,
    deviation_payoff,
    eps_nash_from_exact,
    equilibrium_with_welfare,
    expected_payoff,
    is_eps_nash,
    kendall_tau_cost,
    manipulation_witness,
    nash_equilibria_2p,
    pairwise_weights,
    plurality_winner,
    round_distribution,
    solve_kemeny,
)


def test_pure_nash_equilibrium_is_eps_nash():
    a = [[3, 0], [5, 1]]
    b = [[3, 5], [0, 1]]
    equilibrium = nash_equilibria_2p(a, b)[0]
    game = NormalFormGame.bimatrix(a, b)
    assert is_eps_nash(game, equilibrium, Fraction(0))


def test_kemeny_solver_returns_candidate_permutation():
    ballots = [[0, 1, 2], [0, 2, 1], [1, 0, 2]]
    result = solve_kemeny(3, ballots, DpllBackend())
    assert sorted(result.order) == [0, 1, 2]
    assert result.cost >= 0


def test_payoffs_approximation_and_distribution_validation():
    game = NormalFormGame.bimatrix([[1, 0], [0, 1]], [[1, 0], [0, 1]])
    profile = [[Fraction(1, 2), Fraction(1, 2)]] * 2
    assert game.num_players == 2
    assert game.max_abs_payoff == 1
    assert expected_payoff(game, profile, 0) == Fraction(1, 2)
    assert deviation_payoff(game, profile, 0, 0) == Fraction(1, 2)
    assert round_distribution([Fraction(1, 3)] * 3, Fraction(1, 10)) == [
        Fraction(1, 3)
    ] * 3
    equilibrium = nash_equilibria_2p(
        [[1, 0], [0, 1]], [[1, 0], [0, 1]]
    )[0]
    rounded = eps_nash_from_exact(game, equilibrium, Fraction(1, 10))
    assert is_eps_nash(game, rounded, Fraction(1, 10))
    assert not is_eps_nash(
        game,
        [[Fraction(1), Fraction(0)], [Fraction(0), Fraction(1)]],
        Fraction(0),
    )
    with pytest.raises(ValueError, match="Wahrscheinlichkeitsverteilung"):
        round_distribution([Fraction(1, 2), Fraction(1, 3)], Fraction(1, 10))
    with pytest.raises(ValueError, match="positiv"):
        eps_nash_from_exact(game, equilibrium, Fraction(0))


def test_equilibrium_support_and_welfare_filter():
    a = [[3, 0], [5, 1]]
    b = [[3, 5], [0, 1]]
    equilibria = nash_equilibria_2p(a, b)
    assert equilibria
    assert equilibrium_with_welfare(a, b, Fraction(2)) is not None
    assert equilibrium_with_welfare(a, b, Fraction(100)) is None
    assert nash_equilibria_2p([[1, 1], [1, 1]], [[1, 1], [1, 1]])
    assert _solve_linear(
        [[Fraction(1), Fraction(1)], [Fraction(2), Fraction(2)]],
        [Fraction(1), Fraction(2)],
    ) is None


def test_election_scores_and_manipulation_witness():
    ballots = [[0, 1, 2], [1, 0, 2], [1, 2, 0]]
    weights = pairwise_weights(3, ballots)
    assert weights[0][1] == 1
    assert kendall_tau_cost([0, 1, 2], weights) >= 0
    assert plurality_winner(ballots) == 1
    assert borda_winner(ballots) == 1
    witness = manipulation_witness(plurality_winner, [[1, 0, 2], [0, 1, 2]], 0, 0)
    assert witness is not None
    assert manipulation_witness(plurality_winner, ballots, 0, 99) is None
