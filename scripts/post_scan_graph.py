#!/usr/bin/env python3
"""Auto-wikilink entity mentions in scheduled task outputs.

Scans a fixed set of vault folders (daily notes, facts/context, facts/work,
facts/learning, transcripts) and rewrites plain-text mentions of known
entities (people/organizations/projects) as `[[wikilinks]]`. For each entity
it touches, appends a `- mentioned in [[path]]` line to that entity's
`## Connections` section.

Usage:
  post_scan_graph.py --since-start <epoch>   # scan files modified after epoch
  post_scan_graph.py --paths FILE [FILE…]    # explicit targets
  post_scan_graph.py --all                   # full sweep
  post_scan_graph.py --prune                 # drop stale `mentioned in` lines
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from write_to_vault import (  # noqa: E402
    VAULT,
    PEOPLE_DIR,
    ORGS_DIR,
    PROJECTS_DIR,
    _add_connection_line,
)

AUDIT_LOG = VAULT.parent / "logs" / "graph-scan.log"


def _audit(event: str, message: str) -> None:
    try:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().astimezone().replace(microsecond=0).isoformat()
        with AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(f"{ts} {event} {message}\n")
    except OSError:
        pass


SCAN_GLOBS = (
    "daily/*.md",
    "facts/context/*.md",
    "facts/work/*.md",
    "facts/learning/*.md",
    "transcripts/*.md",
)

# Entity basenames whose bare text would drown the graph in false positives.
# Multi-word variants still match normally. Extend via --blocklist-file.
DEFAULT_BLOCKLIST = frozenset({
    "People", "Organizations", "Projects",
})

FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
FENCED_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
WIKILINK_RE = re.compile(r"\[\[[^\]]+\]\]")
INLINE_LINK_RE = re.compile(r"\[[^\]]+\]\([^)]+\)")
MENTION_LINE_RE = re.compile(r"^-\s+mentioned in \[\[([^\]]+)\]\]\s*$")

PLACEHOLDER_PREFIX = "\x00PLC"
PLACEHOLDER_RE = re.compile(rf"{re.escape(PLACEHOLDER_PREFIX)}(\d+)\x00")


def _parse_aliases(text: str) -> list[str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return []
    fm = m.group(0)
    inline = re.search(r"^aliases:\s*\[([^\]]*)\]", fm, re.MULTILINE)
    if inline:
        return [
            a.strip().strip('"').strip("'")
            for a in inline.group(1).split(",")
            if a.strip()
        ]
    return []


def _is_hub(path: Path) -> bool:
    folder = path.parent.name.lower()
    stem = path.stem.lower()
    return stem == folder or stem == folder.rstrip("s")


def build_entity_index(blocklist: set[str]) -> dict[str, Path]:
    entities: dict[str, Path] = {}
    alias_candidates: dict[str, list[Path]] = {}
    for directory in (PEOPLE_DIR, ORGS_DIR, PROJECTS_DIR):
        if not directory.exists():
            continue
        for md in directory.glob("*.md"):
            if _is_hub(md):
                continue
            base = md.stem
            if base in blocklist:
                continue
            entities[base] = md
            try:
                text = md.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for alias in _parse_aliases(text):
                if alias and alias not in blocklist:
                    alias_candidates.setdefault(alias, []).append(md)
    for alias, matches in alias_candidates.items():
        if alias in entities:
            continue
        if len(matches) > 1:
            print(f"warning: alias '{alias}' matches multiple entities, skipping", file=sys.stderr)
            continue
        # Skip single-word aliases — false positives on shared first names.
        if " " not in alias:
            continue
        entities[alias] = matches[0]
    return entities


def _protect(body: str) -> tuple[str, list[str]]:
    saved: list[str] = []

    def sub(match: re.Match) -> str:
        saved.append(match.group(0))
        return f"{PLACEHOLDER_PREFIX}{len(saved) - 1}\x00"

    body = FENCED_RE.sub(sub, body)
    body = INLINE_CODE_RE.sub(sub, body)
    body = WIKILINK_RE.sub(sub, body)
    body = INLINE_LINK_RE.sub(sub, body)
    return body, saved


def _restore(body: str, saved: list[str]) -> str:
    return PLACEHOLDER_RE.sub(lambda m: saved[int(m.group(1))], body)


def wikilink_file(path: Path, index: dict[str, Path]) -> set[str]:
    text = path.read_text(encoding="utf-8")
    fm_match = FRONTMATTER_RE.match(text)
    fm = fm_match.group(0) if fm_match else ""
    body = text[len(fm):]

    body, saved = _protect(body)
    touched: set[str] = set()

    for name in sorted(index, key=lambda s: (-len(s), s)):
        entity_path = index[name]
        base = entity_path.stem
        pattern = rf"\b{re.escape(name)}\b"
        hits = 0

        def repl(_m: re.Match) -> str:
            nonlocal hits
            hits += 1
            saved.append(f"[[{base}]]")
            return f"{PLACEHOLDER_PREFIX}{len(saved) - 1}\x00"

        new_body = re.sub(pattern, repl, body)
        if hits > 0:
            body = new_body
            touched.add(base)

    body = _restore(body, saved)
    new_text = fm + body
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return touched


def add_back_references(file_path: Path, touched: set[str], index: dict[str, Path]) -> None:
    rel = file_path.relative_to(VAULT).with_suffix("")
    line = f"- mentioned in [[{rel}]]"
    seen: set[Path] = set()
    for base in touched:
        ep = index.get(base)
        if not ep or ep in seen:
            continue
        seen.add(ep)
        _add_connection_line(ep, line)


def iter_targets(*, since_ts: float | None, explicit: list[str] | None, all_mode: bool):
    if explicit:
        for raw in explicit:
            p = Path(raw).resolve()
            if p.exists() and p.is_file():
                yield p
        return
    for pattern in SCAN_GLOBS:
        for path in VAULT.glob(pattern):
            if not path.is_file():
                continue
            if all_mode or since_ts is None or path.stat().st_mtime >= since_ts:
                yield path.resolve()


def prune_stale_mentions() -> int:
    removed = 0
    for directory in (PEOPLE_DIR, ORGS_DIR, PROJECTS_DIR):
        if not directory.exists():
            continue
        for md in directory.glob("*.md"):
            text = md.read_text(encoding="utf-8")
            out = []
            changed = False
            for line in text.splitlines(keepends=True):
                m = MENTION_LINE_RE.match(line.rstrip("\n"))
                if m and not (VAULT / f"{m.group(1)}.md").exists():
                    changed = True
                    removed += 1
                    continue
                out.append(line)
            if changed:
                md.write_text("".join(out), encoding="utf-8")
                rel = md.relative_to(VAULT)
                print(f"pruned mentions in {rel}")
                _audit("pruned", str(rel))
    return removed


def _parse_since(raw: str) -> float:
    try:
        return float(raw)
    except ValueError:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since-start", help="Epoch or ISO timestamp — scan files modified after this")
    ap.add_argument("--paths", nargs="+", help="Explicit file paths to process")
    ap.add_argument("--all", action="store_true", help="Sweep all files matching scope globs")
    ap.add_argument("--prune", action="store_true", help="Drop stale 'mentioned in' lines from entity notes")
    ap.add_argument("--blocklist-file", help="File with one blocked name per line")
    args = ap.parse_args()

    blocklist = set(DEFAULT_BLOCKLIST)
    if args.blocklist_file:
        bf = Path(args.blocklist_file)
        if bf.exists():
            blocklist.update(line.strip() for line in bf.read_text().splitlines() if line.strip())

    if args.prune and not (args.paths or args.all or args.since_start):
        n = prune_stale_mentions()
        print(f"pruned {n} stale mention lines")
        return

    since_ts = _parse_since(args.since_start) if args.since_start else None
    index = build_entity_index(blocklist)
    if not index:
        print("no entities found in people/organizations/projects", file=sys.stderr)
        return

    scanned = 0
    changed_files = 0
    total_touches = 0
    for path in iter_targets(since_ts=since_ts, explicit=args.paths, all_mode=args.all):
        scanned += 1
        touched = wikilink_file(path, index)
        if touched:
            changed_files += 1
            total_touches += len(touched)
            add_back_references(path, touched, index)
            try:
                display = path.relative_to(VAULT)
            except ValueError:
                display = path
            entities_csv = ", ".join(sorted(touched))
            print(f"linked {display}: {entities_csv}")
            _audit("linked", f"{display} -> {entities_csv}")

    if args.prune:
        prune_stale_mentions()

    print(f"scanned {scanned} files · linked {total_touches} mentions across {changed_files} files")


if __name__ == "__main__":
    main()
