"""Spiele, Gleichgewichte und kollektive Entscheidungen (Kapitel 7)."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from fractions import Fraction
from math import ceil
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .backends import SatBackend
from .foundation import Problem, minimize

Number = Fraction
MixedProfile = List[List[Fraction]]

# ------------------------------------------------------ Näherungsgleichgewichte


@dataclass
class NormalFormGame:
    """Endliches ``k``-Personen-Spiel in Normalform mit rationalen Auszahlungen."""

    action_counts: Tuple[int, ...]
    payoffs: Dict[Tuple[int, ...], Tuple[Fraction, ...]]

    @classmethod
    def from_function(cls, action_counts: Sequence[int],
                      payoff: Callable[[Tuple[int, ...]], Sequence[object]]) -> "NormalFormGame":
        table = {
            profile: tuple(Fraction(v) for v in payoff(profile))
            for profile in itertools.product(*[range(a) for a in action_counts])
        }
        return cls(tuple(action_counts), table)

    @classmethod
    def bimatrix(cls, a: Sequence[Sequence[object]], b: Sequence[Sequence[object]]) -> "NormalFormGame":
        return cls.from_function(
            (len(a), len(a[0])), lambda p: (a[p[0]][p[1]], b[p[0]][p[1]])
        )

    @property
    def num_players(self) -> int:
        return len(self.action_counts)

    @property
    def max_abs_payoff(self) -> Fraction:
        return max(abs(v) for row in self.payoffs.values() for v in row)


def expected_payoff(game: NormalFormGame, profile: Sequence[Sequence[Fraction]], player: int) -> Fraction:
    """Erwartete Auszahlung von ``player`` unter dem gemischten Profil."""
    total = Fraction(0)
    for actions in itertools.product(*[range(a) for a in game.action_counts]):
        prob = Fraction(1)
        for i, a in enumerate(actions):
            prob *= profile[i][a]
        if prob:
            total += prob * game.payoffs[actions][player]
    return total


def deviation_payoff(game: NormalFormGame, profile: Sequence[Sequence[Fraction]],
                     player: int, action: int) -> Fraction:
    """Auszahlung, wenn ``player`` die reine Aktion ``action`` spielt, die anderen ihr Profil."""
    deviating = [list(p) for p in profile]
    deviating[player] = [Fraction(1) if a == action else Fraction(0)
                         for a in range(game.action_counts[player])]
    return expected_payoff(game, deviating, player)


def is_eps_nash(game: NormalFormGame, profile: Sequence[Sequence[Fraction]], eps: Fraction) -> bool:
    """Prüft ``u_i(a_i', x_{-i}) ≤ u_i(x) + ε`` für alle Spieler und Aktionen (exakt, rational)."""
    for i in range(game.num_players):
        base = expected_payoff(game, profile, i)
        for a in range(game.action_counts[i]):
            if deviation_payoff(game, profile, i, a) > base + eps:
                return False
    return True


def round_distribution(dist: Sequence[object], eta: Fraction) -> List[Fraction]:
    """Rundung auf Nenner ``q = ⌈|A|/η⌉`` (Beweis von Satz ``satz:eps-nash``).

    Größte-Reste-Verfahren: Ergebnis ist eine Verteilung mit ``‖x'−x‖₁ ≤ η``.
    """
    exact = [Fraction(p) for p in dist]
    if any(p < 0 for p in exact) or sum(exact) != 1:
        raise ValueError("keine Wahrscheinlichkeitsverteilung")
    q = ceil(Fraction(len(exact)) / Fraction(eta))
    floors = [int(p * q) for p in exact]
    remainder = q - sum(floors)
    order = sorted(range(len(exact)), key=lambda i: exact[i] * q - floors[i], reverse=True)
    for i in order[:remainder]:
        floors[i] += 1
    return [Fraction(f, q) for f in floors]


def eps_nash_from_exact(game: NormalFormGame, exact_profile: Sequence[Sequence[object]],
                        eps: Fraction) -> List[List[Fraction]]:
    """Rationales ``ε``-Gleichgewicht aus einem exakten Gleichgewicht (Satz ``satz:eps-nash``).

    Mit ``η = ε/(2kU)`` wird jede Verteilung gerundet; das Ergebnis ist polynomiell
    verifizierbar und erfüllt ``is_eps_nash``.
    """
    eps = Fraction(eps)
    if eps <= 0:
        raise ValueError("ε muss positiv sein")
    u = game.max_abs_payoff or Fraction(1)
    eta = eps / (2 * game.num_players * u)
    rounded = [round_distribution(p, eta) for p in exact_profile]
    if not is_eps_nash(game, rounded, eps):  # pragma: no cover - widerspräche dem Satz
        raise AssertionError("gerundetes Profil ist kein ε-Gleichgewicht")
    return rounded


def _solve_linear(matrix: List[List[Fraction]], rhs: List[Fraction]) -> Optional[List[Fraction]]:
    """Gauß-Elimination über den Rationalzahlen; ``None`` bei singulärem System."""
    n = len(matrix)
    aug = [row[:] + [r] for row, r in zip(matrix, rhs)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if aug[r][col] != 0), None)
        if pivot is None:
            return None
        aug[col], aug[pivot] = aug[pivot], aug[col]
        aug[col] = [v / aug[col][col] for v in aug[col]]
        for r in range(n):
            if r != col and aug[r][col] != 0:
                factor = aug[r][col]
                aug[r] = [a - factor * b for a, b in zip(aug[r], aug[col])]
    return [aug[r][n] for r in range(n)]


