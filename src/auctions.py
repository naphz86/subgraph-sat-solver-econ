"""Kombinatorische Auktionen und VCG-Mechanismus (Kapitel 4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple

from .backends import SatBackend
from .cnf import Cnf
from .foundation import Problem, maximize
from .reduction import Graph, clique_number, subgraph_instance_json


@dataclass(frozen=True)
class Bid:
    """Gebot ``(S_j, p_j)``; ``agent`` für die XOR-Bietersprache (höchstens ein Gebot je Agent)."""

    items: FrozenSet[int]
    price: int
    agent: Optional[int] = None

    def __post_init__(self) -> None:
        if self.price < 0:
            raise ValueError("Preise müssen nichtnegativ sein")
        object.__setattr__(self, "items", frozenset(self.items))


def conflicting_pairs(bids: Sequence[Bid], xor_agents: bool = False) -> List[Tuple[int, int]]:
    """Paare ``j<k`` mit ``S_j ∩ S_k ≠ ∅`` (bei ``xor_agents`` auch Gebote desselben Agenten)."""
    pairs = []
    for j in range(len(bids)):
        for k in range(j + 1, len(bids)):
            clash = bool(bids[j].items & bids[k].items)
            same_agent = xor_agents and bids[j].agent is not None and bids[j].agent == bids[k].agent
            if clash or same_agent:
                pairs.append((j, k))
    return pairs


def is_feasible(bids: Sequence[Bid], winners: Iterable[int], xor_agents: bool = False) -> bool:
    chosen = sorted(set(winners))
    bad = set(conflicting_pairs(bids, xor_agents))
    return not any((j, k) in bad for i, j in enumerate(chosen) for k in chosen[i + 1:])


def revenue(bids: Sequence[Bid], winners: Iterable[int]) -> int:
    return sum(bids[j].price for j in set(winners))


# ----------------------------------------------------------------- SAT-Kodierung


def wdp_problem(bids: Sequence[Bid], xor_agents: bool = False) -> Tuple[Problem, List[int]]:
    """SAT-Kodierung mit binären Preisen (Satz ``satz:wdp-sat``).

    Variablen ``y_j`` (Gebot ``j`` gewinnt); Klauseln ``(¬y_j ∨ ¬y_k)`` für Konflikte;
    Erlösschaltkreis ``Σ p_j·y_j`` (Summierer). Gibt das Problem und das Erlöswort zurück
    (Zielwort ist ``problem.objectives[0]``).
    """
    problem = Problem(len(bids))
    y = problem.x
    for j, k in conflicting_pairs(bids, xor_agents):
        problem.cnf.add_clause(-y[j], -y[k])
    word = problem.cb.weighted_sum(y, [b.price for b in bids])
    problem.add_objective(word)
    return problem, word


def encode_wdp(bids: Sequence[Bid], bound: int, xor_agents: bool = False) -> Cnf:
    """Die CNF ``φ_B``: erfüllbar ⇔ Erlös ``≥ B`` erreichbar (Satz ``satz:wdp-sat``)."""
    problem, word = wdp_problem(bids, xor_agents)
    cb = problem.cb
    cb.assert_true(cb.ge_const(word, bound))
    return problem.cnf


@dataclass
class WDPResult:
    revenue: int
    winners: List[int]
    calls: int


def solve_wdp(bids: Sequence[Bid], backend: SatBackend, xor_agents: bool = False,
              *, use_models: bool = False) -> WDPResult:
    """Optimaler Erlös und Gewinnerset mit ``≤ L'+n+2`` Entscheideraufrufen."""
    problem, word = wdp_problem(bids, xor_agents)
    result = maximize(problem, word, backend, use_models=use_models)
    winners = [j for j, w in enumerate(result.x or []) if w]
    return WDPResult(result.value or 0, winners, result.calls)


# ----------------------------------------------------------- WDP → Clique → Subgraph


def compatibility_graph(bids: Sequence[Bid]) -> Graph:
    """Kompatibilitätsgraph ``C`` (Satz ``satz:wdp-clique`` (a)): Kante ⇔ disjunkte Gebote."""
    g = Graph(len(bids))
    for j in range(len(bids)):
        for k in range(j + 1, len(bids)):
            if not (bids[j].items & bids[k].items):
                g.add_edge(j, k)
    return g


