"""
Unit tests for semiring axiom compliance.

Test index
----------
Boolean semiring (𝔹)
    TB-1   zero() == False
    TB-2   one() == True
    TB-3   add() implements logical OR for all four input combinations
    TB-4   mul() implements logical AND for all four input combinations
    TB-5   is_zero() identifies False as zero and True as non-zero
    TB-6   add is idempotent (True ∨ True = True)
    TB-7   add(False, False) == False
    TB-8   mul(True, False) == False (zero annihilator)

Counting semiring (ℕ)
    TN-1   zero() == 0
    TN-2   one() == 1
    TN-3   add() is integer addition
    TN-4   mul() is integer multiplication
    TN-5   is_zero() identifies 0 and only 0
    TN-6   add is commutative: a + b == b + a
    TN-7   mul is commutative: a · b == b · a
    TN-8   add is associative: (a + b) + c == a + (b + c)
    TN-9   mul is associative: (a · b) · c == a · (b · c)
    TN-10  mul distributes over add: a · (b + c) == a·b + a·c

Polynomial semiring (ℕ[X])
    TP-1   zero() == Polynomial.zero()  (empty polynomial)
    TP-2   one() == Polynomial.one()    (constant 1)
    TP-3   add() accumulates coefficients
    TP-4   mul() distributes monomials
    TP-5   is_zero() identifies empty polynomial and only it
    TP-6   variables() extracts all variable names
    TP-7   from_var() creates a single-variable polynomial
    TP-8   Polynomial.one() is_zero() → False

Shared semiring axioms — parametrized across (𝔹, ℕ, ℕ[X])
    AX-1   0 + a == a  (zero is additive identity)
    AX-2   a + 0 == a  (commutativity of additive identity)
    AX-3   1 · a == a  (one is multiplicative identity)
    AX-4   a · 1 == a  (commutativity of multiplicative identity)
    AX-5   0 · a == 0  (zero annihilates multiplication)
    AX-6   a · 0 == 0  (commutativity of multiplicative annihilation)
    AX-7   add is commutative: a + b == b + a
    AX-8   mul is commutative: a · b == b · a
    AX-9   mul distributes over add: a · (b + c) == a·b + a·c
    AX-10  is_zero(zero()) == True
    AX-11  is_zero(one()) == False
"""

import pytest

from src.semirings import BOOL_SR, NAT_SR, POLY_SR
from src.semirings.polynomial import Polynomial

# Sample non-zero values for each semiring, used in axiom tests.
_SAMPLES = [
    (BOOL_SR, True, True),
    (NAT_SR,  3, 5),
    (POLY_SR, Polynomial.from_var("t1"), Polynomial.from_var("t2")),
]
_SAMPLES_IDS = ["bool", "nat", "poly"]


# ──────────────────────────────────────────────────────────────────────
# Boolean semiring
# ──────────────────────────────────────────────────────────────────────

def test_bool_zero_is_false():
    """TB-1: Boolean zero equals Python False."""
    assert BOOL_SR.zero() is False


def test_bool_one_is_true():
    """TB-2: Boolean one equals Python True."""
    assert BOOL_SR.one() is True


@pytest.mark.parametrize("a,b,expected", [
    (False, False, False),
    (False, True, True),
    (True, False, True),
    (True, True, True),
])
def test_bool_add_is_or(a, b, expected):
    """TB-3: Boolean addition is logical OR for all input combinations."""
    assert BOOL_SR.add(a, b) == expected


@pytest.mark.parametrize("a,b,expected", [
    (False, False, False),
    (False, True, False),
    (True, False, False),
    (True, True, True),
])
def test_bool_mul_is_and(a, b, expected):
    """TB-4: Boolean multiplication is logical AND for all input combinations."""
    assert BOOL_SR.mul(a, b) == expected


@pytest.mark.parametrize("a,expected", [
    (False, True),
    (True, False),
])
def test_bool_is_zero(a, expected):
    """TB-5: is_zero() treats False as zero and True as non-zero."""
    assert BOOL_SR.is_zero(a) == expected


def test_bool_add_idempotent():
    """TB-6: In 𝔹: a + a = a (True ∨ True = True, False ∨ False = False)."""
    assert BOOL_SR.add(True, True)  == True
    assert BOOL_SR.add(False, False) == False


def test_bool_add_false_false():
    """TB-7: False ∨ False = False."""
    assert BOOL_SR.add(False, False) is False


def test_bool_mul_true_false():
    """TB-8: True ∧ False = False (zero annihilator in 𝔹)."""
    assert BOOL_SR.mul(True, False) is False


# ──────────────────────────────────────────────────────────────────────
# Counting semiring (ℕ)
# ──────────────────────────────────────────────────────────────────────

def test_nat_zero_is_zero_int():
    """TN-1: Counting zero is 0."""
    assert NAT_SR.zero() == 0


