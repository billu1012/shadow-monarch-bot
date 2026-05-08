# Shadow Monarch Protocol — Project Context

## Overview
Shadow Monarch Protocol is Prat's Solo Leveling-inspired gamified habit tracker and personal operating system. It combines discipline tracking, AI-powered quest generation, and multi-agent collaboration into a unified ecosystem designed to push Prat toward mastery.

## Core System Components

### Discord Bot (Live)
- Built with discord.py 2.x
- 26 daily quests across fitness, nutrition, discipline, focus, and creative categories
- XP and rank progression from E-Rank through Shadow Monarch
- Weekly check-in forms (Discord Modals) that auto-generate emergency quests
- Plain-text message commands + slash commands
- State backup system to prevent data loss

### iOS Focus Remind App (S-Rank Gate)
- SwiftUI local-first app
- Create focus quests, schedule reminders, run focus sessions
- Awards local XP and tracks streaks
- S-Rank Gate screen showing unlock checklist
- **This is the gate to S-Rank. XP alone cannot unlock it.**

### React Dashboard (Planned)
- Shadow Command Center showing rank, XP, quest completion, streaks
- Agent activity log for Chakra / Igris / Gemini / Codex
- Portfolio-grade centerpiece

### Agent Bridge System (This Repo)
- docs/ — Human-readable project state and handoff protocols
- agent_state/ — Machine-readable JSON for automation
- GitHub repo is the single source of truth between all agents

## Current Major Gate
**S-Rank is LOCKED.**
To unlock S-Rank, Prat must complete and ship the iOS Focus Remind App MVP built in Swift/SwiftUI. XP alone cannot unlock S-Rank.

## Agent Roles

| Agent | Platform | Role |
|-------|----------|------|
| **Igris** | Claude/Anthropic | Engineering execution, debugging, refactoring, test execution, deployment |
| **Chakra** | ChatGPT | Strategy, UX, gamification, growth system, handoff design, creative direction |
| **Beru** | Google Gemini | Research, market intelligence, content scouting, workflow optimization |
| **Codex** | OpenAI Codex | Repo implementation, branch creation, code edits, automated handoff file updates |

## Agent Bridge Protocol (v1)
```
Chakra writes directive
  -> Codex/Igris implements and updates state files
  -> Igris reads repo and continues engineering
  -> Igris updates handoff files
  -> Prat brings summary back to Chakra
  -> Gemini (Beru) scouts research and optimizations in parallel
```

## Universal Handoff Prompt (Gemini's Recommendation)
When switching between agents, use this standard extraction prompt:
> "Igris, extract the latest directive from `agent_state/latest_chakra_directive.json` and initialize the build phase. Reference `docs/QUEST_BOARD.md` for priority."

## Commit Message Standards (Gemini's Recommendation)
All agents must write commit messages in system-log style:
```
[SYSTEM UPDATE] Implemented FocusSessionView; XP logic integrated.
[QUEST COMPLETE] Weekly check-in modal deployed to Discord bot.
[GATE PROGRESS] S-Rank Gate checklist updated — 3/6 conditions met.
[AGENT HANDOFF] Codex -> Igris: iOS scaffold ready for review.
```

## Current State
- **Rank**: D-Rank (inactivity penalty applied May 8, 2026)
- **XP**: 300
- **Active Sprint**: S-Rank Ecosystem Foundation
- **Bot Status**: Code ready, needs deployment to Render
- **iOS App**: Scaffold phase — not yet started
- **Dashboard**: React app exists but needs Command Center upgrade
