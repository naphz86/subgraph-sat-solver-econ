from auctions import encode_wdp, choose_winners, vcg_payments


def test_wdp_encoding_has_variables_and_clauses():
    model = encode_wdp([[0, 1], [1, 2], [2]], [3, 2, 1], 3)
    assert model.variables
    assert model.clauses


def test_choose_winners_finds_valuable_set():
    winners = choose_winners([[0, 1], [1, 2], [2]], [3, 2, 1])
    assert isinstance(winners, list)


def test_vcg_payments_are_non_negative():
    total, payments = vcg_payments([[0], [1], [0, 1]], [1, 1, 2])
    assert total >= 0
    assert all(p >= 0 for p in payments)
