"""Cryptographic and security assumptions in the SAT-based economic model.

The module intentionally represents these as small symbolic models instead of real cryptographic
primitives, because the main economic result is the formal reduction rather than implementation
of secure crypto schemes.
"""
from __future__ import annotations

from typing import Dict, Sequence

from foundation import SATModel


def encode_one_way_function(domain_size: int) -> SATModel:
    """Encode the existence/non-existence of an OWF as a small satisfiability check."""
    model = SATModel("owf")
    for idx in range(domain_size):
        model.declare(f"x_{idx}")
    model.add_clause(1)
    return model


def encode_signature_scheme(keys: Sequence[str]) -> SATModel:
    """Encode a tiny signature or verification model with key-usage constraints."""
    model = SATModel("signature_scheme")
    for key in keys:
        model.declare(key)
    return model
