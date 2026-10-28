#!/bin/sh
# Nightly backup: PostgreSQL (pg_dump custom format) and the encrypted MMS volume, with retention.
#   /opt/communication-manager/deploy/backup.sh            # crontab: 15 2 * * * /opt/communication-manager/deploy/backup.sh
# Env: BACKUP_DIR (/var/backups/communication-manager), BACKUP_RETENTION_DAYS (14), COMPOSE_PROJECT_DIR (repo root).
#
# The dump holds encrypted mailbox tokens and encrypted SMS/call notes; the media archive holds encrypted MMS files.
# Both are useless without MAIL_TOKEN_KEYS / SMS_DATA_KEYS, which are NOT in this backup: keep the keys offline, apart
# from the backups (docs/deployment.md § Backups). Copy the backup directory off the server (rsync, restic, rclone).
set -eu
project=${COMPOSE_PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}
dir=${BACKUP_DIR:-/var/backups/communication-manager}
keep=${BACKUP_RETENTION_DAYS:-14}
stamp=$(date +%Y-%m-%dT%H%M)
cd "$project"
mkdir -p "$dir"
chmod 700 "$dir"
umask 077

db_user=$(docker compose exec -T postgres sh -c 'echo $POSTGRES_USER')
db_name=$(docker compose exec -T postgres sh -c 'echo $POSTGRES_DB')
dump="$dir/db-$stamp.dump"
docker compose exec -T postgres pg_dump -U "$db_user" -d "$db_name" -Fc --no-owner > "$dump.part"
# A dump that pg_restore cannot list is not a backup.
docker compose exec -T postgres pg_restore --list < "$dump.part" > /dev/null
mv "$dump.part" "$dump"

media="$dir/sms-media-$stamp.tgz"
docker compose run --rm --no-deps -T -v "$dir:/backup" --entrypoint sh backend -c "tar czf /backup/$(basename "$media").part -C /data/sms-media ."
mv "$media.part" "$media"

( cd "$dir" && sha256sum "$(basename "$dump")" "$(basename "$media")" > "checksums-$stamp.sha256" )
find "$dir" -maxdepth 1 -type f \( -name 'db-*.dump' -o -name 'sms-media-*.tgz' -o -name 'checksums-*.sha256' \) -mtime +"$keep" -delete
echo "backup ok: $dump ($(du -h "$dump" | cut -f1)), $media ($(du -h "$media" | cut -f1))"
