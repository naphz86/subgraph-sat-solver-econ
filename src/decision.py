"""Entscheidungstheorie (Kapitel 3): Nutzen, Lexikographie, Pareto, Wohlfahrt,
Risiko, robuste Entscheidungen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from math import lcm
from typing import Callable, Dict, Hashable, List, Optional, Sequence, Tuple

from .backends import SatBackend
from .circuits import CircuitBuilder, Signal, Word
from .foundation import Optimum, Problem, maximize

# ------------------------------------------------------------ Nutzendarstellung


def utility_from_preference(
    items: Sequence[Hashable], weakly_prefers: Callable[[Hashable, Hashable], bool]
) -> Dict[Hashable, int]:
    """``u(a) = |{b : a ⪰ b}|`` (Satz ``satz:utility``).

    ``weakly_prefers`` muss auf der endlichen Menge vollständig und transitiv sein.
    """
    return {a: sum(1 for b in items if weakly_prefers(a, b)) for a in items}


# ------------------------------------------------------------- Rationale Wahl


def rational_choice(problem: Problem, objective_index: int, backend: SatBackend, *,
                    use_models: bool = False) -> Optimum:
    """Nutzenmaximales Element der implizit gegebenen Menge (Satz ``satz:choice``)."""
    return maximize(problem, problem.objectives[objective_index], backend, use_models=use_models)


# ------------------------------------------------------- Lexikographische Optimierung


@dataclass
class LexResult:
    feasible: bool
    values: List[int] = field(default_factory=list)
    x: Optional[List[bool]] = None
    optimizations: int = 0


def lexicographic(problem: Problem, objectives: Sequence[Sequence[Signal]],
                  backend: SatBackend, *, use_models: bool = False) -> LexResult:
    """Lexikographische Optimierung ``U_1 ≻ … ≻ U_k`` (Satz ``satz:lex``): ``k`` Optimierungen."""
    current = problem
    values: List[int] = []
    last: Optional[Optimum] = None
    for count, word in enumerate(objectives, start=1):
        # Der Zielwort-Bezug muss in der aktuellen (kopierten) Instanz gelten: Signale sind
        # Literale in einem gemeinsamen Variablenraum, daher bleiben sie in Kopien gültig.
        last = maximize(current, word, backend, use_models=use_models)
        if not last.feasible:
            return LexResult(False, values, None, count)
        values.append(last.value)  # type: ignore[arg-type]
        current = current.with_lower_bound(word, last.value)  # type: ignore[arg-type]
    return LexResult(True, values, last.x if last else None, len(objectives))


# ------------------------------------------------------------- Pareto-Front


@dataclass
class ParetoResult:
    front: List[Tuple[int, ...]]
    optimizations: int


def pareto_front(problem: Problem, objectives: Sequence[Sequence[Signal]],
                 backend: SatBackend, *, use_models: bool = False) -> ParetoResult:
    """Aufzählung der Pareto-Front (Satz ``satz:pareto``): ``|P| + 1`` Optimierungen.

    Wiederholt: maximiere ``Σ U_i`` über den zulässigen Punkten, die von keinem bisher
    gefundenen Vektor ``y`` schwach dominiert werden (``∀y ∃i: U_i(x) > y_i``).
    """
    found: List[Tuple[int, ...]] = []
    optimizations = 0
    while True:
        p = problem.copy()
        cb = p.cb
        for y in found:
            p.require(cb.or_all([cb.ge_const(w, yi + 1) for w, yi in zip(objectives, y)]))
        total = cb.sum_words(objectives)
        result = maximize(p, total, backend, use_models=use_models)
        optimizations += 1
        if not result.feasible:
            return ParetoResult(found, optimizations)
        values = cb.evaluate(dict(zip(p.x, result.x)))  # type: ignore[arg-type]
        found.append(tuple(cb.word_value(w, values) for w in objectives))


# ------------------------------------------------------------- Soziale Wohlfahrt


def welfare_word(cb: CircuitBuilder, utilities: Sequence[Sequence[Signal]], kind: str) -> Word:
    """Wohlfahrtsfunktion ``W(U_1..U_k)`` (Satz ``satz:swf``).

    ``kind``: ``"utilitarian"`` (Summe), ``"egalitarian"`` (Minimum) oder ``"nash"``
    (Produkt). Alle sind in Polynomialzeit berechenbar, das Ergebnis ist ein Bitwort.
    """
    if not utilities:
        raise ValueError("mindestens ein Nutzen erforderlich")
    if kind == "utilitarian":
        return cb.sum_words(utilities)
    if kind == "egalitarian":
        return cb.min_words(utilities)
    if kind == "nash":
        acc: Word = list(utilities[0])
        for w in utilities[1:]:
            acc = cb.mul_words(acc, w, len(acc) + len(w))
        return acc
    raise ValueError(f"unbekannte Wohlfahrtsfunktion: {kind!r}")


def maximize_welfare(problem: Problem, utilities: Sequence[Sequence[Signal]], kind: str,
                     backend: SatBackend, *, use_models: bool = False) -> Optimum:
    """Maximiert die soziale Wohlfahrt (Satz ``satz:swf``)."""
    p = problem.copy()
    word = welfare_word(p.cb, utilities, kind)
    return maximize(p, word, backend, use_models=use_models)


# -------------------------------------------------- Risiko: explizite Zustandsräume


def _integer_weights(probabilities: Sequence[Fraction]) -> List[int]:
    if any(p < 0 for p in probabilities) or sum(probabilities) != 1:
        raise ValueError("Wahrscheinlichkeiten müssen nichtnegativ sein und sich zu 1 summieren")
    den = lcm(*(Fraction(p).denominator for p in probabilities))
    return [int(Fraction(p) * den) for p in probabilities]


def expected_utility_word(cb: CircuitBuilder, state_utilities: Sequence[Sequence[Signal]],
                          probabilities: Sequence[Fraction]) -> Word:
    """Ganzzahliges Wort für ``Σ_s π_s·U(x,s)`` (nach Skalierung mit dem Hauptnenner)."""
    if len(state_utilities) != len(probabilities):
        raise ValueError("Zustände und Wahrscheinlichkeiten müssen gleich viele sein")
    weights = _integer_weights([Fraction(p) for p in probabilities])
    width = max(len(w) for w in state_utilities) + max(weights).bit_length() + len(weights).bit_length()
    terms = [cb.mul_const(w, c, width) for w, c in zip(state_utilities, weights)]
    return cb.sum_words(terms)


def maximize_expected_utility(problem: Problem, state_utilities: Sequence[Sequence[Signal]],
                              probabilities: Sequence[Fraction], backend: SatBackend, *,
                              use_models: bool = False) -> Optimum:
    """Erwartungsnutzen bei explizitem Zustandsraum (Satz "Erwartungsnutzen")."""
    p = problem.copy()
    word = expected_utility_word(p.cb, state_utilities, probabilities)
    return maximize(p, word, backend, use_models=use_models)


def maximin(problem: Problem, state_utilities: Sequence[Sequence[Signal]], backend: SatBackend, *,
            use_models: bool = False) -> Optimum:
    """Wald-Kriterium ``max_x min_s U(x,s)``."""
    p = problem.copy()
    word = p.cb.min_words(state_utilities)
    return maximize(p, word, backend, use_models=use_models)


@dataclass
class RegretResult:
    feasible: bool
    regret: Optional[int] = None
    x: Optional[List[bool]] = None
    state_optima: List[int] = field(default_factory=list)


def minimax_regret(problem: Problem, state_utilities: Sequence[Sequence[Signal]],
                   backend: SatBackend, *, use_models: bool = False) -> RegretResult:
    """Minimax-Regret ``min_x max_s (opt_s - U(x,s))``.

    Mit ``M = max_s opt_s`` und ``c_s = M - opt_s ≥ 0`` ist das gleichwertig zu
    ``max_x min_s (U(x,s) + c_s)``; der Regret ist ``M`` minus dieser Wert.
    """
    optima: List[int] = []
    for word in state_utilities:
        result = maximize(problem, word, backend, use_models=use_models)
        if not result.feasible:
            return RegretResult(False)
        optima.append(result.value)  # type: ignore[arg-type]
    big = max(optima)
    p = problem.copy()
    shifted: List[Word] = []
    for word, opt in zip(state_utilities, optima):
        shift = big - opt
        width = max(len(word), shift.bit_length()) + 1
        shifted.append(p.cb.add_words(word, p.cb.const_word(shift, width), width))
    best = maximize(p, p.cb.min_words(shifted), backend, use_models=use_models)
    return RegretResult(True, big - (best.value or 0), best.x, optima)


# -------------------------------------------------- Robustheit und CEGAR (Σ2)


@dataclass
class CegarResult:
    robust: bool
    a: Optional[List[bool]]
    scenarios: List[Tuple[bool, ...]]
    rounds: int


def cegar_robust(
    n_a: int,
    n_s: int,
    build: Callable[[CircuitBuilder, Sequence[Signal], Sequence[Signal]], Signal],
    backend: SatBackend,
) -> CegarResult:
    """Gegenbeispielgesteuerte Lösung von ``∃a ∀s: ok(a,s)`` (Satz ``satz:cegar``).

    ``build(cb, a_bits, s_bits)`` liefert das Signal ``ok(a,s)`` (z.B. ``U(a,s) ≥ B``).
    Es werden abwechselnd (1) ein ``a`` gesucht, das alle bisherigen Szenarien besteht,
    und (2) ein Szenario, das dieses ``a`` verletzt. Terminiert nach höchstens
    ``2^m + 1`` Runden; liegt in ``Σ_2^p`` (Satz ``satz:robust``) und wird mit zwei
    SAT-Aufrufen je Runde gelöst.
    """
    scenarios: List[Tuple[bool, ...]] = []
    rounds = 0
    while True:
        rounds += 1
        cb1 = CircuitBuilder()
        a_vars = cb1.inputs(n_a)
        for s in scenarios:
            cb1.assert_true(build(cb1, a_vars, list(s)))
        model = backend.solve(cb1.cnf)
        if model is None:
            return CegarResult(False, None, scenarios, rounds)
        a_values = [model[v] for v in a_vars]

        cb2 = CircuitBuilder()
        s_vars = cb2.inputs(n_s)
        cb2.assert_false(build(cb2, list(a_values), s_vars))
        counter = backend.solve(cb2.cnf)
        if counter is None:
            return CegarResult(True, a_values, scenarios, rounds)
        scenarios.append(tuple(counter[v] for v in s_vars))
