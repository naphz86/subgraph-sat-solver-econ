"""Kryptographie und Sicherheit (Kapitel 8): Unter ``(E_poly)`` gibt es keine Einwegfunktionen.

Die Implementierung zeigt den Beweisschritt konstruktiv: Zu einer als Schaltkreis gegebenen
Funktion ``f`` wird ein Urbild mit einem SAT-Entscheider gefunden (Satz ``satz:owf``), einmal
direkt über ein Modell und einmal rein über Präfixentscheidungen (Satz ``satz:fpfnp``).
Praktisch ist das nur für kleine Eingabelängen möglich; es ist *kein* Angriff auf reale
Verfahren, sondern die Veranschaulichung der konditionalen Aussage der Arbeit.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Sequence

from .backends import SatBackend
from .circuits import CircuitBuilder, Signal, Word
from .foundation import find_witness

Build = Callable[[CircuitBuilder, Sequence[Signal]], Sequence[Signal]]


def toy_mixer(cb: CircuitBuilder, x: Sequence[Signal], rounds: int = 3) -> Word:
    """Kleine nichtlineare Mischfunktion (nur Demonstrationszweck, nicht kryptographisch)."""
    n = len(x)
    state: Word = list(x)
    for r in range(rounds):
        mixed: Word = []
        for i in range(n):
            nonlinear = cb.and_(state[(i + 1) % n], state[(i + 2) % n])
            mixed.append(cb.xor_(state[i], nonlinear))
        state = mixed[r + 1:] + mixed[: r + 1]  # Rotation
    return state


def _constrain_output(cb: CircuitBuilder, out: Sequence[Signal], target: Sequence[bool]) -> None:
    if len(out) != len(target):
        raise ValueError("Zielbreite passt nicht zur Ausgabebreite")
    for o, t in zip(out, target):
        cb.assert_true(o if t else cb.neg(o))


def invert(build: Build, n_in: int, target: Sequence[bool], backend: SatBackend) -> Optional[List[bool]]:
    """Urbild ``x`` mit ``f(x) = target`` per Modell des Entscheiders oder ``None``."""
    cb = CircuitBuilder()
    x = cb.inputs(n_in)
    _constrain_output(cb, build(cb, x), target)
    model = backend.solve(cb.cnf)
    return None if model is None else [model[v] for v in x]


def _prefix_sat(build: Build, n_in: int, target: Sequence[bool], prefix: str,
                backend: SatBackend) -> bool:
    cb = CircuitBuilder()
    fixed: List[Signal] = [c == "1" for c in prefix]
    free = cb.inputs(n_in - len(prefix))
    _constrain_output(cb, build(cb, fixed + list(free)), target)
    return backend.is_sat(cb.cnf)


def invert_by_prefix(build: Build, n_in: int, target: Sequence[bool],
                     backend: SatBackend) -> Optional[List[bool]]:
    """Urbildsuche nur mit Präfixentscheidungen (FNP-Suche, Satz ``satz:fpfnp``)."""

    def is_witness(u: str) -> bool:
        if len(u) != n_in:
            return False
        out = build(CircuitBuilder(), [c == "1" for c in u])
        return [bool(o) for o in out] == list(target)

    found = find_witness(
        lambda u: _prefix_sat(build, n_in, target, u, backend), is_witness, n_in
    )
    return None if found is None else [c == "1" for c in found]


def evaluate(build: Build, bits: Sequence[bool]) -> List[bool]:
    """Wertet ``f`` auf konkreten Bits aus (alle Gatter falten zu Konstanten)."""
    return [bool(o) for o in build(CircuitBuilder(), list(bits))]


def proof_of_work(build: Build, n_in: int, difficulty: int, backend: SatBackend) -> Optional[List[bool]]:
    """Proof-of-Work als FNP-Suche: Eingabe, deren Ausgabe mit ``difficulty`` Nullbits beginnt."""
    cb = CircuitBuilder()
    x = cb.inputs(n_in)
    out = build(cb, x)
    if difficulty > len(out):
        raise ValueError("Schwierigkeit größer als Ausgabebreite")
    for o in out[:difficulty]:
        cb.assert_false(o)
    model = backend.solve(cb.cnf)
    return None if model is None else [model[v] for v in x]


def otp_encrypt(plaintext: Sequence[bool], key: Sequence[bool]) -> List[bool]:
    """One-Time-Pad (Shannon): informationstheoretisch sicher, von ``(E_poly)`` unberührt."""
    if len(plaintext) != len(key):
        raise ValueError("Schlüssel und Klartext müssen gleich lang sein")
    return [p != k for p, k in zip(plaintext, key)]


def otp_key_for(ciphertext: Sequence[bool], plaintext: Sequence[bool]) -> List[bool]:
    """Zu *jedem* Klartext gleicher Länge gibt es einen passenden Schlüssel – das Chiffrat
    verrät nichts, auch nicht einem unbeschränkten Entscheider."""
    return otp_encrypt(ciphertext, plaintext)
