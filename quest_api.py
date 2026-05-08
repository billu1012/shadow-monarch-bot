"""
quest_api.py
─────────────────────────────────────────────────────────────────────────────
Minimal HTTP server bridging shadow_monarch_bot.py ↔ React dashboard.

Endpoints:
  GET  /api/state        → shadow_state.json + enriched quest metadata
  POST /api/complete     → {"quest_id": "wake"} → mark quest complete
  POST /api/skip         → {"quest_id": "wake"} → mark quest skipped
  POST /api/reset_quest  → {"quest_id": "wake"} → reset to pending

Run:  python quest_api.py   (default port 8765)
      QUEST_API_PORT=9000 python quest_api.py

The bot writes to data/shadow_state.json after every action.
This server reads/writes the same file so both stay in sync.
─────────────────────────────────────────────────────────────────────────────
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

BASE_DIR   = Path(__file__).parent
DATA_DIR   = BASE_DIR / "data"
STATE_FILE = DATA_DIR / "shadow_state.json"
ET         = ZoneInfo("America/New_York")

# ── QUEST REGISTRY (mirrors shadow_monarch_bot.py) ────────────────────────
QUESTS = [
    # Morning block
    {"id": "wake",         "title": "Arise",                 "description": "Wake up and get out of bed",                            "xp": 50,  "category": "discipline", "time_block": "morning"},
    {"id": "activation",   "title": "Shadow Activation",     "description": "Morning squats + stretches (50 squats, 5 min stretch)",  "xp": 75,  "category": "fitness",    "time_block": "morning"},
    {"id": "mana",         "title": "Mana Infusion",         "description": "Coffee or Celsius — activate your core energy",          "xp": 25,  "category": "nutrition",  "time_block": "morning"},
    {"id": "outfit",       "title": "Don the Armor",         "description": "Dress sharp. You are the Monarch.",                      "xp": 25,  "category": "discipline", "time_block": "morning"},
    {"id": "commute",      "title": "Shadow March",          "description": "Commute to the dungeon (work)",                          "xp": 30,  "category": "discipline", "time_block": "morning"},
    # Work block
    {"id": "dungeon_open", "title": "Dungeon Gate: Open",    "description": "Start work — be fully present at your desk",             "xp": 100, "category": "focus",      "time_block": "work"},
    {"id": "water1",       "title": "Hydration Protocol I",  "description": "Drink a full glass of water",                            "xp": 50,  "category": "nutrition",  "time_block": "work"},
    {"id": "stand1",       "title": "Movement Protocol I",   "description": "Stand up and walk for 2 minutes",                        "xp": 30,  "category": "fitness",    "time_block": "work"},
    {"id": "deep_work1",   "title": "Shadow Extraction I",   "description": "90 minutes of deep focus — no distractions",             "xp": 100, "category": "focus",      "time_block": "work"},
    {"id": "lunch",        "title": "Main Quest Meal",       "description": "Eat a balanced, protein-rich lunch",                     "xp": 75,  "category": "nutrition",  "time_block": "work"},
    {"id": "water2",       "title": "Hydration Protocol II", "description": "Drink a full glass of water",                            "xp": 50,  "category": "nutrition",  "time_block": "work"},
    {"id": "stand2",       "title": "Movement Protocol II",  "description": "Stand up and walk for 2 minutes",                        "xp": 30,  "category": "fitness",    "time_block": "work"},
    {"id": "deep_work2",   "title": "Shadow Extraction II",  "description": "90 minutes of deep focus — no distractions",             "xp": 100, "category": "focus",      "time_block": "work"},
    {"id": "water3",       "title": "Hydration Protocol III","description": "Drink a full glass of water",                            "xp": 50,  "category": "nutrition",  "time_block": "work"},
    {"id": "stand3",       "title": "Movement Protocol III", "description": "Stand up and walk for 2 minutes",                        "xp": 30,  "category": "fitness",    "time_block": "work"},
    {"id": "deep_work3",   "title": "Shadow Extraction III", "description": "90 minutes of deep focus — finish strong",               "xp": 100, "category": "focus",      "time_block": "work"},
    {"id": "dungeon_clear","title": "Dungeon Cleared",       "description": "Wrap up work — clean desk, review tasks done",           "xp": 75,  "category": "discipline", "time_block": "work"},
    # Evening block
    {"id": "commute_home", "title": "Return March",          "description": "Commute home from the dungeon",                          "xp": 30,  "category": "discipline", "time_block": "evening"},
    {"id": "home",         "title": "Respawn Point",         "description": "Arrive home — change clothes, decompress 10 min",        "xp": 25,  "category": "discipline", "time_block": "evening"},
    {"id": "pre_gym",      "title": "Boss Prep",             "description": "Pre-workout snack + 10 min mental prep",                 "xp": 25,  "category": "nutrition",  "time_block": "evening"},
    {"id": "gym_warmup",   "title": "Shadow Warmup",         "description": "10 min cardio warmup + dynamic stretching",              "xp": 50,  "category": "fitness",    "time_block": "evening"},
    {"id": "gym",          "title": "Shadow Raid",           "description": "Full gym workout — no excuses, no mercy",                "xp": 200, "category": "fitness",    "time_block": "evening"},
    {"id": "recovery_meal","title": "Recovery Rations",      "description": "Post-workout protein meal within 30 min",               "xp": 75,  "category": "nutrition",  "time_block": "evening"},
    {"id": "water4",       "title": "Hydration Protocol IV", "description": "Final hydration push — full glass of water",             "xp": 50,  "category": "nutrition",  "time_block": "evening"},
    {"id": "rest",         "title": "Rest Phase",            "description": "Wind down — no screens 30 min before sleep",             "xp": 30,  "category": "discipline", "time_block": "evening"},
    {"id": "sleep",        "title": "Shadow Sleep",          "description": "In bed by 11 PM — full 7-8 hours recovery",              "xp": 200, "category": "discipline", "time_block": "evening"},
]

QUEST_BY_ID   = {q["id"]: q for q in QUESTS}
TOTAL_XP_MAX  = sum(q["xp"] for q in QUESTS)  # 1555 XP max/weekday

# ── WEEKEND QUEST REGISTRY ────────────────────────────────────────────────────
WEEKEND_QUESTS = [
    {"id": "wake",             "title": "Arise",                    "description": "Wake up and get out of bed",                              "xp": 50,  "category": "discipline", "time_block": "morning"},
    {"id": "activation",       "title": "Shadow Activation",        "description": "Morning squats + stretches (50 squats, 5 min stretch)",    "xp": 75,  "category": "fitness",    "time_block": "morning"},
    {"id": "mana",             "title": "Mana Infusion",            "description": "Coffee or Celsius — activate your core energy",            "xp": 25,  "category": "nutrition",  "time_block": "morning"},
    {"id": "outfit",           "title": "Don the Armor",            "description": "Dress sharp. You are the Monarch.",                        "xp": 25,  "category": "discipline", "time_block": "morning"},
    {"id": "weekend_recovery", "title": "Weekend Recovery Session", "description": "30 min yoga or full-body stretching — restore the vessel", "xp": 75,  "category": "fitness",    "time_block": "morning"},
    {"id": "side_hustle",      "title": "Side Hustle Focus",        "description": "2-hour focused block — personal projects or trading",      "xp": 150, "category": "focus",      "time_block": "morning"},
    {"id": "social_connection","title": "Social Connection",        "description": "Reach out to a friend, family member, or mentor",          "xp": 50,  "category": "discipline", "time_block": "evening"},
    {"id": "meal_prep",        "title": "Meal Prep",                "description": "Prep meals for the week — fuel the machine in advance",    "xp": 100, "category": "nutrition",  "time_block": "evening"},
    {"id": "pre_gym",          "title": "Boss Prep",                "description": "Pre-workout snack + 10 min mental prep",                   "xp": 25,  "category": "nutrition",  "time_block": "evening"},
    {"id": "gym_warmup",       "title": "Shadow Warmup",            "description": "10 min cardio warmup + dynamic stretching",                "xp": 50,  "category": "fitness",    "time_block": "evening"},
    {"id": "gym",              "title": "Shadow Raid",              "description": "Full gym workout — no excuses, no mercy",                  "xp": 200, "category": "fitness",    "time_block": "evening"},
    {"id": "recovery_meal",    "title": "Recovery Rations",         "description": "Post-workout protein meal within 30 min",                  "xp": 75,  "category": "nutrition",  "time_block": "evening"},
    {"id": "water4",           "title": "Hydration Protocol IV",    "description": "Final hydration push — full glass of water",               "xp": 50,  "category": "nutrition",  "time_block": "evening"},
    {"id": "rest",             "title": "Rest Phase",               "description": "Wind down — no screens 30 min before sleep",               "xp": 30,  "category": "discipline", "time_block": "evening"},
    {"id": "sleep",            "title": "Shadow Sleep",             "description": "In bed by 11 PM — full 7-8 hours recovery",                "xp": 200, "category": "discipline", "time_block": "evening"},
]

WEEKEND_QUEST_BY_ID = {q["id"]: q for q in WEEKEND_QUESTS}
WEEKEND_XP_MAX      = sum(q["xp"] for q in WEEKEND_QUESTS)  # 1180 XP max/weekend day
ALL_QUEST_BY_ID     = {**QUEST_BY_ID, **WEEKEND_QUEST_BY_ID}


def is_weekend(date_str: str | None = None) -> bool:
    if date_str:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        d = datetime.now(ET)
    return d.weekday() >= 5


def get_daily_quests(date_str: str | None = None) -> list:
    return WEEKEND_QUESTS if is_weekend(date_str) else QUESTS


def get_daily_xp_max(date_str: str | None = None) -> int:
    return WEEKEND_XP_MAX if is_weekend(date_str) else TOTAL_XP_MAX


# ── iMESSAGE COMPLETION PAGE ─────────────────────────────────────────────────

COMPLETE_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <title>Quest Complete</title>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{background:#08080f;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display','Segoe UI',sans-serif;
         min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}}
    .card{{background:#0f0f1e;border:1px solid #7c3aed;border-radius:20px;padding:40px 28px;
           text-align:center;max-width:380px;width:100%;
           box-shadow:0 0 50px rgba(124,58,237,0.35),0 0 100px rgba(124,58,237,0.1);
           animation:pulse 2.5s ease-in-out infinite alternate}}
    @keyframes pulse{{from{{box-shadow:0 0 30px rgba(124,58,237,0.3)}}to{{box-shadow:0 0 70px rgba(124,58,237,0.65)}}}}
    .icon{{font-size:60px;margin-bottom:14px;animation:drop .6s ease-out}}
    @keyframes drop{{from{{transform:translateY(-20px);opacity:0}}to{{transform:translateY(0);opacity:1}}}}
    .sys{{color:#7c3aed;font-size:10px;letter-spacing:4px;text-transform:uppercase;margin-bottom:6px}}
    h1{{font-size:26px;font-weight:800;color:#f0f0ff;margin-bottom:6px}}
    .qname{{color:#a78bfa;font-size:17px;font-weight:600;margin-bottom:22px;line-height:1.4}}
    .xp{{background:linear-gradient(135deg,#7c3aed,#4f46e5);border-radius:50px;
         padding:11px 30px;display:inline-block;font-size:22px;font-weight:900;
         color:#fff;margin-bottom:22px;box-shadow:0 4px 24px rgba(124,58,237,0.55)}}
    .flavor{{color:#6b7280;font-size:13px;font-style:italic;margin-bottom:22px;line-height:1.5}}
    .already{{color:#10b981;font-size:13px;margin-bottom:8px}}
    .ct{{color:#4b5563;font-size:12px}}
    .bar{{width:100%;height:3px;background:#1c1c2e;border-radius:3px;margin-top:14px;overflow:hidden}}
    .fill{{height:100%;background:linear-gradient(90deg,#7c3aed,#a78bfa);
           border-radius:3px;animation:shrink {duration}s linear forwards}}
    @keyframes shrink{{from{{width:100%}}to{{width:0%}}}}
  </style>
  <script>
    var t={duration};
    function tick(){{
      var el=document.getElementById('ct');
      if(el) el.textContent=t;
      t--;
      if(t<0){{
        try{{window.close()}}catch(e){{}}
        document.body.innerHTML='<p style="color:#6b7280;text-align:center;margin-top:40%;font-family:sans-serif">Logged. You may close this tab.</p>';
      }}else{{setTimeout(tick,1000)}}
    }}
    window.onload=tick;
  </script>
</head>
<body>
  <div class="card">
    <div class="icon">⚔️</div>
    <div class="sys">Shadow Monarch System</div>
    <h1>{status_title}</h1>
    <div class="qname">{quest_title}</div>
    <div class="xp">+{xp} XP</div>
    {already_msg}
    <div class="flavor">{flavor}</div>
    <div class="ct">Closing in <span id="ct">{duration}</span>s…</div>
    <div class="bar"><div class="fill"></div></div>
  </div>
</body>
</html>"""

