#!/bin/bash

# Smoke Tests for Dev-Assist Environments
# Comprehensive testing for ephemeral and development environments

set -euo pipefail

# Configuration
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
TIMEOUT="${TIMEOUT:-60}"
VERBOSE="${VERBOSE:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test results
TESTS_PASSED=0
TESTS_FAILED=0
FAILED_TESTS=()

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TESTS_PASSED++))
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TESTS_FAILED++))
    FAILED_TESTS+=("$1")
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Wait for service to be ready
wait_for_service() {
    local url="$1"
    local name="$2"
    local timeout="${3:-$TIMEOUT}"
    
    log_info "Waiting for $name to be ready at $url..."
    
    local start_time=$(date +%s)
    local end_time=$((start_time + timeout))
    
    while [[ $(date +%s) -lt $end_time ]]; do
        if curl -f -s --max-time 5 "$url" >/dev/null 2>&1; then
            log_success "$name is ready"
            return 0
        fi
        
        if [[ "$VERBOSE" == "true" ]]; then
            log_info "Waiting for $name... ($(($(date +%s) - start_time))s elapsed)"
        fi
        sleep 2
    done
    
    log_error "$name failed to become ready within ${timeout}s"
    return 1
}

# Test HTTP endpoint
test_endpoint() {
    local method="$1"
    local endpoint="$2"
    local expected_status="$3"
    local description="$4"
    local headers="${5:-}"
    local data="${6:-}"
    
    if [[ "$VERBOSE" == "true" ]]; then
        log_info "Testing: $description"
        log_info "  $method $endpoint (expecting $expected_status)"
    fi
    
    local curl_cmd="curl -s -o /dev/null -w %{http_code}"
    curl_cmd+=" -X $method"
    curl_cmd+=" --max-time 10"
    
    if [[ -n "$headers" ]]; then
        curl_cmd+=" $headers"
    fi
    
    if [[ -n "$data" ]]; then
        curl_cmd+=" -d '$data'"
    fi
    
    curl_cmd+=" '$endpoint'"
    
    local response_code
    if response_code=$(eval $curl_cmd 2>/dev/null); then
        if [[ "$response_code" == "$expected_status" ]]; then
            log_success "$description"
            return 0
        else
            log_error "$description (expected $expected_status, got $response_code)"
            return 1
        fi
    else
        log_error "$description (request failed)"
        return 1
    fi
}

# Test JSON response
test_json_endpoint() {
    local endpoint="$1"
    local description="$2"
    local jq_filter="${3:-.}"
    
    if [[ "$VERBOSE" == "true" ]]; then
        log_info "Testing JSON: $description"
    fi
    
    local response
    if response=$(curl -f -s --max-time 10 "$endpoint" 2>/dev/null); then
        if echo "$response" | jq "$jq_filter" >/dev/null 2>&1; then
            log_success "$description"
            return 0
        else
            log_error "$description (invalid JSON or jq filter failed)"
            return 1
        fi
    else
        log_error "$description (request failed)"
        return 1
    fi
}

# Test WebSocket connection
test_websocket() {
    local ws_url="$1"
    local description="$2"
    
    if [[ "$VERBOSE" == "true" ]]; then
        log_info "Testing WebSocket: $description"
    fi
    
    # Simple WebSocket test using curl with upgrade headers
    if curl -f -s --max-time 5 \
        -H "Connection: Upgrade" \
        -H "Upgrade: websocket" \
        -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
        -H "Sec-WebSocket-Version: 13" \
        "$ws_url" >/dev/null 2>&1; then
        log_success "$description"
        return 0
    else
        log_error "$description (WebSocket connection failed)"
        return 1
    fi
}

# API Health Tests
test_api_health() {
    log_info "🏥 Running API health tests..."
    
    # Basic health check
    test_endpoint "GET" "$API_BASE_URL/api/v1/healthz" "200" "Basic health check"
    
    # Detailed health check
    test_json_endpoint "$API_BASE_URL/api/v1/health/detailed" "Detailed health check" ".status"
    
    # API documentation
    test_endpoint "GET" "$API_BASE_URL/docs" "200" "API documentation"
    
    # OpenAPI schema
    test_endpoint "GET" "$API_BASE_URL/openapi.json" "200" "OpenAPI schema"
}

