#!/usr/bin/env python3
"""Onboarding setup — takes an answers JSON file, turns this template repo into
a personalized assistant.

Invoked by the `onboard-assistant` skill after it's collected answers from
the user, but runnable standalone too:

    python3 scripts/setup.py --profile /tmp/assistant-onboarding.json

The profile JSON is expected to have keys (all optional except the first two):
    USER_NAME, ASSISTANT_NAME, ASSISTANT_NAME_SLUG, PRONOUN_SUBJ/_OBJ/_POSS/_REFL,
    PEOPLE (list of {name, relationship, notes}), PARTNER_NAME,
    USER_ROLE, USER_EMPLOYER, TIMEZONE, WORK_HOURS, USER_TOOLS,
    PRIORITIES (list), OFF_HOURS_RULE, COMMS_STYLE, BRIEFING_STYLE,
    TICKETING_SYSTEM, USE_PUSHOVER, USE_GMAIL, USE_CALENDAR, USE_SMART_CONNECTIONS,
    SCHEDULED_TASKS ({task_name: {enabled, hour, minute}, ...})

This script is idempotent — safe to re-run after editing the profile.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).parent.parent.resolve()

PRONOUN_PRESETS = {
    "he/him":   {"PRONOUN_SUBJ": "he",   "PRONOUN_OBJ": "him",   "PRONOUN_POSS": "his",   "PRONOUN_REFL": "himself"},
    "she/her":  {"PRONOUN_SUBJ": "she",  "PRONOUN_OBJ": "her",   "PRONOUN_POSS": "her",   "PRONOUN_REFL": "herself"},
    "they/them":{"PRONOUN_SUBJ": "they", "PRONOUN_OBJ": "them",  "PRONOUN_POSS": "their", "PRONOUN_REFL": "themself"},
}


def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s).strip("-")
    return s or "assistant"


def expand_pronouns(profile: dict) -> None:
    """If PRONOUN_SUBJ etc. aren't set but a preset key was given, fill them in."""
    preset = profile.pop("PRONOUNS", None)
    if preset and preset in PRONOUN_PRESETS:
        for k, v in PRONOUN_PRESETS[preset].items():
            profile.setdefault(k, v)
    profile.setdefault("PRONOUN_SUBJ", "they")
    profile.setdefault("PRONOUN_OBJ", "them")
    profile.setdefault("PRONOUN_POSS", "their")
    profile.setdefault("PRONOUN_REFL", "themself")


def default_context(profile: dict) -> dict:
    """Build the full substitution context from the profile."""
    now = datetime.now()
    ctx = {
        "USER_NAME": profile.get("USER_NAME", "User"),
        "ASSISTANT_NAME": profile.get("ASSISTANT_NAME", "Assistant"),
        "ASSISTANT_NAME_SLUG": profile.get("ASSISTANT_NAME_SLUG") or slugify(profile.get("ASSISTANT_NAME", "assistant")),
        "ASSISTANT_REPO": str(REPO),
        "USER_ROLE": profile.get("USER_ROLE", ""),
        "USER_EMPLOYER": profile.get("USER_EMPLOYER", ""),
        "TIMEZONE": profile.get("TIMEZONE", "UTC"),
        "WORK_HOURS": profile.get("WORK_HOURS", ""),
        "USER_TOOLS": profile.get("USER_TOOLS", ""),
        "OFF_HOURS_RULE": profile.get("OFF_HOURS_RULE") or "(none set)",
        "COMMS_STYLE": profile.get("COMMS_STYLE", ""),
        "BRIEFING_STYLE": profile.get("BRIEFING_STYLE", ""),
        "PARTNER_NAME": profile.get("PARTNER_NAME") or "",
        "CURRENT_YEAR": str(now.year),
        "CURRENT_QUARTER": f"Q{(now.month - 1) // 3 + 1} {now.year}",
    }

    expand_pronouns(profile)
    for k in ("PRONOUN_SUBJ", "PRONOUN_OBJ", "PRONOUN_POSS", "PRONOUN_REFL"):
        ctx[k] = profile[k]

    # People list — fill the first few numbered placeholders in USER.md
    people = profile.get("PEOPLE") or []
    for i, p in enumerate(people[:5], start=1):
        ctx[f"PERSON_{i}_NAME"] = p.get("name", "")
        ctx[f"PERSON_{i}_RELATIONSHIP"] = p.get("relationship", "")
        ctx[f"PERSON_{i}_NOTES"] = p.get("notes", "")

    # Priorities
    priorities = profile.get("PRIORITIES") or []
    for i, pri in enumerate(priorities[:4], start=1):
        ctx[f"PRIORITY_{i}"] = pri

    # Goals / projects / strategies / beliefs — leave as placeholders unless provided
    for k in ("MISSION", "GOAL_1", "GOAL_2", "GOAL_3",
              "ANNUAL_GOAL_1", "ANNUAL_GOAL_2",
              "PROJECT_1_NAME", "PROJECT_1_SLUG", "PROJECT_1_WHY", "PROJECT_1_FOCUS",
              "PROJECT_2_NAME", "PROJECT_2_SLUG", "PROJECT_2_WHY",
              "BACKLOG_1", "STRATEGY_1", "STRATEGY_2", "STRATEGY_3",
              "BELIEF_1", "BELIEF_2", "BELIEF_3",
              "IMPORTANT_DATE_1"):
        ctx.setdefault(k, profile.get(k, ""))

    return ctx


