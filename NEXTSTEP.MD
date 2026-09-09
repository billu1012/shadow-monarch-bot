# Claude Code Prompt — Shadow Monarch OS Rebuild

## Give this to Claude Code in your terminal:

---

Rebuild the Shadow Monarch OS dashboard (`/j` repo) as a proper multi-file Vite + React 18 app with the following requirements:

### Design Language — Solo Leveling Aesthetic
- **Color palette**: Deep blacks (#0a0a12, #0d0d1a), electric purples (#7B2FF2, #9D4EDD), neon cyan (#00D4FF), blood red accents (#FF2D55), gold for XP (#FFD700)
- **Typography**: Use "Rajdhani" (from Google Fonts) for headings — it has that angular, hunter-gate aesthetic. Use "Inter" for body text at 13-14px
- **Background**: Full dark theme. Subtle animated particle system in the background (tiny purple dots drifting upward slowly, like the Shadow Monarch's aura). Use CSS only, no canvas — use multiple `box-shadow` on pseudo-elements with `@keyframes float`
- **Cards**: Glassmorphism — `background: rgba(15, 15, 30, 0.7)`, `backdrop-filter: blur(12px)`, thin 1px border with `rgba(123, 47, 242, 0.3)`, subtle purple glow on hover
- **Transitions**: All state changes should have smooth 200ms transitions. Tab switches use a fade + slight slide
- **The Hunter Avatar**: Animated with a purple pulsing aura ring around it using CSS `box-shadow` animation
- **Progress bars**: Neon gradient fills (purple → cyan), with a subtle shimmer animation moving left to right
- **Rank badges**: Styled like Solo Leveling rank gates — E-Rank is gray, D is green, C is blue, B is purple, A is gold, S is crimson with glow

### Architecture — Multi-file, Clean
```
src/
  App.jsx              # Router + layout shell + tab navigation
  components/
    HunterAvatar.jsx   # Animated avatar with aura
    TabBar.jsx         # Bottom navigation (8 tabs)
    XPBar.jsx          # Level progress bar
    RankBadge.jsx      # Current rank display
    QuestCard.jsx      # Individual quest with complete toggle
    MissionCard.jsx    # Mission card with progress
    MacroRing.jsx      # Circular macro visualization (protein/carbs/fat)
    WorkoutLogger.jsx  # Exercise logging
    FastingTimer.jsx   # IF timer with countdown
    EODReflection.jsx  # End of day form
    ShadowArmy.jsx     # Shadow soldier collection display
  pages/
    Home.jsx           # Dashboard overview — XP, rank, streaks, motivational quote
    CheckIn.jsx        # Morning check-in flow
    Quests.jsx         # Daily auto-generated quests
    Missions.jsx       # Long-term mission gallery
    Train.jsx          # Workout logging + V-Taper split
    Fuel.jsx           # Macro tracking + fasting timer
    Body.jsx           # Body stats, measurements, weekly goals
    EOD.jsx            # End of day reflection
  hooks/
    useLocalStorage.js # Generic localStorage hook with JSON serialization
    useQuests.js       # Quest generation, completion, XP reward logic
    useXP.js           # XP tracking, level calculation, rank thresholds
    useFasting.js      # Fasting timer state management
  data/
    quotes.js          # Motivational quotes array (SJW, Drake, Luffy, etc.)
    ranks.js           # Rank thresholds and names
    workouts.js        # V-Taper workout split definitions
  styles/
    global.css         # CSS variables, animations, particle background
  utils/
    xp.js              # XP math, level-up thresholds
    date.js            # Date formatting helpers
```

### Data Persistence
- All state persists to `localStorage` with a unified key structure: `smp_quests`, `smp_xp`, `smp_macros`, `smp_workouts`, `smp_checkin`, `smp_fasting`, `smp_army`, `smp_eod`
- ALSO expose a `window.SMP_API` global object that external integrations can call:
  ```js
  window.SMP_API = {
    completeQuest: (questId) => { ... },
    addXP: (amount, source) => { ... },
    logMeal: (meal) => { ... },
    logWorkout: (workout) => { ... },
    getState: () => { ... }, // returns full serialized state
    setState: (newState) => { ... }, // merges incoming state
    exportJSON: () => { ... }, // downloads state as JSON
    importJSON: (json) => { ... } // imports state from JSON
  }
  ```
  This API is the bridge — external tools (Claude chat, Discord bot, iOS Shortcuts, Google Calendar) will push data through this interface.

### PWA Requirements
- Include `manifest.json` for Add to Home Screen (standalone display mode)
- App icon should be a purple lightning bolt on dark background
- Meta viewport for mobile: `width=device-width, initial-scale=1, viewport-fit=cover`
- Safe area insets for iPhone notch: `env(safe-area-inset-top)` etc.

### Deployment
- GitHub Pages via `gh-pages` branch
- `vite.config.js` with `base: '/j/'`
- Build output to `dist/`

### Key Interactions
1. **Tab navigation**: Fixed bottom bar, 8 tabs with icons (use Unicode symbols, no icon library needed). Active tab has purple glow underline
2. **Quest completion**: Tap a quest → it glows, XP animates upward (+25 XP floating text), quest card fades to completed state
3. **Fasting timer**: Big circular countdown, tap to start/stop, shows elapsed time and target
4. **Macro rings**: Three concentric rings (protein inner, carbs middle, fat outer) that fill as you log meals
5. **Shadow Army**: Grid of shadow soldier silhouettes that unlock as you hit milestones — starts empty, fills up

Make it feel like you're opening a System Window from Solo Leveling — every card should have that "floating holographic panel in a dark dungeon" energy.

---
