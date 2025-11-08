#!/bin/bash

# Security Audit Script for AP Intake & Validation System
# This script performs comprehensive security checks and hardening

set -euo pipefail

# Configuration
LOG_FILE="/var/log/security-audit.log"
REPORT_FILE="/tmp/security-audit-$(date +%Y%m%d_%H%M%S).json"
HIGH_RISK_THRESHOLD=7
MEDIUM_RISK_THRESHOLD=4

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Risk levels
RISK_HIGH=3
RISK_MEDIUM=2
RISK_LOW=1

# Initialize audit report
echo '{"security_audit": {' > "$REPORT_FILE"
echo '"timestamp": "'$(date -Iseconds)'",' >> "$REPORT_FILE"
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
    local risk="$3"
    local details="$4"
    local recommendation="$5"

    cat >> "$REPORT_FILE" <<EOF
{
  "name": "$name",
  "status": "$status",
  "risk_level": $risk,
  "details": "$details",
  "recommendation": "$recommendation"
},
EOF
}

# Check 1: Container Security
check_container_security() {
    log "Checking container security..."

    # Check if containers are running as root
    local root_containers=$(docker-compose -f docker-compose.prod.yml ps -q | xargs -I {} docker inspect {} --format='{{.Config.User}}' | grep -v "" | wc -l)

    if [[ $root_containers -gt 0 ]]; then
        add_check "Container User Security" "FAIL" $RISK_HIGH "$root_containers containers running as root" "Update Dockerfile.prod to use non-root user"
    else
        add_check "Container User Security" "PASS" $RISK_LOW "All containers running as non-root users" "Maintain current security posture"
    fi

    # Check for exposed sensitive ports
    local exposed_sensitive=$(docker-compose -f docker-compose.prod.yml config | grep -E "5432|6379|9000" | wc -l)
    if [[ $exposed_sensitive -gt 0 ]]; then
        add_check "Port Exposure" "FAIL" $RISK_MEDIUM "Sensitive ports exposed to host" "Remove port mappings for internal services"
    else
        add_check "Port Exposure" "PASS" $RISK_LOW "No sensitive ports exposed" "Maintain current network configuration"
    fi

    # Check for read-only filesystems
    local readonly_fs=$(docker-compose -f docker-compose.prod.yml config | grep -c "read_only: true" || true)
    if [[ $readonly_fs -eq 0 ]]; then
        add_check "Read-only Filesystem" "WARN" $RISK_MEDIUM "Containers not using read-only filesystems" "Consider implementing read-only filesystems where possible"
    else
        add_check "Read-only Filesystem" "PASS" $RISK_LOW "Some containers using read-only filesystems" "Extend to all applicable containers"
    fi
}

# Check 2: Secrets Management
check_secrets_management() {
    log "Checking secrets management..."

    # Check for hardcoded secrets in docker-compose
    if grep -q "password\|secret\|key" docker-compose.yml; then
        add_check "Hardcoded Secrets" "FAIL" $RISK_HIGH "Hardcoded secrets found in docker-compose.yml" "Use environment variables or Docker secrets"
    else
        add_check "Hardcoded Secrets" "PASS" $RISK_LOW "No hardcoded secrets in docker-compose.yml" "Maintain current secrets management"
    fi

    # Check for secrets in code
    local secrets_in_code=$(grep -r -i "password\|secret\|key" app/ --include="*.py" | grep -v "env\|config\|settings" | wc -l)
    if [[ $secrets_in_code -gt 0 ]]; then
        add_check "Secrets in Code" "FAIL" $RISK_HIGH "$secrets_in_code potential secrets found in code" "Remove hardcoded secrets and use environment variables"
    else
        add_check "Secrets in Code" "PASS" $RISK_LOW "No hardcoded secrets found in application code" "Maintain current security practices"
    fi

    # Check .env file permissions
    if [[ -f .env ]]; then
        local env_perms=$(stat -c %a .env)
        if [[ "$env_perms" != "600" ]]; then
            add_check "Environment File Permissions" "FAIL" $RISK_MEDIUM ".env file has permissions $env_perms" "Set .env file permissions to 600"
        else
            add_check "Environment File Permissions" "PASS" $RISK_LOW ".env file properly secured" "Maintain current file permissions"
        fi
    fi
}

