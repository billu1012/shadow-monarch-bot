# ⚔ Monarch Terminal

A free, legal stand-in for TradingView Premium, built from four pieces:

| # | Piece | What it gives you | Where |
|---|---|---|---|
| 1 | **Lightweight Charts** (TradingView's own open-source lib, Apache-2.0) | Your own TradingView-style chart at `/trading` | `dashboard/`, `routes.js` |
| 2 | **tradingview-mcp** (MIT, unofficial) | Claude reads and drives *your* TradingView Desktop | `tradingview-mcp/` |
| 3 | **Pine Script + community scripts** | A custom indicator with alerts, plus free open-source scripts | `pine/` |
| 4 | **Market data** (Yahoo Finance → Twelve Data → Alpha Vantage) | Real prices for the chart, the signals API and Discord | `market.js`, `../market_signals.py` |

> Why not the "free reverse-engineered TradingView Premium" GitHub repos going around on X?
> They're the standard bait for infostealer malware that targets traders' exchange logins
> and wallets. Don't download them onto any machine that holds keys or funds.

---

## 1 · Chart dashboard

The chart runs inside the existing Express server (`index.js`), so there's nothing extra to deploy.

```bash
npm install
npm start                 # http://localhost:3001/trading
npm test                  # data-layer + indicator tests
```

- Symbols: `AAPL`, `SPY`, `BTC/USD`, `ETH/USD` (or type `BTC` and pick **Crypto**)
- Timeframes: 5m · 15m · 1H · 1D · 1W
- Studies: SMA 20/50, EMA 9, VWAP, RSI, MACD (computed locally, so they cost no API calls)
- Bias badge (bullish / neutral / bearish) and signal list for the latest bar
- Watchlist: click to load, **right-click to remove**, **+ Watch** to add. It's saved per browser.
- Auto-refreshes every 60s, and the server caches responses so your free quota lasts

It works with no API keys (Yahoo Finance). If every provider fails you get the error, never
fake prices. `MARKET_DATA_PROVIDERS=demo` gives labelled demo data for offline work.

### API (for the Discord bot, iPhone Shortcuts, etc.)

| Endpoint | Returns |
|---|---|
| `GET /api/market/candles?symbol=BTC/USD&interval=daily` | OHLCV candles, oldest first |
| `GET /api/market/signals?symbol=NVDA&interval=60min` | close, SMA20/50, RSI14, MACD, `bias`, `signals[]` |
| `GET /api/market/providers` | which data providers are configured |

`interval` is one of `5min`, `15min`, `60min`, `daily`, `weekly`. `market=crypto` is optional
(any `X/Y` symbol is treated as crypto).

## 2 · tradingview-mcp (Claude ↔ your TradingView Desktop)

[tradesdontlie/tradingview-mcp](https://github.com/tradesdontlie/tradingview-mcp) connects to
TradingView Desktop over Chrome DevTools. Claude can then read charts and indicator values,
write and compile Pine, run replay, set alerts and take screenshots. It runs on **your
computer** and needs TradingView Desktop installed. It can't run in a cloud session.

```bat
:: Windows
trading\tradingview-mcp\setup_tradingview_mcp.bat
```
```bash
# macOS / Linux
./trading/tradingview-mcp/setup_tradingview_mcp.sh
```

Each script clones the project to your home folder, installs it, and runs
`claude mcp add tradingview -s user …`. Then:
1. Quit TradingView and relaunch it with the debug script the installer prints.
2. In Claude Code, ask it to run `tv_health_check`.

Before you rely on it, know that it's unofficial. It uses undocumented TradingView internals,
so app updates can break it. The author warns that it may conflict with TradingView's terms on
automated data collection, and that its data must not drive automated trading. Use it as an
analysis assistant, and keep order execution on your broker's or exchange's own API.

## 3 · Pine Script

**Our indicator:** `pine/shadow_monarch_signals.pine`
1. Open TradingView → **Pine Editor** → **New**, paste the file in, and click **Add to chart**.
2. It plots SMA 20/50, shades the background by bias, and marks MACD crosses and bias flips.
3. **Alerts** → Create → Condition: *Shadow Monarch Signals* → choose a signal
   (e.g. *SM: bias turned bullish*). Alerts can go to the app, email or a webhook.

It uses the same scoring as `/api/market/signals`, so the chart and the bot agree.

**Free community scripts:** in TradingView, go to **Indicators → Community** (or
tradingview.com/scripts), filter to **open-source**, and sort by popularity. Paid
"invite-only" scripts are paid for a reason. Anything claiming to unlock them for free,
or asking you to download something to get them, is a scam.

## 4 · Market data

Providers are tried in order, and a keyed provider is skipped when its key isn't set:

| Provider | Free tier | Env var | Role |
|---|---|---|---|
| Yahoo Finance | no key; unofficial, can rate-limit | — | primary |
| [Twelve Data](https://twelvedata.com/account/api-keys) | 800 req/day, 8/min | `TWELVE_DATA_API_KEY` | fallback |
| [Alpha Vantage](https://www.alphavantage.co/support/#api-key) | 25 req/day | `ALPHA_VANTAGE_API_KEY` | fallback |

`MARKET_DATA_PROVIDERS` changes the order (e.g. `twelvedata,yahoo`).
Server-side cache TTLs: 1 min (5m bars), 3 min (15m), 10 min (1H), 30 min (1D), 6 h (1W).

## 5 · Discord: `/signal` and the market brief

`market_signals.py` gives the Python bot the same trend read straight from Yahoo, so it doesn't
depend on the Express server being up. It uses the same scoring as the dashboard and the Pine
indicator, and is cross-checked against the JS version.

- `/signal NVDA` (optionally `interval:60min`): price, day change, bias, RSI, SMA 20/50, signals
- `/brief` (optionally `symbols:AAPL,MSFT,BTC-USD`): one line per symbol plus a bull/bear tally
- Auto-posts the brief to the quest channel on weekdays at `MARKET_BRIEF_TIME` (default 09:00 ET)
  for `MARKET_WATCHLIST`
- Crypto uses Yahoo's format: `BTC-USD` (`BTC/USD` also works)
