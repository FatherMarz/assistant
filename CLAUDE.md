# CLAUDE.md — Assistant Template

> Instructions Claude Code reads on session start. For full setup, see `README.md` and `ONBOARDING.md`.

## Repo Layout

- `config/` — Persona and rules (not in vault). `SOUL.md`, `USER.md`, `BRIEFING_RULES.md`, `HEARTBEAT.md`, `telos/`, `daily_sections.yaml`, `kanban_rules.yaml`.
- `vault/` — Obsidian knowledge base. Contains `daily/`, `people/`, `organizations/`, `projects/`, `facts/` (context/family/work/projects/learning/other), `transcripts/`, `notes/`, `weblinks/`, `todos.md` (Kanban).
- `scripts/` — Python write helpers (`write_to_daily.py`, `write_to_kanban.py`, `write_to_vault.py`), semantic search (`vault_search.py`), graph auto-linker (`post_scan_graph.py`), scheduled task system (`scheduled/`).
- `schedulers/` — Template scheduler definitions (launchd plist template, cron).
- `skills/` — Persona skill, vault skill, onboarding skill.
- `docs/` — Setup guides.
- `.env` — Integration secrets (Pushover, ticketing). Copy from `.env.example`.

## Identity & Context

Read these files when needed (not preloaded by default):
- **config/SOUL.md** — Personality, tone, guardrails, priorities, accountability style
- **config/USER.md** — User profile, people, priorities, off-hours rule, communication preferences
- **config/BRIEFING_RULES.md** — What to include/skip in briefings
- **config/HEARTBEAT.md** — Rules for proactive heartbeat checks (default: silence)

## TELOS — Mission & Goals

Read these when reasoning about priorities, planning, or making decisions:
- **config/telos/MISSION.md** — Personal mission statement
- **config/telos/GOALS.md** — Current quarterly/annual goals
- **config/telos/PROJECTS.md** — Active project priorities
- **config/telos/STRATEGIES.md** — Operating principles
- **config/telos/BELIEFS.md** — Core values

## Boundaries

- Ask before sending messages, changing data, or spending money.
- Never send emails or messages on the user's behalf without explicit approval.
- Never contact a partner, family member, or colleague directly. Coach the human.
- Apply the priorities and off-hours rule defined in `config/USER.md`.

## Data Layer

**Everything lives in the Obsidian vault** — one file per entity/fact. Cross-platform: plain markdown + YAML frontmatter.

| Scope | File / Folder | Access |
|-------|---------------|--------|
| Daily notes | `vault/daily/YYYY-MM-DD.md` | `scripts/write_to_daily.py` |
| Todos (Kanban) | `vault/todos.md` + `vault/todos-archive.md` | `scripts/write_to_kanban.py` |
| Facts | `vault/facts/<category>/<slug>.md` | `scripts/write_to_vault.py fact` |
| People / orgs / projects | `vault/people/<name>.md`, etc. | `scripts/write_to_vault.py person/org/project` |
| Relationships | `## Connections` in each entity note | `scripts/write_to_vault.py connect` |

### Reads

Use the built-in Read, Glob, and Grep tools for most vault operations. For conceptual queries where keyword search misses the mark, use:

```bash
scripts/vault-search "natural language query"           # top 10 files
scripts/vault-search "..." --top 5 --kind blocks        # section-level
scripts/vault-search "..." --paths                      # paths only
scripts/vault-search "..." --min-score 0.6              # filter weak matches
```

Requires Obsidian + Smart Connections plugin to be running (populates the embedding cache). See `docs/obsidian-setup.md`.

### Writes

```bash
# Daily section (idempotent, canonical ordering)
scripts/write_to_daily.py section --key "Midday" --content "..."

# Upsert a fact
scripts/write_to_vault.py fact --category context --key "slug" --value "..."

# Todos (Kanban)
scripts/write_to_kanban.py propose --title "..." --priority high --due 2026-04-20 --project clients
scripts/write_to_kanban.py move --match "substring" --to "In Progress"
scripts/write_to_kanban.py complete --match "substring"

# People / orgs / projects
scripts/write_to_vault.py person --name "Jane Doe" --role CTO --company Acme
scripts/write_to_vault.py org --name "Acme" --description "..."
scripts/write_to_vault.py project --name "Onboarding" --status active

# Graph relationships (writes into ## Connections)
scripts/write_to_vault.py connect --from "Jane Doe" --relation "works at" --to "Acme" --inverse "employs"
```

### Kanban board

6 columns in canonical order:
1. `📥 Review` — proposed items waiting for accept/decline
2. `💤 Backlog` — someday, not now
3. `📋 To Do` — active pending
4. `⚙️ In Progress` — currently working
5. `🛑 Blocked` — stuck on dependency
6. `✅ Done` — recent completions

Card syntax: `- [ ] Title ⏫ 📅 2026-04-16 #project/slug` (⏫ high, 🔽 low, no emoji = medium).

Optional rules in `config/kanban_rules.yaml` — `forbidden_project_prefixes` rejects project slugs starting with those prefixes (useful for routing product/dev work to a separate ticketing system).

## Scheduled Tasks

Defined declaratively in `scripts/scheduled/manifest.yaml`. Each task is:
- A prompt in `scripts/scheduled/prompts/<name>.md`
- A schedule (hour/minute/days_of_week, or raw `cron:`)
- A list of required integrations
- A model (sonnet/opus/haiku)

Scheduled via `scripts/scheduled/install.sh` — platform-aware (launchd on macOS, cron on Linux/WSL).

If the user asks for a briefing/checkpoint/journal and it's already been generated today, **read the file** (`briefings/YYYY-MM-DD.md`, `checkpoints/YYYY-MM-DD.md`, `journal/YYYY-MM-DD.md`) instead of regenerating.

## Knowledge Graph

Graph edges are expressed as `[[wikilinks]]` in each entity note's `## Connections` section. Add curated edges with `scripts/write_to_vault.py connect`.

**Auto-linking.** After every scheduled task, `scripts/post_scan_graph.py` scans `daily/`, `facts/context/`, `facts/work/`, `facts/learning/`, and `transcripts/` for plain-text entity mentions and rewrites them as wikilinks. It also appends `- mentioned in [[path]]` to each mentioned entity's `## Connections`. Case-sensitive, word-boundary match. Audit log at `logs/graph-scan.log`. Prompts don't need to wikilink manually.

## Integrations

Configure via `.env` (copied from `.env.example`):
- **Pushover** — push notifications from scheduled tasks
- **Claude model** — `CLAUDE_MODEL=sonnet` by default
- **Timezone** — used by prompts
- **Ticketing** — stub for Jira/Linear/GitHub (not wired by default; see `docs/integrations.md`)

Google Workspace (Gmail + Calendar) and other MCP-backed integrations are external skills the user installs separately — see `docs/integrations.md`.

## Known Gotchas

- **Cron on WSL only runs while WSL is running.** If the PC is asleep or WSL is shut down, scheduled tasks miss their window. Consider a Windows Task Scheduler entry that wakes WSL before briefing time.
- **Smart Connections cache must be kept fresh.** Open Obsidian periodically so the plugin can re-index — otherwise semantic search returns stale results.
- **Git sync** pushes on a schedule; if there's a merge conflict it'll fail silently. The morning briefing can surface this.
