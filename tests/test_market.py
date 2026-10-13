from market import encode_repacking, encode_cycle_exchange


def test_repacking_encoding_has_constraints():
    model = encode_repacking([[0, 1], [0, 1]], [(0, 0, 1, 0)])
    assert model.variables
    assert model.clauses


def test_cycle_exchange_has_structure():
    model = encode_cycle_exchange([[1, 0], [0, 1]], 2)
    assert model.variables