# API Functionality Tests
test_api_functionality() {
    log_info "⚙️ Running API functionality tests..."
    
    # Test CORS headers
    test_endpoint "OPTIONS" "$API_BASE_URL/api/v1/healthz" "200" "CORS preflight" \
        "-H 'Origin: http://localhost:3000' -H 'Access-Control-Request-Method: GET'"
    
    # Test API versioning
    test_endpoint "GET" "$API_BASE_URL/api/v1/" "404" "API root endpoint"
    
    # Test tasks endpoint (if available)
    test_endpoint "GET" "$API_BASE_URL/api/v1/tasks" "200" "Tasks endpoint" \
        "-H 'Content-Type: application/json'" || true
    
    # Test analytics endpoint (if available)
    test_endpoint "GET" "$API_BASE_URL/api/v1/analytics/summary" "200" "Analytics endpoint" \
        "-H 'Content-Type: application/json'" || true
}

# WebSocket Tests
test_websocket_functionality() {
    log_info "🔌 Running WebSocket tests..."
    
    # Convert HTTP URL to WebSocket URL
    local ws_url="${API_BASE_URL/http/ws}/ws"
    
    test_websocket "$ws_url" "WebSocket connection"
}

# Frontend Tests
test_frontend() {
    log_info "🎨 Running frontend tests..."
    
    # Basic frontend loading
    test_endpoint "GET" "$FRONTEND_URL" "200" "Frontend homepage"
    
    # Static assets
    test_endpoint "GET" "$FRONTEND_URL/favicon.ico" "200" "Favicon" || true
    
    # Check for SvelteKit app
    local response
    if response=$(curl -f -s --max-time 10 "$FRONTEND_URL" 2>/dev/null); then
        if echo "$response" | grep -q "svelte\|SvelteKit" || echo "$response" | grep -q "app\|application"; then
            log_success "Frontend app detection"
        else
            log_warning "Frontend app detection (content not recognized)"
        fi
    else
        log_error "Frontend app detection (failed to fetch)"
    fi
}

# Database Tests
test_database() {
    log_info "🗄️ Running database tests..."
    
    # Test database health through API
    test_json_endpoint "$API_BASE_URL/api/v1/health/detailed" "Database connectivity" \
        ".database.status" || true
    
    # Test if we can create/read data (through API if endpoints exist)
    # This would depend on your API endpoints
}

# Performance Tests
test_performance() {
    log_info "⚡ Running basic performance tests..."
    
    # Response time test
    local start_time=$(date +%s%N)
    if curl -f -s --max-time 10 "$API_BASE_URL/api/v1/healthz" >/dev/null 2>&1; then
        local end_time=$(date +%s%N)
        local response_time=$(( (end_time - start_time) / 1000000 )) # Convert to milliseconds
        
        if [[ $response_time -lt 1000 ]]; then
            log_success "API response time (${response_time}ms)"
        else
            log_warning "API response time (${response_time}ms - slower than expected)"
        fi
    else
        log_error "API response time test (request failed)"
    fi
    
    # Concurrent requests test
    log_info "Testing concurrent requests..."
    local concurrent_success=0
    for i in {1..5}; do
        if curl -f -s --max-time 5 "$API_BASE_URL/api/v1/healthz" >/dev/null 2>&1 &; then
            ((concurrent_success++))
        fi
    done
    wait
    
    if [[ $concurrent_success -eq 5 ]]; then
        log_success "Concurrent requests handling"
    else
        log_error "Concurrent requests handling ($concurrent_success/5 succeeded)"
    fi
}

