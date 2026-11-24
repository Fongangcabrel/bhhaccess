#!/bin/sh
# BHH Access - daily backup (service "backup" of docker-compose.yml, image postgres:16).
#   database : pg_dump custom format  -> /backups/bhhaccess-AAAAMMJJ-HHMM.dump
#   photos   : tar.gz of /data/photos -> /backups/bhhaccess-AAAAMMJJ-HHMM-photos.tar.gz
# Runs every day at BACKUP_TIME (site time, TZ), keeps BACKUP_KEEP_DAYS days.
# "backup.sh now" makes one backup at once and stops (manual backup, restore test).
set -u
: "${BACKUP_TIME:=02:00}"
: "${BACKUP_KEEP_DAYS:=14}"
OUT=/backups

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }

backup() {
    stamp=$(date +%Y%m%d-%H%M)
    name="bhhaccess-$stamp"
    # Written under a temporary name, renamed only when complete: a half-written file never looks valid.
    pg_dump -h db -U bhh -d bhhaccess -Fc -f "$OUT/.$name.dump" || return 1
    tar -czf "$OUT/.$name-photos.tar.gz" -C /data photos || return 1
    mv "$OUT/.$name.dump" "$OUT/$name.dump" || return 1
    mv "$OUT/.$name-photos.tar.gz" "$OUT/$name-photos.tar.gz" || return 1
    find "$OUT" -maxdepth 1 -name 'bhhaccess-*' -mtime +"$BACKUP_KEEP_DAYS" -delete
    log "sauvegarde OK : $name ($(du -h "$OUT/$name.dump" | cut -f1) base, $(du -h "$OUT/$name-photos.tar.gz" | cut -f1) photos)"
}

if [ "${1:-}" = "now" ]; then
    backup || { log "ÉCHEC de la sauvegarde" >&2; exit 1; }
    exit 0
fi

log "sauvegarde quotidienne à $BACKUP_TIME, conservation $BACKUP_KEEP_DAYS jours, dossier $OUT"
while true; do
    now=$(date +%s)
    next=$(date -d "today $BACKUP_TIME" +%s)
    [ "$next" -le "$now" ] && next=$(date -d "tomorrow $BACKUP_TIME" +%s)
    sleep $((next - now))
    if ! backup; then
        log "ÉCHEC de la sauvegarde" >&2
        rm -f "$OUT"/.bhhaccess-*
    fi
done
