# mini-agent-board

Status board for a crew of software-design agents running on Tyler's Mac Mini (2024 M4, macOS Tahoe),
shown on a Seeed reTerminal E1002 e-paper display (7.3" color, 800x480) via GitHub Pages.

## Architecture (decided — do not re-litigate)

```
Mac Mini                          GitHub Pages                    Seeed cloud            E1002
agents write status/<agent>.json  →  docs/status.json  →  SenseCraft `data` widgets  →  rendered bitmap
run_agents.py (visible rich TUI)     (publish.py, launchd 15 min)   pull the JSON       pulled by display
```

- The display never renders anything itself. Seeed's cloud renders the SenseCraft layout and the display
  downloads a bitmap. All widget fetches originate from Seeed's servers, so the data must be on a public URL.
  Localhost, LAN, and Tailscale are all invisible to it. No custom firmware.
- Public repo → nothing secret in `docs/status.json`: no hostnames, IPs, tokens, file paths under $HOME.
- GitHub Pages CDN caches ~10 min, so 15 min publish cadence is the floor. Display refresh = 15–30 min.
- Repo lives at `~/projects/mini-agent-board`, GitHub Pages serves `docs/` on `main`.
  Feed URL: `https://<user>.github.io/mini-agent-board/status.json`.

## Deliverables to build

1. `agents/run_agents.py` — fake agent crew ("Scout", "Builder", "Critic") doing obviously silly but *real*
   work (sort shuffled Beatles songs, count primes, refactor a haiku…), 30–90 s per task, real progress.
   Renders a live `rich` dashboard in the terminal so the Mini's own screen shows work happening.
   Each agent writes `status/<agent>.json` continuously. That file IS the contract (below).
2. `publish.py` — merges `status/*.json` → `docs/status.json`, adds `updated` (unix), `git commit` + `push`.
   Idempotent; no commit if nothing changed. Never fails loudly enough to stop launchd.
3. `launchd/com.tyler.mini-agent-board.agents.plist` (KeepAlive at login) and
   `launchd/com.tyler.mini-agent-board.publish.plist` (StartInterval 900). Log to `~/Library/Logs/`.
4. `bootstrap.sh` — checks python3, git, `gh auth status`; creates venv; installs deps; enables Pages
   (`gh api` or instructions); installs plists; prints the feed URL. Reminds to disable sleep (`caffeinate` /
   Energy settings).
5. `docs/index.html` — human-readable board reading `status.json` client-side (for phone). Static, no build.
6. `board/build_layout.py` + generated `board/layout.json` — SenseCraft HMI import file for the E1002.
   Style: **big status cards per agent** (three cards), header with "updated" time that turns red when stale
   (>45 min), footer with tasks completed today. Use only the six panel colors.
   Read `board/sensecraft-hmi-layout-reference.md` first; reuse helpers in `board/build_layout_helpers.py`.
7. `README.md` — setup, the JSON contract, how a real agent adopts it, how to import the layout into
   SenseCraft (Workspace → design → Import; click each data widget once after import; Preview; Apply).

## Status contract — `status/<agent>.json`

```json
{
  "agent": "builder",
  "display_name": "Builder",
  "state": "working",              // working | idle | blocked | done | error
  "task": "Write unit tests for haiku.py",
  "progress": 0.64,                // 0..1 or null
  "started": 1758000000,           // unix
  "heartbeat": 1758000123,         // unix — publisher marks agent stale if > 10 min old
  "completed_today": 7,
  "last_result": "3 tests passing",
  "note": ""                       // optional short free text
}
```

`docs/status.json` = `{"updated": <unix>, "agents": [ ...the above, sorted by display_name ], "totals": {"completed_today": n, "working": n}}`.
Keep it flat and array-indexed: SenseCraft `dataKey` paths look like `agents.0.task`, `totals.completed_today`.

## SenseCraft widget facts (from reverse-engineering 518 public templates)

- Top level: `{"dither": 3, "stageSize": {...}, "stageElements": [container]}`; container is a `group` with
  `id: "__device_container_group__"`, 800×480, children in z-order, child coords relative to panel.
- Data widget: `type: "data"`, `requiredPlatform: "externalApi"`, `dataUrl`, `dataKey` (dot path, numeric
  index for arrays), `dataTransform` ∈ time/date/number/compactNumber/currency/percentage/custom
  (`customFunction` JS body with `value`), text styling keys (`fontFamily: "Montserrat"`, `fontSize`,
  `fontStyle: "bold"`, `textAlign`, `color`), `value` = editor preview.
- `type: "date"` with `dataTransform.type: "time"`, `options.format: "h:mm A"`, `timezone: "America/New_York"`.
- Panel colors: `#000000 #ffffff #ff0000 #ffff00 #0000ff #00ff00`. Everything else dithers.
- Device id for the E1002 (battery via `requiredPlatform: "device"`): 20233536.

## Conventions

- Python 3.11+, stdlib + `rich` only. No frameworks.
- Timezone everywhere: America/New_York. Unix timestamps in JSON.
- Everything must run unattended; a failed push must not kill the agents.
