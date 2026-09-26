"""Clopper-Pearson intervals, checked against their definition (binomial tails) and closed forms."""

import math

import pytest

from relay.evaluation.intervals import clopper_pearson, regularized_beta


def upper_tail(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p), summed directly."""
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))


def lower_tail(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p), summed directly."""
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(0, k + 1))


@pytest.mark.parametrize(
    "k,n", [(1, 10), (5, 10), (9, 10), (1, 29), (29, 100), (1, 100), (7, 1000)]
)
def test_the_bounds_invert_the_binomial_tails(k, n):
    lower, upper = clopper_pearson(k, n)
    assert upper_tail(k, n, lower) == pytest.approx(0.025, abs=1e-9)
    assert lower_tail(k, n, upper) == pytest.approx(0.025, abs=1e-9)
    assert lower < k / n < upper


def test_zero_and_all_successes_have_closed_forms():
    assert clopper_pearson(0, 10) == pytest.approx((0.0, 1 - 0.025 ** (1 / 10)), abs=1e-12)
    assert clopper_pearson(10, 10) == pytest.approx((0.025 ** (1 / 10), 1.0), abs=1e-12)


def test_the_interval_is_symmetric_under_k_to_n_minus_k():
    lower, upper = clopper_pearson(3, 17)
    mirror_lower, mirror_upper = clopper_pearson(14, 17)
    assert lower == pytest.approx(1 - mirror_upper, abs=1e-12)
    assert upper == pytest.approx(1 - mirror_lower, abs=1e-12)


def test_a_published_value():
    # 5 of 10: the textbook exact 95% interval (0.1871, 0.8129).
    assert clopper_pearson(5, 10) == pytest.approx((0.187086, 0.812914), abs=1e-6)


def test_regularized_beta_edges_and_a_known_value():
    assert regularized_beta(0.0, 2, 3) == 0.0
    assert regularized_beta(1.0, 2, 3) == 1.0
    assert regularized_beta(0.5, 1, 1) == pytest.approx(0.5)  # Beta(1, 1) is uniform
    assert regularized_beta(0.3, 2, 2) == pytest.approx(3 * 0.3**2 - 2 * 0.3**3)


@pytest.mark.parametrize("k,n", [(0, 0), (-1, 5), (6, 5)])
def test_impossible_counts_are_rejected(k, n):
    with pytest.raises(ValueError):
        clopper_pearson(k, n)


def test_confidence_must_be_a_probability():
    with pytest.raises(ValueError):
        clopper_pearson(1, 2, confidence=1.0)
