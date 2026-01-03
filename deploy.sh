#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/srv/my-office-reservation"
BRANCH="main"
VENV_DIR="$APP_DIR/.venv"
SERVICE_NAME="gunicorn"   # 필요하면 실제 서비스명으로 변경

cd "$APP_DIR"

echo "==> Git pull"
git fetch origin
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

echo "==> Activate venv: $VENV_DIR"
if [ ! -d "$VENV_DIR" ]; then
  echo "Venv not found. Creating..."
  python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

echo "==> Upgrade pip"
pip install -U pip wheel

if [ -f "requirements.txt" ]; then
  echo "==> Install requirements"
  pip install -r requirements.txt
else
  echo "⚠️ requirements.txt not found. Skipping dependency install."
fi

if [ -f "manage.py" ]; then
  echo "==> Migrate"
  python manage.py migrate --noinput

  echo "==> Collectstatic"
  python manage.py collectstatic --noinput || true
fi

echo "==> Restart service: $SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "✅ Deploy complete"
