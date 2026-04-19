# Integrations

The assistant starts with zero external integrations. Add what you want; skip what you don't. Each integration is optional — scheduled tasks that need a missing integration will skip silently.

## Pushover (push notifications)

What it's for: scheduled tasks push their output to your phone (morning briefing, failure alerts, etc.).

Setup:
1. Create an account at https://pushover.net
2. Install the Pushover mobile app, log in
3. On the web dashboard, note your **User Key**
4. "Your Applications" → Create Application → get an **API Token**
5. Add both to `.env`:
   ```
   PUSHOVER_TOKEN=...
   PUSHOVER_USER=...
   ```

Cost: one-time ~$5 per platform. Worth it.

## Google Workspace (Gmail + Calendar)

What it's for: email scans, meeting prep, weekly review.

The assistant uses Google Workspace via a separate skill (recommended: install the `gog` Google CLI skill or a Gmail MCP server into your `~/.claude/skills/` or MCP config). Setup is skill-specific — see that skill's own docs.

Once the Google skill is installed and authenticated, scheduled task prompts can reference it. No env vars needed here.

## Ticketing (Jira / Linear / GitHub Issues)

What it's for: sync your tickets into `vault/tickets/open.md` so you can see them alongside your Kanban.

Set `TICKETING_SYSTEM` in `.env` to one of: `jira`, `linear`, `github`, `none`.

**Stub only in v1.** The integration is not wired up out of the box — add a `scripts/scheduled/prompts/ticketing-sync.md` and register it in `manifest.yaml`. Use your system's MCP server or CLI (Jira MCP, Linear MCP, `gh` CLI) from inside the prompt.

## iMessage (macOS only)

Not supported in this template. The Welendathas original reads `~/Library/Messages/chat.db` to pick up signal from a partner — the approach requires Full Disk Access and is Mac-only. If you're on macOS and want to add this, reference the Welendathas pattern at `Users/marcello/Development/Welendathas/scripts/scheduled/prompts/imessage-scan.md`.

## Smart Connections (Obsidian plugin)

What it's for: semantic vault search via `scripts/vault-search`.

Setup: see `docs/obsidian-setup.md`. No env vars.

## Adding a new integration

Integrations are just things the scheduled task prompts reference. To add one:

1. Add its required creds to `.env.example` and document them here
2. Write a prompt in `scripts/scheduled/prompts/` that uses the creds
3. Register the task in `scripts/scheduled/manifest.yaml`, listing the integration in `integrations: [...]`
4. Re-run `scripts/scheduled/install.sh`
