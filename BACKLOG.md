# Backlog

Ideas and pending chores for the agent board. Nothing here is scheduled. Add to it freely;
when an item is done, delete it (git history keeps the record).

## Ideas for the next layout update

- **Show the date next to the "updated" time in the header.** Tyler likes the updated
  timestamp and wants a date with it, e.g. `updated Sep 17 · 1:08 PM`. Notes for whoever
  builds it: the header time comes from two stacked widgets in `board/build_layout.py`
  (`js_updated(False)` black / `js_updated(True)` red STALE), both formatting the feed's
  `updated` unix value with `fmt()`. Extend `fmt()` (or add a `fmtDate()`) using
  `toLocaleDateString('en-US', {month:'short', day:'numeric', timeZone:'America/New_York'})`,
  keep the 12-hour clock, and widen the box (currently 300 px, right-aligned at the top-right
  corner). The STALE variant is the longest string, so size for that one. Consider the same
  date on the footer's "rendered" stamp.

## Pending chores (known, not urgent)

- **Swap the display off the probe layout.** It is currently running `layout.probe.json`,
  whose request logger stops after 100 hits (about a day at a 15 min interval). Re-import
  `board/layout.json` (it keeps the "rendered" stamp, bound to the feed) and re-add the
  battery widget by hand.
- **Battery widget is manual on every import.** Imported `device` widgets never get the
  account key (see reference §8.5). Any layout change means re-adding Data → Device →
  Battery Level. Worth batching layout changes so this happens rarely.
- **Slashed battery icon (top-right, drawn by firmware v1.2.2).** Seen while on USB at 100 %.
  Undocumented. Test: unplug and see whether it clears on the next refresh.
- **Pick a refresh interval for untethered use.** Rough battery life per charge: 15 min ≈ 4
  days, 30 min ≈ 8 days, 60 min ≈ 2 weeks. The Mini can keep publishing every 15 min.
- **Mini needs a pull + crew restart** to pick up the wrap-friendly anagram bullet:
  `cd ~/projects/mini-agent-board && git pull && launchctl kickstart -k gui/$(id -u)/com.tyler.mini-agent-board.agents`
