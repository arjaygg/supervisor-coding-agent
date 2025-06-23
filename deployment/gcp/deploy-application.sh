#!/bin/bash

# Deploy Dev-Assist Application to Google Cloud VM
# Handles application deployment, SSL setup, and service configuration

set -euo pipefail

# Configuration variables
PROJECT_ID="${GCP_PROJECT_ID:-}"
ZONE="${GCP_ZONE:-us-central1-a}"
VM_NAME="${VM_NAME:-dev-assist-vm}"
DOMAIN_NAME="${DOMAIN_NAME:-}"
EMAIL="${LETSENCRYPT_EMAIL:-}"
REPO_URL="${REPO_URL:-https://github.com/your-username/dev-assist.git}"
BRANCH="${BRANCH:-main}"

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
# Production Environment Configuration
APP_DEBUG=false
LOG_LEVEL=INFO

# Database Configuration
DATABASE_URL=postgresql://supervisor:supervisor_pass@postgres:5432/supervisor_agent

# Redis Configuration
REDIS_URL=redis://redis:6379/0

# Celery Configuration
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

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

# Deploy application to VM
deploy_application() {
    log_info "Deploying application to VM..."
    
    # Create deployment commands
    cat > /tmp/deploy-commands.sh << 'EOF'
#!/bin/bash
set -euo pipefail

# Navigate to application directory
cd /opt/dev-assist

# Clone or update repository
if [ -d ".git" ]; then
    echo "Updating existing repository..."
    git fetch origin
    git reset --hard origin/main
else
    echo "Cloning repository..."
    git clone https://github.com/your-username/dev-assist.git .
fi

# Copy environment file
cp /tmp/.env.prod .env

# Stop existing services if running
docker-compose down || true

# Build services in parallel with BuildKit
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Build with optimized settings
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build --parallel

# Start services with optimized startup order
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --remove-orphans

# Wait for critical services to be healthy
echo "Waiting for critical services to be healthy..."
max_attempts=20
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker-compose ps | grep -E "(postgres|redis)" | grep -q "healthy"; then
        echo "Critical services are healthy"
        break
    fi
    echo "Waiting for services... attempt $((attempt + 1))/$max_attempts"
    sleep 3
    attempt=$((attempt + 1))
done

# Run database migrations
echo "Running database migrations..."
docker-compose exec -T api alembic upgrade head

# Final health check
echo "Verifying all services..."
docker-compose ps

echo "Application deployed successfully!"
EOF

    # Copy files to VM
    gcloud compute scp /tmp/.env.prod $VM_NAME:/tmp/.env.prod --zone=$ZONE --project=$PROJECT_ID
    gcloud compute scp /tmp/deploy-commands.sh $VM_NAME:/tmp/deploy-commands.sh --zone=$ZONE --project=$PROJECT_ID
    
    # Execute deployment
    gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command="chmod +x /tmp/deploy-commands.sh && sudo /tmp/deploy-commands.sh"
    
    log_success "Application deployed successfully"
}

