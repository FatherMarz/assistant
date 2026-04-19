# Heartbeat — {{ASSISTANT_NAME}}

On each heartbeat, scan silently and absorb context. Only notify if something genuinely needs attention RIGHT NOW.

## Checks

### Todos
- Scan `vault/todos.md` for overdue items that need action NOW
- Only flag genuine urgency; skip anything {{USER_NAME}} can address later today

### System
- Flag if abnormal

## What NOT to do
- Don't dump message contents, calendar summaries, or email threads
- Don't overlap with scheduled checks

## Output
Brief update. If nothing needs attention, stay silent.

## Default Behavior
DEFAULT TO SILENCE. Reply "nothing new" unless genuinely urgent RIGHT NOW.
Do NOT narrate checks. Do NOT repeat instructions. Do NOT explain workflow.
