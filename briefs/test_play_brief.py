"""Run: python3 -m unittest discover briefs"""

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import play_brief as pb  # noqa: E402


def trend(n, start=100.0, step=0.002, wiggle=0.01, phase=0):
    """Hourly candles drifting by `step` per bar with a gentle wave."""
    out, p = [], start
    for i in range(n):
        o = p
        p = p * (1 + step + wiggle * math.sin((i + phase) / 3))
        out.append({"time": 1_700_000_000 + i * 3600, "open": o, "high": max(o, p) * 1.003,
                    "low": min(o, p) * 0.997, "close": p})
    return out


# Wavy drifts whose last bar sits mid-swing (RSI ~52 and ~39), so the rule fires.
def up(n=260):
    return trend(n, step=0.001, wiggle=0.01, phase=0)


def down(n=260):
    return trend(n, step=-0.001, wiggle=0.01, phase=8)


QUOTE = {"close": "120", "rolling_1d_change": "1.5", "rolling_7d_change": "-2", "name": "Test Coin",
         "exchange": "Binance", "fifty_two_week_low": "50", "fifty_two_week_high": "200"}


class ParseTests(unittest.TestCase):
    def test_series_sorted_and_utc(self):
        text = "datetime;open;high;low;close\n2026-10-11 10:00:00;2;3;1;2.5\n2026-10-11 09:00:00;1;2;0.5;2\n"
        c = pb.parse_series(text)
        self.assertEqual([x["close"] for x in c], [2.0, 2.5])
        self.assertEqual(c[1]["time"], 1791712800)

    def test_json_wrapped_result(self):
        self.assertEqual(pb.parse_quote('{"result": "symbol;close\\nQNT/USD;242.67"}')["close"], "242.67")

    def test_error_text_rejected(self):
        with self.assertRaises(ValueError):
            pb.parse_series("Error: symbol not found")


class RuleTests(unittest.TestCase):
    def test_uptrend_goes_long_with_levels(self):
        c = up()
        p = pb.decide(c)
        self.assertEqual(p["side"], "LONG")
        self.assertAlmostEqual(p["entry"] - p["stop"], pb.STOP_ATR * p["atr"])
        self.assertAlmostEqual(p["target"] - p["entry"], pb.TARGET_ATR * p["atr"])

    def test_downtrend_goes_short(self):
        p = pb.decide(down())
        self.assertEqual(p["side"], "SHORT")
        self.assertGreater(p["stop"], p["entry"])
        self.assertLess(p["target"], p["entry"])

    def test_not_enough_history(self):
        self.assertEqual(pb.decide(trend(150))["side"], "NO TRADE")

    def test_trend_filter_blocks_counter_trend_long(self):
        # Long decline, then a short sharp bounce: bullish bias but below SMA200.
        c = trend(240, step=-0.003, wiggle=0.002) + trend(30, start=0, step=0.01, wiggle=0.001)
        last = c[239]["close"]
        bounce = trend(30, start=last, step=0.006, wiggle=0.001)
        for k, b in enumerate(bounce):
            b["time"] = c[239]["time"] + (k + 1) * 3600
        c = c[:240] + bounce
        p = pb.decide(c)
        if p["summary"]["bias"] == "bullish":
            self.assertEqual(p["side"], "NO TRADE")
            self.assertTrue(any("trend filter" in r for r in p["reasons"]))


    def test_anchor_recentres_on_live_price(self):
        p = pb.anchor(pb.decide(up()), 150.0)
        self.assertEqual(p["entry"], 150.0)
        self.assertAlmostEqual(150.0 - p["stop"], pb.STOP_ATR * p["atr"])
        self.assertEqual(pb.anchor({"side": "NO TRADE", "reasons": []}, 150.0)["side"], "NO TRADE")


class BacktestTests(unittest.TestCase):
    def test_counts_and_r_values(self):
        bt = pb.backtest(trend(400, step=0.001, wiggle=0.01))
        self.assertGreater(bt["trades"], 0)
        for t in bt["last"]:
            self.assertGreaterEqual(t["r"], -1.0 - 1e-9)
            self.assertLessEqual(t["r"], pb.TARGET_ATR / pb.STOP_ATR + 1e-9)

    def test_simulate_exits(self):
        play = {"side": "LONG", "entry": 100.0, "stop": 97.0, "target": 106.0}
        bar = lambda lo, hi, close=100.0: {"low": lo, "high": hi, "close": close}
        self.assertEqual(pb.simulate(play, [bar(99, 101), bar(96, 101)]), (-1.0, 2))
        self.assertEqual(pb.simulate(play, [bar(99, 107)]), (2.0, 1))
        self.assertEqual(pb.simulate(play, [bar(96, 107)]), (-1.0, 1))  # tie → stop
        self.assertIsNone(pb.simulate(play, [bar(99, 101)] * 3))       # unfinished
        flat = [bar(99, 101, 101.5)] * pb.TIME_STOP_BARS
        self.assertEqual(pb.simulate(play, flat), (0.5, pb.TIME_STOP_BARS))  # time stop
        short = {"side": "SHORT", "entry": 100.0, "stop": 103.0, "target": 94.0}
        self.assertEqual(pb.simulate(short, [bar(93, 101)]), (2.0, 1))


class RenderTests(unittest.TestCase):
    def test_email_passes_gmail_checks_for_every_side(self):
        sides = set()
        for c in (up(), down(), up(150)):
            p = pb.decide(c)
            subject, body, text = pb.render("TEST/USD", c, QUOTE, p, pb.backtest(c))
            pb.check_email_html(body)
            sides.add(p["side"])
            self.assertIn(p["side"], subject)
            self.assertIn(p["side"], text)
        self.assertEqual(sides, {"LONG", "SHORT", "NO TRADE"})

    def test_checks_catch_bad_markup(self):
        for bad in ('<td style="background:#000">x</td>', "<td></td>", '<img src="data:image/png;base64,AA">'):
            with self.assertRaises(ValueError):
                pb.check_email_html(bad)


if __name__ == "__main__":
    unittest.main()
