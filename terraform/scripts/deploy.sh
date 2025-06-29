#!/bin/bash
# Advanced Deployment Script for Supervisor Coding Agent
# Supports blue-green, canary, and rolling deployments

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEPLOYMENT_LOG="${PROJECT_ROOT}/logs/deployment-$(date +%Y%m%d-%H%M%S).log"

# Default values
ENVIRONMENT="staging"
DEPLOYMENT_STRATEGY="rolling"
IMAGE_TAG=""
NAMESPACE="supervisor-agent"
HEALTH_CHECK_TIMEOUT=300
ROLLBACK_ON_FAILURE=true
DRY_RUN=false
FORCE=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $*${NC}" | tee -a "${DEPLOYMENT_LOG}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $*${NC}" | tee -a "${DEPLOYMENT_LOG}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*${NC}" | tee -a "${DEPLOYMENT_LOG}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $*${NC}" | tee -a "${DEPLOYMENT_LOG}"
}

# Usage function
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Advanced deployment script for Supervisor Coding Agent supporting multiple deployment strategies.

OPTIONS:
    -e, --environment ENVIRONMENT    Target environment (dev, staging, prod) [default: staging]
    -s, --strategy STRATEGY          Deployment strategy (rolling, blue-green, canary) [default: rolling]
    -t, --tag TAG                   Docker image tag to deploy [required]
    -n, --namespace NAMESPACE        Kubernetes namespace [default: supervisor-agent]
    --timeout SECONDS               Health check timeout in seconds [default: 300]
    --no-rollback                   Disable automatic rollback on failure
    --dry-run                       Show what would be deployed without making changes
    --force                         Force deployment even if health checks fail
    -h, --help                      Show this help message

DEPLOYMENT STRATEGIES:
    rolling                         Standard rolling update (default)
    blue-green                      Blue-green deployment with traffic switching
    canary                         Canary deployment with gradual traffic shift

EXAMPLES:
    # Rolling deployment to staging
    $0 --environment staging --strategy rolling --tag v1.2.3

    # Blue-green deployment to production
    $0 --environment prod --strategy blue-green --tag v1.2.3

    # Canary deployment with 10% traffic
    $0 --environment prod --strategy canary --tag v1.2.3

    # Dry run to see what would be deployed
    $0 --environment staging --tag v1.2.3 --dry-run

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -s|--strategy)
                DEPLOYMENT_STRATEGY="$2"
                shift 2
                ;;
            -t|--tag)
                IMAGE_TAG="$2"
                shift 2
                ;;
            -n|--namespace)
                NAMESPACE="$2"
                shift 2
                ;;
            --timeout)
                HEALTH_CHECK_TIMEOUT="$2"
                shift 2
                ;;
            --no-rollback)
                ROLLBACK_ON_FAILURE=false
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done

    # Validate required arguments
    if [[ -z "${IMAGE_TAG}" ]]; then
        error "Image tag is required. Use --tag option."
        usage
        exit 1
    fi

    # Validate environment
    if [[ ! "${ENVIRONMENT}" =~ ^(dev|staging|prod)$ ]]; then
        error "Invalid environment: ${ENVIRONMENT}. Must be dev, staging, or prod."
        exit 1
    fi

    # Validate deployment strategy
    if [[ ! "${DEPLOYMENT_STRATEGY}" =~ ^(rolling|blue-green|canary)$ ]]; then
        error "Invalid deployment strategy: ${DEPLOYMENT_STRATEGY}. Must be rolling, blue-green, or canary."
        exit 1
    fi
}

