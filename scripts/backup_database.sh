#!/bin/bash
# PostgreSQL backup script for AP Intake database
# This script creates comprehensive backups with verification and cleanup

set -euo pipefail

# Configuration
DB_NAME="${DB_NAME:-ap_intake}"
DB_USER="${DB_USER:-postgres}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/postgresql}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
DATE=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${BACKUP_DIR}/backup_log_${DATE}.txt"

# Ensure backup directory exists
mkdir -p "${BACKUP_DIR}"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

# Function to check command success
check_success() {
    if [ $? -eq 0 ]; then
        log "✓ $1 completed successfully"
        return 0
    else
        log "✗ $1 failed"
        return 1
    fi
}

# Function to get database size
get_db_size() {
    psql -U "${DB_USER}" -h "${DB_HOST}" -p "${DB_PORT}" -d "${DB_NAME}" -t -c "
        SELECT pg_size_pretty(pg_database_size('${DB_NAME}'));
    " | xargs
}

log "Starting PostgreSQL backup for database: ${DB_NAME}"
log "Backup directory: ${BACKUP_DIR}"
log "Database size: $(get_db_size)"

# Initialize counters
success_count=0
total_backups=6

# 1. Full database backup (custom format)
log "Creating full database backup..."
FULL_BACKUP="${BACKUP_DIR}/full_backup_${DATE}.dump"
pg_dump -U "${DB_USER}" -h "${DB_HOST}" -p "${DB_PORT}" -d "${DB_NAME}" \
    --format=custom \
    --compress=9 \
    --verbose \
    --file="${FULL_BACKUP}" 2>&1 | tee -a "${LOG_FILE}"

if check_success "Full database backup"; then
    BACKUP_SIZE=$(stat -c%s "${FULL_BACKUP}")
    log "Full backup size: $(numfmt --to=iec ${BACKUP_SIZE})"
    ((success_count++))
else
    log "Full backup failed - aborting remaining backups"
    exit 1
fi

# 2. Schema-only backup
log "Creating schema-only backup..."
SCHEMA_BACKUP="${BACKUP_DIR}/schema_backup_${DATE}.sql"
pg_dump -U "${DB_USER}" -h "${DB_HOST}" -p "${DB_PORT}" -d "${DB_NAME}" \
    --schema-only \
    --verbose \
    --file="${SCHEMA_BACKUP}" 2>&1 | tee -a "${LOG_FILE}"

if check_success "Schema-only backup"; then
    ((success_count++))
fi

# 3. Data-only backup (excluding large JSON columns for faster restore)
log "Creating data-only backup..."
DATA_BACKUP="${BACKUP_DIR}/data_backup_${DATE}.sql"
pg_dump -U "${DB_USER}" -h "${DB_HOST}" -p "${DB_PORT}" -d "${DB_NAME}" \
    --data-only \
    --exclude-table='invoice_extractions' \
    --exclude-table='export_jobs' \
    --verbose \
    --file="${DATA_BACKUP}" 2>&1 | tee -a "${LOG_FILE}"

if check_success "Data-only backup"; then
    ((success_count++))
fi

# 4. Critical tables backup (invoices, exceptions, validations)
log "Creating critical tables backup..."
CRITICAL_BACKUP="${BACKUP_DIR}/critical_tables_${DATE}.dump"
pg_dump -U "${DB_USER}" -h "${DB_HOST}" -p "${DB_PORT}" -d "${DB_NAME}" \
    --format=custom \
    --compress=9 \
    --table=invoices \
    --table=invoice_extractions \
    --table=validations \
    --table=exceptions \
    --table=staged_exports \
    --verbose \
    --file="${CRITICAL_BACKUP}" 2>&1 | tee -a "${LOG_FILE}"

if check_success "Critical tables backup"; then
    ((success_count++))
fi

# 5. Configuration backup
log "Creating configuration backup..."
CONFIG_BACKUP="${BACKUP_DIR}/config_backup_${DATE}.sql"
pg_dumpall -U "${DB_USER}" -h "${DB_HOST}" -p "${DB_PORT}" \
    --globals-only \
    --verbose \
    --file="${CONFIG_BACKUP}" 2>&1 | tee -a "${LOG_FILE}"

