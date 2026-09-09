import React, { useState, useEffect, useCallback, useRef } from "react";

// ═══════════════════════════════════════════════════════════════
// SHADOW MONARCH PROTOCOL v3 — FULL QUEST OPERATING SYSTEM
// ═══════════════════════════════════════════════════════════════

// ── CONFIG ──
const BACKEND_URL = typeof window !== "undefined" && window.location.hostname !== "localhost"
  ? window.location.origin
  : "http://localhost:3001";

const STORAGE_PREFIX = "smo_";
const today = () => new Date().toISOString().slice(0, 10);

// ── LOCAL STORAGE HELPERS ──
function save(key, val) {
  try { localStorage.setItem(STORAGE_PREFIX + key, JSON.stringify(val)); } catch {}
}
function load(key, fallback) {
  try {
    const v = localStorage.getItem(STORAGE_PREFIX + key);
    return v ? JSON.parse(v) : fallback;
  } catch { return fallback; }
}

// ── RANK SYSTEM ──
const RANKS = [
  { name: "E-Rank Hunter", minXP: 0, color: "#6b7280" },
  { name: "D-Rank Hunter", minXP: 500, color: "#3b82f6" },
  { name: "C-Rank Hunter", minXP: 1500, color: "#22c55e" },
  { name: "B-Rank Hunter", minXP: 3000, color: "#eab308" },
  { name: "A-Rank Hunter", minXP: 6000, color: "#f97316" },
  { name: "S-Rank Hunter", minXP: 10000, color: "#ef4444" },
  { name: "National Level", minXP: 20000, color: "#a855f7" },
  { name: "Shadow Monarch", minXP: 50000, color: "#7c3aed" },
];

function getRank(xp) {
  for (let i = RANKS.length - 1; i >= 0; i--) {
    if (xp >= RANKS[i].minXP) return RANKS[i];
  }
  return RANKS[0];
}

function getNextRank(xp) {
  for (let i = 0; i < RANKS.length; i++) {
    if (xp < RANKS[i].minXP) return RANKS[i];
  }
  return null;
}

