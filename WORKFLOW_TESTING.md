# 🚀 Testing Deployment via GitHub Actions Workflow

Complete guide to test our cost-optimized GCP deployment through GitHub Actions.

## 🎯 Quick Start (Workflow-First Testing)

### Step 1: Minimal GCP Setup

**What you need**:
- GCP Project ID (e.g., `my-project-123456`)
- **Required APIs** (enable these manually in GCP Console first):
  - Service Usage API (required to enable other APIs)
  - Compute Engine API
  - Container Registry API  
  - Artifact Registry API
  - Cloud Resource Manager API

**Enable APIs manually**:
```bash
# Go to GCP Console and enable these APIs, or use gcloud:
gcloud services enable serviceusage.googleapis.com
gcloud services enable compute.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable artifactregistry.googleapis.com
```

### Step 2: Configure GitHub Secrets

Go to: `GitHub Repo → Settings → Secrets and Variables → Actions`

**Add these repository secrets**:
```
GCP_PROJECT_ID=your-project-id
GCP_ZONE=asia-southeast1-a
DEV_VM_NAME=dev-assist-vm
DEV_ENVIRONMENT_URL=dev-assist.example.com
LETSENCRYPT_EMAIL=your-email@domain.com
```

**For GCP Authentication**, you'll need:
```
GCP_WORKLOAD_IDENTITY_PROVIDER=projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/providers/PROVIDER_ID
GCP_SERVICE_ACCOUNT_EMAIL=github-actions-deploy@PROJECT_ID.iam.gserviceaccount.com
```

### Step 3: Set up Workload Identity Federation

**Use the provided setup script:**
```bash
./scripts/setup-github-gcp-integration.sh \
  --project-id YOUR_PROJECT_ID \
  --repo-owner arjaygg \
  --repo-name supervisor-coding-agent
```

**Or manually via GCP Console:**
1. Go to GCP Console → IAM & Admin → Workload Identity Federation
2. Create workload identity pool: `github-actions-pool`
3. Create OIDC provider for GitHub Actions
4. Create service account: `github-actions-deploy` with roles:
   - Compute Admin
   - Storage Admin
   - Service Account User

**The script will output the required secrets that you need to add to GitHub.**

### Step 4: Create Test Branch and PR

```bash
# Create test deployment branch
git checkout -b test-gcp-deployment
echo "# Testing GCP deployment $(date)" >> README.md
git add README.md
git commit -m "test: Trigger real GCP deployment workflow"
git push -u origin test-gcp-deployment

# Create PR
gh pr create \
  --title "🧪 Test Real GCP Deployment" \
  --body "Testing cost-optimized deployment to actual GCP infrastructure"
```

### Step 5: Merge and Trigger Deployment

```bash
# Merge the PR
gh pr merge --squash

# Get the PR number that was just merged
MERGED_PR=$(gh pr list --state merged --limit 1 --json number --jq '.[0].number')

# Trigger promote-to-development workflow
gh workflow run "🚀 Promote to Development" \
  --field pr_number="$MERGED_PR"
```

### Step 6: Monitor Workflow Execution

```bash
# Watch the workflow run
gh run watch

# Or check status
gh run list --workflow="promote-to-dev.yml" --limit 5
```

## 🎯 What the Workflow Will Do

### **Phase 1: Validation** ✅
- Check PR is merged
- Validate GCP credentials
- Check if images can be built

### **Phase 2: Build & Push** 🏗️
- Build optimized Docker images
- Push to Google Container Registry
- Tag with PR number for tracking

### **Phase 3: VM Management** 🖥️
- **Create VM if needed** (e2-micro, 10GB disk)
- Start VM if stopped
- Configure Docker and dependencies

### **Phase 4: Deploy** 🚀
- SSH to VM
- Pull latest images from GCR
- Update docker-compose services
- Start optimized stack

### **Phase 5: Validate** ✅
- Health check API endpoint
- Test frontend loading
- Verify Traefik dashboard
- Report deployment success

## 📊 Expected Results

**If successful, you'll see**:
- ✅ VM created with e2-micro specs (~$8/month)
- ✅ Services running within memory limits
- ✅ API responding at `http://VM_IP:8000/api/v1/healthz`
- ✅ Frontend loading at `http://VM_IP:3000`
- ✅ Traefik dashboard at `http://VM_IP:8080`

**Cost Impact**:
- 💰 **Monthly Cost**: ~$8 (vs $122 original = 93% savings)
- 💰 **With auto-scheduling**: ~$2-3/month (97% total savings)

## 🐛 Common Workflow Issues

### **1. Authentication Failed**
```
Error: You do not currently have an active account selected
```
**Fix**: Ensure `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT_EMAIL` secrets are properly configured

### **1b. Service Usage API Disabled**
```
Error: Service Usage API has not been used in project before or it is disabled
```
**Fix**: Enable Service Usage API manually in GCP Console:
- Go to https://console.developers.google.com/apis/api/serviceusage.googleapis.com/overview?project=YOUR_PROJECT_ID
- Click "Enable API"
- Then enable other required APIs (Compute Engine, Container Registry, Artifact Registry)

### **2. VM Creation Failed**
```
Error: Insufficient quota for 'CPUS' in region 'asia-southeast1'
```
**Fix**: Check GCP quotas or try different region

### **3. Images Failed to Push**
```
Error: denied: Token exchange failed
```
**Fix**: Enable Container Registry API, check service account permissions

### **4. SSH Connection Failed**
```
Error: Permission denied (publickey)
```
**Fix**: VM may still be starting, wait 60s and retry

## 🎉 Success Validation

**After workflow completes**:
1. Check workflow logs show "✅ Deployment completed successfully"
2. Visit your GCP Console → Compute Engine → see new VM
3. Check GCP billing for cost impact
4. Test the deployed application

**Next step**: Set up auto-scheduling for additional 70% cost savings!

## 🚀 Ready to Test?

1. **Share your GCP Project ID**
2. **Configure the GitHub secrets**
3. **Run the workflow test**

The entire test takes ~10-15 minutes and creates real infrastructure!