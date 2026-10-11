"""
shadow_monarch_bot.py
─────────────────────────────────────────────────────────────────────────────
Full interactive Discord bot for the Shadow Monarch Protocol.
Built with discord.py 2.x — slash commands + button interactions.

Run:  python shadow_monarch_bot.py
Needs: .env with DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID
─────────────────────────────────────────────────────────────────────────────
"""

import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
import json
import os
import asyncio
import logging
import random
import hashlib
from datetime import datetime, timedelta
from lifeos_bridge import append_event
from market_signals import get_signals, MarketError, INTERVALS as MARKET_INTERVALS
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import aiohttp
from aiohttp import web

# ── ENV ───────────────────────────────────────────────────────────────────────
load_dotenv()
TOKEN      = os.getenv("DISCORD_BOT_TOKEN", "")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID") or "0")
ET         = ZoneInfo("America/New_York")

# ── PATHS ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
DATA_DIR   = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
STATE_FILE = DATA_DIR / "shadow_state.json"

# ── LOGGING ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ShadowMonarch")

# ── COLORS ────────────────────────────────────────────────────────────────────
C_PURPLE    = 0x7C3AED
C_GREEN     = 0x10B981
C_RED       = 0xEF4444
C_GOLD      = 0xFBBF24
C_CYAN      = 0x06B6D4
C_EMERGENCY = 0xFF6B35   # urgent orange — Emergency Quest signature colour

AVATAR_URL = "https://prcasley.github.io/j/monarch.jpg"

# Market brief — Yahoo Finance symbols (crypto as BTC-USD), posted weekdays at MARKET_BRIEF_TIME ET
MARKET_WATCHLIST  = [s.strip() for s in os.getenv("MARKET_WATCHLIST", "SPY,QQQ,NVDA,TSLA,BTC-USD,ETH-USD").split(",") if s.strip()]
MARKET_BRIEF_TIME = os.getenv("MARKET_BRIEF_TIME", "09:00")
BIAS_STYLE = {"bullish": ("🟢", C_GREEN), "bearish": ("🔴", C_RED), "neutral": ("🟡", C_GOLD)}

RANK_UP_GIFS = {
    "D-Rank":         "https://media.tenor.com/imgbnO1rt5QAAAAM/master-roshi.gif",
    "C-Rank":         "https://media4.giphy.com/media/v1.Y2lkPTZjMDliOTUyM21jbjN6ZW52NnpwNTFqOTEwMG9oaTRpYnZ5YjF2N3oyb3JoY3JkdCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/mD6w0JKLEhBGcyBrsi/200w.gif",
    "B-Rank":         "https://media.tenor.com/CxYnMq-4iqYAAAAM/lr-phy-super-saiyan-2-gohan-youth-fighter-entrusted-with-fate.gif",
    "A-Rank":         "https://media.tenor.com/Z3DYCffBSt4AAAAM/super-saiyan3-goku.gif",
    "S-Rank":         "https://i.redd.it/nwyrfewyuqte1.gif",
    "National Level": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTjXozAZnxbGojI7148y0EzMMLVfl6NYqz4fNRiTZVrpw&s=10",
    "Shadow Monarch": "https://i.redd.it/nwyrfewyuqte1.gif",
}

# ═════════════════════════════════════════════════════════════════════════════
# RANK SYSTEM
# ═════════════════════════════════════════════════════════════════════════════

RANKS = [
    {"name": "E-Rank",         "emoji": "⬜", "min_xp": 0,    "next_xp": 200},
    {"name": "D-Rank",         "emoji": "🟩", "min_xp": 200,  "next_xp": 500},
    {"name": "C-Rank",         "emoji": "🟦", "min_xp": 500,  "next_xp": 1000},
    {"name": "B-Rank",         "emoji": "🟧", "min_xp": 1000, "next_xp": 1800},
    {"name": "A-Rank",         "emoji": "🟥", "min_xp": 1800, "next_xp": 2800},
    {"name": "S-Rank",         "emoji": "🟨", "min_xp": 2800, "next_xp": 4000},
    {"name": "National Level", "emoji": "💜", "min_xp": 4000, "next_xp": 6000},
    {"name": "Shadow Monarch", "emoji": "🖤", "min_xp": 6000, "next_xp": None},
]


def get_rank(xp: int) -> dict:
    rank = RANKS[0]
    for r in RANKS:
        if xp >= r["min_xp"]:
            rank = r
    return rank


