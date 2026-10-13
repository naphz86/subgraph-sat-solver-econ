"""Anbindung des C++-Solvers über den Shim unter ``src/native`` (ctypes).

Ablauf: :func:`build_shim` baut den Shim (CMake) gegen einen Checkout des
Subgraph-SAT-Solvers, :class:`NativeLibrary` lädt ihn, :class:`NativeBackend` stellt ihn
als :class:`~subgraph_sat_wirtschaft.backends.SatBackend` bereit. Als externes
Subgraph-Programm dient standardmäßig das exakte Orakel aus :mod:`oracle`.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from .backends import BackendError, SatBackend
from .cnf import Assignment, Cnf
from .oracle import make_launcher

ABI_VERSION = 1
WSAT_UNSAT, WSAT_SAT, WSAT_UNKNOWN, WSAT_ERROR = 0, 1, -1, -2

REPO_ROOT = Path(__file__).resolve().parents[2]
NATIVE_DIR = Path(__file__).resolve().parent.parent / "native"
DEFAULT_SOLVER_DIR = REPO_ROOT / "third_party" / "subgraph-sat-solver"
ENV_SOLVER_DIR = "SUBGRAPH_SAT_SOLVER_DIR"
ENV_SHIM_PATH = "WSAT_SHIM_PATH"


class NativeUnavailable(RuntimeError):
    """Shim oder Solver-Quellen sind nicht verfügbar."""


class _Stats(ctypes.Structure):
    _fields_ = [
        ("reduction_ms", ctypes.c_double),
        ("subgraph_ms", ctypes.c_double),
        ("extraction_ms", ctypes.c_double),
        ("total_ms", ctypes.c_double),
        ("num_variables", ctypes.c_int),
        ("num_clauses", ctypes.c_int),
    ]


@dataclass
class NativeResult:
    """Antwort des C++-Solvers samt Phasenlaufzeiten (Messplan, Punkt 3)."""

    status: str                      # "SAT", "UNSAT", "UNKNOWN", "ERROR"
    model: Optional[Assignment]
    error: str
    reduction_ms: float
    subgraph_ms: float
    extraction_ms: float
    total_ms: float
    num_variables: int
    num_clauses: int


# --------------------------------------------------------------------------- Bauen


def find_solver_dir(explicit: Optional[os.PathLike] = None) -> Optional[Path]:
    """Sucht die Solver-Quellen: Argument, ``$SUBGRAPH_SAT_SOLVER_DIR``, ``third_party/``."""
    candidates = [explicit, os.environ.get(ENV_SOLVER_DIR), DEFAULT_SOLVER_DIR]
    for cand in candidates:
        if cand and (Path(cand) / "SubgraphSATSolver.cpp").is_file():
            return Path(cand)
    return None


def library_filename() -> str:
    if sys.platform == "win32":
        return "wsat_shim.dll"
    if sys.platform == "darwin":
        return "libwsat_shim.dylib"
    return "libwsat_shim.so"


def build_shim(build_dir: os.PathLike, solver_dir: Optional[os.PathLike] = None) -> Path:
    """Baut den Shim mit CMake und gibt den Pfad der Bibliothek zurück."""
    source = find_solver_dir(solver_dir)
    if source is None:
        raise NativeUnavailable(
            f"Solver-Quellen nicht gefunden (Argument, ${ENV_SOLVER_DIR} oder {DEFAULT_SOLVER_DIR})"
        )
    if shutil.which("cmake") is None:
        raise NativeUnavailable("cmake nicht gefunden")
    build = Path(build_dir)
    build.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["cmake", "-S", str(NATIVE_DIR), "-B", str(build),
             f"-DSUBGRAPH_SAT_SOLVER_DIR={source}", "-DCMAKE_BUILD_TYPE=Release"],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(["cmake", "--build", str(build), "-j", "4"],
                       check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise NativeUnavailable(f"Build des Shims fehlgeschlagen:\n{exc.stdout}\n{exc.stderr}") from exc
    lib = build / library_filename()
    if not lib.is_file():
        raise NativeUnavailable(f"Bibliothek nicht erzeugt: {lib}")
    return lib


# ------------------------------------------------------------------------- Laden


class NativeLibrary:
    """Geladene Shim-Bibliothek (dünner ctypes-Wrapper um ``wsat_solve``)."""

    def __init__(self, path: os.PathLike) -> None:
        try:
            self._lib = ctypes.CDLL(str(path))
        except OSError as exc:
            raise NativeUnavailable(f"Bibliothek nicht ladbar: {path}: {exc}") from exc
        self._lib.wsat_abi_version.restype = ctypes.c_int
        self._lib.wsat_abi_version.argtypes = []
        if self._lib.wsat_abi_version() != ABI_VERSION:
            raise NativeUnavailable("ABI-Version des Shims passt nicht")
        self._lib.wsat_solve.restype = ctypes.c_int
        self._lib.wsat_solve.argtypes = [
            ctypes.POINTER(ctypes.c_int), ctypes.c_size_t, ctypes.c_int,
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_byte), ctypes.c_size_t,
            ctypes.POINTER(_Stats),
            ctypes.c_char_p, ctypes.c_size_t,
        ]
        self.path = Path(path)

    @classmethod
    def load(cls, path: Optional[os.PathLike] = None) -> "NativeLibrary":
        """Lädt die Bibliothek aus ``path``, ``$WSAT_SHIM_PATH`` oder ``build/``."""
        candidates = [path, os.environ.get(ENV_SHIM_PATH), REPO_ROOT / "build" / library_filename()]
        for cand in candidates:
            if cand and Path(cand).is_file():
                return cls(cand)
        raise NativeUnavailable(
            "Shim-Bibliothek nicht gefunden; bauen mit build_shim() oder "
            f"cmake -S src/native -B build (Pfad optional über ${ENV_SHIM_PATH})"
        )

    def abi_version(self) -> int:
        return int(self._lib.wsat_abi_version())

    def solve(self, cnf: Cnf, subgraph_binary: os.PathLike, temp_dir: os.PathLike,
              timeout_sec: int = 60, validate: bool = True, verbose: bool = False) -> NativeResult:
        flat = [lit for clause in cnf.clauses for lit in (*clause, 0)]
        arr = (ctypes.c_int * max(1, len(flat)))(*flat)
        model = (ctypes.c_byte * (cnf.num_vars + 1))()
        stats = _Stats()
        err = ctypes.create_string_buffer(512)
        code = self._lib.wsat_solve(
            arr, len(flat), cnf.num_vars,
            os.fsencode(os.fspath(subgraph_binary)), os.fsencode(os.fspath(temp_dir)),
            timeout_sec, int(validate), int(verbose),
            model, len(model), ctypes.byref(stats), err, len(err),
        )
        status = {WSAT_SAT: "SAT", WSAT_UNSAT: "UNSAT", WSAT_UNKNOWN: "UNKNOWN"}.get(code, "ERROR")
        assignment = (
            {v: bool(model[v]) for v in range(1, cnf.num_vars + 1)} if status == "SAT" else None
        )
        return NativeResult(
            status, assignment, err.value.decode("utf-8", "replace"),
            stats.reduction_ms, stats.subgraph_ms, stats.extraction_ms, stats.total_ms,
            stats.num_variables, stats.num_clauses,
        )


# ------------------------------------------------------------------------ Backend


class NativeBackend(SatBackend):
    """Entscheider auf Basis des C++-Subgraph-SAT-Solvers (über den Shim).

    Jede SAT-Antwort wird zusätzlich in Python gegen die Formel validiert; ``UNKNOWN`` und
    ``ERROR`` führen zu :class:`BackendError` (nie zu einer geratenen Antwort).
    """

    def __init__(self, library: NativeLibrary, subgraph_binary: Optional[os.PathLike] = None,
                 work_dir: Optional[os.PathLike] = None, timeout_sec: int = 60,
                 validate: bool = True) -> None:
        self.library = library
        self.timeout_sec = timeout_sec
        self.validate = validate
        self._owned_dir: Optional[tempfile.TemporaryDirectory] = None
        if work_dir is None:
            self._owned_dir = tempfile.TemporaryDirectory(prefix="wsat_")
            work_dir = self._owned_dir.name
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.subgraph_binary = (
            Path(subgraph_binary) if subgraph_binary is not None else Path(make_launcher(str(self.work_dir)))
        )
        self.last: Optional[NativeResult] = None
        self.calls = 0

    def solve_detailed(self, cnf: Cnf) -> NativeResult:
        self.calls += 1
        result = self.library.solve(cnf, self.subgraph_binary, self.work_dir,
                                    self.timeout_sec, self.validate)
        self.last = result
        return result

    def solve(self, cnf: Cnf) -> Optional[Assignment]:
        result = self.solve_detailed(cnf)
        if result.status == "UNSAT":
            return None
        if result.status != "SAT":
            raise BackendError(f"C++-Solver: {result.status}: {result.error}")
        assert result.model is not None
        if not cnf.evaluate(result.model):
            raise BackendError("C++-Solver lieferte eine Belegung, die die Formel nicht erfüllt")
        return result.model

    def close(self) -> None:
        if self._owned_dir is not None:
            self._owned_dir.cleanup()
            self._owned_dir = None
