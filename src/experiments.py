"""Reproducible native-solver experiments for the economic SAT models.

Run from the repository root with ``python -m src.experiments`` after installing
the ``experiments`` extra. The C++ shim is built for each run; missing native
components and failed native answers are errors, never Python-backend fallbacks.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import shutil
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Optional

# Allow both ``python -m src.experiments`` and direct execution from any cwd.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.auctions import Bid, is_feasible, solve_wdp
from src.backends import BackendError, DpllBackend, SatBackend
from src.cnf import Cnf
from src.games import kendall_tau_cost, pairwise_weights, solve_kemeny
from src.markets import (
    Repacking,
    is_feasible_repacking,
    solve_kidney,
    solve_repacking,
)
from src.native import NativeBackend, NativeLibrary, build_shim
from src.production import (
    Job,
    is_valid_schedule,
    optimal_schedule,
    solve_ufl,
    ufl_cost,
    weighted_completion,
)

DEFAULT_SOLVER_DIR = ROOT.parent / "subgraph-sat-solver"
DEFAULT_SUBGRAPH_BINARY = ROOT.parent / "csubgraph" / "build" / "subgraph.exe"
RESULTS_DIR = ROOT / "src" / "results"
BASE_SEED = 20261013


@dataclass
class QueryMetrics:
    calls: int = 0
    elapsed_ms: float = 0.0
    max_variables: int = 0
    max_clauses: int = 0
    max_literals: int = 0
    reduction_ms: float = 0.0
    subgraph_ms: float = 0.0
    extraction_ms: float = 0.0


class MeasuredBackend(SatBackend):
    """Capture per-query formula size and native phase metrics around a backend."""

    def __init__(self, backend: SatBackend, native: bool) -> None:
        self.backend = backend
        self.native = native
        self.metrics = QueryMetrics()

    def solve(self, cnf: Cnf) -> Optional[dict[int, bool]]:
        started = time.perf_counter()
        try:
            return self.backend.solve(cnf)
        finally:
            self.metrics.elapsed_ms += (time.perf_counter() - started) * 1000
            self.metrics.calls += 1
            self.metrics.max_variables = max(self.metrics.max_variables, cnf.num_vars)
            self.metrics.max_clauses = max(self.metrics.max_clauses, cnf.num_clauses)
            self.metrics.max_literals = max(self.metrics.max_literals, cnf.size)
            if self.native:
                result = self.backend.last  # type: ignore[attr-defined]
                if result is not None:
                    self.metrics.reduction_ms += result.reduction_ms
                    self.metrics.subgraph_ms += result.subgraph_ms
                    self.metrics.extraction_ms += result.extraction_ms

    def as_json(self) -> dict[str, object]:
        data: dict[str, object] = {
            "sat_calls": self.metrics.calls,
            "backend_wall_ms_sum": round(self.metrics.elapsed_ms, 6),
            "max_query_cnf": {
                "variables": self.metrics.max_variables,
                "clauses": self.metrics.max_clauses,
                "literal_occurrences": self.metrics.max_literals,
            },
        }
        if self.native:
            data["native_phase_ms_sum"] = {
                "reduction": round(self.metrics.reduction_ms, 6),
                "subgraph": round(self.metrics.subgraph_ms, 6),
                "extraction": round(self.metrics.extraction_ms, 6),
            }
        return data


Outcome = dict[str, object]
CaseFactory = Callable[[random.Random, int], Callable[[SatBackend], Outcome]]


def _auction_case(rng: random.Random, num_bids: int) -> Callable[[SatBackend], Outcome]:
    num_goods = max(3, num_bids // 2)
    bids = []
    for index in range(num_bids):
        count = rng.randint(1, min(3, num_goods))
        items = frozenset(rng.sample(range(num_goods), count))
        bids.append(Bid(items, rng.randint(1, 30), agent=index // 2))

    def solve(backend: SatBackend) -> Outcome:
        result = solve_wdp(bids, backend, xor_agents=True)
        valid = is_feasible(bids, result.winners, xor_agents=True)
        return {
            "objective": result.revenue,
            "feasible": valid,
            "reported_sat_calls": result.calls,
        }

    return solve


def _repacking_case(rng: random.Random, vertices: int) -> Callable[[SatBackend], Outcome]:
    colors = [rng.randrange(3) for _ in range(vertices)]
    forbidden = set()
    for u in range(vertices):
        for v in range(u + 1, vertices):
            if colors[u] != colors[v] and rng.random() < 0.38:
                for color in range(1, 4):
                    forbidden.add((u, color, v, color))
    instance = Repacking({v: [1, 2, 3] for v in range(vertices)}, forbidden)

    def solve(backend: SatBackend) -> Outcome:
        assignment = solve_repacking(instance, backend)
        valid = assignment is not None and is_feasible_repacking(instance, assignment)
        return {
            "objective": int(valid),
            "feasible": valid,
            "reported_sat_calls": 1,
        }

    return solve


def _schedule_case(rng: random.Random, num_jobs: int) -> Callable[[SatBackend], Outcome]:
    jobs = []
    for _ in range(num_jobs):
        release = rng.randint(0, 2)
        proc = rng.randint(1, 2)
        deadline = 3 * num_jobs + 5
        jobs.append(Job(release, deadline, proc, rng.randint(1, 9)))

    def solve(backend: SatBackend) -> Outcome:
        result = optimal_schedule(jobs, backend)
        valid = (
            result is not None
            and is_valid_schedule(jobs, result.starts)
            and weighted_completion(jobs, result.starts) == result.value
        )
        return {
            "objective": result.value if result is not None else None,
            "feasible": valid,
            "reported_sat_calls": result.calls if result is not None else 0,
        }

    return solve


def _facility_case(rng: random.Random, facilities: int) -> Callable[[SatBackend], Outcome]:
    customers = facilities + 1
    open_costs = [rng.randint(4, 25) for _ in range(facilities)]
    assignment_costs = [
        [rng.randint(1, 30) for _ in range(customers)]
        for _ in range(facilities)
    ]

    def solve(backend: SatBackend) -> Outcome:
        result = solve_ufl(open_costs, assignment_costs, backend)
        valid = (
            result is not None
            and all(i in result.open_facilities for i in result.assignment.values())
            and set(result.assignment) == set(range(customers))
            and ufl_cost(open_costs, assignment_costs, result.open_facilities,
                         result.assignment) == result.cost
        )
        return {
            "objective": result.cost if result is not None else None,
            "feasible": valid,
            "reported_sat_calls": result.calls if result is not None else 0,
            "facilities": facilities,
            "customers": customers,
        }

    return solve


def _kidney_case(rng: random.Random, vertices: int) -> Callable[[SatBackend], Outcome]:
    arcs: set[tuple[int, int]] = set()
    for u in range(0, vertices - 1, 2):
        arcs.update(((u, u + 1), (u + 1, u)))
    for u in range(vertices):
        for v in range(vertices):
            if u != v and rng.random() < 0.16:
                arcs.add((u, v))
    arc_weights = {arc: rng.randint(1, 5) for arc in arcs}

    def solve(backend: SatBackend) -> Outcome:
        result = solve_kidney(vertices, sorted(arcs), 3, backend, arc_weights)
        used: set[int] = set()
        calculated = 0
        valid = True
        for cycle in result.cycles:
            if not 2 <= len(cycle) <= 3 or used.intersection(cycle):
                valid = False
            used.update(cycle)
            for i, u in enumerate(cycle):
                arc = (u, cycle[(i + 1) % len(cycle)])
                if arc not in arc_weights:
                    valid = False
                else:
                    calculated += arc_weights[arc]
        valid = valid and calculated == result.value
        return {
            "objective": result.value,
            "feasible": valid,
            "reported_sat_calls": result.calls,
            "cycles_found": len(result.cycles),
        }

    return solve


def _kemeny_case(rng: random.Random, candidates: int) -> Callable[[SatBackend], Outcome]:
    ballots = [
        rng.sample(range(candidates), candidates)
        for _ in range(max(3, 2 * candidates))
    ]
    weights = pairwise_weights(candidates, ballots)

    def solve(backend: SatBackend) -> Outcome:
        result = solve_kemeny(candidates, ballots, backend)
        valid = (
            sorted(result.order) == list(range(candidates))
            and kendall_tau_cost(result.order, weights) == result.cost
        )
        return {
            "objective": result.cost,
            "feasible": valid,
            "reported_sat_calls": result.calls,
            "ballots": len(ballots),
        }

    return solve


FAMILIES: tuple[tuple[str, str, tuple[int, ...], CaseFactory], ...] = (
    ("auctions", "Combinatorial winner determination", (3, 4, 5, 6), _auction_case),
    ("repacking", "Frequency assignment / graph coloring", (3, 4, 5, 6), _repacking_case),
    ("scheduling", "Weighted single-machine scheduling", (3, 4, 5, 6), _schedule_case),
    ("facility_location", "Uncapacitated facility location", (2, 3, 4, 5), _facility_case),
    ("kidney_exchange", "Kidney-exchange cycle packing", (3, 4, 5, 6), _kidney_case),
    ("kemeny", "Kemeny consensus ranking", (2, 3, 4, 5), _kemeny_case),
)


def _run_backend(
    case: Callable[[SatBackend], Outcome],
    backend: SatBackend,
    native: bool,
) -> dict[str, object]:
    measured = MeasuredBackend(backend, native)
    started = time.perf_counter()
    try:
        outcome = case(measured)
    except BackendError as exc:
        return {
            "status": "error",
            **measured.as_json(),
            "end_to_end_wall_ms": round((time.perf_counter() - started) * 1000, 6),
            "error": str(exc),
        }
    wall_ms = (time.perf_counter() - started) * 1000
    if not outcome["feasible"]:
        raise AssertionError(f"Ungültiger ökonomischer Zeuge: {outcome}")
    if outcome["reported_sat_calls"] != measured.metrics.calls:
        raise AssertionError(
            f"Modul meldet {outcome['reported_sat_calls']} SAT-Aufrufe, "
            f"gemessen wurden {measured.metrics.calls}"
        )
    return {
        "status": "ok",
        **measured.as_json(),
        "end_to_end_wall_ms": round(wall_ms, 6),
        "outcome": outcome,
    }


def _run_experiments(
    native_backend: NativeBackend, repetitions: int, seed: int, timeout_sec: int
) -> dict[str, list[dict[str, object]]]:
    reference = DpllBackend()
    results: dict[str, list[dict[str, object]]] = {}
    for family_index, (name, title, sizes, factory) in enumerate(FAMILIES):
        records = []
        for size in sizes:
            for repetition in range(repetitions):
                case_seed = seed + family_index * 100_000 + size * 100 + repetition
                case = factory(random.Random(case_seed), size)
                dpll_run = _run_backend(case, reference, False)
                native_run = _run_backend(case, native_backend, True)
                equivalence = "not_checked"
                if native_run["status"] == "ok":
                    native_outcome = native_run["outcome"]
                    dpll_outcome = dpll_run["outcome"]
                    if native_outcome["objective"] != dpll_outcome["objective"]:  # type: ignore[index]
                        raise AssertionError(
                            f"{name} (Größe {size}, Seed {case_seed}): "
                            "nativer Solver und DPLL liefern verschiedene Optimalwerte"
                        )
                    if native_outcome["feasible"] != dpll_outcome["feasible"]:  # type: ignore[index]
                        raise AssertionError(
                            f"{name} (Größe {size}, Seed {case_seed}): "
                            "native und DPLL widersprechen sich bei der Zeugenprüfung"
                        )
                    equivalence = "matched"
                record = {
                    "size": size,
                    "repetition": repetition,
                    "seed": case_seed,
                    "backends": {"dpll": dpll_run, "native_cpp": native_run},
                    "equivalence": equivalence,
                }
                records.append(record)
                RESULTS_DIR.mkdir(parents=True, exist_ok=True)
                _write_family_result(name, title, seed, repetitions, records)
                native_value = (
                    native_run["outcome"]["objective"]  # type: ignore[index]
                    if native_run["status"] == "ok" else "TIMEOUT/ERROR"
                )
                print(
                    f"{name:18s} size={size:2d} rep={repetition + 1}/{repetitions}: "
                    f"opt={native_value}, "
                    f"native={native_run['end_to_end_wall_ms']:.2f} ms "
                    f"({native_run['status']}), "
                    f"DPLL={dpll_run['end_to_end_wall_ms']:.2f} ms"
                )
        results[name] = records
    return results


def _write_family_result(
    name: str,
    title: str,
    seed: int,
    repetitions: int,
    records: list[dict[str, object]],
) -> None:
    path = RESULTS_DIR / f"{name}.json"
    path.write_text(
        json.dumps({
            "schema_version": 1,
            "experiment": name,
            "title": title,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "seed": seed,
            "repetitions": repetitions,
            "native_solver": "subgraph-sat-solver via satlib + wsat_shim",
            "reference_solver": "Python DpllBackend",
            "records": records,
        }, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _median(records: list[dict[str, object]], key: str, metric: str) -> float:
    values = [
        float(record["backends"][key][metric])  # type: ignore[index]
        for record in records
    ]
    return statistics.median(values)


def _plot_results(
    results: Mapping[str, list[dict[str, object]]], timeout_sec: int
) -> list[Path]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            'Matplotlib fehlt. Installiere die Abhängigkeit mit '
            '`python -m pip install -e ".[experiments]`.'
        ) from exc

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    names = [family[0] for family in FAMILIES if results.get(family[0])]
    labels = dict((family[0], family[1]) for family in FAMILIES)

    fig, axes = plt.subplots(1, len(names), figsize=(5 * len(names), 4.5),
                             squeeze=False, constrained_layout=True)
    for axis, name in zip(axes.flat, names):
        sizes = sorted({int(record["size"]) for record in results[name]})
        for backend, label, color, marker in (
            ("native_cpp", "C++ subgraph-sat-solver", "#1f5a94", "o"),
            ("dpll", "Python-DPLL-Referenz", "#d17b0f", "s"),
        ):
            plotted_sizes, times = [], []
            failed_sizes, failed_times = [], []
            for size in sizes:
                matching = [
                    record["backends"][backend]  # type: ignore[index]
                    for record in results[name] if int(record["size"]) == size
                ]
                samples = [float(run["end_to_end_wall_ms"]) for run in matching
                           if run["status"] == "ok"]
                failures = [float(run["end_to_end_wall_ms"]) for run in matching
                            if run["status"] != "ok"]
                if samples:
                    plotted_sizes.append(size)
                    times.append(statistics.median(samples))
                if failures and backend == "native_cpp":
                    failed_sizes.append(size)
                    failed_times.append(max(failures))
            axis.plot(plotted_sizes, times, marker=marker, color=color, label=label)
            if failed_sizes:
                axis.scatter(failed_sizes, failed_times, marker="x", color="#b22222",
                             label="C++-Abbruch (keine Lösung)", zorder=3)
        axis.set_title(labels[name])
        axis.set_xlabel("Instanzgröße")
        axis.set_ylabel("Median, Ende-zu-Ende (ms)")
        axis.set_yscale("log")
        axis.grid(True, which="both", alpha=0.25)
    axes.flat[0].legend(fontsize=8)
    fig.suptitle("Laufzeit der ökonomischen Optimierungs- und Entscheidungsinstanzen")
    path = RESULTS_DIR / "experiment_runtime.pdf"
    fig.savefig(path)
    plt.close(fig)
    paths.append(path)

    fig, axes = plt.subplots(1, len(names), figsize=(5 * len(names), 4.5),
                             squeeze=False, constrained_layout=True)
    for axis, name in zip(axes.flat, names):
        sizes = sorted({int(record["size"]) for record in results[name]})
        for field, label, color, marker in (
            ("variables", "Variablen", "#1f5a94", "o"),
            ("clauses", "Klauseln", "#d17b0f", "s"),
            ("literal_occurrences", "Literalvorkommen", "#3b8c61", "^"),
        ):
            values = []
            for size in sizes:
                samples = [
                    float(record["backends"]["native_cpp"]["max_query_cnf"][field])  # type: ignore[index]
                    for record in results[name] if int(record["size"]) == size
                ]
                values.append(statistics.median(samples) if samples else float("nan"))
            axis.plot(sizes, values, marker=marker, color=color, label=label)
        axis.set_title(labels[name])
        axis.set_xlabel("Instanzgröße")
        axis.set_ylabel("Median der größten SAT-Abfrage")
        axis.grid(True, alpha=0.25)
    axes.flat[0].legend(fontsize=8)
    fig.suptitle("Größe der durch die Wirtschaftsmodelle erzeugten SAT-Abfragen")
    path = RESULTS_DIR / "experiment_formula_size.pdf"
    fig.savefig(path)
    plt.close(fig)
    paths.append(path)

    phase_names = ("reduction", "subgraph", "extraction")
    phase_labels = ("Reduktion", "Subgraph-Entscheidung", "Extraktion")
    phase_data = []
    for name in names:
        records = results[name]
        phase_data.append([
            statistics.median([
                float(record["backends"]["native_cpp"]["native_phase_ms_sum"][phase])  # type: ignore[index]
                for record in records
                if record["backends"]["native_cpp"]["status"] == "ok"  # type: ignore[index]
            ]) if any(
                record["backends"]["native_cpp"]["status"] == "ok"  # type: ignore[index]
                for record in records
            ) else float("nan")
            for phase in phase_names
        ])
    fig, axis = plt.subplots(figsize=(max(8, 2.5 * len(names)), 5),
                             constrained_layout=True)
    bottom = [0.0] * len(names)
    for index, label in enumerate(phase_labels):
        values = [row[index] for row in phase_data]
        axis.bar(names, values, bottom=bottom, label=label)
        bottom = [old + value for old, value in zip(bottom, values)]
    axis.set_ylabel("Median je Instanz, Phasensumme über SAT-Aufrufe (ms)")
    axis.set_title("Zeitaufteilung innerhalb des nativen C++-Solvers")
    axis.tick_params(axis="x", labelrotation=20)
    axis.legend()
    path = RESULTS_DIR / "experiment_native_phases.pdf"
    fig.savefig(path)
    plt.close(fig)
    paths.append(path)

    fig, axis = plt.subplots(figsize=(10, 5), constrained_layout=True)
    labels = [labels[name] for name in names]
    completion = [
        sum(
            record["backends"]["native_cpp"]["status"] == "ok"  # type: ignore[index]
            for record in results[name]
        ) / len(results[name]) if results[name] else 0.0
        for name in names
    ]
    axis.bar(labels, completion, color="#3b8c61")
    axis.set_ylim(0, 1)
    axis.set_ylabel("Anteil vollständig gelöster Instanzen")
    axis.set_title(f"Native Abschlussquote (Zeitlimit {timeout_sec} s)")
    axis.tick_params(axis="x", labelrotation=20)
    axis.grid(True, axis="y", alpha=0.25)
    path = RESULTS_DIR / "experiment_completion.pdf"
    fig.savefig(path)
    plt.close(fig)
    paths.append(path)

    return paths


def _build_native(solver_dir: Path, subgraph_binary: Path, build_dir: Path) -> Path:
    if not solver_dir.is_dir():
        raise FileNotFoundError(f"C++-Solver-Checkout nicht gefunden: {solver_dir}")
    if not subgraph_binary.is_file():
        raise FileNotFoundError(f"Subgraph-Programm nicht gefunden: {subgraph_binary}")
    if shutil.which("cmake") is None:
        raise RuntimeError("CMake wurde nicht gefunden; der native Shim wird benötigt.")
    generator = "MinGW Makefiles" if sys.platform == "win32" and shutil.which("mingw32-make") else None
    return build_shim(build_dir, solver_dir, generator)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=BASE_SEED)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--timeout-sec", type=int, default=60)
    parser.add_argument("--solver-dir", type=Path, default=DEFAULT_SOLVER_DIR)
    parser.add_argument("--subgraph-binary", type=Path, default=DEFAULT_SUBGRAPH_BINARY)
    args = parser.parse_args(argv)
    if args.repetitions < 1:
        parser.error("--repetitions muss mindestens 1 sein")
    if args.timeout_sec < 1:
        parser.error("--timeout-sec muss mindestens 1 sein")

    solver_dir = args.solver_dir.resolve()
    subgraph_binary = args.subgraph_binary.resolve()
    print(f"Python: {sys.version.split()[0]} ({platform.platform()})")
    print(f"C++ Solver: {solver_dir}")
    print(f"Subgraph-Programm: {subgraph_binary}")
    print(f"Seed: {args.seed}; Wiederholungen je Größe: {args.repetitions}")

    build_dir = ROOT / "build" / "experiment-native"
    old_mode = os.environ.get("SUBGRAPH_MODE")
    old_timeout = os.environ.get("SUBGRAPH_TIMEOUT_SEC")
    os.environ["SUBGRAPH_MODE"] = "exact"
    os.environ["SUBGRAPH_TIMEOUT_SEC"] = str(args.timeout_sec)
    try:
        with tempfile.TemporaryDirectory(prefix="subgraph-sat-experiments-") as temporary:
            shim_path = _build_native(solver_dir, subgraph_binary, build_dir)
            print(f"Native Shim: {shim_path}")
            library = NativeLibrary.load(shim_path)
            backend = NativeBackend(
                library,
                subgraph_binary=subgraph_binary,
                work_dir=Path(temporary) / "solver-work",
                timeout_sec=args.timeout_sec,
                validate=True,
            )
            try:
                results = _run_experiments(
                    backend, args.repetitions, args.seed, args.timeout_sec
                )
            finally:
                backend.close()
    finally:
        if old_mode is None:
            os.environ.pop("SUBGRAPH_MODE", None)
        else:
            os.environ["SUBGRAPH_MODE"] = old_mode
        if old_timeout is None:
            os.environ.pop("SUBGRAPH_TIMEOUT_SEC", None)
        else:
            os.environ["SUBGRAPH_TIMEOUT_SEC"] = old_timeout

    figure_paths = _plot_results(results, args.timeout_sec)
    manifest = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "repetitions_per_size": args.repetitions,
        "subgraph_timeout_sec": args.timeout_sec,
        "native_solver": str(solver_dir),
        "subgraph_binary": str(subgraph_binary),
        "reference_solver": "Python DpllBackend",
        "families": {
            name: {
                "title": title,
                "sizes": list(sizes),
                "instances": len(results[name]),
                "results_file": f"{name}.json",
            }
            for name, title, sizes, _ in FAMILIES
        },
        "figures": [str(path.relative_to(ROOT)) for path in figure_paths],
    }
    (RESULTS_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"JSON-Ergebnisse: {RESULTS_DIR}")
    for path in figure_paths:
        print(f"PDF: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
