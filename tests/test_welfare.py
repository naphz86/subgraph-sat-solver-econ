from welfare import aggregate_welfare, communication_need, welfare_gain


def test_welfare_gain_is_positive_for_small_values():
    value = welfare_gain(0.1, 0.1)
    assert value > 0


def test_aggregate_welfare_is_integer_total():
    total = aggregate_welfare([(1, 2), (3, 4)])
    assert total == 10


def test_communication_need_is_exponential():
    assert communication_need(4) == 16
