from encodings import FreshVarGenerator, tseitin_and, tseitin_not, tseitin_or, tseitin_xor, to_3cnf


def test_fresh_var_generator():
    gen = FreshVarGenerator()
    assert gen.next() == 1
    assert gen.next() == 2


def test_gate_gadgets_are_correct_size():
    assert len(tseitin_and(1, 2, 3)) == 3
    assert len(tseitin_or(1, 2, 3)) == 3
    assert len(tseitin_not(1, 3)) == 2
    assert len(tseitin_xor(1, 2, 3)) == 4


def test_to_3cnf_breaks_long_clauses():
    cnf = to_3cnf([(1, 2, 3, 4, 5, 6)])
    assert all(len(clause) <= 3 for clause in cnf)
