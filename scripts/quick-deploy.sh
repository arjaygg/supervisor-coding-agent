#!/bin/bash

# Quick deployment script with optimizations
# Optimized for development and testing scenarios

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
ENVIRONMENT=${1:-development}
SKIP_BUILD=${SKIP_BUILD:-false}
SKIP_MIGRATIONS=${SKIP_MIGRATIONS:-false}

log_info "🚀 Starting quick deployment for $ENVIRONMENT environment"

# Enable BuildKit for faster builds
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Select compose file based on environment
if [ "$ENVIRONMENT" = "production" ]; then
    COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
elif [ "$ENVIRONMENT" = "staging" ]; then
    COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
else
    COMPOSE_FILES="-f docker-compose.yml"
fi

# Quick health check function
check_service_health() {
    local service=$1
    local max_attempts=10
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker-compose $COMPOSE_FILES ps $service | grep -q "healthy\|Up"; then
            log_success "$service is healthy"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    log_warning "$service health check timed out"
    return 1
}

# Stop existing services
log_info "🛑 Stopping existing services..."
docker-compose $COMPOSE_FILES down --remove-orphans

# Build only if needed
if [ "$SKIP_BUILD" != "true" ]; then
    log_info "🔨 Building services with parallel optimization..."
    # Build with cache and parallel processing
    docker-compose $COMPOSE_FILES build --parallel --compress
else
    log_info "⏭️ Skipping build (SKIP_BUILD=true)"
fi

# Start services with optimized order
log_info "🚀 Starting services..."
docker-compose $COMPOSE_FILES up -d --remove-orphans

# Wait for critical infrastructure services
log_info "⏳ Waiting for infrastructure services..."
check_service_health "postgres" &
check_service_health "redis" &
wait

# Run migrations if needed
if [ "$SKIP_MIGRATIONS" != "true" ] && [ "$ENVIRONMENT" != "development" ]; then
    log_info "🗄️ Running database migrations..."
    docker-compose $COMPOSE_FILES exec -T api alembic upgrade head
else
    log_info "⏭️ Skipping migrations"
fi

# Quick application health check
log_info "🏥 Checking application health..."
sleep 10

# Check API health
if docker-compose $COMPOSE_FILES exec -T api curl -f http://localhost:8000/api/v1/ping > /dev/null 2>&1; then
    log_success "API is healthy"
    API_HEALTHY=true
else
    log_warning "API health check failed"
    API_HEALTHY=false
fi

# Get service status
log_info "📊 Service Status:"
docker-compose $COMPOSE_FILES ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}"

# Display access information
EXTERNAL_IP=$(curl -s ifconfig.me 2>/dev/null || echo "localhost")
log_success "🎉 Deployment completed!"
echo ""
echo "📋 Access Information:"
echo "====================="
if [ "$ENVIRONMENT" = "production" ]; then
    echo "🌐 Frontend: http://$EXTERNAL_IP:3000"
    echo "🔗 API: http://$EXTERNAL_IP:8000"
    echo "📚 API Docs: http://$EXTERNAL_IP:8000/docs"
else
    echo "🌐 Frontend: http://localhost:3000"
    echo "🔗 API: http://localhost:8000"
    echo "📚 API Docs: http://localhost:8000/docs"
fi
echo ""
echo "🛠️ Management Commands:"
echo "📊 Status: docker-compose $COMPOSE_FILES ps"
echo "📋 Logs: docker-compose $COMPOSE_FILES logs -f"
echo "🔄 Restart: docker-compose $COMPOSE_FILES restart"
echo "🛑 Stop: docker-compose $COMPOSE_FILES down"
echo ""
echo "⚡ Performance Tips:"
echo "- Use SKIP_BUILD=true for faster restarts"
echo "- Use SKIP_MIGRATIONS=true to skip DB migrations"
echo "- Example: SKIP_BUILD=true ./scripts/quick-deploy.sh"

if [ "$API_HEALTHY" = true ]; then
    exit 0
else
    log_error "Some services failed health checks"
    exit 1
fi