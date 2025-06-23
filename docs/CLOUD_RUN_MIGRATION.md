# Cloud Run Migration Guide

## Overview

This guide explains the migration from VM-based deployment to Google Cloud Run container-native deployment for the dev-assist application.

## Cost & Performance Benefits

### Before (VM-based)
- **Cost**: ~$12-15/month (e2-small always-on)
- **Scaling**: Manual VM resizing
- **Management**: SSH, VM patching, manual scaling
- **Deployment**: Mixed container builds + git operations

### After (Cloud Run)
- **Cost**: ~$2-8/month (pay-per-request, auto-scale to zero)
- **Scaling**: Automatic 0 to 1000+ instances
- **Management**: Serverless, no infrastructure management
- **Deployment**: Pure container-native

**Expected Savings: 60-80% cost reduction**

## Architecture Changes

### Secret Management
**From**: GitHub Secrets (build-time only)
**To**: Google Cloud Secret Manager (runtime access)

```bash
# Old approach
GitHub Secrets → Environment Variables → Container Image

# New approach  
Cloud Secret Manager → Runtime API Access → Container
```

### Deployment Pipeline
**From**: VM + SSH + git operations
**To**: Pure container deployment

```bash
# Old approach
Build Container → Push to Registry → SSH to VM → git pull → docker-compose

# New approach
Build Container → Push to Registry → Deploy to Cloud Run
```

## Migration Steps

### Step 1: Set up Cloud Secret Manager
```bash
# Navigate to secrets directory
cd deployment/secrets

# Set your project ID
export GCP_PROJECT_ID="your-project-id"
export ENVIRONMENT="development"

# Run setup script
chmod +x setup-secret-manager.sh
./setup-secret-manager.sh
```

### Step 2: Update secrets with actual values
```bash
# Update database URL (if using Cloud SQL)
echo 'postgresql://user:pass@/db?host=/cloudsql/project:region:instance' | \
gcloud secrets versions add development-db-url --data-file=-

# Update API keys
echo 'your-openai-api-key' | \
gcloud secrets versions add development-openai-api-key --data-file=-

echo 'your-github-token' | \
gcloud secrets versions add development-github-token --data-file=-

# Update email for SSL
echo 'your-email@domain.com' | \
gcloud secrets versions add development-letsencrypt-email --data-file=-
```

### Step 3: Deploy to Cloud Run
```bash
# Use the new deployment command in PR comments
/deploy-cloud-run development

# Or trigger via workflow dispatch with branch
# Go to Actions → Deploy to Cloud Run → Run workflow
```

### Step 4: Test the deployment
The deployment will automatically run health checks. You can also test manually:

```bash
# Get service URLs
API_URL=$(gcloud run services describe dev-assist-api \
  --region=asia-southeast1 \
  --format="value(status.url)")

FRONTEND_URL=$(gcloud run services describe dev-assist-frontend \
  --region=asia-southeast1 \
  --format="value(status.url)")

# Test endpoints
curl "$API_URL/api/v1/ping"
curl "$FRONTEND_URL/health"
```

## Key Features

### Automatic Scaling
- **Cold starts**: ~2-3 seconds (first request after idle)
- **Scale to zero**: No cost when not in use
- **Auto-scaling**: Handles traffic spikes automatically

### Security Enhancements
- **Runtime secrets**: Secrets fetched at runtime, not baked into images
- **IAM integration**: Fine-grained access controls
- **Audit trails**: All secret access logged
- **No SSH keys**: Eliminates SSH-based attack vectors

### Performance Optimizations
- **Parallel builds**: True parallelism with GitHub Actions matrix
- **BuildKit caching**: Layer caching across builds
- **Regional deployment**: Asia-Southeast1 for optimal latency
- **HTTP/2 support**: Built-in with Cloud Run

## Development Workflow

