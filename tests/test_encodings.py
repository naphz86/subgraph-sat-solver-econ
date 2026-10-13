from src.circuits import CircuitBuilder
from src.cnf import Cnf
import pytest


def test_circuit_builder_encodes_boolean_gates():
    cb = CircuitBuilder()
    a, b = cb.inputs(2)
    cb.and_(a, b)
    cb.or_(a, b)
    cb.xor_(a, b)
    cb.not_(a)
    assert len(cb.cnf.clauses) == 12


def test_to_3cnf_breaks_long_clauses():
    cnf = Cnf()
    cnf.new_vars(6)
    cnf.add_clause(1, 2, 3, 4, 5, 6)
    converted = cnf.to_3cnf()
    assert converted.is_3cnf()
    assert converted.num_clauses == 4


def test_circuit_arithmetic_and_invalid_inputs():
    cb = CircuitBuilder()
    a, b = cb.inputs(2)
    summed = cb.add_words([a], [b], 2)
    product = cb.mul_words([a, b], [b, a], 3)
    scaled = cb.mul_const([a, b], 3, 3)
    weights = cb.weighted_sum([a, b], [2, 1])
    for assignment in ({a: False, b: False}, {a: False, b: True},
                       {a: True, b: False}, {a: True, b: True}):
        values = cb.evaluate(assignment)
        expected_a, expected_b = assignment[a], assignment[b]
        assert cb.word_value(summed, values) == int(expected_a) + int(expected_b)
        assert cb.word_value(product, values) == (
            int(expected_a) + 2 * int(expected_b)
        ) * (int(expected_b) + 2 * int(expected_a)) % 8
        assert cb.word_value(scaled, values) == 3 * (
            int(expected_a) + 2 * int(expected_b)
        ) % 8
        assert cb.word_value(weights, values) == 2 * int(expected_a) + int(expected_b)
    assert cb.word_value(cb.mul_const([a], 0, 2), {a: True}) == 0
    assert cb.word_value(cb.complement([a, b]), {a: True, b: False}) == 2
    with pytest.raises(ValueError, match="gleich lang"):
        cb.weighted_sum([a], [])
    with pytest.raises(ValueError, match="nichtnegativ"):
        cb.weighted_sum([a], [-1])
    with pytest.raises(ValueError, match="passt nicht"):
        cb.const_word(4, 2)
    with pytest.raises(ValueError, match="nichtnegativ"):
        cb.mul_const([a], -1, 2)


def test_circuit_simplification_comparison_and_minimum():
    cb = CircuitBuilder()
    a, b = cb.inputs(2)
    assert cb.neg(True) is False
    assert cb.neg(-a) == a
    assert cb.and_(False, a) is False
    assert cb.and_(True, a) == a
    assert cb.and_(a, a) == a
    assert cb.and_(a, -a) is False
    assert cb.or_(True, a) is True
    assert cb.or_(False, a) == a
    assert cb.or_(a, a) == a
    assert cb.or_(a, -a) is True
    assert cb.xor_(False, a) == a
    assert cb.xor_(True, a) == -a
    assert cb.xor_(a, a) is False
    assert cb.xor_(a, -a) is True
    assert cb.mux(True, a, b) == a
    assert cb.and_all([]) is True
    assert cb.or_all([]) is False
    cb.assert_true(True)
    cb.assert_false(False)
    assert cb.num_gates == 0
    assert cb.value_of(-a, {a: True}) is False
    assert cb.word_value([a, b], {a: True, b: True}) == 3
    assert cb.word_value([], {}) == 0

    ge = cb.ge_const([a, b], 2)
    le = cb.le_const([a, b], 1)
    min_word = cb.min_words([[a, b], [b]])
    for assignment in ({a: False, b: False}, {a: True, b: False},
                       {a: False, b: True}, {a: True, b: True}):
        values = cb.evaluate(assignment)
        number = int(assignment[a]) + 2 * int(assignment[b])
        assert cb.value_of(ge, values) == (number >= 2)
        assert cb.value_of(le, values) == (number <= 1)
        assert cb.word_value(min_word, values) == min(number, int(assignment[b]))
    with pytest.raises(ValueError, match="mindestens"):
        cb.min_words([])
