---
title: Transcripts
type: hub
---

# 🎙️ Transcripts

Meeting transcripts, captured as `transcripts/YYYY-MM-DD-slug.md`.

Parent: [[🏠 Brain]]

```dataview
TABLE WITHOUT ID
  file.link AS "Transcript"
FROM "transcripts"
WHERE file.name != "Transcripts"
SORT file.name DESC
LIMIT 20
```
