"""
Short-term play brief: candle chart, stats, bias tag and a mechanical
long / short / no-trade call, rendered as a Gmail-safe HTML email.

Inputs are Twelve Data's raw semicolon text (the `result` string from the
connector's get_time_series and get_quote), so a scheduled routine can save
those two responses to files and run:

    python3 play_brief.py --symbol QNT/USD --series series.txt --quote quote.txt --out out/

It writes out/brief.html, out/brief.txt, out/subject.txt and out/play.json.

THE RULE (hourly bars):
  LONG      bias bullish  AND close above SMA200 AND RSI below 70
  SHORT     bias bearish  AND close below SMA200 AND RSI above 30
  NO TRADE  anything else
  Entry at the last price; stop 1.5 x ATR(14) away; target 3 x ATR (2R);
  close at market after 24 bars if neither is hit.
The same rule is replayed over the fetched history so every email shows how
it has actually done on this symbol.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from signal_math import atr, rsi, sma, summarize  # noqa: E402

STOP_ATR = 1.5
TARGET_ATR = 3.0
TIME_STOP_BARS = 24
TREND_SMA = 200
CHART_BARS = 20          # Gmail-safe chart limit
CHART_GROUP = 4          # 1h bars per chart candle → 4h candles
CHART_H = 140

PALETTE = {
    "page": "#080808", "card": "#121212", "line": "#242424", "text": "#ffffff",
    "muted": "#8a8a84", "secondary": "#c9c9c4", "blue": "#3987e5", "gold": "#c98500",
    "green": "#0ca30c", "amber": "#fab219", "red": "#d03b3b",
}


# ── parsing ──────────────────────────────────────────────────────────────────

def parse_rows(text: str, required: str) -> list[dict]:
    text = text.strip()
    if text.startswith("{"):
        try:
            j = json.loads(text)
            if isinstance(j.get("result"), str):
                text = j["result"].strip()
        except ValueError:
            pass
    lines = [l for l in text.split("\n") if l.strip()]
    head = lines[0].split(";") if lines else []
    if required not in head:
        raise ValueError(f"Unexpected Twelve Data response: {text[:160]!r}")
    return [dict(zip(head, l.split(";"))) for l in lines[1:]]


def to_unix(dt: str) -> int:
    fmt = "%Y-%m-%d" if len(dt) <= 10 else "%Y-%m-%d %H:%M:%S"
    return int(datetime.strptime(dt, fmt).replace(tzinfo=timezone.utc).timestamp())


def parse_series(text: str) -> list[dict]:
    rows = parse_rows(text, "close")
    candles = sorted(
        ({"time": to_unix(r["datetime"]), "open": float(r["open"]), "high": float(r["high"]),
          "low": float(r["low"]), "close": float(r["close"])} for r in rows),
        key=lambda c: c["time"],
    )
    return [c for i, c in enumerate(candles) if i == 0 or c["time"] != candles[i - 1]["time"]]


def parse_quote(text: str) -> dict:
    rows = parse_rows(text, "close")
    if not rows:
        raise ValueError("Empty quote")
    return rows[0]


# ── the rule ─────────────────────────────────────────────────────────────────

def decide(candles: list[dict]) -> dict:
    """The play for the last bar of `candles`."""
    if len(candles) < TREND_SMA + 1:
        return {"side": "NO TRADE", "reasons": [f"Need {TREND_SMA + 1} hourly bars, have {len(candles)}"]}
    s = summarize(candles)
    closes = [c["close"] for c in candles]
    trend = sma(closes, TREND_SMA)[-1]
    r = s["rsi14"]
    a = atr(candles, 14)
    close = closes[-1]
    above = close > trend

    reasons = [f"Hourly bias is {s['bias']}", f"Price is {'above' if above else 'below'} the 200-hour average"]
    side = "NO TRADE"
    if s["bias"] == "bullish" and above and r < 70:
        side = "LONG"
    elif s["bias"] == "bearish" and not above and r > 30:
        side = "SHORT"
    else:
        if s["bias"] == "neutral":
            reasons.append("Signals are mixed, so there is no edge to lean on")
        elif s["bias"] == "bullish" and not above:
            reasons.append("Bullish bounce inside a downtrend: the trend filter blocks the long")
        elif s["bias"] == "bearish" and above:
            reasons.append("Bearish dip inside an uptrend: the trend filter blocks the short")
        elif r >= 70:
            reasons.append(f"RSI {r:.0f} is stretched; chasing here is poor risk")
        elif r <= 30:
            reasons.append(f"RSI {r:.0f} is washed out; shorting here is poor risk")
    reasons.append(f"RSI {r:.0f}")

    play = {"side": side, "reasons": reasons, "summary": s, "sma200": trend, "atr": a, "entry": close}
    if side != "NO TRADE":
        sign = 1 if side == "LONG" else -1
        play["stop"] = close - sign * STOP_ATR * a
        play["target"] = close + sign * TARGET_ATR * a
    return play


def anchor(play: dict, price: float) -> dict:
    """Re-centre a live play on the current quote, keeping the ATR distances."""
    if play["side"] == "NO TRADE" or not price:
        return play
    sign = 1 if play["side"] == "LONG" else -1
    return {**play, "entry": price, "stop": price - sign * STOP_ATR * play["atr"],
            "target": price + sign * TARGET_ATR * play["atr"]}


def simulate(play: dict, future: list[dict]) -> tuple[float, int] | None:
    """Walk a trade forward. Returns (R multiple, bars held), or None when
    `future` ends before the stop, target or time stop is reached. A bar that
    touches both stop and target counts as the stop (conservative)."""
    sign = 1 if play["side"] == "LONG" else -1
    risk = abs(play["entry"] - play["stop"])
    for k, c in enumerate(future, start=1):
        hit_stop = c["low"] <= play["stop"] if sign == 1 else c["high"] >= play["stop"]
        hit_tgt = c["high"] >= play["target"] if sign == 1 else c["low"] <= play["target"]
        if hit_stop:
            return -1.0, k
        if hit_tgt:
            return TARGET_ATR / STOP_ATR, k
    if len(future) < TIME_STOP_BARS:
        return None
    return sign * (future[-1]["close"] - play["entry"]) / risk, len(future)


def backtest(candles: list[dict]) -> dict:
    """Replay the rule bar by bar. One position at a time; if a bar touches
    both stop and target, count the stop (conservative). No fees."""
    trades = []
    i = TREND_SMA
    n = len(candles)
    while i < n - 1:
        p = decide(candles[: i + 1])
        if p["side"] == "NO TRADE":
            i += 1
            continue
        result = simulate(p, candles[i + 1:i + 1 + TIME_STOP_BARS])
        if result is None:  # history ran out before the trade finished
            break
        exit_r, bars_held = result
        trades.append({"time": candles[i]["time"], "side": p["side"], "r": exit_r})
        i += bars_held + 1
    wins = [t for t in trades if t["r"] > 0]
    total = sum(t["r"] for t in trades)
    return {
        "bars": n,
        "days": round((candles[-1]["time"] - candles[0]["time"]) / 86400, 1) if n > 1 else 0,
        "trades": len(trades),
        "wins": len(wins),
        "win_rate": len(wins) / len(trades) * 100 if trades else 0.0,
        "total_r": total,
        "avg_r": total / len(trades) if trades else 0.0,
        "last": trades[-5:],
    }


# ── email rendering (Gmail mobile-safe: tables, bgcolor attributes, no CSS backgrounds)

P = PALETTE
NB = "&nbsp;"


def esc(s) -> str:
    return html.escape(str(s))


def fmt(v: float) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{v:,.2f}" if abs(v) >= 1 else f"{v:,.4f}"


def pct(v: float) -> str:
    return f"{v:+.2f}%"


SPAN3 = ' colspan="3"'
W40 = ' width="40%"'
W20 = ' width="20%"'


def width_attr(pct_: int) -> str:
    return ' width="' + str(pct_) + '%"'


def cell(h: int, color: str | None = None, extra: str = "") -> str:
    bg = f' bgcolor="{color}"' if color else ""
    return f'<td height="{h}"{bg}{extra} style="font-size:1px;line-height:1px">{NB}</td>'


def group_candles(candles: list[dict], size: int) -> list[dict]:
    """Merge 1h bars into `size`-hour candles, aligned to the end."""
    out = []
    start = len(candles) % size
    for k in range(start, len(candles), size):
        g = candles[k:k + size]
        out.append({"time": g[0]["time"], "open": g[0]["open"], "high": max(c["high"] for c in g),
                    "low": min(c["low"] for c in g), "close": g[-1]["close"]})
    return out


def candle_chart(candles: list[dict]) -> str:
    bars = group_candles(candles, CHART_GROUP)[-CHART_BARS:]
    hi = max(c["high"] for c in bars)
    lo = min(c["low"] for c in bars)
    span = (hi - lo) or 1
    y = lambda v: round((hi - v) / span * CHART_H)
    cols = []
    for c in bars:
        color = P["green"] if c["close"] >= c["open"] else P["red"]
        top, btop = y(c["high"]), y(max(c["open"], c["close"]))
        bbot, bot = y(min(c["open"], c["close"])), y(c["low"])
        bbot = max(bbot, btop + 2)
        bot = max(bot, bbot)
        segs = [("pad", top), ("wick", btop - top), ("body", bbot - btop), ("wick", bot - bbot), ("pad", CHART_H - bot)]
        rows = []
        for kind, h in segs:
            if h <= 0:
                continue
            if kind == "pad":
                rows.append("<tr>" + cell(h, extra=SPAN3) + "</tr>")
            elif kind == "body":
                rows.append("<tr>" + cell(h, color, SPAN3) + "</tr>")
            else:
                rows.append("<tr>" + cell(h, extra=W40) + cell(h, color, W20) + cell(h, extra=W40) + "</tr>")
        cols.append(
            '<td valign="bottom" style="padding:0 1px"><table width="100%" border="0" cellpadding="0" cellspacing="0">'
            + "".join(rows) + "</table></td>"
        )
    t0 = datetime.fromtimestamp(bars[0]["time"], timezone.utc).strftime("%b %d %H:%M")
    t1 = datetime.fromtimestamp(bars[-1]["time"], timezone.utc).strftime("%b %d %H:%M")
    return (
        f'<table width="100%" border="0" cellpadding="0" cellspacing="0"><tr>{"".join(cols)}</tr></table>'
        f'<table width="100%" border="0" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="font-size:11px;color:{P["muted"]};padding-top:4px">{esc(t0)} UTC · low {fmt(lo)}</td>'
        f'<td align="right" style="font-size:11px;color:{P["muted"]};padding-top:4px">high {fmt(hi)} · {esc(t1)} UTC</td>'
        f'</tr></table>'
    )


def sparkline(values: list[float], width: int = 26) -> str:
    blocks = "▁▂▃▄▅▆▇█"
    step = max(1, math.ceil(len(values) / width))
    pts = values[::-1][::step][::-1][-width:]
    lo, hi = min(pts), max(pts)
    return "".join(blocks[int((v - lo) / ((hi - lo) or 1) * (len(blocks) - 1))] for v in pts)


def ladder(play: dict) -> str:
    """Stop → entry → target as one horizontal bar."""
    lo, hi = sorted([play["stop"], play["target"]])
    entry_pct = round((play["entry"] - lo) / (hi - lo) * 100)
    left_color, right_color = (P["red"], P["green"]) if play["side"] == "LONG" else (P["green"], P["red"])
    left_w, right_w = max(1, entry_pct - 1), max(1, 100 - entry_pct - 1)
    bar = (
        '<table width="100%" border="0" cellpadding="0" cellspacing="0"><tr>'
        + cell(14, left_color, width_attr(left_w)) + cell(14, P["text"], width_attr(2)) + cell(14, right_color, width_attr(right_w))
        + "</tr></table>"
    )
    left_lbl, right_lbl = ("Stop", "Target") if play["side"] == "LONG" else ("Target", "Stop")
    labels = (
        '<table width="100%" border="0" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="font-size:11px;color:{P["muted"]};padding-top:4px">{left_lbl} {fmt(lo)}</td>'
        f'<td align="center" style="font-size:11px;color:{P["text"]};padding-top:4px">Entry {fmt(play["entry"])}</td>'
        f'<td align="right" style="font-size:11px;color:{P["muted"]};padding-top:4px">{right_lbl} {fmt(hi)}</td>'
        "</tr></table>"
    )
    return bar + labels


def card(inner: str) -> str:
    return (
        f'<tr><td style="padding:6px 0"><table width="100%" border="0" cellpadding="0" cellspacing="0" bgcolor="{P["card"]}">'
        f'<tr><td style="padding:16px">{inner}</td></tr></table></td></tr>'
    )


def label(t: str) -> str:
    return f'<div style="font-size:10px;letter-spacing:1px;text-transform:uppercase;color:{P["muted"]};padding-bottom:4px">{esc(t)}</div>'


def metric_grid(items: list[tuple[str, str, str]]) -> str:
    rows = []
    for k in range(0, len(items), 2):
        tds = []
        for name, value, sub in items[k:k + 2]:
            tds.append(
                f'<td width="50%" valign="top" style="padding:8px 8px 8px 0">{label(name)}'
                f'<div style="font-size:21px;font-weight:bold;color:{P["text"]}">{value}</div>'
                + (f'<div style="font-size:11px;color:{P["muted"]}">{esc(sub)}</div>' if sub else "")
                + "</td>"
            )
        if len(tds) == 1:
            tds.append(f'<td width="50%" style="font-size:1px">{NB}</td>')
        rows.append("<tr>" + "".join(tds) + "</tr>")
    return '<table width="100%" border="0" cellpadding="0" cellspacing="0">' + "".join(rows) + "</table>"


def render(symbol: str, candles: list[dict], quote: dict, play: dict, bt: dict) -> tuple[str, str, str]:
    s = play.get("summary") or summarize(candles)
    price = float(quote.get("close") or candles[-1]["close"])
    d1 = float(quote.get("rolling_1d_change") or 0)
    d7 = float(quote.get("rolling_7d_change") or 0)
    lo52, hi52 = float(quote.get("fifty_two_week_low") or 0), float(quote.get("fifty_two_week_high") or 0)
    name = quote.get("name") or symbol
    exch = quote.get("exchange") or ""
    side = play["side"]
    side_color = {"LONG": P["green"], "SHORT": P["red"]}.get(side, P["amber"])
    bias_color = {"bullish": P["green"], "bearish": P["red"]}.get(s["bias"], P["amber"])
    now = datetime.now(timezone.utc).strftime("%a %b %d · %H:%M UTC")
    a = play.get("atr") or 0

    # Play card
    if side == "NO TRADE":
        play_rows = f'<div style="font-size:14px;color:{P["secondary"]};padding-top:6px">Stand aside. The rule only trades when bias and trend agree.</div>'
    else:
        risk_pct = abs(play["entry"] - play["stop"]) / play["entry"] * 100
        rew_pct = abs(play["target"] - play["entry"]) / play["entry"] * 100
        play_rows = metric_grid([
            ("Entry", fmt(play["entry"]), "live price"),
            ("Stop", fmt(play["stop"]), f"{risk_pct:.1f}% away · {STOP_ATR:g}× ATR"),
            ("Target", fmt(play["target"]), f"{rew_pct:.1f}% away · {TARGET_ATR:g}× ATR"),
            ("Time stop", f"{TIME_STOP_BARS}h", f"risk:reward 1:{TARGET_ATR / STOP_ATR:g}"),
        ]) + f'<div style="padding-top:10px">{ladder(play)}</div>'
    why = "".join(f'<div style="font-size:13px;color:{P["secondary"]};padding-top:3px">· {esc(r)}</div>' for r in play["reasons"])
    play_card = (
        label("Short-term play · hourly bars")
        + f'<div style="font-size:30px;font-weight:bold;color:{side_color};letter-spacing:1px">{side}</div>'
        + play_rows
        + f'<div style="padding-top:10px">{why}</div>'
    )

    # Backtest card
    if bt["trades"]:
        plural = lambda n, word: f"{n} {word}" + ("" if n == 1 else "s")
        bt_line = (f'{plural(bt["trades"], "trade")} · {plural(bt["wins"], "win")} ({bt["win_rate"]:.0f}%) · '
                   f'net {bt["total_r"]:+.1f}R · avg {bt["avg_r"]:+.2f}R per trade')
        recent = " ".join(f'{"▲" if t["side"] == "LONG" else "▼"}{t["r"]:+.1f}R' for t in bt["last"])
    else:
        bt_line, recent = "No trades fired in this window", ""
    small = bt["trades"] < 20
    bt_card = (
        label(f"This rule on {symbol}, last {bt['days']:g} days")
        + f'<div style="font-size:15px;color:{P["text"]}">{esc(bt_line)}</div>'
        + (f'<div style="font-size:12px;color:{P["muted"]};padding-top:4px">Recent: {esc(recent)}</div>' if recent else "")
        + f'<div style="font-size:11px;color:{P["muted"]};padding-top:6px">'
        + ("Small sample, so treat this as a sanity check, not proof. " if small else "")
        + "1R = the distance to the stop. No fees or slippage counted.</div>"
    )

    pos52 = (price - lo52) / (hi52 - lo52) * 100 if hi52 > lo52 else 0
    stats = metric_grid([
        ("Bias", f'<span style="color:{bias_color}">{s["bias"].upper()}</span>', "same read as /signal and the chart"),
        ("RSI 14 (1h)", f'{s["rsi14"]:.1f}', "70+ stretched · 30− washed out"),
        ("24h", f'<span style="color:{P["green"] if d1 >= 0 else P["red"]}">{pct(d1)}</span>', ""),
        ("7d", f'<span style="color:{P["green"] if d7 >= 0 else P["red"]}">{pct(d7)}</span>', ""),
        ("SMA 20 / 50", f'{fmt(s["sma20"])}', f'50h: {fmt(s["sma50"])}'),
        ("SMA 200 (1h)", fmt(play.get("sma200")), "trend filter"),
        ("ATR 14 (1h)", fmt(a), f"{a / price * 100:.2f}% typical hourly range" if price else ""),
        ("52-week", f"{pos52:.0f}%", f"of range {fmt(lo52)} – {fmt(hi52)}"),
    ])

    chg_color = P["green"] if d1 >= 0 else P["red"]
    header = (
        f'<div style="font-size:26px;font-weight:bold;color:{P["text"]}">{esc(symbol)}</div>'
        f'<div style="font-size:13px;color:{P["muted"]}">{esc(name)} · {esc(exch)}</div>'
        f'<div style="padding-top:8px"><span style="font-size:21px;font-weight:bold;color:{P["text"]}">{fmt(price)}</span>'
        f' <span style="font-size:14px;color:{chg_color}">{pct(d1)} 24h</span></div>'
        f'<div style="font-size:11px;color:{P["muted"]};padding-top:2px">{esc(now)}</div>'
    )
    closes = [c["close"] for c in candles[-80:]]
    chart = (
        label(f"Last {CHART_BARS * CHART_GROUP} hours · {CHART_GROUP}h candles")
        + candle_chart(candles)
        + f'<div style="font-family:monospace;white-space:nowrap;font-size:12px;color:{P["muted"]};padding-top:6px">{sparkline(closes)} <span style="font-size:10px">text fallback</span></div>'
    )
    footer = (
        f'<div style="font-size:11px;color:{P["muted"]};line-height:16px">Mechanical signal from hourly bars via Twelve Data. '
        "It is a rule, not a forecast, and not financial advice. Size positions so a stop-out is a loss you are fine taking.</div>"
    )
    body = (
        f'<table width="100%" bgcolor="{P["page"]}" border="0" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:20px 10px">'
        f'<table width="100%" border="0" cellpadding="0" cellspacing="0" style="max-width:420px;font-family:Helvetica,Arial,sans-serif">'
        + card(header) + card(play_card) + card(chart) + card(stats) + card(bt_card)
        + f'<tr><td style="padding:10px 4px">{footer}</td></tr>'
        + "</table></td></tr></table>"
    )

    subject = f"{symbol} {side} — {fmt(price)}, bias {s['bias']}"
    if side != "NO TRADE":
        subject += f", stop {fmt(play['stop'])} / target {fmt(play['target'])}"

    text = [f"{symbol} — {name} ({exch})", f"Price {fmt(price)} · 24h {pct(d1)} · 7d {pct(d7)}", "",
            f"PLAY: {side}"]
    if side != "NO TRADE":
        text += [f"  Entry {fmt(play['entry'])}", f"  Stop {fmt(play['stop'])} ({STOP_ATR:g}x ATR)",
                 f"  Target {fmt(play['target'])} ({TARGET_ATR:g}x ATR, 1:{TARGET_ATR / STOP_ATR:g})",
                 f"  Time stop {TIME_STOP_BARS}h"]
    text += ["  Why: " + "; ".join(play["reasons"]), "",
             f"Bias {s['bias']} · RSI {s['rsi14']:.1f} · SMA20 {fmt(s['sma20'])} · SMA50 {fmt(s['sma50'])} · SMA200 {fmt(play.get('sma200'))} · ATR {fmt(a)}",
             f"52-week: {fmt(lo52)} – {fmt(hi52)} ({pos52:.0f}% of range)",
             f"Last 80h: {sparkline(closes)}", "",
             f"Backtest, last {bt['days']:g} days: {bt_line}" + (" (small sample)" if small else ""), "",
             "Mechanical signal, not financial advice."]
    return subject, body, "\n".join(text)


def check_email_html(body: str) -> None:
    """The mobile Gmail rules the other briefs follow."""
    problems = []
    if re.search(r'style="[^"]*background(?!-)', body):
        problems.append("CSS background found")
    if re.search(r"<td[^>]*>\s*</td>", body):
        problems.append("empty <td> found")
    if "data:" in body:
        problems.append("data: URI found")
    if len(body.encode()) >= 100_000:
        problems.append(f"too large ({len(body.encode())} bytes)")
    if problems:
        raise ValueError("Email HTML failed checks: " + "; ".join(problems))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--series", required=True, help="Twelve Data get_time_series result (interval 1h)")
    ap.add_argument("--quote", required=True, help="Twelve Data get_quote result")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    candles = parse_series(Path(args.series).read_text())
    quote = parse_quote(Path(args.quote).read_text())
    play = anchor(decide(candles), float(quote.get("close") or 0))
    bt = backtest(candles)
    subject, body, text = render(args.symbol, candles, quote, play, bt)
    check_email_html(body)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "brief.html").write_text(body)
    (out / "brief.txt").write_text(text)
    (out / "subject.txt").write_text(subject)
    summary = {k: v for k, v in play.items() if k != "summary"}
    summary["bias"] = play.get("summary", {}).get("bias")
    (out / "play.json").write_text(json.dumps({"play": summary, "backtest": bt}, indent=2))
    print(subject)


if __name__ == "__main__":
    main()
