# Deploying to a single Ubuntu 24.04 VM

Layout on the server: nginx (HTTPS, static, media) -> gunicorn (unix socket) ->
Django, with Postgres on the same machine. The app lives in
`/srv/gad-and-wid`.

## 1. Before you start
- The VM has a public IP, and ports 80/443 are open in the cloud firewall
  (Oracle: VCN security list ingress rules for TCP 80 and 443).
- The domain (DuckDNS) points at that IP: `nslookup gadgetandwidget.duckdns.org`.

## 2. Copy the project to the server (from your computer)
Replace the key path and IP.

```bash
ssh -i ~/Downloads/ssh-key.key ubuntu@130.210.4.177 "sudo mkdir -p /srv/gad-and-wid && sudo chown -R ubuntu:ubuntu /srv/gad-and-wid"
```

```bash
rsync -az --progress -e "ssh -i ~/Downloads/ssh-key.key" \
  --exclude .venv --exclude .git --exclude __pycache__ --exclude .env --exclude .cache \
  --exclude '*.dump' --exclude '*.sql' --exclude staticfiles \
  ./ ubuntu@130.210.4.177:/srv/gad-and-wid/
```

The database dump goes separately:

```bash
scp -i ~/Downloads/ssh-key.key grip_and_drip.dump ubuntu@130.210.4.177:/tmp/
```

## 3. Run the setup (on the server)

```bash
cd /srv/gad-and-wid && chmod +x deploy/*.sh scripts/*.sh
DOMAIN=gadgetandwidget.duckdns.org EMAIL=you@example.com \
FRONTEND_ORIGIN=https://your-shop.vercel.app ./deploy/setup.sh
```

If you don't know the frontend URL yet, leave `FRONTEND_ORIGIN` out and edit
`CORS_ALLOWED_ORIGINS` in `/srv/gad-and-wid/.env` later.

## 4. Restore the database, then start the app

```bash
cd /srv/gad-and-wid
DB_URL=$(grep ^DATABASE_URL .env | cut -d= -f2-)
pg_restore --no-owner --no-privileges --dbname "$DB_URL" /tmp/grip_and_drip.dump
./deploy/deploy.sh
.venv/bin/python manage.py createsuperuser   # only if the dump has no admin you can log in with
```

`pg_restore` may print warnings about the `public` schema or extensions; check
that the products table has rows before continuing:

```bash
psql "$DB_URL" -c "select count(*) from products_product;"
```

## 5. Check it works

```bash
curl -I https://gadgetandwidget.duckdns.org/api/products/
```

Open `https://gadgetandwidget.duckdns.org/admin/` and log in. An image such as
`https://gadgetandwidget.duckdns.org/media/products/images/...` should load.

## 6. Frontend
Set `NEXT_PUBLIC_API_URL=https://gadgetandwidget.duckdns.org` and
`NEXT_PUBLIC_SITE_URL` on the frontend host, deploy it, then put the frontend
URL into `CORS_ALLOWED_ORIGINS` in `.env` and run
`sudo systemctl restart gunicorn`.

## Updating later
Re-run the rsync from step 2, then on the server `./deploy/deploy.sh`.

## Backups
`setup.sh` schedules `scripts/backup.sh` nightly to `/var/backups/grip-and-drip`
on the same disk. That does not survive losing the VM: copy those folders
off-site (Backblaze B2, R2, Google Drive) as well.

## Moving to a real domain
Change `DOMAIN` in `.env` (`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`), the
`server_name` in `/etc/nginx/sites-available/grip-and-drip`, point DNS at the
IP, run `sudo certbot --nginx -d new.domain`, and update the frontend's
`NEXT_PUBLIC_API_URL`.
