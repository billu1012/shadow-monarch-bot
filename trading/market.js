// Market data layer: normalizes Twelve Data and Alpha Vantage into one candle
// shape, with an in-memory cache so the free-tier quotas last.
//
//   Twelve Data   — TWELVE_DATA_API_KEY   (free: 800 req/day, 8/min)
//   Alpha Vantage — ALPHA_VANTAGE_API_KEY (free: 25 req/day)
//
// Order: Twelve Data first (bigger quota), Alpha Vantage as fallback. With no
// keys set at all, a clearly-labelled demo feed is served so the dashboard
// still renders. Demo data is never used to cover for a failing real provider.

export const INTERVALS = ["5min", "15min", "60min", "daily", "weekly"];

const TD_INTERVAL = { "5min": "5min", "15min": "15min", "60min": "1h", daily: "1day", weekly: "1week" };
const CACHE_TTL_MS = { "5min": 60e3, "15min": 3 * 60e3, "60min": 10 * 60e3, daily: 30 * 60e3, weekly: 6 * 3600e3 };
const FETCH_TIMEOUT_MS = 15e3;

const cache = new Map();

export class MarketDataError extends Error {
  constructor(message, status = 502) {
    super(message);
    this.status = status;
  }
}

// "btc/usd" → crypto BTC quoted in USD; "aapl" → stock AAPL.
export function parseSymbol(raw, marketHint) {
  const s = String(raw || "").trim().toUpperCase();
  if (!/^[A-Z0-9.\-]{1,12}(\/[A-Z]{2,6})?$/.test(s)) {
    throw new MarketDataError(`Invalid symbol "${raw}"`, 400);
  }
  if (s.includes("/")) {
    const [base, quote] = s.split("/");
    return { market: "crypto", base, quote, display: s };
  }
  if (marketHint === "crypto") return { market: "crypto", base: s, quote: "USD", display: `${s}/USD` };
  return { market: "stock", base: s, quote: null, display: s };
}

export function configuredProviders() {
  const list = [];
  if (process.env.TWELVE_DATA_API_KEY) list.push("twelvedata");
  if (process.env.ALPHA_VANTAGE_API_KEY) list.push("alphavantage");
  return list;
}

export async function getCandles(rawSymbol, interval = "daily", marketHint) {
  if (!INTERVALS.includes(interval)) {
    throw new MarketDataError(`interval must be one of ${INTERVALS.join(", ")}`, 400);
  }
  const sym = parseSymbol(rawSymbol, marketHint);
  const key = `${sym.display}|${interval}`;
  const hit = cache.get(key);
  if (hit && hit.expires > Date.now()) return { ...hit.data, cached: true };

  const providers = configuredProviders();
  let data;
  if (providers.length === 0) {
    data = { provider: "demo", demo: true, candles: demoCandles(sym.display, interval) };
  } else {
    const errors = [];
    for (const p of providers) {
      try {
        const candles = p === "twelvedata"
          ? await fetchTwelveData(sym, interval)
          : await fetchAlphaVantage(sym, interval);
        data = { provider: p, demo: false, candles };
        break;
      } catch (err) {
        errors.push(`${p}: ${err.message}`);
      }
    }
    if (!data) throw new MarketDataError(errors.join(" | "));
  }

  data = { symbol: sym.display, market: sym.market, interval, ...data };
  cache.set(key, { expires: Date.now() + CACHE_TTL_MS[interval], data });
  return { ...data, cached: false };
}

// ── Providers ───────────────────────────────────────────────────

