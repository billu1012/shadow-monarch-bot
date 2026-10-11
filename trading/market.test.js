// Run: npm test
import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { getCandles, parseSymbol } from "./market.js";
import { sma, rsi, macd, summarize } from "./indicators.js";

const reply = body => async () => ({ ok: true, json: async () => body });
let n = 0;
beforeEach(() => {
  delete process.env.TWELVE_DATA_API_KEY;
  delete process.env.ALPHA_VANTAGE_API_KEY;
  // Keyed providers only unless a test opts into Yahoo or demo.
  process.env.MARKET_DATA_PROVIDERS = "twelvedata,alphavantage";
  n++; // unique symbols per test so the cache never interferes
});

test("parseSymbol", () => {
  assert.deepEqual(parseSymbol("btc/usd"), { market: "crypto", base: "BTC", quote: "USD", display: "BTC/USD" });
  assert.equal(parseSymbol("eth", "crypto").display, "ETH/USD");
  assert.equal(parseSymbol("aapl").market, "stock");
  assert.throws(() => parseSymbol("x;rm -rf"), /Invalid symbol/);
});

test("Twelve Data: newest-first values are sorted oldest-first", async () => {
  process.env.TWELVE_DATA_API_KEY = "k";
  globalThis.fetch = reply({ status: "ok", values: [
    { datetime: "2026-10-09", open: "2", high: "3", low: "1", close: "2.5", volume: "10" },
    { datetime: "2026-10-08", open: "1", high: "2", low: "0.5", close: "2", volume: "5" },
  ] });
  const r = await getCandles(`TD${n}`, "daily");
  assert.equal(r.provider, "twelvedata");
  assert.deepEqual(r.candles.map(c => c.close), [2, 2.5]);
  assert.equal(r.candles[0].time, Date.UTC(2026, 9, 8) / 1000);
});

test("Alpha Vantage crypto: legacy '1a. open (USD)' field names parse", async () => {
  process.env.ALPHA_VANTAGE_API_KEY = "k";
  let url;
  globalThis.fetch = async u => { url = String(u); return reply({ "Meta Data": {}, "Time Series (Digital Currency Daily)": {
    "2026-10-09": { "1a. open (USD)": "100", "2a. high (USD)": "110", "3a. low (USD)": "90", "4a. close (USD)": "105", "5. volume": "7" },
  } })(); };
  const r = await getCandles(`AV${n}/USD`, "daily");
  assert.match(url, /function=DIGITAL_CURRENCY_DAILY/);
  assert.deepEqual(r.candles[0], { time: Date.UTC(2026, 9, 9) / 1000, open: 100, high: 110, low: 90, close: 105, volume: 7 });
});

test("falls back to Alpha Vantage when Twelve Data errors", async () => {
  process.env.TWELVE_DATA_API_KEY = "k";
  process.env.ALPHA_VANTAGE_API_KEY = "k";
  globalThis.fetch = async u => String(u).includes("twelvedata")
    ? reply({ status: "error", message: "rate limit" })()
    : reply({ "Time Series (5min)": { "2026-10-09 15:55:00": { "1. open": "1", "2. high": "2", "3. low": "0.5", "4. close": "1.5", "5. volume": "3" } } })();
  const r = await getCandles(`FB${n}`, "5min");
  assert.equal(r.provider, "alphavantage");
  assert.equal(r.candles[0].time, Date.UTC(2026, 9, 9, 15, 55) / 1000);
});

test("quota notice surfaces as an error, never as demo data", async () => {
  process.env.ALPHA_VANTAGE_API_KEY = "k";
  globalThis.fetch = reply({ Information: "API rate limit reached" });
  await assert.rejects(getCandles(`Q${n}`, "daily"), /rate limit/);
});

test("Yahoo: crypto symbol mapping, null bars dropped, UA header sent", async () => {
  process.env.MARKET_DATA_PROVIDERS = "yahoo";
  let req;
  globalThis.fetch = async (u, opts) => { req = { url: String(u), opts }; return reply({ chart: { error: null, result: [{
    meta: { symbol: `Y${n}-USD` },
    timestamp: [1791590400, 1791676800, 1791763200],
    indicators: { quote: [{ open: [1, null, 3], high: [2, 2, 4], low: [0.5, 1, 2.5], close: [1.5, 1.8, 3.5], volume: [10, 0, 30] }] },
  }] } })(); };
  const r = await getCandles(`Y${n}/USD`, "daily");
  assert.equal(r.provider, "yahoo");
  assert.match(req.url, new RegExp(`/chart/Y${n}-USD\\?interval=1d&range=2y`));
  assert.ok(req.opts.headers["User-Agent"]);
  assert.deepEqual(r.candles.map(c => c.time), [1791590400, 1791763200]);
});

test("Yahoo error falls through to Twelve Data", async () => {
  process.env.MARKET_DATA_PROVIDERS = "yahoo,twelvedata";
  process.env.TWELVE_DATA_API_KEY = "k";
  globalThis.fetch = async u => String(u).includes("yahoo")
    ? reply({ chart: { result: null, error: { code: "Not Found", description: "No data found, symbol may be delisted" } } })()
    : reply({ status: "ok", values: [{ datetime: "2026-10-09", open: "1", high: "2", low: "0.5", close: "1.5", volume: "1" }] })();
  const r = await getCandles(`YF${n}`, "daily");
  assert.equal(r.provider, "twelvedata");
});

test("all providers failing reports each error", async () => {
  process.env.MARKET_DATA_PROVIDERS = "yahoo";
  globalThis.fetch = async () => ({ ok: false, status: 429, json: async () => ({}) });
  await assert.rejects(getCandles(`YX${n}`, "daily"), /yahoo: HTTP 429/);
});

test("demo provider → labelled demo data, cached on repeat", async () => {
  process.env.MARKET_DATA_PROVIDERS = "demo";
  const a = await getCandles(`DEMO${n}`, "daily");
  assert.equal(a.demo, true);
  assert.equal(a.candles.length, 300);
  assert.equal((await getCandles(`DEMO${n}`, "daily")).cached, true);
});

test("indicators", () => {
  const candles = Array.from({ length: 60 }, (_, i) => ({ time: i, open: i, high: i + 1, low: i - 1, close: i + 1, volume: 1 }));
  assert.equal(sma(candles, 3)[0].value, 2);
  assert.equal(rsi(candles, 14).at(-1).value, 100); // straight up → RSI 100
  assert.ok(macd(candles).at(-1).macd > 0);
  // Accelerating rally: trend + momentum outweigh the RSI-overbought penalty.
  const rally = candles.map((c, i) => ({ ...c, close: 1 + i * i }));
  assert.equal(summarize(rally).bias, "bullish");
  assert.match(summarize(candles.slice(0, 10)).error, /at least 50/);
});
