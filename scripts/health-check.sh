#!/bin/bash

# Supervisor Coding Agent - Health Check Script
# Comprehensive system health verification

set -e

echo "🏥 Supervisor Coding Agent - Health Check"
echo "========================================"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
API_URL="http://localhost:8000"
TIMEOUT=10
VERBOSE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -u|--url)
            API_URL="$2"
            shift 2
            ;;
        -t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  -v, --verbose    Show detailed output"
            echo "  -u, --url URL    API base URL (default: http://localhost:8000)"
            echo "  -t, --timeout N  Request timeout in seconds (default: 10)"
            echo "  -h, --help       Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Helper function for HTTP requests
http_check() {
    local url="$1"
    local expected_status="${2:-200}"
    local description="$3"
    
    if [[ "$VERBOSE" == "true" ]]; then
        echo "Checking: $description"
        echo "URL: $url"
    fi
    
    local response
    local status_code
    
    if response=$(curl -s -w "%{http_code}" --max-time "$TIMEOUT" "$url" 2>/dev/null); then
        status_code="${response: -3}"
        response="${response%???}"
        
        if [[ "$status_code" == "$expected_status" ]]; then
            echo -e "${GREEN}✅ $description${NC}"
            if [[ "$VERBOSE" == "true" ]]; then
                echo "Response: $response"
                echo ""
            fi
            return 0
        else
            echo -e "${RED}❌ $description (HTTP $status_code)${NC}"
            if [[ "$VERBOSE" == "true" ]]; then
                echo "Response: $response"
                echo ""
            fi
            return 1
        fi
    else
        echo -e "${RED}❌ $description (Connection failed)${NC}"
        return 1
    fi
}

# Check JSON response contains expected fields
json_check() {
    local url="$1"
    local description="$2"
    local expected_fields="$3"
    
    if [[ "$VERBOSE" == "true" ]]; then
        echo "Checking JSON: $description"
        echo "URL: $url"
    fi
    
    local response
    if response=$(curl -s --max-time "$TIMEOUT" "$url" 2>/dev/null); then
        # Check if response is valid JSON
        if echo "$response" | python3 -m json.tool >/dev/null 2>&1; then
            # Check for expected fields
            local missing_fields=""
            for field in $expected_fields; do
                if ! echo "$response" | python3 -c "import sys, json; data=json.load(sys.stdin); sys.exit(0 if '$field' in data else 1)" 2>/dev/null; then
                    missing_fields="$missing_fields $field"
                fi
            done
            
            if [[ -z "$missing_fields" ]]; then
                echo -e "${GREEN}✅ $description${NC}"
                if [[ "$VERBOSE" == "true" ]]; then
                    echo "$response" | python3 -m json.tool
                    echo ""
                fi
                return 0
            else
                echo -e "${YELLOW}⚠️ $description (missing fields:$missing_fields)${NC}"
                return 1
            fi
        else
            echo -e "${RED}❌ $description (invalid JSON)${NC}"
            return 1
        fi
    else
        echo -e "${RED}❌ $description (connection failed)${NC}"
        return 1
    fi
}

# Check Docker services
check_docker_services() {
    echo -e "${BLUE}Docker Services:${NC}"
    
    if ! command -v docker-compose &>/dev/null; then
        echo -e "${YELLOW}⚠️ Docker Compose not available${NC}"
        return 1
    fi
    
    local services=(
        "postgres:PostgreSQL Database"
        "redis:Redis Cache"
        "api:API Server"
        "worker:Celery Worker"
    )
    
    for service_info in "${services[@]}"; do
        local service="${service_info%%:*}"
        local description="${service_info##*:}"
        
        if docker-compose ps "$service" 2>/dev/null | grep -q "Up"; then
            echo -e "${GREEN}✅ $description ($service)${NC}"
        else
            echo -e "${RED}❌ $description ($service)${NC}"
        fi
    done
}

# Check database connectivity
check_database() {
    echo -e "${BLUE}Database Connectivity:${NC}"
    
    if docker-compose exec -T postgres pg_isready -U supervisor 2>/dev/null; then
        echo -e "${GREEN}✅ PostgreSQL connection${NC}"
    else
        echo -e "${RED}❌ PostgreSQL connection${NC}"
    fi
    
    if docker-compose exec -T redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
        echo -e "${GREEN}✅ Redis connection${NC}"
    else
        echo -e "${RED}❌ Redis connection${NC}"
    fi
}