def xp_bar(xp: int, width: int = 10) -> str:
    rank = get_rank(xp)
    if rank["next_xp"] is None:
        return "█" * width + " **MAX**"
    lo, hi = rank["min_xp"], rank["next_xp"]
    pct = (xp - lo) / (hi - lo)
    filled = int(pct * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"`{bar}` {int(pct * 100)}%"


def progress_bar(value: int, maximum: int, width: int = 10) -> str:
    if maximum == 0:
        return "░" * width
    filled = int((value / maximum) * width)
    return "█" * filled + "░" * (width - filled)


# ═════════════════════════════════════════════════════════════════════════════
# QUEST REGISTRY  (26 quests across three time blocks)
# ═════════════════════════════════════════════════════════════════════════════

QUESTS = [
    # ── MORNING BLOCK (6:00–8:00 AM) ─────────────────────────────────────────
    {
        "id": "wake",
        "title": "Arise",
        "description": "Wake up and get out of bed",
        "xp": 50, "category": "discipline", "time_block": "morning",
        "notify_time": "06:00",
        "flavor": "The Monarch awakens. The dungeon awaits.",
    },
    {
        "id": "activation",
        "title": "Shadow Activation",
        "description": "Morning squats + stretches (50 squats, 5 min stretch)",
        "xp": 75, "category": "fitness", "time_block": "morning",
        "notify_time": "06:15",
        "flavor": "Forge the vessel before the battle begins.",
    },
    {
        "id": "mana",
        "title": "Mana Infusion",
        "description": "Coffee or Celsius — activate your core energy",
        "xp": 25, "category": "nutrition", "time_block": "morning",
        "notify_time": "06:30",
        "flavor": "Even the Shadow Monarch needs mana.",
    },
    {
        "id": "outfit",
        "title": "Don the Armor",
        "description": "Dress sharp. You are the Monarch.",
        "xp": 25, "category": "discipline", "time_block": "morning",
        "notify_time": "06:45",
        "flavor": "Your armor defines your intent.",
    },
    {
        "id": "commute",
        "title": "Shadow March",
        "description": "Commute to the dungeon (work)",
        "xp": 30, "category": "discipline", "time_block": "morning",
        "notify_time": "07:30",
        "flavor": "The march to battle begins.",
    },
    # ── WORK BLOCK (8:30 AM–5:00 PM) ─────────────────────────────────────────
    {
        "id": "dungeon_open",
        "title": "Dungeon Gate: Open",
        "description": "Start work — be fully present at your desk",
        "xp": 100, "category": "focus", "time_block": "work",
        "notify_time": "08:30",
        "flavor": "The Gate opens. Your trial begins.",
    },
    {
        "id": "water1",
        "title": "Hydration Protocol I",
        "description": "Drink a full glass of water",
        "xp": 50, "category": "nutrition", "time_block": "work",
        "notify_time": "09:30",
        "flavor": "Shadows cannot thrive without water.",
    },
    {
        "id": "stand1",
        "title": "Movement Protocol I",
        "description": "Stand up and walk for 2 minutes",
        "xp": 30, "category": "fitness", "time_block": "work",
        "notify_time": "10:00",
        "flavor": "Stagnation is death. Keep moving.",
    },
    {
        "id": "deep_work1",
        "title": "Shadow Extraction I",
        "description": "90 minutes of deep focus — no distractions",
        "xp": 100, "category": "focus", "time_block": "work",
        "notify_time": "10:30",
        "flavor": "Extract maximum value from this dungeon floor.",
    },
    {
        "id": "lunch",
        "title": "Main Quest Meal",
        "description": "Eat a balanced, protein-rich lunch",
        "xp": 75, "category": "nutrition", "time_block": "work",
        "notify_time": "12:00",
        "flavor": "Even monarchs must fuel the body.",
    },
    {
        "id": "water2",
        "title": "Hydration Protocol II",
        "description": "Drink a full glass of water",
        "xp": 50, "category": "nutrition", "time_block": "work",
        "notify_time": "13:00",
        "flavor": "The second wave of hydration.",
    },
    {
        "id": "stand2",
        "title": "Movement Protocol II",
        "description": "Stand up and walk for 2 minutes",
        "xp": 30, "category": "fitness", "time_block": "work",
        "notify_time": "14:00",
        "flavor": "Your body is your greatest shadow soldier.",
    },
    {
        "id": "deep_work2",
        "title": "Shadow Extraction II",
        "description": "90 minutes of deep focus — no distractions",
        "xp": 100, "category": "focus", "time_block": "work",
        "notify_time": "14:30",
        "flavor": "Push deeper. The strongest shadows await.",
    },
    {
        "id": "water3",
        "title": "Hydration Protocol III",
        "description": "Drink a full glass of water",
        "xp": 50, "category": "nutrition", "time_block": "work",
        "notify_time": "15:00",
        "flavor": "Three waves. Consistency is power.",
    },
    {
        "id": "stand3",
        "title": "Movement Protocol III",
        "description": "Stand up and walk for 2 minutes",
        "xp": 30, "category": "fitness", "time_block": "work",
        "notify_time": "15:30",
        "flavor": "Rise again. Always rise.",
    },
    {
        "id": "deep_work3",
        "title": "Shadow Extraction III",
        "description": "90 minutes of deep focus — finish strong",
        "xp": 100, "category": "focus", "time_block": "work",
        "notify_time": "16:00",
        "flavor": "Final extraction. Leave nothing behind.",
    },
    {
        "id": "dungeon_clear",
        "title": "Dungeon Cleared",
        "description": "Wrap up work — clean desk, review tasks done",
        "xp": 75, "category": "discipline", "time_block": "work",
        "notify_time": "17:00",
        "flavor": "The dungeon falls. The Monarch prevails.",
    },
    # ── EVENING BLOCK (5:00–11:00 PM) ────────────────────────────────────────
    {
        "id": "commute_home",
        "title": "Return March",
        "description": "Commute home from the dungeon",
        "xp": 30, "category": "discipline", "time_block": "evening",
        "notify_time": "17:30",
        "flavor": "The warrior returns from battle.",
    },
    {
        "id": "home",
        "title": "Respawn Point",
        "description": "Arrive home — change clothes, decompress 10 min",
        "xp": 25, "category": "discipline", "time_block": "evening",
        "notify_time": "18:00",
        "flavor": "Home is your respawn. Reset and recover.",
    },
    {
        "id": "pre_gym",
        "title": "Boss Prep",
        "description": "Pre-workout snack + 10 min mental prep",
        "xp": 25, "category": "nutrition", "time_block": "evening",
        "notify_time": "18:30",
        "flavor": "You don't fight a boss unprepared.",
    },
    {
        "id": "gym_warmup",
        "title": "Shadow Warmup",
        "description": "10 min cardio warmup + dynamic stretching",
        "xp": 50, "category": "fitness", "time_block": "evening",
        "notify_time": "18:45",
        "flavor": "Warm the shadows before they strike.",
    },
    {
        "id": "gym",
        "title": "Shadow Raid",
        "description": "Full gym workout — no excuses, no mercy",
        "xp": 200, "category": "fitness", "time_block": "evening",
        "notify_time": "19:00",
        "flavor": "This is where E-Ranks become S-Ranks.",
    },
    {
        "id": "recovery_meal",
        "title": "Recovery Rations",
        "description": "Post-workout protein meal within 30 min",
        "xp": 75, "category": "nutrition", "time_block": "evening",
        "notify_time": "20:30",
        "flavor": "Feed the shadows. They earned it.",
    },
    {
        "id": "water4",
        "title": "Hydration Protocol IV",
        "description": "Final hydration push — full glass of water",
        "xp": 50, "category": "nutrition", "time_block": "evening",
        "notify_time": "21:00",
        "flavor": "Complete the ritual. Four waves of power.",
    },
    {
        "id": "rest",
        "title": "Rest Phase",
        "description": "Wind down — no screens 30 min before sleep",
        "xp": 30, "category": "discipline", "time_block": "evening",
        "notify_time": "21:30",
        "flavor": "Even the Monarch must rest to rule again.",
    },
    {
        "id": "sleep",
        "title": "Shadow Sleep",
        "description": "In bed by 11 PM — full 7-8 hours recovery",
        "xp": 200, "category": "discipline", "time_block": "evening",
        "notify_time": "23:00",
        "flavor": "The Monarch sleeps. The shadows stand guard.",
    },
]

QUEST_BY_ID = {q["id"]: q for q in QUESTS}
TOTAL_XP    = sum(q["xp"] for q in QUESTS)   # 1555 XP max per weekday

CAT_EMOJI   = {"discipline": "⚔️", "fitness": "💪", "nutrition": "🍖", "focus": "🧠"}
BLOCK_TITLE = {"morning": "🌅 Morning", "work": "🏢 Work Block", "evening": "🌙 Evening"}

# ═════════════════════════════════════════════════════════════════════════════
# WEEKEND QUEST REGISTRY  (no work block — recovery + side hustle focus)
# ═════════════════════════════════════════════════════════════════════════════

WEEKEND_QUESTS = [
    # ── MORNING BLOCK (8:00–10:00 AM) ────────────────────────────────────────
    {
        "id": "wake",
        "title": "Arise",
        "description": "Wake up and get out of bed",
        "xp": 50, "category": "discipline", "time_block": "morning",
        "notify_time": "08:00",
        "flavor": "The Monarch awakens. The weekend dungeon awaits.",
    },
    {
        "id": "activation",
        "title": "Shadow Activation",
        "description": "Morning squats + stretches (50 squats, 5 min stretch)",
        "xp": 75, "category": "fitness", "time_block": "morning",
        "notify_time": "08:15",
        "flavor": "Forge the vessel before the battle begins.",
    },
    {
        "id": "mana",
        "title": "Mana Infusion",
        "description": "Coffee or Celsius — activate your core energy",
        "xp": 25, "category": "nutrition", "time_block": "morning",
        "notify_time": "08:30",
        "flavor": "Even the Shadow Monarch needs mana.",
    },
    {
        "id": "outfit",
        "title": "Don the Armor",
        "description": "Dress sharp. You are the Monarch.",
        "xp": 25, "category": "discipline", "time_block": "morning",
        "notify_time": "09:00",
        "flavor": "Your armor defines your intent.",
    },
    # ── WEEKEND-SPECIFIC BLOCK (10:00 AM–4:00 PM) ────────────────────────────
    {
        "id": "weekend_recovery",
        "title": "Weekend Recovery Session",
        "description": "30 min yoga or full-body stretching — restore the vessel",
        "xp": 75, "category": "fitness", "time_block": "morning",
        "notify_time": "10:00",
        "flavor": "The strongest shadows recover before they strike again.",
    },
    {
        "id": "side_hustle",
        "title": "Side Hustle Focus",
        "description": "2-hour focused block — personal projects or trading",
        "xp": 150, "category": "focus", "time_block": "morning",
        "notify_time": "11:00",
        "flavor": "Dungeons beyond the office. Build your empire.",
    },
    {
        "id": "social_connection",
        "title": "Social Connection",
        "description": "Reach out to a friend, family member, or mentor",
        "xp": 50, "category": "discipline", "time_block": "evening",
        "notify_time": "13:00",
        "flavor": "Even monarchs need their guild.",
    },
    {
        "id": "meal_prep",
        "title": "Meal Prep",
        "description": "Prep meals for the week — fuel the machine in advance",
        "xp": 100, "category": "nutrition", "time_block": "evening",
        "notify_time": "15:00",
        "flavor": "Prepare the rations. Victory favors the prepared.",
    },
    # ── EVENING BLOCK (5:00–11:00 PM) ────────────────────────────────────────
    {
        "id": "pre_gym",
        "title": "Boss Prep",
        "description": "Pre-workout snack + 10 min mental prep",
        "xp": 25, "category": "nutrition", "time_block": "evening",
        "notify_time": "17:00",
        "flavor": "You don't fight a boss unprepared.",
    },
    {
        "id": "gym_warmup",
        "title": "Shadow Warmup",
        "description": "10 min cardio warmup + dynamic stretching",
        "xp": 50, "category": "fitness", "time_block": "evening",
        "notify_time": "17:30",
        "flavor": "Warm the shadows before they strike.",
    },
    {
        "id": "gym",
        "title": "Shadow Raid",
        "description": "Full gym workout — no excuses, no mercy",
        "xp": 200, "category": "fitness", "time_block": "evening",
        "notify_time": "18:30",
        "flavor": "This is where E-Ranks become S-Ranks.",
    },
    {
        "id": "recovery_meal",
        "title": "Recovery Rations",
        "description": "Post-workout protein meal within 30 min",
        "xp": 75, "category": "nutrition", "time_block": "evening",
        "notify_time": "20:00",
        "flavor": "Feed the shadows. They earned it.",
    },
    {
        "id": "water4",
        "title": "Hydration Protocol IV",
        "description": "Final hydration push — full glass of water",
        "xp": 50, "category": "nutrition", "time_block": "evening",
        "notify_time": "20:30",
        "flavor": "Complete the ritual. Four waves of power.",
    },
    {
        "id": "rest",
        "title": "Rest Phase",
        "description": "Wind down — no screens 30 min before sleep",
        "xp": 30, "category": "discipline", "time_block": "evening",
        "notify_time": "21:30",
        "flavor": "Even the Monarch must rest to rule again.",
    },
    {
        "id": "sleep",
        "title": "Shadow Sleep",
        "description": "In bed by 11 PM — full 7-8 hours recovery",
        "xp": 200, "category": "discipline", "time_block": "evening",
        "notify_time": "23:00",
        "flavor": "The Monarch sleeps. The shadows stand guard.",
    },
]

WEEKEND_QUEST_BY_ID = {q["id"]: q for q in WEEKEND_QUESTS}
WEEKEND_XP          = sum(q["xp"] for q in WEEKEND_QUESTS)  # 1180 XP max/weekend day

# Merged lookup — covers quest IDs from both weekday and weekend schedules
ALL_QUEST_BY_ID = {**QUEST_BY_ID, **WEEKEND_QUEST_BY_ID}


def is_weekend(date_str: str | None = None) -> bool:
    """True if the given YYYY-MM-DD string (or today) falls on Saturday/Sunday."""
    if date_str:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        d = datetime.now(ET)
    return d.weekday() >= 5   # 5=Sat, 6=Sun


def get_daily_quests(date_str: str | None = None) -> list:
    """Return weekend or weekday quest list based on the day.
    meal_prep is Sunday-only — excluded on Saturday.
    """
    if not is_weekend(date_str):
        return QUESTS
    d = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now(ET)
    if d.weekday() == 5:  # Saturday — exclude meal_prep
        return [q for q in WEEKEND_QUESTS if q["id"] != "meal_prep"]
    return WEEKEND_QUESTS  # Sunday — full weekend list


def get_daily_xp_max(date_str: str | None = None) -> int:
    if not is_weekend(date_str):
        return TOTAL_XP
    d = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now(ET)
    if d.weekday() == 5:  # Saturday — meal_prep excluded
        meal_prep_xp = next((q["xp"] for q in WEEKEND_QUESTS if q["id"] == "meal_prep"), 0)
        return WEEKEND_XP - meal_prep_xp
    return WEEKEND_XP


# ═════════════════════════════════════════════════════════════════════════════
# DATA MANAGEMENT
# ═════════════════════════════════════════════════════════════════════════════

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
    # Try main state file first
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            log.warning("Main state file corrupted, trying backup...")
    # Fall back to backup
    if BACKUP_FILE.exists():
        try:
            state = json.loads(BACKUP_FILE.read_text(encoding="utf-8"))
            log.info("Restored state from backup file.")
            save_state(state)  # restore the main file
            return state
        except (json.JSONDecodeError, OSError):
            log.warning("Backup file also corrupted.")
    # Last resort: defaults
    log.warning("No valid state found — creating fresh defaults.")
    state = _default_state()
    save_state(state)
    return state


BACKUP_FILE = DATA_DIR / "shadow_state.backup.json"

def save_state(state: dict):
    # Backup before overwrite — prevents data loss from corruption
    if STATE_FILE.exists():
        try:
            BACKUP_FILE.write_text(STATE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            pass
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    _sync_legacy(state)


def _sync_legacy(state: dict):
    """Keep data/YYYY-MM-DD.json in sync so the Node.js dashboard still works."""
    td     = state["today"]["date"]
    done   = [qid for qid, s in state["today"]["quests"].items() if s == "complete"]
    xp_day = sum(ALL_QUEST_BY_ID[qid]["xp"] for qid in done if qid in ALL_QUEST_BY_ID)
    legacy = {"date": td, "completed": done, "xpEarned": xp_day}
    (DATA_DIR / f"{td}.json").write_text(json.dumps(legacy, indent=2), encoding="utf-8")


def maybe_reset(state: dict) -> tuple[dict, bool]:
    """Archive yesterday and reset today if the date has changed."""
    td = today_et()
    if state["today"]["date"] == td:
        return state, False

    # Archive yesterday
    yesterday     = state["today"]
    active_quests = get_daily_quests(yesterday["date"])
    done_count    = sum(1 for s in yesterday["quests"].values() if s == "complete")
    pct           = done_count / len(active_quests) if active_quests else 0
    xp_earned     = sum(
        ALL_QUEST_BY_ID[qid]["xp"]
        for qid, s in yesterday["quests"].items()
        if s == "complete" and qid in ALL_QUEST_BY_ID
    )

    # Category breakdown for weekly/monthly reports
    cat_stats: dict[str, dict] = {}
    for cat in ("discipline", "fitness", "nutrition", "focus"):
        cat_qs   = [q for q in active_quests if q["category"] == cat]
        cat_done = sum(1 for q in cat_qs if yesterday["quests"].get(q["id"]) == "complete")
        cat_stats[cat] = {"done": cat_done, "total": len(cat_qs)}

    state["history"].append({
        "date":           yesterday["date"],
        "completed":      done_count,
        "skipped":        sum(1 for s in yesterday["quests"].values() if s == "skipped"),
        "total":          len(active_quests),
        "completion_pct": round(pct * 100, 1),
        "xp_earned":      xp_earned,
        "cat_stats":      cat_stats,
    })
    state["history"] = state["history"][-90:]   # keep 90-day rolling window

    # Streak
    if pct >= 0.8:
        state["streak_days"] += 1
        state["streak_best"] = max(state["streak_days"], state["streak_best"])
    else:
        state["streak_days"] = 0

    state["today"] = _blank_today(td)
    state["rank"]  = get_rank(state["total_xp"])["name"]
    save_state(state)
    return state, True


def get_day_stats(state: dict) -> dict:
    active    = get_daily_quests(state["today"]["date"])
    quest_map = state["today"]["quests"]
    completed = [qid for qid, s in quest_map.items() if s == "complete"]
    skipped   = [qid for qid, s in quest_map.items() if s == "skipped"]
    pending   = [qid for qid, s in quest_map.items() if s == "pending"]
    xp_earned = sum(ALL_QUEST_BY_ID[qid]["xp"] for qid in completed if qid in ALL_QUEST_BY_ID)
    total     = len(active)
    return {
        "completed":      completed,
        "skipped":        skipped,
        "pending":        pending,
        "xp_earned":      xp_earned,
        "total":          total,
        "completion_pct": round(len(completed) / total * 100, 1) if total else 0,
    }


def do_complete(state: dict, quest_id: str) -> tuple[bool, int, bool]:
    """Mark a quest complete. Returns (success, xp_gained, ranked_up)."""
    if state["today"]["quests"].get(quest_id) == "complete":
        return False, 0, False
    quest = ALL_QUEST_BY_ID.get(quest_id)
    if not quest:
        return False, 0, False
    old_rank = get_rank(state["total_xp"])
    state["today"]["quests"][quest_id] = "complete"
    state["total_xp"] += quest["xp"]
    new_rank = get_rank(state["total_xp"])
    state["rank"] = new_rank["name"]
    save_state(state)
    return True, quest["xp"], old_rank["name"] != new_rank["name"]


def do_skip(state: dict, quest_id: str) -> bool:
    if state["today"]["quests"].get(quest_id) == "complete":
        return False
    state["today"]["quests"][quest_id] = "skipped"
    save_state(state)
    return True


# ═════════════════════════════════════════════════════════════════════════════
# DISCORD VIEWS  (interactive buttons)
# ═════════════════════════════════════════════════════════════════════════════

class QuestView(ui.View):
    """Attached to each auto-posted quest embed."""

    def __init__(self, quest_id: str, bot_instance: "ShadowBot"):
        super().__init__(timeout=86400)   # 24-hour window
        self.quest_id = quest_id
        self.bot_ref  = bot_instance

    def _disable_all(self):
        for item in self.children:
            item.disabled = True

    @ui.button(label="✅  Complete", style=discord.ButtonStyle.success)
    async def complete_btn(self, interaction: discord.Interaction, button: ui.Button):
        state = load_state()
        state, _ = maybe_reset(state)
        quest = ALL_QUEST_BY_ID[self.quest_id]
        success, xp, ranked_up = do_complete(state, self.quest_id)

        if not success:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"**{quest['title']}** is already marked complete! ✅",
                    color=C_CYAN,
                ),
                ephemeral=True,
            )
            return

        stats  = get_day_stats(state)
        bar    = progress_bar(len(stats["completed"]), stats["total"])
        embed  = discord.Embed(
            title=       "⚔️  QUEST COMPLETE",
            description= f"**{quest['title']}**\n*{quest['flavor']}*",
            color=       C_GREEN,
        )
        embed.add_field(name="XP Gained",  value=f"+{xp} XP",                                      inline=True)
        embed.add_field(name="Total XP",   value=f"{state['total_xp']:,}",                          inline=True)
        embed.add_field(name="Today",      value=f"{len(stats['completed'])}/{stats['total']}", inline=True)
        embed.add_field(
            name="Progress",
            value=f"`{bar}` {stats['completion_pct']}%",
            inline=False,
        )
        embed.set_thumbnail(url=AVATAR_URL)
        embed.set_footer(text=f"Rank: {state['rank']}  •  {state['streak_days']} 🔥 day streak")

        self._disable_all()
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(embed=embed)

        if ranked_up:
            await self.bot_ref.send_rank_up(state)

    @ui.button(label="⏭  Skip", style=discord.ButtonStyle.secondary)
    async def skip_btn(self, interaction: discord.Interaction, button: ui.Button):
        state = load_state()
        state, _ = maybe_reset(state)
        quest = QUEST_BY_ID[self.quest_id]
        do_skip(state, self.quest_id)

        embed = discord.Embed(
            description=f"Skipped **{quest['title']}**. The shadows take note.",
            color=C_RED,
        )
        self._disable_all()
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(embed=embed, ephemeral=True)


