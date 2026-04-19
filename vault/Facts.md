---
title: Facts
type: hub
---

# 🧠 Facts

Long-term memory for {{ASSISTANT_NAME}} — context, family, projects, work, and learning.

Parent: [[🏠 Brain]]

## Categories

- `facts/context/` — current situational context (day-to-day, recent conversations)
- `facts/family/` — family context and preferences
- `facts/work/` — work context, role, colleagues
- `facts/projects/` — project-scoped facts
- `facts/learning/` — things learned, dated `YYYY-MM-DD:topic-slug`
- `facts/other/` — everything else

```dataview
TABLE WITHOUT ID
  file.link AS "Fact",
  category AS "Category",
  updated AS "Updated"
FROM "facts"
WHERE file.name != "Facts"
SORT file.mtime DESC
LIMIT 20
```
