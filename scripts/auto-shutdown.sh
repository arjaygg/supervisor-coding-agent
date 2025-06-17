#!/bin/bash

# Auto-shutdown script for cost optimization
# Automatically shuts down VM during non-work hours to save costs

set -euo pipefail

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-}"
ZONE="${GCP_ZONE:-asia-southeast1-a}"
VM_NAME="${VM_NAME:-dev-assist-vm}"
LOG_FILE="/var/log/auto-shutdown.log"

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Check if running on the VM itself or external
if [[ -n "${VM_INSTANCE_NAME:-}" ]]; then
    # Running on the VM itself
    log "Auto-shutdown initiated from within VM"
    
    # Graceful shutdown of services
    log "Stopping Docker services gracefully..."
    cd /opt/dev-assist
    docker-compose -f docker-compose.prod.yml down --timeout 30
    
    log "Services stopped. VM will shutdown in 60 seconds."
    sleep 60
    
    # Shutdown the VM
    sudo shutdown -h now
    
else
    # Running externally (from CI/CD or local machine)
    if [[ -z "$PROJECT_ID" ]]; then
        echo "Error: GCP_PROJECT_ID is required"
        exit 1
    fi
    
    log "External auto-shutdown initiated for VM: $VM_NAME"
    
    # Check if VM is running
    VM_STATUS=$(gcloud compute instances describe "$VM_NAME" \
        --project="$PROJECT_ID" \
        --zone="$ZONE" \
        --format="value(status)" 2>/dev/null || echo "NOT_FOUND")
    
    if [[ "$VM_STATUS" == "RUNNING" ]]; then
        log "VM is running. Initiating shutdown..."
        
        # Stop the VM
        gcloud compute instances stop "$VM_NAME" \
            --project="$PROJECT_ID" \
            --zone="$ZONE" \
            --quiet
        
        log "VM shutdown completed successfully"
    elif [[ "$VM_STATUS" == "TERMINATED" ]]; then
        log "VM is already stopped"
    else
        log "VM not found or in unexpected state: $VM_STATUS"
    fi
fi