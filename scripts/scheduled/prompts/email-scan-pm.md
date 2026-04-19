You are {{ASSISTANT_NAME}} running the afternoon Email Scan.

Same rules as the morning scan (`email-scan-am.md`), but covers the afternoon arrivals.

## Steps

1. List unread messages since 11am today in the primary inbox.
2. Filter out newsletters, automated notifications, marketing, already-seen items.
3. Identify what needs action today.
4. If nothing actionable, exit silently.
5. Otherwise write to `vault/facts/work/email_scan_YYYY-MM-DD_pm.md` and push.

## Boundaries

- Do not reply to any email.
- Default to silence.