# ═════════════════════════════════════════════════════════════════════════════
# EMERGENCY QUEST  (surprise / on-demand quests)
# ═════════════════════════════════════════════════════════════════════════════

def build_emergency_embed(title: str, description: str, xp: int) -> discord.Embed:
    embed = discord.Embed(
        title="⚠️  EMERGENCY QUEST HAS ARRIVED",
        description=(
            "**WARNING: An Emergency Quest has been issued. "
            "Failure to comply will result in penalties.**\n\n"
            f"**{title}**\n{description}"
        ),
        color=C_EMERGENCY,
    )
    embed.add_field(name="⚡ Reward",  value=f"+{xp} XP  *(Emergency Bonus)*", inline=True)
    embed.add_field(name="Category",   value="🆘 Emergency",                    inline=True)
    embed.set_thumbnail(url=AVATAR_URL)
    embed.set_footer(text="The System demands your immediate action.")
    return embed


class EmergencyQuestView(ui.View):
    """Button view for surprise / emergency quests not in the main quest registry."""

    def __init__(self, quest_id: str, title: str, xp: int, bot_instance: "ShadowBot"):
        super().__init__(timeout=86400)
        self.quest_id = quest_id
        self.title    = title
        self.xp       = xp
        self.bot_ref  = bot_instance

    def _disable_all(self):
        for item in self.children:
            item.disabled = True

    @ui.button(label="✅  Complete", style=discord.ButtonStyle.danger)
    async def complete_btn(self, interaction: discord.Interaction, button: ui.Button):
        state = load_state()
        state, _ = maybe_reset(state)

        if state["today"]["quests"].get(self.quest_id) == "complete":
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"**{self.title}** is already complete! ✅",
                    color=C_CYAN,
                ),
                ephemeral=True,
            )
            return

        old_rank = get_rank(state["total_xp"])
        state["today"]["quests"][self.quest_id] = "complete"
        state["total_xp"] += self.xp
        new_rank = get_rank(state["total_xp"])
        state["rank"] = new_rank["name"]
        save_state(state)
        ranked_up = old_rank["name"] != new_rank["name"]

        embed = discord.Embed(
            title="⚔️  EMERGENCY QUEST COMPLETE",
            description=f"**{self.title}**\n*The System acknowledges your compliance.*",
            color=C_GREEN,
        )
        embed.add_field(name="XP Gained", value=f"+{self.xp} XP",         inline=True)
        embed.add_field(name="Total XP",  value=f"{state['total_xp']:,}", inline=True)
        embed.set_footer(text=f"Rank: {state['rank']}  •  Emergency Quest Cleared")
        embed.set_thumbnail(url=AVATAR_URL)

        self._disable_all()
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(embed=embed)

        if ranked_up:
            await self.bot_ref.send_rank_up(state)

    @ui.button(label="⏭  Skip", style=discord.ButtonStyle.secondary)
    async def skip_btn(self, interaction: discord.Interaction, button: ui.Button):
        state = load_state()
        state, _ = maybe_reset(state)
        state["today"]["quests"][self.quest_id] = "skipped"
        save_state(state)

        embed = discord.Embed(
            description=f"Skipped **{self.title}**. The shadows note your failure.",
            color=C_RED,
        )
        self._disable_all()
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(embed=embed, ephemeral=True)


# ═════════════════════════════════════════════════════════════════════════════
# ARCHITECT WELCOME
# ═════════════════════════════════════════════════════════════════════════════

C_ARCHITECT = 0x1a1a2e   # deep midnight blue — the Architect's signature colour


