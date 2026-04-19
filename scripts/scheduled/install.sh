#!/usr/bin/env bash
# Install (or re-install) scheduled tasks from manifest.yaml.
#
# Detects platform:
#   darwin  → ~/Library/LaunchAgents/com.assistant.<task>.plist
#   linux   → user crontab (via `crontab -e` style rewrite)
#   wsl     → user crontab (same as linux)
#
# Idempotent: safe to re-run after editing manifest.yaml.
#
# Usage:
#   install.sh             # install all tasks flagged enabled=true
#   install.sh <name>      # install one (still must be enabled in manifest)
#   install.sh --uninstall # remove all tasks this installer owns

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MANIFEST="$SCRIPT_DIR/manifest.yaml"
RUN_SH="$SCRIPT_DIR/run.sh"
LABEL_PREFIX="com.assistant"
CRON_MARKER_BEGIN="# >>> assistant scheduled tasks (managed) >>>"
CRON_MARKER_END="# <<< assistant scheduled tasks (managed) <<<"

if [ ! -f "$MANIFEST" ]; then
    echo "manifest missing: $MANIFEST" >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required" >&2
    exit 1
fi

detect_platform() {
    case "$(uname -s)" in
        Darwin) echo "darwin" ;;
        Linux)
            if grep -qi microsoft /proc/version 2>/dev/null; then
                echo "wsl"
            else
                echo "linux"
            fi
            ;;
        *) echo "unsupported"; return 1 ;;
    esac
}

PLATFORM="$(detect_platform)"
if [ "$PLATFORM" = "unsupported" ]; then
    echo "unsupported platform $(uname -s)" >&2
    exit 1
fi

read_manifest() {
    python3 - <<'PY'
import json, os, sys, yaml
path = os.environ["MANIFEST"]
data = yaml.safe_load(open(path)) or {}
tasks = data.get("tasks") or []
out = []
for t in tasks:
    if not t.get("enabled"):
        continue
    entry = {
        "name": t["name"],
        "hour": t.get("hour"),
        "minute": t.get("minute", 0),
        "days_of_week": t.get("days_of_week") or [1,2,3,4,5,6,7],
        "cron": t.get("cron"),
        "every_minutes": t.get("every_minutes"),
        "model": t.get("model", "sonnet"),
        "timeout_secs": t.get("timeout_secs", 600),
    }
    out.append(entry)
print(json.dumps(out))
PY
}

export MANIFEST RUN_SH LABEL_PREFIX

