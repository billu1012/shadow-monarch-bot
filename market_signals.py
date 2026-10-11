"""
Market signals for the Discord bot — /signal and the morning brief.

Pulls candles from Yahoo Finance (no API key) and scores them with the same
rules as trading/indicators.js `summarize()` and the Pine indicator (via
signal_math.py), so the bot, the /trading dashboard and TradingView all agree.
"""

import asyncio
import re
import time

import aiohttp

from signal_math import summarize

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


async def get_signals(raw_symbol: str, interval: str = "daily", session: aiohttp.ClientSession | None = None) -> dict:
    data = await get_candles(raw_symbol, interval, session)
    summary = summarize(data["candles"])
    if "error" in summary:
        raise MarketError(f"{data['symbol']}: {summary['error']}")
    last = data["candles"][-1]
    return {**{k: v for k, v in data.items() if k != "candles"}, **summary, "last_bar": last["time"]}
