#!/bin/bash

# Auto-startup script for cost optimization
# Automatically starts VM during work hours

set -euo pipefail

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-}"
ZONE="${GCP_ZONE:-asia-southeast1-a}"
VM_NAME="${VM_NAME:-dev-assist-vm}"
LOG_FILE="/var/log/auto-startup.log"

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Validate required parameters
if [[ -z "$PROJECT_ID" ]]; then
    echo "Error: GCP_PROJECT_ID is required"
    exit 1
fi

log "Auto-startup initiated for VM: $VM_NAME"

# Check current VM status
VM_STATUS=$(gcloud compute instances describe "$VM_NAME" \
    --project="$PROJECT_ID" \
    --zone="$ZONE" \
    --format="value(status)" 2>/dev/null || echo "NOT_FOUND")

if [[ "$VM_STATUS" == "TERMINATED" ]]; then
    log "VM is stopped. Starting up..."
    
    # Start the VM
    gcloud compute instances start "$VM_NAME" \
        --project="$PROJECT_ID" \
        --zone="$ZONE" \
        --quiet
    
    log "VM startup initiated. Waiting for services..."
    
    # Wait for VM to be accessible
    sleep 30
    
    # Get VM external IP
    VM_IP=$(gcloud compute instances describe "$VM_NAME" \
        --project="$PROJECT_ID" \
        --zone="$ZONE" \
        --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    
    log "VM started successfully. IP: $VM_IP"
    log "Services should be available in 2-3 minutes"
    
elif [[ "$VM_STATUS" == "RUNNING" ]]; then
    log "VM is already running"
    
    # Get VM external IP
    VM_IP=$(gcloud compute instances describe "$VM_NAME" \
        --project="$PROJECT_ID" \
        --zone="$ZONE" \
        --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    
    log "VM IP: $VM_IP"
    
else
    log "VM not found or in unexpected state: $VM_STATUS"
    exit 1
fi

# Optional: Health check
if command -v curl &> /dev/null && [[ -n "${VM_IP:-}" ]]; then
    log "Performing health check..."
    
    # Wait up to 3 minutes for services to be ready
    for i in {1..18}; do
        if curl -s -o /dev/null -w "%{http_code}" "http://$VM_IP" | grep -q "200\|301\|302"; then
            log "Services are responding successfully"
            break
        fi
        
        if [[ $i -eq 18 ]]; then
            log "Warning: Services may still be starting up"
        else
            sleep 10
        fi
    done
fi

log "Auto-startup completed"