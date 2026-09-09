# ⚔️ Shadow Monarch Discord Bot

A full interactive Discord bot for the **Shadow Monarch Protocol** — Solo Leveling themed daily quest & habit tracker. Uses Discord slash commands and interactive buttons.

---

## One-Time Setup

### Step 1 — Create a Discord Application & Bot

1. Go to **https://discord.com/developers/applications**
2. Click **New Application** → name it `Shadow Monarch` (or anything you like)
3. In the left sidebar, click **Bot**
4. Click **Reset Token** → copy the token (you'll only see it once)
5. Under **Privileged Gateway Intents**, enable:
   - ✅ **Message Content Intent**
   - ✅ **Server Members Intent** (optional but harmless)
6. Click **Save Changes**

### Step 2 — Invite the Bot to Your Server

1. In the left sidebar, click **OAuth2 → URL Generator**
2. Under **Scopes**, check: `bot` and `applications.commands`
3. Under **Bot Permissions**, check:
   - `Send Messages`
   - `Embed Links`
   - `Read Message History`
   - `Use Slash Commands`
4. Copy the generated URL and open it in your browser
5. Select your server and click **Authorize**

### Step 3 — Get Your Channel ID

1. In Discord, go to **User Settings → Advanced** and enable **Developer Mode**
2. Right-click the text channel where you want quests to appear
3. Click **Copy Channel ID**

### Step 4 — Configure the Bot

```bash
# In the sololevelingproject folder:
cp .env.example .env
```

Edit `.env` and fill in your values:

```
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_CHANNEL_ID=your_channel_id_here
```

### Step 5 — Install Dependencies

```bash
pip install -r requirements_discord.txt
```

### Step 6 — Run the Bot

```bash
python shadow_monarch_bot.py
```

You should see:
```
HH:MM:SS  [INFO]  SYSTEM online  ·  Shadow Monarch#1234  (ID: ...)
HH:MM:SS  [INFO]  Quest channel : 123456789
```

---

## Features

### Auto-Posted Quest Notifications

The bot posts each quest to your channel at its scheduled time with **Complete** and **Skip** buttons:

| Button | Effect |
|--------|--------|
| ✅ Complete | Marks quest done, awards XP, shows progress embed |
| ⏭ Skip | Marks as skipped, no XP penalty |

### Scheduled Messages (Eastern Time)

| Time | Event |
|------|-------|
| 5:00 AM | Daily reset — archives yesterday, resets today |
| 6:00 AM | **ARISE** — morning kick-off embed |
| 6:00–11:00 PM | Quest reminders at each quest's scheduled time |
| 10:00 PM | Daily debrief / summary |
| Every 30 min | Penalty warning if 3+ quests are 2+ hours overdue |

### Slash Commands

| Command | Description |
|---------|-------------|
| `/status` | Current day progress, XP, rank, streak |
| `/quests [block]` | All quests with status — filter by morning/work/evening |
| `/complete <quest_id>` | Manually complete a quest by ID |
| `/streak` | Streak history with last 7 days breakdown |
| `/rank` | Full rank ladder with your current position |
| `/reset confirm:RESET` | Admin — reset today's quests (keeps total XP) |

### Quest IDs (for `/complete`)

```
Morning:  wake  activation  mana  outfit  commute
Work:     dungeon_open  water1  stand1  deep_work1  lunch
          water2  stand2  deep_work2  water3  stand3  deep_work3  dungeon_clear
Evening:  commute_home  home  pre_gym  gym_warmup  gym
          recovery_meal  water4  rest  sleep
```

### XP & Rank System

| Rank | XP Required |
|------|-------------|
| ⬜ E-Rank | 0 |
| 🟩 D-Rank | 200 |
| 🟦 C-Rank | 500 |
| 🟧 B-Rank | 1,000 |
| 🟥 A-Rank | 1,800 |
| 🟨 S-Rank | 2,800 |
| 💜 National Level | 4,000 |
| 🖤 Shadow Monarch | 6,000 |

Max daily XP: **1,555** (completing all 26 quests)

**Streak rule:** Complete 80%+ of daily quests to extend your streak. Falls to 0 if you miss a day.

---

## Data Files

| File | Purpose |
|------|---------|
| `data/shadow_state.json` | Bot's primary state — XP, rank, streak, history |
| `data/YYYY-MM-DD.json` | Daily files synced for the React dashboard |

The bot keeps the legacy `YYYY-MM-DD.json` files updated so your existing **Solo Leveling dashboard** (`node index.js`) continues to work alongside the bot.

---

## Running Continuously

To keep the bot running in the background on Windows:

**Option A — Simple (PowerShell):**
```powershell
Start-Process python -ArgumentList "shadow_monarch_bot.py" -WindowStyle Hidden
```

**Option B — As a Windows Service:**
Use [NSSM](https://nssm.cc/) (Non-Sucking Service Manager):
```
nssm install ShadowMonarch python C:\path\to\shadow_monarch_bot.py
nssm start ShadowMonarch
```

**Option C — Railway / Cloud:**
Add a `Procfile`:
```
worker: python shadow_monarch_bot.py
```
Then deploy to Railway, Fly.io, or any VPS. The bot uses Eastern Time by default — change `ET = ZoneInfo("America/New_York")` at the top of the file if needed.

---

## Troubleshooting

**"Missing Access" / bot not posting**
→ Re-invite the bot using the OAuth2 URL Generator. Make sure `Send Messages` and `Embed Links` permissions are checked.

**Slash commands not showing up**
→ It can take up to an hour for Discord to propagate global slash commands. For instant sync during development, pass your guild (server) ID to `tree.sync(guild=...)`.

**Bot posts but buttons don't respond**
→ Ensure `Message Content Intent` is enabled in the Developer Portal under Bot → Privileged Gateway Intents.

**Wrong timezone**
→ Change `ET = ZoneInfo("America/New_York")` at the top of `shadow_monarch_bot.py` to your timezone string (e.g. `"America/Los_Angeles"`, `"Europe/London"`).
