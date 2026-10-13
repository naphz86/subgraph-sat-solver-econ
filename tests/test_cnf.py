import pytest

from src.cnf import Cnf, DimacsError, complete_assignment, enumerate_assignments


def test_cnf_building_copy_restrict_and_evaluate():
    cnf = Cnf()
    x, y = cnf.new_vars(2)
    cnf.add_clause(x, -y)
    cnf.add_clause()
    assert cnf.num_clauses == 2
    assert not cnf.evaluate({x: True, y: False})
    assert cnf.restrict({x: True}).clauses == [()]
    assert cnf.copy().clauses == cnf.clauses
    with pytest.raises(ValueError, match="ungültig"):
        cnf.add_clause(0)
    with pytest.raises(ValueError, match="ungültig"):
        cnf.add_clause(3)


def test_dimacs_parsing_serialization_and_errors():
    formula = Cnf.from_dimacs("c sample\np cnf 3 2\n1 -2\n3 0\n0\n")
    assert formula.clauses == [(1, -2, 3), ()]
    assert Cnf.from_dimacs(formula.to_dimacs()).clauses == formula.clauses
    with pytest.raises(DimacsError, match="vor der Kopfzeile"):
        Cnf.from_dimacs("1 0")
    with pytest.raises(DimacsError, match="Kopfzeile"):
        Cnf.from_dimacs("p bad 1 0")
    with pytest.raises(DimacsError, match="Ungültiges Literal"):
        Cnf.from_dimacs("p cnf 1 1\nx 0")
    with pytest.raises(DimacsError, match="nicht mit 0"):
        Cnf.from_dimacs("p cnf 1 1\n1")
    with pytest.raises(DimacsError, match="kündigt"):
        Cnf.from_dimacs("p cnf 1 2\n1 0")


def test_assignment_helpers_return_complete_boolean_models():
    cnf = Cnf(3)
    assert complete_assignment(cnf, {2: 1}) == {1: False, 2: True, 3: False}
    assert list(enumerate_assignments(0)) == [{}]
    assert len(list(enumerate_assignments(3))) == 8
