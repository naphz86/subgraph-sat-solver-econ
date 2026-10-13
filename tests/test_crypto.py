from src.backends import DpllBackend
from src.circuits import CircuitBuilder
import pytest

from src.crypto import (
    evaluate,
    invert,
    invert_by_prefix,
    otp_encrypt,
    otp_key_for,
    proof_of_work,
    toy_mixer,
)


def test_toy_mixer_preserves_output_width():
    cb = CircuitBuilder()
    assert len(toy_mixer(cb, cb.inputs(3))) == 3


def test_invert_finds_input_for_identity_function():
    result = invert(lambda _cb, bits: bits, 2, [True, False], DpllBackend())
    assert result == [True, False]


def test_prefix_inversion_and_unsatisfiable_target():
    backend = DpllBackend()
    identity = lambda _cb, bits: bits
    assert invert_by_prefix(identity, 2, [True, False], backend) == [True, False]
    always_true = lambda _cb, _bits: [True]
    assert invert(always_true, 1, [False], backend) is None
    assert invert_by_prefix(always_true, 1, [False], backend) is None
    with pytest.raises(ValueError, match="Zielbreite"):
        invert(identity, 1, [True, False], backend)


def test_evaluate_and_proof_of_work():
    parity = lambda cb, bits: [cb.xor_(bits[0], bits[1])]
    assert evaluate(parity, [True, False]) == [True]
    result = proof_of_work(parity, 2, 1, DpllBackend())
    assert result is not None
    assert evaluate(parity, result) == [False]
    with pytest.raises(ValueError, match="Schwierigkeit"):
        proof_of_work(parity, 2, 2, DpllBackend())


def test_one_time_pad_round_trip_and_length_validation():
    ciphertext = otp_encrypt([True, False], [False, True])
    assert ciphertext == [True, True]
    assert otp_key_for(ciphertext, [True, False]) == [False, True]
    with pytest.raises(ValueError, match="gleich lang"):
        otp_encrypt([True], [])
