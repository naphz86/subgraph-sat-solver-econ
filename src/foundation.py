"""Formales Fundament (Kapitel 2): wirtschaftliche Optimierungsprobleme, Selbstreduzierbarkeit,
Optimierung aus Entscheidung.

Zentrale Bausteine:

* :class:`Problem` – ein wirtschaftliches Optimierungsproblem (Definition ``def:wop``):
  Entscheidungsbits ``x``, Zulässigkeit ``F`` und Zielfunktionen ``U`` als Schaltkreis.
* :func:`selfreduce` – Entscheiden ⇒ Finden (Satz ``satz:selfred``).
* :func:`maximize` – Optimalwert und Optimallösung mit ``≤ L+n+2`` Entscheideraufrufen
  (Satz ``satz:opt``).
* :func:`find_witness` – FP = FNP-Suche über Präfixentscheidungen (Satz ``satz:fpfnp``).
* :func:`s3_time_bound` – Laufzeitschranke ``O(N^3)`` unter der Hypothese ``(S_3)``
  (Lemma ``lem:S3``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .backends import BackendError, DecisionOnlyBackend, SatBackend
from .circuits import CircuitBuilder, Signal, Word
from .cnf import Cnf

# --------------------------------------------------------------------------- Problem


class Problem:
    """Wirtschaftliches Optimierungsproblem (Definition ``def:wop``).

    ``x`` sind die Entscheidungsvariablen (Eingänge). Harte Nebenbedingungen können
    direkt als Klauseln in ``cb.cnf`` stehen (z.B. Konfliktklauseln einer Auktion) oder
    über das Signal ``feasible``. Zielfunktionen sind Bitwörter ``objectives``.
    """

    def __init__(self, num_decision_vars: int = 0, cb: Optional[CircuitBuilder] = None,
                 x: Optional[List[int]] = None) -> None:
        self.cb = cb if cb is not None else CircuitBuilder()
        self.x: List[int] = x if x is not None else self.cb.inputs(num_decision_vars)
        self.feasible: Signal = True
        self.objectives: List[Word] = []

    @property
    def n(self) -> int:
        return len(self.x)

    @property
    def cnf(self) -> Cnf:
        return self.cb.cnf

    def require(self, signal: Signal) -> None:
        """Verlangt ``signal`` zusätzlich zur Zulässigkeit ``F``."""
        self.feasible = self.cb.and_(self.feasible, signal)

    def add_objective(self, word: Word) -> int:
        self.objectives.append(list(word))
        return len(self.objectives) - 1

    def copy(self) -> "Problem":
        cb = CircuitBuilder(self.cb.cnf.copy())
        cb.gates = list(self.cb.gates)
        other = Problem(cb=cb, x=list(self.x))
        other.feasible = self.feasible
        other.objectives = [list(w) for w in self.objectives]
        return other

    def with_lower_bound(self, word: Sequence[Signal], bound: int) -> "Problem":
        """Kopie mit zusätzlicher Bedingung ``val(word) ≥ bound`` (Stufe ``F_i`` in Satz ``satz:lex``)."""
        other = self.copy()
        other.require(other.cb.ge_const(word, bound))
        return other

    def check(self, x_values: Sequence[bool]) -> Tuple[bool, List[int]]:
        """Polynomielle Zeugenprüfung (Lemma ``lem:wop-np``): ``(F(x), (U_i(x))_i)``."""
        if len(x_values) != self.n:
            raise ValueError("falsche Anzahl Entscheidungsbits")
        values = self.cb.evaluate(dict(zip(self.x, x_values)))
        hard_ok = all(
            any(self.cb.value_of(lit, values) for lit in clause)
            for clause in self.cb.cnf.clauses
            if all(abs(lit) in values for lit in clause)
        )
        # Klauseln mit freien Hilfsvariablen (nicht aus x oder Gattern) werden nicht geprüft;
        # Probleme dieses Pakets verwenden solche Variablen nicht.
        feasible = hard_ok and self.cb.value_of(self.feasible, values)
        return feasible, [self.cb.word_value(w, values) for w in self.objectives]


def new_problem(num_decision_vars: int) -> Problem:
    return Problem(num_decision_vars)


# ----------------------------------------------------------------- Selbstreduzierbarkeit


def selfreduce(
    cnf: Cnf,
    backend: SatBackend,
    variables: Optional[Iterable[int]] = None,
    *,
    known_sat: bool = False,
) -> Optional[Dict[int, bool]]:
    """Entscheiden ⇒ Finden (Satz ``satz:selfred``).

    Benutzt vom Backend nur :meth:`SatBackend.is_sat`. Für ``variables`` (Standard: alle)
    wird schrittweise ``x_i:=0`` versucht, sonst ``x_i:=1``. Höchstens ``|variables|+1``
    Aufrufe (``|variables|``, falls ``known_sat``). Gibt die Belegung der Variablen
    oder ``None`` (unerfüllbar) zurück.
    """
    if not known_sat and not backend.is_sat(cnf):
        return None
    chosen = list(range(1, cnf.num_vars + 1)) if variables is None else list(variables)
    current = cnf
    assignment: Dict[int, bool] = {}
    for var in chosen:
        attempt = current.restrict({var: False})
        if backend.is_sat(attempt):
            current, assignment[var] = attempt, False
        else:
            current, assignment[var] = current.restrict({var: True}), True
    return assignment


def find_model(cnf: Cnf, backend: SatBackend) -> Optional[Dict[int, bool]]:
    """Vollständige erfüllende Belegung nur mit Entscheideraufrufen (``n+1`` Aufrufe)."""
    return selfreduce(cnf, backend)


# ------------------------------------------------------------------------- Optimierung


@dataclass
class Optimum:
    feasible: bool
    value: Optional[int] = None
    x: Optional[List[bool]] = None
    calls: int = 0


def _phi(problem: Problem, objective: Sequence[Signal], bound: int) -> Cnf:
    """``φ_B = τ(F) ∧ τ(GE_B(U)) ∧ (g_F) ∧ (g_GE)`` aus dem Beweis von Satz ``satz:opt``."""
    cnf = problem.cnf.copy()
    cb = CircuitBuilder(cnf)
    cb.assert_true(problem.feasible)
    cb.assert_true(cb.ge_const(objective, bound))
    return cnf


def maximize(
    problem: Problem,
    objective: Sequence[Signal],
    backend: SatBackend,
    *,
    use_models: bool = False,
) -> Optimum:
    """Optimalwert und Optimallösung (Satz ``satz:opt``).

    (a) ``φ_0`` entscheidet die Zulässigkeit; (b) binäre Suche über ``{0..2^L-1}`` mit
    höchstens ``L`` weiteren Aufrufen; (c) Selbstreduktion von ``φ_opt`` über die
    Eingangsvariablen. Insgesamt höchstens ``1 + L + n`` Aufrufe (Schranke der Arbeit:
    ``L + n + 2``). Mit ``use_models=True`` wird stattdessen das Modell des Backends
    gelesen (weniger Aufrufe, aber nicht mehr "nur Entscheider").
    """
    width = len(objective)
    calls = 0

    def decide(bound: int) -> bool:
        nonlocal calls
        calls += 1
        return backend.is_sat(_phi(problem, objective, bound))

    if not decide(0):
        return Optimum(False, None, None, calls)
    lo, hi = 0, 1 << width
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if decide(mid):
            lo = mid
        else:
            hi = mid
    phi_opt = _phi(problem, objective, lo)
    if use_models:
        calls += 1
        model = backend.solve(phi_opt)
        if model is None:  # pragma: no cover - widerspricht der Invariante der binären Suche
            raise BackendError("inkonsistente Antworten des Entscheiders")
        x = [model[v] for v in problem.x]
    else:
        counter = DecisionOnlyBackend(backend)
        assignment = selfreduce(phi_opt, counter, problem.x, known_sat=True)
        calls += counter.calls
        if assignment is None:  # pragma: no cover - known_sat=True
            raise BackendError("inkonsistente Antworten des Entscheiders")
        x = [assignment[v] for v in problem.x]
    return Optimum(True, lo, x, calls)


def minimize(
    problem: Problem,
    objective: Sequence[Signal],
    backend: SatBackend,
    *,
    use_models: bool = False,
) -> Optimum:
    """Minimierung über ``U' = (2^L-1) - U`` (Definition ``def:wop``)."""
    p = problem.copy()
    complemented = p.cb.complement(objective)
    result = maximize(p, complemented, backend, use_models=use_models)
    if result.feasible:
        result.value = (1 << len(objective)) - 1 - (result.value or 0)
    return result