def build_architect_embed() -> discord.Embed:
    embed = discord.Embed(
        title="FROM THE ARCHITECT:",
        description=(
            "**[DAILY QUEST HAS ARRIVED]**\n\n"
            "**I.** Complete all assigned quests before midnight.\n"
            "**II.** Failure to complete will result in penalty.\n"
            "**III.** The System rewards the disciplined.\n"
            "**IV.** Rise — or be forgotten.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Type `/start` to accept the System's power."
        ),
        color=C_ARCHITECT,
    )
    embed.set_author(name="SYSTEM · THE ARCHITECT — KANDIARU")
    embed.set_footer(text="I have been watching you. Now the real test begins.")
    embed.set_image(url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTu4hYbwBRe2idHGiPAAgBwhz9wOxhPjgGXAgBjln8CHQ&s=10")
    return embed


class StartView(discord.ui.View):
    def __init__(self, bot_instance):
        super().__init__(timeout=None)
        self.bot_instance = bot_instance
        self._accepted = False

    async def _accept(self, interaction: discord.Interaction):
        if self._accepted:
            await interaction.response.defer(ephemeral=True)
            return
        self._accepted = True

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        await interaction.followup.send(
            embed=discord.Embed(
                description="CONTRACT ACCEPTED — Your daily quests begin now.",
                color=C_PURPLE,
            )
        )
        await interaction.followup.send("https://media.tenor.com/HMlYHYdk2SMAAAAd/solo-leveling-statue-smile-solo-leveling.gif")
        await self.bot_instance._send_arise()

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def yes_button_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._accept(interaction)

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def yes_button_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._accept(interaction)


# ═════════════════════════════════════════════════════════════════════════════
# WEEKLY CHECK-IN FORM + EMERGENCY QUEST GENERATOR
# ═════════════════════════════════════════════════════════════════════════════

CHECKIN_FILE = DATA_DIR / "weekly_checkins.json"

# ── Emergency quest pools ────────────────────────────────────────────────────

PUNISHMENT_QUESTS = {
    "fitness": [
        {"title": "IRON ATONEMENT", "desc": "100 push-ups + 100 squats + 50 burpees. Split throughout the day. No excuses.", "xp": 200},
        {"title": "CARDIO DUNGEON", "desc": "30 min run or 45 min intense walk. The shadows demand your sweat.", "xp": 150},
        {"title": "GYM REDEMPTION ARC", "desc": "Hit the gym TODAY. Full workout — no shortcuts, no phone scrolling.", "xp": 250},
        {"title": "BODY WEIGHT TRIAL", "desc": "4 sets: 25 push-ups, 30 squats, 20 lunges, 1 min plank. Time it.", "xp": 175},
    ],
    "nutrition": [
        {"title": "CLEAN FUEL ONLY", "desc": "Zero junk food, zero sugar drinks for 48 hours. Log every meal.", "xp": 200},
        {"title": "MEAL PREP DUNGEON", "desc": "Prep 4 clean meals for the week. Protein + veg + complex carbs.", "xp": 175},
        {"title": "HYDRATION SIEGE", "desc": "Drink 1 gallon of water today. No soda, no juice, no excuses.", "xp": 125},
        {"title": "SUGAR DETOX GATE", "desc": "3 days zero added sugar. Track it. The System will know if you cheat.", "xp": 250},
    ],
    "discipline": [
        {"title": "PHONE LOCKDOWN", "desc": "2-hour phone-free deep work block. No social media. No scrolling.", "xp": 150},
        {"title": "WAKE UP PROTOCOL", "desc": "Wake up at 5:30 AM for 3 consecutive days. The shadows rise early.", "xp": 200},
        {"title": "ZERO EXCUSES DAY", "desc": "Complete 100% of today's quests. Every. Single. One.", "xp": 300},
        {"title": "STANDING FORTRESS", "desc": "Stand for every meeting and every work session today. 10+ hours on your feet.", "xp": 175},
    ],
    "focus": [
        {"title": "DEEP WORK MARATHON", "desc": "4 uninterrupted 45-min deep work sessions. Phone in another room.", "xp": 200},
        {"title": "INBOX ZERO RAID", "desc": "Clear your email, Slack, and notifications. Zero unread. Zero pending.", "xp": 150},
        {"title": "SINGLE TASK SIEGE", "desc": "Pick ONE project. Work on ONLY that project for 3 hours straight.", "xp": 175},
    ],
}

GROWTH_QUESTS = [
    {"title": "SHADOW NETWORK", "desc": "Reach out to 3 people in your industry. LinkedIn, text, or in person. Build your army.", "xp": 200, "cat": "social"},
    {"title": "KNOWLEDGE DUNGEON", "desc": "Watch 2 hours of educational content (YouTube tutorials, courses, docs). Take notes.", "xp": 150, "cat": "growth"},
    {"title": "SIDE HUSTLE SPRINT", "desc": "Spend 2 hours on a money-making side project. Ship something.", "xp": 250, "cat": "money"},
    {"title": "CONTENT CREATOR GATE", "desc": "Create and post one piece of content — LinkedIn, Twitter, blog. Share your knowledge.", "xp": 200, "cat": "growth"},
    {"title": "SKILL UPGRADE", "desc": "Learn something new: a Python library, a Power BI technique, a business concept. Document it.", "xp": 175, "cat": "growth"},
    {"title": "MENTOR QUEST", "desc": "Help someone with a problem in your area of expertise. Teaching = mastery.", "xp": 150, "cat": "social"},
    {"title": "COLD CALL COURAGE", "desc": "Make 1 uncomfortable outreach — a business pitch, a collaboration ask, a negotiation.", "xp": 300, "cat": "money"},
    {"title": "FUTURE ARCHITECT", "desc": "Spend 1 hour planning your next 90 days. Goals, milestones, systems. Write it down.", "xp": 200, "cat": "discipline"},
    {"title": "iOS FOCUS APP SPRINT", "desc": "Dedicate 2 hours to the iOS Focus Remind App with Claude Chakra. The S-Rank gate won't open itself.", "xp": 250, "cat": "growth"},
    {"title": "SHADOW FUSION LINK", "desc": "Work on bridging Claude Igris and Claude Chakra. Document how the two should communicate.", "xp": 200, "cat": "growth"},
]


def _load_checkins() -> list:
    if CHECKIN_FILE.exists():
        try:
            return json.loads(CHECKIN_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save_checkin(entry: dict):
    checkins = _load_checkins()
    checkins.append(entry)
    checkins = checkins[-52]  # keep 1 year of weeklies
    CHECKIN_FILE.write_text(json.dumps(checkins, indent=2), encoding="utf-8")


def generate_emergency_quest(checkin: dict, state: dict) -> dict:
    """Generate a custom emergency quest based on check-in answers and quest history."""
    weaknesses = checkin.get("weaknesses", "").lower()
    wins       = checkin.get("wins", "").lower()
    goals      = checkin.get("goals", "").lower()
    discipline = int(checkin.get("discipline_rating", 5))

    # Determine weak categories from text + quest history
    weak_cats = []
    fitness_words   = ["gym", "workout", "exercise", "run", "push", "body", "weight", "cardio", "skip"]
    nutrition_words = ["eat", "food", "junk", "sugar", "meal", "cook", "diet", "dunkin", "fast food"]
    discipline_words = ["sleep", "wake", "phone", "procrastinat", "lazy", "late", "scroll", "distract"]
    focus_words     = ["focus", "work", "project", "deep", "concentrate", "productive"]

    for word in fitness_words:
        if word in weaknesses:
            weak_cats.append("fitness")
            break
    for word in nutrition_words:
        if word in weaknesses:
            weak_cats.append("nutrition")
            break
    for word in discipline_words:
        if word in weaknesses:
            weak_cats.append("discipline")
            break
    for word in focus_words:
        if word in weaknesses:
            weak_cats.append("focus")
            break

    # Also check quest completion history for weak categories
    recent_history = state.get("history", [])[-7:]
    for entry in recent_history:
        for cat, stats in entry.get("cat_stats", {}).items():
            if stats.get("total", 0) > 0:
                pct = stats["done"] / stats["total"]
                if pct < 0.5 and cat not in weak_cats:
                    weak_cats.append(cat)

    # Decide: punishment or growth (mix of both, weighted by discipline rating)
    # Low discipline → more punishment. High discipline → more growth.
    seed = hashlib.md5(checkin.get("date", "").encode()).hexdigest()
    rng  = random.Random(seed)

    punishment_weight = max(0.3, 1.0 - (discipline / 10))
    pick_punishment   = rng.random() < punishment_weight

    if pick_punishment and weak_cats:
        cat   = rng.choice(weak_cats)
        pool  = PUNISHMENT_QUESTS.get(cat, PUNISHMENT_QUESTS["discipline"])
        quest = rng.choice(pool)
        return {
            "quest_id": f"emergency_punishment_{checkin.get('date', 'unknown')}",
            "title":    f"⚠️ {quest['title']}",
            "desc":     quest["desc"] + f"\n\n*Triggered by: weak {cat} performance this week.*",
            "xp":       quest["xp"],
            "type":     "punishment",
            "category": cat,
        }
    else:
        quest = rng.choice(GROWTH_QUESTS)
        # Boost XP if goals mention the quest topic
        bonus = 50 if any(w in goals for w in quest["title"].lower().split()) else 0
        return {
            "quest_id": f"emergency_growth_{checkin.get('date', 'unknown')}",
            "title":    f"🌟 {quest['title']}",
            "desc":     quest["desc"] + "\n\n*The System rewards those who grow beyond their limits.*",
            "xp":       quest["xp"] + bonus,
            "type":     "growth",
            "category": quest["cat"],
        }


class WeeklyCheckinModal(ui.Modal, title="⚔️ WEEKLY SHADOW CHECK-IN"):
    weaknesses = ui.TextInput(
        label="What did you skip or struggle with?",
        placeholder="e.g. skipped gym 3x, ate junk, woke up late...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500,
    )
    wins = ui.TextInput(
        label="What went well this week?",
        placeholder="e.g. hit all deep work blocks, ate clean, finished project...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500,
    )
    goals = ui.TextInput(
        label="What do you want to push next week?",
        placeholder="e.g. gym 4x, finish iOS app, network more...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500,
    )
    discipline_rating = ui.TextInput(
        label="Rate your discipline this week (1-10)",
        placeholder="1 = trash, 10 = shadow monarch level",
        style=discord.TextStyle.short,
        required=True,
        max_length=2,
    )

    def __init__(self, bot_ref):
        super().__init__()
        self.bot_ref = bot_ref

    async def on_submit(self, interaction: discord.Interaction):
        # Validate discipline rating
        try:
            rating = int(self.discipline_rating.value)
            rating = max(1, min(10, rating))
        except ValueError:
            rating = 5

        now    = datetime.now(ET)
        state  = load_state()
        checkin = {
            "date":              now.strftime("%Y-%m-%d"),
            "weaknesses":        self.weaknesses.value,
            "wins":              self.wins.value,
            "goals":             self.goals.value,
            "discipline_rating": rating,
        }
        _save_checkin(checkin)

        # Generate the emergency quest
        eq = generate_emergency_quest(checkin, state)

        # Confirm to user
        embed = discord.Embed(
            title="✅  CHECK-IN RECEIVED",
            description="The System has analyzed your report. An Emergency Quest will be issued shortly.",
            color=C_GREEN,
        )
        embed.add_field(name="Discipline", value=f"{'🟩' * rating}{'⬜' * (10 - rating)} {rating}/10", inline=False)
        embed.add_field(name="Weaknesses", value=self.weaknesses.value[:200], inline=False)
        embed.add_field(name="Wins",       value=self.wins.value[:200],       inline=False)
        embed.add_field(name="Next Week",  value=self.goals.value[:200],      inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Fire the emergency quest to the channel
        await asyncio.sleep(3)  # dramatic pause
        await self.bot_ref.send_emergency_quest(eq["title"], eq["desc"], eq["xp"], eq["quest_id"])


class CheckinPromptView(discord.ui.View):
    """Persistent view with a button to open the weekly check-in form."""
    def __init__(self, bot_ref):
        super().__init__(timeout=None)
        self.bot_ref = bot_ref

    @discord.ui.button(label="📋 Open Check-In", style=discord.ButtonStyle.primary, custom_id="weekly_checkin_btn")
    async def open_checkin(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WeeklyCheckinModal(self.bot_ref))


# ═════════════════════════════════════════════════════════════════════════════
# BOT
# ═════════════════════════════════════════════════════════════════════════════

class ShadowBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self._fired: set[str] = set()   # tracks which scheduled messages were sent today
        self._welcome_sent: bool = False  # ensures the Architect welcome fires only once per process
        self._startup_emergency: dict | None = None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    async def setup_hook(self):
        await self.tree.sync()
        self.scheduler.start()
        log.info("Slash commands synced. Scheduler started.")

    async def on_ready(self):
        log.info(f"SYSTEM online  ·  {self.user}  (ID: {self.user.id})")
        log.info(f"Quest channel : {CHANNEL_ID}")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="the Shadow Realm",
            )
        )
        if not self._welcome_sent:
            self._welcome_sent = True
            ch = await self.quest_channel()
            if ch:
                await ch.send(embed=build_architect_embed())

        if self._startup_emergency:
            eq = self._startup_emergency
            self._startup_emergency = None
            await self.send_emergency_quest(
                eq["title"], eq["description"], eq["xp"], eq["quest_id"]
            )
            log.info(f"Startup emergency quest fired: {eq['title']}")
    async def on_message(self, message: discord.Message):
        """Read & respond to plain-text messages in the quest channel."""
        if message.author.bot or not message.content:
            return
        if message.channel.id != CHANNEL_ID:
            return

        text = message.content.strip().lower()

        # Life OS has its own ledger; do not mutate the legacy 550 XP state.
        if text.startswith("!done ") or text == "!done":
            quest_id = text.partition(" ")[2].strip()
            quest = ALL_QUEST_BY_ID.get(quest_id)
            if not quest:
                await message.reply("Usage: `!done <quest_id>` — e.g. `!done gym`.")
                return
            added = append_event(DATA_DIR / "lifeos-events.json", today_et(), quest_id, quest["xp"])
            await message.reply(
                f"Life OS: `{quest_id}` recorded (+{quest['xp']} XP). Import Discord events in Chronicle."
                if added else f"Life OS: `{quest_id}` already recorded today."
            )
            return

        # ── status ───────────────────────────────────────────────────
        if text in ("status", "s", "stats"):
            state = load_state()
            state, _ = maybe_reset(state)
            stats = get_day_stats(state)
            rank  = get_rank(state["total_xp"])
            bar   = progress_bar(len(stats["completed"]), stats["total"])
            mode  = "⚡ Weekend" if is_weekend() else "🗡️ Weekday"
            now_et = datetime.now(ET)

            rank_idx  = next((i for i, r in enumerate(RANKS) if r["name"] == rank["name"]), 0)
            next_rank = RANKS[rank_idx + 1] if rank_idx + 1 < len(RANKS) else None
            if next_rank:
                rank_str = (
                    f"{rank['emoji']} **{rank['name']}**\n"
                    f"{xp_bar(state['total_xp'])} → **{next_rank['name']}** in {next_rank['min_xp'] - state['total_xp']:,} XP"
                )
            else:
                rank_str = f"{rank['emoji']} **{rank['name']}**\n🏆 Maximum rank achieved."

            embed = discord.Embed(
                title="📊  SHADOW MONARCH STATUS",
                description=f"*{now_et.strftime('%A, %B %d, %Y')}*  —  {mode} Protocol",
                color=C_CYAN,
            )
            embed.add_field(name="Rank",     value=rank_str,                          inline=False)
            embed.add_field(name="Total XP", value=f"{state['total_xp']:,}",         inline=True)
            embed.add_field(name="Streak",   value=f"{state['streak_days']} 🔥 (best: {state['streak_best']})", inline=True)
            embed.add_field(
                name="Today's Progress",
                value=f"`{bar}` {len(stats['completed'])}/{stats['total']} ({stats['completion_pct']}%)\nXP today: **+{stats['xp_earned']}**",
                inline=False,
            )
            embed.set_thumbnail(url=AVATAR_URL)
            embed.set_footer(text="SYSTEM  •  Shadow Monarch Protocol")
            await message.channel.send(embed=embed)
            return

        # ── quests / quest list ──────────────────────────────────────
        if text in ("quests", "q", "quest", "list"):
            state = load_state()
            state, _ = maybe_reset(state)
            daily = get_daily_quests()
            STATUS_EMOJI = {"complete": "✅", "skipped": "⏭", "pending": "⏳"}
            lines = []
            for quest in daily:
                st = state["today"]["quests"].get(quest["id"], "pending")
                emoji = STATUS_EMOJI.get(st, "⏳")
                lines.append(f"{emoji} `{quest['id']}` — {quest['name']} (+{quest['xp']} XP)")
            chunks = [lines[i:i+15] for i in range(0, len(lines), 15)]
            for i, chunk in enumerate(chunks):
                embed = discord.Embed(
                    title="📋  QUEST REGISTRY" if i == 0 else "📋  QUESTS (cont.)",
                    description="\n".join(chunk),
                    color=C_PURPLE,
                )
                await message.channel.send(embed=embed)
            return

        # ── complete <quest_id> ──────────────────────────────────────
        if text.startswith("complete ") or text.startswith("done ") or text.startswith("c "):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                await message.reply("Usage: `complete <quest_id>`")
                return
            quest_id = parts[1].strip()
            state = load_state()
            state, _ = maybe_reset(state)

            if quest_id not in state["today"]["quests"]:
                await message.reply(f"❌ Quest `{quest_id}` not found today.")
                return
            if state["today"]["quests"][quest_id] == "complete":
                await message.reply(f"✅ `{quest_id}` is already complete.")
                return

            old_rank = get_rank(state["total_xp"])
            state["today"]["quests"][quest_id] = "complete"
            if quest_id in ALL_QUEST_BY_ID:
                state["total_xp"] += ALL_QUEST_BY_ID[quest_id]["xp"]
            new_rank = get_rank(state["total_xp"])
            state["rank"] = new_rank["name"]
            save_state(state)

            xp_gained = ALL_QUEST_BY_ID[quest_id]["xp"] if quest_id in ALL_QUEST_BY_ID else 0
            embed = discord.Embed(
                title="✅  QUEST COMPLETE",
                description=f"**{quest_id}** cleared!  **+{xp_gained} XP**\nTotal: **{state['total_xp']:,} XP** | {new_rank['emoji']} {new_rank['name']}",
                color=C_GREEN,
            )
            await message.channel.send(embed=embed)

            if new_rank["name"] != old_rank["name"]:
                await self.send_rank_up(state)
            return

        # ── checkin ───────────────────────────────────────────────────
        if text in ("checkin", "check-in", "check in", "form"):
            embed = discord.Embed(
                title="📋  WEEKLY SHADOW CHECK-IN",
                description="Click the button below to submit your report.",
                color=C_EMERGENCY,
            )
            await message.channel.send(embed=embed, view=CheckinPromptView(self))
            return

        # ── help ─────────────────────────────────────────────────────
        if text in ("help", "h", "commands"):
            embed = discord.Embed(
                title="⚔️  SHADOW MONARCH COMMANDS",
                description=(
                    "**Message commands** (type in chat):\n"
                    "`status` / `s` — View your rank & progress\n"
                    "`quests` / `q` — List today's quests\n"
                    "`complete <id>` / `c <id>` — Complete a quest\n"
                    "`checkin` — Open the weekly check-in form\n"
                    "`help` / `h` — This message\n\n"
                    "**Slash commands** also available:\n"
                    "`/status` `/quests` `/complete` `/checkin` `/streak` `/rank` `/reset` `/surprise`"
                ),
                color=C_PURPLE,
            )
            embed.set_footer(text="The System watches. Always.")
            await message.channel.send(embed=embed)
            return

    # ── helpers ───────────────────────────────────────────────────────────────

    async def quest_channel(self) -> discord.TextChannel | None:
        ch = self.get_channel(CHANNEL_ID)
        if ch is None:
            try:
                ch = await self.fetch_channel(CHANNEL_ID)
            except Exception:
                ch = None
        return ch

    async def send_rank_up(self, state: dict):
        ch = await self.quest_channel()
        if not ch:
            return
        rank  = get_rank(state["total_xp"])
        embed = discord.Embed(
            title=       "🏆  RANK UP!",
            description= f"You have ascended to **{rank['emoji']} {rank['name']}**!\n*The System acknowledges your growth.*",
            color=       C_GOLD,
        )
        embed.add_field(name="Total XP",      value=f"{state['total_xp']:,}",        inline=True)
        embed.add_field(name="Streak",        value=f"{state['streak_days']} 🔥",    inline=True)
        embed.set_image(url=AVATAR_URL)
        embed.set_footer(text="Arise. Your shadows grow stronger.")
        await ch.send(embed=embed)
        gif_url = RANK_UP_GIFS.get(rank["name"])
        if gif_url:
            await ch.send(gif_url)

    async def send_emergency_quest(
        self,
        title: str,
        description: str,
        xp: int,
        quest_id: str | None = None,
    ):
        ch = await self.quest_channel()
        if not ch:
            return
        if quest_id is None:
            quest_id = f"emergency_{int(datetime.now(ET).timestamp())}"
        embed = build_emergency_embed(title, description, xp)
        view  = EmergencyQuestView(quest_id, title, xp, self)
        await ch.send(embed=embed, view=view)

    # ── embeds ────────────────────────────────────────────────────────────────

    async def _send_arise(self):
        ch = await self.quest_channel()
        if not ch:
            return
        state         = load_state()
        rank          = get_rank(state["total_xp"])
        active_quests = get_daily_quests()
        xp_max        = get_daily_xp_max()
        weekend       = is_weekend()
        mode_label    = "⚡ Weekend Protocol" if weekend else "🗡️ Weekday Protocol"
        embed = discord.Embed(
            title=       "⚔️  ARISE",
            description= (
                "*A new day of trials begins, Shadow Monarch.*\n\n"
                "The Gate is open. The dungeon awaits. Will you answer the call?"
            ),
            color=C_PURPLE,
        )
        embed.add_field(name="Mode",            value=mode_label,                                inline=True)
        embed.add_field(name="Today's Quests",  value=f"{len(active_quests)} available",         inline=True)
        embed.add_field(name="Max XP",          value=f"{xp_max:,}",                             inline=True)
        embed.add_field(name="Current Rank",    value=f"{rank['emoji']} {rank['name']}",         inline=True)
        embed.add_field(name="Streak",          value=f"🔥 {state['streak_days']} days",         inline=True)
        if weekend:
            embed.add_field(
                name="Weekend Quests",
                value="No work block today — recovery, side hustle, social, meal prep",
                inline=False,
            )
        embed.set_thumbnail(url=AVATAR_URL)
        embed.set_footer(text="Use /quests to see all missions  •  /status for your stats")
        await ch.send(embed=embed)

    async def _send_quest(self, quest: dict):
        ch = await self.quest_channel()
        if not ch:
            return
        cat   = quest["category"]
        embed = discord.Embed(
            title=       f"{CAT_EMOJI.get(cat,'📌')}  {quest['title']}",
            description= f"{quest['description']}\n\n*{quest['flavor']}*",
            color=       C_PURPLE,
        )
        embed.add_field(name="Reward",   value=f"+{quest['xp']} XP",           inline=True)
        embed.add_field(name="Category", value=cat.title(),                     inline=True)
        embed.add_field(name="Block",    value=BLOCK_TITLE[quest["time_block"]], inline=True)
        embed.set_footer(text=f"Quest ID: {quest['id']}  •  /complete {quest['id']}")
        view = QuestView(quest["id"], self)
        await ch.send(embed=embed, view=view)

    async def _send_summary(self):
        ch = await self.quest_channel()
        if not ch:
            return
        state  = load_state()
        stats  = get_day_stats(state)
        rank   = get_rank(state["total_xp"])
        bar    = progress_bar(len(stats["completed"]), stats["total"])
        now_et = datetime.now(ET)

        embed = discord.Embed(
            title=       "🌙  DAILY DEBRIEF",
            description= f"*{now_et.strftime('%A, %B %d')} — Shadow Protocol Report*",
            color=       C_GOLD,
        )
        embed.add_field(
            name="Quest Completion",
            value=f"`{bar}` {len(stats['completed'])}/{stats['total']} ({stats['completion_pct']}%)",
            inline=False,
        )
        embed.add_field(name="XP Earned Today", value=f"+{stats['xp_earned']}",      inline=True)
        embed.add_field(name="Total XP",        value=f"{state['total_xp']:,}",       inline=True)
        embed.add_field(name="Rank",            value=f"{rank['emoji']} {rank['name']}", inline=True)
        streak_fire = "🔥" * min(state["streak_days"], 10)
        embed.add_field(name="Streak",          value=f"{streak_fire} {state['streak_days']} days", inline=True)

        if stats["completion_pct"] >= 80:
            verdict = "✅  **DUNGEON CLEARED** — Streak preserved. The shadows grow stronger."
        elif stats["completion_pct"] >= 50:
            verdict = "⚠️  **PARTIAL CLEAR** — Decent effort. Push harder tomorrow."
        else:
            verdict = "💀  **DUNGEON FAILED** — The shadows are disappointed. Rise tomorrow."
        embed.add_field(name="Verdict", value=verdict, inline=False)

        if stats["pending"]:
            items = [f"`{qid}`" for qid in stats["pending"][:6]]
            if len(stats["pending"]) > 6:
                items.append(f"…+{len(stats['pending'])-6} more")
            embed.add_field(name="⏳ Still Pending", value="  ".join(items), inline=False)

        embed.set_thumbnail(url=AVATAR_URL)
        embed.set_footer(text="Sleep quest still available for +200 XP.")
        await ch.send(embed=embed)

    async def _send_reset_notice(self, state: dict):
        ch = await self.quest_channel()
        if not ch:
            return
        rank  = get_rank(state["total_xp"])
        embed = discord.Embed(
            title=       "🔄  NEW DAY — PROTOCOL RESET",
            description= "Yesterday's trials are archived. A new dungeon has spawned.",
            color=       C_CYAN,
        )
        embed.add_field(name="Streak",    value=f"🔥 {state['streak_days']} days", inline=True)
        embed.add_field(name="Total XP",  value=f"{state['total_xp']:,}",           inline=True)
        embed.add_field(name="Rank",      value=f"{rank['emoji']} {rank['name']}",  inline=True)
        await ch.send(embed=embed)

    async def _check_overdue(self, now: datetime):
        """Warn if 3+ quests are 2+ hours past their scheduled time and still pending."""
        ch = await self.quest_channel()
        if not ch:
            return
        state         = load_state()
        active_quests = get_daily_quests()
        overdue = []
        for quest in active_quests:
            if state["today"]["quests"].get(quest["id"]) != "pending":
                continue
            qt = datetime.strptime(quest["notify_time"], "%H:%M").replace(
                year=now.year, month=now.month, day=now.day, tzinfo=ET
            )
            if now > qt + timedelta(hours=2):
                overdue.append(quest)

        if len(overdue) >= 3:
            names = "  ".join(f"**{q['title']}**" for q in overdue[:5])
            embed = discord.Embed(
                title=       "⚠️  PENALTY WARNING",
                description= f"**{len(overdue)} quests** are overdue! The shadow army grows restless.",
                color=       C_RED,
            )
            embed.add_field(name="Overdue", value=names or "—", inline=False)
            embed.set_footer(text="Complete them now or face the judgment of the shadows.")
            await ch.send(embed=embed)

    # ── scheduler ─────────────────────────────────────────────────────────────

    @tasks.loop(minutes=1)
    async def scheduler(self):
        now      = datetime.now(ET)
        hhmm     = now.strftime("%H:%M")
        date_str = now.strftime("%Y-%m-%d")

        # Helper: fire once per (key, date)
        def should_fire(key: str) -> bool:
            token = f"{key}_{date_str}"
            if token in self._fired:
                return False
            self._fired.add(token)
            return True

        # 5:00 AM — daily reset
        if hhmm == "05:00" and should_fire("reset"):
            state = load_state()
            state, did_reset = maybe_reset(state)
            if did_reset:
                await self._send_reset_notice(state)

        # 6:00 AM — arise message
        if hhmm == "06:00" and should_fire("arise"):
            await self._send_arise()

        # Quest reminders at their scheduled times (weekend-aware)
        active_quests = get_daily_quests()
        for quest in active_quests:
            if hhmm == quest["notify_time"] and should_fire(f"quest_{quest['id']}"):
                state = load_state()
                if state["today"]["quests"].get(quest["id"]) == "pending":
                    await self._send_quest(quest)

        # 10:00 PM — daily summary
        if hhmm == "22:00" and should_fire("summary"):
            await self._send_summary()

        # Sunday 8:00 PM — weekly check-in form
        if hhmm == "20:00" and now.weekday() == 6 and should_fire("weekly_checkin"):
            await self._send_checkin_prompt()

        # Sunday 9:00 PM — weekly summary auto-post
        if hhmm == "21:00" and now.weekday() == 6 and should_fire("weekly_auto"):
            await self._send_weekly_summary()

        # Weekdays — market brief for the watchlist
        if hhmm == MARKET_BRIEF_TIME and now.weekday() < 5 and should_fire("market_brief"):
            await self._send_market_brief()

        # Every 30 min — overdue penalty check
        if now.minute in (0, 30) and should_fire(f"overdue_{hhmm}"):
            await self._check_overdue(now)

    @scheduler.before_loop
    async def before_scheduler(self):
        await self.wait_until_ready()

    async def _send_market_brief(self):
        ch = await self.quest_channel()
        if not ch:
            return
        try:
            await ch.send(embed=await build_market_brief_embed())
        except Exception as e:
            log.error(f"Market brief failed: {e}")

    # ── weekly summary (auto-post + slash command helper) ─────────────────────

    async def _send_checkin_prompt(self):
        """Send the weekly check-in form prompt every Sunday at 8 PM."""
        ch = await self.quest_channel()
        if not ch:
            return
        embed = discord.Embed(
            title="📋  WEEKLY SHADOW CHECK-IN",
            description=(
                "*The System demands a report, Shadow Monarch.*\n\n"
                "Click the button below to submit your weekly check-in. "
                "Based on your answers, an **Emergency Quest** will be generated "
                "to test your resolve.\n\n"
                "**Honest answers = better quests.** The System knows when you lie."
            ),
            color=C_EMERGENCY,
        )
        embed.set_thumbnail(url=AVATAR_URL)
        embed.set_footer(text="Check-in closes when the next week begins.")
        await ch.send(embed=embed, view=CheckinPromptView(self))

    async def _send_weekly_summary(self):
        ch = await self.quest_channel()
        if not ch:
            return
        state    = load_state()
        state, _ = maybe_reset(state)
        embed    = _build_weekly_embed(state, week_offset=0, auto=True)
        await ch.send(embed=embed)


# ═════════════════════════════════════════════════════════════════════════════
# BOT INSTANCE  (must be created before decorating slash commands)
# ═════════════════════════════════════════════════════════════════════════════

bot = ShadowBot()


# ═════════════════════════════════════════════════════════════════════════════
# REPORT HELPERS  (used by /weekly, /monthly, and Sunday auto-post)
# ═════════════════════════════════════════════════════════════════════════════

def _get_week_range(offset: int = 0) -> tuple[str, str]:
    """Return (start, end) ISO dates for the week at offset (0=current, 1=last)."""
    today      = datetime.now(ET).date()
    week_start = today - timedelta(days=today.weekday() + 7 * offset)
    week_end   = week_start + timedelta(days=6)
    return week_start.isoformat(), week_end.isoformat()


def _slice_history(history: list, start: str, end: str) -> list:
    return [e for e in history if start <= e["date"] <= end]


def _aggregate(days: list) -> dict | None:
    if not days:
        return None
    total_quests = sum(d["completed"] for d in days)
    total_xp     = sum(d["xp_earned"] for d in days)
    avg_pct      = sum(d["completion_pct"] for d in days) / len(days)
    best         = max(days, key=lambda d: d["completion_pct"])
    worst        = min(days, key=lambda d: d["completion_pct"])
    cat_totals: dict[str, list] = {
        cat: [0, 0] for cat in ("discipline", "fitness", "nutrition", "focus")
    }
    for d in days:
        for cat, v in d.get("cat_stats", {}).items():
            if cat in cat_totals:
                cat_totals[cat][0] += v.get("done",  0)
                cat_totals[cat][1] += v.get("total", 0)
    cat_pcts = {
        cat: round(v[0] / v[1] * 100, 1) if v[1] > 0 else 0.0
        for cat, v in cat_totals.items()
    }
    return {
        "days":          days,
        "day_count":     len(days),
        "total_quests":  total_quests,
        "total_xp":      total_xp,
        "avg_pct":       round(avg_pct, 1),
        "best":          best,
        "worst":         worst,
        "cat_pcts":      cat_pcts,
    }


def _build_weekly_embed(state: dict, week_offset: int = 0, auto: bool = False) -> discord.Embed:
    start, end = _get_week_range(week_offset)
    curr_days  = _slice_history(state["history"], start, end)
    curr       = _aggregate(curr_days)

    # Previous week for comparison
    prev_start, prev_end = _get_week_range(week_offset + 1)
    prev = _aggregate(_slice_history(state["history"], prev_start, prev_end))

    title = "📅  WEEKLY SUMMARY" if auto else "📅  WEEKLY REPORT"
    embed = discord.Embed(
        title=       title,
        description= f"*Week of {start} → {end}*",
        color=       C_PURPLE,
    )

    if not curr:
        embed.description += "\n\nNo history recorded this week yet."
        return embed

    embed.add_field(
        name="This Week",
        value=(
            f"**{curr['total_quests']}** quests completed  •  "
            f"**{curr['total_xp']:,}** XP  •  "
            f"Avg **{curr['avg_pct']}%**"
        ),
        inline=False,
    )

    # Daily breakdown bar chart
    day_lines = []
    for d in curr["days"]:
        bar     = progress_bar(d["completed"], d["total"], 8)
        verdict = "✅" if d["completion_pct"] >= 80 else ("⚠️" if d["completion_pct"] >= 50 else "💀")
        day_lines.append(
            f"{verdict} `{d['date']}`  `{bar}`  {d['completion_pct']}%  +{d['xp_earned']} XP"
        )
    embed.add_field(name="Daily Breakdown", value="\n".join(day_lines) or "—", inline=False)

    embed.add_field(
        name="Best Day",
        value=f"`{curr['best']['date']}` — {curr['best']['completion_pct']}%",
        inline=True,
    )
    embed.add_field(
        name="Worst Day",
        value=f"`{curr['worst']['date']}` — {curr['worst']['completion_pct']}%",
        inline=True,
    )

    # Category breakdown
    cat_lines = []
    for cat, pct in curr["cat_pcts"].items():
        bar = progress_bar(int(pct), 100, 8)
        cat_lines.append(f"{CAT_EMOJI.get(cat,'📌')} **{cat.title()}**: `{bar}` {pct}%")
    embed.add_field(name="Category Breakdown", value="\n".join(cat_lines), inline=False)

    # Streak
    embed.add_field(
        name="Streak",
        value=f"🔥 **{state['streak_days']} days** (best: {state['streak_best']})",
        inline=True,
    )

    # vs last week comparison
    if prev:
        diff     = curr["total_xp"] - prev["total_xp"]
        diff_str = f"+{diff:,}" if diff >= 0 else f"{diff:,}"
        trend    = "📈" if diff > 0 else ("📉" if diff < 0 else "➡️")
        embed.add_field(
            name="vs Last Week",
            value=f"{trend} {diff_str} XP  (was {prev['total_xp']:,} XP, {prev['avg_pct']}% avg)",
            inline=True,
        )

    embed.set_thumbnail(url=AVATAR_URL)
    embed.set_footer(text=f"Rank: {state['rank']}  •  Shadow Monarch Protocol")
    return embed


def _build_monthly_embed(state: dict) -> discord.Embed:
    now_et     = datetime.now(ET)
    # current month: first day to today
    month_start = now_et.replace(day=1).strftime("%Y-%m-%d")
    month_end   = now_et.strftime("%Y-%m-%d")
    # previous month
    first_of_month = now_et.replace(day=1)
    prev_end_dt    = first_of_month - timedelta(days=1)
    prev_start     = prev_end_dt.replace(day=1).strftime("%Y-%m-%d")
    prev_end       = prev_end_dt.strftime("%Y-%m-%d")

    curr_days = _slice_history(state["history"], month_start, month_end)
    curr      = _aggregate(curr_days)
    prev      = _aggregate(_slice_history(state["history"], prev_start, prev_end))

    embed = discord.Embed(
        title=       "🗓️  MONTHLY REPORT",
        description= f"*{now_et.strftime('%B %Y')}*  ({month_start} → {month_end})",
        color=       C_GOLD,
    )

    if not curr:
        embed.description += "\n\nNo history recorded this month yet."
        return embed

    embed.add_field(
        name="Month Summary",
        value=(
            f"**{curr['day_count']}** days tracked  •  "
            f"**{curr['total_quests']}** quests  •  "
            f"**{curr['total_xp']:,}** XP  •  "
            f"Avg **{curr['avg_pct']}%**"
        ),
        inline=False,
    )

    # XP trend: last 4 weeks as a mini bar chart
    weeks_xp = []
    for w in range(3, -1, -1):
        ws, we = _get_week_range(w)
        wd     = _aggregate(_slice_history(state["history"], ws, we))
        if wd:
            weeks_xp.append((ws[:10], wd["total_xp"]))
    if weeks_xp:
        xp_max_week = max(x for _, x in weeks_xp) or 1
        trend_lines = []
        for label, xp in weeks_xp:
            bar = progress_bar(xp, xp_max_week, 10)
            trend_lines.append(f"`{label}`  `{bar}`  {xp:,} XP")
        embed.add_field(name="XP Trend (Weekly)", value="\n".join(trend_lines), inline=False)

    embed.add_field(
        name="Best Day",
        value=f"`{curr['best']['date']}` — {curr['best']['completion_pct']}%",
        inline=True,
    )
    embed.add_field(
        name="Worst Day",
        value=f"`{curr['worst']['date']}` — {curr['worst']['completion_pct']}%",
        inline=True,
    )

    # Longest streak within the month
    best_streak = 0
    cur_streak  = 0
    for d in sorted(curr_days, key=lambda x: x["date"]):
        if d["completion_pct"] >= 80:
            cur_streak  += 1
            best_streak  = max(best_streak, cur_streak)
        else:
            cur_streak = 0
    embed.add_field(name="Longest Streak (Month)", value=f"🔥 {best_streak} days", inline=True)

    # Category breakdown
    cat_lines = []
    for cat, pct in curr["cat_pcts"].items():
        bar = progress_bar(int(pct), 100, 8)
        cat_lines.append(f"{CAT_EMOJI.get(cat,'📌')} **{cat.title()}**: `{bar}` {pct}%")
    embed.add_field(name="Category Breakdown", value="\n".join(cat_lines), inline=False)

    # Rank progression
    rank = get_rank(state["total_xp"])
    embed.add_field(
        name="Rank",
        value=f"{rank['emoji']} **{rank['name']}**  —  {state['total_xp']:,} total XP",
        inline=True,
    )
    embed.add_field(
        name="Overall Streak",
        value=f"🔥 **{state['streak_days']} days** (best: {state['streak_best']})",
        inline=True,
    )

    # vs last month
    if prev:
        diff     = curr["total_xp"] - prev["total_xp"]
        diff_str = f"+{diff:,}" if diff >= 0 else f"{diff:,}"
        trend    = "📈" if diff > 0 else ("📉" if diff < 0 else "➡️")
        embed.add_field(
            name="vs Last Month",
            value=f"{trend} {diff_str} XP  (last month: {prev['total_xp']:,} XP, {prev['avg_pct']}% avg)",
            inline=False,
        )

    embed.set_thumbnail(url=AVATAR_URL)
    embed.set_footer(text=f"Rank: {state['rank']}  •  Shadow Monarch Protocol")
    return embed


# ═════════════════════════════════════════════════════════════════════════════
# SLASH COMMANDS
# ═════════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="status", description="Show your Shadow Monarch status for today")
async def cmd_status(interaction: discord.Interaction):
    await interaction.response.defer()
    state = load_state()
    state, _ = maybe_reset(state)
    stats     = get_day_stats(state)
    rank      = get_rank(state["total_xp"])
    now_et    = datetime.now(ET)

    # Rank progress line
    rank_idx  = next((i for i, r in enumerate(RANKS) if r["name"] == rank["name"]), 0)
    next_rank = RANKS[rank_idx + 1] if rank_idx + 1 < len(RANKS) else None
    if next_rank:
        needed   = next_rank["next_xp"] if next_rank["next_xp"] else next_rank["min_xp"]
        rank_str = (
            f"{rank['emoji']} **{rank['name']}**\n"
            f"{xp_bar(state['total_xp'])} → **{next_rank['name']}** in {next_rank['min_xp'] - state['total_xp']:,} XP"
        )
    else:
        rank_str = f"{rank['emoji']} **{rank['name']}**\n🏆 Maximum rank achieved."

    bar   = progress_bar(len(stats["completed"]), stats["total"])
    mode  = "⚡ Weekend" if is_weekend() else "🗡️ Weekday"
    embed = discord.Embed(
        title=       "📊  SHADOW MONARCH STATUS",
        description= f"*{now_et.strftime('%A, %B %d, %Y')}*  —  {mode} Protocol",
        color=       C_CYAN,
    )
    embed.add_field(name="Rank",     value=rank_str,                                              inline=False)
    embed.add_field(name="Total XP", value=f"{state['total_xp']:,}",                             inline=True)
    embed.add_field(
        name="Streak",
        value=f"{'🔥' * min(state['streak_days'], 10)} {state['streak_days']} days (best: {state['streak_best']})",
        inline=True,
    )
    embed.add_field(
        name="Today's Progress",
        value=(
            f"`{bar}` {len(stats['completed'])}/{stats['total']} ({stats['completion_pct']}%)\n"
            f"XP earned today: **+{stats['xp_earned']}**"
        ),
        inline=False,
    )
    if stats["completed"]:
        done_ids = "  ".join(f"`{qid}`" for qid in stats["completed"][:12])
        if len(stats["completed"]) > 12:
            done_ids += f"  +{len(stats['completed'])-12} more"
        embed.add_field(name=f"✅ Done ({len(stats['completed'])}/{stats['total']})", value=done_ids, inline=False)
    if stats["pending"]:
        pend_ids = "  ".join(f"`{qid}`" for qid in stats["pending"][:12])
        embed.add_field(name=f"⏳ Pending ({len(stats['pending'])})", value=pend_ids, inline=False)
    if stats["skipped"]:
        skip_ids = "  ".join(f"`{qid}`" for qid in stats["skipped"])
        embed.add_field(name=f"⏭ Skipped ({len(stats['skipped'])})", value=skip_ids, inline=False)

    embed.set_thumbnail(url=AVATAR_URL)
    embed.set_footer(text="SYSTEM  •  Shadow Monarch Protocol")
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="quests", description="View all quests and their current status")
@app_commands.describe(block="Filter by time block")
@app_commands.choices(block=[
    app_commands.Choice(name="All",                    value="all"),
    app_commands.Choice(name="Morning  (6–8 AM)",      value="morning"),
    app_commands.Choice(name="Work  (8:30 AM–5 PM)",   value="work"),
    app_commands.Choice(name="Evening  (5–11 PM)",     value="evening"),
])
async def cmd_quests(interaction: discord.Interaction, block: str = "all"):
    await interaction.response.defer()
    state      = load_state()
    state, _   = maybe_reset(state)
    filter_blk = None if block == "all" else block
    to_show    = [q for q in get_daily_quests() if filter_blk is None or q["time_block"] == filter_blk]

    STATUS_EMOJI = {"complete": "✅", "skipped": "⏭", "pending": "⏳"}

    mode  = "⚡ Weekend" if is_weekend() else "🗡️ Weekday"
    embed = discord.Embed(
        title=       "📋  QUEST REGISTRY",
        description= f"Filter: **{block.title()}**  —  {mode} Protocol",
        color=       C_PURPLE,
    )

    current_block = None
    lines: list[str] = []

    for quest in to_show:
        if quest["time_block"] != current_block:
            if lines and current_block:
                embed.add_field(
                    name=  BLOCK_TITLE[current_block],
                    value= "\n".join(lines),
                    inline=False,
                )
            current_block = quest["time_block"]
            lines = []
        status = state["today"]["quests"].get(quest["id"], "pending")
        s_e    = STATUS_EMOJI[status]
        c_e    = CAT_EMOJI.get(quest["category"], "📌")
        lines.append(f"{s_e} {c_e} **{quest['title']}** `+{quest['xp']} XP`  ·  `{quest['id']}`")

    if lines and current_block:
        embed.add_field(name=BLOCK_TITLE[current_block], value="\n".join(lines), inline=False)

    stats = get_day_stats(state)
    embed.set_footer(
        text=f"✅ {len(stats['completed'])}/{stats['total']} done  •  ⏳ {len(stats['pending'])} pending  •  ⏭ {len(stats['skipped'])} skipped"
    )
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="complete", description="Manually mark a quest as complete")
@app_commands.describe(quest_id="Quest ID to complete — e.g. gym, wake, water1, deep_work2, side_hustle")
async def cmd_complete(interaction: discord.Interaction, quest_id: str):
    quest = ALL_QUEST_BY_ID.get(quest_id.lower())
    if not quest:
        sample = "  ".join(f"`{q['id']}`" for q in get_daily_quests()[:8])
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"Quest `{quest_id}` not found.\nExample IDs: {sample} …",
                color=C_RED,
            ),
            ephemeral=True,
        )
        return

    await interaction.response.defer()
    state            = load_state()
    state, _         = maybe_reset(state)
    success, xp, rup = do_complete(state, quest_id.lower())

    if not success:
        await interaction.followup.send(
            embed=discord.Embed(
                description=f"**{quest['title']}** is already complete! ✅",
                color=C_CYAN,
            ),
            ephemeral=True,
        )
        return

    stats = get_day_stats(state)
    embed = discord.Embed(
        title=       "⚔️  QUEST COMPLETE",
        description= f"**{quest['title']}**\n*{quest['flavor']}*",
        color=       C_GREEN,
    )
    embed.add_field(name="XP Gained", value=f"+{xp} XP",                                             inline=True)
    embed.add_field(name="Total XP",  value=f"{state['total_xp']:,}",                                 inline=True)
    embed.add_field(name="Today",     value=f"{len(stats['completed'])}/{stats['total']} ({stats['completion_pct']}%)", inline=True)
    embed.set_thumbnail(url=AVATAR_URL)
    embed.set_footer(text=f"Rank: {state['rank']}  •  {state['streak_days']} 🔥 streak")
    await interaction.followup.send(embed=embed)

    if rup:
        await bot.send_rank_up(state)


