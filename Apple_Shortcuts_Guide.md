# Shadow Monarch — Apple Shortcuts iMessage Integration

One-tap quest completion from your iPhone. Each shortcut fires at the quest's scheduled time, sends you a notification with a tappable link. Tap the link → Safari opens → quest is marked complete on your local API → the Solo Leveling confirmation page auto-closes in 3 seconds.

---

## Prerequisites

- `quest_api.py` must be running on your Mac: `python quest_api.py`
- Your iPhone and Mac must be on the **same Wi-Fi network**
- Find your Mac's local IP: **System Settings → Wi-Fi → Details → IP Address** (e.g. `192.168.1.42`)
- Base URL: `http://192.168.1.42:8765`

> **Tip:** Assign your Mac a static local IP in your router's DHCP settings so the URL never changes.

---

## Part 1: Create a Reusable "Complete Quest" Shortcut

This is the core shortcut. All quest shortcuts call this one.

1. Open **Shortcuts** app → tap **+** (New Shortcut)
2. Name it: `Shadow Complete Quest`
3. Add these actions in order:

| Step | Action | Setting |
|------|--------|---------|
| 1 | **Receive Input** | Type: Text, Input from: Shortcut Input |
| 2 | **URL** | `http://192.168.1.42:8765/api/complete/` |
| 3 | **Combine Text** | Combine: URL (step 2) + Shortcut Input |
| 4 | **Open URLs** | URL: Combined Text (step 3) |

4. Tap **Done**

> This shortcut takes a quest ID as input (e.g. `wake`) and opens the completion URL in Safari.

---

## Part 2: Create Individual Quest Shortcuts

For each quest below, create a shortcut that calls `Shadow Complete Quest` with the quest ID.

**Template for each quest:**

1. Open **Shortcuts** app → tap **+**
2. Name it: `✅ [Quest Title]` (e.g. `✅ Arise`)
3. Add action: **Run Shortcut** → select `Shadow Complete Quest`
4. Set Input: type the quest ID (e.g. `wake`)
5. Tap **Done**

### Weekday Quests

| Quest ID | Title | Time |
|----------|-------|------|
| `wake` | Arise | 6:00 AM |
| `activation` | Shadow Activation | 6:15 AM |
| `mana` | Mana Infusion | 6:30 AM |
| `outfit` | Don the Armor | 6:45 AM |
| `commute` | Shadow March | 7:30 AM |
| `dungeon_open` | Dungeon Gate: Open | 8:30 AM |
| `water1` | Hydration Protocol I | 9:30 AM |
| `stand1` | Movement Protocol I | 10:00 AM |
| `deep_work1` | Shadow Extraction I | 10:30 AM |
| `lunch` | Main Quest Meal | 12:00 PM |
| `water2` | Hydration Protocol II | 1:00 PM |
| `stand2` | Movement Protocol II | 2:00 PM |
| `deep_work2` | Shadow Extraction II | 2:30 PM |
| `water3` | Hydration Protocol III | 3:00 PM |
| `stand3` | Movement Protocol III | 3:30 PM |
| `deep_work3` | Shadow Extraction III | 4:00 PM |
| `dungeon_clear` | Dungeon Cleared | 5:00 PM |
| `commute_home` | Return March | 5:30 PM |
| `home` | Respawn Point | 6:00 PM |
| `pre_gym` | Boss Prep | 6:30 PM |
| `gym_warmup` | Shadow Warmup | 6:45 PM |
| `gym` | Shadow Raid | 7:00 PM |
| `recovery_meal` | Recovery Rations | 8:30 PM |
| `water4` | Hydration Protocol IV | 9:00 PM |
| `rest` | Rest Phase | 9:30 PM |
| `sleep` | Shadow Sleep | 11:00 PM |

### Weekend Quests

