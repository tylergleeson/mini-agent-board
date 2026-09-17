# mini-agent-board

A status board for a crew of software-design agents running on a Mac Mini, shown on a
Seeed **reTerminal E1002** e-paper display (7.3" color, 800×480) through SenseCraft HMI,
and on any phone through GitHub Pages.

```
Mac Mini                             GitHub Pages                    Seeed cloud            E1002
agents write status/<agent>.json  →  docs/status.json  →  SenseCraft `data` widgets  →  rendered bitmap
agents/run_agents.py (rich TUI)      publish.py (launchd, 15 min)     pull the JSON          pulled by display
```

The display never renders anything itself. Seeed's cloud renders the layout, fetching every
data widget from a public URL, so the feed lives on GitHub Pages:

```
https://tylergleeson.github.io/mini-agent-board/status.json    ← feed (SenseCraft + phone board)
https://tylergleeson.github.io/mini-agent-board/               ← human-readable board
```

Because the repo is public, `docs/status.json` never contains hostnames, IPs, tokens or
paths under `$HOME` (`publish.py` whitelists keys and scrubs strings).

## Setup on the Mini

```sh
git clone https://github.com/tylergleeson/mini-agent-board.git ~/projects/mini-agent-board
cd ~/projects/mini-agent-board
./bootstrap.sh
```

`bootstrap.sh` checks `python3` (3.11+), `git`, `gh auth status`; creates `.venv` and installs
`rich`; makes the first commit and push if needed; enables GitHub Pages (`main`, `/docs`) via
`gh api` or tells you where to click; renders the two launchd plists into
`~/Library/LaunchAgents` and loads them; then prints the feed URL. Re-running it is safe.

What ends up running:

| launchd job | what | cadence | log |
|---|---|---|---|
| `com.tyler.mini-agent-board.agents` | `agents/run_agents.py --headless` | always (KeepAlive) | `~/Library/Logs/mini-agent-board/agents.log` |
| `com.tyler.mini-agent-board.publish` | `publish.py` | every 15 min | `~/Library/Logs/mini-agent-board/publish.log` |

To see the live dashboard on the Mini's own screen, open Terminal and run
`agents/Dashboard.command` (or `.venv/bin/python agents/run_agents.py --watch`). It only
reads `status/*.json`; the crew keeps running under launchd whether or not the window is open.

Keep the Mini awake: System Settings → Energy → *Prevent automatic sleeping when the display
is off*, or run `caffeinate -s -i &`. If you want the TUI visible, also set the display to
never sleep.

Useful commands:

```sh
.venv/bin/python agents/run_agents.py            # crew + TUI in the foreground (Ctrl-C stops)
.venv/bin/python agents/run_agents.py --fast     # 4–9 s tasks, for testing
.venv/bin/python publish.py --dry-run            # show the merged feed without writing
.venv/bin/python publish.py --no-push            # write + commit locally only
launchctl kickstart gui/$(id -u)/com.tyler.mini-agent-board.publish   # publish now
tail -f ~/Library/Logs/mini-agent-board/*.log
```

## The status contract

Each agent owns one file, `status/<agent>.json`, and rewrites it atomically (write a temp
file, `os.replace`) whenever its state changes and at least every few seconds for the
heartbeat:

```json
{
  "agent": "builder",
  "display_name": "Builder",
  "state": "working",
  "task": "Write unit tests for haiku.py",
  "progress": 0.64,
  "started": 1758000000,
  "heartbeat": 1758000123,
  "completed_today": 7,
  "last_result": "3 tests passing",
  "note": ""
}
```

| field | type | meaning |
|---|---|---|
| `agent` | string | lowercase id; also the file name |
| `display_name` | string | what the board shows |
| `state` | `working` \| `idle` \| `blocked` \| `done` \| `error` | |
| `task` | string | current (or just-finished) task title |
| `progress` | 0..1 or `null` | real progress; `null` hides the bar |
| `started` | unix | when the current state/task began |
| `heartbeat` | unix | last write; the publisher marks the agent **stale** after 10 min |
| `completed_today` | int | the agent resets this at local midnight (America/New_York) |
| `last_result` | string | one plain-English sentence saying what the agent just did; shown as a bullet on every board |
| `note` | string | optional short free text (shown in italics) |

Keys starting with `_` are private to the agent and are dropped by the publisher.

`publish.py` merges the files into `docs/status.json`:

```json
{
  "updated": 1758000130,
  "agents": [ { ...agent..., "stale": false }, ... ],
  "totals": { "completed_today": 21, "working": 2, "agents": 3 }
}
```

* `agents` is sorted by `display_name`, so SenseCraft `dataKey` paths are positional:
  `agents.0.task`, `agents.1.state`, `totals.completed_today`.
* A stale agent is published with `"state": "stale"`, `"stale": true`, its original state
  in `last_state`, `progress: null`, and a note like `no heartbeat for 23 min`.
* Strings are collapsed to one line and cut at 140 characters; `$HOME` is replaced by `~`.
* Nothing is written or committed if the merged content (ignoring `updated`) is unchanged,
  so a dead crew stops advancing `updated` and the board's header turns red after 45 min.

### How a real agent adopts it

Write the JSON above to `status/<agent>.json` inside the repo (or wherever `MAB_STATUS_DIR`
points), atomically, at least every 5 minutes. That's the whole integration. In Python:

```python
import json, os, time
from pathlib import Path

STATUS = Path("~/projects/mini-agent-board/status").expanduser()

def report(agent, state, task="", progress=None, completed_today=0, last_result="", note=""):
    data = {"agent": agent, "display_name": agent.title(), "state": state, "task": task,
            "progress": progress, "started": int(time.time()), "heartbeat": int(time.time()),
            "completed_today": completed_today, "last_result": last_result, "note": note}
    tmp = STATUS / f"{agent}.json.tmp"
    tmp.write_text(json.dumps(data))
    os.replace(tmp, STATUS / f"{agent}.json")
```

Keep `started` fixed for the lifetime of a task (the boards show elapsed time from it), bump
`heartbeat` on every write, and delete the file when the agent retires so it drops off the board.

## The fake crew (`agents/run_agents.py`)

Scout, Builder and Critic pick tasks from small per-agent pools and really do them — bubble
sort shuffled Beatles titles, count primes by trial division, Monte-Carlo π, longest Collatz
chain, palindromic primes, refactor a haiku to 5-7-5 with a syllable heuristic, unit-test that
heuristic (it genuinely fails on words like *every* and *queue*, which is where `error` comes
from), group anagrams, word-frequency of the Gettysburg Address. Each task is paced to 30–90 s
with real progress. A shared "workbench" lock produces real `blocked` states. Critic reviews
Builder's actual output through a shared blackboard.

## The e-paper layout (`board/`)

* `board/sensecraft-hmi-layout-reference.md` — the layout JSON format, reverse-engineered.
* `board/build_layout_helpers.py` — tiny element factories.
* `board/build_layout.py` → `board/layout.json` — the board: header with the feed's `updated`
  time (turns red past 45 min), three big agent cards (name, colored state word, task, progress
  bar + percent, last result, done count), footer with tasks completed today, working count
  and the E1002's battery. No live clocks: the only time shown is the feed's `updated`. Only the six panel colors are used: a pure-blue field,
  white header band and cards.
* `board/preview.html` — local approximation of Seeed's render. Serve the repo root
  (`python3 -m http.server 8766`) and open `http://127.0.0.1:8766/board/preview.html`. It fills the
  data widgets from `docs/status.json`; add `?demo=1` for a working/blocked/error sample,
  `&stale=1` for the red header, `?empty=1` for no feed. Example renders are in `board/renders/`.

SenseCraft can't recolor a widget from data, so each colored dynamic label is a stack of
same-box `data` widgets, one per color, whose custom function returns a zero-width space
unless its condition holds. The `updated` time is two widgets (black when fresh, red + "STALE"
when old). Three renderer facts learned from the live editor, all handled in `build_layout.py`:
a missing value reaches the custom function as the string `N/A`; a function that returns `''`
is drawn as the text `N/A`; and until a widget has fetched once, the editor canvas runs the
function on the widget's baked preview `value` (so previews are raw feed values).

### Importing into SenseCraft HMI

1. `python3 board/build_layout.py` (already committed as `board/layout.json`).
2. In SenseCraft HMI: **Workspace → your design → Import** (the inward-arrow icon) and pick
   `layout.json`. This replaces the canvas.
3. The editor canvas shows baked preview text until each `data` widget has fetched once;
   clicking a widget triggers that fetch. The battery widget (`device`) also gets your device
   key attached when clicked. The **Preview** window always fetches live and is what the
   device will show.
4. **Preview**, then **Save** and **Apply** to the E1002. Set the device refresh to 15–30 min.

GitHub Pages sits behind a CDN that caches for about 10 minutes, so a 15 min publish cadence
is the floor; there is no point refreshing the display faster than that.

## Layout

```
agents/run_agents.py        fake crew + rich dashboard (--watch = dashboard only)
agents/Dashboard.command    double-click launcher for the dashboard
publish.py                  status/*.json → docs/status.json → commit + push
bootstrap.sh                one-shot setup on the Mini
launchd/*.plist             templates; bootstrap renders __REPO__/__HOME__ into ~/Library/LaunchAgents
docs/index.html             phone board (static, reads status.json client-side)
docs/status.json            the published feed
board/                      SenseCraft layout builder, helpers, reference, generated layout.json
status/                     runtime per-agent files (gitignored)
```