@bot.tree.command(name="streak", description="View your streak history and consistency")
async def cmd_streak(interaction: discord.Interaction):
    await interaction.response.defer()
    state    = load_state()
    state, _ = maybe_reset(state)

    embed = discord.Embed(title="🔥  STREAK STATUS", color=C_GOLD)
    fire  = "🔥" * min(state["streak_days"], 20)
    embed.add_field(
        name="Current Streak",
        value=f"{fire}\n**{state['streak_days']} days**",
        inline=True,
    )
    embed.add_field(name="Best Streak", value=f"**{state['streak_best']} days**", inline=True)

    if state["history"]:
        recent = state["history"][-7:]
        lines  = []
        for day in reversed(recent):
            bar     = progress_bar(day["completed"], day["total"], 8)
            verdict = "✅" if day["completion_pct"] >= 80 else ("⚠️" if day["completion_pct"] >= 50 else "💀")
            lines.append(f"{verdict} `{day['date']}`  `{bar}`  {day['completion_pct']}%  (+{day['xp_earned']} XP)")
        embed.add_field(name="Last 7 Days", value="\n".join(lines), inline=False)

    embed.add_field(
        name="Streak Rule",
        value="Complete **80%+** of daily quests to maintain your streak.",
        inline=False,
    )
    embed.set_thumbnail(url=AVATAR_URL)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="rank", description="View your rank and XP ladder")
