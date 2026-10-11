import express from "express";
import cors from "cors";
import cron from "node-cron";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { mountTrading } from "./trading/routes.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(express.json());

// ── DATA PERSISTENCE ──
const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, "data");
if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

function getDataPath(date) {
  return path.join(DATA_DIR, `${date}.json`);
}

function loadDay(date) {
  const p = getDataPath(date);
  if (fs.existsSync(p)) return JSON.parse(fs.readFileSync(p, "utf8"));
  return { date, completed: [], xpEarned: 0 };
}

function saveDay(date, data) {
  fs.writeFileSync(getDataPath(date), JSON.stringify(data, null, 2));
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

// ── QUEST DEFINITIONS (must match frontend) ──
const QUESTS = [
  { id: "wake", xp: 50 }, { id: "activation", xp: 75 }, { id: "mana", xp: 25 },
  { id: "outfit", xp: 25 }, { id: "commute", xp: 30 }, { id: "dungeon_open", xp: 100 },
  { id: "water1", xp: 50 }, { id: "stand1", xp: 30 }, { id: "deep_work1", xp: 100 },
  { id: "lunch", xp: 75 }, { id: "water2", xp: 50 }, { id: "stand2", xp: 30 },
  { id: "deep_work2", xp: 100 }, { id: "water3", xp: 50 }, { id: "stand3", xp: 30 },
  { id: "deep_work3", xp: 100 }, { id: "dungeon_clear", xp: 75 }, { id: "commute_home", xp: 30 },
  { id: "home", xp: 25 }, { id: "pre_gym", xp: 25 }, { id: "gym_warmup", xp: 50 },
  { id: "gym", xp: 200 }, { id: "recovery_meal", xp: 75 }, { id: "water4", xp: 50 },
  { id: "rest", xp: 30 }, { id: "sleep", xp: 200 },
];

// ═══════════════════════════════════════════════════════════════
// API ROUTES
// ═══════════════════════════════════════════════════════════════

// ONE-TAP COMPLETION — This is the iMessage magic
// URL: /tap/gym or /tap/wake etc.
// When tapped from iMessage, marks quest complete then redirects to dashboard
app.get("/tap/:questId", (req, res) => {
  const { questId } = req.params;
  const quest = QUESTS.find(q => q.id === questId);
  if (!quest) return res.status(404).send("Quest not found");

  const d = today();
  const dayData = loadDay(d);

  if (!dayData.completed.includes(questId)) {
    dayData.completed.push(questId);
    dayData.xpEarned += quest.xp;
    saveDay(d, dayData);
    console.log(`✅ Quest completed via tap: ${questId} (+${quest.xp} XP)`);
  }

  // Redirect to dashboard with completion flag
  // The frontend will show the XP animation
  res.redirect(`/?complete=${questId}`);
});

// API: Complete quest (from dashboard tap)
app.post("/api/complete", (req, res) => {
  const { questId, date } = req.body;
  const d = date || today();
  const quest = QUESTS.find(q => q.id === questId);
  if (!quest) return res.status(404).json({ error: "Quest not found" });

  const dayData = loadDay(d);
  if (!dayData.completed.includes(questId)) {
    dayData.completed.push(questId);
    dayData.xpEarned += quest.xp;
    saveDay(d, dayData);
  }

  res.json({ ok: true, completed: dayData.completed, xpEarned: dayData.xpEarned });
});

// API: Get today's status (dashboard syncs from this)
app.get("/api/status/:date", (req, res) => {
  const dayData = loadDay(req.params.date);
  res.json(dayData);
});

// API: Get weekly summary
app.get("/api/weekly", (req, res) => {
  const days = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().slice(0, 10);
    days.push(loadDay(dateStr));
  }
  res.json(days);
});

// Health check
app.get("/api/health", (req, res) => {
  res.json({ status: "Shadow Monarch OS Online", date: today() });
});

// ═══════════════════════════════════════════════════════════════
// WEBHOOK INBOUND — External tools (Claude, Zapier, n8n) POST here
// SSE stream pushes events to the frontend in real time
// ═══════════════════════════════════════════════════════════════
const sseClients = [];

app.get("/api/webhook/stream", (req, res) => {
  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Access-Control-Allow-Origin": "*",
  });
  res.write("data: {\"type\":\"connected\"}\n\n");
  sseClients.push(res);
  req.on("close", () => {
    const idx = sseClients.indexOf(res);
    if (idx >= 0) sseClients.splice(idx, 1);
  });
});

