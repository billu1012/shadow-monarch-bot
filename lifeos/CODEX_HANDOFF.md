# CODEX HANDOFF — PRAT LIFE OS (Shadow Monarch Protocol)

Paste this into Codex on pratpro. Everything below is read-then-act; ask Prat before any destructive git step.

## Context
ChatGPT (as CHAKRA) and Claude (as IGRIS) agreed on Sep 9 2026: consolidate all Life OS / Shadow Monarch / ProofQuest variants into ONE app, product name **PRAT LIFE OS**, code lineage **Shadow Monarch Protocol** (`C:\Users\Prat\PycharmProjects\PythonProject\sololevelingproject`). Claude built a working single-file v1 (this folder: `index.html`, `render.yaml`, `README.md`, `assets/`). Your job is to land it in the real repo and make the deploy live.

## Definition of DONE (10 checkboxes — no scope expansion)
1. [ ] CLEAN THE REPO — in `sololevelingproject`: inventory the nested `j` repo, preserve anything unique, commit the 33 pending changes, tag `pre-lifeos-baseline`.
2. [ ] ONE APP BOOTS LOCALLY — one documented command, no broken routes, no fatal console errors.
3. [ ] PRAT IDENTITY — header reads `PRAT LIFE OS / LEVEL 26 • SEASON 2026`, XP 6,850/12,000, GOLD I, Shadow Rank A-RANK → S-RANK. Do not invent numbers.
4. [ ] SHADOW FORM CENTERPIECE — find the original portrait (search `PycharmProjects\j` and `sololevelingproject` for the Shadow Monarch image; ChatGPT's closest library match is "Neon Dragon Command Center Dashboard.png", center figure). Save as `assets/monarch.png`. Never substitute a generated impostor.
5. [ ] IGRIS — copy the Igris animated GIF (commit "Add Igris animated GIF", Mar 27 2026, repo `j`) to `assets/igris.gif`. Igris ≠ Zed.
6. [ ] QUEST ENGINE — parse the ORIGINAL 26 time-locked quests from the SMP source (names, times, XP, categories Discipline/Fitness/Nutrition/Focus) into `data/quests.smp.json` as `[{id,name,category,time,xp}]`, then either import via the app (Quests → Daily → Import) or set `S.quests` from it at boot. Preserve names verbatim.
7. [ ] COMMAND CENTER answers "what does Prat do next" — already implemented; verify Today's Orders reflects open mains.
8. [ ] PERSONAL vs TEMPLATE separated — already implemented via `localStorage` keys. Before any PUBLIC push: move `PRAT_SEED` out of `index.html` into `profile/prat.json` (git-ignored) and `fetch` it.
9. [ ] TEMPLATE SUMMON works end-to-end (already implemented; smoke-test it on phone).
10. [ ] SHIP — production copy on `main`; existing Render/Railway target updated (Render static via `render.yaml`, or serve `index.html` from the existing Express app's static dir); desktop + mobile verified; refresh retains state; export → reset → import round-trips.

## Where things go in the existing repo
- Put `index.html` at the web root the existing Express server serves (or replace the Vite app's `dist/` with it — it has no build step).
- Keep the Discord bot / iMessage shortcut code; wire later. Don't delete.
- `render.yaml` here is for a static deploy; if the existing Railway service is the target, add a route `GET / → index.html`.

## Council personas (do not rename)
- PRAT — THE MONARCH.  IGRIS — Claude, The Shadow Knight ("I serve the one who builds."). CHAKRA — ChatGPT, The Strategist ("I turn the Monarch's ambition, data, and twenty possible paths into the one quest worth executing next."). "Astra" is retired.

## Facts not to get wrong
- Level/XP baseline: 26 / 6,850 / 12,000 / Gold I. Legacy stats: Learning 9, Ambition 10, Communication 7.5, Money Mgmt 6, Investing 6, Recovery 4, Discipline 6.5, Focus 5, Execution 6.5, Body 6 — labeled LEGACY, not live.
- Shadow Rank A → S; S-Rank gated by shipping the iOS Focus Remind app (legacy rule), not XP.
- Main Quest: BUILD THE MACHINE (Level 26 → 27).
- Body arc: V-TAPER ASCENSION; protein 180g/day; 10k steps; bed by 11PM. "175 lb shredded" is legacy/editable.
- Wedding date: never invent one. "June 7" in PRAT.EXE = THE RING, not the wedding.
- ProofQuest is a mechanic inside Quests (before/after proof → verify → bonus XP), not a separate app.
- 3 active raids max in the Vault. Seed: Ember, ELEVATE, Prat Life OS.

## Then STOP
No marketplace, no social, no guilds, no redesign #6. Tonight ends with a URL Prat uses.