RANKS = [
    {"name": "E-Rank",         "min_xp": 0},
    {"name": "D-Rank",         "min_xp": 200},
    {"name": "C-Rank",         "min_xp": 500},
    {"name": "B-Rank",         "min_xp": 1000},
    {"name": "A-Rank",         "min_xp": 1800},
    {"name": "S-Rank",         "min_xp": 2800},
    {"name": "National Level", "min_xp": 4000},
    {"name": "Shadow Monarch", "min_xp": 6000},
]


def get_rank(xp: int) -> str:
    rank = RANKS[0]["name"]
    for r in RANKS:
        if xp >= r["min_xp"]:
            rank = r["name"]
    return rank


def today_et() -> str:
    return datetime.now(ET).strftime("%Y-%m-%d")


def _blank_today(date_str: str) -> dict:
    quests = get_daily_quests(date_str)
    return {"date": date_str, "quests": {q["id"]: "pending" for q in quests}}


def _default_state() -> dict:
    return {
        "total_xp":    0,
        "rank":        "E-Rank",
        "streak_days": 0,
        "streak_best": 0,
        "today":       _blank_today(today_et()),
        "history":     [],
    }


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return _default_state()


def save_state(state: dict):
    DATA_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    _sync_legacy(state)


def _sync_legacy(state: dict):
    """Keep data/YYYY-MM-DD.json in sync so the Node.js dashboard still works."""
    td   = state["today"]["date"]
    done = [qid for qid, s in state["today"]["quests"].items() if s == "complete"]
    xp_day = sum(ALL_QUEST_BY_ID[qid]["xp"] for qid in done if qid in ALL_QUEST_BY_ID)
    legacy = {"date": td, "completed": done, "xpEarned": xp_day}
    (DATA_DIR / f"{td}.json").write_text(json.dumps(legacy, indent=2), encoding="utf-8")