def _indifferent_mix(matrix: Sequence[Sequence[Fraction]], rows: Sequence[int],
                     cols: Sequence[int]) -> Optional[Tuple[List[Fraction], Fraction]]:
    """Verteilung ``y`` auf ``cols`` mit gleichem Wert ``v`` für alle ``rows`` (Σy=1)."""
    s = len(cols)
    system = [[Fraction(matrix[r][c]) for c in cols] + [Fraction(-1)] for r in rows]
    system.append([Fraction(1)] * s + [Fraction(0)])
    solution = _solve_linear(system, [Fraction(0)] * len(rows) + [Fraction(1)])
    if solution is None:
        return None
    return solution[:s], solution[s]


def nash_equilibria_2p(a: Sequence[Sequence[object]], b: Sequence[Sequence[object]]
                       ) -> List[Tuple[List[Fraction], List[Fraction]]]:
    """Alle Gleichgewichte eines nichtdegenerierten Bimatrixspiels (Support-Aufzählung, exakt).

    Zeugenverifikation in Polynomialzeit; die Aufzählung selbst ist exponentiell
    (keine SAT-Kodierung). Dient der Berechnung von ``x*`` für Satz ``satz:eps-nash`` und
    der Suche nach Gleichgewichten mit Zusatzeigenschaft (NP).
    """
    am = [[Fraction(v) for v in row] for row in a]
    bm = [[Fraction(v) for v in row] for row in b]
    m, n = len(am), len(am[0])
    found: List[Tuple[List[Fraction], List[Fraction]]] = []
    for size in range(1, min(m, n) + 1):
        for rows in itertools.combinations(range(m), size):
            for cols in itertools.combinations(range(n), size):
                y_mix = _indifferent_mix(am, rows, cols)
                bt = [[bm[i][j] for i in range(m)] for j in range(n)]
                x_mix = _indifferent_mix(bt, cols, rows)
                if y_mix is None or x_mix is None:
                    continue
                y_s, _ = y_mix
                x_s, _ = x_mix
                if any(v < 0 for v in y_s) or any(v < 0 for v in x_s):
                    continue
                x = [Fraction(0)] * m
                y = [Fraction(0)] * n
                for r, v in zip(rows, x_s):
                    x[r] = v
                for c, v in zip(cols, y_s):
                    y[c] = v
                if _is_best_response_2p(am, bm, x, y):
                    found.append((x, y))
    return found


def _is_best_response_2p(a, b, x, y) -> bool:
    m, n = len(a), len(a[0])
    row_values = [sum(a[i][j] * y[j] for j in range(n)) for i in range(m)]
    col_values = [sum(b[i][j] * x[i] for i in range(m)) for j in range(n)]
    best_row, best_col = max(row_values), max(col_values)
    return all(row_values[i] == best_row for i in range(m) if x[i] > 0) and \
        all(col_values[j] == best_col for j in range(n) if y[j] > 0)


def equilibrium_with_welfare(a, b, welfare: Fraction):
    """Gibt ein Gleichgewicht mit ``u_1+u_2 ≥ welfare`` zurück (NP-vollständig, Bemerkung nach Korollar "Nash unter E_poly") oder ``None``."""
    for x, y in nash_equilibria_2p(a, b):
        u1 = sum(Fraction(a[i][j]) * x[i] * y[j] for i in range(len(x)) for j in range(len(y)))
        u2 = sum(Fraction(b[i][j]) * x[i] * y[j] for i in range(len(x)) for j in range(len(y)))
        if u1 + u2 >= welfare:
            return x, y
    return None


# ------------------------------------------------------------------ Soziale Wahl


