#!/bin/bash

# Google Cloud VM Setup Script for Dev-Assist System
# Automated provisioning script following Lean DevOps principles

set -euo pipefail

# Configuration variables
PROJECT_ID="${GCP_PROJECT_ID:-}"
ZONE="${GCP_ZONE:-us-central1-a}"
MACHINE_TYPE="${GCP_MACHINE_TYPE:-e2-standard-4}"
VM_NAME="${VM_NAME:-dev-assist-vm}"
BOOT_DISK_SIZE="${BOOT_DISK_SIZE:-50GB}"
DOMAIN_NAME="${DOMAIN_NAME:-}"
EMAIL="${LETSENCRYPT_EMAIL:-}"

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
    
    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        log_error "Google Cloud CLI (gcloud) is not installed. Please install it first."
        exit 1
    fi
    
    # Check if project ID is set
    if [[ -z "$PROJECT_ID" ]]; then
        log_error "GCP_PROJECT_ID environment variable is not set."
        exit 1
    fi
    
    # Check if user is authenticated
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
        log_error "You are not authenticated with Google Cloud. Run 'gcloud auth login' first."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Enable required APIs
enable_apis() {
    log_info "Enabling required Google Cloud APIs..."
    
    gcloud services enable compute.googleapis.com --project=$PROJECT_ID
    gcloud services enable secretmanager.googleapis.com --project=$PROJECT_ID
    gcloud services enable monitoring.googleapis.com --project=$PROJECT_ID
    gcloud services enable logging.googleapis.com --project=$PROJECT_ID
    gcloud services enable cloudresourcemanager.googleapis.com --project=$PROJECT_ID
    
    log_success "APIs enabled successfully"
}

# Create firewall rules
create_firewall_rules() {
    log_info "Creating firewall rules..."
    
    # HTTP/HTTPS traffic
    gcloud compute firewall-rules create dev-assist-http-https \
        --allow tcp:80,tcp:443 \
        --source-ranges 0.0.0.0/0 \
        --description "Allow HTTP and HTTPS traffic for Dev-Assist" \
        --project=$PROJECT_ID \
        --quiet || log_warning "HTTP/HTTPS firewall rule might already exist"
    
    # API port
    gcloud compute firewall-rules create dev-assist-api \
        --allow tcp:8000 \
        --source-ranges 0.0.0.0/0 \
        --description "Allow API traffic for Dev-Assist" \
        --project=$PROJECT_ID \
        --quiet || log_warning "API firewall rule might already exist"
    
    # Frontend port
    gcloud compute firewall-rules create dev-assist-frontend \
        --allow tcp:3000 \
        --source-ranges 0.0.0.0/0 \
        --description "Allow Frontend traffic for Dev-Assist" \
        --project=$PROJECT_ID \
        --quiet || log_warning "Frontend firewall rule might already exist"
    
    # SSH access
    gcloud compute firewall-rules create dev-assist-ssh \
        --allow tcp:22 \
        --source-ranges 0.0.0.0/0 \
        --description "Allow SSH access for Dev-Assist VM" \
        --project=$PROJECT_ID \
        --quiet || log_warning "SSH firewall rule might already exist"
    
    log_success "Firewall rules created successfully"
}

# Generate startup script
generate_startup_script() {
    log_info "Generating VM startup script..."
    
    cat > /tmp/startup-script.sh << 'EOF'
#!/bin/bash

# Update system
apt-get update && apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
usermod -aG docker $USER

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install Git
apt-get install -y git curl wget unzip

# Install Google Cloud SDK
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -
apt-get update && apt-get install -y google-cloud-cli

# Install Certbot for Let's Encrypt
apt-get install -y certbot python3-certbot-nginx nginx

# Create application directory
mkdir -p /opt/dev-assist
cd /opt/dev-assist

# Set up logging
mkdir -p /var/log/dev-assist
touch /var/log/dev-assist/startup.log

echo "VM setup completed at $(date)" >> /var/log/dev-assist/startup.log
EOF

    log_success "Startup script generated"
}

