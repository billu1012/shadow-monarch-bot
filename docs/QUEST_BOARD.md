# Quest Board

## Active Quests

### Questline 1: iOS Focus Remind App MVP (S-Rank Gate)
- [ ] Create SwiftUI app scaffold (Models, Stores, Views)
- [ ] Implement FocusQuest model with title, duration, reminder time
- [ ] Build CreateFocusQuestView screen
- [ ] Implement local persistence (UserDefaults/Codable)
- [ ] Add UserNotifications with system-alert copy
- [ ] Build FocusSessionView with countdown timer
- [ ] Implement XP award on session completion
- [ ] Build SRankGateView with checklist
- [ ] Add visual rank feedback (Glitch effect / gradient — Gemini spec)
- [ ] Commit MVP to repo
- [ ] Record demo / capture screenshots

### Questline 2: Discord Bot Deployment + Stability
- [ ] Push bot code to GitHub (billu1012/shadow-monarch-bot)
- [ ] Connect repo to Render
- [ ] Configure env vars (DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID)
- [ ] Deploy and verify bot is running 24/7
- [ ] Test weekly check-in form in production
- [ ] Test emergency quest generation
- [ ] Verify state backup system works on Render

### Questline 3: Agent Bridge System
- [x] Create docs/PROJECT_CONTEXT.md
- [x] Create docs/AGENT_HANDOFF.md
- [x] Create docs/S_RANK_GATE.md
- [x] Create docs/QUEST_BOARD.md
- [x] Create docs/DECISIONS.md
- [x] Create agent_state/shadow_state.json
- [x] Create agent_state/latest_chakra_directive.json
- [x] Create agent_state/latest_igris_update.json
- [ ] Add .github/workflows/agent-handoff.yml (optional CI validation)
- [ ] Test handoff cycle: Chakra -> Igris -> Chakra

### Questline 4: Shadow Command Center Dashboard (Chakra Proposal)
- [ ] Define React component architecture
- [ ] Build Overview panel (rank, XP, streak, quest completion rate)
- [ ] Build S-Rank Gate progress widget
- [ ] Build agent activity log (Chakra / Igris / Gemini / Codex)
- [ ] Build emergency quest tracker
- [ ] Connect to Discord bot API (quest_api.py)

## Backlog
- Power BI automation toolkit for Woodmont Properties (BI work leverage)
- Shadow Monarch Protocol public template / open-source version
- Weekly AI intelligence briefing automation
- Gamified CRE property analysis tool
- Discord bot <-> iOS app sync via API
- Authentication and multi-user support
- Monetization: Productivity SaaS based on Shadow Monarch system

## Completed
- [x] Discord bot core implementation (26 quests, XP, ranks)
- [x] Weekly check-in modal with emergency quest generation
- [x] State backup system
- [x] Plain-text message handler
- [x] Render deployment files (Dockerfile, render.yaml, Procfile)
- [x] Agent bridge documentation

## Blocked
- iOS app scaffold — blocked by: need Xcode (Mac required) or Codex to generate scaffold
- Render deployment — blocked by: code not yet pushed to GitHub
- Codex task — blocked by: repo must have code pushed first
