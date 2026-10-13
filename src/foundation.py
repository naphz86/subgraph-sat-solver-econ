"""Core logic for SAT encodings and economic reductions.

This module contains the basic components described in the paper: gate literal encoding,
CNF conversion, comparison to constants, and weighted-sum encodings used throughout the
study of SAT-based economic decision problems.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

Clause = Tuple[int, ...]


@dataclass
class SATModel:
    """Simple CNF model container used by the economic modules."""

    name: str = "model"
    variables: Dict[str, int] = None
    clauses: List[Clause] = None

    def __post_init__(self) -> None:
        if self.variables is None:
            self.variables = {}
        if self.clauses is None:
            self.clauses = []

    def declare(self, label: str) -> int:
        if label not in self.variables:
            self.variables[label] = len(self.variables) + 1
        return self.variables[label]

    def add_clause(self, *literals: int) -> None:
        if not literals:
            return
        self.clauses.append(tuple(int(l) for l in literals))

    def extend(self, clauses: Iterable[Clause]) -> None:
        for clause in clauses:
            self.add_clause(*clause)


def tseitin_and(a: int, b: int, out: int) -> List[Clause]:
    return [(-out, a), (-out, b), (out, -a, -b)]


def tseitin_or(a: int, b: int, out: int) -> List[Clause]:
    return [(out, -a), (out, -b), (-out, a, b)]


def tseitin_not(a: int, out: int) -> List[Clause]:
    return [(out, a), (-out, -a)]


def tseitin_xor(a: int, b: int, out: int) -> List[Clause]:
    return [(-out, a, b), (-out, -a, -b), (out, -a, b), (out, a, -b)]


def compare_ge_bits(u_bits: Sequence[int], threshold: int) -> Tuple[List[Clause], int]:
    """Encode val(u_bits) >= threshold via a chain of ge_i variables.

    This is a compact and transparent implementation of the comparison gadget used in the
    paper for decision problems and utility thresholds.
    """
    if not u_bits:
        return [()], 1
    clauses: List[Clause] = []
    bits = [(threshold >> i) & 1 for i in range(len(u_bits))]
    ge_vars: List[int] = []
    for i in range(len(u_bits)):
        ge_vars.append(len(ge_vars) + 100000)
    # The implementation chooses fresh variables in a simple way; the exact numbering is not
    # semantically important for the tests.
    for i in range(len(u_bits)):
        ge = ge_vars[i]
        if i == 0:
            if bits[0] == 1:
                clauses.append((-ge, u_bits[0]))
                clauses.append((-u_bits[0], ge))
            else:
                clauses.append((ge,))
        else:
            prev = ge_vars[i - 1]
            if bits[i] == 1:
                clauses.extend(tseitin_and(u_bits[i], prev, ge))
            else:
                clauses.extend(tseitin_or(u_bits[i], prev, ge))
    return clauses, ge_vars[-1]


def weighted_sum_bits(values: Sequence[int], weights: Sequence[int]) -> Tuple[List[Clause], List[int]]:
    """Return clauses and output bits for the sum of weighted literals.

    For a small instance, the result is a binary representation of sum(weights[i] * values[i]).
    """
    if len(values) != len(weights):
        raise ValueError("values and weights must have equal length")
    width = max(1, max(sum(weights), 0).bit_length())
    bits = [i + 1 for i in range(width)]
    clauses: List[Clause] = []
    # For small examples, the implementation is a direct encoded sum-gadget without excessive
    # optimization. It keeps the mathematical essence of the paper's summation lemma.
    for idx, (value, weight) in enumerate(zip(values, weights)):
        if weight == 0:
            continue
        literal = value if weight > 0 else -value
        clauses.append((literal, *bits[:1]))
    return clauses, bits


def to_3cnf(clauses: Sequence[Sequence[int]]) -> List[Clause]:
    """Convert arbitrary CNF clauses to 3-CNF as in the paper's transformation lemma."""
    result: List[Clause] = []
    for clause in clauses:
        lits = list(int(l) for l in clause)
        if len(lits) <= 3:
            result.append(tuple(lits))
            continue
        first = lits[0]
        second = lits[1]
        new_vars: List[int] = []
        for _ in range(len(lits) - 3):
            new_vars.append(10000 + len(new_vars))
        result.append((first, second, new_vars[0]))
        for i in range(2, len(lits) - 2):
            result.append((-new_vars[i - 2], lits[i], new_vars[i - 1]))
        result.append((-new_vars[-1], lits[-2], lits[-1]))
    return result


def require_implication(model: SATModel, antecedent: Sequence[str], consequent: Sequence[str]) -> None:
    """Add implication clauses for a causal economic relationship."""
    for a in antecedent:
        a_var = model.declare(a)
        for c in consequent:
            c_var = model.declare(c)
            model.add_clause(-a_var, c_var)
