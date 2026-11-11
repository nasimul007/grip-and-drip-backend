#!/usr/bin/env bash
# One-time server setup for Ubuntu 24.04 (Oracle Cloud ARM or any other VM).
#
# Run as the `ubuntu` user, from the project copied to /srv/grip-and-drip/app:
#   DOMAIN=gadgetandwidget.duckdns.org EMAIL=you@example.com \
#   FRONTEND_ORIGIN=https://your-shop.vercel.app ./deploy/setup.sh
#
# It installs the packages, creates the database and .env, opens the firewall,
# installs nginx and the gunicorn service, and starts nginx. It does NOT run
# migrations or start the app: restore your database dump first (see
# deploy/README.md), then run ./deploy/deploy.sh.

set -euo pipefail

APP_DIR=/srv/grip-and-drip/app
DOMAIN="${DOMAIN:?set DOMAIN, e.g. gadgetandwidget.duckdns.org}"
EMAIL="${EMAIL:?set EMAIL, used by the HTTPS certificate authority for expiry notices}"
FRONTEND_ORIGIN="${FRONTEND_ORIGIN:-https://CHANGE-ME.example.com}"
DB_NAME=grip_and_drip
DB_USER=grip_and_drip

log() { printf '\n==> %s\n' "$*"; }
[[ "$(id -u)" -ne 0 ]] || { echo "Run as the ubuntu user, not root (sudo is used where needed)."; exit 1; }
[[ "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" == "$APP_DIR" ]] \
  || { echo "The project must live in $APP_DIR (nginx and the service use that path)."; exit 1; }

log "Installing packages"
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  nginx postgresql postgresql-client certbot python3-certbot-nginx \
  curl rsync iptables-persistent

log "Adding swap (small VMs run out of RAM during migrations and builds)"
if ! swapon --show | grep -q .; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

log "Opening ports 80 and 443 in the VM firewall (Oracle images block them)"
for port in 80 443; do
  sudo iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null \
    || sudo iptables -I INPUT 1 -p tcp --dport "$port" -j ACCEPT
done
sudo netfilter-persistent save

log "Creating the database"
if [[ ! -f "$APP_DIR/.env" ]]; then
  DB_PASSWORD="$(openssl rand -hex 24)"
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
CREATE ROLE $DB_USER LOGIN PASSWORD '$DB_PASSWORD';
CREATE DATABASE $DB_NAME OWNER $DB_USER;
SQL

  log "Writing $APP_DIR/.env"
  SECRET_KEY="$(openssl rand -hex 40)"
  (
    umask 077
    cat > "$APP_DIR/.env" <<ENV
SECRET_KEY=$SECRET_KEY
DJANGO_ENV=prod
ALLOWED_HOSTS=$DOMAIN
CORS_ALLOWED_ORIGINS=$FRONTEND_ORIGIN
CSRF_TRUSTED_ORIGINS=https://$DOMAIN
NUM_PROXIES=1
CACHE_DIR=/var/tmp/grip-and-drip-cache
DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME
CKEDITOR_UPLOAD_PATH=uploads/
ENV
  )
else
  echo ".env already exists, leaving it and the database untouched."
fi

mkdir -p /var/tmp/grip-and-drip-cache
sudo mkdir -p "$APP_DIR/media" /var/backups/grip-and-drip
sudo chown -R ubuntu:ubuntu "$APP_DIR/media" /var/backups/grip-and-drip
# nginx (www-data) must be able to walk into the app folder to serve static and media.
sudo chmod o+rx /srv /srv/grip-and-drip "$APP_DIR"

log "Installing uv and the Python dependencies"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
(cd "$APP_DIR" && uv sync --frozen --no-dev)

log "Installing the gunicorn service"
sudo cp "$APP_DIR/deploy/gunicorn.service" /etc/systemd/system/gunicorn.service
sudo systemctl daemon-reload
sudo systemctl enable gunicorn

log "Installing the nginx site"
sed "s/__DOMAIN__/$DOMAIN/g" "$APP_DIR/deploy/nginx.conf" \
  | sudo tee /etc/nginx/sites-available/grip-and-drip >/dev/null
sudo ln -sf /etc/nginx/sites-available/grip-and-drip /etc/nginx/sites-enabled/grip-and-drip
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

log "Requesting the HTTPS certificate (the domain must already point at this server)"
sudo certbot --nginx -d "$DOMAIN" -m "$EMAIL" --agree-tos --no-eff-email --redirect --non-interactive

log "Scheduling the nightly backup (02:30, local copies only)"
echo "30 2 * * * ubuntu $APP_DIR/scripts/backup.sh >> /var/log/grip-and-drip-backup.log 2>&1" \
  | sudo tee /etc/cron.d/grip-and-drip-backup >/dev/null
sudo touch /var/log/grip-and-drip-backup.log
sudo chown ubuntu /var/log/grip-and-drip-backup.log

log "Server ready. Next: restore the database, then ./deploy/deploy.sh (see deploy/README.md)."
[[ "$FRONTEND_ORIGIN" != *CHANGE-ME* ]] \
  || echo "WARNING: set CORS_ALLOWED_ORIGINS in $APP_DIR/.env to your frontend URL before going live."