# Create VM instance
create_vm() {
    log_info "Creating VM instance: $VM_NAME..."
    
    gcloud compute instances create $VM_NAME \
        --project=$PROJECT_ID \
        --zone=$ZONE \
        --machine-type=$MACHINE_TYPE \
        --network-interface=network-tier=PREMIUM,subnet=default \
        --maintenance-policy=MIGRATE \
        --provisioning-model=STANDARD \
        --service-account=default \
        --scopes=https://www.googleapis.com/auth/cloud-platform \
        --tags=http-server,https-server,dev-assist \
        --create-disk=auto-delete=yes,boot=yes,device-name=$VM_NAME,image=projects/ubuntu-os-cloud/global/images/ubuntu-2204-jammy-v20240319,mode=rw,size=$BOOT_DISK_SIZE,type=projects/$PROJECT_ID/zones/$ZONE/diskTypes/pd-standard \
        --metadata-from-file startup-script=/tmp/startup-script.sh \
        --no-shielded-secure-boot \
        --shielded-vtpm \
        --shielded-integrity-monitoring \
        --labels=environment=production,app=dev-assist \
        --reservation-affinity=any
    
    log_success "VM instance created successfully"
}

# Wait for VM to be ready
wait_for_vm() {
    log_info "Waiting for VM to be ready..."
    
    # Wait for VM to be running
    while [[ $(gcloud compute instances describe $VM_NAME --zone=$ZONE --project=$PROJECT_ID --format="value(status)") != "RUNNING" ]]; do
        echo "Waiting for VM to start..."
        sleep 10
    done
    
    # Get external IP
    EXTERNAL_IP=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --project=$PROJECT_ID --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    
    log_success "VM is ready. External IP: $EXTERNAL_IP"
    
    # Wait for SSH to be available
    log_info "Waiting for SSH to be available..."
    until gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command="echo 'SSH is ready'" --quiet; do
        echo "Waiting for SSH..."
        sleep 10
    done
    
    log_success "SSH is available"
}

# Display connection information
display_connection_info() {
    EXTERNAL_IP=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --project=$PROJECT_ID --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    
    log_success "VM Setup Complete!"
    echo ""
    echo "Connection Information:"
    echo "======================"
    echo "VM Name: $VM_NAME"
    echo "Zone: $ZONE"
    echo "External IP: $EXTERNAL_IP"
    echo ""
    echo "SSH Command:"
    echo "gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID"
    echo ""
    echo "Access URLs (after deployment):"
    echo "API: http://$EXTERNAL_IP:8000"
    echo "Frontend: http://$EXTERNAL_IP:3000"
    echo "API Docs: http://$EXTERNAL_IP:8000/docs"
    echo ""
    if [[ -n "$DOMAIN_NAME" ]]; then
        echo "Custom Domain URLs (after SSL setup):"
        echo "API: https://$DOMAIN_NAME:8000"
        echo "Frontend: https://$DOMAIN_NAME:3000"
        echo ""
    fi
    echo "Next Steps:"
    echo "1. Run the deployment script to install the application"
    echo "2. Configure SSL certificates if using a custom domain"
    echo "3. Set up monitoring and alerting"
}

# Main execution
main() {
    log_info "Starting Google Cloud VM setup for Dev-Assist System"
    
    check_prerequisites
    enable_apis
    create_firewall_rules
    generate_startup_script
    create_vm
    wait_for_vm
    display_connection_info
    
    # Clean up
    rm -f /tmp/startup-script.sh
    
    log_success "VM setup completed successfully!"
}

# Show usage if no arguments provided
if [[ $# -eq 0 ]]; then
    echo "Usage: $0"
    echo ""
    echo "Environment Variables:"
    echo "  GCP_PROJECT_ID       : Google Cloud Project ID (required)"
    echo "  GCP_ZONE            : Zone for VM (default: us-central1-a)"
    echo "  GCP_MACHINE_TYPE    : Machine type (default: e2-standard-4)"
    echo "  VM_NAME             : VM instance name (default: dev-assist-vm)"
    echo "  BOOT_DISK_SIZE      : Boot disk size (default: 50GB)"
    echo "  DOMAIN_NAME         : Custom domain name (optional)"
    echo "  LETSENCRYPT_EMAIL   : Email for Let's Encrypt (optional)"
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