function broadcastSSE(event) {
  const data = `data: ${JSON.stringify(event)}\n\n`;
  sseClients.forEach(client => {
    try { client.write(data); } catch {}
  });
}

app.post("/api/webhook/inbound", (req, res) => {
  const body = req.body;
  if (!body) return res.status(400).json({ error: "Request body required" });

  // Support both { command, params } and { type, data } formats
  const event = body.command
    ? { type: "command", command: body.command, params: body.params || {} }
    : { type: body.type || "event", ...body };

  broadcastSSE(event);
  console.log(`\u26A1 Webhook inbound: ${JSON.stringify(event)}`);

  // Process known commands server-side too
  if (body.command === "add_xp" || body.type === "add_xp") {
    const d = today();
    const dayData = loadDay(d);
    dayData.xpEarned += body.params?.amount || body.data?.amount || 0;
    saveDay(d, dayData);
  }

  res.json({ ok: true, received: event });
});

// API: Get streak
app.get("/api/streak", (req, res) => {
  const streakPath = path.join(DATA_DIR, "streak.json");
  let streak = { streak: 0, lastUpdate: null };
  try { streak = JSON.parse(fs.readFileSync(streakPath, "utf8")); } catch {}
  res.json(streak);
});

// ═══════════════════════════════════════════════════════════════
// TEXT COMMAND API — Claude sends natural language, server processes it
// This is the bridge for Claude Code / Cowork Dispatch integration
// ═══════════════════════════════════════════════════════════════

// Quest name aliases for fuzzy matching from text messages
const QUEST_ALIASES = {
  // wake / morning
  "wake": "wake", "woke up": "wake", "awake": "wake", "up": "wake", "morning": "wake",
  // activation
  "activation": "activation", "squats": "activation", "stretches": "activation", "stretch": "activation", "warmup morning": "activation",
  // mana
  "mana": "mana", "coffee": "mana", "celsius": "mana", "caffeine": "mana", "energy drink": "mana",
  // outfit
  "outfit": "outfit", "dressed": "outfit", "armor": "outfit", "clothes": "outfit", "changed": "outfit",
  // commute
  "commute": "commute", "driving": "commute", "on the way": "commute", "headed to work": "commute",
  // dungeon open
  "dungeon open": "dungeon_open", "dungeon_open": "dungeon_open", "work start": "dungeon_open", "started work": "dungeon_open", "at work": "dungeon_open", "clocked in": "dungeon_open",
  // water
  "water 1": "water1", "water1": "water1", "water 2": "water2", "water2": "water2",
  "water 3": "water3", "water3": "water3", "water 4": "water4", "water4": "water4",
  "water": "water1", // defaults to next incomplete water quest (handled in logic)
  // stand
  "stand 1": "stand1", "stand1": "stand1", "stand 2": "stand2", "stand2": "stand2",
  "stand 3": "stand3", "stand3": "stand3",
  "stand": "stand1", "stood up": "stand1", "standing": "stand1",
  // deep work
  "deep work 1": "deep_work1", "deep_work1": "deep_work1", "extraction 1": "deep_work1",
  "deep work 2": "deep_work2", "deep_work2": "deep_work2", "extraction 2": "deep_work2",
  "deep work 3": "deep_work3", "deep_work3": "deep_work3", "extraction 3": "deep_work3",
  "deep work": "deep_work1", "focused": "deep_work1", "extraction": "deep_work1",
  // lunch
  "lunch": "lunch", "ate lunch": "lunch", "meal": "lunch", "main quest meal": "lunch",
  // dungeon clear
  "dungeon clear": "dungeon_clear", "dungeon_clear": "dungeon_clear", "done work": "dungeon_clear", "leaving work": "dungeon_clear", "end of day": "dungeon_clear",
  // commute home
  "commute home": "commute_home", "commute_home": "commute_home", "heading home": "commute_home", "driving home": "commute_home",
  // home
  "home": "home", "got home": "home", "respawn": "home",
  // pre gym
  "pre gym": "pre_gym", "pre_gym": "pre_gym", "snack": "pre_gym", "boss prep": "pre_gym", "pre workout": "pre_gym",
  // gym warmup
  "gym warmup": "gym_warmup", "gym_warmup": "gym_warmup", "shadow warmup": "gym_warmup", "cardio": "gym_warmup",
  // gym
  "gym": "gym", "workout": "gym", "shadow raid": "gym", "lifted": "gym", "training": "gym",
  // recovery meal
  "recovery meal": "recovery_meal", "recovery_meal": "recovery_meal", "post workout meal": "recovery_meal", "dinner": "recovery_meal", "recovery rations": "recovery_meal",
  // rest
  "rest": "rest", "rest phase": "rest", "relaxing": "rest", "gaming": "rest", "shows": "rest",
  // sleep
  "sleep": "sleep", "going to bed": "sleep", "bedtime": "sleep", "shadow sleep": "sleep", "goodnight": "sleep", "night": "sleep",
};

