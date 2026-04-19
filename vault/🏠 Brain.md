---
title: Home
type: hub
---

# 🏠 {{ASSISTANT_NAME}} Knowledge Graph

Top-level map of the vault. Every folder has its own hub; every note links up to its hub; every hub links up to Home.

---

## 🧭 Hubs

- [[People]] — everyone I've worked with, spoken to, or care about
- [[Organizations]] — companies, teams, and institutions
- [[Projects]] — active + past work
- [[Facts]] — assistant memory (context, family, projects, work, learning)
- [[Daily]] — daily notes (journal + briefings)
- [[Notes]] — atomic notes, dialogues, one-off pages
- [[Transcripts]] — meeting transcripts
- [[Weblinks]] — saved web links

---

## ✅ Tasks

- [[todos]] — live kanban board (swim lanes by project/area)
- [[todos-archive]] — declined items kept for dedup

---

## 📊 Vault Stats

```dataviewjs
const folders = ["people", "organizations", "projects", "facts", "daily", "notes", "transcripts", "weblinks"];
const rows = folders.map(f => {
  const pages = dv.pages(`"${f}"`).where(p => p.file.name !== p.file.folder);
  return [f, pages.length];
});
dv.table(["Folder", "Notes"], rows);
```

---

## 🆕 Recent Activity

```dataview
TABLE WITHOUT ID
  file.link AS "Note",
  file.folder AS "Folder",
  dateformat(file.mtime, "yyyy-MM-dd HH:mm") AS "Updated"
SORT file.mtime DESC
LIMIT 15
```
