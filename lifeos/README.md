# PRAT LIFE OS — Shadow Monarch Protocol

From sololevelingproject, install dependencies once with npm install, then run:

```powershell
npm start
```

Open http://localhost:3001. Equivalent boot command: node index.js. No build step.
Express serves lifeos at / and retains the existing API and iMessage routes. The Discord bot runs separately and is unchanged by this integration.

The 26 original timed quests load from data/quests.smp.json into a fresh Monarch profile. Names match App.jsx labels verbatim. Existing saved profiles are preserved; use Quests → Daily → Import Quests JSON to replace their daily quests.

Personal seed: profile/prat.json (git-ignored), fetched at boot. Provision this file privately on a personal deployment. Without it, the app opens Template mode. Do not publish the personal profile. Browser keys separate Monarch and Template profiles. Export before resetting or switching devices.

Discord bot legacy total: 550 XP, unreconciled

Original portrait and Igris GIF copied from C:/Users/Prat/PycharmProjects/j. Igris commit: 6c1eda6 (2026-03-27). No generated replacement.

Production push/deployment awaits Prat's approval. lifeos/render.yaml describes an optional Render static deployment; it does not modify the existing bot service.

## Verification

Run `node docs/test-lifeos.cjs` from the repository root. It checks the app state handlers for export/reset/import, reload, mode isolation, next-open-main orders, and the 26 source quests. It requires the local private seed.

Desktop browser: Level 26, 6,850/12,000, portrait, and no console errors verified. Template Summon and refresh verified at 390px phone viewport. Physical phone testing remains pending. Embedded-browser download events timed out, so the browser export/reset/import round-trip remains unverified; the state-handler round-trip passes.

The original nested j checkout remains in place and ignored. Its full Git history and working files are preserved under docs/legacy-j. The Windows-reserved nul file is preserved as docs/legacy-j/legacy-nul.txt.
