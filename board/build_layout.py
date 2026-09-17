#!/usr/bin/env python3
"""Generate board/layout.json — a SenseCraft HMI import file for the reTerminal E1002.

    python3 board/build_layout.py            # writes board/layout.json
    python3 board/build_layout.py --stdout   # prints instead

Design (800×480, six panel colors only; pure-blue field, white header band and cards):
  * header: title, and in the top-right corner the feed's 'updated' time (black; overlapped
    by a red twin that only renders when the feed is older than 45 min). No live clocks.
  * three big agent cards (Builder, Critic, Scout — feed is sorted by display_name)
    with name, colored state word, task, progress bar + percent, last result, done count
  * footer: tasks completed today, working count, battery

SenseCraft can't change a widget's color from data, so every colored dynamic label is a
stack of same-box `data` widgets, one per color, whose custom function returns '' unless
its own condition holds. Read board/sensecraft-hmi-layout-reference.md for the format.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_layout_helpers import P, _id, layout, rect, text  # noqa: E402

FEED = "https://tylergleeson.github.io/mini-agent-board/status.json"
DEVICE = "https://sensecraft-hmi-api.seeed.cc/api/v1/user/device/iot_data/20233536"
STALE_MIN = 45

BLACK, WHITE, RED, YELLOW, BLUE, GREEN = "#000000", "#ffffff", "#ff0000", "#ffff00", "#0000ff", "#00ff00"

W, H = 800, 480
MARGIN, GAP = 16, 14
CARD_Y, CARD_H = 66, 352
CARD_W = (W - 2 * MARGIN - 2 * GAP) // 3  # 246
N_CARDS = 3


def feed(x, y, w, h, key, label, js=None, size=20, color=BLACK, align="left", bold=False, value="--",
         transform=None, height_lock=True):
    """A `data` widget bound to the public feed (externalApi → no key injection needed)."""
    e = text(x, y, w, h, value, size, color, align, bold)
    e["type"] = "data"
    e["id"] = _id("data")
    e.update({"label": label, "requiredPlatform": "externalApi", "dataUrl": FEED,
              "dataHeaders": {}, "dataKey": key, "sanitizedFields": []})
    if height_lock:
        e["lockHeight"] = True
    if transform:
        e["dataTransform"] = transform
    elif js:
        e["dataTransform"] = {"type": "custom", "options": {"customFunction": js}}
    return e


# ---- JS snippets used inside custom transforms (value is the dataKey's value) ----------
JS_FMT_TIME = (
    "function fmt(u){var d=new Date(u*1000);"
    "try{return d.toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit',timeZone:'America/New_York'});}"
    "catch(e){var y=d.getUTCFullYear();"
    "function nth(m,n){var f=new Date(Date.UTC(y,m,1)).getUTCDay();return 1+((7-f)%7)+7*(n-1);}"
    "var s=Date.UTC(y,2,nth(2,2),7),e2=Date.UTC(y,10,nth(10,1),6);var off=(d>=s&&d<e2)?-4:-5;"
    "var l=new Date(d.getTime()+off*3600000);var h=l.getUTCHours(),mi=l.getUTCMinutes();"
    "return ((h%12)||12)+':'+(mi<10?'0':'')+mi+(h<12?' AM':' PM');}}"
)
JS_AGE_MIN = "var age=(Date.now()/1000-Number(value))/60;"


def js_updated(stale: bool) -> str:
    cond = f"age>{STALE_MIN}" if stale else f"age<={STALE_MIN}"
    body = "'STALE · updated '+fmt(value)" if stale else "'updated '+fmt(value)"
    return f"if(value==null)return '';{JS_AGE_MIN}if(!({cond}))return '';{JS_FMT_TIME}return {body};"


def js_state(states: tuple[str, ...]) -> str:
    arr = ",".join(f"'{s}'" for s in states)
    return f"var s=String(value||'').toLowerCase();return [{arr}].indexOf(s)>=0?s.toUpperCase():'';"


JS_TASK = "if(value==null)return '';var s=String(value);return s.length>60?s.slice(0,59)+'…':s;"
JS_PCT = "if(value==null||value==='')return '';var p=Math.max(0,Math.min(1,Number(value)));return Math.round(p*100)+'%';"
JS_BAR = ("if(value==null||value==='')return '';var p=Math.max(0,Math.min(1,Number(value)));"
          "var n=10,k=Math.round(p*n),s='';for(var i=0;i<n;i++)s+=(i<k?'█':'░');return s;")
JS_RESULT = "var s=(value==null||value==='')?'Nothing finished yet.':String(value);if(s.length>120)s=s.slice(0,119)+'…';return '• '+s;"
JS_DONE = "return (value==null?0:value)+' done today';"
JS_TOTAL_DONE = "return String(value==null?0:value);"
JS_WORKING = "var n=(value==null?0:Number(value));return n+' working';"
JS_NAME = "return value==null?'—':String(value);"
JS_BATTERY = "return value==null?'':'Battery '+value+'%';"


def card(i: int, x: int) -> list[dict]:
    """Card i binds to agents.<i>.* — the feed is sorted by display_name."""
    k = f"agents.{i}"
    pad = 14
    ix, iw = x + pad, CARD_W - 2 * pad
    els: list[dict] = []
    els.append(rect(x, CARD_Y, CARD_W, CARD_H, WHITE, BLACK, 3, 10))
    els.append(rect(x + 3, CARD_Y + 3, CARD_W - 6, 10, BLUE, "transparent", 0, 0))  # top bar (static)
    # name
    els.append(feed(ix, CARD_Y + 22, iw, 40, f"{k}.display_name", f"Agent {i} name", JS_NAME,
                    size=30, bold=True, value=["Builder", "Critic", "Scout"][i]))
    # state word: three overlapping widgets, one per color
    sy = CARD_Y + 64
    for states, color in (
        (("working",), GREEN),
        (("idle", "done"), BLUE),
        (("blocked", "error", "stale"), RED),
    ):
        els.append(feed(ix, sy, iw, 26, f"{k}.state", f"Agent {i} state ({'/'.join(states)})",
                        js_state(states), size=18, color=color, bold=True,
                        value=states[0].upper() if color == GREEN else ""))
    # task (wraps up to 3 lines)
    els.append(feed(ix, CARD_Y + 96, iw, 78, f"{k}.task", f"Agent {i} task", JS_TASK,
                    size=19, bold=True, value="Sort shuffled Beatles songs by hand"))
    # progress bar + percent
    els.append(feed(ix, CARD_Y + 182, iw - 58, 24, f"{k}.progress", f"Agent {i} progress bar", JS_BAR,
                    size=15, color=BLACK, value="██████░░░░"))
    els.append(feed(x + CARD_W - pad - 56, CARD_Y + 176, 56, 32, f"{k}.progress", f"Agent {i} progress %",
                    JS_PCT, size=24, bold=True, align="right", value="64%"))
    # divider
    els.append(rect(ix, CARD_Y + 218, iw, 2, BLACK))
    # what the agent just did, as one plain-English bullet
    els.append(feed(ix, CARD_Y + 228, iw, 84, f"{k}.last_result", f"Agent {i} last result", JS_RESULT,
                    size=15, value="• Sorted 56 Beatles songs alphabetically by hand in 812 swaps."))
    # done today
    els.append(feed(ix, CARD_Y + CARD_H - 34, iw, 24, f"{k}.completed_today", f"Agent {i} done today",
                    JS_DONE, size=15, color=BLUE, bold=True, value="7 done today"))
    return els


def build() -> dict:
    c: list[dict] = []
    c.append(rect(0, 0, W, H, BLUE))          # rich blue field
    c.append(rect(0, 0, W, 58, WHITE))        # white header band: black title, red stale time
    c.append(text(MARGIN, 12, 330, 32, "MAC MINI AGENT CREW", 24, BLACK, bold=True))
    ux, uw = W - MARGIN - 300, 300
    c.append(feed(ux, 19, uw, 24, "updated", "Updated (fresh)", js_updated(False),
                  size=17, color=BLACK, align="right", value="updated 7:24 PM"))
    c.append(feed(ux, 19, uw, 24, "updated", f"Updated (STALE > {STALE_MIN} min)", js_updated(True),
                  size=17, color=RED, align="right", bold=True, value=""))
    # cards
    for i in range(N_CARDS):
        c.extend(card(i, MARGIN + i * (CARD_W + GAP)))
    # footer
    fy = CARD_Y + CARD_H + 10
    c.append(text(MARGIN, fy + 8, 230, 24, "TASKS COMPLETED TODAY", 14, WHITE, bold=True))
    c.append(feed(MARGIN + 232, fy - 4, 90, 44, "totals.completed_today", "Total done today", JS_TOTAL_DONE,
                  size=36, bold=True, color=YELLOW, value="21"))
    c.append(feed(360, fy + 8, 140, 24, "totals.working", "Working now", JS_WORKING,
                  size=14, color=GREEN, bold=True, value="2 working"))
    bat = feed(W - MARGIN - 110, fy + 8, 110, 24, "result.battery.level", "Battery", JS_BATTERY,
               size=13, color=WHITE, align="right", value="Battery 87%")
    bat.update({"requiredPlatform": "device", "dataUrl": DEVICE})
    c.append(bat)
    return layout(c)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()
    doc = build()
    out = json.dumps(doc, indent=2, ensure_ascii=False)
    if args.stdout:
        print(out)
    else:
        target = Path(__file__).resolve().parent / "layout.json"
        target.write_text(out + "\n")
        n = len(doc["stageElements"][0]["children"])
        print(f"wrote {target.name}: {n} elements, {sum(1 for e in doc['stageElements'][0]['children'] if e['type']=='data')} data widgets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
