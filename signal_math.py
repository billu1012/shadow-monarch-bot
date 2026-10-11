"""
Indicator math shared by the Discord bot (market_signals.py) and the email
briefs (briefs/play_brief.py). Pure Python, no dependencies.

Mirrors trading/indicators.js `summarize()` and the Pine indicator, so every
surface gives the same bullish / neutral / bearish read for the same bars.
Candles are dicts with time, open, high, low, close, sorted oldest first.
"""

from __future__ import annotations


def sma(values: list[float], period: int) -> list[float]:
    return [sum(values[i - period + 1:i + 1]) / period for i in range(period - 1, len(values))]


def ema(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        return []
    k = 2 / (period + 1)
    out = [sum(values[:period]) / period]
    for v in values[period:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(values: list[float], period: int = 14) -> list[float]:
    """Wilder's RSI."""
    if len(values) <= period:
        return []
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    gain = sum(max(d, 0) for d in deltas[:period]) / period
    loss = sum(max(-d, 0) for d in deltas[:period]) / period
    val = lambda: 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)
    out = [val()]
    for d in deltas[period:]:
        gain = (gain * (period - 1) + max(d, 0)) / period
        loss = (loss * (period - 1) + max(-d, 0)) / period
        out.append(val())
    return out


def macd_hist(values: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> list[float]:
    fast_e, slow_e = ema(values, fast), ema(values, slow)
    line = [f - s for f, s in zip(fast_e[slow - fast:], slow_e)]
    sig = ema(line, signal)
    return [m - s for m, s in zip(line[signal - 1:], sig)]


def atr(candles: list[dict], period: int = 14) -> float | None:
    """Wilder's average true range of the latest bar."""
    if len(candles) <= period:
        return None
    trs = [
        max(c["high"] - c["low"], abs(c["high"] - p["close"]), abs(c["low"] - p["close"]))
        for p, c in zip(candles, candles[1:])
    ]
    a = sum(trs[:period]) / period
    for tr in trs[period:]:
        a = (a * (period - 1) + tr) / period
    return a


def summarize(candles: list[dict]) -> dict:
    if len(candles) < 50:
        return {"error": "Need at least 50 candles for signals"}
    closes = [c["close"] for c in candles]
    close = closes[-1]
    sma20, sma50 = sma(closes, 20)[-1], sma(closes, 50)[-1]
    r = rsi(closes, 14)[-1]
    hist = macd_hist(closes)
    h_now = hist[-1] if hist else None
    h_prev = hist[-2] if len(hist) > 1 else None

    signals = []
    if r >= 70:
        signals.append("RSI overbought")
    elif r <= 30:
        signals.append("RSI oversold")
    if h_now is not None and h_prev is not None:
        if h_prev <= 0 < h_now:
            signals.append("MACD bullish cross")
        if h_prev >= 0 > h_now:
            signals.append("MACD bearish cross")
    signals.append("SMA20 above SMA50 (uptrend)" if sma20 > sma50 else "SMA20 below SMA50 (downtrend)")

    score = (1 if sma20 > sma50 else -1) + (1 if close > sma20 else -1) + (1 if (h_now or 0) > 0 else -1)
    if r >= 70:
        score -= 1
    if r <= 30:
        score += 1
    bias = "bullish" if score >= 2 else "bearish" if score <= -2 else "neutral"

    prev = closes[-2]
    return {
        "close": close,
        "change": close - prev,
        "change_pct": (close - prev) / prev * 100 if prev else 0.0,
        "sma20": sma20,
        "sma50": sma50,
        "rsi14": r,
        "macd_hist": h_now,
        "bias": bias,
        "signals": signals,
    }
