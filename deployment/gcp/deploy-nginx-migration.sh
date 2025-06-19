#!/bin/bash

# Deploy nginx Migration Branch to Google Cloud VM
# Specialized deployment script for testing the Traefik → nginx migration

set -euo pipefail

# Configuration variables
PROJECT_ID="${GCP_PROJECT_ID:-}"
ZONE="${GCP_ZONE:-us-central1-a}"
VM_NAME="${VM_NAME:-dev-assist-vm}"
DOMAIN_NAME="${DOMAIN_NAME:-}"
EMAIL="${LETSENCRYPT_EMAIL:-}"
REPO_URL="${REPO_URL:-https://github.com/arjaygg/supervisor-coding-agent.git}"
BRANCH="feature/migrate-traefik-to-nginx"

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

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if [[ -z "$PROJECT_ID" ]]; then
        log_error "GCP_PROJECT_ID environment variable is not set."
        exit 1
    fi
    
    # Check if VM exists
    if ! gcloud compute instances describe $VM_NAME --zone=$ZONE --project=$PROJECT_ID &> /dev/null; then
        log_error "VM $VM_NAME does not exist in zone $ZONE. Run vm-setup.sh first."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Generate environment file
generate_env_file() {
    log_info "Generating environment configuration..."
    
    cat > /tmp/.env.prod << EOF
# Production Environment Configuration - nginx Migration Testing
APP_DEBUG=false
LOG_LEVEL=INFO

# Database Configuration
DATABASE_URL=postgresql://supervisor:supervisor_pass@postgres:5432/supervisor_agent

# Redis Configuration
REDIS_URL=redis://redis:6379/0

# Celery Configuration
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# SSL Configuration for nginx migration
DOMAIN_NAME=${DOMAIN_NAME:-localhost}
LETSENCRYPT_EMAIL=${EMAIL:-admin@example.com}

# Claude Configuration (you'll need to set these)
CLAUDE_API_KEYS=your-api-keys-here
CLAUDE_QUOTA_LIMIT_PER_AGENT=1000
CLAUDE_QUOTA_RESET_HOURS=24

# Application Configuration
APP_HOST=0.0.0.0
APP_PORT=8000
WORKER_CONCURRENCY=4
BATCH_SIZE=10
BATCH_INTERVAL_SECONDS=60
MAX_RETRIES=3

# Notification Configuration (optional)
SLACK_BOT_TOKEN=
SLACK_CHANNEL=#alerts
EMAIL_SMTP_HOST=
EMAIL_USERNAME=
EMAIL_PASSWORD=
EMAIL_FROM=
EMAIL_TO=

# Security
SECRET_KEY=$(openssl rand -hex 32)
EOF

    log_success "Environment file generated"
}

# Deploy nginx migration branch
deploy_nginx_migration() {
    log_info "Deploying nginx migration branch to VM..."
    
    # Create deployment commands for nginx migration
    cat > /tmp/deploy-nginx-migration.sh << EOF
#!/bin/bash
set -euo pipefail

echo "🚀 Starting nginx migration deployment..."

# Navigate to application directory
cd /opt/dev-assist

# Clone or update repository to nginx migration branch
if [ -d ".git" ]; then
    echo "📥 Updating existing repository..."
    git fetch origin
    git checkout feature/migrate-traefik-to-nginx
    git reset --hard origin/feature/migrate-traefik-to-nginx
else
    echo "📥 Cloning repository..."
    git clone --branch feature/migrate-traefik-to-nginx $REPO_URL .
fi

# Copy environment file
cp /tmp/.env.prod .env

# Stop existing services if running
echo "⏹️  Stopping existing services..."
docker compose -f docker-compose.prod.yml down || true

# Clean up any existing containers and networks
docker system prune -f || true

# Create necessary directories for nginx migration
echo "📁 Creating necessary directories..."
mkdir -p ./deployment/nginx/ssl
mkdir -p ./deployment/certbot/www
mkdir -p ./deployment/certbot/conf

# Generate DH parameters if not exists
if [ ! -f "./deployment/nginx/ssl/dhparam.pem" ]; then
    echo "🔐 Generating DH parameters (this may take a few minutes)..."
    openssl dhparam -out ./deployment/nginx/ssl/dhparam.pem 2048
fi

# Make sure init scripts are executable
chmod +x ./deployment/nginx/docker-ssl-init.sh
chmod +x ./deployment/nginx/init-ssl.sh

# Build images first
echo "🔨 Building images..."
docker compose -f docker-compose.prod.yml build

# Start database services first
echo "🗄️  Starting database services..."
docker compose -f docker-compose.prod.yml up -d postgres redis

# Wait for databases to be ready
echo "⏳ Waiting for databases to be ready..."
sleep 20

# Start application services
echo "🚀 Starting application services..."
docker compose -f docker-compose.prod.yml up -d api worker beat frontend

# Wait for application services
echo "⏳ Waiting for application services..."
sleep 15

# Initialize SSL and start nginx + certbot
echo "🔒 Initializing SSL and starting nginx..."
./deployment/nginx/docker-ssl-init.sh

echo "✅ nginx migration deployment completed!"

# Show service status
echo "📊 Service status:"
docker compose -f docker-compose.prod.yml ps

echo "📋 nginx and certbot logs:"
docker compose -f docker-compose.prod.yml logs --tail=20 nginx certbot
EOF

    # Copy files to VM
    gcloud compute scp /tmp/.env.prod $VM_NAME:/tmp/.env.prod --zone=$ZONE --project=$PROJECT_ID
    gcloud compute scp /tmp/deploy-nginx-migration.sh $VM_NAME:/tmp/deploy-nginx-migration.sh --zone=$ZONE --project=$PROJECT_ID
    
    # Execute deployment
    gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command="chmod +x /tmp/deploy-nginx-migration.sh && sudo REPO_URL=$REPO_URL /tmp/deploy-nginx-migration.sh"
    
    log_success "nginx migration deployed successfully"
}

