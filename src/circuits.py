"""Tseitin-Kodierung, Vergleicher und Summierer (Kapitel 2.2 der Arbeit).

Ein *Signal* ist entweder ein Literal (``int``, von 0 verschieden) oder eine
Konstante (``bool``). Konstanten werden beim Aufbau gefaltet; dadurch entstehen nie
mehr Gatter als im Schaltkreis der Arbeit. Ein *Wort* ist eine Liste von Signalen,
Bit 0 zuerst (little-endian).
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Tuple, Union

from .cnf import Cnf

Signal = Union[int, bool]
Word = List[Signal]


class CircuitBuilder:
    """Baut einen Schaltkreis und seine Tseitin-CNF gleichzeitig auf.

    Lemma ``lem:tseitin``: Für jede Belegung der Eingänge existiert genau eine
    Fortsetzung auf die Gattervariablen, die ``τ(C)`` erfüllt; jedes Gatter erzeugt
    höchstens 12 Literalvorkommen.
    """

    def __init__(self, cnf: Optional[Cnf] = None) -> None:
        self.cnf: Cnf = cnf if cnf is not None else Cnf()
        #: Gatterliste ``(op, ausgang, a, b)`` in topologischer Reihenfolge
        self.gates: List[Tuple[str, int, Signal, Optional[Signal]]] = []

    # ----------------------------------------------------------------- Eingänge
    def input(self) -> int:
        return self.cnf.new_var()

    def inputs(self, n: int) -> List[int]:
        return self.cnf.new_vars(n)

    @property
    def num_gates(self) -> int:
        return len(self.gates)

    # ------------------------------------------------------------------ Gatter
    @staticmethod
    def neg(a: Signal) -> Signal:
        """Negation ohne Gatter (Vorzeichenwechsel des Literals)."""
        return (not a) if isinstance(a, bool) else -a

    def _new_gate(self, op: str, a: Signal, b: Optional[Signal]) -> int:
        g = self.cnf.new_var()
        add = self.cnf.add_clause
        if op == "AND":
            add(-g, a)
            add(-g, b)
            add(g, -a, -b)
        elif op == "OR":
            add(g, -a)
            add(g, -b)
            add(-g, a, b)
        elif op == "XOR":
            add(-g, a, b)
            add(-g, -a, -b)
            add(g, -a, b)
            add(g, a, -b)
        else:  # NOT
            add(g, a)
            add(-g, -a)
        self.gates.append((op, g, a, b))
        return g

    def and_(self, a: Signal, b: Signal) -> Signal:
        if a is False or b is False:
            return False
        if a is True:
            return b
        if b is True:
            return a
        if a == b:
            return a
        if a == -b:
            return False
        return self._new_gate("AND", a, b)

    def or_(self, a: Signal, b: Signal) -> Signal:
        if a is True or b is True:
            return True
        if a is False:
            return b
        if b is False:
            return a
        if a == b:
            return a
        if a == -b:
            return True
        return self._new_gate("OR", a, b)

    def xor_(self, a: Signal, b: Signal) -> Signal:
        if a is False:
            return b
        if b is False:
            return a
        if a is True:
            return self.neg(b)
        if b is True:
            return self.neg(a)
        if a == b:
            return False
        if a == -b:
            return True
        return self._new_gate("XOR", a, b)

    def not_(self, a: Signal) -> Signal:
        """NOT als *echtes* Gatter (wie im Lemma); für freie Negation siehe :meth:`neg`."""
        if isinstance(a, bool):
            return not a
        return self._new_gate("NOT", a, None)

    def mux(self, sel: Signal, if_true: Signal, if_false: Signal) -> Signal:
        """``sel ? if_true : if_false``."""
        return self.or_(self.and_(sel, if_true), self.and_(self.neg(sel), if_false))

    def and_all(self, signals: Sequence[Signal]) -> Signal:
        result: Signal = True
        for s in signals:
            result = self.and_(result, s)
        return result

    def or_all(self, signals: Sequence[Signal]) -> Signal:
        result: Signal = False
        for s in signals:
            result = self.or_(result, s)
        return result

    # --------------------------------------------------------------- Behauptungen
    def assert_true(self, a: Signal) -> None:
        """Verlangt ``a = 1`` (Einheitsklausel; ``False`` erzeugt die leere Klausel)."""
        if a is True:
            return
        if a is False:
            self.cnf.add_clause()
            return
        self.cnf.add_clause(a)

    def assert_false(self, a: Signal) -> None:
        self.assert_true(self.neg(a))

    # --------------------------------------------------------------- Auswertung
    def evaluate(self, inputs: Mapping[int, bool]) -> Dict[int, bool]:
        """Wertet alle Gatter für eine Eingabebelegung aus (Referenz für Tests)."""
        values: Dict[int, bool] = dict(inputs)

        def val(s: Signal) -> bool:
            if isinstance(s, bool):
                return s
            v = values[abs(s)]
            return v if s > 0 else not v

        for op, out, a, b in self.gates:
            x = val(a)
            if op == "NOT":
                values[out] = not x
                continue
            y = val(b)  # type: ignore[arg-type]
            values[out] = {"AND": x and y, "OR": x or y, "XOR": x != y}[op]
        return values

    @staticmethod
    def value_of(signal: Signal, values: Mapping[int, bool]) -> bool:
        if isinstance(signal, bool):
            return signal
        v = values[abs(signal)]
        return v if signal > 0 else not v

    @staticmethod
    def word_value(word: Sequence[Signal], values: Mapping[int, bool]) -> int:
        return sum(
            (1 << i) for i, s in enumerate(word) if CircuitBuilder.value_of(s, values)
        )

    # ------------------------------------------------------------ Arithmetik
    def full_adder(self, a: Signal, b: Signal, c: Signal) -> Tuple[Signal, Signal]:
        """Volladdierer mit höchstens 5 Gattern: (Summenbit, Übertrag)."""
        t = self.xor_(a, b)
        s = self.xor_(t, c)
        carry = self.or_(self.and_(a, b), self.and_(c, t))
        return s, carry

    def add_words(self, a: Sequence[Signal], b: Sequence[Signal], width: int) -> Word:
        """Ripple-Carry-Addition modulo ``2**width`` (Überlauf wird abgeschnitten)."""
        out: Word = []
        carry: Signal = False
        for i in range(width):
            x: Signal = a[i] if i < len(a) else False
            y: Signal = b[i] if i < len(b) else False
            s, carry = self.full_adder(x, y, carry)
            out.append(s)
        return out

    def const_word(self, value: int, width: int) -> Word:
        if value < 0 or value >= (1 << width):
            raise ValueError(f"{value} passt nicht in {width} Bit")
        return [bool((value >> i) & 1) for i in range(width)]

    def mul_const(self, word: Sequence[Signal], c: int, width: int) -> Word:
        """Multiplikation eines Wortes mit einer Konstanten (Shift-and-add)."""
        if c < 0:
            raise ValueError("Konstante muss nichtnegativ sein")
        acc: Word = [False] * width
        shift = 0
        while c >> shift:
            if (c >> shift) & 1:
                shifted: Word = [False] * shift + list(word)
                acc = self.add_words(acc, shifted, width)
            shift += 1
        return acc

    def mul_words(self, a: Sequence[Signal], b: Sequence[Signal], width: int) -> Word:
        """Multiplikation zweier Wörter (Schulmethode) modulo ``2**width``."""
        acc: Word = [False] * width
        for j, bj in enumerate(b):
            partial: Word = [False] * j + [self.and_(ai, bj) for ai in a]
            acc = self.add_words(acc, partial, width)
        return acc

    def weighted_sum(self, ys: Sequence[Signal], cs: Sequence[int]) -> Word:
        """Summierer (Lemma ``lem:sum``): Bitwort der Summe ``Σ c_j·y_j``.

        Breite ``L' = L + ⌈log2(n+1)⌉`` mit ``L`` der Bitbreite der größten Konstante;
        es entstehen höchstens ``5·n·L'`` Gatter.
        """
        if len(ys) != len(cs):
            raise ValueError("ys und cs müssen gleich lang sein")
        if any(c < 0 for c in cs):
            raise ValueError("Konstanten müssen nichtnegativ sein")
        n = len(ys)
        width = sum_width(max(cs) if cs else 0, n)
        acc: Word = [False] * width
        for y, c in zip(ys, cs):
            term: Word = [y if (c >> i) & 1 else False for i in range(width)]
            acc = self.add_words(acc, term, width)
        return acc

    def sum_words(self, words: Sequence[Sequence[Signal]]) -> Word:
        """Summe variabler Wörter in ausreichender Breite (kein Überlauf)."""
        if not words:
            return [False]
        width = max(len(w) for w in words) + max(1, (len(words)).bit_length())
        acc: Word = [False] * width
        for w in words:
            acc = self.add_words(acc, w, width)
        return acc

    # -------------------------------------------------------------- Vergleiche
    def ge_const(self, word: Sequence[Signal], bound: int) -> Signal:
        """Vergleicher (Lemma ``lem:compare``): Signal für ``val(word) ≥ bound``."""
        width = len(word)
        if bound <= 0:
            return True
        if bound >= (1 << width):
            return False
        ge: Signal = True
        for i in range(width):
            if (bound >> i) & 1:
                ge = self.and_(word[i], ge)
            else:
                ge = self.or_(word[i], ge)
        return ge

    def le_const(self, word: Sequence[Signal], bound: int) -> Signal:
        """Signal für ``val(word) ≤ bound``."""
        return self.neg(self.ge_const(word, bound + 1))

    def ge_words(self, a: Sequence[Signal], b: Sequence[Signal]) -> Signal:
        """Signal für ``val(a) ≥ val(b)`` zweier variabler Wörter."""
        width = max(len(a), len(b))
        ge: Signal = True
        for i in range(width):
            x: Signal = a[i] if i < len(a) else False
            y: Signal = b[i] if i < len(b) else False
            ge = self.mux(self.xor_(x, y), x, ge)
        return ge

    def min_words(self, words: Sequence[Sequence[Signal]]) -> Word:
        """Bitweises Minimum mehrerer Wörter."""
        if not words:
            raise ValueError("min_words benötigt mindestens ein Wort")
        width = max(len(w) for w in words)
        best: Word = _pad(words[0], width)
        for other in words[1:]:
            other = _pad(other, width)
            take_other = self.ge_words(best, other)  # best >= other  =>  other ist kleiner
            best = [self.mux(take_other, o, b) for b, o in zip(best, other)]
        return best

    def complement(self, word: Sequence[Signal]) -> Word:
        """``(2^L-1) - val(word)`` (bitweise Negation): macht Minimieren zu Maximieren."""
        return [self.neg(s) for s in word]


def sum_width(max_const: int, n: int) -> int:
    """``L' = L + ⌈log2(n+1)⌉`` mit ``L = max(1, bitlen(max_const))``."""
    return max(1, max_const.bit_length()) + n.bit_length()


def _pad(word: Sequence[Signal], width: int) -> Word:
    return list(word) + [False] * (width - len(word))
