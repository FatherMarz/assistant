---
name: onboard-assistant
description: "Interactive onboarding to turn this template into a personalized AI executive assistant. Walks the user through naming, profile, priorities, integrations, and scheduled tasks. Use when a new user opens this repo for the first time, says 'onboard me', 'set up my assistant', 'let's get started', or invokes /onboard-assistant."
---

# Onboarding — Assistant Template

When this skill is invoked, walk the user through a conversational onboarding that turns this template repo into their personal assistant. The end state is:

- `config/SOUL.md` and `config/USER.md` filled in with their identity
- `skills/<their-assistant-name>/` installed at `~/.claude/skills/<name>/`
- `skills/<their-assistant-name>-vault/` installed at `~/.claude/skills/<name>-vault/`
- `scripts/scheduled/manifest.yaml` updated with the tasks they enabled
- `.env` created with their integration creds
- Scheduler (launchd or cron) installed for the enabled tasks

**Before you start**: read `README.md` at the repo root so you understand the moving parts. Read `skills/assistant-template/SKILL.md` and `skills/assistant-vault-template/SKILL.md` to see what placeholders exist.

## The flow

Work through these sections in order. After each answer, briefly acknowledge what you captured (one sentence) and move on — don't recap paragraphs. Stage all answers in a JSON file at `/tmp/assistant-onboarding.json` as you go, so you can resume if interrupted. At the end, run `scripts/setup.py` with that file.

Pacing: this should take ~10 minutes. Be efficient. Don't ask for anything you don't need.

---

### Section 1 — Core Identity

1. "What's your name?" → `USER_NAME`
2. "What should I call your assistant? You can pick any name — a fantasy name gives it personality (e.g., Welendathas, Faelwen, Morrigan, Caerwyn, Thistle). Or something simple (Ava, Ren, Sable). Your call."
   → `ASSISTANT_NAME`
   - Derive `ASSISTANT_NAME_SLUG` = lowercase, hyphenated (e.g., "Welendathas" → `welendathas`)
3. "Your pronouns? (he/him, she/her, they/them)" → set `PRONOUN_SUBJ`, `PRONOUN_OBJ`, `PRONOUN_POSS`, `PRONOUN_REFL` accordingly

### Section 2 — People

4. "Who are the most important people in your life that you'd want me to know about? Partner, kids, close friends, key colleagues — whoever shapes your day. Give me names and a one-line description of each. Type 'done' when finished."
   → Collect into `PEOPLE` list: `[{name, relationship, notes}, ...]`
   - Specifically confirm: "Do you have a partner (spouse, life partner) you'd want me to help you stay connected with? If yes, what's their name?" → `PARTNER_NAME` (or `null`)

### Section 3 — Work

5. "What's your role? (e.g., 'Software Engineer', 'Founder', 'Teacher')" → `USER_ROLE`
6. "Company or employer?" → `USER_EMPLOYER`
7. "Timezone? (e.g., `America/New_York`, `America/Edmonton`, `Europe/London`)" → `TIMEZONE`
8. "Work hours? (e.g., '9am–5pm weekdays')" → `WORK_HOURS`
9. "Main tools / stacks / systems you use daily?" → `USER_TOOLS`

### Section 4 — Priorities

10. "Stack-rank your top priorities, highest first. 3 or 4 is ideal. Examples: 'family', 'health', 'my startup', 'writing'."
    → `PRIORITIES` as an ordered list

11. "Do you have an off-hours rule? Something like 'after 6pm and weekends = family time, flag work bleeding in'. This lets me call out drift. Skip if you don't want one."
    → `OFF_HOURS_RULE` (or `null`)

### Section 5 — Communication Style

12. "How do you want me to talk to you? Pick any that apply:
    - Direct and concise, hates walls of text
    - Bullet points over paragraphs
    - Offers to DO things, not just report
    - Proactive context, but never dumps raw messages
    - Other (describe)"
    → `COMMS_STYLE`

13. "Briefing style preference? e.g., 'only action items, ask about each one instead of dumping everything', or 'summary + full list'."
    → `BRIEFING_STYLE`

### Section 6 — Ticketing (optional)

14. "Do you use a ticketing system for work? (Jira / Linear / GitHub Issues / None)"
    → `TICKETING_SYSTEM` — if not None, note it; we won't wire a live sync in v1 but we'll leave a stub for it later

### Section 7 — Integrations

