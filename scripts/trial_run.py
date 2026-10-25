#!/usr/bin/env python3
# Trial run of the spot/leverage volume filter on Crypto.com Exchange data.
# Research / paper trading only. Reads public market data; places no orders.
"""
Usage:
    python3 scripts/trial_run.py                      # live public API
    python3 scripts/trial_run.py --snapshot FILE.json # offline, from a saved snapshot

OI change is measured against the open interest saved by the previous run
(--state file), so the first run reports 0%. Funding comes from the public
valuations endpoint when available, else 0.
"""

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trdbot.filters import spot_leverage_volume_filter  # noqa: E402

API = "https://api.crypto.com/exchange/v1/public"
DEFAULT_COINS = ["BTC", "ETH", "SOL", "XRP", "DOGE"]

# A single venue sees far less perp-vs-spot skew than aggregated market data,
# so the filter's cross-exchange defaults (6x / 12x) are scaled down here.
SINGLE_VENUE = {
    "baseline_perp_spot_ratio": 1.5,
    "max_acceptable_ratio": 3.0,
    "max_abs_funding_rate": 0.0005,
    "max_oi_change_pct": 20.0,
}


def _get(endpoint, **params):
    url = f"{API}/{endpoint}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.load(resp)["result"]["data"]


def _ticker_fields(t):
    # The REST API uses short keys (vv, oi); some wrappers use long names.
    return {
        "volume_value": float(t.get("vv", t.get("volume_value", 0)) or 0),
        "open_interest": float(t.get("oi", t.get("open_interest", 0)) or 0),
    }


def fetch_live(coins):
    snap = {}
    for coin in coins:
        spot = _ticker_fields(_get("get-tickers", instrument_name=f"{coin}_USD")[0])
        perp = _ticker_fields(_get("get-tickers", instrument_name=f"{coin}USD-PERP")[0])
        try:
            rows = _get("get-valuations", instrument_name=f"{coin}USD-PERP",
                        valuation_type="funding_hist", count=1)
            funding = float(rows[0]["v"]) if rows else None
        except Exception:
            funding = None
        snap[coin] = {"spot": spot, "perp": perp, "funding": funding}
    return snap


def load_state(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_state(path, snap, now):
    state = {coin: {"open_interest": d["perp"]["open_interest"], "ts": now}
             for coin, d in snap.items()}
    with open(path, "w") as fh:
        json.dump(state, fh, indent=2)


def evaluate(snap, prev_state, thresholds):
    rows = []
    for coin, d in snap.items():
        oi_now = d["perp"]["open_interest"]
        oi_prev = prev_state.get(coin, {}).get("open_interest")
        oi_change = (oi_now - oi_prev) / oi_prev * 100 if oi_prev else 0.0
        funding = d.get("funding")
        result = spot_leverage_volume_filter(
            d["spot"]["volume_value"],
            d["perp"]["volume_value"],
            oi_change,
            funding if funding is not None else 0.0,
            **thresholds,
        )
        rows.append((coin, d, result, funding is None, oi_prev is None))
    return rows


def print_report(rows):
    print(f"{'Coin':5} {'Spot 24h':>12} {'Perp 24h':>12} {'Ratio':>6} "
          f"{'OI chg':>8} {'Funding':>9}  Result")
    for coin, d, r, no_funding, no_oi in rows:
        ratio = "-" if r["ratio"] is None else f"{r['ratio']:.2f}x"
        oi = "n/a" if no_oi else f"{r['oi_change']:+.1f}%"
        funding = "n/a" if no_funding else f"{r['funding'] * 100:.4f}%"
        verdict = "PASS" if r["pass"] else "FAIL"
        print(f"{coin:5} {d['spot']['volume_value']:>12,.0f} {d['perp']['volume_value']:>12,.0f} "
              f"{ratio:>6} {oi:>8} {funding:>9}  {verdict}  {r['reason']}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--coins", default=",".join(DEFAULT_COINS), help="comma-separated base coins")
    p.add_argument("--snapshot", help="read market data from this JSON file instead of the API")
    p.add_argument("--save-snapshot", help="write fetched market data to this JSON file")
    p.add_argument("--state", default=".trial_state.json", help="file holding the previous run's OI")
    p.add_argument("--no-state", action="store_true", help="don't read or write the state file")
    p.add_argument("--aggregate-defaults", action="store_true",
                   help="use the filter's cross-exchange defaults instead of single-venue ones")
    args = p.parse_args(argv)

    coins = [c.strip().upper() for c in args.coins.split(",") if c.strip()]
    if args.snapshot:
        with open(args.snapshot) as fh:
            snap = {c: v for c, v in json.load(fh).items() if c in coins}
    else:
        snap = fetch_live(coins)
    if args.save_snapshot:
        with open(args.save_snapshot, "w") as fh:
            json.dump(snap, fh, indent=2)

    prev_state = {} if args.no_state else load_state(args.state)
    thresholds = {} if args.aggregate_defaults else SINGLE_VENUE
    rows = evaluate(snap, prev_state, thresholds)
    print_report(rows)

    if not args.no_state:
        save_state(args.state, snap, time.time())
    return rows


if __name__ == "__main__":
    main()
