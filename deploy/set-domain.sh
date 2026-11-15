#!/usr/bin/env bash
# Point the API at a new hostname: updates .env, rewrites the nginx site,
# gets an HTTPS certificate for it and restarts gunicorn.
#
# Run on the server, from the project folder:
#   API_DOMAIN=api.gadgetandwidget.shop \
#   FRONTEND_ORIGIN=https://gadgetandwidget.shop,https://www.gadgetandwidget.shop \
#   EMAIL=you@example.com ./deploy/set-domain.sh

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DOMAIN="${API_DOMAIN:?set API_DOMAIN, e.g. api.gadgetandwidget.shop}"
FRONTEND_ORIGIN="${FRONTEND_ORIGIN:?set FRONTEND_ORIGIN, comma separated, e.g. https://gadgetandwidget.shop}"
EMAIL="${EMAIL:?set EMAIL, used by the HTTPS certificate authority for expiry notices}"

log() { printf '\n==> %s\n' "$*"; }
[[ -f "$APP_DIR/.env" ]] || { echo "$APP_DIR/.env not found; run deploy/setup.sh first."; exit 1; }

# Replace KEY=... in .env, or add it when missing. '|' never occurs in these values.
set_env() {
  local key="$1" value="$2"
  if grep -q "^$key=" "$APP_DIR/.env"; then
    sed -i "s|^$key=.*|$key=$value|" "$APP_DIR/.env"
  else
    echo "$key=$value" >> "$APP_DIR/.env"
  fi
}

log "Updating $APP_DIR/.env"
cp "$APP_DIR/.env" "$APP_DIR/.env.bak"
set_env ALLOWED_HOSTS "$API_DOMAIN"
set_env CSRF_TRUSTED_ORIGINS "https://$API_DOMAIN"
set_env CORS_ALLOWED_ORIGINS "$FRONTEND_ORIGIN"

log "Rewriting the nginx site for $API_DOMAIN"
sed -e "s/__DOMAIN__/$API_DOMAIN/g" -e "s#__APP_DIR__#$APP_DIR#g" "$APP_DIR/deploy/nginx.conf" \
  | sudo tee /etc/nginx/sites-available/grip-and-drip >/dev/null
sudo nginx -t
sudo systemctl reload nginx

log "Requesting the HTTPS certificate (DNS must already point at this server, proxy off)"
sudo certbot --nginx -d "$API_DOMAIN" -m "$EMAIL" --agree-tos --no-eff-email --redirect --non-interactive

sudo systemctl restart gunicorn
sudo systemctl is-active --quiet gunicorn && echo "gunicorn is running"
echo "Old settings kept in $APP_DIR/.env.bak"
