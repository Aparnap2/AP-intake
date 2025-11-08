#!/bin/bash

# Comprehensive Health Check Script for AP Intake & Validation System
# This script monitors system health and provides detailed status reports

set -euo pipefail

# Configuration
HEALTH_CHECK_URL="http://localhost/health"
METRICS_URL="http://localhost:8000/metrics"
LOG_FILE="/var/log/health-check.log"
REPORT_FILE="/tmp/health-report-$(date +%Y%m%d_%H%M%S).json"
CRITICAL_THRESHOLD=90
WARNING_THRESHOLD=70

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Health status levels
STATUS_CRITICAL=0
STATUS_WARNING=1
STATUS_HEALTHY=2

# Initialize health report
echo '{"health_report": {' > "$REPORT_FILE"
echo '"timestamp": "'$(date -Iseconds)'",' >> "$REPORT_FILE"
echo '"overall_status": "unknown",' >> "$REPORT_FILE"
echo '"checks": [' >> "$REPORT_FILE"

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] SUCCESS:${NC} $1" | tee -a "$LOG_FILE"
}

# Add check to report
add_check() {
    local name="$1"
    local status="$2"
    local status_level="$3"
    local details="$4"
    local metrics="$5"

    cat >> "$REPORT_FILE" <<EOF
{
  "name": "$name",
  "status": "$status",
  "status_level": $status_level,
  "details": "$details",
  "metrics": $metrics
},
EOF
}

# Check application health
check_application_health() {
    log "Checking application health..."

    local status="unknown"
    local status_level=$STATUS_CRITICAL
    local details=""
    local metrics='{}'

    # Check API health endpoint
    if curl -f -s "$HEALTH_CHECK_URL" > /dev/null 2>&1; then
        local response=$(curl -s "$HEALTH_CHECK_URL")
        status="healthy"
        status_level=$STATUS_HEALTHY
        details="API responding normally"

        # Extract metrics from health response
        local version=$(echo "$response" | grep -o '"version":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
        local environment=$(echo "$response" | grep -o '"environment":"[^"]*"' | cut -d'"' -f4 || echo "unknown")

        metrics="{\"version\":\"$version\",\"environment\":\"$environment\"}"
    else
        status="unhealthy"
        status_level=$STATUS_CRITICAL
        details="API health check failed"
        metrics="{\"error\":\"connection_failed\"}"
    fi

    add_check "Application Health" "$status" $status_level "$details" "$metrics"
}

# Check database connectivity
check_database_health() {
    log "Checking database health..."

    local status="unknown"
    local status_level=$STATUS_CRITICAL
    local details=""
    local metrics='{}'

    # Check database connection
    if docker-compose exec -T postgres pg_isready -U "${POSTGRES_USER:-postgres}" > /dev/null 2>&1; then
        # Get database metrics
        local connections=$(docker-compose exec -T postgres psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-ap_intake}" -t -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';" | tr -d ' ')
        local db_size=$(docker-compose exec -T postgres psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-ap_intake}" -t -c "SELECT pg_size_pretty(pg_database_size('${POSTGRES_DB:-ap_intake}'));" | tr -d ' ')

        status="healthy"
        status_level=$STATUS_HEALTHY
        details="Database responding normally"
        metrics="{\"active_connections\":$connections,\"database_size\":\"$db_size\"}"

        # Check connection count
        if [[ $connections -gt 80 ]]; then
            status="warning"
            status_level=$STATUS_WARNING
            details="High number of active connections: $connections"
        fi
    else
        status="unhealthy"
        status_level=$STATUS_CRITICAL
        details="Database connection failed"
        metrics="{\"error\":\"connection_failed\"}"
    fi

    add_check "Database Health" "$status" $status_level "$details" "$metrics"
}

