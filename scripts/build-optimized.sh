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
        .\n    \n    log_success \"✅ Frontend build completed\"\n}\n\n# Build both in parallel\nbuild_parallel() {\n    log_info \"⚡ Building backend and frontend in parallel...\"\n    \n    build_backend &\n    backend_pid=$!\n    \n    build_frontend &\n    frontend_pid=$!\n    \n    # Wait for both builds to complete\n    wait $backend_pid\n    backend_result=$?\n    \n    wait $frontend_pid\n    frontend_result=$?\n    \n    if [ $backend_result -eq 0 ] && [ $frontend_result -eq 0 ]; then\n        log_success \"🎉 Parallel build completed successfully!\"\n        return 0\n    else\n        log_error \"❌ One or more builds failed\"\n        return 1\n    fi\n}\n\n# Analyze build cache efficiency\nanalyze_cache() {\n    log_info \"📊 Analyzing build cache efficiency...\"\n    \n    # Check cache usage\n    docker system df\n    \n    # Show build cache\n    docker buildx du\n    \n    log_info \"💡 Cache optimization tips:\"\n    echo \"  - Layer cache hit rate should be >80% for incremental builds\"\n    echo \"  - Use 'docker buildx prune' to clean old cache periodically\"\n    echo \"  - GitHub Actions cache is shared across CI runs\"\n}\n\n# Setup buildx if not exists\nsetup_buildx() {\n    if ! docker buildx inspect optimized-builder >/dev/null 2>&1; then\n        log_info \"🛠️ Setting up optimized buildx builder...\"\n        docker buildx create --name optimized-builder --driver docker-container --use\n        docker buildx inspect optimized-builder --bootstrap\n    else\n        docker buildx use optimized-builder\n    fi\n}\n\n# Main execution\ncase $TARGET in\n    \"backend\")\n        setup_buildx\n        build_backend\n        ;;\n    \"frontend\")\n        setup_buildx\n        build_frontend\n        ;;\n    \"parallel\"|\"all\")\n        setup_buildx\n        build_parallel\n        ;;\n    \"analyze\")\n        analyze_cache\n        ;;\n    *)\n        echo \"Usage: $0 [backend|frontend|parallel|all|analyze]\"\n        echo \"\"\n        echo \"Environment Variables:\"\n        echo \"  PLATFORM=linux/amd64     - Target platform\"\n        echo \"  PUSH=false               - Push to registry\"\n        echo \"  VITE_API_URL=...         - Frontend API URL\"\n        echo \"  VITE_WS_URL=...          - Frontend WebSocket URL\"\n        echo \"\"\n        echo \"Examples:\"\n        echo \"  $0 parallel              - Build both services in parallel\"\n        echo \"  PUSH=true $0 all         - Build and push to registry\"\n        echo \"  $0 analyze               - Analyze build cache efficiency\"\n        exit 1\n        ;;\nesac\n\nlog_success \"🎯 Build optimization completed!\""