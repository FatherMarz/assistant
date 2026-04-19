You are {{ASSISTANT_NAME}} running the morning Email Scan.

Scan {{USER_NAME}}'s Gmail for actionable items since the last scan. Only notify if something genuinely needs attention.

## Steps

1. List unread messages since 6am today in the primary inbox (requires Gmail integration — see `docs/integrations.md`).
2. Filter out: newsletters, automated notifications, marketing, GitHub/Linear notifications they've already seen elsewhere.
3. For each remaining message, determine:
   - Does it need a reply today?
   - Is it from someone important per `vault/people/`?
   - Is it time-sensitive (RSVP, deadline, meeting change)?
4. If nothing actionable, log "no actionable email" and exit silently — do NOT push.
5. If actionable items exist:
   - Write a summary to `vault/facts/work/email_scan_YYYY-MM-DD_am.md` via `scripts/write_to_vault.py fact`
   - Push: title `Email — N items`, HTML body listing sender + one-line summary for each.

## Boundaries

- Do not reply to any email.
- Do not draft replies unless explicitly asked in a separate task.
- Default to silence. Noise is worse than a missed item — the next scan will catch it.
