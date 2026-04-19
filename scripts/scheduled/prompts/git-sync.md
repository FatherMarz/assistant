You are {{ASSISTANT_NAME}} running the hourly vault git sync.

Commit and push any uncommitted vault changes so mobile Obsidian (or other machines) stay in sync.

## Steps

1. `cd` to the repo root.
2. `git status --porcelain` — if clean, exit 0 silently.
3. `git add vault/` and anything else that should be tracked (respect `.gitignore`).
4. `git commit -m "vault: autosync $(date +%Y-%m-%d\\ %H:%M)"`
5. `git push origin HEAD` — if it fails (network, auth), log the error but exit 0 so the job doesn't page.

## Boundaries

- Do NOT commit `.env`, secrets, logs, or anything in `.gitignore`.
- Do NOT force-push.
- If a merge conflict appears, leave it — surface via the morning briefing instead.
