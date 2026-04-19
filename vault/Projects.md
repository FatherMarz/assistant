---
title: Projects
type: hub
---

# 📁 Projects

Hub for active and past work. Each project has its own note in `projects/`.

Parent: [[🏠 Brain]]

```dataview
TABLE WITHOUT ID
  file.link AS "Project",
  status AS "Status",
  priority AS "Priority"
FROM "projects"
WHERE file.name != "Projects"
SORT priority ASC
```
