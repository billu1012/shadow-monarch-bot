# ⚔️ Shadow Monarch OS v3

Solo Leveling-themed daily quest operating system with iMessage integration.

## How It Works

- **26 daily quests** unlock at real times throughout your day
- **iMessage automations** send you quest reminders on iPhone + Mac
- **One-tap completion** — tap a link in the message → quest marked done
- **Live dashboard** syncs every 30s — tracks XP, rank, streaks, categories
- **Backend API** persists your progress across devices

## Architecture

```
iPhone Shortcuts (26 automations)
  → Sends iMessage at quest time
  → Message contains /tap/{questId} URL
  → You tap link
  → Express server marks quest complete
  → Dashboard polls /api/status every 30s
  → XP animation + progress update
```

## Tech Stack

- **Frontend**: React 18 + Vite (PWA)
- **Backend**: Express.js + node-cron
- **Hosting**: Railway
- **Data**: JSON file persistence (with Railway Volume)
- **Notifications**: Apple Shortcuts → iMessage

## Deploy to Railway

1. Push to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Railway reads `nixpacks.toml` → builds frontend → starts server
4. Add Volume: Settings → Volumes → mount at `/app/data`
5. Get your URL and set up iMessage automations (see `IMESSAGE_SETUP.txt`)

## Local Development

```bash
npm install
npm run dev          # Frontend on :5173
node server/index.js # Backend on :3001
```

## API

| Endpoint | Method | Description |
|---|---|---|
| `/tap/:questId` | GET | One-tap quest completion (redirects to dashboard) |
| `/api/complete` | POST | Mark quest complete `{ questId, date }` |
| `/api/status/:date` | GET | Get day's completion data |
| `/api/weekly` | GET | Get last 7 days of data |
| `/api/health` | GET | Server health check |

## Rank System

| Rank | XP Required |
|---|---|
| E-Rank Hunter | 0 |
| D-Rank Hunter | 500 |
| C-Rank Hunter | 1,500 |
| B-Rank Hunter | 3,000 |
| A-Rank Hunter | 6,000 |
| S-Rank Hunter | 10,000 |
| National Level | 20,000 |
| Shadow Monarch | 50,000 |
