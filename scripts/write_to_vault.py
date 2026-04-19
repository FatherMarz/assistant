#!/usr/bin/env python3
"""Programmatic vault writer — used by scheduled tasks and ad-hoc Claude sessions.

Writes to the Obsidian vault at `vault/`: facts, people, organizations,
projects, and wikilink connections between them.

Facts are stored as `facts/<category>/<key>.md` — one file per fact — with
frontmatter (`type: fact`, `category`, `key`, `tags`, `updated`).

Usage:
  python3 scripts/write_to_vault.py fact --category context --key last_nudge --value "2026-04-13T12:00"
  python3 scripts/write_to_vault.py person --name "Jane Doe" --role CTO --company Acme
  python3 scripts/write_to_vault.py connect --from "Jane Doe" --relation "works at" --to "Acme" --inverse "employs"
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).parent.parent
VAULT = REPO / "vault"

PEOPLE_DIR = VAULT / "people"
ORGS_DIR = VAULT / "organizations"
PROJECTS_DIR = VAULT / "projects"
FACTS_DIR = VAULT / "facts"

CATEGORY_TO_DIR = {
    "project":       "projects",
    "projects":      "projects",
    "work":          "work",
    "learning":      "learning",
    "family":        "family",
    "context":       "context",
    "daily_context": "context",
    "other":         "other",
}


def slugify(name: str) -> str:
    """Filesystem-safe filename stem — preserves spaces for human-readable wikilinks."""
    name = name.strip()
    name = re.sub(r'[/\\:*?"<>|]', " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def _slug_fact_key(key: str) -> str:
    slug = re.sub(r"[^\w\-]+", "_", key).strip("_")
    return slug or "unnamed"


def _derive_fact_tags(category: str, key: str) -> list[str]:
    """Generic tag inference. Extend in a fork by editing this function."""
    tags = {category}
    kl = key.lower()
    if any(w in kl for w in ("job", "career", "offer")):
        tags.add("career")
    if any(w in kl for w in ("meeting", "agenda", "prep")):
        tags.add("meeting")
    if any(w in kl for w in ("read", "book", "course", "learn")):
        tags.add("learning")
    return sorted(tags)


def _fact_path(category: str, key: str) -> Path:
    cat_dir = CATEGORY_TO_DIR.get(category, "other")
    return FACTS_DIR / cat_dir / (_slug_fact_key(key) + ".md")


def cmd_fact(args: argparse.Namespace) -> None:
    category = args.category.strip()
    key = args.key.strip()
    value = args.value.strip()

    if not category or not key or not value:
        print("ERROR: --category, --key, and --value are required", file=sys.stderr)
        sys.exit(1)

    path = _fact_path(category, key)
    path.parent.mkdir(parents=True, exist_ok=True)

    tags = _derive_fact_tags(category, key)
    updated = datetime.now().isoformat(timespec="minutes")

    lines = [
        "---",
        "type: fact",
        f"category: {category}",
        f"key: {key}",
        f"tags: [{', '.join(tags)}]",
        f"updated: {updated}",
        "---",
        "",
        value,
        "",
        "Up:: [[Facts]]",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"fact written: {path.relative_to(VAULT)}")


def _first_name_alias(name: str) -> str | None:
    parts = name.split()
    if len(parts) > 1:
        return f"[{parts[0]}]"
    return None


def cmd_person(args: argparse.Namespace) -> None:
    PEOPLE_DIR.mkdir(exist_ok=True)
    name = args.name.strip()
    path = PEOPLE_DIR / f"{slugify(name)}.md"

    if not path.exists():
        fm: dict[str, str] = {"type": "person"}
        alias = _first_name_alias(name)
        if alias:
            fm["aliases"] = alias
        for field in ("role", "company", "email", "location", "relationship", "context"):
            val = getattr(args, field, None)
            if val:
                fm[field] = val.strip()

        lines = ["---"]
        for k, v in fm.items():
            lines.append(f"{k}: {v}")
        lines += ["---", "", ""]

        company = (getattr(args, "company", None) or "").strip()
        if company:
            lines += ["## Connections", f"- works at [[{company}]]", "", ""]

        lines += ["Up:: [[People]]", ""]

        path.write_text("\n".join(lines), encoding="utf-8")
        print(f"person created: {path}")
        return

    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        print(f"person exists but no front matter — skipping: {path}")
        return

    end = text.find("---", 3)
    if end == -1:
        print(f"malformed front matter in {path} — skipping")
        return

    fm_block = text[3:end].strip()
    body = text[end + 3:]
    fm_lines = fm_block.splitlines()
    updated_keys: set[str] = set()

    if not any(line.startswith("type:") for line in fm_lines):
        fm_lines.append("type: person")
        updated_keys.add("type")

    alias = _first_name_alias(name)
    if alias and not any(line.startswith("aliases:") for line in fm_lines):
        fm_lines.append(f"aliases: {alias}")
        updated_keys.add("aliases")

    for field in ("role", "company", "email", "location", "relationship", "context"):
        val = getattr(args, field, None)
        if not val:
            continue
        val = val.strip()
        replaced = False
        for i, line in enumerate(fm_lines):
            if line.startswith(f"{field}:"):
                fm_lines[i] = f"{field}: {val}"
                replaced = True
                updated_keys.add(field)
                break
        if not replaced:
            fm_lines.append(f"{field}: {val}")
            updated_keys.add(field)

    new_text = "---\n" + "\n".join(fm_lines) + "\n---" + body
    path.write_text(new_text, encoding="utf-8")
    print(f"person updated ({', '.join(sorted(updated_keys)) or 'no changes'}): {path}")


def _create_entity_note(directory: Path, hub: str, entity_type: str,
                        name: str, description: str | None,
                        extra_fm: dict[str, str]) -> Path:
    directory.mkdir(exist_ok=True)
    path = directory / f"{slugify(name)}.md"
    if path.exists():
        print(f"{entity_type} already exists: {path}")
        return path

    fm: dict[str, str] = {"type": entity_type}
    fm.update(extra_fm)

    lines = ["---"]
    for k, v in fm.items():
        lines.append(f"{k}: {v}")
    lines += ["---", ""]
    if description:
        lines += [description.strip(), ""]
    lines += [f"Up:: [[{hub}]]", ""]

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"{entity_type} created: {path}")
    return path


def cmd_org(args: argparse.Namespace) -> None:
    extra: dict[str, str] = {}
    for field in ("industry", "location", "website"):
        val = getattr(args, field, None)
        if val:
            extra[field] = val.strip()
    _create_entity_note(
        ORGS_DIR, "Organizations", "organization",
        args.name.strip(),
        (args.description or "").strip() or None,
        extra,
    )


def cmd_project(args: argparse.Namespace) -> None:
    extra: dict[str, str] = {}
    for field in ("status", "owner"):
        val = getattr(args, field, None)
        if val:
            extra[field] = val.strip()
    _create_entity_note(
        PROJECTS_DIR, "Projects", "project",
        args.name.strip(),
        (args.description or "").strip() or None,
        extra,
    )


def _find_entity_path(name: str) -> Path | None:
    safe = slugify(name)
    for directory in (PEOPLE_DIR, ORGS_DIR, PROJECTS_DIR):
        candidate = directory / f"{safe}.md"
        if candidate.exists():
            return candidate
    return None


def _add_connection_line(path: Path, line: str) -> bool:
    text = path.read_text(encoding="utf-8")

    section_pattern = re.compile(
        r"(^## Connections\s*\n)((?:.*?\n)*?)(?=^## |\Z)",
        re.MULTILINE,
    )
    match = section_pattern.search(text)

    if match:
        existing_body = match.group(2)
        if line in existing_body.splitlines():
            return False
        lines = [ln for ln in existing_body.splitlines() if ln.strip()]
        lines.append(line)
        lines.sort()
        new_section = match.group(1) + "\n".join(lines) + "\n\n"
        new_text = text[: match.start()] + new_section + text[match.end():]
    else:
        new_text = text.rstrip("\n") + "\n\n## Connections\n" + line + "\n"

    path.write_text(new_text, encoding="utf-8")
    return True


def cmd_connect(args: argparse.Namespace) -> None:
    src_name = args.source.strip()
    rel = args.relation.strip()
    tgt_name = args.target.strip()
    inverse = (args.inverse or "").strip()

    src_path = _find_entity_path(src_name)
    if not src_path:
        print(
            f"ERROR: source entity not found: {src_name}. Create it first "
            f"(write_to_vault.py person/org/project).",
            file=sys.stderr,
        )
        sys.exit(1)

    line = f"- {rel} [[{tgt_name}]]"
    if _add_connection_line(src_path, line):
        print(f"connected: {src_name} --[{rel}]--> {tgt_name}")
    else:
        print(f"already connected: {src_name} --[{rel}]--> {tgt_name}")

    if inverse:
        tgt_path = _find_entity_path(tgt_name)
        if not tgt_path:
            print(f"  (target {tgt_name} not found — inverse skipped)", file=sys.stderr)
            return
        inverse_line = f"- {inverse} [[{src_name}]]"
        if _add_connection_line(tgt_path, inverse_line):
            print(f"connected: {tgt_name} --[{inverse}]--> {src_name}")
        else:
            print(f"already connected: {tgt_name} --[{inverse}]--> {src_name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write to the Obsidian vault at vault/")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_fact = subparsers.add_parser("fact", help="Upsert a fact in the vault")
    p_fact.add_argument("--category", required=True)
    p_fact.add_argument("--key", required=True)
    p_fact.add_argument("--value", required=True)

    p_person = subparsers.add_parser("person", help="Create or update a person note")
    p_person.add_argument("--name", required=True)
    p_person.add_argument("--role")
    p_person.add_argument("--company")
    p_person.add_argument("--email")
    p_person.add_argument("--location")
    p_person.add_argument("--relationship")
    p_person.add_argument("--context")

    p_org = subparsers.add_parser("org", help="Create a stub organization note")
    p_org.add_argument("--name", required=True)
    p_org.add_argument("--description")
    p_org.add_argument("--industry")
    p_org.add_argument("--location")
    p_org.add_argument("--website")

    p_project = subparsers.add_parser("project", help="Create a stub project note")
    p_project.add_argument("--name", required=True)
    p_project.add_argument("--description")
    p_project.add_argument("--status")
    p_project.add_argument("--owner")

    p_connect = subparsers.add_parser("connect",
        help="Add a wikilink relationship to an entity's ## Connections section")
    p_connect.add_argument("--from", dest="source", required=True)
    p_connect.add_argument("--relation", required=True)
    p_connect.add_argument("--to", dest="target", required=True)
    p_connect.add_argument("--inverse")

    args = parser.parse_args()

    commands = {
        "fact": cmd_fact, "person": cmd_person, "org": cmd_org,
        "project": cmd_project, "connect": cmd_connect,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
