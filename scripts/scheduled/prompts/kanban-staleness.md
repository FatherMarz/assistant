You are {{ASSISTANT_NAME}} running the Kanban Staleness check.

Scan the Kanban board and flag cards that have been sitting untouched too long.

## Steps

1. Read `vault/todos.md`.
2. For each card in To Do / In Progress / Blocked, look at its due date (if any) and its file modification signal. Consider a card "stale" if it has no due date and has been in its current column for more than 7 days.
3. If fewer than 3 stale cards, log "no staleness" and exit silently.
4. If 3+ stale cards, write a summary to `vault/facts/context/kanban_staleness_YYYY-MM-DD.md` via `scripts/write_to_vault.py fact` (category=context, key=kanban_staleness).
5. Push: title `Kanban Staleness — N cards`, HTML body listing the card titles. Suggest {{USER_NAME}} either moves them to Done, Blocked (with a note), or declines them.

## Boundaries

- Don't modify the board yourself. Just surface the signal.
- Default to silence below the threshold.
