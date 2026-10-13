import json

import pytest

from src.cnf import Cnf
from src.reduction import (
    Graph,
    clique_number,
    extract_assignment,
    max_clique,
    sat_to_clique,
    subgraph_instance_json,
    three_sat_to_clique,
)


def test_graph_edge_validation_and_serialization():
    graph = Graph(3)
    graph.add_edge(0, 1)
    graph.add_edge(1, 0)
    graph.add_edge(2, 2)
    assert graph.edges() == [(0, 1)]
    assert graph.num_edges == 1
    assert graph.has_edge(0, 1)
    assert not graph.has_edge(-1, 1)
    assert graph.to_dict() == {
        "nodes": ["v0", "v1", "v2"],
        "edges": [["v0", "v1"]],
    }
    with pytest.raises(IndexError):
        graph.add_edge(0, 3)
    serialized = json.loads(subgraph_instance_json(graph, Graph.complete(2)))
    assert serialized["H"]["edges"] == [["v0", "v1"]]


def test_graph_complete_and_clique_search_helpers():
    complete = Graph.complete(3)
    assert complete.num_edges == 3
    assert clique_number(complete) == 3
    assert len(max_clique(complete)) == 3
    assert clique_number(Graph(0)) == 0
    assert max_clique(Graph(0)) == []


def test_three_sat_reduction_connects_nonconflicting_literals_only():
    cnf = Cnf()
    cnf.new_vars(2)
    cnf.add_clause(1, 2)
    cnf.add_clause(-1, 2)
    reduction = three_sat_to_clique(cnf)
    assert reduction.k == 2
    assert reduction.graph.num_edges == 3
    assignment = extract_assignment(reduction, [0, 2])
    assert assignment == {1: True, 2: False}
    with pytest.raises(ValueError, match="3-CNF"):
        three_sat_to_clique(Cnf(4, [(1, 2, 3, 4)]))


def test_sat_to_clique_preserves_original_variable_count():
    cnf = Cnf()
    cnf.new_vars(5)
    cnf.add_clause(1, 2, 3, 4, 5)
    reduction = sat_to_clique(cnf)
    assert reduction.num_original_vars == 5
    assert reduction.cnf3.is_3cnf()
    assert len(extract_assignment(reduction, [])) == 5
