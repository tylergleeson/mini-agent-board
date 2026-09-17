#!/usr/bin/env python3
"""Merge status/*.json into docs/status.json and push it to GitHub Pages.

Run by launchd every 15 minutes (launchd/com.tyler.mini-agent-board.publish.plist)
or by hand: ``python3 publish.py [--dry-run] [--no-push]``.

Guarantees
----------
* Idempotent: if the merged content (ignoring ``updated``) matches what is already
  in docs/status.json, nothing is written or committed.
* Only whitelisted keys are copied, strings are truncated, and anything that looks
  like a home-directory path is scrubbed — the output is served from a public repo.
* An agent whose heartbeat is older than 10 minutes is published with
  ``state: "stale"`` (its original state is kept in ``last_state``).
* Never exits non-zero for a failed commit or push; launchd must keep scheduling it.

Output contract (docs/status.json)::

    {"updated": <unix>,
     "agents": [ {agent, display_name, state, task, progress, started, heartbeat,
                  completed_today, last_result, note, last_state?, stale} ... ],
     "totals": {"completed_today": n, "working": n, "agents": n}}
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent
STATUS_DIR = Path(os.environ.get("MAB_STATUS_DIR", ROOT / "status"))
OUT = ROOT / "docs" / "status.json"
STALE_AFTER = 10 * 60  # seconds without a heartbeat
STATES = {"working", "idle", "blocked", "done", "error"}
MAX_STR = 140
HOME = str(Path.home())


def log(msg: str) -> None:
    print(f"{datetime.now(TZ).strftime('%Y-%m-%d %-I:%M:%S %p')} {msg}", flush=True)


def scrub(s: object) -> str:
    s = "" if s is None else str(s)
    if HOME and HOME in s:
        s = s.replace(HOME, "~")
    s = " ".join(s.split())
    return s[: MAX_STR - 1] + "…" if len(s) > MAX_STR else s


def as_int(v: object, default: int = 0) -> int:
    try:
        return int(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def normalize(raw: dict, now: int) -> dict | None:
    agent = scrub(raw.get("agent")).lower()
    if not agent:
        return None
    state = str(raw.get("state", "idle")).lower()
    if state not in STATES:
        state = "idle"
    progress = raw.get("progress")
    try:
        progress = None if progress is None else round(max(0.0, min(1.0, float(progress))), 3)
    except (TypeError, ValueError):
        progress = None
    heartbeat = as_int(raw.get("heartbeat"), 0)
    out = {
        "agent": agent,
        "display_name": scrub(raw.get("display_name") or agent.title()),
        "state": state,
        "task": scrub(raw.get("task")),
        "progress": progress,
        "started": as_int(raw.get("started"), heartbeat),
        "heartbeat": heartbeat,
        "completed_today": max(0, as_int(raw.get("completed_today"))),
        "last_result": scrub(raw.get("last_result")),
        "note": scrub(raw.get("note")),
        "stale": False,
    }
    if now - heartbeat > STALE_AFTER:
        out["stale"] = True
        out["last_state"] = state
        out["state"] = "stale"
        out["progress"] = None
        mins = (now - heartbeat) // 60
        out["note"] = f"no heartbeat for {mins} min" if heartbeat else "no heartbeat"
    return out


def merge(now: int) -> dict:
    agents = []
    for p in sorted(STATUS_DIR.glob("*.json")):
        try:
            raw = json.loads(p.read_text())
        except (OSError, ValueError) as e:
            log(f"skip {p.name}: {e}")
            continue
        if not isinstance(raw, dict):
            continue
        a = normalize(raw, now)
        if a:
            agents.append(a)
    agents.sort(key=lambda a: a["display_name"].lower())
    return {
        "updated": now,
        "agents": agents,
        "totals": {
            "completed_today": sum(a["completed_today"] for a in agents),
            "working": sum(1 for a in agents if a["state"] == "working"),
            "agents": len(agents),
        },
    }


def unchanged(new: dict) -> bool:
    try:
        old = json.loads(OUT.read_text())
    except (OSError, ValueError):
        return False
    strip = lambda d: {k: v for k, v in d.items() if k != "updated"}  # noqa: E731
    return strip(old) == strip(new)


def git(*args: str, timeout: int = 90) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=timeout)


def commit_and_push(now: int, push: bool) -> None:
    rel = OUT.relative_to(ROOT).as_posix()
    r = git("add", "--", rel)
    if r.returncode:
        log(f"git add failed: {r.stderr.strip()}")
        return
    stamp = datetime.fromtimestamp(now, TZ).strftime("%Y-%m-%d %-I:%M %p")
    r = git("commit", "-q", "-m", f"status: {stamp}", "--", rel)
    if r.returncode:
        if "nothing to commit" in (r.stdout + r.stderr):
            log("nothing to commit")
        else:
            log(f"git commit failed: {r.stderr.strip() or r.stdout.strip()}")
        return
    log(f"committed status: {stamp}")
    if not push:
        return
    r = git("push", "-q", timeout=120)
    if r.returncode == 0:
        log("pushed")
        return
    log(f"push failed ({r.stderr.strip()[:200]}); trying pull --rebase")
    r = git("pull", "-q", "--rebase", "--autostash", timeout=120)
    if r.returncode:
        log(f"pull --rebase failed: {r.stderr.strip()[:200]}")
        git("rebase", "--abort")
        return
    r = git("push", "-q", timeout=120)
    log("pushed after rebase" if r.returncode == 0 else f"push still failing: {r.stderr.strip()[:200]}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print the merged JSON, write nothing")
    ap.add_argument("--no-push", action="store_true", help="write and commit but do not push")
    ap.add_argument("--force", action="store_true", help="write even if unchanged")
    args = ap.parse_args()

    now = int(time.time())
    try:
        merged = merge(now)
    except Exception as e:  # noqa: BLE001
        log(f"merge failed: {e!r}")
        return 0
    if args.dry_run:
        print(json.dumps(merged, indent=2, ensure_ascii=False))
        return 0
    if not args.force and unchanged(merged):
        log(f"unchanged ({len(merged['agents'])} agents); not writing")
        return 0
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(merged, indent=1, ensure_ascii=False) + "\n")
        os.replace(tmp, OUT)
        log(f"wrote {OUT.relative_to(ROOT)}: {len(merged['agents'])} agents, "
            f"{merged['totals']['completed_today']} done today, {merged['totals']['working']} working")
    except OSError as e:
        log(f"write failed: {e}")
        return 0
    try:
        commit_and_push(now, push=not args.no_push)
    except Exception as e:  # noqa: BLE001  (timeouts, missing git, etc.)
        log(f"git step failed: {e!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