def lower_bound_decision(problem: Problem, objective: Sequence[Signal], bound: int,
                         backend: SatBackend) -> bool:
    """``Π_dec``: existiert ``x`` zulässig mit ``U(x) ≥ B``?"""
    return backend.is_sat(_phi(problem, objective, bound))


# ----------------------------------------------------------------- FP = FNP (Suche)


def find_witness(
    prefix_exists: Callable[[str], bool],
    is_witness: Callable[[str], bool],
    max_len: int,
) -> Optional[str]:
    """Zeugensuche über Präfixentscheidungen (Satz ``satz:fpfnp``).

    ``prefix_exists(u)`` entscheidet ``(x,u) ∈ L_R`` (gibt es eine Verlängerung ``uv`` mit
    ``R(x,uv)``?), ``is_witness(u)`` entscheidet ``R(x,u)``. Gibt einen Zeugen
    (Bitstring) oder ``None`` zurück; höchstens ``max_len`` Verlängerungsschritte.
    """
    if not prefix_exists(""):
        return None
    u = ""
    for _ in range(max_len + 1):
        if is_witness(u):
            return u
        if len(u) >= max_len:
            break
        u += "0" if prefix_exists(u + "0") else "1"
    raise BackendError("Präfixentscheider inkonsistent: kein Zeuge innerhalb der Längenschranke")


