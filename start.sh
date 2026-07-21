#!/bin/bash
# One-command start for the CRPT tracker.
# Loads private credentials (if any), refreshes the data snapshot, serves the app.
cd "$(dirname "$0")/backend" || exit 1
if [ -f credentials.env ]; then
  set -a
  source credentials.env
  set +a
fi
python3 loader.py || exit 1
echo "CRPT tracker -> http://127.0.0.1:8642"
exec python3 -m uvicorn main:app --port 8642