# Check 3: Network Security
check_network_security() {
    log "Checking network security..."

    # Check for HTTPS enforcement
    if ! grep -q "ssl_certificate" nginx/nginx.conf; then
        add_check "HTTPS Configuration" "FAIL" $RISK_HIGH "SSL certificates not configured in Nginx" "Configure SSL certificates and HTTPS redirect"
    else
        add_check "HTTPS Configuration" "PASS" $RISK_LOW "SSL certificates configured" "Maintain SSL configuration"
    fi

    # Check for security headers
    local security_headers=$(grep -c "add_header.*X-" nginx/nginx.conf || true)
    if [[ $security_headers -lt 5 ]]; then
        add_check "Security Headers" "WARN" $RISK_MEDIUM "Insufficient security headers configured" "Add comprehensive security headers"
    else
        add_check "Security Headers" "PASS" $RISK_LOW "Security headers properly configured" "Maintain current security headers"
    fi

    # Check for rate limiting
    if ! grep -q "limit_req_zone" nginx/nginx.conf; then
        add_check "Rate Limiting" "FAIL" $RISK_MEDIUM "No rate limiting configured" "Implement rate limiting for API endpoints"
    else
        add_check "Rate Limiting" "PASS" $RISK_LOW "Rate limiting configured" "Monitor and adjust rate limits as needed"
    fi
}

# Check 4: Database Security
check_database_security() {
    log "Checking database security..."

    # Check PostgreSQL connection security
    if grep -q "trust\|password" postgresql/pg_hba.conf 2>/dev/null; then
        add_check "Database Authentication" "WARN" $RISK_MEDIUM "Database authentication may use weak methods" "Implement strong database authentication"
    else
        add_check "Database Authentication" "PASS" $RISK_LOW "Database authentication appears secure" "Maintain current database security"
    fi

    # Check for database encryption
    if ! grep -q "ssl" docker-compose.prod.yml; then
        add_check "Database Encryption" "WARN" $RISK_MEDIUM "Database SSL encryption not configured" "Enable database connection encryption"
    else
        add_check "Database Encryption" "PASS" $RISK_LOW "Database encryption configured" "Maintain database encryption"
    fi
}

# Check 5: Application Security
check_application_security() {
    log "Checking application security..."

    # Check for CORS configuration
    if grep -q "cors_origins.*\*" app/core/config.py; then
        add_check "CORS Configuration" "FAIL" $RISK_HIGH "CORS allows all origins" "Configure specific allowed origins"
    else
        add_check "CORS Configuration" "PASS" $RISK_LOW "CORS properly configured" "Maintain current CORS settings"
    fi

    # Check for input validation
    local validation_count=$(grep -r "pydantic\|validate" app/api/ --include="*.py" | wc -l)
    if [[ $validation_count -lt 10 ]]; then
        add_check "Input Validation" "WARN" $RISK_MEDIUM "Limited input validation found" "Implement comprehensive input validation"
    else
        add_check "Input Validation" "PASS" $RISK_LOW "Input validation implemented" "Maintain input validation"
    fi

    # Check for SQL injection protection
    if grep -r "execute\|raw" app/ --include="*.py" | grep -v "sqlalchemy" | wc -l > 0; then
        add_check "SQL Injection Protection" "FAIL" $RISK_HIGH "Potential SQL injection vulnerabilities" "Use parameterized queries and SQLAlchemy ORM"
    else
        add_check "SQL Injection Protection" "PASS" $RISK_LOW "SQL injection protection implemented" "Maintain current query protection"
    fi
}

# Check 6: File Security
check_file_security() {
    log "Checking file security..."

    # Check file upload security
    if grep -q "ALLOWED_FILE_TYPES.*\*" .env.example; then
        add_check "File Upload Security" "FAIL" $RISK_HIGH "File upload allows all file types" "Restrict file types to specific allowed types"
    else
        add_check "File Upload Security" "PASS" $RISK_LOW "File upload restrictions in place" "Maintain file upload security"
    fi

    # Check for file size limits
    if ! grep -q "MAX_FILE_SIZE" .env.example; then
        add_check "File Size Limits" "FAIL" $RISK_MEDIUM "No file size limits configured" "Configure appropriate file size limits"
    else
        add_check "File Size Limits" "PASS" $RISK_LOW "File size limits configured" "Maintain file size restrictions"
    fi

    # Check directory permissions
    local storage_perms=$(stat -c %a storage 2>/dev/null || echo "755")
    if [[ "$storage_perms" != "755" ]]; then
        add_check "Directory Permissions" "WARN" $RISK_MEDIUM "Storage directory has permissions $storage_perms" "Set directory permissions to 755"
    else
        add_check "Directory Permissions" "PASS" $RISK_LOW "Directory permissions properly set" "Maintain current permissions"
    fi
}

# Check 7: Monitoring & Logging
check_monitoring() {
    log "Checking monitoring and logging..."

    # Check for application monitoring
    if [[ -f monitoring/prometheus.yml ]]; then
        add_check "Application Monitoring" "PASS" $RISK_LOW "Prometheus monitoring configured" "Maintain monitoring configuration"
    else
        add_check "Application Monitoring" "FAIL" $RISK_MEDIUM "No application monitoring configured" "Implement monitoring and alerting"
    fi

    # Check for logging configuration
    if grep -q "loguru\|logging" app/main.py; then
        add_check "Application Logging" "PASS" $RISK_LOW "Application logging configured" "Maintain logging configuration"
    else
        add_check "Application Logging" "FAIL" $RISK_MEDIUM "Application logging not configured" "Implement structured logging"
    fi

    # Check for error tracking
    if grep -q "sentry" app/main.py; then
        add_check "Error Tracking" "PASS" $RISK_LOW "Error tracking configured" "Maintain error tracking"
    else
        add_check "Error Tracking" "WARN" $RISK_LOW "Error tracking not configured" "Consider implementing error tracking"
    fi
}