# ------------------------------------------------------------- Entscheiden via Reduktion


def decide_via_sat(instance, encode: Callable[[object], Cnf], backend: SatBackend) -> bool:
    """Reduktionslemma (Satz ``satz:reduktion``): ``I ∈ Π ⇔ φ_I ∈ SAT``."""
    return backend.is_sat(encode(instance))


# -------------------------------------------------------------- Größen- und Laufzeitschranken


def three_cnf_size_bounds(n_size: int) -> Tuple[int, int]:
    """Schranken aus Lemma ``lem:3cnf`` für ``|φ| = N``: ``(max. Klauseln, max. Literale)``."""
    return n_size, 3 * n_size


def clique_graph_node_bound(n_size: int) -> int:
    """Der Clique-Graph hat höchstens ``3N`` Knoten (Beweis von Lemma ``lem:S3``)."""
    return 3 * n_size


def s3_time_bound(n_size: int, c: float = 1.0) -> float:
    """Unter ``(S_3)``: ``c·(3N)^3 = 27·c·N^3`` Schritte (Lemma ``lem:S3``)."""
    return c * (3 * n_size) ** 3


def tseitin_size_bound(num_gates: int) -> int:
    """``|τ(C)| ≤ 12·s`` (Lemma ``lem:tseitin``)."""
    return 12 * num_gates


def opt_call_bound(width: int, n: int) -> int:
    """Aufrufschranke ``L + n + 2`` aus Satz ``satz:opt``."""
    return width + n + 2


def opt_formula_size_bound(s: int, width: int) -> int:
    """Größenschranke ``12(s+L)+2`` der Formeln ``φ_B`` (Beweis von Satz ``satz:opt``)."""
    return 12 * (s + width) + 2
