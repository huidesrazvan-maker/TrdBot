import contextlib
import io
import json
import os
import tempfile
import unittest

from scripts import trial_run

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "cryptocom_2026-10-25.json")


def run(*args):
    with contextlib.redirect_stdout(io.StringIO()):
        return {coin: r for coin, _, r, _, _ in trial_run.main(list(args))}


class TrialRunTest(unittest.TestCase):
    def test_snapshot_single_venue(self):
        results = run("--snapshot", FIXTURE, "--no-state")
        self.assertEqual(set(results), {"BTC", "ETH", "SOL", "XRP", "DOGE"})
        self.assertTrue(all(r["pass"] for r in results.values()))
        self.assertIn("leverage-heavy", results["BTC"]["reason"])  # 1.14x >= 1.5 * 0.7
        self.assertIn("strong", results["XRP"]["reason"])          # 0.36x

    def test_oi_change_from_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "state.json")
            with open(state, "w") as fh:
                json.dump({"BTC": {"open_interest": 5000.0, "ts": 0}}, fh)
            results = run("--snapshot", FIXTURE, "--coins", "BTC", "--state", state)
            self.assertAlmostEqual(results["BTC"]["oi_change"], 23.8279, places=3)
            with open(state) as fh:
                self.assertEqual(json.load(fh)["BTC"]["open_interest"], 6191.3958)

    def test_crowded_with_funding(self):
        with open(FIXTURE) as fh:
            snap = json.load(fh)
        snap["BTC"]["funding"] = 0.001
        rows = trial_run.evaluate({"BTC": snap["BTC"]}, {"BTC": {"open_interest": 5000.0}},
                                  trial_run.SINGLE_VENUE)
        self.assertFalse(rows[0][2]["pass"])
        self.assertIn("crowded", rows[0][2]["reason"])

    def test_ticker_fields_accepts_short_and_long_keys(self):
        self.assertEqual(trial_run._ticker_fields({"vv": "10", "oi": "2"}),
                         {"volume_value": 10.0, "open_interest": 2.0})
        self.assertEqual(trial_run._ticker_fields({"volume_value": "10"}),
                         {"volume_value": 10.0, "open_interest": 0.0})


if __name__ == "__main__":
    unittest.main()