# Check API endpoints
check_api_endpoints() {
    echo -e "${BLUE}API Endpoints:${NC}"
    
    # Basic health check
    http_check "$API_URL/api/v1/healthz" "200" "Basic health check"
    
    # Detailed health check
    json_check "$API_URL/api/v1/health/detailed" "Detailed health check" "status timestamp components"
    
    # Metrics endpoint
    http_check "$API_URL/api/v1/metrics" "200" "Metrics endpoint"
    
    # API documentation
    http_check "$API_URL/docs" "200" "API documentation"
    
    # Task endpoints
    http_check "$API_URL/api/v1/tasks" "200" "Tasks endpoint"
    
    # Agent quota status
    json_check "$API_URL/api/v1/agents/quota/status" "Agent quota status" "available_agents total_agents"
}

# Check external dependencies
check_external_deps() {
    echo -e "${BLUE}External Dependencies:${NC}"
    
    # Check Claude CLI
    if command -v claude &>/dev/null; then
        local claude_version
        if claude_version=$(claude --version 2>/dev/null); then
            echo -e "${GREEN}✅ Claude CLI ($claude_version)${NC}"
        else
            echo -e "${GREEN}✅ Claude CLI (version unknown)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️ Claude CLI not found${NC}"
    fi
    
    # Check Python environment
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        echo -e "${GREEN}✅ Virtual environment ($VIRTUAL_ENV)${NC}"
    else
        echo -e "${YELLOW}⚠️ Not in virtual environment${NC}"
    fi
    
    # Check Python packages
    local packages=("fastapi" "celery" "sqlalchemy" "pytest")
    for package in "${packages[@]}"; do
        if python3 -c "import $package" 2>/dev/null; then
            echo -e "${GREEN}✅ Python package: $package${NC}"
        else
            echo -e "${RED}❌ Python package: $package${NC}"
        fi
    done
}

# Performance check
check_performance() {
    echo -e "${BLUE}Performance Check:${NC}"
    
    # API response time
    local start_time end_time duration
    start_time=$(date +%s%N)
    
    if curl -s --max-time "$TIMEOUT" "$API_URL/api/v1/healthz" >/dev/null 2>&1; then
        end_time=$(date +%s%N)
        duration=$(( (end_time - start_time) / 1000000 ))
        
        if [[ $duration -lt 500 ]]; then
            echo -e "${GREEN}✅ API response time: ${duration}ms${NC}"
        elif [[ $duration -lt 2000 ]]; then
            echo -e "${YELLOW}⚠️ API response time: ${duration}ms (slow)${NC}"
        else
            echo -e "${RED}❌ API response time: ${duration}ms (very slow)${NC}"
        fi
    else
        echo -e "${RED}❌ API response time check failed${NC}"
    fi
}

# Summary function
print_summary() {
    echo ""
    echo -e "${BLUE}Health Check Summary:${NC}"
    echo "===================="
    echo ""
    
    # Count successes and failures
    local total_checks failed_checks
    total_checks=$(echo -e "${check_results}" | wc -l)
    failed_checks=$(echo -e "${check_results}" | grep -c "❌" || true)
    
    if [[ $failed_checks -eq 0 ]]; then
        echo -e "${GREEN}🎉 All systems operational!${NC}"
        echo "The Supervisor Coding Agent is running perfectly."
    elif [[ $failed_checks -lt 3 ]]; then
        echo -e "${YELLOW}⚠️ Minor issues detected${NC}"
        echo "The system is mostly functional but has some issues."
    else
        echo -e "${RED}❌ Multiple issues detected${NC}"
        echo "The system requires attention."
    fi
    
    echo ""
    echo "For more help:"
    echo "  make help               # Show available commands"
    echo "  make docker-logs        # View service logs"
    echo "  docker-compose ps       # Check service status"
    echo "  $API_URL/docs          # API documentation"
}

# Main health check
main() {
    echo "Performing comprehensive health check..."
    echo ""
    
    # Capture all output for summary
    check_results=""
    
    {
        check_docker_services
        echo ""
        
        check_database
        echo ""
        
        check_api_endpoints
        echo ""
        
        check_external_deps
        echo ""
        
        check_performance
    } 2>&1 | tee >(check_results=$(cat))
    
    print_summary
}

# Run main function
main "$@"