def _ensure_today(state: dict) -> dict:
    """Roll over to a new day if the date has changed."""
    if state["today"]["date"] != today_et():
        state["today"] = _blank_today(today_et())
        save_state(state)
    return state


# ── HTTP HANDLER ──────────────────────────────────────────────────────────────

class QuestAPIHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # silence per-request logs; startup prints are enough

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    # ── GET ──────────────────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        params = parse_qs(parsed.query)

        if path.startswith("/api/complete/"):
            quest_id = path[len("/api/complete/"):].strip("/")
            self._handle_get_complete(quest_id, params)
            return

        if not path.startswith("/api/state"):
            self._json(404, {"error": "not found"})
            return

        state = _ensure_today(load_state())

        quests_today  = state["today"]["quests"]
        active_quests = get_daily_quests(state["today"]["date"])
        xp_today_max  = get_daily_xp_max(state["today"]["date"])
        xp_today      = sum(
            ALL_QUEST_BY_ID[qid]["xp"]
            for qid, s in quests_today.items()
            if s == "complete" and qid in ALL_QUEST_BY_ID
        )
        done_count = sum(1 for s in quests_today.values() if s == "complete")
        skip_count = sum(1 for s in quests_today.values() if s == "skipped")
        total      = len(active_quests)

        enriched = {
            **state,
            "xp_today":          xp_today,
            "xp_today_max":      xp_today_max,
            "done_count":        done_count,
            "skip_count":        skip_count,
            "total_quests":      total,
            "completion_pct":    round(done_count / total * 100, 1) if total else 0,
            "quest_meta":        ALL_QUEST_BY_ID,
            "is_weekend":        is_weekend(state["today"]["date"]),
        }
        self._json(200, enriched)

    def _handle_get_complete(self, quest_id: str, params: dict):
        """GET /api/complete/:questId — iMessage one-tap completion, returns HTML."""
        if not quest_id or quest_id not in ALL_QUEST_BY_ID:
            self._raw_html(404, "<html><body style='background:#08080f;color:#e2e8f0;font-family:sans-serif;text-align:center;padding:60px'><h2>Quest not found</h2><p>ID: <code>" + quest_id + "</code></p></body></html>")
            return

        quest       = ALL_QUEST_BY_ID[quest_id]
        state       = _ensure_today(load_state())
        already_done = state["today"]["quests"].get(quest_id) == "complete"

        xp_gained = quest["xp"]
        if not already_done:
            state["today"]["quests"][quest_id] = "complete"
            state["total_xp"] = state.get("total_xp", 0) + xp_gained
            state["rank"]     = get_rank(state["total_xp"])
            save_state(state)
            source = params.get("source", [""])[0]
            print(f"  + COMPLETE  {quest_id:20s}  +{xp_gained} XP  [source={source or 'direct'}]")

        already_msg  = '<div class="already">✅ Already logged — XP was counted earlier</div>' if already_done else ""
        status_title = "Already Complete!" if already_done else "Quest Complete!"
        flavor       = quest.get("description", "The shadows acknowledge your discipline.")

        html = COMPLETE_PAGE.format(
            quest_title  = quest["title"],
            xp           = xp_gained,
            flavor       = flavor,
            status_title = status_title,
            already_msg  = already_msg,
            duration     = 3,
        )
        self._raw_html(200, html)

    # ── POST ─────────────────────────────────────────────────────────────────

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = {}
        if length:
            try:
                body = json.loads(self.rfile.read(length))
            except json.JSONDecodeError:
                self._json(400, {"error": "invalid JSON"})
                return

        if self.path == "/api/complete":
            self._handle_complete(body)
        elif self.path == "/api/skip":
            self._handle_skip(body)
        elif self.path == "/api/reset_quest":
            self._handle_reset(body)
        else:
            self._json(404, {"error": "not found"})

    def _handle_complete(self, body: dict):
        quest_id = body.get("quest_id", "")
        if not quest_id or quest_id not in ALL_QUEST_BY_ID:
            self._json(400, {"error": f"unknown quest_id: {quest_id!r}"})
            return

        state = _ensure_today(load_state())
        current = state["today"]["quests"].get(quest_id, "pending")
        if current == "complete":
            self._json(200, {"ok": True, "message": "already complete",
                             "total_xp": state["total_xp"], "rank": state["rank"]})
            return

        xp_gained = ALL_QUEST_BY_ID[quest_id]["xp"]
        state["today"]["quests"][quest_id] = "complete"
        state["total_xp"] = state.get("total_xp", 0) + xp_gained
        state["rank"]     = get_rank(state["total_xp"])
        save_state(state)
        print(f"  + COMPLETE  {quest_id:20s}  +{xp_gained} XP  ->  {state['total_xp']} XP  [{state['rank']}]")
        self._json(200, {"ok": True, "xp_gained": xp_gained,
                         "total_xp": state["total_xp"], "rank": state["rank"]})

    def _handle_skip(self, body: dict):
        quest_id = body.get("quest_id", "")
        if not quest_id or quest_id not in ALL_QUEST_BY_ID:
            self._json(400, {"error": f"unknown quest_id: {quest_id!r}"})
            return

        state = _ensure_today(load_state())
        if state["today"]["quests"].get(quest_id) != "complete":
            state["today"]["quests"][quest_id] = "skipped"
            save_state(state)
            print(f"  - SKIP      {quest_id}")
        self._json(200, {"ok": True})

    def _handle_reset(self, body: dict):
        quest_id = body.get("quest_id", "")
        if not quest_id or quest_id not in ALL_QUEST_BY_ID:
            self._json(400, {"error": f"unknown quest_id: {quest_id!r}"})
            return

        state = _ensure_today(load_state())
        state["today"]["quests"][quest_id] = "pending"
        save_state(state)
        print(f"  ~ RESET     {quest_id}")
        self._json(200, {"ok": True})

    # ── helpers ───────────────────────────────────────────────────────────────

    def _json(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _raw_html(self, code: int, html: str):
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port   = int(os.environ.get("QUEST_API_PORT", 8765))
    server = HTTPServer(("", port), QuestAPIHandler)
    print(f"Shadow Monarch Quest API  ->  http://localhost:{port}")
    print(f"  GET  /api/state                  (current quest state + metadata)")
    print(f"  GET  /api/complete/:questId      (iMessage one-tap — returns HTML confirmation)")
    print(f"  POST /api/complete               (body: {{quest_id: 'wake'}})")
    print(f"  POST /api/skip                   (body: {{quest_id: 'wake'}})")
    print(f"  POST /api/reset_quest            (body: {{quest_id: 'wake'}})")
    print(f"  State file: {STATE_FILE}")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