async def cmd_rank(interaction: discord.Interaction):
    await interaction.response.defer()
    state    = load_state()
    state, _ = maybe_reset(state)
    rank     = get_rank(state["total_xp"])

    embed = discord.Embed(
        title=       f"{rank['emoji']}  {rank['name']}",
        description= "*The System evaluates your worth.*",
        color=       C_GOLD,
    )
    embed.add_field(name="Total XP", value=f"{state['total_xp']:,}", inline=True)
    embed.add_field(name="Rank",     value=rank["name"],             inline=True)

    rank_lines = []
    for r in RANKS:
        marker   = "**→ **" if r["name"] == rank["name"] else "       "
        unlocked = "✅" if state["total_xp"] >= r["min_xp"] else "🔒"
        xp_req   = f"{r['min_xp']:,} XP"
        rank_lines.append(f"{unlocked} {marker}{r['emoji']} **{r['name']}** — {xp_req}")
    embed.add_field(name="Rank Ladder", value="\n".join(rank_lines), inline=False)

    if rank["next_xp"] is not None:
        needed = rank["next_xp"] - state["total_xp"]
        embed.add_field(
            name="Progress to Next Rank",
            value=f"{xp_bar(state['total_xp'])}\n**{needed:,} XP** remaining",
            inline=False,
        )
    else:
        embed.add_field(
            name="Status",
            value="🏆 **You have reached the pinnacle. You ARE the Shadow Monarch.**",
            inline=False,
        )

    embed.set_thumbnail(url=AVATAR_URL)
    embed.set_footer(text="Arise. The shadows await your command.")
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="weekly", description="View your weekly quest summary and stats")
@app_commands.describe(last_week="Set True to view last week instead of current week")
async def cmd_weekly(interaction: discord.Interaction, last_week: bool = False):
    await interaction.response.defer()
    state    = load_state()
    state, _ = maybe_reset(state)
    embed    = _build_weekly_embed(state, week_offset=1 if last_week else 0)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="monthly", description="View your monthly quest summary and stats")
