#!/bin/bash

# Dev-Assist Health Monitor Script
# Comprehensive health monitoring and alerting system

set -euo pipefail

# Configuration
HEALTH_CHECK_INTERVAL="${HEALTH_CHECK_INTERVAL:-30}"
ALERT_THRESHOLD="${ALERT_THRESHOLD:-3}"
LOG_FILE="${LOG_FILE:-/var/log/dev-assist/health-monitor.log}"
WEBHOOK_URL="${WEBHOOK_URL:-}"
EMAIL_ALERTS="${EMAIL_ALERTS:-false}"
RESTART_UNHEALTHY="${RESTART_UNHEALTHY:-true}"

# Global variables
FAILURE_COUNT=0
LAST_ALERT_TIME=0
ALERT_COOLDOWN=3600  # 1 hour between alerts

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log_info() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1"
    echo -e "${BLUE}$msg${NC}"
    echo "$msg" >> "$LOG_FILE"
}

log_success() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [SUCCESS] $1"
    echo -e "${GREEN}$msg${NC}"
    echo "$msg" >> "$LOG_FILE"
}

log_warning() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [WARNING] $1"
    echo -e "${YELLOW}$msg${NC}"
    echo "$msg" >> "$LOG_FILE"
}

log_error() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1"
    echo -e "${RED}$msg${NC}"
    echo "$msg" >> "$LOG_FILE"
}

# Setup logging
setup_logging() {
    mkdir -p "$(dirname "$LOG_FILE")"
    touch "$LOG_FILE"
}

# Check API health
check_api_health() {
    local status="healthy"
    local details=""
    
    # Basic HTTP health check
    if ! curl -f -s --max-time 10 "http://localhost:8000/api/v1/healthz" >/dev/null 2>&1; then
        status="unhealthy"
        details="API endpoint not responding"
        return 1
    fi
    
    # Detailed health check
    local health_response
    if health_response=$(curl -s --max-time 10 "http://localhost:8000/api/v1/health/detailed" 2>/dev/null); then
        # Parse health response (assuming JSON)
        if command -v jq >/dev/null 2>&1; then
            local db_status=$(echo "$health_response" | jq -r '.database.status // "unknown"')
            local redis_status=$(echo "$health_response" | jq -r '.redis.status // "unknown"')
            
            if [[ "$db_status" != "healthy" ]]; then
                status="unhealthy"
                details="Database unhealthy: $db_status"
                return 1
            fi
            
            if [[ "$redis_status" != "healthy" ]]; then
                status="unhealthy"
                details="Redis unhealthy: $redis_status"
                return 1
            fi
        fi
    else
        status="unhealthy"
        details="Detailed health endpoint not responding"
        return 1
    fi
    
    return 0
}

# Check database connectivity
check_database_health() {
    if ! docker-compose exec -T postgres pg_isready -U supervisor -d supervisor_agent >/dev/null 2>&1; then
        return 1
    fi
    
    # Check if we can actually query the database
    if ! docker-compose exec -T postgres psql -U supervisor -d supervisor_agent -c "SELECT 1;" >/dev/null 2>&1; then
        return 1
    fi
    
    return 0
}

# Check Redis connectivity
check_redis_health() {
    if ! docker-compose exec -T redis redis-cli ping | grep -q "PONG" 2>/dev/null; then
        return 1
    fi
    
    return 0
}

# Check worker health
check_worker_health() {
    # Check if Celery workers are responding
    local worker_status
    if worker_status=$(docker-compose exec -T worker celery -A supervisor_agent.queue.celery_app inspect ping 2>/dev/null); then
        if echo "$worker_status" | grep -q "pong"; then
            return 0
        fi
    fi
    
    return 1
}

# Check frontend health
check_frontend_health() {
    if ! curl -f -s --max-time 10 "http://localhost:3000" >/dev/null 2>&1; then
        return 1
    fi
    
    return 0
}