# Setup SSL certificates
setup_ssl() {
    if [[ -z "$DOMAIN_NAME" || -z "$EMAIL" ]]; then
        log_warning "Domain name or email not provided. Skipping SSL setup."
        return
    fi
    
    log_info "Setting up SSL certificates for $DOMAIN_NAME..."
    
    # Create Nginx configuration
    cat > /tmp/nginx-dev-assist.conf << EOF
server {
    listen 80;
    server_name $DOMAIN_NAME;
    
    # Redirect all HTTP traffic to HTTPS
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN_NAME;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    
    # API proxy
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # WebSocket proxy
    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # Frontend proxy
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

    # Create SSL setup commands
    cat > /tmp/ssl-setup.sh << EOF
#!/bin/bash
set -euo pipefail

# Install Nginx configuration
cp /tmp/nginx-dev-assist.conf /etc/nginx/sites-available/dev-assist
ln -sf /etc/nginx/sites-available/dev-assist /etc/nginx/sites-enabled/dev-assist

# Remove default Nginx configuration if it exists
rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
nginx -t

# Get SSL certificate
certbot --nginx -d $DOMAIN_NAME --email $EMAIL --agree-tos --non-interactive

# Start Nginx
systemctl enable nginx
systemctl restart nginx

echo "SSL setup completed successfully!"
EOF

    # Copy files and execute SSL setup
    gcloud compute scp /tmp/nginx-dev-assist.conf $VM_NAME:/tmp/nginx-dev-assist.conf --zone=$ZONE --project=$PROJECT_ID
    gcloud compute scp /tmp/ssl-setup.sh $VM_NAME:/tmp/ssl-setup.sh --zone=$ZONE --project=$PROJECT_ID
    gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command="chmod +x /tmp/ssl-setup.sh && sudo /tmp/ssl-setup.sh"
    
    log_success "SSL certificates configured for $DOMAIN_NAME"
}

# Setup systemd services
setup_systemd_services() {
    log_info "Setting up systemd services..."
    
    # Create systemd service file
    cat > /tmp/dev-assist.service << 'EOF'
[Unit]
Description=Dev-Assist Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/dev-assist
ExecStart=/usr/local/bin/docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

    # Create service setup commands
    cat > /tmp/systemd-setup.sh << 'EOF'
#!/bin/bash
set -euo pipefail

# Install systemd service
cp /tmp/dev-assist.service /etc/systemd/system/dev-assist.service

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable dev-assist.service

# Create auto-renewal cron job for SSL certificates
echo "0 12 * * * /usr/bin/certbot renew --quiet" | crontab -

echo "Systemd services configured successfully!"
EOF

    # Copy files and execute setup
    gcloud compute scp /tmp/dev-assist.service $VM_NAME:/tmp/dev-assist.service --zone=$ZONE --project=$PROJECT_ID
    gcloud compute scp /tmp/systemd-setup.sh $VM_NAME:/tmp/systemd-setup.sh --zone=$ZONE --project=$PROJECT_ID
    gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command="chmod +x /tmp/systemd-setup.sh && sudo /tmp/systemd-setup.sh"
    
    log_success "Systemd services configured"
}

# Verify deployment
verify_deployment() {
    log_info "Verifying deployment..."
    
    # Get VM external IP
    EXTERNAL_IP=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --project=$PROJECT_ID --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    
    # Test API endpoint with faster check
    if curl -f --max-time 10 "http://$EXTERNAL_IP:8000/api/v1/ping" &> /dev/null; then
        log_success "API is responding correctly"
    else
        log_warning "API health check failed"
    fi
    
    # Quick service status check
    gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command="docker-compose ps --services --filter status=running | wc -l" > /tmp/running_services
    running_count=$(cat /tmp/running_services)
    if [ "$running_count" -gt 0 ]; then
        log_success "$running_count services are running"
    else
        log_warning "Some services may not be running properly"
    fi
    
    log_success "Deployment verification completed"
}

# Display access information
display_access_info() {
    EXTERNAL_IP=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --project=$PROJECT_ID --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    
    log_success "Deployment Complete!"
    echo ""
    echo "Access Information:"
    echo "=================="
    echo "External IP: $EXTERNAL_IP"
    echo ""
    echo "Application URLs:"
    if [[ -n "$DOMAIN_NAME" ]]; then
        echo "Frontend: https://$DOMAIN_NAME"
        echo "API: https://$DOMAIN_NAME/api/v1/"
        echo "API Docs: https://$DOMAIN_NAME/api/v1/docs"
        echo "WebSocket: wss://$DOMAIN_NAME/ws"
    else
        echo "Frontend: http://$EXTERNAL_IP:3000"
        echo "API: http://$EXTERNAL_IP:8000/api/v1/"
        echo "API Docs: http://$EXTERNAL_IP:8000/docs"
        echo "WebSocket: ws://$EXTERNAL_IP:8000/ws"
    fi
    echo ""
    echo "Management Commands:"
    echo "SSH: gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID"
    echo "Logs: gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command='cd /opt/dev-assist && docker-compose logs -f'"
    echo "Restart: gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command='sudo systemctl restart dev-assist'"
    echo ""
    echo "Important Notes:"
    echo "- Update the CLAUDE_API_KEYS in /opt/dev-assist/.env on the VM"
    echo "- Configure notification settings if needed"
    echo "- Monitor system resources and scale as needed"
}

# Main execution
main() {
    log_info "Starting Dev-Assist application deployment"
    
    check_prerequisites
    generate_env_file
    deploy_application
    setup_ssl
    setup_systemd_services
    verify_deployment
    display_access_info
    
    # Clean up temporary files
    rm -f /tmp/.env.prod /tmp/deploy-commands.sh /tmp/nginx-dev-assist.conf /tmp/ssl-setup.sh /tmp/dev-assist.service /tmp/systemd-setup.sh
    
    log_success "Deployment completed successfully!"
}

# Show usage if no arguments provided
if [[ $# -eq 0 ]]; then
    echo "Usage: $0"
    echo ""
    echo "Environment Variables:"
    echo "  GCP_PROJECT_ID       : Google Cloud Project ID (required)"
    echo "  GCP_ZONE            : Zone for VM (default: us-central1-a)"
    echo "  VM_NAME             : VM instance name (default: dev-assist-vm)"
    echo "  DOMAIN_NAME         : Custom domain name (optional, for SSL)"
    echo "  LETSENCRYPT_EMAIL   : Email for Let's Encrypt (required if using SSL)"
    echo "  REPO_URL            : Git repository URL (optional)"
    echo "  BRANCH              : Git branch to deploy (default: main)"
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