def render(text: str, ctx: dict) -> str:
    """Substitute {{KEY}} tokens using ctx. Unknown keys are left as-is (so files
    without required values stay obvious when you re-open them)."""
    def repl(m: re.Match) -> str:
        key = m.group(1)
        return ctx.get(key, m.group(0))
    return re.sub(r"\{\{([A-Z_0-9]+)\}\}", repl, text)


def render_file(path: Path, ctx: dict) -> None:
    text = path.read_text(encoding="utf-8")
    new = render(text, ctx)
    if new != text:
        path.write_text(new, encoding="utf-8")
        print(f"  rendered: {path.relative_to(REPO)}")


def render_tree(root: Path, ctx: dict, patterns=("*.md", "*.yaml")) -> None:
    for pat in patterns:
        for path in root.rglob(pat):
            if ".venv" in path.parts or "node_modules" in path.parts:
                continue
            render_file(path, ctx)


def rename_skill_dirs(ctx: dict) -> tuple[Path, Path]:
    slug = ctx["ASSISTANT_NAME_SLUG"]
    src_persona = REPO / "skills" / "assistant-template"
    src_vault = REPO / "skills" / "assistant-vault-template"
    dst_persona = REPO / "skills" / slug
    dst_vault = REPO / "skills" / f"{slug}-vault"

    if src_persona.exists():
        if dst_persona.exists():
            shutil.rmtree(dst_persona)
        shutil.move(str(src_persona), str(dst_persona))
        print(f"renamed: skills/assistant-template → skills/{slug}")
    if src_vault.exists():
        if dst_vault.exists():
            shutil.rmtree(dst_vault)
        shutil.move(str(src_vault), str(dst_vault))
        print(f"renamed: skills/assistant-vault-template → skills/{slug}-vault")

    # Render any remaining placeholders inside the renamed skills
    render_tree(dst_persona, ctx)
    render_tree(dst_vault, ctx)
    return dst_persona, dst_vault


def install_skills_to_claude(persona_dir: Path, vault_dir: Path, ctx: dict) -> None:
    """Symlink or copy the skills into ~/.claude/skills/."""
    claude_skills = Path.home() / ".claude" / "skills"
    claude_skills.mkdir(parents=True, exist_ok=True)

    slug = ctx["ASSISTANT_NAME_SLUG"]
    for src, name in [(persona_dir, slug), (vault_dir, f"{slug}-vault")]:
        dst = claude_skills / name
        if dst.exists() or dst.is_symlink():
            if dst.is_symlink() or dst.is_dir():
                if dst.is_symlink():
                    dst.unlink()
                else:
                    shutil.rmtree(dst)
        # Symlink is simpler — edits in the repo show up live in Claude Code.
        try:
            dst.symlink_to(src, target_is_directory=True)
            print(f"linked: ~/.claude/skills/{name} → {src}")
        except OSError:
            shutil.copytree(src, dst)
            print(f"copied: ~/.claude/skills/{name} ← {src}")


