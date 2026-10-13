from production import encode_job_schedule, encode_product_configuration


def test_job_schedule_encoding_has_at_least_one_choice():
    model = encode_job_schedule([(0, 3, 2), (1, 4, 2)], horizon=5)
    assert model.variables


def test_product_configuration_encoding_has_conflict_clauses():
    model = encode_product_configuration(["A", "B", "C"], [("A", "B")])
    assert model.variables["A"] > 0
    assert model.clauses
