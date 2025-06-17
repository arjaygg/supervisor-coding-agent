# 🧪 Testing Cost-Optimized GCP Deployment

Complete testing guide for our 97% cost-reduced deployment infrastructure.

## 📋 Prerequisites

- **GCP Account** with billing enabled
- **Google Cloud CLI** installed (`gcloud`)
- **GitHub repository** admin access
- **Domain name** (optional, for SSL testing)

## 🚀 Step-by-Step Testing

### Step 1: GCP Project Setup

```bash
# Set your project ID
export GCP_PROJECT_ID="your-project-id"
export GCP_ZONE="asia-southeast1-a"  # Singapore region
export VM_NAME="dev-assist-vm"

# Authenticate with GCP
gcloud auth login
gcloud config set project $GCP_PROJECT_ID
```

### Step 2: GitHub-GCP Integration

```bash
# Run the integration setup script
./scripts/setup-github-gcp-integration.sh \
  --project-id $GCP_PROJECT_ID \
  --repo-owner arjaygg \
  --repo-name supervisor-coding-agent
```

**Expected Outcome**: 
- ✅ Workload Identity Federation configured
- ✅ Service account created with proper permissions
- ✅ GitHub Actions can authenticate to GCP

### Step 3: Configure GitHub Secrets

Go to GitHub repository → Settings → Secrets and Variables → Actions

Add these secrets:
```
GCP_PROJECT_ID=your-project-id
GCP_ZONE=asia-southeast1-a
DEV_VM_NAME=dev-assist-vm
LETSENCRYPT_EMAIL=your-email@domain.com
```

### Step 4: Create Development VM

```bash
# Create the cost-optimized VM
./deployment/gcp/vm-setup.sh
```

**Expected VM Specs**:
- ✅ **Machine**: e2-micro (1 vCPU, 1GB RAM)
- ✅ **Disk**: 10GB standard
- ✅ **Cost**: ~$8-10/month (95% cheaper than original)
- ✅ **Location**: Asia Southeast (Singapore)

### Step 5: Test Real Deployment

1. **Create a test branch**:
   ```bash
   git checkout -b test-deployment
   echo "# Test deployment $(date)" >> README.md
   git add README.md
   git commit -m "test: Trigger deployment test"
   git push -u origin test-deployment
   ```

2. **Create PR**:
   ```bash
   gh pr create --title "Test Cost-Optimized Deployment" --body "Testing our 97% cost-reduced GCP deployment infrastructure"
   ```

3. **Merge PR**:
   ```bash
   gh pr merge --squash
   ```

4. **Promote to Development**:
   ```bash
   # Trigger the real deployment workflow
   gh workflow run "🚀 Promote to Development" --field pr_number="[PR_NUMBER]"
   ```

### Step 6: Validate Deployment

Check the deployment worked:

```bash
# Get VM IP
VM_IP=$(gcloud compute instances describe $VM_NAME \
  --zone=$GCP_ZONE \
  --format="value(networkInterfaces[0].accessConfigs[0].natIP)")

echo "VM IP: $VM_IP"

# Test services
curl -f "http://$VM_IP:8000/api/v1/healthz"  # API health
curl -f "http://$VM_IP:3000"                 # Frontend
curl -f "http://$VM_IP:8080"                 # Traefik dashboard
```

**Expected Results**:
- ✅ API returns health check response
- ✅ Frontend loads successfully  
- ✅ Traefik dashboard accessible
- ✅ All services using optimized memory limits

### Step 7: Cost Validation

Monitor actual costs:

```bash
# Check current resource usage
gcloud compute instances describe $VM_NAME \
  --zone=$GCP_ZONE \
  --format="value(machineType,disks[0].diskSizeGb,status)"

# Check billing (after 24 hours)
gcloud billing accounts list
gcloud billing budgets list --account=[BILLING_ACCOUNT_ID]
```

### Step 8: Auto-Scheduling Setup

```bash
# Set up cost-saving schedule (3 AM - 3 PM weekdays)
./scripts/setup-schedule.sh --install

# Check status
./scripts/setup-schedule.sh --status
```

**Expected Cost Impact**:
- 🎯 **Base Cost**: ~$8/month (e2-micro)
- 🎯 **With Scheduling**: ~$2-3/month (70% additional savings)
- 🎯 **Total Savings**: 97%+ vs original infrastructure

## 🎯 Success Criteria

- [ ] VM created with optimized specs
- [ ] GitHub Actions deploys to real GCP (not simulation)
- [ ] All services running within memory limits
- [ ] Health checks passing
- [ ] Auto-scheduling configured
- [ ] Total cost under $5/month

## 🐛 Troubleshooting

### Common Issues

1. **GCP Authentication Fails**
   ```bash
   gcloud auth application-default login
   ```

2. **VM Out of Memory**
   ```bash
   # Check memory usage
   gcloud compute ssh $VM_NAME --zone=$GCP_ZONE --command "free -h"
   
   # Restart services if needed
   gcloud compute ssh $VM_NAME --zone=$GCP_ZONE --command "cd /opt/dev-assist && docker-compose restart"
   ```

3. **Services Not Starting**
   ```bash
   # Check logs
   gcloud compute ssh $VM_NAME --zone=$GCP_ZONE --command "cd /opt/dev-assist && docker-compose logs"
   ```

## 📊 Cost Monitoring

Keep track of actual costs:

```bash
# Weekly cost check
gcloud billing accounts list
echo "Monitor your GCP billing dashboard for actual usage"
```

**Target**: Keep monthly costs under $5 for development environment.