# Check Redis connectivity
check_redis_health() {
    log "Checking Redis health..."

    local status="unknown"
    local status_level=$STATUS_CRITICAL
    local details=""
    local metrics='{}'

    # Check Redis connection
    if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        # Get Redis metrics
        local memory_usage=$(docker-compose exec -T redis redis-cli info memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')
        local connected_clients=$(docker-compose exec -T redis redis-cli info clients | grep connected_clients | cut -d: -f2 | tr -d '\r')
        local keyspace_hits=$(docker-compose exec -T redis redis-cli info stats | grep keyspace_hits | cut -d: -f2 | tr -d '\r')
        local keyspace_misses=$(docker-compose exec -T redis redis-cli info stats | grep keyspace_misses | cut -d: -f2 | tr -d '\r')

        status="healthy"
        status_level=$STATUS_HEALTHY
        details="Redis responding normally"
        metrics="{\"memory_usage\":\"$memory_usage\",\"connected_clients\":$connected_clients,\"keyspace_hits\":$keyspace_hits,\"keyspace_misses\":$keyspace_misses}"
    else
        status="unhealthy"
        status_level=$STATUS_CRITICAL
        details="Redis connection failed"
        metrics="{\"error\":\"connection_failed\"}"
    fi

    add_check "Redis Health" "$status" $status_level "$details" "$metrics"
}

# Check Celery workers
check_celery_health() {
    log "Checking Celery worker health..."

    local status="unknown"
    local status_level=$STATUS_CRITICAL
    local details=""
    local metrics='{}'

    # Check if Celery workers are running
    if docker-compose exec -T api celery -A app.workers.celery_app inspect active > /dev/null 2>&1; then
        # Get worker metrics
        local active_workers=$(docker-compose exec -T api celery -A app.workers.celery_app inspect active | grep -c "worker" || echo "0")
        local active_tasks=$(docker-compose exec -T api celery -A app.workers.celery_app inspect active | grep -c "uuid" || echo "0")

        status="healthy"
        status_level=$STATUS_HEALTHY
        details="Celery workers responding normally"
        metrics="{\"active_workers\":$active_workers,\"active_tasks\":$active_tasks}"

        if [[ $active_workers -eq 0 ]]; then
            status="critical"
            status_level=$STATUS_CRITICAL
            details="No active Celery workers found"
        elif [[ $active_tasks -gt 100 ]]; then
            status="warning"
            status_level=$STATUS_WARNING
            details="High number of active tasks: $active_tasks"
        fi
    else
        status="unhealthy"
        status_level=$STATUS_CRITICAL
        details="Celery workers not responding"
        metrics="{\"error\":\"workers_unavailable\"}"
    fi

    add_check "Celery Workers" "$status" $status_level "$details" "$metrics"
}

# Check storage health
check_storage_health() {
    log "Checking storage health..."

    local status="unknown"
    local status_level=$STATUS_CRITICAL
    local details=""
    local metrics='{}'

    # Check storage directories
    local storage_dirs=("storage" "exports" "logs")
    local all_healthy=true

    for dir in "${storage_dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            all_healthy=false
            break
        fi
    done

    if $all_healthy; then
        # Get storage metrics
        local storage_usage=$(df -h storage | tail -1 | awk '{print $5}' | sed 's/%//')
        local storage_available=$(df -h storage | tail -1 | awk '{print $4}')
        local file_count=$(find storage -type f | wc -l)

        status="healthy"
        status_level=$STATUS_HEALTHY
        details="Storage directories accessible"
        metrics="{\"storage_usage\":$storage_usage,\"storage_available\":\"$storage_available\",\"file_count\":$file_count}"

        if [[ $storage_usage -gt 90 ]]; then
            status="critical"
            status_level=$STATUS_CRITICAL
            details="Storage usage critical: ${storage_usage}%"
        elif [[ $storage_usage -gt 80 ]]; then
            status="warning"
            status_level=$STATUS_WARNING
            details="Storage usage high: ${storage_usage}%"
        fi
    else
        status="unhealthy"
        status_level=$STATUS_CRITICAL
        details="Storage directories not accessible"
        metrics="{\"error\":\"storage_unavailable\"}"
    fi

    add_check "Storage Health" "$status" $status_level "$details" "$metrics"
}

# Check MinIO health
check_minio_health() {
    log "Checking MinIO health..."

    local status="unknown"
    local status_level=$STATUS_CRITICAL
    local details=""
    local metrics='{}'

    # Check MinIO health endpoint
    if curl -f -s "http://localhost:9000/minio/health/live" > /dev/null 2>&1; then
        status="healthy"
        status_level=$STATUS_HEALTHY
        details="MinIO responding normally"
        metrics="{\"endpoint\":\"http://localhost:9000\"}"
    else
        status="unhealthy"
        status_level=$STATUS_CRITICAL
        details="MinIO health check failed"
        metrics="{\"error\":\"connection_failed\"}"
    fi

    add_check "MinIO Health" "$status" $status_level "$details" "$metrics"
}

# Check system resources
check_system_resources() {
    log "Checking system resources..."

    local status="unknown"
    local status_level=$STATUS_HEALTHY
    local details=""
    local metrics='{}'

    # Get system metrics
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//')
    local memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    local disk_usage=$(df -h / | tail -1 | awk '{print $5}' | sed 's/%//')
    local load_average=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')

    metrics="{\"cpu_usage\":$cpu_usage,\"memory_usage\":$memory_usage,\"disk_usage\":$disk_usage,\"load_average\":$load_average}"

    # Determine status based on thresholds
    local issues=0
    local issue_details=()

    # CPU check
    if (( $(echo "$cpu_usage > 90" | bc -l) )); then
        issues=$((issues + 1))
        issue_details+=("High CPU usage: ${cpu_usage}%")
        status_level=$STATUS_CRITICAL
    elif (( $(echo "$cpu_usage > 70" | bc -l) )); then
        issues=$((issues + 1))
        issue_details+=("Elevated CPU usage: ${cpu_usage}%")
        if [[ $status_level -eq $STATUS_HEALTHY ]]; then
            status_level=$STATUS_WARNING
        fi
    fi

    # Memory check
    if (( $(echo "$memory_usage > 90" | bc -l) )); then
        issues=$((issues + 1))
        issue_details+=("High memory usage: ${memory_usage}%")
        status_level=$STATUS_CRITICAL
    elif (( $(echo "$memory_usage > 80" | bc -l) )); then
        issues=$((issues + 1))
        issue_details+=("Elevated memory usage: ${memory_usage}%")
        if [[ $status_level -eq $STATUS_HEALTHY ]]; then
            status_level=$STATUS_WARNING
        fi
    fi

    # Disk check
    if [[ $disk_usage -gt 90 ]]; then
        issues=$((issues + 1))
        issue_details+=("High disk usage: ${disk_usage}%")
        status_level=$STATUS_CRITICAL
    elif [[ $disk_usage -gt 80 ]]; then
        issues=$((issues + 1))
        issue_details+=("Elevated disk usage: ${disk_usage}%")
        if [[ $status_level -eq $STATUS_HEALTHY ]]; then
            status_level=$STATUS_WARNING
        fi
    fi

    # Set status and details
    if [[ $issues -eq 0 ]]; then
        status="healthy"
        details="System resources within normal limits"
    elif [[ $status_level -eq $STATUS_CRITICAL ]]; then
        status="critical"
        details=$(IFS='; '; echo "${issue_details[*]}")
    elif [[ $status_level -eq $STATUS_WARNING ]]; then
        status="warning"
        details=$(IFS='; '; echo "${issue_details[*]}")
    else
        status="warning"
        details="Minor resource utilization concerns"
    fi

    add_check "System Resources" "$status" $status_level "$details" "$metrics"
}

# Check SSL certificates
check_ssl_health() {
    log "Checking SSL certificate health..."

    local status="unknown"
    local status_level=$STATUS_HEALTHY
    local details=""
    local metrics='{}'

    # Check if SSL certificate exists
    if [[ -f "nginx/ssl/cert.pem" ]]; then
        # Get certificate expiry
        local expiry_date=$(openssl x509 -in nginx/ssl/cert.pem -noout -enddate | cut -d= -f2)
        local expiry_timestamp=$(date -d "$expiry_date" +%s)
        local current_timestamp=$(date +%s)
        local days_until_expiry=$(( (expiry_timestamp - current_timestamp) / 86400 ))

        metrics="{\"expiry_date\":\"$expiry_date\",\"days_until_expiry\":$days_until_expiry}"

        if [[ $days_until_expiry -lt 7 ]]; then
            status="critical"
            status_level=$STATUS_CRITICAL
            details="SSL certificate expires in $days_until_expiry days"
        elif [[ $days_until_expiry -lt 30 ]]; then
            status="warning"
            status_level=$STATUS_WARNING
            details="SSL certificate expires in $days_until_expiry days"
        else
            status="healthy"
            details="SSL certificate valid for $days_until_expiry days"
        fi
    else
        status="warning"
        status_level=$STATUS_WARNING
        details="SSL certificate not found"
        metrics="{\"error\":\"certificate_not_found\"}"
    fi

    add_check "SSL Certificate" "$status" $status_level "$details" "$metrics"
}

# Calculate overall health score
calculate_overall_health() {
    # Remove trailing comma and close JSON
    sed -i '$ s/,$//' "$REPORT_FILE"
    echo '],' >> "$REPORT_FILE"

    # Count status levels
    local critical_count=$(grep -c '"status_level": 0' "$REPORT_FILE" || true)
    local warning_count=$(grep -c '"status_level": 1' "$REPORT_FILE" || true)
    local healthy_count=$(grep -c '"status_level": 2' "$REPORT_FILE" || true)
    local total_checks=$((critical_count + warning_count + healthy_count))

    # Calculate health score (0-100)
    local health_score=0
    if [[ $total_checks -gt 0 ]]; then
        health_score=$(( (healthy_count * 100 + warning_count * 50) / total_checks ))
    fi

    # Determine overall status
    local overall_status="healthy"
    if [[ $critical_count -gt 0 ]]; then
        overall_status="critical"
    elif [[ $warning_count -gt 0 ]]; then
        overall_status="warning"
    fi

    # Add summary to report
    cat >> "$REPORT_FILE" <<EOF
"summary": {
  "total_checks": $total_checks,
  "critical_count": $critical_count,
  "warning_count": $warning_count,
  "healthy_count": $healthy_count,
  "health_score": $health_score,
  "overall_status": "$overall_status"
}
}
}
EOF

    echo "$overall_status"
}