def twin_graph(bids: Sequence[Bid]) -> Tuple[Graph, List[int]]:
    """Zwillingsgraph ``C'`` für ganzzahlige Preise (Satz ``satz:wdp-clique`` (b)).

    Gebot ``j`` wird durch ``p_j`` Zwillinge ersetzt, die untereinander eine Clique bilden
    und mit allen Zwillingen kompatibler Gebote verbunden sind. Gibt den Graphen und die
    Zuordnung Knoten → Gebot zurück.
    """
    owner = [j for j, b in enumerate(bids) for _ in range(b.price)]
    g = Graph(len(owner))
    for u in range(len(owner)):
        for v in range(u + 1, len(owner)):
            ju, jv = owner[u], owner[v]
            if ju == jv or not (bids[ju].items & bids[jv].items):
                g.add_edge(u, v)
    return g, owner


def max_revenue_via_clique(bids: Sequence[Bid]) -> int:
    """Maximaler Erlös = größte Clique im Zwillingsgraphen (pseudopolynomiell)."""
    g, _ = twin_graph(bids)
    return clique_number(g)


def revenue_at_least_via_subgraph(bids: Sequence[Bid], k: int) -> bool:
    """Einheitspreise: Erlös ``≥ k`` ⇔ ``K_k ⊑ C`` (Satz ``satz:wdp-clique`` (a))."""
    from .oracle import find_embedding

    g = compatibility_graph(bids)
    return find_embedding(g.adj, Graph.complete(k).adj) is not None


def auction_subgraph_instance(bids: Sequence[Bid], k: int) -> str:
    """JSON-Eingabe ``{"G": C, "H": K_k}`` für das Subgraph-Programm (Beispiel der Arbeit)."""
    return subgraph_instance_json(compatibility_graph(bids), Graph.complete(k))


def independent_set_to_wdp(num_vertices: int, edges: Sequence[Tuple[int, int]]) -> List[Bid]:
    """NP-Härte (Satz ``satz:wdp-np``): Independent Set → WDP mit Einheitspreisen.

    Güter: ein Gut je Kante und ein privates Gut je Knoten; das Gebot von ``v`` umfasst
    seine Kanten und sein privates Gut. Zwei Gebote kollidieren genau bei adjazenten Knoten.
    """
    incident: Dict[int, set] = {v: set() for v in range(num_vertices)}
    for e, (u, v) in enumerate(edges):
        incident[u].add(e)
        incident[v].add(e)
    return [
        Bid(frozenset(incident[v] | {len(edges) + v}), 1)
        for v in range(num_vertices)
    ]


# ------------------------------------------------------------------------------ VCG


@dataclass
class VCGResult:
    winners: List[int]
    welfare: int
    values: Dict[int, int]          # Wert jedes Agenten im Ergebnis ω*
    payments: Dict[int, int]        # Zahlungen t_i
    optimizations: int
    calls: int = 0


def vcg(bids: Sequence[Bid], backend: SatBackend, *, use_models: bool = False) -> VCGResult:
    """VCG-Mechanismus in der XOR-Bietersprache mit ``N+1`` WDP-Optimierungen
    (Sätze ``satz:vcg`` und ``satz:vcg-comp``).

    ``t_i = max_ω Σ_{j≠i} v_j(ω) − Σ_{j≠i} v_j(ω*)``.
    """
    if any(b.agent is None for b in bids):
        raise ValueError("VCG benötigt für jedes Gebot einen Agenten")
    agents = sorted({b.agent for b in bids})  # type: ignore[type-var]
    full = solve_wdp(bids, backend, xor_agents=True, use_models=use_models)
    calls = full.calls
    values = {a: 0 for a in agents}
    for j in full.winners:
        values[bids[j].agent] += bids[j].price  # type: ignore[index]
    payments: Dict[int, int] = {}
    for a in agents:
        others = [b for b in bids if b.agent != a]
        without = solve_wdp(others, backend, xor_agents=True, use_models=use_models)
        calls += without.calls
        payments[a] = without.revenue - (full.revenue - values[a])
    return VCGResult(full.winners, full.revenue, values, payments, len(agents) + 1, calls)