async def cmd_monthly(interaction: discord.Interaction):
    await interaction.response.defer()
    state    = load_state()
    state, _ = maybe_reset(state)
    embed    = _build_monthly_embed(state)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="reset", description="[ADMIN] Reset today's quests for testing")
@app_commands.describe(confirm="Type RESET to confirm")
async def cmd_reset(interaction: discord.Interaction, confirm: str = ""):
    if confirm != "RESET":
        await interaction.response.send_message(
            embed=discord.Embed(
                description="Safety check: pass `confirm: RESET` to confirm.\n**This resets today's quests but keeps your total XP.**",
                color=C_RED,
            ),
            ephemeral=True,
        )
        return

    state          = load_state()
    state["today"] = _blank_today(today_et())
    save_state(state)
    bot._fired.clear()

    embed = discord.Embed(
        title=       "🔄  RESET COMPLETE",
        description= f"Today's quests reset to pending.\nTotal XP and rank **preserved**.",
        color=       C_CYAN,
    )
    embed.add_field(name="Quests",   value=f"{len(get_daily_quests())} set to pending", inline=True)
    embed.add_field(name="Total XP", value=f"{state['total_xp']:,}",        inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="surprise", description="[ADMIN] Issue an Emergency Quest to the channel")
@app_commands.describe(
    title="Emergency quest title",
    description="What must be done",
    xp="XP reward (default 100)",
)
async def cmd_surprise(
    interaction: discord.Interaction,
    title: str,
    description: str,
    xp: int = 100,
):
    await interaction.response.defer(ephemeral=True)
    await bot.send_emergency_quest(title, description, xp)
    await interaction.followup.send(
        embed=discord.Embed(
            description="⚠️ Emergency Quest issued to the channel.",
            color=C_EMERGENCY,
        ),
        ephemeral=True,
    )


@bot.tree.command(name="checkin", description="Open the weekly Shadow Check-In form")
async def cmd_checkin(interaction: discord.Interaction):
    await interaction.response.send_modal(WeeklyCheckinModal(bot))


@bot.tree.command(name="welcome", description="Resend the Architect's welcome message")
async def cmd_welcome(interaction: discord.Interaction):
    await interaction.response.send_message(embed=build_architect_embed())


@bot.tree.command(name="start", description="Accept the System's power and begin your daily quests")
async def cmd_start(interaction: discord.Interaction):
    embed = discord.Embed(
        title="THE SYSTEM AWAITS YOUR ANSWER",
        description="**[The quest cannot be refused.]**",
        color=C_ARCHITECT,
    )
    await interaction.response.send_message("https://media.tenor.com/HMlYHYdk2SMAAAAd/solo-leveling-statue-smile-solo-leveling.gif")
    await interaction.followup.send(embed=embed, view=StartView(bot))


def _fmt_price(v: float) -> str:
    return f"{v:,.2f}" if abs(v) >= 1 else f"{v:,.6f}"


def build_signal_embed(sig: dict) -> discord.Embed:
    emoji, color = BIAS_STYLE[sig["bias"]]
    arrow = "▲" if sig["change"] >= 0 else "▼"
    embed = discord.Embed(
        title=f"{emoji}  {sig['symbol']} — {sig['bias'].upper()}",
        description=(
            f"**{_fmt_price(sig['close'])} {sig['currency']}**  {arrow} {sig['change']:+,.2f} ({sig['change_pct']:+.2f}%)\n"
            f"*{sig['name']} · {sig['interval']} bars*"
        ),
        color=color,
    )
    embed.add_field(name="RSI 14", value=f"{sig['rsi14']:.1f}", inline=True)
    embed.add_field(name="SMA 20", value=_fmt_price(sig["sma20"]), inline=True)
    embed.add_field(name="SMA 50", value=_fmt_price(sig["sma50"]), inline=True)
    embed.add_field(name="Signals", value="\n".join(f"• {x}" for x in sig["signals"]), inline=False)
    bar_time = datetime.fromtimestamp(sig["last_bar"], ET).strftime("%b %d %I:%M %p ET")
    embed.set_footer(text=f"Yahoo Finance · last bar {bar_time} · trend context, not financial advice")
    return embed


async def build_market_brief_embed(symbols: list[str] | None = None) -> discord.Embed:
    symbols = symbols or MARKET_WATCHLIST
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*(get_signals(s, "daily", session) for s in symbols), return_exceptions=True)

    lines, counts = [], {"bullish": 0, "neutral": 0, "bearish": 0}
    for sym, r in zip(symbols, results):
        if isinstance(r, Exception):
            reason = str(r) if isinstance(r, MarketError) else "data unavailable"
            lines.append(f"⚪ **{sym.upper()}** — {reason}")
            continue
        counts[r["bias"]] += 1
        emoji, _ = BIAS_STYLE[r["bias"]]
        lines.append(
            f"{emoji} **{r['symbol']}** {_fmt_price(r['close'])} ({r['change_pct']:+.2f}%) · RSI {r['rsi14']:.0f}"
            + (f" · {r['signals'][0]}" if len(r["signals"]) > 1 else "")
        )
    color = C_GREEN if counts["bullish"] > counts["bearish"] else C_RED if counts["bearish"] > counts["bullish"] else C_GOLD
    embed = discord.Embed(
        title="📈  MARKET BRIEF",
        description="\n".join(lines),
        color=color,
    )
    embed.add_field(
        name="Board",
        value=f"🟢 {counts['bullish']} bullish · 🟡 {counts['neutral']} neutral · 🔴 {counts['bearish']} bearish",
        inline=False,
    )
    embed.set_footer(text=f"Daily bars · Yahoo Finance · {datetime.now(ET).strftime('%a %b %d')} · /signal <symbol> for detail")
    return embed


@bot.tree.command(name="signal", description="Trend read for a stock or crypto (e.g. NVDA, BTC-USD)")
@app_commands.describe(symbol="Ticker — stocks like NVDA, crypto like BTC-USD", interval="Bar size (default daily)")
@app_commands.choices(interval=[app_commands.Choice(name=i, value=i) for i in MARKET_INTERVALS])
async def cmd_signal(interaction: discord.Interaction, symbol: str, interval: str = "daily"):
    await interaction.response.defer()
    try:
        sig = await get_signals(symbol, interval)
    except MarketError as e:
        await interaction.followup.send(f"⚠️ {e}")
        return
    await interaction.followup.send(embed=build_signal_embed(sig))


@bot.tree.command(name="brief", description="Market brief for your watchlist (or a custom list)")
@app_commands.describe(symbols="Optional comma-separated list, e.g. AAPL,MSFT,BTC-USD")
async def cmd_brief(interaction: discord.Interaction, symbols: str = ""):
    await interaction.response.defer()
    custom = [s.strip() for s in symbols.split(",") if s.strip()][:10]
    await interaction.followup.send(embed=await build_market_brief_embed(custom or None))