# Generate health recommendations
generate_recommendations() {
    local overall_status="$1"
    local health_score="$2"

    log "Generating health recommendations..."

    local cat <<EOF > "/tmp/health-recommendations-$(date +%Y%m%d_%H%M%S).md"
# Health Check Recommendations

## Current Status: $overall_status
## Health Score: $health_score/100

EOF

    if [[ "$overall_status" == "critical" ]]; then
        cat >> "/tmp/health-recommendations-$(date +%Y%m%d_%H%M%S).md" <<EOF
## Immediate Action Required

### Critical Issues
- Review all critical findings immediately
- Check system logs for errors
- Verify service dependencies
- Consider emergency maintenance procedures

### Next Steps
1. Address critical service failures
2. Verify data integrity
3. Implement temporary fixes
4. Schedule permanent resolutions

EOF
    elif [[ "$overall_status" == "warning" ]]; then
        cat >> "/tmp/health-recommendations-$(date +%Y%m%d_%H%M%S).md" <<EOF
## Action Recommended

### Warning Items
- Monitor system performance closely
- Plan maintenance for warning items
- Review resource utilization
- Check for potential bottlenecks

### Next Steps
1. Optimize resource usage
2. Schedule preventive maintenance
3. Monitor trends over time
4. Plan capacity upgrades if needed

EOF
    else
        cat >> "/tmp/health-recommendations-$(date +%Y%m%d_%H%M%S).md" <<EOF
## System Healthy

### Current Status
- All systems operating normally
- Resource utilization within limits
- No immediate action required

### Maintenance Recommendations
1. Continue regular monitoring
2. Schedule routine maintenance
3. Monitor for trends
4. Plan future capacity needs

EOF
    fi

    success "Health recommendations generated"
}

