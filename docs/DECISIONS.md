# Decisions Log

## Architecture Decisions

### 2026-05-08: Local-first iOS MVP
- **Decision**: iOS Focus Remind App will be local-first with no cloud sync in MVP
- **Reason**: Reduces complexity, gets to S-Rank gate faster, cloud sync is a future sprint
- **Alternatives Considered**: Firebase, Supabase, custom API — all deferred

### 2026-05-08: UserNotifications for reminders
- **Decision**: Use Apple's UserNotifications framework for local reminders
- **Reason**: No server needed, works offline, native iOS experience
- **Copy Style**: System-alert themed (not generic reminder text)

### 2026-05-08: UserDefaults/Codable for persistence
- **Decision**: Use UserDefaults or Codable file persistence for MVP storage
- **Reason**: SwiftData is newer but adds unnecessary complexity for MVP
- **Migration Path**: Can move to SwiftData or Core Data later if needed

### 2026-05-08: GitHub repo as agent bridge
- **Decision**: Use GitHub repo with Markdown docs + JSON state files as the bridge between Chakra, Igris, Beru, and Codex
- **Reason**: All platforms can read/write to GitHub; no custom infrastructure needed for v1
- **Future**: GitHub Actions for validation, then webhooks + Cloudflare Worker for automation

### 2026-05-08: No copyrighted Solo Leveling assets
- **Decision**: The theme is Solo Leveling-inspired but uses NO copyrighted names, logos, or images
- **Reason**: Legal safety, app store compliance, portfolio-ready

### 2026-05-08: Render for Discord bot hosting
- **Decision**: Deploy Discord bot as a Render Background Worker
- **Reason**: Free tier available, supports Python workers, simple Docker deployment
- **Alternatives Considered**: Railway, Fly.io, AWS — Render won user vote

### 2026-05-08: System-style commit messages (Gemini)
- **Decision**: All commits use system-log format: `[SYSTEM UPDATE]`, `[QUEST COMPLETE]`, `[GATE PROGRESS]`, `[AGENT HANDOFF]`
- **Reason**: Maintains theme consistency, makes git log feel like game system logs
- **Source**: Gemini (Beru) recommendation

### 2026-05-08: Gemini as Research/Scout agent (Beru)
- **Decision**: Gemini's role is Research / Market / Content Scout — NOT strategy or coding
- **Reason**: Prevents overlap with Chakra (strategy) and Igris (engineering)
- **Capabilities**: Market research, workflow optimization suggestions, content scouting, competitive analysis

### 2026-05-08: Visual rank feedback in SwiftUI (Gemini)
- **Decision**: Implement a "Glitch" effect or Deep Purple/Blue gradient that intensifies as user nears S-Rank Gate
- **Reason**: Psychological "Creative Growth" feedback loop — the UI should feel alive
- **Source**: Gemini (Beru) recommendation
