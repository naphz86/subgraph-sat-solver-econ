"""Wohlfahrtsmodell und Informationsgrenzen (Kapitel 9)."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Sequence, Union

Rational = Union[int, float, Fraction]


def _check_unit(name: str, value: Rational) -> Fraction:
    v = Fraction(value)
    if not 0 <= v <= 1:
        raise ValueError(f"{name} muss in [0, 1] liegen")
    return v


def computation_gap(optimum: Rational, achieved: Rational) -> Fraction:
    """Rechenlücke ``g = (opt − A)/opt ∈ [0,1]``."""
    opt, got = Fraction(optimum), Fraction(achieved)
    if opt <= 0:
        raise ValueError("opt muss positiv sein")
    if not 0 <= got <= opt:
        raise ValueError("A muss in [0, opt] liegen")
    return (opt - got) / opt


def total_output(optima: Sequence[Rational], gaps: Sequence[Rational]) -> Fraction:
    """``Y = Σ_i opt_i (1 − g_i)``."""
    if len(optima) != len(gaps):
        raise ValueError("optima und gaps müssen gleich lang sein")
    return sum((Fraction(o) * (1 - _check_unit("g", g)) for o, g in zip(optima, gaps)), Fraction(0))


def welfare_gain(alpha: Rational, mean_gap: Rational) -> Fraction:
    """Relativer Zugewinn ``(O − Y)/Y = αγ̄ / (1 − αγ̄)`` (Satz ``satz:gain``).

    ``alpha``: Wertanteil der NP-artigen Entscheidungen an ``O``; ``mean_gap``: wertgewichtete
    mittlere Lücke dieser Entscheidungen.
    """
    a, g = _check_unit("alpha", alpha), _check_unit("mean_gap", mean_gap)
    product = a * g
    if product == 1:
        raise ValueError("α·γ̄ = 1: Output Y wäre 0, der relative Zugewinn undefiniert")
    return product / (1 - product)


def net_gain(alpha: Rational, mean_gap: Rational, replacement_cost_share: Rational) -> Fraction:
    """Zugewinn abzüglich Ersatzkosten der Sicherheitsinfrastruktur (Kapitel 8, nichtmonoton).

    ``replacement_cost_share``: Ersatzkosten als Anteil an ``Y``. Rein modellhaft: die Arbeit
    liefert keinen Zahlenwert, die Parameter sind empirisch zu bestimmen.
    """
    return welfare_gain(alpha, mean_gap) - _check_unit("replacement_cost_share", replacement_cost_share)


def illustrative_example() -> Fraction:
    """Beispiel der Arbeit (rein illustrativ): ``α=0,10``, ``γ̄=0,05`` ⇒ ``0,005/0,995 ≈ 0,50 %``."""
    return welfare_gain(Fraction(1, 10), Fraction(1, 20))


def communication_requirement(num_goods: int) -> int:
    """Zwei Agenten, ``L`` unteilbare Güter, allgemeine Bewertungen (Satz ``satz:comm``):
    ein Preis je nichtleerem Bündel, also ``2^L − 1`` Werte müssen offenbart werden."""
    if num_goods < 0:
        raise ValueError("Anzahl der Güter muss nichtnegativ sein")
    return (1 << num_goods) - 1