# Check 8: Backup Security
check_backup_security() {
    log "Checking backup security..."

    # Check for backup encryption
    if grep -q "encrypt\|gpg" scripts/backup.sh; then
        add_check "Backup Encryption" "PASS" $RISK_LOW "Backup encryption configured" "Maintain backup encryption"
    else
        add_check "Backup Encryption" "WARN" $RISK_MEDIUM "Backup encryption not configured" "Implement backup encryption"
    fi

    # Check backup retention
    if grep -q "RETENTION_DAYS" scripts/backup.sh; then
        add_check "Backup Retention" "PASS" $RISK_LOW "Backup retention policy configured" "Maintain backup retention policy"
    else
        add_check "Backup Retention" "FAIL" $RISK_MEDIUM "No backup retention policy" "Configure backup retention policy"
    fi
}

# Generate security score
calculate_security_score() {
    # Remove trailing comma and close JSON
    sed -i '$ s/,$//' "$REPORT_FILE"
    echo '],' >> "$REPORT_FILE"

    # Count risks
    local high_risk=$(grep -c '"risk_level": 3' "$REPORT_FILE" || true)
    local medium_risk=$(grep -c '"risk_level": 2' "$REPORT_FILE" || true)
    local low_risk=$(grep -c '"risk_level": 1' "$REPORT_FILE" || true)
    local total_checks=$((high_risk + medium_risk + low_risk))

    # Calculate score (0-100)
    local score=0
    if [[ $total_checks -gt 0 ]]; then
        score=$(( (total_checks - high_risk * 2 - medium_risk) * 100 / total_checks ))
    fi

    # Add score to report
    cat >> "$REPORT_FILE" <<EOF
"summary": {
  "total_checks": $total_checks,
  "high_risk": $high_risk,
  "medium_risk": $medium_risk,
  "low_risk": $low_risk,
  "security_score": $score
}
}
}
EOF

    echo "$score"
}

# Generate recommendations
generate_recommendations() {
    log "Generating security recommendations..."

    local cat <<EOF > "/tmp/security-recommendations-$(date +%Y%m%d_%H%M%S).md"
# Security Audit Recommendations

## Immediate Actions (High Risk)
- Review and fix all high-risk findings
- Implement SSL/TLS configuration
- Remove hardcoded secrets
- Restrict file upload types

## Short-term Improvements (Medium Risk)
- Implement rate limiting
- Add comprehensive security headers
- Configure backup encryption
- Implement database connection encryption

## Long-term Enhancements (Low Risk)
- Implement read-only filesystems
- Add comprehensive monitoring
- Regular security scans
- Security training for team

## Security Score: $score/100

EOF

    success "Security recommendations generated"
}

# Main audit function
main() {
    log "Starting security audit for AP Intake & Validation System..."

    # Run security checks
    check_container_security
    check_secrets_management
    check_network_security
    check_database_security
    check_application_security
    check_file_security
    check_monitoring
    check_backup_security

    # Calculate security score
    local score=$(calculate_security_score)

    # Generate recommendations
    generate_recommendations

    # Output results
    echo -e "\n${BLUE}=== SECURITY AUDIT RESULTS ===${NC}"
    echo -e "Security Score: ${score}/100"
    echo -e "Report saved to: $REPORT_FILE"
    echo -e "Recommendations saved to: /tmp/security-recommendations-$(date +%Y%m%d_%H%M%S).md"

    if [[ $score -lt $HIGH_RISK_THRESHOLD ]]; then
        echo -e "\n${RED}🚨 HIGH SECURITY RISK - Immediate action required${NC}"
        error "Security score below acceptable threshold"
    elif [[ $score -lt $MEDIUM_RISK_THRESHOLD ]]; then
        echo -e "\n${YELLOW}⚠️  MEDIUM SECURITY RISK - Action recommended${NC}"
        warning "Security score requires improvement"
    else
        echo -e "\n${GREEN}✅ GOOD SECURITY POSTURE - Maintain current practices${NC}"
        success "Security audit completed successfully"
    fi
}

# Script usage
usage() {
    echo "Usage: $0 [--help|-h]"
    echo "This script performs a comprehensive security audit of the AP Intake system"
    exit 1
}

# Handle script arguments
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
fi

# Run main function
main "$@"