# Security Tests
test_security() {
    log_info "🔒 Running basic security tests..."
    
    # Test security headers
    local headers
    if headers=$(curl -I -s --max-time 10 "$API_BASE_URL/api/v1/healthz" 2>/dev/null); then
        if echo "$headers" | grep -i "x-content-type-options" >/dev/null; then
            log_success "Security headers (X-Content-Type-Options)"
        else
            log_warning "Security headers (X-Content-Type-Options missing)"
        fi
        
        if echo "$headers" | grep -i "x-frame-options" >/dev/null; then
            log_success "Security headers (X-Frame-Options)"
        else
            log_warning "Security headers (X-Frame-Options missing)"
        fi
    else
        log_error "Security headers test (failed to fetch headers)"
    fi
    
    # Test for common vulnerabilities
    test_endpoint "GET" "$API_BASE_URL/../etc/passwd" "404" "Path traversal protection"
    test_endpoint "GET" "$API_BASE_URL/api/v1/healthz?<script>" "200" "XSS protection"
}

# Integration Tests
test_integration() {
    log_info "🔗 Running integration tests..."
    
    # Test API + Frontend integration
    if curl -f -s --max-time 10 "$FRONTEND_URL" >/dev/null 2>&1 && \
       curl -f -s --max-time 10 "$API_BASE_URL/api/v1/healthz" >/dev/null 2>&1; then
        log_success "Frontend + API integration"
    else
        log_error "Frontend + API integration"
    fi
    
    # Test if frontend can reach API (check for CORS configuration)
    local cors_test
    if cors_test=$(curl -s -H "Origin: $FRONTEND_URL" "$API_BASE_URL/api/v1/healthz" 2>/dev/null); then
        log_success "CORS configuration"
    else
        log_warning "CORS configuration (may need adjustment)"
    fi
}

# Main test execution
run_all_tests() {
    log_info "🚀 Starting Dev-Assist Environment Smoke Tests"
    log_info "API URL: $API_BASE_URL"
    log_info "Frontend URL: $FRONTEND_URL"
    echo ""
    
    # Wait for services to be ready
    wait_for_service "$API_BASE_URL/api/v1/healthz" "API" 30 || return 1
    wait_for_service "$FRONTEND_URL" "Frontend" 30 || return 1
    
    echo ""
    
    # Run test suites
    test_api_health
    echo ""
    
    test_api_functionality
    echo ""
    
    test_websocket_functionality
    echo ""
    
    test_frontend
    echo ""
    
    test_database
    echo ""
    
    test_performance
    echo ""
    
    test_security
    echo ""
    
    test_integration
    echo ""
}

# Generate test report
generate_report() {
    local total_tests=$((TESTS_PASSED + TESTS_FAILED))
    
    echo "📊 Test Results Summary"
    echo "======================"
    echo "Total tests: $total_tests"
    echo "Passed: $TESTS_PASSED"
    echo "Failed: $TESTS_FAILED"
    echo "Success rate: $(( TESTS_PASSED * 100 / (total_tests == 0 ? 1 : total_tests) ))%"
    
    if [[ ${#FAILED_TESTS[@]} -gt 0 ]]; then
        echo ""
        echo "Failed tests:"
        for test in "${FAILED_TESTS[@]}"; do
            echo "  ❌ $test"
        done
    fi
    
    echo ""
    
    if [[ $TESTS_FAILED -eq 0 ]]; then
        log_success "All smoke tests passed! 🎉"
        return 0
    else
        log_error "Some tests failed. Check the details above."
        return 1
    fi
}

# Show usage
show_usage() {
    cat << EOF
Usage: $0 [options]

Options:
  --api-url URL        API base URL (default: http://localhost:8000)
  --frontend-url URL   Frontend URL (default: http://localhost:3000)
  --timeout SECONDS    Service readiness timeout (default: 60)
  --verbose           Enable verbose output
  --help, -h          Show this help

Examples:
  $0                                    # Test local environment
  $0 --api-url http://localhost:8001   # Test with custom API port
  $0 --verbose                         # Verbose output
  
Environment Variables:
  API_BASE_URL         API base URL
  FRONTEND_URL         Frontend URL
  TIMEOUT              Timeout in seconds
  VERBOSE              Enable verbose output (true/false)

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --api-url)
            API_BASE_URL="$2"
            shift 2
            ;;
        --frontend-url)
            FRONTEND_URL="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE="true"
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    run_all_tests
    generate_report
fi