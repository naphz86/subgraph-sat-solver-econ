from crypto import encode_one_way_function, encode_signature_scheme


def test_one_way_function_model_is_nonempty():
    model = encode_one_way_function(3)
    assert model.variables


def test_signature_scheme_model_has_keys():
    model = encode_signature_scheme(["pk1", "sk1"])
    assert set(model.variables) == {"pk1", "sk1"}
