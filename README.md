# assistant — Personal AI Executive Assistant (Template)

A template repo that turns Claude Code into a persistent, memory-backed personal EA. Gives you:

- An **Obsidian vault** as long-term memory (daily notes, todos Kanban, facts, people, orgs, projects, transcripts)
- A **persona skill** (`/<your-assistant>`) that loads your voice, priorities, and boundaries into any Claude Code session
- A catalog of **scheduled tasks** (morning briefing, midday checkpoint, daily journal, email scan, meeting prep, weekly review, etc.) you opt into individually
- **Semantic search** across the vault via Obsidian's Smart Connections embeddings
- **Auto-wikilinking** of entity mentions across your notes

## Quick Start

```bash
# 1. Clone into your home directory (or wherever)
git clone <repo-url> ~/Development/assistant
cd ~/Development/assistant

# 2. Install Python deps (one-time)
pip install pyyaml
# For semantic search later, also:
# python3 -m venv scripts/.vault-search-venv
# scripts/.vault-search-venv/bin/pip install sentence-transformers numpy

# 3. Open in Claude Code, then run the onboarding
claude  # or: code . if you're using the VS Code integration

# Inside Claude Code:
/onboard-assistant
```

The onboarding walks you through:
1. Naming yourself + your assistant (pick any name — fantasy names work great)
2. Describing the people who matter and what to remember about them
3. Your work context, timezone, working hours
4. Your top priorities and off-hours rule
5. Which integrations to enable (Pushover, Gmail, Calendar, Smart Connections)
6. Which scheduled tasks to turn on, and at what times

At the end, it installs a `/<your-assistant-name>` skill into `~/.claude/skills/` and sets up the scheduler (launchd on macOS, cron on Linux/WSL).

Total time: ~10 minutes.

## Repo Layout

```
assistant/
├── config/              Persona + user profile (SOUL, USER, BRIEFING_RULES, HEARTBEAT, telos/)
├── vault/               Obsidian knowledge base (opened as the vault root)
├── scripts/             Write helpers + scheduled task system
│   └── scheduled/       manifest.yaml + one prompt per task + installer
├── skills/              Persona + vault + onboarding skills
├── docs/                Setup guides (Obsidian, integrations)
├── CLAUDE.md            Instructions Claude Code reads on session start
├── ONBOARDING.md        Manual onboarding walkthrough (alternative to /onboard-assistant)
└── .env.example         Copy to .env, fill in integration keys
```

## After Onboarding

- Type `/<your-assistant-name>` in any Claude Code session to activate the persona
- Open `vault/` in Obsidian (install plugins per `docs/obsidian-setup.md`)
- Fill in secrets in `.env` (Pushover keys, etc.)
- Edit `config/USER.md` as you learn what else the assistant should know
- Add more people to `vault/people/`, orgs to `vault/organizations/`, etc.
- Add new scheduled tasks by dropping a prompt in `scripts/scheduled/prompts/` and a row in `manifest.yaml`, then re-running `scripts/scheduled/install.sh`

## Uninstall

```bash
scripts/scheduled/install.sh --uninstall   # remove scheduled jobs
rm -rf ~/.claude/skills/<your-assistant-name>*
rm -rf ~/Development/assistant
```

## Credits

Based on Welendathas, Marcello Delcaro's personal AI chief-of-staff.
