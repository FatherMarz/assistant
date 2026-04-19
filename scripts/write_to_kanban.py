#!/usr/bin/env python3
"""Kanban board writer/reader for vault/todos.md.

The Kanban file is a plain markdown file consumed by the Obsidian Kanban plugin.
Columns are `## {emoji} {Name}` headers; cards are `- [ ]` list items underneath.
Cards use Tasks-plugin emoji metadata: ⏫ high, 🔽 low, 📅 YYYY-MM-DD due date,
#project/slug tag.

Declined items live in vault/todos-archive.md under `## ❌ Declined` so we can
dedup-check proposals against previously-rejected titles.

Optional config at `config/kanban_rules.yaml`:
  forbidden_project_prefixes: [ ... ]   # slugs starting with these get rejected
  duplicate_threshold: 0.88              # fuzzy dedup ratio

Usage:
  propose  — append a new card under 📥 Review with dedup check
  move     — move a card matching a title substring to another column
  complete — mark a card as done (move to ✅ Done with ✅ date)
  list     — emit cards in given columns (simple, json, or tsv)

  python3 scripts/write_to_kanban.py propose \\
    --title "Send Joe paperwork" \\
    --priority high --due 2026-04-16 --project clients
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date as dt_date
from difflib import SequenceMatcher
from pathlib import Path

REPO = Path(__file__).parent.parent
VAULT = REPO / "vault"
TODOS = VAULT / "todos.md"
ARCHIVE = VAULT / "todos-archive.md"
RULES_CONFIG = REPO / "config" / "kanban_rules.yaml"


def _load_rules() -> dict:
    if not RULES_CONFIG.exists():
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    return yaml.safe_load(RULES_CONFIG.read_text(encoding="utf-8")) or {}


_RULES = _load_rules()
FORBIDDEN_PREFIXES: list[str] = [p.lower() for p in _RULES.get("forbidden_project_prefixes") or []]
DUPLICATE_THRESHOLD: float = float(_RULES.get("duplicate_threshold") or 0.88)

COLUMNS = [
    ("Review", "📥 Review"),
    ("Backlog", "💤 Backlog"),
    ("To Do", "📋 To Do"),
    ("In Progress", "⚙️ In Progress"),
    ("Blocked", "🛑 Blocked"),
    ("Done", "✅ Done"),
]
COLUMN_KEYS = [k for k, _ in COLUMNS]
COLUMN_HEADING_BY_KEY = {k: h for k, h in COLUMNS}
COLUMN_KEY_BY_HEADING = {h: k for k, h in COLUMNS}

PRIORITY_EMOJI = {"high": "⏫", "medium": "", "low": "🔽"}
EMOJI_TO_PRIORITY = {"⏫": "high", "🔼": "medium", "🔽": "low"}

KANBAN_FRONTMATTER = "---\nkanban-plugin: board\n---\n\n"
KANBAN_SETTINGS_FOOTER = (
    "\n%% kanban:settings\n```\n"
    '{"kanban-plugin":"board","lane-width":272,"show-checkboxes":true,'
    '"archive-with-date":true,"new-note-folder":"daily"}'
    "\n```\n%%\n"
)


@dataclass
class Card:
    done: bool
    title: str
    priority: str = "medium"
    due: str | None = None
    project: str | None = None
    completed_date: str | None = None
    raw_line: str = ""

    def render(self) -> str:
        checkbox = "[x]" if self.done else "[ ]"
        bits = [f"- {checkbox} {self.title}"]
        if self.project:
            bits.append(f"#project/{self.project}")
        pri_emoji = PRIORITY_EMOJI.get(self.priority, "")
        if pri_emoji:
            bits.append(pri_emoji)
        if self.due:
            bits.append(f"📅 {self.due}")
        if self.completed_date:
            bits.append(f"✅ {self.completed_date}")
        return " ".join(bits)


def parse_card(line: str) -> Card | None:
    m = re.match(r"^\s*-\s*\[( |x)\]\s+(.+?)\s*$", line)
    if not m:
        return None
    done = m.group(1) == "x"
    body = m.group(2)

    due = None
    due_m = re.search(r"📅\s*(\d{4}-\d{2}-\d{2})", body)
    if due_m:
        due = due_m.group(1)
        body = body.replace(due_m.group(0), "").strip()

    completed = None
    comp_m = re.search(r"✅\s*(\d{4}-\d{2}-\d{2})", body)
    if comp_m:
        completed = comp_m.group(1)
        body = body.replace(comp_m.group(0), "").strip()

    project = None
    proj_m = re.search(r"#project/([\w-]+)", body)
    if proj_m:
        project = proj_m.group(1)
        body = body.replace(proj_m.group(0), "").strip()

    priority = "medium"
    for emoji, level in EMOJI_TO_PRIORITY.items():
        if emoji in body:
            priority = level
            body = body.replace(emoji, "").strip()
            break

    title = re.sub(r"\s+", " ", body).strip()
    return Card(done=done, title=title, priority=priority, due=due,
                project=project, completed_date=completed, raw_line=line.rstrip())


@dataclass
class Board:
    columns: dict[str, list[Card]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "Board":
        b = cls(columns={k: [] for k, _ in COLUMNS})
        if not path.exists():
            return b
        current_key: str | None = None
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                heading = line[3:].strip()
                current_key = COLUMN_KEY_BY_HEADING.get(heading)
                if current_key is None:
                    for k, h in COLUMNS:
                        if heading.endswith(h) or h.endswith(heading):
                            current_key = k
                            break
                continue
            if current_key is None:
                continue
            card = parse_card(line)
            if card:
                b.columns.setdefault(current_key, []).append(card)
        return b

    def render(self) -> str:
        parts = [KANBAN_FRONTMATTER]
        for key, heading in COLUMNS:
            parts.append(f"## {heading}\n\n")
            for card in self.columns.get(key, []):
                parts.append(card.render() + "\n")
            parts.append("\n")
        parts.append(KANBAN_SETTINGS_FOOTER)
        return "".join(parts)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render(), encoding="utf-8")


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())


def _fuzzy_match(a: str, b: str, threshold: float = DUPLICATE_THRESHOLD) -> bool:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio() >= threshold


def _declined_titles() -> list[str]:
    if not ARCHIVE.exists():
        return []
    text = ARCHIVE.read_text(encoding="utf-8")
    m = re.search(r"^## ❌ Declined\s*\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if not m:
        return []
    titles = []
    for line in m.group(1).splitlines():
        card = parse_card(line)
        if card:
            titles.append(card.title)
    return titles


def find_duplicate(title: str, board: Board) -> tuple[str, str] | None:
    active_keys = ("Review", "Backlog", "To Do", "In Progress", "Blocked")
    for key in active_keys:
        for card in board.columns.get(key, []):
            if _fuzzy_match(card.title, title):
                return (key, card.title)
    for declined_title in _declined_titles():
        if _fuzzy_match(declined_title, title):
            return ("archive-declined", declined_title)
    return None


def cmd_propose(args: argparse.Namespace) -> None:
    title = args.title.strip()
    if not title:
        print("ERROR: --title required", file=sys.stderr)
        sys.exit(1)

    if args.project and not args.force:
        proj_lower = args.project.lower()
        for prefix in FORBIDDEN_PREFIXES:
            if proj_lower.startswith(prefix):
                print(
                    f"REJECTED: project '{args.project}' starts with forbidden prefix "
                    f"'{prefix}' (see config/kanban_rules.yaml). Pass --force to override.",
                    file=sys.stderr,
                )
                sys.exit(1)

    board = Board.load(TODOS)
    dupe = find_duplicate(title, board)
    if dupe and not args.force:
        print(f"Skipped (duplicate in {dupe[0]}): {dupe[1]}")
        return

    card = Card(
        done=False,
        title=title,
        priority=(args.priority or "medium").lower(),
        due=args.due,
        project=args.project,
    )
    target_column = args.column or "Review"
    if target_column not in COLUMN_KEYS:
        print(f"ERROR: invalid column '{target_column}'. Valid: {COLUMN_KEYS}", file=sys.stderr)
        sys.exit(1)

    board.columns[target_column].append(card)
    board.save(TODOS)
    print(f"Proposed → {target_column}: {title}")


def cmd_move(args: argparse.Namespace) -> None:
    match = args.match.strip().lower()
    target = args.to
    if target not in COLUMN_KEYS:
        print(f"ERROR: --to must be one of {COLUMN_KEYS}", file=sys.stderr)
        sys.exit(1)

    board = Board.load(TODOS)
    moved = None
    source_col = None
    for key in COLUMN_KEYS:
        cards = board.columns.get(key, [])
        for i, card in enumerate(cards):
            if match in card.title.lower():
                moved = cards.pop(i)
                source_col = key
                break
        if moved:
            break

    if not moved:
        print(f"No card matched: {args.match}", file=sys.stderr)
        sys.exit(1)

    if target == "Done":
        moved.done = True
        moved.completed_date = dt_date.today().isoformat()
    else:
        moved.done = False
        moved.completed_date = None

    board.columns[target].append(moved)
    board.save(TODOS)
    print(f"Moved: {moved.title} ({source_col} → {target})")


def cmd_complete(args: argparse.Namespace) -> None:
    args.to = "Done"
    cmd_move(args)


def cmd_decline(args: argparse.Namespace) -> None:
    match = args.match.strip().lower()
    board = Board.load(TODOS)

    target = None
    for key in ("Review", "Backlog", "To Do"):
        cards = board.columns.get(key, [])
        for i, card in enumerate(cards):
            if match in card.title.lower():
                target = cards.pop(i)
                break
        if target:
            break

    if not target:
        print(f"No card matched: {args.match}", file=sys.stderr)
        sys.exit(1)

    board.save(TODOS)

    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    header = "# Todos Archive\n\n## ❌ Declined\n\n"
    if ARCHIVE.exists():
        text = ARCHIVE.read_text(encoding="utf-8")
        if "## ❌ Declined" not in text:
            text = text.rstrip() + "\n\n## ❌ Declined\n\n"
    else:
        text = header
    target.completed_date = dt_date.today().isoformat()
    text = text.rstrip() + "\n" + target.render() + "\n"
    ARCHIVE.write_text(text, encoding="utf-8")
    print(f"Declined: {target.title}")


def cmd_list(args: argparse.Namespace) -> None:
    board = Board.load(TODOS)
    wanted = [s.strip() for s in (args.status or "To Do,In Progress").split(",")]
    wanted = [w for w in wanted if w in COLUMN_KEYS]
    if not wanted:
        wanted = ["To Do", "In Progress"]

    items: list[tuple[str, Card]] = []
    for key in wanted:
        for card in board.columns.get(key, []):
            items.append((key, card))

    pri_rank = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda it: (pri_rank.get(it[1].priority, 3), it[1].due or "9999-12-31", it[1].title))

    if args.format == "json":
        print(json.dumps([
            {"column": col, "title": c.title, "priority": c.priority,
             "due_date": c.due, "project": c.project}
            for col, c in items
        ], indent=2))
        return

    if args.format == "tsv":
        for col, c in items:
            print("\t".join([col, c.priority, c.due or "", c.project or "", c.title]))
        return

    for col, c in items:
        pri = PRIORITY_EMOJI.get(c.priority, "")
        due = f" [{c.due}]" if c.due else ""
        proj = f" ({c.project})" if c.project else ""
        print(f"[{col}] {c.title} {pri}{due}{proj}".strip())


def cmd_all_titles(args: argparse.Namespace) -> None:
    board = Board.load(TODOS)
    titles = set()
    for cards in board.columns.values():
        for c in cards:
            titles.add(c.title)
    for t in _declined_titles():
        titles.add(t)
    for t in sorted(titles):
        print(t)


def main() -> None:
    parser = argparse.ArgumentParser(description="Read/write the vault Kanban board at vault/todos.md")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p = subparsers.add_parser("propose", help="Add a new card to the Review column (with dedup)")
    p.add_argument("--title", required=True)
    p.add_argument("--priority", choices=["high", "medium", "low"], default="medium")
    p.add_argument("--due", help="ISO date YYYY-MM-DD")
    p.add_argument("--project", help="Project slug (lowercase, no spaces)")
    p.add_argument("--column", help="Override target column (default: Review)")
    p.add_argument("--force", action="store_true", help="Skip dedup + rules and write anyway")
    p.add_argument("--source", help="Informational tag (not written to board)")

    p = subparsers.add_parser("move", help="Move a card matching a title substring to another column")
    p.add_argument("--match", required=True, help="Case-insensitive substring of the card title")
    p.add_argument("--to", required=True, choices=COLUMN_KEYS)

    p = subparsers.add_parser("complete", help="Mark a card as done (shortcut for move --to Done)")
    p.add_argument("--match", required=True)

    p = subparsers.add_parser("decline", help="Move a card to the archive's Declined section")
    p.add_argument("--match", required=True)

    p = subparsers.add_parser("list", help="Emit cards from given columns")
    p.add_argument("--status", default="To Do,In Progress")
    p.add_argument("--format", choices=["simple", "json", "tsv"], default="simple")

    p = subparsers.add_parser("all-titles", help="Print all card titles (including declined) for dedup")

    args = parser.parse_args()
    handlers = {
        "propose": cmd_propose, "move": cmd_move, "complete": cmd_complete,
        "decline": cmd_decline, "list": cmd_list, "all-titles": cmd_all_titles,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
