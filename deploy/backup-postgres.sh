#!/usr/bin/env bash
set -euo pipefail
umask 077

backup_dir=${BACKUP_DIR:-/var/backups/skat-service}
retention_days=${BACKUP_RETENTION_DAYS:-14}
if [[ "$backup_dir" != /* || ! "$retention_days" =~ ^[1-9][0-9]*$ ]]; then
    echo 'BACKUP_DIR must be absolute and BACKUP_RETENTION_DAYS a positive integer.' >&2
    exit 2
fi

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
compose=(docker compose -f compose.prod.yaml)

mkdir -p -- "$backup_dir"
exec 9>"$backup_dir/.backup.lock"
flock -x 9

archive=$(mktemp -- "$backup_dir/.skat-postgres.XXXXXXXX")
trap 'rm -f -- "$archive"' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

"${compose[@]}" exec -T db sh -ec '
    exec pg_dump --no-password --format=custom --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"
' > "$archive"
test -s "$archive"
"${compose[@]}" exec -T db pg_restore --list < "$archive" > /dev/null

destination="$backup_dir/skat-postgres-$(date -u +%Y%m%dT%H%M%S%NZ).dump"
mv -- "$archive" "$destination"
find "$backup_dir" -maxdepth 1 -type f -name 'skat-postgres-*.dump' \
    -mmin "+$((retention_days * 1440))" -delete
printf 'PostgreSQL backup: %s\n' "$destination"
