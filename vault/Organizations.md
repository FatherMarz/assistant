---
title: Organizations
type: hub
---

# 🏢 Organizations

Hub for companies, teams, and institutions. Each has its own note in `organizations/`.

Parent: [[🏠 Brain]]

```dataview
TABLE WITHOUT ID
  file.link AS "Org",
  type AS "Type",
  status AS "Status"
FROM "organizations"
WHERE file.name != "Organizations"
SORT file.name ASC
```
