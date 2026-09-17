#!/usr/bin/env python3
"""Fake agent crew for the mini-agent-board.

Three agents (Scout, Builder, Critic) do silly but *real* work — sorting shuffled
Beatles songs, counting primes, refactoring haiku — 30–90 s per task with real
progress. Each agent continuously writes ``status/<agent>.json`` (the contract
that publish.py merges into docs/status.json).

Modes
-----
  python3 agents/run_agents.py            run the crew; if stdout is a TTY, also
                                          render a live rich dashboard
  python3 agents/run_agents.py --watch    dashboard only, reading status/*.json
                                          (open this in Terminal on the Mini while
                                          launchd runs the crew headless)
  python3 agents/run_agents.py --fast     shrink task budgets (for testing)

Stdlib + rich only. Timezone: America/New_York. Timestamps in JSON are unix.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")
sys.set_int_max_str_digits(0)  # the Fibonacci task prints numbers with >4300 digits
ROOT = Path(__file__).resolve().parent.parent
STATUS_DIR = Path(os.environ.get("MAB_STATUS_DIR", ROOT / "status"))
DOCS_STATUS = ROOT / "docs" / "status.json"
STATES = ("working", "idle", "blocked", "done", "error")

log = logging.getLogger("agents")


def now() -> int:
    return int(time.time())


def today_key() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def fmt_clock(ts: float | None = None) -> str:
    """12-hour clock, e.g. '7:24 PM'."""
    dt = datetime.fromtimestamp(ts, TZ) if ts else datetime.now(TZ)
    return dt.strftime("%-I:%M %p")


class Stopped(Exception):
    """Raised inside a task when the crew is shutting down."""


# --------------------------------------------------------------------------- data
BEATLES = [
    "A Day in the Life", "A Hard Day's Night", "Across the Universe", "All My Loving",
    "All You Need Is Love", "And I Love Her", "Back in the U.S.S.R.", "Blackbird",
    "Can't Buy Me Love", "Come Together", "Day Tripper", "Dear Prudence",
    "Don't Let Me Down", "Drive My Car", "Eight Days a Week", "Eleanor Rigby",
    "Get Back", "Golden Slumbers", "Good Day Sunshine", "Hello, Goodbye",
    "Help!", "Helter Skelter", "Here Comes the Sun", "Hey Jude",
    "I Am the Walrus", "I Feel Fine", "I Saw Her Standing There", "I Want to Hold Your Hand",
    "I Will", "If I Fell", "In My Life", "Julia",
    "Lady Madonna", "Let It Be", "Lucy in the Sky with Diamonds", "Michelle",
    "Norwegian Wood", "Nowhere Man", "Ob-La-Di, Ob-La-Da", "Octopus's Garden",
    "Paperback Writer", "Penny Lane", "Please Please Me", "Revolution",
    "Rocky Raccoon", "Something", "Strawberry Fields Forever", "Taxman",
    "Ticket to Ride", "Twist and Shout", "We Can Work It Out", "While My Guitar Gently Weeps",
    "With a Little Help from My Friends", "Yellow Submarine", "Yesterday", "You Won't See Me",
]

GETTYSBURG = """Four score and seven years ago our fathers brought forth on this continent,
a new nation, conceived in Liberty, and dedicated to the proposition that all men are created
equal. Now we are engaged in a great civil war, testing whether that nation, or any nation so
conceived and so dedicated, can long endure. We are met on a great battle-field of that war.
We have come to dedicate a portion of that field, as a final resting place for those who here
gave their lives that that nation might live. It is altogether fitting and proper that we
should do this. But, in a larger sense, we can not dedicate -- we can not consecrate -- we can
not hallow -- this ground. The brave men, living and dead, who struggled here, have
consecrated it, far above our poor power to add or detract. The world will little note, nor
long remember what we say here, but it can never forget what they did here. It is for us the
living, rather, to be dedicated here to the unfinished work which they who fought here have
thus far so nobly advanced. It is rather for us to be here dedicated to the great task
remaining before us -- that from these honored dead we take increased devotion to that cause
for which they gave the last full measure of devotion -- that we here highly resolve that
these dead shall not have died in vain -- that this nation, under God, shall have a new birth
of freedom -- and that government of the people, by the people, for the people, shall not
perish from the earth."""

ANAGRAM_WORDS = [
    "listen", "silent", "enlist", "tinsel", "inlets", "google", "evil", "vile", "live", "veil",
    "dusty", "study", "night", "thing", "below", "elbow", "bowel", "angel", "glean", "angle",
    "brag", "grab", "garb", "cider", "cried", "dirce", "earth", "heart", "hater", "rates",
    "stare", "tears", "aster", "taser", "parse", "spare", "spear", "pears", "reaps", "apres",
    "state", "taste", "teats", "diary", "dairy", "alert", "alter", "later", "ratel", "least",
    "steal", "slate", "stale", "tales", "teals", "python", "typhon", "phyton", "binary", "brainy",
    "scout", "builder", "critic", "agent", "board", "paper", "screen", "signal", "aligns",
]

# Haiku line templates: each slot is a list of candidate words; syllable targets 5/7/5.
HAIKU_TEMPLATES = [
    (
        [["silent", "quiet", "sleepless", "old"], ["server", "laptop", "mac mini", "kernel"], ["hums", "waits", "sleeps", "dreams"]],
        [["the", "a", "one"], ["tests", "builds", "agents", "cron jobs"], ["pass", "fail", "run", "spin"], ["in the", "past the", "through the"], ["night", "dawn", "dark", "morning"]],
        [["refactor", "commit", "deploy", "merge"], ["at", "by", "near"], ["midnight", "sunrise", "noon", "dusk"]],
    ),
    (
        [["e-paper", "the display", "pixels"], ["blinks", "wakes", "refreshes", "stirs"], ["once", "slowly", "at last"]],
        [["fifteen", "twenty", "thirty"], ["minutes", "seconds"], ["of", "in", "for"], ["patience", "silence", "waiting", "stillness"]],
        [["the", "one", "a"], ["crew", "board", "cloud", "queue"], ["keeps", "holds", "counts"], ["working", "going", "score", "time"]],
    ),
    (
        [["primes", "bugs", "songs", "tasks"], ["counted", "sorted", "tallied", "handled"], ["twice", "again", "by hand"]],
        [["nobody", "no one", "someone"], ["asked", "wanted", "needed"], ["for", "about"], ["this", "any", "the", "that"], ["work", "data", "haiku", "result"]],
        [["but", "and", "so", "still"], ["the", "a"], ["board", "screen", "crew"], ["looks", "seems", "reads"], ["busy", "alive", "happy"]],
    ),
]

# Words with human-verified syllable counts for the "unit tests" task. Some of these
# defeat the heuristic on purpose, so the tests genuinely fail sometimes.
SYLLABLE_CASES = {
    "haiku": 2, "agent": 2, "builder": 2, "critic": 2, "scout": 1, "python": 2,
    "beatles": 2, "prime": 1, "refactor": 3, "display": 2, "paper": 2, "mini": 2,
    "commit": 2, "publish": 2, "table": 2, "board": 1, "yellow": 2, "submarine": 3,
    "every": 3, "queue": 1, "fire": 1, "chocolate": 3, "camera": 3, "science": 2,
    "poem": 2, "idea": 3, "hour": 1, "orange": 2, "create": 2, "area": 3,
}


# ----------------------------------------------------------------------- helpers
def syllables(word: str) -> int:
    """Rough English syllable heuristic (vowel groups, silent-e). Deliberately imperfect."""
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]+", w)))


def line_syllables(line: str) -> int:
    return sum(syllables(w) for w in line.split())


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


def compact(n: int) -> str:
    return f"{n:,}"


# ------------------------------------------------------------------------- tasks
class Ctx:
    """Paces a task so its real work is spread over ``budget`` seconds."""

    def __init__(self, agent: "Agent", budget: float, stop: threading.Event):
        self.agent = agent
        self.budget = budget
        self.stop = stop
        self.t0 = time.monotonic()

    def step(self, i: int, n: int, note: str | None = None) -> None:
        self.agent.set_progress(min(1.0, i / n), note)
        target = self.t0 + self.budget * i / n
        while not self.stop.is_set():
            d = target - time.monotonic()
            if d <= 0:
                break
            self.stop.wait(min(d, 0.5))
        if self.stop.is_set():
            raise Stopped()


class TaskError(Exception):
    """A task that finished but with a bad outcome (agent goes to 'error')."""


def task_sort_beatles(ctx: Ctx) -> str:
    songs = BEATLES[:]
    random.shuffle(songs)
    n = len(songs)
    swaps = 0
    for p in range(n):  # bubble sort, one pass per step — real O(n²) work
        swapped = False
        for j in range(n - 1 - p):
            if songs[j].lower() > songs[j + 1].lower():
                songs[j], songs[j + 1] = songs[j + 1], songs[j]
                swaps += 1
                swapped = True
        ctx.step(p + 1, n, f"pass {p + 1}/{n}, {swaps} swaps")
        if not swapped:
            ctx.step(n, n)
            break
    BLACKBOARD["sorted_songs"] = songs
    return f"Sorted {n} Beatles songs alphabetically by hand in {swaps} swaps."


def task_count_primes(ctx: Ctx) -> str:
    limit = random.randrange(150_000, 400_000, 1000)
    chunks = 60
    count, largest = 0, 0
    for c in range(chunks):
        lo, hi = limit * c // chunks, limit * (c + 1) // chunks
        for k in range(max(lo, 2), hi):
            if is_prime(k):
                count += 1
                largest = k
        ctx.step(c + 1, chunks, f"{compact(count)} primes so far")
    return f"Counted {compact(count)} primes below {compact(limit)}; the biggest was {compact(largest)}."


def task_monte_carlo_pi(ctx: Ctx) -> str:
    total = random.choice([1_000_000, 1_500_000, 2_000_000])
    chunks = 50
    inside = 0
    per = total // chunks
    rnd = random.random
    for c in range(chunks):
        for _ in range(per):
            x, y = rnd(), rnd()
            if x * x + y * y <= 1.0:
                inside += 1
        est = 4 * inside / ((c + 1) * per)
        ctx.step(c + 1, chunks, f"π ≈ {est:.4f}")
    return f"Threw {compact(total)} random darts and estimated π at {4 * inside / total:.4f}."


def task_collatz(ctx: Ctx) -> str:
    limit = random.choice([200_000, 300_000, 500_000])
    chunks = 50
    best_n, best_len = 1, 1
    cache: dict[int, int] = {1: 1}
    for c in range(chunks):
        lo, hi = limit * c // chunks + 1, limit * (c + 1) // chunks + 1
        for n0 in range(lo, hi):
            n, steps, path = n0, 0, []
            while n not in cache:
                path.append(n)
                n = n // 2 if n % 2 == 0 else 3 * n + 1
                steps += 1
            base = cache[n]
            for i, v in enumerate(path):
                cache[v] = base + steps - i
            if cache[n0] > best_len:
                best_n, best_len = n0, cache[n0]
        ctx.step(c + 1, chunks, f"longest so far: {best_n} ({best_len} steps)")
    return f"Checked every number under {compact(limit)}; {compact(best_n)} has the longest Collatz chain at {best_len} steps."


def task_palindromic_primes(ctx: Ctx) -> str:
    limit = random.choice([100_000, 200_000, 300_000])
    chunks = 40
    found: list[int] = []
    for c in range(chunks):
        lo, hi = limit * c // chunks, limit * (c + 1) // chunks
        for k in range(max(lo, 2), hi):
            s = str(k)
            if s == s[::-1] and is_prime(k):
                found.append(k)
        ctx.step(c + 1, chunks, f"{len(found)} found")
    return f"Found {len(found)} primes below {compact(limit)} that read the same backwards; the largest is {compact(found[-1])}."


def task_refactor_haiku(ctx: Ctx) -> str:
    template = random.choice(HAIKU_TEMPLATES)
    targets = (5, 7, 5)
    lines: list[str] = []
    tries_per_line = 30
    total = tries_per_line * 3
    done = 0
    for li, (slots, target) in enumerate(zip(template, targets)):
        best = None
        for t in range(tries_per_line):
            cand = " ".join(random.choice(s) for s in slots)
            done += 1
            ctx.step(done, total, f"line {li + 1}: '{cand}' = {line_syllables(cand)}")
            if line_syllables(cand) == target:
                best = cand
                done = tries_per_line * (li + 1)
                ctx.step(done, total, f"line {li + 1} ✓ '{cand}'")
                break
        if best is None:
            raise TaskError(f"Gave up on a haiku: line {li + 1} never hit {target} syllables in {tries_per_line} rewrites.")
        lines.append(best)
    ctx.step(total, total)
    BLACKBOARD["haiku"] = lines
    return "Rewrote a haiku until it scanned 5-7-5: “" + " / ".join(lines) + "”"


def task_unit_tests(ctx: Ctx) -> str:
    cases = random.sample(sorted(SYLLABLE_CASES.items()), 9)
    failing = []
    for i, (word, expected) in enumerate(cases):
        got = syllables(word)
        if got != expected:
            failing.append(f"{word} (got {got}, want {expected})")
        ctx.step(i + 1, len(cases), f"test_{word}: {'ok' if got == expected else 'FAIL'}")
    passing = len(cases) - len(failing)
    if failing:
        raise TaskError(f"Ran {len(cases)} syllable-counter tests; {len(failing)} failed on {', '.join(failing)}.")
    return f"Ran {len(cases)} syllable-counter tests and all of them passed."


def task_anagrams(ctx: Ctx) -> str:
    words = ANAGRAM_WORDS[:]
    random.shuffle(words)
    groups: dict[str, list[str]] = {}
    for i, w in enumerate(words):
        groups.setdefault("".join(sorted(w)), []).append(w)
        ctx.step(i + 1, len(words), f"{sum(1 for g in groups.values() if len(g) > 1)} groups")
    multi = [g for g in groups.values() if len(g) > 1]
    biggest = max(multi, key=len)
    return f"Sorted {len(words)} words into {len(multi)} anagram groups; the biggest was {', '.join(sorted(biggest))}."


def task_word_frequency(ctx: Ctx) -> str:
    words = re.findall(r"[a-z]+", GETTYSBURG.lower())
    counts: dict[str, int] = {}
    n = len(words)
    for i, w in enumerate(words):
        counts[w] = counts.get(w, 0) + 1
        if i % 5 == 0 or i == n - 1:
            ctx.step(i + 1, n, f"{len(counts)} distinct words")
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    return f"Read the Gettysburg Address: {n} words, {len(counts)} different ones, '{top[0][0]}' used most ({top[0][1]} times)."


def task_review_sort(ctx: Ctx) -> str:
    songs = BLACKBOARD.get("sorted_songs")
    if not songs:
        songs = sorted(BEATLES, key=str.lower)
    n = len(songs)
    inversions = 0
    for i in range(n):
        for j in range(i + 1, n):
            if songs[i].lower() > songs[j].lower():
                inversions += 1
        ctx.step(i + 1, n, f"{inversions} inversions")
    if inversions:
        raise TaskError(f"Found {inversions} out-of-order pairs in Builder's Beatles sort.")
    return f"Double-checked Builder's Beatles sort: all {n} titles in order, no mistakes."


def task_review_haiku(ctx: Ctx) -> str:
    lines = BLACKBOARD.get("haiku") or ["silent server hums", "the tests pass in the night", "commit at midnight"]
    counts = []
    for i, line in enumerate(lines):
        counts.append(line_syllables(line))
        ctx.step(i + 1, 3, f"line {i + 1}: {counts[-1]} syllables")
    if counts != [5, 7, 5]:
        raise TaskError(f"Rejected Builder's haiku: it scans {'-'.join(map(str, counts))}, not 5-7-5.")
    return "Approved Builder's haiku; it scans 5-7-5."


def task_fib_digits(ctx: Ctx) -> str:
    n = random.choice([20_000, 30_000, 40_000])
    chunks = 40
    a, b = 0, 1
    for c in range(chunks):
        for _ in range(n // chunks):
            a, b = b, a + b
        ctx.step(c + 1, chunks, f"F({(c + 1) * (n // chunks)}) has {len(str(a))} digits")
    return f"Computed the {compact(n)}th Fibonacci number; it has {compact(len(str(a)))} digits."


# task name, function, whether it needs the shared workbench (causes real 'blocked' time)
TASKS = {
    "scout": [
        ("Count primes below a random N", task_count_primes, False),
        ("Estimate π with Monte Carlo darts", task_monte_carlo_pi, False),
        ("Find the longest Collatz chain", task_collatz, False),
        ("Hunt palindromic primes", task_palindromic_primes, False),
        ("Word-frequency audit of the Gettysburg Address", task_word_frequency, True),
        ("Compute a very large Fibonacci number", task_fib_digits, False),
    ],
    "builder": [
        ("Sort shuffled Beatles songs by hand", task_sort_beatles, True),
        ("Refactor a haiku to 5-7-5", task_refactor_haiku, True),
        ("Write unit tests for haiku.py", task_unit_tests, True),
        ("Group anagrams in the word list", task_anagrams, False),
        ("Compute a very large Fibonacci number", task_fib_digits, False),
    ],
    "critic": [
        ("Review Builder's Beatles sort", task_review_sort, True),
        ("Review Builder's haiku", task_review_haiku, True),
        ("Re-run the syllable unit tests", task_unit_tests, True),
        ("Word-frequency audit of the Gettysburg Address", task_word_frequency, False),
        ("Count primes below a random N", task_count_primes, False),
    ],
}

BLACKBOARD: dict[str, object] = {}
WORKBENCH = threading.Lock()  # shared resource: contention produces real 'blocked' states


# ------------------------------------------------------------------------- agent
class Agent:
    def __init__(self, name: str, display_name: str, stop: threading.Event, fast: bool):
        self.name = name
        self.display_name = display_name
        self.stop = stop
        self.fast = fast
        self.lock = threading.Lock()
        self.path = STATUS_DIR / f"{name}.json"
        self.state = "idle"
        self.task = ""
        self.progress: float | None = None
        self.started = now()
        self.completed_today = 0
        self.last_result = ""
        self.note = ""
        self._day = today_key()
        self._load_counters()
        self.thread = threading.Thread(target=self.run, name=name, daemon=True)

    # ---- persistence
    def _load_counters(self) -> None:
        try:
            prev = json.loads(self.path.read_text())
            if prev.get("_day") == self._day:
                self.completed_today = int(prev.get("completed_today", 0))
                self.last_result = str(prev.get("last_result", ""))
        except (OSError, ValueError):
            pass

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "agent": self.name,
                "display_name": self.display_name,
                "state": self.state,
                "task": self.task,
                "progress": None if self.progress is None else round(self.progress, 3),
                "started": self.started,
                "heartbeat": now(),
                "completed_today": self.completed_today,
                "last_result": self.last_result,
                "note": self.note,
                "_day": self._day,
            }

    def write(self) -> None:
        data = self.snapshot()
        tmp = self.path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            os.replace(tmp, self.path)
        except OSError as e:
            log.warning("%s: could not write status: %s", self.name, e)

    # ---- state changes
    def set(self, state: str, task: str | None = None, progress: float | None = None,
            note: str = "", result: str | None = None) -> None:
        assert state in STATES
        with self.lock:
            self._rollover()
            if state != self.state or (task is not None and task != self.task):
                self.started = now()
            self.state = state
            if task is not None:
                self.task = task
            self.progress = progress
            self.note = note
            if result is not None:
                self.last_result = result
        log.info("%-8s %-8s %s%s", self.display_name, state.upper(), self.task, f"  [{note}]" if note else "")
        self.write()

    def set_progress(self, p: float, note: str | None) -> None:
        with self.lock:
            self.progress = p
            if note is not None:
                self.note = note

    def _rollover(self) -> None:
        day = today_key()
        if day != self._day:
            self._day = day
            self.completed_today = 0

    # ---- main loop
    def run(self) -> None:
        rnd = random.Random(hash((self.name, time.time())))
        self.set("idle", "", None, "warming up")
        self._pause(rnd.uniform(1, 4))
        while not self.stop.is_set():
            try:
                title, fn, needs_bench = rnd.choice(TASKS[self.name])
                budget = rnd.uniform(4, 9) if self.fast else rnd.uniform(30, 90)
                self.set("idle", "", None, f"next: {title}")
                self._pause(rnd.uniform(2, 8))
                held = False
                if needs_bench:
                    held = self._acquire_bench(title)
                try:
                    self.set("working", title, 0.0, "")
                    result = fn(Ctx(self, budget, self.stop))
                    with self.lock:
                        self._rollover()
                        self.completed_today += 1
                    self.set("done", title, 1.0, "", result)
                    self._pause(rnd.uniform(4, 9))
                except TaskError as e:
                    self.set("error", title, None, "needs a human", str(e))
                    self._pause(rnd.uniform(8, 15))
                finally:
                    if held:
                        WORKBENCH.release()
            except Stopped:
                break
            except Exception as e:  # never let a bug kill the crew
                log.exception("%s crashed in task loop", self.name)
                self.set("error", None, None, "internal error", f"{type(e).__name__}: {e}")
                self._pause(10)
        self.set("idle", "", None, "crew stopped")

    def _acquire_bench(self, title: str) -> bool:
        if WORKBENCH.acquire(timeout=0.2):
            return True
        holder = next((a.display_name for a in CREW if a is not self and a.state == "working"), "someone")
        self.set("blocked", title, None, f"waiting for {holder} to release the workbench")
        while not self.stop.is_set():
            if WORKBENCH.acquire(timeout=1.0):
                return True
        raise Stopped()

    def _pause(self, seconds: float) -> None:
        if self.stop.wait(seconds):
            raise Stopped()


CREW: list[Agent] = []


def heartbeat_loop(stop: threading.Event, interval: float = 2.0) -> None:
    while not stop.is_set():
        for a in CREW:
            a.write()
        stop.wait(interval)


# --------------------------------------------------------------------- dashboard
def read_status_files() -> list[dict]:
    out = []
    for p in sorted(STATUS_DIR.glob("*.json")):
        try:
            out.append(json.loads(p.read_text()))
        except (OSError, ValueError):
            continue
    return sorted(out, key=lambda a: a.get("display_name", ""))


def read_published() -> dict | None:
    try:
        return json.loads(DOCS_STATUS.read_text())
    except (OSError, ValueError):
        return None


STATE_STYLE = {
    "working": "bold green", "idle": "dim", "blocked": "bold yellow",
    "done": "bold blue", "error": "bold red", "stale": "bold red",
}


def render(agents: list[dict], published: dict | None, source: str):
    from rich.console import Group
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.progress_bar import ProgressBar
    from rich.table import Table
    from rich.text import Text

    t = now()
    header = Text.assemble(
        ("  MAC MINI AGENT CREW", "bold"), ("   ", ""),
        (datetime.now(TZ).strftime("%a %b %-d · %-I:%M:%S %p"), "cyan"),
    )
    if published:
        age = (t - int(published.get("updated", 0))) // 60
        style = "red" if age > 45 else "green"
        header.append(f"   last publish {fmt_clock(published.get('updated'))} ({age} min ago)", style)
    else:
        header.append("   not published yet", "dim")
    header.append(f"   [{source}]", "dim")

    cards = Table.grid(expand=True, padding=(0, 1))
    for _ in agents or [None]:
        cards.add_column(ratio=1)
    panels = []
    for a in agents:
        state = a.get("state", "?")
        if t - int(a.get("heartbeat", 0)) > 600:
            state = "stale"
        body = [Text(state.upper(), style=STATE_STYLE.get(state, ""))]
        body.append(Text(a.get("task") or "—", style="bold" if state == "working" else ""))
        p = a.get("progress")
        if p is not None:
            body.append(ProgressBar(total=1.0, completed=float(p), width=None))
            body.append(Text(f"{int(float(p) * 100)}%  ·  {int(t - int(a.get('started', t)))}s", style="dim"))
        if a.get("note"):
            body.append(Text(a["note"], style="italic dim"))
        body.append(Text(""))
        body.append(Text("• " + (a.get("last_result") or "nothing finished yet")))
        body.append(Text.assemble(("done today: ", "dim"), (str(a.get("completed_today", 0)), "bold")))
        panels.append(Panel(Group(*body), title=f"[bold]{a.get('display_name', '?')}[/]",
                            border_style=STATE_STYLE.get(state, "").replace("bold ", "") or "white"))
    if panels:
        cards.add_row(*panels)
    else:
        cards.add_row(Text("no status files yet", style="dim"))

    total_done = sum(int(a.get("completed_today", 0)) for a in agents)
    working = sum(1 for a in agents if a.get("state") == "working")
    footer = Text.assemble(
        ("  tasks completed today: ", "dim"), (str(total_done), "bold"),
        ("    working now: ", "dim"), (str(working), "bold"),
        ("    publish every 15 min · display refresh 15–30 min", "dim"),
        ("    Ctrl-C to quit", "dim"),
    )

    layout = Layout()
    layout.split_column(Layout(Panel(header), size=3, name="header"),
                        Layout(cards, name="cards"),
                        Layout(Panel(footer), size=3, name="footer"))
    return layout


def dashboard(stop: threading.Event, source: str) -> None:
    from rich.console import Console
    from rich.live import Live

    console = Console()
    with Live(render([], None, source), console=console, screen=True, refresh_per_second=4) as live:
        while not stop.is_set():
            agents = [a.snapshot() for a in CREW] if CREW else read_status_files()
            live.update(render(agents, read_published(), source))
            stop.wait(0.25)


# -------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--watch", action="store_true", help="dashboard only; do not run agents")
    ap.add_argument("--fast", action="store_true", help="short task budgets (testing)")
    ap.add_argument("--headless", action="store_true", help="never render the dashboard")
    args = ap.parse_args()

    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    stop = threading.Event()
    tty = sys.stdout.isatty() and not args.headless
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr if tty else sys.stdout,
    )
    if tty:
        logging.getLogger().setLevel(logging.WARNING)  # keep the TUI clean

    def on_signal(signum, _frame):
        log.warning("signal %s: stopping crew", signum)
        stop.set()

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    if args.watch:
        try:
            dashboard(stop, "watch")
        except KeyboardInterrupt:
            pass
        return 0

    CREW.extend([
        Agent("scout", "Scout", stop, args.fast),
        Agent("builder", "Builder", stop, args.fast),
        Agent("critic", "Critic", stop, args.fast),
    ])
    for a in CREW:
        a.thread.start()
    hb = threading.Thread(target=heartbeat_loop, args=(stop,), name="heartbeat", daemon=True)
    hb.start()
    log.info("crew started (%s), status dir %s", "fast" if args.fast else "normal", STATUS_DIR)

    try:
        if tty:
            dashboard(stop, "live")
        else:
            while not stop.is_set():
                stop.wait(1.0)
    except KeyboardInterrupt:
        stop.set()
    finally:
        stop.set()
        for a in CREW:
            a.thread.join(timeout=5)
        for a in CREW:
            a.write()
    return 0


if __name__ == "__main__":
    sys.exit(main())
