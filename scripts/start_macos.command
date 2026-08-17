#!/bin/bash
# Double-click launcher (also the target Automator wraps for a desktop icon
# — see the macOS section of the deployment instructions).
cd "$(dirname "$0")/.."
(sleep 3 && open http://127.0.0.1:5000) &
.venv/bin/python -m flask --app src.app run
