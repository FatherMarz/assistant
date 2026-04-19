---
name: {{ASSISTANT_NAME_SLUG}}-vault
description: "{{ASSISTANT_NAME}}'s Obsidian vault operations — read and write to the knowledge base (daily notes, todos Kanban, facts, people, organizations, projects, transcripts). Invoke when {{USER_NAME}} asks {{ASSISTANT_NAME}} to 'remember', 'look up', 'search', add a todo, or retrieve anything from the vault."
---

# {{ASSISTANT_NAME}} Vault — Read/Write Guide

The vault is rooted at:
```
{{ASSISTANT_REPO}}/vault/
```

Obsidian opens this folder directly. The parent repo (`{{ASSISTANT_REPO}}/`) also contains persona config (`config/`), scheduled task scripts (`scripts/`), and logs — those are NOT in the vault.

Cross-platform: reads use plain file I/O (Read, Glob, Grep tools, or shell `cat`/`rg`); writes go through the Python helpers. Obsidian does NOT need to be running for this skill to work.

---

## Vault Structure

```
vault/
├── 🏠 Brain.md                          ← top-of-graph hub
├── daily/               YYYY-MM-DD.md   ← one file per day (Morning, Midday, Evening, etc.)
├── todos.md                             ← Kanban board (6 columns, swim lanes by #project)
├── todos-archive.md                     ← declined / archived items
├── transcripts/         YYYY-MM-DD-slug.md
├── people/              First Last.md   ← one note per person (filenames preserve spaces)
├── organizations/       Org Name.md
├── projects/            Project Name.md
├── notes/               Title.md
├── weblinks/            Title.md
└── facts/
    ├── context/         <slug>.md       (daily context, flags, timestamps)
    ├── family/          <slug>.md
    ├── work/            <slug>.md
    ├── projects/        <slug>.md
    ├── learning/        YYYY-MM-DD:topic-slug.md
    └── other/           <slug>.md
```

**Every folder has a hub** (`People.md`, `Organizations.md`, etc.) linking up to `🏠 Brain`. Every note has an `Up:: [[Hub]]` line linking back.

**Persona + telos** live OUTSIDE the vault at `{{ASSISTANT_REPO}}/config/`:
- `SOUL.md`, `USER.md`, `BRIEFING_RULES.md`, `HEARTBEAT.md` — voice and rules
- `telos/` — MISSION, GOALS, PROJECTS, STRATEGIES, BELIEFS

**Daily file sections** (configurable via `config/daily_sections.yaml`):
```
# Tue Apr 14
## ☀️ Morning          ← morning-briefing
## 🔔 Midday           ← midday-checkpoint
## Meeting Prep        ← meeting-prep (dated for tomorrow)
## Yesterday's Recap   ← daily-journal
## Open Loops          ← daily-journal
## 🌙 Evening          ← daily-journal
```

---

## Reading

### A specific file
Use the built-in Read tool (absolute path) or shell `cat`.

### List files in a folder
Glob tool: `vault/daily/*.md`. Or shell: `ls {{ASSISTANT_REPO}}/vault/daily/ | sort -r | head -5`

### Full-text search
Grep tool (preferred) or shell `rg`:
```bash
rg --type md "query" {{ASSISTANT_REPO}}/vault/
rg --type md -C 2 "query" {{ASSISTANT_REPO}}/vault/facts/      # with 2 lines of context
```

### Semantic search
Natural-language / conceptual queries. Reuses Smart Connections' cached embeddings — matches on meaning even when wording differs:
```bash
{{ASSISTANT_REPO}}/scripts/vault-search "fundraising advice"
{{ASSISTANT_REPO}}/scripts/vault-search "resilience thesis" --top 5 --kind blocks
{{ASSISTANT_REPO}}/scripts/vault-search "..." --paths           # paths only
{{ASSISTANT_REPO}}/scripts/vault-search "..." --min-score 0.6    # filter weak matches
```
Requires Obsidian + Smart Connections plugin to keep the embedding cache fresh. Setup: `docs/obsidian-setup.md`.

