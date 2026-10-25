# Conceptual filter only — paper trading / research use
# Not connected to any exchange. Do not use with real money as-is.

import math


def spot_leverage_volume_filter(
    spot_volume_24h: float,
    perp_volume_24h: float,
    open_interest_change_pct: float,   # e.g. +15.0 for +15%
    funding_rate: float,               # fraction per funding interval, e.g. 0.01 for 1%
    baseline_perp_spot_ratio: float = 6.0,  # typical crypto baseline
    max_acceptable_ratio: float = 12.0,
    max_abs_funding_rate: float = 0.03,
    max_oi_change_pct: float = 20.0,
) -> dict:
    """
    Returns pass/fail + reason.
    Goal: prefer setups where spot volume is not overwhelmed by leverage.

    Every result carries the same keys: pass, reason, ratio, oi_change, funding.
    ratio is None when it cannot be computed.
    """
    inputs = (spot_volume_24h, perp_volume_24h, open_interest_change_pct, funding_rate)
    if not all(math.isfinite(x) for x in inputs):
        return _result(False, "Non-finite input", None, open_interest_change_pct, funding_rate)

    if spot_volume_24h <= 0:
        return _result(False, "No meaningful spot volume", None, open_interest_change_pct, funding_rate)

    if perp_volume_24h < 0:
        return _result(False, "Negative perp volume", None, open_interest_change_pct, funding_rate)

    ratio = perp_volume_24h / spot_volume_24h

    # High leverage dominance relative to baseline
    if ratio > max_acceptable_ratio:
        return _result(
            False,
            f"Perp/spot ratio {ratio:.1f}x exceeds limit ({max_acceptable_ratio}x)",
            ratio, open_interest_change_pct, funding_rate,
        )

    # Extreme funding + rising OI often signals crowded leverage
    if abs(funding_rate) > max_abs_funding_rate and open_interest_change_pct > max_oi_change_pct:
        return _result(
            False,
            "High funding + rising OI — crowded positioning",
            ratio, open_interest_change_pct, funding_rate,
        )

    # Optional: prefer clearer spot confirmation
    if ratio < baseline_perp_spot_ratio * 0.7:
        strength = "strong spot confirmation"
    else:
        strength = "acceptable but leverage-heavy"

    return _result(
        True,
        f"Volume OK (ratio {ratio:.1f}x) — {strength}",
        ratio, open_interest_change_pct, funding_rate,
    )


def _result(passed, reason, ratio, oi_change, funding):
    return {
        "pass": passed,
        "reason": reason,
        "ratio": None if ratio is None else round(ratio, 2),
        "oi_change": oi_change,
        "funding": funding,
    }
