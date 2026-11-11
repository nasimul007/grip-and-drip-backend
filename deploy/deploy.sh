#!/usr/bin/env bash
# Run on the server after copying new code (and after setup.sh the first time):
# installs dependencies, collects static files, migrates, restarts the app.

set -euo pipefail

APP_DIR=/srv/grip-and-drip/app
export PATH="$HOME/.local/bin:$PATH"
export DJANGO_ENV=prod

cd "$APP_DIR"
uv sync --frozen --no-dev
.venv/bin/python manage.py check --deploy
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py migrate --noinput
sudo systemctl restart gunicorn
sudo systemctl is-active --quiet gunicorn && echo "gunicorn is running"
