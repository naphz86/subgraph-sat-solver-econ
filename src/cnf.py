"""CNF-Formeln, DIMACS und Konversion nach 3-CNF.

Grundlage ist Kapitel 2 der Arbeit "Wirtschaftliche Konsequenzen eines effizienten
SAT-Solvers". Die *Größe* |φ| einer Formel ist dort die Gesamtzahl der
Literalvorkommen (Summe der Klausellängen), siehe :attr:`Cnf.size`.

Literale sind von 0 verschiedene ganze Zahlen (DIMACS-Konvention): ``+v`` ist die
Variable ``v``, ``-v`` ihre Negation. Eine Belegung ist ein ``dict[int, bool]``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

Assignment = Dict[int, bool]
Clause = Tuple[int, ...]


class DimacsError(ValueError):
    """Ungültige DIMACS-Eingabe."""


@dataclass
class Cnf:
    """Formel in konjunktiver Normalform über den Variablen ``1..num_vars``."""

    num_vars: int = 0
    clauses: List[Clause] = field(default_factory=list)

    # ------------------------------------------------------------------ Aufbau
    def new_var(self) -> int:
        """Legt eine frische Variable an und gibt ihre Nummer zurück."""
        self.num_vars += 1
        return self.num_vars

    def new_vars(self, n: int) -> List[int]:
        """Legt ``n`` frische Variablen an."""
        return [self.new_var() for _ in range(n)]

    def add_clause(self, *literals: int) -> None:
        """Fügt eine Klausel hinzu. Die leere Klausel ist erlaubt (unerfüllbar)."""
        for lit in literals:
            if lit == 0 or abs(lit) > self.num_vars:
                raise ValueError(
                    f"Literal {lit} ungültig für {self.num_vars} Variablen"
                )
        self.clauses.append(tuple(literals))

    def copy(self) -> "Cnf":
        return Cnf(self.num_vars, list(self.clauses))

    # --------------------------------------------------------------- Kennzahlen
    @property
    def size(self) -> int:
        """|φ|: Gesamtzahl der Literalvorkommen."""
        return sum(len(c) for c in self.clauses)

    @property
    def num_clauses(self) -> int:
        return len(self.clauses)

    def is_3cnf(self) -> bool:
        return all(len(c) <= 3 for c in self.clauses)

    # ----------------------------------------------------------- Auswertung
    def evaluate(self, assignment: Mapping[int, bool]) -> bool:
        """Wertet die Formel unter einer *vollständigen* Belegung aus."""
        for clause in self.clauses:
            if not any(_lit_value(lit, assignment) for lit in clause):
                return False
        return True

    def restrict(self, fixed: Mapping[int, bool]) -> "Cnf":
        """Substitution ``φ[x:=v]`` (Satz ``satz:selfred``).

        Klauseln mit wahrem Literal entfallen, falsche Literale werden gestrichen.
        Eine leere Klausel bleibt stehen und macht die Formel unerfüllbar. Die
        Variablenzahl bleibt unverändert, die Größe wächst nie.
        """
        result = Cnf(self.num_vars)
        for clause in self.clauses:
            satisfied = False
            reduced: List[int] = []
            for lit in clause:
                var = abs(lit)
                if var in fixed:
                    if (lit > 0) == fixed[var]:
                        satisfied = True
                        break
                else:
                    reduced.append(lit)
            if not satisfied:
                result.clauses.append(tuple(reduced))
        return result

    # ----------------------------------------------------------------- DIMACS
    def to_dimacs(self) -> str:
        lines = ["c erzeugt von subgraph_sat_wirtschaft",
                 f"p cnf {self.num_vars} {len(self.clauses)}"]
        for clause in self.clauses:
            lines.append(" ".join(str(l) for l in clause) + (" " if clause else "") + "0")
        return "\n".join(lines) + "\n"

    @classmethod
    def from_dimacs(cls, text: str) -> "Cnf":
        """Liest DIMACS-CNF. Klauseln dürfen sich über Zeilen erstrecken."""
        cnf: Optional[Cnf] = None
        declared = -1
        current: List[int] = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("c"):
                continue
            if line.startswith("%"):  # Terminator mancher Benchmark-Dateien
                break
            if line.startswith("p"):
                parts = line.split()
                if len(parts) != 4 or parts[1] != "cnf":
                    raise DimacsError(f"Ungültige Kopfzeile: {line!r}")
                try:
                    cnf = cls(int(parts[2]))
                    declared = int(parts[3])
                except ValueError as exc:
                    raise DimacsError(f"Ungültige Kopfzeile: {line!r}") from exc
                continue
            if cnf is None:
                raise DimacsError("Klausel vor der Kopfzeile")
            for token in line.split():
                try:
                    lit = int(token)
                except ValueError as exc:
                    raise DimacsError(f"Ungültiges Literal: {token!r}") from exc
                if lit == 0:
                    cnf.add_clause(*current)
                    current = []
                else:
                    current.append(lit)
        if cnf is None:
            raise DimacsError("Kopfzeile 'p cnf' fehlt")
        if current:
            raise DimacsError("Letzte Klausel nicht mit 0 abgeschlossen")
        if declared != len(cnf.clauses):
            raise DimacsError(
                f"Kopfzeile kündigt {declared} Klauseln an, gefunden {len(cnf.clauses)}"
            )
        return cnf

    # ----------------------------------------------------------------- 3-CNF
    def to_3cnf(self) -> "Cnf":
        """Erfüllbarkeitsäquivalente 3-CNF (Lemma ``lem:3cnf``).

        Eine Klausel ``(l1 ∨ … ∨ lk)`` mit ``k ≥ 4`` wird durch
        ``(l1 ∨ l2 ∨ z1) ∧ (¬z1 ∨ l3 ∨ z2) ∧ … ∧ (¬z_{k-3} ∨ l_{k-1} ∨ lk)`` ersetzt
        (``k-2`` Klauseln mit frischen Variablen). Klauseln der Länge ≤ 3 bleiben
        unverändert. Es entstehen höchstens ``N`` Klauseln und ``3N`` Literale.
        """
        result = Cnf(self.num_vars)
        for clause in self.clauses:
            k = len(clause)
            if k <= 3:
                result.clauses.append(clause)
                continue
            z_prev = result.new_var()
            result.clauses.append((clause[0], clause[1], z_prev))
            for lit in clause[2:-2]:
                z_next = result.new_var()
                result.clauses.append((-z_prev, lit, z_next))
                z_prev = z_next
            result.clauses.append((-z_prev, clause[-2], clause[-1]))
        return result


def _lit_value(lit: int, assignment: Mapping[int, bool]) -> bool:
    value = assignment[abs(lit)]
    return value if lit > 0 else not value


def complete_assignment(cnf: Cnf, assignment: Mapping[int, bool]) -> Assignment:
    """Ergänzt fehlende Variablen mit ``False``."""
    return {v: bool(assignment.get(v, False)) for v in range(1, cnf.num_vars + 1)}


def enumerate_assignments(num_vars: int) -> Iterable[Assignment]:
    """Alle ``2**num_vars`` Belegungen (nur für kleine Tests/Referenzen gedacht)."""
    for mask in range(1 << num_vars):
        yield {v: bool((mask >> (v - 1)) & 1) for v in range(1, num_vars + 1)}