| Quest ID | Title | Time |
|----------|-------|------|
| `wake` | Arise | 8:00 AM |
| `activation` | Shadow Activation | 8:15 AM |
| `mana` | Mana Infusion | 8:30 AM |
| `outfit` | Don the Armor | 9:00 AM |
| `weekend_recovery` | Weekend Recovery Session | 10:00 AM |
| `side_hustle` | Side Hustle Focus | 11:00 AM |
| `social_connection` | Social Connection | 1:00 PM |
| `meal_prep` | Meal Prep | 3:00 PM |
| `pre_gym` | Boss Prep | 5:00 PM |
| `gym_warmup` | Shadow Warmup | 5:30 PM |
| `gym` | Shadow Raid | 6:30 PM |
| `recovery_meal` | Recovery Rations | 8:00 PM |
| `water4` | Hydration Protocol IV | 8:30 PM |
| `rest` | Rest Phase | 9:30 PM |
| `sleep` | Shadow Sleep | 11:00 PM |

---

## Part 3: Set Up Automation Triggers

Each automation fires at a quest's scheduled time and sends you a notification with a tappable link.

**Template for each quest automation:**

1. Open **Shortcuts** → tap **Automation** tab → tap **+** → **Personal Automation**
2. Choose **Time of Day** → set the time (e.g. 6:00 AM)
3. Set **Repeat**: Daily (or Weekdays / Weekends as appropriate)
4. Add action: **Show Notification**
   - Title: `⚔️ Shadow Quest`
   - Body: `[Quest description]` (e.g. `Wake up and get out of bed`)
   - Attachment / URL: `http://192.168.1.42:8765/api/complete/wake?source=imessage`
5. Add a second action: **Run Shortcut** → `✅ [Quest Name]` *(optional — auto-completes without tapping)*
6. Toggle **Ask Before Running** → **OFF**
7. Tap **Done**

> **Recommended:** Only add step 5 (auto-complete) for low-stakes quests like `stand1`, `water1`, etc. For high-value quests like `gym` (200 XP), keep it notification-only so you only get credit when you actually do it.

### Priority Automations to Set Up First

These have the highest XP and are most worth tracking:

| Quest | Time | XP | Days |
|-------|------|----|------|
| `wake` | 6:00 AM | 50 | Weekdays |
| `wake` | 8:00 AM | 50 | Weekends |
| `gym` | 7:00 PM | 200 | Weekdays |
| `gym` | 6:30 PM | 200 | Weekends |
| `sleep` | 11:00 PM | 200 | Daily |
| `deep_work1` | 10:30 AM | 100 | Weekdays |
| `deep_work2` | 2:30 PM | 100 | Weekdays |
| `deep_work3` | 4:00 PM | 100 | Weekdays |
| `side_hustle` | 11:00 AM | 150 | Weekends |

---

## Part 4: The Confirmation Page

When you tap a completion link, your iPhone opens Safari and shows:

```
⚔️
Shadow Monarch System
Quest Complete!
[Quest Title]
+[XP] XP
[Quest description]
Closing in 3s…
████████████░░  ← shrinking bar
```

The page auto-closes after 3 seconds. If Safari can't close the tab automatically (iOS restriction), it shows a "You may close this tab" message.

The page works fully in mobile Safari with:
- Dark background (#08080f)
- Purple glow border animation
- Large tap targets
- No scrolling needed on any iPhone screen size

---

## Troubleshooting

**"Safari cannot open the page"**
- Confirm `quest_api.py` is running: `python quest_api.py`
- Check your Mac's IP hasn't changed (router may reassign it)
- Both devices must be on the same Wi-Fi (not cellular)

**Quest shows "already logged"**
- That's fine — the XP display still shows the quest value, confirming which quest this was
- The green "Already logged" message appears instead of auto-completing again

**Shortcut won't run without prompting**
- Go to **Shortcuts → Automation → [your automation]** → toggle "Ask Before Running" OFF

**How to find your Mac's current IP quickly:**
```bash
ipconfig getifaddr en0
```
Run this in Terminal on your Mac.
