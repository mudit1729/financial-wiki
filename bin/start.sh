#!/usr/bin/env sh
set -eu

export FLASK_APP="${FLASK_APP:-run.py}"

flask db upgrade

exec gunicorn --bind "0.0.0.0:${PORT:-8000}" run:app
