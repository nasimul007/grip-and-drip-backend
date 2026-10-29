#!/usr/bin/env bash
# Restore a backup made by scripts/backup.sh.
#
#   scripts/restore.sh <backup-folder> [--media]
#
# Replaces the tables in DATABASE_URL with the ones in the backup (asks first).
# With --media, also puts the backed-up media folder in place; the current one
# is kept as media.before-restore-<timestamp>.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MEDIA_DIR="${MEDIA_DIR:-$PROJECT_DIR/media}"

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
fail() { log "ERROR: $*"; exit 1; }

[[ $# -ge 1 ]] || fail "usage: $0 <backup-folder> [--media]"
backup="$(cd "$1" && pwd)"
with_media=false
[[ "${2:-}" == "--media" ]] && with_media=true

if [[ -z "${DATABASE_URL:-}" && -f "$PROJECT_DIR/.env" ]]; then
  DATABASE_URL="$(grep -E '^[[:space:]]*DATABASE_URL[[:space:]]*=' "$PROJECT_DIR/.env" | tail -n 1 \
    | sed -E 's/^[^=]*=[[:space:]]*//; s/[[:space:]]+$//; s/^"(.*)"$/\1/; s/^'"'"'(.*)'"'"'$/\1/')"
fi
[[ -n "${DATABASE_URL:-}" ]] || fail "DATABASE_URL is not set (environment or $PROJECT_DIR/.env)"
[[ -f "$backup/db.dump" ]] || fail "$backup/db.dump not found"

log "Checking files"
(cd "$backup" && sha256sum --check --quiet SHA256SUMS) || fail "checksums do not match; backup is damaged"

db_name="${DATABASE_URL##*/}"
db_name="${db_name%%\?*}"
echo "This replaces every table in database '$db_name' with the backup from $(basename "$backup")."
read -r -p "Type the database name to continue: " answer
[[ "$answer" == "$db_name" ]] || fail "cancelled"

log "Restoring database"
pg_restore --clean --if-exists --no-owner --no-privileges --single-transaction \
  --dbname "$DATABASE_URL" "$backup/db.dump"

if $with_media; then
  [[ -f "$backup/media.tar.gz" ]] || fail "this backup has no media.tar.gz"
  parent="$(dirname "$MEDIA_DIR")"
  staging="$(mktemp -d "$parent/.media-restore.XXXXXX")"
  tar -xzf "$backup/media.tar.gz" -C "$staging"
  if [[ -d "$MEDIA_DIR" ]]; then
    kept="$MEDIA_DIR.before-restore-$(date '+%Y%m%d%H%M%S')"
    mv "$MEDIA_DIR" "$kept"
    log "Current media moved to $kept"
  fi
  mv "$staging/$(basename "$MEDIA_DIR")" "$MEDIA_DIR"
  rmdir "$staging"
  log "Media restored to $MEDIA_DIR"
fi

log "Done"