# Verify nginx deployment
verify_nginx_deployment() {
    log_info "Verifying nginx deployment..."
    
    # Get VM external IP
    EXTERNAL_IP=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --project=$PROJECT_ID --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    
    log_info "Testing nginx endpoints..."
    
    # Test HTTP endpoint (should redirect to HTTPS or serve content)
    if curl -f -s "http://$EXTERNAL_IP/health" &> /dev/null; then
        log_success "nginx HTTP health endpoint is responding"
    else
        log_warning "nginx HTTP health endpoint check failed"
    fi
    
    # Test API through nginx
    sleep 5
    if curl -f -s "http://$EXTERNAL_IP/api/v1/healthz" &> /dev/null; then
        log_success "API is accessible through nginx"
    else
        log_warning "API health check through nginx failed"
    fi
    
    # Check service logs
    log_info "Checking nginx and certbot service status..."
    gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command="cd /opt/dev-assist && docker compose -f docker-compose.prod.yml ps nginx certbot"
    
    log_success "nginx deployment verification completed"
}

# Display access information
display_access_info() {
    EXTERNAL_IP=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --project=$PROJECT_ID --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    
    log_success "nginx Migration Deployment Complete! 🎉"
    echo ""
    echo "Access Information:"
    echo "=================="
    echo "External IP: $EXTERNAL_IP"
    echo "Branch: feature/migrate-traefik-to-nginx"
    echo ""
    echo "Application URLs (via nginx):"
    if [[ -n "$DOMAIN_NAME" ]]; then
        echo "Frontend: https://$DOMAIN_NAME"
        echo "API: https://$DOMAIN_NAME/api/v1/"
        echo "API Docs: https://$DOMAIN_NAME/api/v1/docs"
        echo "WebSocket: wss://$DOMAIN_NAME/ws"
        echo "Health Check: https://$DOMAIN_NAME/health"
    else
        echo "Frontend: http://$EXTERNAL_IP (via nginx port 80)"
        echo "API: http://$EXTERNAL_IP/api/v1/"
        echo "API Docs: http://$EXTERNAL_IP/api/docs"
        echo "WebSocket: ws://$EXTERNAL_IP/ws"
        echo "Health Check: http://$EXTERNAL_IP/health"
    fi
    echo ""
    echo "Testing Commands:"
    echo "================"
    echo "# Test API endpoint"
    echo "curl http://$EXTERNAL_IP/api/v1/healthz"
    echo ""
    echo "# Test frontend"
    echo "curl http://$EXTERNAL_IP/"
    echo ""
    echo "# Check nginx status"
    echo "gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command='cd /opt/dev-assist && docker compose -f docker-compose.prod.yml logs nginx'"
    echo ""
    echo "# Check all services"
    echo "gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command='cd /opt/dev-assist && docker compose -f docker-compose.prod.yml ps'"
    echo ""
    echo "Management Commands:"
    echo "==================="
    echo "SSH: gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID"
    echo "Logs: gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command='cd /opt/dev-assist && docker compose -f docker-compose.prod.yml logs -f'"
    echo "Restart nginx: gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command='cd /opt/dev-assist && docker compose -f docker-compose.prod.yml restart nginx'"
    echo ""
    echo "Important Notes:"
    echo "==============="
    echo "- This is testing the nginx migration branch"
    echo "- Update CLAUDE_API_KEYS in /opt/dev-assist/.env on the VM"
    echo "- Monitor nginx and certbot services for SSL certificate management"
    echo "- Compare performance with previous Traefik setup"
}

# Main execution
main() {
    log_info "Starting nginx migration deployment"
    
    check_prerequisites
    generate_env_file
    deploy_nginx_migration
    verify_nginx_deployment
    display_access_info
    
    # Clean up temporary files
    rm -f /tmp/.env.prod /tmp/deploy-nginx-migration.sh
    
    log_success "nginx migration deployment completed successfully!"
}

# Show usage if no arguments provided
if [[ $# -eq 0 ]]; then
    echo "nginx Migration Deployment Script"
    echo "================================="
    echo ""
    echo "This script deploys the feature/migrate-traefik-to-nginx branch for testing"
    echo ""
    echo "Environment Variables:"
    echo "  GCP_PROJECT_ID       : Google Cloud Project ID (required)"
    echo "  GCP_ZONE            : Zone for VM (default: us-central1-a)"
    echo "  VM_NAME             : VM instance name (default: dev-assist-vm)"
    echo "  DOMAIN_NAME         : Custom domain name (optional, for SSL)"
    echo "  LETSENCRYPT_EMAIL   : Email for Let's Encrypt (required if using SSL)"
    echo ""
    echo "Example:"
    echo "  export GCP_PROJECT_ID=my-project"
    echo "  export DOMAIN_NAME=dev-assist.example.com"
    echo "  export LETSENCRYPT_EMAIL=admin@example.com"
    echo "  $0"
    exit 1
fi

# Run main function
main "$@"