import json

import pytest

from src.oracle import (
    EXIT_BAD_INPUT,
    EXIT_OK,
    EXIT_TIMEOUT,
    _Deadline,
    _parse_graph,
    find_clique,
    find_embedding,
    main,
    solve_instance,
    OracleTimeout,
)


def test_find_clique_handles_empty_and_invalid_sizes():
    assert find_clique([], 0) == []
    assert find_clique([], 1) is None
    with pytest.raises(ValueError):
        find_clique([], -1)


def test_find_clique_finds_and_rejects_cliques():
    graph = [{1, 2}, {0, 2}, {0, 1}, set()]
    clique = find_clique(graph, 3)
    assert clique is not None
    assert len(clique) == 3
    assert find_clique(graph, 4) is None


def test_find_embedding_handles_size_complete_and_general_targets():
    source = [{1, 2}, {0, 2}, {0, 1}, set()]
    assert find_embedding(source, [set(), set(), set(), set()]) is not None
    assert find_embedding(source, [{1}, {0}]) is not None
    assert find_embedding(source, [{1, 2}, {0, 2}, {0, 1}]) is not None
    assert find_embedding(source, [{1, 2, 3}, {0}, {0}, {0}]) is None


def test_parse_graph_rejects_duplicate_nodes_and_malformed_edges():
    with pytest.raises(ValueError, match="doppelte"):
        _parse_graph({"nodes": ["a", "a"], "edges": []})
    with pytest.raises(ValueError, match="ungültige Kante"):
        _parse_graph({"nodes": ["a"], "edges": [["a"]]})
    with pytest.raises(KeyError):
        _parse_graph({"nodes": ["a"], "edges": [["a", "missing"]]})


def test_solve_instance_returns_mapping_and_negative_answer():
    source = {"nodes": ["a", "b", "c"], "edges": [["a", "b"], ["b", "c"]]}
    target = {"nodes": ["x", "y"], "edges": [["x", "y"]]}
    result = solve_instance({"G": source, "H": target})
    assert result["is_subgraph"] is True
    assert len(set(result["mapping"])) == 2
    empty_target = {"nodes": ["x", "y", "z", "w"], "edges": []}
    assert solve_instance({"G": source, "H": empty_target}) == {"is_subgraph": False}


def test_deadline_check_raises_after_deadline():
    deadline = _Deadline(0)
    deadline.ticks = 255
    with pytest.raises(OracleTimeout):
        deadline.check()


def test_oracle_cli_writes_json_and_rejects_bad_arguments(tmp_path):
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    instance = {
        "G": {"nodes": ["a"], "edges": []},
        "H": {"nodes": ["x"], "edges": []},
    }
    input_path.write_text(json.dumps(instance), encoding="utf-8")
    assert main([str(input_path), str(output_path)]) == EXIT_OK
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "is_subgraph": True,
        "mapping": [0],
    }
    assert main([]) == EXIT_BAD_INPUT


def test_oracle_cli_reports_invalid_input_and_timeout(tmp_path, monkeypatch):
    input_path = tmp_path / "bad.json"
    output_path = tmp_path / "output.json"
    input_path.write_text("{}", encoding="utf-8")
    assert main([str(input_path), str(output_path)]) == EXIT_BAD_INPUT

    import src.oracle as oracle

    input_path.write_text(
        json.dumps({
            "G": {"nodes": ["a"], "edges": []},
            "H": {"nodes": ["x"], "edges": []},
        }),
        encoding="utf-8",
    )
    class ExpiredDeadline:
        def __init__(self, _seconds):
            pass

        def check(self):
            raise OracleTimeout()

    monkeypatch.setattr(oracle, "_Deadline", ExpiredDeadline)
    assert main([str(input_path), str(output_path)]) == EXIT_TIMEOUT
