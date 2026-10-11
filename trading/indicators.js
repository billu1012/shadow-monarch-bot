// Pure indicator math shared by the server (/api/market/signals) and the
// browser dashboard. Input is an array of candles sorted oldest → newest:
//   { time, open, high, low, close, volume }
// Each function returns [{ time, value }] aligned to the candle times, skipping
// the warm-up bars where the indicator is undefined.

export function sma(candles, period, key = "close") {
  const out = [];
  let sum = 0;
  for (let i = 0; i < candles.length; i++) {
    sum += candles[i][key];
    if (i >= period) sum -= candles[i - period][key];
    if (i >= period - 1) out.push({ time: candles[i].time, value: sum / period });
  }
  return out;
}

export function ema(candles, period, key = "close") {
  const out = [];
  if (candles.length < period) return out;
  const k = 2 / (period + 1);
  // Seed with the SMA of the first `period` values.
  let prev = 0;
  for (let i = 0; i < period; i++) prev += candles[i][key];
  prev /= period;
  out.push({ time: candles[period - 1].time, value: prev });
  for (let i = period; i < candles.length; i++) {
    prev = candles[i][key] * k + prev * (1 - k);
    out.push({ time: candles[i].time, value: prev });
  }
  return out;
}

// Wilder's RSI.
export function rsi(candles, period = 14) {
  const out = [];
  if (candles.length <= period) return out;
  let gain = 0;
  let loss = 0;
  for (let i = 1; i <= period; i++) {
    const d = candles[i].close - candles[i - 1].close;
    if (d >= 0) gain += d; else loss -= d;
  }
  gain /= period;
  loss /= period;
  const val = () => (loss === 0 ? 100 : 100 - 100 / (1 + gain / loss));
  out.push({ time: candles[period].time, value: val() });
  for (let i = period + 1; i < candles.length; i++) {
    const d = candles[i].close - candles[i - 1].close;
    gain = (gain * (period - 1) + Math.max(d, 0)) / period;
    loss = (loss * (period - 1) + Math.max(-d, 0)) / period;
    out.push({ time: candles[i].time, value: val() });
  }
  return out;
}

export function macd(candles, fast = 12, slow = 26, signal = 9) {
  const fastE = new Map(ema(candles, fast).map(p => [p.time, p.value]));
  const line = ema(candles, slow)
    .map(p => ({ time: p.time, close: fastE.get(p.time) - p.value }));
  const sig = new Map(ema(line, signal).map(p => [p.time, p.value]));
  return line
    .filter(p => sig.has(p.time))
    .map(p => {
      const s = sig.get(p.time);
      return { time: p.time, macd: p.close, signal: s, histogram: p.close - s };
    });
}

// Session-agnostic cumulative VWAP over the loaded range.
export function vwap(candles) {
  let pv = 0;
  let vol = 0;
  return candles.map(c => {
    const typical = (c.high + c.low + c.close) / 3;
    pv += typical * (c.volume || 0);
    vol += c.volume || 0;
    return { time: c.time, value: vol ? pv / vol : typical };
  });
}

// One-glance read of the latest bar, used by the API and the dashboard header.
export function summarize(candles) {
  if (candles.length < 50) return { error: "Need at least 50 candles for signals" };
  const last = arr => arr[arr.length - 1]?.value;
  const close = candles[candles.length - 1].close;
  const sma20 = last(sma(candles, 20));
  const sma50 = last(sma(candles, 50));
  const r = last(rsi(candles, 14));
  const m = macd(candles);
  const mNow = m[m.length - 1];
  const mPrev = m[m.length - 2];

  const signals = [];
  if (r >= 70) signals.push("RSI overbought");
  else if (r <= 30) signals.push("RSI oversold");
  if (mNow && mPrev) {
    if (mPrev.histogram <= 0 && mNow.histogram > 0) signals.push("MACD bullish cross");
    if (mPrev.histogram >= 0 && mNow.histogram < 0) signals.push("MACD bearish cross");
  }
  signals.push(sma20 > sma50 ? "SMA20 above SMA50 (uptrend)" : "SMA20 below SMA50 (downtrend)");

  let score = 0;
  if (sma20 > sma50) score++; else score--;
  if (close > sma20) score++; else score--;
  if (mNow?.histogram > 0) score++; else score--;
  if (r >= 70) score--;
  if (r <= 30) score++;
  const bias = score >= 2 ? "bullish" : score <= -2 ? "bearish" : "neutral";

  return {
    close,
    sma20,
    sma50,
    rsi14: r,
    macd: mNow ?? null,
    bias,
    signals,
  };
}
