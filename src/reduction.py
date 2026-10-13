"""Reduktionskette 3-SAT → Clique → Subgraph in Python (Referenzimplementierung).

Entspricht der Konstruktion der Grundarbeit und des C++-Solvers: ein Knoten je
Literalvorkommen ``(Klausel, Position)``, Kanten zwischen Knoten *verschiedener*
Klauseln mit nicht widersprüchlichen Literalen; ``φ`` erfüllbar ⇔ ``K_m ⊑ G_φ``.
Die JSON-Serialisierung ist bitgleich zum Format des C++-Solvers (Knoten ``v0, v1, …``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .cnf import Assignment, Cnf


class Graph:
    """Einfacher ungerichteter Graph auf den Knoten ``0..n-1``."""

    def __init__(self, n: int = 0) -> None:
        self.n = n
        self.adj: List[Set[int]] = [set() for _ in range(n)]

    def add_edge(self, u: int, v: int) -> None:
        if u == v:
            return
        if not (0 <= u < self.n and 0 <= v < self.n):
            raise IndexError("Knoten außerhalb des Bereichs")
        self.adj[u].add(v)
        self.adj[v].add(u)

    def has_edge(self, u: int, v: int) -> bool:
        return 0 <= u < self.n and 0 <= v < self.n and v in self.adj[u]

    def edges(self) -> List[Tuple[int, int]]:
        return [(u, v) for u in range(self.n) for v in sorted(self.adj[u]) if u < v]

    @property
    def num_edges(self) -> int:
        return sum(len(a) for a in self.adj) // 2

    def to_dict(self) -> dict:
        return {
            "nodes": [f"v{i}" for i in range(self.n)],
            "edges": [[f"v{u}", f"v{v}"] for u, v in self.edges()],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def complete(cls, k: int) -> "Graph":
        """Vollständiger Graph ``K_k``."""
        g = cls(k)
        for u in range(k):
            for v in range(u + 1, k):
                g.add_edge(u, v)
        return g


def subgraph_instance_json(source: Graph, target: Graph) -> str:
    """Eingabe des Subgraph-Programms ``{"G": Quelle, "H": Ziel}``."""
    return json.dumps({"G": source.to_dict(), "H": target.to_dict()})


@dataclass
class CliqueReduction:
    """Ergebnis von :func:`sat_to_clique`."""

    cnf3: Cnf                      # die 3-CNF, auf der der Graph beruht
    graph: Graph                   # Clique-Graph G_φ
    k: int                         # gesuchte Cliquengröße (= Klauselzahl)
    nodes: List[Tuple[int, int]]   # Knoten i ↔ (Klausel, Literalposition)
    num_original_vars: int

    @property
    def target(self) -> Graph:
        return Graph.complete(self.k)


def three_sat_to_clique(cnf3: Cnf, num_original_vars: Optional[int] = None) -> CliqueReduction:
    """Clique-Graph einer 3-CNF (Satz "3-SAT auf Clique" der Grundarbeit)."""
    if not cnf3.is_3cnf():
        raise ValueError("Formel muss eine 3-CNF sein")
    nodes = [(c, p) for c, clause in enumerate(cnf3.clauses) for p in range(len(clause))]
    g = Graph(len(nodes))
    for i, (ci, pi) in enumerate(nodes):
        li = cnf3.clauses[ci][pi]
        for j in range(i + 1, len(nodes)):
            cj, pj = nodes[j]
            if ci != cj and li != -cnf3.clauses[cj][pj]:
                g.add_edge(i, j)
    return CliqueReduction(
        cnf3, g, len(cnf3.clauses), nodes,
        cnf3.num_vars if num_original_vars is None else num_original_vars,
    )


def sat_to_clique(cnf: Cnf) -> CliqueReduction:
    """Beliebige CNF → 3-CNF → Clique-Graph (Lemma ``lem:3cnf`` + Grundarbeit)."""
    cnf3 = cnf.to_3cnf()
    return three_sat_to_clique(cnf3, cnf.num_vars)


def extract_assignment(red: CliqueReduction, mapping: Sequence[int]) -> Assignment:
    """Belegung aus einer ``K_m``-Einbettung: das gewählte Literal wird wahr.

    Nicht festgelegte Variablen erhalten ``False``. Die Belegung ist auf die
    ursprünglichen Variablen eingeschränkt (Lemma ``lem:3cnf``).
    """
    values: Dict[int, bool] = {}
    for node in mapping:
        clause, pos = red.nodes[node]
        lit = red.cnf3.clauses[clause][pos]
        values.setdefault(abs(lit), lit > 0)
    return {v: values.get(v, False) for v in range(1, red.num_original_vars + 1)}


def clique_number(g: Graph) -> int:
    """Größe einer größten Clique (exakt, über wiederholte Cliquensuche)."""
    from .oracle import find_clique

    best = 0
    while find_clique(g.adj, best + 1) is not None:
        best += 1
    return best


def max_clique(g: Graph) -> List[int]:
    """Eine größte Clique von ``g`` (exakt)."""
    from .oracle import find_clique

    best: List[int] = []
    while True:
        found = find_clique(g.adj, len(best) + 1)
        if found is None:
            return best
        best = found
