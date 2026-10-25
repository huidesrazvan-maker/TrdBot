import unittest

from trdbot.filters import spot_leverage_volume_filter as f


class SpotLeverageVolumeFilterTest(unittest.TestCase):
    def test_strong_spot_confirmation(self):
        r = f(100.0, 300.0, 5.0, 0.0001)
        self.assertTrue(r["pass"])
        self.assertEqual(r["ratio"], 3.0)
        self.assertIn("strong spot confirmation", r["reason"])

    def test_leverage_heavy_but_acceptable(self):
        r = f(100.0, 1000.0, 5.0, 0.0001)
        self.assertTrue(r["pass"])
        self.assertIn("leverage-heavy", r["reason"])

    def test_ratio_at_limit_passes(self):
        self.assertTrue(f(100.0, 1200.0, 0.0, 0.0)["pass"])

    def test_ratio_over_limit_fails(self):
        r = f(100.0, 1300.0, 0.0, 0.0)
        self.assertFalse(r["pass"])
        self.assertEqual(r["ratio"], 13.0)

    def test_crowded_positioning_fails(self):
        r = f(100.0, 500.0, 25.0, -0.05)
        self.assertFalse(r["pass"])
        self.assertIn("crowded", r["reason"])

    def test_high_funding_without_oi_growth_passes(self):
        self.assertTrue(f(100.0, 500.0, 10.0, 0.05)["pass"])

    def test_custom_funding_threshold(self):
        r = f(100.0, 500.0, 25.0, 0.001, max_abs_funding_rate=0.0005)
        self.assertFalse(r["pass"])

    def test_bad_inputs_fail(self):
        for args in [(0.0, 100.0), (-1.0, 100.0), (100.0, -1.0), (float("nan"), 100.0), (100.0, float("inf"))]:
            r = f(*args, 0.0, 0.0)
            self.assertFalse(r["pass"], args)
            self.assertIsNone(r["ratio"])

    def test_consistent_keys(self):
        keys = {"pass", "reason", "ratio", "oi_change", "funding"}
        self.assertEqual(set(f(100.0, 300.0, 0.0, 0.0)), keys)
        self.assertEqual(set(f(0.0, 300.0, 0.0, 0.0)), keys)
        self.assertEqual(set(f(100.0, 3000.0, 0.0, 0.0)), keys)


if __name__ == "__main__":
    unittest.main()