// ── QUEST SCHEDULE (26 QUESTS) ──
const QUESTS = [
  { id: "wake", time: "06:00", expires: "07:00", label: "SYSTEM BOOT", icon: "⚡", desc: "Wake up. Stand within 60s. Drink 16oz water.", xp: 50, cat: "discipline", critical: true },
  { id: "activation", time: "06:10", expires: "07:00", label: "BODY ACTIVATION", icon: "🔥", desc: "10 squats · 10 arm circles · 10 calf raises · 60s stretch", xp: 75, cat: "fitness" },
  { id: "mana", time: "06:30", expires: "08:00", label: "MANA CHARGE", icon: "☕", desc: "Celsius/coffee + 8oz water. Zero sugar only.", xp: 25, cat: "nutrition" },
  { id: "outfit", time: "06:45", expires: "07:30", label: "ARMOR EQUIP", icon: "👔", desc: "Get dressed. Look sharp. Posture check.", xp: 25, cat: "discipline" },
  { id: "commute", time: "07:00", expires: "08:00", label: "GATE TRANSIT", icon: "🚗", desc: "Commute. Podcast or audiobook — no music zombiemode.", xp: 30, cat: "focus" },
  { id: "dungeon_open", time: "07:30", expires: "09:00", label: "DUNGEON OPEN", icon: "🖥️", desc: "Work started. Posture check. 30-min stand reminders ON.", xp: 100, cat: "discipline", critical: true },
  { id: "water1", time: "10:00", expires: "11:00", label: "WATER RAID I", icon: "💧", desc: "32oz consumed by now. Refill. Light yellow urine.", xp: 50, cat: "nutrition" },
  { id: "stand1", time: "10:30", expires: "11:00", label: "STAND BREAK I", icon: "🧍", desc: "Stand. Walk. 10 calf raises at desk.", xp: 30, cat: "fitness" },
  { id: "deep_work1", time: "11:00", expires: "12:00", label: "EXTRACTION I", icon: "🎯", desc: "Deep work block. Phone on DND. Zero distractions.", xp: 100, cat: "focus" },
  { id: "lunch", time: "12:00", expires: "13:30", label: "MAIN QUEST MEAL", icon: "🍖", desc: "35-50g protein FIRST. Large veggies. Measured carbs.", xp: 75, cat: "nutrition", critical: true },
  { id: "water2", time: "13:00", expires: "14:00", label: "WATER RAID II", icon: "💧", desc: "64oz total by now. Refill again.", xp: 50, cat: "nutrition" },
  { id: "stand2", time: "13:30", expires: "14:00", label: "STAND BREAK II", icon: "🧍", desc: "Walk loop. Stretch hip flexors. Reset posture.", xp: 30, cat: "fitness" },
  { id: "deep_work2", time: "14:00", expires: "15:30", label: "EXTRACTION II", icon: "🎯", desc: "Afternoon deep work. Most creative block — use it.", xp: 100, cat: "focus" },
  { id: "water3", time: "15:00", expires: "16:00", label: "WATER RAID III", icon: "💧", desc: "96oz consumed. On track for gallon.", xp: 50, cat: "nutrition" },
  { id: "stand3", time: "15:30", expires: "16:00", label: "STAND BREAK III", icon: "🧍", desc: "Stand, walk, 10 calf raises. Avoid afternoon slump.", xp: 30, cat: "fitness" },
  { id: "deep_work3", time: "16:00", expires: "17:00", label: "EXTRACTION III", icon: "🎯", desc: "Final work sprint. Close loops. Clear inbox.", xp: 100, cat: "focus" },
  { id: "dungeon_clear", time: "17:00", expires: "18:00", label: "DUNGEON CLEAR", icon: "🏁", desc: "Work done. Write tomorrow's top 3. Shut laptop.", xp: 75, cat: "discipline" },
  { id: "commute_home", time: "17:30", expires: "18:30", label: "RETURN GATE", icon: "🚗", desc: "Commute home. Decompress. No doom scrolling.", xp: 30, cat: "discipline" },
  { id: "home", time: "18:00", expires: "19:00", label: "RESPAWN POINT", icon: "🏠", desc: "Home. Change clothes. Light snack optional.", xp: 25, cat: "discipline" },
  { id: "pre_gym", time: "19:00", expires: "20:00", label: "BOSS PREP", icon: "🍌", desc: "Pre-gym fuel: banana or rice cake + caffeine if needed.", xp: 25, cat: "nutrition" },
  { id: "gym_warmup", time: "19:45", expires: "20:15", label: "SHADOW WARMUP", icon: "🔥", desc: "5 min cardio warmup. Dynamic stretches. Mental lock-in.", xp: 50, cat: "fitness" },
  { id: "gym", time: "20:00", expires: "21:30", label: "SHADOW RAID", icon: "⚔️", desc: "V-TAPER PROTOCOL. Give everything. No phone between sets.", xp: 200, cat: "fitness", critical: true },
  { id: "recovery_meal", time: "21:15", expires: "22:00", label: "RECOVERY RATIONS", icon: "🍗", desc: "25-40g protein post-workout. Real food, not junk.", xp: 75, cat: "nutrition", critical: true },
  { id: "water4", time: "21:30", expires: "22:30", label: "WATER RAID IV", icon: "💧", desc: "128oz target. Final push for the gallon.", xp: 50, cat: "nutrition" },
  { id: "rest", time: "22:00", expires: "23:00", label: "REST PHASE", icon: "🎮", desc: "Shows/games. Stand every 30min. No snacking.", xp: 30, cat: "discipline" },
  { id: "sleep", time: "23:00", expires: "23:59", label: "SHADOW SLEEP", icon: "🌙", desc: "Wind down. No screens. Lights out.", xp: 200, cat: "discipline", critical: true },
];

const CAT_COLORS = {
  discipline: "#7c3aed",
  fitness: "#ef4444",
  nutrition: "#22c55e",
  focus: "#3b82f6",
};

const CAT_ICONS = {
  discipline: "👑",
  fitness: "💪",
  nutrition: "🥗",
  focus: "🧠",
};

const MAX_DAILY_XP = QUESTS.reduce((s, q) => s + q.xp, 0);

