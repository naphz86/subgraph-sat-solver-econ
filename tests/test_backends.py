import pytest

from src.backends import (
    BackendError,
    BruteForceBackend,
    ChainBackend,
    CountingBackend,
    DecisionOnlyBackend,
    DpllBackend,
    validated,
)
from src.cnf import Cnf


def test_reference_backends_solve_sat_and_unsat_formulas():
    satisfiable = Cnf(2, [(1, -2), (2,)])
    unsatisfiable = Cnf(1, [(1,), (-1,)])
    for backend in (BruteForceBackend(), DpllBackend(), ChainBackend()):
        model = backend.solve(satisfiable)
        assert model is not None
        assert satisfiable.evaluate(model)
        assert backend.solve(unsatisfiable) is None


def test_backend_wrappers_count_and_enforce_decision_only_behavior():
    cnf = Cnf(1, [(1,)])
    counter = CountingBackend(DpllBackend())
    assert counter.solve(cnf) == {1: True}
    assert counter.calls == 1
    decision_only = DecisionOnlyBackend(DpllBackend())
    assert decision_only.is_sat(cnf)
    assert decision_only.calls == 1
    with pytest.raises(BackendError, match="keine Modelle"):
        decision_only.solve(cnf)


def test_backend_model_validation_completes_or_rejects_assignments():
    cnf = Cnf(2, [(1,)])
    assert validated(cnf, {1: True}) == {1: True, 2: False}
    assert validated(cnf, None) is None
    with pytest.raises(BackendError, match="erfüllt"):
        validated(cnf, {1: False})
    too_large = Cnf(23)
    with pytest.raises(BackendError, match="zu viele"):
        BruteForceBackend().solve(too_large)
