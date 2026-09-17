#!/bin/zsh
# One-shot setup for the mini-agent-board on the Mac Mini.
#   ./bootstrap.sh            full setup (venv, deps, git remote, Pages, launchd agents)
#   ./bootstrap.sh --no-launchd   everything except installing/starting the launchd jobs
#
# Idempotent: safe to re-run. Every step prints what it did or why it skipped.
set -u
cd "$(dirname "$0")" || exit 1
REPO="$(pwd -P)"
LABEL_AGENTS=com.tyler.mini-agent-board.agents
LABEL_PUBLISH=com.tyler.mini-agent-board.publish
LAUNCH_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/Library/Logs/mini-agent-board"
INSTALL_LAUNCHD=1
[[ "${1:-}" == "--no-launchd" ]] && INSTALL_LAUNCHD=0

ok()   { print -P "%F{green}✔%f $*"; }
warn() { print -P "%F{yellow}▲%f $*"; }
die()  { print -P "%F{red}✘%f $*"; exit 1; }

# ---- prerequisites ----------------------------------------------------------
command -v python3 >/dev/null || die "python3 not found (install Xcode CLT or Homebrew python)"
PYV=$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')
python3 -c 'import sys;sys.exit(0 if sys.version_info>=(3,11) else 1)' || die "python3 is $PYV; need 3.11+"
ok "python3 $PYV"
command -v git >/dev/null || die "git not found"
ok "git $(git --version | awk '{print $3}')"
if command -v gh >/dev/null; then
  if gh auth status >/dev/null 2>&1; then
    GH_USER=$(gh api user --jq .login 2>/dev/null)
    ok "gh authenticated as $GH_USER"
    gh auth setup-git >/dev/null 2>&1 && ok "git credential helper set to gh" || warn "gh auth setup-git failed; pushes may prompt"
  else
    warn "gh is installed but not logged in — run: gh auth login   (needed to enable Pages and push)"
    GH_USER=""
  fi
else
  warn "gh not installed (brew install gh). Pages must then be enabled by hand: Settings → Pages → main /docs"
  GH_USER=""
fi

# ---- venv + deps ------------------------------------------------------------
if [[ ! -x "$REPO/.venv/bin/python" ]]; then
  python3 -m venv "$REPO/.venv" || die "venv creation failed"
  ok "created .venv"
fi
"$REPO/.venv/bin/pip" install -q -r "$REPO/requirements.txt" || die "pip install failed"
ok "deps installed ($("$REPO/.venv/bin/python" -c 'import rich,importlib.metadata as m;print("rich",m.version("rich"))'))"
mkdir -p "$REPO/status" "$LOG_DIR"

# ---- git remote / first push ------------------------------------------------
REMOTE=$(git remote get-url origin 2>/dev/null || true)
if [[ -z "$REMOTE" ]]; then
  if [[ -n "$GH_USER" ]]; then
    git remote add origin "https://github.com/$GH_USER/mini-agent-board.git" && ok "added origin for $GH_USER"
  else
    warn "no git remote 'origin'; add one before publishing"
  fi
  REMOTE=$(git remote get-url origin 2>/dev/null || true)
fi
OWNER_REPO=$(print -r -- "$REMOTE" | sed -E 's#.*github.com[:/]##; s#\.git$##')
if ! git rev-parse --verify -q HEAD >/dev/null; then
  warn "repo has no commits yet — creating the initial commit"
  git add -A && git commit -q -m "mini-agent-board: initial import" && ok "initial commit"
fi
if [[ -n "$REMOTE" ]] && ! git ls-remote --exit-code --heads origin main >/dev/null 2>&1; then
  git push -u origin main && ok "pushed main to $REMOTE" || warn "push failed; Pages needs main on GitHub"
fi

# ---- GitHub Pages -----------------------------------------------------------
FEED_URL=""
if [[ -n "$GH_USER" && -n "$OWNER_REPO" ]]; then
  if gh api "repos/$OWNER_REPO/pages" >/dev/null 2>&1; then
    ok "GitHub Pages already enabled"
  else
    if gh api -X POST "repos/$OWNER_REPO/pages" --input - <<<'{"build_type":"legacy","source":{"branch":"main","path":"/docs"}}' >/dev/null 2>&1; then
      ok "enabled GitHub Pages (main, /docs)"
    else
      warn "could not enable Pages via API. Do it once in the browser: https://github.com/$OWNER_REPO/settings/pages → Deploy from branch → main → /docs"
    fi
  fi
  PAGES_URL=$(gh api "repos/$OWNER_REPO/pages" --jq .html_url 2>/dev/null || true)
  [[ -n "$PAGES_URL" ]] && FEED_URL="${PAGES_URL%/}/status.json"
fi
[[ -z "$FEED_URL" && -n "$OWNER_REPO" ]] && FEED_URL="https://${OWNER_REPO%%/*}.github.io/${OWNER_REPO##*/}/status.json"

# ---- launchd ----------------------------------------------------------------
render_plist() {  # $1 = label
  sed -e "s#__REPO__#$REPO#g" -e "s#__HOME__#$HOME#g" "$REPO/launchd/$1.plist" > "$LAUNCH_DIR/$1.plist"
  plutil -lint -s "$LAUNCH_DIR/$1.plist" >/dev/null || die "rendered $1.plist is invalid"
}
if (( INSTALL_LAUNCHD )); then
  mkdir -p "$LAUNCH_DIR"
  UID_=$(id -u)
  for L in $LABEL_AGENTS $LABEL_PUBLISH; do
    render_plist "$L"
    launchctl bootout "gui/$UID_/$L" >/dev/null 2>&1 || true
    launchctl bootstrap "gui/$UID_" "$LAUNCH_DIR/$L.plist" && ok "loaded $L" || warn "launchctl bootstrap failed for $L (try: launchctl bootstrap gui/$UID_ $LAUNCH_DIR/$L.plist)"
  done
  launchctl kickstart "gui/$UID_/$LABEL_PUBLISH" >/dev/null 2>&1 && ok "kicked first publish" || true
else
  warn "skipped launchd install (--no-launchd)"
fi

# ---- summary ----------------------------------------------------------------
print
print "  Feed URL (paste into board/build_layout.py FEED and SenseCraft data widgets):"
print "    $FEED_URL"
print "  Phone board:   ${FEED_URL%status.json}"
print "  Logs:          $LOG_DIR/{agents,publish}.log"
print "  Dashboard:     open Terminal and run  $REPO/agents/Dashboard.command"
print
print "  Keep the Mini awake: System Settings → Energy → 'Prevent automatic sleeping when the display is off'"
print "  (or run: caffeinate -s -i &  ). Also set the display to never sleep if you want the TUI visible."
print