// ── TIME HELPERS ──
function parseTime(t) {
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
}

function nowMinutes() {
  const n = new Date();
  return n.getHours() * 60 + n.getMinutes();
}

function formatTime(t) {
  const [h, m] = t.split(":");
  const hr = parseInt(h);
  const ampm = hr >= 12 ? "PM" : "AM";
  const h12 = hr === 0 ? 12 : hr > 12 ? hr - 12 : hr;
  return `${h12}:${m} ${ampm}`;
}

function getQuestStatus(quest, completed) {
  if (completed.includes(quest.id)) return "done";
  const now = nowMinutes();
  const start = parseTime(quest.time);
  const end = parseTime(quest.expires);
  if (now < start) return "locked";
  if (now > end) return "expired";
  return "active";
}

// ── SOLO LEVELING QUOTES ──
const QUOTES = [
  "I alone am the one who levels up.",
  "Arise.",
  "I am the shadow monarch. I need no one's help.",
  "The weak have no right to choose how they die.",
  "Every day I get stronger. That is my only truth.",
  "I don't need a reason to fight. I fight because I can.",
  "In this world, only the strong survive.",
  "My shadows are infinite.",
  "Pain is the greatest teacher.",
  "I will surpass all limits.",
];

// ═══════════════════════════════════════════════════════════════
// MAIN APP COMPONENT
// ═══════════════════════════════════════════════════════════════
export default function App() {
  const [tab, setTab] = useState("quests");
  const [completed, setCompleted] = useState([]);
  const [totalXP, setTotalXP] = useState(0);
  const [streak, setStreak] = useState(0);
  const [tick, setTick] = useState(0);
  const [showComplete, setShowComplete] = useState(null);
  const [syncing, setSyncing] = useState(false);

  const dateKey = `completed_${today()}`;

  // Load saved state
  useEffect(() => {
    setCompleted(load(dateKey, []));
    setTotalXP(load("totalXP", 0));
    setStreak(load("streak", 0));
  }, []);

  // Check URL for ?complete=questId (one-tap from iMessage)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const questId = params.get("complete");
    if (questId && !completed.includes(questId)) {
      completeQuest(questId, true);
      // Clean URL
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [completed]);

  // Sync from backend every 30s
  useEffect(() => {
    async function syncFromBackend() {
      try {
        setSyncing(true);
        const res = await fetch(`${BACKEND_URL}/api/status/${today()}`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.completed && data.completed.length > completed.length) {
          setCompleted(data.completed);
          save(dateKey, data.completed);
        }
      } catch {} finally { setSyncing(false); }
    }
    syncFromBackend();
    const interval = setInterval(syncFromBackend, 30000);
    return () => clearInterval(interval);
  }, []);

  // Tick every 30s to update quest statuses
  useEffect(() => {
    const t = setInterval(() => setTick(k => k + 1), 30000);
    return () => clearInterval(t);
  }, []);

  const completeQuest = useCallback(async (questId, fromURL = false) => {
    const quest = QUESTS.find(q => q.id === questId);
    if (!quest || completed.includes(questId)) return;

    const updated = [...completed, questId];
    setCompleted(updated);
    save(dateKey, updated);

    const newXP = totalXP + quest.xp;
    setTotalXP(newXP);
    save("totalXP", newXP);

    setShowComplete({ quest, xp: quest.xp });
    setTimeout(() => setShowComplete(null), 2500);

    // Notify backend
    try {
      await fetch(`${BACKEND_URL}/api/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ questId, date: today() }),
      });
    } catch {}
  }, [completed, totalXP, dateKey]);

  const rank = getRank(totalXP);
  const nextRank = getNextRank(totalXP);
  const dailyXP = completed.reduce((s, id) => {
    const q = QUESTS.find(x => x.id === id);
    return s + (q ? q.xp : 0);
  }, 0);
  const pct = Math.round((dailyXP / MAX_DAILY_XP) * 100);

  const activeQuest = QUESTS.find(q => getQuestStatus(q, completed) === "active" && !completed.includes(q.id));

  // Category breakdown
  const catStats = {};
  for (const cat of Object.keys(CAT_COLORS)) {
    const catQuests = QUESTS.filter(q => q.cat === cat);
    const catDone = catQuests.filter(q => completed.includes(q.id));
    catStats[cat] = { total: catQuests.length, done: catDone.length, pct: Math.round((catDone.length / catQuests.length) * 100) };
  }

  return (
    <div style={styles.app}>
      {/* XP COMPLETE ANIMATION */}
      {showComplete && (
        <div style={styles.xpPopup}>
          <div style={styles.xpIcon}>{showComplete.quest.icon}</div>
          <div style={styles.xpLabel}>QUEST COMPLETE</div>
          <div style={styles.xpAmount}>+{showComplete.xp} XP</div>
          <div style={styles.xpQuote}>{QUOTES[Math.floor(Math.random() * QUOTES.length)]}</div>
        </div>
      )}

      {/* HEADER */}
      <div style={styles.header}>
        <div style={styles.monarchBanner}>
          <img src="/monarch.jpg" alt="Shadow Monarch" style={styles.monarchImg} />
          <div style={styles.monarchOverlay} />
          <div style={styles.monarchInfo}>
            <div style={{ ...styles.rankBadge, background: rank.color }}>{rank.name}</div>
            <div style={styles.xpTotal}>{totalXP.toLocaleString()} XP{streak > 0 ? ` · 🔥${streak}` : ""}</div>
          </div>
          <div style={styles.dailyProgress}>
            <div style={styles.dailyPct}>{pct}%</div>
            <div style={styles.dailyLabel}>{completed.length}/{QUESTS.length} quests</div>
          </div>
        </div>

        {/* DAILY XP BAR */}
        <div style={styles.xpBarOuter}>
          <div style={{ ...styles.xpBarInner, width: `${pct}%` }} />
        </div>

        {/* ACTIVE QUEST BANNER */}
        {activeQuest && (
          <div style={styles.activeBanner} onClick={() => completeQuest(activeQuest.id)}>
            <span style={styles.activePulse}>●</span>
            <span style={styles.activeIcon}>{activeQuest.icon}</span>
            <div style={styles.activeText}>
              <div style={styles.activeLabel}>{activeQuest.label}</div>
              <div style={styles.activeDesc}>{activeQuest.desc}</div>
            </div>
            <div style={styles.activeTap}>TAP ✓</div>
          </div>
        )}
      </div>

      {/* TAB BAR */}
      <div style={styles.tabBar}>
        {["quests", "stats", "code"].map(t => (
          <div
            key={t}
            style={{ ...styles.tab, ...(tab === t ? styles.tabActive : {}) }}
            onClick={() => setTab(t)}
          >
            {t === "quests" ? "⚔️" : t === "stats" ? "📊" : "👑"}{" "}
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </div>
        ))}
      </div>

      {/* CONTENT */}
      <div style={styles.content}>
        {tab === "quests" && (
          <QuestList completed={completed} onComplete={completeQuest} tick={tick} />
        )}
        {tab === "stats" && (
          <StatsPanel
            catStats={catStats}
            dailyXP={dailyXP}
            totalXP={totalXP}
            rank={rank}
            nextRank={nextRank}
            streak={streak}
            completed={completed}
          />
        )}
        {tab === "code" && (
          <MonarchCode />
        )}
      </div>

      {/* SYNC INDICATOR */}
      {syncing && <div style={styles.syncDot}>⟳</div>}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// QUEST LIST
// ═══════════════════════════════════════════════════════════════
function QuestList({ completed, onComplete, tick }) {
  const now = nowMinutes();
  const activeRef = useRef(null);

  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, []);

  return (
    <div style={styles.questList}>
      {QUESTS.map((quest, i) => {
        const status = getQuestStatus(quest, completed);
        const isActive = status === "active";

        return (
          <div
            key={quest.id}
            ref={isActive && !activeRef.current ? activeRef : null}
            style={{
              ...styles.questCard,
              ...(status === "done" ? styles.questDone : {}),
              ...(status === "locked" ? styles.questLocked : {}),
              ...(status === "expired" ? styles.questExpired : {}),
              ...(isActive ? styles.questActive : {}),
              borderLeft: `3px solid ${CAT_COLORS[quest.cat]}`,
            }}
            onClick={() => {
              if (status === "active") onComplete(quest.id);
            }}
          >
            <div style={styles.questTop}>
              <div style={styles.questTime}>{formatTime(quest.time)}</div>
              {quest.critical && <span style={styles.criticalBadge}>CRITICAL</span>}
              <div style={styles.questXP}>+{quest.xp} XP</div>
            </div>

            <div style={styles.questMain}>
              <span style={styles.questIcon}>{quest.icon}</span>
              <div>
                <div style={styles.questLabel}>
                  {status === "done" ? "✅ " : status === "locked" ? "🔒 " : status === "expired" ? "⚠️ " : ""}
                  {quest.label}
                </div>
                <div style={styles.questDesc}>{quest.desc}</div>
              </div>
            </div>

            {isActive && (
              <div style={styles.tapHint}>
                <span style={styles.tapPulse} /> TAP TO COMPLETE
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// STATS PANEL
// ═══════════════════════════════════════════════════════════════
function StatsPanel({ catStats, dailyXP, totalXP, rank, nextRank, streak, completed }) {
  return (
    <div style={styles.statsPanel}>
      {/* RANK CARD */}
      <div style={{ ...styles.statCard, borderColor: rank.color }}>
        <div style={styles.statTitle}>CURRENT RANK</div>
        <div style={{ ...styles.statValue, color: rank.color, fontSize: 22 }}>{rank.name}</div>
        {nextRank && (
          <div style={styles.statSub}>
            {nextRank.minXP - totalXP} XP to {nextRank.name}
          </div>
        )}
      </div>

      {/* DAILY SUMMARY */}
      <div style={styles.statCard}>
        <div style={styles.statTitle}>TODAY</div>
        <div style={styles.statValue}>{dailyXP} / {MAX_DAILY_XP} XP</div>
        <div style={styles.statSub}>{completed.length} / {QUESTS.length} quests completed</div>
      </div>

      {/* CATEGORY BREAKDOWN */}
      <div style={styles.statCard}>
        <div style={styles.statTitle}>CATEGORIES</div>
        {Object.entries(catStats).map(([cat, s]) => (
          <div key={cat} style={styles.catRow}>
            <span style={{ color: CAT_COLORS[cat] }}>{CAT_ICONS[cat]} {cat.toUpperCase()}</span>
            <div style={styles.catBarOuter}>
              <div style={{ ...styles.catBarInner, width: `${s.pct}%`, background: CAT_COLORS[cat] }} />
            </div>
            <span style={styles.catPct}>{s.done}/{s.total}</span>
          </div>
        ))}
      </div>

      {/* STREAK */}
      <div style={styles.statCard}>
        <div style={styles.statTitle}>STREAK</div>
        <div style={styles.statValue}>🔥 {streak} days</div>
        <div style={styles.statSub}>Complete 80%+ daily to maintain streak</div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// MONARCH'S CODE
// ═══════════════════════════════════════════════════════════════
function MonarchCode() {
  const rules = [
    "I do not eat junk food. I fuel the machine.",
    "I do not doom scroll. I own my attention.",
    "I do not skip the gym. The Shadow Raid is non-negotiable.",
    "I drink a gallon of water daily. Hydration is mana.",
    "I sleep by 11 PM. Recovery is power.",
    "I stand every 30 minutes. Posture is armor.",
    "I eat protein first. Always.",
    "I do not vape. My lungs are sacred.",
    "No sugar drinks. Zero tolerance.",
    "I am the Shadow Monarch. I level up every single day.",
  ];

  return (
    <div style={styles.codePanel}>
      <div style={styles.codeTitle}>👑 THE MONARCH'S CODE</div>
      <div style={styles.codeSubtitle}>These are non-negotiable. Break them and you break yourself.</div>
      {rules.map((rule, i) => (
        <div key={i} style={styles.codeRule}>
          <span style={styles.codeNum}>{String(i + 1).padStart(2, "0")}</span>
          <span style={styles.codeText}>{rule}</span>
        </div>
      ))}
      <div style={styles.codeQuote}>
        "{QUOTES[Math.floor(Math.random() * QUOTES.length)]}"
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// STYLES
// ═══════════════════════════════════════════════════════════════
const styles = {
  app: {
    fontFamily: "'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif",
    background: "linear-gradient(180deg, #0a0a14 0%, #0d0d1a 100%)",
    color: "#e2e8f0",
    minHeight: "100vh",
    maxWidth: 480,
    margin: "0 auto",
    position: "relative",
    overflow: "hidden",
  },

  // Header
  header: { padding: "0 0 8px", background: "rgba(124,58,237,0.06)", borderBottom: "1px solid rgba(124,58,237,0.15)" },
  monarchBanner: { position: "relative", height: 180, overflow: "hidden", display: "flex", alignItems: "flex-end", justifyContent: "space-between", padding: "0 16px 12px" },
  monarchImg: { position: "absolute", top: 0, left: 0, width: "100%", height: "100%", objectFit: "cover", objectPosition: "center top", filter: "brightness(0.7)" },
  monarchOverlay: { position: "absolute", bottom: 0, left: 0, right: 0, height: "70%", background: "linear-gradient(transparent, rgba(10,10,20,0.95))", pointerEvents: "none" },
  monarchInfo: { position: "relative", zIndex: 1 },
  rankBadge: { display: "inline-block", padding: "3px 10px", borderRadius: 6, fontSize: 12, fontWeight: 700, letterSpacing: 1, color: "#fff" },
  xpTotal: { fontSize: 12, color: "#94a3b8", marginTop: 4 },
  dailyProgress: { textAlign: "right", position: "relative", zIndex: 1 },
  dailyPct: { fontSize: 28, fontWeight: 800, color: "#7c3aed" },
  dailyLabel: { fontSize: 11, color: "#64748b" },
  xpBarOuter: { height: 4, background: "rgba(124,58,237,0.15)", borderRadius: 2, overflow: "hidden", marginBottom: 8, margin: "0 16px 8px" },
  xpBarInner: { height: "100%", background: "linear-gradient(90deg, #7c3aed, #a78bfa)", borderRadius: 2, transition: "width 0.5s ease" },

  // Active Quest Banner
  activeBanner: {
    display: "flex", alignItems: "center", gap: 10, padding: "10px 12px",
    background: "rgba(124,58,237,0.12)", border: "1px solid rgba(124,58,237,0.3)",
    borderRadius: 10, cursor: "pointer", marginTop: 4,
  },
  activePulse: { color: "#22c55e", fontSize: 10, animation: "pulse 1.5s infinite" },
  activeIcon: { fontSize: 24 },
  activeText: { flex: 1 },
  activeLabel: { fontSize: 13, fontWeight: 700, color: "#e2e8f0" },
  activeDesc: { fontSize: 11, color: "#94a3b8", marginTop: 2 },
  activeTap: { fontSize: 12, fontWeight: 700, color: "#22c55e", padding: "4px 10px", background: "rgba(34,197,94,0.12)", borderRadius: 6 },

  // Tab Bar
  tabBar: { display: "flex", borderBottom: "1px solid rgba(255,255,255,0.06)", background: "rgba(0,0,0,0.3)" },
  tab: { flex: 1, padding: "10px 0", textAlign: "center", fontSize: 13, fontWeight: 600, color: "#64748b", cursor: "pointer", transition: "all 0.2s" },
  tabActive: { color: "#a78bfa", borderBottom: "2px solid #7c3aed" },

  // Content
  content: { height: "calc(100vh - 200px)", overflowY: "auto", WebkitOverflowScrolling: "touch" },

  // Quest List
  questList: { padding: "8px 12px" },
  questCard: {
    padding: "12px 14px", marginBottom: 8, borderRadius: 10,
    background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)",
    transition: "all 0.2s", cursor: "pointer",
  },
  questDone: { opacity: 0.5, background: "rgba(34,197,94,0.04)", border: "1px solid rgba(34,197,94,0.15)" },
  questLocked: { opacity: 0.35 },
  questExpired: { opacity: 0.4, background: "rgba(239,68,68,0.04)", border: "1px solid rgba(239,68,68,0.1)" },
  questActive: { background: "rgba(124,58,237,0.08)", border: "1px solid rgba(124,58,237,0.25)", boxShadow: "0 0 20px rgba(124,58,237,0.1)" },
  questTop: { display: "flex", alignItems: "center", gap: 8, marginBottom: 6 },
  questTime: { fontSize: 11, color: "#64748b", fontWeight: 600, fontFamily: "monospace" },
  criticalBadge: { fontSize: 9, fontWeight: 800, color: "#ef4444", background: "rgba(239,68,68,0.15)", padding: "1px 6px", borderRadius: 4 },
  questXP: { fontSize: 11, color: "#a78bfa", fontWeight: 700, marginLeft: "auto" },
  questMain: { display: "flex", alignItems: "flex-start", gap: 10 },
  questIcon: { fontSize: 22, flexShrink: 0 },
  questLabel: { fontSize: 14, fontWeight: 700, color: "#e2e8f0" },
  questDesc: { fontSize: 12, color: "#94a3b8", marginTop: 3, lineHeight: 1.4 },
  tapHint: { display: "flex", alignItems: "center", justifyContent: "center", gap: 6, marginTop: 8, fontSize: 11, fontWeight: 700, color: "#22c55e", letterSpacing: 1 },
  tapPulse: { width: 6, height: 6, borderRadius: "50%", background: "#22c55e", display: "inline-block" },

  // Stats
  statsPanel: { padding: "12px" },
  statCard: { padding: "16px", marginBottom: 10, borderRadius: 10, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" },
  statTitle: { fontSize: 11, fontWeight: 700, color: "#64748b", letterSpacing: 1, marginBottom: 8 },
  statValue: { fontSize: 20, fontWeight: 800, color: "#e2e8f0" },
  statSub: { fontSize: 12, color: "#94a3b8", marginTop: 4 },
  catRow: { display: "flex", alignItems: "center", gap: 8, marginBottom: 8, fontSize: 12, fontWeight: 600 },
  catBarOuter: { flex: 1, height: 6, background: "rgba(255,255,255,0.06)", borderRadius: 3, overflow: "hidden" },
  catBarInner: { height: "100%", borderRadius: 3, transition: "width 0.5s ease" },
  catPct: { fontSize: 11, color: "#64748b", minWidth: 30, textAlign: "right" },

  // Monarch's Code
  codePanel: { padding: "16px" },
  codeTitle: { fontSize: 20, fontWeight: 800, textAlign: "center", marginBottom: 4 },
  codeSubtitle: { fontSize: 12, color: "#64748b", textAlign: "center", marginBottom: 16 },
  codeRule: { display: "flex", gap: 12, padding: "12px 0", borderBottom: "1px solid rgba(255,255,255,0.04)" },
  codeNum: { fontSize: 12, fontWeight: 800, color: "#7c3aed", fontFamily: "monospace", minWidth: 20 },
  codeText: { fontSize: 14, color: "#e2e8f0", fontWeight: 500, lineHeight: 1.4 },
  codeQuote: { marginTop: 20, padding: 16, textAlign: "center", fontSize: 14, fontStyle: "italic", color: "#a78bfa", background: "rgba(124,58,237,0.06)", borderRadius: 10, border: "1px solid rgba(124,58,237,0.15)" },

  // XP Popup
  xpPopup: {
    position: "fixed", top: 0, left: 0, right: 0, bottom: 0, zIndex: 9999,
    display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
    background: "rgba(0,0,0,0.85)", backdropFilter: "blur(8px)",
    animation: "fadeInOut 2.5s ease forwards",
  },
  xpIcon: { fontSize: 48, marginBottom: 12 },
  xpLabel: { fontSize: 14, fontWeight: 800, color: "#22c55e", letterSpacing: 2 },
  xpAmount: { fontSize: 36, fontWeight: 900, color: "#a78bfa", marginTop: 4 },
  xpQuote: { fontSize: 13, color: "#64748b", fontStyle: "italic", marginTop: 12, maxWidth: 280, textAlign: "center" },

  // Sync dot
  syncDot: { position: "fixed", bottom: 8, right: 8, fontSize: 14, color: "#7c3aed", animation: "spin 1s linear infinite" },
};
