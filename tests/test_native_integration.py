"""Integration checks against the compiled C++ solver and subgraph artifacts."""

import json
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _build_dir(variable: str, sibling: str) -> Path:
    configured = os.environ.get(variable)
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / sibling / "build"


def _executable(build_dir: Path, stem: str) -> Path:
    for suffix in (".exe", ""):
        candidate = build_dir / f"{stem}{suffix}"
        if candidate.is_file():
            return candidate
    pytest.skip(f"C++-Build-Artefakt {stem} fehlt in {build_dir}")


def test_subgraph_sat_solver_cpp_test_suite():
    build_dir = _build_dir("SUBGRAPH_SAT_SOLVER_BUILD_DIR", "subgraph-sat-solver")
    executable = _executable(build_dir, "sat-tests")
    result = subprocess.run(
        [str(executable)],
        capture_output=True,
        timeout=120,
        check=False,
    )
    output = result.stdout.decode("utf-8", errors="replace")
    error = result.stderr.decode("utf-8", errors="replace")
    assert result.returncode == 0, output + error
    assert "Failed:         0" in output


def test_csubgraph_cpp_test_suite():
    build_dir = _build_dir("CSUBGRAPH_BUILD_DIR", "csubgraph")
    executable = _executable(build_dir, "subgraph-tests")
    result = subprocess.run(
        [str(executable)],
        capture_output=True,
        timeout=120,
        check=False,
    )
    output = result.stdout.decode("utf-8", errors="replace")
    error = result.stderr.decode("utf-8", errors="replace")
    assert result.returncode == 0, output + error
    assert "[  PASSED  ]" in output


def test_csubgraph_cpp_cli_decides_subgraph_instances(tmp_path):
    build_dir = _build_dir("CSUBGRAPH_BUILD_DIR", "csubgraph")
    executable = _executable(build_dir, "subgraph")
    source = {
        "nodes": ["a", "b", "c"],
        "edges": [["a", "b"], ["b", "c"], ["c", "a"]],
    }
    edge = {"nodes": ["x", "y"], "edges": [["x", "y"]]}
    impossible = {
        "nodes": ["u", "v", "w", "z"],
        "edges": [["u", "v"], ["v", "w"], ["w", "z"]],
    }

    def decide(target, name):
        input_path = tmp_path / f"{name}-input.json"
        output_path = tmp_path / f"{name}-output.json"
        input_path.write_text(json.dumps({"G": source, "H": target}), encoding="utf-8")
        result = subprocess.run(
            [str(executable), str(input_path), str(output_path)],
            capture_output=True,
            timeout=30,
            check=False,
        )
        output = result.stdout.decode("utf-8", errors="replace")
        error = result.stderr.decode("utf-8", errors="replace")
        assert result.returncode == 0, output + error
        return json.loads(output_path.read_text(encoding="utf-8"))

    positive = decide(edge, "positive")
    assert positive["is_subgraph"] is True
    assert len(set(positive["mapping"])) == 2
    assert decide(impossible, "negative") == {"is_subgraph": False}
