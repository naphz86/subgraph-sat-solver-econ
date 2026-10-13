from fractions import Fraction

import pytest

from src.welfare import (
    communication_requirement,
    computation_gap,
    illustrative_example,
    net_gain,
    total_output,
    welfare_gain,
)


def test_welfare_gain_is_positive_for_small_values():
    assert welfare_gain(0.1, 0.1) > 0


def test_total_output_applies_weighted_gaps():
    total = total_output([2, 4], [Fraction(1, 2), Fraction(1, 4)])
    assert total == 4


def test_communication_requirement_counts_nonempty_bundles():
    assert communication_requirement(4) == 15


def test_welfare_helpers_cover_exact_values_and_invalid_inputs():
    assert computation_gap(10, 7) == Fraction(3, 10)
    assert illustrative_example() == Fraction(1, 199)
    assert net_gain(Fraction(1, 10), Fraction(1, 10), Fraction(1, 100)) == Fraction(1, 9900)
    with pytest.raises(ValueError, match="positiv"):
        computation_gap(0, 0)
    with pytest.raises(ValueError, match="opt"):
        computation_gap(2, 3)
    with pytest.raises(ValueError, match="gleich lang"):
        total_output([1], [])
    with pytest.raises(ValueError, match="in \\[0, 1\\]"):
        total_output([1], [2])
    with pytest.raises(ValueError, match="undefiniert"):
        welfare_gain(1, 1)
    with pytest.raises(ValueError, match="nichtnegativ"):
        communication_requirement(-1)