def test_nat_one_is_one_int():
    """TN-2: Counting one is 1."""
    assert NAT_SR.one() == 1


@pytest.mark.parametrize("a,b,expected", [
    (0, 0, 0),
    (0, 5, 5),
    (3, 4, 7),
    (7, 3, 10),
])
def test_nat_add_is_integer_addition(a, b, expected):
    """TN-3: Counting addition is ordinary integer addition."""
    assert NAT_SR.add(a, b) == expected


@pytest.mark.parametrize("a,b,expected", [
    (0, 5, 0),
    (1, 7, 7),
    (3, 4, 12),
])
def test_nat_mul_is_integer_multiplication(a, b, expected):
    """TN-4: Counting multiplication is ordinary integer multiplication."""
    assert NAT_SR.mul(a, b) == expected


@pytest.mark.parametrize("a,expected", [
    (0, True),
    (1, False),
    (10, False),
])
def test_nat_is_zero(a, expected):
    """TN-5: is_zero() returns True only for 0."""
    assert NAT_SR.is_zero(a) == expected


def test_nat_add_commutative():
    """TN-6: Counting add is commutative: a + b == b + a."""
    assert NAT_SR.add(3, 7) == NAT_SR.add(7, 3)


def test_nat_mul_commutative():
    """TN-7: Counting mul is commutative: a · b == b · a."""
    assert NAT_SR.mul(3, 7) == NAT_SR.mul(7, 3)


def test_nat_add_associative():
    """TN-8: Counting add is associative: (a + b) + c == a + (b + c)."""
    assert NAT_SR.add(NAT_SR.add(2, 3), 5) == NAT_SR.add(2, NAT_SR.add(3, 5))


def test_nat_mul_associative():
    """TN-9: Counting mul is associative: (a · b) · c == a · (b · c)."""
    assert NAT_SR.mul(NAT_SR.mul(2, 3), 5) == NAT_SR.mul(2, NAT_SR.mul(3, 5))


def test_nat_mul_distributes_over_add():
    """TN-10: Counting mul distributes over add: a · (b + c) == a·b + a·c."""
    a, b, c = 4, 3, 5
    lhs = NAT_SR.mul(a, NAT_SR.add(b, c))
    rhs = NAT_SR.add(NAT_SR.mul(a, b), NAT_SR.mul(a, c))
    assert lhs == rhs


# ──────────────────────────────────────────────────────────────────────
# Polynomial semiring (ℕ[X])
# ──────────────────────────────────────────────────────────────────────

def test_poly_zero_is_empty_polynomial():
    """TP-1: Semiring zero() returns an empty (no terms) Polynomial."""
    z = POLY_SR.zero()
    assert z == Polynomial.zero()
    assert z.is_zero()


def test_poly_one_is_constant_polynomial():
    """TP-2: Semiring one() returns the constant-1 Polynomial."""
    one = POLY_SR.one()
    assert one == Polynomial.one()
    assert not one.is_zero()


def test_poly_add_accumulates_coefficients():
    """TP-3: Adding two single-variable polynomials gives a two-term sum."""
    t1 = Polynomial.from_var("t1")
    t2 = Polynomial.from_var("t2")
    result = POLY_SR.add(t1, t2)
    # t1 + t2 should have 2 distinct monomials
    assert result.term_count() == 2
    assert result == t1.add(t2)


def test_poly_add_same_variable_doubles_coefficient():
    """TP-3b: Adding a polynomial to itself doubles the coefficient."""
    t1 = Polynomial.from_var("t1")
    result = POLY_SR.add(t1, t1)
    # 2·t1 — should still have one monomial but coefficient 2
    assert result.term_count() == 1
    assert result == Polynomial.from_var("t1").add(Polynomial.from_var("t1"))


def test_poly_mul_distributes_monomials():
    """TP-4: Multiplying two single-variable polynomials gives t1·t2."""
    t1 = Polynomial.from_var("t1")
    t2 = Polynomial.from_var("t2")
    result = POLY_SR.mul(t1, t2)
    expected = t1.multiply(t2)
    assert result == expected
    assert "t1" in result.variables()
    assert "t2" in result.variables()


@pytest.mark.parametrize("p,expected", [
    (Polynomial.zero(), True),
    (Polynomial.one(), False),
    (Polynomial.from_var("t1"), False),
])
def test_poly_is_zero(p, expected):
    """TP-5: is_zero identifies the empty polynomial and only it."""
    assert POLY_SR.is_zero(p) == expected


def test_poly_variables_extracts_all_names():
    """TP-6: variables() returns all variable names across all monomials."""
    t1 = Polynomial.from_var("t1")
    t2 = Polynomial.from_var("t2")
    t3 = Polynomial.from_var("t3")
    combined = POLY_SR.add(POLY_SR.add(t1, t2), t3)
    assert combined.variables() == {"t1", "t2", "t3"}


