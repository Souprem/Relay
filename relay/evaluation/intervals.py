"""Exact (Clopper-Pearson) binomial confidence intervals, in pure Python.

The interval for k successes in n trials inverts the binomial tails: the lower bound is the
alpha/2 quantile of Beta(k, n - k + 1) (0 when k == 0), the upper bound the 1 - alpha/2 quantile
of Beta(k + 1, n - k) (1 when k == n). Quantiles come from bisection on the regularized
incomplete beta function, evaluated by its continued fraction.
"""

import math

_EPS = 1e-15
_TINY = 1e-300
_MAX_TERMS = 500
_BISECTIONS = 100


def _beta_cf(a: float, b: float, x: float) -> float:
    """The continued fraction for the incomplete beta function (modified Lentz)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > _TINY else _TINY)
    h = d
    for m in range(1, _MAX_TERMS + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > _TINY else _TINY)
        c = 1.0 + aa / c
        c = c if abs(c) > _TINY else _TINY
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > _TINY else _TINY)
        c = 1.0 + aa / c
        c = c if abs(c) > _TINY else _TINY
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _EPS:
            return h
    raise ArithmeticError(f"incomplete beta did not converge for a={a}, b={b}, x={x}")


def regularized_beta(x: float, a: float, b: float) -> float:
    """I_x(a, b), the Beta(a, b) cumulative distribution function at x."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    front = math.exp(log_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_cf(a, b, x) / a
    return 1.0 - front * _beta_cf(b, a, 1.0 - x) / b


def beta_quantile(p: float, a: float, b: float) -> float:
    """The x in [0, 1] with I_x(a, b) == p, by bisection."""
    low, high = 0.0, 1.0
    for _ in range(_BISECTIONS):
        mid = (low + high) / 2.0
        if regularized_beta(mid, a, b) < p:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def clopper_pearson(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """The exact two-sided `confidence` interval for a binomial proportion k / n."""
    if n <= 0 or not 0 <= k <= n:
        raise ValueError(f"need 0 <= k <= n and n > 0, got k={k}, n={n}")
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")
    alpha = 1.0 - confidence
    lower = 0.0 if k == 0 else beta_quantile(alpha / 2.0, k, n - k + 1)
    upper = 1.0 if k == n else beta_quantile(1.0 - alpha / 2.0, k + 1, n - k)
    return lower, upper
