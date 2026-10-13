"""Märkte mit Nebenbedingungen (Kapitel 5): Frequenzzuteilung (Station Repacking) und
Tauschmärkte (Nierenaustausch als Zyklenpackung)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Hashable, List, Mapping, Optional, Sequence, Set, Tuple

from .auctions import Bid, WDPResult, solve_wdp
from .backends import SatBackend
from .cnf import Cnf

Station = Hashable
Forbidden = Tuple[Station, int, Station, int]


@dataclass
class Repacking:
    """Repacking-Instanz: Kanalmengen ``D_s`` und verbotene Paare ``(s,c,s',c')``."""

    domains: Dict[Station, Sequence[int]]
    forbidden: Set[Forbidden] = field(default_factory=set)


def encode_repacking(rep: Repacking) -> Tuple[Cnf, Dict[Tuple[Station, int], int]]:
    """Kodierung nach Satz ``satz:repack``.

    Variablen ``x_{s,c}``; je Station mindestens und höchstens ein Kanal; je verbotenem
    Paar eine Konfliktklausel. Erfüllbar ⇔ zulässiges Repacking existiert.
    """
    cnf = Cnf()
    var: Dict[Tuple[Station, int], int] = {}
    for s, channels in rep.domains.items():
        for c in channels:
            var[(s, c)] = cnf.new_var()
    for s, channels in rep.domains.items():
        cnf.add_clause(*[var[(s, c)] for c in channels])
        chans = list(channels)
        for i in range(len(chans)):
            for j in range(i + 1, len(chans)):
                cnf.add_clause(-var[(s, chans[i])], -var[(s, chans[j])])
    for (s, c, t, d) in rep.forbidden:
        if (s, c) in var and (t, d) in var:
            cnf.add_clause(-var[(s, c)], -var[(t, d)])
    return cnf, var


def is_feasible_repacking(rep: Repacking, gamma: Mapping[Station, int]) -> bool:
    if set(gamma) != set(rep.domains):
        return False
    if any(gamma[s] not in rep.domains[s] for s in gamma):
        return False
    return not any(gamma.get(s) == c and gamma.get(t) == d for (s, c, t, d) in rep.forbidden)


def solve_repacking(rep: Repacking, backend: SatBackend) -> Optional[Dict[Station, int]]:
    """Zulässiges Repacking ``γ`` oder ``None``."""
    cnf, var = encode_repacking(rep)
    model = backend.solve(cnf)
    if model is None:
        return None
    gamma = {}
    for (s, c), v in var.items():
        if model[v]:
            gamma[s] = c
    return gamma


def coloring_to_repacking(num_vertices: int, edges: Sequence[Tuple[int, int]], k: int) -> Repacking:
    """NP-Härte (Satz ``satz:repack``): ``k``-Färbbarkeit als Repacking."""
    domains = {v: list(range(1, k + 1)) for v in range(num_vertices)}
    forbidden: Set[Forbidden] = set()
    for u, v in edges:
        for c in range(1, k + 1):
            forbidden.add((u, c, v, c))
    return Repacking(domains, forbidden)


# ------------------------------------------------------------------ Tauschmärkte


def cycles_up_to(num_vertices: int, arcs: Sequence[Tuple[int, int]], max_len: int) -> List[Tuple[int, ...]]:
    """Alle einfachen gerichteten Zyklen der Länge ``2..max_len`` (kanonisch: kleinster Knoten zuerst)."""
    out: Dict[int, List[int]] = {v: [] for v in range(num_vertices)}
    for u, v in set(arcs):
        if u != v:
            out[u].append(v)
    cycles: List[Tuple[int, ...]] = []

    def extend(start: int, path: List[int]) -> None:
        last = path[-1]
        for nxt in sorted(out[last]):
            if nxt == start and len(path) >= 2:
                cycles.append(tuple(path))
            elif nxt > start and nxt not in path and len(path) < max_len:
                extend(start, path + [nxt])

    for s in range(num_vertices):
        extend(s, [s])
    return cycles


def kidney_bids(num_vertices: int, arcs: Sequence[Tuple[int, int]], max_len: int,
                weights: Optional[Mapping[Tuple[int, int], int]] = None
                ) -> Tuple[List[Bid], List[Tuple[int, ...]]]:
    """Zyklenpackung als WDP (Satz ``satz:kidney``): Güter = Knoten, Gebot = Zyklus.

    Das Zyklengewicht ist die Summe der Kantengewichte (Standard 1 je Kante).
    """
    cycles = cycles_up_to(num_vertices, arcs, max_len)
    bids = []
    for cyc in cycles:
        cycle_arcs = [(cyc[i], cyc[(i + 1) % len(cyc)]) for i in range(len(cyc))]
        w = sum((weights or {}).get(a, 1) for a in cycle_arcs)
        bids.append(Bid(frozenset(cyc), w))
    return bids, cycles


@dataclass
class KidneyResult:
    value: int
    cycles: List[Tuple[int, ...]]
    calls: int


def solve_kidney(num_vertices: int, arcs: Sequence[Tuple[int, int]], max_len: int,
                 backend: SatBackend, weights: Optional[Mapping[Tuple[int, int], int]] = None,
                 *, use_models: bool = False) -> KidneyResult:
    """Optimaler Austausch (knotendisjunkte Zyklen der Länge ``≤ ℓ``)."""
    bids, cycles = kidney_bids(num_vertices, arcs, max_len, weights)
    result: WDPResult = solve_wdp(bids, backend, use_models=use_models)
    return KidneyResult(result.revenue, [cycles[j] for j in result.winners], result.calls)