def test_poly_from_var_single_variable():
    """TP-7: from_var() creates a polynomial with exactly one monomial."""
    p = Polynomial.from_var("x")
    assert p.term_count() == 1
    assert p.variables() == {"x"}
    assert not p.is_zero()


def test_poly_one_is_not_zero():
    """TP-8: Polynomial.one() is not the zero polynomial."""
    assert not Polynomial.one().is_zero()


def test_poly_mul_by_zero_is_zero():
    """Polynomial multiplication by zero yields zero."""
    t1 = Polynomial.from_var("t1")
    assert POLY_SR.mul(t1, Polynomial.zero()) == Polynomial.zero()
    assert POLY_SR.mul(Polynomial.zero(), t1) == Polynomial.zero()


def test_poly_mul_distributes_over_add():
    """Polynomial mul distributes over add: a·(b+c) == a·b + a·c."""
    a = Polynomial.from_var("a")
    b = Polynomial.from_var("b")
    c = Polynomial.from_var("c")
    lhs = POLY_SR.mul(a, POLY_SR.add(b, c))
    rhs = POLY_SR.add(POLY_SR.mul(a, b), POLY_SR.mul(a, c))
    assert lhs == rhs


# ──────────────────────────────────────────────────────────────────────
# Shared semiring axioms — parametrized across (𝔹, ℕ, ℕ[X])
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("sr,a,_b", _SAMPLES, ids=_SAMPLES_IDS)
def test_zero_is_additive_identity(sr, a, _b):
    """AX-1: 0 + a == a for all semirings."""
    assert sr.add(sr.zero(), a) == a


@pytest.mark.parametrize("sr,a,_b", _SAMPLES, ids=_SAMPLES_IDS)
def test_zero_is_right_additive_identity(sr, a, _b):
    """AX-2: a + 0 == a for all semirings."""
    assert sr.add(a, sr.zero()) == a


@pytest.mark.parametrize("sr,a,_b", _SAMPLES, ids=_SAMPLES_IDS)
def test_one_is_multiplicative_identity(sr, a, _b):
    """AX-3: 1 · a == a for all semirings."""
    assert sr.mul(sr.one(), a) == a


@pytest.mark.parametrize("sr,a,_b", _SAMPLES, ids=_SAMPLES_IDS)
def test_one_is_right_multiplicative_identity(sr, a, _b):
    """AX-4: a · 1 == a for all semirings."""
    assert sr.mul(a, sr.one()) == a


@pytest.mark.parametrize("sr,a,_b", _SAMPLES, ids=_SAMPLES_IDS)
def test_zero_annihilates_multiplication(sr, a, _b):
    """AX-5: 0 · a == 0 for all semirings."""
    assert sr.mul(sr.zero(), a) == sr.zero()


@pytest.mark.parametrize("sr,a,_b", _SAMPLES, ids=_SAMPLES_IDS)
def test_zero_annihilates_right_multiplication(sr, a, _b):
    """AX-6: a · 0 == 0 for all semirings."""
    assert sr.mul(a, sr.zero()) == sr.zero()


@pytest.mark.parametrize("sr,a,b", _SAMPLES, ids=_SAMPLES_IDS)
def test_add_is_commutative(sr, a, b):
    """AX-7: add is commutative: a + b == b + a for all semirings."""
    assert sr.add(a, b) == sr.add(b, a)


@pytest.mark.parametrize("sr,a,b", _SAMPLES, ids=_SAMPLES_IDS)
def test_mul_is_commutative(sr, a, b):
    """AX-8: mul is commutative: a · b == b · a for all semirings."""
    assert sr.mul(a, b) == sr.mul(b, a)


@pytest.mark.parametrize("sr,a,b", _SAMPLES, ids=_SAMPLES_IDS)
def test_mul_distributes_over_add(sr, a, b):
    """AX-9: a · (b + c) == a·b + a·c for all semirings (c = one())."""
    c = sr.one()
    lhs = sr.mul(a, sr.add(b, c))
    rhs = sr.add(sr.mul(a, b), sr.mul(a, c))
    assert lhs == rhs


@pytest.mark.parametrize("sr,_a,_b", _SAMPLES, ids=_SAMPLES_IDS)
def test_is_zero_of_zero_is_true(sr, _a, _b):
    """AX-10: is_zero(zero()) == True for all semirings."""
    assert sr.is_zero(sr.zero()) is True


@pytest.mark.parametrize("sr,_a,_b", _SAMPLES, ids=_SAMPLES_IDS)
def test_is_zero_of_one_is_false(sr, _a, _b):
    """AX-11: is_zero(one()) == False for all semirings."""
    assert sr.is_zero(sr.one()) is False
