"""DPLL SAT solver utilities.

The implementation is intentionally small and explicit to support the economics models and to
allow unit tests to validate the algebraic properties of SAT reductions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class SATResult:
    satisfiable: bool
    assignment: Dict[int, bool]
    explanation: str = ""


def _clause_is_satisfied(clause: Sequence[int], assignment: Dict[int, bool]) -> Optional[bool]:
    unassigned = False
    for literal in clause:
        variable = abs(literal)
        value = assignment.get(variable)
        if value is None:
            unassigned = True
            continue
        if literal > 0 and value:
            return True
        if literal < 0 and not value:
            return True
    if not unassigned:
        return False
    return None


def _simplify(clauses: Sequence[Sequence[int]], assignment: Dict[int, bool]) -> List[Tuple[int, ...]]:
    simplified: List[Tuple[int, ...]] = []
    for clause in clauses:
        result = _clause_is_satisfied(clause, assignment)
        if result is True:
            continue
        if result is False:
            return []
        reduced = tuple(literal for literal in clause if abs(literal) not in assignment)
        if reduced:
            simplified.append(reduced)
    return simplified


def _dpll(clauses: Sequence[Sequence[int]], assignment: Optional[Dict[int, bool]] = None) -> Optional[Dict[int, bool]]:
    assignment = {} if assignment is None else dict(assignment)
    simplified = _simplify(clauses, assignment)
    if not simplified:
        return assignment
    if any(len(clause) == 0 for clause in simplified):
        return None

    unit_literals = [clause[0] for clause in simplified if len(clause) == 1]
    if unit_literals:
        literal = unit_literals[0]
        variable = abs(literal)
        assignment[variable] = literal > 0
        return _dpll(clauses, assignment)

    literal = next(iter(simplified[0]))
    variable = abs(literal)
    for positive in (True, False):
        trial = dict(assignment)
        trial[variable] = positive
        solved = _dpll(clauses, trial)
        if solved is not None:
            return solved
    return None


def solve_cnf(clauses: Sequence[Sequence[int]]) -> SATResult:
    """Solve a CNF formula via a small DPLL procedure."""
    normalized = [tuple(int(literal) for literal in clause) for clause in clauses if clause]
    if not normalized:
        return SATResult(satisfiable=True, assignment={}, explanation="empty formula")
    assignment = _dpll(normalized)
    if assignment is None:
        return SATResult(satisfiable=False, assignment={}, explanation="no satisfying assignment")
    return SATResult(satisfiable=True, assignment=assignment, explanation="satisfiable")


def solve_model(model: object) -> SATResult:
    clauses = getattr(model, "clauses", [])
    return solve_cnf(clauses)


def implication_check(antecedent: Iterable[str], consequent: Iterable[str], model: object) -> bool:
    for item in antecedent:
        if item not in getattr(model, "variables", {}):
            return False
    for item in consequent:
        if item not in getattr(model, "variables", {}):
            return False
    return solve_model(model).satisfiable
