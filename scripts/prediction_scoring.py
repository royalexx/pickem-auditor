"""Read-only probability transforms for prospective outcome evaluation.

Forecast probabilities remain unchanged. Binary scores on non-push outcomes
must condition the complete forecast or mixture on the same non-push event.
"""
from __future__ import annotations

import math

VERSION = "conditional-nonpush-mixture-v1"


def _win_push(win, push):
    if isinstance(win, bool) or isinstance(push, bool):
        raise ValueError("invalid_win_push_probability")
    try:
        win, push = float(win), float(push)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_win_push_probability") from exc
    if (not all(math.isfinite(v) for v in (win, push)) or
            not (0 <= win <= 1 and 0 <= push <= 1) or
            win + push > 1 + 1e-10):
        raise ValueError("invalid_win_push_probability")
    # Permit only floating-point roundoff beyond the simplex boundary.
    return min(win, 1 - push), push


def conditional_win(win, push):
    """P(win | no push) from a complete unconditional win/push forecast."""
    win, push = _win_push(win, push)
    if push >= 1:
        raise ValueError("undefined_all_push_conditional_probability")
    return min(1., max(0., win / (1 - push)))


def market_conditional_win(snapshot):
    """Read the frozen conditional market *policy score*, preserving zero.

    q_market_comparable is already multiplied by this forecast's push mass.
    It needs conversion back to the no-push scale when q_market is absent.
    This function does not call that policy score a raw no-vig probability.
    """
    market = snapshot.get("market") or {}
    raw = snapshot.get("q_market")
    if raw is None:
        raw = market.get("q_market")
    if raw is not None:
        return conditional_win(raw, 0)
    comparable = snapshot.get("q_market_comparable")
    if comparable is None:
        comparable = market.get("q_market_comparable")
    push = snapshot.get("q_push")
    if push is None:
        try:
            line = float(snapshot.get("reference_line"))
        except (TypeError, ValueError) as exc:
            raise ValueError("market_conditional_scale_unavailable") from exc
        if not math.isfinite(line) or abs(line - round(line)) < 1e-9:
            raise ValueError("market_conditional_scale_unavailable")
        push = 0.
    return conditional_win(comparable, push)


def conditional_mixture_win(a_win, a_push, b_win, b_push, *, weight_a=.70):
    """P(win | no push) for a mixture of complete A/B outcome forecasts.

    First form the mixture's unconditional win and push masses, then
    condition once. Averaging conditional probabilities uses different
    mixture weights whenever the component push probabilities differ.
    """
    a_win, a_push = _win_push(a_win, a_push)
    b_win, b_push = _win_push(b_win, b_push)
    if isinstance(weight_a, bool):
        raise ValueError("invalid_mixture_weight")
    try:
        weight_a = float(weight_a)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_mixture_weight") from exc
    if not math.isfinite(weight_a) or not 0 <= weight_a <= 1:
        raise ValueError("invalid_mixture_weight")
    win = weight_a * a_win + (1 - weight_a) * b_win
    nonpush = weight_a * (1 - a_push) + (1 - weight_a) * (1 - b_push)
    if nonpush <= 0:
        raise ValueError("undefined_all_push_conditional_probability")
    return min(1., max(0., win / nonpush))