// Sequenced quests — when user says "water" or "stand" without a number, pick the next incomplete one
const SEQUENCED = {
  water: ["water1", "water2", "water3", "water4"],
  stand: ["stand1", "stand2", "stand3"],
  deep_work: ["deep_work1", "deep_work2", "deep_work3"],
};

function resolveQuestId(text, completedQuests) {
  const lower = text.toLowerCase().trim();

  // Direct quest ID match
  const directMatch = QUESTS.find(q => q.id === lower);
  if (directMatch) return directMatch.id;

  // Alias match
  let matched = QUEST_ALIASES[lower];
  if (!matched) {
    // Fuzzy: check if text contains any alias key
    for (const [alias, id] of Object.entries(QUEST_ALIASES)) {
      if (lower.includes(alias) || alias.includes(lower)) {
        matched = id;
        break;
      }
    }
  }
  if (!matched) return null;

  // If it's a sequenced quest base (water1, stand1, deep_work1), find next incomplete
  for (const [base, sequence] of Object.entries(SEQUENCED)) {
    if (sequence.includes(matched) && matched === sequence[0]) {
      // User said the generic form — find the next incomplete one
      const next = sequence.find(id => !completedQuests.includes(id));
      if (next) return next;
      return matched; // all done, return original
    }
  }

  return matched;
}

function getRankInfo(totalXp) {
  const ranks = [
    { name: "E-Rank Hunter", minXp: 0 },
    { name: "D-Rank Hunter", minXp: 500 },
    { name: "C-Rank Hunter", minXp: 1500 },
    { name: "B-Rank Hunter", minXp: 3000 },
    { name: "A-Rank Hunter", minXp: 6000 },
    { name: "S-Rank Hunter", minXp: 10000 },
    { name: "National Level", minXp: 20000 },
    { name: "Shadow Monarch", minXp: 50000 },
  ];
  let rank = ranks[0];
  for (const r of ranks) {
    if (totalXp >= r.minXp) rank = r;
  }
  return rank;
}

