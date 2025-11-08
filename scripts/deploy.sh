#!/bin/bash

# Production Deployment Script for AP Intake & Validation System
# This script automates the deployment process with zero-downtime support

set -euo pipefail

# Configuration
PROJECT_NAME="ap-intake"
BACKUP_DIR="/backups"
LOG_FILE="/var/log/deploy.log"
HEALTH_CHECK_URL="http://localhost/health"
MAX_RETRIES=30
RETRY_INTERVAL=10

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

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        error "This script should not be run as root for security reasons"
    fi
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
    fi

    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed"
    fi

    # Check if .env file exists
    if [[ ! -f .env ]]; then
        error ".env file not found. Please create it from .env.example"
    fi

    # Check if required environment variables are set
    source .env
    required_vars=("POSTGRES_USER" "POSTGRES_PASSWORD" "POSTGRES_DB" "REDIS_PASSWORD" "SECRET_KEY")
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            error "Required environment variable $var is not set"
        fi
    done

    success "Prerequisites check passed"
}

# Create backup of database
create_backup() {
    log "Creating database backup..."

    BACKUP_FILE="$BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).sql"
    mkdir -p "$BACKUP_DIR"

    docker-compose exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$BACKUP_FILE"

    if [[ $? -eq 0 ]]; then
        success "Database backup created: $BACKUP_FILE"
        echo "$BACKUP_FILE" > "$BACKUP_DIR/latest_backup.txt"
    else
        error "Failed to create database backup"
    fi
}

# Pull latest images
pull_images() {
    log "Pulling latest Docker images..."

    docker-compose -f docker-compose.prod.yml pull --quiet

    if [[ $? -eq 0 ]]; then
        success "Images pulled successfully"
    else
        error "Failed to pull images"
    fi
}

# Run database migrations
run_migrations() {
    log "Running database migrations..."

    docker-compose -f docker-compose.prod.yml run --rm api uv run alembic upgrade head

    if [[ $? -eq 0 ]]; then
        success "Database migrations completed successfully"
    else
        error "Database migrations failed"
    fi
}

# Build new images
build_images() {
    log "Building new Docker images..."

    docker-compose -f docker-compose.prod.yml build --parallel

    if [[ $? -eq 0 ]]; then
        success "Images built successfully"
    else
        error "Failed to build images"
    fi
}

# Zero-downtime deployment
deploy_zero_downtime() {
    log "Starting zero-downtime deployment..."

    # Scale up new services
    log "Scaling up new services..."
    docker-compose -f docker-compose.prod.yml up -d --scale api=4 --scale worker=6

    # Wait for new services to be healthy
    wait_for_health_check

    # Gradually scale down old services
    log "Scaling down old services..."
    docker-compose -f docker-compose.prod.yml up -d --scale api=2 --scale worker=3

    success "Zero-downtime deployment completed"
}

# Wait for health check
wait_for_health_check() {
    log "Waiting for application health check..."

    local retries=0
    while [[ $retries -lt $MAX_RETRIES ]]; do
        if curl -f -s "$HEALTH_CHECK_URL" > /dev/null; then
            success "Application is healthy"
            return 0
        fi

        retries=$((retries + 1))
        log "Health check attempt $retries/$MAX_RETRIES failed. Retrying in $RETRY_INTERVAL seconds..."
        sleep "$RETRY_INTERVAL"
    done

    error "Health check failed after $MAX_RETRIES attempts"
}

# Cleanup old images and containers
cleanup() {
    log "Cleaning up old Docker resources..."

    # Remove unused images
    docker image prune -f

    # Remove unused containers
    docker container prune -f

    # Remove unused volumes (be careful with this)
    # docker volume prune -f

    success "Cleanup completed"
}

# Update SSL certificates (if needed)
update_ssl() {
    log "Checking SSL certificates..."

    if [[ -d "nginx/ssl" && -f "nginx/ssl/cert.pem" ]]; then
        # Check if certificate is expiring within 30 days
        local expiry_date
        expiry_date=$(openssl x509 -in nginx/ssl/cert.pem -noout -enddate | cut -d= -f2)
        local expiry_timestamp
        expiry_timestamp=$(date -d "$expiry_date" +%s)
        local current_timestamp
        current_timestamp=$(date +%s)
        local days_until_expiry
        days_until_expiry=$(( (expiry_timestamp - current_timestamp) / 86400 ))

        if [[ $days_until_expiry -lt 30 ]]; then
            warning "SSL certificate expires in $days_until_expiry days"
            # Add certbot renewal logic here if needed
        fi
    fi

    success "SSL certificates checked"
}

# Monitor deployment
monitor_deployment() {
    log "Starting deployment monitoring..."

    # Check resource usage
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

    # Check service logs for errors
    log "Checking recent service logs for errors..."
    docker-compose -f docker-compose.prod.yml logs --tail=50 | grep -i error || true

    success "Deployment monitoring completed"
}

# Rollback function
rollback() {
    log "Initiating rollback..."

    # Stop current services
    docker-compose -f docker-compose.prod.yml down

    # Restore database if needed
    if [[ -f "$BACKUP_DIR/latest_backup.txt" ]]; then
        LATEST_BACKUP=$(cat "$BACKUP_DIR/latest_backup.txt")
        log "Restoring database from $LATEST_BACKUP"
        docker-compose -f docker-compose.prod.yml up -d postgres
        sleep 10
        docker-compose -f docker-compose.prod.yml exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$LATEST_BACKUP"
    fi

    # Restart services
    docker-compose -f docker-compose.prod.yml up -d

    # Wait for health check
    wait_for_health_check

    success "Rollback completed"
}

# Main deployment function
main() {
    log "Starting AP Intake & Validation System deployment..."

    # Check if rollback is requested
    if [[ "${1:-}" == "rollback" ]]; then
        rollback
        exit 0
    fi

    check_root
    check_prerequisites

    # Create backup before deployment
    create_backup

    # Deployment steps
    pull_images
    build_images
    run_migrations
    deploy_zero_downtime

    # Post-deployment tasks
    update_ssl
    cleanup
    monitor_deployment

    success "Deployment completed successfully!"
    log "Application is available at: https://your-domain.com"
    log "Grafana dashboard: https://your-domain.com:3001"
    log "Flower monitoring: https://your-domain.com:5555"
}

# Script usage
usage() {
    echo "Usage: $0 [rollback]"
    echo "  rollback: Rollback to the previous deployment"
    exit 1
}

# Handle script arguments
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
fi

# Trap errors and cleanup
trap 'error "Deployment failed at line $LINENO"' ERR

# Run main function
main "$@"