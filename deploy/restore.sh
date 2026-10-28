#!/bin/sh
# Restore a backup made by backup.sh into this stack. DESTRUCTIVE: replaces the database and the MMS volume.
#   deploy/restore.sh /var/backups/communication-manager/db-2026-10-28T0215.dump [/var/backups/…/sms-media-2026-10-28T0215.tgz]
# Before: put the SAME MAIL_TOKEN_KEYS and SMS_DATA_KEYS (from your offline copy) in .env, or nothing decrypts.
set -eu
dump=${1:?usage: restore.sh <db-….dump> [<sms-media-….tgz>]}
media=${2:-}
project=${COMPOSE_PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}
cd "$project"
checks=$(dirname "$dump")/checksums-$(basename "$dump" .dump | sed 's/^db-//').sha256
if [ -f "$checks" ]; then (cd "$(dirname "$dump")" && sha256sum -c --ignore-missing "$(basename "$checks")"); fi

if [ "${RESTORE_YES:-}" != "1" ]; then
  printf 'This replaces the database%s of %s. Type "restore" to continue: ' "${media:+ and MMS files}" "$project"
  read -r answer
  [ "$answer" = "restore" ] || { echo "aborted"; exit 1; }
fi

docker compose stop backend worker beat frontend
docker compose up -d postgres
db_user=$(docker compose exec -T postgres sh -c 'echo $POSTGRES_USER')
db_name=$(docker compose exec -T postgres sh -c 'echo $POSTGRES_DB')
docker compose exec -T postgres dropdb -U "$db_user" --if-exists "$db_name"
docker compose exec -T postgres createdb -U "$db_user" "$db_name"
docker compose exec -T postgres pg_restore -U "$db_user" -d "$db_name" --no-owner --exit-on-error < "$dump"
if [ -n "$media" ]; then
  docker compose run --rm --no-deps -T -v "$(cd "$(dirname "$media")" && pwd):/backup:ro" --entrypoint sh backend \
    -c "find /data/sms-media -mindepth 1 -delete && tar xzf /backup/$(basename "$media") -C /data/sms-media"
fi
# Queued tasks in Redis refer to the old database state; the beat schedule re-creates what is needed.
docker compose up -d
echo "restored $dump${media:+ and $media}"
