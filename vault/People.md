---
title: People
type: hub
---

# 👥 People

Hub for everyone {{USER_NAME}} has worked with, spoken to, or cares about. Each person has their own note in `people/`.

Parent: [[🏠 Brain]]

```dataview
TABLE WITHOUT ID
  file.link AS "Person",
  role AS "Role",
  org AS "Org"
FROM "people"
WHERE file.name != "People"
SORT file.name ASC
```
