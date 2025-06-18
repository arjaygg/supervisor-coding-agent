# 🛠️ GCP Deployment Troubleshooting Guide

Complete guide for diagnosing and fixing common deployment issues.

## 🚀 Quick Diagnostics

### Check Overall System Status
```bash
# Check all container status
gcloud compute ssh VM_NAME --zone=ZONE --command="sudo docker ps --format 'table {{.Names}}\t{{.Status}}'"

# Check memory usage
gcloud compute ssh VM_NAME --zone=ZONE --command="free -h"

# Check .env file
gcloud compute ssh VM_NAME --zone=ZONE --command="cd /opt/dev-assist && tail -10 .env"
```

## 🔧 Common Issues & Solutions

### 1. API Container Crashes with Pydantic Validation Error

**Error**: `ValidationError: max_retries - Input should be a valid integer, unable to parse string as an integer [type=int_parsing, input_value='3LETSENCRYPT_EMAIL=admin@example.com']`

**Root Cause**: .env file corruption during deployment - environment variables concatenated without newlines.

**Diagnosis**:
```bash
gcloud compute ssh VM_NAME --zone=ZONE --command="cd /opt/dev-assist && cat .env | tail -5"
# Look for lines like: MAX_RETRIES=3LETSENCRYPT_EMAIL=admin@example.com
```

**Solution**:
```bash
# Fix .env file on VM
gcloud compute ssh VM_NAME --zone=ZONE --command="
cd /opt/dev-assist && \
sudo cp .env.sample .env && \
echo 'GCP_PROJECT_ID=PROJECT_ID' | sudo tee -a .env && \
echo 'DOMAIN_NAME=dev.dev-assist.example.com' | sudo tee -a .env && \
echo 'LETSENCRYPT_EMAIL=admin@example.com' | sudo tee -a .env && \
sudo sed -i 's/MAX_RETRIES=3.*$/MAX_RETRIES=3/' .env"

# Restart affected containers
gcloud compute ssh VM_NAME --zone=ZONE --command="cd /opt/dev-assist && sudo docker compose -f docker-compose.prod.yml restart api worker beat"
```

**Prevention**: Fixed in workflow with proper newline handling.

### 2. Traefik Configuration Error

**Error**: `Error reading TOML config file /traefik.yml : Near line 4 (last key parsed ''): bare keys cannot contain ':'`

**Root Cause**: Traefik expects TOML format by default, but we provided YAML.

**Diagnosis**:
```bash
gcloud compute ssh VM_NAME --zone=ZONE --command="sudo docker logs TRAEFIK_CONTAINER --tail 10"
# Look for: "Error reading TOML config file"
```

**Solution**:
```bash
# Switch to TOML configuration (already implemented)
# File: deployment/traefik/traefik.toml (TOML format)
# docker-compose.prod.yml updated to use .toml file
```

### 3. External Access Timeout/Connection Refused

**Error**: `Connection timed out` when accessing via IP:80 or IP:443

**Root Cause**: Missing firewall rules for HTTP/HTTPS traffic.

**Diagnosis**:
```bash
# Check firewall rules
gcloud compute firewall-rules list --project=PROJECT_ID --format="table(name,allowed.ports)" | grep -E "(80|443)"

# Test local access (should work)
gcloud compute ssh VM_NAME --zone=ZONE --command="curl -s http://localhost:8080/dashboard/"
```

**Solution**:
```bash
# Create firewall rule for HTTP/HTTPS access
gcloud compute firewall-rules create allow-dev-http \
  --allow tcp:80,tcp:443,tcp:3000,tcp:8000,tcp:8080 \
  --source-ranges 0.0.0.0/0 \
  --target-tags http-server,https-server \
  --project=PROJECT_ID
```

### 4. API Returns 404 Through Traefik

**Error**: `404 page not found` when accessing `/api/v1/healthz` through Traefik

**Root Cause**: Traefik routes configured for HTTPS-only, but testing with HTTP.

**Diagnosis**:
```bash
# Check container labels
gcloud compute ssh VM_NAME --zone=ZONE --command="sudo docker inspect API_CONTAINER | grep -A 5 traefik.http.routers"

# Test with correct host header
curl -H "Host: dev.dev-assist.example.com" "http://VM_IP/api/v1/healthz"
```

**Solution**: Update docker-compose.prod.yml to include both HTTP and HTTPS entrypoints:
```yaml
labels:
  - "traefik.http.routers.api.entrypoints=web,websecure"  # Added 'web' for HTTP
```

### 5. Database Health Check Failures

**Error**: `Database health check failed: Textual SQL expression 'SELECT 1' should be explicitly declared as text('SELECT 1')`

**Root Cause**: SQLAlchemy version compatibility issue with raw SQL in health checks.

**Diagnosis**:
```bash
gcloud compute ssh VM_NAME --zone=ZONE --command="sudo docker logs API_CONTAINER | grep 'Database health check'"
```

**Status**: Known issue, doesn't affect functionality. API still works properly.

### 6. Memory Issues on e2-micro VM

**Error**: Containers being killed or failing to start due to memory pressure.

**Root Cause**: e2-micro (1GB RAM) insufficient for full stack.

**Diagnosis**:
```bash
# Check memory usage
gcloud compute ssh VM_NAME --zone=ZONE --command="free -h && echo '=== Container Memory ===' && sudo docker stats --no-stream"

# Check for OOM kills
gcloud compute ssh VM_NAME --zone=ZONE --command="dmesg | grep -i 'killed process'"
```