### Backlinks to an entity
Since every mention becomes a wikilink via the auto-linker, grep for wikilinks pointing at a name:
```bash
rg -l "\[\[Jane Doe\]\]|\[\[Acme\]\]" {{ASSISTANT_REPO}}/vault/
```

### Today's daily note
```bash
cat {{ASSISTANT_REPO}}/vault/daily/$(date +%Y-%m-%d).md
```

---

## Writing

### Upsert a section in today's daily note
```bash
python3 {{ASSISTANT_REPO}}/scripts/write_to_daily.py section \
  --key "Midday" --content "- Remaining item
- Follow-up"
```
Idempotent — replaces the existing section or inserts it in canonical order. Valid keys come from `config/daily_sections.yaml`.

### Upsert a fact
```bash
python3 {{ASSISTANT_REPO}}/scripts/write_to_vault.py \
  fact --category context --key "last_nudge_time" --value "2026-04-14T12:00"
```
Categories: `context`, `family`, `work`, `projects`, `learning`, `other`.

### Create or update a person
```bash
python3 {{ASSISTANT_REPO}}/scripts/write_to_vault.py \
  person --name "Jane Doe" --role "CTO" --company "Acme"
```
Auto-seeds `## Connections` with `- works at [[Acme]]` and appends `Up:: [[People]]` on create.

### Create an org / project stub
```bash
python3 {{ASSISTANT_REPO}}/scripts/write_to_vault.py \
  org --name "Acme" --description "..." --industry "SaaS"

python3 {{ASSISTANT_REPO}}/scripts/write_to_vault.py \
  project --name "Onboarding" --status "active" --owner "{{USER_NAME}}"
```

### Todos (Kanban)

Six columns: `📥 Review`, `💤 Backlog`, `📋 To Do`, `⚙️ In Progress`, `🛑 Blocked`, `✅ Done`. Cards use emoji metadata (⏫ high, 🔽 low, 📅 due date, #project/slug).

```bash
# Propose new todo (dedup-checked against active + declined archive)
python3 {{ASSISTANT_REPO}}/scripts/write_to_kanban.py propose \
  --title "Send paperwork" --priority high --due 2026-04-16 --project clients

# List open items
python3 {{ASSISTANT_REPO}}/scripts/write_to_kanban.py list \
  --status "To Do,In Progress,Blocked"

# Move / complete / decline
python3 {{ASSISTANT_REPO}}/scripts/write_to_kanban.py move --match "paperwork" --to "In Progress"
python3 {{ASSISTANT_REPO}}/scripts/write_to_kanban.py complete --match "paperwork"
python3 {{ASSISTANT_REPO}}/scripts/write_to_kanban.py decline --match "unwanted item"
```

### Add a graph relationship
Writes `- relation [[Target]]` into the source's `## Connections` section. Idempotent. Source must exist.
```bash
python3 {{ASSISTANT_REPO}}/scripts/write_to_vault.py connect \
  --from "Jane Doe" --relation "advises" --to "Acme" \
  --inverse "advised by"
```
Common phrasings: `works at`, `advises`, `customer of`, `introduced by`, `partner of`, `formerly at`, `mentor of`.

### Write a transcript
Direct file write — not structural, just verbatim meeting content.
```bash
cat > "{{ASSISTANT_REPO}}/vault/transcripts/2026-04-14-kickoff.md" <<'EOF'
... transcript body ...
EOF
```

---

## Auto-wikilinking

`scripts/post_scan_graph.py` runs after every scheduled task via `run.sh`. Scans `daily/`, `facts/context/`, `facts/work/`, `facts/learning/`, `transcripts/` for plain-text entity mentions and rewrites them as `[[wikilinks]]`. Also appends `- mentioned in [[path]]` to each entity's `## Connections`. Case-sensitive, word-boundary, multi-word aliases only. Audit log at `logs/graph-scan.log`. **You don't need to wikilink manually in prompts** — the post-processor handles it.

Run manually: `python3 {{ASSISTANT_REPO}}/scripts/post_scan_graph.py --all`
Prune stale mentions: `python3 {{ASSISTANT_REPO}}/scripts/post_scan_graph.py --prune`
