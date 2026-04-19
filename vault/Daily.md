---
title: Daily
type: hub
---

# 📅 Daily Notes

One note per day, produced by {{ASSISTANT_NAME}} and edited by {{USER_NAME}}. Lives in `daily/YYYY-MM-DD.md`.

Parent: [[🏠 Brain]]

```dataview
TABLE WITHOUT ID
  file.link AS "Date"
FROM "daily"
WHERE file.name != "Daily"
SORT file.name DESC
LIMIT 14
```