**Solution**: 
1. **Immediate**: Use memory-optimized limits (current configuration)
2. **If still failing**: Upgrade to e2-small (2GB RAM, ~$14/month)

```bash
# Stop VM
gcloud compute instances stop VM_NAME --zone=ZONE --project=PROJECT_ID

# Resize VM
gcloud compute instances set-machine-type VM_NAME --machine-type=e2-small --zone=ZONE --project=PROJECT_ID

# Start VM
gcloud compute instances start VM_NAME --zone=ZONE --project=PROJECT_ID
```

### 7. Git Permission Issues on VM

**Error**: `fatal: detected dubious ownership in repository` or `Permission denied`

**Root Cause**: Repository cloned by root but accessed by SSH user.

**Solution**:
```bash
gcloud compute ssh VM_NAME --zone=ZONE --command="
cd /opt/dev-assist && \
sudo chown -R \$USER:\$USER /opt/dev-assist && \
git config --global --add safe.directory /opt/dev-assist"
```

### 8. Docker Permission Issues

**Error**: `permission denied while trying to connect to the Docker daemon socket`

**Root Cause**: SSH user not in docker group.

**Solution**:
```bash
gcloud compute ssh VM_NAME --zone=ZONE --command="
sudo usermod -aG docker \$USER && \
sudo systemctl restart docker"

# Or use sudo for docker commands
sudo docker ps
```

## 🔍 Advanced Diagnostics

### Complete Health Check
```bash
#!/bin/bash
VM_NAME="supervisor-agent"
ZONE="asia-southeast1-b"
PROJECT_ID="gen-lang-client-0274960249"

echo "=== VM Status ==="
gcloud compute instances describe $VM_NAME --zone=$ZONE --project=$PROJECT_ID --format="value(status)"

echo "=== Container Status ==="
gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command="sudo docker ps --format 'table {{.Names}}\t{{.Status}}'"

echo "=== Memory Usage ==="
gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command="free -h"

echo "=== Disk Usage ==="
gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command="df -h"

echo "=== API Health ==="
gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command="sudo docker exec dev-assist-api-1 curl -s http://localhost:8000/api/v1/healthz 2>/dev/null || echo 'API not responding'"

echo "=== Traefik Dashboard ==="
gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command="curl -s http://localhost:8080/dashboard/ | head -1"

echo "=== Environment Check ==="
gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command="cd /opt/dev-assist && tail -5 .env"
```

### Network Connectivity Test
```bash
VM_IP="35.198.238.175"  # Replace with your VM IP

echo "=== External Connectivity ==="
echo "HTTP (port 80):"
curl -s --max-time 5 -H "Host: dev.dev-assist.example.com" "http://$VM_IP/" || echo "Failed"

echo "API through Traefik:"
curl -s --max-time 5 -H "Host: dev.dev-assist.example.com" "http://$VM_IP/api/v1/healthz" || echo "Failed"

echo "Traefik Dashboard:"
curl -s --max-time 5 "http://$VM_IP:8080" || echo "Failed"
```

## 📋 Deployment Checklist

Before troubleshooting, verify:

- [ ] **APIs Enabled**: Service Usage, Compute Engine, Container Registry, Artifact Registry
- [ ] **GitHub Secrets**: `GCP_PROJECT_ID`, `GCP_SERVICE_ACCOUNT_EMAIL`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `LETSENCRYPT_EMAIL`
- [ ] **Firewall Rules**: `allow-dev-http` rule exists
- [ ] **VM Tags**: VM has `http-server` and `https-server` tags
- [ ] **VM Specs**: Sufficient memory (e2-small recommended)

## 🚨 Emergency Recovery

### Complete Stack Reset
```bash
# Stop all services
gcloud compute ssh VM_NAME --zone=ZONE --command="cd /opt/dev-assist && sudo docker compose -f docker-compose.prod.yml down"

# Clean up containers and networks
gcloud compute ssh VM_NAME --zone=ZONE --command="sudo docker system prune -f"

# Reset .env file
gcloud compute ssh VM_NAME --zone=ZONE --command="cd /opt/dev-assist && sudo cp .env.sample .env"

# Pull latest code
gcloud compute ssh VM_NAME --zone=ZONE --command="cd /opt/dev-assist && sudo git pull origin main"

# Restart everything
gcloud compute ssh VM_NAME --zone=ZONE --command="cd /opt/dev-assist && sudo docker compose -f docker-compose.prod.yml up -d"
```

### VM Recreation
```bash
# Delete VM (will lose data but get clean state)
gcloud compute instances delete VM_NAME --zone=ZONE --project=PROJECT_ID

# Run workflow again - it will recreate everything
gh workflow run "🚀 Promote to Development" --field pr_number="LATEST_MERGED_PR"
```

## 📞 Getting Help

1. **Check Logs**: Always start with container logs: `sudo docker logs CONTAINER_NAME`
2. **Verify Configuration**: Check .env file, docker-compose labels, firewall rules
3. **Test Incrementally**: Test containers → internal network → external access
4. **Use Diagnostics**: Run the health check script above
5. **Document Issues**: Add new issues to this troubleshooting guide

## 🔄 Prevention

1. **Monitor Resources**: Set up alerts for memory/CPU usage
2. **Backup Strategy**: Regular .env and volume backups
3. **Testing**: Always test in development before production
4. **Documentation**: Keep this guide updated with new issues

---

**Last Updated**: 2025-06-18  
**Tested Environment**: GCP e2-micro/e2-small, Ubuntu 22.04, Docker Compose v2