# Main health check function
main() {
    local mode="${1:-check}"

    case $mode in
        "check")
            log "Starting comprehensive health check..."

            # Run all health checks
            check_application_health
            check_database_health
            check_redis_health
            check_celery_health
            check_storage_health
            check_minio_health
            check_system_resources
            check_ssl_health

            # Calculate overall health
            local overall_status=$(calculate_overall_health)
            local health_score=$(grep -o '"health_score": [0-9]*' "$REPORT_FILE" | cut -d: -f2 | tr -d ' ')

            # Generate recommendations
            generate_recommendations "$overall_status" "$health_score"

            # Output results
            echo -e "\n${BLUE}=== HEALTH CHECK RESULTS ===${NC}"
            echo -e "Overall Status: ${overall_status^^}"
            echo -e "Health Score: ${health_score}/100"
            echo -e "Report saved to: $REPORT_FILE"
            echo -e "Recommendations saved to: /tmp/health-recommendations-$(date +%Y%m%d_%H%M%S).md"

            if [[ "$overall_status" == "critical" ]]; then
                echo -e "\n${RED}🚨 CRITICAL ISSUES DETECTED - Immediate action required${NC}"
                error "System health check indicates critical issues"
            elif [[ "$overall_status" == "warning" ]]; then
                echo -e "\n${YELLOW}⚠️  WARNING ISSUES DETECTED - Action recommended${NC}"
                warning "System health check indicates warning issues"
            else
                echo -e "\n${GREEN}✅ SYSTEM HEALTHY - No action required${NC}"
                success "All health checks passed"
            fi
            ;;
        "quick")
            log "Running quick health check..."

            # Quick check only critical services
            check_application_health
            check_database_health
            check_celery_health

            # Remove trailing comma and close JSON
            sed -i '$ s/,$//' "$REPORT_FILE"
            echo ']}' >> "$REPORT_FILE"

            echo "Quick health check completed. Report: $REPORT_FILE"
            ;;
        *)
            echo "Usage: $0 {check|quick}"
            echo "  check - Comprehensive health check"
            echo "  quick - Quick health check of critical services"
            exit 1
            ;;
    esac
}

# Script usage
usage() {
    echo "Usage: $0 {check|quick}"
    echo "  check - Comprehensive health check"
    echo "  quick - Quick health check of critical services"
    exit 1
}

# Handle script arguments
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
fi

# Run main function
main "$@"