def kemeny_problem(num_candidates: int, weights: Sequence[Sequence[int]]
                   ) -> Tuple[Problem, Dict[Tuple[int, int], int]]:
    """Kemeny-Rangaggregation (Satz ``satz:kemeny``).

    Variablen ``o_{ab}`` für ``a<b`` (``o_{ba} := ¬o_{ab}``); Klauseln
    ``(¬o_{ab} ∨ ¬o_{bc} ∨ o_{ac})`` verbieten 3-Zyklen. Zielfunktion: Kendall-Tau-Kosten
    ``Σ_{a≠b} w_{ab} [o_{ba}]`` (``w_{ab}`` = Zahl der Wähler mit ``a`` vor ``b``).
    """
    q = num_candidates
    pairs = [(a, b) for a in range(q) for b in range(a + 1, q)]
    problem = Problem(len(pairs))
    var = dict(zip(pairs, problem.x))

    def o(a: int, b: int) -> int:
        return var[(a, b)] if a < b else -var[(b, a)]

    for a, b, c in itertools.permutations(range(q), 3):
        problem.cnf.add_clause(-o(a, b), -o(b, c), o(a, c))
    signals, consts = [], []
    for a in range(q):
        for b in range(q):
            if a != b:
                signals.append(o(b, a))
                consts.append(weights[a][b])
    problem.add_objective(problem.cb.weighted_sum(signals, consts))
    return problem, var


def pairwise_weights(num_candidates: int, ballots: Sequence[Sequence[int]]) -> List[List[int]]:
    """``w_{ab}`` = Zahl der Stimmzettel, in denen ``a`` vor ``b`` steht."""
    w = [[0] * num_candidates for _ in range(num_candidates)]
    for ballot in ballots:
        pos = {c: i for i, c in enumerate(ballot)}
        for a in range(num_candidates):
            for b in range(num_candidates):
                if a != b and pos[a] < pos[b]:
                    w[a][b] += 1
    return w


def kendall_tau_cost(order: Sequence[int], weights: Sequence[Sequence[int]]) -> int:
    pos = {c: i for i, c in enumerate(order)}
    return sum(
        weights[a][b] for a in pos for b in pos if a != b and pos[b] < pos[a]
    )


@dataclass
class KemenyResult:
    order: List[int]
    cost: int
    calls: int


def solve_kemeny(num_candidates: int, ballots: Sequence[Sequence[int]], backend: SatBackend,
                 *, use_models: bool = False) -> KemenyResult:
    """Optimale Konsensrangfolge (Kemeny) mit Entscheideraufrufen."""
    weights = pairwise_weights(num_candidates, ballots)
    problem, var = kemeny_problem(num_candidates, weights)
    result = minimize(problem, problem.objectives[0], backend, use_models=use_models)
    values = dict(zip(problem.x, result.x or []))
    # a steht vor b ⇔ o_ab; Rang = Zahl der Kandidaten, die vor a stehen
    def before(a: int, b: int) -> bool:
        return values[var[(a, b)]] if a < b else not values[var[(b, a)]]

    order = sorted(range(num_candidates),
                   key=lambda c: sum(1 for d in range(num_candidates) if d != c and before(d, c)))
    return KemenyResult(order, result.value or 0, result.calls)


# --------------------------------------------------------------- Manipulation


def plurality_winner(ballots: Sequence[Sequence[int]]) -> int:
    """Pluralität mit Tie-Break zugunsten des kleineren Kandidatenindex."""
    tally: Dict[int, int] = {}
    for b in ballots:
        tally[b[0]] = tally.get(b[0], 0) + 1
    return min(tally, key=lambda c: (-tally[c], c))


def borda_winner(ballots: Sequence[Sequence[int]]) -> int:
    q = len(ballots[0])
    score = {c: 0 for c in ballots[0]}
    for b in ballots:
        for pos, c in enumerate(b):
            score[c] += q - 1 - pos
    return min(score, key=lambda c: (-score[c], c))


def manipulation_witness(rule: Callable[[Sequence[Sequence[int]]], int],
                         ballots: Sequence[Sequence[int]], voter: int, target: int
                         ) -> Optional[Tuple[int, ...]]:
    """Stimmzettel von ``voter``, der ``target`` zum Sieger macht (Satz ``satz:manip``).

    Das Problem liegt in NP: Zeuge ist der Stimmzettel, geprüft durch Auswertung der
    Wahlregel. Die Suche hier ist Enumeration aller Permutationen.
    """
    candidates = list(ballots[0])
    for perm in itertools.permutations(candidates):
        trial = list(ballots)
        trial[voter] = perm
        if rule(trial) == target:
            return perm
    return None
