# Cloud Run Setup Guide

## Overview

This guide walks through the one-time setup process for the Cloud Run container-native deployment environment.

## Prerequisites

### Required Tools
- **Google Cloud SDK (gcloud)**: [Install Guide](https://cloud.google.com/sdk/docs/install)
- **Docker**: [Install Guide](https://docs.docker.com/get-docker/) (for local testing)
- **Git**: For repository management

### Required Permissions
Your Google Cloud account needs the following IAM roles:
- **Project Editor** (or combination of specific admin roles below)
- **Service Usage Admin** (to enable APIs)
- **IAM Admin** (to create service accounts)
- **Artifact Registry Admin** (to create container registry)
- **Cloud Run Admin** (to deploy services)
- **Secret Manager Admin** (to manage secrets)

## Setup Methods

### Method 1: Interactive Setup (Recommended)
```bash
# From project root directory
./setup-cloud-run.sh
```

### Method 2: Non-Interactive Setup
```bash
# Set required environment variables
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="asia-southeast1"  # Optional, defaults to asia-southeast1
export ENVIRONMENT="development"     # Optional, defaults to development

# Run setup script
./deployment/cloud-run/setup-cloud-run.sh
```

### Method 3: Manual Step-by-Step
If you prefer to run commands manually or need to troubleshoot:

#### 1. Authenticate with Google Cloud
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

#### 2. Enable Required APIs
```bash
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable iam.googleapis.com
gcloud services enable cloudresourcemanager.googleapis.com
```

#### 3. Create Artifact Registry Repository
```bash
gcloud artifacts repositories create dev-assist \
  --repository-format=docker \
  --location=asia-southeast1 \
  --description="Dev Assist application container images"
```

#### 4. Create Service Accounts
```bash
# API service account
gcloud iam service-accounts create dev-assist-api \
  --display-name="Dev Assist API Service"

# Frontend service account
gcloud iam service-accounts create dev-assist-frontend \
  --display-name="Dev Assist Frontend Service"
```

#### 5. Grant IAM Permissions
```bash
# API service account permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:dev-assist-api@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Add other required roles as needed
```

#### 6. Set Up Secrets
```bash
cd deployment/secrets
export GCP_PROJECT_ID="your-project-id"
export ENVIRONMENT="development"
./setup-secret-manager.sh
```

## What the Setup Script Does

### 1. 🔐 Authentication Verification
- Verifies gcloud CLI is installed and authenticated
- Checks project access permissions
- Sets up gcloud configuration defaults

### 2. 📡 API Enablement
Enables all required Google Cloud APIs:
- Cloud Run API
- Cloud Build API
- Secret Manager API
- Artifact Registry API
- IAM API
- Cloud Resource Manager API
- Service Usage API

### 3. 📦 Artifact Registry Setup
- Creates `dev-assist` Docker repository in specified region
- Configures Docker authentication for the registry
- Sets up proper access permissions

### 4. 👤 Service Account Creation
Creates dedicated service accounts with minimal required permissions:

**API Service Account** (`dev-assist-api`):
- `secretmanager.secretAccessor` - Access runtime secrets
- `cloudsql.client` - Database access (if using Cloud SQL)
- `logging.logWriter` - Write application logs
- `monitoring.metricWriter` - Write metrics
- `cloudtrace.agent` - Distributed tracing

**Frontend Service Account** (`dev-assist-frontend`):
- `logging.logWriter` - Write application logs
- `monitoring.metricWriter` - Write metrics

### 5. 🔐 Secret Manager Configuration
- Runs the secret manager setup script
- Creates all required application secrets
- Sets up proper access permissions

### 6. 🧪 Validation Testing
- Tests Cloud Run service creation capability
- Verifies all components are properly configured
- Provides comprehensive setup verification

## Expected Output

### Successful Setup
```
🎉 Cloud Run setup completed successfully!

✅ All APIs enabled
✅ Service accounts created and configured
✅ Artifact Registry repository ready
✅ Cloud Secret Manager configured
✅ IAM permissions granted

🚀 Ready to deploy with:
   Comment on PR: /deploy-cloud-run development
   Or use GitHub Actions workflow dispatch

📊 Expected benefits:
   💰 60-80% cost reduction vs VM deployment
   ⚡ 2-3 minute deployments vs 5-10 minutes
   📦 Auto-scaling from 0 to 1000+ instances
   🔒 Enhanced security with runtime secrets
```

### Common Issues and Solutions

#### Permission Denied Errors
```
ERROR: (gcloud.services.enable) PERMISSION_DENIED: Permission denied to enable service
```
**Solution**: Ensure you have `Service Usage Admin` role or `Project Editor` role.

#### Service Account Creation Failed
```
ERROR: (gcloud.iam.service-accounts.create) PERMISSION_DENIED
```
**Solution**: Ensure you have `IAM Admin` role or `Project Editor` role.

#### Artifact Registry Creation Failed
```
ERROR: (gcloud.artifacts.repositories.create) PERMISSION_DENIED
```
**Solution**: Ensure you have `Artifact Registry Admin` role or `Project Editor` role.

## Post-Setup Steps

### 1. Update Secrets with Real Values
The setup script creates placeholder secrets. Update them with actual values:

```bash
# Update OpenAI API key
echo 'your-actual-openai-key' | \
gcloud secrets versions add development-openai-api-key --data-file=-

# Update GitHub token
echo 'your-actual-github-token' | \
gcloud secrets versions add development-github-token --data-file=-

# Update Let's Encrypt email
echo 'your-email@domain.com' | \
gcloud secrets versions add development-letsencrypt-email --data-file=-
```

### 2. Test Deployment
Create a test PR and comment:
```
/deploy-cloud-run development
```

### 3. Monitor First Deployment
- Watch GitHub Actions workflow execution
- Verify health checks pass
- Test service accessibility
- Monitor costs in GCP Console

## Troubleshooting

### Setup Script Fails
1. **Check permissions**: Ensure your account has all required IAM roles
2. **Verify project**: Confirm project ID is correct and accessible
3. **Check quotas**: Ensure project has sufficient quotas for Cloud Run
4. **Review logs**: Check detailed error messages in script output

### Manual Verification
After setup, manually verify components:

```bash
# Check APIs are enabled
gcloud services list --enabled --filter="name:run.googleapis.com"

# Check service accounts exist
gcloud iam service-accounts list --filter="displayName:Dev Assist"

# Check Artifact Registry
gcloud artifacts repositories list --location=asia-southeast1

# Check secrets
gcloud secrets list --filter="labels.environment=development"
```

### Getting Help
- Review setup logs carefully for specific error messages
- Check [Cloud Run documentation](https://cloud.google.com/run/docs)
- Verify IAM permissions in GCP Console
- Contact development team for project-specific issues

## Cost Considerations

### Setup Costs
- **One-time setup**: Free (within free tier limits)
- **Artifact Registry storage**: ~$0.10/GB/month
- **Secret Manager**: First 6 secret versions free, then $0.06/10K accesses

### Runtime Costs (After Deployment)
- **Cloud Run**: Pay per request (estimated $2-8/month for typical usage)
- **Significant savings**: 60-80% reduction compared to always-on VM ($12-15/month)

## Security Notes

### Service Account Permissions
The setup follows the principle of least privilege:
- Each service account has only the minimum required permissions
- Secrets are accessed at runtime, not embedded in containers
- All access is logged and auditable

### Network Security
- Services can be configured with VPC connectors for private networking
- All traffic is encrypted in transit
- Cloud Run provides built-in DDoS protection

## Next Steps

After successful setup:
1. **Deploy and test** the application
2. **Monitor performance** and costs for the first week
3. **Fine-tune** auto-scaling settings based on usage patterns
4. **Plan migration** from VM-based deployment
5. **Train team** on new deployment workflow

The Cloud Run setup provides a modern, cost-effective, and secure deployment platform that scales automatically with your application needs.