# ═════════════════════════════════════════════════════════════════════════════
# DUAL TWO-WAY LISTENER — HTTP API (External ↔ Discord)
# ═════════════════════════════════════════════════════════════════════════════
# Direction 1: Discord → System  (handled by on_message / slash commands above)
# Direction 2: System → Discord  (handled by aiohttp web server below)
#
# Any external agent (Chakra, Gemini/Beru, Codex, quest_api, iOS app, dashboard)
# can POST to these endpoints to push messages/updates into Discord.
# ═════════════════════════════════════════════════════════════════════════════

API_PORT = int(os.getenv("API_PORT", 8080))

AGENT_COLORS = {
    "igris":  0x7C3AED,  # purple
    "chakra": 0x10B981,  # green
    "beru":   0x3B82F6,  # blue
    "codex":  0xFBBF24,  # gold
    "system": 0x06B6D4,  # cyan
}


async def api_health(request):
    """GET / — Health check for uptime monitors."""
    return web.json_response({
        "status": "online",
        "bot": str(bot.user) if bot.user else "connecting...",
        "rank": load_state().get("rank", "Unknown"),
        "total_xp": load_state().get("total_xp", 0),
    })


async def api_get_state(request):
    """GET /api/state — Return current shadow state."""
    state = load_state()
    return web.json_response(state)


async def api_post_message(request):
    """POST /api/message — Send a plain or embed message to Discord.
    Body: {
        "content": "plain text message",          # optional
        "agent": "chakra",                         # optional — wraps in agent-colored embed
        "title": "Directive Update",               # optional — embed title
        "description": "New sprint plan ready.",   # optional — embed body
        "fields": [{"name":"k","value":"v"}]       # optional — embed fields
    }
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)

    ch = bot.get_channel(CHANNEL_ID)
    if not ch:
        return web.json_response({"error": "channel not found"}, status=503)

    agent = data.get("agent", "system").lower()
    content = data.get("content")

    # If agent is specified, build an embed
    if data.get("title") or data.get("description"):
        color = AGENT_COLORS.get(agent, C_PURPLE)
        embed = discord.Embed(
            title=data.get("title", ""),
            description=data.get("description", ""),
            color=color,
            timestamp=datetime.now(ET),
        )
        embed.set_author(
            name=f"Agent {agent.title()}",
            icon_url=AVATAR_URL,
        )
        for field in data.get("fields", []):
            embed.add_field(
                name=field.get("name", ""),
                value=field.get("value", ""),
                inline=field.get("inline", True),
            )
        embed.set_footer(text=f"TWO-WAY LISTENER  •  via {agent.upper()}")
        await ch.send(content=content, embed=embed)
    elif content:
        await ch.send(content)
    else:
        return web.json_response({"error": "need 'content', 'title', or 'description'"}, status=400)

    log.info(f"[API] Message sent to Discord from agent={agent}")
    return web.json_response({"ok": True, "agent": agent})


async def api_agent_update(request):
    """POST /api/agent/update — Agent posts a structured status update.
    Body: {
        "agent": "chakra",
        "status": "active",
        "summary": "Expanded sprint to 5 questlines",
        "tasks_completed": ["Bridge system", "Codex prompt"],
        "next_actions": ["Deploy bot", "Scaffold iOS"],
        "message_for_monarch": "The shadows grow stronger."
    }
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)

    ch = bot.get_channel(CHANNEL_ID)
    if not ch:
        return web.json_response({"error": "channel not found"}, status=503)

    agent = data.get("agent", "unknown").lower()
    color = AGENT_COLORS.get(agent, C_PURPLE)

    embed = discord.Embed(
        title=f"⚡ AGENT UPDATE — {agent.upper()}",
        description=data.get("summary", "No summary provided."),
        color=color,
        timestamp=datetime.now(ET),
    )
    embed.set_author(name=f"Agent {agent.title()}", icon_url=AVATAR_URL)

    if data.get("tasks_completed"):
        completed = "\n".join(f"✅ {t}" for t in data["tasks_completed"])
        embed.add_field(name="Completed", value=completed, inline=False)

    if data.get("next_actions"):
        actions = "\n".join(f"➡️ {a}" for a in data["next_actions"])
        embed.add_field(name="Next Actions", value=actions, inline=False)

    if data.get("message_for_monarch"):
        embed.add_field(
            name="Message for the Monarch",
            value=f"*\"{data['message_for_monarch']}\"*",
            inline=False,
        )

    embed.add_field(name="Status", value=data.get("status", "unknown").upper(), inline=True)
    embed.set_footer(text="DUAL LISTENER  •  Agent Bridge Protocol")

    await ch.send(embed=embed)

    # Also log to agent_state/agent_activity_log.json
    _log_agent_activity(agent, data)

    log.info(f"[API] Agent update from {agent}: {data.get('summary', '')[:60]}")
    return web.json_response({"ok": True, "agent": agent})


async def api_quest_complete(request):
    """POST /api/quest/complete — Complete a quest via API and notify Discord.
    Body: { "quest_id": "gym", "source": "ios_app" }
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)

    quest_id = data.get("quest_id", "")
    source = data.get("source", "api")

    state = load_state()
    state, _ = maybe_reset(state)

    quests_today = state.get("today", {}).get("quests", {})
    if quest_id not in quests_today:
        return web.json_response({"error": f"unknown quest: {quest_id}"}, status=400)

    if quests_today[quest_id] == "complete":
        return web.json_response({"ok": True, "message": "already complete",
                                   "total_xp": state["total_xp"], "rank": state["rank"]})

    # Find quest XP from registry
    quest_meta = None
    for q in (QUESTS if not is_weekend() else WEEKEND_QUESTS):
        if q["id"] == quest_id:
            quest_meta = q
            break
    if not quest_meta:
        # Check surprise quests
        return web.json_response({"error": f"no metadata for quest: {quest_id}"}, status=400)

    xp_gained = quest_meta["xp"]
    state["today"]["quests"][quest_id] = "complete"
    state["total_xp"] = state.get("total_xp", 0) + xp_gained
    old_rank = state["rank"]
    state["rank"] = get_rank(state["total_xp"])["name"]
    save_state(state)

    # Notify Discord
    ch = bot.get_channel(CHANNEL_ID)
    if ch:
        embed = discord.Embed(
            title=f"⚔️ QUEST COMPLETE — {quest_meta['title']}",
            description=quest_meta["description"],
            color=C_GREEN,
            timestamp=datetime.now(ET),
        )
        embed.add_field(name="XP Gained", value=f"+{xp_gained}", inline=True)
        embed.add_field(name="Total XP", value=f"{state['total_xp']:,}", inline=True)
        embed.add_field(name="Rank", value=state["rank"], inline=True)
        embed.set_footer(text=f"Source: {source}  •  Two-Way Listener")
        await ch.send(embed=embed)

        # Check for rank up
        if state["rank"] != old_rank:
            rank_gif = RANK_UP_GIFS.get(state["rank"], "")
            await ch.send(f"🎉 **RANK UP!** → **{state['rank']}**\n{rank_gif}")

    log.info(f"[API] Quest complete: {quest_id} +{xp_gained}XP [source={source}]")
    return web.json_response({
        "ok": True,
        "quest": quest_id,
        "xp_gained": xp_gained,
        "total_xp": state["total_xp"],
        "rank": state["rank"],
    })


async def api_body_protocol(request):
    """POST /api/body/log — Log Shadow Body Protocol data and update XP.
    Body: {
        "day": 4,
        "grade": "B-",
        "intake_cal": 1470,
        "burn_cal": 3084,
        "protein_g": 102,
        "steps": 8100,
        "training": "Heavy arms + back + chest",
        "active_zone_min": 85
    }
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)

    # Calculate XP based on grade
    grade_xp = {"A+": 200, "A": 175, "A-": 150, "B+": 125, "B": 100, "B-": 75,
                "C+": 50, "C": 25, "C-": 10, "D": 0, "F": -50}
    grade = data.get("grade", "C")
    xp_earned = grade_xp.get(grade, 25)

    state = load_state()
    state["total_xp"] = state.get("total_xp", 0) + xp_earned
    state["rank"] = get_rank(state["total_xp"])["name"]
    save_state(state)

    # Notify Discord
    ch = bot.get_channel(CHANNEL_ID)
    if ch:
        protein_status = "✅" if data.get("protein_g", 0) >= 150 else "❌"
        embed = discord.Embed(
            title=f"🏋️ SHADOW BODY PROTOCOL — Day {data.get('day', '?')}",
            description=f"Grade: **{grade}** | XP: **+{xp_earned}**",
            color=C_GOLD,
            timestamp=datetime.now(ET),
        )
        embed.add_field(name="Intake", value=f"{data.get('intake_cal', '?')} cal", inline=True)
        embed.add_field(name="Burn", value=f"{data.get('burn_cal', '?')} cal", inline=True)
        embed.add_field(name="Protein", value=f"{data.get('protein_g', '?')}g {protein_status}", inline=True)
        embed.add_field(name="Steps", value=f"{data.get('steps', '?')}", inline=True)
        embed.add_field(name="Training", value=data.get("training", "Rest day"), inline=True)
        embed.add_field(name="AZM", value=f"{data.get('active_zone_min', 0)} min", inline=True)
        embed.set_footer(text="Shadow Body Protocol  •  Two-Way Listener")
        await ch.send(embed=embed)

    log.info(f"[API] Body protocol day {data.get('day')}: grade={grade} +{xp_earned}XP")
    return web.json_response({"ok": True, "xp_earned": xp_earned, "total_xp": state["total_xp"]})


def _log_agent_activity(agent: str, data: dict):
    """Append to agent_state/agent_activity_log.json."""
    log_file = BASE_DIR / "agent_state" / "agent_activity_log.json"
    try:
        entries = json.loads(log_file.read_text(encoding="utf-8")) if log_file.exists() else []
    except (json.JSONDecodeError, OSError):
        entries = []

    entries.append({
        "id": len(entries) + 1,
        "timestamp": datetime.now(ET).isoformat(),
        "agent": agent.title(),
        "platform": "Two-Way Listener API",
        "type": "update",
        "summary": data.get("summary", "No summary"),
        "related_files": [],
        "next_action": (data.get("next_actions") or [""])[0] if data.get("next_actions") else "",
    })

    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text(json.dumps(entries, indent=2), encoding="utf-8")


async def start_api_server():
    """Start the aiohttp web server for the two-way listener."""
    app = web.Application()
    app.router.add_get("/", api_health)
    app.router.add_get("/api/state", api_get_state)
    app.router.add_post("/api/message", api_post_message)
    app.router.add_post("/api/agent/update", api_agent_update)
    app.router.add_post("/api/quest/complete", api_quest_complete)
    app.router.add_post("/api/body/log", api_body_protocol)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", API_PORT)
    await site.start()
    log.info(f"[TWO-WAY LISTENER] HTTP API running on port {API_PORT}")
    log.info(f"  GET  /                    → Health check")
    log.info(f"  GET  /api/state           → Current shadow state")
    log.info(f"  POST /api/message         → Send message to Discord")
    log.info(f"  POST /api/agent/update    → Agent status update → Discord")
    log.info(f"  POST /api/quest/complete  → Complete quest + notify Discord")
    log.info(f"  POST /api/body/log        → Log body protocol + notify Discord")


# ═════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if not TOKEN:
        print("\nERROR: DISCORD_BOT_TOKEN is not set.")
        print("  Create a .env file with:  DISCORD_BOT_TOKEN=your_token_here")
        print("  See DISCORD_BOT_README.md for full setup instructions.\n")
        raise SystemExit(1)

    if not CHANNEL_ID:
        print("\nWARNING: DISCORD_CHANNEL_ID is not set.")
        print("  The bot will connect but won't post quest notifications.")
        print("  Add to your .env:  DISCORD_CHANNEL_ID=your_channel_id\n")

    # Hook the two-way listener into the bot's setup
    original_setup = bot.setup_hook

    async def enhanced_setup():
        await original_setup()
        await start_api_server()
        log.info("DUAL TWO-WAY LISTENER active — Discord ↔ HTTP API")

    bot.setup_hook = enhanced_setup

    log.info("Starting Shadow Monarch Protocol...")
    log.info(f"  Discord bot  →  listening for messages & slash commands")
    log.info(f"  HTTP API     →  port {API_PORT} (Two-Way Listener)")
    bot.run(TOKEN, log_handler=None)
