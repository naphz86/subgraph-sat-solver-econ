from foundation import SATModel, compare_ge_bits, require_implication, to_3cnf


def test_sat_model_declares_variables_and_clauses():
    model = SATModel("demo")
    assert model.declare("a") == 1
    assert model.declare("a") == 1
    model.add_clause(1, -2)
    assert model.clauses


def test_require_implication_adds_imply_clauses():
    model = SATModel("demo")
    require_implication(model, ["a"], ["b"])
    assert (-model.variables["a"], model.variables["b"]) in model.clauses


def test_compare_ge_bits_returns_final_var_and_clauses():
    clauses, final_var = compare_ge_bits([1, 2], 2)
    assert clauses
    assert final_var > 0


def test_three_cnf_conversion_keeps_clauses_short():
    clauses = to_3cnf([(1, 2, 3, 4, 5)])
    assert all(len(clause) <= 3 for clause in clauses)
