"""
Market signals for the Discord bot — /signal and the morning brief.

Pulls candles from Yahoo Finance (no API key) and scores them with the same
rules as trading/indicators.js `summarize()` and the Pine indicator, so the bot,
the /trading dashboard and TradingView all agree on the same bar.
"""

import asyncio
import re
import time

import aiohttp

# interval → (yahoo interval, range)
INTERVALS = {
    "5min": ("5m", "5d"),
    "15min": ("15m", "1mo"),
    "60min": ("60m", "3mo"),
    "daily": ("1d", "2y"),
    "weekly": ("1wk", "10y"),
}
CACHE_TTL = {"5min": 60, "15min": 180, "60min": 600, "daily": 1800, "weekly": 21600}
_SYMBOL_RE = re.compile(r"^[A-Z0-9.\-]{1,12}([/\-][A-Z]{2,6})?$")
_cache: dict[tuple[str, str], tuple[float, dict]] = {}


class MarketError(Exception):
    pass


def yahoo_symbol(raw: str) -> str:
    """'btc/usd' → 'BTC-USD', 'aapl' → 'AAPL'."""
    s = (raw or "").strip().upper().replace("/", "-")
    if not _SYMBOL_RE.match(s):
        raise MarketError(f"Invalid symbol `{raw}`")
    return s


async def get_candles(raw_symbol: str, interval: str = "daily", session: aiohttp.ClientSession | None = None) -> dict:
    if interval not in INTERVALS:
        raise MarketError(f"interval must be one of {', '.join(INTERVALS)}")
    symbol = yahoo_symbol(raw_symbol)
    key = (symbol, interval)
    hit = _cache.get(key)
    if hit and hit[0] > time.time():
        return hit[1]

    y_interval, y_range = INTERVALS[interval]
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"interval": y_interval, "range": y_range, "includePrePost": "false"}
    headers = {"User-Agent": "Mozilla/5.0 (shadow-monarch-bot)"}
    own = session is None
    session = session or aiohttp.ClientSession()
    try:
        async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                raise MarketError(f"Yahoo returned HTTP {resp.status} for {symbol}")
            data = await resp.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        raise MarketError(f"Couldn't reach Yahoo Finance: {e}") from e
    finally:
        if own:
            await session.close()

    result = ((data.get("chart") or {}).get("result") or [None])[0]
    if not result:
        err = (data.get("chart") or {}).get("error") or {}
        raise MarketError(err.get("description") or f"No data for {symbol}")
    candles = parse_yahoo(result)
    if not candles:
        raise MarketError(f"No data for {symbol}")

    out = {
        "symbol": symbol,
        "name": result.get("meta", {}).get("shortName") or symbol,
        "currency": result.get("meta", {}).get("currency", ""),
        "interval": interval,
        "candles": candles,
    }
    _cache[key] = (time.time() + CACHE_TTL[interval], out)
    return out


def parse_yahoo(result: dict) -> list[dict]:
    q = (result.get("indicators", {}).get("quote") or [{}])[0]
    candles = []
    for i, t in enumerate(result.get("timestamp") or []):
        vals = [(q.get(k) or [None] * (i + 1))[i] for k in ("open", "high", "low", "close")]
        if any(v is None for v in vals):  # Yahoo pads halted/partial bars with nulls
            continue
        vol = (q.get("volume") or [0] * (i + 1))[i] or 0
        candles.append({"time": t, "open": vals[0], "high": vals[1], "low": vals[2], "close": vals[3], "volume": vol})
    candles.sort(key=lambda c: c["time"])
    return [c for i, c in enumerate(candles) if i == 0 or c["time"] != candles[i - 1]["time"]]


# ── indicators (mirror trading/indicators.js) ────────────────────────────────

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


async def get_signals(raw_symbol: str, interval: str = "daily", session: aiohttp.ClientSession | None = None) -> dict:
    data = await get_candles(raw_symbol, interval, session)
    summary = summarize(data["candles"])
    if "error" in summary:
        raise MarketError(f"{data['symbol']}: {summary['error']}")
    last = data["candles"][-1]
    return {**{k: v for k, v in data.items() if k != "candles"}, **summary, "last_bar": last["time"]}