# Check system resources
check_system_resources() {
    local warnings=()
    
    # Check disk usage
    local disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ $disk_usage -gt 85 ]]; then
        warnings+=("Disk usage high: ${disk_usage}%")
    fi
    
    # Check memory usage
    local memory_usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2 }')
    if [[ $memory_usage -gt 90 ]]; then
        warnings+=("Memory usage high: ${memory_usage}%")
    fi
    
    # Check load average
    local load_avg=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
    local cpu_cores=$(nproc)
    local load_percentage=$(echo "$load_avg $cpu_cores" | awk '{printf "%.0f", ($1/$2)*100}')
    if [[ $load_percentage -gt 80 ]]; then
        warnings+=("CPU load high: ${load_percentage}%")
    fi
    
    if [[ ${#warnings[@]} -gt 0 ]]; then
        log_warning "System resource warnings: $(IFS=', '; echo "${warnings[*]}")"
        return 1
    fi
    
    return 0
}

# Check Docker containers
check_docker_health() {
    local unhealthy_containers=()
    
    # Get container statuses
    while IFS= read -r line; do
        local container_name=$(echo "$line" | awk '{print $1}')
        local status=$(echo "$line" | awk '{print $2}')
        
        if [[ "$status" != "running" ]]; then
            unhealthy_containers+=("$container_name: $status")
        fi
    done < <(docker-compose ps --format "table {{.Name}}\t{{.State}}" | tail -n +2)
    
    if [[ ${#unhealthy_containers[@]} -gt 0 ]]; then
        log_error "Unhealthy containers: $(IFS=', '; echo "${unhealthy_containers[*]}")"
        return 1
    fi
    
    return 0
}

# Comprehensive health check
run_health_checks() {
    local checks=(
        "API:check_api_health"
        "Database:check_database_health"
        "Redis:check_redis_health"
        "Workers:check_worker_health"
        "Frontend:check_frontend_health"
        "System:check_system_resources"
        "Docker:check_docker_health"
    )
    
    local failed_checks=()
    local passed_checks=()
    
    for check in "${checks[@]}"; do
        local name=$(echo "$check" | cut -d: -f1)
        local function=$(echo "$check" | cut -d: -f2)
        
        if $function; then
            passed_checks+=("$name")
        else
            failed_checks+=("$name")
        fi
    done
    
    # Log results
    if [[ ${#failed_checks[@]} -eq 0 ]]; then
        log_success "All health checks passed: $(IFS=', '; echo "${passed_checks[*]}")"
        FAILURE_COUNT=0
        return 0
    else
        log_error "Health check failures: $(IFS=', '; echo "${failed_checks[*]}")"
        ((FAILURE_COUNT++))
        return 1
    fi
}

# Send alert notification
send_alert() {
    local severity="$1"
    local message="$2"
    local current_time=$(date +%s)
    
    # Check cooldown period
    if [[ $((current_time - LAST_ALERT_TIME)) -lt $ALERT_COOLDOWN ]]; then
        log_info "Alert cooldown active, skipping notification"
        return
    fi
    
    # Webhook notification
    if [[ -n "$WEBHOOK_URL" ]]; then
        local payload=$(cat <<EOF
{
    "text": "🚨 Dev-Assist Alert",
    "attachments": [
        {
            "color": "danger",
            "title": "Health Check Alert",
            "fields": [
                {
                    "title": "Severity",
                    "value": "$severity",
                    "short": true
                },
                {
                    "title": "Message",
                    "value": "$message",
                    "short": false
                },
                {
                    "title": "Timestamp",
                    "value": "$(date)",
                    "short": true
                },
                {
                    "title": "Failure Count",
                    "value": "$FAILURE_COUNT",
                    "short": true
                }
            ]
        }
    ]
}
EOF
        )
        
        if curl -X POST -H 'Content-type: application/json' \
               --data "$payload" \
               "$WEBHOOK_URL" >/dev/null 2>&1; then
            log_info "Alert sent to webhook"
        else
            log_warning "Failed to send webhook alert"
        fi
    fi
    
    # Email notification (if configured)
    if [[ "$EMAIL_ALERTS" == "true" && -n "${EMAIL_TO:-}" ]]; then
        local subject="Dev-Assist Health Alert - $severity"
        local body="Health check alert for Dev-Assist system:\n\nSeverity: $severity\nMessage: $message\nFailure Count: $FAILURE_COUNT\nTimestamp: $(date)\n\nPlease check the system immediately."
        
        if command -v mail >/dev/null 2>&1; then
            echo -e "$body" | mail -s "$subject" "$EMAIL_TO" 2>/dev/null || log_warning "Failed to send email alert"
        fi
    fi
    
    LAST_ALERT_TIME=$current_time
}

# Attempt to restart unhealthy services
restart_unhealthy_services() {
    if [[ "$RESTART_UNHEALTHY" != "true" ]]; then
        log_info "Auto-restart disabled, skipping service restart"
        return
    fi
    
    log_warning "Attempting to restart unhealthy services..."
    
    # Restart individual services that are unhealthy
    local services_to_restart=()
    
    if ! check_api_health; then
        services_to_restart+=("api")
    fi
    
    if ! check_worker_health; then
        services_to_restart+=("worker")
    fi
    
    if ! check_frontend_health; then
        services_to_restart+=("frontend")
    fi
    
    if [[ ${#services_to_restart[@]} -gt 0 ]]; then
        log_info "Restarting services: $(IFS=', '; echo "${services_to_restart[*]}")"
        
        for service in "${services_to_restart[@]}"; do
            if docker-compose restart "$service"; then
                log_success "Restarted $service successfully"
            else
                log_error "Failed to restart $service"
            fi
        done
        
        # Wait for services to come back up
        sleep 30
    fi
}

# Generate health report
generate_health_report() {
    local report_file="/tmp/health-report-$(date +%Y%m%d_%H%M%S).json"
    
    cat > "$report_file" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "hostname": "$(hostname)",
    "uptime": "$(uptime -p)",
    "system": {
        "disk_usage": "$(df / | awk 'NR==2 {print $5}')",
        "memory_usage": "$(free | awk 'NR==2{printf "%.1f%%", $3*100/$2 }')",
        "load_average": "$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')",
        "cpu_cores": $(nproc)
    },
    "docker": {
        "containers": $(docker-compose ps --format json 2>/dev/null || echo "[]"),
        "images": $(docker images --format json 2>/dev/null | jq -s '.' || echo "[]")
    },
    "health_checks": {
        "api": $(check_api_health && echo "true" || echo "false"),
        "database": $(check_database_health && echo "true" || echo "false"),
        "redis": $(check_redis_health && echo "true" || echo "false"),
        "workers": $(check_worker_health && echo "true" || echo "false"),
        "frontend": $(check_frontend_health && echo "true" || echo "false")
    },
    "failure_count": $FAILURE_COUNT,
    "last_alert": $LAST_ALERT_TIME
}
EOF
    
    log_info "Health report generated: $report_file"
}

# Main monitoring loop
main_monitor_loop() {
    log_info "Starting health monitoring (interval: ${HEALTH_CHECK_INTERVAL}s, threshold: $ALERT_THRESHOLD)"
    
    while true; do
        if run_health_checks; then
            # Reset failure count on success
            if [[ $FAILURE_COUNT -gt 0 ]]; then
                log_success "System recovered after $FAILURE_COUNT failed checks"
                FAILURE_COUNT=0
            fi
        else
            log_warning "Health check failed (attempt $FAILURE_COUNT/$ALERT_THRESHOLD)"
            
            # Send alert if threshold reached
            if [[ $FAILURE_COUNT -ge $ALERT_THRESHOLD ]]; then
                send_alert "CRITICAL" "Health checks failing for $FAILURE_COUNT consecutive attempts"
                restart_unhealthy_services
                
                # Generate detailed health report
                generate_health_report
            fi
        fi
        
        sleep "$HEALTH_CHECK_INTERVAL"
    done
}

# One-time health check
run_single_check() {
    log_info "Running single health check..."
    
    if run_health_checks; then
        log_success "System is healthy"
        exit 0
    else
        log_error "System has health issues"
        generate_health_report
        exit 1
    fi
}

# Show usage
show_usage() {
    cat << EOF
Usage: $0 [options]

Options:
  --monitor         Run continuous monitoring (default)
  --check           Run single health check and exit
  --report          Generate health report and exit
  --help, -h        Show this help message

Environment Variables:
  HEALTH_CHECK_INTERVAL    Check interval in seconds (default: 30)
  ALERT_THRESHOLD          Failures before alert (default: 3)
  LOG_FILE                 Log file path (default: /var/log/dev-assist/health-monitor.log)
  WEBHOOK_URL              Slack/webhook URL for alerts
  EMAIL_ALERTS             Enable email alerts (default: false)
  RESTART_UNHEALTHY        Auto-restart unhealthy services (default: true)

Examples:
  $0                       # Start continuous monitoring
  $0 --check               # Single health check
  $0 --report              # Generate health report
  
  # With custom settings
  HEALTH_CHECK_INTERVAL=60 ALERT_THRESHOLD=5 $0

EOF
}

# Main execution
main() {
    setup_logging
    
    case "${1:---monitor}" in
        --monitor)
            main_monitor_loop
            ;;
        --check)
            run_single_check
            ;;
        --report)
            generate_health_report
            ;;
        --help|-h)
            show_usage
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"