#!/usr/bin/env bash
# Back up the Postgres database and the uploaded media folder.
#
# Each run creates BACKUP_DIR/daily/<timestamp>/ with db.dump, media.tar.gz and
# SHA256SUMS. Sunday backups are also kept under BACKUP_DIR/weekly/. Old copies
# are rotated out. Exits non-zero on any failure so cron reports it.
#
# Settings (environment variables):
#   DATABASE_URL  postgresql://user:pass@host:port/db  (falls back to the .env file)
#   BACKUP_DIR    where backups go          (default /var/backups/grip-and-drip)
#   KEEP_DAILY    daily copies to keep      (default 14)
#   KEEP_WEEKLY   weekly copies to keep     (default 8)
#   MEDIA_DIR     uploaded files to include (default <project>/media)

set -euo pipefail
umask 077

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/grip-and-drip}"
KEEP_DAILY="${KEEP_DAILY:-14}"
KEEP_WEEKLY="${KEEP_WEEKLY:-8}"
MEDIA_DIR="${MEDIA_DIR:-$PROJECT_DIR/media}"

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
fail() { log "ERROR: $*"; exit 1; }

# DATABASE_URL from the environment, else the one line from .env (never sourced).
if [[ -z "${DATABASE_URL:-}" && -f "$PROJECT_DIR/.env" ]]; then
  DATABASE_URL="$(grep -E '^[[:space:]]*DATABASE_URL[[:space:]]*=' "$PROJECT_DIR/.env" | tail -n 1 \
    | sed -E 's/^[^=]*=[[:space:]]*//; s/[[:space:]]+$//; s/^"(.*)"$/\1/; s/^'"'"'(.*)'"'"'$/\1/')"
fi
[[ -n "${DATABASE_URL:-}" ]] || fail "DATABASE_URL is not set (environment or $PROJECT_DIR/.env)"

for tool in pg_dump pg_restore tar sha256sum flock; do
  command -v "$tool" >/dev/null || fail "$tool is not installed"
done

mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"
chmod 700 "$BACKUP_DIR"

# One run at a time.
exec 9>"$BACKUP_DIR/.lock"
flock -n 9 || fail "another backup is already running"

stamp="$(date '+%Y-%m-%d_%H%M%S')"
partial="$BACKUP_DIR/daily/$stamp.partial"
final="$BACKUP_DIR/daily/$stamp"
trap 'rm -rf "$partial"' EXIT
mkdir "$partial"

log "Dumping database"
pg_dump --format=custom --no-owner --no-privileges --file "$partial/db.dump" "$DATABASE_URL"
pg_restore --list "$partial/db.dump" >/dev/null || fail "the dump cannot be read back"

if [[ -d "$MEDIA_DIR" ]]; then
  log "Archiving $MEDIA_DIR"
  tar -czf "$partial/media.tar.gz" -C "$(dirname "$MEDIA_DIR")" "$(basename "$MEDIA_DIR")"
else
  log "No media folder at $MEDIA_DIR, skipping"
fi

(cd "$partial" && sha256sum -- * > SHA256SUMS)
mv "$partial" "$final"
trap - EXIT
log "Backup written to $final ($(du -sh "$final" | cut -f1))"

# Sunday copy for the weekly set (hard links, so no extra disk space).
if [[ "$(date +%u)" == 7 ]]; then
  cp -al "$final" "$BACKUP_DIR/weekly/$stamp"
  log "Kept as weekly backup"
fi

# Keep the newest N finished backups in a folder; names sort by time.
rotate() {
  local dir="$1" keep="$2"
  find "$dir" -mindepth 1 -maxdepth 1 -type d ! -name '*.partial' -printf '%f\n' \
    | sort -r | tail -n +"$((keep + 1))" \
    | while read -r old; do
        rm -rf -- "${dir:?}/$old"
        log "Removed old backup $dir/$old"
      done
}
rotate "$BACKUP_DIR/daily" "$KEEP_DAILY"
rotate "$BACKUP_DIR/weekly" "$KEEP_WEEKLY"
# Leftovers from runs that were killed before they could clean up.
find "$BACKUP_DIR/daily" -mindepth 1 -maxdepth 1 -type d -name '*.partial' -mmin +1440 -exec rm -rf {} +

log "Done"