### PR-based Deployments
```bash
# In PR comments, use:
/deploy-cloud-run                    # Deploy to development
/deploy-cloud-run staging           # Deploy to staging
/deploy-cloud-run production        # Deploy to production
```

### Branch-based Deployments
Use GitHub Actions workflow dispatch for direct branch deployments.

## Monitoring & Debugging

### View Logs
```bash
# API service logs
gcloud run services logs read dev-assist-api --region=asia-southeast1

# Frontend service logs
gcloud run services logs read dev-assist-frontend --region=asia-southeast1

# Real-time logs
gcloud run services logs tail dev-assist-api --region=asia-southeast1
```

### View Metrics
```bash
# List all services
gcloud run services list --region=asia-southeast1

# Get service details
gcloud run services describe dev-assist-api --region=asia-southeast1
```

### Update Services
```bash
# Update with new image
gcloud run services update dev-assist-api \
  --image=asia-southeast1-docker.pkg.dev/PROJECT/dev-assist/api:new-tag \
  --region=asia-southeast1

# Update environment variables
gcloud run services update dev-assist-api \
  --set-env-vars="LOG_LEVEL=DEBUG" \
  --region=asia-southeast1
```

## Rollback Procedure

### Automatic Rollback
Cloud Run maintains previous revisions. To rollback:

```bash
# List revisions
gcloud run revisions list --service=dev-assist-api --region=asia-southeast1

# Route traffic to previous revision
gcloud run services update-traffic dev-assist-api \
  --to-revisions=REVISION_NAME=100 \
  --region=asia-southeast1
```

### Emergency Rollback
```bash
# Quick rollback to previous revision
gcloud run services update-traffic dev-assist-api \
  --to-latest=false \
  --region=asia-southeast1
```

## Cost Monitoring

### Enable Billing Alerts
1. Go to Google Cloud Console → Billing
2. Set up budget alerts for your project
3. Monitor Cloud Run usage in billing reports

### Cost Optimization Tips
- **Scale to zero**: Ensure services scale to zero when not in use
- **Right-size resources**: Adjust CPU/memory allocation based on usage
- **Use regions wisely**: Deploy in regions closest to users
- **Monitor cold starts**: Optimize if cold start frequency is too high

## Troubleshooting

### Common Issues

#### Service Won't Start
```bash
# Check logs for startup errors
gcloud run services logs read SERVICE_NAME --region=asia-southeast1 --limit=50

# Check service configuration
gcloud run services describe SERVICE_NAME --region=asia-southeast1
```

#### Secret Access Issues
```bash
# Verify service account has secret access
gcloud secrets get-iam-policy SECRET_NAME

# Grant access if needed
gcloud secrets add-iam-policy-binding SECRET_NAME \
  --member='serviceAccount:SERVICE_ACCOUNT@PROJECT.iam.gserviceaccount.com' \
  --role='roles/secretmanager.secretAccessor'
```

#### Build Failures
- Check Artifact Registry permissions
- Verify BuildKit cache access
- Review build logs in GitHub Actions

## Support

For issues with Cloud Run migration:
1. Check service logs first
2. Review this migration guide
3. Check GitHub Actions workflow logs
4. Contact the development team

## Next Steps

After successful migration:
1. **Monitor performance** for first week
2. **Update documentation** with new URLs
3. **Decommission VM** deployment (keep as backup initially)
4. **Set up monitoring alerts** for the new services
5. **Train team** on new deployment workflow

## Comparison Summary

| Aspect | VM Deployment | Cloud Run |
|--------|---------------|-----------|
| **Cost** | $12-15/month | $2-8/month |
| **Scaling** | Manual | Automatic |
| **Management** | High (SSH, patching) | None (serverless) |
| **Deployment Time** | 5-10 minutes | 2-3 minutes |
| **Cold Starts** | None | 2-3 seconds |
| **Security** | VM-based | Container-native |
| **Monitoring** | Custom setup | Built-in |
| **Rollback** | Manual | Automatic |