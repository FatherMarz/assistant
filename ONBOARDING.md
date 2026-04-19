# ONBOARDING — Assistant Template

The easy way: open Claude Code in this repo and run `/onboard-assistant`. The skill drives the whole thing conversationally, asks every question in order, and calls `scripts/setup.py` at the end.

This file is the **manual alternative** — use it if you want to skip the conversation and fill in a profile JSON yourself, or if you want to understand what `/onboard-assistant` is actually doing under the hood.

## Steps

### 1. Install Python deps

```bash
pip install pyyaml
```

### 2. Fill in a profile JSON

Create `/tmp/assistant-onboarding.json` with your answers:

```json
{
  "USER_NAME": "Jon",
  "ASSISTANT_NAME": "Welendathas",
  "ASSISTANT_NAME_SLUG": "welendathas",
  "PRONOUNS": "he/him",

  "PEOPLE": [
    {"name": "Blakeny", "relationship": "wife", "notes": "Works in HR. Recovering from surgery."},
    {"name": "Maya", "relationship": "daughter (9)", "notes": "Loves horses and piano."}
  ],
  "PARTNER_NAME": "Blakeny",

  "USER_ROLE": "Senior Software Engineer",
  "USER_EMPLOYER": "Acme Corp",
  "TIMEZONE": "America/Edmonton",
  "WORK_HOURS": "9am-5pm weekdays",
  "USER_TOOLS": "VS Code, GitHub, Slack, Notion",

  "PRIORITIES": [
    "Family (Blakeny, Maya)",
    "Health (sleep, gym)",
    "Work",
    "Hobbies (woodworking)"
  ],
  "OFF_HOURS_RULE": "After 6pm and weekends = family time. Flag work bleeding in.",

  "COMMS_STYLE": "Direct and concise. Bullets over paragraphs. Offer to DO things, not just report.",
  "BRIEFING_STYLE": "Action items only. Ask about each one instead of dumping everything.",

  "TICKETING_SYSTEM": "github",

  "USE_PUSHOVER": true,
  "USE_GMAIL": true,
  "USE_CALENDAR": true,
  "USE_SMART_CONNECTIONS": true,

  "SCHEDULED_TASKS": {
    "morning-briefing":   {"enabled": true,  "hour": 8,  "minute": 0},
    "midday-checkpoint":  {"enabled": true,  "hour": 12, "minute": 0},
    "daily-journal":      {"enabled": true,  "hour": 22, "minute": 0},
    "kanban-staleness":   {"enabled": true,  "hour": 11, "minute": 0},
    "email-scan-am":      {"enabled": true,  "hour": 10, "minute": 30},
    "email-scan-pm":      {"enabled": true,  "hour": 14, "minute": 30},
    "meeting-prep":       {"enabled": true,  "hour": 15, "minute": 30},
    "partner-morning":    {"enabled": false},
    "partner-evening":    {"enabled": false},
    "weekly-review":      {"enabled": true,  "hour": 16, "minute": 0},
    "git-sync":           {"enabled": false}
  }
}
```

Every field is optional except `USER_NAME` and `ASSISTANT_NAME`. Missing values stay as `{{PLACEHOLDER}}` in the rendered files so you can see what's left to fill in.

### 3. Run setup

```bash
python3 scripts/setup.py --profile /tmp/assistant-onboarding.json
```

This will:
- Render `{{PLACEHOLDER}}` tokens in `config/`, `vault/` hubs, and scheduled task prompts
- Rename `skills/assistant-template/` → `skills/<your-slug>/` and the vault skill similarly
- Symlink both skills into `~/.claude/skills/` so Claude Code picks them up
- Update `scripts/scheduled/manifest.yaml` with your enabled tasks
- Write `.env` from `.env.example` (you'll fill in Pushover keys etc. manually)
- Run `scripts/scheduled/install.sh` to schedule the enabled tasks

### 4. Fill in secrets

Open `.env` and add your Pushover keys (or leave blank to skip push notifications):

```
PUSHOVER_TOKEN=az1b2c3d4e5f...
PUSHOVER_USER=u1234567890...
```

### 5. Set up Obsidian

See `docs/obsidian-setup.md` — install plugins, open the vault, set up Smart Connections for semantic search.

### 6. Test it

In Claude Code:

```
/<your-assistant-slug>
```

The persona should activate. Ask it something simple:

> "What do you know about me?"

It should pull from `config/USER.md`.

### 7. Test a scheduled task manually

```bash
scripts/scheduled/run.sh morning-briefing
tail -50 logs/scheduled/morning-briefing.log
```

## Re-onboarding / Editing

You can re-run `setup.py` any time with an updated profile JSON — it's idempotent. Or just edit `config/USER.md` / `config/SOUL.md` directly. Those files are the source of truth once they're rendered; setup.py only re-renders `{{PLACEHOLDERS}}` that are still in the files.

## Uninstall

```bash
scripts/scheduled/install.sh --uninstall
rm -rf ~/.claude/skills/<your-assistant-slug>*
```
