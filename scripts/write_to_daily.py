#!/usr/bin/env python3
"""Idempotent section upsert for the daily note (vault/daily/YYYY-MM-DD.md).

Scheduled tasks output markdown; this script handles file I/O, section placement,
and canonical ordering. Sections not listed in the config still get preserved
and appended at the end so nothing is lost.

Section configuration lives in `config/daily_sections.yaml` (loaded at import).
If the file is absent, a minimal default is used (Morning, Midday, Meeting Prep,
Evening). Add or remove sections there to customize this assistant's daily
rhythm without touching Python.

Usage:
  python3 scripts/write_to_daily.py section \\
    --date 2026-04-14 \\
    --key "Morning" \\
    --content "$(cat /tmp/morning.md)"

  # Or via stdin for multiline content:
  cat /tmp/morning.md | python3 scripts/write_to_daily.py section --date 2026-04-14 --key "Morning"
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date as dt_date
from pathlib import Path

REPO = Path(__file__).parent.parent
VAULT = REPO / "vault"
DAILY_DIR = VAULT / "daily"
SECTIONS_CONFIG = REPO / "config" / "daily_sections.yaml"

DEFAULT_SECTIONS: list[tuple[str, str, str]] = [
    ("Morning",      "☀️ Morning",      "morning-briefing"),
    ("Midday",       "🔔 Midday",       "midday-checkpoint"),
    ("Meeting Prep", "Meeting Prep",    "meeting-prep"),
    ("Evening",      "🌙 Evening",      "daily-journal"),
]


def _load_sections() -> list[tuple[str, str, str]]:
    """Return [(key, title, owner), ...] from YAML if present, else defaults."""
    if not SECTIONS_CONFIG.exists():
        return list(DEFAULT_SECTIONS)
    try:
        import yaml  # PyYAML, optional
    except ImportError:
        print(
            f"WARN: PyYAML not installed — using default daily sections. "
            f"Run `pip install pyyaml` to enable {SECTIONS_CONFIG.name}.",
            file=sys.stderr,
        )
        return list(DEFAULT_SECTIONS)

    data = yaml.safe_load(SECTIONS_CONFIG.read_text(encoding="utf-8")) or {}
    rows = data.get("sections") or []
    out: list[tuple[str, str, str]] = []
    for row in rows:
        key = (row.get("key") or "").strip()
        title = (row.get("title") or key).strip()
        owner = (row.get("owner") or "").strip()
        if key:
            out.append((key, title, owner))
    return out or list(DEFAULT_SECTIONS)


_SECTIONS = _load_sections()
SECTIONS: dict[str, tuple[str, str]] = {k: (t, o) for k, t, o in _SECTIONS}
CANONICAL_ORDER = [k for k, _, _ in _SECTIONS]


def canonical_heading(key: str) -> str:
    return SECTIONS[key][0] if key in SECTIONS else key


def daily_path(date_str: str | None) -> Path:
    iso = date_str or dt_date.today().isoformat()
    return DAILY_DIR / f"{iso}.md"


def file_title(iso_date: str) -> str:
    """e.g. 'Tue Apr 14' from 2026-04-14."""
    d = dt_date.fromisoformat(iso_date)
    return d.strftime("# %a %b %-d")


# ---------------------------------------------------------------------------
# Parse existing file into (title_line, sections_dict)
# ---------------------------------------------------------------------------

def parse_daily(text: str) -> tuple[str | None, dict[str, str]]:
    """Return (title_line or None, {heading_line: body_text})."""
    text = text.lstrip("\n")
    title = None
    rest = text

    if rest.startswith("# "):
        nl = rest.find("\n")
        if nl == -1:
            title = rest.rstrip()
            rest = ""
        else:
            title = rest[:nl].rstrip()
            rest = rest[nl + 1:]

    sections: dict[str, str] = {}
    current_heading: str | None = None
    buf: list[str] = []
    for line in rest.splitlines():
        if line.startswith("## "):
            if current_heading is not None:
                sections[current_heading] = "\n".join(buf).rstrip("\n")
            current_heading = line.rstrip()
            buf = []
        else:
            if current_heading is None:
                if title is None:
                    title = line.rstrip()
            else:
                buf.append(line)
    if current_heading is not None:
        sections[current_heading] = "\n".join(buf).rstrip("\n")

    return title, sections


def heading_to_key(heading_line: str) -> str:
    stripped = heading_line[3:].strip() if heading_line.startswith("## ") else heading_line
    for key, (canonical, _owner) in SECTIONS.items():
        if stripped == canonical:
            return key
    return stripped


def render_daily(iso_date: str, sections: dict[str, str]) -> str:
    title = file_title(iso_date)
    parts: list[str] = [title, ""]

    keys_in_order: list[str] = []
    for canonical_key in CANONICAL_ORDER:
        if canonical_key in sections and sections[canonical_key].strip():
            keys_in_order.append(canonical_key)
    for key in sections:
        if key not in CANONICAL_ORDER and sections[key].strip() and key not in keys_in_order:
            keys_in_order.append(key)

    for key in keys_in_order:
        heading = f"## {canonical_heading(key)}"
        body = sections[key].strip("\n")
        parts.append(heading)
        if body:
            parts.append(body)
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_section(args: argparse.Namespace) -> None:
    date_str = args.date or dt_date.today().isoformat()
    key = args.key.strip()

    content = args.content if args.content is not None else sys.stdin.read()

    if not content.strip() and not args.allow_empty:
        print(f"ERROR: empty content for section '{key}' (pass --allow-empty to clear)", file=sys.stderr)
        sys.exit(1)

    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    path = daily_path(date_str)

    if path.exists():
        existing = path.read_text(encoding="utf-8")
        _title, sections_by_heading = parse_daily(existing)
        sections: dict[str, str] = {}
        for heading, body in sections_by_heading.items():
            sections[heading_to_key(heading)] = body
    else:
        sections = {}

    sections[key] = content.rstrip("\n")
    path.write_text(render_daily(date_str, sections), encoding="utf-8")
    print(f"upserted '{key}' in {path.relative_to(VAULT.parent)}")


def cmd_show(args: argparse.Namespace) -> None:
    path = daily_path(args.date)
    if not path.exists():
        print(f"(no file: {path.name})")
        return
    print(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Upsert sections into vault/daily/YYYY-MM-DD.md")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_section = subparsers.add_parser("section", help="Upsert a single section")
    p_section.add_argument("--date", help="ISO date (default: today)")
    p_section.add_argument("--key", required=True,
                           help="Section key (one of: " + ", ".join(CANONICAL_ORDER) + ")")
    p_section.add_argument("--content", help="Section body (omit to read from stdin)")
    p_section.add_argument("--allow-empty", action="store_true",
                           help="Write even if content is empty (effectively clears the section)")

    p_show = subparsers.add_parser("show", help="Print the daily file for a given date")
    p_show.add_argument("--date", help="ISO date (default: today)")

    args = parser.parse_args()
    commands = {"section": cmd_section, "show": cmd_show}
    commands[args.command](args)


if __name__ == "__main__":
    main()
