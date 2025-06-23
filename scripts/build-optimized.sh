#!/bin/bash

# Optimized Docker build script with advanced caching
# Maximizes build speed through intelligent layer caching

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Configuration
TARGET=${1:-all}
PLATFORM=${PLATFORM:-linux/amd64}
PUSH=${PUSH:-false}
REGISTRY=${REGISTRY:-asia-southeast1-docker.pkg.dev}
PROJECT_ID=${GCP_PROJECT_ID:-dev-assist}

# Enable BuildKit with all optimizations
export DOCKER_BUILDKIT=1
export BUILDKIT_PROGRESS=plain
export BUILDKIT_INLINE_CACHE=1

log_info "🚀 Starting optimized build process for: $TARGET"

# Build backend with advanced caching
build_backend() {
    log_info "🔨 Building backend with multi-stage optimization..."
    
    docker buildx build \
        --platform $PLATFORM \
        --cache-from type=gha,scope=api \
        --cache-from type=registry,ref=$REGISTRY/$PROJECT_ID/dev-assist/api:latest \
        --cache-to type=gha,mode=max,scope=api \
        --target runtime \
        --tag dev-assist-api:latest \
        --tag dev-assist-api:$(git rev-parse --short HEAD) \
        $([ "$PUSH" = "true" ] && echo "--push" || echo "--load") \
        .
    
    log_success "✅ Backend build completed"
}

# Build frontend with advanced caching
build_frontend() {
    log_info "🔨 Building frontend with multi-stage optimization..."
    
    docker buildx build \
        --platform $PLATFORM \
        --cache-from type=gha,scope=frontend \
        --cache-from type=registry,ref=$REGISTRY/$PROJECT_ID/dev-assist/frontend:latest \
        --cache-to type=gha,mode=max,scope=frontend \
        --target runtime \
        --file frontend/Dockerfile.prod \
        --tag dev-assist-frontend:latest \
        --tag dev-assist-frontend:$(git rev-parse --short HEAD) \
        --build-arg VITE_API_URL=${VITE_API_URL:-http://localhost:8000} \
        --build-arg VITE_WS_URL=${VITE_WS_URL:-ws://localhost:8000} \
        $([ "$PUSH" = "true" ] && echo "--push" || echo "--load") \
        .
    
    log_success "✅ Frontend build completed"
}

# Build both in parallel
build_parallel() {
    log_info "⚡ Building backend and frontend in parallel..."
    
    build_backend &
    backend_pid=$!
    
    build_frontend &
    frontend_pid=$!
    
    # Wait for both builds to complete
    wait $backend_pid
    backend_result=$?
    
    wait $frontend_pid
    frontend_result=$?
    
    if [ $backend_result -eq 0 ] && [ $frontend_result -eq 0 ]; then
        log_success "🎉 Parallel build completed successfully!"
        return 0
    else
        log_error "❌ One or more builds failed"
        return 1
    fi
}

# Analyze build cache efficiency
analyze_cache() {
    log_info "📊 Analyzing build cache efficiency..."
    
    # Check cache usage
    docker system df
    
    # Show build cache
    docker buildx du
    
    log_info "💡 Cache optimization tips:"
    echo "  - Layer cache hit rate should be >80% for incremental builds"
    echo "  - Use 'docker buildx prune' to clean old cache periodically"
    echo "  - GitHub Actions cache is shared across CI runs"
}

# Setup buildx if not exists
setup_buildx() {
    if ! docker buildx inspect optimized-builder >/dev/null 2>&1; then
        log_info "🛠️ Setting up optimized buildx builder..."
        docker buildx create --name optimized-builder --driver docker-container --use
        docker buildx inspect optimized-builder --bootstrap
    else
        docker buildx use optimized-builder
    fi
}

# Main execution
case $TARGET in
    "backend")
        setup_buildx
        build_backend
        ;;
    "frontend")
        setup_buildx
        build_frontend
        ;;
    "parallel"|"all")
        setup_buildx
        build_parallel
        ;;
    "analyze")
        analyze_cache
        ;;
    *)
        echo "Usage: $0 [backend|frontend|parallel|all|analyze]"
        echo ""
        echo "Environment Variables:"
        echo "  PLATFORM=linux/amd64     - Target platform"
        echo "  PUSH=false               - Push to registry"
        echo "  VITE_API_URL=...         - Frontend API URL"
        echo "  VITE_WS_URL=...          - Frontend WebSocket URL"
        echo ""
        echo "Examples:"
        echo "  $0 parallel              - Build both services in parallel"
        echo "  PUSH=true $0 all         - Build and push to registry"
        echo "  $0 analyze               - Analyze build cache efficiency"
        exit 1
        ;;
esac

log_success "🎯 Build optimization completed!""