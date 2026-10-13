"""Produktion, Logistik und Konfiguration (Kapitel 6): Terminplanung, Produktkonfiguration,
Standortplanung."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .backends import SatBackend
from .circuits import CircuitBuilder
from .cnf import Cnf
from .foundation import Problem, maximize, minimize

# ----------------------------------------------------------------- Terminplanung


@dataclass(frozen=True)
class Job:
    """Job mit Freigabe ``r``, Endtermin ``d``, Dauer ``p`` und Gewicht ``w``."""

    release: int
    deadline: int
    proc: int
    weight: int = 1

    def __post_init__(self) -> None:
        if self.proc < 1:
            raise ValueError("Bearbeitungsdauer muss ≥ 1 sein")
        if self.release < 0 or self.weight < 0:
            raise ValueError("Freigabe und Gewicht müssen nichtnegativ sein")

    @property
    def starts(self) -> range:
        """Zulässiges Startfenster ``W_j = [r_j, d_j - p_j]``."""
        return range(self.release, self.deadline - self.proc + 1)


def overlaps(t: int, p: int, t2: int, p2: int) -> bool:
    """Intervalle ``[t,t+p)`` und ``[t2,t2+p2)`` überlappen ⇔ ``t < t2+p2 ∧ t2 < t+p``."""
    return t < t2 + p2 and t2 < t + p


def schedule_problem(jobs: Sequence[Job]) -> Tuple[Problem, Dict[Tuple[int, int], int]]:
    """Einmaschinenplanung (Satz ``satz:sched``): Variablen ``z_{j,t}``.

    Je Job genau ein Startpunkt, paarweise überlappungsfrei. Zielfunktion
    ``Σ w_j (s_j + p_j) = Σ w_j (t + p_j) z_{j,t}`` ist linear in ``z`` (Summierer).
    """
    index: Dict[Tuple[int, int], int] = {}
    total = sum(len(j.starts) for j in jobs)
    problem = Problem(total)
    it = iter(problem.x)
    for j, job in enumerate(jobs):
        for t in job.starts:
            index[(j, t)] = next(it)
    cnf = problem.cnf
    for j, job in enumerate(jobs):
        window = [index[(j, t)] for t in job.starts]
        cnf.add_clause(*window)  # leeres Fenster ⇒ leere Klausel ⇒ unzulässig
        for a in range(len(window)):
            for b in range(a + 1, len(window)):
                cnf.add_clause(-window[a], -window[b])
    for j in range(len(jobs)):
        for k in range(j + 1, len(jobs)):
            for t in jobs[j].starts:
                for t2 in jobs[k].starts:
                    if overlaps(t, jobs[j].proc, t2, jobs[k].proc):
                        cnf.add_clause(-index[(j, t)], -index[(k, t2)])
    keys = list(index)
    consts = [jobs[j].weight * (t + jobs[j].proc) for (j, t) in keys]
    problem.add_objective(problem.cb.weighted_sum([index[k] for k in keys], consts))
    return problem, index


def is_valid_schedule(jobs: Sequence[Job], starts: Mapping[int, int]) -> bool:
    if set(starts) != set(range(len(jobs))):
        return False
    if any(starts[j] not in jobs[j].starts for j in starts):
        return False
    return not any(
        overlaps(starts[j], jobs[j].proc, starts[k], jobs[k].proc)
        for j in range(len(jobs)) for k in range(j + 1, len(jobs))
    )


def weighted_completion(jobs: Sequence[Job], starts: Mapping[int, int]) -> int:
    return sum(job.weight * (starts[j] + job.proc) for j, job in enumerate(jobs))


def _starts_from(index: Mapping[Tuple[int, int], int], model: Mapping[int, bool]) -> Dict[int, int]:
    return {j: t for (j, t), v in index.items() if model[v]}


def feasible_schedule(jobs: Sequence[Job], backend: SatBackend) -> Optional[Dict[int, int]]:
    """Zulässiger Plan oder ``None``."""
    problem, index = schedule_problem(jobs)
    model = backend.solve(problem.cnf)
    return None if model is None else _starts_from(index, model)


@dataclass
class ScheduleResult:
    value: int
    starts: Dict[int, int]
    calls: int


def optimal_schedule(jobs: Sequence[Job], backend: SatBackend,
                     *, use_models: bool = False) -> Optional[ScheduleResult]:
    """Minimale gewichtete Fertigstellungszeit (Minimierung nach Definition ``def:wop``)."""
    problem, index = schedule_problem(jobs)
    result = minimize(problem, problem.objectives[0], backend, use_models=use_models)
    if not result.feasible:
        return None
    x = dict(zip(problem.x, result.x))  # type: ignore[arg-type]
    return ScheduleResult(result.value or 0, _starts_from(index, x), result.calls)


# --------------------------------------------------------------- Konfiguration


class Configurator:
    """Produktdokumentation ``Φ`` als CNF über Optionen (Satz ``satz:config``)."""

    def __init__(self, phi: Cnf) -> None:
        self.phi = phi

    def _with_literals(self, literals: Sequence[int]) -> Cnf:
        cnf = self.phi.copy()
        for lit in literals:
            cnf.add_clause(lit)
        return cnf

    def is_realizable(self, wishes: Sequence[int], backend: SatBackend) -> bool:
        """Kundenwunsch ``c`` (Literalmenge) realisierbar ⇔ ``Φ ∧ c`` erfüllbar."""
        return backend.is_sat(self._with_literals(wishes))

    def classify(self, backend: SatBackend, options: Optional[Sequence[int]] = None) -> Dict[int, str]:
        """Klassifiziert alle Optionen mit ``2|O|`` Entscheideraufrufen.

        ``"never"``: ``Φ ∧ o`` unerfüllbar; ``"mandatory"``: ``Φ ∧ ¬o`` unerfüllbar;
        ``"optional"``: sonst; ``"inconsistent"``: ``Φ`` selbst unerfüllbar.
        """
        result: Dict[int, str] = {}
        for o in (options if options is not None else range(1, self.phi.num_vars + 1)):
            can_be_on = backend.is_sat(self._with_literals([o]))
            can_be_off = backend.is_sat(self._with_literals([-o]))
            if not can_be_on and not can_be_off:
                result[o] = "inconsistent"
            elif not can_be_on:
                result[o] = "never"
            elif not can_be_off:
                result[o] = "mandatory"
            else:
                result[o] = "optional"
        return result

    def min_violation(self, wishes: Sequence[Tuple[Sequence[int], int]], backend: SatBackend,
                      *, use_models: bool = False) -> Optional[Tuple[int, List[bool]]]:
        """Minimale gewichtete Wunschverletzung: ``U(x) = Σ w_k [Wunsch k erfüllt]``, ``F = Φ``.

        Ein Wunsch ist eine Literalmenge, die vollständig erfüllt sein muss. Gibt
        ``(Verletzung, Belegung)`` oder ``None`` zurück, falls ``Φ`` unerfüllbar ist.
        """
        cb = CircuitBuilder(self.phi.copy())
        problem = Problem(cb=cb, x=list(range(1, self.phi.num_vars + 1)))
        signals = [cb.and_all(list(lits)) for lits, _ in wishes]
        word = cb.weighted_sum(signals, [w for _, w in wishes])
        result = maximize(problem, word, backend, use_models=use_models)
        if not result.feasible:
            return None
        return sum(w for _, w in wishes) - (result.value or 0), result.x  # type: ignore[return-value]


# --------------------------------------------------------------- Standortplanung


@dataclass
class UFLResult:
    cost: int
    open_facilities: Set[int]
    assignment: Dict[int, int]
    calls: int


def ufl_problem(open_costs: Sequence[int], assign_costs: Sequence[Sequence[int]]
                ) -> Tuple[Problem, List[int], List[List[int]]]:
    """Uncapacitated Facility Location (Satz ``satz:ufl``).

    Variablen ``y_i`` (Fabrik offen) und ``x_{ij}`` (Kunde ``j`` wird von ``i`` bedient);
    Klauseln ``∨_i x_{ij}`` und ``(¬x_{ij} ∨ y_i)``; Kosten ``Σ f_i y_i + Σ c_{ij} x_{ij}``.
    ``assign_costs[i][j]`` sind die Zuordnungskosten von Kunde ``j`` zu Fabrik ``i``.
    """
    n_f = len(open_costs)
    n_c = len(assign_costs[0]) if assign_costs else 0
    if any(len(row) != n_c for row in assign_costs) or len(assign_costs) != n_f:
        raise ValueError("assign_costs muss eine Fabriken × Kunden-Matrix sein")
    problem = Problem(n_f + n_f * n_c)
    y = problem.x[:n_f]
    x = [[problem.x[n_f + i * n_c + j] for j in range(n_c)] for i in range(n_f)]
    for j in range(n_c):
        problem.cnf.add_clause(*[x[i][j] for i in range(n_f)])
    for i in range(n_f):
        for j in range(n_c):
            problem.cnf.add_clause(-x[i][j], y[i])
    ys = list(y) + [x[i][j] for i in range(n_f) for j in range(n_c)]
    cs = list(open_costs) + [assign_costs[i][j] for i in range(n_f) for j in range(n_c)]
    problem.add_objective(problem.cb.weighted_sum(ys, cs))
    return problem, y, x


def ufl_cost(open_costs: Sequence[int], assign_costs: Sequence[Sequence[int]],
             open_set: Set[int], assignment: Mapping[int, int]) -> int:
    return sum(open_costs[i] for i in open_set) + sum(assign_costs[i][j] for j, i in assignment.items())


def solve_ufl(open_costs: Sequence[int], assign_costs: Sequence[Sequence[int]],
              backend: SatBackend, *, use_models: bool = False) -> Optional[UFLResult]:
    """Kostenminimale Standortplanung; ``None``, falls es keine Fabrik gibt, aber Kunden."""
    problem, y, x = ufl_problem(open_costs, assign_costs)
    result = minimize(problem, problem.objectives[0], backend, use_models=use_models)
    if not result.feasible:
        return None
    values = dict(zip(problem.x, result.x))  # type: ignore[arg-type]
    open_set = {i for i, v in enumerate(y) if values[v]}
    assignment: Dict[int, int] = {}
    for j in range(len(assign_costs[0]) if assign_costs else 0):
        serving = [i for i in range(len(open_costs)) if values[x[i][j]]]
        assignment[j] = min(serving, key=lambda i: assign_costs[i][j])
    return UFLResult(result.value or 0, open_set, assignment, result.calls)


def set_cover_to_ufl(universe_size: int, sets: Sequence[Set[int]], k: int
                     ) -> Tuple[List[int], List[List[int]]]:
    """NP-Härte (Satz ``satz:ufl``): Set Cover mit Budget ``k`` → UFL-Instanz.

    ``f_i = 1``, ``c_{ij} = 0`` falls ``j ∈ S_i``, sonst ``k+1``. Kosten ``≤ k`` ⇔ Überdeckung
    der Größe ``≤ k``.
    """
    open_costs = [1] * len(sets)
    assign = [[0 if j in s else k + 1 for j in range(universe_size)] for s in sets]
    return open_costs, assign