# Setup logging directory
setup_logging() {
    mkdir -p "$(dirname "${DEPLOYMENT_LOG}")"
    log "Starting deployment with strategy: ${DEPLOYMENT_STRATEGY}"
    log "Environment: ${ENVIRONMENT}"
    log "Image tag: ${IMAGE_TAG}"
    log "Namespace: ${NAMESPACE}"
    log "Log file: ${DEPLOYMENT_LOG}"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    # Check required tools
    local required_tools=("kubectl" "helm" "docker")
    for tool in "${required_tools[@]}"; do
        if ! command -v "${tool}" &> /dev/null; then
            error "${tool} is not installed or not in PATH"
            exit 1
        fi
    done

    # Check Kubernetes connection
    if ! kubectl cluster-info &> /dev/null; then
        error "Cannot connect to Kubernetes cluster"
        exit 1
    fi

    # Check if namespace exists
    if ! kubectl get namespace "${NAMESPACE}" &> /dev/null; then
        warn "Namespace ${NAMESPACE} does not exist. Creating it..."
        if [[ "${DRY_RUN}" == "false" ]]; then
            kubectl create namespace "${NAMESPACE}"
        fi
    fi

    # Verify image exists
    if ! docker manifest inspect "supervisor-agent:${IMAGE_TAG}" &> /dev/null; then
        warn "Image supervisor-agent:${IMAGE_TAG} not found locally. Assuming it exists in registry."
    fi

    log "Prerequisites check completed successfully"
}

# Get current deployment info
get_current_deployment() {
    local current_deployment=""
    if kubectl get deployment supervisor-agent -n "${NAMESPACE}" &> /dev/null; then
        current_deployment=$(kubectl get deployment supervisor-agent -n "${NAMESPACE}" -o jsonpath='{.spec.template.spec.containers[0].image}')
        log "Current deployment: ${current_deployment}"
    else
        log "No existing deployment found"
    fi
    echo "${current_deployment}"
}