async function getJson(url) {
  const res = await fetch(url, { signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// Provider timestamps are exchange-local strings; treat them as UTC so bars
// line up without a timezone database. Good enough for charting.
function toUnix(str) {
  const iso = str.length <= 10 ? `${str}T00:00:00Z` : `${str.replace(" ", "T")}Z`;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) throw new Error(`Bad timestamp "${str}"`);
  return Math.floor(t / 1000);
}

function sortAndDedupe(candles) {
  candles.sort((a, b) => a.time - b.time);
  return candles.filter((c, i) => i === 0 || c.time !== candles[i - 1].time);
}

async function fetchTwelveData(sym, interval) {
  const symbol = sym.market === "crypto" ? `${sym.base}/${sym.quote}` : sym.base;
  const url = new URL("https://api.twelvedata.com/time_series");
  url.search = new URLSearchParams({
    symbol,
    interval: TD_INTERVAL[interval],
    outputsize: "300",
    apikey: process.env.TWELVE_DATA_API_KEY,
  });
  const json = await getJson(url);
  if (json.status === "error") throw new Error(json.message || "Twelve Data error");
  if (!Array.isArray(json.values)) throw new Error("Unexpected Twelve Data response");
  return sortAndDedupe(json.values.map(v => ({
    time: toUnix(v.datetime),
    open: +v.open,
    high: +v.high,
    low: +v.low,
    close: +v.close,
    volume: v.volume !== undefined ? +v.volume : 0,
  })));
}

async function fetchAlphaVantage(sym, interval) {
  const intraday = interval.endsWith("min");
  const params = { apikey: process.env.ALPHA_VANTAGE_API_KEY };
  if (sym.market === "crypto") {
    Object.assign(params, { symbol: sym.base, market: sym.quote });
    if (intraday) Object.assign(params, { function: "CRYPTO_INTRADAY", interval, outputsize: "compact" });
    else params.function = interval === "weekly" ? "DIGITAL_CURRENCY_WEEKLY" : "DIGITAL_CURRENCY_DAILY";
  } else {
    params.symbol = sym.base;
    if (intraday) Object.assign(params, { function: "TIME_SERIES_INTRADAY", interval, outputsize: "compact" });
    else if (interval === "weekly") params.function = "TIME_SERIES_WEEKLY";
    else Object.assign(params, { function: "TIME_SERIES_DAILY", outputsize: "compact" });
  }
  const url = new URL("https://www.alphavantage.co/query");
  url.search = new URLSearchParams(params);
  const json = await getJson(url);

  // Quota and premium-endpoint messages come back as 200s with these keys.
  const notice = json["Error Message"] || json.Note || json.Information;
  if (notice) throw new Error(notice);
  const seriesKey = Object.keys(json).find(k => k.startsWith("Time Series"));
  if (!seriesKey) throw new Error("Unexpected Alpha Vantage response");

  // Field names vary by endpoint ("1. open" vs legacy "1a. open (USD)"), so
  // match on the field name rather than the exact key.
  const pick = (row, name) => {
    const k = Object.keys(row).find(f => f.replace(/^\d+[a-z]?\.\s*/, "").startsWith(name));
    return k ? +row[k] : 0;
  };
  return sortAndDedupe(Object.entries(json[seriesKey]).map(([ts, row]) => ({
    time: toUnix(ts),
    open: pick(row, "open"),
    high: pick(row, "high"),
    low: pick(row, "low"),
    close: pick(row, "close"),
    volume: pick(row, "volume"),
  })));
}

// Deterministic random walk seeded by symbol, so the demo chart is stable
// between refreshes.
function demoCandles(symbol, interval) {
  let seed = [...symbol].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7);
  const rand = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 2 ** 32);
  const step = { "5min": 300, "15min": 900, "60min": 3600, daily: 86400, weekly: 604800 }[interval];
  const n = 300;
  const end = Math.floor(Date.now() / 1000 / step) * step;
  let price = 50 + rand() * 450;
  const out = [];
  for (let i = n - 1; i >= 0; i--) {
    const open = price;
    const close = Math.max(1, open * (1 + (rand() - 0.49) * 0.04));
    const high = Math.max(open, close) * (1 + rand() * 0.015);
    const low = Math.min(open, close) * (1 - rand() * 0.015);
    out.push({ time: end - i * step, open, high, low, close, volume: Math.round(1e5 + rand() * 9e5) });
    price = close;
  }
  return out;
}
