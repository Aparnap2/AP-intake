#!/bin/bash

# Backup and Recovery Script for AP Intake & Validation System
# This script handles automated backups and recovery procedures

set -euo pipefail

# Configuration
BACKUP_DIR="/backups"
RETENTION_DAYS=30
S3_BACKUP_BUCKET="ap-intake-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/var/log/backup.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] SUCCESS:${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

# Check prerequisites
check_prerequisites() {
    log "Checking backup prerequisites..."

    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        error "Docker is not running"
    fi

    # Create backup directory
    mkdir -p "$BACKUP_DIR"

    # Load environment variables
    if [[ -f .env ]]; then
        source .env
    else
        error ".env file not found"
    fi

    success "Prerequisites check passed"
}

# Database backup
backup_database() {
    log "Starting database backup..."

    local backup_file="$BACKUP_DIR/database_backup_$TIMESTAMP.sql"
    local compressed_file="$backup_file.gz"

    # Create database backup
    if docker-compose exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$backup_file"; then
        # Compress backup
        gzip "$backup_file"

        success "Database backup created: $compressed_file"
        echo "$compressed_file" >> "$BACKUP_DIR/latest_database_backup.txt"
    else
        error "Database backup failed"
    fi
}

# Redis backup
backup_redis() {
    log "Starting Redis backup..."

    local backup_file="$BACKUP_DIR/redis_backup_$TIMESTAMP.rdb"

    # Create Redis backup
    if docker-compose exec -T redis redis-cli BGSAVE && \
       docker cp $(docker-compose ps -q redis):/data/dump.rdb "$backup_file"; then
        # Compress backup
        gzip "$backup_file"

        success "Redis backup created: $backup_file.gz"
        echo "$backup_file.gz" >> "$BACKUP_DIR/latest_redis_backup.txt"
    else
        error "Redis backup failed"
    fi
}

# Storage backup
backup_storage() {
    log "Starting storage backup..."

    local storage_backup="$BACKUP_DIR/storage_backup_$TIMESTAMP.tar.gz"

    # Create storage backup
    if tar -czf "$storage_backup" storage/; then
        success "Storage backup created: $storage_backup"
        echo "$storage_backup" >> "$BACKUP_DIR/latest_storage_backup.txt"
    else
        error "Storage backup failed"
    fi
}

# Configuration backup
backup_config() {
    log "Starting configuration backup..."

    local config_backup="$BACKUP_DIR/config_backup_$TIMESTAMP.tar.gz"

    # Create configuration backup
    if tar -czf "$config_backup" \
        docker-compose.yml \
        docker-compose.prod.yml \
        nginx/ \
        monitoring/ \
        kubernetes/ \
        .env \
        scripts/; then
        success "Configuration backup created: $config_backup"
        echo "$config_backup" >> "$BACKUP_DIR/latest_config_backup.txt"
    else
        error "Configuration backup failed"
    fi
}

