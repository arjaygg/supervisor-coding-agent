# 🚀 Testing Deployment via GitHub Actions Workflow

Complete guide to test our cost-optimized GCP deployment through GitHub Actions.

## 🎯 Quick Start (Workflow-First Testing)

### Step 1: Minimal GCP Setup

**What you need**:
- GCP Project ID (e.g., `my-project-123456`)
- **APIs**: The workflow will auto-enable these, but you can enable manually:
  - Compute Engine API
  - Container Registry API  
  - Artifact Registry API
  - Cloud Resource Manager API

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
GOOGLE_CREDENTIALS=<service-account-json>
```

### Step 3: Quick Service Account Creation

**Option A: Via GCP Console (Fastest)**
1. Go to GCP Console → IAM & Admin → Service Accounts
2. Create service account: `github-actions-deploy`
3. Add roles:
   - Compute Admin
   - Storage Admin
   - Service Account User
4. Create JSON key → Copy to `GOOGLE_CREDENTIALS` secret

**Option B: Via CLI**
```bash
# Create service account
gcloud iam service-accounts create github-actions-deploy \
  --display-name="GitHub Actions Deployment"

# Add required roles
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:github-actions-deploy@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/compute.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:github-actions-deploy@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

# Create key
gcloud iam service-accounts keys create key.json \
  --iam-account=github-actions-deploy@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

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
Error: google: could not find default credentials
```
**Fix**: Check `GOOGLE_CREDENTIALS` secret is valid JSON

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