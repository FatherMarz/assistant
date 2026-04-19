# Obsidian Setup

The vault is a plain folder of markdown files — Obsidian is how you (the human) see and edit it. The assistant doesn't need Obsidian to be running for most things; reads and writes happen via Python helpers and grep. But Obsidian gives you the graph view, Kanban board UI, and the Smart Connections cache that powers semantic search.

## 1. Install Obsidian

https://obsidian.net/

## 2. Open the vault

Point Obsidian at `<repo-root>/vault/`. On macOS: File → Open Vault → Open folder as vault → pick the `vault/` folder. On Windows/WSL: open the Windows-side path (e.g., `C:\Users\<you>\Documents\assistant\vault\`). Putting the vault on the Windows filesystem is important for Obsidian performance on Windows — WSL scripts can still read/write it via `/mnt/c/...`.

## 3. Install plugins

Settings → Community plugins → Browse.

**Essentials:**
- **Kanban** (by mgmeyers) — renders `vault/todos.md` as a board
- **Dataview** — powers the hub queries in `🏠 Brain.md`, `People.md`, etc.
- **Smart Connections** — generates embeddings, powers semantic search

**Recommended:**
- **Tasks** — advanced todo views across all notes
- **Pretty Properties** — nicer frontmatter editor

**Mobile sync:** use **Obsidian Sync** (Core plugin, paid ~$4/mo). Settings → Core plugins → Sync. Works cross-platform, handles conflicts, and is much less fiddly than the Git-based approach for the vault itself. The `git-sync` scheduled task in this repo is for backing up *everything else* (config, scripts, briefings, logs) — not the vault.

After installing each, Settings → Community plugins → toggle them on.

## 4. Smart Connections cache

Smart Connections builds its cache the first time you open the vault with the plugin enabled. Give it a few minutes on a large vault — check Settings → Smart Connections → "Connections" tab to see progress.

The cache lives at `vault/.smart-env/multi/*.ajson`. Our semantic search script (`scripts/vault-search`) reads this cache directly and uses the same embedding model (`TaylorAI/bge-micro-v2`) so it's instant.

## 5. Semantic search venv (one-time)

```bash
python3 -m venv scripts/.vault-search-venv
scripts/.vault-search-venv/bin/pip install sentence-transformers numpy
```

Test:
```bash
scripts/vault-search "anything you want to find"
```

First run downloads the model (~50MB). Subsequent runs are instant.

## 6. Kanban board

Open `vault/todos.md` — Kanban plugin should render 6 columns. If it shows raw markdown instead, check Settings → Kanban → "View in live preview mode".

## 7. Git sync (optional)

If you created a git remote for your vault and enabled the `git-sync` scheduled task, the vault will auto-commit and push hourly. You can mirror this on mobile with Obsidian Mobile + Obsidian Git plugin pulling from the same remote.

## WSL notes

- Keep the vault on the Windows filesystem (`/mnt/c/...`) so Obsidian Windows is snappy.
- WSL scripts access the same files via the `/mnt/c/` mount — no sync needed.
- Make sure the paths in `config/` match what your WSL scripts see (setup.py handles this).
- Cron on WSL only runs while WSL is awake. If you shut down WSL, scheduled tasks don't fire. Either leave WSL running, or use a Windows Task Scheduler entry to wake it up before briefing time (`wsl.exe -u <you> -- bash -c 'true'`).