# Upload to S3 (optional)
upload_to_s3() {
    if [[ -n "${AWS_ACCESS_KEY_ID:-}" && -n "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
        log "Uploading backups to S3..."

        local s3_prefix="backups/$(date +%Y/%m/%d)"

        # Upload database backup
        if [[ -f "$BACKUP_DIR/latest_database_backup.txt" ]]; then
            latest_db_backup=$(cat "$BACKUP_DIR/latest_database_backup.txt")
            aws s3 cp "$latest_db_backup" "s3://$S3_BACKUP_BUCKET/$s3_prefix/$(basename $latest_db_backup)"
        fi

        # Upload Redis backup
        if [[ -f "$BACKUP_DIR/latest_redis_backup.txt" ]]; then
            latest_redis_backup=$(cat "$BACKUP_DIR/latest_redis_backup.txt")
            aws s3 cp "$latest_redis_backup" "s3://$S3_BACKUP_BUCKET/$s3_prefix/$(basename $latest_redis_backup)"
        fi

        # Upload storage backup
        if [[ -f "$BACKUP_DIR/latest_storage_backup.txt" ]]; then
            latest_storage_backup=$(cat "$BACKUP_DIR/latest_storage_backup.txt")
            aws s3 cp "$latest_storage_backup" "s3://$S3_BACKUP_BUCKET/$s3_prefix/$(basename $latest_storage_backup)"
        fi

        success "Backups uploaded to S3"
    else
        warning "AWS credentials not configured, skipping S3 upload"
    fi
}

# Cleanup old backups
cleanup_old_backups() {
    log "Cleaning up old backups (older than $RETENTION_DAYS days)..."

    # Remove old database backups
    find "$BACKUP_DIR" -name "database_backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete

    # Remove old Redis backups
    find "$BACKUP_DIR" -name "redis_backup_*.rdb.gz" -mtime +$RETENTION_DAYS -delete

    # Remove old storage backups
    find "$BACKUP_DIR" -name "storage_backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete

    # Remove old configuration backups
    find "$BACKUP_DIR" -name "config_backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete

    success "Old backups cleaned up"
}

# Verify backup integrity
verify_backups() {
    log "Verifying backup integrity..."

    local errors=0

    # Verify database backup
    if [[ -f "$BACKUP_DIR/latest_database_backup.txt" ]]; then
        latest_db_backup=$(cat "$BACKUP_DIR/latest_database_backup.txt")
        if gzip -t "$latest_db_backup" 2>/dev/null; then
            success "Database backup integrity verified"
        else
            error "Database backup integrity check failed"
            errors=$((errors + 1))
        fi
    fi

    # Verify Redis backup
    if [[ -f "$BACKUP_DIR/latest_redis_backup.txt" ]]; then
        latest_redis_backup=$(cat "$BACKUP_DIR/latest_redis_backup.txt")
        if gzip -t "$latest_redis_backup" 2>/dev/null; then
            success "Redis backup integrity verified"
        else
            error "Redis backup integrity check failed"
            errors=$((errors + 1))
        fi
    fi

    # Verify storage backup
    if [[ -f "$BACKUP_DIR/latest_storage_backup.txt" ]]; then
        latest_storage_backup=$(cat "$BACKUP_DIR/latest_storage_backup.txt")
        if tar -tzf "$latest_storage_backup" > /dev/null 2>&1; then
            success "Storage backup integrity verified"
        else
            error "Storage backup integrity check failed"
            errors=$((errors + 1))
        fi
    fi

    if [[ $errors -eq 0 ]]; then
        success "All backup integrity checks passed"
    else
        error "$errors backup integrity checks failed"
    fi
}

# Database recovery
restore_database() {
    local backup_file="${1:-}"

    if [[ -z "$backup_file" ]]; then
        if [[ -f "$BACKUP_DIR/latest_database_backup.txt" ]]; then
            backup_file=$(cat "$BACKUP_DIR/latest_database_backup.txt")
        else
            error "No backup file specified and no latest backup found"
        fi
    fi

    log "Restoring database from $backup_file..."

    # Stop application services
    docker-compose stop api worker scheduler

    # Restore database
    if [[ "$backup_file" == *.gz ]]; then
        gunzip -c "$backup_file" | docker-compose exec -T postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB"
    else
        docker-compose exec -T postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB" < "$backup_file"
    fi

    # Start application services
    docker-compose start api worker scheduler

    success "Database restored from $backup_file"
}

# Full system recovery
restore_full_system() {
    local backup_timestamp="${1:-}"

    if [[ -z "$backup_timestamp" ]]; then
        error "Backup timestamp must be specified for full system recovery"
    fi

    log "Starting full system recovery from backup timestamp: $backup_timestamp"

    # Stop all services
    docker-compose down

    # Restore configuration
    local config_backup="$BACKUP_DIR/config_backup_$backup_timestamp.tar.gz"
    if [[ -f "$config_backup" ]]; then
        log "Restoring configuration..."
        tar -xzf "$config_backup" -C /
    else
        error "Configuration backup not found: $config_backup"
    fi

    # Start core services
    docker-compose up -d postgres redis minio

    # Wait for services to be ready
    sleep 30

    # Restore database
    local db_backup="$BACKUP_DIR/database_backup_$backup_timestamp.sql.gz"
    if [[ -f "$db_backup" ]]; then
        restore_database "$db_backup"
    else
        error "Database backup not found: $db_backup"
    fi

    # Restore storage
    local storage_backup="$BACKUP_DIR/storage_backup_$backup_timestamp.tar.gz"
    if [[ -f "$storage_backup" ]]; then
        log "Restoring storage..."
        tar -xzf "$storage_backup"
    else
        error "Storage backup not found: $storage_backup"
    fi

    # Start all services
    docker-compose up -d

    success "Full system recovery completed"
}

# List available backups
list_backups() {
    log "Available backups:"

    echo -e "\n${YELLOW}Database Backups:${NC}"
    ls -la "$BACKUP_DIR"/database_backup_*.sql.gz 2>/dev/null || echo "No database backups found"

    echo -e "\n${YELLOW}Redis Backups:${NC}"
    ls -la "$BACKUP_DIR"/redis_backup_*.rdb.gz 2>/dev/null || echo "No Redis backups found"

    echo -e "\n${YELLOW}Storage Backups:${NC}"
    ls -la "$BACKUP_DIR"/storage_backup_*.tar.gz 2>/dev/null || echo "No storage backups found"

    echo -e "\n${YELLOW}Configuration Backups:${NC}"
    ls -la "$BACKUP_DIR"/config_backup_*.tar.gz 2>/dev/null || echo "No configuration backups found"
}

# Main backup function
main() {
    local action="${1:-backup}"

    case $action in
        "backup")
            check_prerequisites
            backup_database
            backup_redis
            backup_storage
            backup_config
            verify_backups
            upload_to_s3
            cleanup_old_backups
            success "Backup process completed successfully"
            ;;
        "restore-db")
            check_prerequisites
            restore_database "${2:-}"
            ;;
        "restore-full")
            check_prerequisites
            restore_full_system "${2:-}"
            ;;
        "list")
            list_backups
            ;;
        *)
            echo "Usage: $0 {backup|restore-db [backup_file]|restore-full [timestamp]|list}"
            exit 1
            ;;
    esac
}

# Script usage
usage() {
    echo "Usage: $0 {backup|restore-db [backup_file]|restore-full [timestamp]|list}"
    echo ""
    echo "Commands:"
    echo "  backup           - Create full system backup"
    echo "  restore-db       - Restore database from backup"
    echo "  restore-full     - Restore full system from backup timestamp"
    echo "  list             - List available backups"
    echo ""
    echo "Examples:"
    echo "  $0 backup"
    echo "  $0 restore-db /backups/database_backup_20231201_120000.sql.gz"
    echo "  $0 restore-full 20231201_120000"
    echo "  $0 list"
    exit 1
}

# Handle script arguments
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
fi

# Trap errors
trap 'error "Backup process failed at line $LINENO"' ERR

# Run main function
main "$@"