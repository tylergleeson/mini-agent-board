#!/bin/zsh
# Double-click in Finder (or run from Terminal) to show the live crew dashboard
# on the Mac Mini's screen. It only reads status/*.json; launchd runs the crew.
cd "$(dirname "$0")/.." || exit 1
exec ./.venv/bin/python agents/run_agents.py --watch
