"""Exaktes Subgraph-Orakel (ExactSubgraph) mit der Schnittstelle des SAT-Solvers.

Der C++-Solver ruft ein externes Programm als ``<programm> <input.json> <output.json>``
auf. ``input.json`` enthält ``{"G": {...}, "H": {...}}`` (Quell- und Zielgraph mit
``nodes`` und ``edges``). Das Programm schreibt ``{"is_subgraph": true, "mapping": [...]}``
bzw. ``{"is_subgraph": false}``. ``mapping[i]`` ist der Index (Position in
``G.nodes``) des Quellknotens, auf den der i-te Knoten von ``H`` abgebildet wird.

Dieses Modul benötigt ausschließlich die Standardbibliothek. Gesucht wird eine
injektive, kantenerhaltende Abbildung ``H → G`` (nicht notwendig induziert), wie in
der Grundarbeit gefordert. Das Orakel ist *exakt*: Antworten sind nie heuristisch
(Grundarbeit, Abschnitt zur Orakel-Schnittstelle). Für vollständige Zielgraphen
``K_k`` (der Fall der Reduktionskette) wird eine Cliquensuche mit Bitmengen
verwendet, sonst ein Backtracking-Verfahren.

Zeitlimit: Umgebungsvariable ``SUBGRAPH_ORACLE_TIME_LIMIT`` (Sekunden). Bei
Überschreitung endet das Programm mit Exit-Code 3, der Solver meldet dann
``SAT_ERROR`` statt einer falschen Antwort.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Dict, List, Optional, Sequence, Set, Tuple

EXIT_OK = 0
EXIT_BAD_INPUT = 2
EXIT_TIMEOUT = 3


class OracleTimeout(Exception):
    """Zeitlimit des Orakels überschritten."""


class _Deadline:
    def __init__(self, seconds: Optional[float]) -> None:
        self.limit = None if seconds is None else time.monotonic() + seconds
        self.ticks = 0

    def check(self) -> None:
        self.ticks += 1
        if self.limit is not None and self.ticks % 256 == 0 and time.monotonic() > self.limit:
            raise OracleTimeout()


def _masks(adj: Sequence[Set[int]]) -> List[int]:
    masks = []
    for neighbours in adj:
        m = 0
        for u in neighbours:
            m |= 1 << u
        masks.append(m)
    return masks


def _is_complete(adj: Sequence[Set[int]]) -> bool:
    n = len(adj)
    return all(len(adj[v] - {v}) == n - 1 for v in range(n))


def find_clique(adj: Sequence[Set[int]], k: int, deadline: Optional[_Deadline] = None) -> Optional[List[int]]:
    """Findet eine ``k``-Clique (Liste von Knotenindizes) oder ``None``."""
    if k < 0:
        raise ValueError("k muss nichtnegativ sein")
    if k == 0:
        return []
    deadline = deadline or _Deadline(None)
    n = len(adj)
    masks = _masks(adj)
    # k-Kern: Knoten mit Grad < k-1 können in keiner k-Clique liegen
    alive = (1 << n) - 1
    changed = True
    while changed:
        changed = False
        for v in range(n):
            if (alive >> v) & 1 and bin(masks[v] & alive).count("1") < k - 1:
                alive &= ~(1 << v)
                changed = True
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 4 * k + 1000))

    def search(cands: int, chosen: List[int]) -> Optional[List[int]]:
        deadline.check()
        if len(chosen) == k:
            return chosen
        while cands:
            if len(chosen) + bin(cands).count("1") < k:
                return None
            low = cands & -cands
            v = low.bit_length() - 1
            cands &= ~low
            found = search(cands & masks[v], chosen + [v])
            if found is not None:
                return found
        return None

    return search(alive, [])


def find_embedding(
    g_adj: Sequence[Set[int]],
    h_adj: Sequence[Set[int]],
    deadline: Optional[_Deadline] = None,
) -> Optional[List[int]]:
    """Exakte Subgraph-Suche ``H ⊑ G``: Abbildung ``H-Knoten → G-Knoten`` oder ``None``."""
    deadline = deadline or _Deadline(None)
    nh, ng = len(h_adj), len(g_adj)
    if nh > ng:
        return None
    if _is_complete(h_adj):
        return find_clique(g_adj, nh, deadline)

    g_masks = _masks(g_adj)
    g_deg = [len(a - {v}) for v, a in enumerate(g_adj)]
    h_deg = [len(a - {v}) for v, a in enumerate(h_adj)]
    # Reihenfolge: zusammenhängend wachsend, hohe Grade zuerst
    order: List[int] = []
    remaining = set(range(nh))
    while remaining:
        placed = set(order)
        start = max(remaining, key=lambda v: (len(h_adj[v] & placed), h_deg[v], -v))
        order.append(start)
        remaining.discard(start)
    mapping: Dict[int, int] = {}

    def search(i: int, used: int) -> bool:
        deadline.check()
        if i == nh:
            return True
        hv = order[i]
        cand = ((1 << ng) - 1) & ~used
        for hu in h_adj[hv]:
            if hu in mapping:
                cand &= g_masks[mapping[hu]]
        while cand:
            low = cand & -cand
            gv = low.bit_length() - 1
            cand &= ~low
            if g_deg[gv] < h_deg[hv]:
                continue
            mapping[hv] = gv
            if search(i + 1, used | low):
                return True
            del mapping[hv]
        return False

    sys.setrecursionlimit(max(sys.getrecursionlimit(), 4 * nh + 1000))
    if search(0, 0):
        return [mapping[v] for v in range(nh)]
    return None


def _parse_graph(obj: dict) -> Tuple[List[str], List[Set[int]]]:
    nodes = [str(x) for x in obj["nodes"]]
    index = {name: i for i, name in enumerate(nodes)}
    if len(index) != len(nodes):
        raise ValueError("doppelte Knotennamen")
    adj: List[Set[int]] = [set() for _ in nodes]
    for edge in obj["edges"]:
        if len(edge) != 2:
            raise ValueError(f"ungültige Kante: {edge!r}")
        u, v = index[str(edge[0])], index[str(edge[1])]
        if u != v:
            adj[u].add(v)
            adj[v].add(u)
    return nodes, adj


def solve_instance(instance: dict, time_limit: Optional[float] = None) -> dict:
    """Entscheidet eine Instanz ``{"G":…, "H":…}`` und liefert das Ausgabeobjekt."""
    _, g_adj = _parse_graph(instance["G"])
    _, h_adj = _parse_graph(instance["H"])
    mapping = find_embedding(g_adj, h_adj, _Deadline(time_limit))
    if mapping is None:
        return {"is_subgraph": False}
    return {"is_subgraph": True, "mapping": mapping}


def main(argv: Sequence[str]) -> int:
    """Kommandozeile: ``<input.json> <output.json>``."""
    if len(argv) != 2:
        print("Aufruf: subgraph_oracle <input.json> <output.json>", file=sys.stderr)
        return EXIT_BAD_INPUT
    limit_env = os.environ.get("SUBGRAPH_ORACLE_TIME_LIMIT")
    try:
        limit = float(limit_env) if limit_env else None
        with open(argv[0], "r", encoding="utf-8") as fh:
            instance = json.load(fh)
        result = solve_instance(instance, limit)
    except OracleTimeout:
        print("Zeitlimit überschritten", file=sys.stderr)
        return EXIT_TIMEOUT
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Ungültige Eingabe: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT
    with open(argv[1], "w", encoding="utf-8") as fh:
        # json.dumps erzeugt genau die vom Solver erwartete Schreibweise '"is_subgraph": true'
        fh.write(json.dumps(result))
    return EXIT_OK


def make_launcher(directory: str) -> str:
    """Schreibt ein ausführbares Startskript für das Orakel nach ``directory``.

    Der C++-Solver startet das Orakel per ``execl``; das Skript ruft dieses Modul mit
    dem aktuellen Interpreter auf, unabhängig davon, ob das Paket installiert ist.
    """
    src_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "subgraph_oracle")
    script = (
        f"#!{sys.executable}\n"
        "import sys\n"
        f"sys.path.insert(0, {src_root!r})\n"
        "from subgraph_sat_wirtschaft.oracle import main\n"
        "sys.exit(main(sys.argv[1:]))\n"
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(script)
    os.chmod(path, 0o755)
    return path


if __name__ == "__main__":  # pragma: no cover - dünner Einstiegspunkt
    sys.exit(main(sys.argv[1:]))