// POST /api/text — Claude sends a natural language message, server processes it
app.post("/api/text", (req, res) => {
  const { message } = req.body;
  if (!message) return res.status(400).json({ error: "message is required" });

  const d = today();
  const dayData = loadDay(d);
  const lower = message.toLowerCase().trim();

  // ── STATUS CHECK ──
  if (lower.includes("status") || lower.includes("how am i") || lower.includes("progress") || lower.includes("check")) {
    const totalXp = dayData.xpEarned;
    const maxXp = QUESTS.reduce((s, q) => s + q.xp, 0);
    const pct = Math.round((dayData.completed.length / QUESTS.length) * 100);
    const rank = getRankInfo(totalXp);
    const remaining = QUESTS.filter(q => !dayData.completed.includes(q.id));
    const streakPath = path.join(DATA_DIR, "streak.json");
    let streak = 0;
    try { streak = JSON.parse(fs.readFileSync(streakPath, "utf8")).streak || 0; } catch {}

    return res.json({
      ok: true,
      type: "status",
      response: `Shadow Monarch Status Report — ${d}\n\nRank: ${rank.name}\nXP: ${totalXp} / ${maxXp}\nQuests: ${dayData.completed.length}/${QUESTS.length} (${pct}%)\nStreak: ${streak} days\n\nCompleted: ${dayData.completed.join(", ") || "None yet"}\nRemaining: ${remaining.map(q => q.id).join(", ")}`,
      data: { rank: rank.name, xp: totalXp, maxXp, completed: dayData.completed, remaining: remaining.map(q => q.id), streak, pct }
    });
  }

  // ── UNDO / UNCOMPLETE ──
  if (lower.startsWith("undo ") || lower.startsWith("uncomplete ")) {
    const questText = lower.replace(/^(undo|uncomplete)\s+/, "");
    const questId = resolveQuestId(questText, dayData.completed);
    if (!questId) return res.json({ ok: false, response: `Could not find quest matching "${questText}". Try the exact quest ID.` });

    const quest = QUESTS.find(q => q.id === questId);
    if (dayData.completed.includes(questId)) {
      dayData.completed = dayData.completed.filter(id => id !== questId);
      dayData.xpEarned -= quest.xp;
      saveDay(d, dayData);
      return res.json({ ok: true, type: "undo", response: `Undid quest: ${questId} (-${quest.xp} XP). Total: ${dayData.xpEarned} XP`, data: dayData });
    }
    return res.json({ ok: true, type: "undo", response: `Quest ${questId} wasn't completed — nothing to undo.` });
  }

  // ── COMPLETE QUEST (default action) ──
  // Strip common prefixes like "done", "completed", "finished", "did"
  let questText = lower
    .replace(/^(done with|done|completed|finished|did|complete|finish|mark)\s+/, "")
    .replace(/\s+(done|completed|finished|complete)$/, "")
    .trim();

  const questId = resolveQuestId(questText, dayData.completed);
  if (!questId) {
    // Try the full message as a last resort
    const fallbackId = resolveQuestId(lower, dayData.completed);
    if (!fallbackId) {
      return res.json({
        ok: false,
        response: `Could not match "${message}" to any quest. Available quests: ${QUESTS.map(q => q.id).join(", ")}`,
        availableQuests: QUESTS.map(q => q.id)
      });
    }
    // Use fallback
    const quest = QUESTS.find(q => q.id === fallbackId);
    if (dayData.completed.includes(fallbackId)) {
      return res.json({ ok: true, type: "already_done", response: `Quest "${fallbackId}" already completed today! (+${quest.xp} XP was earned)` });
    }
    dayData.completed.push(fallbackId);
    dayData.xpEarned += quest.xp;
    saveDay(d, dayData);
    const pct = Math.round((dayData.completed.length / QUESTS.length) * 100);
    return res.json({
      ok: true, type: "complete",
      response: `Quest completed: ${fallbackId} (+${quest.xp} XP)\nTotal: ${dayData.xpEarned} XP | ${dayData.completed.length}/${QUESTS.length} quests (${pct}%)`,
      data: dayData
    });
  }

  const quest = QUESTS.find(q => q.id === questId);
  if (dayData.completed.includes(questId)) {
    return res.json({ ok: true, type: "already_done", response: `Quest "${questId}" already completed today! (+${quest.xp} XP was earned)` });
  }

  dayData.completed.push(questId);
  dayData.xpEarned += quest.xp;
  saveDay(d, dayData);
  const pct = Math.round((dayData.completed.length / QUESTS.length) * 100);
  const rank = getRankInfo(dayData.xpEarned);
  console.log(`Quest completed via text: ${questId} (+${quest.xp} XP)`);

  return res.json({
    ok: true, type: "complete",
    response: `Quest completed: ${questId} (+${quest.xp} XP)\nRank: ${rank.name} | Total: ${dayData.xpEarned} XP | ${dayData.completed.length}/${QUESTS.length} quests (${pct}%)`,
    data: dayData
  });
});

// ═══════════════════════════════════════════════════════════════
// TRADING TERMINAL — charts + market data (see trading/README.md)
// ═══════════════════════════════════════════════════════════════
mountTrading(app);

// ═══════════════════════════════════════════════════════════════
// SERVE FRONTEND (built Vite app)
// ═══════════════════════════════════════════════════════════════
app.use(express.static(path.join(__dirname, "lifeos")));

// ═══════════════════════════════════════════════════════════════
// CRON — STREAK CALCULATOR (runs at midnight)
// ═══════════════════════════════════════════════════════════════
cron.schedule("0 0 * * *", () => {
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const yd = yesterday.toISOString().slice(0, 10);
  const dayData = loadDay(yd);
  const pct = dayData.completed.length / QUESTS.length;

  const streakPath = path.join(DATA_DIR, "streak.json");
  let streak = 0;
  try { streak = JSON.parse(fs.readFileSync(streakPath, "utf8")).streak || 0; } catch {}

  if (pct >= 0.8) {
    streak++;
    console.log(`🔥 Streak extended to ${streak} days!`);
  } else {
    streak = 0;
    console.log("💀 Streak broken. Reset to 0.");
  }

  fs.writeFileSync(streakPath, JSON.stringify({ streak, lastUpdate: yd }));
});

// ═══════════════════════════════════════════════════════════════
// START
// ═══════════════════════════════════════════════════════════════
app.listen(PORT, () => {
  console.log(`
⚔️  SHADOW MONARCH OS — SERVER ONLINE
🌐  Port: ${PORT}
📅  Date: ${today()}
🔗  Tap URLs: /tap/{questId}
📊  Status:   /api/status/${today()}
  `);
});