if check_success "Configuration backup"; then
    ((success_count++))
fi

# 6. Verify backup integrity
log "Verifying backup integrity..."
if pg_restore --list "${FULL_BACKUP}" > /dev/null 2>&1; then
    log "✓ Full backup integrity verified"
    ((success_count++))
else
    log "✗ Full backup integrity check failed"
fi

# Create backup manifest
MANIFEST_FILE="${BACKUP_DIR}/backup_manifest_${DATE}.json"
cat > "${MANIFEST_FILE}" << EOF
{
    "backup_date": "${DATE}",
    "database_name": "${DB_NAME}",
    "database_size": "$(get_db_size)",
    "backups_created": {
        "full_backup": {
            "file": "full_backup_${DATE}.dump",
            "size_bytes": $(stat -c%s "${FULL_BACKUP}" 2>/dev/null || echo "0")
        },
        "schema_backup": {
            "file": "schema_backup_${DATE}.sql",
            "size_bytes": $(stat -c%s "${SCHEMA_BACKUP}" 2>/dev/null || echo "0")
        },
        "data_backup": {
            "file": "data_backup_${DATE}.sql",
            "size_bytes": $(stat -c%s "${DATA_BACKUP}" 2>/dev/null || echo "0")
        },
        "critical_tables_backup": {
            "file": "critical_tables_${DATE}.dump",
            "size_bytes": $(stat -c%s "${CRITICAL_BACKUP}" 2>/dev/null || echo "0")
        },
        "config_backup": {
            "file": "config_backup_${DATE}.sql",
            "size_bytes": $(stat -c%s "${CONFIG_BACKUP}" 2>/dev/null || echo "0")
        }
    },
    "success_rate": "${success_count}/${total_backups}",
    "log_file": "backup_log_${DATE}.txt"
}
EOF

log "Backup manifest created: ${MANIFEST_FILE}"

# Clean up old backups
log "Cleaning up backups older than ${RETENTION_DAYS} days..."
DELETED_COUNT=0

# Clean up old backup files
while IFS= read -r -d '' file; do
    if rm "$file"; then
        ((DELETED_COUNT++))
        log "Deleted old backup: $(basename "$file")"
    fi
done < <(find "${BACKUP_DIR}" -name "full_backup_*.dump" -mtime +${RETENTION_DAYS} -print0)
done < <(find "${BACKUP_DIR}" -name "schema_backup_*.sql" -mtime +${RETENTION_DAYS} -print0)
done < <(find "${BACKUP_DIR}" -name "data_backup_*.sql" -mtime +${RETENTION_DAYS} -print0)
done < <(find "${BACKUP_DIR}" -name "critical_tables_*.dump" -mtime +${RETENTION_DAYS} -print0)
done < <(find "${BACKUP_DIR}" -name "config_backup_*.sql" -mtime +${RETENTION_DAYS} -print0)
done < <(find "${BACKUP_DIR}" -name "backup_log_*.txt" -mtime +${RETENTION_DAYS} -print0)

# Clean up old manifests
find "${BACKUP_DIR}" -name "backup_manifest_*.json" -mtime +${RETENTION_DAYS} -delete

log "Deleted ${DELETED_COUNT} old backup files"

# Calculate total backup size
TOTAL_SIZE=$(du -sh "${BACKUP_DIR}" | cut -f1)
log "Total backup directory size: ${TOTAL_SIZE}"

# Summary
log "Backup operation completed"
log "Success rate: ${success_count}/${total_backups} backups"
log "Backup location: ${BACKUP_DIR}"
log "Log file: ${LOG_FILE}"

# Exit with appropriate code
if [ ${success_count} -eq ${total_backups} ]; then
    log "🎉 All backups completed successfully!"
    exit 0
elif [ ${success_count} -ge 4 ]; then
    log "⚠️  Backup completed with some failures"
    exit 1
else
    log "❌ Backup operation failed significantly"
    exit 2
fi