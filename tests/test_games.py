from games import encode_kemeny_election, encode_nash_gap, encode_social_choice


def test_nash_gap_model_has_variables():
    model = encode_nash_gap([1, 2], [2, 3])
    assert model.variables


def test_kemeny_election_encoding_builds_order_terms():
    model = encode_kemeny_election(["A", "B", "C"], [("A", "B", 2)])
    assert model.variables


def test_social_choice_accepts_target_winner():
    model = encode_social_choice([["A", "B"], ["B", "C"]], "B")
    assert model.variables["B"] > 0