def update_manifest(profile: dict) -> int:
    """Flip the enabled flags in manifest.yaml based on SCHEDULED_TASKS."""
    try:
        import yaml
    except ImportError:
        print("ERROR: PyYAML is required. Install: pip install pyyaml", file=sys.stderr)
        sys.exit(1)

    manifest_path = REPO / "scripts" / "scheduled" / "manifest.yaml"
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    tasks_cfg = profile.get("SCHEDULED_TASKS") or {}
    enabled_count = 0
    for t in data.get("tasks") or []:
        name = t.get("name")
        if name in tasks_cfg:
            cfg = tasks_cfg[name] or {}
            t["enabled"] = bool(cfg.get("enabled"))
            if cfg.get("hour") is not None:
                t["hour"] = int(cfg["hour"])
            if cfg.get("minute") is not None:
                t["minute"] = int(cfg["minute"])
            if t["enabled"]:
                enabled_count += 1

    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    print(f"manifest updated: {enabled_count} tasks enabled")
    return enabled_count


def write_env(profile: dict) -> None:
    env_path = REPO / ".env"
    if env_path.exists():
        print(f"skipped .env (already exists — merge manually if needed)")
        return
    example = REPO / ".env.example"
    text = example.read_text(encoding="utf-8") if example.exists() else ""

    # Fill TZ if provided
    tz = profile.get("TIMEZONE")
    if tz:
        text = re.sub(r"^TZ=.*$", f"TZ={tz}", text, flags=re.MULTILINE)
    # Ticketing system
    ts = (profile.get("TICKETING_SYSTEM") or "none").lower()
    text = re.sub(r"^TICKETING_SYSTEM=.*$", f"TICKETING_SYSTEM={ts}", text, flags=re.MULTILINE)

    env_path.write_text(text, encoding="utf-8")
    print(f"wrote .env (fill in secrets manually — Pushover keys, etc.)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", required=True, help="Path to answers JSON")
    ap.add_argument("--skip-scheduler-install", action="store_true",
                    help="Skip running scripts/scheduled/install.sh at the end")
    ap.add_argument("--skip-claude-link", action="store_true",
                    help="Skip linking skills into ~/.claude/skills/")
    args = ap.parse_args()

    profile_path = Path(args.profile).expanduser().resolve()
    if not profile_path.exists():
        print(f"profile not found: {profile_path}", file=sys.stderr)
        sys.exit(1)

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if "ASSISTANT_NAME" not in profile or "USER_NAME" not in profile:
        print("profile must include USER_NAME and ASSISTANT_NAME", file=sys.stderr)
        sys.exit(1)

    ctx = default_context(profile)
    print(f"setting up assistant '{ctx['ASSISTANT_NAME']}' for {ctx['USER_NAME']}")
    print(f"repo: {REPO}")
    print("")

    # 1. Render config/ templates
    print("rendering config/ ...")
    render_tree(REPO / "config", ctx)

    # 2. Render vault hub notes (they contain {{ASSISTANT_NAME}}, {{USER_NAME}})
    print("rendering vault/ hub notes ...")
    render_tree(REPO / "vault", ctx, patterns=("*.md",))

    # 3. Render scheduled task prompts
    print("rendering scripts/scheduled/prompts/ ...")
    render_tree(REPO / "scripts" / "scheduled" / "prompts", ctx)

    # 4. Rename + render the persona and vault skills
    print("renaming + rendering skills ...")
    persona_dir, vault_dir = rename_skill_dirs(ctx)

    # 5. Install skills into ~/.claude/skills/
    if not args.skip_claude_link:
        print("installing skills into ~/.claude/skills/ ...")
        install_skills_to_claude(persona_dir, vault_dir, ctx)

    # 6. Update manifest + write .env
    enabled_count = update_manifest(profile)
    write_env(profile)

    # 7. Install scheduled tasks
    if enabled_count > 0 and not args.skip_scheduler_install:
        install_sh = REPO / "scripts" / "scheduled" / "install.sh"
        print(f"\nrunning {install_sh.relative_to(REPO)} ...")
        result = subprocess.run(["bash", str(install_sh)], cwd=str(REPO))
        if result.returncode != 0:
            print(f"install.sh exited {result.returncode} — review output above.", file=sys.stderr)

    print("\n" + "=" * 60)
    print(f"Done. Your assistant '{ctx['ASSISTANT_NAME']}' is set up.")
    print(f"Type /{ctx['ASSISTANT_NAME_SLUG']} in any Claude Code session to activate.")
    print("=" * 60)


if __name__ == "__main__":
    main()