# ---------------------------------------------------------------------------
# macOS: launchd plist
# ---------------------------------------------------------------------------
render_plist() {
    local name="$1"
    local hour="$2"
    local minute="$3"
    local days_csv="$4"       # "1,2,3,4,5" — ISO weekday (1=Mon)
    local cron_expr="$5"
    local every_minutes="$6"
    local dest="$7"

    python3 - "$name" "$hour" "$minute" "$days_csv" "$cron_expr" "$every_minutes" "$dest" <<'PY'
import os, sys
name, hour, minute, days_csv, cron_expr, every_minutes, dest = sys.argv[1:]
repo = os.environ["REPO_ROOT"]
run_sh = os.environ["RUN_SH"]
label_prefix = os.environ["LABEL_PREFIX"]
label = f"{label_prefix}.{name}"

plist_head = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{run_sh}</string>
        <string>{name}</string>
    </array>
"""

plist_tail = f"""    <key>StandardOutPath</key>
    <string>{repo}/logs/scheduled/launchd-{name}.log</string>
    <key>StandardErrorPath</key>
    <string>{repo}/logs/scheduled/launchd-{name}.log</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
"""

schedule = ""
if every_minutes and every_minutes != "None":
    schedule = f"    <key>StartInterval</key>\n    <integer>{int(every_minutes)*60}</integer>\n"
elif cron_expr and cron_expr != "None":
    # Minimal mapping: parse "MIN HOUR * * DOW" form; launchd needs a dict list.
    parts = cron_expr.split()
    mn, hr = parts[0], parts[1]
    dow = parts[4] if len(parts) >= 5 else "*"
    entries = []
    if mn.isdigit() and hr.isdigit():
        if dow == "*":
            entries.append(f"        <dict>\n            <key>Hour</key><integer>{int(hr)}</integer>\n            <key>Minute</key><integer>{int(mn)}</integer>\n        </dict>")
        else:
            for d in dow.split(","):
                d = d.strip()
                if d.isdigit():
                    # cron DOW: 0=Sun..6=Sat; launchd Weekday: 0=Sun..6=Sat too
                    entries.append(f"        <dict>\n            <key>Weekday</key><integer>{int(d)}</integer>\n            <key>Hour</key><integer>{int(hr)}</integer>\n            <key>Minute</key><integer>{int(mn)}</integer>\n        </dict>")
    if entries:
        schedule = "    <key>StartCalendarInterval</key>\n    <array>\n" + "\n".join(entries) + "\n    </array>\n"
    else:
        # Fallback: every 15 minutes
        schedule = "    <key>StartInterval</key>\n    <integer>900</integer>\n"
elif hour and hour != "None":
    entries = []
    for d in days_csv.split(","):
        d = d.strip()
        if not d:
            continue
        # ISO weekday 1=Mon..7=Sun → launchd Weekday 0=Sun..6=Sat
        iso = int(d)
        launchd_dow = 0 if iso == 7 else iso
        entries.append(
            f"        <dict>\n"
            f"            <key>Weekday</key><integer>{launchd_dow}</integer>\n"
            f"            <key>Hour</key><integer>{int(hour)}</integer>\n"
            f"            <key>Minute</key><integer>{int(minute)}</integer>\n"
            f"        </dict>"
        )
    schedule = "    <key>StartCalendarInterval</key>\n    <array>\n" + "\n".join(entries) + "\n    </array>\n"

open(dest, "w").write(plist_head + schedule + plist_tail)
PY
}

install_darwin() {
    local agents_dir="$HOME/Library/LaunchAgents"
    mkdir -p "$agents_dir"
    local uid_gui="gui/$(id -u)"

    for entry in $(read_manifest | python3 -c 'import json,sys; print("\n".join(json.dumps(x) for x in json.load(sys.stdin)))'); do
        python3 - "$entry" "$agents_dir" <<'PY'
import json, os, subprocess, sys
entry = json.loads(sys.argv[1])
agents_dir = sys.argv[2]
name = entry["name"]
label = f"{os.environ['LABEL_PREFIX']}.{name}"
plist = os.path.join(agents_dir, f"{label}.plist")
# emit via shell-side render_plist
days_csv = ",".join(str(d) for d in entry["days_of_week"])
cron_expr = entry.get("cron") or "None"
every_min = entry.get("every_minutes") or "None"
hour = entry.get("hour") if entry.get("hour") is not None else "None"
subprocess.run([
    "bash", "-c",
    "render_plist " + " ".join([
        f"'{name}'", f"'{hour}'", f"'{entry.get('minute',0)}'",
        f"'{days_csv}'", f"'{cron_expr}'", f"'{every_min}'", f"'{plist}'",
    ])
], check=True, env={**os.environ})

# lint + load
subprocess.run(["plutil", "-lint", plist], check=True)
subprocess.run(["launchctl", "bootout", f"{os.environ['HOME']}/Library/LaunchAgents/{label}.plist"], check=False)
subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", plist], check=False)
print(f"{name}: installed ({plist})")
PY
    done
}

# ---------------------------------------------------------------------------
# Linux / WSL: user crontab
# ---------------------------------------------------------------------------
build_crontab_block() {
    python3 - <<'PY'
import json, os, subprocess
manifest_path = os.environ["MANIFEST"]
run_sh = os.environ["RUN_SH"]
import yaml
data = yaml.safe_load(open(manifest_path)) or {}
lines = [os.environ["CRON_MARKER_BEGIN"]]
for t in data.get("tasks") or []:
    if not t.get("enabled"):
        continue
    name = t["name"]
    if t.get("cron"):
        cron = t["cron"]
    elif t.get("every_minutes"):
        cron = f"*/{int(t['every_minutes'])} * * * *"
    else:
        mn = int(t.get("minute", 0))
        hr = int(t.get("hour", 9))
        dow_iso = t.get("days_of_week") or [1,2,3,4,5,6,7]
        # cron DOW: 0=Sun..6=Sat; ISO: 1=Mon..7=Sun
        dow = sorted(set(0 if d == 7 else d for d in dow_iso))
        dow_csv = ",".join(str(d) for d in dow) if dow else "*"
        cron = f"{mn} {hr} * * {dow_csv}"
    lines.append(f"{cron} {run_sh} {name}  # assistant:{name}")
lines.append(os.environ["CRON_MARKER_END"])
print("\n".join(lines))
PY
}

install_cron() {
    export CRON_MARKER_BEGIN CRON_MARKER_END
    local existing
    existing="$(crontab -l 2>/dev/null || true)"

    # Strip any existing managed block
    local stripped
    stripped="$(python3 - "$existing" <<'PY'
import os, sys
text = sys.argv[1]
begin = os.environ["CRON_MARKER_BEGIN"]
end = os.environ["CRON_MARKER_END"]
if begin in text and end in text:
    pre, _, rest = text.partition(begin)
    _, _, post = rest.partition(end)
    text = (pre.rstrip("\n") + "\n" + post.lstrip("\n")).strip("\n")
print(text)
PY
)"

    local block
    block="$(build_crontab_block)"

    local new_crontab
    if [ -n "$stripped" ]; then
        new_crontab="$stripped"$'\n\n'"$block"$'\n'
    else
        new_crontab="$block"$'\n'
    fi

    printf '%s' "$new_crontab" | crontab -
    echo "Installed $(echo "$block" | grep -c '^[0-9\*]') scheduled tasks in user crontab."
    echo "Run 'crontab -l' to review."
}

uninstall() {
    case "$PLATFORM" in
        darwin)
            for p in "$HOME/Library/LaunchAgents/${LABEL_PREFIX}."*.plist; do
                [ -f "$p" ] || continue
                launchctl bootout "$HOME/Library/LaunchAgents/$(basename "$p")" 2>/dev/null || true
                rm -f "$p"
                echo "removed $p"
            done
            ;;
        linux|wsl)
            local existing stripped
            existing="$(crontab -l 2>/dev/null || true)"
            stripped="$(python3 - "$existing" <<PY
import os, sys
text = sys.argv[1]
begin = "$CRON_MARKER_BEGIN"
end = "$CRON_MARKER_END"
if begin in text and end in text:
    pre, _, rest = text.partition(begin)
    _, _, post = rest.partition(end)
    text = (pre.rstrip("\n") + "\n" + post.lstrip("\n")).strip("\n")
print(text)
PY
)"
            printf '%s\n' "$stripped" | crontab -
            echo "removed managed block from crontab"
            ;;
    esac
}

case "${1:-}" in
    --uninstall|uninstall)
        uninstall
        exit 0
        ;;
esac

echo "platform: $PLATFORM"
case "$PLATFORM" in
    darwin) export REPO_ROOT; install_darwin ;;
    linux|wsl) install_cron ;;
esac

echo ""
echo "Done. Logs → $REPO_ROOT/logs/scheduled/"