# Health check function
health_check() {
    local deployment_name="$1"
    local timeout="${2:-${HEALTH_CHECK_TIMEOUT}}"
    
    log "Performing health check for ${deployment_name} (timeout: ${timeout}s)..."

    # Wait for deployment to be ready
    if ! kubectl wait --for=condition=available deployment/"${deployment_name}" \
        -n "${NAMESPACE}" --timeout="${timeout}s"; then
        error "Deployment ${deployment_name} failed health check"
        return 1
    fi

    # Additional application-specific health checks
    local pod_name
    pod_name=$(kubectl get pods -n "${NAMESPACE}" -l app="${deployment_name}" \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

    if [[ -n "${pod_name}" ]]; then
        # Check if the application is responding
        if kubectl exec -n "${NAMESPACE}" "${pod_name}" -- \
            curl -f http://localhost:8000/api/v1/healthz &> /dev/null; then
            log "Application health check passed for ${deployment_name}"
            return 0
        else
            warn "Application health check failed for ${deployment_name}"
            return 1
        fi
    else
        warn "No pods found for deployment ${deployment_name}"
        return 1
    fi
}

# Rolling deployment strategy
deploy_rolling() {
    log "Starting rolling deployment..."

    local helm_values_file="${PROJECT_ROOT}/helm/supervisor-agent/values-${ENVIRONMENT}.yaml"
    
    if [[ ! -f "${helm_values_file}" ]]; then
        error "Helm values file not found: ${helm_values_file}"
        exit 1
    fi

    # Update image tag in values file or use --set flag
    local helm_command=(
        helm upgrade --install supervisor-agent
        "${PROJECT_ROOT}/helm/supervisor-agent"
        -n "${NAMESPACE}"
        -f "${helm_values_file}"
        --set "image.tag=${IMAGE_TAG}"
        --set "environment=${ENVIRONMENT}"
        --wait
        --timeout="${HEALTH_CHECK_TIMEOUT}s"
    )

    if [[ "${DRY_RUN}" == "true" ]]; then
        helm_command+=(--dry-run --debug)
    fi

    info "Executing: ${helm_command[*]}"
    
    if "${helm_command[@]}"; then
        log "Rolling deployment completed successfully"
        
        if [[ "${DRY_RUN}" == "false" ]]; then
            health_check "supervisor-agent"
        fi
    else
        error "Rolling deployment failed"
        if [[ "${ROLLBACK_ON_FAILURE}" == "true" && "${DRY_RUN}" == "false" ]]; then
            rollback_deployment
        fi
        exit 1
    fi
}

# Blue-green deployment strategy
deploy_blue_green() {
    log "Starting blue-green deployment..."

    # Determine current and new colors
    local current_color=""
    local new_color=""
    
    if kubectl get deployment supervisor-agent-blue -n "${NAMESPACE}" &> /dev/null; then
        if kubectl get service supervisor-agent -n "${NAMESPACE}" \
            -o jsonpath='{.spec.selector.color}' 2>/dev/null | grep -q "blue"; then
            current_color="blue"
            new_color="green"
        else
            current_color="green"
            new_color="blue"
        fi
    else
        current_color="blue"
        new_color="green"
    fi

    log "Current color: ${current_color}, New color: ${new_color}"

    # Deploy to new color
    local helm_command=(
        helm upgrade --install "supervisor-agent-${new_color}"
        "${PROJECT_ROOT}/helm/supervisor-agent"
        -n "${NAMESPACE}"
        -f "${PROJECT_ROOT}/helm/supervisor-agent/values-${ENVIRONMENT}.yaml"
        --set "image.tag=${IMAGE_TAG}"
        --set "nameOverride=supervisor-agent-${new_color}"
        --set "service.name=supervisor-agent-${new_color}"
        --set "deployment.color=${new_color}"
        --wait
        --timeout="${HEALTH_CHECK_TIMEOUT}s"
    )

    if [[ "${DRY_RUN}" == "true" ]]; then
        helm_command+=(--dry-run --debug)
        "${helm_command[@]}"
        return
    fi

    if "${helm_command[@]}"; then
        log "New ${new_color} deployment completed"
        
        # Health check new deployment
        if health_check "supervisor-agent-${new_color}"; then
            log "Health check passed for ${new_color} deployment"
            
            # Switch traffic to new deployment
            log "Switching traffic from ${current_color} to ${new_color}..."
            kubectl patch service supervisor-agent -n "${NAMESPACE}" \
                -p '{"spec":{"selector":{"color":"'${new_color}'"}}}'
            
            log "Traffic switched to ${new_color}"
            
            # Wait a bit and perform final health check
            sleep 10
            if health_check "supervisor-agent-${new_color}" 30; then
                log "Final health check passed. Blue-green deployment successful!"
                
                # Clean up old deployment
                if kubectl get deployment "supervisor-agent-${current_color}" -n "${NAMESPACE}" &> /dev/null; then
                    log "Cleaning up old ${current_color} deployment..."
                    kubectl delete deployment "supervisor-agent-${current_color}" -n "${NAMESPACE}"
                    kubectl delete service "supervisor-agent-${current_color}" -n "${NAMESPACE}" 2>/dev/null || true
                fi
            else
                error "Final health check failed. Rolling back..."
                rollback_blue_green "${current_color}" "${new_color}"
                exit 1
            fi
        else
            error "Health check failed for ${new_color} deployment"
            if [[ "${ROLLBACK_ON_FAILURE}" == "true" ]]; then
                log "Cleaning up failed ${new_color} deployment..."
                kubectl delete deployment "supervisor-agent-${new_color}" -n "${NAMESPACE}" 2>/dev/null || true
            fi
            exit 1
        fi
    else
        error "Blue-green deployment failed"
        exit 1
    fi
}

# Canary deployment strategy
deploy_canary() {
    log "Starting canary deployment..."

    # Deploy canary version
    local helm_command=(
        helm upgrade --install supervisor-agent-canary
        "${PROJECT_ROOT}/helm/supervisor-agent"
        -n "${NAMESPACE}"
        -f "${PROJECT_ROOT}/helm/supervisor-agent/values-${ENVIRONMENT}.yaml"
        --set "image.tag=${IMAGE_TAG}"
        --set "nameOverride=supervisor-agent-canary"
        --set "replicaCount=1"  # Start with single replica
        --set "service.name=supervisor-agent-canary"
        --wait
        --timeout="${HEALTH_CHECK_TIMEOUT}s"
    )

    if [[ "${DRY_RUN}" == "true" ]]; then
        helm_command+=(--dry-run --debug)
        "${helm_command[@]}"
        return
    fi

    if "${helm_command[@]}"; then
        log "Canary deployment completed"
        
        # Health check canary
        if health_check "supervisor-agent-canary"; then
            log "Canary health check passed"
            
            # Configure traffic splitting (this would typically be done with a service mesh)
            # For now, we'll just log the canary deployment success
            log "Canary deployment successful. Monitor metrics and promote when ready."
            log "To promote canary: kubectl scale deployment supervisor-agent-canary --replicas=3"
            log "To rollback canary: kubectl delete deployment supervisor-agent-canary"
            
        else
            error "Canary health check failed"
            if [[ "${ROLLBACK_ON_FAILURE}" == "true" ]]; then
                log "Cleaning up failed canary deployment..."
                kubectl delete deployment supervisor-agent-canary -n "${NAMESPACE}" 2>/dev/null || true
            fi
            exit 1
        fi
    else
        error "Canary deployment failed"
        exit 1
    fi
}

# Rollback function
rollback_deployment() {
    log "Initiating rollback..."
    
    case "${DEPLOYMENT_STRATEGY}" in
        rolling)
            helm rollback supervisor-agent -n "${NAMESPACE}"
            ;;
        blue-green)
            # This is handled in deploy_blue_green function
            log "Blue-green rollback handled in deployment function"
            ;;
        canary)
            kubectl delete deployment supervisor-agent-canary -n "${NAMESPACE}" 2>/dev/null || true
            ;;
    esac
    
    log "Rollback completed"
}

