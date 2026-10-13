"""SAT-Entscheider (*Backends*) mit einheitlicher Schnittstelle.

Alle wirtschaftlichen Kodierungen sprechen nur diese Schnittstelle an. Dadurch lässt
sich derselbe Algorithmus mit dem Subgraph-SAT-Solver (C++-Bibliothek über den Shim,
siehe :mod:`native`), mit der Python-Referenzkette oder mit einem unabhängigen
Entscheider (DPLL, Enumeration) ausführen, wie es der Messplan der Arbeit verlangt.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from .cnf import Assignment, Cnf, complete_assignment, enumerate_assignments
from .oracle import find_embedding
from .reduction import extract_assignment, sat_to_clique


class BackendError(RuntimeError):
    """Der Entscheider konnte keine verlässliche Antwort liefern."""


class SatBackend(ABC):
    """Entscheider ``E_T``: liefert eine Belegung oder ``None`` (unerfüllbar)."""

    @abstractmethod
    def solve(self, cnf: Cnf) -> Optional[Assignment]:
        """Erfüllende Belegung aller Variablen ``1..cnf.num_vars`` oder ``None``."""

    def is_sat(self, cnf: Cnf) -> bool:
        """Nur die Entscheidung (kein Modell verwendet)."""
        return self.solve(cnf) is not None


class CountingBackend(SatBackend):
    """Zählt die Aufrufe (Nachweis der Aufrufschranken der Arbeit)."""

    def __init__(self, inner: SatBackend) -> None:
        self.inner = inner
        self.calls = 0

    def solve(self, cnf: Cnf) -> Optional[Assignment]:
        self.calls += 1
        return self.inner.solve(cnf)


class DecisionOnlyBackend(SatBackend):
    """Gibt nur Ja/Nein preis: das Modell des inneren Entscheiders wird verworfen.

    Damit lässt sich prüfen, dass Algorithmen (Selbstreduzierbarkeit, Optimierung)
    wirklich nur mit einem *Entscheider* auskommen (Satz ``satz:selfred``).
    """

    def __init__(self, inner: SatBackend) -> None:
        self.inner = inner
        self.calls = 0

    def solve(self, cnf: Cnf) -> Optional[Assignment]:
        raise BackendError("DecisionOnlyBackend liefert keine Modelle")

    def is_sat(self, cnf: Cnf) -> bool:
        self.calls += 1
        return self.inner.is_sat(cnf)


class BruteForceBackend(SatBackend):
    """Vollständige Enumeration; unabhängige Referenz für kleine Formeln."""

    MAX_VARS = 22

    def solve(self, cnf: Cnf) -> Optional[Assignment]:
        if cnf.num_vars > self.MAX_VARS:
            raise BackendError(f"zu viele Variablen für Enumeration: {cnf.num_vars}")
        for assignment in enumerate_assignments(cnf.num_vars):
            if cnf.evaluate(assignment):
                return assignment
        return None


class DpllBackend(SatBackend):
    """DPLL mit Einheitspropagation (2 überwachte Literale), iterativ.

    Unabhängig von der Subgraph-Kette; dient als Referenzentscheider ("CDCL-Rolle"
    im Messplan) und als schneller Standard für die Tests der Kodierungen.
    Entscheidungsvariablen werden in aufsteigender Nummer belegt (zuerst ``False``);
    bei Tseitin-Formeln sind das die Eingänge, der Rest folgt durch Propagation.
    """

    def solve(self, cnf: Cnf) -> Optional[Assignment]:
        n = cnf.num_vars
        clauses: List[List[int]] = []
        for clause in cnf.clauses:
            lits = list(dict.fromkeys(clause))
            if any(-l in lits for l in lits):
                continue  # Tautologie
            if not lits:
                return None
            clauses.append(lits)

        value = [0] * (n + 1)  # 0 offen, 1 wahr, -1 falsch (Wert der Variablen)
        trail: List[int] = []
        watches: Dict[int, List[int]] = {}
        units: List[int] = []
        for idx, lits in enumerate(clauses):
            if len(lits) == 1:
                units.append(lits[0])
            else:
                watches.setdefault(lits[0], []).append(idx)
                watches.setdefault(lits[1], []).append(idx)

        def lit_value(lit: int) -> int:
            v = value[abs(lit)]
            return v if lit > 0 else -v

        def assign(lit: int) -> None:
            value[abs(lit)] = 1 if lit > 0 else -1
            trail.append(lit)

        def propagate(head: int) -> int:
            """Propagiert ab ``head``; gibt neuen Kopf oder ``-1`` bei Konflikt zurück."""
            while head < len(trail):
                false_lit = -trail[head]
                head += 1
                pending = watches.get(false_lit, [])
                kept: List[int] = []
                conflict = False
                for pos, idx in enumerate(pending):
                    if conflict:
                        kept.append(idx)
                        continue
                    lits = clauses[idx]
                    if lits[0] == false_lit:
                        lits[0], lits[1] = lits[1], lits[0]
                    # lits[1] == false_lit
                    if lit_value(lits[0]) == 1:
                        kept.append(idx)
                        continue
                    moved = False
                    for j in range(2, len(lits)):
                        if lit_value(lits[j]) != -1:
                            lits[1], lits[j] = lits[j], lits[1]
                            watches.setdefault(lits[1], []).append(idx)
                            moved = True
                            break
                    if moved:
                        continue
                    kept.append(idx)
                    if lit_value(lits[0]) == -1:
                        conflict = True
                    else:
                        assign(lits[0])
                watches[false_lit] = kept
                if conflict:
                    return -1
            return head

        for u in units:
            current = lit_value(u)
            if current == -1:
                return None
            if current == 0:
                assign(u)
        head = propagate(0)
        if head < 0:
            return None

        decisions: List[List[int]] = []  # [Trail-Position, Literal, schon umgedreht]
        start = 1
        while True:
            while start <= n and value[start] != 0:
                start += 1
            if start > n:
                return {v: value[v] == 1 for v in range(1, n + 1)}
            decisions.append([len(trail), -start, 0])
            assign(-start)
            while True:
                head = propagate(head)
                if head >= 0:
                    break
                # Konflikt: zurück zur letzten noch nicht umgedrehten Entscheidung
                while decisions:
                    pos, lit, flipped = decisions.pop()
                    for undone in trail[pos:]:
                        value[abs(undone)] = 0
                        start = min(start, abs(undone))
                    del trail[pos:]
                    head = pos
                    if not flipped:
                        decisions.append([pos, -lit, 1])
                        assign(-lit)
                        break
                else:
                    return None


class ChainBackend(SatBackend):
    """Python-Referenz der Kette CNF → 3-CNF → Clique → Subgraph (exaktes Orakel).

    Gleiche Konstruktion wie der C++-Solver, aber ohne externen Prozess. Jede
    Antwort wird gegen die ursprüngliche Formel validiert (Messplan, Punkt 2).
    """

    def solve(self, cnf: Cnf) -> Optional[Assignment]:
        red = sat_to_clique(cnf)
        mapping = find_embedding(red.graph.adj, red.target.adj)
        if mapping is None:
            return None
        model = extract_assignment(red, mapping)
        if not cnf.evaluate(model):
            raise BackendError("Extrahierte Belegung erfüllt die Formel nicht")
        return model


def validated(cnf: Cnf, model: Optional[Assignment]) -> Optional[Assignment]:
    """Prüft ein Modell gegen die Formel und ergänzt fehlende Variablen."""
    if model is None:
        return None
    full = complete_assignment(cnf, model)
    if not cnf.evaluate(full):
        raise BackendError("Modell erfüllt die Formel nicht")
    return full
