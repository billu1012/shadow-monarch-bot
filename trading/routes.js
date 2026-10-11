import express from "express";
import path from "path";
import { fileURLToPath } from "url";
import { getCandles, configuredProviders, INTERVALS } from "./market.js";
import { summarize } from "./indicators.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Mounts the trading terminal on an existing Express app:
//   GET /trading                         → chart dashboard
//   GET /api/market/candles?symbol=&interval=&market=
//   GET /api/market/signals?symbol=&interval=&market=
//   GET /api/market/providers
export function mountTrading(app) {
  const send = async (res, fn) => {
    try {
      res.json(await fn());
    } catch (err) {
      res.status(err.status || 500).json({ error: err.message });
    }
  };

  app.get("/api/market/providers", (req, res) => {
    const providers = configuredProviders();
    res.json({ providers, demo: providers.length === 0, intervals: INTERVALS });
  });

  app.get("/api/market/candles", (req, res) => send(res, () =>
    getCandles(req.query.symbol, req.query.interval, req.query.market)));

  app.get("/api/market/signals", (req, res) => send(res, async () => {
    const { candles, ...meta } = await getCandles(req.query.symbol, req.query.interval, req.query.market);
    return { ...meta, ...summarize(candles) };
  }));

  app.use("/trading", express.static(path.join(__dirname, "dashboard")));
  // The browser imports the same indicator code the server uses.
  app.get("/trading/indicators.js", (req, res) => res.sendFile(path.join(__dirname, "indicators.js")));
  app.get("/trading/vendor/lightweight-charts.js", (req, res) => res.sendFile(
    path.join(__dirname, "..", "node_modules", "lightweight-charts", "dist", "lightweight-charts.standalone.production.mjs")));
}
