# Grip & Drip backend

## Backups

`scripts/backup.sh` saves the Postgres database and the `media/` folder (product, variant and brand images).

Needs `postgresql-client` on the server, the same major version as the database server or newer:

```sh
sudo apt install postgresql-client
```

The script reads `DATABASE_URL` from the environment, or from the project's `.env` if it isn't set.

### Run it every night

```sh
sudo mkdir -p /var/backups/grip-and-drip
sudo chown "$USER" /var/backups/grip-and-drip
crontab -e
```

Add:

```
15 3 * * * cd /path/to/grip-and-drip-backend && scripts/backup.sh >> /var/log/grip-and-drip-backup.log 2>&1
```

Each run creates `/var/backups/grip-and-drip/daily/<date_time>/` with:

- `db.dump`: the database (compressed `pg_dump` custom format)
- `media.tar.gz`: the uploaded files
- `SHA256SUMS`: checksums used by the restore script

Sunday backups are also kept in `weekly/`. By default the last 14 daily and 8 weekly backups are kept; older ones are deleted. Change this with `KEEP_DAILY`, `KEEP_WEEKLY`, `BACKUP_DIR` or `MEDIA_DIR` in front of the command.

The backups sit on the same server as the database, so they will not help if the server itself is lost. Copy `/var/backups/grip-and-drip` somewhere else from time to time.

### Restore

```sh
scripts/restore.sh /var/backups/grip-and-drip/daily/2026-10-29_031500            # database only
scripts/restore.sh /var/backups/grip-and-drip/daily/2026-10-29_031500 --media    # database and media
```

The script checks the files, asks you to type the database name, then replaces every table with the backup. With `--media` the current media folder is kept as `media.before-restore-<time>` next to the restored one. Stop the app before restoring and start it again afterwards.