For each integration, briefly describe what it enables and ask yes/no. If yes, note it (setup.py will write `.env` keys for them; the user fills in secrets themselves after).

15. **Pushover** — push notifications to your phone from scheduled tasks (morning briefing, failures, etc.). Requires a Pushover account (~$5 one-time). Enable?
    → `USE_PUSHOVER` (bool)

16. **Gmail** — Claude Code can read your inbox via the `gog` Google Workspace skill (separate install). Needed for email scan tasks. Enable?
    → `USE_GMAIL` (bool)

17. **Google Calendar** — used for morning briefing, meeting prep. Same `gog` skill. Enable?
    → `USE_CALENDAR` (bool)

18. **Smart Connections** — Obsidian plugin that generates embeddings, powers semantic vault search. No secrets needed, just install the plugin inside Obsidian later. Enable?
    → `USE_SMART_CONNECTIONS` (bool)

### Section 8 — Scheduled Tasks

Walk through the catalog one by one. For each, print:
- Name + emoji
- What it does (read from `scripts/scheduled/manifest.yaml` description)
- Default time / day
- What integrations it needs
- Ask: "Enable? (y/n) — change time? (HH:MM or 'default')"

Tasks to cover, in this order:

1. Morning Briefing (8am weekdays) — needs Calendar
2. Midday Checkpoint (12pm weekdays) — needs nothing
3. Daily Journal (10pm every day) — needs nothing
4. Kanban Staleness (11am weekdays) — needs nothing
5. Email Scan AM (10:30am weekdays) — needs Gmail
6. Email Scan PM (2:30pm weekdays) — needs Gmail
7. Meeting Prep (3:30pm Sun–Thu) — needs Calendar
8. Partner Morning nudge (10:15am daily) — **only ask if `PARTNER_NAME` was set**
9. Partner Evening intention (5pm daily) — **only ask if `PARTNER_NAME` was set**
10. Weekly Review (Friday 4pm) — needs Calendar + Gmail
11. Git Sync (hourly) — requires git remote; mention they can skip and add later

Skip the ask if required integrations were disabled in Section 7. Tell them why ("skipping email-scan because Gmail wasn't enabled").

Stage results as `SCHEDULED_TASKS`:
```json
{
  "morning-briefing": {"enabled": true, "hour": 8, "minute": 0},
  ...
}
```

### Section 9 — Preflight

Before running setup, confirm a destructive-ish action:

"I'm about to:
- Rename `skills/assistant-template/` → `skills/<slug>/` and install it at `~/.claude/skills/<slug>/`
- Same for the vault skill
- Write `config/SOUL.md`, `config/USER.md`, and telos templates with your values
- Flip the enabled flag on [N] scheduled tasks in `manifest.yaml`
- Install scheduled tasks to [launchd|cron] (you can remove with `scripts/scheduled/install.sh --uninstall`)
- Write `.env` with your chosen settings

Proceed? (y/n)"

### Section 10 — Run setup.py

Write the staged answers to `/tmp/assistant-onboarding.json` and run:

```bash
python3 scripts/setup.py --profile /tmp/assistant-onboarding.json
```

Relay the script's output to the user. If it errors, surface the error plainly — don't pretend it worked.

### Section 11 — Verify

After setup.py succeeds, do a one-shot verification:

1. `ls ~/.claude/skills/<slug>/ ~/.claude/skills/<slug>-vault/` — confirm installed
2. Check `config/SOUL.md` head — confirm `{{USER_NAME}}` is replaced
3. Platform-dependent:
   - macOS: `launchctl list | grep com.assistant` — show what's scheduled
   - Linux/WSL: `crontab -l | grep assistant` — show cron entries

Final message to user (one-line each):
- "Your assistant `<name>` is set up."
- "Type `/<slug>` in any Claude Code session to activate the persona."
- "Scheduled tasks will fire starting <next trigger time>."
- "Edit `config/USER.md` anytime as you add people or priorities."
- "Pushover/Gmail/Calendar secrets: open `.env` and fill them in."

---

## Rules

- **Don't invent values.** If the user skips a question, store `null` and move on. setup.py handles missing values gracefully.
- **Don't over-narrate.** One-sentence acknowledgments between questions. No "Great choice!" — just confirm what was captured and move on.
- **Resumable.** Re-read `/tmp/assistant-onboarding.json` if it exists and offer to continue where you left off.
- **Stay in your own voice** for the onboarding — you are not the assistant persona yet. The persona activates only after setup completes and they type `/<slug>`.