# Blue-green specific rollback
rollback_blue_green() {
    local old_color="$1"
    local new_color="$2"
    
    log "Rolling back blue-green deployment from ${new_color} to ${old_color}..."
    
    # Switch traffic back
    kubectl patch service supervisor-agent -n "${NAMESPACE}" \
        -p '{"spec":{"selector":{"color":"'${old_color}'"}}}'
    
    # Remove failed deployment
    kubectl delete deployment "supervisor-agent-${new_color}" -n "${NAMESPACE}" 2>/dev/null || true
    
    log "Blue-green rollback completed"
}

# Main deployment function
main() {
    parse_args "$@"
    setup_logging
    
    log "=== Supervisor Coding Agent Deployment ==="
    log "Strategy: ${DEPLOYMENT_STRATEGY}"
    log "Environment: ${ENVIRONMENT}"
    log "Image Tag: ${IMAGE_TAG}"
    log "Dry Run: ${DRY_RUN}"
    
    check_prerequisites
    
    local current_deployment
    current_deployment=$(get_current_deployment)
    
    # Execute deployment strategy
    case "${DEPLOYMENT_STRATEGY}" in
        rolling)
            deploy_rolling
            ;;
        blue-green)
            deploy_blue_green
            ;;
        canary)
            deploy_canary
            ;;
        *)
            error "Unknown deployment strategy: ${DEPLOYMENT_STRATEGY}"
            exit 1
            ;;
    esac
    
    if [[ "${DRY_RUN}" == "false" ]]; then
        log "=== Deployment Summary ==="
        log "Previous deployment: ${current_deployment:-"None"}"
        log "New deployment: supervisor-agent:${IMAGE_TAG}"
        log "Strategy: ${DEPLOYMENT_STRATEGY}"
        log "Environment: ${ENVIRONMENT}"
        log "Status: SUCCESS"
        log "==========================="
    else
        log "Dry run completed successfully"
    fi
}

# Trap for cleanup on exit
cleanup() {
    local exit_code=$?
    if [[ ${exit_code} -ne 0 ]]; then
        error "Deployment failed with exit code ${exit_code}"
        error "Check the deployment log: ${DEPLOYMENT_LOG}"
    fi
}

trap cleanup EXIT

# Run main function
main "$@"